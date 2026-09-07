# score() is difficulty × a weighted sum, not a product

The original scope stated `score = hours_behind × difficulty × deadline_pressure`
while the config table shipped `w_hours_behind` and `w_deadline` — two weights
that change no ordering whatsoever on a product. The product also failed at the
bottom of its range twice over: a Course sitting exactly on its Ration scored zero
no matter what was due, and a Course that was *ahead* had its score pushed further
down by an approaching exam, so Deadline Pressure ran backwards.

The score is now `difficulty × (w_hours_behind × behind + w_deadline × pressure)`,
with Hours Behind floored at zero. Supersedes locked decision 5.

## Consequences

- `w_deadline` becomes a unit conversion, and that is the only reason it has a
  defensible value: it reads as *how many hours of neglect a full-weight item due
  today is worth*, and is set to **20** — about one Ration. At the originally
  shipped 1.0 a 40% final due tomorrow moved the score less than three extra
  minutes of neglect, and `deadline_half_life_days` could never have changed an
  outcome.
- Difficulty still appears twice — once raising the Ration, once multiplying the
  whole score — so ADR-0004 holds unchanged. Normalising to Capacity did sharpen
  it: a `hard` flag is now zero-sum, taking hours from other Courses rather than
  inflating the week, so the burying it warns about is visibly at another Course's
  expense.
- Deadline Pressure can now lift a Course but never suppress one, which is what
  lets a heavy exam surface several days out instead of on the last day.
- Pressure is forward-looking only. Nothing past its due date contributes, because
  studying tonight cannot change it — and because the decay term grows explosively
  on negative inputs (an item two months overdue would score 382×). Unscored past
  items belong to the pass forecast and Course detail, not to the ranking. The
  alternative was tracking submission per item, which is the task list that locked
  decision 2 rejected, arriving through the back door.
- The Override Window is still required, and is not redundant with a larger
  `w_deadline`. Pressure is bounded by 1 while Hours Behind runs to a full Ration,
  so a badly-neglected hard Course outranks a heavy exam right up until the window
  fires. The window gained a weight floor (`override_min_weight`, 10%) so that a
  2% quiz due tomorrow no longer displaces a 40% parcial due in three days.

## Considered Options

Flooring Hours Behind at zero while keeping the product was the minimal change and
would have preserved decision 5 word-for-word, but it fixes only the inversion —
an on-target Course with an exam four days out still scores exactly zero. Flooring
at a small positive baseline keeps the product alive at the cost of a fudge factor
with no domain meaning and a reason string that cannot be written honestly. A
fully normalised weighted sum, with difficulty as a third weighted term, is the
conventional choice and was rejected because it breaks ADR-0004 outright.
