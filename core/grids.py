"""`parse_grid`: the row-extraction step shared by every editable grid in
Awá (#49, #50) — quick log's Study Logs, course detail's Graded Items,
cuatrimestre setup's deadlines grid, the availability template's
Availability Blocks.

Pure: no Django `request`, no ORM. `data` is anything supporting `.get()`
(a plain dict or a `QueryDict`), standing in for `request.POST`. Everything
downstream of parsing — field validation, defaulting, and how a row gets
reconciled against the database — stays with the caller; this module only
turns POST keys into row dicts.
"""


def parse_grid(data, prefix, fields, *, anchor=None, new_prefix=None):
    """Extract a grid's rows from `data`.

    Returns `(rows, new_row)`. Every call site imports Django's `gettext`
    as `_` — never unpack this into a bare `_` (`rows, _ = parse_grid(...)`
    or `_, new_row = parse_grid(...)`): it shadows that alias for the rest
    of the enclosing function, and the next `_("...")` call crashes trying
    to call `None`. Name the discarded half instead (`_new_row`, `_rows`).

    Existing rows are addressed as `<prefix><row-key>_<field>` for each name
    in `fields`. Row keys are discovered by scanning for `anchor` (the first
    field in `fields`, unless given explicitly) so field names that contain
    underscores of their own don't get mis-split. Returned rows carry every
    requested field's raw string value — stripped of surrounding whitespace,
    the one normalization every caller already applied by hand — plus their
    `id`, sorted numerically by row-key for a deterministic order.

    When `new_prefix` is given, a trailing new row is read from
    `<new_prefix>_<field>` and returned as a plain dict with no `id` — or
    `None` when every one of its fields is blank (an untouched "new row"
    slot). No new row is looked for at all when `new_prefix` is omitted.

    Existing rows are never dropped for being blank, even when every field
    on one comes back empty: unlike the new-row slot, an existing row is
    addressed by a real `id`, and a screen that lets the student blank out
    a saved row's fields needs the chance to reject that as invalid rather
    than have it silently disappear.
    """

    anchor = anchor or fields[0]
    anchor_suffix = f"_{anchor}"

    row_keys = sorted(
        (
            key[len(prefix) : -len(anchor_suffix)]
            for key in data.keys()
            if key.startswith(prefix) and key.endswith(anchor_suffix)
        ),
        key=int,
    )

    rows = [
        {
            "id": row_key,
            **{
                field: data.get(f"{prefix}{row_key}_{field}", "").strip()
                for field in fields
            },
        }
        for row_key in row_keys
    ]

    new_row = None
    if new_prefix is not None:
        candidate = {
            field: data.get(f"{new_prefix}_{field}", "").strip() for field in fields
        }
        if any(candidate.values()):
            new_row = candidate

    return rows, new_row
