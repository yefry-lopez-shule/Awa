"""The reference view: the self-study roadmap, grouped and read-only.

ADR-0006 — roadmap entries are never studied, scheduled, or recommended.
This module has no write path anywhere: no forms, no POST handling, no
model saves. Coverage rolls up live off each linked Course's Status
(ADR-0012), so real progress moves the view with no re-import.
"""

from itertools import groupby

from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import RoadmapEntry


@require_GET
def roadmap(request):
    """Every Roadmap Entry, grouped by university then category, each with
    its rolled-up coverage and per-link standing."""

    entries = (
        RoadmapEntry.objects.prefetch_related("links__course__status_record")
        .all()
    )

    universities = []
    for university, uni_entries in groupby(entries, key=lambda e: e.university):
        categories = []
        for category, cat_entries in groupby(uni_entries, key=lambda e: e.category):
            categories.append(
                {
                    "name": category,
                    "entries": [_entry_row(entry) for entry in cat_entries],
                }
            )
        universities.append({"name": university, "categories": categories})

    return render(request, "reference/roadmap.html", {"universities": universities})


def _entry_row(entry):
    return {
        "entry": entry,
        "coverage": entry.coverage(),
        "links": [
            {
                "link": link,
                "status": link.effective_status(),
                "satisfied": link.is_satisfied(),
                "frozen": link.course_id is None,
            }
            for link in entry.links.all()
        ],
    }
