"""Seam 1 (scope.md testing decisions): `rank()`, a pure function over a plain
snapshot. Every case is a snapshot and an expected ordering / committed hours /
reason. Nothing here touches a database or asserts an intermediate value —
Rations and pressures are checked through their effect, never by reaching in.

These are the first tests of the engine and are written to read as its
specification.
"""

import datetime

from django.test import SimpleTestCase
from django.utils.translation import override

from .models import ScoringConfig
from .ranking import (
    RULE_DEADLINE_PRESSURE,
    RULE_HOURS_BEHIND,
    RULE_OVERRIDE,
    CourseSnapshot,
    Reason,
    Snapshot,
    SnapshotItem,
    rank,
)
from .reasons import render_reason

TODAY = datetime.date(2026, 9, 7)


def config(**overrides):
    cfg = ScoringConfig()  # unsaved — field defaults only, no DB
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def item(name="parcial", weight=20.0, due_in=None):
    due_at = None if due_in is None else TODAY + datetime.timedelta(days=due_in)
    return SnapshotItem(name=name, weight=weight, due_at=due_at)


def course(code, *, credits=3, difficulty="normal", logged=0.0, items=()):
    return CourseSnapshot(
        code=code,
        name=f"Course {code}",
        credits=credits,
        difficulty=difficulty,
        hours_logged_7d=logged,
        items=tuple(items),
    )


def snapshot(
    courses,
    *,
    capacity=1000.0,
    hours_left_today=4.0,
    hours_per_credit=3.0,
    grade_scale_max=100.0,
    days_since_last_log=0,
):
    return Snapshot(
        courses=tuple(courses),
        capacity=capacity,
        hours_left_today=hours_left_today,
        hours_per_credit=hours_per_credit,
        grade_scale_max=grade_scale_max,
        days_since_last_log=days_since_last_log,
    )


def by_code(ranking):
    return {c.code: c for c in ranking.courses}


def order(ranking):
    return [c.code for c in ranking.courses]


class RationTests(SimpleTestCase):
    def test_scales_down_proportionally_when_demand_exceeds_capacity(self):
        # Targets 12 and 9, Σ = 21, capacity 10.5 → every Ration halves.
        ranking = rank(
            snapshot(
                [course("A", credits=4), course("B", credits=3)], capacity=10.5
            ),
            config(),
            TODAY,
        )

        rows = by_code(ranking)
        self.assertAlmostEqual(rows["A"].ration, 6.0)
        self.assertAlmostEqual(rows["B"].ration, 4.5)

    def test_collapses_to_raw_target_only_when_capacity_covers_demand(self):
        ranking = rank(
            snapshot([course("A", credits=4)], capacity=1000.0), config(), TODAY
        )

        self.assertAlmostEqual(by_code(ranking)["A"].ration, 12.0)
        self.assertAlmostEqual(by_code(ranking)["A"].target, 12.0)


class HoursBehindTests(SimpleTestCase):
    def test_a_course_ahead_of_its_ration_is_not_behind(self):
        ranking = rank(
            snapshot([course("A", credits=4, logged=20.0)]), config(), TODAY
        )

        row = by_code(ranking)["A"]
        self.assertEqual(row.hours_behind, 0.0)
        self.assertEqual(row.score, 0.0)

    def test_being_ahead_ties_at_zero_rather_than_sorting_below(self):
        # A is far ahead; B is exactly on its Ration. Neither is behind, and
        # neither has anything due — they tie at a zero Score.
        ranking = rank(
            snapshot(
                [
                    course("A", credits=4, logged=50.0),
                    course("B", credits=4, logged=12.0),
                ]
            ),
            config(),
            TODAY,
        )

        rows = by_code(ranking)
        self.assertEqual(rows["A"].score, 0.0)
        self.assertEqual(rows["B"].score, 0.0)

    def test_hours_behind_dominates_a_faint_deadline(self):
        ranking = rank(
            snapshot(
                [
                    course(
                        "A",
                        credits=4,
                        logged=2.0,
                        items=[item(weight=10.0, due_in=10)],
                    )
                ]
            ),
            config(),
            TODAY,
        )

        reason = by_code(ranking)["A"].reason
        self.assertEqual(reason.rule, RULE_HOURS_BEHIND)
        self.assertAlmostEqual(reason.hours_behind, 10.0)
        self.assertIsNone(reason.item_name)


