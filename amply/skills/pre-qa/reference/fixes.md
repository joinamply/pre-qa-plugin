# Fix playbook — what to do about each flag

Every finding in a pre-QA report carries a `→ Fix:` line. Take the wording from here so the
same defect always gets the same instruction, and so the dev never has to work out the remedy
from the flag name.

Several of these are **not dev fixes** — `CONTRAST_FAIL` belongs to design, `NO_SRCSET` belongs
to Webflow's own pipeline, and undelivered copy or assets belong to the Project Manager. Say so
explicitly rather than handing the dev a task they can't complete.

---

## Images

| Flag | → Fix |
|---|---|
| `WRAPPED_BITMAP` | The file is a raster wearing a `.svg` extension (a base64 PNG inside `<pattern>`/`<image>`). Go back to the Figma source: if the artwork is genuinely vector, re-export as SVG with **Include bitmap** off; if it isn't (a photo, a client logo supplied as PNG), export **WebP at 2× the rendered slot** and replace the asset. Never "optimise" the SVG — the bitmap inside it is the problem. |
| `BLUR_FILTER` | Figma flattened a blur or drop-shadow into an SVG `<filter>`. Re-export without the effect and recreate it in CSS (`filter: blur()` / `box-shadow`) so it stays crisp and cheap. |
| `BLURRY` | Intrinsic width is below the rendered width — soft on every screen. Re-export at **2× the rendered CSS width** and re-upload. Replacing the asset in the Webflow asset panel updates every reference at once. |
| `SOFT_ON_RETINA` | Sharp at 1×, mushy on a retina laptop — which is what the client will open it on. Same fix: re-export at 2× the rendered width. |
| `OVERSIZED` | Far larger than the slot needs, so the visitor downloads bytes they never see. Two options: re-export at 2× the slot, or run `data_assets_tool > compress_assets {format:"webp"}` on the asset ids. **Compression replaces the hosted file in place for every reference on the site** — confirm the list with the dev first. |
| `BROKEN` | The image finished loading and has no dimensions: the asset 404s or is corrupt. Check the URL in the network log, re-upload the asset, and re-point the element. |
| `NOT_LOADED` | Not a defect — the image never entered the viewport, so it could not be measured. Force-load and re-run before drawing any conclusion. If it still won't load, then investigate. |
| `PLACEHOLDER_ASSET` | A stock or placeholder file (Unsplash, `plus.svg`, `picsum`, `dummy`) is live. Replace with the real client asset, or confirm with the Project Manager that the placeholder is intentional. |
| `OFFSITE_ASSET` | Hotlinked from Figma, Drive, Dropbox or S3. These die or go private without warning. Download it, upload to Webflow, re-point the element. |
| `NO_SRCSET` | **Not a dev fix — Webflow controls this.** The platform generates responsive variants automatically; nobody authors a srcset by hand in Webflow. The only lever is the **upload format**: Webflow produces `-p-*` variants for PNG/JPG but **never for AVIF**. So: if the file is AVIF and it fills a large responsive slot, re-upload it as PNG/JPG and Webflow will generate the variants. Otherwise report it as information about image weight and leave it alone. |
| `ALT_MISSING` | Set alt text on the element, or on the asset via `data_assets_tool > update_asset {alt_text}`. Pass `null` to mark genuinely decorative — `alt=""` is a decision, an absent attribute is an oversight. |
| `HUGE` (SVG >100 KB) | Almost always a traced bitmap or an un-simplified illustration. Re-export, or run it through an SVG optimiser and re-upload. |

## Links

| Flag | → Fix |
|---|---|
| `BROKEN_LINK` (4xx/5xx) | Repoint the link. If the target page was renamed, add a 301 in **Site settings → Publishing → Redirects** so old inbound links survive too. |
| `HASH_ONLY` | `href="#"` — the Webflow default. On a real CTA it's a dead button. Set the real destination. Leave it only if the element is a dropdown toggle driven by script, and confirm that's the case. |
| `NO_HREF` | Empty or missing `href`. Same fix; on a CMS-bound link, the collection field is empty — fill the field or add a fallback. |
| `DEAD_ANCHOR` | `#section` with no matching element id. Set the target element's ID in Webflow's element settings, or correct the href. Silent failure — nothing happens on click. |
| `STAGING_URL` | A `*.webflow.io` URL hardcoded in an href. It will survive to production and leak the staging site. Make it a **relative** path (`/about`), which works on both. |
| `DEV_URL` | Points at localhost, Figma, Drive or Dropbox. Replace with the real destination. |
| `INSECURE_HTTP` | Change to `https://`. Browsers block or warn on mixed content. |
| `MALFORMED_MAILTO` / `MALFORMED_TEL` | Malformed address or number. Note that `mailto:a@b.com?subject=…` is **valid** — a query string is not a defect. |
| `BLANK_NO_NOOPENER` | `target="_blank"` without `rel="noopener"`. In Webflow: select the link → **Settings → Link Settings**, ensure "Open in new tab" is set (Webflow adds `noopener` itself), or add `rel="noopener noreferrer"` via a custom attribute. Fixes a real tab-napping and performance issue. |
| `EMPTY_LINK_TEXT` / `ICON_LINK_NO_LABEL` | The link has no accessible name, so a screen reader announces "link" and nothing else. Add an `aria-label` custom attribute describing the destination ("View all services"), or give the icon/image inside it real alt text. For card overlay links, `aria-label` on the `<a>` is the right fix. |
| `REDIRECT_CHAIN` | Internal link 301s somewhere else. Point it at the final URL. |

