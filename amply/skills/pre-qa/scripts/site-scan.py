#!/usr/bin/env python3
"""
site-scan.py — the site-wide half of /amply:pre-qa.

Crawls every page reachable from the start URL and runs every check that can be
answered from the SERVED HTML: links, image formats and wrapped-bitmap SVGs, meta,
headings, placeholder copy. It does NOT open a browser, so it scales to a whole site.

The rendered checks a browser is genuinely required for — horizontal overflow, computed
contrast, intrinsic-vs-rendered image size, clipped text, console errors — are sampled
separately on a handful of pages. See SKILL.md Step 4.

usage: python3 site-scan.py https://site.webflow.io [--max 200] [--out scan.json]
"""
import sys, json, re, time, argparse, urllib.parse as up
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 pre-qa"}
TIMEOUT = 20

PLACEHOLDER_TEXT = re.compile(
    r"lorem ipsum|dolor sit amet|consectetur|your text here|sample text|\btbd\b|\btodo\b"
    r"|xxx+|client name|placeholder", re.I)
PLACEHOLDER_ASSET = re.compile(
    r"placeholder|plus\.svg|image-placeholder|picsum|unsplash|dummy|lorem", re.I)
WF_DEFAULT_COPY = re.compile(
    r">\s*(Heading|Paragraph|Button|Text Link|List Item|"
    r"This is some text inside of a div block)\.?\s*<", re.I)


def fetch(url, want_bytes=False, method="GET"):
    """Return (status, body, final_url). status 0 on network failure."""
    try:
        req = Request(url, headers=UA, method=method)
        with urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read() if method == "GET" else b""
            return r.status, (raw if want_bytes else raw.decode("utf-8", "replace")), r.url
    except HTTPError as e:
        return e.code, "", url
    except (URLError, OSError, ValueError) as e:
        return 0, str(e), url


def finding_key(flag, subject):
    """Stable identifier a human decision can reattach to across runs.

    Keys must survive re-crawls, re-orderings and count changes, so they are built from
    things that do not move: asset filenames, Webflow page/collection ids, URL paths.
    CSS-path keys (contrast, layout) are inherently fragile — a class rename orphans them,
    so decisions matched on those are reported as POSSIBLY STALE rather than reapplied.
    """
    s = str(subject)
    if s.startswith("http"):
        p = up.urlparse(s)
        s = p.path.rsplit("/", 1)[-1] if re.search(r"\.\w{2,5}$", p.path) else (p.path or "/")
        s = up.unquote(s)
        s = re.sub(r"^[0-9a-f]{24}_", "", s)      # strip the Webflow asset-id prefix
    return f"{flag}:{s}"


FRAGILE_KEY = re.compile(r"^(CONTRAST_FAIL|TEXT_CLIPPED|ZERO_HEIGHT|HORIZONTAL_OVERFLOW|COLLAPSED_EMPTY):")


def strip_tags(h):
    h = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", h, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", h)


