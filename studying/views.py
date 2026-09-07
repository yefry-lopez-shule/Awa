"""Views for the studying app: the input surfaces the student actually
touches (onboarding, quick log, course detail, cuatrimestre setup).
"""

import datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from curriculum.models import AppSettings, BlockEntry, Course

from .models import CourseStatus, Difficulty, Enrollment, Outcome, Status, Term, status_for_course
from .queries import is_unlocked


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
