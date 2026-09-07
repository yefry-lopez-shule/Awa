"""Views for the studying app: the input surfaces the student actually
touches (onboarding, quick log, course detail, cuatrimestre setup).
"""

import datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from curriculum.models import AppSettings, BlockEntry, Course

from .models import (
    CourseStatus,
    Difficulty,
    Enrollment,
    GradedItem,
    Outcome,
    Status,
    Term,
    status_for_course,
)
from .queries import credits_earned, is_unlocked, opens_next_term


def onboarding(request):
    """The 23-row onboarding checklist (#10, ADR-0011).

    Historical statuses (pending/passed/transferred/failed) write directly to
    CourseStatus. Marking a Course in progress additionally opens (or
    reuses) the current Term and creates an Enrollment + Difficulty, so the
    ranking engine has something to work with immediately.
    """

    app_settings = AppSettings.load()
    plan = app_settings.active_plan
    if plan is None:
        return render(request, "studying/onboarding.html", {"plan": None, "rows": []})

    entries = list(
        BlockEntry.objects.filter(block__plan=plan)
        .select_related("block", "course", "course__status_record")
        .order_by("block__name", "id")
    )

    errors = []
    if request.method == "POST":
        errors = _process_onboarding_submission(request, plan, entries)
        if not errors:
            messages.success(request, _("Saved."))
            return redirect("studying:onboarding")

    rows = _build_rows(entries, plan)
    context = {"plan": plan, "rows": rows}
    if errors:
        context["errors"] = errors
    return render(request, "studying/onboarding.html", context)


def degree_map(request):
    """The degree map (#11): the five Bloques, créditos earned against the
    Plan's total, and which Courses are unlocked — with a distinct projection
    for what opens once this term's in-progress Courses pass.

    Reads `CourseStatus`, `BlockEntry` and the curriculum queries from #9,
    scoped to the Plan named by `AppSettings`. Nothing here is cached: the
    projection is recomputed every view, so a Course later marked failed
    simply stops appearing in it.
    """

    plan = AppSettings.load().active_plan
    if plan is None:
        return render(request, "studying/degree_map.html", {"plan": None, "blocks": []})

    blocks = []
    credits_required = 0
    for block in plan.blocks.prefetch_related("entries__course__status_record"):
        rows = []
        for entry in block.entries.all():
            course = entry.course
            if course is None:
                rows.append(
                    {
                        "entry": entry,
                        "course": None,
                        "is_slot": True,
                        "status": None,
                        "unlocked": False,
                        "opens_next_term": False,
                        "credits": entry.credits,
                    }
                )
                continue
            rows.append(
                {
                    "entry": entry,
                    "course": course,
                    "is_slot": False,
                    "status": status_for_course(course),
                    "unlocked": is_unlocked(course, plan),
                    "opens_next_term": opens_next_term(course, plan),
                    "credits": entry.credits,
                }
            )
        blocks.append(
            {
                "block": block,
                "rows": rows,
                "credits_earned": credits_earned(plan, block=block),
                "credits_total": block.credits,
            }
        )
        credits_required += block.credits

    context = {
        "plan": plan,
        "blocks": blocks,
        "credits_earned_total": credits_earned(plan),
        "credits_required": credits_required,
    }
    return render(request, "studying/degree_map.html", context)


def course_detail(request, course_id):
    """Course detail (#13, scope.md §4 screen 4).

    Keyed on a Course. When the student has an active Enrollment for it, the
    page is an inline grid to add, edit, and remove that Enrollment's Graded
    Items — type, weight, due date, and a grade entered whenever it arrives.
    Otherwise it shows only the historical Status and final_grade (#14 grows
    the live forecast into that same space).
    """

    course = get_object_or_404(Course, pk=course_id)
    enrollment = (
        Enrollment.objects.filter(course=course, outcome=Outcome.IN_PROGRESS)
        .select_related("term__program")
        .order_by("-term__start_date")
        .first()
    )

    try:
        final_grade = course.status_record.final_grade
    except CourseStatus.DoesNotExist:
        final_grade = None

    errors = []
    if request.method == "POST" and enrollment is not None:
        errors = _save_graded_items(request, enrollment)
        if not errors:
            messages.success(request, _("Saved."))
            return redirect("studying:course_detail", course_id=course.id)

    context = {
        "course": course,
        "enrollment": enrollment,
        "status": status_for_course(course),
        "final_grade": final_grade,
    }
    if enrollment is not None:
        program = enrollment.term.program
        items = list(enrollment.graded_items.order_by("due_at", "id"))
        context.update(
            {
                "items": items,
                "item_types": program.item_types,
                "grade_scale_max": program.grade_scale_max,
                "weight_total": sum(item.weight for item in items),
            }
        )
    if errors:
        context["errors"] = errors
    return render(request, "studying/course_detail.html", context)