class DeadlinePressureTests(SimpleTestCase):
    def test_an_on_ration_course_with_a_heavy_item_outranks_an_untouched_one(self):
        # The case a pure product got wrong: A sits exactly on its Ration
        # (Hours Behind 0) but has a 40% parcial five days out; B has nothing.
        ranking = rank(
            snapshot(
                [
                    course(
                        "A", credits=4, logged=12.0, items=[item(weight=40.0, due_in=5)]
                    ),
                    course("B", credits=4, logged=12.0),
                ]
            ),
            config(),
            TODAY,
        )

        self.assertEqual(order(ranking), ["A", "B"])
        self.assertGreater(by_code(ranking)["A"].score, 0.0)

    def test_adding_a_graded_item_never_moves_a_course_down(self):
        base = [course("A", credits=4, logged=12.0), course("B", credits=4, logged=12.0)]
        before = rank(snapshot(base), config(), TODAY)
        self.assertEqual(order(before), ["A", "B"])  # tie, broken by code

        after = rank(
            snapshot(
                [
                    course("A", credits=4, logged=12.0),
                    course(
                        "B", credits=4, logged=12.0, items=[item(weight=40.0, due_in=5)]
                    ),
                ]
            ),
            config(),
            TODAY,
        )
        self.assertEqual(order(after), ["B", "A"])

    def test_the_strongest_upcoming_item_drives_pressure_not_the_soonest(self):
        # A 5% quiz tomorrow must not shadow a 40% final in five days.
        ranking = rank(
            snapshot(
                [
                    course(
                        "A",
                        credits=4,
                        logged=12.0,
                        items=[
                            item(name="quiz", weight=5.0, due_in=1),
                            item(name="final", weight=40.0, due_in=5),
                        ],
                    )
                ]
            ),
            config(),
            TODAY,
        )

        reason = by_code(ranking)["A"].reason
        self.assertEqual(reason.rule, RULE_DEADLINE_PRESSURE)
        self.assertEqual(reason.item_name, "final")
        self.assertEqual(reason.item_weight, 40.0)

    def test_a_past_due_item_contributes_nothing_even_months_overdue(self):
        ranking = rank(
            snapshot(
                [
                    course(
                        "A",
                        credits=4,
                        logged=12.0,
                        items=[
                            item(weight=40.0, due_in=-1),
                            item(weight=90.0, due_in=-70),
                        ],
                    )
                ]
            ),
            config(),
            TODAY,
        )

        row = by_code(ranking)["A"]
        self.assertEqual(row.pressure, 0.0)
        self.assertEqual(row.score, 0.0)

    def test_no_upcoming_items_is_zero_pressure_without_zeroing_the_score(self):
        ranking = rank(
            snapshot([course("A", credits=4, logged=2.0)]), config(), TODAY
        )

        row = by_code(ranking)["A"]
        self.assertEqual(row.pressure, 0.0)
        self.assertAlmostEqual(row.score, 10.0)  # 1.0 × (1.0 × 10h behind)


