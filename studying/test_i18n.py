"""The bilingual completion pass (#19, ADR-0013, scope.md decision 18).

Four things this locks in:

- the language switcher persists a cookie-based choice with no account;
- every screen renders under both `es` and `en`;
- Status and Outcome render translated labels while their stored values stay
  the English code enum (ADR-0001);
- `rank()`'s and `forecast()`'s structured output renders a sentence per
  locale (ADR-0013) — and curriculum / roadmap data never passes through a
  catalog, which is the regression the last test exists for.

`setUpModule` compiles the catalogs first: the `.mo` files are a build
artifact (git-ignored), so the suite can't assume they are already on disk.
"""

import datetime

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from curriculum.models import (
    AppSettings,
    Block,
    BlockEntry,
    Course,
    Institution,
    Plan,
    Program,
)
from planning.ranking import RULE_HOURS_BEHIND, Reason
from planning.reasons import render_reason
from reference.models import CoverageLink, RoadmapEntry

from .models import (
    CourseStatus,
    Difficulty,
    Enrollment,
    GradedItem,
    Outcome,
    Status,
    Term,
)


def setUpModule():
    call_command(
        "compilemessages",
        locale=["es", "en"],
        ignore=[".venv", "*/site-packages/*"],
        verbosity=0,
    )


def make_plan():
    institution = Institution.objects.create(name="UNED", country="CR")
    program = Program.objects.create(
        institution=institution,
        name="Diplomado",
        code="IIC-2026",
        pass_mark=70,
        hours_per_credit=3.0,
        grade_scale_max=100,
        term_type="cuatrimestre",
        term_weeks=15,
        terms_per_year=3,
        item_types=["tarea", "parcial"],
    )
    plan = Plan.objects.create(program=program, name="IIC-2026")
    settings_obj = AppSettings.load()
    settings_obj.active_plan = plan
    settings_obj.save()
    return institution, program, plan


class LanguageSwitcherTests(TestCase):
    def test_switcher_persists_the_choice_across_later_visits(self):
        make_plan()

        # Default: settings.LANGUAGE_CODE is "es".
        self.assertEqual(self.client.get(reverse("planning:dashboard")).context["LANGUAGE_CODE"], "es")

        response = self.client.post(
            reverse("set_language"),
            {"language": "en", "next": reverse("planning:dashboard")},
        )
        self.assertRedirects(response, reverse("planning:dashboard"))

        # A fresh request carrying only the cookie the switcher set — no
        # Accept-Language, no query string — still comes back in English.
        later = self.client.get(reverse("studying:onboarding"))
        self.assertEqual(later.context["LANGUAGE_CODE"], "en")
        self.assertContains(later, 'lang="en"')

    def test_switcher_offers_both_configured_languages(self):
        make_plan()
        response = self.client.get(reverse("planning:dashboard"))
        self.assertContains(response, reverse("set_language"))
        self.assertContains(response, 'value="es"')
        self.assertContains(response, 'value="en"')


class StatusAndOutcomeLabelsTests(TestCase):
    """ADR-0001: the value is a fixed English code; only the label moves."""

    def test_status_labels_translate_but_values_do_not(self):
        for status in Status:
            with translation.override("en"):
                en_label = str(status.label)
            with translation.override("es"):
                es_label = str(status.label)
            self.assertNotEqual(
                en_label, es_label, f"{status.name} has no Spanish label"
            )
            # The stored value is untouched by either locale.
            self.assertEqual(status.value, status.value.lower())
            self.assertRegex(status.value, r"^[a-z_]+$")

    def test_outcome_labels_translate_but_values_do_not(self):
        for outcome in Outcome:
            with translation.override("en"):
                en_label = str(outcome.label)
            with translation.override("es"):
                es_label = str(outcome.label)
            self.assertNotEqual(en_label, es_label)
            self.assertRegex(outcome.value, r"^[a-z_]+$")

    def test_degree_map_renders_the_spanish_standing_with_the_english_value_stored(self):
        institution, program, plan = make_plan()
        block = Block.objects.create(plan=plan, name="A", credits=3)
        course = Course.objects.create(
            institution=institution, code="03304", name="Álgebra Lineal", credits=3
        )
        BlockEntry.objects.create(block=block, course=course, credits=3)
        CourseStatus.objects.create(course=course, status=Status.PASSED)

        with translation.override("es"):
            spanish_label = str(Status.PASSED.label)
        response = self.client.post(
            reverse("set_language"),
            {"language": "es", "next": reverse("studying:degree_map")},
            follow=True,
        )
        self.assertContains(response, spanish_label)
        self.assertEqual(CourseStatus.objects.get(course=course).status, "passed")


