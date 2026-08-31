---
description: Pre-QA audit of a published Webflow site — broken links, blurry/wrong-format images, layout breaks, meta, a11y, console errors
argument-hint: <staging-url> [--for internal|client]
---

# /pre-qa — run this before any handover, internal or client

**Arguments:** `$ARGUMENTS` — the published staging URL, plus optional `--for internal|client`.
The `site_id` is resolved from the URL; don't ask for it.

You are running the **pre-QA gate**. Nothing goes to a client until this passes. The check
catalogue, thresholds and severities live in [`reference/checks.md`](reference/checks.md) — **read it first**, it is the
source of truth for what counts as a Blocker. The remedy for every flag lives in
[`reference/fixes.md`](reference/fixes.md) — **read that before writing the report**, so each finding ships with a fix
the dev can act on rather than a flag name they have to decode.

Two things to hold onto:

1. **This is a *rendered* check, not an API check.** `starter-lint` reads the API and verifies
   *intent*; this verifies *result*. Every bug this exists to catch — a blurry logo, a link to
   `#`, a section overflowing at 375px — is invisible to the API. If you find yourself checking
   a class name instead of a pixel, you are in the wrong tool.
2. **Report, don't fix.** Produce the report, propose fixes, and stop. Writes to the site
   (`compress_assets`, `update_asset`, `update_page_settings`) happen only after the dev says go —
   see Step 7.

---

## The shape of a run: whole site statically, a sample in the browser

Two tiers, and the split is not a shortcut — it's what each tool can actually answer.

| | **Tier 1 — site-wide** | **Tier 2 — rendered sample** |
|---|---|---|
| How | `scripts/site-scan.py`, plain HTTP | the browser, page by page |
| Covers | **every page** | ~5–8 representative pages |
| Answers | links, SVG/asset formats, meta, headings, placeholder copy | overflow, computed contrast, intrinsic-vs-rendered size, clipped text, console errors |
| Cost | ~3 min for 300 pages | ~2 min per page |

Anything answerable from the **served HTML** scales to the whole site, so there is no excuse
for auditing one page. Only the checks that need a live layout engine get sampled — and the
report must say which pages those were.

## Surface: this runs in the terminal or desktop app, not on the web

Two reasons, and the second is the one that can't be configured away:

1. **Plugins are terminal/desktop only.** Claude Code on the web states plainly that commands
   which only run in the terminal interface, `/plugin` among them, aren't available.
2. **Every Webflow staging domain disallows crawling.** `*.webflow.io/robots.txt` serves
   `User-agent: * / Disallow: /` — verified on two separate staging sites. A cloud session's
   fetch honours robots.txt and returns `ROBOTS_DISALLOWED`, so **the site-wide tier cannot run
   there at all**, with or without the plugin.

`scripts/site-scan.py` uses `urllib` directly and does not consult robots.txt, which is why the
same crawl succeeds from a terminal.

> ⚠️ That is only appropriate because you own the site you are auditing. `Disallow: /` on a
> staging domain is aimed at third-party crawlers, not at the site's own team testing it before
> handover. **Never point this scanner at a site your team doesn't own or hasn't been asked to
> audit** — at that point you are ignoring someone else's stated wishes, not your own.

## Step 0 — Ask who this build is going to

**Before anything else, establish the audience: internal QA or client QA.** The checks are
identical; the verdict is not. If the dev didn't say, **ask** — never assume.

| | **Internal QA** | **Client QA** |
|---|---|---|
| Passes when | every blocker is fixed **or** carries a recorded justification | blocker count is **zero** |
| Justifications | lift a blocker for this gate | **do not lift anything** |
| The only way past a blocker | fix it, or justify it | fix it |

> **A justification never unblocks a client send.** It records *why* something is still open so
> the internal reviewer isn't rediscovering it — it is not a waiver. If a blocker is genuinely
> acceptable forever, that is a conversation about changing the build or the design, not a note
> on a report.

State the audience in the report header and in the verdict line, so nobody reads an
internal-QA pass as clearance to send the link to a client.

## Step 0 — Scope

- If no URL was given, ask for the published staging URL. **You cannot run this against the
  Designer** — it needs published HTML.
- Don't rely on `sitemap.xml`: Webflow staging often doesn't serve one (on a real client build it
  returned the 404 page). The scanner discovers pages by crawling links instead, which also surfaces
  pages a sitemap would have missed.
- Optionally cross-check the crawl against `data_pages_tool > get_pages_list`. A page in one and
  not the other is itself a finding — an orphan page is usually an unfinished one.

### Resolve the site_id yourself — never ask the dev for it

The staging subdomain **is** the site's `shortName`. Verified on two live sites:
`acme-stg.webflow.io` resolves via shortName `acme-stg` to that site's 24-character id.

1. Take the subdomain from the URL the dev gave you: `https://<shortName>.webflow.io`.
2. `data_sites_tool > list_sites {detail: "summary"}` and match on `shortName`.
3. On a large workspace the result exceeds the token limit and is written to a file — grep that
   file for the shortName rather than reading it. (This account has 300+ sites, so expect it.)

