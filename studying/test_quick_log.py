"""Quick log (#16, scope.md §5 screen 3) through the Django test client:
create a Study Log in one tap from the banner's Course, backdate the date
studied, and edit or delete a past session — each landing in the next ranking.
"""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from curriculum.models import AppSettings, Course, Institution, Plan, Program
from planning.models import StudyWindow

from .models import Difficulty, Enrollment, Outcome, StudyLog, Term

EN = {"accept-language": "en"}


def a_study_window_for_today():
    """A wide Study Window today, so Capacity covers demand and every Ration
    equals its Target — keeps the arithmetic in these tests simple.
    """

    StudyWindow.objects.create(
        weekday=timezone.localdate().weekday(),
        start=datetime.time(0, 0),
        end=datetime.time(23, 59),
    )


def activate_plan():
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
    settings_obj = AppSettings.load()
    settings_obj.active_plan = plan
    settings_obj.save()
    return institution, program, plan


def open_term(program):
    return Term.objects.create(
        program=program,
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 12, 15),
    )


def enrol(term, institution, code, credits=4, difficulty=Difficulty.NORMAL):
    course = Course.objects.create(
        institution=institution, code=code, name=f"Course {code}", credits=credits
    )
    enrollment = Enrollment.objects.create(
        term=term, course=course, outcome=Outcome.IN_PROGRESS, difficulty=difficulty
    )
    return course, enrollment


class EmptyStateTests(TestCase):
    def test_no_term_open_shows_a_friendly_message_and_no_form(self):
        response = self.client.get(reverse("studying:quick_log"), headers=EN)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["term"])
        self.assertContains(response, "No Term is open")
        self.assertNotContains(response, "new_log_hours")


class CreateTests(TestCase):
    def setUp(self):
        self.institution, self.program, _ = activate_plan()
        self.term = open_term(self.program)
        self.course, self.enrollment = enrol(self.term, self.institution, "AAA")

    def test_logs_hours_a_note_and_both_dates(self):
        today = timezone.localdate()

        response = self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(self.course.id),
                "new_log_hours": "2.5",
                "new_log_studied_on": today.isoformat(),
                "new_log_note": "terminé 3FN, falta el diagrama ER",
            },
        )

        self.assertRedirects(response, reverse("studying:quick_log"))
        log = StudyLog.objects.get()
        self.assertEqual(log.enrollment, self.enrollment)
        self.assertEqual(log.hours, 2.5)
        self.assertEqual(log.note, "terminé 3FN, falta el diagrama ER")
        self.assertEqual(log.studied_on, today)
        self.assertEqual(timezone.localtime(log.recorded_at).date(), today)

    def test_the_note_is_optional(self):
        self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(self.course.id),
                "new_log_hours": "1",
                "new_log_studied_on": timezone.localdate().isoformat(),
            },
        )

        self.assertEqual(StudyLog.objects.get().note, "")

    def test_studied_on_defaults_to_today_when_left_blank(self):
        self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(self.course.id),
                "new_log_hours": "1",
                "new_log_studied_on": "",
            },
        )

        self.assertEqual(StudyLog.objects.get().studied_on, timezone.localdate())

    def test_studied_on_is_editable_to_a_past_date(self):
        studied = timezone.localdate() - datetime.timedelta(days=3)

        self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(self.course.id),
                "new_log_hours": "1",
                "new_log_studied_on": studied.isoformat(),
            },
        )

        log = StudyLog.objects.get()
        self.assertEqual(log.studied_on, studied)
        # recorded_at still lands today — the two dates do different jobs.
        self.assertEqual(timezone.localtime(log.recorded_at).date(), timezone.localdate())

    def test_zero_or_negative_hours_are_rejected_and_nothing_is_saved(self):
        response = self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(self.course.id),
                "new_log_hours": "0",
                "new_log_studied_on": timezone.localdate().isoformat(),
            },
            headers=EN,
        )

        self.assertIn("errors", response.context)
        self.assertFalse(StudyLog.objects.exists())

    def test_a_bad_date_is_rejected(self):
        response = self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(self.course.id),
                "new_log_hours": "2",
                "new_log_studied_on": "not-a-date",
            },
            headers=EN,
        )

        self.assertIn("errors", response.context)
        self.assertFalse(StudyLog.objects.exists())


