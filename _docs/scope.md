# Awá — Scope

> **Awá** — named for the *awá*, the traditional healer of the Bribri people of
> Talamanca, Costa Rica: the one who holds the deep knowledge and guides others.
> Display name `Awá`. All technical identifiers use plain `awa` (repo, Django
> project, modules, any future domain) to avoid diacritic friction.

**Status:** scoped, not yet built
**Date:** 2026-09-03
**Owner:** Yefry Lopez

**Related:** [`CONTEXT.md`](../CONTEXT.md) — the glossary · [`adr/`](./adr/) — the
six decisions that were hard to reverse, surprising, and genuinely contested

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
| 4 | **Availability template**: work, class, gym, chores set once as recurring blocks | Derives real capacity so the app can say "you need 33h, you have 21h." |
| 5 | Ranking = `hours_behind × difficulty × deadline_pressure` | See §4. |
| 6 | **Difficulty compounds** — it raises the target *and* multiplies the score | Deliberate. A course flagged hard should dominate until unflagged. |
| 7 | **48h deadline override** — anything due within 48h jumps the queue | The floor that prevents the only truly stupid recommendation. |
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

```
target       = créditos × hours_per_credit × difficulty
hours_behind = target − hours_logged_this_week

score        = hours_behind × difficulty × deadline_pressure

override     = any graded item due within `override_window_hours` (48)
               outranks everything, difficulty included

output       = (score, reason_string)
```

**Two hard rules:**

1. **It always shows its reasoning in one line.** `"exam in 3 days · 30% of grade · 12h behind"`. With three weighting knobs, an unauditable score is one you stop believing.
2. **It never recommends from data it knows is stale.** If logging has gone quiet, it says so rather than guessing.

`score()` is one function, ~40 lines, fully unit-testable, returning both the number and the explanation.

---

## 5. Screens (8)

| # | Screen | Contents |
|---|---|---|
| 1 | **Onboarding checklist** | All 23 course slots with a status picker, prereqs validated live. ~24 taps, once. Grade field optional. |
| 2 | **Dashboard** (home) | Recommendation banner on top, course cards below. |
| 3 | **Quick log** | Course + hours + optional "left off" note. |
| 4 | **Course detail** | Hours vs target, graded items, current weighted grade, pass forecast. |
| 5 | **Cuatrimestre setup** | Enrol courses, set difficulty flags, term dates. |
| 6 | **Availability template** | Recurring weekly blocks; derives capacity. |
| 7 | **Degree map** | Bloques A–E, créditos earned, prerequisite unlocking, what next term opens. |
| 8 | **Roadmap reference** | Harvard/Stanford/MIT/Caltech equivalences, read-only. |

Reference data (institutions, programs, plans, courses) has **no UI** — it loads from YAML.

### Dashboard shape

```
Wed · 2h free · week 16.5/33h

  TONIGHT → BASE DE DATOS   2h
  ⏰ Lab 3 due tomorrow 8am · 48h override
  last session (Mon, 1.5h): "terminé 3FN,
  falta el diagrama ER y probar los queries"
  ─────────────────────────────────────────
  BASE DE DATOS        3cr
   9/9h  ██████████   76 · ⏰ 8am

  ARQUITECTURA    4cr · hard
   6/18h ███░░░░░░░   81 · exam 9d

  PROG INTERMEDIA      4cr
   4/12h ███░░░░░░░    — · —
```

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
prerequisite edges · graded item types.

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
| `hours_per_credit` | 3.0 | `difficulty` | easy .75 / normal 1.0 / hard 1.5 |
| `grade_scale_max` | 100 | `deadline_half_life_days` | 7 |
| `term_type` | cuatrimestre | `w_hours_behind` | 1.0 |
| `term_weeks` | 15 | `w_deadline` | 1.0 |

> **Note:** `hours_per_credit = 3.0` follows the Costa Rican credit convention
> (1 crédito ≈ 3 hours of student work per week). **Verify against UNED's own
> reglamento before trusting the overload warning.**
>
> Run the plan through it and Bloque D is 17 créditos → **51 h/week**. That is not
> a bug in the math; it is the reason the weeks don't work. The app should say so.

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
prerequisites and counts créditos but carries no UNED grade.

---

## 7. Data model sketch

```
Institution ─┬─ Program ─┬─ Plan ─┬─ Block ─── Course ──┐
             │           │        │                     │ requires (M2M, self)
             │           │        └─ ItemType            │
             │           └─ pass_mark, hours_per_credit,
             │              term_type, term_weeks, …
             │
Student ─────┴─ Term ───── Enrollment ─┬─ GradedItem (type, weight, due, score)
                                        └─ StudyLog (hours, note, logged_at)

AvailabilityBlock (weekday, start, end, label)
ScoringConfig (singleton)
RoadmapEntry (university, code, name, links, uned_course FK, coverage note)
```

`Course` is catalog. `Enrollment` is that course in a specific term — which is what
makes retakes representable.

---

## 8. Build order

| Phase | Contents |
|---|---|
| **0 — Foundation** *(timeboxed ~1 week)* | Models, plan YAML schema, `loadplan` command, UNED plan seeded, onboarding checklist, degree map |
| **1 — The loop** | Dashboard + banner, quick log, course detail, scoring engine with tests |
| **2 — Setup surfaces** | Cuatrimestre setup, availability template, overload warning |
| **3 — Extras** | Grade forecast polish, streaks, roadmap import + reference view |
| **Later** | Hosting, Telegram nudge, catch-up prompt, CSV import |

**The timebox on Phase 0 is the point.** The failure mode is a beautiful degree map
admired twice and an app that never tells you what to do tonight.

---

## 9. Risks accepted, on the record

1. **Free-form logging decays.** v1 has no nudge and no catch-up prompt. When logging stops the app goes blind, and week 5 — when it matters most — is exactly when logging stops. Only defence is the streak counter making the gap visible.
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
| Stale data | Nudge before the gap | Catch-up prompt · Honest banner · Assume zero |
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
| Override | 48h jumps the queue | No override · Top 3 · Configurable window |
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

---

*Scoped 2026-09-03 through a structured interview. Nothing here is built yet.*
