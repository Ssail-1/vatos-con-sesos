"""Pruebas de validación, materialización y escritura atómica."""

from datetime import date, time
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

import psycopg

from app import app
import database
import plan_item_creation_service as creation_service
from plan_item_materializer import materialize_occurrence_drafts
from repositories import plan_item_repository


REFERENCE_DATE = date(2026, 9, 11)


def weekly_config(**changes):
    config = {
        "mode": "weekly",
        "startDate": "2026-09-11",
        "endDate": None,
        "indefinite": True,
        "weekdays": [1, 3, 5],
        "defaultStartTime": "08:00",
        "defaultEndTime": "09:00",
        "weekdayTimeOverrides": {},
    }
    config.update(changes)
    return config


def interval_config(**changes):
    config = {
        "mode": "interval_days",
        "startDate": "2026-09-11",
        "endDate": None,
        "indefinite": True,
        "intervalDays": 3,
        "defaultStartTime": "12:00",
        "defaultEndTime": "13:00",
    }
    config.update(changes)
    return config


def manual_config(entries=None, **controls):
    return {
        "mode": "manual_dates",
        "entries": entries
        if entries is not None
        else [
            {
                "date": "2026-09-11",
                "startTime": "10:00",
                "endTime": "11:00",
            }
        ],
        **controls,
    }


def activity_payload(config=None, subtype="periodic"):
    return {
        "name": "Actividad",
        "kind": "activity",
        "activityType": subtype,
        "generationConfig": config or manual_config(),
    }


def habit_payload(config=None):
    return {
        "name": "Hábito",
        "kind": "habit",
        "habitType": "scheduled",
        "generationConfig": config or weekly_config(),
    }


def create_without_database(payload, reference_date=REFERENCE_DATE):
    with patch.object(database, "get_connection") as connect, patch.object(
        plan_item_repository, "list_blocking_occurrences", return_value=[]
    ), patch.object(
        plan_item_repository, "insert_plan_item_graph"
    ) as insert:
        connection = connect.return_value.__enter__.return_value
        result = creation_service.create_plan_item(
            payload, reference_date=reference_date
        )
    return result, connection, insert


