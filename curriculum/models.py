"""Curriculum: the reference data every Program is built from.

See CONTEXT.md's "Curriculum" section and ADR-0009 for why Course belongs to
Institution rather than to a Plan, and why prerequisites belong to the Plan
rather than to the Course.
"""

from django.db import models


class Institution(models.Model):
    """A body that awards qualifications. UNED is the only one seeded."""

    name = models.CharField(max_length=200, unique=True)
    country = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Course(models.Model):
    """A catalogue entry, belonging to the Institution — never to a Plan.

    ADR-0009: a Course passed under one Plan (e.g. the Diplomado) must be the
    same Course row under another Plan (e.g. the Bachillerato), so a pass
    carries across without a second, orphaned row.
    """

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="courses"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    credits = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "code"], name="unique_course_code_per_institution"
            )
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class Program(models.Model):
    """A qualification a student works towards (Diplomado, Bachillerato).

    Grading scale, credit-to-hours conversion, and term calendar are plain
    configuration fields here — never pluggable strategy classes (ADR-0002).
    """

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="programs"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)

    pass_mark = models.PositiveSmallIntegerField()
    hours_per_credit = models.FloatField()
    grade_scale_max = models.PositiveSmallIntegerField()

    term_type = models.CharField(max_length=50)
    term_weeks = models.PositiveSmallIntegerField()
    terms_per_year = models.PositiveSmallIntegerField()

    # The engine only ever reads `weight` and `due_date` off a Graded Item,
    # so its type vocabulary and the default grading-shape skeleton are data,
    # never a fixed enum (scope.md §6).
    item_types = models.JSONField(default=list)
    default_items = models.JSONField(
        default=list,
        help_text="Starting skeleton for a Cuatrimestre's deadlines grid — "
        "never a constraint. Each item: {type, weight}.",
    )

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Plan(models.Model):
    """The complete set of Courses a Program requires, grouped into Blocks.

    Reserved for the curriculum only — a schedule, a roadmap, or a document
    is never a Plan (CONTEXT.md).
    """

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="plans")
    name = models.CharField(
        max_length=200,
        help_text="e.g. 'IIC-2026' — distinguishes this Plan from a later "
        "revision of the same Program.",
    )

    class Meta:
        ordering = ["program", "name"]
        constraints = [
            models.UniqueConstraint(fields=["program", "name"], name="unique_plan_name_per_program")
        ]

    def __str__(self):
        return f"{self.program.code} / {self.name}"


class Block(models.Model):
    """A named grouping of Courses within a Plan, carrying its own credit total."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="blocks")
    name = models.CharField(max_length=50, help_text="e.g. 'A'")
    credits = models.PositiveSmallIntegerField(
        help_text="Declared total; loadplan rejects a mismatch against the sum "
        "of this Block's entries."
    )

    class Meta:
        ordering = ["plan", "name"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "name"], name="unique_block_name_per_plan")
        ]

    def __str__(self):
        return f"{self.plan} — Bloque {self.name}"


class BlockEntry(models.Model):
    """One place in a Block: a named Course, or an unfilled Slot.

    ADR-0009: a null `course` is a Slot. It carries its own créditos so a
    Plan totals correctly whether or not its Slots are filled, and filling
    one is an assignment to `course` — never a special case.
    """

    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="entries")
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="block_entries", null=True, blank=True
    )
    credits = models.PositiveSmallIntegerField()

    # Only meaningful when course is null — what kind of Slot this is, and
    # which one of a `count: N` group it is, so re-running loadplan can
    # reconcile it instead of duplicating an anonymous entry.
    slot_label = models.CharField(max_length=100, blank=True, default="")
    slot_index = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["block", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["block", "course"],
                condition=models.Q(course__isnull=False),
                name="unique_named_entry_per_block",
            ),
            models.UniqueConstraint(
                fields=["block", "slot_label", "slot_index"],
                condition=models.Q(course__isnull=True),
                name="unique_slot_per_block",
            ),
        ]

    def is_slot(self):
        return self.course_id is None

    def __str__(self):
        if self.course_id:
            return f"{self.block} — {self.course.code}"
        return f"{self.block} — Slot({self.slot_label} #{self.slot_index})"


class Prerequisite(models.Model):
    """One edge of a Plan's prerequisite graph: `course` requires `requires_course`.

    Belongs to the Plan, not the Course (ADR-0009) — two Plans may require
    different things of the same shared Course. Multiple rows for the same
    `course` are a conjunction: every one must be satisfied, never any one.
    """

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="prerequisites")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="+")
    requires_course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "course", "requires_course"], name="unique_prerequisite_edge"
            )
        ]

    def __str__(self):
        return f"{self.plan}: {self.course.code} requires {self.requires_course.code}"


class AppSettings(models.Model):
    """Singleton: which Plan the single student is currently active in.

    One student per install (scope.md §6), so there is exactly one row.
    """

    active_plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"AppSettings(active_plan={self.active_plan})"
