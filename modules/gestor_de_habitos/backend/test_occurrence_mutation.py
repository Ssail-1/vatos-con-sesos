"""Pruebas sin secretos para PATCH/DELETE de una sola occurrence."""

from datetime import date, time
import unittest
from unittest.mock import ANY, MagicMock, patch
from uuid import UUID

import psycopg

from app import app
import database
import occurrence_mutation_service as service
from repositories import occurrence_repository


REFERENCE_DATE = date(2026, 9, 20)
OCCURRENCE_ID = UUID("00000000-0000-0000-0000-000000000001")
PLAN_ITEM_ID = UUID("00000000-0000-0000-0000-000000000002")
SLOT_ID = UUID("00000000-0000-4000-8000-000000000003")


def occurrence_row(**changes):
    row = {
        "id": OCCURRENCE_ID,
        "plan_item_id": PLAN_ITEM_ID,
        "occurrence_date": REFERENCE_DATE,
        "start_time": time(14, 0),
        "end_time": time(17, 0),
        "status": "pending",
        "status_reason": None,
        "source_occurrence_id": None,
        "source_generation_slot_id": SLOT_ID,
    }
    row.update(changes)
    return row


def context(mode="weekly", **occurrence_changes):
    occurrence = occurrence_row(**occurrence_changes)
    source_slot = occurrence["source_generation_slot_id"]
    slot = None if source_slot is None else {
        "id": SLOT_ID,
        "plan_item_id": PLAN_ITEM_ID,
        "start_time": time(14, 0),
        "end_time": time(17, 0),
        "weekday_count": 1 if mode == "weekly" else 0,
        "date_count": 1 if mode == "manual_dates" else 0,
        "excluded_date_count": 0,
    }
    return {
        "planItem": {
            "id": PLAN_ITEM_ID,
            "kind": "activity",
            "subtype": "periodic",
            "mode": mode,
            "slot_count": 2,
            "global_exclusion_count": 0,
        },
        "occurrence": occurrence,
        "slot": slot,
        "manualSlots": (
            [
                {"id": SLOT_ID},
                {"id": UUID("00000000-0000-4000-8000-000000000004")},
            ]
            if mode == "manual_dates" and source_slot is not None
            else None
        ),
        "manualSlotDate": (
            {"slot_id": SLOT_ID, "entry_date": REFERENCE_DATE}
            if mode == "manual_dates" and source_slot is not None
            else None
        ),
    }


def database_mocks(locked_context):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    patches = [
        patch.object(database, "get_connection", return_value=connection),
        patch.object(service, "_load_locked_context", return_value=locked_context),
        patch.object(occurrence_repository, "set_serializable_transaction"),
        patch.object(
            occurrence_repository, "lock_blocking_occurrences", return_value=[]
        ),
        patch.object(
            occurrence_repository,
            "lock_source_occurrence_on_date",
            return_value=None,
        ),
        patch.object(
            occurrence_repository,
            "lock_manual_sibling_slots_on_date",
            return_value=[],
        ),
        patch.object(occurrence_repository, "insert_slot_exclusion"),
        patch.object(
            occurrence_repository, "update_occurrence_schedule", return_value=1
        ),
        patch.object(
            occurrence_repository,
            "update_generation_slot_schedule",
            return_value=1,
        ),
        patch.object(
            occurrence_repository, "update_manual_slot_date", return_value=1
        ),
        patch.object(occurrence_repository, "delete_occurrence", return_value=1),
        patch.object(
            occurrence_repository, "delete_generation_slot", return_value=1
        ),
        patch.object(
            occurrence_repository, "lock_status_context_dependents", return_value=[]
        ),
    ]
    return connection, patches