class ReasonRenderingPerLocaleTests(TestCase):
    def test_hours_behind_reason_differs_by_locale(self):
        reason = Reason(rule=RULE_HOURS_BEHIND, hours_behind=12.0)
        with translation.override("en"):
            en_line = render_reason(reason)
        with translation.override("es"):
            es_line = render_reason(reason)

        self.assertIn("12.0", en_line)
        self.assertIn("12.0", es_line)  # the number is data, not translated
        self.assertNotEqual(en_line, es_line)


class DomainDataIsNeverTranslatedTests(TestCase):
    """The regression ADR-0013 asks for: a Course name, a código, and a
    Roadmap Entry's university name render identically under both locales —
    they are facts about the real curriculum, not UI chrome.
    """

    def test_course_name_codigo_and_university_render_identically_in_es_and_en(self):
        institution, program, plan = make_plan()
        block = Block.objects.create(plan=plan, name="A", credits=3)
        course = Course.objects.create(
            institution=institution,
            code="03304",
            name="Introducción a la Programación",
            credits=3,
        )
        BlockEntry.objects.create(block=block, course=course, credits=3)
        entry = RoadmapEntry.objects.create(
            university="Massachusetts Institute of Technology",
            category="Computer Science",
            code="6.006",
            name="Introduction to Algorithms",
        )
        CoverageLink.objects.create(entry=entry, position=0, course=course, note="")

        def rendered(url, language):
            self.client.post(reverse("set_language"), {"language": language, "next": url})
            return self.client.get(url).content.decode()

        expected = {
            reverse("studying:degree_map"): ["03304", "Introducción a la Programación"],
            reverse("reference:roadmap"): [
                "03304",
                "Introducción a la Programación",
                "Massachusetts Institute of Technology",
                "6.006",
                "Introduction to Algorithms",
            ],
        }
        for url, tokens in expected.items():
            es_html = rendered(url, "es")
            en_html = rendered(url, "en")
            self.assertNotEqual(es_html, en_html, f"{url} did not change with locale")
            for token in tokens:
                self.assertIn(token, es_html, f"{token!r} missing from es {url}")
                self.assertIn(token, en_html, f"{token!r} missing from en {url}")


class EveryScreenRendersInBothLocalesTests(TestCase):
    def setUp(self):
        self.institution, self.program, self.plan = make_plan()
        block = Block.objects.create(plan=self.plan, name="A", credits=6)
        self.course = Course.objects.create(
            institution=self.institution, code="03304", name="Cálculo", credits=3
        )
        BlockEntry.objects.create(block=block, course=self.course, credits=3)
        BlockEntry.objects.create(
            block=block, course=None, credits=3, slot_label="humanidades", slot_index=1
        )
        term = Term.objects.create(
            program=self.program,
            start_date=datetime.date(2026, 1, 5),
            end_date=datetime.date(2026, 4, 20),
        )
        enrollment = Enrollment.objects.create(
            term=term, course=self.course, difficulty=Difficulty.NORMAL
        )
        GradedItem.objects.create(
            enrollment=enrollment, type="parcial", weight=100, due_at=datetime.date(2026, 3, 1)
        )

    def test_all_screens_return_200_in_each_locale(self):
        urls = [
            reverse("planning:dashboard"),
            reverse("studying:quick_log"),
            reverse("studying:onboarding"),
            reverse("studying:cuatrimestre_setup"),
            reverse("studying:degree_map"),
            reverse("planning:availability_template"),
            reverse("reference:roadmap"),
            reverse("studying:course_detail", args=[self.course.id]),
        ]
        for language in ("es", "en"):
            self.client.post(reverse("set_language"), {"language": language, "next": "/"})
            for url in urls:
                with self.subTest(language=language, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)
