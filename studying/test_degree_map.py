"""Tests for the degree map (#11).

Seam 2 of the spec: what the screen shows, plus the projection added to #9's
query module. Assertions are against rendered/context state and the query's
return value, not how either is phrased internally.
"""

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

from .models import CourseStatus, Status
from .queries import opens_next_term


def make_program():
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
    return institution, program


def course(institution, code, credits=3, name=None):
    return Course.objects.create(
        institution=institution, code=code, name=name or code, credits=credits
    )


def build_map_plan():
    """A two-Bloque Plan exercising every label the map can show:

    Bloque A (10 cr): 03304 passed (4) · 03071 in progress (3) · one Slot (3)
    Bloque B (9 cr):  00823 gated only by 03071 (in progress) → opens next term
                      00831 gated by 03071 + a pending course → neither label
                      00226 gated only by 03304 (passed)      → unlocked
    """

    institution, program = make_program()
    plan = Plan.objects.create(program=program, name="TEST-1")

    a = Block.objects.create(plan=plan, name="A", credits=10)
    b = Block.objects.create(plan=plan, name="B", credits=9)

    passed = course(institution, "03304", credits=4)
    in_progress = course(institution, "03071", credits=3)
    pending = course(institution, "04168", credits=4)  # not on any Block entry here
    opens = course(institution, "00823", credits=3)
    still_locked = course(institution, "00831", credits=3)
    unlocked = course(institution, "00226", credits=3)

    BlockEntry.objects.create(block=a, course=passed, credits=4)
    BlockEntry.objects.create(block=a, course=in_progress, credits=3)
    slot = BlockEntry.objects.create(
        block=a, course=None, credits=3, slot_label="humanidades", slot_index=1
    )
    e_opens = BlockEntry.objects.create(block=b, course=opens, credits=3)
    e_locked = BlockEntry.objects.create(block=b, course=still_locked, credits=3)
    e_unlocked = BlockEntry.objects.create(block=b, course=unlocked, credits=3)

    Prerequisite.objects.create(plan=plan, course=opens, requires_course=in_progress)
    Prerequisite.objects.create(plan=plan, course=still_locked, requires_course=in_progress)
    Prerequisite.objects.create(plan=plan, course=still_locked, requires_course=pending)
    Prerequisite.objects.create(plan=plan, course=unlocked, requires_course=passed)

    CourseStatus.objects.create(course=passed, status=Status.PASSED)
    CourseStatus.objects.create(course=in_progress, status=Status.IN_PROGRESS)

    settings_obj = AppSettings.load()
    settings_obj.active_plan = plan
    settings_obj.save()

    return {
        "institution": institution,
        "program": program,
        "plan": plan,
        "in_progress": in_progress,
        "opens": opens,
        "still_locked": still_locked,
        "unlocked": unlocked,
        "slot": slot,
        "e_opens": e_opens,
        "e_locked": e_locked,
        "e_unlocked": e_unlocked,
    }


def rows_by_entry(response):
    rows = {}
    for block in response.context["blocks"]:
        for row in block["rows"]:
            rows[row["entry"].id] = row
    return rows


class DegreeMapCreditsTests(TestCase):
    def test_bloque_totals_and_credits_earned_match_the_fixture(self):
        build_map_plan()

        response = self.client.get(reverse("studying:degree_map"))

        blocks = {b["block"].name: b for b in response.context["blocks"]}
        self.assertEqual(blocks["A"]["credits_total"], 10)
        self.assertEqual(blocks["A"]["credits_earned"], 4)  # only 03304 passed
        self.assertEqual(blocks["B"]["credits_earned"], 0)
        self.assertEqual(response.context["credits_earned_total"], 4)
        self.assertEqual(response.context["credits_required"], 19)


class DegreeMapUnlockTests(TestCase):
    def test_course_with_every_prerequisite_passed_shows_unlocked(self):
        ctx = build_map_plan()

        response = self.client.get(reverse("studying:degree_map"))

        row = rows_by_entry(response)[ctx["e_unlocked"].id]
        self.assertTrue(row["unlocked"])
        self.assertFalse(row["opens_next_term"])

    def test_course_gated_only_by_in_progress_course_opens_next_term(self):
        ctx = build_map_plan()

        response = self.client.get(reverse("studying:degree_map"))

        row = rows_by_entry(response)[ctx["e_opens"].id]
        self.assertFalse(row["unlocked"])
        self.assertTrue(row["opens_next_term"])

    def test_opens_next_term_label_is_visibly_distinct_from_unlocked(self):
        build_map_plan()

        html = self.client.get(reverse("studying:degree_map")).content.decode()

        self.assertIn('class="unlocked"', html)
        self.assertIn('class="projection"', html)

    def test_course_gated_by_a_pending_course_shows_neither_label(self):
        ctx = build_map_plan()

        response = self.client.get(reverse("studying:degree_map"))

        row = rows_by_entry(response)[ctx["e_locked"].id]
        self.assertFalse(row["unlocked"])
        self.assertFalse(row["opens_next_term"])

    def test_failing_the_in_progress_course_drops_the_dependent_from_the_projection(self):
        ctx = build_map_plan()
        self.assertTrue(opens_next_term(ctx["opens"], ctx["plan"]))

        CourseStatus.objects.filter(course=ctx["in_progress"]).update(status=Status.FAILED)

        response = self.client.get(reverse("studying:degree_map"))
        row = rows_by_entry(response)[ctx["e_opens"].id]
        self.assertFalse(row["opens_next_term"])
        self.assertFalse(row["unlocked"])


class DegreeMapSlotTests(TestCase):
    def test_unfilled_slot_renders_as_outstanding_with_its_credits(self):
        ctx = build_map_plan()

        response = self.client.get(
            reverse("studying:degree_map"), headers={"accept-language": "en"}
        )

        row = rows_by_entry(response)[ctx["slot"].id]
        self.assertTrue(row["is_slot"])
        self.assertEqual(row["credits"], 3)
        self.assertContains(response, "outstanding")


class DegreeMapActivePlanTests(TestCase):
    def test_map_reflects_the_active_plan(self):
        ctx = build_map_plan()
        other_program = Program.objects.create(
            institution=ctx["institution"],
            name="Bachillerato",
            code="BACH-1",
            pass_mark=70,
            hours_per_credit=3.0,
            grade_scale_max=100,
            term_type="cuatrimestre",
            term_weeks=15,
            terms_per_year=3,
        )
        other_plan = Plan.objects.create(program=other_program, name="BACH-1")
        Block.objects.create(plan=other_plan, name="Z", credits=5)

        settings_obj = AppSettings.load()
        settings_obj.active_plan = other_plan
        settings_obj.save()

        response = self.client.get(reverse("studying:degree_map"))

        names = [b["block"].name for b in response.context["blocks"]]
        self.assertEqual(names, ["Z"])
        # Switching the Plan touched no stored Status.
        self.assertEqual(CourseStatus.objects.count(), 2)

    def test_no_active_plan_renders_an_empty_state(self):
        response = self.client.get(reverse("studying:degree_map"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["blocks"], [])
