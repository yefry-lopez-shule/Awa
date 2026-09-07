"""The availability template screen (#12, scope.md §5 screen 6).

A Study Window per weekday, the Availability Blocks subtracted from it, the
Capacity that remains, and — when the Plan demands more hours than exist — the
overload warning stating both numbers.
"""

import datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from curriculum.models import AppSettings
from studying.models import Term

from .capacity import capacity_hours, course_targets, overload
from .models import AvailabilityBlock, StudyWindow, Weekday


def _current_term(plan):
    if plan is None:
        return None
    return Term.objects.filter(program=plan.program).order_by("-start_date").first()


def availability_template(request):
    """Render and save the availability template.

    Saving replaces the Study Windows and Availability Blocks wholesale from
    the submitted form; nothing else is touched, so Capacity is the only
    derived figure that moves.
    """

    plan = AppSettings.load().active_plan
    term = _current_term(plan)

    errors = []
    if request.method == "POST":
        errors = _save_template(request)
        if not errors:
            messages.success(request, _("Saved."))
            return redirect("planning:availability_template")

    windows = {w.weekday: w for w in StudyWindow.objects.all()}
    weekday_rows = [
        {"value": value, "label": label, "window": windows.get(value)}
        for value, label in Weekday.choices
    ]

    targets = course_targets(term) if term is not None else {}
    over = overload(term)

    context = {
        "weekday_rows": weekday_rows,
        "blocks": list(AvailabilityBlock.objects.all()),
        "weekday_choices": Weekday.choices,
        "targets": sorted(
            ({"course": c, "hours": h} for c, h in targets.items()),
            key=lambda row: row["course"].code,
        ),
        "capacity": capacity_hours(),
        "overload": over,
        "term": term,
    }
    if errors:
        context["errors"] = errors
    return render(request, "planning/availability_template.html", context)


def _parse_time(raw, errors):
    try:
        return datetime.time.fromisoformat(raw)
    except ValueError:
        errors.append(_("Times must be valid (HH:MM)."))
        return None


def _save_template(request):
    errors = []
    parsed_windows = []

    for value, _label in Weekday.choices:
        start_raw = request.POST.get(f"window_start_{value}", "").strip()
        end_raw = request.POST.get(f"window_end_{value}", "").strip()
        if not start_raw and not end_raw:
            continue
        if bool(start_raw) != bool(end_raw):
            errors.append(_("A Study Window needs both a start and an end, or neither."))
            continue
        start = _parse_time(start_raw, errors)
        end = _parse_time(end_raw, errors)
        if start is None or end is None:
            continue
        if start >= end:
            errors.append(_("A Study Window's start must come before its end."))
            continue
        parsed_windows.append((value, start, end))

    parsed_blocks = []
    for row in _submitted_block_rows(request):
        if row["delete"] or not any((row["start_raw"], row["end_raw"], row["label"])):
            continue
        if not (row["start_raw"] and row["end_raw"] and row["label"]):
            errors.append(_("An Availability Block needs a weekday, a start, an end and a label."))
            continue
        try:
            weekday = int(row["weekday_raw"])
            Weekday(weekday)
        except ValueError:
            errors.append(_("Invalid weekday for an Availability Block."))
            continue
        start = _parse_time(row["start_raw"], errors)
        end = _parse_time(row["end_raw"], errors)
        if start is None or end is None:
            continue
        if start >= end:
            errors.append(_("An Availability Block's start must come before its end."))
            continue
        parsed_blocks.append((weekday, start, end, row["label"]))

    if errors:
        return errors

    with transaction.atomic():
        StudyWindow.objects.all().delete()
        StudyWindow.objects.bulk_create(
            StudyWindow(weekday=value, start=start, end=end)
            for value, start, end in parsed_windows
        )
        AvailabilityBlock.objects.all().delete()
        AvailabilityBlock.objects.bulk_create(
            AvailabilityBlock(weekday=weekday, start=start, end=end, label=label)
            for weekday, start, end, label in parsed_blocks
        )

    return []


def _submitted_block_rows(request):
    """Existing blocks come back as `block_<id>_*`; a fresh one as `new_block_*`.
    Both are re-created from scratch on save, so their ids don't matter here.
    """

    rows = []
    ids = set()
    for key in request.POST:
        if key.startswith("block_") and key.endswith("_weekday"):
            ids.add(key[len("block_") : -len("_weekday")])
    for block_id in ids:
        prefix = f"block_{block_id}_"
        rows.append(
            {
                "weekday_raw": request.POST.get(f"{prefix}weekday", "").strip(),
                "start_raw": request.POST.get(f"{prefix}start", "").strip(),
                "end_raw": request.POST.get(f"{prefix}end", "").strip(),
                "label": request.POST.get(f"{prefix}label", "").strip(),
                "delete": bool(request.POST.get(f"{prefix}delete")),
            }
        )
    rows.append(
        {
            "weekday_raw": request.POST.get("new_block_weekday", "").strip(),
            "start_raw": request.POST.get("new_block_start", "").strip(),
            "end_raw": request.POST.get("new_block_end", "").strip(),
            "label": request.POST.get("new_block_label", "").strip(),
            "delete": False,
        }
    )
    return rows
