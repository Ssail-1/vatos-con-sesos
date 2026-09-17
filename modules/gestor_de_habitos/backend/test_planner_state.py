"""Pruebas del repository, reconstrucción y endpoint de planner-state."""

from datetime import date, datetime, time, timezone
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app import app
import database
import planner_state_service
from repositories import planner_state_repository


COLLECTIONS = (
    "plan_items",
    "generation_configs",
    "generation_slots",
    "generation_slot_weekdays",
    "generation_slot_dates",
    "generation_excluded_dates",
    "generation_slot_excluded_dates",
    "occurrences",
)


def uuid(number):
    return UUID(int=number)


def empty_rows():
    return {collection: [] for collection in COLLECTIONS}


def plan_item_row(number, kind="activity", subtype="periodic", name=None):
    return {
        "id": uuid(number),
        "name": name or f"PlanItem {number}",
        "kind": kind,
        "subtype": subtype,
        "created_at": datetime(2026, 9, 10, number, tzinfo=timezone.utc),
    }


def generation_config_row(number, mode, **changes):
    row = {
        "plan_item_id": uuid(number),
        "mode": mode,
        "start_date": None,
        "end_date": None,
        "indefinite": False,
        "interval_days": None,
        "stopped_from_date": None,
    }
    if mode in {"weekly", "interval_days"}:
        row.update(
            {
                "start_date": date(2026, 9, 1),
                "indefinite": True,
            }
        )
    if mode == "interval_days":
        row["interval_days"] = 3
    row.update(changes)
    return row


def slot_row(slot_number, plan_item_id, start, end):
    return {
        "id": UUID(f"00000000-0000-4000-8000-{slot_number:012d}"),
        "plan_item_id": uuid(plan_item_id),
        "start_time": start,
        "end_time": end,
    }


def slot_uuid(slot_number):
    return UUID(f"00000000-0000-4000-8000-{slot_number:012d}")


def occurrence_row(
    occurrence_id,
    plan_item_id,
    occurrence_date,
    start,
    end,
    status="pending",
    reason=None,
    source_id=None,
    source_slot=None,
):
    return {
        "id": uuid(occurrence_id),
        "plan_item_id": uuid(plan_item_id),
        "occurrence_date": occurrence_date,
        "start_time": start,
        "end_time": end,
        "status": status,
        "status_reason": reason,
        "source_occurrence_id": uuid(source_id) if source_id else None,
        "source_generation_slot_id": slot_uuid(source_slot)
        if source_slot
        else None,
    }


