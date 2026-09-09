"""The dashboard's Recommendation banner (#15, scope.md §5 screen 2), through
the Django test client. Deliberately thin — the arithmetic is seam 1's; here
we only check the banner names a Course, its committed hours and its reason,
and that it labels a stale ranking rather than hiding it.
"""

import datetime
import re

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from curriculum.models import AppSettings, Course, Institution, Plan, Program
from studying.models import Difficulty, Enrollment, GradedItem, Outcome, StudyLog, Term

from .models import StudyWindow

T = datetime.time
EN = {"accept-language": "en"}


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
    return Enrollment.objects.create(
        term=term, course=course, outcome=Outcome.IN_PROGRESS, difficulty=difficulty
    )


def a_study_window_for_today():
    StudyWindow.objects.create(
        weekday=timezone.localdate().weekday(), start=T(0, 0), end=T(23, 59)
    )


class EmptyStateTests(TestCase):
    def test_no_active_plan_renders_an_empty_state(self):
        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["term"])
        self.assertContains(response, "No Term is open")

    def test_a_term_with_no_in_progress_courses_says_nothing_to_rank(self):
        _, program, _ = activate_plan()
        open_term(program)

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        self.assertIsNone(response.context["recommendation"])
        self.assertContains(response, "Nothing to rank yet")


