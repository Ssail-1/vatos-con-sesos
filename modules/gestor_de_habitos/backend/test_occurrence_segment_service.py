"""Pruebas sin credenciales para status segmentario y reconciliación."""

from contextlib import ExitStack
from datetime import date, datetime, time
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app import app
import database
import occurrence_segment_service as service
from repositories import occurrence_segment_repository as repository


NOW = datetime(2026, 9, 20, 12, 0)
OCCURRENCE_ID = UUID("00000000-0000-0000-0000-000000000101")
PLAN_ITEM_ID = UUID("00000000-0000-0000-0000-000000000102")
SEGMENT_ID = UUID("00000000-0000-0000-0000-000000000103")


def occurrence_row(**changes):
    row = {
        "id": OCCURRENCE_ID,
        "plan_item_id": PLAN_ITEM_ID,
        "occurrence_date": NOW.date(),
        "start_time": time(8, 0),
        "end_time": time(12, 0),
        "status": "pending",
        "conflict_reason": None,
        "source_occurrence_id": None,
        "source_generation_slot_id": None,
        "origin_reason": None,
        "last_conflict_action": None,
    }
    row.update(changes)
    return row


def segment_row(segment_id=SEGMENT_ID, **changes):
    row = {
        "id": segment_id,
        "occurrence_id": OCCURRENCE_ID,
        "start_time": time(8, 0),
        "end_time": time(10, 0),
        "status": "pending",
    }
    row.update(changes)
    return row


class ServiceMocks:
    def __init__(self, occurrence=None, segments=None, blockers=None):
        self.connection = MagicMock()
        self.connection.__enter__.return_value = self.connection
        self.stack = ExitStack()
        self.get_connection = self.stack.enter_context(
            patch.object(database, "get_connection", return_value=self.connection)
        )
        self.find_owner = self.stack.enter_context(
            patch.object(
                repository,
                "find_segment_owner",
                return_value={"occurrence_id": OCCURRENCE_ID},
            )
        )
        self.lock_occurrence = self.stack.enter_context(
            patch.object(
                repository,
                "lock_occurrence",
                return_value=occurrence or occurrence_row(),
            )
        )
        self.lock_segments = self.stack.enter_context(
            patch.object(
                repository,
                "lock_occurrence_segments",
                return_value=segments or [segment_row()],
            )
        )
        self.blockers = self.stack.enter_context(
            patch.object(
                repository,
                "list_blocking_overlaps",
                return_value=blockers or [],
            )
        )
        self.update_segment = self.stack.enter_context(
            patch.object(repository, "update_segment_status", return_value=1)
        )
        self.update_occurrence = self.stack.enter_context(
            patch.object(repository, "update_occurrence_status", return_value=1)
        )

    def close(self):
        self.stack.close()


