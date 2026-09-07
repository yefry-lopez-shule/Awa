"""The ranking engine (scope.md §4, ADR-0004, ADR-0007, ADR-0008, ADR-0013).

`rank()` is the whole engine: one pure function over a plain `Snapshot`, no
database, no request, no clock threaded through it. It returns an ordered list
of `RankedCourse`s — Score, tier, committed hours, and a *structured* reason
(which rule won plus the raw values it used, never a rendered sentence). The
ORM-to-snapshot adapter and the sentence rendering both live outside this
module (`recommendation.py`, `reasons.py`).

The arithmetic, verbatim from scope.md §4:

    target    = créditos × hours_per_credit × difficulty
    ration    = target × min(1, capacity / Σ targets)      # scales down only
    behind    = max(0, ration − hours_logged_trailing_7_days)
    pressure  = max over upcoming Graded Items of
                  (weight / grade_scale_max) × 0.5^(days_until / half_life)
    score     = difficulty × (w_hours_behind × behind + w_deadline × pressure)

Four properties are load-bearing and must not be "simplified" away (ADR-0008):
Difficulty appears twice — in the Ration and again as the outer multiplier;
`behind` is floored at zero, so being ahead never inverts the ordering; the
deadline term is *added*, so pressure can lift a Course but never suppress one;
and Graded Items past their due date are excluded entirely.
"""

import datetime
from dataclasses import dataclass


def deadline_pressure(items, grade_scale_max, *, half_life_days=7, today=None):
    """How near and how heavily weighted a Course's most pressing *upcoming*
    Graded Item is: the max over items still due of
    `(weight / grade_scale_max) * 0.5 ** (days_until / half_life_days)`.

    Forward-looking only (scope.md §4 rule 3, ADR-0008): an item whose due
    date has passed — or that carries no due date — contributes nothing,
    because studying tonight cannot change it and the decay term grows
    explosively on negative inputs. 0 when nothing is upcoming.
    """

    today = today or datetime.date.today()
    pressures = [
        (item.weight / grade_scale_max)
        * 0.5 ** ((item.due_at - today).days / half_life_days)
        for item in items
        if item.due_at is not None and item.due_at > today
    ]
    return max(pressures, default=0.0)


# --- The snapshot: plain data in ------------------------------------------------


@dataclass(frozen=True)
class SnapshotItem:
    """One upcoming or past Graded Item, reduced to what the engine reads."""

    name: str
    weight: float
    due_at: datetime.date | None = None


@dataclass(frozen=True)
class CourseSnapshot:
    """One in-progress Course as the engine sees it."""

    code: str
    name: str
    credits: float
    difficulty: str  # a `studying.models.Difficulty` value: "easy"/"normal"/"hard"
    hours_logged_7d: float = 0.0
    items: tuple[SnapshotItem, ...] = ()


@dataclass(frozen=True)
class Snapshot:
    """Everything `rank()` needs, assembled once by the adapter.

    `days_since_last_log` is `None` when nothing has ever been logged — which
    the engine treats as stale, because a ranking built on zero logged hours
    is standing on exactly the invented deficit Risk 1 warns about.
    """

    courses: tuple[CourseSnapshot, ...]
    capacity: float
    hours_left_today: float
    hours_per_credit: float
    grade_scale_max: float
    days_since_last_log: int | None = None


# --- The ranking: plain data out ----------------------------------------------

RULE_OVERRIDE = "override"
RULE_DEADLINE_PRESSURE = "deadline_pressure"
RULE_HOURS_BEHIND = "hours_behind"


@dataclass(frozen=True)
class Reason:
    """Which rule won, plus the raw values it used — never a sentence
    (ADR-0013). A rendering layer turns this into locale-specific prose.
    """

    rule: str
    item_name: str | None = None
    item_weight: float | None = None
    days_until_due: int | None = None
    hours_behind: float | None = None


@dataclass(frozen=True)
class RankedCourse:
    code: str
    name: str
    difficulty: str
    target: float
    ration: float
    hours_logged_7d: float
    hours_behind: float
    pressure: float
    committed_hours: float
    tier: int  # 1 = Override tier (ordered by pressure), 2 = everything else
    reason: Reason
    score: float | None = None  # None on the Override tier — it did not win on one


@dataclass(frozen=True)
class Ranking:
    courses: tuple[RankedCourse, ...]
    stale: bool
    days_since_last_log: int | None = None

    @property
    def recommendation(self):
        return self.courses[0] if self.courses else None


@dataclass
class _Working:
    course: CourseSnapshot
    target: float
    ration: float
    behind: float
    pressure: float
    behind_term: float
    pressure_term: float
    raw_score: float
    committed: float
    override_item: SnapshotItem | None
    strongest_item: SnapshotItem | None


def _as_date(now):
    if isinstance(now, datetime.datetime):
        return now.date()
    return now