class OverrideTierTests(SimpleTestCase):
    def test_a_weighty_item_inside_the_window_jumps_the_queue(self):
        # B sits on its Ration but has a 40% parcial due tomorrow; A is 10h
        # behind and would win on Score. The Override tier settles it.
        ranking = rank(
            snapshot(
                [
                    course("A", credits=4, logged=2.0),
                    course(
                        "B", credits=4, logged=12.0, items=[item(weight=40.0, due_in=1)]
                    ),
                ]
            ),
            config(),
            TODAY,
        )

        self.assertEqual(order(ranking), ["B", "A"])
        winner = ranking.recommendation
        self.assertEqual(winner.tier, 1)
        self.assertIsNone(winner.score)
        self.assertEqual(winner.reason.rule, RULE_OVERRIDE)
        self.assertEqual(winner.reason.item_weight, 40.0)
        self.assertEqual(winner.reason.days_until_due, 1)

    def test_a_light_item_tomorrow_does_not_displace_a_heavy_one_in_three_days(self):
        ranking = rank(
            snapshot(
                [
                    course(
                        "LIGHT",
                        credits=4,
                        logged=12.0,
                        items=[item(weight=2.0, due_in=1)],
                    ),
                    course(
                        "HEAVY",
                        credits=4,
                        logged=12.0,
                        items=[item(weight=40.0, due_in=3)],
                    ),
                ]
            ),
            config(),
            TODAY,
        )

        self.assertEqual(order(ranking), ["HEAVY", "LIGHT"])
        for row in ranking.courses:
            self.assertEqual(row.tier, 2)

    def test_the_override_tier_always_precedes_tier_two(self):
        ranking = rank(
            snapshot(
                [
                    course("BEHIND", credits=4, logged=0.0),  # huge Score
                    course(
                        "DUE",
                        credits=4,
                        logged=12.0,
                        items=[item(weight=20.0, due_in=2)],
                    ),
                ]
            ),
            config(),
            TODAY,
        )

        self.assertEqual(ranking.courses[0].code, "DUE")
        self.assertEqual(ranking.courses[0].tier, 1)
        self.assertEqual(ranking.courses[1].tier, 2)

    def test_within_the_override_tier_the_heavier_closer_item_wins(self):
        ranking = rank(
            snapshot(
                [
                    course(
                        "HEAVY",
                        credits=4,
                        logged=12.0,
                        items=[item(weight=40.0, due_in=2)],
                    ),
                    course(
                        "CLOSE",
                        credits=4,
                        logged=12.0,
                        items=[item(weight=20.0, due_in=1)],
                    ),
                ]
            ),
            config(),
            TODAY,
        )

        self.assertEqual(order(ranking), ["HEAVY", "CLOSE"])


class CommittedHoursTests(SimpleTestCase):
    def test_capped_by_tonights_free_time(self):
        ranking = rank(
            snapshot(
                [course("A", credits=4, logged=3.0)], hours_left_today=4.0
            ),
            config(),
            TODAY,
        )

        # Ration 12 − 3 logged = 9 owed, but only 4h free tonight.
        self.assertAlmostEqual(by_code(ranking)["A"].committed_hours, 4.0)

    def test_capped_by_the_ration_still_owed(self):
        ranking = rank(
            snapshot(
                [course("A", credits=4, logged=9.0)], hours_left_today=20.0
            ),
            config(),
            TODAY,
        )

        self.assertAlmostEqual(by_code(ranking)["A"].committed_hours, 3.0)

    def test_never_negative_when_the_course_is_already_over_its_ration(self):
        ranking = rank(
            snapshot(
                [course("A", credits=4, logged=20.0)], hours_left_today=4.0
            ),
            config(),
            TODAY,
        )

        self.assertEqual(by_code(ranking)["A"].committed_hours, 0.0)


class DifficultyCompoundingTests(SimpleTestCase):
    def test_a_hard_course_outranks_an_identical_normal_one_by_more_than_1_5(self):
        # Same créditos, same (zero) hours logged. Difficulty raises the hard
        # course's Ration *and* multiplies its Score (ADR-0004).
        ranking = rank(
            snapshot(
                [
                    course("HARD", credits=4, difficulty="hard"),
                    course("NORMAL", credits=4, difficulty="normal"),
                ]
            ),
            config(),
            TODAY,
        )

        rows = by_code(ranking)
        self.assertEqual(order(ranking), ["HARD", "NORMAL"])
        self.assertGreater(rows["HARD"].score, 1.5 * rows["NORMAL"].score)


