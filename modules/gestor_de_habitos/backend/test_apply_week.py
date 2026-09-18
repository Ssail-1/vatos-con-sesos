"""Pruebas sin secretos para Apply Week persistente."""

from datetime import date, time
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app import app
import database
from repositories import occurrence_repository
import week_mutation_service as service


REFERENCE_DATE = date(2026, 9, 14)
PLAN_ITEM_ID = UUID("00000000-0000-0000-0000-000000000010")


def occurrence_id(number):
    return UUID(f"00000000-0000-0000-0000-{number:012d}")


def slot_id(number):
    return UUID(f"00000000-0000-4000-8000-{number:012d}")


def occurrence(number, slot_number, day, start, end, **changes):
    row = {
        "id": occurrence_id(number),
        "plan_item_id": PLAN_ITEM_ID,
        "occurrence_date": day,
        "start_time": time.fromisoformat(start),
        "end_time": time.fromisoformat(end),
        "status": "pending",
        "status_reason": None,
        "source_occurrence_id": None,
        "source_generation_slot_id": (
            slot_id(slot_number) if slot_number is not None else None
        ),
    }
    row.update(changes)
    return row


def plan_item_context(mode="weekly"):
    return {
        "id": PLAN_ITEM_ID,
        "kind": "activity",
        "subtype": "periodic",
        "mode": mode,
        "start_date": date(2026, 9, 14),
        "end_date": date(2026, 9, 20),
        "indefinite": False,
        "interval_days": 1 if mode == "interval_days" else None,
        "stopped_from_date": None,
        "slot_count": 6,
        "global_exclusion_count": 0,
    }


def slots():
    return [
        {
            "id": slot_id(number),
            "plan_item_id": PLAN_ITEM_ID,
            "start_time": time(8 if number % 2 else 14),
            "end_time": time(11 if number % 2 else 17),
            "weekday_count": 1,
            "date_count": 0,
            "entry_date": None,
            "excluded_date_count": 0,
        }
        for number in range(1, 7)
    ]


def week_rows():
    return [
        occurrence(1, 1, date(2026, 9, 14), "08:00", "11:00"),
        occurrence(2, 2, date(2026, 9, 14), "14:00", "17:00"),
        occurrence(3, 3, date(2026, 9, 15), "08:00", "11:00"),
        occurrence(4, 4, date(2026, 9, 15), "14:00", "17:00"),
        occurrence(5, 5, date(2026, 9, 16), "08:00", "11:00"),
        occurrence(6, 6, date(2026, 9, 16), "14:00", "17:00"),
    ]