class PayloadValidationTests(unittest.TestCase):
    def test_accepts_only_the_three_canonical_modes(self):
        for payload in (
            activity_payload(weekly_config()),
            activity_payload(interval_config()),
            activity_payload(manual_config()),
        ):
            with self.subTest(mode=payload["generationConfig"]["mode"]):
                normalized = creation_service.validate_plan_item_payload(payload)
                self.assertEqual(
                    normalized["generationConfig"]["mode"],
                    payload["generationConfig"]["mode"],
                )

        with self.assertRaises(creation_service.PlanItemValidationError):
            creation_service.validate_plan_item_payload(
                activity_payload(
                    {
                        "mode": "single_date",
                        "date": "2026-09-11",
                        "startTime": "10:00",
                        "endTime": "11:00",
                    }
                )
            )

    def test_rejects_invalid_plan_item_and_generation_values(self):
        duplicate_entry = {
            "date": "2026-09-11",
            "startTime": "10:00",
            "endTime": "11:00",
        }
        invalid_payloads = [
            {**activity_payload(), "name": " "},
            {**activity_payload(), "activityType": "unknown"},
            {**habit_payload(), "activityType": "periodic"},
            activity_payload(weekly_config(weekdays=[])),
            activity_payload(weekly_config(weekdays=[1, 1])),
            activity_payload(weekly_config(defaultEndTime="07:00")),
            activity_payload(interval_config(intervalDays=0)),
            activity_payload(manual_config(entries=[])),
            activity_payload(manual_config(entries=[duplicate_entry, duplicate_entry])),
            activity_payload(manual_config(excludedDates=["invalid"])),
            activity_payload(manual_config(stoppedFromDate="invalid")),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(creation_service.PlanItemValidationError):
                    creation_service.validate_plan_item_payload(payload)

    def test_normalizes_name_order_and_optional_controls(self):
        payload = activity_payload(
            weekly_config(
                weekdays=[5, 1],
                weekdayTimeOverrides={
                    "5": {"startTime": "10:00", "endTime": "11:00"}
                },
                excludedDates=["2026-09-25", "2026-09-12"],
                stoppedFromDate="2026-10-01",
            )
        )
        payload["name"] = "  Actividad normalizada  "
        result = creation_service.validate_plan_item_payload(payload)
        self.assertEqual(result["name"], "Actividad normalizada")
        self.assertEqual(result["generationConfig"]["weekdays"], [1, 5])
        self.assertEqual(
            result["generationConfig"]["excludedDates"],
            ["2026-09-12", "2026-09-25"],
        )


class MaterializationTests(unittest.TestCase):
    def test_weekly_override_interval_and_manual_dates(self):
        cases = (
            (
                activity_payload(
                    weekly_config(
                        weekdayTimeOverrides={
                            "5": {"startTime": "10:00", "endTime": "11:30"}
                        }
                    )
                ),
                lambda occurrences: self.assertTrue(
                    any(
                        occurrence["date"] == "2026-09-11"
                        and occurrence["startTime"] == "10:00"
                        for occurrence in occurrences
                    )
                ),
            ),
            (
                activity_payload(interval_config()),
                lambda occurrences: self.assertEqual(
                    [item["date"] for item in occurrences[:3]],
                    ["2026-09-11", "2026-09-14", "2026-09-17"],
                ),
            ),
            (
                activity_payload(manual_config()),
                lambda occurrences: self.assertEqual(len(occurrences), 1),
            ),
            (
                activity_payload(
                    manual_config(
                        entries=[
                            {
                                "date": "2026-09-11",
                                "startTime": "08:00",
                                "endTime": "09:00",
                            },
                            {
                                "date": "2026-09-12",
                                "startTime": "10:00",
                                "endTime": "11:00",
                            },
                        ]
                    )
                ),
                lambda occurrences: self.assertEqual(len(occurrences), 2),
            ),
        )
        for payload, assertion in cases:
            with self.subTest(mode=payload["generationConfig"]["mode"]):
                result, _, _ = create_without_database(payload)
                assertion(result["occurrences"])
                self.assertTrue(
                    all(item["status"] == "pending" for item in result["occurrences"])
                )

    def test_exclusions_and_stopped_from_date_filter_occurrences(self):
        result, _, _ = create_without_database(
            activity_payload(
                interval_config(
                    excludedDates=["2026-09-14"],
                    stoppedFromDate="2026-09-20",
                )
            )
        )
        self.assertEqual(
            [item["date"] for item in result["occurrences"]],
            ["2026-09-11", "2026-09-17"],
        )

    def test_habit_and_activity_keep_the_discriminated_contract(self):
        for payload, subtype_field in (
            (habit_payload(), "habitType"),
            (activity_payload(), "activityType"),
        ):
            with self.subTest(kind=payload["kind"]):
                result, _, _ = create_without_database(payload)
                self.assertIn(subtype_field, result["planItem"])
                opposite = (
                    "activityType" if subtype_field == "habitType" else "habitType"
                )
                self.assertNotIn(opposite, result["planItem"])

    def test_materializer_matches_the_javascript_implementation(self):
        fixtures = [
            {
                "planItem": {
                    "id": "weekly",
                    **activity_payload(
                        weekly_config(
                            endDate="2026-09-30",
                            indefinite=False,
                            weekdayTimeOverrides={
                                "5": {
                                    "startTime": "10:00",
                                    "endTime": "11:30",
                                }
                            },
                            excludedDates=["2026-09-16"],
                            stoppedFromDate="2026-09-26",
                        )
                    ),
                },
                "rangeStart": "2026-09-01",
                "rangeEnd": "2026-09-30",
            },
            {
                "planItem": {
                    "id": "interval",
                    **activity_payload(
                        interval_config(excludedDates=["2026-09-17"])
                    ),
                },
                "rangeStart": "2026-09-01",
                "rangeEnd": "2026-10-01",
            },
            {
                "planItem": {
                    "id": "manual",
                    **activity_payload(
                        manual_config(
                            entries=[
                                {
                                    "date": "2026-09-11",
                                    "startTime": "08:00",
                                    "endTime": "09:00",
                                },
                                {
                                    "date": "2026-10-03",
                                    "startTime": "12:00",
                                    "endTime": "13:00",
                                },
                            ]
                        )
                    ),
                },
                "rangeStart": "2026-09-01",
                "rangeEnd": "2026-10-31",
            },
        ]
        module_root = Path(__file__).resolve().parents[1]
        script = """
            import fs from 'node:fs';
            import { materializeOccurrenceDrafts } from './js/scheduling/materializer.js';
            const fixtures = JSON.parse(fs.readFileSync(0, 'utf8'));
            const result = fixtures.map(({ planItem, rangeStart, rangeEnd }) =>
                materializeOccurrenceDrafts(planItem, rangeStart, rangeEnd));
            process.stdout.write(JSON.stringify(result));
        """
        javascript = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=module_root,
            input=json.dumps(fixtures),
            capture_output=True,
            text=True,
            check=True,
        )
        expected = json.loads(javascript.stdout)
        actual = [
            materialize_occurrence_drafts(
                fixture["planItem"],
                date.fromisoformat(fixture["rangeStart"]),
                date.fromisoformat(fixture["rangeEnd"]),
            )
            for fixture in fixtures
        ]
        self.assertEqual(actual, expected)


