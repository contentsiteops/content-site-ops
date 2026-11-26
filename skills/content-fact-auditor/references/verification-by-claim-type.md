# Verification by claim type (read when verifying; jump to the type you need)

Contents: 0 General rules · 1 price · 2 time/hours/dates · 3 quantity · 4 availability/state ·
5 absence · 6 superlative · 7 statistic · 8 first-person experience · 9 time-sensitive ·
10 named entity + attribute

## 0. General rules (apply to every type)

- **Identify who decides the fact first.** The operator of the facility, the chain's head
  office versus one branch, the municipality department that runs a park, the publisher of a
  study. Checking the wrong authority is the most common way to "verify" something wrongly.
- **Same-name entities.** Before matching, identify the entity by at least two of: address,
  operator, opening year. Names that differ by one word ("City Park" vs "City Central Park")
  are different entities until proven otherwise.
- **Rendered page vs raw HTML.** A non-JS fetch (curl, a fetch tool, "view source") returns
  everything in the HTML: comments, hidden elements, every state the page's JavaScript can
  show. Numbers (prices, hours) can usually be read from it; **states** cannot (see 4).
- **HTML comment trap.** Old notices, previous prices and withdrawn announcements are often
  left inside `<!-- … -->`. If a sentence is found only inside a comment or hidden element, it
  is not what the operator currently tells readers. Field observation in 2026 while auditing
  several content sites: stale price-change and "sold out" notices that existed only in
  comments or hidden elements were mistaken for live notices more than once.
- **"Could not load" is not "not there".** A timeout, 403, empty JS shell or PDF that will not
  parse means the check failed. Write `unverified (source could not be read: <reason>)`.
- **Search summaries and AI answers are not sources.** Follow them to the page they cite; if
  you cannot reach it, the claim stays `reported` at best.
- **Your own other articles** are the fastest place to find the operator's real URL and a
  previous conclusion. If two of your articles disagree, one of them is wrong: resolve it.

## 1. Price / money

- Authority: the operator's current price page (or booking page). For chains, the per-location
  page if prices vary by location.
- Check: amount, currency, tax included or not, age bands and their boundaries, weekday vs
  weekend, online vs gate price, the date the price took effect.
- A non-JS fetch is fine for reading the number; a "price revision" notice is a state (see 4).
- Prices in brand catalogs and gift sets drift upward; field observation: older articles most
  often went wrong on brand-product prices and on example products that no longer fit the
  stated price band.
- Write with an "as of <date>" and a re-check date.

## 2. Time / hours / dates

- Authority: the operator's hours or calendar page, plus its notices page.
- Check: opening and closing time, last entry, regular closing day, holiday exceptions,
  seasonal hours, the year of the calendar you are reading.
- A weekday closing rule ("closed on Wednesdays") often has exceptions (holidays, school
  breaks). Read the exceptions line before confirming.

## 3. Quantity / measurement

- Authority: the operator's spec, access or facility page.
- Walking minutes, parking spaces and floor areas from maps, reviews or blogs are `reported`.
- Rounded or "about" numbers: confirm the operator's own wording and keep the hedge.

## 4. Availability / state (sold out, open, closed, in stock, reservations required)

- **Must be seen on the live rendered page in a real browser.** A raw fetch cannot tell which
  of the states in the HTML is currently displayed. A saved copy only shows the state on the
  day it was saved. Without a live check the claim stays `unverified` (write
  "method: non-JS fetch" if that is all you had).
- Read notices to the end: date, which product/location it applies to, whether it is resolved.
- Partial external views mislead: RSS feeds, APIs and logged-out views show a limited window
  (for example only the newest items). "Missing from the feed" is not "discontinued". Confirm in
  the operator's own primary screen, or write `unverified (not visible in <view>)`.
- A dead guessed URL, an unreachable domain or a removed listing is not evidence of closure;
  the operator may have moved.

## 5. Absence / negation ("there is no…", "ありません", "非対応", "not available")

Before writing or confirming "none / no / not available", check **all** of these and list the
ones you checked:

1. The rendered listing (menu, facility list, product list) in a real browser, not a raw fetch
   (JS-rendered lists are often empty in raw HTML).
2. Campaign, seasonal and special pages (kids' menus, limited facilities, events).
3. Per-location pages for 2–3 locations (chains differ by branch; facility pages differ by
   building). Include the location-search results and photos when the operator shows them.
4. Your own other articles about the same entity (if one says it exists, one of them is wrong).

If it is still not found, the most you can write is scoped: "The official <page name> did not
list X as of <date>." Never "X does not exist". Field observation in 2026: "not listed"
conclusions about menus, prices and private rooms were wrong several times when only one page
had been checked; the item was on a per-location page or a JS-rendered list.

## 6. Superlative / ranking (best, No.1, only, largest, cheapest, 唯一, 最安)

- Needs a named, dated, checkable source (the ranking body, the year, the category).
- "Only", "first" and "largest" are factual claims that one missed competitor breaks. If you
  cannot cite the source, rewrite to a neutral description ("has a night safari").
- Self-made scores or rankings need the method written in the article; otherwise remove them.

## 7. Statistic / attribution ("according to", "a survey found", %, 調査によると)

- Trace to the original: publisher, title, year, sample size, question wording.
- "X% of parents" without a named survey is `unverified`; remove it or name the source.
- Aggregated "voices" ("150 reviews analyzed", "most visitors say") need the data and method;
  without them treat as fabricated-style wording (see `fabricated-experience.md`).

## 8. First-person experience

See `fabricated-experience.md`. No web source can confirm it.

## 9. Time-sensitive (limited-time, until <date>, campaigns, "currently", specific years)

- Record the end date stated by the operator, and add a **re-check date** to the report
  (the end date, or 30 days for open-ended "currently" claims, whichever is sooner).
- Unannounced or rumored items are `unverified` until the operator announces them.
- Re-verify before every republish; time-sensitive claims expire silently.

## 10. Named entity + attribute (facility has X)

- Identify the entity first (2 of address / operator / opening year).
- Authority: the entity's own facility or access page; for chains, the specific branch.
- "Multiple branches in the area" and "except some locations" must be counted from the
  operator's location search, not estimated.
- Do not move an attribute from one branch or one building to another.
