"""Tests for the pass forecast and its deliberate disagreement with Deadline
Pressure over past-due, ungraded items (#14, ADR-0008).
"""

import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from .forecast import Verdict, forecast
from .ranking import deadline_pressure


def item(weight, grade=None, due_at=None):
    return SimpleNamespace(weight=weight, grade=grade, due_at=due_at)


class ForecastTests(SimpleTestCase):
    def test_returns_the_four_numbers_and_a_verdict(self):
        fc = forecast(
            [item(50, grade=80), item(50, grade=None)], pass_mark=70, grade_scale_max=100
        )

        self.assertEqual(fc.weighted_so_far, 40)  # 80 × 50 / 100
        self.assertEqual(fc.remaining_weight, 50)
        self.assertEqual(fc.required_average, 60)  # 40 + 60 % of 50 = 70
        self.assertEqual(fc.verdict, Verdict.NEEDS)

    def test_an_ungraded_course_needs_the_pass_mark_on_everything(self):
        fc = forecast(
            [item(40), item(30), item(30)], pass_mark=70, grade_scale_max=100
        )

        self.assertEqual(fc.weighted_so_far, 0)
        self.assertEqual(fc.remaining_weight, 100)
        self.assertEqual(fc.required_average, 70)
        self.assertIsNone(fc.grade_so_far)
        self.assertEqual(fc.verdict, Verdict.NEEDS)

    def test_at_or_above_pass_mark_with_weight_remaining_is_secured(self):
        fc = forecast(
            [item(80, grade=90), item(20, grade=None)], pass_mark=70, grade_scale_max=100
        )

        self.assertEqual(fc.weighted_so_far, 72)
        self.assertEqual(fc.verdict, Verdict.SECURED)
        self.assertEqual(fc.required_average, 0.0)  # not a required average

    def test_a_required_average_above_the_scale_max_is_impossible(self):
        fc = forecast(
            [item(70, grade=20), item(30, grade=None)], pass_mark=70, grade_scale_max=100
        )

        self.assertGreater(fc.required_average, 100)
        self.assertEqual(fc.verdict, Verdict.IMPOSSIBLE)

    def test_all_items_graded_and_clear_is_passed(self):
        fc = forecast(
            [item(50, grade=75), item(50, grade=75)], pass_mark=70, grade_scale_max=100
        )

        self.assertEqual(fc.remaining_weight, 0)
        self.assertEqual(fc.verdict, Verdict.PASSED)

    def test_all_items_graded_and_short_is_failed(self):
        fc = forecast(
            [item(50, grade=60), item(50, grade=60)], pass_mark=70, grade_scale_max=100
        )

        self.assertEqual(fc.remaining_weight, 0)
        self.assertEqual(fc.verdict, Verdict.FAILED)

    def test_grade_so_far_is_a_weighted_average_not_the_banked_points(self):
        # One 20-weight parcial at 80: banked 16 points, but the honest
        # mid-term number is 80, not 16.
        fc = forecast(
            [item(20, grade=80), item(80, grade=None)], pass_mark=70, grade_scale_max=100
        )

        self.assertEqual(fc.weighted_so_far, 16)
        self.assertEqual(fc.grade_so_far, 80)

    def test_a_non_hundred_grade_scale_is_respected(self):
        fc = forecast(
            [item(5, grade=8), item(5, grade=None)], pass_mark=7, grade_scale_max=10
        )

        self.assertEqual(fc.weighted_so_far, 4)  # 8 × 5 / 10
        self.assertEqual(fc.required_average, 6)  # 4 + 60 % of 5 = 7


class PastDueContrastTests(SimpleTestCase):
    """A past-due, ungraded item counts full weight toward the forecast's
    remaining_weight but exerts zero Deadline Pressure — same rows, opposite
    reading at the due date (ADR-0008).
    """

    def setUp(self):
        self.today = datetime.date(2026, 5, 1)
        self.overdue_ungraded = item(30, grade=None, due_at=datetime.date(2026, 4, 1))
        self.done = item(70, grade=80, due_at=datetime.date(2026, 3, 1))
        self.items = [self.overdue_ungraded, self.done]

    def test_forecast_includes_the_past_due_ungraded_item_in_remaining_weight(self):
        fc = forecast(self.items, pass_mark=70, grade_scale_max=100)

        self.assertEqual(fc.remaining_weight, 30)
        # required average is computed over that 30 weight, overdue item and all
        self.assertAlmostEqual(fc.required_average, (70 - 56) / 30 * 100)

    def test_the_same_item_contributes_zero_deadline_pressure(self):
        self.assertEqual(
            deadline_pressure(self.items, grade_scale_max=100, today=self.today),
            0.0,
        )

    def test_deadline_pressure_is_non_zero_only_for_an_upcoming_item(self):
        upcoming = item(30, grade=None, due_at=datetime.date(2026, 5, 8))

        self.assertGreater(
            deadline_pressure([upcoming, self.done], grade_scale_max=100, today=self.today),
            0.0,
        )
