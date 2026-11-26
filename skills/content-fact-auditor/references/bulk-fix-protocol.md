# Bulk-fix protocol (read before fixing many claims or many articles at once)

Machine detection (this skill's extractor, any regex, any script, any spreadsheet comparison)
produces candidates. Applying a fix to dozens of items on the strength of a pattern is how a
correct article gets broken. Follow these steps.

## 1. Spot-check before you fix

- Group the findings by issue type (for example: "price differs from source", "absence claim",
  "experience sentence", "state word").
- For **each type**, open **1–3 real items** — the actual article line and the actual source page
  — and confirm the finding is real.
- If any spot-check is a false positive, stop and find out why before touching the rest.
  Suspect the detector first: a regex that cuts at an escape, a value that was in an HTML
  comment, a passage about a different age band or branch, a truncated export, a source copy
  older than the article.
- Do not write "all wrong", "broken everywhere" or "cannot be determined" from a machine
  comparison alone. Look at 3 real items first.

## 2. Fix

- Make the fix table first: `article · line · old text · new text · source (URL/file:line) ·
  checked-on`. Apply from the table, not by hand-editing in place. The table can be re-applied
  if the article changes underneath you.
- Fix the value and every other copy of the old value (search the article and sibling articles
  for the old number or phrase).
- Do not "improve" surrounding text in the same pass. Fact fixes and rewrites are separate.
- For experience sentences follow `fabricated-experience.md` (no new first-person wording).

## 3. When the audit itself was wrong

- If a flagged item turns out to be correct, do not just skip it. **Correct the audit record**:
  mark the item `false positive`, write the reason, and add the sentence to the extractor's
  `--known` list (one substring per line) so the next run lists it separately.
- If a whole issue type was a false positive, write that down in the report's notes so the
  next reviewer does not repeat it.

## 4. Verify the fix

- Rerun `extract_claims.py` on the fixed article and compare counts with the first run.
  Experience and absence counts should go down; no new types should appear in unchanged
  sections.
- If the article is published, check the published page (rendered), not only the source file.
  "Saved" or "deployed" is not "visible to readers".

## 5. Parallel work

- When checks are split across helpers or subagents, give each one the claim list, the
  four-state definitions and the required output line (state, source, date, method). Keep the
  writer and the checker separate when possible: the writer is the worst at spotting their own
  invention.
- Start with about 10 items to see the error patterns, then scale out.
