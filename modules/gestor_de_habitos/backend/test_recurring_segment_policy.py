"""Regresión pura de SIMPLE/CUSTOM sin credenciales de PostgreSQL."""

from datetime import date, datetime, time
import unittest
from uuid import UUID

from recurring_segment_policy import (
    RecurringSegmentError,
    is_simple_occurrence,
    transform_recurring_segments,
)


NOW = datetime(2026, 9, 21, 18, 0)
DAY = date(2026, 9, 21)


def parent(start="08:00", end="12:00"):
    return {
        "occurrence_date": DAY,
        "start_time": time.fromisoformat(start),
        "end_time": time.fromisoformat(end),
    }


def segment(number, start, end, status="pending"):
    return {
        "id": UUID(f"00000000-0000-4000-8000-{number:012d}"),
        "startTime": time.fromisoformat(start),
        "endTime": time.fromisoformat(end),
        "status": status,
    }


class RecurringSegmentPolicyTests(unittest.TestCase):
    def test_only_one_full_envelope_segment_is_simple(self):
        source = parent()
        self.assertTrue(is_simple_occurrence(source, [segment(1, "08:00", "12:00")]))
        self.assertFalse(is_simple_occurrence(source, [segment(1, "08:30", "12:00")]))
        self.assertFalse(is_simple_occurrence(source, [
            segment(1, "08:00", "09:00"), segment(2, "10:00", "12:00"),
        ]))

    def test_simple_resize_preserves_id_and_status(self):
        source = parent("08:00", "09:00")
        original = segment(1, "08:00", "09:00", "completed")
        result, aggregate = transform_recurring_segments(
            source, [original], parent("10:00", "11:30"), NOW
        )
        self.assertEqual(result, [{**original, "startTime": time(10), "endTime": time(11, 30)}])
        self.assertEqual(aggregate, "completed")
        self.assertEqual(original["startTime"], time(8))

    def test_custom_translation_preserves_ids_statuses_and_gap(self):
        original = [segment(1, "08:00", "09:00", "completed"), segment(2, "10:30", "12:00")]
        moved, aggregate = transform_recurring_segments(parent(), original, parent("13:00", "17:00"), NOW)
        self.assertEqual([(row["id"], row["startTime"], row["endTime"], row["status"]) for row in moved], [
            (original[0]["id"], time(13), time(14), "completed"),
            (original[1]["id"], time(15, 30), time(17), "pending"),
        ])
        self.assertEqual(aggregate, "in_progress")

    def test_custom_resize_and_date_move_reject_without_mutation(self):
        original = [segment(1, "08:00", "09:00"), segment(2, "10:00", "12:00")]
        with self.assertRaises(RecurringSegmentError) as resize:
            transform_recurring_segments(parent(), original, parent("08:00", "11:00"), NOW)
        self.assertEqual(resize.exception.code, "segmented_recurring_resize_requires_resolution")
        with self.assertRaises(RecurringSegmentError) as date_move:
            transform_recurring_segments(parent(), original, {**parent(), "occurrence_date": date(2026, 9, 22)}, NOW)
        self.assertEqual(date_move.exception.code, "segmented_recurring_date_move_requires_resolution")
        self.assertEqual(original[0]["startTime"], time(8))

    def test_completed_future_and_yesterday_transient_reject(self):
        with self.assertRaises(RecurringSegmentError) as future_completed:
            transform_recurring_segments(
                parent("08:00", "09:00"), [segment(1, "08:00", "09:00", "completed")],
                parent("18:30", "19:30"), NOW,
            )
        self.assertEqual(future_completed.exception.code, "segment_not_ended")
        yesterday = {**parent(), "occurrence_date": date(2026, 9, 20)}
        with self.assertRaises(RecurringSegmentError) as reconciliation:
            transform_recurring_segments(yesterday, [segment(1, "08:00", "12:00")], yesterday, NOW)
        self.assertEqual(reconciliation.exception.code, "temporal_reconciliation_required")

    def test_simple_date_move_and_custom_noop(self):
        source = parent("08:00", "09:00")
        original = segment(1, "08:00", "09:00")
        moved, aggregate = transform_recurring_segments(
            source, [original], {**parent("10:00", "11:00"), "occurrence_date": date(2026, 9, 22)}, NOW,
        )
        self.assertEqual(moved[0]["id"], original["id"])
        self.assertEqual(moved[0]["status"], "pending")
        self.assertEqual((moved[0]["startTime"], moved[0]["endTime"]), (time(10), time(11)))
        self.assertEqual(aggregate, "pending")

        custom = [segment(2, "08:00", "08:30"), segment(3, "08:45", "09:00")]
        unchanged, _aggregate = transform_recurring_segments(source, custom, source, NOW)
        self.assertEqual(unchanged, custom)
        self.assertIsNot(unchanged, custom)

    def test_one_trimmed_child_is_custom_and_translates_without_reset(self):
        source = parent("08:00", "10:00")
        trimmed = segment(1, "08:30", "09:30", "cancelled")
        self.assertFalse(is_simple_occurrence(source, [trimmed]))
        moved, aggregate = transform_recurring_segments(
            source, [trimmed], parent("11:00", "13:00"), NOW
        )
        self.assertEqual(moved, [{**trimmed, "startTime": time(11, 30), "endTime": time(12, 30)}])
        self.assertEqual(aggregate, "cancelled")

    def test_frozen_history_rejects_structural_change(self):
        frozen = {**parent("08:00", "09:00"), "occurrence_date": date(2026, 9, 1)}
        with self.assertRaises(RecurringSegmentError) as raised:
            transform_recurring_segments(
                frozen, [segment(1, "08:00", "09:00", "completed")],
                {**frozen, "start_time": time(10), "end_time": time(11)}, NOW,
            )
        self.assertEqual(raised.exception.code, "history_frozen")


if __name__ == "__main__":
    unittest.main()
