# Decisions — carrying human judgement across runs

A finding that a human has already ruled on should not come back as a fresh blocker every
time someone runs the audit. Decisions are how that judgement persists — stored **on the
Webflow site**, so the next dev on a different machine with no repo gets them automatically.

## Where they live

`data_agent_instructions_tool`, as a skill companion file on the site being audited:

```
pre-qa/state/decisions.md      kind: "skill"
```

Site-stored, versioned, 256 KB, travels with the site, invisible to the client in their CMS,
and needs no publish. **Not** a CMS collection (costs item quota, shows up in the client's
Editor) and **not** an element inside a component (component edits are shared across every
page and get clobbered by starter updates).

### Three API behaviours, verified on the AI First sandbox 2026-08-26

1. **A companion file needs its `SKILL.md` root to exist first.** Creating
   `pre-qa/state/decisions.md` on its own fails with a bare **HTTP 500 `internal_error`** —
   not a 400, and with no hint about the cause. Create `pre-qa/SKILL.md` first, then the
   companion. Budget for this: the error tells you nothing.
2. **Drafts are fully readable.** `read_instruction` returns a draft's complete markdown, so
   `isDraft: true` does not put the file out of reach of the next run.
3. **Drafts are NOT hidden from discovery.** An unfiltered `search_instructions` lists draft
   files alongside published ones, with path and description. So `isDraft` is *not* a way to
   keep this file out of an agent's view — it only marks it unpublished. Keep the file small
   and let its description say plainly that it is state, not instructions.

> ⚠️ **Do not trust the `name` filter.** `search_instructions {name: "decisions"}` returned
> **zero** results for a file named `decisions.md` that an unfiltered search listed. Read this
> file by its known path with `read_instruction`; never go looking for it by name.

## Justifications vs decisions — and which gate they clear

A decision on a 🟠 or 🟡 finding is housekeeping. A decision on a 🔴 **blocker** is a
**justification**, and it clears exactly one gate:

| | Internal QA | Client QA |
|---|---|---|
| Blocker, fixed | passes | passes |
| Blocker, justified | **passes** | **does not pass** |
| Blocker, open | does not pass | does not pass |

A justification says *why this is still open*, so the internal reviewer isn't rediscovering it
and the next audit doesn't re-raise it. **It is not a waiver.** A build with justified blockers
is not sendable to a client — the only route there is to fix them.

If a blocker is genuinely acceptable forever, don't paper over it with a permanent
justification: either fix the build, or change the severity of that check in
[`checks.md`](checks.md) so it stops being graded as a blocker. A standing justification on a
blocker is a signal that the grade is wrong, not that the gate should bend.

Record the gate on the row so it can never be misread:

```markdown
| `WRAPPED_BITMAP:…_Logo.svg` | wontfix | for: internal — client-supplied logo, no vector source | Beto | 2026-08-26 |
```

## How a decision gets made

The dev tells you in the prompt, in their own words, right after reading the report:

> "the marquee logos are client-supplied, we're not re-exporting them — wontfix"
> "contrast is approved by design, Ana signed off today"
> "lorem on /contact-us is waiting on client copy, defer it"

You map that onto finding keys and write it. **Three rules govern this — all three matter:**

### 1. Confirm the mapping before writing

Natural language is ambiguous — "the logos" could be 3 assets or 75. Echo back an exact table
and wait for a yes. Never write on inference alone.

```
About to record 3 decisions on acme-stg.webflow.io:

  wontfix   WRAPPED_BITMAP:*  (75 assets)   "client-supplied logos, not re-exporting"
  accepted  CONTRAST_FAIL:div.card-testimonial_info>.u-color-secondary
                                            "approved by design, Ana, 2026-08-26"
  deferred  LOREM:/contact-us               "waiting on client copy"

Write these to pre-qa/state/decisions.md?
```

This is a write to the client's live site — treat it like any other outward-facing action.

### 2. A decision never silently suppresses a finding

This is the rule that keeps the gate worth running. A decided finding moves into a
**Previously decided** section with its note and author attached — it does not vanish, and the
raw count stays visible:

```
5 blockers — not QA-ready          (7 found, 2 previously decided)
```

The moment a decision can hide a blocker without trace, the report becomes a mute button and
nobody trusts the number again.

### 3. Decisions go stale; they are never silently reapplied

- **The finding no longer appears** → mark the decision `stale` with the date. Don't delete it:
  the same defect often returns, and the old note is the fastest context for whoever sees it next.
- **The key is fragile** → `CONTRAST_FAIL`, `TEXT_CLIPPED`, `ZERO_HEIGHT`, `HORIZONTAL_OVERFLOW`
  and `COLLAPSED_EMPTY` key on CSS paths, which a class rename orphans. Show a matched decision
  on these as **possibly stale** and make the reader confirm it still applies.
- **A decision older than ~6 months** on a still-live finding → surface it for re-confirmation
  rather than treating it as settled forever.

## File format

One table. Keep it readable by a human in the Webflow UI, not just by an agent.

```markdown
# Pre-QA decisions — <site name>

| Key | Status | Note | By | Date |
|---|---|---|---|---|
| `WRAPPED_BITMAP:6a0b45a5_Logo.svg` | wontfix | Client-supplied logo, no vector source exists | Beto | 2026-08-26 |
| `CONTRAST_FAIL:div.card-testimonial_info>.u-color-secondary` | accepted | Approved by design (Ana) | Beto | 2026-08-26 |
| `LOREM:/contact-us` | deferred | Waiting on client copy — chase before launch | Beto | 2026-08-26 |
| `NO_SEO_BINDING:<template-page-id>` | fixed | Bound to CMS fields | Beto | 2026-08-26 |
```

**Statuses:** `accepted` (real, judged acceptable) · `wontfix` (real, not being fixed) ·
`deferred` (will fix, not now) · `fixed` (believed fixed — verify on the next run and drop it
if the finding is gone) · `stale` (auto-set when the finding stops appearing).

**Attribution:** take the name from `git config user.name` rather than asking. It's per-machine,
which is exactly right — it records who actually ran it.

## Where it plugs into a run

- **Step 0** — read `pre-qa/state/decisions.md` **by path** with `read_instruction` before
  crawling. If it doesn't exist, carry on; a first run has no decisions. On the first write,
  create `pre-qa/SKILL.md` before the companion file, or the create fails with an opaque 500.
- **Step 8** — fold decisions into the report: matched findings move to *Previously decided*,
  counts show `found` and `decided` separately, stale ones are flagged.
- **After the report** — if the dev responds with judgement calls, map, confirm, write.

## Keys

The scanner emits `all_keys` and a `keys[]` on every finding. Keys are built from things that
don't move — asset filenames, Webflow page and collection ids, URL paths:

```
WRAPPED_BITMAP:6a0b45a5…_Logo.svg
NO_SEO_BINDING:<template-page-id>     ← template page id
BROKEN_LINK:/capabilities/international-market-research-company
NO_DESCRIPTION:/article/tiktok-ai-automation-report
```

One deliberate quirk: for a re-uploaded asset whose filename carries two Webflow id prefixes,
only the first is stripped. Stripping both would collapse `Logo.svg`, `Logo here.svg` and
`Logo.svg.svg` into colliding keys — and a decision landing on the wrong asset is worse than
a slightly ugly key.
