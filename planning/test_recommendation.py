"""The ORM-to-snapshot adapter — the one piece sitting outside seam 1
(scope.md testing decisions). One test that a realistic Term produces a
snapshot of the right shape, plus the rolling-window and staleness rules the
adapter (not `rank()`) is responsible for.
"""

import datetime

from django.test import TestCase
from django.utils import timezone

from curriculum.models import Course, Institution, Program
from studying.models import Difficulty, Enrollment, GradedItem, Outcome, StudyLog, Term

from .models import StudyWindow, Weekday
from .recommendation import build_snapshot

T = datetime.time


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
        end_date=datetime.date(2026, 6, 15),
    )
    return institution, program, term


def enrol(term, institution, code, credits=4, difficulty=Difficulty.NORMAL):
    course = Course.objects.create(
        institution=institution, code=code, name=f"Course {code}", credits=credits
    )
    return Enrollment.objects.create(
        term=term, course=course, outcome=Outcome.IN_PROGRESS, difficulty=difficulty
    )


def at(year, month, day, hour=20):
    return timezone.make_aware(datetime.datetime(year, month, day, hour, 0))


class SnapshotShapeTests(TestCase):
    def test_a_realistic_term_produces_a_snapshot_of_the_right_shape(self):
        institution, program, term = make_term()
        now = at(2026, 4, 15)  # a Wednesday
        StudyWindow.objects.create(
            weekday=now.weekday(), start=T(0, 0), end=T(23, 59)
        )

        a = enrol(term, institution, "AAA", credits=4, difficulty=Difficulty.HARD)
        b = enrol(term, institution, "BBB", credits=3)
        GradedItem.objects.create(
            enrollment=a, type="parcial", weight=30, due_at=datetime.date(2026, 4, 20)
        )
        StudyLog.objects.create(
            enrollment=a, hours=2.5, studied_on=now.date() - datetime.timedelta(days=1)
        )
        # An Enrollment that has already ended is not ranked.
        ended = enrol(term, institution, "CCC")
        ended.outcome = Outcome.PASSED
        ended.save()

        snap = build_snapshot(term, now)

        self.assertEqual({c.code for c in snap.courses}, {"AAA", "BBB"})
        self.assertEqual(snap.hours_per_credit, 3.0)
        self.assertEqual(snap.grade_scale_max, 100)
        by_code = {c.code: c for c in snap.courses}
        self.assertEqual(by_code["AAA"].difficulty, Difficulty.HARD)
        self.assertEqual(by_code["AAA"].credits, 4)
        self.assertEqual(by_code["AAA"].hours_logged_7d, 2.5)
        self.assertEqual(len(by_code["AAA"].items), 1)
        self.assertEqual(by_code["AAA"].items[0].weight, 30)
        self.assertEqual(by_code["BBB"].items, ())

    def test_capacity_and_hours_left_today_come_from_the_availability_template(self):
        institution, program, term = make_term()
        now = at(2026, 4, 15, hour=18)
        StudyWindow.objects.create(weekday=now.weekday(), start=T(8, 0), end=T(22, 0))
        # Other weekdays add to Capacity but not to tonight's free time.
        StudyWindow.objects.create(weekday=Weekday.SUNDAY, start=T(8, 0), end=T(12, 0))
        enrol(term, institution, "AAA")

        snap = build_snapshot(term, now)

        self.assertEqual(snap.capacity, 14.0 + 4.0)
        self.assertEqual(snap.hours_left_today, 4.0)  # 18:00 → 22:00


class RollingWindowTests(TestCase):
    def test_hours_logged_sums_only_the_trailing_seven_days(self):
        institution, program, term = make_term()
        now = at(2026, 4, 15)
        enrollment = enrol(term, institution, "AAA")
        StudyLog.objects.create(
            enrollment=enrollment, hours=3.0, studied_on=now.date() - datetime.timedelta(days=3)
        )
        StudyLog.objects.create(
            enrollment=enrollment, hours=5.0, studied_on=now.date() - datetime.timedelta(days=10)
        )

        snap = build_snapshot(term, now)

        self.assertEqual(snap.courses[0].hours_logged_7d, 3.0)

    def test_the_window_edge_is_six_days_back_not_seven(self):
        institution, program, term = make_term()
        now = at(2026, 4, 15)
        enrollment = enrol(term, institution, "AAA")
        StudyLog.objects.create(
            enrollment=enrollment, hours=1.0, studied_on=now.date() - datetime.timedelta(days=6)
        )
        StudyLog.objects.create(
            enrollment=enrollment, hours=1.0, studied_on=now.date() - datetime.timedelta(days=7)
        )

        # Advancing "now" by a day drops the six-days-back log smoothly — the
        # value steps by that log's hours, never from full to zero.
        self.assertEqual(build_snapshot(term, now).courses[0].hours_logged_7d, 1.0)
        self.assertEqual(
            build_snapshot(term, now + datetime.timedelta(days=1)).courses[0].hours_logged_7d,
            0.0,
        )


class StalenessInputTests(TestCase):
    def test_days_since_last_log_uses_the_recorded_date_not_the_studied_date(self):
        institution, program, term = make_term()
        now = at(2026, 4, 15)
        enrollment = enrol(term, institution, "AAA")
        log = StudyLog.objects.create(
            enrollment=enrollment, hours=2.0, studied_on=now.date()
        )
        StudyLog.objects.filter(pk=log.pk).update(
            recorded_at=now - datetime.timedelta(days=10)
        )

        snap = build_snapshot(term, now)

        self.assertEqual(snap.days_since_last_log, 10)

    def test_no_logs_at_all_leaves_days_since_none(self):
        institution, program, term = make_term()
        enrol(term, institution, "AAA")

        snap = build_snapshot(term, at(2026, 4, 15))

        self.assertIsNone(snap.days_since_last_log)
