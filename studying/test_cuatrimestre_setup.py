"""Tests for Cuatrimestre setup (#17): term closeout, then the new-Term
form — dates, enrol + Difficulty off the seeded Plan, and the deadlines grid.
"""

import datetime

from django.test import TestCase
from django.urls import reverse

from curriculum.models import (
    AppSettings,
    Block,
    BlockEntry,
    Course,
    Institution,
    Plan,
    Prerequisite,
    Program,
)

from .models import (
    CourseStatus,
    Difficulty,
    Enrollment,
    GradedItem,
    Outcome,
    Status,
    Term,
    status_for_course,
)

URL = reverse("studying:cuatrimestre_setup")


def build(*, with_last_term=True):
    """A two-Course Plan (`102` requires `101`), a Program whose
    `default_items` sum to 100, and — by default — a most-recent Term with
    `101` still in progress so the page opens on closeout.
    """

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
        item_types=["tarea", "parcial", "final"],
        default_items=[
            {"type": "tarea", "weight": 20},
            {"type": "parcial", "weight": 30},
            {"type": "final", "weight": 50},
        ],
    )
    plan = Plan.objects.create(program=program, name="TEST-1")
    block = Block.objects.create(plan=plan, name="A", credits=8)
    intro = Course.objects.create(institution=institution, code="101", name="Intro", credits=4)
    advanced = Course.objects.create(institution=institution, code="102", name="Advanced", credits=4)
    BlockEntry.objects.create(block=block, course=intro, credits=4)
    BlockEntry.objects.create(block=block, course=advanced, credits=4)
    Prerequisite.objects.create(plan=plan, course=advanced, requires_course=intro)

    settings_obj = AppSettings.load()
    settings_obj.active_plan = plan
    settings_obj.save()

    ctx = {
        "institution": institution,
        "program": program,
        "plan": plan,
        "intro": intro,
        "advanced": advanced,
    }
    if with_last_term:
        term = Term.objects.create(
            program=program,
            start_date=datetime.date(2025, 1, 6),
            end_date=datetime.date(2025, 4, 25),
        )
        enrollment = Enrollment.objects.create(
            term=term, course=intro, outcome=Outcome.IN_PROGRESS
        )
        ctx["last_term"] = term
        ctx["enrollment"] = enrollment
    return ctx


def prefilled_grid(course, **overrides):
    """The three `default_items` rows for `course`, all present and summing to
    100. `overrides` replace individual `deadline_<id>_<row>_<field>` keys.
    """

    cid = course.id
    data = {
        f"deadline_{cid}_0_type": "tarea",
        f"deadline_{cid}_0_weight": "20",
        f"deadline_{cid}_1_type": "parcial",
        f"deadline_{cid}_1_weight": "30",
        f"deadline_{cid}_2_type": "final",
        f"deadline_{cid}_2_weight": "50",
    }
    data.update(overrides)
    return data


class CloseoutGateTests(TestCase):
    def test_page_opens_on_closeout_while_last_term_has_an_in_progress_enrollment(self):
        build()

        response = self.client.get(URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["step"], "closeout")

    def test_new_term_submission_is_refused_while_the_last_term_is_unclosed(self):
        ctx = build()

        self.client.post(
            URL,
            {
                "term_start": "2025-05-05",
                "term_end": "2025-08-22",
                f"enrol_{ctx['intro'].id}": "on",
                **prefilled_grid(ctx["intro"]),
            },
        )

        # Only the pre-existing Term survives; no new one was opened.
        self.assertEqual(Term.objects.count(), 1)
        self.assertEqual(Term.objects.get(), ctx["last_term"])

    def test_page_opens_on_the_new_term_form_when_no_term_was_ever_opened(self):
        build(with_last_term=False)

        response = self.client.get(URL)

        self.assertEqual(response.context["step"], "new_term")