class StatusMutationTests(unittest.TestCase):
    def test_rejects_invalid_id_and_payload_before_database_access(self):
        invalid = (
            ("not-a-uuid", {"status": "pending"}),
            (str(SEGMENT_ID), None),
            (str(SEGMENT_ID), {}),
            (str(SEGMENT_ID), {"status": "unknown"}),
            (str(SEGMENT_ID), {"status": "pending", "extra": True}),
        )
        for segment_id, payload in invalid:
            with self.subTest(payload=payload), patch.object(
                database, "get_connection"
            ) as connect, self.assertRaises(
                service.OccurrenceSegmentValidationError
            ):
                service.mutate_segment_status(segment_id, payload, now=NOW)
            connect.assert_not_called()

    def test_single_segment_completed_updates_child_and_derived_parent(self):
        mocks = ServiceMocks(
            occurrence=occurrence_row(end_time=time(10, 0)),
            segments=[segment_row(end_time=time(10, 0))],
        )
        self.addCleanup(mocks.close)

        result = service.mutate_segment_status(
            str(SEGMENT_ID), {"status": "completed"}, now=NOW
        )

        self.assertEqual(
            result,
            {
                "status": "ok",
                "occurrenceId": str(OCCURRENCE_ID),
                "segmentId": str(SEGMENT_ID),
                "segmentStatus": "completed",
                "occurrenceStatus": "completed",
            },
        )
        mocks.update_segment.assert_called_once_with(
            mocks.connection, SEGMENT_ID, "completed"
        )
        mocks.update_occurrence.assert_called_once_with(
            mocks.connection, OCCURRENCE_ID, "completed"
        )
        self.assertEqual(
            mocks.connection.isolation_level, service.IsolationLevel.SERIALIZABLE
        )
        mocks.connection.transaction.assert_called_once_with()

    def test_all_siblings_participate_in_current_and_historical_aggregate(self):
        second_id = UUID(int=104)
        cases = (
            (
                occurrence_row(),
                [
                    segment_row(status="pending"),
                    segment_row(
                        second_id,
                        start_time=time(10, 0),
                        end_time=time(12, 0),
                        status="pending",
                    ),
                ],
                "completed",
                NOW,
                "in_progress",
            ),
            (
                occurrence_row(
                    occurrence_date=date(2026, 9, 19),
                    status="not_finished",
                ),
                [
                    segment_row(status="not_completed"),
                    segment_row(
                        second_id,
                        start_time=time(10, 0),
                        end_time=time(12, 0),
                        status="completed",
                    ),
                ],
                "completed",
                NOW,
                "completed",
            ),
        )
        for occurrence, segments, requested, now, expected in cases:
            with self.subTest(date=occurrence["occurrence_date"]):
                mocks = ServiceMocks(occurrence=occurrence, segments=segments)
                try:
                    result = service.mutate_segment_status(
                        str(SEGMENT_ID), {"status": requested}, now=now
                    )
                    self.assertEqual(result["occurrenceStatus"], expected)
                    mocks.update_occurrence.assert_called_once_with(
                        mocks.connection, OCCURRENCE_ID, expected
                    )
                finally:
                    mocks.close()

    def test_completed_uses_target_segment_end_not_parent_end(self):
        mocks = ServiceMocks(
            occurrence=occurrence_row(end_time=time(17, 0)),
            segments=[segment_row(end_time=time(11, 0))],
        )
        self.addCleanup(mocks.close)
        result = service.mutate_segment_status(
            str(SEGMENT_ID), {"status": "completed"}, now=NOW
        )
        self.assertEqual(result["segmentStatus"], "completed")

    def test_previous_day_transient_sibling_requires_reconciliation(self):
        second_id = UUID(int=104)
        mocks = ServiceMocks(
            occurrence=occurrence_row(occurrence_date=date(2026, 9, 19)),
            segments=[
                segment_row(status="not_completed"),
                segment_row(
                    second_id,
                    start_time=time(10, 0),
                    end_time=time(12, 0),
                    status="pending",
                ),
            ],
        )
        self.addCleanup(mocks.close)
        with self.assertRaises(service.OccurrenceSegmentConflictError) as error:
            service.mutate_segment_status(
                str(SEGMENT_ID), {"status": "completed"}, now=NOW
            )
        self.assertEqual(error.exception.code, "temporal_reconciliation_required")
        mocks.update_segment.assert_not_called()
        mocks.update_occurrence.assert_not_called()

    def test_blocking_activation_returns_segment_blockers_without_writes(self):
        blocker_occurrence_id = UUID(int=201)
        blocker_segment_id = UUID(int=202)
        blocker_plan_item_id = UUID(int=203)
        blocker = {
            "occurrence_id": blocker_occurrence_id,
            "segment_id": blocker_segment_id,
            "plan_item_id": blocker_plan_item_id,
            "occurrence_date": NOW.date(),
            "start_time": time(8, 30),
            "end_time": time(9, 30),
            "status": "not_finished",
        }
        mocks = ServiceMocks(
            segments=[segment_row(status="cancelled")], blockers=[blocker]
        )
        self.addCleanup(mocks.close)
        with self.assertRaises(service.OccurrenceSegmentConflictError) as error:
            service.mutate_segment_status(
                str(SEGMENT_ID), {"status": "pending"}, now=NOW
            )
        self.assertEqual(error.exception.code, "segment_status_conflict")
        self.assertEqual(
            error.exception.blockers,
            [
                {
                    "occurrenceId": str(blocker_occurrence_id),
                    "segmentId": str(blocker_segment_id),
                    "planItemId": str(blocker_plan_item_id),
                    "date": "2026-09-20",
                    "startTime": "08:30",
                    "endTime": "09:30",
                    "status": "not_finished",
                }
            ],
        )
        mocks.update_segment.assert_not_called()
        mocks.update_occurrence.assert_not_called()

    def test_non_blocking_status_does_not_query_conflicts(self):
        for status in ("cancelled", "not_completed"):
            with self.subTest(status=status):
                mocks = ServiceMocks()
                try:
                    service.mutate_segment_status(
                        str(SEGMENT_ID), {"status": status}, now=NOW
                    )
                    mocks.blockers.assert_not_called()
                finally:
                    mocks.close()

    def test_frozen_history_is_read_only(self):
        mocks = ServiceMocks(
            occurrence=occurrence_row(occurrence_date=date(2026, 9, 18)),
            segments=[segment_row(status="completed")],
        )
        self.addCleanup(mocks.close)
        with self.assertRaises(service.OccurrenceSegmentConflictError) as error:
            service.mutate_segment_status(
                str(SEGMENT_ID), {"status": "completed"}, now=NOW
            )
        self.assertEqual(error.exception.code, "history_frozen")
        mocks.update_segment.assert_not_called()


