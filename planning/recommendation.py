"""The ORM-to-snapshot adapter and the one call the dashboard makes.

`rank()` is pure (see `ranking.py`); this module is the thin layer that reads
the database and assembles the plain `Snapshot` it runs on. It holds no rules —
every arithmetic decision lives in `rank()` or `capacity.py`.
"""

import datetime

from django.utils import timezone

from studying.models import Outcome, StudyLog, Term

from .capacity import capacity_hours, hours_left_in_todays_window
from .models import ScoringConfig
from .ranking import CourseSnapshot, Snapshot, SnapshotItem, rank

ROLLING_WINDOW_DAYS = 7


def current_term(plan):
    """The Term the Recommendation is about: the most recent one of the active
    Plan's Program. None when no Plan is active or no Term has been opened.
    """

    if plan is None:
        return None
    return (
        Term.objects.filter(program=plan.program).order_by("-start_date").first()
    )


def build_snapshot(term, now=None):
    """Assemble the `Snapshot` `rank()` runs on from `term`'s in-progress
    Enrollments and the current availability template.
    """

    now = now or timezone.localtime()
    today = now.date()
    window_start = today - datetime.timedelta(days=ROLLING_WINDOW_DAYS - 1)
    program = term.program

    enrollments = (
        term.enrollments.filter(outcome=Outcome.IN_PROGRESS)
        .select_related("course")
        .prefetch_related("graded_items", "study_logs")
    )

    courses = []
    for enrollment in enrollments:
        hours_logged_7d = sum(
            log.hours
            for log in enrollment.study_logs.all()
            if window_start <= log.studied_on <= today
        )
        items = tuple(
            SnapshotItem(name=item.type, weight=item.weight, due_at=item.due_at)
            for item in enrollment.graded_items.all()
        )
        courses.append(
            CourseSnapshot(
                code=enrollment.course.code,
                name=enrollment.course.name,
                credits=enrollment.course.credits,
                difficulty=enrollment.difficulty,
                hours_logged_7d=hours_logged_7d,
                items=items,
            )
        )

    return Snapshot(
        courses=tuple(courses),
        capacity=capacity_hours(),
        hours_left_today=hours_left_in_todays_window(now),
        hours_per_credit=program.hours_per_credit,
        grade_scale_max=program.grade_scale_max,
        days_since_last_log=_days_since_last_log(term, today),
    )


def _days_since_last_log(term, today):
    """Whole days between today and the most recent Study Log's *recorded* date
    (never its studied date — a backdated entry must not clear staleness,
    ADR-0006). None when nothing has ever been logged this Term.
    """

    last_recorded = (
        StudyLog.objects.filter(enrollment__term=term)
        .order_by("-recorded_at")
        .values_list("recorded_at", flat=True)
        .first()
    )
    if last_recorded is None:
        return None
    return (today - timezone.localtime(last_recorded).date()).days


def todays_ranking(term, now=None):
    """`rank()` over `term`, or None when there is nothing to rank."""

    now = now or timezone.localtime()
    snapshot = build_snapshot(term, now)
    if not snapshot.courses:
        return None
    return rank(snapshot, ScoringConfig.load(), now)
