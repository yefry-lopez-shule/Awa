"""Rendering the structured `Reason` from `rank()` into one line of prose.

ADR-0013: `rank()` returns *which rule won and its raw values*, never a
sentence. This is the separate layer that turns that structure into text in
whichever locale is active, using message templates with placeholders. Course
names and item types are inserted as-is — they are facts about the real
curriculum, not UI chrome.

The `es`/`en` catalogs that translate these templates are wired by #6; until
then every locale renders the English source string.
"""

from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from .ranking import RULE_DEADLINE_PRESSURE, RULE_HOURS_BEHIND, RULE_OVERRIDE


def _pct(weight):
    return "{:g}".format(weight)


def _hours(value):
    return "{:.1f}".format(value)


def _in_days(days):
    if days <= 0:
        return _("today")
    return ngettext("in %(days)d day", "in %(days)d days", days) % {"days": days}


def render_reason(reason):
    """One line explaining why the recommended Course won (scope.md §4 rule 1)."""

    if reason.rule == RULE_OVERRIDE:
        return _("%(item)s due %(when)s · %(weight)s%% of the grade · deadline override") % {
            "item": reason.item_name,
            "when": _in_days(reason.days_until_due),
            "weight": _pct(reason.item_weight),
        }

    if reason.rule == RULE_DEADLINE_PRESSURE:
        return _("%(item)s due %(when)s · %(weight)s%% of the grade") % {
            "item": reason.item_name,
            "when": _in_days(reason.days_until_due),
            "weight": _pct(reason.item_weight),
        }

    if reason.rule == RULE_HOURS_BEHIND:
        if reason.hours_behind and reason.hours_behind > 0:
            return _("%(hours)sh behind its Ration this week") % {
                "hours": _hours(reason.hours_behind)
            }
        return _("Nothing pressing right now")

    return ""  # unreachable; a Reason always carries one of the three rules