Only ask the dev if the match fails — a custom production domain, or a site renamed since it
was published.

> A Designer URL (`https://<workspace>-<hash>.design.webflow.com/…`) does **not** contain the
> site id. That hash is 29 characters; a Webflow site id is 24. Don't try to parse one.

## Step 0b — Read prior decisions

Before crawling, read what humans already ruled on:

`data_agent_instructions_tool > read_instruction` on `pre-qa/state/decisions.md` — **by path.**
The `name` filter on `search_instructions` is unreliable (it returned zero for a file named
`decisions.md` that an unfiltered search listed), so never go looking for this file by name.
On a first write, `pre-qa/SKILL.md` must be created *before* the companion file or the create
fails with an opaque HTTP 500.

Missing file = first run, carry on. Full format, statuses and the staleness rules:
[`reference/decisions.md`](reference/decisions.md). Three things that matter enough to repeat here:

- **A decision never silently suppresses a finding.** Decided findings move to a *Previously
  decided* section with the note and author; the headline keeps both numbers —
  `5 blockers (7 found, 2 previously decided)`. A report that can hide a blocker without trace
  is a mute button, not a gate.
- **Fragile keys are shown as possibly stale.** `CONTRAST_FAIL`, `TEXT_CLIPPED`,
  `ZERO_HEIGHT`, `HORIZONTAL_OVERFLOW` and `COLLAPSED_EMPTY` key on CSS paths that a class
  rename orphans. Never reapply those silently.
- **When a decided finding stops appearing**, mark the decision `stale` — don't delete it.

## Step 1 — Tier 1: scan the whole site

```bash
python3 scripts/site-scan.py https://site.webflow.io --max 300 --out scan.json
```

Stdlib only, no install. It crawls every reachable page and returns `scan.json` with:
links (deduped and status-checked), every unique SVG fetched and tested for wrapped bitmaps,
per-page meta/heading/placeholder findings, and missing alt text.

**Three things about reading its output:**

1. **`links_flagged_grouped`, never `links_flagged_instances`.** A nav dropdown on 304 pages is
   **one** defect, not 304. On a real run this collapsed **5,352 instances into 126 distinct
   defects**. Report the distinct defect with its page count; a report built from instance
   counts is unreadable and will be ignored.
2. **`global: true` means it lives in the nav or footer** — one fix, every page. Put those first:
   they're the cheapest wins on the whole site.
3. **`links_unverifiable` is not `links_broken`.** 401/403/429/999 usually means the host blocks
   bots — LinkedIn, WSJ, Gartner, Cloudflare-fronted sites. Only 404/410 and network failures
   are candidate defects. Spot-check a few unverifiable ones in the browser before saying a word
   about them.

## Step 2 — Tier 2: pick the browser sample

Choose 5–8 pages and **say in the report which ones**:

- the homepage
- the most structurally complex page (most sections, sliders, tabs)
- **one page per CMS template** — a broken binding breaks every item in the collection; check one
  and note how many items it affects
- any page Tier 1 flagged as an outlier (no title, lorem, the most placeholder assets)
- the contact page, because it has the form

## Step 3 — Per sampled page: load and settle

For each page, in the browser pane:

```
navigate → resize_window 1440 → force-load every image → settle
```

**Forcing the load is not optional.** Webflow lazy-loads images, and on a real build most of
them never enter the viewport at all — carousel slides, inactive tabs, marquee tracks. Scrolling
alone does not reach them: on a 17,700px page a full scroll pass still left 205 of 243 images
unloaded. Un-loaded images cannot be size-audited, and naively read as broken.

Run this first, and re-run it after every `resize_window`:

```js
(async()=>{const i=[...document.images];i.forEach(x=>x.loading='eager');
await Promise.all(i.map(x=>x.decode?x.decode().catch(()=>{}):null));
await new Promise(r=>setTimeout(r,500));
return{total:i.length,loaded:i.filter(x=>x.complete&&x.naturalWidth>0).length};})()
```

It loads a few hundred images in ~5s. Check the returned counts — if `loaded` is short of
`total`, say so in the report rather than letting un-evaluated images read as passes.

Also scroll the page top-to-bottom once, in bursts of ~10 steps, to fire scroll-triggered
reveals (GSAP/IX3 elements sitting at `opacity:0` are skipped by the audit). **Front the tab
first** (`tabs_select`) — a hidden tab throttles `setTimeout` to ~1/second and the scroll pass
will blow the 30s tool limit.

Then capture, before running the audit:
- `read_console_messages {onlyErrors: true}` — JS errors on load
- `read_network_requests` — any 4xx/5xx (missing assets, dead API calls, mixed content)

## Step 4 — Run the audit snippet

Run this via `javascript_tool` on each page, at each breakpoint (`resize_window` between runs).
It is deliberately **synchronous** — it collects facts only, no `fetch`, so CORS can't break it.
Link and SVG *verification* already happened site-wide in Step 1.

