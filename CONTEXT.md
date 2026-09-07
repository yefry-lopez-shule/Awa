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

**Slot** (*asignatura de humanidades*):
A place in a Block reserved by its Credits alone, filled later by a Course the
student chooses. It counts towards the Plan whether or not it has been filled.
_Avoid_: placeholder, elective, optional course, hueco

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

**Outcome**:
How one Enrollment ended: in progress, passed, or failed. An Outcome describes a
single attempt; a Status describes where the student stands across all of them.
_Avoid_: result, status, grade

**Status**:
Where the student stands on a Course: pending, in progress, passed, transferred,
or failed. Each status carries fixed meaning about whether it satisfies
prerequisites, counts credits, and holds a grade. It belongs to the Course, not to
any one attempt at it, and exists for Courses never enrolled in.

**Transferred** (*convalidado*):
A Status meaning prior study elsewhere satisfies the Course. It unlocks
prerequisites and counts credits but carries no grade.
_Avoid_: exempt, waived, credited, recognised

**Graded Item**:
Anything marked that contributes to a Course's Grade — a tarea, quiz, parcial,
final, proyecto. Carries a due date, a weight, and eventually a Grade.
_Avoid_: assignment, task, deliverable, assessment, evaluación

**Grade** (*nota*):
A mark on a Graded Item, or the weighted total of those marks for a Course. Never
the ranking number — that is a **Score**.
_Avoid_: score, mark, points, result

**Study Log**:
A record that the student spent some hours on a Course, optionally noting where
they left off.
_Avoid_: session, time entry, activity

### Planning

**Availability Block**:
A recurring weekly commitment that consumes hours — work, class, gym, chores. It
is never studied and never recommended; it only reduces what is left.
_Avoid_: event, appointment, calendar entry, task

**Study Window**:
The stretch of a given weekday during which the student is willing to study at
all. Varies by weekday and is a statement of appetite, not of obligation.
_Avoid_: working hours, day, schedule

**Capacity**:
The hours left in a week once Availability Blocks are subtracted from the Study
Windows. What the student actually has, as opposed to what the Plan demands.
_Avoid_: free time, availability, bandwidth

**Target**:
The hours a Course demands in a week, derived from its Credits and the student's
Difficulty rating for it. Regularly exceeds Capacity — that gap is the overload
warning, not an error.
_Avoid_: goal, quota, budget, allocation

**Ration**:
The hours a Course actually gets in a week: its share of Capacity, proportional to
its Target and never larger than it. What Hours Behind is measured against.
_Avoid_: allocation, budget, quota, allotment, fair share

**Difficulty**:
The student's own rating of how hard a Course is for them. It both raises the
Target and amplifies the Score.
_Avoid_: weight, priority, importance

**Hours Behind**:
Ration minus the hours logged against a Course in the trailing seven days. The
primary measure of neglect. The window rolls daily; it never resets. Never
negative — a Course ahead of its Ration is simply not behind.
_Avoid_: deficit, gap, shortfall

**Deadline Pressure**:
How near and how heavily weighted a Course's most pressing upcoming Graded Item
is — the one whose nearness and weight together outrank the rest, which is not
always the soonest. Forward-looking only: an item whose due date has passed exerts
none, because tonight cannot change it.
_Avoid_: urgency, priority

**Score**:
The ranked number expressing how much a Course needs attention right now. Never
means a mark on a Graded Item — that is a **grade**.
_Avoid_: rank, weight, priority

**Override Window**:
The interval before a Graded Item's due date within which it outranks every other
consideration. Only an item carrying real weight qualifies — a trivial item due
tomorrow never displaces a heavy one due later.
_Avoid_: grace period, deadline buffer

**Recommendation**:
The single Course the app commits to for the next study session, together with
the hours it commits to and the reason that Course won.
_Avoid_: suggestion, next action, task

**Streak**:
Consecutive days on which any Study Log was recorded. Measures whether the
student is still feeding the app, not whether they are learning.

### Reference

**Roadmap Entry**:
A course at another university, catalogued for comparison. Reference material
only — it is never studied, scheduled, or recommended.
_Avoid_: equivalent, external course, mapping

**Coverage Link**:
One piece of what a Roadmap Entry corresponds to on the UNED side: a note, and
optionally a Course whose Status settles whether that piece is done. A Roadmap
Entry may carry several — one foreign course often spans more than one UNED
Course — or none backed by a Course at all, when the coverage is a fact about
prior study elsewhere with nothing in any catalog to point to.
_Avoid_: mapping, equivalence, crosswalk
