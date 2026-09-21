"""Pruebas puras del batch recurrente y sus intervals reales."""

from datetime import date, datetime, time
import unittest
from unittest.mock import patch
from uuid import UUID

import recurring_segment_service as service


DAY = date(2026, 9, 22)
NOW = datetime(2026, 9, 21, 12)


def identifier(number):
    return UUID(f"00000000-0000-4000-8000-{number:012d}")


def occurrence(number, start="08:00", end="10:00", status="pending"):
    return {
        "id": identifier(number), "plan_item_id": identifier(900 + number),
        "occurrence_date": DAY, "start_time": time.fromisoformat(start),
        "end_time": time.fromisoformat(end), "status": status,
        "source_generation_slot_id": None,
    }


def segment(number, start="08:00", end="10:00", status="pending"):
    return {
        "id": identifier(100 + number), "startTime": time.fromisoformat(start),
        "endTime": time.fromisoformat(end), "status": status,
    }


class RecurringSegmentServiceTests(unittest.TestCase):
    def test_multiple_custom_resizes_return_all_without_mutation(self):
        originals = [occurrence(1), occurrence(2, "11:00", "13:00")]
        graphs = {
            originals[0]["id"]: [segment(1, "08:00", "08:30"), segment(2, "09:00", "10:00")],
            originals[1]["id"]: [segment(3, "11:00", "11:30"), segment(4, "12:00", "13:00")],
        }
        candidates = [{**originals[0], "end_time": time(11)},
                      {**originals[1], "end_time": time(14)}]
        with self.assertRaises(service.RecurringGraphError) as raised:
            service.build_candidate_graphs(originals, candidates, graphs, NOW)
        self.assertEqual(raised.exception.code, "segmented_recurring_resize_requires_resolution")
        self.assertEqual([row["occurrenceId"] for row in raised.exception.occurrences],
                         [str(originals[0]["id"]), str(originals[1]["id"])])
        self.assertEqual(graphs[originals[0]["id"]][0]["endTime"], time(8, 30))

    def test_candidate_self_conflict_reports_both_segments(self):
        rows = [occurrence(1, "08:00", "10:00"), occurrence(2, "09:00", "11:00")]
        graphs = {rows[0]["id"]: [segment(1)], rows[1]["id"]: [segment(2, "09:00", "11:00")]}
        with patch.object(service.recurring_segment_repository, "lock_external_blocking_segments", return_value=[]), \
                self.assertRaises(service.RecurringGraphError) as raised:
            service.validate_batch_conflicts(object(), rows, rows, graphs)
        self.assertEqual(raised.exception.code, "recurring_schedule_conflict")
        self.assertEqual({item["segmentId"] for item in raised.exception.blockers},
                         {str(segment(1)["id"]), str(segment(2)["id"])})

    def test_gap_adjacency_nonblocking_and_batch_exclusion(self):
        rows = [occurrence(1, "08:00", "12:00"), occurrence(2, "09:00", "10:00")]
        graphs = {
            rows[0]["id"]: [segment(1, "08:00", "09:00"), segment(2, "11:00", "12:00")],
            rows[1]["id"]: [segment(3, "09:00", "10:00")],
        }
        external = [{
            "occurrence_id": identifier(50), "plan_item_id": identifier(950),
            "occurrence_date": DAY, "segment_id": identifier(150),
            "start_time": time(10), "end_time": time(11), "status": "pending",
        }]
        with patch.object(service.recurring_segment_repository, "lock_external_blocking_segments", return_value=external) as query:
            service.validate_batch_conflicts(object(), rows, rows, graphs)
        self.assertEqual(query.call_args.args[1], [rows[0]["id"], rows[1]["id"]])

        graphs[rows[1]["id"]] = [segment(3, "09:00", "11:00", "cancelled")]
        with patch.object(service.recurring_segment_repository, "lock_external_blocking_segments", return_value=external):
            service.validate_batch_conflicts(object(), rows, rows, graphs)

    def test_multiple_external_blockers_are_sorted_and_never_modified(self):
        candidate = occurrence(1, "08:00", "12:00")
        graphs = {candidate["id"]: [segment(1, "08:00", "12:00")]}
        blockers = [{
            "occurrence_id": identifier(number), "plan_item_id": identifier(900 + number),
            "occurrence_date": DAY, "segment_id": identifier(100 + number),
            "start_time": time(hour), "end_time": time(hour + 1), "status": "not_finished",
        } for number, hour in [(3, 10), (2, 8)]]
        with patch.object(service.recurring_segment_repository, "lock_external_blocking_segments", return_value=blockers), \
                self.assertRaises(service.RecurringGraphError) as raised:
            service.validate_batch_conflicts(object(), [candidate], [candidate], graphs)
        self.assertEqual([row["startTime"] for row in raised.exception.blockers], ["08:00", "10:00"])
        self.assertEqual(blockers[0]["status"], "not_finished")

    def test_mixed_yesterday_requires_reconciliation_before_recurring_write(self):
        parent = {**occurrence(1), "occurrence_date": date(2026, 9, 20)}
        children = [
            {"id": identifier(101), "occurrence_id": parent["id"],
             "start_time": time(8), "end_time": time(9), "status": "pending"},
            {"id": identifier(102), "occurrence_id": parent["id"],
             "start_time": time(9), "end_time": time(10), "status": "cancelled"},
        ]
        with patch.object(service.occurrence_segment_repository, "lock_segments_for_occurrences", return_value=children), \
                self.assertRaises(service.RecurringGraphError) as raised:
            service.load_segment_graphs(object(), [parent], NOW)
        self.assertEqual(raised.exception.code, "temporal_reconciliation_required")


if __name__ == "__main__":
    unittest.main()
