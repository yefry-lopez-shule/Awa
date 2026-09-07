"""Views for the studying app: the input surfaces the student actually
touches (onboarding, quick log, course detail, cuatrimestre setup).
"""

import datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from curriculum.models import AppSettings, BlockEntry, Course
from planning.forecast import forecast
from planning.recommendation import current_term

from .models import (
    STATUSES_COUNTING_CREDITS,
    CourseStatus,
    Difficulty,
    Enrollment,
    GradedItem,
    Outcome,
    Status,
    StudyLog,
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


def quick_log(request):
    """Quick log (#16, scope.md §5 screen 3): Course + hours + an optional
    "left off" note. Reached in one tap from the dashboard banner with the
    recommended Course pre-selected (`?course=<id>`), so the nightly path is
    read the banner, study, log — no Course picker to work through.

    The page also lists this Term's recent Study Logs, each editable in place
    with a delete box: `studied_on` is what Hours Behind sums over the rolling
    window, so a session recorded on the wrong day has to be fixable. Every
    edit and deletion lands in the next ranking — nothing here is cached.

    `recorded_at` is set once by the model and never shown for editing: it is
    what the Streak and staleness measure, and a backdated `studied_on` must
    not be able to repair either (ADR-0006).
    """

    plan = AppSettings.load().active_plan
    term = current_term(plan)
    if term is None:
        return render(request, "studying/quick_log.html", {"term": None})

    enrollments = list(
        term.enrollments.filter(outcome=Outcome.IN_PROGRESS)
        .select_related("course")
        .order_by("course__code")
    )

    errors = []
    if request.method == "POST":
        errors = _save_study_logs(request, enrollments)
        if not errors:
            messages.success(request, _("Logged."))
            return redirect("studying:quick_log")

    logs = list(
        StudyLog.objects.filter(enrollment__term=term)
        .select_related("enrollment__course")[:20]
    )

    context = {
        "term": term,
        "enrollments": enrollments,
        "logs": logs,
        "preselected_course_id": request.GET.get("course", ""),
        "today": timezone.localdate(),
    }
    if errors:
        context["errors"] = errors
    return render(request, "studying/quick_log.html", context)


def _submitted_log_rows(request):
    """Existing logs come back as `log_<id>_*`; the new session as `new_log_*`."""

    rows = []
    ids = set()
    for key in request.POST:
        if key.startswith("log_") and key.endswith("_hours"):
            ids.add(key[len("log_") : -len("_hours")])
    for log_id in ids:
        prefix = f"log_{log_id}_"
        rows.append(
            {
                "id": log_id,
                "course_raw": None,  # an existing log's Course is not reassigned here
                "hours_raw": request.POST.get(f"{prefix}hours", "").strip(),
                "studied_raw": request.POST.get(f"{prefix}studied_on", "").strip(),
                "note": request.POST.get(f"{prefix}note", "").strip(),
                "delete": bool(request.POST.get(f"{prefix}delete")),
            }
        )
    rows.append(
        {
            "id": None,
            "course_raw": request.POST.get("new_log_course", "").strip(),
            "hours_raw": request.POST.get("new_log_hours", "").strip(),
            "studied_raw": request.POST.get("new_log_studied_on", "").strip(),
            "note": request.POST.get("new_log_note", "").strip(),
            "delete": False,
        }
    )
    return rows


def _save_study_logs(request, enrollments):
    """Reconcile the submitted rows against this Term's Study Logs. Nothing is
    written unless the whole submission is valid (the Course detail grid rule).
    """

    enrollment_by_course = {str(e.course_id): e for e in enrollments}
    rows = _submitted_log_rows(request)
    log_ids = {r["id"] for r in rows if r["id"]}
    existing = {
        str(log.id): log
        for log in StudyLog.objects.filter(
            id__in=log_ids, enrollment__in=enrollments
        )
    }

    errors = []
    to_create = []
    to_update = []
    to_delete = []

    for row in rows:
        if row["id"] is None:
            if not any((row["course_raw"], row["hours_raw"], row["studied_raw"], row["note"])):
                continue  # the new-session row left untouched
            enrollment = enrollment_by_course.get(row["course_raw"])
            if enrollment is None:
                errors.append(_("Choose a Course you are enrolled in this Term."))
                continue
            if not row["studied_raw"]:
                row["studied_raw"] = timezone.localdate().isoformat()  # defaults to today
        else:
            log = existing.get(row["id"])
            if log is None:
                continue  # a row for a log that is not this Term's — ignore
            if row["delete"]:
                to_delete.append(log)
                continue
            enrollment = log.enrollment

        hours = _parse_hours(row["hours_raw"], errors)
        studied_on = _parse_studied_on(row["studied_raw"], errors)
        if hours is None or studied_on is None:
            continue

        if row["id"] is None:
            to_create.append(
                StudyLog(
                    enrollment=enrollment,
                    hours=hours,
                    note=row["note"],
                    studied_on=studied_on,
                )
            )
        else:
            log = existing[row["id"]]
            log.hours = hours
            log.studied_on = studied_on
            log.note = row["note"]
            to_update.append(log)

    if errors:
        return errors

    with transaction.atomic():
        for log in to_delete:
            log.delete()
        for log in to_update:
            log.save(update_fields=["hours", "studied_on", "note"])
        StudyLog.objects.bulk_create(to_create)
    return []


def _parse_hours(raw, errors):
    try:
        hours = float(raw)
    except ValueError:
        errors.append(_("Hours must be a number."))
        return None
    if hours <= 0:
        errors.append(_("Hours must be greater than zero."))
        return None
    return hours


def _parse_studied_on(raw, errors):
    if not raw:
        errors.append(_("A Study Log needs the date you studied."))
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        errors.append(_("The date studied must be a valid date."))
        return None


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
        # #4 leaves a Course with an active Enrollment but no Graded Items
        # yet (its deadlines grid unfilled) out of scope for forecasting —
        # there is nothing to forecast from.
        if items:
            context["forecast"] = forecast(
                items, program.pass_mark, program.grade_scale_max
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


# ---------------------------------------------------------------------------
# Cuatrimestre setup (#17, scope.md §5 screen 5)
# ---------------------------------------------------------------------------

DEADLINE_EXTRA_ROWS = 2


def cuatrimestre_setup(request):
    """The recurring Cuatrimestre setup flow (#17, scope.md §5 screen 5).

    Step one gates the rest: while the most recent Term still has an
    in-progress Enrollment, the page shows only term closeout — each closing
    Enrollment with an Outcome derived from its weighted grade against
    ``pass_mark`` (``forecast().weighted_so_far``), which the student confirms
    or overrides. The Status that rides off that Outcome is never written
    silently (ADR-0010), and closing a passing Course unlocks the
    prerequisites it satisfies for the enrol list further down.

    Once the last Term is closed (or none was ever opened) the page becomes
    the new-Term form: dates, enrol + Difficulty ticked straight off the
    seeded Plan with no typing, and a deadlines grid per enrolled Course
    pre-filled from the Program's ``default_items`` — every row editable and
    removable, new rows addable, weights validated to sum to
    ``grade_scale_max`` exactly as the Course detail grid does.
    """

    plan = AppSettings.load().active_plan
    if plan is None:
        return render(request, "studying/cuatrimestre_setup.html", {"plan": None})

    program = plan.program
    last_term = Term.objects.filter(program=program).order_by("-start_date").first()
    unclosed = (
        list(
            last_term.enrollments.filter(outcome=Outcome.IN_PROGRESS)
            .select_related("course")
            .prefetch_related("graded_items")
            .order_by("course__code")
        )
        if last_term is not None
        else []
    )

    if unclosed:
        errors = []
        if request.method == "POST":
            errors = _close_last_term(request, unclosed, program)
            if not errors:
                messages.success(request, _("Last Term closed."))
                return redirect("studying:cuatrimestre_setup")
        context = {
            "plan": plan,
            "step": "closeout",
            "last_term": last_term,
            "closeout_rows": [_closeout_row(e, program) for e in unclosed],
        }
        if errors:
            context["errors"] = errors
        return render(request, "studying/cuatrimestre_setup.html", context)

    eligible = _eligible_entries(plan)
    errors = []
    if request.method == "POST":
        errors = _open_new_term(request, plan, eligible)
        if not errors:
            messages.success(request, _("Cuatrimestre set up."))
            return redirect("planning:dashboard")

    default_rows = list(program.default_items) + [{} for _ in range(DEADLINE_EXTRA_ROWS)]
    context = {
        "plan": plan,
        "step": "new_term",
        "last_term": last_term,
        "item_types": program.item_types,
        "grade_scale_max": program.grade_scale_max,
        "enrol_rows": [
            {
                "course": entry.course,
                "credits": entry.credits,
                "deadline_rows": list(enumerate(default_rows)),
            }
            for entry in eligible
        ],
    }
    if errors:
        context["errors"] = errors
    return render(request, "studying/cuatrimestre_setup.html", context)


def _closeout_row(enrollment, program):
    """One closing Enrollment: its weighted grade so far and the Outcome that
    derives from it against ``pass_mark`` (scope.md §5 step 1).
    """

    fc = forecast(
        list(enrollment.graded_items.all()), program.pass_mark, program.grade_scale_max
    )
    derived = (
        Outcome.PASSED if fc.weighted_so_far >= program.pass_mark else Outcome.FAILED
    )
    return {
        "enrollment": enrollment,
        "course": enrollment.course,
        "weighted_so_far": fc.weighted_so_far,
        "grade_so_far": fc.grade_so_far,
        "derived": derived,
    }


def _close_last_term(request, unclosed, program):
    """Write each closing Enrollment's Outcome and update its Course's Status
    from it. Confirmation is the whole point — a submitted Outcome, derived or
    overridden, is what gets written; nothing is silent (ADR-0010).
    """

    parsed = []
    errors = []
    for enrollment in unclosed:
        raw = request.POST.get(f"outcome_{enrollment.id}", "").strip()
        try:
            outcome = Outcome(raw)
        except ValueError:
            errors.append(_("Choose passed or failed for every closing Course."))
            continue
        if outcome == Outcome.IN_PROGRESS:
            errors.append(_("A closing Course is either passed or failed."))
            continue
        parsed.append((enrollment, outcome))

    if errors:
        return errors

    with transaction.atomic():
        for enrollment, outcome in parsed:
            enrollment.outcome = outcome
            enrollment.save(update_fields=["outcome"])
            fc = forecast(
                list(enrollment.graded_items.all()),
                program.pass_mark,
                program.grade_scale_max,
            )
            CourseStatus.objects.update_or_create(
                course=enrollment.course,
                defaults={
                    "status": Status.PASSED if outcome == Outcome.PASSED else Status.FAILED,
                    # The weighted grade rides along as the historical grade so
                    # it survives the Enrollment leaving the live forecast.
                    "final_grade": (
                        fc.weighted_so_far if fc.grade_so_far is not None else None
                    ),
                },
            )
    return []


def _eligible_entries(plan):
    """Named BlockEntries the student could enrol in this Term: Course not
    already passed or transferred, and every prerequisite in the Plan
    satisfied. A failed Course reappears here — a retake is a fresh Enrollment
    (ADR-0010).
    """

    entries = (
        BlockEntry.objects.filter(block__plan=plan, course__isnull=False)
        .select_related("course", "course__status_record", "block")
        .order_by("block__name", "course__code")
    )
    return [
        entry
        for entry in entries
        if status_for_course(entry.course) not in STATUSES_COUNTING_CREDITS
        and is_unlocked(entry.course, plan)
    ]


def _open_new_term(request, plan, eligible):
    """Create the new Term, its Enrollments (with Difficulty) and each one's
    Graded Items from the submitted deadlines grid. All-or-nothing: one bad
    weight sum and nothing is written (scope.md §5 step 4).
    """

    program = plan.program
    errors = []

    start = _parse_term_date(request.POST.get("term_start", "").strip(), errors, _("a start date"))
    end = _parse_term_date(request.POST.get("term_end", "").strip(), errors, _("an end date"))
    if start is not None and end is not None and start >= end:
        errors.append(_("The Term's start date must come before its end date."))

    enrolments = []
    for entry in eligible:
        course = entry.course
        if not request.POST.get(f"enrol_{course.id}"):
            continue
        try:
            difficulty = Difficulty(
                request.POST.get(f"difficulty_{course.id}", Difficulty.NORMAL)
            )
        except ValueError:
            difficulty = Difficulty.NORMAL
        items = _parse_deadline_grid(request, course, program, errors)
        enrolments.append((course, difficulty, items))

    if not enrolments:
        errors.append(_("Tick at least one Course to enrol in."))

    if errors:
        return errors

    with transaction.atomic():
        term = Term.objects.create(program=program, start_date=start, end_date=end)
        for course, difficulty, items in enrolments:
            enrollment = Enrollment.objects.create(
                term=term,
                course=course,
                outcome=Outcome.IN_PROGRESS,
                difficulty=difficulty,
            )
            CourseStatus.objects.update_or_create(
                course=course,
                defaults={"status": Status.IN_PROGRESS, "final_grade": None},
            )
            GradedItem.objects.bulk_create(
                GradedItem(
                    enrollment=enrollment,
                    type=item["type"],
                    weight=item["weight"],
                    due_at=item["due_at"],
                )
                for item in items
            )
    return []


def _parse_term_date(raw, errors, label):
    if not raw:
        errors.append(_("The Term needs %(label)s.") % {"label": label})
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        errors.append(_("The Term's dates must be valid dates."))
        return None


def _parse_deadline_grid(request, course, program, errors):
    """The deadlines grid for one enrolled Course: rows keyed
    ``deadline_<course id>_<row>_*``. Same shape and the same weight rule as
    the Course detail grid — a non-empty grid whose weights don't sum to
    ``grade_scale_max`` is reported and the whole setup is refused.
    """

    valid_types = set(program.item_types)
    prefix = f"deadline_{course.id}_"
    row_keys = sorted(
        key[len(prefix) : -len("_type")]
        for key in request.POST
        if key.startswith(prefix) and key.endswith("_type")
    )

    rows = []
    for row in row_keys:
        base = f"{prefix}{row}_"
        if request.POST.get(f"{base}delete"):
            continue
        type_ = request.POST.get(f"{base}type", "").strip()
        weight_raw = request.POST.get(f"{base}weight", "").strip()
        due_raw = request.POST.get(f"{base}due", "").strip()
        if not any((type_, weight_raw, due_raw)):
            continue

        if type_ not in valid_types:
            errors.append(_("Choose an item type from the Program's list."))
            continue
        try:
            weight = float(weight_raw)
        except ValueError:
            errors.append(_("A weight must be a number."))
            continue
        if weight <= 0:
            errors.append(_("A weight must be greater than zero."))
            continue
        due_at = None
        if due_raw:
            try:
                due_at = datetime.date.fromisoformat(due_raw)
            except ValueError:
                errors.append(_("A due date must be a valid date."))
                continue
        rows.append({"type": type_, "weight": weight, "due_at": due_at})

    total = sum(row["weight"] for row in rows)
    if rows and round(total - program.grade_scale_max, 6) != 0:
        errors.append(
            _("Weights for %(code)s must sum to %(max)s; they sum to %(total)s.")
            % {
                "code": course.code,
                "max": program.grade_scale_max,
                "total": "{:g}".format(total),
            }
        )
    return rows