class ConflictTests(unittest.TestCase):
    def test_overlapping_manual_entries_are_a_domain_conflict(self):
        payload = activity_payload(
            manual_config(
                entries=[
                    {
                        "date": "2026-09-11",
                        "startTime": "08:00",
                        "endTime": "10:00",
                    },
                    {
                        "date": "2026-09-11",
                        "startTime": "09:00",
                        "endTime": "11:00",
                    },
                ]
            )
        )
        with self.assertRaises(creation_service.PlanItemConflictError) as error:
            creation_service.create_plan_item(payload, reference_date=REFERENCE_DATE)
        self.assertEqual(error.exception.code, "candidate_internal_conflict")

    def test_frozen_history_is_rejected_before_opening_a_connection(self):
        payload = activity_payload(
            manual_config(
                entries=[
                    {
                        "date": "2026-09-09",
                        "startTime": "08:00",
                        "endTime": "09:00",
                    }
                ]
            )
        )
        with patch.object(database, "get_connection") as connect:
            with self.assertRaises(creation_service.PlanItemConflictError) as error:
                creation_service.create_plan_item(
                    payload, reference_date=REFERENCE_DATE
                )
        self.assertEqual(error.exception.code, "history_frozen")
        connect.assert_not_called()

    def test_existing_priority_conflicts_are_classified(self):
        existing = {
            "id": UUID(int=900),
            "plan_item_id": UUID(int=901),
            "occurrence_date": REFERENCE_DATE,
            "start_time": time(10, 30),
            "end_time": time(11, 30),
            "status": "pending",
            "kind": "activity",
            "subtype": "periodic",
        }
        for subtype, expected_code in (
            ("periodic", "priority_conflict"),
            ("event", "priority_override_required"),
        ):
            with self.subTest(subtype=subtype), patch.object(
                database, "get_connection"
            ) as connect, patch.object(
                plan_item_repository,
                "list_blocking_occurrences",
                return_value=[existing],
            ), patch.object(plan_item_repository, "insert_plan_item_graph") as insert:
                connection = connect.return_value
                connection.__enter__.return_value = connection
                with self.assertRaises(
                    creation_service.PlanItemConflictError
                ) as error:
                    creation_service.create_plan_item(
                        activity_payload(subtype=subtype),
                        reference_date=REFERENCE_DATE,
                    )
                self.assertEqual(error.exception.code, expected_code)
                insert.assert_not_called()


