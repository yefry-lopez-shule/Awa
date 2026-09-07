"""Studying: where the student stands, and one attempt at a Course.

See CONTEXT.md's "Studying" section, ADR-0001 (Status is a fixed code enum)
and ADR-0010 (Status lives on the Course; Outcome lives on the Enrollment).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from curriculum.models import Course, Program


class Status(models.TextChoices):
    """Where the student stands on a Course. ADR-0001: fixed semantics, only
    the label translates.

    satisfies_prereq / counts_credits / has_grade:
        PENDING      no  / no  / no
        IN_PROGRESS  no  / no  / no
        PASSED       yes / yes / yes
        TRANSFERRED  yes / yes / no
        FAILED       no  / no  / yes
    """

    PENDING = "pending", _("Pending")
    IN_PROGRESS = "in_progress", _("In progress")
    PASSED = "passed", _("Passed")
    TRANSFERRED = "transferred", _("Transferred")
    FAILED = "failed", _("Failed")


STATUSES_SATISFYING_PREREQ = {Status.PASSED, Status.TRANSFERRED}
STATUSES_COUNTING_CREDITS = {Status.PASSED, Status.TRANSFERRED}


class CourseStatus(models.Model):
    """The Status of one Course (ADR-0010). Writable with no Enrollment behind
    it — the case for a Course passed before this app existed.

    A missing row means the same thing as an explicit PENDING row (a Course
    left untouched on the onboarding checklist defaults to pending); callers
    use `status_for_course` rather than querying this table directly so that
    default holds in exactly one place.
    """

    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name="status_record")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    final_grade = models.FloatField(
        null=True,
        blank=True,
        help_text="Historical grade for display only — recorded for a Course "
        "passed/failed before this app existed. Never set for TRANSFERRED.",
    )

    def __str__(self):
        return f"{self.course.code}: {self.status}"


def status_for_course(course):
    """The Status of a Course, defaulting to PENDING when no row exists yet."""

    try:
        return Status(course.status_record.status)
    except CourseStatus.DoesNotExist:
        return Status.PENDING


class Difficulty(models.TextChoices):
    """The student's own rating of how hard a Course is for them. Compounds
    (ADR-0004): raises the Target and multiplies the Score.
    """

    EASY = "easy", _("Easy")
    NORMAL = "normal", _("Normal")
    HARD = "hard", _("Hard")


class Outcome(models.TextChoices):
    """How one Enrollment ended (ADR-0010). Narrower than Status: no PENDING
    (an Enrollment means you enrolled) and no TRANSFERRED (that is the
    absence of an attempt).
    """

    IN_PROGRESS = "in_progress", _("In progress")
    PASSED = "passed", _("Passed")
    FAILED = "failed", _("Failed")


class Term(models.Model):
    """A dated period during which the student is enrolled in Courses."""

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="terms")
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.program.code} {self.start_date}–{self.end_date}"


class Enrollment(models.Model):
    """One Course taken by the student in one Term (ADR-0010, ADR-0011).

    Distinct from Course because the same Course can be retaken: a failed
    attempt and a later passing attempt are two Enrollment rows.
    """

    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="enrollments")
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.IN_PROGRESS)
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, default=Difficulty.NORMAL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["term", "course"], name="unique_enrollment_per_term")
        ]

    def __str__(self):
        return f"{self.course.code} @ {self.term}"


class GradedItem(models.Model):
    """Anything marked that contributes to a Course's Grade — a tarea, quiz,
    parcial, final, proyecto (CONTEXT.md). Attaches to one Enrollment.

    `type` is picked from the Program's `item_types` at entry but stored as
    plain text: the engine only ever reads `weight` and `due_at`, so the type
    vocabulary is data, not an enum (ADR-0002, scope.md §6).

    Weights across an Enrollment's items are validated to sum to the Program's
    `grade_scale_max` — but by the Course detail grid at save time, not here. A
    half-entered grid is a legitimate transient state; a *saved* one that
    doesn't add up would let a forecast lie quietly (scope.md §5 step 4).
    """

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="graded_items"
    )
    type = models.CharField(max_length=50)
    weight = models.FloatField(
        help_text="Share of the Course Grade, in the same units as the Program's grade_scale_max."
    )
    due_at = models.DateField(null=True, blank=True)
    grade = models.FloatField(
        null=True,
        blank=True,
        help_text="The mark once earned; null until the grade arrives.",
    )

    class Meta:
        ordering = ["due_at", "id"]

    def __str__(self):
        return f"{self.type} ({self.weight}) — {self.enrollment.course.code}"