def _strongest_upcoming(items, grade_scale_max, half_life_days, today):
    """The single upcoming item driving Deadline Pressure — strongest by
    nearness *and* weight together, not merely the soonest (scope.md §4).
    """

    upcoming = [
        item for item in items if item.due_at is not None and item.due_at > today
    ]
    if not upcoming:
        return None
    return max(
        upcoming,
        key=lambda item: (item.weight / grade_scale_max)
        * 0.5 ** ((item.due_at - today).days / half_life_days),
    )


def _override_item(items, config, grade_scale_max, today):
    """The upcoming item that qualifies this Course for the Override tier:
    due within `override_window_hours` *and* carrying at least
    `override_min_weight` of the grade (ADR-0008). The strongest such item, or
    None.
    """

    qualifying = [
        item
        for item in items
        if item.due_at is not None
        and item.due_at > today
        and (item.due_at - today).days * 24 <= config.override_window_hours
        and item.weight / grade_scale_max >= config.override_min_weight
    ]
    if not qualifying:
        return None
    return max(
        qualifying,
        key=lambda item: (item.weight / grade_scale_max)
        * 0.5 ** ((item.due_at - today).days / config.deadline_half_life_days),
    )


def rank(snapshot, config, now=None):
    """Rank `snapshot`'s Courses for the next study session.

    `config` is anything exposing the `ScoringConfig` fields plus a
    `difficulty_multipliers` mapping; `now` is a date or datetime (defaults to
    today). Pure: no I/O, no globals, deterministic down to ties.
    """

    today = _as_date(now) or datetime.date.today()
    multipliers = config.difficulty_multipliers

    targets = {
        c.code: c.credits * snapshot.hours_per_credit * multipliers[c.difficulty]
        for c in snapshot.courses
    }
    total_target = sum(targets.values())
    # Ration scales *down* only: when Capacity covers demand, Ration == Target
    # and the surplus belongs to the student, not the ranking (ADR-0007).
    scale = min(1.0, snapshot.capacity / total_target) if total_target else 1.0

    working = []
    for c in snapshot.courses:
        target = targets[c.code]
        ration = target * scale
        behind = max(0.0, ration - c.hours_logged_7d)
        pressure = deadline_pressure(
            c.items,
            snapshot.grade_scale_max,
            half_life_days=config.deadline_half_life_days,
            today=today,
        )
        difficulty_mult = multipliers[c.difficulty]
        behind_term = config.w_hours_behind * behind
        pressure_term = config.w_deadline * pressure
        raw_score = difficulty_mult * (behind_term + pressure_term)
        committed = max(0.0, min(snapshot.hours_left_today, ration - c.hours_logged_7d))
        working.append(
            _Working(
                course=c,
                target=target,
                ration=ration,
                behind=behind,
                pressure=pressure,
                behind_term=behind_term,
                pressure_term=pressure_term,
                raw_score=raw_score,
                committed=committed,
                override_item=_override_item(
                    c.items, config, snapshot.grade_scale_max, today
                ),
                strongest_item=_strongest_upcoming(
                    c.items,
                    snapshot.grade_scale_max,
                    config.deadline_half_life_days,
                    today,
                ),
            )
        )

    tier1 = sorted(
        (w for w in working if w.override_item is not None),
        key=lambda w: (-w.pressure, w.course.code),
    )
    tier2 = sorted(
        (w for w in working if w.override_item is None),
        key=lambda w: (-w.raw_score, w.course.code),
    )

    ranked = tuple(
        _to_ranked(w, tier=1, today=today) for w in tier1
    ) + tuple(_to_ranked(w, tier=2, today=today) for w in tier2)

    stale = (
        snapshot.days_since_last_log is None
        or snapshot.days_since_last_log > config.stale_after_days
    )
    return Ranking(
        courses=ranked, stale=stale, days_since_last_log=snapshot.days_since_last_log
    )


def _to_ranked(w, *, tier, today):
    if tier == 1:
        item = w.override_item
        reason = Reason(
            rule=RULE_OVERRIDE,
            item_name=item.name,
            item_weight=item.weight,
            days_until_due=(item.due_at - today).days,
        )
        score = None
    elif w.pressure_term > w.behind_term and w.strongest_item is not None:
        item = w.strongest_item
        reason = Reason(
            rule=RULE_DEADLINE_PRESSURE,
            item_name=item.name,
            item_weight=item.weight,
            days_until_due=(item.due_at - today).days,
        )
        score = w.raw_score
    else:
        reason = Reason(rule=RULE_HOURS_BEHIND, hours_behind=w.behind)
        score = w.raw_score

    return RankedCourse(
        code=w.course.code,
        name=w.course.name,
        difficulty=w.course.difficulty,
        target=w.target,
        ration=w.ration,
        hours_logged_7d=w.course.hours_logged_7d,
        hours_behind=w.behind,
        pressure=w.pressure,
        committed_hours=w.committed,
        tier=tier,
        reason=reason,
        score=score,
    )