class PlannerStateRepositoryTests(unittest.TestCase):
    def test_reads_all_collections_with_one_connection(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor_context = connection.cursor.return_value
        cursor = cursor_context.__enter__.return_value
        cursor.fetchall.side_effect = [[] for _ in COLLECTIONS]
        transaction = connection.transaction.return_value

        with patch.object(database, "get_connection", return_value=connection) as connect:
            result = planner_state_repository.read_planner_state_rows()

        self.assertEqual(result, empty_rows())
        connect.assert_called_once_with()
        connection.transaction.assert_called_once_with()
        connection.cursor.assert_called_once_with(row_factory=dict_row)
        self.assertEqual(cursor.execute.call_count, len(COLLECTIONS) + 1)
        self.assertIn("REPEATABLE READ READ ONLY", cursor.execute.call_args_list[0].args[0])
        executed_sql = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        for table in COLLECTIONS:
            self.assertIn(f"public.{table}", executed_sql)
        cursor_context.__exit__.assert_called_once()
        transaction.__exit__.assert_called_once()
        connection.__exit__.assert_called_once()

    def test_database_error_is_sanitized_and_resources_are_closed(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor_context = connection.cursor.return_value
        cursor = cursor_context.__enter__.return_value
        cursor.execute.side_effect = psycopg.OperationalError("PRIVATE_SQL_DETAIL")

        with patch.object(database, "get_connection", return_value=connection):
            with self.assertRaises(
                planner_state_repository.PlannerStateRepositoryError
            ) as error:
                planner_state_repository.read_planner_state_rows()

        self.assertNotIn("PRIVATE_SQL_DETAIL", str(error.exception))
        cursor_context.__exit__.assert_called_once()
        connection.__exit__.assert_called_once()


class PlannerStateMappingTests(unittest.TestCase):
    def test_empty_planner(self):
        self.assertEqual(
            planner_state_service.build_planner_state(empty_rows()),
            {"planItems": [], "occurrences": []},
        )

    def test_weekly_with_multiple_slots_exclusions_and_stop(self):
        rows = empty_rows()
        rows["plan_items"] = [
            plan_item_row(1, kind="habit", subtype="scheduled", name="Meditar")
        ]
        rows["generation_configs"] = [
            generation_config_row(
                1, "weekly", stopped_from_date=date(2026, 10, 1)
            )
        ]
        rows["generation_slots"] = [
            slot_row(12, 1, time(14, 0), time(15, 0)),
            slot_row(11, 1, time(8, 0), time(9, 0)),
            slot_row(15, 1, time(10, 15), time(11, 30)),
        ]
        rows["generation_slot_weekdays"] = [
            {"slot_id": slot_uuid(12), "iso_weekday": 1},
            {"slot_id": slot_uuid(11), "iso_weekday": 1},
            {"slot_id": slot_uuid(15), "iso_weekday": 5},
        ]
        rows["generation_excluded_dates"] = [
            {"plan_item_id": uuid(1), "excluded_date": date(2026, 9, 22)},
            {"plan_item_id": uuid(1), "excluded_date": date(2026, 9, 15)},
        ]
        rows["generation_slot_excluded_dates"] = [
            {"slot_id": slot_uuid(12), "excluded_date": date(2026, 9, 29)},
            {"slot_id": slot_uuid(12), "excluded_date": date(2026, 9, 22)},
        ]

        result = planner_state_service.build_planner_state(rows)

        self.assertEqual(
            result["planItems"],
            [
                {
                    "id": str(uuid(1)),
                    "name": "Meditar",
                    "kind": "habit",
                    "habitType": "scheduled",
                    "generationConfig": {
                        "mode": "weekly",
                        "startDate": "2026-09-01",
                        "endDate": None,
                        "indefinite": True,
                        "slots": [
                            {
                                "id": str(slot_uuid(11)),
                                "isoWeekday": 1,
                                "startTime": "08:00",
                                "endTime": "09:00",
                            },
                            {
                                "id": str(slot_uuid(12)),
                                "isoWeekday": 1,
                                "startTime": "14:00",
                                "endTime": "15:00",
                                "excludedDates": ["2026-09-22", "2026-09-29"],
                            },
                            {
                                "id": str(slot_uuid(15)),
                                "isoWeekday": 5,
                                "startTime": "10:15",
                                "endTime": "11:30",
                            },
                        ],
                        "excludedDates": ["2026-09-15", "2026-09-22"],
                        "stoppedFromDate": "2026-10-01",
                    },
                }
            ],
        )

    def test_interval_days(self):
        rows = empty_rows()
        rows["plan_items"] = [plan_item_row(2, name="Cada cuatro días")]
        rows["generation_configs"] = [
            generation_config_row(
                2,
                "interval_days",
                end_date=date(2026, 10, 31),
                indefinite=False,
                interval_days=4,
            )
        ]
        rows["generation_slots"] = [
            slot_row(21, 2, time(12, 0), time(13, 30)),
            slot_row(22, 2, time(16, 0), time(17, 0)),
        ]
        rows["generation_slot_excluded_dates"] = [
            {"slot_id": slot_uuid(22), "excluded_date": date(2026, 9, 17)}
        ]

        result = planner_state_service.build_planner_state(rows)

        self.assertEqual(
            result["planItems"][0]["generationConfig"],
            {
                "mode": "interval_days",
                "startDate": "2026-09-01",
                "endDate": "2026-10-31",
                "indefinite": False,
                "intervalDays": 4,
                "slots": [
                    {
                        "id": str(slot_uuid(21)),
                        "startTime": "12:00",
                        "endTime": "13:30",
                    },
                    {
                        "id": str(slot_uuid(22)),
                        "startTime": "16:00",
                        "endTime": "17:00",
                        "excludedDates": ["2026-09-17"],
                    },
                ],
            },
        )

    def test_manual_dates_with_multiple_entries_and_stop(self):
        rows = empty_rows()
        rows["plan_items"] = [plan_item_row(3, subtype="event", name="Curso")]
        rows["generation_configs"] = [
            generation_config_row(
                3, "manual_dates", stopped_from_date=date(2026, 12, 1)
            )
        ]
        rows["generation_slots"] = [
            slot_row(32, 3, time(16, 0), time(17, 30)),
            slot_row(31, 3, time(10, 0), time(11, 0)),
        ]
        rows["generation_slot_dates"] = [
            {"slot_id": slot_uuid(32), "entry_date": date(2026, 11, 20)},
            {"slot_id": slot_uuid(31), "entry_date": date(2026, 9, 1)},
        ]

        result = planner_state_service.build_planner_state(rows)

        self.assertEqual(
            result["planItems"][0]["generationConfig"],
            {
                "mode": "manual_dates",
                "entries": [
                    {
                        "id": str(slot_uuid(31)),
                        "date": "2026-09-01",
                        "startTime": "10:00",
                        "endTime": "11:00",
                    },
                    {
                        "id": str(slot_uuid(32)),
                        "date": "2026-11-20",
                        "startTime": "16:00",
                        "endTime": "17:30",
                    },
                ],
                "stoppedFromDate": "2026-12-01",
            },
        )

    def test_multiple_plan_items_occurrences_and_status_context(self):
        rows = empty_rows()
        rows["plan_items"] = [
            plan_item_row(4, name="Rutina"),
            plan_item_row(5, subtype="event", name="Evento"),
        ]
        rows["generation_configs"] = [
            generation_config_row(4, "manual_dates"),
            generation_config_row(5, "manual_dates"),
        ]
        rows["generation_slots"] = [
            slot_row(41, 4, time(8, 0), time(10, 0)),
            slot_row(51, 5, time(9, 0), time(9, 30)),
        ]
        rows["generation_slot_dates"] = [
            {"slot_id": slot_uuid(41), "entry_date": date(2026, 9, 10)},
            {"slot_id": slot_uuid(51), "entry_date": date(2026, 9, 10)},
        ]
        rows["occurrences"] = [
            occurrence_row(
                402,
                4,
                date(2026, 9, 10),
                time(8, 0),
                time(10, 0),
                status="cancelled",
                reason="priority_override",
                source_id=501,
                source_slot=41,
            ),
            occurrence_row(
                501,
                5,
                date(2026, 9, 10),
                time(9, 0),
                time(9, 30),
                source_slot=51,
            ),
        ]

        result = planner_state_service.build_planner_state(rows)

        self.assertEqual(len(result["planItems"]), 2)
        self.assertEqual(result["planItems"][0]["activityType"], "periodic")
        self.assertEqual(result["planItems"][1]["activityType"], "event")
        self.assertEqual(
            result["occurrences"],
            [
                {
                    "id": str(uuid(402)),
                    "planItemId": str(uuid(4)),
                    "date": "2026-09-10",
                    "startTime": "08:00",
                    "endTime": "10:00",
                    "status": "cancelled",
                    "sourceGenerationSlotId": str(slot_uuid(41)),
                    "statusContext": {
                        "reason": "priority_override",
                        "sourceOccurrenceId": str(uuid(501)),
                    },
                },
                {
                    "id": str(uuid(501)),
                    "planItemId": str(uuid(5)),
                    "date": "2026-09-10",
                    "startTime": "09:00",
                    "endTime": "09:30",
                    "status": "pending",
                    "sourceGenerationSlotId": str(slot_uuid(51)),
                },
            ],
        )

    def test_plan_item_without_generation_config_is_inconsistent(self):
        rows = empty_rows()
        rows["plan_items"] = [plan_item_row(6)]

        with self.assertRaises(
            planner_state_service.PlannerStateConsistencyError
        ):
            planner_state_service.build_planner_state(rows)

    def test_manual_dates_without_entries_is_inconsistent(self):
        rows = empty_rows()
        rows["plan_items"] = [plan_item_row(7)]
        rows["generation_configs"] = [
            generation_config_row(7, "manual_dates")
        ]

        with self.assertRaises(
            planner_state_service.PlannerStateConsistencyError
        ):
            planner_state_service.build_planner_state(rows)

    def test_subminute_time_is_rejected_instead_of_truncated(self):
        rows = empty_rows()
        rows["plan_items"] = [plan_item_row(8)]
        rows["generation_configs"] = [generation_config_row(8, "interval_days")]
        rows["generation_slots"] = [
            slot_row(81, 8, time(8, 0, 1), time(9, 0))
        ]

        with self.assertRaises(
            planner_state_service.PlannerStateConsistencyError
        ):
            planner_state_service.build_planner_state(rows)

    def test_rejects_incompatible_slot_details_and_overlaps(self):
        cases = []

        weekly_without_slots = empty_rows()
        weekly_without_slots["plan_items"] = [plan_item_row(19)]
        weekly_without_slots["generation_configs"] = [
            generation_config_row(19, "weekly")
        ]
        cases.append(weekly_without_slots)

        weekly_missing_detail = empty_rows()
        weekly_missing_detail["plan_items"] = [plan_item_row(9)]
        weekly_missing_detail["generation_configs"] = [
            generation_config_row(9, "weekly")
        ]
        weekly_missing_detail["generation_slots"] = [
            slot_row(91, 9, time(8, 0), time(9, 0))
        ]
        cases.append(weekly_missing_detail)

        weekly_with_date = empty_rows()
        weekly_with_date["plan_items"] = [plan_item_row(16)]
        weekly_with_date["generation_configs"] = [
            generation_config_row(16, "weekly")
        ]
        weekly_with_date["generation_slots"] = [
            slot_row(161, 16, time(8, 0), time(9, 0))
        ]
        weekly_with_date["generation_slot_weekdays"] = [
            {"slot_id": slot_uuid(161), "iso_weekday": 1}
        ]
        weekly_with_date["generation_slot_dates"] = [
            {"slot_id": slot_uuid(161), "entry_date": date(2026, 9, 15)}
        ]
        cases.append(weekly_with_date)

        interval_without_slots = empty_rows()
        interval_without_slots["plan_items"] = [plan_item_row(17)]
        interval_without_slots["generation_configs"] = [
            generation_config_row(17, "interval_days")
        ]
        cases.append(interval_without_slots)

        interval_with_detail = empty_rows()
        interval_with_detail["plan_items"] = [plan_item_row(10)]
        interval_with_detail["generation_configs"] = [
            generation_config_row(10, "interval_days")
        ]
        interval_with_detail["generation_slots"] = [
            slot_row(101, 10, time(8, 0), time(9, 0))
        ]
        interval_with_detail["generation_slot_weekdays"] = [
            {"slot_id": slot_uuid(101), "iso_weekday": 1}
        ]
        cases.append(interval_with_detail)

        manual_with_weekday = empty_rows()
        manual_with_weekday["plan_items"] = [plan_item_row(11)]
        manual_with_weekday["generation_configs"] = [
            generation_config_row(11, "manual_dates")
        ]
        manual_with_weekday["generation_slots"] = [
            slot_row(111, 11, time(8, 0), time(9, 0))
        ]
        manual_with_weekday["generation_slot_weekdays"] = [
            {"slot_id": slot_uuid(111), "iso_weekday": 1}
        ]
        manual_with_weekday["generation_slot_dates"] = [
            {"slot_id": slot_uuid(111), "entry_date": date(2026, 9, 15)}
        ]
        cases.append(manual_with_weekday)

        manual_without_date = empty_rows()
        manual_without_date["plan_items"] = [plan_item_row(18)]
        manual_without_date["generation_configs"] = [
            generation_config_row(18, "manual_dates")
        ]
        manual_without_date["generation_slots"] = [
            slot_row(181, 18, time(8, 0), time(9, 0))
        ]
        cases.append(manual_without_date)

        overlapping = empty_rows()
        overlapping["plan_items"] = [plan_item_row(12)]
        overlapping["generation_configs"] = [
            generation_config_row(12, "interval_days")
        ]
        overlapping["generation_slots"] = [
            slot_row(121, 12, time(8, 0), time(10, 0)),
            slot_row(122, 12, time(9, 0), time(11, 0)),
        ]
        cases.append(overlapping)

        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(
                planner_state_service.PlannerStateConsistencyError
            ):
                planner_state_service.build_planner_state(rows)

    def test_rejects_unrepresentable_exclusions_and_cross_plan_source_slot(self):
        rows = empty_rows()
        rows["plan_items"] = [plan_item_row(13), plan_item_row(14)]
        rows["generation_configs"] = [
            generation_config_row(13, "manual_dates"),
            generation_config_row(14, "manual_dates"),
        ]
        rows["generation_slots"] = [
            slot_row(131, 13, time(8, 0), time(9, 0)),
            slot_row(141, 14, time(10, 0), time(11, 0)),
        ]
        rows["generation_slot_dates"] = [
            {"slot_id": slot_uuid(131), "entry_date": date(2026, 9, 15)},
            {"slot_id": slot_uuid(141), "entry_date": date(2026, 9, 15)},
        ]
        rows["occurrences"] = [
            occurrence_row(
                1301,
                13,
                date(2026, 9, 15),
                time(8, 0),
                time(9, 0),
                source_slot=141,
            )
        ]
        with self.assertRaises(planner_state_service.PlannerStateConsistencyError):
            planner_state_service.build_planner_state(rows)

        rows["occurrences"] = []
        rows["generation_excluded_dates"] = [
            {"plan_item_id": uuid(13), "excluded_date": date(2026, 9, 16)}
        ]
        with self.assertRaises(planner_state_service.PlannerStateConsistencyError):
            planner_state_service.build_planner_state(rows)

        rows["generation_excluded_dates"] = []
        rows["occurrences"] = []
        rows["generation_slot_excluded_dates"] = [
            {"slot_id": slot_uuid(131), "excluded_date": date(2026, 9, 15)}
        ]
        with self.assertRaises(planner_state_service.PlannerStateConsistencyError):
            planner_state_service.build_planner_state(rows)

    def test_null_source_generation_slot_is_omitted(self):
        rows = empty_rows()
        rows["plan_items"] = [plan_item_row(15)]
        rows["generation_configs"] = [generation_config_row(15, "manual_dates")]
        rows["generation_slots"] = [
            slot_row(151, 15, time(8, 0), time(9, 0))
        ]
        rows["generation_slot_dates"] = [
            {"slot_id": slot_uuid(151), "entry_date": date(2026, 9, 15)}
        ]
        rows["occurrences"] = [
            occurrence_row(
                1501, 15, date(2026, 9, 15), time(8, 0), time(9, 0)
            )
        ]

        result = planner_state_service.build_planner_state(rows)

        self.assertNotIn("sourceGenerationSlotId", result["occurrences"][0])

    def test_repository_failure_is_sanitized_by_service(self):
        with patch.object(
            planner_state_repository,
            "read_planner_state_rows",
            side_effect=planner_state_repository.PlannerStateRepositoryError(
                "PRIVATE_DATABASE_DETAIL"
            ),
        ):
            with self.assertRaises(
                planner_state_service.PlannerStateUnavailableError
            ) as error:
                planner_state_service.get_planner_state()

        self.assertNotIn("PRIVATE_DATABASE_DETAIL", str(error.exception))


class PlannerStateEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_returns_planner_state(self):
        state = {"planItems": [], "occurrences": []}
        with patch.object(
            planner_state_service, "get_planner_state", return_value=state
        ) as get_state:
            response = self.client.get("/api/planner-state")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), state)
        get_state.assert_called_once_with()

    def test_cors_allows_only_configured_origin_for_planner_state_get(self):
        state = {"planItems": [], "occurrences": []}
        with patch.dict(
            os.environ,
            {"VCS_ALLOWED_ORIGINS": "http://127.0.0.1:8000,http://localhost:8000"},
        ), patch.object(planner_state_service, "get_planner_state", return_value=state):
            allowed = self.client.get(
                "/api/planner-state", headers={"Origin": "http://127.0.0.1:8000"}
            )
            rejected = self.client.get(
                "/api/planner-state", headers={"Origin": "http://example.invalid"}
            )
            unrelated = self.client.get(
                "/api/health", headers={"Origin": "http://127.0.0.1:8000"}
            )

        self.assertEqual(
            allowed.headers.get("Access-Control-Allow-Origin"),
            "http://127.0.0.1:8000",
        )
        self.assertIn("Origin", allowed.headers.get("Vary", ""))
        self.assertNotIn("Access-Control-Allow-Origin", rejected.headers)
        self.assertNotIn("Access-Control-Allow-Origin", unrelated.headers)

    def test_database_failure_returns_sanitized_503(self):
        with patch.object(
            planner_state_service,
            "get_planner_state",
            side_effect=planner_state_service.PlannerStateUnavailableError(
                "PRIVATE_DATABASE_DETAIL"
            ),
        ):
            response = self.client.get("/api/planner-state")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("PRIVATE_DATABASE_DETAIL", response.get_data(as_text=True))

    def test_inconsistent_state_returns_sanitized_500(self):
        with patch.object(
            planner_state_service,
            "get_planner_state",
            side_effect=planner_state_service.PlannerStateConsistencyError(
                "PRIVATE_ROW_DETAIL"
            ),
        ):
            response = self.client.get("/api/planner-state")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json(),
            {
                "status": "error",
                "message": "El estado persistido del planner no es válido.",
            },
        )
        self.assertNotIn("PRIVATE_ROW_DETAIL", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
