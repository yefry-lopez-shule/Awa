"""`manage.py loadroadmap <file>` — load one university's slice of the
self-study roadmap from a YAML file (ADR-0003, ADR-0012).

One university per file. Reconciles by foreign código: re-running on an
unchanged file changes nothing, and a second run for the same university
matches entries by código rather than duplicating them. Every validation
runs before anything is written — a rejection leaves the database untouched
(the whole load is one transaction).

A Coverage Link either names a `course` código that must already exist in
the catalog, or carries a frozen `status` and no Course at all (the prior
Física degree's convalidaciones). A código absent from the catalog fails
the load, naming the bad código.
"""

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from curriculum.models import AppSettings, Course
from studying.models import Status

from reference.models import CoverageLink, RoadmapEntry


class Command(BaseCommand):
    help = "Load one university's roadmap slice from a YAML file (ADR-0003, ADR-0012)."

    def add_arguments(self, parser):
        parser.add_argument("roadmap_file", type=str)

    def handle(self, *args, **options):
        path = options["roadmap_file"]
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except OSError as exc:
            raise CommandError(f"Could not read roadmap file {path}: {exc}")
        except yaml.YAMLError as exc:
            raise CommandError(f"{path} is not valid YAML: {exc}")

        with transaction.atomic():
            university = self._load(data)

        self.stdout.write(self.style.SUCCESS(f"Loaded {university} roadmap from {path}"))

    def _load(self, data):
        if not isinstance(data, dict) or not data.get("university"):
            raise CommandError("Roadmap file must name a single `university`.")
        university = str(data["university"])

        institution = self._catalog_institution()
        valid_statuses = {s.value for s in Status}

        # Validate the whole file first, resolving every Course, so a bad
        # código aborts before a single row is written.
        resolved = []  # [(entry_data, [(position, course_or_None, note, imported_status)])]
        for entry_data in data.get("entries", []):
            code = str(entry_data["code"])
            links = []
            for position, link_data in enumerate(entry_data.get("links", [])):
                course = None
                imported_status = ""
                if link_data.get("course") is not None:
                    course_code = str(link_data["course"])
                    course = Course.objects.filter(
                        institution=institution, code=course_code
                    ).first()
                    if course is None:
                        raise CommandError(
                            f"{university} {code}: Coverage Link names código "
                            f"'{course_code}', which is not a known Course for "
                            f"{institution.name}"
                        )
                else:
                    imported_status = str(link_data.get("status", "") or "")
                    if imported_status and imported_status not in valid_statuses:
                        raise CommandError(
                            f"{university} {code}: Coverage Link status "
                            f"'{imported_status}' is not one of "
                            f"{sorted(valid_statuses)}"
                        )
                links.append(
                    (position, course, str(link_data.get("note", "") or ""), imported_status)
                )
            resolved.append((entry_data, links))

        for entry_data, links in resolved:
            entry = self._reconcile_entry(university, entry_data)
            seen_positions = []
            for position, course, note, imported_status in links:
                CoverageLink.objects.update_or_create(
                    entry=entry,
                    position=position,
                    defaults={
                        "course": course,
                        "note": note,
                        "imported_status": imported_status,
                    },
                )
                seen_positions.append(position)
            # Drop links the file no longer lists for this entry.
            entry.links.exclude(position__in=seen_positions).delete()

        return university

    def _catalog_institution(self):
        """The Institution whose catalog a Coverage Link's código resolves
        against — the active Plan's, since that is the only Plan the
        reference view speaks to (ADR-0012 names no second Institution)."""

        plan = AppSettings.load().active_plan
        if plan is None:
            raise CommandError(
                "No active Plan — load a curriculum Plan with `loadplan` before "
                "importing a roadmap that links to its Courses."
            )
        return plan.program.institution

    def _reconcile_entry(self, university, entry_data):
        entry, _ = RoadmapEntry.objects.update_or_create(
            university=university,
            code=str(entry_data["code"]),
            defaults={
                "category": str(entry_data.get("category", "") or ""),
                "name": str(entry_data.get("name", "") or ""),
                "official_link": str(entry_data.get("official_link", "") or ""),
                "video_link": str(entry_data.get("video_link", "") or ""),
                "youtube_channel": str(entry_data.get("youtube_channel", "") or ""),
                "textbook": str(entry_data.get("textbook", "") or ""),
            },
        )
        return entry
