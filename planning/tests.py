"""Tests for the availability template, Capacity, and the overload warning (#12).

Capacity and demand are exercised at the function level in `capacity.py`; the
screen and its save path go through the Django test client.
"""

import datetime

from django.test import TestCase
from django.urls import reverse

from curriculum.models import AppSettings, Course, Institution, Plan, Program
from studying.models import CourseStatus, Difficulty, Enrollment, Outcome, Status, Term

from .capacity import capacity_hours, course_targets, demand_hours, overload
from .models import AvailabilityBlock, StudyWindow, Weekday

T = datetime.time


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


def make_term(program):
    return Term.objects.create(
        program=program,
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 6, 15),
    )


def enrol(term, institution, code, credits, difficulty=Difficulty.NORMAL, outcome=Outcome.IN_PROGRESS):
    course = Course.objects.create(
        institution=institution, code=code, name=code, credits=credits
    )
    Enrollment.objects.create(term=term, course=course, outcome=outcome, difficulty=difficulty)
    return course


class CapacityHoursTests(TestCase):
    def test_a_single_window_with_no_blocks_is_its_full_length(self):
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(22, 0))

        self.assertEqual(capacity_hours(), 4.0)

    def test_windows_differ_per_weekday_and_sum_across_the_week(self):
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(22, 0))
        StudyWindow.objects.create(weekday=Weekday.SATURDAY, start=T(8, 0), end=T(14, 30))

        self.assertEqual(capacity_hours(), 4.0 + 6.5)

    def test_a_block_inside_the_window_is_subtracted(self):
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(8, 0), end=T(20, 0))
        AvailabilityBlock.objects.create(
            weekday=Weekday.MONDAY, start=T(9, 0), end=T(17, 0), label="Work"
        )

        self.assertEqual(capacity_hours(), 12.0 - 8.0)

    def test_a_block_is_clipped_to_the_window_edges(self):
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(22, 0))
        AvailabilityBlock.objects.create(
            weekday=Weekday.MONDAY, start=T(16, 0), end=T(19, 0), label="Commute + class"
        )

        # Only 18:00–19:00 overlaps the window.
        self.assertEqual(capacity_hours(), 4.0 - 1.0)

    def test_overlapping_blocks_are_counted_once(self):
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(8, 0), end=T(20, 0))
        AvailabilityBlock.objects.create(
            weekday=Weekday.MONDAY, start=T(9, 0), end=T(13, 0), label="Work"
        )
        AvailabilityBlock.objects.create(
            weekday=Weekday.MONDAY, start=T(12, 0), end=T(15, 0), label="Errand"
        )

        # 09:00–15:00 covered, not 7 hours.
        self.assertEqual(capacity_hours(), 12.0 - 6.0)

    def test_a_block_on_a_weekday_with_no_window_changes_nothing(self):
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(22, 0))
        AvailabilityBlock.objects.create(
            weekday=Weekday.TUESDAY, start=T(9, 0), end=T(17, 0), label="Work"
        )

        self.assertEqual(capacity_hours(), 4.0)

    def test_no_windows_means_zero_capacity(self):
        self.assertEqual(capacity_hours(), 0.0)


class DemandTests(TestCase):
    def test_target_is_credits_times_hours_per_credit_times_difficulty(self):
        institution, program = make_program()
        term = make_term(program)
        normal = enrol(term, institution, "101", credits=4, difficulty=Difficulty.NORMAL)
        hard = enrol(term, institution, "102", credits=3, difficulty=Difficulty.HARD)

        targets = course_targets(term)
        self.assertEqual(targets[normal], 4 * 3.0 * 1.0)
        self.assertEqual(targets[hard], 3 * 3.0 * 1.5)

    def test_only_in_progress_enrollments_count(self):
        institution, program = make_program()
        term = make_term(program)
        enrol(term, institution, "101", credits=4)
        enrol(term, institution, "102", credits=4, outcome=Outcome.PASSED)

        self.assertEqual(demand_hours(term), 12.0)


class OverloadTests(TestCase):
    def _term_with_demand(self):
        institution, program = make_program()
        term = make_term(program)
        enrol(term, institution, "101", credits=4, difficulty=Difficulty.HARD)  # 18h
        return term

    def test_fires_and_carries_both_numbers_when_demand_exceeds_capacity(self):
        term = self._term_with_demand()
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(21, 0))  # 3h

        over = overload(term)
        self.assertTrue(over.overloaded)
        self.assertEqual(over.demand, 18.0)
        self.assertEqual(over.capacity, 3.0)
        self.assertEqual(over.gap, 15.0)

    def test_does_not_fire_when_capacity_covers_demand(self):
        term = self._term_with_demand()
        for day in (Weekday.MONDAY, Weekday.TUESDAY, Weekday.WEDNESDAY):
            StudyWindow.objects.create(weekday=day, start=T(8, 0), end=T(18, 0))  # 30h

        self.assertFalse(overload(term).overloaded)

    def test_no_term_means_no_demand_and_no_warning(self):
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(21, 0))

        over = overload(None)
        self.assertEqual(over.demand, 0.0)
        self.assertFalse(over.overloaded)


