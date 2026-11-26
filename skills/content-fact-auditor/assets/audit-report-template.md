# Fact audit: {{article title or file}}

- Audited on: {{YYYY-MM-DD}} · Auditor: {{name / "assistant"}}
- Article version: {{file name, commit, or URL + date fetched}}
- Sources used: {{list: URL or file, how read (browser / fetch / user copy), date}}
- Tools: extract_claims.py {{version}} ({{N}} claims), check_against_sources.py {{yes/no}}

## 1. Summary

| State | Count |
|---|---|
| confirmed | {{n}} |
| reported | {{n}} |
| unverified | {{n}} |
| contradicted | {{n}} |
| **total claims** | {{N}} |

Hidden text blocks: {{n}} · First-person experience items: {{n}} · Re-check dates set: {{n}}

Verdict: {{"Do not publish until the items in section 6 are resolved" / "OK to publish after the fixes in section 2"}}

## 2. High-risk claims

| id | claim (line) | state | evidence (URL or file:line) | checked on | fix |
|---|---|---|---|---|---|
| {{C001}} | {{text}} (L{{n}}) | {{contradicted}} | {{source:line "quoted value"}} | {{YYYY-MM-DD}} | {{change X to Y}} |

## 3. Other claims

| id | claim (line) | state | evidence | checked on | fix / note |
|---|---|---|---|---|---|

## 4. Hidden text (not visible to readers)

These were found in HTML comments or hidden elements. They were **not** audited as published
claims and **not** used as evidence.

| id | kind | line | content | recommendation |
|---|---|---|---|---|
| {{H01}} | {{html-comment}} | {{n}} | {{text}} | {{delete stale notice / keep}} |

## 5. First-person experience

| id | sentence (line) | record provided? | action |
|---|---|---|---|
| {{C010}} | {{text}} | {{no}} | {{neutral rewrite: "..." / delete}} |

## 6. Not verified — do not publish as fact

Each item below needs the user (or a source) before it can stay in the article as a fact.

- [ ] {{C006}} {{claim}} — what to check: {{page / place}} — why it is open: {{not mentioned in the provided sources}}

## 7. Re-check dates

| id | claim | expires / re-check on |
|---|---|---|

## 8. Notes and corrections to this audit

- {{false positives found, detector issues, places that could not be read}}
