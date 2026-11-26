# Evidence states (read before labeling any claim)

Every claim in an audit gets exactly one of four states. A claim with no state is not written
as fact. Script outputs (`*-candidate`, `not-found-in-provided-sources`) are inputs to this
decision, never the decision itself.

| State | Condition (all must hold) | How to write it in the report | How to write it in the article |
|---|---|---|---|
| **confirmed** | You read the primary source's own text in this session: you opened it yourself, or the user supplied a copy of it that names the page (URL preferred) and the capture date. For a *state* (sold out, open, closed) the source is the live rendered page, not a saved copy or raw fetch. | `confirmed — <URL or file:line>, checked <YYYY-MM-DD>, method <browser / fetch / user copy>` | State it plainly. Keep the source and date in your notes or an "as of" line. |
| **reported** | A secondary source says it (news article, review site, search snippet, AI answer, a subagent's summary, your own older article). | `reported — <who says it>, <URL>, seen <date>; primary not opened` | "According to <source>, …" — or upgrade to confirmed before publishing if it matters. |
| **unverified** | You could not reach a source, or the sources you saw do not mention it. | `unverified — looked at: <places>; not mentioned there` | Do not write it as fact. Do not write the opposite either. Remove, or write "we could not confirm X on <named page> as of <date>". |
| **contradicted** | A primary source (or the user's dated copy of it) says something different about the same thing. | `contradicted — article says <X>; source says <Y> (<URL/file:line>, <date>)` | Correct it to the source value, then search the article (and sibling articles) for every other copy of the old value. |

## Rules that decide the borderline cases

1. **"Not found" is never "does not exist".** If the sources are silent, the claim is
   `unverified`. This applies in both directions: a claim that something exists is not false
   because a page omits it, and a claim that something is absent ("there is no nursing room")
   is not confirmed because a page omits it.
2. **Script candidates are hints.** `contradicted-candidate` means "a related line has a
   different number". Open the cited line and check that it is about the same thing (same age
   band, same location, same season, tax included or not). If it is not, the claim is
   `unverified`, not contradicted.
3. **Hidden text is not evidence.** HTML comments, `display:none` blocks, `<template>` and
   `<noscript>` content are not shown to readers. Text found only there cannot confirm or
   contradict anything; report it in the hidden-text section.
4. **A date in one place does not audit the whole article.** A single "checked on" / 確認日 line
   only covers what was actually checked. Label each claim on its own.
5. **Partial checks stay partial.** If you checked the adult price but not the child price, the
   child price is `unverified`. Do not round a mostly-checked sentence up to confirmed.
6. **Secondary sources stay secondary**, including search-engine summaries, AI answers, review
   aggregators and your own team's notes or older articles: they record what was true when they
   were written.
7. **Knowledge-cutoff topics** (prices, schedules, availability, product specs, anything that
   changes) are never confirmed from memory. Memory gives at most "unverified — recalled".
8. **First-person experiences** cannot be confirmed by any web source. Only the writer's own
   record (date, photos, receipt, notes) supports them. See `fabricated-experience.md`.
9. **When you discover your own earlier label was wrong, say so** in the report rather than
   silently changing it.

## Report line format

```
C012 · "Adult admission is $18" · contradicted · source: notes.txt:5 "Adults $22" (user copy of the official Prices page, captured 2026-11-20) · fix: change to $22 and add "as of <date>"
```
