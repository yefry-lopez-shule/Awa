"""Reference: the self-study roadmap, read-only.

See CONTEXT.md's "Reference" section, ADR-0006 (the roadmap is reference
material, not a second track) and ADR-0012 (coverage is many-to-many, and
not every link needs a Course).

Nothing here is ever studied, scheduled, recommended, or given hours. Rows
arrive through `manage.py loadroadmap` (ADR-0003 — reference data is a data
file, never a CRUD screen) and are read by exactly one screen.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from curriculum.models import Course
from studying.models import STATUSES_COUNTING_CREDITS, Status, status_for_course


class Coverage(models.TextChoices):
    """A Roadmap Entry's overall coverage, rolled up from its Coverage Links.

    Not stored — recomputed on every read so a Course marked passed later
    moves the entry with no re-import (ADR-0012).
    """

    ALL = "all", _("All covered")
    PARTIAL = "partial", _("Partially covered")
    NONE = "none", _("Not covered by this Plan")


class RoadmapEntry(models.Model):
    """A course at another university, catalogued for comparison (CONTEXT.md).

    The foreign side's código and name are stored verbatim, messy cases
    included — ``"18.01 / 18.02 / 18.03 / 18.06"`` is one string, not four
    parsed alternatives (ADR-0012). `university` is a plain string, never a
    foreign key to Institution: Harvard, Stanford, MIT and Caltech are
    comparison points, never places the student enrolls.
    """

    university = models.CharField(max_length=100)
    category = models.CharField(
        max_length=100,
        help_text="The foreign programme's own grouping — the reference view "
        "groups by university then this.",
    )
    code = models.CharField(max_length=100, help_text="The foreign course's código, verbatim.")
    name = models.CharField(max_length=300, help_text="The foreign course's name, verbatim.")

    # Resource shelf (scope.md §7) — all optional, shown by the reference view
    # where present.
    official_link = models.URLField(blank=True, default="")
    video_link = models.URLField(blank=True, default="")
    youtube_channel = models.CharField(max_length=300, blank=True, default="")
    textbook = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["university", "category", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["university", "code"], name="unique_roadmap_code_per_university"
            )
        ]

    def __str__(self):
        return f"{self.university}: {self.code} {self.name}"

    def coverage(self):
        """Roll up this entry's Coverage Links (ADR-0012):

        - no links at all → "not covered by this Plan"
        - every link satisfied (live or frozen) → all covered
        - a mix → partially covered
        """

        links = list(self.links.all())
        if not links:
            return Coverage.NONE
        if all(link.is_satisfied() for link in links):
            return Coverage.ALL
        return Coverage.PARTIAL


class CoverageLink(models.Model):
    """One piece of what a Roadmap Entry corresponds to on the UNED side
    (CONTEXT.md, ADR-0012): a note, and optionally a Course.

    Where a real Course exists the link points at it and reads its Status
    live — passing that Course moves the parent entry's rollup with no
    re-import. Where the coverage is a fact about study elsewhere with
    nothing in any catalog to point to (the prior Física degree's
    convalidaciones), `course` is null and `imported_status` carries the
    status captured once at import, never recomputed.
    """

    entry = models.ForeignKey(RoadmapEntry, on_delete=models.CASCADE, related_name="links")

    # Position in the source file, within this entry's link list — the
    # reconciliation key so re-running loadroadmap updates in place instead
    # of duplicating (links have no natural identity of their own).
    position = models.PositiveSmallIntegerField()

    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="coverage_links",
        null=True,
        blank=True,
    )
    note = models.CharField(max_length=500, blank=True, default="")
    imported_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        blank=True,
        default="",
        help_text="Frozen status, used only when `course` is null. With a "
        "Course, its live Status wins and this is ignored.",
    )

    class Meta:
        ordering = ["entry", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["entry", "position"], name="unique_coverage_link_position_per_entry"
            )
        ]

    def __str__(self):
        target = self.course.code if self.course_id else "(no Course)"
        return f"{self.entry.code} → {target}"

    def effective_status(self):
        """The Status this link counts as: the linked Course's live Status
        where there is one, otherwise the frozen `imported_status`."""

        if self.course_id is not None:
            return status_for_course(self.course)
        return Status(self.imported_status) if self.imported_status else Status.PENDING

    def is_satisfied(self):
        """True when this piece of coverage is done — passed or transferred,
        live or frozen (ADR-0012)."""

        return self.effective_status() in STATUSES_COUNTING_CREDITS