def _submitted_item_rows(request):
    """Existing items come back as `item_<id>_*`; a fresh one as `new_item_*`.
    An unchanged row round-trips its id so its identity (and any grade already
    on it) survives the save.
    """

    rows = []
    ids = set()
    for key in request.POST:
        if key.startswith("item_") and key.endswith("_type"):
            ids.add(key[len("item_") : -len("_type")])
    for item_id in ids:
        prefix = f"item_{item_id}_"
        rows.append(
            {
                "id": item_id,
                "type": request.POST.get(f"{prefix}type", "").strip(),
                "weight_raw": request.POST.get(f"{prefix}weight", "").strip(),
                "due_raw": request.POST.get(f"{prefix}due", "").strip(),
                "grade_raw": request.POST.get(f"{prefix}grade", "").strip(),
                "delete": bool(request.POST.get(f"{prefix}delete")),
            }
        )
    rows.append(
        {
            "id": None,
            "type": request.POST.get("new_item_type", "").strip(),
            "weight_raw": request.POST.get("new_item_weight", "").strip(),
            "due_raw": request.POST.get("new_item_due", "").strip(),
            "grade_raw": request.POST.get("new_item_grade", "").strip(),
            "delete": False,
        }
    )
    return rows


def _save_graded_items(request, enrollment):
    """Reconcile the submitted grid against the Enrollment's Graded Items.

    Nothing is written unless the whole submission is valid, and — the rule
    scope.md §5 step 4 exists for — a non-empty grid whose weights don't sum
    to `grade_scale_max` is reported and not saved.
    """

    program = enrollment.term.program
    valid_types = set(program.item_types)
    errors = []
    parsed = []

    for row in _submitted_item_rows(request):
        if row["delete"]:
            continue
        if not any((row["type"], row["weight_raw"], row["due_raw"], row["grade_raw"])):
            continue  # An untouched new row.

        if row["type"] not in valid_types:
            errors.append(_("Choose an item type from the Program's list."))
            continue

        try:
            weight = float(row["weight_raw"])
        except ValueError:
            errors.append(_("A weight must be a number."))
            continue
        if weight <= 0:
            errors.append(_("A weight must be greater than zero."))
            continue

        due_at = None
        if row["due_raw"]:
            try:
                due_at = datetime.date.fromisoformat(row["due_raw"])
            except ValueError:
                errors.append(_("A due date must be a valid date."))

        grade = None
        if row["grade_raw"]:
            try:
                grade = float(row["grade_raw"])
            except ValueError:
                errors.append(_("A grade must be a number."))
            else:
                if not 0 <= grade <= program.grade_scale_max:
                    errors.append(
                        _("A grade must be between 0 and %(max)s.")
                        % {"max": program.grade_scale_max}
                    )

        parsed.append(
            {"id": row["id"], "type": row["type"], "weight": weight, "due_at": due_at, "grade": grade}
        )

    if errors:
        return errors

    total = sum(p["weight"] for p in parsed)
    if parsed and round(total - program.grade_scale_max, 6) != 0:
        return [
            _("Weights must sum to %(max)s; the current items sum to %(total)s.")
            % {"max": program.grade_scale_max, "total": "{:g}".format(total)}
        ]

    submitted_ids = {p["id"] for p in parsed if p["id"]}
    with transaction.atomic():
        enrollment.graded_items.exclude(id__in=submitted_ids).delete()
        for p in parsed:
            if p["id"]:
                GradedItem.objects.filter(id=p["id"], enrollment=enrollment).update(
                    type=p["type"], weight=p["weight"], due_at=p["due_at"], grade=p["grade"]
                )
            else:
                GradedItem.objects.create(
                    enrollment=enrollment,
                    type=p["type"],
                    weight=p["weight"],
                    due_at=p["due_at"],
                    grade=p["grade"],
                )
    return []