def parse_page(url, html):
    """Every check answerable from static HTML."""
    def meta(name):
        m = re.search(r'<meta[^>]+(?:name|property)=["\']%s["\'][^>]*content=["\']([^"\']*)'
                      % re.escape(name), html, re.I)
        if not m:
            m = re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:name|property)=["\']%s["\']'
                          % re.escape(name), html, re.I)
        return m.group(1) if m else None

    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    canon = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', html, re.I)
    heads = [(int(m.group(1)), re.sub(r"\s+", " ", strip_tags(m.group(2))).strip()[:70])
             for m in re.finditer(r"<h([1-6])\b[^>]*>(.*?)</h\1>", html, re.S | re.I)]
    order = [h[0] for h in heads]
    skips, prev = [], 0
    for lvl in order:
        if prev and lvl > prev + 1:
            skips.append(f"{prev}->{lvl}")
        prev = lvl

    imgs = []
    for m in re.finditer(r"<img\b([^>]*)>", html, re.I):
        a = m.group(1)
        src = re.search(r'\ssrc=["\']([^"\']+)', a)
        if not src:
            continue
        imgs.append({
            "src": up.urljoin(url, src.group(1)),
            "alt": (re.search(r'\salt=["\']([^"\']*)', a) or [None, None])[1]
                   if re.search(r'\salt=', a) else None,
            "srcset": bool(re.search(r"\ssrcset=", a)),
            "lazy": bool(re.search(r'loading=["\']lazy', a)),
        })

    links = []
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", html, re.S | re.I):
        a, inner = m.group(1), m.group(2)
        href = re.search(r'\shref=["\']([^"\']*)', a)
        if href is None:
            links.append({"href": None, "abs": None, "text": "", "blank": False,
                          "noopener": False, "has_media": False, "aria": False})
            continue
        raw = href.group(1)
        links.append({
            "href": raw,
            "abs": up.urljoin(url, raw) if raw and not raw.startswith(("#", "mailto:", "tel:", "javascript:")) else None,
            "text": re.sub(r"\s+", " ", strip_tags(inner)).strip()[:60],
            "blank": 'target="_blank"' in a or "target='_blank'" in a,
            "noopener": "noopener" in a,
            "has_media": bool(re.search(r"<(img|svg)\b", inner, re.I)),
            "aria": bool(re.search(r"aria-label=", a)),
        })

    body_text = re.sub(r"\s+", " ", strip_tags(html))
    ids = set(re.findall(r'\sid=["\']([^"\']+)', html))

    return {
        "url": url,
        "title": (title.group(1).strip() if title else None),
        "description": meta("description"),
        "canonical": canon.group(1) if canon else None,
        "robots": meta("robots"),
        "og_image": meta("og:image"),
        "og_title": meta("og:title"),
        "lang": (re.search(r"<html[^>]+lang=[\"']([^\"']+)", html) or [None, None])[1]
                if re.search(r"<html[^>]+lang=", html) else None,
        "json_ld": len(re.findall(r'type=["\']application/ld\+json', html)),
        "h1": [h[1] for h in heads if h[0] == 1],
        "heading_skips": skips,
        "images": imgs,
        "links": links,
        "ids": ids,
        "lorem": sorted(set(m.group(0) for m in PLACEHOLDER_TEXT.finditer(body_text)))[:5],
        "wf_default_copy": sorted(set(m.group(1) for m in WF_DEFAULT_COPY.finditer(html)))[:5],
        "bytes": len(html),
    }


