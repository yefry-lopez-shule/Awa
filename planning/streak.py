"""The Streak: consecutive days the student has fed the app a Study Log.

CONTEXT.md: "Consecutive days on which any Study Log was recorded. Measures
whether the student is still feeding the app, not whether they are learning."
ADR-0006 kept the Streak — redefined off any logged study — precisely because
it does useful work as an alarm for logging going stale.

It reads `recorded_at` only, never `studied_on` (scope.md §5). A session
entered late still counts for the day it was *entered*, so logging tonight
always extends the Streak; but back-dating a `studied_on` cannot reach back
and repair a day that went by with nothing recorded. That is what keeps the
Streak an alarm rather than something that can be filled in after the fact
(scope.md Risk 1).
"""

import datetime

from django.utils import timezone

from studying.models import StudyLog


def current_streak(term, today):
    """The number of consecutive days ending `today` on which at least one
    Study Log for `term` was recorded. 0 when nothing was recorded today —
    the run is already broken.
    """

    recorded_days = {
        timezone.localtime(recorded_at).date()
        for recorded_at in StudyLog.objects.filter(
            enrollment__term=term
        ).values_list("recorded_at", flat=True)
    }

    streak = 0
    day = today
    while day in recorded_days:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak
