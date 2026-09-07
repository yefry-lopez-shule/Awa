# Status belongs to the Course; an Enrollment carries an Outcome

`CONTEXT.md` defines Status as where the student stands on a **Course**, while the
scope document's sketch hung it off Enrollment — "one Course taken in one Term".
Both cannot be true, and the seed data settles it: five Courses are already passed
(`03068`, `03071`, `03304`, `04168`, `00823`) from before the app existed, with no
Term, no grade and no Graded Items; every convalidación is `transferred`, which
means precisely that no Enrollment ever happened; eight more are `pending`; and the
onboarding checklist writes a Status to all 23 rows before a single Term exists.

So the five-value Status of ADR-0001 is **stored per Course** and is what
prerequisite unlocking, the degree map and créditos-earned interrogate. An
Enrollment carries a narrower **Outcome** — in progress, passed, or failed — which
describes one attempt.

## Consequences

- Two enumerations that look mergeable are not. An Outcome has no `pending` (you
  enrolled) and no `transferred` (that is the absence of an attempt). Collapsing
  them means either inventing Enrollments with a null Term to hold statuses for
  things that never happened, or losing the retakes that Enrollment exists for.
- Status is written from two places: onboarding, directly, for Courses with no
  history; and the term closeout, which records an Outcome and updates the Status
  from it. Nothing else writes it, and the closeout always asks for confirmation —
  a derived Status is a suggestion, never a silent write.
- A retake keeps both attempts. A Course failed in one cuatrimestre and passed in
  the next has two Enrollments with different Outcomes and one Status: passed. The
  failed attempt keeps its grade.
- Because Status is per Course and Courses are institution-wide (ADR-0009), a pass
  carries into the Bachillerato automatically. That is the point of both decisions
  together.
- `transferred` has **no instance in the Diplomado's seed data**. ADR-0001
  justifies it with convalidaciones for Cálculo I/II and Álgebra Lineal, none of
  which are courses in this 78-crédito plan — they belong to the Bachillerato. The
  status is correct and currently unused; nobody should go looking for the missing
  row.

## Considered Options

Deriving Status entirely from Enrollments is the tidier design and cannot drift out
of sync — it was rejected because thirteen of the nineteen named Courses have no
Enrollment to derive from, and manufacturing empty ones purely to hold a status is
worse than storing it. Keeping Status only on Enrollment matches the original
sketch but makes "is this prerequisite satisfied" a query over rows representing
things that never occurred. Storing Status on the Course with no Outcome at all is
the simplest of the four, and loses a failed attempt and its grade the moment a
Course is retaken.
