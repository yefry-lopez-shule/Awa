"""Tests for the curriculum catalog and `loadplan` (#8, ADR-0009, ADR-0003)."""

import tempfile
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from curriculum.models import Block, BlockEntry, Course, Institution, Plan, Prerequisite, Program

MINIMAL_PLAN = {
    "institution": {"name": "Test U", "country": "CR"},
    "program": {
        "name": "Test Program",
        "code": "TEST-1",
        "pass_mark": 70,
        "hours_per_credit": 3.0,
        "grade_scale_max": 100,
        "term_type": "cuatrimestre",
        "term_weeks": 15,
        "terms_per_year": 3,
        "item_types": ["tarea", "final"],
        "default_items": [{"type": "tarea", "weight": 40}, {"type": "final", "weight": 60}],
    },
    "plan": {"name": "TEST-1"},
    "blocks": [
        {
            "name": "A",
            "credits": 7,
            "courses": [
                {"code": "101", "credits": 4, "name": "Intro"},
                {"code": "102", "credits": 3, "name": "Follow-up", "requires": ["101"]},
            ],
        }
    ],
}


def write_yaml(data):
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    yaml.safe_dump(data, f, allow_unicode=True)
    f.close()
    return f.name


class LoadplanMinimalTests(TestCase):
    def test_loads_minimal_fixture_into_expected_rows(self):
        path = write_yaml(MINIMAL_PLAN)

        call_command("loadplan", path)

        institution = Institution.objects.get(name="Test U")
        program = Program.objects.get(code="TEST-1")
        plan = Plan.objects.get(program=program, name="TEST-1")
        block = Block.objects.get(plan=plan, name="A")
        self.assertEqual(block.credits, 7)
        self.assertEqual(
            set(Course.objects.filter(institution=institution).values_list("code", flat=True)),
            {"101", "102"},
        )
        self.assertEqual(BlockEntry.objects.filter(block=block).count(), 2)
        prereq = Prerequisite.objects.get(plan=plan)
        self.assertEqual(prereq.course.code, "102")
        self.assertEqual(prereq.requires_course.code, "101")

    def test_rerun_on_unchanged_file_is_idempotent(self):
        path = write_yaml(MINIMAL_PLAN)

        call_command("loadplan", path)
        call_command("loadplan", path)

        self.assertEqual(Course.objects.count(), 2)
        self.assertEqual(BlockEntry.objects.count(), 2)
        self.assertEqual(Prerequisite.objects.count(), 1)

    def test_second_plan_reconciles_existing_code_by_matching(self):
        path = write_yaml(MINIMAL_PLAN)
        call_command("loadplan", path)

        second = {
            **MINIMAL_PLAN,
            "program": {**MINIMAL_PLAN["program"], "code": "TEST-2"},
            "plan": {"name": "TEST-2"},
            "blocks": [
                {
                    "name": "A",
                    "credits": 4,
                    "courses": [{"code": "101", "credits": 4, "name": "Intro"}],
                }
            ],
        }
        path2 = write_yaml(second)

        call_command("loadplan", path2)

        self.assertEqual(Course.objects.filter(code="101").count(), 1)

    def test_disagreeing_credits_for_existing_code_fails_the_load(self):
        path = write_yaml(MINIMAL_PLAN)
        call_command("loadplan", path)

        conflicting = {
            **MINIMAL_PLAN,
            "program": {**MINIMAL_PLAN["program"], "code": "TEST-2"},
            "plan": {"name": "TEST-2"},
            "blocks": [
                {
                    "name": "A",
                    "credits": 5,
                    "courses": [{"code": "101", "credits": 5, "name": "Intro"}],
                }
            ],
        }
        path2 = write_yaml(conflicting)

        with self.assertRaises(CommandError) as ctx:
            call_command("loadplan", path2)

        message = str(ctx.exception)
        self.assertIn("101", message)
        self.assertIn("4", message)
        self.assertIn("5", message)
        # Nothing from the failed load's own Program is left half-written.
        self.assertFalse(Program.objects.filter(code="TEST-2").exists())

    def test_block_credits_mismatch_with_entries_is_rejected(self):
        bad = {
            **MINIMAL_PLAN,
            "blocks": [
                {
                    "name": "A",
                    "credits": 99,
                    "courses": [{"code": "101", "credits": 4, "name": "Intro"}],
                }
            ],
        }
        path = write_yaml(bad)

        with self.assertRaises(CommandError):
            call_command("loadplan", path)

        self.assertFalse(Course.objects.exists())

    def test_slot_count_expands_to_independently_fillable_slots(self):
        data = {
            **MINIMAL_PLAN,
            "blocks": [
                {
                    "name": "A",
                    "credits": 6,
                    "courses": [{"slot": "humanidades", "credits": 3, "count": 2}],
                }
            ],
        }
        path = write_yaml(data)

        call_command("loadplan", path)

        entries = BlockEntry.objects.filter(block__name="A")
        self.assertEqual(entries.count(), 2)
        self.assertTrue(all(e.is_slot() for e in entries))
        self.assertEqual(set(entries.values_list("slot_index", flat=True)), {1, 2})

    def test_default_items_not_summing_to_grade_scale_max_is_rejected(self):
        bad = {
            **MINIMAL_PLAN,
            "program": {
                **MINIMAL_PLAN["program"],
                "default_items": [{"type": "tarea", "weight": 40}],
            },
        }
        path = write_yaml(bad)

        with self.assertRaises(CommandError):
            call_command("loadplan", path)

    def test_prerequisites_are_conjunctions_not_disjunctions(self):
        data = {
            **MINIMAL_PLAN,
            "blocks": [
                {
                    "name": "A",
                    "credits": 11,
                    "courses": [
                        {"code": "101", "credits": 4, "name": "Intro"},
                        {"code": "102", "credits": 3, "name": "Second"},
                        {
                            "code": "103",
                            "credits": 4,
                            "name": "Third",
                            "requires": ["101", "102"],
                        },
                    ],
                }
            ],
        }
        path = write_yaml(data)

        call_command("loadplan", path)

        plan = Plan.objects.get(name="TEST-1")
        course_103 = Course.objects.get(code="103")
        required = set(
            Prerequisite.objects.filter(plan=plan, course=course_103).values_list(
                "requires_course__code", flat=True
            )
        )
        self.assertEqual(required, {"101", "102"})