class DerivedOutcomeTests(TestCase):
    def test_outcome_is_derived_passed_when_weighted_grade_clears_the_pass_mark(self):
        ctx = build()
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="parcial", weight=40, grade=90)
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=60, grade=80)

        response = self.client.get(URL)

        row = response.context["closeout_rows"][0]
        self.assertEqual(row["derived"], Outcome.PASSED)
        self.assertAlmostEqual(row["weighted_so_far"], 84)  # (90*40 + 80*60)/100

    def test_outcome_is_derived_failed_when_the_weighted_grade_is_short(self):
        ctx = build()
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="parcial", weight=40, grade=50)
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=60, grade=60)

        response = self.client.get(URL)

        self.assertEqual(response.context["closeout_rows"][0]["derived"], Outcome.FAILED)

    def test_confirming_the_derivation_writes_the_outcome_and_the_status(self):
        ctx = build()
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=100, grade=88)

        self.client.post(URL, {f"outcome_{ctx['enrollment'].id}": "passed"})

        ctx["enrollment"].refresh_from_db()
        self.assertEqual(ctx["enrollment"].outcome, Outcome.PASSED)
        self.assertEqual(status_for_course(ctx["intro"]), Status.PASSED)
        self.assertEqual(CourseStatus.objects.get(course=ctx["intro"]).final_grade, 88)

    def test_an_override_wins_over_the_derivation(self):
        ctx = build()
        # Weighted grade 40 → derivation says failed.
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=100, grade=40)
        self.assertEqual(
            self.client.get(URL).context["closeout_rows"][0]["derived"], Outcome.FAILED
        )

        self.client.post(URL, {f"outcome_{ctx['enrollment'].id}": "passed"})

        ctx["enrollment"].refresh_from_db()
        self.assertEqual(ctx["enrollment"].outcome, Outcome.PASSED)
        self.assertEqual(status_for_course(ctx["intro"]), Status.PASSED)

    def test_a_missing_outcome_is_reported_and_nothing_is_written(self):
        ctx = build()

        response = self.client.post(URL, {})

        self.assertIn("errors", response.context)
        ctx["enrollment"].refresh_from_db()
        self.assertEqual(ctx["enrollment"].outcome, Outcome.IN_PROGRESS)
        self.assertFalse(CourseStatus.objects.filter(course=ctx["intro"]).exists())


class UnlockOnCloseoutTests(TestCase):
    def test_closing_a_passing_term_unlocks_the_prerequisites_it_satisfies(self):
        ctx = build()

        self.client.post(URL, {f"outcome_{ctx['enrollment'].id}": "passed"})

        response = self.client.get(URL)
        self.assertEqual(response.context["step"], "new_term")
        offered = {row["course"] for row in response.context["enrol_rows"]}
        self.assertIn(ctx["advanced"], offered)

    def test_a_still_locked_course_is_not_offered_after_a_failing_closeout(self):
        ctx = build()

        self.client.post(URL, {f"outcome_{ctx['enrollment'].id}": "failed"})

        response = self.client.get(URL)
        offered = {row["course"] for row in response.context["enrol_rows"]}
        self.assertNotIn(ctx["advanced"], offered)
        self.assertIn(ctx["intro"], offered)  # a failed Course can be retaken


