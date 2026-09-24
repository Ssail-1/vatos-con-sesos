"""Pruebas puras del estado final y la traslación estructural."""

from datetime import time
import unittest
from uuid import uuid4

from occurrence_structure_domain import (
    OccurrenceStructureDomainError,
    translate_segments,
    validate_final_segments,
)


class OccurrenceStructureDomainTests(unittest.TestCase):
    def setUp(self):
        self.first = {"id": uuid4(), "startTime": time(8), "endTime": time(9), "status": "pending"}
        self.second = {"id": uuid4(), "startTime": time(10), "endTime": time(12), "status": "cancelled"}

    def test_final_set_sorts_without_mutating_and_accepts_adjacency(self):
        second = {**self.second, "startTime": time(9)}
        original = [second, self.first]
        final = validate_final_segments(time(8), time(12), original)
        self.assertEqual([row["id"] for row in final], [self.first["id"], second["id"]])
        self.assertEqual(original[0]["startTime"], time(9))

    def test_rejects_empty_invalid_bounds_duration_and_overlap(self):
        cases = [
            ([], "occurrence_requires_segment"),
            ([{**self.first, "endTime": time(8)}], "segment_time_invalid"),
            ([{**self.first, "startTime": time(7)}], "segment_outside_occurrence"),
            ([self.first, {**self.second, "startTime": time(8, 30)}], "segment_sibling_overlap"),
            ([self.first, self.first], "duplicate_segment_id"),
        ]
        for segments, code in cases:
            with self.subTest(code=code), self.assertRaises(OccurrenceStructureDomainError) as caught:
                validate_final_segments(time(8), time(12), segments)
            self.assertEqual(caught.exception.code, code)

    def test_translate_preserves_ids_statuses_durations_and_gap(self):
        source = [self.first, self.second]
        translated = translate_segments(time(8), time(12), time(13), time(17), source)
        self.assertEqual(
            [(row["id"], row["startTime"], row["endTime"], row["status"]) for row in translated],
            [(self.first["id"], time(13), time(14), "pending"),
             (self.second["id"], time(15), time(17), "cancelled")],
        )
        self.assertEqual(source[0]["startTime"], time(8))

    def test_translate_rejects_duration_change(self):
        with self.assertRaises(OccurrenceStructureDomainError) as caught:
            translate_segments(time(8), time(12), time(13), time(18), [self.first])
        self.assertEqual(caught.exception.code, "occurrence_translate_duration_mismatch")

    def test_translate_does_not_wrap_across_midnight(self):
        with self.assertRaises(OccurrenceStructureDomainError) as caught:
            translate_segments(time(8), time(12), time(23), time(3), [self.first])
        self.assertEqual(caught.exception.code, "invalid_payload")