class FromTheBannerTests(TestCase):
    def test_the_recommended_course_arrives_pre_selected_from_the_query_string(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        course, _ = enrol(term, institution, "AAA")

        response = self.client.get(
            reverse("studying:quick_log"), {"course": str(course.id)}, headers=EN
        )

        self.assertEqual(response.context["preselected_course_id"], str(course.id))
        self.assertContains(
            response, f'<option value="{course.id}" selected>', html=False
        )

    def test_logging_the_pre_selected_course_needs_no_further_choice(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        course, enrollment = enrol(term, institution, "AAA")

        # Exactly what the pre-filled form submits — the course value is the
        # one the banner put there, no picker step.
        self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(course.id),
                "new_log_hours": "3",
                "new_log_studied_on": timezone.localdate().isoformat(),
            },
        )

        self.assertEqual(StudyLog.objects.get().enrollment, enrollment)


class BackdatingAndTheRankingTests(TestCase):
    """AC: a Study Log backdated inside the rolling window reduces that
    Course's Hours Behind; one backdated outside it does not.
    """

    def _card(self, code):
        response = self.client.get(reverse("planning:dashboard"), headers=EN)
        return {c["course"].code: c["course"] for c in response.context["cards"]}[code]

    def setUp(self):
        self.institution, self.program, _ = activate_plan()
        self.term = open_term(self.program)
        a_study_window_for_today()
        self.course, self.enrollment = enrol(self.term, self.institution, "AAA")

    def test_a_backdate_inside_the_window_reduces_hours_behind(self):
        before = self._card("AAA").hours_behind
        self.assertGreater(before, 0)

        studied = timezone.localdate() - datetime.timedelta(days=3)
        self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(self.course.id),
                "new_log_hours": "4",
                "new_log_studied_on": studied.isoformat(),
            },
        )

        self.assertAlmostEqual(self._card("AAA").hours_behind, before - 4)

    def test_a_backdate_outside_the_window_does_not(self):
        before = self._card("AAA").hours_behind

        studied = timezone.localdate() - datetime.timedelta(days=30)
        self.client.post(
            reverse("studying:quick_log"),
            {
                "new_log_course": str(self.course.id),
                "new_log_hours": "4",
                "new_log_studied_on": studied.isoformat(),
            },
        )

        self.assertAlmostEqual(self._card("AAA").hours_behind, before)


class EditAndDeleteTests(TestCase):
    """AC: editing or deleting a Study Log changes the ranking on the next
    load — nothing on the dashboard is cached.
    """

    def _behind(self, code):
        response = self.client.get(reverse("planning:dashboard"), headers=EN)
        return {c["course"].code: c["course"] for c in response.context["cards"]}[code].hours_behind

    def setUp(self):
        self.institution, self.program, _ = activate_plan()
        self.term = open_term(self.program)
        a_study_window_for_today()
        self.course, self.enrollment = enrol(self.term, self.institution, "AAA")
        self.log = StudyLog.objects.create(
            enrollment=self.enrollment, hours=3.0, studied_on=timezone.localdate()
        )

    def test_editing_the_hours_moves_hours_behind_on_the_next_load(self):
        before = self._behind("AAA")

        self.client.post(
            reverse("studying:quick_log"),
            {
                f"log_{self.log.id}_hours": "9",
                f"log_{self.log.id}_studied_on": timezone.localdate().isoformat(),
                f"log_{self.log.id}_note": "",
            },
        )

        self.log.refresh_from_db()
        self.assertEqual(self.log.hours, 9.0)
        self.assertAlmostEqual(self._behind("AAA"), before - 6)

    def test_deleting_the_log_restores_the_full_deficit(self):
        with_log = self._behind("AAA")

        self.client.post(
            reverse("studying:quick_log"),
            {
                f"log_{self.log.id}_hours": "3",
                f"log_{self.log.id}_studied_on": timezone.localdate().isoformat(),
                f"log_{self.log.id}_delete": "on",
            },
        )

        self.assertFalse(StudyLog.objects.exists())
        self.assertAlmostEqual(self._behind("AAA"), with_log + 3)

    def test_editing_the_date_out_of_the_window_drops_the_hours(self):
        before = self._behind("AAA")

        self.client.post(
            reverse("studying:quick_log"),
            {
                f"log_{self.log.id}_hours": "3",
                f"log_{self.log.id}_studied_on": (
                    timezone.localdate() - datetime.timedelta(days=20)
                ).isoformat(),
                f"log_{self.log.id}_note": "",
            },
        )

        self.assertAlmostEqual(self._behind("AAA"), before + 3)

    def test_recorded_at_survives_an_edit(self):
        original = StudyLog.objects.get(pk=self.log.pk).recorded_at

        self.client.post(
            reverse("studying:quick_log"),
            {
                f"log_{self.log.id}_hours": "5",
                f"log_{self.log.id}_studied_on": timezone.localdate().isoformat(),
                f"log_{self.log.id}_note": "changed my mind",
            },
        )

        self.log.refresh_from_db()
        self.assertEqual(self.log.recorded_at, original)
        self.assertEqual(self.log.note, "changed my mind")