```js
(() => {
const out={url:location.href,vw:innerWidth,dpr:devicePixelRatio||1,ts:Date.now()};
const CS=el=>getComputedStyle(el);
const vis=el=>{const s=CS(el);return s.display!=='none'&&s.visibility!=='hidden'&&+s.opacity>0.05};
const sel=el=>{if(!el||!el.tagName)return'?';const c=[...el.classList].filter(x=>!/^w-/.test(x)).slice(0,2).join('.');
  return el.tagName.toLowerCase()+(c?'.'+c:'')+(el.id?'#'+el.id:'')};
const where=el=>{const p=[];let n=el;for(let i=0;i<4&&n&&n.tagName;i++){p.unshift(sel(n));n=n.parentElement}
  return p.join(' > ')};
const txt=el=>(el.textContent||'').trim().replace(/\s+/g,' ').slice(0,60);
const all=[...document.querySelectorAll('body *')].filter(vis);

// ── 1. HORIZONTAL OVERFLOW ────────────────────────────────────────────
const de=document.documentElement;
out.overflow={page:de.scrollWidth-de.clientWidth,offenders:[]};
if(out.overflow.page>1){
  // Only RIGHTWARD overflow creates the scrollbar. Elements far to the left are almost always
  // marquee/carousel tracks moving by design — including them buries the real offender.
  const clipped=el=>{let n=el.parentElement;while(n&&n.nodeType===1){const o=CS(n);
    if(o.overflow==='hidden'||o.overflowX==='hidden')return true;n=n.parentElement}return false};
  for(const el of all){const r=el.getBoundingClientRect();
    if(r.width===0||r.height===0)continue;
    if(r.right>innerWidth+1){
      if(clipped(el))continue;                      // an ancestor already clips it
      const p=el.parentElement,pr=p?p.getBoundingClientRect():null;
      if(pr&&pr.right>innerWidth+1)continue;        // report only the outermost of a chain
      out.overflow.offenders.push({el:where(el),right:Math.round(r.right),left:Math.round(r.left),w:Math.round(r.width),text:txt(el)});
    }}
  out.overflow.offenders=out.overflow.offenders.slice(0,15);
}

// ── 2. IMAGES: blurry / broken / oversized / format ───────────────────
out.images=[];
for(const img of document.querySelectorAll('img')){
  if(!vis(img))continue;
  const r=img.getBoundingClientRect(); if(r.width<2)continue;
  const src=img.currentSrc||img.src||'';
  const dpr=devicePixelRatio||1;
  const rec={el:where(img),src:src.split('?')[0],alt:img.getAttribute('alt'),
    rendered:Math.round(r.width)+'x'+Math.round(r.height),
    natural:img.naturalWidth+'x'+img.naturalHeight,
    // ratioCss<1 = blurry on ANY screen. ratioDpr<1 = only soft on retina.
    ratioCss:img.naturalWidth?+(img.naturalWidth/r.width).toFixed(2):0,
    ratioDpr:img.naturalWidth?+(img.naturalWidth/(r.width*dpr)).toFixed(2):0,
    srcset:!!img.srcset,loading:img.loading||'',flags:[]};
  const ext=(rec.src.match(/\.(svg|png|jpe?g|webp|avif|gif)(?=$|\?)/i)||[])[1]||'';
  if(!src)rec.flags.push('NO_SRC');
  // A lazy image that never entered the viewport is NOT broken — it just never loaded.
  // Without this guard every off-screen image reports BROKEN. Verified on a real build:
  // 157 false positives out of 157. Force-load in Step 1 so this rarely fires.
  else if(!img.complete)rec.flags.push('NOT_LOADED');
  else if(img.naturalWidth===0)rec.flags.push('BROKEN');
  else if(ext.toLowerCase()!=='svg'){
    if(rec.ratioCss<0.95)rec.flags.push('BLURRY');
    else if(rec.ratioDpr<0.8)rec.flags.push('SOFT_ON_RETINA');
    if(rec.ratioDpr>2)rec.flags.push('OVERSIZED');
    if(!img.srcset&&r.width>320)rec.flags.push('NO_SRCSET');
  }
  if(ext.toLowerCase()==='svg')rec.flags.push('IS_SVG'); // verified site-wide in Step 1
  if(/placeholder|plus\.svg|image-placeholder|lorem|picsum|unsplash|dummy|\/1x1\./i.test(rec.src))rec.flags.push('PLACEHOLDER_ASSET');
  try{const h=new URL(src,location.href).host;
    if(h!==location.host&&!/(website-files\.com|webflow\.com)$/i.test(h))rec.flags.push('OFFSITE_ASSET:'+h);}catch(e){}
  if(rec.alt===null)rec.flags.push('ALT_MISSING');
  if(rec.flags.length)out.images.push(rec);
}
// background-images get the same treatment (no natural size available — flag for curl)
out.bgImages=[];
for(const el of all){const b=CS(el).backgroundImage;
  if(!b||b==='none'||!/url\(/.test(b))continue;
  const u=(b.match(/url\(["']?(.*?)["']?\)/)||[])[1]||'';
  if(!u||u.startsWith('data:'))continue;
  const r=el.getBoundingClientRect();
  out.bgImages.push({el:where(el),src:u.split('?')[0],rendered:Math.round(r.width)+'x'+Math.round(r.height)});
}

// ── 3. INLINE SVG: blur filters, embedded raster ──────────────────────
out.svgIssues=[];
for(const s of document.querySelectorAll('svg')){
  if(!vis(s))continue;const f=[];
  if(s.querySelector('feGaussianBlur,feDropShadow'))f.push('BLUR_FILTER');
  if(s.querySelector('image'))f.push('EMBEDDED_RASTER');
  if(s.outerHTML.length>60000)f.push('HUGE_INLINE_'+Math.round(s.outerHTML.length/1024)+'KB');
  if(f.length)out.svgIssues.push({el:where(s),flags:f});
}

// ── 4. LINKS ──────────────────────────────────────────────────────────
out.links=[];const seen=new Set();
for(const a of document.querySelectorAll('a')){
  const raw=a.getAttribute('href'),f=[];
  if(raw===null||raw==='')f.push('NO_HREF');
  else if(raw==='#')f.push('HASH_ONLY');
  else if(/^#/.test(raw)&&!document.querySelector('[id="'+CSS.escape(raw.slice(1))+'"]'))f.push('DEAD_ANCHOR');
  else if(/^http:\/\//i.test(raw))f.push('INSECURE_HTTP');
  else if(/webflow\.io/i.test(raw))f.push('STAGING_URL');
  else if(/^(mailto|tel):/i.test(raw)){if(!/^(mailto:[^@\s]+@[^@\s.]+\.\w+(\?[^\s]*)?|tel:\+?[\d\-().\s]{6,})$/i.test(raw))f.push('MALFORMED_'+raw.split(':')[0].toUpperCase())}
  else if(/localhost|127\.0\.0|\.local|figma\.com|dropbox|drive\.google/i.test(raw))f.push('DEV_URL');
  if(a.target==='_blank'&&!/noopener/.test(a.rel||''))f.push('BLANK_NO_NOOPENER');
  if(!txt(a)&&!a.querySelector('img,svg')&&!a.getAttribute('aria-label'))f.push('EMPTY_LINK_TEXT');
  if(a.querySelector('img,svg')&&!txt(a)&&!a.getAttribute('aria-label'))f.push('ICON_LINK_NO_LABEL');
  const key=raw+'|'+f.join(',');
  if(f.length&&!seen.has(key)){seen.add(key);
    out.links.push({el:where(a),href:raw,text:txt(a),target:a.target||'',flags:f})}
}
// every unique outbound href, for curl in Step 3
out.hrefs=[...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href)
  .filter(h=>/^https?:/.test(h)))].sort();

// ── 5. PLACEHOLDER / DEFAULT CONTENT ──────────────────────────────────
const PLACE=/lorem ipsum|dolor sit amet|consectetur|placeholder|your text here|sample text|\btbd\b|\btodo\b|xxx+|coming soon|client name|lorem/i;
const WFDEF=/^(heading( \d)?|paragraph|button|text link|link block|list item|name|email|submit|this is some text inside of a div block)$/i;
out.placeholders=[];
for(const el of all){
  if(el.children.length)continue;const t=txt(el);if(!t)continue;
  if(PLACE.test(t))out.placeholders.push({el:where(el),text:t,flag:'LOREM'});
  else if(WFDEF.test(t))out.placeholders.push({el:where(el),text:t,flag:'WEBFLOW_DEFAULT_COPY'});
}
out.placeholders=out.placeholders.slice(0,25);

// ── 6. CLIPPED / COLLAPSED / EMPTY ────────────────────────────────────
out.boxIssues=[];
for(const el of all){
  const s=CS(el),r=el.getBoundingClientRect();
  if((s.overflow==='hidden'||s.overflowY==='hidden')&&el.scrollHeight>el.clientHeight+2&&el.clientHeight>0&&txt(el))
    out.boxIssues.push({el:where(el),flag:'TEXT_CLIPPED',text:txt(el),vis:el.clientHeight,real:el.scrollHeight});
  // Skip anything inside a collapsed container (closed dropdown, inactive tab, accordion):
  // its zero height is intentional, not a layout failure.
  if(r.height===0&&el.children.length===0&&txt(el)&&!(()=>{let n=el.parentElement;
      while(n&&n.nodeType===1){if(n.getBoundingClientRect().height===0)return true;n=n.parentElement}return false})())
    out.boxIssues.push({el:where(el),flag:'ZERO_HEIGHT_WITH_TEXT',text:txt(el)});
  if(/^(section|div)$/i.test(el.tagName)&&r.height>0&&r.height<4&&!txt(el)&&!el.children.length)
    out.boxIssues.push({el:where(el),flag:'COLLAPSED_EMPTY'});
}
out.boxIssues=out.boxIssues.slice(0,25);

// ── 7. WEBFLOW DEFAULT CLASS NAMES (rendered evidence) ────────────────
out.defaultClasses=[...new Set([...document.querySelectorAll('[class]')]
  .flatMap(el=>[...el.classList])
  .filter(c=>/^(div-block|section-\d|heading-\d|paragraph-\d|text-block|link-block|image-\d|container-\d|button-\d|grid-\d|columns-\d|bold-text|italic-text)/i.test(c)))];

// ── 8. HEADINGS + META + SEO ──────────────────────────────────────────
const h1=[...document.querySelectorAll('h1')].filter(vis);
const meta=n=>{const m=document.querySelector('meta[name="'+n+'"],meta[property="'+n+'"]');return m?m.content:null};
out.seo={title:document.title||null,titleLen:(document.title||'').length,
  desc:meta('description'),descLen:(meta('description')||'').length,
  canonical:(document.querySelector('link[rel=canonical]')||{}).href||null,
  robots:meta('robots'),ogTitle:meta('og:title'),ogDesc:meta('og:description'),
  ogImage:meta('og:image'),  // og:image only — twitter:card is deliberately not checked
  favicon:!!document.querySelector('link[rel~="icon"]'),
  jsonLd:document.querySelectorAll('script[type="application/ld+json"]').length,
  h1Count:h1.length,h1Text:h1.map(txt),
  headingOrder:[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map(h=>+h.tagName[1]),
  lang:document.documentElement.lang||null};
{let prev=0,skips=[];for(const l of out.seo.headingOrder){if(prev&&l>prev+1)skips.push(prev+'→'+l);prev=l}
 out.seo.headingSkips=skips}

// ── 9. FORMS ──────────────────────────────────────────────────────────
out.forms=[...document.querySelectorAll('form')].map(f=>({
  el:where(f),action:f.getAttribute('action')||'(webflow default)',method:f.method,
  name:f.getAttribute('name')||f.getAttribute('data-name')||null,
  fields:[...f.querySelectorAll('input,select,textarea')].filter(i=>i.type!=='hidden').map(i=>({
    name:i.name||null,type:i.type,required:i.required,
    labelled:!!(f.querySelector('label[for="'+CSS.escape(i.id||'~')+'"]')||i.closest('label')||i.getAttribute('aria-label')||i.placeholder)})),
  hasSuccess:!!f.parentElement.querySelector('.w-form-done'),
  hasError:!!f.parentElement.querySelector('.w-form-fail')}));

// ── 10. CONTRAST (computed, WCAG AA) ──────────────────────────────────
const lum=c=>{const m=c.match(/[\d.]+/g);if(!m)return null;
  const [r,g,b]=m.slice(0,3).map(v=>{v=v/255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});
  return 0.2126*r+0.7152*g+0.0722*b};
const bgOf=el=>{let n=el;while(n&&n.nodeType===1){const s=CS(n);
  if(s.backgroundImage&&s.backgroundImage!=='none')return null;
  const a=(s.backgroundColor.match(/[\d.]+/g)||[])[3];
  if(s.backgroundColor!=='transparent'&&a!=='0')return s.backgroundColor;n=n.parentElement}
  return 'rgb(255,255,255)'};
out.contrast=[];
for(const el of all){
  if(el.children.length||!txt(el))continue;
  const s=CS(el),bg=bgOf(el);if(!bg)continue;
  const l1=lum(s.color),l2=lum(bg);if(l1===null||l2===null)continue;
  const ratio=+(((Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05))).toFixed(2);
  const px=parseFloat(s.fontSize),bold=+s.fontWeight>=700;
  const min=(px>=24||(px>=18.66&&bold))?3:4.5;
  if(ratio<min)out.contrast.push({el:where(el),text:txt(el),fg:s.color,bg,ratio,min,size:px});
}
out.contrast=out.contrast.slice(0,20);

// ── 11. SCRIPTS / LIBS ACTUALLY LOADED ────────────────────────────────
out.libs={gsap:!!window.gsap,scrollTrigger:!!(window.gsap&&window.ScrollTrigger),
  swiper:!!window.Swiper,jquery:!!window.jQuery,webflow:!!window.Webflow,
  fsAttributes:!!window.fsAttributes,
  scriptSrcs:[...document.querySelectorAll('script[src]')].map(s=>s.src.split('?')[0])
    .filter(s=>!/webflow\.js|jquery/.test(s))};
out.libs.gsapUsed=out.libs.gsap?document.querySelectorAll('[data-gsap],[class*=anim]').length:0;
out.libs.swiperUsed=document.querySelectorAll('.swiper').length;
// coverage: never let un-evaluated images read as "passed"
out.coverage={imgsTotal:document.images.length,
  imgsEvaluated:[...document.images].filter(i=>i.complete&&i.naturalWidth>0).length,
  imgsNotLoaded:[...document.images].filter(i=>!i.complete).length};

return out;})()
```

