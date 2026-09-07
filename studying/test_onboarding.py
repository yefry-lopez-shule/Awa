"""Tests for the onboarding checklist (#10)."""

import datetime

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from curriculum.models import AppSettings, Block, BlockEntry, Course, Institution, Plan, Prerequisite, Program

from .models import CourseStatus, Difficulty, Enrollment, Outcome, Status, Term, status_for_course


def build_plan():
    """A small plan exercising: a plain course, a course with an unsatisfied
    prerequisite, and an unfilled humanities Slot. Mirrors the real UNED
    shape closely enough to test the checklist without loading all 23 rows.
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
    )
    plan = Plan.objects.create(program=program, name="TEST-1")
    block = Block.objects.create(plan=plan, name="A", credits=10)
    req = Course.objects.create(institution=institution, code="101", name="Intro", credits=4)
    gated = Course.objects.create(institution=institution, code="102", name="Advanced", credits=3)
    entry_req = BlockEntry.objects.create(block=block, course=req, credits=4)
    entry_gated = BlockEntry.objects.create(block=block, course=gated, credits=3)
    Prerequisite.objects.create(plan=plan, course=gated, requires_course=req)
    entry_slot = BlockEntry.objects.create(
        block=block, course=None, credits=3, slot_label="humanidades", slot_index=1
    )

    settings_obj = AppSettings.load()
    settings_obj.active_plan = plan
    settings_obj.save()

    return {
        "institution": institution,
        "program": program,
        "plan": plan,
        "block": block,
        "req": req,
        "gated": gated,
        "entry_req": entry_req,
        "entry_gated": entry_gated,
        "entry_slot": entry_slot,
    }


class OnboardingRenderTests(TestCase):
    def test_renders_all_23_rows_for_the_real_uned_plan(self):
        from pathlib import Path

        from django.conf import settings as dj_settings

        path = Path(dj_settings.BASE_DIR) / "plans" / "uned" / "iic-diplomado-2026.yaml"
        call_command("loadplan", str(path))
        # loadplan sets active_plan automatically when none was set yet.

        response = self.client.get(reverse("studying:onboarding"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rows"]), 23)

    def test_flags_a_course_with_unsatisfied_prerequisite_inline(self):
        ctx = build_plan()

        response = self.client.get(reverse("studying:onboarding"))

        rows_by_entry = {row["entry"].id: row for row in response.context["rows"]}
        self.assertFalse(rows_by_entry[ctx["entry_gated"].id]["unlocked"])
        self.assertTrue(rows_by_entry[ctx["entry_req"].id]["unlocked"])

    def test_revisit_preserves_previously_set_statuses(self):
        ctx = build_plan()
        CourseStatus.objects.create(course=ctx["req"], status=Status.PASSED)

        response = self.client.get(reverse("studying:onboarding"))

        rows_by_entry = {row["entry"].id: row for row in response.context["rows"]}
        self.assertEqual(rows_by_entry[ctx["entry_req"].id]["status"], Status.PASSED)
        self.assertEqual(rows_by_entry[ctx["entry_gated"].id]["status"], Status.PENDING)


class OnboardingSubmitHistoricalStatusTests(TestCase):
    def test_setting_passed_writes_course_status_with_no_enrollment(self):
        ctx = build_plan()

        self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "passed",
                f"grade_{ctx['entry_req'].id}": "85",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "pending",
            },
        )

        self.assertEqual(status_for_course(ctx["req"]), Status.PASSED)
        self.assertEqual(CourseStatus.objects.get(course=ctx["req"]).final_grade, 85)
        self.assertFalse(Enrollment.objects.exists())

    def test_a_course_left_untouched_defaults_to_pending(self):
        ctx = build_plan()

        self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "pending",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "pending",
            },
        )

        self.assertEqual(status_for_course(ctx["req"]), Status.PENDING)

    def test_transferred_accepts_no_grade(self):
        ctx = build_plan()

        response = self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "transferred",
                f"grade_{ctx['entry_req'].id}": "85",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "pending",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CourseStatus.objects.filter(course=ctx["req"]).exists())
        self.assertIn("errors", response.context)

    def test_grade_is_rejected_for_pending_and_in_progress(self):
        ctx = build_plan()
        term = Term.objects.create(
            program=ctx["program"],
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 6, 15),
        )

        response = self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "pending",
                f"grade_{ctx['entry_req'].id}": "85",
                f"status_{ctx['entry_gated'].id}": "in_progress",
                f"grade_{ctx['entry_gated'].id}": "85",
                f"difficulty_{ctx['entry_gated'].id}": "normal",
                f"status_{ctx['entry_slot'].id}": "pending",
            },
        )

        self.assertIn("errors", response.context)
        self.assertFalse(CourseStatus.objects.filter(course=ctx["req"]).exists())
        self.assertFalse(Enrollment.objects.filter(term=term, course=ctx["gated"]).exists())

    def test_unsatisfied_prerequisite_still_saves(self):
        ctx = build_plan()

        self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "pending",
                f"status_{ctx['entry_gated'].id}": "passed",
                f"status_{ctx['entry_slot'].id}": "pending",
            },
        )

        self.assertEqual(status_for_course(ctx["gated"]), Status.PASSED)


class OnboardingSlotTests(TestCase):
    def test_filling_a_slot_creates_the_course_and_fills_the_entry(self):
        ctx = build_plan()

        self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "pending",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "passed",
                f"slot_code_{ctx['entry_slot'].id}": "HUM-01",
                f"slot_name_{ctx['entry_slot'].id}": "Ética",
            },
        )

        ctx["entry_slot"].refresh_from_db()
        self.assertIsNotNone(ctx["entry_slot"].course)
        self.assertEqual(ctx["entry_slot"].course.code, "HUM-01")
        self.assertEqual(ctx["entry_slot"].course.name, "Ética")
        self.assertEqual(ctx["entry_slot"].course.credits, 3)
        self.assertEqual(status_for_course(ctx["entry_slot"].course), Status.PASSED)

    def test_filling_a_slot_with_a_code_that_already_exists_reconciles_instead_of_crashing(self):
        ctx = build_plan()
        # A humanities Course recorded some other way (e.g. a previous partial
        # pass through the checklist) that isn't attached to any BlockEntry.
        existing = Course.objects.create(
            institution=ctx["institution"], code="HUM-01", name="Ética", credits=3
        )

        response = self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "pending",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "passed",
                f"slot_code_{ctx['entry_slot'].id}": "HUM-01",
                f"slot_name_{ctx['entry_slot'].id}": "Some other name typed by mistake",
            },
        )

        self.assertNotEqual(response.status_code, 500)
        ctx["entry_slot"].refresh_from_db()
        self.assertEqual(ctx["entry_slot"].course_id, existing.id)
        self.assertEqual(Course.objects.filter(code="HUM-01").count(), 1)

    def test_leaving_a_slot_unfilled_contributes_credits_but_not_earned(self):
        from studying.queries import credits_earned

        ctx = build_plan()

        self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "passed",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "pending",
            },
        )

        self.assertIsNone(BlockEntry.objects.get(pk=ctx["entry_slot"].id).course)
        self.assertEqual(ctx["plan"].blocks.get(name="A").credits, 10)
        self.assertEqual(credits_earned(ctx["plan"]), 4)


class OnboardingInProgressTests(TestCase):
    def test_marking_in_progress_without_term_dates_prompts_and_saves_nothing(self):
        ctx = build_plan()

        response = self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "in_progress",
                f"difficulty_{ctx['entry_req'].id}": "hard",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "pending",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("errors", response.context)
        self.assertFalse(Term.objects.exists())
        self.assertFalse(Enrollment.objects.exists())

    def test_marking_in_progress_with_term_dates_creates_term_and_enrollment(self):
        ctx = build_plan()

        self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "in_progress",
                f"difficulty_{ctx['entry_req'].id}": "hard",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "pending",
                "term_start": "2026-03-01",
                "term_end": "2026-06-15",
            },
        )

        term = Term.objects.get(program=ctx["program"])
        self.assertEqual(term.start_date, datetime.date(2026, 3, 1))
        enrollment = Enrollment.objects.get(term=term, course=ctx["req"])
        self.assertEqual(enrollment.outcome, Outcome.IN_PROGRESS)
        self.assertEqual(enrollment.difficulty, Difficulty.HARD)
        self.assertEqual(status_for_course(ctx["req"]), Status.IN_PROGRESS)

    def test_second_in_progress_course_reuses_the_existing_term_without_asking_again(self):
        ctx = build_plan()
        term = Term.objects.create(
            program=ctx["program"],
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 6, 15),
        )

        self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "in_progress",
                f"difficulty_{ctx['entry_req'].id}": "normal",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "pending",
            },
        )

        self.assertEqual(Term.objects.count(), 1)
        self.assertTrue(Enrollment.objects.filter(term=term, course=ctx["req"]).exists())

    def test_enrollment_created_is_visible_to_a_rank_shaped_query(self):
        ctx = build_plan()

        self.client.post(
            reverse("studying:onboarding"),
            {
                f"status_{ctx['entry_req'].id}": "in_progress",
                f"difficulty_{ctx['entry_req'].id}": "normal",
                f"status_{ctx['entry_gated'].id}": "pending",
                f"status_{ctx['entry_slot'].id}": "pending",
                "term_start": "2026-03-01",
                "term_end": "2026-06-15",
            },
        )

        in_progress = Enrollment.objects.filter(outcome=Outcome.IN_PROGRESS).select_related("course")
        self.assertEqual(list(in_progress.values_list("course__code", flat=True)), ["101"])