## Layout

| Flag | → Fix |
|---|---|
| `HORIZONTAL_OVERFLOW` | Something is wider than the viewport. Usual causes, in order: a fixed `width` in px instead of `%`/`max-width: 100%`; a grid/flex child that won't shrink (add `min-width: 0`); negative margins; an element sized `100vw` inside padded container. The report names the outermost offender — start there, not at `body`. |
| `TEXT_CLIPPED` | Copy is cut off by an `overflow: hidden` box with a fixed height. Remove the fixed height and let the box grow, or shorten the copy. Watch this one at 375 — it usually only appears there. |
| `ZERO_HEIGHT_WITH_TEXT` | An element with content is rendering at 0px — usually a collapsed flex/grid child. Check for a missing `min-height`, a `height: 0` inherited from an animation start state, or an image that never loaded holding the box open. |
| `COLLAPSED_EMPTY` | An empty section or div. Either it was built and never filled, or it's leftover structure — delete it. Also zero its padding: Webflow's canvas inflates empty divs. |
| `CONTRAST_FAIL` | **Not a dev fix — route it to design.** The dev cannot repaint the brand palette unilaterally. Report the exact pairing (foreground, background, measured ratio, required ratio, element) to the design team and ask for an approved alternative. If design signs off on the existing pairing, record that decision in the report so it stops resurfacing every run. |
| `NO_RESPONSIVE_CHANGE` | Layout is identical at 1440 and 375 on a multi-column section — the mobile pass never happened. Add the mobile-breakpoint column classes. |

## Content, SEO, technical

| Flag | → Fix |
|---|---|
| `LOREM` / `WEBFLOW_DEFAULT_COPY` | Replace with real copy. If the copy hasn't been delivered, that's a content blocker — raise it with the Project Manager; don't ship it. |
| `MULTIPLE_H1` | Exactly one `<h1>` per page. Demote the others to `<h2>` in element settings — visual size comes from the `text-style-*` class, so **changing the tag does not change the look**. |
| `HEADING_SKIP` | A level was skipped (`h1 → h3`). Retag to keep the order continuous; again, styling is unaffected. |
| `META_MISSING` | Set title and description in **Page settings → SEO**, or via `data_pages_tool > update_page_settings`. Unique per page. |
| `CANONICAL_MISSING` / `CANONICAL_STAGING` | Set the canonical in Page settings. A canonical pointing at `*.webflow.io` tells Google the staging URL is the real one. |
| `NOINDEX` | Staging should be noindexed and production should not. Check **Site settings → SEO → Global canonical / robots.txt** before launch. |
| `NO_JSON_LD` | Add JSON-LD via `data_pages_tool > bulk_update_pages_schema_markup` where the build calls for it (Organization, Article, BreadcrumbList). |
| `CONSOLE_ERROR` | A JS error on load means something is silently dead. `Cannot read properties of null` almost always means a script queries an element that doesn't exist on this page — guard the selector (`const el = document.querySelector(...); if (!el) return;`) inside the component's own embed, not globally. |
| `FAILED_REQUEST` | A 4xx/5xx on load. If it's an asset, re-upload; if it's a third-party pixel, confirm the tag is configured; if it's blocked by an ad blocker (`ERR_BLOCKED_BY_CLIENT`), it's environmental — note and move on. |
| `FORM_UNNAMED` | Give every form a unique name in element settings. Webflow keys submissions by form name — unnamed or duplicate-named forms make submissions impossible to trace. |
| `FORM_UNLABELLED_FIELD` | Placeholder text is not a label. Add a real `<label>`, or an `aria-label` custom attribute on the input. |
| `FORM_NO_STATES` | Missing success/error blocks. Webflow ships `.w-form-done` / `.w-form-fail` with the Form Block — restore them and style them. Third-party embeds (HubSpot) handle their own states; verify by submitting a real test entry. |
| `LIB_UNUSED` | A library is loading but nothing on the page uses it. Turn its toggle off on the `Project Settings` instance — that's the performance win the manager exists for. |
| `MULTI_CODE_PROP` | More than one instance on the page has `Code` enabled, so an init script runs twice. Leave `Code` on for exactly one instance. |
| `OPEN_COMMENT` | An unresolved Designer comment means the build isn't finished. Resolve or answer it before the client sees the page. |