class ReconciliationTests(unittest.TestCase):
    def _run(self, occurrence_rows, segment_rows):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        with patch.object(
            database, "get_connection", return_value=connection
        ), patch.object(
            repository,
            "lock_historical_occurrences",
            return_value=occurrence_rows,
        ) as lock_parents, patch.object(
            repository,
            "lock_segments_for_occurrences",
            return_value=segment_rows,
        ) as lock_segments, patch.object(
            repository, "update_segment_status", return_value=1
        ) as update_segment, patch.object(
            repository, "update_occurrence_status", return_value=1
        ) as update_occurrence:
            result = service.reconcile_planner(now=NOW)
        return {
            "result": result,
            "connection": connection,
            "lockParents": lock_parents,
            "lockSegments": lock_segments,
            "updateSegment": update_segment,
            "updateOccurrence": update_occurrence,
        }

    def test_reconciles_missed_days_and_historical_aggregates(self):
        occurrence_ids = (UUID(int=301), UUID(int=302), UUID(int=303))
        occurrences = [
            occurrence_row(
                id=occurrence_id,
                occurrence_date=day,
                status=status,
            )
            for occurrence_id, day, status in zip(
                occurrence_ids,
                (date(2026, 9, 19), date(2026, 9, 18), date(2026, 9, 15)),
                ("pending", "in_progress", "completed"),
            )
        ]
        segments = [
            segment_row(
                UUID(int=400 + index),
                occurrence_id=occurrence_id,
                status=status,
            )
            for index, (occurrence_id, status) in enumerate(
                zip(
                    occurrence_ids,
                    ("pending", "in_progress", "completed"),
                )
            )
        ]
        actual = self._run(occurrences, segments)
        self.assertEqual(
            actual["result"],
            {"status": "ok", "updatedOccurrences": 2, "updatedSegments": 2},
        )
        self.assertEqual(
            [call.args[2] for call in actual["updateSegment"].call_args_list],
            ["not_completed", "not_finished"],
        )
        actual["lockParents"].assert_called_once_with(
            actual["connection"], NOW.date()
        )
        actual["lockSegments"].assert_called_once_with(
            actual["connection"], list(occurrence_ids)
        )

    def test_second_reconciliation_is_idempotent_and_repairs_stale_aggregate(self):
        stable = occurrence_row(
            occurrence_date=date(2026, 9, 19), status="pending"
        )
        segments = [segment_row(status="not_completed")]
        first = self._run([stable], segments)
        self.assertEqual(
            first["result"],
            {"status": "ok", "updatedOccurrences": 1, "updatedSegments": 0},
        )
        first["updateOccurrence"].assert_called_once()

        stable["status"] = "not_completed"
        second = self._run([stable], segments)
        self.assertEqual(
            second["result"],
            {"status": "ok", "updatedOccurrences": 0, "updatedSegments": 0},
        )
        second["updateSegment"].assert_not_called()
        second["updateOccurrence"].assert_not_called()

    def test_client_cannot_supply_time_authority(self):
        for payload in ({}, {"today": "2035-01-01"}, {"now": "2035-01-01T00:00"}):
            with self.subTest(payload=payload), patch.object(
                database, "get_connection"
            ) as connect, self.assertRaises(
                service.OccurrenceSegmentValidationError
            ):
                service.reconcile_planner(payload, now=NOW)
            connect.assert_not_called()


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_patch_success_and_error_contracts(self):
        success = {
            "status": "ok",
            "occurrenceId": str(OCCURRENCE_ID),
            "segmentId": str(SEGMENT_ID),
            "segmentStatus": "completed",
            "occurrenceStatus": "completed",
        }
        with patch.object(
            service, "mutate_segment_status", return_value=success
        ) as mutate:
            response = self.client.patch(
                f"/api/occurrence-segments/{SEGMENT_ID}/status",
                json={"status": "completed"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), success)
        mutate.assert_called_once_with(str(SEGMENT_ID), {"status": "completed"})

        blockers = [{"segmentId": str(UUID(int=999))}]
        with patch.object(
            service,
            "mutate_segment_status",
            side_effect=service.OccurrenceSegmentConflictError(
                "segment_status_conflict", "Existe un blocker.", blockers
            ),
        ):
            conflict = self.client.patch(
                f"/api/occurrence-segments/{SEGMENT_ID}/status",
                json={"status": "pending"},
            )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.get_json()["code"], "segment_status_conflict")
        self.assertEqual(conflict.get_json()["blockers"], blockers)

    def test_reconciliation_success_and_rejects_public_clock(self):
        summary = {
            "status": "ok",
            "updatedOccurrences": 3,
            "updatedSegments": 4,
        }
        with patch.object(service, "reconcile_planner", return_value=summary) as run:
            response = self.client.post("/api/planner/reconcile")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), summary)
        run.assert_called_once_with(None)

        with patch.object(
            service,
            "reconcile_planner",
            side_effect=service.OccurrenceSegmentValidationError("invalid"),
        ):
            invalid = self.client.post(
                "/api/planner/reconcile", json={"today": "2035-01-01"}
            )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["code"], "invalid_payload")

    def test_cors_permits_only_configured_origin_for_new_routes(self):
        origin = "http://127.0.0.1:8000"
        with patch.dict(os.environ, {"VCS_ALLOWED_ORIGINS": origin}), patch.object(
            service,
            "mutate_segment_status",
            return_value={"status": "ok", "segmentId": str(SEGMENT_ID)},
        ), patch.object(
            service,
            "reconcile_planner",
            return_value={"status": "ok", "updatedOccurrences": 0, "updatedSegments": 0},
        ):
            segment_path = f"/api/occurrence-segments/{SEGMENT_ID}/status"
            preflight_patch = self.client.options(
                segment_path,
                headers={"Origin": origin, "Access-Control-Request-Method": "PATCH"},
            )
            actual_patch = self.client.patch(
                segment_path, json={"status": "pending"}, headers={"Origin": origin}
            )
            preflight_reconcile = self.client.options(
                "/api/planner/reconcile",
                headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
            )
            actual_reconcile = self.client.post(
                "/api/planner/reconcile", headers={"Origin": origin}
            )
            rejected = self.client.options(
                segment_path,
                headers={"Origin": "http://unapproved.invalid"},
            )
        for response, method in (
            (preflight_patch, "PATCH, OPTIONS"),
            (actual_patch, "PATCH, OPTIONS"),
            (preflight_reconcile, "POST, OPTIONS"),
            (actual_reconcile, "POST, OPTIONS"),
        ):
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)
            self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), method)
            self.assertEqual(response.headers.get("Vary"), "Origin")
        self.assertEqual(preflight_patch.headers.get("Access-Control-Allow-Headers"), "Content-Type")
        self.assertNotIn("Access-Control-Allow-Origin", rejected.headers)


if __name__ == "__main__":
    unittest.main()
