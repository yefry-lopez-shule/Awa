"""Tests for `parse_grid` (#49, #50): the shared editable-grid row parser.

Pure function, no Django `request`/ORM in its signature — tested directly
against plain dict fixtures standing in for `request.POST`/`QueryDict`.
"""

from django.http import QueryDict
from django.test import SimpleTestCase

from .grids import parse_grid


class ParseGridExistingRowsTests(SimpleTestCase):
    def test_existing_row_with_all_fields_present(self):
        data = {
            "log_7_hours": "2.5",
            "log_7_studied_on": "2026-09-10",
            "log_7_note": "read chapter 3",
        }
        rows, new_row = parse_grid(
            data, "log_", ["hours", "studied_on", "note"]
        )

        self.assertEqual(
            rows,
            [
                {
                    "id": "7",
                    "hours": "2.5",
                    "studied_on": "2026-09-10",
                    "note": "read chapter 3",
                }
            ],
        )
        self.assertIsNone(new_row)

    def test_existing_row_with_some_fields_blank(self):
        data = {
            "item_3_type": "quiz",
            "item_3_weight": "10",
            "item_3_due": "",
            "item_3_grade": "",
        }
        rows, _ = parse_grid(data, "item_", ["type", "weight", "due", "grade"])

        self.assertEqual(
            rows,
            [{"id": "3", "type": "quiz", "weight": "10", "due": "", "grade": ""}],
        )

    def test_rows_returned_in_deterministic_order_regardless_of_submission_order(self):
        data = {
            "block_10_weekday": "1",
            "block_10_label": "gym",
            "block_2_weekday": "3",
            "block_2_label": "work",
        }
        rows, _ = parse_grid(data, "block_", ["weekday", "label"])

        self.assertEqual([row["id"] for row in rows], ["2", "10"])

    def test_existing_row_is_not_dropped_when_every_field_is_blank(self):
        # Unlike the new-row slot, an existing row is never silently
        # dropped for arriving blank — it's addressed by a real id, and a
        # screen must get the chance to reject blanking it out as invalid
        # rather than have it vanish.
        data = {"log_7_hours": "", "log_7_studied_on": "", "log_7_note": ""}
        rows, _ = parse_grid(data, "log_", ["hours", "studied_on", "note"])

        self.assertEqual(
            rows, [{"id": "7", "hours": "", "studied_on": "", "note": ""}]
        )

    def test_field_values_are_stripped_of_surrounding_whitespace(self):
        data = {"log_7_hours": "  2.5  ", "log_7_studied_on": "2026-09-10\n", "log_7_note": " "}
        rows, _ = parse_grid(data, "log_", ["hours", "studied_on", "note"])

        self.assertEqual(
            rows, [{"id": "7", "hours": "2.5", "studied_on": "2026-09-10", "note": ""}]
        )


class ParseGridNewRowTests(SimpleTestCase):
    def test_no_new_row_looked_for_when_new_prefix_omitted(self):
        # The deadlines grid's shape: every row is create-only, addressed by
        # a plain index, no distinguished "new" slot.
        data = {"deadline_9_0_type": "quiz", "deadline_9_0_weight": "20"}
        rows, new_row = parse_grid(data, "deadline_9_", ["type", "weight"])

        self.assertEqual(rows, [{"id": "0", "type": "quiz", "weight": "20"}])
        self.assertIsNone(new_row)

    def test_fully_blank_new_row_is_dropped(self):
        data = {"new_log_hours": "", "new_log_studied_on": "", "new_log_note": ""}
        rows, new_row = parse_grid(
            data, "log_", ["hours", "studied_on", "note"], new_prefix="new_log"
        )

        self.assertEqual(rows, [])
        self.assertIsNone(new_row)

    def test_whitespace_only_new_row_is_treated_as_blank_and_dropped(self):
        data = {"new_log_hours": "  ", "new_log_studied_on": "\t", "new_log_note": ""}
        rows, new_row = parse_grid(
            data, "log_", ["hours", "studied_on", "note"], new_prefix="new_log"
        )

        self.assertEqual(rows, [])
        self.assertIsNone(new_row)

    def test_partially_filled_new_row_is_kept(self):
        data = {"new_log_hours": "1.5", "new_log_studied_on": "", "new_log_note": ""}
        rows, new_row = parse_grid(
            data, "log_", ["hours", "studied_on", "note"], new_prefix="new_log"
        )

        self.assertEqual(rows, [])
        self.assertEqual(
            new_row, {"hours": "1.5", "studied_on": "", "note": ""}
        )


class ParseGridQueryDictTests(SimpleTestCase):
    def test_works_against_a_real_querydict_like_request_post(self):
        data = QueryDict(
            "log_7_hours=2.5&log_7_studied_on=2026-09-10&log_7_note=&"
            "new_log_hours=&new_log_studied_on=&new_log_note="
        )
        rows, new_row = parse_grid(
            data, "log_", ["hours", "studied_on", "note"], new_prefix="new_log"
        )

        self.assertEqual(
            rows,
            [{"id": "7", "hours": "2.5", "studied_on": "2026-09-10", "note": ""}],
        )
        self.assertIsNone(new_row)
