"""Pruebas unitarias de las reglas puras de OccurrenceSegment."""

from datetime import date
import unittest

from occurrence_segment_domain import (
    CURRENT_DAY,
    FROZEN_HISTORY,
    FUTURE,
    PREVIOUS_EDITABLE_DAY,
    OccurrenceSegmentDomainError,
    derive_occurrence_status,
    temporal_phase_for_date,
)
from scheduling_policy import BLOCKING_STATUSES


def segments(*statuses):
    return [
        {"id": f"segment-{index}", "status": status}
        for index, status in enumerate(statuses)
    ]


class TemporalPhaseTests(unittest.TestCase):
    def test_classifies_all_explicit_temporal_phases(self):
        reference = date(2026, 9, 20)
        self.assertEqual(
            temporal_phase_for_date(date(2026, 9, 21), reference, 1), FUTURE
        )
        self.assertEqual(
            temporal_phase_for_date(reference, reference, 1), CURRENT_DAY
        )
        self.assertEqual(
            temporal_phase_for_date(date(2026, 9, 19), reference, 1),
            PREVIOUS_EDITABLE_DAY,
        )
        self.assertEqual(
            temporal_phase_for_date(date(2026, 9, 18), reference, 1),
            FROZEN_HISTORY,
        )


class AggregateStatusTests(unittest.TestCase):
    def test_rejects_empty_unknown_and_invalid_phase(self):
        with self.assertRaises(OccurrenceSegmentDomainError):
            derive_occurrence_status([], CURRENT_DAY)
        with self.assertRaises(OccurrenceSegmentDomainError):
            derive_occurrence_status(segments("unknown"), CURRENT_DAY)
        with self.assertRaises(OccurrenceSegmentDomainError):
            derive_occurrence_status(segments("pending"), "unknown_phase")

    def test_uniform_status_always_has_precedence(self):
        for status in (
            "pending",
            "in_progress",
            "completed",
            "not_completed",
            "not_finished",
            "cancelled",
        ):
            for phase in (
                FUTURE,
                CURRENT_DAY,
                PREVIOUS_EDITABLE_DAY,
                FROZEN_HISTORY,
            ):
                with self.subTest(status=status, phase=phase):
                    for status_count in (1, 2):
                        self.assertEqual(
                            derive_occurrence_status(
                                segments(*(status,) * status_count), phase
                            ),
                            status,
                        )

    def test_future_mixed_pending_and_cancelled_is_pending(self):
        self.assertEqual(
            derive_occurrence_status(segments("pending", "cancelled"), FUTURE),
            "pending",
        )

    def test_current_day_mixed_precedence(self):
        cases = (
            (("completed", "pending"), "in_progress"),
            (("completed", "cancelled"), "in_progress"),
            (("not_finished", "pending"), "in_progress"),
            (("in_progress", "cancelled"), "in_progress"),
            (("pending", "cancelled"), "pending"),
            (("not_completed", "cancelled"), "not_completed"),
        )
        for statuses, expected in cases:
            with self.subTest(statuses=statuses):
                self.assertEqual(
                    derive_occurrence_status(segments(*statuses), CURRENT_DAY),
                    expected,
                )

    def test_historical_mixed_precedence(self):
        cases = (
            (("completed", "not_finished"), "not_finished"),
            (("completed", "not_completed"), "not_finished"),
            (("completed", "cancelled"), "not_finished"),
            (("not_completed", "cancelled"), "not_completed"),
        )
        for phase in (PREVIOUS_EDITABLE_DAY, FROZEN_HISTORY):
            for statuses, expected in cases:
                with self.subTest(phase=phase, statuses=statuses):
                    self.assertEqual(
                        derive_occurrence_status(segments(*statuses), phase),
                        expected,
                    )

    def test_historical_mixed_transient_status_is_explicitly_rejected(self):
        for phase in (PREVIOUS_EDITABLE_DAY, FROZEN_HISTORY):
            with self.subTest(phase=phase), self.assertRaises(
                OccurrenceSegmentDomainError
            ):
                derive_occurrence_status(segments("pending", "cancelled"), phase)

    def test_does_not_mutate_inputs(self):
        source = segments("completed", "pending")
        snapshot = [dict(segment) for segment in source]
        self.assertEqual(
            derive_occurrence_status(source, CURRENT_DAY), "in_progress"
        )
        self.assertEqual(source, snapshot)


class BlockingStatusTests(unittest.TestCase):
    def test_backend_policy_blocks_not_finished_only_with_active_statuses(self):
        self.assertEqual(
            BLOCKING_STATUSES,
            {"pending", "in_progress", "completed", "not_finished"},
        )
        self.assertTrue({"not_completed", "cancelled"}.isdisjoint(BLOCKING_STATUSES))


if __name__ == "__main__":
    unittest.main()