## Step 5 — Spot-verify anything Tier 1 could not settle

Tier 1 already status-checked every link and tested every SVG site-wide. Use this step only for
what the crawler can't see: **CSS background images** (no intrinsic size in the DOM) and any
asset that appeared only after JS ran.

**Links** — batch the deduped `hrefs` from every page into one file, then:

```bash
sort -u /tmp/hrefs.txt | while read -r u; do printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -L --max-time 12 -A 'Mozilla/5.0' "$u")" "$u"; done
```

Read it as: `4xx/5xx` = **Blocker**. `000` = timeout/DNS — retry once, then flag. A `301` to a
*different* final URL on an internal link = fix the href (redirect chains are slow and leak
old paths). Some hosts (LinkedIn, Instagram, Cloudflare-fronted sites) 403/999 bots — verify
those manually in the browser before reporting them.

**SVGs and image weights** — for every `.svg` in the image list, and every image over the
weight threshold:

```bash
curl -sL --max-time 15 "$SVG_URL" -o /tmp/a.svg
wc -c < /tmp/a.svg
grep -o -E '<image|data:image/(png|jpe?g)|feGaussianBlur|feDropShadow|feImage|feTurbulence' /tmp/a.svg | sort | uniq -c
```

Decide:
- `<image` or `data:image/png|jpeg` inside an SVG → **the SVG is a wrapped bitmap.** This is
  the "blurry .svg" bug — it does not scale, and Webflow can't serve responsive variants of it.
  → re-export from Figma as PNG/WebP at 2×, or as a real vector if it should be one.
