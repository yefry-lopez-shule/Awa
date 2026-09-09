"""Tests for Course detail's Graded Items grid (#13)."""

import datetime

from django.test import TestCase
from django.urls import reverse

from curriculum.models import AppSettings, Block, BlockEntry, Course, Institution, Plan, Program

from .models import CourseStatus, Enrollment, GradedItem, Outcome, Status, Term


def build_enrollment():
    """One active Enrollment on a Program whose grade scale is 100 and whose
    item types are the UNED set. Enough to drive the grid without loading a
    full Plan.
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
    )
    plan = Plan.objects.create(program=program, name="TEST-1")
    block = Block.objects.create(plan=plan, name="A", credits=4)
    course = Course.objects.create(institution=institution, code="101", name="Intro", credits=4)
    BlockEntry.objects.create(block=block, course=course, credits=4)
    term = Term.objects.create(
        program=program,
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 6, 15),
    )
    enrollment = Enrollment.objects.create(term=term, course=course, outcome=Outcome.IN_PROGRESS)

    settings_obj = AppSettings.load()
    settings_obj.active_plan = plan
    settings_obj.save()

    return {
        "institution": institution,
        "program": program,
        "plan": plan,
        "course": course,
        "term": term,
        "enrollment": enrollment,
    }


def full_grid(**overrides):
    """Three items whose weights sum to 100 — a submission that passes the
    weight check. Pass `prefix`/field overrides to mutate one row.
    """

    data = {
        "new_item_type": "",
        "new_item_weight": "",
        "new_item_due": "",
        "new_item_grade": "",
    }
    data.update(overrides)
    return data


class GradedItemModelTests(TestCase):
    def test_graded_item_attaches_to_an_enrollment(self):
        ctx = build_enrollment()

        item = GradedItem.objects.create(
            enrollment=ctx["enrollment"], type="parcial", weight=20, due_at=datetime.date(2026, 4, 1)
        )

        self.assertEqual(list(ctx["enrollment"].graded_items.all()), [item])
        self.assertIsNone(item.grade)


class CourseDetailGridRenderTests(TestCase):
    def test_active_enrollment_renders_the_grid_with_program_item_types(self):
        ctx = build_enrollment()
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=100)

        response = self.client.get(reverse("studying:course_detail", args=[ctx["course"].id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["items"]), 1)
        self.assertEqual(response.context["item_types"], ["tarea", "parcial", "final"])
        self.assertEqual(response.context["weight_total"], 100)

    def test_course_with_no_enrollment_shows_status_and_no_grid(self):
        ctx = build_enrollment()
        ctx["enrollment"].delete()
        CourseStatus.objects.create(
            course=ctx["course"], status=Status.PASSED, final_grade=88
        )

        response = self.client.get(reverse("studying:course_detail", args=[ctx["course"].id]))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["enrollment"])
        self.assertNotIn("items", response.context)
        self.assertContains(response, "88")


class CourseDetailForecastTests(TestCase):
    """#14: the live forecast for an active Enrollment; Status + final_grade
    and no forecast section for a historical-only Course.
    """

    def test_active_enrollment_shows_the_live_forecast(self):
        ctx = build_enrollment()
        GradedItem.objects.create(
            enrollment=ctx["enrollment"], type="parcial", weight=40, grade=80
        )
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=60)

        response = self.client.get(
            reverse("studying:course_detail", args=[ctx["course"].id]),
            headers={"accept-language": "en"},
        )

        forecast = response.context["forecast"]
        self.assertEqual(forecast.weighted_so_far, 32)  # 80 × 40 / 100
        self.assertEqual(forecast.remaining_weight, 60)
        self.assertAlmostEqual(forecast.required_average, (70 - 32) / 60 * 100)
        self.assertContains(response, "Pass forecast")

    def test_enrollment_with_no_graded_items_yet_shows_no_forecast(self):
        ctx = build_enrollment()

        response = self.client.get(
            reverse("studying:course_detail", args=[ctx["course"].id])
        )

        self.assertNotIn("forecast", response.context)

    def test_historical_only_course_shows_status_and_final_grade_no_forecast(self):
        ctx = build_enrollment()
        ctx["enrollment"].delete()
        CourseStatus.objects.create(
            course=ctx["course"], status=Status.PASSED, final_grade=91
        )

        response = self.client.get(
            reverse("studying:course_detail", args=[ctx["course"].id]),
            headers={"accept-language": "en"},
        )

        self.assertNotIn("forecast", response.context)
        self.assertNotContains(response, "Pass forecast")
        self.assertContains(response, "91")


class CourseDetailGridWriteTests(TestCase):
    def post(self, ctx, data):
        return self.client.post(
            reverse("studying:course_detail", args=[ctx["course"].id]), data
        )

    def test_creates_items_from_the_new_row(self):
        ctx = build_enrollment()

        self.post(
            ctx,
            full_grid(
                new_item_type="final",
                new_item_weight="100",
                new_item_due="2026-06-10",
            ),
        )

        item = GradedItem.objects.get(enrollment=ctx["enrollment"])
        self.assertEqual(item.type, "final")
        self.assertEqual(item.weight, 100)
        self.assertEqual(item.due_at, datetime.date(2026, 6, 10))

    def test_edits_an_existing_item_in_place(self):
        ctx = build_enrollment()
        item = GradedItem.objects.create(
            enrollment=ctx["enrollment"], type="parcial", weight=100, due_at=datetime.date(2026, 4, 1)
        )

        self.post(
            ctx,
            full_grid(
                **{
                    f"item_{item.id}_type": "final",
                    f"item_{item.id}_weight": "100",
                    f"item_{item.id}_due": "2026-05-01",
                    f"item_{item.id}_grade": "",
                }
            ),
        )

        item.refresh_from_db()
        self.assertEqual(item.type, "final")
        self.assertEqual(item.due_at, datetime.date(2026, 5, 1))
        self.assertEqual(GradedItem.objects.count(), 1)

    def test_removes_an_item_via_the_delete_checkbox(self):
        ctx = build_enrollment()
        keep = GradedItem.objects.create(enrollment=ctx["enrollment"], type="parcial", weight=60)
        drop = GradedItem.objects.create(enrollment=ctx["enrollment"], type="tarea", weight=40)

        self.post(
            ctx,
            full_grid(
                **{
                    f"item_{keep.id}_type": "parcial",
                    f"item_{keep.id}_weight": "100",
                    f"item_{drop.id}_type": "tarea",
                    f"item_{drop.id}_weight": "40",
                    f"item_{drop.id}_delete": "on",
                }
            ),
        )

        self.assertEqual(list(GradedItem.objects.all()), [keep])

    def test_a_grade_is_optional_and_can_be_entered_later(self):
        ctx = build_enrollment()

        self.post(
            ctx, full_grid(new_item_type="final", new_item_weight="100", new_item_due="2026-06-10")
        )
        item = GradedItem.objects.get(enrollment=ctx["enrollment"])
        self.assertIsNone(item.grade)

        self.post(
            ctx,
            full_grid(
                **{
                    f"item_{item.id}_type": "final",
                    f"item_{item.id}_weight": "100",
                    f"item_{item.id}_due": "2026-06-10",
                    f"item_{item.id}_grade": "73",
                }
            ),
        )
        item.refresh_from_db()
        self.assertEqual(item.grade, 73)

    def test_weights_not_summing_to_grade_scale_max_are_reported_and_not_saved(self):
        ctx = build_enrollment()

        response = self.post(
            ctx,
            full_grid(
                new_item_type="parcial",
                new_item_weight="30",
                new_item_due="2026-04-01",
            ),
        )

        self.assertIn("errors", response.context)
        self.assertFalse(GradedItem.objects.exists())

    def test_a_partial_edit_that_breaks_the_sum_leaves_the_stored_grid_untouched(self):
        ctx = build_enrollment()
        a = GradedItem.objects.create(enrollment=ctx["enrollment"], type="parcial", weight=50)
        b = GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=50)

        response = self.post(
            ctx,
            full_grid(
                **{
                    f"item_{a.id}_type": "parcial",
                    f"item_{a.id}_weight": "20",
                    f"item_{b.id}_type": "final",
                    f"item_{b.id}_weight": "50",
                }
            ),
        )

        self.assertIn("errors", response.context)
        a.refresh_from_db()
        self.assertEqual(a.weight, 50)
        self.assertEqual(GradedItem.objects.count(), 2)

    def test_an_item_type_outside_the_programs_list_is_rejected(self):
        ctx = build_enrollment()

        response = self.post(
            ctx, full_grid(new_item_type="essay", new_item_weight="100")
        )

        self.assertIn("errors", response.context)
        self.assertFalse(GradedItem.objects.exists())

    def test_an_empty_grid_is_a_valid_saved_state(self):
        ctx = build_enrollment()
        item = GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=100)

        response = self.post(
            ctx,
            full_grid(
                **{
                    f"item_{item.id}_type": "final",
                    f"item_{item.id}_weight": "100",
                    f"item_{item.id}_delete": "on",
                }
            ),
        )

        self.assertNotIn("errors", getattr(response, "context", {}) or {})
        self.assertFalse(GradedItem.objects.exists())

    def test_a_due_date_edited_here_is_reflected_on_the_next_read(self):
        ctx = build_enrollment()
        item = GradedItem.objects.create(
            enrollment=ctx["enrollment"], type="final", weight=100, due_at=datetime.date(2026, 6, 1)
        )

        self.post(
            ctx,
            full_grid(
                **{
                    f"item_{item.id}_type": "final",
                    f"item_{item.id}_weight": "100",
                    f"item_{item.id}_due": "2026-06-20",
                }
            ),
        )

        self.assertEqual(GradedItem.objects.get(id=item.id).due_at, datetime.date(2026, 6, 20))
        response = self.client.get(reverse("studying:course_detail", args=[ctx["course"].id]))
        self.assertEqual(response.context["items"][0].due_at, datetime.date(2026, 6, 20))


class CourseDetailResponsiveReflowTests(TestCase):
    """#32: the Graded Items grid reflows to stacked, labelled rows on a
    narrow viewport — a `data-label` on every body cell plus a CSS rule, no
    JS and no view change.
    """

    def test_every_grid_cell_carries_its_column_label(self):
        ctx = build_enrollment()
        GradedItem.objects.create(enrollment=ctx["enrollment"], type="final", weight=100)

        html = self.client.get(
            reverse("studying:course_detail", args=[ctx["course"].id]),
            headers={"accept-language": "en"},
        ).content.decode()

        for label in ("Type", "Weight", "Due", "Grade", "Remove"):
            self.assertIn(f'data-label="{label}"', html)
        self.assertNotIn("<script", html)
