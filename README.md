# pre-qa-plugin

The **pre-QA gate** for Webflow builds, as a Claude Code plugin. Run it on a published staging
URL before any handover — internal QA or client QA — and it audits the *rendered* site for the
defects an API-only check structurally cannot see.

## Install

```bash
claude plugin marketplace add joinamply/pre-qa-plugin
claude plugin install amply@amply --scope user
```

`--scope user` matters: project scope binds the plugin to one repo, and `/amply` then shows
nothing in every other project.

In the desktop app: **Settings → Plugins → Add → Add marketplace**, paste
`joinamply/pre-qa-plugin`, leave **Sync automatically** on, and choose **User scope** when
installing.

## Use

```
/amply:pre-qa https://acme-stg.webflow.io --for internal
```

`--for internal` passes when every blocker is fixed **or** carries a written justification.
`--for client` passes only at zero blockers — a justification never clears that gate.

It runs in three tiers: a static crawl of **every page** for links, asset formats, metadata and
placeholder copy; a Webflow API pass that tells a CMS template fault from empty CMS content; and
a rendered browser sample for overflow, computed contrast, intrinsic-vs-rendered image size and
console errors. The report is published as a filterable page with Markdown, CSV and PDF export.

- Check catalogue and severities — [`amply/skills/pre-qa/reference/checks.md`](amply/skills/pre-qa/reference/checks.md)
- Fix playbook, keyed by flag — [`amply/skills/pre-qa/reference/fixes.md`](amply/skills/pre-qa/reference/fixes.md)
- How decisions and justifications persist — [`amply/skills/pre-qa/reference/decisions.md`](amply/skills/pre-qa/reference/decisions.md)

## Requirements

- A **published** URL. This cannot run against the Webflow Designer.
- Claude Code in the **terminal or desktop app**. Not the web: plugins aren't supported there,
  and every `*.webflow.io` domain serves `Disallow: /`, which a cloud session's fetch honours.
- The Webflow MCP for the API tier. Without it everything else still runs.

## Why this repo is public

Marketplace refresh drops git credential helpers, so a **private** marketplace repo fails to
update and the client is deleted on the failed pull. Public removes that entirely — no
credentials, no SSH keys, no tokens in anyone's gitconfig. The plugin contains no client data.

## Updates

`plugin.json` deliberately has **no `version` field**. A declared version pins the plugin, and
pushing commits without bumping it leaves every installed copy frozen with no warning. Omitting
it makes the resolved version track the commit, so each push is an update.

> ⚠️ `claude plugin validate` warns *"No version specified"*. That warning is expected. Adding a
> version re-pins the plugin and silently stops updates reaching anyone.
