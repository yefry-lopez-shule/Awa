"""`manage.py loadplan <file>` — load a Plan (and its Institution/Program/
Courses/Blocks/Prerequisites) from a YAML reference-data file.

ADR-0003: reference data is authored as YAML and loaded by a management
command; there are no CRUD screens for any of it.

Reconciles rather than duplicates: re-running on an unchanged file changes
nothing, and a second file naming an existing código must agree about its
créditos or the load fails loudly, naming the código and both values. Every
validation runs before anything is written; a rejection leaves the database
untouched (the whole load is one transaction).
"""

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from curriculum.models import Block, BlockEntry, Course, Institution, Plan, Prerequisite, Program


class Command(BaseCommand):
    help = "Load a curriculum Plan from a YAML file (ADR-0003, ADR-0009)."

    def add_arguments(self, parser):
        parser.add_argument("plan_file", type=str)

    def handle(self, *args, **options):
        path = options["plan_file"]
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except OSError as exc:
            raise CommandError(f"Could not read plan file {path}: {exc}")
        except yaml.YAMLError as exc:
            raise CommandError(f"{path} is not valid YAML: {exc}")

        with transaction.atomic():
            self._load(data)

        self.stdout.write(self.style.SUCCESS(f"Loaded plan from {path}"))

    def _load(self, data):
        institution = self._reconcile_institution(data["institution"])
        program = self._reconcile_program(institution, data["program"])
        plan = self._reconcile_plan(program, data.get("plan", {}))

        # Pass 1 — every Block and its entries, reconciling Courses as we go.
        # A course code may appear in more than one Block across a file (rare,
        # but reconciliation must hold even then) and requires may reference a
        # código defined later in the file, so Courses are fully resolved here
        # before any `requires` list is touched in pass 2.
        entries_needing_requires = []  # [(course, [required_codes])]

        for block_data in data.get("blocks", []):
            block = self._reconcile_block(plan, block_data)
            entries = block_data.get("entries", block_data.get("courses", []))
            declared_total = 0

            for entry_data in entries:
                if "slot" in entry_data:
                    count = entry_data.get("count", 1)
                    for i in range(1, count + 1):
                        credits = entry_data["credits"]
                        self._reconcile_slot_entry(block, entry_data["slot"], i, credits)
                        declared_total += credits
                else:
                    code = str(entry_data["code"])
                    credits = entry_data["credits"]
                    name = entry_data["name"]
                    course = self._reconcile_course(institution, code, name, credits)
                    self._reconcile_named_entry(block, course, credits)
                    declared_total += credits
                    if entry_data.get("requires"):
                        entries_needing_requires.append((course, entry_data["requires"]))

            if declared_total != block.credits:
                raise CommandError(
                    f"Block {block.name}: declared {block.credits} créditos but "
                    f"its entries sum to {declared_total}"
                )

        # Pass 2 — prerequisite edges, now that every Course in the file exists.
        for course, required_codes in entries_needing_requires:
            for req_code in required_codes:
                req_code = str(req_code)
                try:
                    requires_course = Course.objects.get(institution=institution, code=req_code)
                except Course.DoesNotExist:
                    raise CommandError(
                        f"{course.code} requires '{req_code}', which is not a "
                        f"known Course for {institution.name}"
                    )
                Prerequisite.objects.get_or_create(
                    plan=plan, course=course, requires_course=requires_course
                )

    # -- reconciliation helpers -------------------------------------------------

    def _reconcile_institution(self, d):
        institution, _ = Institution.objects.get_or_create(
            name=d["name"], defaults={"country": d.get("country", "")}
        )
        return institution

    def _reconcile_program(self, institution, d):
        item_types = d.get("item_types", [])
        default_items = d.get("default_items", [])
        if default_items:
            total = sum(item["weight"] for item in default_items)
            if total != d["grade_scale_max"]:
                raise CommandError(
                    f"Program {d['code']}: default_items weights sum to {total}, "
                    f"not grade_scale_max ({d['grade_scale_max']})"
                )

        program, _ = Program.objects.update_or_create(
            code=d["code"],
            defaults=dict(
                institution=institution,
                name=d["name"],
                pass_mark=d["pass_mark"],
                hours_per_credit=d["hours_per_credit"],
                grade_scale_max=d["grade_scale_max"],
                term_type=d["term_type"],
                term_weeks=d["term_weeks"],
                terms_per_year=d["terms_per_year"],
                item_types=item_types,
                default_items=default_items,
            ),
        )
        return program

    def _reconcile_plan(self, program, d):
        name = d.get("name", program.code)
        plan, _ = Plan.objects.get_or_create(program=program, name=name)
        return plan

    def _reconcile_block(self, plan, block_data):
        block, _ = Block.objects.update_or_create(
            plan=plan,
            name=block_data["name"],
            defaults={"credits": block_data["credits"]},
        )
        return block

    def _reconcile_course(self, institution, code, name, credits):
        existing = Course.objects.filter(institution=institution, code=code).first()
        if existing is None:
            return Course.objects.create(
                institution=institution, code=code, name=name, credits=credits
            )
        if existing.credits != credits:
            raise CommandError(
                f"Course {code}: existing créditos={existing.credits} but this "
                f"plan declares {credits} — refusing to overwrite recorded history"
            )
        if existing.name != name:
            existing.name = name
            existing.save(update_fields=["name"])
        return existing

    def _reconcile_named_entry(self, block, course, credits):
        BlockEntry.objects.update_or_create(
            block=block, course=course, defaults={"credits": credits}
        )

    def _reconcile_slot_entry(self, block, slot_label, slot_index, credits):
        BlockEntry.objects.update_or_create(
            block=block,
            course=None,
            slot_label=slot_label,
            slot_index=slot_index,
            defaults={"credits": credits},
        )
