"""Tests for CourseStatus, curriculum queries, and AppSettings (#9)."""

from django.test import TestCase

from curriculum.models import AppSettings, Course, Institution, Plan, Prerequisite, Program

from .models import CourseStatus, Status, status_for_course
from .queries import credits_earned, is_unlocked


def make_program_and_plan():
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
    return institution, plan


def make_course(institution, code, credits=4, name=None):
    return Course.objects.create(institution=institution, code=code, name=name or code, credits=credits)


class CourseStatusTests(TestCase):
    def test_defaults_to_pending_with_no_row(self):
        institution, _ = make_program_and_plan()
        course = make_course(institution, "101")

        self.assertEqual(status_for_course(course), Status.PENDING)

    def test_explicit_status_overrides_default(self):
        institution, _ = make_program_and_plan()
        course = make_course(institution, "101")
        CourseStatus.objects.create(course=course, status=Status.PASSED)

        self.assertEqual(status_for_course(course), Status.PASSED)


class AppSettingsTests(TestCase):
    def test_singleton_holds_active_plan(self):
        _, plan = make_program_and_plan()

        settings_obj = AppSettings.load()
        settings_obj.active_plan = plan
        settings_obj.save()

        reloaded = AppSettings.load()
        self.assertEqual(reloaded.active_plan, plan)
        self.assertEqual(AppSettings.objects.count(), 1)


class IsUnlockedTests(TestCase):
    def test_unlocked_when_every_prerequisite_satisfied(self):
        institution, plan = make_program_and_plan()
        req = make_course(institution, "101")
        target = make_course(institution, "102")
        Prerequisite.objects.create(plan=plan, course=target, requires_course=req)
        CourseStatus.objects.create(course=req, status=Status.PASSED)

        self.assertTrue(is_unlocked(target, plan))

    def test_locked_when_one_of_several_prerequisites_outstanding(self):
        """The conjunction case, exercised against 00831's three-requirement shape."""
        institution, plan = make_program_and_plan()
        req_a = make_course(institution, "03071")
        req_b = make_course(institution, "03069")
        req_c = make_course(institution, "03072")
        target = make_course(institution, "00831")
        for req in (req_a, req_b, req_c):
            Prerequisite.objects.create(plan=plan, course=target, requires_course=req)
        CourseStatus.objects.create(course=req_a, status=Status.PASSED)
        CourseStatus.objects.create(course=req_b, status=Status.PASSED)
        # req_c left pending — one outstanding requirement must lock the course.

        self.assertFalse(is_unlocked(target, plan))

    def test_transferred_satisfies_prerequisite_like_passed(self):
        institution, plan = make_program_and_plan()
        req = make_course(institution, "101")
        target = make_course(institution, "102")
        Prerequisite.objects.create(plan=plan, course=target, requires_course=req)
        CourseStatus.objects.create(course=req, status=Status.TRANSFERRED)

        self.assertTrue(is_unlocked(target, plan))

    def test_in_progress_failed_and_pending_do_not_satisfy(self):
        institution, plan = make_program_and_plan()
        target = make_course(institution, "102")
        for status in (Status.IN_PROGRESS, Status.FAILED, Status.PENDING):
            req = make_course(institution, f"req-{status}")
            Prerequisite.objects.create(plan=plan, course=target, requires_course=req)
            CourseStatus.objects.create(course=req, status=status)

            self.assertFalse(is_unlocked(target, plan))

    def test_unlocking_is_plan_scoped(self):
        institution, plan_a = make_program_and_plan()
        program_b = Program.objects.create(
            institution=institution,
            name="Program B",
            code="TEST-2",
            pass_mark=70,
            hours_per_credit=3.0,
            grade_scale_max=100,
            term_type="cuatrimestre",
            term_weeks=15,
            terms_per_year=3,
        )
        plan_b = Plan.objects.create(program=program_b, name="TEST-2")

        req = make_course(institution, "101")
        target = make_course(institution, "102")
        # Only Plan A requires it; Plan B has no such prerequisite edge, so
        # target is trivially unlocked there.
        Prerequisite.objects.create(plan=plan_a, course=target, requires_course=req)
        # req left pending: locked under Plan A.

        self.assertFalse(is_unlocked(target, plan_a))
        self.assertTrue(is_unlocked(target, plan_b))


class CreditsEarnedTests(TestCase):
    def test_counts_only_passed_or_transferred_courses(self):
        institution, plan = make_program_and_plan()
        from curriculum.models import Block, BlockEntry

        block = Block.objects.create(plan=plan, name="A", credits=11)
        passed = make_course(institution, "101", credits=4)
        transferred = make_course(institution, "102", credits=3)
        pending = make_course(institution, "103", credits=4)
        BlockEntry.objects.create(block=block, course=passed, credits=4)
        BlockEntry.objects.create(block=block, course=transferred, credits=3)
        BlockEntry.objects.create(block=block, course=pending, credits=4)
        CourseStatus.objects.create(course=passed, status=Status.PASSED)
        CourseStatus.objects.create(course=transferred, status=Status.TRANSFERRED)

        self.assertEqual(credits_earned(plan), 7)

    def test_unfilled_slot_contributes_nothing_to_credits_earned(self):
        institution, plan = make_program_and_plan()
        from curriculum.models import Block, BlockEntry

        block = Block.objects.create(plan=plan, name="A", credits=3)
        BlockEntry.objects.create(
            block=block, course=None, credits=3, slot_label="humanidades", slot_index=1
        )

        self.assertEqual(credits_earned(plan), 0)
