"""Planning: the availability template the Capacity figure is derived from,
and `ScoringConfig` — the ranking engine's tunable constants.

See CONTEXT.md's "Planning" section and ADR-0007 (neglect is measured against
Capacity). A Study Window is what a weekday offers at most; an Availability
Block is what is taken out of it; Capacity is the remainder, recomputed on
every read so editing the template touches no other stored data.

`ScoringConfig` is a singleton holding the numbers `rank()` is calibrated
around (scope.md §6): the formula's shape is code, its constants are here.
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


class ScoringConfig(models.Model):
    """Singleton: the ranking engine's tunable constants (scope.md §6, locked
    decision 15 — the formula's *shape* is code, its *numbers* are here).

    Separate from `AppSettings` (which points at the active Plan): a curriculum
    pointer and a set of scoring weights get changed by different people for
    different reasons. `pass_mark`, `hours_per_credit` and `grade_scale_max`
    stay on `Program` — they are the institution's rules, not tuning knobs.

    `w_deadline` is a unit conversion, not a taste knob (ADR-0008): how many
    hours of neglect a full-weight Graded Item due today is worth. At 1.0 the
    deadline term changes no ordering at all; at 50 it overrides Difficulty
    everywhere and reverses ADR-0004. ~20 — about one Ration — is the only
    defensible value.
    """

    override_window_hours = models.FloatField(
        default=48.0,
        help_text="A Graded Item due within this many hours can jump the queue.",
    )
    override_min_weight = models.FloatField(
        default=0.10,
        help_text="As a fraction of the full grade — a lighter item never "
        "triggers the Override (ADR-0008).",
    )
    deadline_half_life_days = models.FloatField(
        default=7.0,
        help_text="Days over which Deadline Pressure from an item halves.",
    )
    w_hours_behind = models.FloatField(default=1.0)
    w_deadline = models.FloatField(default=20.0)
    stale_after_days = models.PositiveSmallIntegerField(
        default=4,
        help_text="Days since the last Study Log after which the banner labels "
        "its recommendation a guess. Never suppresses it.",
    )

    difficulty_easy = models.FloatField(default=0.75)
    difficulty_normal = models.FloatField(default=1.0)
    difficulty_hard = models.FloatField(default=1.5)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def difficulty_multipliers(self):
        """Keyed by the `Difficulty` value string, so `rank()` and
        `course_targets()` look a multiplier up the same way.
        """

        return {
            "easy": self.difficulty_easy,
            "normal": self.difficulty_normal,
            "hard": self.difficulty_hard,
        }

    def __str__(self):
        return f"ScoringConfig(w_deadline={self.w_deadline})"