- `feGaussianBlur` / `feDropShadow` → Figma flattened a blur/shadow effect into a filter.
  Renders soft, inconsistently across browsers, and is expensive. → re-export without the
  effect and recreate it in CSS.
- SVG over ~100 KB → it is almost certainly a traced bitmap or an un-simplified illustration.
- Any raster over ~400 KB → flag for `compress_assets`.

## Step 6 — Breakpoint sweep

Re-run **Step 3 + Step 4** at each width. Full sweep on the homepage and the two most complex
pages; the overflow + image blocks only on the rest.

| Width | Why |
|---|---|
| 1920 | max-width containers, over-stretched backgrounds |
| 1440 | design baseline |
| 991 | Webflow tablet — first breakpoint most builds skip |
| 767 | Webflow mobile-landscape |
| 375 | the one that actually breaks — iPhone width |

**Read `out.vw` from the result, don't trust the preset.** The pane scales emulated viewports:
a `resize_window` to 375 came back measuring `innerWidth: 532` in testing. Report the width you
actually measured, and if it never reaches 375, say the narrowest tested width was wider.

`out.overflow.page > 1` at **any** width is a Blocker. Compare `out.images[].ratio` across
widths too — an image that is crisp at 1440 is often blurry at 375, where Webflow serves a
smaller srcset variant into a full-bleed slot.

