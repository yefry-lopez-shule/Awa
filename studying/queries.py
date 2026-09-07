"""Questions about where the student stands, answered against ADR-0001's fixed
Status semantics. The only place those semantics get interpreted (#9).
"""

from curriculum.models import BlockEntry, Prerequisite

from .models import STATUSES_COUNTING_CREDITS, STATUSES_SATISFYING_PREREQ, status_for_course


def is_unlocked(course, plan):
    """True only when every one of `course`'s prerequisites in `plan` is
    satisfied (passed or transferred). Prerequisites are conjunctions
    (ADR-0009): one outstanding requirement locks the course.

    Unlocking is Plan-scoped — a Course can be unlocked under one Plan's
    prerequisite graph and locked under another's.
    """

    required_courses = Prerequisite.objects.filter(plan=plan, course=course).select_related(
        "requires_course"
    )
    return all(
        status_for_course(prereq.requires_course) in STATUSES_SATISFYING_PREREQ
        for prereq in required_courses
    )


def credits_earned(plan):
    """Créditos counted as earned: named BlockEntries whose Course is passed
    or transferred. An unfilled Slot contributes to the Plan's total
    elsewhere but never here — there is no Course to have passed.
    """

    total = 0
    entries = BlockEntry.objects.filter(block__plan=plan, course__isnull=False).select_related(
        "course"
    )
    for entry in entries:
        if status_for_course(entry.course) in STATUSES_COUNTING_CREDITS:
            total += entry.credits
    return total
