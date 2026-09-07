"""Questions about where the student stands, answered against ADR-0001's fixed
Status semantics. The only place those semantics get interpreted (#9, #11).
"""

from curriculum.models import BlockEntry, Prerequisite

from .models import (
    STATUSES_COUNTING_CREDITS,
    STATUSES_SATISFYING_PREREQ,
    Status,
    status_for_course,
)


def is_unlocked(course, plan, *, projecting=False):
    """True only when every one of `course`'s prerequisites in `plan` is
    satisfied (passed or transferred). Prerequisites are conjunctions
    (ADR-0009): one outstanding requirement locks the course.

    Unlocking is Plan-scoped — a Course can be unlocked under one Plan's
    prerequisite graph and locked under another's.

    With `projecting=True`, a prerequisite Course the student is currently
    studying (Status `IN_PROGRESS`) counts as provisionally satisfied. That is
    the "what opens next term" question the degree map asks (#11): it is
    applied to direct prerequisites only, not chained, so the projection
    reaches exactly as far as what is actually being studied.
    """

    required_courses = Prerequisite.objects.filter(plan=plan, course=course).select_related(
        "requires_course"
    )
    return all(
        _prereq_satisfied(prereq.requires_course, projecting)
        for prereq in required_courses
    )


def _prereq_satisfied(course, projecting):
    status = status_for_course(course)
    if status in STATUSES_SATISFYING_PREREQ:
        return True
    return projecting and status == Status.IN_PROGRESS


def opens_next_term(course, plan):
    """True when `course` is locked now but would unlock if every Course the
    student is currently studying passes (#11).

    Recomputed on every read — a Course later marked `FAILED` simply stops
    qualifying, with nothing cached and nothing to explicitly revert.
    """

    return not is_unlocked(course, plan) and is_unlocked(course, plan, projecting=True)


def credits_earned(plan, block=None):
    """Créditos counted as earned: named BlockEntries whose Course is passed
    or transferred. An unfilled Slot contributes to the Plan's total
    elsewhere but never here — there is no Course to have passed.

    Scoped to one `block` when given, otherwise the whole Plan.
    """

    total = 0
    entries = BlockEntry.objects.filter(block__plan=plan, course__isnull=False).select_related(
        "course"
    )
    if block is not None:
        entries = entries.filter(block=block)
    for entry in entries:
        if status_for_course(entry.course) in STATUSES_COUNTING_CREDITS:
            total += entry.credits
    return total
