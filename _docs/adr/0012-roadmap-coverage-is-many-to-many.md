# Roadmap coverage is many-to-many, and not every link needs a Course

ADR-0006 established that Roadmap Entries "hang off Courses" — read at the time as
one Course per entry, which is how the original data model sketch drew it:
`RoadmapEntry(university, code, name, links, course FK, coverage note)`. The actual
spreadsheet contradicts this in both directions. Harvard's CS 50 covers both
`03071` and `00831`, each with its own note — one entry, two Courses. And several
entries' only coverage is a convalidación from the student's prior Física degree —
*"Completado — título en Física: Cálculo I"* — which names no UNED Course at all,
because none of Cálculo I, Cálculo II or Álgebra Lineal is a course in this
78-crédito plan; they exist only as ADR-0001's justification for why `TRANSFERRED`
is a status, not as seeded data.

A Roadmap Entry now has zero or more **Coverage Links**. A Coverage Link's Course
reference is nullable: where a real Course exists, the link points at it; where the
coverage is a fact about study elsewhere with nothing to point to, the link carries
only its note.

## Consequences

- A Coverage Link with a Course reads that Course's Status live. Passing `00831`
  next term turns Harvard CS 50 from partially- to fully-covered with no
  re-import — the reference view stays honest without the student re-running the
  Excel-to-import pipeline every time real progress changes it.
- A Coverage Link with no Course carries a status captured once at import and
  never recomputed, because there is no live Course behind it to check. A Roadmap
  Entry's overall coverage rolls up from whichever links it has, live and frozen
  together.
- This is not a second Institution. Modeling the prior Física degree as a real
  Institution with seeded Courses for Cálculo I/II and Álgebra Lineal would give
  every Coverage Link a Course to point to, at the cost of catalog entries that will
  never be enrolled in, scheduled, or ranked — the same reference-only weight
  ADR-0002 already declined to carry for institutions the student doesn't attend.
- `university` on Roadmap Entry stays a plain string, not a foreign key to
  `Institution`. Harvard, Stanford, MIT and Caltech are comparison points, never
  places the student enrolls — modeling them as `Institution` would misstate what
  that entity means everywhere else it's used.
- The foreign side's código and name are stored verbatim, including the messy
  cases — `"18.01 / 18.02 / 18.03 / 18.06"` is one string, not four parsed
  alternatives. Nothing downstream reasons about it; it is read, not interrogated.

## Considered Options

Splitting a multi-course cell into several Roadmap Entries — one per UNED
Course — was rejected because it duplicates the foreign course's name and links and
makes "Harvard CS 50" appear twice in the reference view as if it were two
different courses. Restricting Coverage Links to always require a Course, and
dropping the convalidación notes that don't resolve to one, was rejected as
discarding real information the student curated on purpose, and specifically on
the rows that happen to already be fully done.
