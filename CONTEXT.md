# Awá

A single student's study planner. It decides what to study tonight, forecasts
whether each course will pass, and tracks progress through a degree programme.
Built around the UNED Diplomado IIC (Costa Rica), but the language below is
deliberately institution-neutral.

Terms are canonical in English; the Costa Rican equivalent is given where the
Spanish term is the one people actually say.

## Language

### Curriculum

**Institution**:
A body that awards qualifications. UNED is the only one seeded, but never assume it.

**Program**:
A qualification a student works towards, such as a Diplomado or a Bachillerato.
_Avoid_: degree, carrera, career, track

**Plan** (*plan de estudios*):
The complete set of courses a Program requires, grouped into Blocks. Reserve this
word for the curriculum only — never for a schedule, a roadmap, or a document.
_Avoid_: curriculum, syllabus, study plan

**Block** (*bloque*):
A named grouping of courses within a Plan, carrying its own credit total.
_Avoid_: level, stage, year, phase

**Course** (*curso*, *asignatura*):
A catalogue entry: a code, a name, a credit value, and the courses it requires
first. It exists independently of anyone studying it.
_Avoid_: class, subject, module, materia

**Credit** (*crédito*):
The unit of a Course's weight, expressing expected student workload rather than
contact time.
_Avoid_: unit, point, hour

### Studying

**Term** (*cuatrimestre*):
A dated period during which a student is enrolled in courses. Its length and how
many fall in a year are properties of the Program, not universal.
_Avoid_: semester, quarter, trimester, period

**Enrollment** (*matrícula*):
One Course taken by the student in one Term. Distinct from Course because the same
course can be taken more than once.
_Avoid_: registration, attempt, instance

**Status**:
Where the student stands on a Course: pending, in progress, passed, transferred,
or failed. Each status carries fixed meaning about whether it satisfies
prerequisites, counts credits, and holds a grade.

**Transferred** (*convalidado*):
A Status meaning prior study elsewhere satisfies the Course. It unlocks
prerequisites and counts credits but carries no grade.
_Avoid_: exempt, waived, credited, recognised

**Graded Item**:
Anything scored that contributes to a Course's final grade — a tarea, quiz,
parcial, final, proyecto. Carries a due date, a weight, and eventually a score.
_Avoid_: assignment, task, deliverable, assessment, evaluación

**Study Log**:
A record that the student spent some hours on a Course, optionally noting where
they left off.
_Avoid_: session, time entry, activity

### Planning

**Availability Block**:
A recurring weekly commitment that consumes hours — work, class, gym, chores. It
is never studied and never recommended; it only reduces what is left.
_Avoid_: event, appointment, calendar entry, task

**Capacity**:
The hours remaining in a week once Availability Blocks are subtracted. What the
student actually has, as opposed to what the Plan demands.
_Avoid_: free time, availability, bandwidth

**Target**:
The hours a Course should receive in a week, derived from its Credits and the
student's Difficulty rating for it.
_Avoid_: goal, quota, budget, allocation

**Difficulty**:
The student's own rating of how hard a Course is for them. It both raises the
Target and amplifies the Score.
_Avoid_: weight, priority, importance

**Hours Behind**:
Target minus hours logged this week. The primary measure of neglect.
_Avoid_: deficit, gap, shortfall

**Deadline Pressure**:
How near and how heavily weighted a Course's next Graded Item is.
_Avoid_: urgency, priority

**Score**:
The ranked number expressing how much a Course needs attention right now. Never
means a mark on a Graded Item — that is a **grade**.
_Avoid_: rank, weight, priority

**Override Window**:
The interval before a Graded Item's due date within which it outranks every other
consideration.
_Avoid_: grace period, deadline buffer

**Recommendation**:
The single Course the app commits to for the next study session, always
accompanied by the reason it won.
_Avoid_: suggestion, next action, task

**Streak**:
Consecutive days on which any Study Log was recorded. Measures whether the
student is still feeding the app, not whether they are learning.

### Reference

**Roadmap Entry**:
A course at another university mapped to a Course in the Plan, recording what that
course covers and what it leaves uncovered. Reference material only — it is never
studied, scheduled, or recommended.
_Avoid_: equivalent, external course, mapping