def _build_rows(entries, plan):
    rows = []
    for entry in entries:
        if entry.course is not None:
            status = status_for_course(entry.course)
            unlocked = is_unlocked(entry.course, plan)
            try:
                final_grade = entry.course.status_record.final_grade
            except CourseStatus.DoesNotExist:
                final_grade = None
        else:
            status = Status.PENDING
            unlocked = True
            final_grade = None
        rows.append(
            {
                "entry": entry,
                "status": status,
                "unlocked": unlocked,
                "final_grade": final_grade,
            }
        )
    return rows


def _process_onboarding_submission(request, plan, entries):
    errors = []
    parsed = []

    for entry in entries:
        status_raw = request.POST.get(f"status_{entry.id}", Status.PENDING)
        try:
            status = Status(status_raw)
        except ValueError:
            errors.append(_("Invalid status submitted."))
            continue

        grade_raw = request.POST.get(f"grade_{entry.id}", "").strip()
        grade = None
        if grade_raw:
            try:
                grade = float(grade_raw)
            except ValueError:
                errors.append(_("Grade must be a number."))

        if grade is not None and status not in (Status.PASSED, Status.FAILED):
            errors.append(_("A grade may only be recorded for a passed or failed Course."))

        difficulty_raw = request.POST.get(f"difficulty_{entry.id}", Difficulty.NORMAL)
        try:
            difficulty = Difficulty(difficulty_raw)
        except ValueError:
            difficulty = Difficulty.NORMAL

        slot_code = request.POST.get(f"slot_code_{entry.id}", "").strip()
        slot_name = request.POST.get(f"slot_name_{entry.id}", "").strip()
        if entry.course is None and bool(slot_code) != bool(slot_name):
            errors.append(_("A Slot needs both a código and a name, or neither."))

        parsed.append(
            {
                "entry": entry,
                "status": status,
                "grade": grade,
                "difficulty": difficulty,
                "slot_code": slot_code,
                "slot_name": slot_name,
            }
        )

    current_term = Term.objects.filter(program=plan.program).order_by("-start_date").first()
    any_in_progress = any(p["status"] == Status.IN_PROGRESS for p in parsed)

    new_term_dates = None
    if any_in_progress and current_term is None:
        term_start_raw = request.POST.get("term_start", "").strip()
        term_end_raw = request.POST.get("term_end", "").strip()
        if not term_start_raw or not term_end_raw:
            errors.append(
                _("Marking a Course in progress needs this term's start and end dates.")
            )
        else:
            try:
                new_term_dates = (
                    datetime.date.fromisoformat(term_start_raw),
                    datetime.date.fromisoformat(term_end_raw),
                )
            except ValueError:
                errors.append(_("Term dates must be valid dates."))

    if errors:
        return errors

    with transaction.atomic():
        term = current_term
        if any_in_progress and term is None:
            term = Term.objects.create(
                program=plan.program,
                start_date=new_term_dates[0],
                end_date=new_term_dates[1],
            )

        for p in parsed:
            entry = p["entry"]
            course = entry.course

            if course is None and p["slot_code"] and p["slot_name"]:
                # Matches by código rather than duplicating, same reconciliation
                # rule loadplan applies to the catalog (ADR-0009).
                course, _created = Course.objects.get_or_create(
                    institution=plan.program.institution,
                    code=p["slot_code"],
                    defaults={"name": p["slot_name"], "credits": entry.credits},
                )
                entry.course = course
                entry.save(update_fields=["course"])

            if course is None:
                continue  # Slot left unfilled — nothing else to write.

            CourseStatus.objects.update_or_create(
                course=course, defaults={"status": p["status"], "final_grade": p["grade"]}
            )

            if p["status"] == Status.IN_PROGRESS:
                Enrollment.objects.update_or_create(
                    term=term,
                    course=course,
                    defaults={"outcome": Outcome.IN_PROGRESS, "difficulty": p["difficulty"]},
                )

    return []
