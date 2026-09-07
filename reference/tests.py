"""Tests for the roadmap import and the reference view (#18, ADR-0006, ADR-0012).

Assertions are against imported rows, the rolled-up coverage, and rendered
view state — not how any of it is phrased internally.
"""

import tempfile

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from curriculum.models import AppSettings, Course, Institution, Plan, Program
from studying.models import CourseStatus, Status

from .models import Coverage, CoverageLink, RoadmapEntry


def write_yaml(data):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
    yaml.safe_dump(data, f, allow_unicode=True)
    f.close()
    return f.name


def make_catalog():
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
    )
    plan = Plan.objects.create(program=program, name="IIC-2026")
    AppSettings.objects.update_or_create(pk=1, defaults={"active_plan": plan})
    Course.objects.create(institution=institution, code="03071", name="Lógica para Computación", credits=3)
    Course.objects.create(institution=institution, code="00831", name="Introducción a la Programación", credits=4)
    return institution, plan


HARVARD = {
    "university": "Harvard",
    "entries": [
        {
            "code": "CS 50",
            "name": "Introduction to Computer Science",
            "category": "Programming",
            "links": [
                {"course": "03071", "note": "logic half"},
                {"course": "00831", "note": "programming half"},
            ],
        },
        {
            "code": "MATH 21a",
            "name": "Multivariable Calculus",
            "category": "Mathematics",
            "links": [
                {"status": "transferred", "note": "Completado — título en Física"},
            ],
        },
    ],
}


class LoadroadmapTests(TestCase):
    def setUp(self):
        make_catalog()

    def test_entry_imports_with_two_links_to_two_different_courses(self):
        call_command("loadroadmap", write_yaml(HARVARD))

        entry = RoadmapEntry.objects.get(university="Harvard", code="CS 50")
        linked_codes = sorted(link.course.code for link in entry.links.all())
        self.assertEqual(linked_codes, ["00831", "03071"])

    def test_link_with_no_course_keeps_its_imported_status(self):
        call_command("loadroadmap", write_yaml(HARVARD))

        entry = RoadmapEntry.objects.get(code="MATH 21a")
        link = entry.links.get()
        self.assertIsNone(link.course)
        self.assertEqual(link.imported_status, Status.TRANSFERRED)
        self.assertEqual(link.effective_status(), Status.TRANSFERRED)

    def test_rerun_on_unchanged_file_changes_nothing(self):
        path = write_yaml(HARVARD)
        call_command("loadroadmap", path)
        call_command("loadroadmap", path)

        self.assertEqual(RoadmapEntry.objects.count(), 2)
        self.assertEqual(CoverageLink.objects.count(), 3)

    def test_second_import_for_same_university_matches_by_codigo(self):
        call_command("loadroadmap", write_yaml(HARVARD))

        revised = {
            "university": "Harvard",
            "entries": [
                {
                    "code": "CS 50",
                    "name": "Intro to CS (renamed)",
                    "category": "Programming",
                    "links": [{"course": "03071", "note": "logic half"}],
                }
            ],
        }
        call_command("loadroadmap", write_yaml(revised))

        entry = RoadmapEntry.objects.get(university="Harvard", code="CS 50")
        self.assertEqual(RoadmapEntry.objects.filter(code="CS 50").count(), 1)
        self.assertEqual(entry.name, "Intro to CS (renamed)")
        self.assertEqual(entry.links.count(), 1)

    def test_codigo_absent_from_catalog_fails_the_import_naming_it(self):
        bad = {
            "university": "Harvard",
            "entries": [
                {
                    "code": "CS 50",
                    "name": "Intro",
                    "category": "Programming",
                    "links": [{"course": "99999", "note": "nope"}],
                }
            ],
        }
        with self.assertRaises(CommandError) as ctx:
            call_command("loadroadmap", write_yaml(bad))

        self.assertIn("99999", str(ctx.exception))
        self.assertFalse(RoadmapEntry.objects.exists())

    def test_no_active_plan_fails_loudly(self):
        AppSettings.objects.update_or_create(pk=1, defaults={"active_plan": None})
        with self.assertRaises(CommandError):
            call_command("loadroadmap", write_yaml(HARVARD))

    def test_shipped_harvard_fixture_loads(self):
        from django.conf import settings

        call_command("loadroadmap", str(settings.BASE_DIR / "roadmaps" / "harvard.yaml"))
        self.assertEqual(RoadmapEntry.objects.filter(university="Harvard").count(), 2)


class CoverageRollupTests(TestCase):
    def setUp(self):
        make_catalog()
        call_command("loadroadmap", write_yaml(HARVARD))

    def test_entry_with_no_links_is_not_covered_by_this_plan(self):
        entry = RoadmapEntry.objects.create(
            university="MIT", category="X", code="6.001", name="SICP"
        )
        self.assertEqual(entry.coverage(), Coverage.NONE)

    def test_entry_is_partial_while_some_links_are_unsatisfied(self):
        entry = RoadmapEntry.objects.get(code="CS 50")
        self.assertEqual(entry.coverage(), Coverage.PARTIAL)

    def test_entry_is_all_covered_when_every_link_is_satisfied_live_or_frozen(self):
        # The frozen MATH 21a link is already transferred.
        self.assertEqual(RoadmapEntry.objects.get(code="MATH 21a").coverage(), Coverage.ALL)

    def test_marking_a_linked_course_passed_moves_the_rollup_with_no_reimport(self):
        entry = RoadmapEntry.objects.get(code="CS 50")
        for code in ("03071", "00831"):
            CourseStatus.objects.create(course=Course.objects.get(code=code), status=Status.PASSED)

        self.assertEqual(RoadmapEntry.objects.get(code="CS 50").coverage(), Coverage.ALL)


class ReferenceViewTests(TestCase):
    def setUp(self):
        make_catalog()
        call_command("loadroadmap", write_yaml(HARVARD))

    def test_view_groups_by_university_then_category(self):
        response = self.client.get(reverse("reference:roadmap"))
        self.assertEqual(response.status_code, 200)

        universities = response.context["universities"]
        self.assertEqual([u["name"] for u in universities], ["Harvard"])
        self.assertEqual(
            [c["name"] for c in universities[0]["categories"]],
            ["Mathematics", "Programming"],
        )

    def test_view_has_no_write_path(self):
        response = self.client.post(reverse("reference:roadmap"))
        self.assertIn(response.status_code, (403, 405))
        response = self.client.get(reverse("reference:roadmap"))
        self.assertNotContains(response, "<form")
