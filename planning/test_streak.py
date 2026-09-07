"""The Streak: consecutive days a Study Log was *recorded* (CONTEXT.md).

`recorded_at` is `auto_now_add`, so these tests force it with a queryset
`update()` to place a log on a given day — the same move the staleness tests
use.
"""

import datetime

from django.test import TestCase
from django.utils import timezone

from curriculum.models import Course, Institution, Program
from studying.models import Difficulty, Enrollment, Outcome, StudyLog, Term

from .streak import current_streak

TODAY = datetime.date(2026, 9, 7)


def make_term():
    institution = Institution.objects.create(name="Test U", country="CR")
    program = Program.objects.create(
        institution=institution,
        name="Test Program",
        code="TEST-1",
        pass_mark=70,
        hours_per_credit=3.0,
        grade_scale_max=100,
        term_type="cuatrimestre",
        term_weeks=15,
        terms_per_year=3,
    )
    term = Term.objects.create(
        program=program,
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 12, 15),
    )
    course = Course.objects.create(
        institution=institution, code="AAA", name="Course AAA", credits=4
    )
    enrollment = Enrollment.objects.create(
        term=term, course=course, outcome=Outcome.IN_PROGRESS, difficulty=Difficulty.NORMAL
    )
    return term, enrollment


def log_recorded_on(enrollment, day, *, studied_on=None, hours=1.0):
    """A Study Log whose `recorded_at` lands on `day` (local noon)."""

    log = StudyLog.objects.create(
        enrollment=enrollment, hours=hours, studied_on=studied_on or day
    )
    recorded_at = timezone.make_aware(
        datetime.datetime.combine(day, datetime.time(12, 0))
    )
    StudyLog.objects.filter(pk=log.pk).update(recorded_at=recorded_at)
    return log


class CurrentStreakTests(TestCase):
    def test_no_logs_is_a_zero_streak(self):
        term, _ = make_term()

        self.assertEqual(current_streak(term, TODAY), 0)

    def test_counts_consecutive_recorded_days_ending_today(self):
        term, enrollment = make_term()
        for delta in (0, 1, 2):
            log_recorded_on(enrollment, TODAY - datetime.timedelta(days=delta))

        self.assertEqual(current_streak(term, TODAY), 3)

    def test_multiple_logs_on_one_day_count_once(self):
        term, enrollment = make_term()
        log_recorded_on(enrollment, TODAY)
        log_recorded_on(enrollment, TODAY)
        log_recorded_on(enrollment, TODAY - datetime.timedelta(days=1))

        self.assertEqual(current_streak(term, TODAY), 2)

    def test_a_day_with_nothing_recorded_breaks_the_run(self):
        term, enrollment = make_term()
        log_recorded_on(enrollment, TODAY)
        log_recorded_on(enrollment, TODAY - datetime.timedelta(days=1))
        # nothing on TODAY-2
        log_recorded_on(enrollment, TODAY - datetime.timedelta(days=3))
        log_recorded_on(enrollment, TODAY - datetime.timedelta(days=4))

        self.assertEqual(current_streak(term, TODAY), 2)

    def test_nothing_recorded_today_is_a_zero_streak_even_after_a_long_run(self):
        term, enrollment = make_term()
        for delta in (1, 2, 3, 4):
            log_recorded_on(enrollment, TODAY - datetime.timedelta(days=delta))

        self.assertEqual(current_streak(term, TODAY), 0)

    def test_a_backdated_studied_date_does_not_fill_a_gap_in_the_run(self):
        term, enrollment = make_term()
        # Recorded today and yesterday — a two-day run.
        log_recorded_on(enrollment, TODAY)
        log_recorded_on(enrollment, TODAY - datetime.timedelta(days=1))
        # A session for five days ago, entered late: recorded today, so it
        # cannot reach back past the gap on TODAY-2.
        log_recorded_on(
            enrollment,
            TODAY,
            studied_on=TODAY - datetime.timedelta(days=5),
        )

        self.assertEqual(current_streak(term, TODAY), 2)

    def test_a_log_recorded_today_extends_a_run_that_ended_yesterday(self):
        term, enrollment = make_term()
        log_recorded_on(enrollment, TODAY - datetime.timedelta(days=1))
        self.assertEqual(current_streak(term, TODAY), 0)  # nothing today yet

        log_recorded_on(enrollment, TODAY)
        self.assertEqual(current_streak(term, TODAY), 2)
