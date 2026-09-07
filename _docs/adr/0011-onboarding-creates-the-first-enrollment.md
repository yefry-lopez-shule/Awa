# Onboarding creates the initial Term and Enrollment for in-progress Courses

Onboarding is Phase 0; Cuatrimestre setup — the only place #1 otherwise creates a
Term and an Enrollment — is Phase 2. The student is mid-Diplomado, so some of the
23 checklist rows are genuinely in progress right now, not merely historical. If
onboarding only wrote `Course.Status = IN_PROGRESS`, the ranking engine specified in
#1 — which ranks over Enrollments — would have nothing to rank on day one, for
however long Phase 1 and Phase 2 are apart in the build. That defeats shipping the
recommender in Phase 1 at all.

Marking a Course in progress during onboarding therefore asks for the same handful
of fields Cuatrimestre setup would: current term dates, asked once and shared
across every in-progress Course, and a Difficulty flag per Course. It creates the
Term and Enrollment there and then.

## Consequences

- This is a deliberate, narrow duplication of one slice of Cuatrimestre setup's
  job. The deadlines grid, term closeout and the rest of setup are still Phase 2
  only — onboarding creates the Enrollment and nothing else about it.
- The Term onboarding creates is an ordinary Term. The first real run of
  Cuatrimestre setup, once it ships, finds it already open and offers closeout for
  it in the normal way — there is no special "onboarding term" to migrate away
  from.
- Resolves the build-order dependency #1 left open ("Phase 1 builds deadline logic
  that Phase 2 supplies the data for"): the deadlines grid still ships in Phase 2,
  but Graded Items can be added from Course detail in the meantime (per #1), so the
  engine's deadline half is exercisable before Cuatrimestre setup exists, not only
  by fixtures.

## Considered Options

Writing `Course.Status = IN_PROGRESS` with nothing behind it was rejected because
it leaves the recommender dead until Phase 2 ships, which could be a real gap
depending on how the phases land. Excluding "in progress" from the onboarding
picker entirely — routing every currently-active Course through Cuatrimestre
setup's normal flow immediately after onboarding — was rejected because it
contradicts scope.md §5's onboarding checklist covering all 23 rows with a status
picker, and because Cuatrimestre setup doesn't exist yet in this build order for
the student to be routed to.
