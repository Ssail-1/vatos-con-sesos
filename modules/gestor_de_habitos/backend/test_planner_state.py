"""Pruebas del repository, reconstrucción y endpoint de planner-state."""

from datetime import date, datetime, time, timezone
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
    "generation_weekdays",
    "generation_date_entries",
    "generation_excluded_dates",
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
        "default_start_time": None,
        "default_end_time": None,
        "interval_days": None,
        "stopped_from_date": None,
    }
    if mode in {"weekly", "interval_days"}:
        row.update(
            {
                "start_date": date(2026, 9, 1),
                "indefinite": True,
                "default_start_time": time(8, 0),
                "default_end_time": time(9, 0),
            }
        )
    if mode == "interval_days":
        row["interval_days"] = 3
    row.update(changes)
    return row


def manual_entry_row(entry_id, plan_item_id, entry_date, start, end):
    return {
        "id": uuid(entry_id),
        "plan_item_id": uuid(plan_item_id),
        "entry_date": entry_date,
        "start_time": start,
        "end_time": end,
    }


def occurrence_row(
    occurrence_id,
    plan_item_id,
    occurrence_date,
    start,
    end,
    status="pending",
    reason=None,
    source_id=None,
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
    }


class PlannerStateRepositoryTests(unittest.TestCase):
    def test_reads_all_collections_with_one_connection(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor_context = connection.cursor.return_value
        cursor = cursor_context.__enter__.return_value
        cursor.fetchall.side_effect = [[] for _ in COLLECTIONS]

        with patch.object(database, "get_connection", return_value=connection) as connect:
            result = planner_state_repository.read_planner_state_rows()

        self.assertEqual(result, empty_rows())
        connect.assert_called_once_with()
        connection.cursor.assert_called_once_with(row_factory=dict_row)
        self.assertEqual(cursor.execute.call_count, len(COLLECTIONS))
        executed_sql = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        for table in COLLECTIONS:
            self.assertIn(f"public.{table}", executed_sql)
        cursor_context.__exit__.assert_called_once()
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

    def test_weekly_with_weekdays_overrides_exclusions_and_stop(self):
        rows = empty_rows()
        rows["plan_items"] = [
            plan_item_row(1, kind="habit", subtype="scheduled", name="Meditar")
        ]
        rows["generation_configs"] = [
            generation_config_row(
                1, "weekly", stopped_from_date=date(2026, 10, 1)
            )
        ]
        rows["generation_weekdays"] = [
            {
                "plan_item_id": uuid(1),
                "iso_weekday": 5,
                "override_start_time": time(10, 15),
                "override_end_time": time(11, 30),
            },
            {
                "plan_item_id": uuid(1),
                "iso_weekday": 1,
                "override_start_time": None,
                "override_end_time": None,
            },
        ]
        rows["generation_excluded_dates"] = [
            {"plan_item_id": uuid(1), "excluded_date": date(2026, 9, 22)},
            {"plan_item_id": uuid(1), "excluded_date": date(2026, 9, 15)},
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
                        "weekdays": [1, 5],
                        "defaultStartTime": "08:00",
                        "defaultEndTime": "09:00",
                        "weekdayTimeOverrides": {
                            "5": {"startTime": "10:15", "endTime": "11:30"}
                        },
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
                default_start_time=time(12, 0),
                default_end_time=time(13, 30),
            )
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
                "defaultStartTime": "12:00",
                "defaultEndTime": "13:30",
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
        rows["generation_date_entries"] = [
            manual_entry_row(
                32, 3, date(2026, 11, 20), time(16, 0), time(17, 30)
            ),
            manual_entry_row(
                31, 3, date(2026, 9, 1), time(10, 0), time(11, 0)
            ),
        ]

        result = planner_state_service.build_planner_state(rows)

        self.assertEqual(
            result["planItems"][0]["generationConfig"],
            {
                "mode": "manual_dates",
                "entries": [
                    {
                        "date": "2026-09-01",
                        "startTime": "10:00",
                        "endTime": "11:00",
                    },
                    {
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
        rows["generation_date_entries"] = [
            manual_entry_row(41, 4, date(2026, 9, 10), time(8, 0), time(10, 0)),
            manual_entry_row(51, 5, date(2026, 9, 10), time(9, 0), time(9, 30)),
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
            ),
            occurrence_row(
                501, 5, date(2026, 9, 10), time(9, 0), time(9, 30)
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
        rows["generation_configs"][0]["default_start_time"] = time(8, 0, 1)

        with self.assertRaises(
            planner_state_service.PlannerStateConsistencyError
        ):
            planner_state_service.build_planner_state(rows)

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