class StalenessTests(SimpleTestCase):
    def test_past_the_threshold_the_recommendation_still_returns_but_is_flagged(self):
        ranking = rank(
            snapshot([course("A", credits=4)], days_since_last_log=10),
            config(stale_after_days=4),
            TODAY,
        )

        self.assertTrue(ranking.stale)
        self.assertIsNotNone(ranking.recommendation)

    def test_within_the_threshold_is_not_flagged(self):
        ranking = rank(
            snapshot([course("A", credits=4)], days_since_last_log=2),
            config(stale_after_days=4),
            TODAY,
        )

        self.assertFalse(ranking.stale)

    def test_nothing_ever_logged_counts_as_stale(self):
        ranking = rank(
            snapshot([course("A", credits=4)], days_since_last_log=None),
            config(),
            TODAY,
        )

        self.assertTrue(ranking.stale)
        self.assertIsNotNone(ranking.recommendation)


class ReasonStructureTests(SimpleTestCase):
    def test_the_reason_is_structure_not_a_sentence(self):
        ranking = rank(
            snapshot(
                [
                    course(
                        "A",
                        credits=4,
                        logged=12.0,
                        items=[item(name="parcial 2", weight=30.0, due_in=4)],
                    )
                ]
            ),
            config(),
            TODAY,
        )

        reason = ranking.recommendation.reason
        self.assertEqual(reason.rule, RULE_DEADLINE_PRESSURE)
        self.assertEqual(reason.item_name, "parcial 2")
        self.assertEqual(reason.item_weight, 30.0)
        self.assertEqual(reason.days_until_due, 4)


class DeterminismTests(SimpleTestCase):
    def test_identical_snapshots_produce_identical_orderings(self):
        def build():
            return snapshot(
                [
                    course("A", credits=4, logged=1.0, items=[item(weight=20.0, due_in=6)]),
                    course("B", credits=3, logged=0.0),
                    course("C", credits=4, difficulty="hard", logged=5.0),
                ]
            )

        first = rank(build(), config(), TODAY)
        second = rank(build(), config(), TODAY)
        self.assertEqual(first.courses, second.courses)

    def test_a_tie_is_broken_deterministically_by_code(self):
        ranking = rank(
            snapshot([course("Z", credits=4), course("A", credits=4)]),
            config(),
            TODAY,
        )

        self.assertEqual(order(ranking), ["A", "Z"])


class ReasonRenderingTests(SimpleTestCase):
    """ADR-0013: the structured reason renders to one line per locale, outside
    `rank()`. The `es`/`en` catalogs are #6; until then both render the source.
    """

    def test_override_line_carries_item_weight_and_the_word_override(self):
        with override("en"):
            line = render_reason(
                Reason(
                    rule=RULE_OVERRIDE,
                    item_name="Lab 3",
                    item_weight=15.0,
                    days_until_due=1,
                )
            )

        self.assertIn("Lab 3", line)
        self.assertIn("15%", line)
        self.assertIn("override", line)

    def test_deadline_pressure_line_carries_the_item_and_weight(self):
        with override("en"):
            line = render_reason(
                Reason(
                    rule=RULE_DEADLINE_PRESSURE,
                    item_name="final",
                    item_weight=40.0,
                    days_until_due=5,
                )
            )

        self.assertIn("final", line)
        self.assertIn("40%", line)

    def test_hours_behind_line_carries_the_hours(self):
        with override("en"):
            line = render_reason(Reason(rule=RULE_HOURS_BEHIND, hours_behind=12.0))

        self.assertIn("12.0", line)

    def test_renders_under_the_spanish_locale_without_error(self):
        with override("es"):
            line = render_reason(Reason(rule=RULE_HOURS_BEHIND, hours_behind=3.0))

        self.assertTrue(line)
