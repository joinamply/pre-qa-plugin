# Pre-QA check — the gate before any handover

**Run it with `/amply:pre-qa <staging-url>`.** This doc is the catalogue behind that command:
what gets checked, at what threshold, and how bad it is. The command is the procedure, this is
the standard, and [`fixes.md`](fixes.md) is the remedy for each flag.

> ## Why this exists
> A build went to client QA with blurry images (SVGs that were really wrapped bitmaps, blur
> filters baked in from Figma), and a page full of broken and missing links. None of it was
> subtle. All of it was invisible to every check we had — because **every check we had reads
> the API.**

## The one idea: intent vs. result

| | `starter-lint` | **pre-QA** |
|---|---|---|
| Reads | the Webflow API | the **published page in a browser** |
| Verifies | *intent* — classes, tokens, structure | *result* — pixels, requests, status codes |
| Catches | wrong class, hardcoded px, unregistered style | blurry image, 404, overflow at 375px |
| Runs | after every build | **once, before the client link goes out** |

`starter-lint` would pass a page whose hero image is a 320px bitmap stretched to 1440 — the
`Image / Aspect` component is correct, the classes are correct, the aspect ratio is set. The
image is still blurry. **An API-only linter cannot catch a rendered bug.** These two are
complements; neither replaces the other.

**Corollary:** pre-QA needs a *published* URL. It cannot run against the Designer.

---

## Severity — and holding the line on it

- 🔴 **Blocker** — does not go to QA. Sending one of these costs a review cycle and credibility.
- 🟠 **Should fix** — goes only with the client explicitly told.
- 🟡 **Note** — logged, fixed at cleanup.

A check with a high false-positive rate gets ignored, and an ignored check is worse than no
check. Every threshold below is set to fire on real defects, not on taste. If a check starts
crying wolf, **fix the threshold — don't start skipping the report.**

---

## A. Images and assets — *the one that burned us*

| # | Check | Severity | Threshold / how |
|---|---|---|---|
| A1 | **SVG that wraps a bitmap** | 🔴 | `<image>` or `data:image/png\|jpeg` inside the SVG source. Curl it and grep. Doesn't scale, can't be served responsively — it is a bitmap wearing a vector's file extension. |
| A2 | **Blur baked into an SVG** | 🔴 | `feGaussianBlur` / `feDropShadow` in the source. Figma flattens effects into filters on export. Renders soft and inconsistently; do the blur in CSS instead. |
| A3 | **Upscaled raster** | 🔴 | `naturalWidth / renderedWidth < 0.95` → blurry on **every** screen. |
| A4 | **Soft on retina** | 🟠 | `naturalWidth / (renderedWidth × DPR) < 0.8` while A3 passes. Fine on a 1× monitor, mushy on the laptop the client will open it on. |
| A5 | **Broken image** | 🔴 | `naturalWidth === 0`, or a 4xx in the network log. |
| A6 | **Placeholder asset shipped** | 🔴 | src matches `placeholder`, `plus.svg`, `picsum`, `unsplash`, `dummy`, `lorem`. |
| A7 | **Off-site asset** | 🔴 | host is neither the site nor a Webflow CDN. Figma/Drive/Dropbox/S3 links die or go private without warning. Upload it to Webflow. |
| A8 | **Oversized** | 🟠 | `natural > 2× (rendered × DPR)`, or any raster over ~400 KB. → `data_assets_tool > compress_assets {format:"webp"}`. |
| A9 | **No `srcset`** | 🟡 | **Informational — not a dev task.** Webflow generates responsive variants (`-p-500/800/1080/1600/2000`) automatically; a dev cannot author a srcset by hand. The one lever is the **upload format**: Webflow produces variants for PNG/JPG but **never for AVIF** (measured on a live staging build: 0/8 AVIF had one, 24/36 PNG did). So report it as context for image weight, and only raise it as an action when an AVIF sits in a large responsive slot — where re-uploading as PNG/JPG is the fix. Also appears for images in an Embed or set as a CSS background rather than a real Image element. |
| A10 | **SVG over ~100 KB** | 🟠 | Almost always a traced bitmap or an un-simplified illustration. |
| A11 | **Missing alt** | 🟠 | `alt` attribute absent. `alt=""` is a *decision* (decorative) and passes; absent is an oversight. |
| A12 | **Background images** | 🟠 | No intrinsic size available in the DOM — curl the URL and compare against the rendered box by hand. |
| A13 | **Favicon + webclip** | 🟠 | Still the Webflow default = unfinished. |
| A14 | **OG image** | 🟠 | Present, and 1200×630. The first thing that happens to a client link is someone pastes it into Slack. |