class LoadplanUnedFixtureTests(TestCase):
    def test_real_uned_plan_loads_to_expected_shape(self):
        path = Path(settings.BASE_DIR) / "plans" / "uned" / "iic-diplomado-2026.yaml"

        call_command("loadplan", str(path))

        plan = Plan.objects.get(name="IIC-2026")
        blocks = Block.objects.filter(plan=plan)
        self.assertEqual(blocks.count(), 5)
        self.assertEqual(sum(b.credits for b in blocks), 78)

        entries = BlockEntry.objects.filter(block__plan=plan)
        named = entries.filter(course__isnull=False)
        slots = entries.filter(course__isnull=True)
        self.assertEqual(named.count(), 19)
        self.assertEqual(slots.count(), 4)

        course_00831 = Course.objects.get(code="00831")
        required = set(
            Prerequisite.objects.filter(plan=plan, course=course_00831).values_list(
                "requires_course__code", flat=True
            )
        )
        self.assertEqual(required, {"03071", "03069", "03072"})

    def test_real_uned_plan_load_is_idempotent(self):
        path = Path(settings.BASE_DIR) / "plans" / "uned" / "iic-diplomado-2026.yaml"

        call_command("loadplan", str(path))
        call_command("loadplan", str(path))

        plan = Plan.objects.get(name="IIC-2026")
        self.assertEqual(Course.objects.filter(institution__name="UNED").count(), 19)
        self.assertEqual(BlockEntry.objects.filter(block__plan=plan).count(), 23)
