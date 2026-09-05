# Institution-agnostic entities, but no pluggable rules

The app has exactly one user studying at exactly one institution, which argues for
hardcoding UNED throughout. We modelled `Institution → Program → Plan → Course`
as first-class entities anyway, because the move from the Diplomado to the
Bachillerato is scheduled rather than hypothetical, and the hierarchy is three
models and some foreign keys — an afternoon.

What we explicitly did *not* build is pluggable behaviour. Grading scales, pass
marks, credit-to-hours conversion and term calendars are plain configuration
fields on `Program`, not strategy classes. Adding an institution is a data file;
it is never a subclass.

## Consequences

- An institution whose rules don't fit a field — weighted GPA, ECTS conversion,
  variable-length terms — needs code, not config. Accepted: we would rather
  discover the real requirement than guess at it now.
- UNED's values (`pass_mark: 70`, `hours_per_credit: 3.0`, cuatrimestre of 15
  weeks) ship as seeded defaults, never as literals in logic.

## Considered Options

Full polymorphism — `GradingScheme` and `TermCalendar` subclasses covering GPA,
ECTS and 0–10 scales — was rejected. It is weeks of building and testing
conversions for institutions the single user does not attend, on a project whose
main risk is never shipping.