class PayloadValidationTests(unittest.TestCase):
    def test_accepts_exact_update_delete_create_contract(self):
        anchor, operations = service.validate_apply_week_payload(
            {
                "anchorDate": "2026-09-16",
                "operations": [
                    {
                        "type": "update",
                        "occurrenceId": str(occurrence_id(1)),
                        "date": "2026-09-14",
                        "startTime": "09:00",
                        "endTime": "10:00",
                    },
                    {"type": "delete", "occurrenceId": str(occurrence_id(2))},
                    {
                        "type": "create",
                        "date": "2026-09-16",
                        "startTime": "20:00",
                        "endTime": "21:00",
                    },
                ],
            }
        )
        self.assertEqual(anchor, date(2026, 9, 16))
        self.assertEqual([item["type"] for item in operations], ["update", "delete", "create"])

    def test_rejects_empty_unknown_extra_and_duplicate_occurrence_ids(self):
        invalid_payloads = (
            {"anchorDate": "2026-09-16", "operations": []},
            {"anchorDate": "2026-09-16", "operations": [{"type": "replace"}]},
            {
                "anchorDate": "2026-09-16",
                "operations": [
                    {"type": "delete", "occurrenceId": str(occurrence_id(1))},
                    {"type": "delete", "occurrenceId": str(occurrence_id(1))},
                ],
            },
            {
                "anchorDate": "2026-09-16",
                "operations": [
                    {
                        "type": "create",
                        "date": "2026-09-16",
                        "startTime": "20:00",
                        "endTime": "21:00",
                        "status": "completed",
                    }
                ],
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(
                service.WeekValidationError
            ) as error:
                service.validate_apply_week_payload(payload)
            self.assertEqual(error.exception.code, "invalid_payload")

    def test_invalid_url_identifier_fails_before_database_access(self):
        with patch.object(database, "get_connection") as connect, self.assertRaises(
            service.WeekValidationError
        ) as error:
            service.apply_week("invalid", {"anchorDate": "2026-09-14", "operations": []})
        self.assertEqual(error.exception.code, "invalid_identifier")
        connect.assert_not_called()


class FinalStateTests(unittest.TestCase):
    def test_swap_is_validated_as_final_state_not_sequential_state(self):
        rows = [
            occurrence(1, 1, date(2026, 9, 14), "08:00", "09:00"),
            occurrence(2, 2, date(2026, 9, 14), "09:00", "10:00"),
        ]
        operations = [
            {
                "type": "update",
                "occurrenceId": occurrence_id(1),
                "date": date(2026, 9, 14),
                "startTime": "09:00",
                "endTime": "10:00",
            },
            {
                "type": "update",
                "occurrenceId": occurrence_id(2),
                "date": date(2026, 9, 14),
                "startTime": "08:00",
                "endTime": "09:00",
            },
        ]
        final_rows, *_rest = service._candidate_state(
            rows,
            operations,
            PLAN_ITEM_ID,
            date(2026, 9, 14),
            date(2026, 9, 20),
            REFERENCE_DATE,
            None,
            lambda: occurrence_id(99),
        )
        service._validate_final_internal_state(final_rows)
        self.assertEqual(
            [(row["start_time"].strftime("%H:%M"), row["end_time"].strftime("%H:%M")) for row in final_rows],
            [("09:00", "10:00"), ("08:00", "09:00")],
        )

    def test_real_final_overlap_and_slot_date_duplicate_are_rejected(self):
        overlapping = [
            occurrence(1, 1, date(2026, 9, 14), "08:00", "10:00"),
            occurrence(2, 2, date(2026, 9, 14), "09:00", "11:00"),
        ]
        with self.assertRaises(service.WeekConflictError) as overlap_error:
            service._validate_final_internal_state(overlapping)
        self.assertEqual(overlap_error.exception.code, "schedule_conflict")

        duplicate = [
            occurrence(1, 1, date(2026, 9, 14), "08:00", "09:00"),
            occurrence(2, 1, date(2026, 9, 14), "10:00", "11:00"),
        ]
        with self.assertRaises(service.WeekConflictError) as duplicate_error:
            service._validate_final_internal_state(duplicate)
        self.assertEqual(duplicate_error.exception.code, "slot_date_conflict")

    def test_wrong_week_frozen_and_status_locked_are_atomic_validation_errors(self):
        base = week_rows()
        cases = (
            (
                [{"type": "create", "date": date(2026, 9, 21), "startTime": "20:00", "endTime": "21:00"}],
                service.WeekValidationError,
                None,
            ),
            (
                [{"type": "delete", "occurrenceId": occurrence_id(1)}],
                service.WeekConflictError,
                "history_frozen",
            ),
        )
        for operations, error_type, code in cases:
            with self.subTest(code=code), self.assertRaises(error_type) as error:
                service._candidate_state(
                    base,
                    operations,
                    PLAN_ITEM_ID,
                    date(2026, 9, 14),
                    date(2026, 9, 20),
                    date(2026, 9, 16) if code else REFERENCE_DATE,
                    None,
                    lambda: UUID("00000000-0000-4000-8000-000000000099"),
                )
            if code:
                self.assertEqual(error.exception.code, code)

    def test_manual_mode_and_priority_conflicts_are_controlled(self):
        manual = plan_item_context("manual_dates")
        manual.update(
            {
                "start_date": None,
                "end_date": None,
                "indefinite": False,
                "slot_count": 1,
            }
        )
        with self.assertRaises(service.WeekConflictError) as unsupported:
            service._validate_plan_item_context(manual)
        self.assertEqual(unsupported.exception.code, "unsupported_mode")

        candidate = [occurrence(1, 1, REFERENCE_DATE, "08:00", "10:00")]
        external = {
            "id": occurrence_id(50),
            "plan_item_id": occurrence_id(51),
            "occurrence_date": REFERENCE_DATE,
            "start_time": time(9, 0),
            "end_time": time(9, 30),
            "status": "pending",
            "kind": "activity",
            "subtype": "periodic",
        }
        with self.assertRaises(service.WeekConflictError) as priority:
            service._validate_external_conflicts(
                plan_item_context(), candidate, [external]
            )
        self.assertEqual(priority.exception.code, "priority_conflict")

        external["status"] = "completed"
        with self.assertRaises(service.WeekConflictError) as completed:
            service._validate_external_conflicts(
                plan_item_context(), candidate, [external]
            )
        self.assertEqual(completed.exception.code, "completed_conflict")


class ApplyWeekOrchestrationTests(unittest.TestCase):
    def test_main_batch_uses_one_transaction_and_preserves_slots(self):
        persisted_rows = week_rows()
        recorded_exclusions = []
        connection = MagicMock()
        connection.__enter__.return_value = connection

        def delete_row(_connection, target_id):
            persisted_rows[:] = [row for row in persisted_rows if row["id"] != target_id]
            return 1

        def update_row(_connection, target_id, target_date, start_time, end_time):
            row = next(row for row in persisted_rows if row["id"] == target_id)
            row["occurrence_date"] = target_date
            row["start_time"] = time.fromisoformat(start_time)
            row["end_time"] = time.fromisoformat(end_time)
            return 1

        def insert_rows(_connection, rows):
            persisted_rows.extend(dict(row) for row in rows)

        generated_id = UUID("00000000-0000-4000-8000-000000000099")
        payload = {
            "anchorDate": "2026-09-16",
            "operations": [
                {
                    "type": "update",
                    "occurrenceId": str(occurrence_id(2)),
                    "date": "2026-09-14",
                    "startTime": "15:00",
                    "endTime": "18:00",
                },
                {"type": "delete", "occurrenceId": str(occurrence_id(4))},
                {"type": "create", "date": "2026-09-16", "startTime": "20:00", "endTime": "21:00"},
            ],
        }
        with patch.object(database, "get_connection", return_value=connection), \
                patch.object(occurrence_repository, "set_serializable_transaction") as isolation, \
                patch.object(occurrence_repository, "lock_plan_item_identity", return_value={"id": PLAN_ITEM_ID}), \
                patch.object(occurrence_repository, "lock_plan_item_context", return_value=plan_item_context()), \
                patch.object(occurrence_repository, "lock_plan_item_slots", return_value=slots()) as slot_lock, \
                patch.object(occurrence_repository, "lock_plan_item_week_occurrences", side_effect=lambda *_args: [dict(row) for row in persisted_rows]), \
                patch.object(occurrence_repository, "lock_status_context_dependents_for_sources", return_value=[]) as context_lock, \
                patch.object(occurrence_repository, "lock_external_blocking_occurrences", return_value=[]), \
                patch.object(occurrence_repository, "lock_occurrences_for_slots", return_value=[]), \
                patch.object(occurrence_repository, "stage_occurrence_dates", return_value=True), \
                patch.object(occurrence_repository, "insert_slot_exclusions", side_effect=lambda _connection, values: recorded_exclusions.extend(values)), \
                patch.object(occurrence_repository, "delete_occurrence", side_effect=delete_row), \
                patch.object(occurrence_repository, "update_occurrence_schedule", side_effect=update_row), \
                patch.object(occurrence_repository, "insert_ad_hoc_occurrences", side_effect=insert_rows), \
                patch.object(occurrence_repository, "list_plan_item_week_occurrences", side_effect=lambda *_args: [dict(row) for row in persisted_rows]):
            result = service.apply_week(
                str(PLAN_ITEM_ID), payload, reference_date=REFERENCE_DATE,
                uuid_factory=lambda: generated_id,
            )

        self.assertEqual(result["weekStart"], "2026-09-14")
        self.assertEqual(result["weekEnd"], "2026-09-20")
        self.assertEqual(len(result["occurrences"]), 6)
        created = next(item for item in result["occurrences"] if item["id"] == str(generated_id))
        self.assertNotIn("sourceGenerationSlotId", created)
        self.assertEqual(created["status"], "pending")
        self.assertEqual(recorded_exclusions, [(slot_id(4), date(2026, 9, 15))])
        isolation.assert_called_once_with(connection)
        slot_lock.assert_called_once()
        context_lock.assert_called_once_with(
            connection, [occurrence_id(4), occurrence_id(2)]
        )
        connection.transaction.assert_called_once_with()


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_success_and_sanitized_error_mapping(self):
        expected = {"weekStart": "2026-09-14", "weekEnd": "2026-09-20", "occurrences": []}
        with patch.object(service, "apply_week", return_value=expected):
            response = self.client.post(
                f"/api/plan-items/{PLAN_ITEM_ID}/apply-week",
                json={"anchorDate": "2026-09-14", "operations": [{"type": "create", "date": "2026-09-14", "startTime": "08:00", "endTime": "09:00"}]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)

        cases = (
            (service.WeekValidationError("invalid_identifier", "PRIVATE"), 400, "invalid_identifier"),
            (service.WeekPlanItemNotFoundError("PRIVATE"), 404, "plan_item_not_found"),
            (service.WeekOccurrenceNotFoundError("PRIVATE"), 404, "occurrence_not_found"),
            (service.WeekConflictError("history_frozen", "Historial protegido."), 409, "history_frozen"),
            (service.WeekConsistencyError("PRIVATE"), 500, "persisted_state_invalid"),
            (service.WeekUnavailableError("PRIVATE"), 503, "database_unavailable"),
        )
        for error, status, code in cases:
            with self.subTest(code=code), patch.object(service, "apply_week", side_effect=error):
                response = self.client.post(
                    f"/api/plan-items/{PLAN_ITEM_ID}/apply-week", json={}
                )
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.get_json()["code"], code)
            if status != 409:
                self.assertNotIn("PRIVATE", response.get_data(as_text=True))

    def test_cors_allows_only_approved_recurring_posts(self):
        origin = "http://127.0.0.1:8000"
        with patch.dict(os.environ, {"VCS_ALLOWED_ORIGINS": origin}):
            responses = [
                self.client.options(
                    f"/api/plan-items/{PLAN_ITEM_ID}/apply-week",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "Content-Type",
                    },
                ),
                self.client.options(
                    f"/api/plan-items/{PLAN_ITEM_ID}/apply-future",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "Content-Type",
                    },
                ),
            ]
            rejected = self.client.options(
                f"/api/plan-items/{PLAN_ITEM_ID}/apply-week",
                headers={"Origin": "http://example.invalid"},
            )
            unrelated = self.client.options(
                f"/api/plan-items/{PLAN_ITEM_ID}/other",
                headers={"Origin": origin},
            )

        for response in responses:
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Methods"),
                "POST, OPTIONS",
            )
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Headers"),
                "Content-Type",
            )
        self.assertNotIn("Access-Control-Allow-Origin", rejected.headers)
        self.assertNotIn("Access-Control-Allow-Origin", unrelated.headers)


if __name__ == "__main__":
    unittest.main()