class PatchValidationTests(unittest.TestCase):
    def test_requires_exact_payload_and_valid_values(self):
        invalid_payloads = (
            None,
            {},
            {"date": "2026-09-20", "startTime": "08:00", "endTime": "09:00", "status": "completed"},
            {"date": "20-09-2026", "startTime": "08:00", "endTime": "09:00"},
            {"date": "2026-09-20", "startTime": "9:00", "endTime": "10:00"},
            {"date": "2026-09-20", "startTime": "10:00", "endTime": "10:00"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(
                service.OccurrenceValidationError
            ):
                service.validate_patch_payload(payload)

    def test_invalid_occurrence_id_fails_before_database_access(self):
        with patch.object(database, "get_connection") as connect, self.assertRaises(
            service.OccurrenceValidationError
        ):
            service.delete_occurrence("not-a-uuid", reference_date=REFERENCE_DATE)
        connect.assert_not_called()


class PatchOrchestrationTests(unittest.TestCase):
    def _run(self, locked_context, payload):
        connection, patches = database_mocks(locked_context)
        started = [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])
        result = service.patch_occurrence(
            str(OCCURRENCE_ID), payload, reference_date=REFERENCE_DATE
        )
        mocks = {
            "isolation": started[2],
            "blocking": started[3],
            "source_duplicate": started[4],
            "manual_siblings": started[5],
            "exclusion": started[6],
            "occurrence_update": started[7],
            "slot_update": started[8],
            "date_update": started[9],
        }
        return result, connection, mocks

    def test_recurring_same_date_updates_only_occurrence(self):
        result, connection, mocks = self._run(
            context(),
            {"date": "2026-09-20", "startTime": "15:00", "endTime": "18:00"},
        )
        self.assertEqual(result["occurrence"]["id"], str(OCCURRENCE_ID))
        self.assertEqual(result["occurrence"]["sourceGenerationSlotId"], str(SLOT_ID))
        self.assertEqual(result["occurrence"]["startTime"], "15:00")
        mocks["exclusion"].assert_not_called()
        mocks["slot_update"].assert_not_called()
        mocks["date_update"].assert_not_called()
        mocks["occurrence_update"].assert_called_once()
        mocks["isolation"].assert_called_once_with(connection)
        connection.transaction.assert_called_once_with()

    def test_recurring_move_excludes_original_date_and_preserves_source(self):
        result, _, mocks = self._run(
            context(),
            {"date": "2026-09-21", "startTime": "15:00", "endTime": "18:00"},
        )
        mocks["source_duplicate"].assert_called_once()
        mocks["exclusion"].assert_called_once_with(
            ANY, SLOT_ID, REFERENCE_DATE
        )
        self.assertEqual(result["occurrence"]["date"], "2026-09-21")
        self.assertEqual(result["occurrence"]["sourceGenerationSlotId"], str(SLOT_ID))

    def test_manual_patch_updates_slot_date_and_occurrence(self):
        result, _, mocks = self._run(
            context("manual_dates"),
            {"date": "2026-09-21", "startTime": "15:00", "endTime": "18:00"},
        )
        mocks["manual_siblings"].assert_called_once()
        mocks["slot_update"].assert_called_once()
        mocks["date_update"].assert_called_once()
        mocks["occurrence_update"].assert_called_once()
        mocks["exclusion"].assert_not_called()
        self.assertEqual(result["occurrence"]["id"], str(OCCURRENCE_ID))

    def test_ad_hoc_patch_updates_only_occurrence(self):
        result, _, mocks = self._run(
            context(source_generation_slot_id=None),
            {"date": "2026-09-21", "startTime": "09:00", "endTime": "10:00"},
        )
        mocks["exclusion"].assert_not_called()
        mocks["slot_update"].assert_not_called()
        mocks["date_update"].assert_not_called()
        mocks["occurrence_update"].assert_called_once()
        self.assertNotIn("sourceGenerationSlotId", result["occurrence"])

    def test_frozen_target_and_source_slot_collision_are_controlled(self):
        for target_date, duplicate, expected_code in (
            ("2026-09-18", None, "history_frozen"),
            ("2026-09-21", {"id": UUID(int=99)}, "slot_date_conflict"),
        ):
            connection, patches = database_mocks(context())
            started = [item.start() for item in patches]
            started[4].return_value = duplicate
            try:
                with self.assertRaises(service.OccurrenceConflictError) as error:
                    service.patch_occurrence(
                        str(OCCURRENCE_ID),
                        {"date": target_date, "startTime": "15:00", "endTime": "18:00"},
                        reference_date=REFERENCE_DATE,
                    )
                self.assertEqual(error.exception.code, expected_code)
                started[6].assert_not_called()
                started[7].assert_not_called()
                self.assertIsNotNone(connection)
            finally:
                for item in reversed(patches):
                    item.stop()

    def test_completed_priority_and_override_conflicts_match_current_rules(self):
        for candidate_subtype, conflict_status, conflict_subtype, expected_code in (
            ("unexpected", "completed", "periodic", "completed_conflict"),
            ("periodic", "pending", "periodic", "priority_conflict"),
            ("event", "pending", "periodic", "priority_override_required"),
        ):
            locked = context()
            locked["planItem"]["subtype"] = candidate_subtype
            connection, patches = database_mocks(locked)
            started = [item.start() for item in patches]
            started[3].return_value = [
                {
                    "id": UUID(int=80),
                    "occurrence_date": REFERENCE_DATE,
                    "start_time": time(15, 30),
                    "end_time": time(16, 30),
                    "status": conflict_status,
                    "kind": "activity",
                    "subtype": conflict_subtype,
                }
            ]
            try:
                with self.assertRaises(service.OccurrenceConflictError) as error:
                    service.patch_occurrence(
                        str(OCCURRENCE_ID),
                        {"date": "2026-09-20", "startTime": "15:00", "endTime": "18:00"},
                        reference_date=REFERENCE_DATE,
                    )
                self.assertEqual(error.exception.code, expected_code)
                started[7].assert_not_called()
                self.assertIsNotNone(connection)
            finally:
                for item in reversed(patches):
                    item.stop()

    def test_adjacent_interval_is_not_a_conflict_and_self_is_ignored(self):
        connection, patches = database_mocks(context())
        started = [item.start() for item in patches]
        started[3].return_value = [
            {
                "id": UUID(int=81),
                "occurrence_date": REFERENCE_DATE,
                "start_time": time(18, 0),
                "end_time": time(19, 0),
                "status": "pending",
                "kind": "activity",
                "subtype": "periodic",
            }
        ]
        try:
            service.patch_occurrence(
                str(OCCURRENCE_ID),
                {"date": "2026-09-20", "startTime": "15:00", "endTime": "18:00"},
                reference_date=REFERENCE_DATE,
            )
            started[3].assert_called_once_with(
                connection, REFERENCE_DATE, OCCURRENCE_ID
            )
            started[7].assert_called_once()
        finally:
            for item in reversed(patches):
                item.stop()


class DeleteOrchestrationTests(unittest.TestCase):
    def _run(self, locked_context):
        connection, patches = database_mocks(locked_context)
        started = [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])
        result = service.delete_occurrence(
            str(OCCURRENCE_ID), reference_date=REFERENCE_DATE
        )
        return result, {
            "exclusion": started[6],
            "delete_occurrence": started[10],
            "delete_slot": started[11],
        }

    def test_recurring_delete_adds_only_slot_exclusion(self):
        result, mocks = self._run(context())
        self.assertEqual(result, {"deletedOccurrenceId": str(OCCURRENCE_ID)})
        mocks["exclusion"].assert_called_once_with(
            ANY, SLOT_ID, REFERENCE_DATE
        )
        mocks["delete_occurrence"].assert_called_once()
        mocks["delete_slot"].assert_not_called()

    def test_manual_delete_removes_occurrence_and_slot(self):
        _, mocks = self._run(context("manual_dates"))
        mocks["exclusion"].assert_not_called()
        mocks["delete_occurrence"].assert_called_once()
        mocks["delete_slot"].assert_called_once()

    def test_last_manual_entry_is_rejected_without_writes(self):
        locked = context("manual_dates")
        locked["manualSlots"] = [{"id": SLOT_ID}]
        locked["planItem"]["slot_count"] = 1
        connection, patches = database_mocks(locked)
        started = [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])
        with self.assertRaises(service.OccurrenceConflictError) as error:
            service.delete_occurrence(
                str(OCCURRENCE_ID), reference_date=REFERENCE_DATE
            )
        self.assertEqual(error.exception.code, "last_manual_entry")
        started[10].assert_not_called()
        started[11].assert_not_called()
        self.assertIsNotNone(connection)

    def test_ad_hoc_delete_does_not_change_generation(self):
        _, mocks = self._run(context(source_generation_slot_id=None))
        mocks["exclusion"].assert_not_called()
        mocks["delete_occurrence"].assert_called_once()
        mocks["delete_slot"].assert_not_called()

    def test_status_policy_matches_current_frontend_rules(self):
        for day, status, code in (
            (date(2026, 9, 18), "pending", "history_frozen"),
            (REFERENCE_DATE, "completed", "deletion_status_locked"),
            (date(2026, 9, 21), "in_progress", "deletion_status_locked"),
        ):
            locked = context(occurrence_date=day, status=status)
            connection, patches = database_mocks(locked)
            started = [item.start() for item in patches]
            try:
                with self.assertRaises(service.OccurrenceConflictError) as error:
                    service.delete_occurrence(
                        str(OCCURRENCE_ID), reference_date=REFERENCE_DATE
                    )
                self.assertEqual(error.exception.code, code)
                started[10].assert_not_called()
            finally:
                for item in reversed(patches):
                    item.stop()

    def test_status_context_dependents_protect_the_source_occurrence(self):
        connection, patches = database_mocks(context())
        started = [item.start() for item in patches]
        started[12].return_value = [{"id": UUID(int=90)}]
        try:
            with self.assertRaises(service.OccurrenceConflictError) as error:
                service.delete_occurrence(
                    str(OCCURRENCE_ID), reference_date=REFERENCE_DATE
                )
            self.assertEqual(error.exception.code, "deletion_status_locked")
            started[10].assert_not_called()
            self.assertIsNotNone(connection)
        finally:
            for item in reversed(patches):
                item.stop()


