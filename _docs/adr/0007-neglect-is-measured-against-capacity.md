# Neglect is measured against Capacity, over a rolling week

A Course's Target — `credits × hours_per_credit × difficulty` — is what the Plan
demands, and for this student the Plan demands roughly twice the hours that exist:
Bloque D alone is 17 créditos, or 51 h/week, against a real capacity near 21.
Ranking on demand made every Course permanently behind, so Hours Behind stopped
measuring neglect and started measuring course size — the recommender degenerated
into "the biggest hard course, unless something is due within 48 hours".

Targets are therefore scaled to Capacity to produce a **Ration**
(`target × min(1, capacity / Σ targets)`), and Hours Behind is measured against
the Ration over a **rolling seven-day window** rather than a calendar week.

## Consequences

- Every Course now carries two hour figures. Target is what it demands and is
  never ranked on; Ration is what it gets and is what Hours Behind subtracts from.
  Deleting either one to "simplify" reintroduces the collapse above.
- Target survives precisely because it is unreachable — the gap between Σ Targets
  and Capacity is the overload warning, and scaling everything to fit would have
  silently deleted the app's ability to say "the weeks don't work".
- Ration scales **down only**. When Capacity exceeds demand a Course's Ration is
  its Target; the surplus belongs to the student, not to the ranking.
- The rolling window removes a cliff, not just an inconvenience. Under calendar
  weeks every Monday has zero hours logged against every Course, so the score
  reduces to `credits × difficulty²` — an identical recommendation every Monday of
  the cuatrimestre regardless of the week before, with the signal strongest on
  Sunday when it is too late to act on.
- Capacity and Ration are numerically unchanged by the rolling window, because
  Availability Blocks recur weekly and any trailing seven days contain each
  weekday exactly once. The window cost nothing arithmetically.
- Capacity needed an upper bound to be a real number at all — 168 hours minus
  blocks is around 98 h/week, which would put every Course permanently at zero
  Hours Behind and reduce the engine to a deadline sorter. Hence **Study Window**:
  a per-weekday stretch the student is willing to study within, from which
  Availability Blocks subtract.

## Considered Options

Keeping Targets absolute was the status quo and is what exposed the problem.
Scaling *everything* to Capacity — one concept instead of two — was rejected
because it takes the overload warning with it. Ranking on relative neglect
(share deserved minus share received) is scale-free and would also have worked,
but the decision log had already rejected relative neglect for hour targets, and
it discards the absolute hours the dashboard is built around.
