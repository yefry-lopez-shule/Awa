# No Django admin; every screen is custom

Django admin would have supplied free CRUD for enrollments, graded items, study
logs and availability blocks, cutting v1 to roughly one custom screen. We're
building all eight by hand instead.

The reason is not technical. This project is also a portfolio piece and a learning
exercise on a Computer Science track, and admin screens would remove most of the
work worth doing. The cost is roughly a threefold increase in v1, spent largely on
setup screens touched twice a cuatrimestre.

## Consequences

- v1 lands in roughly 8–11 weeks rather than 2–3, which means it will not be in
  use during the cuatrimestre it was scoped in. This was accepted knowingly.
- Curriculum reference data is the deliberate exception — it has no UI at all
  (ADR-0003).