class RepositoryWriteTests(unittest.TestCase):
    def test_weekly_graph_includes_overrides_exclusions_and_occurrences(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        plan_item = {
            "id": str(UUID(int=1)),
            **activity_payload(
                weekly_config(
                    weekdays=[1, 5],
                    weekdayTimeOverrides={
                        "5": {"startTime": "10:00", "endTime": "11:00"}
                    },
                    excludedDates=["2026-09-14"],
                    stoppedFromDate="2026-10-01",
                )
            ),
        }
        occurrence = {
            "id": str(UUID(int=2)),
            "planItemId": plan_item["id"],
            "date": "2026-09-11",
            "startTime": "10:00",
            "endTime": "11:00",
            "status": "pending",
        }

        plan_item_repository.insert_plan_item_graph(
            connection, plan_item, [occurrence], []
        )

        executed = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        batches = {
            call.args[0]: call.args[1] for call in cursor.executemany.call_args_list
        }
        self.assertIn("public.plan_items", executed)
        self.assertIn("public.generation_configs", executed)
        weekday_query = next(
            query for query in batches if "public.generation_weekdays" in query
        )
        self.assertEqual(
            batches[weekday_query],
            [
                (plan_item["id"], 1, None, None),
                (plan_item["id"], 5, "10:00", "11:00"),
            ],
        )
        self.assertTrue(
            any("public.generation_excluded_dates" in query for query in batches)
        )
        self.assertTrue(any("public.occurrences" in query for query in batches))

    def test_manual_graph_assigns_one_internal_id_per_entry(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        entries = [
            {"date": "2026-09-11", "startTime": "08:00", "endTime": "09:00"},
            {"date": "2026-09-12", "startTime": "10:00", "endTime": "11:00"},
        ]
        plan_item = {
            "id": str(UUID(int=1)),
            **activity_payload(manual_config(entries=entries)),
        }
        entry_ids = [str(UUID(int=2)), str(UUID(int=3))]

        plan_item_repository.insert_plan_item_graph(
            connection, plan_item, [], entry_ids
        )

        entry_call = next(
            call
            for call in cursor.executemany.call_args_list
            if "public.generation_date_entries" in call.args[0]
        )
        self.assertEqual(
            [parameters[0] for parameters in entry_call.args[1]], entry_ids
        )


class TransactionTests(unittest.TestCase):
    def _connection_failing_at(self, table_name):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []

        def fail_execute(query, parameters):
            if f"INSERT INTO public.{table_name}" in query:
                raise psycopg.IntegrityError("PRIVATE_DATABASE_DETAIL")

        def fail_executemany(query, parameters):
            if f"INSERT INTO public.{table_name}" in query:
                raise psycopg.IntegrityError("PRIVATE_DATABASE_DETAIL")

        cursor.execute.side_effect = fail_execute
        cursor.executemany.side_effect = fail_executemany
        return connection

    def test_failures_rollback_without_leaving_an_orphan(self):
        cases = (
            "generation_configs",
            "generation_date_entries",
            "occurrences",
        )
        for table_name in cases:
            with self.subTest(table=table_name):
                connection = self._connection_failing_at(table_name)
                transaction = connection.transaction.return_value
                with patch.object(
                    database, "get_connection", return_value=connection
                ):
                    with self.assertRaises(
                        creation_service.PlanItemCreationUnavailableError
                    ) as error:
                        creation_service.create_plan_item(
                            activity_payload(), reference_date=REFERENCE_DATE
                        )
                self.assertNotIn("PRIVATE_DATABASE_DETAIL", str(error.exception))
                transaction.__exit__.assert_called_once()
                self.assertIsNotNone(transaction.__exit__.call_args.args[0])
                connection.__exit__.assert_called_once()

    def test_success_uses_one_connection_and_one_transaction(self):
        result, connection, insert = create_without_database(activity_payload())
        connection.transaction.assert_called_once_with()
        insert.assert_called_once()
        persisted_connection, plan_item, occurrences, entry_ids = insert.call_args.args
        self.assertIs(persisted_connection, connection)
        self.assertEqual(plan_item, result["planItem"])
        self.assertEqual(occurrences, result["occurrences"])
        self.assertEqual(len(entry_ids), 1)


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_success_returns_created_graph(self):
        result = {
            "planItem": {"id": str(UUID(int=1)), **activity_payload()},
            "occurrences": [],
        }
        with patch.object(
            creation_service, "create_plan_item", return_value=result
        ) as create:
            response = self.client.post("/api/plan-items", json=activity_payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), result)
        create.assert_called_once_with(activity_payload())

    def test_invalid_payload_returns_400_without_private_details(self):
        with patch.object(
            creation_service,
            "create_plan_item",
            side_effect=creation_service.PlanItemValidationError("PRIVATE_DETAIL"),
        ):
            response = self.client.post("/api/plan-items", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "invalid_payload")
        self.assertNotIn("PRIVATE_DETAIL", response.get_data(as_text=True))

    def test_domain_conflict_returns_409(self):
        with patch.object(
            creation_service,
            "create_plan_item",
            side_effect=creation_service.PlanItemConflictError(
                "priority_conflict", "El horario entra en conflicto."
            ),
        ):
            response = self.client.post("/api/plan-items", json=activity_payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "priority_conflict")

    def test_database_failure_returns_sanitized_503(self):
        with patch.object(
            creation_service,
            "create_plan_item",
            side_effect=creation_service.PlanItemCreationUnavailableError(
                "PRIVATE_DATABASE_DETAIL"
            ),
        ):
            response = self.client.post("/api/plan-items", json=activity_payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["code"], "database_unavailable")
        self.assertNotIn("PRIVATE_DATABASE_DETAIL", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