def crawl(start, cap):
    origin = up.urlparse(start).netloc
    seen, queue, pages, failed = set(), [start.rstrip("/") + "/"], {}, {}

    def norm(u):
        p = up.urlparse(u)
        if p.netloc != origin or p.scheme not in ("http", "https"):
            return None
        if re.search(r"\.(png|jpe?g|svg|webp|avif|gif|pdf|zip|css|js|xml|ico|txt|mp4|woff2?)$", p.path, re.I):
            return None
        path = p.path or "/"
        if len(path) > 1:
            path = path.rstrip("/")          # /contact-us/ and /contact-us are ONE page.
        return up.urlunparse((p.scheme, p.netloc, path, "", "", ""))

    while queue and len(pages) < cap:
        batch, queue = queue[:8], queue[8:]
        batch = [b for b in batch if b not in seen]
        for b in batch:
            seen.add(b)
        if not batch:
            continue
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(lambda u: (u,) + fetch(u), batch))
        for url, status, html, final in results:
            if status != 200 or not html:
                failed[url] = status
                continue
            pg = parse_page(url, html)
            pages[url] = pg
            for l in pg["links"]:
                if l["abs"]:
                    n = norm(l["abs"])
                    if n and n not in seen and n not in queue and len(pages) + len(queue) < cap:
                        queue.append(n)
        print(f"  crawled {len(pages)} · queued {len(queue)}", file=sys.stderr)
        time.sleep(0.15)
    return pages, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("--max", type=int, default=200)
    ap.add_argument("--out", default="scan.json")
    args = ap.parse_args()

    print("crawling…", file=sys.stderr)
    pages, crawl_failed = crawl(args.start, args.max)
    origin = up.urlparse(args.start).netloc

    # ---- links: dedupe across the whole site, then status-check once each ----
    link_owners, flagged = {}, []
    for pg in pages.values():
        for l in pg["links"]:
            raw = l["href"]
            f = []
            if raw is None or raw == "":
                f.append("NO_HREF")
            elif raw == "#":
                f.append("HASH_ONLY")
            elif raw.startswith("#"):
                if raw[1:] not in pg["ids"]:
                    f.append("DEAD_ANCHOR")
            elif raw.startswith("http://"):
                f.append("INSECURE_HTTP")
            elif re.match(r"^(mailto|tel):", raw, re.I):
                if not re.match(r"^(mailto:[^@\s]+@[^@\s.]+\.\w+(\?[^\s]*)?|tel:\+?[\d\-().\s]{6,})$", raw, re.I):
                    f.append("MALFORMED_" + raw.split(":")[0].upper())
            elif re.search(r"localhost|127\.0\.0|\.local"
                           r"|figma\.com/(file|design|proto|board)"
                           r"|dropbox\.com/(s|scl)/|drive\.google\.com/(file|drive)", raw, re.I):
                f.append("DEV_URL")   # a figma.com *article* link is editorial, not a leftover
            if "webflow.io" in (raw or "") and raw.startswith("http"):
                f.append("STAGING_URL_HARDCODED")
            if l["blank"] and not l["noopener"]:
                f.append("BLANK_NO_NOOPENER")
            if not l["text"] and not l["has_media"] and not l["aria"]:
                f.append("EMPTY_LINK_TEXT")
            elif l["has_media"] and not l["text"] and not l["aria"]:
                f.append("ICON_LINK_NO_LABEL")
            if f:
                flagged.append({"page": pg["url"], "href": raw, "text": l["text"], "flags": f,
                                "keys": [finding_key(x, raw or pg["url"]) for x in f]})
            if l["abs"]:
                link_owners.setdefault(l["abs"], set()).add(pg["url"])

    print(f"status-checking {len(link_owners)} unique links…", file=sys.stderr)
    def head(u):
        s, _, final = fetch(u, method="GET")
        return u, s, final
    with ThreadPoolExecutor(max_workers=10) as ex:
        statuses = {u: (s, f) for u, s, f in ex.map(head, sorted(link_owners))}

    # 401/403/999 usually means the host blocks bots (LinkedIn, WSJ, Gartner, Cloudflare),
    # not that the link is dead. Keep them apart or the report cries wolf.
    BOT_BLOCK = {401, 403, 429, 999}
    broken, unverifiable = [], []
    for u, (s, f) in statuses.items():
        rec = {"url": u, "status": s, "on_pages": sorted(link_owners[u])[:6],
               "count": len(link_owners[u]),
               "internal": up.urlparse(u).netloc == origin}
        if s in BOT_BLOCK:
            unverifiable.append(rec)
        elif s >= 400 or s == 0:
            broken.append(rec)

    # ---- images: dedupe, then fetch every SVG once ----
    img_owners = {}
    for pg in pages.values():
        for im in pg["images"]:
            e = img_owners.setdefault(im["src"], {"pages": set(), "alt_missing": 0,
                                                  "no_srcset": 0, "n": 0})
            e["pages"].add(pg["url"])
            e["n"] += 1
            if im["alt"] is None:
                e["alt_missing"] += 1
            if not im["srcset"]:
                e["no_srcset"] += 1

    svgs = [u for u in img_owners if u.lower().split("?")[0].endswith(".svg")]
    print(f"scanning {len(svgs)} unique SVGs for wrapped bitmaps…", file=sys.stderr)
    def scan_svg(u):
        s, body, _ = fetch(u, want_bytes=True)
        if s != 200:
            return u, {"status": s, "flags": ["FETCH_FAILED"], "bytes": 0}
        t = body.decode("utf-8", "replace")
        f = []
        if re.search(r"data:image/(png|jpe?g)", t, re.I):
            f.append("WRAPPED_BITMAP")
        elif re.search(r"<image\b", t, re.I):
            f.append("EXTERNAL_RASTER")
        if re.search(r"feGaussianBlur|feDropShadow", t, re.I):
            f.append("BLUR_FILTER")
        if len(body) > 102400:
            f.append("HUGE")
        return u, {"status": s, "flags": f, "bytes": len(body),
                   "keys": [finding_key(x, u) for x in f]}
    with ThreadPoolExecutor(max_workers=8) as ex:
        svg_results = dict(ex.map(scan_svg, svgs))

    # ---- per-page SEO ----
    titles, descs = {}, {}
    for pg in pages.values():
        if pg["title"]:
            titles.setdefault(pg["title"], []).append(pg["url"])
        if pg["description"]:
            descs.setdefault(pg["description"], []).append(pg["url"])

    seo = []
    for pg in sorted(pages.values(), key=lambda p: p["url"]):
        f = []
        if not pg["title"]:
            f.append("NO_TITLE")
        elif len(titles.get(pg["title"], [])) > 1:
            f.append("DUPLICATE_TITLE")
        if not pg["description"]:
            f.append("NO_DESCRIPTION")
        elif len(descs.get(pg["description"], [])) > 1:
            f.append("DUPLICATE_DESCRIPTION")
        if not pg["canonical"]:
            f.append("NO_CANONICAL")
        elif origin in (pg["canonical"] or ""):
            f.append("CANONICAL_POINTS_AT_STAGING")
        if len(pg["h1"]) == 0:
            f.append("NO_H1")
        elif len(pg["h1"]) > 1:
            f.append(f"MULTIPLE_H1_{len(pg['h1'])}")
        if pg["heading_skips"]:
            f.append("HEADING_SKIP")
        if not pg["og_image"]:
            f.append("NO_OG_IMAGE")
        if pg["lorem"]:
            f.append("LOREM")
        if pg["wf_default_copy"]:
            f.append("WEBFLOW_DEFAULT_COPY")
        if f:
            seo.append({"url": pg["url"], "flags": f, "h1_count": len(pg["h1"]),
                        "lorem": pg["lorem"], "default_copy": pg["wf_default_copy"],
                        "keys": [finding_key(x, pg["url"]) for x in f]})

    # One nav dropdown repeated across 256 pages is ONE defect, not 256. Group by
    # (href, flags) and carry the page count, otherwise the report is unreadable noise.
    grouped = {}
    for l in flagged:
        key = f"{l['href']}||{','.join(sorted(l['flags']))}"
        g = grouped.setdefault(key, {"href": l["href"], "text": l["text"],
                                     "flags": sorted(l["flags"]), "pages": []})
        g["pages"].append(l["page"])
    for g in grouped.values():
        g["page_count"] = len(g["pages"])
        g["global"] = g["page_count"] > len(pages) * 0.5   # lives in nav/footer
        g["pages"] = sorted(g["pages"])[:4]

    out = {
        "start": args.start,
        "pages_crawled": len(pages),
        "crawl_failed": crawl_failed,
        "links_unique": len(link_owners),
        "links_broken": sorted(broken, key=lambda b: -b["count"]),
        "links_flagged_grouped": grouped,
        "links_unverifiable": sorted(unverifiable, key=lambda b: -b["count"]),
        "links_flagged_instances": len(flagged),
        "images_unique": len(img_owners),
        "svgs_unique": len(svgs),
        "svg_issues": {u: v for u, v in svg_results.items() if v["flags"]},
        "placeholder_assets": [u for u in img_owners if PLACEHOLDER_ASSET.search(u)],
        "alt_missing": sorted(
            [{"src": u, "pages": len(e["pages"])} for u, e in img_owners.items() if e["alt_missing"]],
            key=lambda x: -x["pages"])[:40],
        "seo": seo,
        "page_list": sorted(pages),
        "all_keys": sorted({k for grp in (flagged, seo) for it in grp for k in it["keys"]}
                           | {k for v in svg_results.values() for k in v.get("keys", [])}),
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1, default=list)

    wb = [u for u, v in svg_results.items() if "WRAPPED_BITMAP" in v["flags"]]
    wb_bytes = sum(svg_results[u]["bytes"] for u in wb)
    lf = {}
    for l in flagged:
        for x in l["flags"]:
            lf[x] = lf.get(x, 0) + 1
    lf_grouped = {k: v for k, v in
                  sorted(((k, len(v)) for k, v in out["links_flagged_grouped"].items()),
                         key=lambda kv: -kv[1])}

    print(f"""
================ SITE SCAN ================
pages crawled        {len(pages)}   (failed: {len(crawl_failed)})
unique links         {len(link_owners)}
BROKEN LINKS         {len(broken)}   (+{len(unverifiable)} bot-blocked, verify by hand)
unique images        {len(img_owners)}
unique SVGs          {len(svgs)}
WRAPPED BITMAPS      {len(wb)}  ({wb_bytes/1048576:.1f} MB)
placeholder assets   {len(out['placeholder_assets'])}
pages with SEO flags {len(seo)} / {len(pages)}
distinct link defects {len(grouped)}  (from {len(flagged)} instances across the site)
link flags           {json.dumps(lf_grouped, indent=1)}
stable finding keys  {len(out['all_keys'])}
written to           {args.out}
===========================================""", file=sys.stderr)


if __name__ == "__main__":
    main()