Take a `screenshot` at 375 and 1440 per page and **look at it**. Some things only a look
catches: text on top of text, a card taller than its neighbours, an icon at 4× size, a
background that ran out. Attach the ones with problems to the report.

## Step 7 — The API-side pass (Webflow MCP)

Rendered checks can't see these. Run with the `site_id`:

- `data_pages_tool > get_pages_list` + `get_page_metadata` per page — title/description/OG set
  at the **page settings** level (a page can render a title inherited from the site default and
  still be misconfigured). Check every page has a **unique** title and description.
- `data_pages_tool > query_pages_schema_markup` — JSON-LD present where the build calls for it.
- `data_sitemap_tool > list_pages_sitemap_status` — utility/thank-you pages excluded, real
  pages included.
- `data_assets_tool > list_assets` — orphaned uploads, missing `altText`, duplicate uploads of
  the same file, and the raw file sizes behind Step 3.
- `data_forms_tool > list_forms` — every form on the site is registered and named (an unnamed
  or duplicate-named form silently loses submissions).
- `data_scripts_tool > get_site_scripts` + `get_page_scripts` — analytics/GTM applied **once**,
  no leftover dev scripts.
- `data_comments_tool > list_comment_threads {isResolved: false}` — **unresolved Designer
  comments are unfinished work.** Never ship to client QA on top of an open internal comment.

## Step 8 — Report: publish the page, then write the file

**The deliverable is a published Artifact, not a markdown file.** The report is read by a dev
working a list, a PM deciding whether it ships, and sometimes a client — it needs filters, an
owner chip per finding, and working exports. A `.md` file alone is not the deliverable; produce
both, in this order.

### 8a. Build the page from the template

[`reference/report-template.html`](reference/report-template.html) is the complete shell — Amply design system, severity
filters, the computed gate strip, and the `.md` / `.csv` / `.pdf` exports already wired. **Do not
rebuild any of it and do not restyle it.** Copy it and replace the placeholders:

| Placeholder | What goes in |
|---|---|
| `{{SITE_NAME}}` `{{HOST}}` `{{STAGING_URL}}` | site name, bare host, full staging URL |
| `{{GATE}}` | `internal` or `client` — the audience from Step 0 |
| `{{VERDICT_FALLBACK}}` | plain-text verdict for no-JS; `renderGates()` overwrites it |
| `{{SCOPE_LABEL}}` `{{SUBTITLE}}` | e.g. `full site`; one sentence on what was covered |
| `{{PILLS}}` | `<span class="pill err\|warn\|ok">…</span>` — counts, and the notable zeros |
| `{{STATS}}` | `<div class="stat"><div class="v">304</div><div class="k">pages</div></div>` |
| `{{N_ALL}}` … `{{N_NOTE}}` | filter counts; they must match the findings you emit |
| `{{GROUPS}}` | the `<section class="group" data-g="…">` blocks |
| `{{COVERAGE_NOTE}}` `{{COVERAGE}}` | what ran, what was sampled, **what did not run** |

