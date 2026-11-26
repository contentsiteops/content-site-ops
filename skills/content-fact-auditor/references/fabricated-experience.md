# Fabricated first-person experience (read when the extractor flags `experience`)

AI drafts routinely invent experiences: "When we visited last spring…", "我が家も行ってきました",
"I tried the kids' menu", "our editors tested 30 shops". Readers and search engines treat these
as first-hand evidence. If they did not happen, they are fabricated, whatever the intent.

## What counts

Flag as first-person experience (the extractor does this):

- First-person subject + experience verb: I/we visited, tried, stayed, ate, used, tested;
  実際に行った／使った, 行ってみた, 行ってきました, 食べてみた.
- Family or team as narrator: my kids, our family, 我が家, うちの子, 筆者, 編集部が訪れて.
- Experience section headings ("Our visit", "体験談", "我が家の体験メモ") — every sentence under
  them is treated as experience, even sentences without "I/we".
- Claimed first-hand research: "we surveyed 50 parents", "visited 30 locations", "a year of
  weekly visits", anonymous quotes such as "Ms. A (30s, mother of a toddler) says…".

Not experience (the extractor ignores these):

- Generic reader address: "if you visit with your family", "我が家に合う選び方".
- Activity nouns: "乗馬体験ができます", "hands-on exhibits" as a facility description is borderline;
  read it.
- Explicit disclosures: "we have not visited yet", "実際には行っていません".
- Sections clearly labeled as hypothetical / example / 想定例 / 架空.

## How to label

- With the writer's own record (date, photos, receipt, notes) that matches the sentence:
  `confirmed — writer's record <what>, <date>`.
- Without such a record: `unverified — first-person experience, no record`. It must not be
  published as is. Never mark it contradicted just because you lack a record; you do not know
  it did not happen. Ask the user.

## Rewrite rules (when there is no record)

1. **Replace with neutral facts, not with a new experience.** Turn "When we visited, my kids
   loved feeding the giraffes" into the checkable fact behind it, if a source supports it:
   "Giraffe feeding is offered at <place> (<times>, <price>) according to the official
   Activities page, checked <date>." If no source supports the fact, delete the sentence.
2. **Do not paraphrase into a different first-person form.** "We loved…" → "Our family's
   favorite was…" or "No.1 at the zoo" → "the one our family visits most" is still a fabricated
   experience, and an automated guard will count it as a new one. When removing a superlative
   inside an experience passage, keep only the name ("Giraffe feeding.") or delete.
3. **Do not move facts into the experience voice.** Prices, floors, rental availability,
   closing days and parking counts belong in the factual sections with a source, not inside a
   story ("we paid $18 and parked on level 2").
4. **Do not invent a disclosure either.** Do not add "we visited in 2025" to make a claim look
   supported. If the user says the experience is real, ask for the record and its date, and
   write only what the record shows.
5. **Delete orphaned experience headings** once the sentences under them are rewritten.
6. After rewriting, rerun `extract_claims.py` and confirm the experience count went down and
   no new experience items appeared.

## What to tell the user

List each experience claim with its line, say plainly that no source can confirm it, and ask:
"Did this happen? If yes, what record do you have (date / photo / receipt)? If not, here is a
neutral rewrite or a deletion."
