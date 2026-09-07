"""Capacity, weekly Target demand, and the overload warning.

Capacity is the hours left in a week once Availability Blocks are subtracted
from the Study Windows (CONTEXT.md). Demand is the sum of every in-progress
Course's Target. The gap between them is the overload warning — surfaced, not
hidden, and never scaled away (ADR-0007).

Everything here is recomputed from the current rows on every call. Editing the
availability template mid-Term therefore changes Capacity and nothing else.
"""

from collections import defaultdict
from dataclasses import dataclass

from studying.models import Difficulty, Outcome

from .models import AvailabilityBlock, StudyWindow

# Difficulty multiplies the Target (ADR-0004, ADR-0007). scope.md §6 places
# these constants on `ScoringConfig`; #15 (the ranking engine) will move them
# there. Until then they live here as the one place the multiplier is written.
DIFFICULTY_HOURS_MULTIPLIER = {
    Difficulty.EASY: 0.75,
    Difficulty.NORMAL: 1.0,
    Difficulty.HARD: 1.5,
}


def _minutes(t):
    return t.hour * 60 + t.minute


def _free_minutes(window, blocks):
    """Minutes of `window` not covered by any of `blocks`. Blocks are clipped
    to the window's edges and their union is taken, so a block hanging off the
    end contributes only its overlap and two overlapping blocks count once.
    """

    window_start, window_end = _minutes(window.start), _minutes(window.end)

    clipped = []
    for block in blocks:
        start = max(window_start, _minutes(block.start))
        end = min(window_end, _minutes(block.end))
        if start < end:
            clipped.append((start, end))

    covered = 0
    cursor = window_start
    for start, end in sorted(clipped):
        if start > cursor:
            cursor = start
        if end > cursor:
            covered += end - cursor
            cursor = end

    return (window_end - window_start) - covered


def capacity_hours():
    """Capacity: Σ over the week of (Study Window minus its Availability
    Blocks), in hours. A weekday with no Study Window offers nothing.
    """

    blocks_by_weekday = defaultdict(list)
    for block in AvailabilityBlock.objects.all():
        blocks_by_weekday[block.weekday].append(block)

    total_minutes = sum(
        _free_minutes(window, blocks_by_weekday[window.weekday])
        for window in StudyWindow.objects.all()
    )
    return total_minutes / 60


def course_targets(term):
    """The weekly Target of every in-progress Course in `term`, keyed by
    Course: créditos × hours_per_credit × difficulty multiplier (scope.md §4).
    """

    hours_per_credit = term.program.hours_per_credit
    targets = {}
    for enrollment in term.enrollments.filter(
        outcome=Outcome.IN_PROGRESS
    ).select_related("course"):
        multiplier = DIFFICULTY_HOURS_MULTIPLIER[Difficulty(enrollment.difficulty)]
        targets[enrollment.course] = (
            enrollment.course.credits * hours_per_credit * multiplier
        )
    return targets


def demand_hours(term):
    """Σ Targets across `term`'s in-progress Courses — what the Plan demands
    this week. 0 when nothing is enrolled.
    """

    return sum(course_targets(term).values())


@dataclass(frozen=True)
class Overload:
    """The overload warning's two numbers and whether it fires."""

    demand: float
    capacity: float

    @property
    def gap(self):
        return self.demand - self.capacity

    @property
    def overloaded(self):
        return self.demand > self.capacity


def overload(term):
    """The gap between what `term` demands and the Capacity that exists.

    `term` may be None (no Term opened yet), in which case demand is 0 and the
    warning never fires.
    """

    demand = demand_hours(term) if term is not None else 0.0
    return Overload(demand=demand, capacity=capacity_hours())