class NewTermTests(TestCase):
    def setUp(self):
        self.ctx = build(with_last_term=False)

    def test_the_deadlines_grid_is_prefilled_from_default_items(self):
        response = self.client.get(URL)

        row = response.context["enrol_rows"][0]
        types = [drow.get("type") for _, drow in row["deadline_rows"]]
        self.assertEqual(types[:3], ["tarea", "parcial", "final"])
        # Two spare rows for additions beyond the template.
        self.assertEqual(len(row["deadline_rows"]), 5)

    def test_enrolling_ticks_a_course_with_difficulty_and_creates_its_graded_items(self):
        self.client.post(
            URL,
            {
                "term_start": "2025-05-05",
                "term_end": "2025-08-22",
                f"enrol_{self.ctx['intro'].id}": "on",
                f"difficulty_{self.ctx['intro'].id}": "hard",
                **prefilled_grid(self.ctx["intro"]),
            },
        )

        term = Term.objects.get()
        self.assertEqual(term.start_date, datetime.date(2025, 5, 5))
        enrollment = Enrollment.objects.get(term=term, course=self.ctx["intro"])
        self.assertEqual(enrollment.outcome, Outcome.IN_PROGRESS)
        self.assertEqual(enrollment.difficulty, Difficulty.HARD)
        self.assertEqual(status_for_course(self.ctx["intro"]), Status.IN_PROGRESS)
        self.assertEqual(
            sorted(i.weight for i in enrollment.graded_items.all()), [20, 30, 50]
        )

    def test_an_unticked_course_is_not_enrolled(self):
        self.client.post(
            URL,
            {
                "term_start": "2025-05-05",
                "term_end": "2025-08-22",
                f"enrol_{self.ctx['intro'].id}": "on",
                **prefilled_grid(self.ctx["intro"]),
            },
        )

        # `102` is locked anyway, but prove nothing was enrolled for it.
        self.assertFalse(
            Enrollment.objects.filter(course=self.ctx["advanced"]).exists()
        )

    def test_weights_not_summing_to_the_scale_max_are_reported_and_nothing_saved(self):
        response = self.client.post(
            URL,
            {
                "term_start": "2025-05-05",
                "term_end": "2025-08-22",
                f"enrol_{self.ctx['intro'].id}": "on",
                **prefilled_grid(
                    self.ctx["intro"], **{f"deadline_{self.ctx['intro'].id}_2_weight": "40"}
                ),
            },
        )

        self.assertIn("errors", response.context)
        self.assertFalse(Term.objects.exists())
        self.assertFalse(GradedItem.objects.exists())

    def test_a_spare_row_adds_an_item_beyond_the_template(self):
        cid = self.ctx["intro"].id
        self.client.post(
            URL,
            {
                "term_start": "2025-05-05",
                "term_end": "2025-08-22",
                f"enrol_{cid}": "on",
                **prefilled_grid(
                    self.ctx["intro"],
                    **{
                        f"deadline_{cid}_2_weight": "40",
                        f"deadline_{cid}_3_type": "tarea",
                        f"deadline_{cid}_3_weight": "10",
                    },
                ),
            },
        )

        enrollment = Enrollment.objects.get(course=self.ctx["intro"])
        self.assertEqual(enrollment.graded_items.count(), 4)

    def test_a_removed_row_is_not_created(self):
        cid = self.ctx["intro"].id
        self.client.post(
            URL,
            {
                "term_start": "2025-05-05",
                "term_end": "2025-08-22",
                f"enrol_{cid}": "on",
                **prefilled_grid(
                    self.ctx["intro"],
                    **{
                        f"deadline_{cid}_0_delete": "on",
                        f"deadline_{cid}_1_weight": "40",
                        f"deadline_{cid}_2_weight": "60",
                    },
                ),
            },
        )

        types = sorted(i.type for i in GradedItem.objects.all())
        self.assertEqual(types, ["final", "parcial"])

    def test_due_dates_typed_into_the_grid_are_stored(self):
        cid = self.ctx["intro"].id
        self.client.post(
            URL,
            {
                "term_start": "2025-05-05",
                "term_end": "2025-08-22",
                f"enrol_{cid}": "on",
                **prefilled_grid(
                    self.ctx["intro"], **{f"deadline_{cid}_2_due": "2025-08-15"}
                ),
            },
        )

        final = GradedItem.objects.get(type="final")
        self.assertEqual(final.due_at, datetime.date(2025, 8, 15))

    def test_setup_with_no_course_ticked_is_refused(self):
        response = self.client.post(
            URL, {"term_start": "2025-05-05", "term_end": "2025-08-22"}
        )

        self.assertIn("errors", response.context)
        self.assertFalse(Term.objects.exists())

    def test_missing_term_dates_are_reported(self):
        response = self.client.post(
            URL,
            {
                f"enrol_{self.ctx['intro'].id}": "on",
                **prefilled_grid(self.ctx["intro"]),
            },
        )

        self.assertIn("errors", response.context)
        self.assertFalse(Term.objects.exists())


class NoPlanTests(TestCase):
    def test_renders_without_an_active_plan(self):
        response = self.client.get(URL)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["plan"])
