# Courses belong to the Institution; Plans reference them

The obvious hierarchy is `Institution → Program → Plan → Block → Course`, with each
Plan owning its own Courses, and that is how the scope document originally drew it.
We inverted the bottom of it: a **Course belongs to the Institution** and is a pure
catalogue entry — código, name, créditos — which Blocks reference through a
**BlockEntry** rather than contain.

The reason is the migration ADR-0002 says is scheduled rather than hypothetical.
The Bachillerato's plan file contains `03304 Lógica Algorítmica` too. Under
plan-owned Courses, loading it creates a second row for a código the student has
already passed: the new degree map shows it pending, its prerequisite chain stays
locked, and its four créditos don't count. Every Status recorded against the
Diplomado would be stranded on rows nothing points at any more.

## Consequences

- **Prerequisites hang off the Plan, not the Course.** A shared Course cannot own a
  prerequisite chain, because two Plans may legitimately require different things of
  it, and whichever plan file loaded second would silently overwrite the first.
  Unlocking is therefore always scoped to the Plan being studied — which the degree
  map already is. Prerequisite lists are conjunctions: the source separates them
  with commas, and reading `00831` as a disjunction would let a student begin
  Introducción a la Programación having passed only Inglés II.
- **`loadplan` reconciles rather than overwrites.** A second plan file naming a
  código that already exists must agree about its créditos; disagreement fails the
  load. Reference data that changes quietly underneath recorded history is worse
  than a refused import.
- **A Slot is a BlockEntry whose Course is null.** The plan states *"2 Asignaturas
  de humanidades (créditos: 3)"* — four such Slots across Bloques A, B and D, 12 of
  the 78 créditos, with no código and no name. Because a BlockEntry carries its own
  créditos, a Plan totals 78 whether or not its Slots are filled, and filling one is
  an assignment rather than a special case.
- **Do not "simplify" Slots into placeholder Courses.** Synthetic códigos in the
  catalogue is the first fix anyone will reach for, and it is the one thing this
  structure forbids: Courses are institution-wide, so `HUM-1` would collide across
  Plans, and renaming it once *Ética* is chosen would rewrite a row two Plans point
  at.
- Filling a Slot creates a catalogue Course from a código and a name typed at the
  point of enrolment, créditos inherited from the Slot. This is not the CRUD that
  ADR-0003 rejected: which humanities course a student chose is student data that no
  plan file can know.

## Considered Options

Plan-owned Courses match the original sketch and give each plan file total
ownership with no reconciliation at load — rejected only because of the
Diplomado→Bachillerato migration, which is scheduled. Tracking Status per Program
rather than per Institution would model how universities actually treat
convalidación *between* programmes, and was rejected as machinery for a case that
does not arise for one student moving up within one institution. Collapsing Plan
into Program removes a model but with it any way to represent IIC-2026 against a
later revision of the same programme.
