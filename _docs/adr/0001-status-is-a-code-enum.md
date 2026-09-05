# Status is a code enum, not configurable data

Every other piece of curriculum vocabulary — courses, blocks, credits, graded item
types — is data loaded from a plan file, so a configurable status list is the
obvious next step. We deliberately didn't. The engine *branches* on status:
prerequisite unlocking asks "does this satisfy?", the degree map asks "do these
credits count?", grade forecasting asks "is there a mark here?". A status the user
can invent is a status the engine cannot interpret.

The five statuses — pending, in progress, passed, transferred, failed — are a code
enum with fixed semantics. Only their display labels are data, so they translate.

## Consequences

- An institution with a status we didn't anticipate has to map it onto one of the
  five, or we change code.
- `transferred` exists specifically because of real convalidaciones from a prior
  Física degree: it satisfies prerequisites and counts credits but holds no grade.
  Collapsing it into `passed` would have quietly invented grades.

## Considered Options

A configurable status table carrying `satisfies_prereq` / `counts_credits` /
`has_grade` flags would preserve the semantics while allowing new statuses. It was
rejected as machinery serving a case that does not exist: the flags *are* the five
statuses, enumerated.