## B. Links — *the other one*

| # | Check | Severity | Threshold / how |
|---|---|---|---|
| B1 | **4xx / 5xx** | 🔴 | curl every unique href. |
| B2 | **`href="#"` or empty** | 🔴 | The Webflow default. On a real CTA it is a dead button. |
| B3 | **Dead anchor** | 🔴 | `#section` with no matching `id` on the page. Silent — nothing happens on click. |
| B4 | **Staging URL in a link** | 🔴 | `*.webflow.io` hardcoded in an href. Survives to production and leaks the staging site. |
| B5 | **Dev / local URL** | 🔴 | `localhost`, `.local`, `figma.com`, Drive, Dropbox. |
| B6 | **Malformed `mailto:` / `tel:`** | 🔴 | `mailto:broken@`, `tel:` with letters. |
| B7 | **`http://`** | 🟠 | Mixed content; browsers block or warn. |
| B8 | **`target="_blank"` without `rel="noopener"`** | 🟠 | Security + performance. |
| B9 | **Empty / unlabelled link** | 🟠 | No text, no image, no `aria-label` — invisible to screen readers and to the click target. |
| B10 | **Redirect chain** | 🟡 | Internal link 301s to a different final URL. Point it at the destination. |
| B11 | **Nav + footer resolve** | 🔴 | Every menu item, on every page. These are the links the client clicks first. |
| B12 | **Every page reachable** | 🟠 | Compare `get_pages_list` against the sitemap and against links found while crawling. An orphan page is usually an unfinished one. |
| B13 | **CMS-bound links** | 🔴 | An empty link field on a collection item renders as `#`. Check the template *and* spot-check real items. |

## C. Layout — *yes, this is checkable*

Not "does it match Figma" — that needs eyes. But the failures that actually reach QA are
measurable, and these are they.

| # | Check | Severity | Threshold / how |
|---|---|---|---|
| C1 | **Horizontal overflow** | 🔴 | `documentElement.scrollWidth > clientWidth` at **any** breakpoint. The single most common QA complaint. The snippet names the outermost offending element. |
| C2 | **Element outside the viewport** | 🔴 | `rect.right > innerWidth` or `rect.left < 0` on a visible element whose parent is in bounds. |
| C3 | **Clipped text** | 🔴 | `scrollHeight > clientHeight` on a box with `overflow:hidden`. Copy is being cut off mid-sentence. |
| C4 | **Zero-height element with content** | 🔴 | Collapsed flex/grid child — content exists and renders at 0px. |
| C5 | **Collapsed empty section** | 🟠 | A `section`/`div` under 4px with no children. Usually a section that was built and never filled — and see the empty-div padding rule. |
| C6 | **Breakpoint sweep** | 🔴 | 1920 / 1440 / 991 / 767 / 375. **991 and 375 are where builds break** — 991 because it gets skipped, 375 because it is narrower than anyone designs for. |
| C7 | **Contrast (computed)** | 🟠 | WCAG AA on *rendered* colors: 4.5:1 normal, 3:1 for ≥24px or ≥18.66px bold. Catches what a token audit can't — the token is fine, the pairing isn't. **Route to design, not to the dev** — repainting the brand palette isn't the dev's call. Record a design sign-off in the report so an accepted pairing stops resurfacing. |
| C8 | **No responsive change** | 🟡 | Identical computed layout at 1440 and 375 on a multi-column section = the mobile pass never happened. |
| C9 | **Visual pass** | 🔴 | Screenshot at 375 and 1440 and **look**. Text over text, one card taller than its siblings, an icon at 4×, a background that ran out — these have no numeric signature. Automation narrows the search; it doesn't replace the look. |

