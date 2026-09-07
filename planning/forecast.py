"""The pass forecast: given what a Course's Graded Items have scored so far
and what weight is still ungraded, the single average the student needs on
the rest to clear `pass_mark` — or a plain statement that passing is no
longer possible.

A pure function over Graded Items (scope.md §4, §6). It reads the same rows
as Deadline Pressure and deliberately disagrees with it about one thing: a
past-due, ungraded item exerts no Deadline Pressure — tonight cannot change
it — but still counts toward `remaining_weight`, because a professor being
slow to grade does not erase that share of the Course (ADR-0008). The two
must never be merged or have one's past-due rule copied onto the other.
"""

from dataclasses import dataclass

from django.db import models
from django.utils.translation import gettext_lazy as _


class Verdict(models.TextChoices):
    """How the forecast reads, worst-case last."""

    NEEDS = "needs", _("Needs a passing average on what's left")
    SECURED = "secured", _("Passing is secured")
    PASSED = "passed", _("Passed")
    FAILED = "failed", _("Not passed")
    IMPOSSIBLE = "impossible", _("Passing is no longer possible")


@dataclass(frozen=True)
class Forecast:
    """The four numbers scope.md promised turned concrete.

    `weighted_so_far` is performance-to-date: the points already banked toward
    the final Grade, summing only items that carry a Grade — never assuming
    zero on the rest. `grade_so_far` is that same performance as a weighted
    average over just the graded weight, so a Course barely started does not
    read as already failing; it is None until something is graded.
    """

    weighted_so_far: float
    remaining_weight: float
    required_average: float
    verdict: str
    grade_so_far: float | None


def forecast(items, pass_mark, grade_scale_max):
    """Forecast the pass outcome for one Enrollment's Graded Items.

    `items` is any iterable of objects with `.weight` and `.grade` (`.grade`
    is None until the mark arrives). Weights are in the same units as
    `grade_scale_max` and, on a saved grid, sum to it (scope.md §5 step 4).
    """

    items = list(items)
    graded = [item for item in items if item.grade is not None]

    graded_weight = sum(item.weight for item in graded)
    remaining_weight = sum(item.weight for item in items if item.grade is None)
    weighted_so_far = (
        sum(item.grade * item.weight for item in graded) / grade_scale_max
    )
    grade_so_far = (
        weighted_so_far / graded_weight * grade_scale_max if graded_weight else None
    )

    if remaining_weight == 0:
        verdict = Verdict.PASSED if weighted_so_far >= pass_mark else Verdict.FAILED
        required_average = 0.0
    elif weighted_so_far >= pass_mark:
        verdict = Verdict.SECURED
        required_average = 0.0
    else:
        required_average = (
            (pass_mark - weighted_so_far) / remaining_weight * grade_scale_max
        )
        verdict = (
            Verdict.IMPOSSIBLE if required_average > grade_scale_max else Verdict.NEEDS
        )

    return Forecast(
        weighted_so_far=weighted_so_far,
        remaining_weight=remaining_weight,
        required_average=required_average,
        verdict=verdict,
        grade_so_far=grade_so_far,
    )
