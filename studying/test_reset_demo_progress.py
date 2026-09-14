"""Tests for `reset_demo_progress` (#42, #44)."""

import datetime

from django.core.management import call_command
from django.test import TestCase

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
from planning.models import AvailabilityBlock, StudyWindow, Weekday
from studying.models import CourseStatus, Enrollment, GradedItem, StudyLog, Status, Term


class ResetDemoProgressTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(name="Test U", country="CR")
        self.program = Program.objects.create(
            institution=self.institution,
            name="Test Program",
            code="TEST-1",
            pass_mark=70,
            hours_per_credit=3.0,
            grade_scale_max=100,
            term_type="cuatrimestre",
            term_weeks=15,
            terms_per_year=3,
            item_types=["tarea", "final"],
            default_items=[{"type": "tarea", "weight": 40}, {"type": "final", "weight": 60}],
        )
        self.plan = Plan.objects.create(program=self.program, name="TEST-1")
        self.block = Block.objects.create(plan=self.plan, name="A", credits=7)
        self.course_101 = Course.objects.create(
            institution=self.institution, code="101", name="Intro", credits=4
        )
        self.course_102 = Course.objects.create(
            institution=self.institution, code="102", name="Follow-up", credits=3
        )
        BlockEntry.objects.create(block=self.block, course=self.course_101, credits=4)
        BlockEntry.objects.create(block=self.block, course=self.course_102, credits=3)
        Prerequisite.objects.create(
            plan=self.plan, course=self.course_102, requires_course=self.course_101
        )
        self.settings = AppSettings.load()
        self.settings.active_plan = self.plan
        self.settings.save()

    def _seed_progress(self):
        CourseStatus.objects.create(course=self.course_101, status=Status.PASSED)
        term = Term.objects.create(
            program=self.program,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 4, 1),
        )
        enrollment = Enrollment.objects.create(term=term, course=self.course_102)
        GradedItem.objects.create(enrollment=enrollment, type="tarea", weight=40)
        StudyLog.objects.create(enrollment=enrollment, hours=2.5)
        StudyWindow.objects.create(
            weekday=Weekday.MONDAY, start=datetime.time(9, 0), end=datetime.time(12, 0)
        )
        AvailabilityBlock.objects.create(
            weekday=Weekday.MONDAY,
            start=datetime.time(9, 0),
            end=datetime.time(10, 0),
            label="Work",
        )

    def test_clears_all_tracked_progress(self):
        self._seed_progress()

        call_command("reset_demo_progress")

        self.assertFalse(CourseStatus.objects.exists())
        self.assertFalse(Term.objects.exists())
        self.assertFalse(Enrollment.objects.exists())
        self.assertFalse(GradedItem.objects.exists())
        self.assertFalse(StudyLog.objects.exists())
        self.assertFalse(AvailabilityBlock.objects.exists())
        self.assertFalse(StudyWindow.objects.exists())

    def test_leaves_curriculum_and_active_plan_untouched(self):
        self._seed_progress()

        call_command("reset_demo_progress")

        self.assertTrue(Institution.objects.filter(pk=self.institution.pk).exists())
        self.assertTrue(Program.objects.filter(pk=self.program.pk).exists())
        self.assertTrue(Plan.objects.filter(pk=self.plan.pk).exists())
        self.assertTrue(Block.objects.filter(pk=self.block.pk).exists())
        self.assertEqual(BlockEntry.objects.count(), 2)
        self.assertEqual(Course.objects.count(), 2)
        self.assertEqual(Prerequisite.objects.count(), 1)
        self.assertEqual(AppSettings.load().active_plan, self.plan)

    def test_rerun_on_empty_progress_does_not_raise(self):
        call_command("reset_demo_progress")

        call_command("reset_demo_progress")

        self.assertFalse(Term.objects.exists())