Each finding is one `<details class="find">`, and the markup is load-bearing — the filters,
the gate maths and all three exports read these attributes:

```html
<details class="find" data-sev="crit" data-owner="dev">
  <summary><div><p class="ftitle">Finding title</p>
    <div class="fmeta"><span class="flag">FLAG_CODE</span><span class="own" data-o="dev">DEV</span></div></div>
    <svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="2" stroke-linecap="round"><path d="M9 6l6 6-6 6"/></svg></summary>
  <div class="fbody">
    <p>What it is and why it matters.</p>
    <div class="ev">machine evidence, monospace, newlines preserved</div>
    <div class="scroller"><table>…</table></div>
    <div class="fix"><span class="lab">Fix</span><p>…</p></div>
  </div>
</details>
```

- `data-sev`: `crit` | `warn` | `note` · `data-owner`: `dev` | `design` | `lead` | `none`
- A justified finding adds `data-status` / `data-by` / `data-date` / `data-gate` and a
  `<div class="just">` block — see [`reference/decisions.md`](reference/decisions.md).
- Asset filenames are links to the CDN URL, in the page and in the exports.

> ⚠️ **No literal non-ASCII anywhere in the file.** Write `&mdash;` in HTML and `\u2014` in
> JavaScript. A charset pass rewrites literals into HTML entities *inside the script*, which has
> already produced a literal `&#8212;` in one export and the string `undefined` in another.

### 8b. Publish it

```
Artifact(file_path: "<the file you wrote>", capabilities: {"downloads": true}, favicon: "🔍")
```

`capabilities` is required — without it the export buttons stay hidden, because page-initiated
downloads are inert in the artifact sandbox. Give the dev the URL in your reply.

### 8c. Write the markdown file too

The artifact is the thing people read; the file is the record that can be committed and diffed.
Write it to **`_sandbox/pre-qa/<YYYY-MM-DD>-pre-qa.md` relative to the repository root** — resolve
it from the repo root, not from the current working directory, or you get
`_sandbox/pre-qa/_sandbox/pre-qa/…`, which has happened. If there is no `_sandbox/`, use
`./pre-qa-<YYYY-MM-DD>.md`.

Print the verdict and the counts in chat as well.

Severity — from [`reference/checks.md`](reference/checks.md); fix wording — from [`reference/fixes.md`](reference/fixes.md). Be strict about severity:

- 🔴 **Blocker** — do not send to QA. Broken link, broken/blurry image, horizontal overflow,
  lorem ipsum, console error, dead form, `#` on a real CTA, unresolved Designer comment.
- 🟠 **Should fix** — send only with the client's knowledge. Contrast failure, missing alt,
  missing meta description, oversized asset, no srcset, heading-level skip.
- 🟡 **Note** — log it, fix at cleanup. Webflow default class names, unused library toggled on,
  minor redirect chains.

Format each finding so the dev can act without re-running anything. **Every finding gets a
`→ Fix:` line**, worded from [`reference/fixes.md`](reference/fixes.md) so the same defect always gets the same
instruction. **Every asset filename is a markdown link to its full CDN URL** so the dev can open
it in one click — never print a bare filename.

```
🔴 WRAPPED_BITMAP — /about
   img.about_portrait  (body > .section > .container > img.about_portrait)
   rendered 640×420 · natural 320×210 · 312 KB
   [team-photo.svg](https://cdn.prod.website-files.com/<site>/<asset>_team-photo.svg)
   A 320px base64 PNG inside <pattern> — it cannot scale and cannot be recoloured.
   → Fix: re-export from Figma as WebP at 1280×840 and replace the asset.
```

Group findings by severity, not by page, so the blockers are all in one place.

### The report page must be exportable

Page-initiated downloads are inert in the artifact sandbox — `<a download>`, blob URLs and
script-driven saves all silently do nothing. Use the **`downloads` capability** instead:
publish with `capabilities: {downloads: true}`, resolve `await claude.use("downloads")`, and
ship the buttons **hidden**, revealing them only when it resolves non-null. Handle `declined`
by doing nothing (never retry) and `rate_limited` by asking the viewer to try again.

Offer two formats, both built from the DOM so they always match what's displayed and honour the
active filter:

- **`.md`** — the whole report: severity, flags, owner, evidence as fenced blocks, tables as
  Markdown tables, every `→ Fix:` line. This is what gets pasted into the ClickUp task.
- **`.csv`** — one row per finding, for bulk task creation:
  `severity, owner, status, finding, section, flags, justification, justified_by, justified_date`

