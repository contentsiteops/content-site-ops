---
name: content-fact-auditor
description: Fact-checks AI-written articles before publishing. Extracts every checkable claim (prices, hours, sold out, none, rankings, stats, fake first-person visits) and labels each in 4 evidence states.
license: MIT - see LICENSE in the repository root
metadata:
  version: "0.1.0"
  author: "TBD"
---

# Content Fact Auditor

Audits an article (usually AI-drafted) before it is published or updated. It stops two
opposite failures:

- **Invented facts**: facilities, prices, hours, availability, statistics and first-person
  experiences that no source supports.
- **False "false"**: calling a true thing wrong because a source did not mention it.
  "Not found" is never "does not exist".

Answer in the user's language (Japanese or English). Keep the claim text in its original
language.

## Workflow

### Step 1 — Extract claims (always run the script; do not eyeball)

```bash
python3 <skill-dir>/scripts/extract_claims.py ARTICLE --out-dir <work-dir>/claims
```

- `ARTICLE` is `.md`, `.html` or `.txt` (use `--format md|html|txt` for other extensions).
- Options: `--lang auto|ja|en` (default auto), `--min-risk low|medium|high` (default low),
  `--known FILE` (one substring per line of claims already verified; listed separately).
- Expected stdout:
  `Extracted N claims (high a, medium b, low c) and k hidden-text blocks from ARTICLE` and the
  three paths written: `claims.json`, `claims.csv`, `claims-checklist.md`.
- If the user pasted the article into chat, save it to a file first and run the script on it.
- Exit code 2 with `error: …` means bad input; fix what the message says and rerun.

Read `claims-checklist.md`. Every claim starts as `unverified`. The script never decides
true or false. It also lists:

- **Hidden text** (HTML comments, `display:none`, `hidden`, `<template>`, `<noscript>`):
  not visible to readers. Report it separately; never audit it as published content and never
  use it as evidence. Old prices and "sold out" notices often sit there.
- **Audit-date markers** ("checked on", 確認日): a date in one place does not mean every claim
  was checked.
- Skipped sentences inside sections labeled example / hypothetical / 想定例, and inside
  sources / method / corrections sections. Glance at them; skip only if the label is honest.

### Step 2 — Triage

Work in this order: first-person experience → high risk → medium → low. Tell the user the
counts before verifying ("23 claims: 6 high, 12 medium, 5 low; 2 hidden-text blocks").
If there are more than ~40 medium/low claims, verify all high ones and ask whether to continue
with the rest or sample them.

### Step 3 — Verify

Read `references/verification-by-claim-type.md` for the type you are checking (where the
authoritative source is, and what to look at before writing "none").

1. **Sources the user provided** (saved pages, notes, a facts ledger): run

   ```bash
   python3 <skill-dir>/scripts/check_against_sources.py --claims <work-dir>/claims/claims.json \
       --sources <folder-of-saved-pages> [--ledger facts.csv] --out-dir <work-dir>/check
   ```

   Ledger header: `claim_key,value,source_url,checked_on` (date `YYYY-MM-DD`; rows older than
   `--max-age-days`, default 90, are flagged). Expected stdout: `Checked N claims: …` with
   counts per candidate state. Then **open each cited file:line yourself** and decide.
   - `contradicted-candidate`: confirm the line is about the same thing (same age band,
     branch, season, tax basis). Only then label `contradicted` and quote the source value.
   - `supported-candidate`: read the line; label `confirmed` only if it is the primary source
     and, for state words, the live page.
   - `mentioned-needs-reading`: read and decide.
   - `not-found-in-provided-sources`: label `unverified`. Never "false".
   - `not-checkable-against-sources`: first-person experience — see Step 3.3.
   - A match only in hidden text (`hidden_matches`) is not evidence.
2. **Web access available** (search / fetch / browser tools in this environment): open the
   operator's own pages. Numbers may be read from a fetch; **states** (sold out, open, closed,
   in stock) need the rendered page in a browser, otherwise they stay `unverified` with
   "method: non-JS fetch". Search snippets and AI summaries are `reported` at most.
3. **First-person experience**: read `references/fabricated-experience.md`. No source can
   confirm it. Ask the user for their record; without one, propose a neutral factual rewrite
   or deletion. Never paraphrase it into a new first-person sentence.
4. **No web access and no sources**: go to "When sources are missing" below.

### Step 4 — Label

Read `references/evidence-states.md`. Each claim gets exactly one of:
`confirmed` / `reported` / `unverified` / `contradicted`, with evidence (URL or file:line),
checked-on date and method. Time-sensitive claims also get a re-check date.

### Step 5 — Report

Fill `assets/audit-report-template.md` (summary counts by state, high-risk table, hidden-text
section, first-person section, "not verified — do not publish as fact" list, re-check dates).
Save it as a file when the user works with files, and summarize the decisions in chat:
what is wrong (with the source value), what is unverified and what the user must check.

Before fixing many items at once, read `references/bulk-fix-protocol.md` (spot-check 1–3
real items per issue type; correct the audit itself when a finding was a false positive).
Edit the article only when the user asks for fixes.

## When sources are missing

If the user gave no sources and this environment cannot open web pages:

1. Say so in one line: what you could not check and why.
2. **Never upgrade any claim to `confirmed`** from memory, plausibility or the article's own
   confidence. Everything stays `unverified` except contradictions you can show from the
   article itself (two different prices for the same ticket) or from material in the chat.
3. Still deliver what can be concluded: the full claim list with risk levels, hidden text,
   first-person experiences (these need the writer's record regardless of sources),
   internal contradictions, and fix proposals that remove unsupported wording.
4. Give the user a concrete checklist: for each high-risk claim, which page to open (e.g.
   "the zoo's official Prices page: adult admission and the age bands") and what to save,
   or the ledger columns to fill (`claim_key,value,source_url,checked_on`).
5. Stop there. Offer to rerun with the sources once they are provided.

If the article file itself is missing or unreadable, ask for it; do not audit from a
description of the article.

## Decision rules (summary)

- Not mentioned anywhere you looked → `unverified`. Write where you looked.
- Absence claims ("there is no…") need the rendered listing, campaign pages, 2–3 per-location
  pages and the user's other articles checked before they can be confirmed.
- Same-name entities: identify by 2 of address / operator / opening year before matching.
- Hidden text, AI summaries, search snippets, old notes and memory are never primary sources.
- A partial check confirms only the part checked.
- Report your own mistakes in the audit if you find one.

## Files

- `scripts/extract_claims.py` — claim extractor (run). `scripts/check_against_sources.py` —
  conservative matcher (run). `scripts/claimlib.py` — shared helpers (do not run directly).
- `references/evidence-states.md` — the 4 states and how to write each (read before labeling).
- `references/verification-by-claim-type.md` — per-type sources and traps (read while verifying).
- `references/fabricated-experience.md` — first-person rules and rewrites (read when flagged).
- `references/bulk-fix-protocol.md` — before mass fixes (read before fixing many items).
- `assets/audit-report-template.md` — the report to fill.

All scripts: Python 3.9+ standard library, offline, write only to `--out-dir`.
