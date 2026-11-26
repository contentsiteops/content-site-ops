# Fact audit: Maple Leaf Zoo with Kids (input/article.md)

> Sample output: what the skill produces for the `absent-in-source-is-not-false` case after
> running both scripts (see `output/`) and reading every cited line. Fictional zoo.

- Audited on: 2026-11-25 · Auditor: assistant
- Article version: input/article.md
- Sources used: sources/source-notes.txt (user's copy of the zoo's official Prices, Hours and
  Facilities pages, captured 2026-11-20; no URLs given)
- Tools: extract_claims.py 0.1.0 (11 claims), check_against_sources.py 0.1.0

## 1. Summary

| State | Count |
|---|---|
| confirmed | 3 |
| reported | 0 |
| unverified | 7 |
| contradicted | 1 |
| **total claims** | 11 |

Hidden text blocks: 0 · First-person experience items: 2 (heading + 1 sentence) · Re-check dates set: 1

Verdict: Do not publish until the items in section 6 are resolved and the adult price is corrected.

## 2. High-risk claims

| id | claim (line) | state | evidence | checked on | fix |
|---|---|---|---|---|---|
| C006 | There is no nursing room at Maple Leaf Zoo… (L19) | unverified | Not in source-notes.txt. The facilities list (L14–19) does not mention one, which does **not** show there is none. | 2026-11-25 | Remove the sentence, or check the live Facilities page, the park map and ask the zoo. |
| C009 | When we visited last spring, my kids loved feeding the giraffes… (L24) | unverified (first-person, no record) | No source can confirm a personal visit. | — | Ask the writer for a record. Without one, delete, or state only a sourced fact (e.g. whether giraffe feeding is offered, from the official Activities page). |
| C010 | According to a survey, 9 out of 10 parents say the zoo is stroller-friendly. (L25) | unverified | No survey named; not in sources. | — | Remove, or name the survey (publisher, year, sample). |

## 3. Other claims

| id | claim (line) | state | evidence | checked on | fix / note |
|---|---|---|---|---|---|
| C001 | Maple Leaf Zoo is the best zoo in the region… (L8) | unverified | Opinion; no ranking source. | — | Rewrite neutrally or cite a named ranking. |
| C002 | Adult admission is $18, and children aged 3 to 12 pay $12. (L12) | contradicted (adult) / confirmed (child) | source-notes.txt:5 "Admission: Adults $22"; :6 "Children (3-12): $12" (user copy, 2026-11-20) | 2026-11-25 | Change adult price to $22; add "as of" date. |
| C003 | Children under 3 get in free. (L13) | confirmed | source-notes.txt:7 "Under 3: free" | 2026-11-25 | — |
| C004 | The zoo opens at 9:00 a.m. and closes at 5:00 p.m. every day. (L14) | confirmed (hours) | source-notes.txt:11 "Open daily 9:00 a.m. - 5:00 p.m." | 2026-11-25 | Consider adding last entry 4:00 p.m. and the Dec 25 closure (source-notes.txt:11–12); "every day" conflicts with the Dec 25 closure. |
| C005 | The zoo has a splash pad that opens in summer. (L18) | unverified | Not mentioned in source-notes.txt. Not mentioned ≠ does not exist. | — | Check the official Facilities/Activities page before keeping. |
| C007 | Stroller rental is available at the main gate. (L20) | confirmed (that the service exists) | source-notes.txt:16 "Stroller rental at the main gate ($8 per day)" | 2026-11-25 | Availability on a given day is a state; do not promise it. |
| C011 | Annual passes are on sale until December 31, 2026. (L29) | unverified | source-notes.txt:8 lists annual pass prices but no sale end date. | — | Check the end date on the live page; set re-check date. |

## 4. Hidden text (not visible to readers)

None found.

## 5. First-person experience

| id | sentence (line) | record provided? | action |
|---|---|---|---|
| C008 | "Our visit" (heading, L22) | no | Remove the heading once the sentences below are handled. |
| C009 | When we visited last spring, my kids loved feeding the giraffes at the Savanna Deck. (L24) | no | Delete, or replace with a sourced neutral fact. Do not rewrite as "our family's favorite…". |

## 6. Not verified — do not publish as fact

- [ ] C005 splash pad — check the official Facilities or Activities page (and seasonal pages).
- [ ] C006 "no nursing room" — check the live Facilities page, the park map, and ask the zoo.
- [ ] C009 giraffe-feeding visit — writer's own record, or delete.
- [ ] C010 survey statistic — named source, or delete.
- [ ] C001 "best zoo in the region" — named ranking, or neutral rewrite.
- [ ] C011 annual pass sale end date — live official page.

## 7. Re-check dates

| id | claim | expires / re-check on |
|---|---|---|
| C011 | Annual passes on sale until December 31, 2026 | 2026-12-31 (and before any republish) |

## 8. Notes and corrections to this audit

- check_against_sources.py marked C011 `mentioned-needs-reading`: the related line has prices
  but no date, so it stays unverified.
- The notes have no URLs. Prices were treated as the operator's text because the user said they
  were copied from the official pages on 2026-11-20; re-open the live Prices page before
  publishing if the notes are older than the article update.