class RepositoryTests(unittest.TestCase):
    def test_lock_occurrence_uses_for_update(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"id": OCCURRENCE_ID}
        result = occurrence_repository.lock_occurrence(connection, OCCURRENCE_ID)
        self.assertEqual(result, {"id": OCCURRENCE_ID})
        self.assertIn("FOR UPDATE", cursor.execute.call_args.args[0])

    def test_slot_exclusion_insert_is_idempotent(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        occurrence_repository.insert_slot_exclusion(
            connection, SLOT_ID, REFERENCE_DATE
        )
        self.assertIn("ON CONFLICT", cursor.execute.call_args.args[0])


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_patch_and_delete_success_contracts(self):
        patch_result = {"occurrence": {"id": str(OCCURRENCE_ID)}}
        with patch.object(service, "patch_occurrence", return_value=patch_result):
            response = self.client.patch(
                f"/api/occurrences/{OCCURRENCE_ID}",
                json={"date": "2026-09-20", "startTime": "08:00", "endTime": "09:00"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), patch_result)

        delete_result = {"deletedOccurrenceId": str(OCCURRENCE_ID)}
        with patch.object(service, "delete_occurrence", return_value=delete_result):
            response = self.client.delete(f"/api/occurrences/{OCCURRENCE_ID}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), delete_result)

    def test_errors_are_mapped_and_private_details_are_hidden(self):
        cases = (
            (service.OccurrenceValidationError("PRIVATE"), 400, "invalid_payload"),
            (service.OccurrenceNotFoundError("PRIVATE"), 404, "occurrence_not_found"),
            (service.OccurrenceConflictError("history_frozen", "Historial protegido."), 409, "history_frozen"),
            (service.OccurrenceConsistencyError("PRIVATE"), 500, "persisted_state_invalid"),
            (service.OccurrenceUnavailableError("PRIVATE"), 503, "database_unavailable"),
        )
        for error, status, code in cases:
            with self.subTest(status=status), patch.object(
                service, "delete_occurrence", side_effect=error
            ):
                response = self.client.delete(f"/api/occurrences/{OCCURRENCE_ID}")
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.get_json()["code"], code)
            if status != 409:
                self.assertNotIn("PRIVATE", response.get_data(as_text=True))

    def test_driver_error_is_sanitized_and_rolls_back(self):
        locked = context()
        connection, patches = database_mocks(locked)
        started = [item.start() for item in patches]
        started[7].side_effect = psycopg.OperationalError("PRIVATE_DRIVER_DETAIL")
        try:
            with self.assertRaises(service.OccurrenceUnavailableError) as error:
                service.patch_occurrence(
                    str(OCCURRENCE_ID),
                    {"date": "2026-09-20", "startTime": "15:00", "endTime": "18:00"},
                    reference_date=REFERENCE_DATE,
                )
            self.assertNotIn("PRIVATE_DRIVER_DETAIL", str(error.exception))
            self.assertIsNotNone(connection.transaction.return_value.__exit__.call_args.args[0])
        finally:
            for item in reversed(patches):
                item.stop()


if __name__ == "__main__":
    unittest.main()
