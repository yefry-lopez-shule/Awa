# Difficulty deliberately compounds

Difficulty appears twice in the ranking maths. It raises a course's weekly
**target** (`credits × hours_per_credit × difficulty`), which makes the course
look further behind, and it also multiplies the resulting **score**. A course
flagged `hard` is therefore amplified twice.

This looks like a bug. It is not. It was chosen over applying difficulty to the
target only, on the grounds that a course the student has flagged as killing them
*should* crowd out everything else until they unflag it.

## Consequences

- One careless `hard` flag buries every other course for a week. The only thing
  that prevents this is the Override Window: anything due within 48 hours outranks
  difficulty entirely. That window is configuration rather than a decision worth
  its own ADR — it is trivially reversible, and it exists purely as a floor under
  this one.
- Do not "fix" this by removing one of the two multiplications without reading
  this file first.