> ⚠️ Never put a non-ASCII character in an export string literal without a `\u` escape. A
> charset pass over the page will rewrite it to an HTML entity *inside the JavaScript*, and the
> export then emits a literal `&#8212;`. Caught exactly this way once.

### Justified findings must survive the export

A justification that only exists on the report page is lost the moment someone exports it, and
the export is what reaches the ClickUp task. So every justified finding carries its decision in
the markup, and the exporter reads it:

```html
<details class="find" data-sev="crit" data-owner="dev"
         data-status="wontfix" data-by="Beto" data-date="2026-08-26" data-gate="internal">
  …
  <div class="just">
    <span class="lab">Justified — wontfix · Beto · 2026-08-26 · clears internal QA only</span>
    <p>Client-supplied logos, no vector source exists.</p>
  </div>
</details>
```

- **Markdown** renders it as a blockquote directly under the finding, before the fix.
- **CSV** fills `status`, `justification`, `justified_by`, `justified_date`; an open finding
  leaves them empty, so filtering the sheet by blank `status` gives the work list.
- The export header repeats the honest headline — `5 blockers (7 found, 2 justified)` — so an
  exported report can never read cleaner than the build actually is.

**Three findings are not dev fixes.** Label them, so nobody is handed a task they can't do:

- `CONTRAST_FAIL` → **route to design.** The dev can't repaint the brand palette. Report the
  exact pairing and measured ratio and ask design for an approved alternative. If design signs
  off on the pairing as-is, record that in the report so it stops resurfacing every run.
- `LOREM` where copy was never delivered → **route to the Project Manager**, it's a content blocker.
- `PLACEHOLDER_ASSET` where the real asset doesn't exist yet → same.

- `NO_SRCSET` → **not a dev task either — Webflow owns it.** The platform generates responsive
  variants (`-p-500/800/1080/1600/2000`) automatically; nobody writes a srcset by hand in
  Webflow. The single lever is the **upload format**: Webflow produces variants for PNG/JPG but
  **never for AVIF** (measured on a live staging build: 0 of 8 AVIFs had one, 24 of 36 PNGs
  did). Report it as context on image weight, and raise it as an action only when an AVIF fills
  a large responsive slot — then re-uploading as PNG/JPG is the fix. Note that this is **not** a
  staging artifact: srcset is generated on staging too.

### The verdict line depends on the audience

Compute it, don't improvise it. `open` = blockers with no recorded justification.

**Internal QA**

- `blockers == 0` → **"Ready for internal QA — 0 blockers."**
- `open == 0` and some are justified → **"Ready for internal QA — N blockers, all justified."**
  List them, each with its justification and who gave it.
- `open > 0` → **"Not ready — N blockers, M still unjustified."** Name the unjustified ones.

**Client QA**

- `blockers == 0` → **"Ready for client QA — 0 blockers."**
- `blockers > 0` → **"NOT ready for client QA — N blockers."** Say it even when every one of
  them is justified, and say so explicitly:
  *"All N are justified, which clears internal QA only. Client QA requires zero blockers."*

> ⚠️ Never report a justified blocker as if it were resolved, and never carry an internal-QA
> pass over to a client send. Two different gates, two different answers, stated plainly.

Do not soften a blocker count. That number is the whole point of the command.

## Step 9 — Record any decisions the dev makes

The dev reads the report and answers in plain language — *"the marquee logos are
client-supplied, wontfix"*, *"contrast is approved by design"*, *"lorem on contact-us is waiting
on copy, defer it"*. That is the input mechanism; there is no UI to build.

1. **Map** their words onto finding keys from the scan (`keys[]` on each finding). A decision on
   a 🔴 blocker is a **justification** — record `for: internal` on it, because that is the only
   gate it can clear.
2. **Confirm before writing.** Echo an exact table — status, key, how many findings it covers,
   the note — and wait for a yes. "The logos" might mean 3 assets or 75; never write on
   inference. This is a write to the client's live site.
3. **Write** to `pre-qa/state/decisions.md` via `data_agent_instructions_tool >
   update_instruction` (or `create_instruction` on a first run, `kind: "skill"`).
4. **Attribute** with `git config user.name` and today's date — per-machine, so it records who
   actually ran it.

Never invent a decision the dev didn't make, and never upgrade "I'll look at that later" into
`wontfix`. When their intent is unclear, ask rather than guessing — a wrong `wontfix` silences
a real blocker on every future run.

## Step 10 — Offer fixes, don't apply them

List what you can fix, grouped, and wait for a yes. Safe and mechanical:

- `data_assets_tool > compress_assets {format: "webp"}` for oversized rasters — note that this
  **replaces the hosted file in place** for every reference on the site, so confirm the list.
- `data_assets_tool > update_asset {alt_text}` for missing alts (write real alt text, or `null`
  to mark genuinely decorative).
- `data_pages_tool > update_page_settings` for missing titles/descriptions.

Everything else — a re-export from Figma, an overflow fix, a wrong href — goes back to the dev
with the exact element path. **Never re-export or invent an image asset yourself.**

Publishing is not part of this command. Fixes need a re-publish before the report is true again;
say so, and offer to re-run `/pre-qa` after.
