# Reason strings are structured data, rendered per locale outside rank()

#1 specified `rank()` returning a `reason_string` — English prose like *"exam in 3
days · 30% of grade · 12h behind"* — as part of its pure-function output. Decision
18 requires a bilingual UI from day one, and a hardcoded English sentence cannot
satisfy that without either baking a language parameter into `rank()` or
translating a string after the fact by pattern-matching it back apart, both of
which corrupt the one property ADR-0007 and ADR-0008 built that function around:
plain data in, plain data out, no external concern threaded through it.

`rank()` (and `forecast()`, #4) now return a **structured reason**: which rule won
— Override, Deadline Pressure, or Hours Behind — plus the raw values that rule
used (item name, weight, days remaining, hours behind). A separate rendering layer
turns that structure into a sentence, in whichever locale is active, using message
templates with placeholders for the values. `rank()` itself contains no string
depending on locale.

## Consequences

- **This amends #1's interface**, published before this decision existed. Every
  seam-1 test asserting a literal reason string must instead assert the structured
  fields the rule selected; a new seam-3-level test (or an extension of #4's
  forecast tests) confirms the same structure renders correctly in both `es` and
  `en`.
- Course names, códigos, and anything sourced from the plan file are never part of
  the translated template — they are inserted as-is into whichever locale's
  sentence is being built, because a course's name is a fact about the real
  curriculum, not UI chrome (§ decision 18's "English identifiers" already implies
  this for code; it now applies to rendered text too).
- Two message catalogs (`es`, `en`) carry the sentence templates — *"{item} due in
  {days} days · {weight}% · {behind}h behind"* and its Spanish equivalent — rather
  than two copies of the engine.
- This generalizes past reason strings: any generated sentence with interpolated
  values (the forecast's verdict text, the degree map's "opens next term" label,
  the staleness banner) follows the same shape — structured data from the pure
  function or query, template rendering at the view.

## Considered Options

Passing a language argument into `rank()` was rejected because it makes tonight's
recommendation depend on which locale happened to be active when it was computed,
and it means every one of seam 1's table-driven cases (#1) doubles to cover both
languages, testing rendering rather than ranking. Post-hoc string translation —
running the finished English sentence through a lookup table — was rejected as
unworkable in general: a sentence with a course name, a percentage and an hour
count embedded in it is not a fixed string to look up, and pattern-matching it back
into parts to translate is more fragile than never assembling English prose inside
the engine in the first place.
