"""Reglas puras de autorización y sustracción de OccurrenceSegments."""

from datetime import time
import unittest
from uuid import UUID, uuid4

from segment_conflict_domain import (
    SegmentConflictDomainError,
    conflict_reason,
    resolve_target_graph,
    resolve_target_segment,
    same_snapshot,
    subtract_intervals,
)
from segment_conflict_service import SegmentConflictValidationError, validate_confirmations


def clock(hour, minute=0):
    return time(hour, minute)


class SegmentConflictDomainTests(unittest.TestCase):
    def setUp(self):
        self.first_id = uuid4()
        self.segment = {
            "id": self.first_id, "startTime": clock(8), "endTime": clock(12),
            "status": "pending",
        }
        self.parent = {"startTime": clock(8), "endTime": clock(12)}

    def test_authorization_is_backend_classified(self):
        self.assertEqual(conflict_reason(300, 100, "pending"), "priority_override")
        self.assertEqual(conflict_reason(100, 100, "pending"), "user_forced_override")
        self.assertEqual(conflict_reason(100, 300, "pending"), "user_forced_override")
        self.assertEqual(conflict_reason(300, 100, "completed"), "user_forced_override")
        self.assertEqual(conflict_reason(300, 100, "not_finished"), "user_forced_override")

    def test_subtraction_half_open_edges_and_middle(self):
        self.assertEqual(subtract_intervals(clock(8), clock(12), [(clock(9), clock(10))]), [
            (clock(8), clock(9)), (clock(10), clock(12)),
        ])
        self.assertEqual(subtract_intervals(clock(8), clock(12), [(clock(7), clock(9))]), [
            (clock(9), clock(12)),
        ])
        self.assertEqual(subtract_intervals(clock(8), clock(12), [(clock(11), clock(13))]), [
            (clock(8), clock(11)),
        ])
        self.assertEqual(subtract_intervals(clock(8), clock(12), [(clock(8), clock(12))]), [])
        self.assertEqual(subtract_intervals(clock(8), clock(12), [(clock(12), clock(13))]), [
            (clock(8), clock(12)),
        ])

    def test_split_preserves_left_id_and_uses_new_uuid(self):
        before = dict(self.segment)
        result = resolve_target_segment(
            self.segment, [(clock(9), clock(10))], "future", uuid4
        )
        self.assertEqual(result[0]["id"], self.first_id)
        self.assertIsInstance(result[1]["id"], UUID)
        self.assertEqual(result[1]["id"].version, 4)
        self.assertNotEqual(result[1]["id"], self.first_id)
        self.assertEqual(self.segment, before)

    def test_pending_full_coverage_preserves_child_as_cancelled(self):
        result = resolve_target_segment(
            self.segment, [(clock(7), clock(13))], "future", uuid4
        )
        self.assertEqual(result, [{**self.segment, "status": "cancelled"}])
        for realized_status in ("completed", "not_finished"):
            realized = {**self.segment, "status": realized_status}
            self.assertEqual(
                resolve_target_segment(realized, [(clock(7), clock(13))], "current_day", uuid4),
                [{**realized, "status": "cancelled"}],
            )

    def test_repeated_segmentation_preserves_unaffected_sibling(self):
        first = {**self.segment, "endTime": clock(9)}
        second = {**self.segment, "id": uuid4(), "startTime": clock(10)}
        result = resolve_target_graph(
            self.parent, [first, second],
            {second["id"]: [(clock(11), clock(11, 30))]},
            "future", uuid4,
        )
        self.assertEqual(result[0], first)
        self.assertEqual(result[1]["id"], second["id"])
        self.assertEqual(result[2]["startTime"], clock(11, 30))

    def test_multiple_source_intervals_keep_real_gap(self):
        result = resolve_target_segment(
            self.segment,
            [(clock(9), clock(9, 30)), (clock(10, 30), clock(11))],
            "future", uuid4,
        )
        self.assertEqual([(item["startTime"], item["endTime"]) for item in result], [
            (clock(8), clock(9)), (clock(9, 30), clock(10, 30)), (clock(11), clock(12)),
        ])

    def test_in_progress_clear_end_and_beginning_vs_ambiguous_middle(self):
        active = {**self.segment, "status": "in_progress"}
        end = resolve_target_segment(active, [(clock(10), clock(12))], "current_day", uuid4)
        self.assertEqual((end[0]["endTime"], end[0]["status"]), (clock(10), "not_finished"))
        beginning = resolve_target_segment(active, [(clock(8), clock(10))], "current_day", uuid4)
        self.assertEqual((beginning[0]["startTime"], beginning[0]["status"]), (clock(10), "in_progress"))
        with self.assertRaises(SegmentConflictDomainError) as error:
            resolve_target_segment(active, [(clock(9), clock(10))], "current_day", uuid4)
        self.assertEqual(error.exception.code, "segment_resolution_undefined")
        with self.assertRaises(SegmentConflictDomainError):
            resolve_target_segment(active, [(clock(8), clock(12))], "current_day", uuid4)

    def test_exact_snapshot_and_duplicate_confirmation(self):
        occurrence_id, segment_id = uuid4(), uuid4()
        snapshot = {
            "occurrenceId": str(occurrence_id), "segmentId": str(segment_id),
            "startTime": "08:00", "endTime": "12:00", "status": "pending",
        }
        blocker = {
            "occurrenceId": occurrence_id, "segmentId": segment_id,
            "startTime": clock(8), "endTime": clock(12), "status": "pending",
        }
        self.assertTrue(same_snapshot(snapshot, blocker))
        for field, changed in (
            ("segmentId", str(uuid4())), ("startTime", "08:01"),
            ("endTime", "12:01"), ("status", "completed"),
        ):
            self.assertFalse(same_snapshot({**snapshot, field: changed}, blocker))
        entry = {"blocker": snapshot, "confirmed": True}
        with self.assertRaises(SegmentConflictValidationError):
            validate_confirmations({"confirmations": [entry, entry]})


if __name__ == "__main__":
    unittest.main()