## D. Content

| # | Check | Severity |
|---|---|---|
| D1 | Lorem ipsum / `TODO` / `TBD` / `XXX` / "Coming soon" / "Client name" | 🔴 |
| D2 | Webflow default copy left in — `Heading`, `Paragraph`, `Button`, `This is some text inside of a div block` | 🔴 |
| D3 | Footer copyright year, client legal name, address, phone | 🟠 |
| D4 | Placeholder CMS items still published (`Item 1`, `Blog Post Title`) | 🔴 |
| D5 | Webflow default class names surviving into production (`div-block-*`, `heading-2`, `link-block-3`) | 🟡 |

## E. SEO and metadata

Read at **both** levels — the rendered `<head>` *and* `data_pages_tool > get_page_metadata`. A
page can render an inherited site-default title and still be unset in page settings.

| # | Check | Severity |
|---|---|---|
| E1 | Title on every page, unique, ~50–60 chars | 🟠 |
| E2 | Meta description on every page, unique, ~140–160 chars | 🟠 |
| E3 | Exactly one visible `<h1>` per page | 🟠 |
| E4 | No heading-level skips (`h1 → h4`) | 🟡 |
| E5 | OG title, description and image set (1200×630). **`twitter:card` is deliberately not checked** — X reads `og:image`, so a separate card tag is redundant for us. | 🟠 |
| E6 | Canonical URL correct — **not pointing at the staging domain** | 🔴 |
| E7 | `noindex` **on** for staging, and a plan to remove it at launch — plus utility/thank-you pages excluded from the sitemap (`data_sitemap_tool`) | 🔴 |
| E8 | 404 page exists and is styled | 🟠 |
| E9 | JSON-LD present where the build calls for it (`query_pages_schema_markup`) | 🟡 |
| E10 | `<html lang>` set | 🟡 |

## F. Technical

| # | Check | Severity | How |
|---|---|---|---|
| F1 | **Zero console errors** on load | 🔴 | `read_console_messages {onlyErrors:true}` |
| F2 | **Zero failed requests** | 🔴 | `read_network_requests` — 4xx/5xx, mixed content |
| F3 | **Forms wired** | 🔴 | Registered in `data_forms_tool > list_forms`, uniquely named, success + error states present, required fields set, notification email configured. **Submit a real test entry** and confirm it lands. |
| F4 | **Analytics once** | 🟠 | `get_site_scripts` + `get_page_scripts` — GTM/GA applied exactly once, no leftover dev scripts |
| F5 | **Only used libraries toggled on** | 🟠 | GSAP/ScrollTrigger/Swiper/Lightbox loading but unused = wasted weight. Compare the toggles against what the page actually instantiates. |
| F6 | **One `Code` prop per page** | 🔴 | Multiple instances running the same init = double-initialised sliders |
| F7 | **Interactions fire** | 🟠 | Scroll the page and watch. GSAP/IX3 elements stuck at `opacity:0` are invisible content. |
| F8 | **Unresolved Designer comments** | 🔴 | `data_comments_tool > list_comment_threads {isResolved:false}` — **an open internal comment means the build isn't finished.** |
| F9 | **Published state current** | 🔴 | Publish before the check. Fixes need a re-publish before the report is true again. |

## G. Accessibility — the quick pass

Not a full audit; the cheap checks that catch the embarrassing failures. C7 (contrast), A11
(alt), B9 (link labels) live above. Plus: visible focus states on interactive elements, form
inputs with real labels (not placeholder-only), icon-only buttons with `aria-label`, and no
autoplaying video with sound.

---

## What this cannot do

Be honest about the boundary in every report:

- **Design fidelity.** It cannot tell you the hero doesn't match Figma. Numbers can't see that.
- **Copy quality.** It finds `lorem ipsum`, not a wrong product name or a typo.
- **Interaction behaviour.** It cannot click through a multi-step form, a filter, or a modal.
  Those need a human path.
- **CMS breadth.** It checks a template, not 400 items. Empty fields on item #237 stay hidden
  until someone looks.
- **Anything unpublished.** It reads the published page and nothing else.

The check narrows the human QA pass down to judgement calls. It doesn't replace it.
