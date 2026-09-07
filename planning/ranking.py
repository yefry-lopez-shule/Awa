"""The ranking engine's building blocks (scope.md §4).

Only Deadline Pressure lands here with #14 — it is the one quantity the pass
forecast must be contrasted against (ADR-0008): the same Graded Items, read
the opposite way at the due date. `rank()` in full — Ration, Hours Behind,
the Override tier, the reason string — is #15 and composes this.
"""

import datetime


def deadline_pressure(items, grade_scale_max, *, half_life_days=7, today=None):
    """How near and how heavily weighted a Course's most pressing *upcoming*
    Graded Item is: the max over items still due of
    `(weight / grade_scale_max) * 0.5 ** (days_until / half_life_days)`.

    Forward-looking only (scope.md §4 rule 3, ADR-0008): an item whose due
    date has passed — or that carries no due date — contributes nothing,
    because studying tonight cannot change it and the decay term grows
    explosively on negative inputs. 0 when nothing is upcoming.
    """

    today = today or datetime.date.today()
    pressures = [
        (item.weight / grade_scale_max)
        * 0.5 ** ((item.due_at - today).days / half_life_days)
        for item in items
        if item.due_at is not None and item.due_at > today
    ]
    return max(pressures, default=0.0)
