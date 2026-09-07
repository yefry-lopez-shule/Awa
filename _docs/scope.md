# Awá — Scope

> **Awá** — named for the *awá*, the traditional healer of the Bribri people of
> Talamanca, Costa Rica: the one who holds the deep knowledge and guides others.
> Display name `Awá`. All technical identifiers use plain `awa` (repo, Django
> project, modules, any future domain) to avoid diacritic friction.

**Status:** scoped, not yet built
**Date:** 2026-09-03
**Owner:** Yefry Lopez

**Related:** [`CONTEXT.md`](../CONTEXT.md) — the glossary · [`adr/`](./adr/) — the
eleven decisions that were hard to reverse, surprising, and genuinely contested ·
[GitHub issues](https://github.com/yefry-lopez-shule/Awa/issues) — specs #1–#4,
ready for an agent

> **Revised 2026-09-05.** The ranking engine was grilled end to end and §4, §6 and
> locked decisions 5 and 7 changed materially. See ADR-0007 and ADR-0008.

---

## 1. What this is

A Django app that answers three questions for one student:

1. **What do I study tonight?** — the primary job
2. **Am I going to pass?** — grade forecasting per course
3. **How far through the degree am I?** — block/prerequisite progress

Built around the **UNED Diplomado IIC-2026** (Ingeniería Informática, Costa Rica),
but institution-agnostic underneath: UNED ships as the default seeded data, not as
a baked-in assumption.

### What this is not

- A calendar
- A todo app
- A life manager

Work, class, gym and chores exist **only as blocks that consume hours**. They are
never tasks, never scheduled by the app, never recommended.

---

## 2. Source material

Both inputs live in [`Idea/`](../Idea/):

| File | Role |
|---|---|
| `UNED_STUDY_PLAN.png` | **The core.** Bloques A–E, 78 créditos, 19 named courses + 4 humanities slots, códigos, prerequisite chains. Seeds the plan. |
| `CS_Bachelor_Roadmaps_Harvard_Stanford_MIT_Caltech_v2.xlsx` | **Reference only.** 4 sheets mapping UNED courses to their Harvard/Stanford/MIT/Caltech equivalents. Curated in Excel, imported flat, read-only in the app. Explicitly *not* a track that competes for hours. |

### The plan, as parsed

| Bloque | Créditos | Courses |
|---|---|---|
| **A** | 16 | `03304` Lógica Algorítmica (4) · `03068` Matemáticas para Computación I (3) · `00997` Inglés para Informática (3) · 2× humanidades (3 ea.) |
| **B** | 15 | `04038` Principios de Administración (3) · `03071` Lógica para Computación (3, req 03304) · `03069` Matemáticas para Computación II (3, req 03068) · `03072` Inglés para Informática II (3, req 00997) · 1× humanidades (3) |
| **C** | 16 | `00831` Introducción a la Programación (4, req 03071/03069/03072) · `00823` Organización de Computadoras (4, req 03069/03071) · `00226` Contabilidad I (4, req 03068) · `04168` Estadística para Informática (4) |
| **D** | 17 | `00824` Programación Intermedia (4, req 00831) · `00826` Base de Datos (3, req 00831) · `03306` Arquitectura de Computadores (4, req 00823/00831) · `00883` Telemática y Redes (3, req 00823/00824) · 1× humanidades (3) |
| **E** | 14 | `00830` Programación Avanzada (4, req 00824/00826) · `03300` Ingeniería del Software (4, req 00824/00826) · `00825` Estructuras de Datos (3, req 00824) · `00881` Sistemas Operativos (3, req 00824/00823) |

**Total: 78 créditos.**

### Status already recoverable from the spreadsheet

```
Aprobado:   03068 · 03071 · 03304 · 04168 · 00823
Pendiente:  00824 · 00825 · 00826 · 00831 · 00881 · 00883 · 03300 · 03306
Unknown:    00997 · 03069 · 03072 · 04038 · 00226 · 00830 + 4 humanities slots
```

Thirteen of nineteen named courses seed themselves. No typing required.

---

## 3. Locked decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Primary job is **"what do I study right now"** | Chosen over deadline-capture, progress-dashboard and habit-tracking. The 20 minutes lost deciding is the actual pain. |
| 2 | **No task list.** Courses + weekly hour targets are the unit of planning | Task lists rot. A course list doesn't. |
| 3 | Hour logging is **free-form** — no forced daily ritual | Accepted with eyes open; see Risk 1. |
| 4 | **Availability template**: study window per weekday, minus work, class, gym, chores as recurring blocks | Derives real capacity so the app can say "you need 39h, you have 21h." |
| 5 | Ranking = `difficulty × (w_behind × hours_behind + w_deadline × pressure)`, measured against the **Ration** | Revised; see §4, ADR-0007, ADR-0008. |
| 6 | **Difficulty compounds** — it raises the target *and* multiplies the score | Deliberate. A course flagged hard should dominate until unflagged. |
| 7 | **48h deadline override**, for items worth ≥10% of the grade | The floor that prevents the only truly stupid recommendation — with a weight floor so it doesn't create a new one. |
| 8 | Graded items carry date, weight **and score**; app forecasts | "You need ≥62 on the final to pass" turns anxiety into a number. |
| 9 | Progress = whole degree map + streaks | Bloques A–E, prerequisite unlocking, what next cuatrimestre opens. |
| 10 | **Streak = days you logged any study.** Surplus-hours rule dropped | Streak doubles as the logging-decay alarm. |
| 11 | Self-study roadmap is **reference only**, curated in Excel, imported flat | Demoted from a competing track. "Not a must — only for my internal progress." |
| 12 | **Institution-agnostic entities**, UNED as shipped default | `Institution → Program → Plan → Course`. |
| 13 | **No pluggable rules** — grading and calendar are plain config fields on `Program` | Strategy classes for institutions you don't attend are pure cost. |
| 14 | Plans authored as **YAML + `manage.py loadplan`** | Reference data changing once a year does not deserve a UI. |
| 15 | Scoring: **formula in code, constants in config** | Structure must be one tested function or the "why" line can't be honest. |
| 16 | **Five fixed statuses** with fixed semantics; labels translatable | The engine branches on them. See §6. |
| 17 | Graded item types **configurable per program** | The engine only reads `weight` and `due_date`. Nothing to preserve. |
| 18 | **English identifiers, bilingual `es` + `en` UI** from day one | Retrofitting Django i18n is painful; wiring it early is nearly free. |
| 19 | **Full custom UI, no Django admin** | Accepted at ~3× the build cost; see Risk 2. |
| 20 | **Foundation first**, timeboxed, recommender immediately after | Risk of stopping at a pretty degree map is real; timebox is the mitigation. |
| 21 | v1 is **local-only, single user** | Hosting and notifications deferred. |
| 22 | Name: **Awá** (display) / `awa` (code) | Bribri, Talamanca. Names the advisor, not the data. |

---

## 4. The ranking engine

Runs over Enrollments in the current Term whose status is *in progress*.

```
target       = créditos × hours_per_credit × difficulty
ration       = target × min(1, capacity / Σ targets)      ← scales down only
behind       = max(0, ration − hours_logged_trailing_7_days)

pressure     = max over graded items with due_at > now of
                 (weight / grade_scale_max) × 0.5^(days_until / half_life)
               0 when nothing is upcoming

score        = difficulty × (w_hours_behind × behind + w_deadline × pressure)

qualifies    = an upcoming item due within `override_window_hours` (48)
               AND its weight ≥ `override_min_weight` (10%)

tier 1       = qualifying courses, ranked by pressure
tier 2       = everything else, ranked by score
winner       = top of tier 1 if any, else top of tier 2

hours        = min(hours left in today's study window, ration − logged_7d)
output       = (winner, hours, reason_string)
```

**Target is what a course demands; Ration is what it gets.** The gap between
Σ targets and capacity is the overload warning — it is never ranked on, and never
scaled away. ADR-0007.

**`w_deadline` is a unit conversion**, not a taste knob: how many hours of neglect
a full-weight item due today is worth. ADR-0008.

**Three hard rules:**

1. **It always shows its reasoning in one line.** `"exam in 3 days · 30% of grade · 12h behind"`. With three weighting knobs, an unauditable score is one you stop believing.
2. **It never asserts a deficit it invented.** Past a staleness threshold the banner still names a course, but labels what it is standing on: *"no logs since Saturday — this assumes you studied nothing."* v1 has no nudge (Risk 1), so the honest label is the whole defence.
3. **Deadlines lift, never suppress, and only look forward.** An item past its due date contributes nothing: tonight cannot change it, and the decay term grows explosively on negative inputs.

`score()` is one function, ~40 lines, fully unit-testable, returning the number,
the hours and the explanation.

---

## 5. Screens (8)

| # | Screen | Contents |
|---|---|---|
| 1 | **Onboarding checklist** | All 23 course slots with a status picker, prereqs validated live. ~24 taps, once. Grade field optional. |
| 2 | **Dashboard** (home) | Recommendation banner on top, course cards below. |
| 3 | **Quick log** | Course + hours + optional "left off" note. |
| 4 | **Course detail** | Hours vs ration, graded items **editable in place**, scores as they arrive, current weighted grade, pass forecast. |
| 5 | **Cuatrimestre setup** | Close last term, then term dates, enrol courses, difficulty flags, deadlines grid. |
| 6 | **Availability template** | Study window per weekday, minus recurring blocks; derives capacity. |
| 7 | **Degree map** | Bloques A–E, créditos earned, prerequisite unlocking, what next term opens. |
| 8 | **Roadmap reference** | Harvard/Stanford/MIT/Caltech equivalences, read-only. |

Reference data (institutions, programs, plans, courses) has **no UI** — it loads from YAML.

### What using it actually looks like

**Once, ever.** The onboarding checklist: 23 course slots, a status each, ~24 taps.

**Once per cuatrimestre — about ten minutes.** All of it in Cuatrimestre setup, in
this order:

1. **Close the last term.** Enrolments from the previous cuatrimestre appear with a
   status derived from the weighted grade against `pass_mark`; confirm or override.
   This blocks the rest of the screen, so it cannot be skipped — and skipping it is
   what would leave the degree map wrong and prerequisites locked.
2. **Term dates.**
3. **Enrol.** Tick courses from the seeded plan. Codes, names, créditos and
   prerequisites are already there; nothing is typed. Flag each easy/normal/hard.
4. **Deadlines.** A grid per enrolled course, pre-filled from the program's
   `default_items` template. Type the dates off the orientación académica — about
   24 of them — and correct any weights that differ. Weights are validated to sum
   to `grade_scale_max`, because a forecast built on weights that don't add up
   lies quietly.
5. **Availability**, only if the class schedule changed.

**Nightly — about twenty seconds.** Read the banner, study, quick log: course,
hours, and what you left off.

**Whenever a grade arrives.** Type the score on Course detail. Dates that slip get
fixed in the same grid.

> **The one that gets skipped is step 4.** It is the only step that is pure
> transcription and the only one whose absence is invisible: with no Graded Items,
> Deadline Pressure is zero for every course, the Override never fires, and the app
> silently degrades into the hours-only ranker that §12 rejected. Everything
> calibrated in §4 — `w_deadline`, the half-life, `override_min_weight` — depends
> on this ten-minute step happening three times a year.

### Dashboard shape

```
Wed · 4h free · last 7d 11/21h · plan wants 39h

  TONIGHT → BASE DE DATOS   3.8h
  ⏰ Lab 3 due tomorrow 8am · 15% · 48h override
  last session (Mon, 1.5h): "terminé 3FN,
  falta el diagrama ER y probar los queries"
  ─────────────────────────────────────────
  BASE DE DATOS        3cr
   1/4.8h ██░░░░░░░░    — · ⏰ 8am

  ARQUITECTURA    4cr · hard
   6/9.7h ██████░░░░  10.5 · parcial 9d

  PROG INTERMEDIA      4cr
   4/6.5h ██████░░░░   2.5 · —
```

Bars run against the **Ration**, not the Target — `4.8h` where the Plan wanted
`9h`. The header carries both so the shortfall stays visible rather than being
scaled away. Base de Datos shows no score because it won on the Override tier,
which is a different question from having ranked highest.

---

## 6. Data / Config / Code

The governing principle:

> **Anything the engine reasons about is code. Anything it merely reads is data.**

Statuses are code *because* prerequisite logic interrogates them.
Graded item types are data *because* the engine only reads `weight` and `due_date`.

### 📄 Data — YAML, no deploy, no code change

```
plans/uned/iic-diplomado-2026.yaml
plans/uned/iic-bachillerato.yaml        ← when you get there
plans/<school>/<program>.yaml           ← anyone else's, someday
```

Holds: institution · program · plan · blocks · courses · códigos · créditos ·
prerequisite edges · graded item types · the default item template.

`default_items` is a starting skeleton, never a constraint — UNED Diplomado courses
are broadly consistent in shape, so pre-filling turns ~60 fields of transcription
per cuatrimestre into ~24 dates. Any course that deviates is edited in the grid.

Loaded by `manage.py loadplan`. Diffable, reviewable, shareable, version-controlled.

```yaml
institution: { name: UNED, country: CR }
program:
  name: Diplomado en Ingeniería Informática
  code: IIC-2026
  pass_mark: 70
  hours_per_credit: 3.0
  grade_scale_max: 100
  term_type: cuatrimestre
  term_weeks: 15
  terms_per_year: 3
  item_types: [tarea, quiz, parcial, final, proyecto]
  default_items:            # pre-fills the deadlines grid; every field editable
    - { type: tarea,   weight: 10 }
    - { type: tarea,   weight: 10 }
    - { type: tarea,   weight: 10 }
    - { type: parcial, weight: 20 }
    - { type: parcial, weight: 20 }
    - { type: final,   weight: 30 }
blocks:
  - name: A
    credits: 16
    courses:
      - { code: '03304', credits: 4, name: Lógica Algorítmica }
      - { code: '03068', credits: 3, name: Matemáticas para Computación I }
      - { code: '00997', credits: 3, name: Inglés para Informática }
      - { slot: humanidades, credits: 3, count: 2 }
  - name: B
    credits: 15
    courses:
      - { code: '03071', credits: 3, name: Lógica para Computación,
          requires: ['03304'] }
      # …
```

### ⚙️ Config — tunable without touching logic

| On `Program` | Default | On `ScoringConfig` | Default |
|---|---|---|---|
| `pass_mark` | 70 | `override_window_hours` | 48 |
| `hours_per_credit` | 3.0 | `override_min_weight` | 0.10 |
| `grade_scale_max` | 100 | `difficulty` | easy .75 / normal 1.0 / hard 1.5 |
| `term_type` | cuatrimestre | `deadline_half_life_days` | 7 |
| `term_weeks` | 15 | `w_hours_behind` | 1.0 |
| | | `w_deadline` | 20.0 |
| | | `stale_after_days` | 4 |

> `w_deadline` is in **hours-of-neglect per unit of pressure** — a full-weight item
> due today is worth about one Ration. It is not a free knob: at 1.0 the deadline
> term cannot change any ordering at all, and at 50 it overrides difficulty
> everywhere, which quietly reverses ADR-0004.

Study Windows live on the availability template, not here — they are one per
weekday and are a statement of appetite, not a tuning constant.

> **Note:** `hours_per_credit = 3.0` follows the Costa Rican credit convention
> (1 crédito ≈ 3 hours of student work per week). **Verify against UNED's own
> reglamento before trusting the overload warning.**
>
> Run the plan through it and Bloque D is 17 créditos → **51 h/week**. That is not
> a bug in the math; it is the reason the weeks don't work. The app should say so —
> which is exactly why Target survives unranked alongside Ration (ADR-0007).

### 🔒 Code — hardcoded deliberately

| Hardcoded | Why it must be |
|---|---|
| The five statuses and their semantics | The engine branches on them |
| The `score()` function's shape | Its numbers are config; its structure must be one tested function |
| One student per install | Multi-user is a different product |

```python
class Status(TextChoices):
    # satisfies_prereq / counts_credits / has_grade
    PENDING      # no  / no  / no
    IN_PROGRESS  # no  / no  / no
    PASSED       # yes / yes / yes
    TRANSFERRED  # yes / yes / no    ← "Convalidado"
    FAILED       # no  / no  / yes
```

`TRANSFERRED` exists because of real convalidations — a prior Física degree from
another university covering Cálculo I/II and Álgebra Lineal. It satisfies
prerequisites and counts créditos but carries no UNED grade. None of those courses
appear in this 78-crédito plan, so **`TRANSFERRED` has no instance in the Diplomado
seed data**; it is there for the Bachillerato.

`Status` lives on the Course. An `Enrollment` carries a narrower `Outcome` —
`IN_PROGRESS`, `PASSED`, `FAILED` — describing one attempt. They look mergeable and
are not: an Outcome has no `pending`, because you enrolled, and no `transferred`,
because that is the absence of an attempt (ADR-0010).

---

## 7. Data model sketch

```
Institution ─┬─ Course (código, name, créditos)     ← catalogue, shared across Plans
             │
             └─ Program ─┬─ ItemType
                         ├─ pass_mark, hours_per_credit, grade_scale_max,
                         │  term_type, term_weeks, terms_per_year
                         │
                         ├─ Term ─── Enrollment ─┬─ GradedItem (type, weight,
                         │      (outcome,         │              due_at, grade)
                         │       difficulty)      └─ StudyLog (hours, note,
                         │                                     studied_on,
                         │                                     recorded_at)
                         │
                         └─ Plan ─┬─ Prerequisite (course, requires_course)
                                  └─ Block ─── BlockEntry ─→ Course
                                                 (créditos; null Course = a Slot)

CourseStatus      (course, status)              ← the five of ADR-0001, per Course
StudyWindow       (weekday, start, end)         ← what a day offers at most
AvailabilityBlock (weekday, start, end, label)  ← what is taken out of it
ScoringConfig     (singleton)
AppSettings       (singleton: active_plan)
RoadmapEntry      (university, category, code, name, official_link, video_link,
                    youtube_channel, textbook)
CoverageLink      (roadmap_entry, course FK nullable, note, imported_status)
```

`Course` is catalogue and belongs to the **Institution**, not to a Plan, so a pass
carries into the Bachillerato (ADR-0009). `Enrollment` is that Course in a specific
Term — which is what makes retakes representable — and carries the attempt's
**Outcome**, while the Course carries the **Status** that prerequisites and the
degree map read (ADR-0010).

A **BlockEntry** carries its own créditos and points at a Course. A **Slot** — the
four *asignaturas de humanidades* — is one whose Course is null, so a Plan totals 78
créditos whether or not its Slots are filled, and filling one is an assignment
rather than a special case.

There is no `Student` model. One student per install is hardcoded (§6), so every
row here has exactly one owner by construction.

A **Roadmap Entry** is a course at another university; a **Coverage Link** is one
piece of what it corresponds to on the UNED side, with an optional Course — some
coverage is a fact about the prior Física degree with no Course to point to at all
(ADR-0012). One entry can carry several links, and a link with a Course reads that
Course's Status live; one without keeps the status it was imported with.

---

## 8. Build order

| Phase | Contents |
|---|---|
| **0 — Foundation** *(timeboxed ~1 week)* | Models, plan YAML schema, `loadplan` command, UNED plan seeded, onboarding checklist, degree map |
| **1 — The loop** | Dashboard + banner, quick log, course detail, scoring engine with tests |
| **2 — Setup surfaces** | Cuatrimestre setup incl. term closeout + deadlines grid, availability template + study windows, overload warning |
| **3 — Extras** | ~~Grade forecast~~, ~~streaks~~ — both specced. Roadmap import + reference view still open |
| **Later** | Hosting, Telegram nudge, catch-up prompt, CSV import |

**The timebox on Phase 0 is the point.** The failure mode is a beautiful degree map
admired twice and an app that never tells you what to do tonight.

> **Phase 1 builds deadline logic that Phase 2 supplies the data for — resolved.**
> The Override tier, the half-life decay and `w_deadline` are all Phase 1, but the
> deadlines grid was Phase 2, so Phase 1 would have shipped an engine whose deadline
> half could only be exercised by fixtures. **ADR-0011**: the onboarding checklist
> (Phase 0) creates the first Term and Enrollment for in-progress Courses, and
> Graded Items can be added from Course detail (Phase 1) ahead of the deadlines
> grid, so the deadline half is exercisable from the start.

---

## 9. Risks accepted, on the record

1. **Free-form logging decays.** v1 has no nudge and no catch-up prompt. When logging stops the app doesn't go blind — it goes *confidently wrong*: with nothing logged, every course sits at a full Ration behind and the score collapses to `créditos × difficulty²`, recommending the biggest hard course nightly on the strength of a deficit it invented. Week 5, when it matters most, is exactly when logging stops. Two defences: the streak counter makes the gap visible, and past `stale_after_days` the banner labels its own recommendation a guess (§4 rule 2). Neither of them recovers the missing hours.
2. **Timeline: ~8–11 weeks.** Foundation-first + full custom UI + 8 screens + institution-agnostic entities + bilingual i18n. **You will not be using this during the current cuatrimestre.** This is a defensible trade for a portfolio piece that outlives the diplomado; it is the wrong trade if the goal was surviving this term. It was chosen deliberately, four separate times.
3. **Difficulty compounds.** One bad flag buries every other course for a week. Only the 48h override stops it.
4. **Dashboard as home** hands the decision back to you — the exact 20 minutes the app exists to eliminate. The banner is the mitigation.
5. **Institution-agnostic with an audience of one.** The hierarchy is cheap; the discipline it imposes is not free. Justified by the near-certain move to the Bachillerato.

---

## 10. Explicitly out of scope

- Life to-dos (chores, errands, gym as *tasks*) — they are blocks only
- Self-study as a competing track with its own hour budget
- Surplus-hours allocation
- Multi-user, auth beyond a single account, sharing
- Pluggable grading schemes, GPA/ECTS conversion, term-calendar strategies
- CRUD screens for institutions, programs or plans
- Mobile app, push notifications, hosting *(deferred, not rejected)*

---

## 11. Still needed before seeding

- [ ] Cuatrimestre start and end dates
- [ ] Which courses are enrolled right now
- [ ] Difficulty flag per enrolled course
- [ ] Real weekly availability (work, class, fixed commitments)
- [ ] Study window per weekday — the hours you are actually willing to study within
- [ ] The `default_items` skeleton — the typical tarea/parcial/final mix and weights for a Diplomado course, read off two or three orientaciones
- [ ] This cuatrimestre's actual deadlines, off the orientación académica of each enrolled course
- [ ] Status for the 6 unknown named courses: `00997 · 03069 · 03072 · 04038 · 00226 · 00830`
- [ ] Which humanities courses fill the 4 slots, and their status
- [ ] Confirm UNED's official créditos → weekly-hours convention

---

## 12. Decision log

Recorded because the *rejected* options explain the design as much as the chosen
ones.

| Question | Chosen | Rejected |
|---|---|---|
| Core pain | "I don't know what to do NOW" | Can't fit the hours · Don't know if behind · Forget things |
| Input cost | Courses + hours, no task list | Real task list · Syllabus import · Calendar sync |
| Logging | Free-form | Daily check-in · Timer · Plan-then-tick |
| Stale data | ~~Nudge before the gap~~ → recommend, label the guess | Refuse + catch-up prompt · Freeze the deficit · Assume zero silently |
| Platform | Django MVP | PWA · Native · Email nudge |
| Nudge path | None in v1, local only | Telegram · Web push · Email |
| Life scope | Recurring blocks only | Courses only · Full life tasks |
| Ranking | + créditos + difficulty | Hours only · Hours + deadlines · No recommender |
| Progress | Whole degree + extras + streaks | This quarter + grade math · Habits |
| Two tracks | UNED first, self-study surplus *(later dropped)* | Two protected budgets · Fake deadlines |
| Source of truth | App owns UNED, Excel keeps roadmap | Import all · Excel authoritative |
| Self-study | Curate in Excel, import flat list | Fully out · App owns everything |
| Grades | Track scores + forecast | Done/not-done · Scores without forecast |
| MVP cut | Data foundation first | Thin vertical slice · Loop + grades · Everything |
| Crosswalk | UNED plan is the base | Coverage links · Free text · Topic-level |
| Roadmap role | Reference only, not a must | Gap map · Resource shelf · Parallel track |
| Streaks | Keep on UNED study, drop surplus | Drop both · Keep both · Per-course |
| Hour targets | Créditos × difficulty | Derive only · Manual · Relative neglect |
| Difficulty | Both target and ranking | Target only · Ranking only |
| Override | 48h jumps the queue, ≥10% weight only | No override · Top 3 · Configurable window · Any weight qualifies |
| Home screen | Course cards dashboard | One answer · Week board · Agenda |
| Recommendation | Banner above the cards | Sort order · No recommendation · Button |
| Stack | Full custom UI, no admin | Admin + one screen · DRF+React · Hybrid |
| Screens | Seven + onboarding | Five · Three · Everything |
| History | Guided checklist onboarding | CSV import · Both · Fixed statuses only |
| Log entry | Course + hours + "left off" note | Hours only · Attribute to item · + mood |
| Flex target | Institution-agnostic | This diplomado only · Plan-as-data · Multi-user |
| How agnostic | Generic entities, config fields | Pluggable strategies · Hierarchy only |
| Plan authoring | YAML + load command | CRUD screens · Django admin · Upload |
| Scoring config | Formula in code, numbers in settings | Rules engine · Named strategies · Hardcode |
| Statuses | Fixed five, labels translatable | Configurable with flags · Minimal three |
| Language | Bilingual es/en day one | English code + Spanish UI · Spanish everywhere |
| Item types | Configurable per program | Fixed enum · Free text |
| Name | **Awá** / `awa` | Rumbo · Bloque · Brújula · Malla · Cuatri |

### Added 2026-09-05 — the ranking engine, grilled

| Question | Chosen | Rejected |
|---|---|---|
| Target vs capacity | Absolute Target for display, scaled **Ration** for ranking | Absolute only · Scale everything · Relative neglect |
| Naming the scaled figure | **Ration** | Fair Share · Share · Redefine Target |
| What "this week" means | Rolling 7 days | Calendar week · Calendar week + carried debt · Term-to-date |
| Formula shape | `difficulty × (w·behind + w·pressure)` | Pure product · Floor + product · Positive baseline · Fully normalised sum |
| Which items press | Strongest upcoming item | Next item only · Sum of all upcoming · Proximity, weight ignored |
| Past-due items | Zero pressure — forward-only | Flat bump until scored · Track submitted separately · Clamp at max |
| Deadline loudness | `w_deadline` ≈ 20 hours-equivalent | 1.0, deadlines binary · 50, deadlines dominate · Self-scaling to ration |
| Override qualifying | ≥10% weight, tie-break by pressure | Any weight qualifies · No tier, steepen decay · First-due wins |
| Bounding a day | Study Window per weekday | Sleep as an availability block · Flat daily cap · Manual weekly capacity |
| Banner hours | `min(free tonight, ration remaining)` | All of tonight's free hours · Full remaining ration · No figure at all |
| Entering deadlines | Grid in Cuatrimestre setup + inline edit on Course detail | A 9th screen · Course detail only · A per-term YAML file |
| Item boilerplate | `default_items` template in the plan YAML | Type every item every term · Weights per item type · No template |
| Term closeout | Derived from the grade, confirmed as step 1 of next setup | Manual picker on Course detail · Fully automatic · A dedicated closeout screen |

---

*Scoped 2026-09-03 through a structured interview; ranking engine revised
2026-09-05 the same way. Nothing here is built yet.*
