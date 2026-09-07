"""Planning: the availability template the Capacity figure is derived from.

See CONTEXT.md's "Planning" section and ADR-0007 (neglect is measured against
Capacity). A Study Window is what a weekday offers at most; an Availability
Block is what is taken out of it; Capacity is the remainder, recomputed on
every read so editing the template touches no other stored data.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Weekday(models.IntegerChoices):
    """Monday-first, matching `datetime.date.weekday()` so a rolling
    seven-day window contains each value exactly once (ADR-0007).
    """

    MONDAY = 0, _("Monday")
    TUESDAY = 1, _("Tuesday")
    WEDNESDAY = 2, _("Wednesday")
    THURSDAY = 3, _("Thursday")
    FRIDAY = 4, _("Friday")
    SATURDAY = 5, _("Saturday")
    SUNDAY = 6, _("Sunday")


class StudyWindow(models.Model):
    """The stretch of a given weekday during which the student is willing to
    study at all — a statement of appetite, not obligation (CONTEXT.md).

    At most one per weekday: a day with no row offers no study hours. This is
    the upper bound that makes Capacity a real number rather than "168 hours
    minus blocks" (ADR-0007).
    """

    weekday = models.IntegerField(choices=Weekday.choices, unique=True)
    start = models.TimeField()
    end = models.TimeField()

    class Meta:
        ordering = ["weekday"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start__lt=models.F("end")),
                name="study_window_start_before_end",
            )
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start:%H:%M}–{self.end:%H:%M}"


class AvailabilityBlock(models.Model):
    """A recurring weekly commitment that consumes hours — work, class, gym,
    chores. Never studied, never recommended; it only reduces what is left
    (CONTEXT.md, scope.md §1).

    Blocks may overlap each other and may extend past a Study Window's edges;
    Capacity counts only the part of each block that falls inside the window,
    and counts overlapping blocks once.
    """

    weekday = models.IntegerField(choices=Weekday.choices)
    start = models.TimeField()
    end = models.TimeField()
    label = models.CharField(max_length=100)

    class Meta:
        ordering = ["weekday", "start"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start__lt=models.F("end")),
                name="availability_block_start_before_end",
            )
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start:%H:%M}–{self.end:%H:%M} {self.label}"
