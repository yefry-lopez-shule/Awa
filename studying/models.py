"""Studying: where the student stands, and one attempt at a Course.

See CONTEXT.md's "Studying" section, ADR-0001 (Status is a fixed code enum)
and ADR-0010 (Status lives on the Course; Outcome lives on the Enrollment).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from curriculum.models import Course


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