class BannerTests(TestCase):
    def test_names_the_winning_course_its_committed_hours_and_its_reason(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        enrolment = enrol(term, institution, "AAA")  # 12h Ration
        StudyLog.objects.create(
            enrollment=enrolment, hours=10.0, studied_on=timezone.localdate()
        )
        GradedItem.objects.create(
            enrollment=enrolment,
            type="parcial",
            weight=40,
            due_at=timezone.localdate() + datetime.timedelta(days=4),
        )

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        recommendation = response.context["recommendation"]
        self.assertEqual(recommendation.code, "AAA")
        self.assertAlmostEqual(recommendation.committed_hours, 2.0)  # 12 Ration − 10 logged
        self.assertContains(response, "Course AAA")
        self.assertContains(response, "TONIGHT")
        self.assertContains(response, "Course AAA · 2h")
        self.assertContains(response, "parcial")  # the reason names the pressing item

    def test_an_item_in_the_override_window_wins_the_banner(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        behind = enrol(term, institution, "BEHIND")
        due_soon = enrol(term, institution, "DUESOON")
        StudyLog.objects.create(
            enrollment=due_soon, hours=12.0, studied_on=timezone.localdate()
        )
        GradedItem.objects.create(
            enrollment=due_soon,
            type="parcial",
            weight=40,
            due_at=timezone.localdate() + datetime.timedelta(days=1),
        )

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        self.assertEqual(response.context["recommendation"].code, "DUESOON")
        self.assertEqual(response.context["recommendation"].tier, 1)
        self.assertContains(response, "override")


class StalenessTests(TestCase):
    def test_an_old_last_log_flags_the_banner_but_still_recommends(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        enrolment = enrol(term, institution, "AAA")
        log = StudyLog.objects.create(
            enrollment=enrolment, hours=3.0, studied_on=timezone.localdate()
        )
        StudyLog.objects.filter(pk=log.pk).update(
            recorded_at=timezone.now() - datetime.timedelta(days=10)
        )

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        self.assertTrue(response.context["ranking"].stale)
        self.assertIsNotNone(response.context["recommendation"])
        self.assertContains(response, "No logs since")

    def test_a_term_with_no_logs_yet_is_flagged(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        enrol(term, institution, "AAA")

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        self.assertTrue(response.context["ranking"].stale)
        self.assertContains(response, "Nothing logged yet")


class CourseCardTests(TestCase):
    def test_cards_render_in_ranks_order_with_the_banner_course_first(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        today = timezone.localdate()

        behind = enrol(term, institution, "BEHIND")  # 0 logged → biggest deficit
        on_ration = enrol(term, institution, "ONRATION")
        StudyLog.objects.create(enrollment=on_ration, hours=12.0, studied_on=today)
        ahead = enrol(term, institution, "AHEAD")
        StudyLog.objects.create(enrollment=ahead, hours=40.0, studied_on=today)

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        ranking_order = [c.code for c in response.context["ranking"].courses]
        card_order = [c["course"].code for c in response.context["cards"]]
        self.assertEqual(card_order, ranking_order)
        self.assertEqual(card_order[0], response.context["recommendation"].code)
        self.assertEqual(card_order[0], "BEHIND")

    def test_a_card_carries_a_ration_bar_a_course_link_and_a_reason(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        enrolment = enrol(term, institution, "AAA")
        StudyLog.objects.create(
            enrollment=enrolment, hours=2.0, studied_on=timezone.localdate()
        )

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        card = response.context["cards"][0]
        self.assertEqual(card["course_id"], enrolment.course_id)
        self.assertEqual(set(card["bar"]), {"█", "░"})
        self.assertTrue(card["reason_line"])
        self.assertContains(response, "2/12h")  # logged vs Ration
        self.assertContains(
            response,
            reverse("studying:course_detail", args=[enrolment.course_id]),
        )

    def test_the_override_course_shows_no_score_on_its_card(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        due_soon = enrol(term, institution, "DUESOON")
        StudyLog.objects.create(
            enrollment=due_soon, hours=12.0, studied_on=timezone.localdate()
        )
        GradedItem.objects.create(
            enrollment=due_soon,
            type="parcial",
            weight=40,
            due_at=timezone.localdate() + datetime.timedelta(days=1),
        )

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        self.assertIsNone(response.context["cards"][0]["course"].score)


class RationBarTests(TestCase):
    """#31: the dashboard's ASCII ration bar (`██░░░░░░░░`) is now a CSS
    element — a track plus a fill whose inline width is `hours_logged_7d /
    ration` as a percentage, held at 100% when a Course is over its Ration,
    and carrying a `data-band` keyed to how far behind the Course is.
    """

    def _dashboard_for(self, logged):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        enrolment = enrol(term, institution, "AAA")  # 12h Ration
        if logged:
            StudyLog.objects.create(
                enrollment=enrolment, hours=logged, studied_on=timezone.localdate()
            )
        return self.client.get(reverse("planning:dashboard"), headers=EN)

    def _fill_widths(self, response):
        # Every `width: N%` in the page is a ration-bar fill (the viewport meta
        # is `width=device-width`), so this is the set of rendered fill widths.
        return [int(n) for n in re.findall(r"width: (\d+)%", response.content.decode())]

    def test_no_hours_logged_renders_a_zero_width_fill(self):
        response = self._dashboard_for(0)

        self.assertEqual(self._fill_widths(response), [0])

    def test_half_the_ration_logged_renders_a_half_width_fill(self):
        response = self._dashboard_for(6.0)  # 6 of a 12h Ration

        self.assertEqual(self._fill_widths(response), [50])

    def test_over_the_ration_never_renders_a_fill_past_one_hundred_percent(self):
        response = self._dashboard_for(20.0)  # 20 logged against a 12h Ration

        widths = self._fill_widths(response)
        self.assertTrue(widths, "expected a ration-bar fill on the card")
        self.assertLessEqual(max(widths), 100)

    def test_a_course_not_behind_its_ration_is_on_track(self):
        self.assertContains(self._dashboard_for(20.0), 'data-band="on-track"')

    def test_a_course_somewhat_behind_its_ration_is_amber(self):
        self.assertContains(self._dashboard_for(8.0), 'data-band="amber"')  # 4h of 12 behind

    def test_a_course_far_behind_its_ration_is_red(self):
        self.assertContains(self._dashboard_for(0), 'data-band="red"')  # a full Ration behind


class StreakBannerTests(TestCase):
    def test_the_banner_shows_the_current_streak(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        enrolment = enrol(term, institution, "AAA")
        StudyLog.objects.create(
            enrollment=enrolment, hours=2.0, studied_on=timezone.localdate()
        )

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        self.assertEqual(response.context["streak"], 1)
        self.assertContains(response, "Streak: 1 day")

    def test_the_left_off_note_from_the_last_session_is_handed_back(self):
        institution, program, _ = activate_plan()
        term = open_term(program)
        a_study_window_for_today()
        enrolment = enrol(term, institution, "AAA")
        StudyLog.objects.create(
            enrollment=enrolment,
            hours=1.5,
            studied_on=timezone.localdate(),
            note="falta el diagrama ER",
        )

        response = self.client.get(reverse("planning:dashboard"), headers=EN)

        self.assertContains(response, "falta el diagrama ER")
