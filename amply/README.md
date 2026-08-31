# `amply` — Webflow delivery tooling for Claude Code

One install, available in **every** project on that machine — the starter repo, a client repo,
or no repo at all.

## Install

### A. Marketplace (needs GitHub access to the repo)

```bash
claude plugin marketplace add joinamply/amply-starter-webflow
claude plugin install amply@amply
```

### B. Desktop app

**Settings → Plugins → Add → Add marketplace**, paste `joinamply/amply-starter-webflow`,
connect GitHub when prompted (the repo is private), and leave **Sync automatically** on.

### C. Manual, one session only — to try it before committing

```bash
claude --plugin-dir ./amply-audit-plugin.zip
```

Also accepts an unzipped directory (`--plugin-dir ./plugins/amply`). Use `/reload-plugins`
after editing files.

> **Zip layout matters.** `.claude-plugin/plugin.json` must sit at the **root of the archive**,
> not inside a wrapper folder. Rebuild with `plugins/build-zip.sh`, which enforces that and
> checks it. `claude plugin validate` only accepts a directory, so validate
> `./plugins/amply` rather than the zip.

## Use

```
/amply:pre-qa https://acme-stg.webflow.io --for internal
```

The **pre-QA gate** — run it on the published staging URL before **any** handover: before internal QA, and again before client QA. It
audits the *rendered* page, which is the half an API linter structurally cannot see:

- **Images** — SVGs that are really wrapped bitmaps, blur filters baked in from Figma, rasters
  upscaled past their intrinsic size, broken and placeholder assets, off-site hotlinks
- **Links** — 4xx/5xx, `href="#"`, dead anchors, staging URLs, malformed `mailto:`/`tel:`
- **Layout** — horizontal overflow, clipped text, collapsed sections, contrast, across
  1920/1440/991/767/375
- **Content, SEO, technical** — leftover lorem, missing meta, console errors, dead forms,
  unresolved Designer comments

Findings come back graded 🔴 Blocker / 🟠 Should fix / 🟡 Note, each naming the exact element
and the fix. It reports and proposes; it never writes to the Webflow site without a yes.

The full check catalogue, thresholds and severities: [`skills/pre-qa/reference/checks.md`](skills/pre-qa/reference/checks.md).

## Requirements

- A **published** URL — this cannot run against the Designer
- Browser tools (built into Claude Code) for the rendered pass
- The Webflow MCP, connected and authorised, for the API-side pass (page metadata, assets,
  forms, scripts, comments). Without it, everything except that section still runs.

## Updates

Installs from the marketplace update on their own. Two things make that work, and both are
easy to undo by accident:

**1. `plugin.json` deliberately has no `version` field.**

> If you declare `"version": "1.0.0"` in `plugin.json` and push new commits without changing
> that string, existing users keep the cached copy, because Claude Code sees the same version.
> Bump the field on every release, **or omit it to fall back to the resolved version.**

We omit it. A pinned version freezes every installer until someone remembers to bump it, and
forgetting is invisible — no error, no warning, devs just quietly run an old gate. Omitting
means each push is a new resolved version.

> ⚠️ `claude plugin validate` warns *"No version specified"*. **That warning is expected — do
> not resolve it by adding a version.** Adding one re-pins the plugin and stops updates
> reaching anyone. If you ever do add it, you own bumping it on every single release.

**2. `.claude/settings.json` sets `autoUpdate: true` on the marketplace entry.**

Auto-update cannot be set in `marketplace.json` — it's consumer-side only, and third-party
marketplaces default to **off**. The repo's settings turn it on so nobody has to know to toggle
it. It applies to anyone working in a repo that carries that file.

For a **user-scope install** on a machine, outside any repo carrying these settings, the dev
turns it on once: `/plugin` → **Marketplaces** → `amply` → **Enable auto-update**.

Updates land on disk after session start (random delay up to ~10 minutes), then Claude Code
prompts for `/reload-plugins`, or they load on the next launch. To pull immediately:

```bash
claude plugin marketplace update amply
```

## Develop

Test changes without installing:

```bash
claude --plugin-dir ./plugins/amply
```

Then `/reload-plugins` to pick up edits. Validate before pushing: `claude plugin validate ./plugins/amply`.
