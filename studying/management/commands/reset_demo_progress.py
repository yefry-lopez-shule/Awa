"""`manage.py reset_demo_progress` — wipe all student-entered progress back
to a blank slate, leaving the curriculum untouched (#42, #44).

Clears every row of Term, Enrollment, GradedItem, StudyLog, CourseStatus
(this app) and AvailabilityBlock, StudyWindow (`planning`) in one atomic
transaction. Institution, Program, Plan, Block, BlockEntry, Course,
Prerequisite, the roadmap reference data, and `AppSettings.active_plan` are
never touched. Safe to re-run against an already-empty progress state — it
is a no-op, not an error.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from planning.models import AvailabilityBlock, StudyWindow
from studying.models import CourseStatus, Enrollment, GradedItem, StudyLog, Term


class Command(BaseCommand):
    help = (
        "Wipe tracked progress (Terms, Enrollments, grades, logs, availability) "
        "back to a blank demo slate. The curriculum and active Plan are untouched."
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            counts = {
                "Study Log": StudyLog.objects.count(),
                "Graded Item": GradedItem.objects.count(),
                "Enrollment": Enrollment.objects.count(),
                "Term": Term.objects.count(),
                "Course Status": CourseStatus.objects.count(),
                "Availability Block": AvailabilityBlock.objects.count(),
                "Study Window": StudyWindow.objects.count(),
            }
            StudyLog.objects.all().delete()
            GradedItem.objects.all().delete()
            Enrollment.objects.all().delete()
            Term.objects.all().delete()
            CourseStatus.objects.all().delete()
            AvailabilityBlock.objects.all().delete()
            StudyWindow.objects.all().delete()

        summary = ", ".join(f"{label}: {count}" for label, count in counts.items())
        self.stdout.write(self.style.SUCCESS(f"Cleared progress — {summary}"))