class AvailabilityTemplateViewTests(TestCase):
    def _activate_plan(self):
        institution, program = make_program()
        plan = Plan.objects.create(program=program, name="TEST-1")
        settings_obj = AppSettings.load()
        settings_obj.active_plan = plan
        settings_obj.save()
        return institution, program, plan

    def test_get_renders_with_no_active_plan(self):
        response = self.client.get(reverse("planning:availability_template"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["capacity"], 0.0)
        self.assertFalse(response.context["overload"].overloaded)

    def test_get_renders_capacity(self):
        self._activate_plan()
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(22, 0))

        response = self.client.get(reverse("planning:availability_template"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["capacity"], 4.0)

    def test_overload_warning_states_both_numbers(self):
        institution, program, _ = self._activate_plan()
        term = make_term(program)
        enrol(term, institution, "101", credits=4, difficulty=Difficulty.HARD)  # 18h
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(21, 0))  # 3h

        response = self.client.get(
            reverse("planning:availability_template"), headers={"accept-language": "en"}
        )

        self.assertContains(response, "warning")
        over = response.context["overload"]
        self.assertEqual((over.demand, over.capacity), (18.0, 3.0))
        html = response.content.decode()
        self.assertIn("18.0", html)
        self.assertIn("3.0", html)

    def test_post_saves_a_different_window_per_weekday(self):
        self._activate_plan()

        self.client.post(
            reverse("planning:availability_template"),
            {
                "window_start_0": "18:00", "window_end_0": "22:00",
                "window_start_5": "08:00", "window_end_5": "14:30",
            },
        )

        monday = StudyWindow.objects.get(weekday=Weekday.MONDAY)
        saturday = StudyWindow.objects.get(weekday=Weekday.SATURDAY)
        self.assertEqual((monday.start, monday.end), (T(18, 0), T(22, 0)))
        self.assertEqual((saturday.start, saturday.end), (T(8, 0), T(14, 30)))
        self.assertEqual(capacity_hours(), 4.0 + 6.5)

    def test_post_with_a_block_recomputes_capacity(self):
        self._activate_plan()

        self.client.post(
            reverse("planning:availability_template"),
            {
                "window_start_0": "08:00", "window_end_0": "20:00",
                "new_block_weekday": "0", "new_block_start": "09:00",
                "new_block_end": "17:00", "new_block_label": "Work",
            },
        )

        self.assertEqual(AvailabilityBlock.objects.count(), 1)
        self.assertEqual(capacity_hours(), 12.0 - 8.0)

    def test_editing_the_template_touches_no_other_stored_data(self):
        institution, program, _ = self._activate_plan()
        term = make_term(program)
        course = enrol(term, institution, "101", credits=4)
        CourseStatus.objects.create(course=course, status=Status.IN_PROGRESS)
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(8, 0), end=T(20, 0))

        self.client.post(
            reverse("planning:availability_template"),
            {"window_start_0": "18:00", "window_end_0": "22:00"},
        )

        self.assertEqual(capacity_hours(), 4.0)
        self.assertEqual(Term.objects.count(), 1)
        self.assertEqual(Enrollment.objects.get().course, course)
        self.assertEqual(CourseStatus.objects.get().status, Status.IN_PROGRESS)

    def test_a_window_with_only_a_start_is_rejected(self):
        self._activate_plan()

        response = self.client.post(
            reverse("planning:availability_template"),
            {"window_start_0": "18:00"},
        )

        self.assertIn("errors", response.context)
        self.assertFalse(StudyWindow.objects.exists())

    def test_a_window_ending_before_it_starts_is_rejected(self):
        self._activate_plan()

        response = self.client.post(
            reverse("planning:availability_template"),
            {"window_start_0": "22:00", "window_end_0": "18:00"},
        )

        self.assertIn("errors", response.context)
        self.assertFalse(StudyWindow.objects.exists())

    def test_a_block_without_a_label_is_rejected(self):
        self._activate_plan()

        response = self.client.post(
            reverse("planning:availability_template"),
            {
                "window_start_0": "08:00", "window_end_0": "20:00",
                "new_block_weekday": "0", "new_block_start": "09:00",
                "new_block_end": "17:00",
            },
        )

        self.assertIn("errors", response.context)
        self.assertFalse(AvailabilityBlock.objects.exists())

    def test_deleting_an_existing_block_via_checkbox(self):
        self._activate_plan()
        block = AvailabilityBlock.objects.create(
            weekday=Weekday.MONDAY, start=T(9, 0), end=T(17, 0), label="Work"
        )
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(8, 0), end=T(20, 0))

        self.client.post(
            reverse("planning:availability_template"),
            {
                "window_start_0": "08:00", "window_end_0": "20:00",
                f"block_{block.id}_weekday": "0",
                f"block_{block.id}_start": "09:00",
                f"block_{block.id}_end": "17:00",
                f"block_{block.id}_label": "Work",
                f"block_{block.id}_delete": "on",
            },
        )

        self.assertFalse(AvailabilityBlock.objects.exists())
        self.assertEqual(capacity_hours(), 12.0)


class AvailabilityTemplateReflowTests(TestCase):
    """#32: the Targets, Study Windows and Availability Blocks tables reflow
    to stacked, labelled rows on a narrow viewport — a `data-label` on every
    body cell plus a CSS rule, with no JS and no view change.
    """

    def test_every_body_cell_carries_its_column_label(self):
        institution, program = make_program()
        plan = Plan.objects.create(program=program, name="TEST-1")
        settings_obj = AppSettings.load()
        settings_obj.active_plan = plan
        settings_obj.save()
        term = make_term(program)
        enrol(term, institution, "101", credits=4)
        StudyWindow.objects.create(weekday=Weekday.MONDAY, start=T(18, 0), end=T(22, 0))
        AvailabilityBlock.objects.create(
            weekday=Weekday.TUESDAY, start=T(9, 0), end=T(12, 0), label="Work"
        )

        html = self.client.get(
            reverse("planning:availability_template"), headers={"accept-language": "en"}
        ).content.decode()

        for label in (
            "Course",
            "Target (h/week)",
            "Weekday",
            "Start",
            "End",
            "Label",
            "Remove",
        ):
            self.assertIn(f'data-label="{label}"', html)
        self.assertNotIn("<script", html)
