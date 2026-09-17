"""Integración opt-in contra una base PostgreSQL 16 exclusivamente de pruebas."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

import psycopg

from app import app
import database
import future_schedule_service
import occurrence_mutation_service as mutation_service
import plan_item_creation_service as creation_service
from plan_item_materializer import materialize_occurrence_drafts
from repositories import occurrence_repository
import week_mutation_service


TEST_DATABASE_ENV = "VCS_TEST_DATABASE_URL"
REFERENCE_DATE = date(2026, 9, 14)
MIGRATION_DIRECTORY = Path(__file__).resolve().parents[1] / "db" / "migrations"
CURRENT_MIGRATIONS = (
    "001_initial_schema.sql",
    "002_fix_occurrence_status_context.sql",
    "003_multi_slot_scheduling.sql",
)


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 9, 14)


def slot_id(number):
    return f"00000000-0000-4000-8000-{number:012d}"


def activity(config, name="Actividad"):
    return {
        "name": name,
        "kind": "activity",
        "activityType": "periodic",
        "generationConfig": config,
    }


def manual_payload(slot_number=1, *, day="2026-09-14"):
    return activity(
        {
            "mode": "manual_dates",
            "entries": [
                {
                    "id": slot_id(slot_number),
                    "date": day,
                    "startTime": "08:00",
                    "endTime": "09:00",
                }
            ],
        }
    )


class PostgreSQLMultiSlotIntegrationTests(unittest.TestCase):
    @classmethod
    def _reset_current_schema(cls):
        with psycopg.connect(cls.database_url, autocommit=True) as connection:
            connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
            connection.execute("CREATE SCHEMA public")
            for migration_name in CURRENT_MIGRATIONS:
                connection.execute(
                    (MIGRATION_DIRECTORY / migration_name).read_text(encoding="utf-8")
                )
            connection.execute(
                """
                CREATE OR REPLACE FUNCTION public.reject_test_insert()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $$
                BEGIN
                    RAISE EXCEPTION 'intentional integration failure';
                END
                $$
                """
            )

    @classmethod
    def setUpClass(cls):
        cls.database_url = os.getenv(TEST_DATABASE_ENV)
        if not cls.database_url:
            raise unittest.SkipTest(
                f"{TEST_DATABASE_ENV} no está configurada para integración PostgreSQL."
            )

        with psycopg.connect(cls.database_url, autocommit=True) as connection:
            database_name = connection.execute("SELECT current_database()").fetchone()[0]
            if not (
                database_name.startswith("vcs_test_")
                or database_name.endswith("_test")
            ):
                raise RuntimeError(
                    "La suite requiere una base cuyo nombre identifique explícitamente pruebas."
                )
        cls._reset_current_schema()

    def setUp(self):
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute("TRUNCATE TABLE public.plan_items CASCADE")

    def _post(self, payload):
        with patch.object(database, "get_database_url", return_value=self.database_url), \
                patch.object(creation_service, "date", FixedDate):
            return app.test_client().post("/api/plan-items", json=payload)

    def _get_state(self):
        with patch.object(database, "get_database_url", return_value=self.database_url):
            return app.test_client().get("/api/planner-state")

    def _patch_occurrence(self, occurrence_id, payload):
        with patch.object(database, "get_database_url", return_value=self.database_url), \
                patch.object(mutation_service, "_today", return_value=REFERENCE_DATE):
            return app.test_client().patch(
                f"/api/occurrences/{occurrence_id}", json=payload
            )

    def _delete_occurrence(self, occurrence_id):
        with patch.object(database, "get_database_url", return_value=self.database_url), \
                patch.object(mutation_service, "_today", return_value=REFERENCE_DATE):
            return app.test_client().delete(f"/api/occurrences/{occurrence_id}")

    def _apply_week(self, plan_item_id, payload, reference_date=REFERENCE_DATE):
        with patch.object(database, "get_database_url", return_value=self.database_url), \
                patch.object(week_mutation_service, "_today", return_value=reference_date):
            return app.test_client().post(
                f"/api/plan-items/{plan_item_id}/apply-week", json=payload
            )

    def _apply_future(self, plan_item_id, payload, reference_date=REFERENCE_DATE):
        with patch.object(database, "get_database_url", return_value=self.database_url), \
                patch.object(future_schedule_service, "_today", return_value=reference_date):
            return app.test_client().post(
                f"/api/plan-items/{plan_item_id}/apply-future", json=payload
            )

    def _weekly_two_slot_payload(self, name="Weekly mutation"):
        return activity(
            {
                "mode": "weekly",
                "startDate": "2026-09-14",
                "endDate": "2026-09-14",
                "indefinite": False,
                "slots": [
                    {
                        "id": slot_id(701),
                        "isoWeekday": 1,
                        "startTime": "08:00",
                        "endTime": "11:00",
                    },
                    {
                        "id": slot_id(702),
                        "isoWeekday": 1,
                        "startTime": "14:00",
                        "endTime": "17:00",
                    },
                ],
            },
            name,
        )

    def _weekly_apply_payload(self, name="Apply Week"):
        slots = []
        sequence = 800
        for weekday in (1, 2, 3):
            for start_time, end_time in (("08:00", "11:00"), ("14:00", "17:00")):
                sequence += 1
                slots.append(
                    {
                        "id": slot_id(sequence),
                        "isoWeekday": weekday,
                        "startTime": start_time,
                        "endTime": end_time,
                    }
                )
        return activity(
            {
                "mode": "weekly",
                "startDate": "2026-09-14",
                "endDate": "2026-09-27",
                "indefinite": False,
                "slots": slots,
            },
            name,
        )

    def _counts(self):
        with psycopg.connect(self.database_url) as connection:
            return connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM public.plan_items),
                    (SELECT COUNT(*) FROM public.generation_configs),
                    (SELECT COUNT(*) FROM public.generation_slots),
                    (SELECT COUNT(*) FROM public.occurrences)
                """
            ).fetchone()

    def test_empty_database_and_health_routes(self):
        state_response = self._get_state()
        self.assertEqual(state_response.status_code, 200)
        self.assertEqual(
            state_response.get_json(), {"planItems": [], "occurrences": []}
        )

        client = app.test_client()
        self.assertEqual(client.get("/api/health").status_code, 200)
        with patch.object(database, "get_database_url", return_value=self.database_url):
            self.assertEqual(client.get("/api/health/db").status_code, 200)
            self.assertEqual(client.get("/api/plan-items").status_code, 200)

    def test_persisted_api_state_hydrates_frontend_store_without_rematerializing(self):
        if not shutil.which("node"):
            self.skipTest("Node.js no está disponible para verificar hydration frontend.")

        payload = activity(
            {
                "mode": "manual_dates",
                "entries": [
                    {
                        "id": slot_id(5011),
                        "date": "2026-09-17",
                        "startTime": "08:00",
                        "endTime": "08:05",
                    },
                    {
                        "id": slot_id(5012),
                        "date": "2026-09-17",
                        "startTime": "14:00",
                        "endTime": "14:05",
                    },
                    {
                        "id": slot_id(5013),
                        "date": "2026-09-17",
                        "startTime": "22:00",
                        "endTime": "22:05",
                    },
                ],
            },
            "Hydration persisted integration",
        )
        created = self._post(payload)
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        state_response = self._get_state()
        self.assertEqual(state_response.status_code, 200)
        server_state = state_response.get_json()
        self.assertEqual(len(server_state["planItems"]), 1)
        self.assertEqual(len(server_state["occurrences"]), 3)

        store_module = (
            Path(__file__).resolve().parents[1] / "js" / "state" / "planner-store.js"
        ).as_uri()
        script = f"""
            import {{ createPlannerStore }} from {json.dumps(store_module)};
            let input = "";
            process.stdin.setEncoding("utf8");
            for await (const chunk of process.stdin) input += chunk;
            const serverState = JSON.parse(input);
            const store = createPlannerStore([], [], "2026-09-17");
            store.hydratePlannerState(serverState);
            process.stdout.write(JSON.stringify({{
                planItems: store.getPlanItems(),
                occurrences: store.getOccurrences(),
            }}));
        """
        hydrated = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            input=json.dumps(server_state),
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(json.loads(hydrated.stdout), server_state)

    def test_weekly_interval_and_manual_post_round_trip(self):
        payloads = (
            activity(
                {
                    "mode": "weekly",
                    "startDate": "2026-09-14",
                    "endDate": "2026-09-14",
                    "indefinite": False,
                    "slots": [
                        {
                            "id": slot_id(11),
                            "isoWeekday": 1,
                            "startTime": "08:00",
                            "endTime": "09:00",
                        },
                        {
                            "id": slot_id(12),
                            "isoWeekday": 1,
                            "startTime": "10:00",
                            "endTime": "11:00",
                        },
                    ],
                    "excludedDates": [],
                    "stoppedFromDate": "2026-10-01",
                },
                "Weekly",
            ),
            activity(
                {
                    "mode": "interval_days",
                    "startDate": "2026-09-15",
                    "endDate": "2026-09-15",
                    "indefinite": False,
                    "intervalDays": 1,
                    "slots": [
                        {
                            "id": slot_id(21),
                            "startTime": "08:00",
                            "endTime": "09:00",
                        },
                        {
                            "id": slot_id(22),
                            "startTime": "10:00",
                            "endTime": "11:00",
                        },
                    ],
                },
                "Interval",
            ),
            activity(
                {
                    "mode": "manual_dates",
                    "entries": [
                        {
                            "id": slot_id(31),
                            "date": "2026-09-16",
                            "startTime": "08:00",
                            "endTime": "09:00",
                        },
                        {
                            "id": slot_id(32),
                            "date": "2026-09-16",
                            "startTime": "10:00",
                            "endTime": "11:00",
                        },
                    ],
                    "stoppedFromDate": "2026-10-01",
                },
                "Manual",
            ),
        )

        for payload in payloads:
            response = self._post(payload)
            self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
            response_config = response.get_json()["planItem"]["generationConfig"]
            input_slots = response_config.get("slots", response_config.get("entries"))
            expected_slots = payload["generationConfig"].get(
                "slots", payload["generationConfig"].get("entries")
            )
            self.assertEqual(
                [slot["id"] for slot in input_slots],
                [slot["id"] for slot in expected_slots],
            )

        state_response = self._get_state()
        self.assertEqual(state_response.status_code, 200)
        state = state_response.get_json()
        self.assertEqual(len(state["planItems"]), 3)
        self.assertEqual(len(state["occurrences"]), 6)
        self.assertTrue(
            all("sourceGenerationSlotId" in item for item in state["occurrences"])
        )

        with psycopg.connect(self.database_url) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.generation_slot_weekdays"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.generation_slot_dates"
                ).fetchone()[0],
                2,
            )

    def test_full_lifecycle_weekly(self):
        slots = [
            {"id": slot_id(1011), "isoWeekday": 1, "startTime": "08:00", "endTime": "09:00"},
            {"id": slot_id(1012), "isoWeekday": 1, "startTime": "10:00", "endTime": "11:00"},
            {"id": slot_id(1013), "isoWeekday": 2, "startTime": "14:00", "endTime": "15:00"},
            {"id": slot_id(1014), "isoWeekday": 2, "startTime": "16:00", "endTime": "17:00"},
        ]
        created_response = self._post(
            activity(
                {
                    "mode": "weekly",
                    "startDate": "2026-09-14",
                    "endDate": "2026-10-12",
                    "indefinite": False,
                    "slots": slots,
                },
                "Weekly lifecycle",
            )
        )
        self.assertEqual(created_response.status_code, 201, created_response.get_data(as_text=True))
        created = created_response.get_json()
        plan_item_id = created["planItem"]["id"]

        first_state = self._get_state().get_json()
        first_item = next(item for item in first_state["planItems"] if item["id"] == plan_item_id)
        self.assertEqual(
            [slot["id"] for slot in first_item["generationConfig"]["slots"]],
            [slot["id"] for slot in slots],
        )
        first_occurrences = [
            item for item in first_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        single_edit = next(
            item for item in first_occurrences
            if item["date"] == "2026-09-21" and item["sourceGenerationSlotId"] == slot_id(1011)
        )
        single_delete = next(
            item for item in first_occurrences
            if item["date"] == "2026-09-21" and item["sourceGenerationSlotId"] == slot_id(1012)
        )
        patched = self._patch_occurrence(
            single_edit["id"],
            {"date": "2026-09-21", "startTime": "08:30", "endTime": "09:30"},
        )
        self.assertEqual(patched.status_code, 200, patched.get_data(as_text=True))
        deleted = self._delete_occurrence(single_delete["id"])
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))

        single_state = self._get_state().get_json()
        single_item = next(item for item in single_state["planItems"] if item["id"] == plan_item_id)
        single_rows = {
            item["id"]: item
            for item in single_state["occurrences"]
            if item["planItemId"] == plan_item_id
        }
        self.assertEqual(single_rows[single_edit["id"]]["startTime"], "08:30")
        self.assertEqual(single_rows[single_edit["id"]]["sourceGenerationSlotId"], slot_id(1011))
        self.assertNotIn(single_delete["id"], single_rows)
        deleted_slot = next(
            slot for slot in single_item["generationConfig"]["slots"]
            if slot["id"] == slot_id(1012)
        )
        self.assertEqual(deleted_slot["excludedDates"], ["2026-09-21"])

        week_rows = [
            item for item in single_state["occurrences"]
            if item["planItemId"] == plan_item_id and item["date"] == "2026-09-22"
        ]
        week_update = next(item for item in week_rows if item["sourceGenerationSlotId"] == slot_id(1013))
        week_delete = next(item for item in week_rows if item["sourceGenerationSlotId"] == slot_id(1014))
        week_response = self._apply_week(
            plan_item_id,
            {
                "anchorDate": "2026-09-22",
                "operations": [
                    {
                        "type": "update",
                        "occurrenceId": week_update["id"],
                        "date": "2026-09-22",
                        "startTime": "14:30",
                        "endTime": "15:30",
                    },
                    {"type": "delete", "occurrenceId": week_delete["id"]},
                    {"type": "create", "date": "2026-09-25", "startTime": "20:00", "endTime": "21:00"},
                ],
            },
        )
        self.assertEqual(week_response.status_code, 200, week_response.get_data(as_text=True))

        week_state = self._get_state().get_json()
        week_item = next(item for item in week_state["planItems"] if item["id"] == plan_item_id)
        self.assertEqual(
            [(slot["id"], slot["startTime"], slot["endTime"]) for slot in week_item["generationConfig"]["slots"]],
            [(slot["id"], slot["startTime"], slot["endTime"]) for slot in slots],
        )
        week_occurrences = [
            item for item in week_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        self.assertTrue(any(
            item["id"] == week_update["id"] and item["startTime"] == "14:30"
            for item in week_occurrences
        ))
        self.assertFalse(any(item["id"] == week_delete["id"] for item in week_occurrences))
        ad_hoc = next(item for item in week_occurrences if item["date"] == "2026-09-25")
        self.assertNotIn("sourceGenerationSlotId", ad_hoc)
        self.assertTrue(any(
            item["date"] == "2026-09-29"
            and item.get("sourceGenerationSlotId") == slot_id(1013)
            and item["startTime"] == "14:00"
            for item in week_occurrences
        ))

        future_response = self._apply_future(
            plan_item_id,
            {
                "futureConfig": {
                    "mode": "weekly",
                    "startDate": "2026-09-28",
                    "endDate": "2026-10-12",
                    "indefinite": False,
                    "slots": [
                        {"id": slot_id(1011), "isoWeekday": 1, "startTime": "09:00", "endTime": "10:00"},
                        {"id": slot_id(1013), "isoWeekday": 2, "startTime": "14:00", "endTime": "15:00"},
                        {"id": slot_id(1015), "isoWeekday": 3, "startTime": "20:00", "endTime": "22:00"},
                    ],
                }
            },
        )
        self.assertEqual(future_response.status_code, 200, future_response.get_data(as_text=True))

        final_state = self._get_state().get_json()
        final_item = next(item for item in final_state["planItems"] if item["id"] == plan_item_id)
        final_rows = [
            item for item in final_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        self.assertEqual(final_item["generationConfig"]["startDate"], "2026-09-28")
        self.assertEqual(
            {slot["id"] for slot in final_item["generationConfig"]["slots"]},
            {slot_id(1011), slot_id(1013), slot_id(1015)},
        )
        self.assertEqual(next(item for item in final_rows if item["id"] == single_edit["id"])["startTime"], "08:30")
        self.assertEqual(next(item for item in final_rows if item["id"] == week_update["id"])["startTime"], "14:30")
        self.assertEqual(next(item for item in final_rows if item["id"] == ad_hoc["id"])["startTime"], "20:00")
        self.assertTrue(any(
            item["date"] == "2026-09-30" and item.get("sourceGenerationSlotId") == slot_id(1015)
            for item in final_rows
        ))
        self.assertFalse(any(
            item["date"] < "2026-09-28" and item.get("sourceGenerationSlotId") == slot_id(1015)
            for item in final_rows
        ))

    def test_full_lifecycle_interval_days(self):
        slots = [
            {"id": slot_id(2011), "startTime": "08:00", "endTime": "09:00"},
            {"id": slot_id(2012), "startTime": "18:00", "endTime": "19:00"},
        ]
        created_response = self._post(
            activity(
                {
                    "mode": "interval_days",
                    "startDate": "2026-09-14",
                    "endDate": "2026-10-10",
                    "indefinite": False,
                    "intervalDays": 2,
                    "slots": slots,
                },
                "Interval lifecycle",
            )
        )
        self.assertEqual(created_response.status_code, 201, created_response.get_data(as_text=True))
        plan_item_id = created_response.get_json()["planItem"]["id"]
        first_state = self._get_state().get_json()
        first_rows = [
            item for item in first_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        single_edit = next(
            item for item in first_rows
            if item["date"] == "2026-09-16" and item["sourceGenerationSlotId"] == slot_id(2011)
        )
        single_delete = next(
            item for item in first_rows
            if item["date"] == "2026-09-16" and item["sourceGenerationSlotId"] == slot_id(2012)
        )
        self.assertEqual(
            self._patch_occurrence(single_edit["id"], {"date": "2026-09-16", "startTime": "08:15", "endTime": "09:15"}).status_code,
            200,
        )
        self.assertEqual(self._delete_occurrence(single_delete["id"]).status_code, 200)

        single_state = self._get_state().get_json()
        single_rows = [
            item for item in single_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        self.assertEqual(next(item for item in single_rows if item["id"] == single_edit["id"])["startTime"], "08:15")
        self.assertFalse(any(item["id"] == single_delete["id"] for item in single_rows))
        week_update = next(
            item for item in single_rows
            if item["date"] == "2026-09-22" and item["sourceGenerationSlotId"] == slot_id(2011)
        )
        week_delete = next(
            item for item in single_rows
            if item["date"] == "2026-09-22" and item["sourceGenerationSlotId"] == slot_id(2012)
        )
        week_response = self._apply_week(
            plan_item_id,
            {
                "anchorDate": "2026-09-22",
                "operations": [
                    {
                        "type": "update",
                        "occurrenceId": week_update["id"],
                        "date": "2026-09-22",
                        "startTime": "09:00",
                        "endTime": "10:00",
                    },
                    {"type": "delete", "occurrenceId": week_delete["id"]},
                    {"type": "create", "date": "2026-09-25", "startTime": "20:00", "endTime": "21:00"},
                ],
            },
        )
        self.assertEqual(week_response.status_code, 200, week_response.get_data(as_text=True))
        week_state = self._get_state().get_json()
        week_rows = [
            item for item in week_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        ad_hoc = next(item for item in week_rows if item["date"] == "2026-09-25")
        self.assertTrue(any(
            item["date"] == "2026-09-30"
            and item.get("sourceGenerationSlotId") == slot_id(2011)
            and item["startTime"] == "08:00"
            for item in week_rows
        ))

        future_response = self._apply_future(
            plan_item_id,
            {
                "futureConfig": {
                    "mode": "interval_days",
                    "startDate": "2026-09-28",
                    "endDate": "2026-10-10",
                    "indefinite": False,
                    "intervalDays": 3,
                    "slots": [
                        {"id": slot_id(2011), "startTime": "10:00", "endTime": "11:00"},
                        {"id": slot_id(2013), "startTime": "20:00", "endTime": "21:00"},
                    ],
                }
            },
        )
        self.assertEqual(future_response.status_code, 200, future_response.get_data(as_text=True))
        final_state = self._get_state().get_json()
        final_item = next(item for item in final_state["planItems"] if item["id"] == plan_item_id)
        final_rows = [
            item for item in final_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        self.assertEqual(final_item["generationConfig"]["intervalDays"], 3)
        self.assertEqual(
            {slot["id"] for slot in final_item["generationConfig"]["slots"]},
            {slot_id(2011), slot_id(2013)},
        )
        self.assertEqual(next(item for item in final_rows if item["id"] == single_edit["id"])["startTime"], "08:15")
        self.assertEqual(next(item for item in final_rows if item["id"] == week_update["id"])["startTime"], "09:00")
        self.assertEqual(next(item for item in final_rows if item["id"] == ad_hoc["id"])["startTime"], "20:00")
        self.assertEqual(
            sorted({item["date"] for item in future_response.get_json()["occurrences"]}),
            ["2026-09-28", "2026-10-01", "2026-10-04", "2026-10-07", "2026-10-10"],
        )

    def test_full_lifecycle_manual_dates(self):
        entries = [
            {"id": slot_id(3011), "date": "2026-09-21", "startTime": "08:00", "endTime": "09:00"},
            {"id": slot_id(3012), "date": "2026-09-21", "startTime": "10:00", "endTime": "11:00"},
            {"id": slot_id(3013), "date": "2026-09-22", "startTime": "12:00", "endTime": "13:00"},
        ]
        created_response = self._post(
            activity({"mode": "manual_dates", "entries": entries}, "Manual lifecycle")
        )
        self.assertEqual(created_response.status_code, 201, created_response.get_data(as_text=True))
        created = created_response.get_json()
        plan_item_id = created["planItem"]["id"]
        first_state = self._get_state().get_json()
        first_item = next(item for item in first_state["planItems"] if item["id"] == plan_item_id)
        self.assertEqual(
            [entry["id"] for entry in first_item["generationConfig"]["entries"]],
            [entry["id"] for entry in entries],
        )
        first_rows = [
            item for item in first_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        first = next(item for item in first_rows if item["sourceGenerationSlotId"] == slot_id(3011))
        second = next(item for item in first_rows if item["sourceGenerationSlotId"] == slot_id(3012))
        third = next(item for item in first_rows if item["sourceGenerationSlotId"] == slot_id(3013))

        patched = self._patch_occurrence(
            first["id"],
            {"date": "2026-09-21", "startTime": "08:30", "endTime": "09:30"},
        )
        self.assertEqual(patched.status_code, 200, patched.get_data(as_text=True))
        self.assertEqual(self._delete_occurrence(second["id"]).status_code, 200)
        middle_state = self._get_state().get_json()
        middle_item = next(item for item in middle_state["planItems"] if item["id"] == plan_item_id)
        self.assertEqual(
            {entry["id"] for entry in middle_item["generationConfig"]["entries"]},
            {slot_id(3011), slot_id(3013)},
        )
        updated_entry = next(
            entry for entry in middle_item["generationConfig"]["entries"]
            if entry["id"] == slot_id(3011)
        )
        self.assertEqual((updated_entry["startTime"], updated_entry["endTime"]), ("08:30", "09:30"))

        self.assertEqual(self._delete_occurrence(third["id"]).status_code, 200)
        rejected = self._delete_occurrence(first["id"])
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.get_json()["code"], "last_manual_entry")
        final_state = self._get_state().get_json()
        final_item = next(item for item in final_state["planItems"] if item["id"] == plan_item_id)
        final_rows = [
            item for item in final_state["occurrences"] if item["planItemId"] == plan_item_id
        ]
        self.assertEqual([entry["id"] for entry in final_item["generationConfig"]["entries"]], [slot_id(3011)])
        self.assertEqual([item["id"] for item in final_rows], [first["id"]])
        self.assertEqual(final_rows[0]["startTime"], "08:30")

    def test_migration_003_preserves_legacy_graph_and_only_safe_provenance(self):
        try:
            with psycopg.connect(self.database_url, autocommit=True) as connection:
                connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
                connection.execute("CREATE SCHEMA public")
                for migration_name in CURRENT_MIGRATIONS[:2]:
                    connection.execute(
                        (MIGRATION_DIRECTORY / migration_name).read_text(encoding="utf-8")
                    )

            with psycopg.connect(self.database_url) as connection:
                connection.execute(
                    """
                    INSERT INTO public.plan_items (id, name, kind, subtype) VALUES
                        ('00000000-0000-0000-0000-000000011001', 'Legacy weekly', 'activity', 'periodic'),
                        ('00000000-0000-0000-0000-000000011002', 'Legacy interval', 'habit', 'scheduled'),
                        ('00000000-0000-0000-0000-000000011003', 'Legacy manual', 'activity', 'event');

                    INSERT INTO public.generation_configs (
                        plan_item_id, mode, start_date, end_date, indefinite,
                        default_start_time, default_end_time, interval_days
                    ) VALUES
                        ('00000000-0000-0000-0000-000000011001', 'weekly', '2026-09-01', NULL, TRUE, '08:00', '09:00', NULL),
                        ('00000000-0000-0000-0000-000000011002', 'interval_days', '2026-09-01', '2026-09-30', FALSE, '06:00', '07:00', 2),
                        ('00000000-0000-0000-0000-000000011003', 'manual_dates', NULL, NULL, FALSE, NULL, NULL, NULL);

                    INSERT INTO public.generation_weekdays (
                        plan_item_id, iso_weekday, override_start_time, override_end_time
                    ) VALUES
                        ('00000000-0000-0000-0000-000000011001', 1, NULL, NULL),
                        ('00000000-0000-0000-0000-000000011001', 3, '10:00', '11:00');

                    INSERT INTO public.generation_date_entries (
                        id, plan_item_id, entry_date, start_time, end_time
                    ) VALUES
                        ('00000000-0000-4000-8000-000000012001', '00000000-0000-0000-0000-000000011003', '2026-09-18', '08:00', '09:00'),
                        ('00000000-0000-4000-8000-000000012002', '00000000-0000-0000-0000-000000011003', '2026-09-18', '10:00', '11:00');

                    INSERT INTO public.generation_excluded_dates (plan_item_id, excluded_date)
                    VALUES ('00000000-0000-0000-0000-000000011001', '2026-09-28');

                    INSERT INTO public.occurrences (
                        id, plan_item_id, occurrence_date, start_time, end_time, status
                    ) VALUES
                        ('00000000-0000-0000-0000-000000013001', '00000000-0000-0000-0000-000000011001', '2026-09-14', '08:00', '09:00', 'completed'),
                        ('00000000-0000-0000-0000-000000013002', '00000000-0000-0000-0000-000000011001', '2026-09-21', '08:00', '09:00', 'pending'),
                        ('00000000-0000-0000-0000-000000013003', '00000000-0000-0000-0000-000000011001', '2026-09-21', '12:00', '13:00', 'pending'),
                        ('00000000-0000-0000-0000-000000013004', '00000000-0000-0000-0000-000000011001', '2026-09-16', '10:00', '11:00', 'pending'),
                        ('00000000-0000-0000-0000-000000013005', '00000000-0000-0000-0000-000000011002', '2026-09-15', '06:00', '07:00', 'pending'),
                        ('00000000-0000-0000-0000-000000013006', '00000000-0000-0000-0000-000000011003', '2026-09-18', '08:00', '09:00', 'pending'),
                        ('00000000-0000-0000-0000-000000013007', '00000000-0000-0000-0000-000000011003', '2026-09-18', '10:00', '11:00', 'pending'),
                        ('00000000-0000-0000-0000-000000013008', '00000000-0000-0000-0000-000000011003', '2026-09-18', '12:00', '13:00', 'pending');
                    """
                )
                before_occurrences = connection.execute(
                    """
                    SELECT id::text, plan_item_id::text, occurrence_date::text,
                           start_time::text, end_time::text, status
                    FROM public.occurrences
                    ORDER BY id
                    """
                ).fetchall()

            with psycopg.connect(self.database_url, autocommit=True) as connection:
                connection.execute(
                    (MIGRATION_DIRECTORY / CURRENT_MIGRATIONS[2]).read_text(encoding="utf-8")
                )

            with psycopg.connect(self.database_url) as connection:
                after_occurrences = connection.execute(
                    """
                    SELECT id::text, plan_item_id::text, occurrence_date::text,
                           start_time::text, end_time::text, status
                    FROM public.occurrences
                    ORDER BY id
                    """
                ).fetchall()
                self.assertEqual(after_occurrences, before_occurrences)

                weekly_slots = connection.execute(
                    """
                    SELECT weekday.iso_weekday, slot.start_time::text, slot.end_time::text
                    FROM public.generation_slots AS slot
                    JOIN public.generation_slot_weekdays AS weekday ON weekday.slot_id = slot.id
                    WHERE slot.plan_item_id = '00000000-0000-0000-0000-000000011001'
                    ORDER BY weekday.iso_weekday
                    """
                ).fetchall()
                self.assertEqual(weekly_slots, [(1, "08:00:00", "09:00:00"), (3, "10:00:00", "11:00:00")])

                interval_slots = connection.execute(
                    """
                    SELECT start_time::text, end_time::text
                    FROM public.generation_slots
                    WHERE plan_item_id = '00000000-0000-0000-0000-000000011002'
                    """
                ).fetchall()
                self.assertEqual(interval_slots, [("06:00:00", "07:00:00")])

                manual_slots = connection.execute(
                    """
                    SELECT slot.id::text, slot_date.entry_date::text,
                           slot.start_time::text, slot.end_time::text
                    FROM public.generation_slots AS slot
                    JOIN public.generation_slot_dates AS slot_date ON slot_date.slot_id = slot.id
                    WHERE slot.plan_item_id = '00000000-0000-0000-0000-000000011003'
                    ORDER BY slot.id
                    """
                ).fetchall()
                self.assertEqual(
                    manual_slots,
                    [
                        ("00000000-0000-4000-8000-000000012001", "2026-09-18", "08:00:00", "09:00:00"),
                        ("00000000-0000-4000-8000-000000012002", "2026-09-18", "10:00:00", "11:00:00"),
                    ],
                )

                provenance = dict(connection.execute(
                    """
                    SELECT id::text, source_generation_slot_id::text
                    FROM public.occurrences
                    ORDER BY id
                    """
                ).fetchall())
                self.assertIsNotNone(provenance["00000000-0000-0000-0000-000000013001"])
                self.assertIsNone(provenance["00000000-0000-0000-0000-000000013002"])
                self.assertIsNone(provenance["00000000-0000-0000-0000-000000013003"])
                self.assertIsNotNone(provenance["00000000-0000-0000-0000-000000013004"])
                self.assertIsNotNone(provenance["00000000-0000-0000-0000-000000013005"])
                self.assertEqual(
                    provenance["00000000-0000-0000-0000-000000013006"],
                    "00000000-0000-4000-8000-000000012001",
                )
                self.assertEqual(
                    provenance["00000000-0000-0000-0000-000000013007"],
                    "00000000-0000-4000-8000-000000012002",
                )
                self.assertIsNone(provenance["00000000-0000-0000-0000-000000013008"])
                self.assertEqual(
                    connection.execute(
                        "SELECT excluded_date::text FROM public.generation_excluded_dates"
                    ).fetchall(),
                    [("2026-09-28",)],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT to_regclass('public.generation_weekdays'), to_regclass('public.generation_date_entries')"
                    ).fetchone(),
                    (None, None),
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'generation_configs'
                          AND column_name IN ('default_start_time', 'default_end_time')
                        """
                    ).fetchone()[0],
                    0,
                )
        finally:
            self._reset_current_schema()

    def test_partial_idempotency_index(self):
        response = self._post(
            activity(
                {
                    "mode": "manual_dates",
                    "entries": [
                        {
                            "id": slot_id(41),
                            "date": "2026-09-14",
                            "startTime": "08:00",
                            "endTime": "09:00",
                        },
                        {
                            "id": slot_id(42),
                            "date": "2026-09-14",
                            "startTime": "10:00",
                            "endTime": "11:00",
                        },
                    ],
                }
            )
        )
        self.assertEqual(response.status_code, 201)
        plan_item_id = response.get_json()["planItem"]["id"]

        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                UPDATE public.generation_slots
                SET start_time = '07:00', end_time = '08:00'
                WHERE id = %s
                """,
                (slot_id(41),),
            )
            historical_occurrence = connection.execute(
                """
                SELECT start_time, end_time, status, source_generation_slot_id
                FROM public.occurrences
                WHERE plan_item_id = %s AND source_generation_slot_id = %s
                """,
                (plan_item_id, slot_id(41)),
            ).fetchone()
            self.assertEqual(str(historical_occurrence[0]), "08:00:00")
            self.assertEqual(str(historical_occurrence[1]), "09:00:00")
            self.assertEqual(historical_occurrence[2], "pending")
            self.assertEqual(str(historical_occurrence[3]), slot_id(41))

            with self.assertRaises(psycopg.errors.UniqueViolation):
                connection.execute(
                    """
                    INSERT INTO public.occurrences (
                        id, plan_item_id, occurrence_date, start_time,
                        end_time, status, source_generation_slot_id
                    ) VALUES (
                        gen_random_uuid(), %s, '2026-09-14', '12:00',
                        '13:00', 'pending', %s
                    )
                    """,
                    (plan_item_id, slot_id(41)),
                )

    def test_each_insert_stage_rolls_back_the_complete_graph(self):
        cases = (
            ("generation_configs", manual_payload(51)),
            ("generation_slots", manual_payload(52)),
            ("generation_slot_dates", manual_payload(53)),
            (
                "generation_slot_weekdays",
                activity(
                    {
                        "mode": "weekly",
                        "startDate": "2026-09-14",
                        "endDate": "2026-09-14",
                        "indefinite": False,
                        "slots": [
                            {
                                "id": slot_id(54),
                                "isoWeekday": 1,
                                "startTime": "08:00",
                                "endTime": "09:00",
                            }
                        ],
                    }
                ),
            ),
            (
                "generation_excluded_dates",
                activity(
                    {
                        "mode": "weekly",
                        "startDate": "2026-09-14",
                        "endDate": "2026-09-14",
                        "indefinite": False,
                        "slots": [
                            {
                                "id": slot_id(55),
                                "isoWeekday": 1,
                                "startTime": "08:00",
                                "endTime": "09:00",
                            }
                        ],
                        "excludedDates": ["2026-09-15"],
                    }
                ),
            ),
            (
                "generation_slot_excluded_dates",
                activity(
                    {
                        "mode": "weekly",
                        "startDate": "2026-09-14",
                        "endDate": "2026-09-14",
                        "indefinite": False,
                        "slots": [
                            {
                                "id": slot_id(57),
                                "isoWeekday": 1,
                                "startTime": "08:00",
                                "endTime": "09:00",
                                "excludedDates": ["2026-09-14"],
                            }
                        ],
                    }
                ),
            ),
            ("occurrences", manual_payload(56)),
        )

        for table_name, payload in cases:
            with self.subTest(table=table_name):
                trigger_name = f"reject_{table_name}_insert"
                with psycopg.connect(self.database_url, autocommit=True) as connection:
                    connection.execute(
                        f"""
                        CREATE TRIGGER {trigger_name}
                        BEFORE INSERT ON public.{table_name}
                        FOR EACH ROW EXECUTE FUNCTION public.reject_test_insert()
                        """
                    )
                try:
                    response = self._post(payload)
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(self._counts(), (0, 0, 0, 0))
                finally:
                    with psycopg.connect(
                        self.database_url, autocommit=True
                    ) as connection:
                        connection.execute(
                            f"DROP TRIGGER IF EXISTS {trigger_name} ON public.{table_name}"
                        )

    def test_inconsistent_persisted_state_returns_sanitized_500(self):
        with psycopg.connect(self.database_url) as connection:
            plan_item_id = connection.execute("SELECT gen_random_uuid()").fetchone()[0]
            connection.execute(
                """
                INSERT INTO public.plan_items (id, name, kind, subtype)
                VALUES (%s, 'Incomplete', 'activity', 'periodic')
                """,
                (plan_item_id,),
            )
            connection.execute(
                """
                INSERT INTO public.generation_configs (
                    plan_item_id, mode, indefinite
                ) VALUES (%s, 'manual_dates', FALSE)
                """,
                (plan_item_id,),
            )

        response = self._get_state()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("generation", response.get_data(as_text=True).lower())

    def test_uber_week_persists_seventeen_occurrences(self):
        slots = []
        sequence = 100
        for weekday in range(1, 6):
            for start_time, end_time in (
                ("08:00", "11:00"),
                ("14:00", "17:00"),
                ("20:00", "22:00"),
            ):
                sequence += 1
                slots.append(
                    {
                        "id": slot_id(sequence),
                        "isoWeekday": weekday,
                        "startTime": start_time,
                        "endTime": end_time,
                    }
                )
        for weekday in (6, 7):
            sequence += 1
            slots.append(
                {
                    "id": slot_id(sequence),
                    "isoWeekday": weekday,
                    "startTime": "08:00",
                    "endTime": "21:00",
                }
            )

        response = self._post(
            activity(
                {
                    "mode": "weekly",
                    "startDate": "2026-09-14",
                    "endDate": "2026-09-20",
                    "indefinite": False,
                    "slots": slots,
                },
                "Uber",
            )
        )

        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        result = response.get_json()
        self.assertEqual(len(result["occurrences"]), 17)
        self.assertEqual(
            {item["sourceGenerationSlotId"] for item in result["occurrences"]},
            {slot["id"] for slot in slots},
        )
        self.assertEqual(self._counts()[3], 17)

    def test_medication_habit_persists_three_occurrences_per_interval_date(self):
        slots = [
            {"id": slot_id(151), "startTime": "08:00", "endTime": "08:05"},
            {"id": slot_id(152), "startTime": "14:00", "endTime": "14:05"},
            {"id": slot_id(153), "startTime": "22:00", "endTime": "22:05"},
        ]
        response = self._post(
            {
                "name": "Medicamento",
                "kind": "habit",
                "habitType": "scheduled",
                "generationConfig": {
                    "mode": "interval_days",
                    "startDate": "2026-09-14",
                    "endDate": "2026-09-16",
                    "indefinite": False,
                    "intervalDays": 1,
                    "slots": slots,
                },
            }
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        result = response.get_json()
        self.assertEqual(result["planItem"]["habitType"], "scheduled")
        self.assertNotIn("activityType", result["planItem"])
        occurrences_by_date = {}
        for occurrence in result["occurrences"]:
            occurrences_by_date.setdefault(occurrence["date"], []).append(occurrence)
        self.assertEqual(
            sorted(occurrences_by_date),
            ["2026-09-14", "2026-09-15", "2026-09-16"],
        )
        self.assertTrue(all(len(items) == 3 for items in occurrences_by_date.values()))
        self.assertTrue(all(
            {item["sourceGenerationSlotId"] for item in items}
            == {slot["id"] for slot in slots}
            for items in occurrences_by_date.values()
        ))

    def test_recurring_delete_is_slot_scoped_and_rematerialization_safe(self):
        created = self._post(self._weekly_two_slot_payload()).get_json()
        by_source = {
            occurrence["sourceGenerationSlotId"]: occurrence
            for occurrence in created["occurrences"]
        }
        first = by_source[slot_id(701)]
        second = by_source[slot_id(702)]

        response = self._delete_occurrence(second["id"])
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(
            response.get_json(), {"deletedOccurrenceId": second["id"]}
        )

        with psycopg.connect(self.database_url) as connection:
            self.assertIsNotNone(
                connection.execute(
                    "SELECT 1 FROM public.occurrences WHERE id = %s", (first["id"],)
                ).fetchone()
            )
            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM public.occurrences WHERE id = %s", (second["id"],)
                ).fetchone()
            )
            self.assertEqual(
                connection.execute(
                    """
                    SELECT slot_id::text, excluded_date::text
                    FROM public.generation_slot_excluded_dates
                    ORDER BY slot_id
                    """
                ).fetchall(),
                [(slot_id(702), "2026-09-14")],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.generation_slots"
                ).fetchone()[0],
                2,
            )

        state = self._get_state().get_json()
        config = state["planItems"][0]["generationConfig"]
        excluded_slot = next(slot for slot in config["slots"] if slot["id"] == slot_id(702))
        self.assertEqual(excluded_slot["excludedDates"], ["2026-09-14"])
        drafts = materialize_occurrence_drafts(
            state["planItems"][0], date(2026, 9, 14), date(2026, 9, 14)
        )
        self.assertEqual(
            [draft["sourceGenerationSlotId"] for draft in drafts], [slot_id(701)]
        )
        existing_keys = {
            (occurrence.get("sourceGenerationSlotId"), occurrence["date"])
            for occurrence in state["occurrences"]
        }
        self.assertEqual(
            [draft for draft in drafts if (draft["sourceGenerationSlotId"], draft["date"]) not in existing_keys],
            [],
        )

    def test_concurrent_delete_has_one_winner_and_one_controlled_rejection(self):
        created = self._post(self._weekly_two_slot_payload()).get_json()
        target = next(
            occurrence
            for occurrence in created["occurrences"]
            if occurrence["sourceGenerationSlotId"] == slot_id(702)
        )

        def attempt_delete():
            try:
                mutation_service.delete_occurrence(
                    target["id"], reference_date=REFERENCE_DATE
                )
                return "deleted"
            except mutation_service.OccurrenceNotFoundError:
                return "not_found"
            except mutation_service.OccurrenceConflictError as error:
                return error.code

        with patch.object(database, "get_database_url", return_value=self.database_url):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _index: attempt_delete(), range(2)))

        self.assertEqual(results.count("deleted"), 1)
        self.assertIn(
            next(result for result in results if result != "deleted"),
            {"not_found", "concurrent_conflict"},
        )
        with psycopg.connect(self.database_url) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.occurrences WHERE id = %s",
                    (target["id"],),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.generation_slot_excluded_dates
                    WHERE slot_id = %s AND excluded_date = '2026-09-14'
                    """,
                    (slot_id(702),),
                ).fetchone()[0],
                1,
            )

    def test_recurring_patch_same_date_and_move_date_preserve_provenance(self):
        created = self._post(self._weekly_two_slot_payload()).get_json()
        second = next(
            occurrence
            for occurrence in created["occurrences"]
            if occurrence["sourceGenerationSlotId"] == slot_id(702)
        )

        same_date = self._patch_occurrence(
            second["id"],
            {"date": "2026-09-14", "startTime": "15:00", "endTime": "18:00"},
        )
        self.assertEqual(same_date.status_code, 200, same_date.get_data(as_text=True))
        self.assertEqual(
            same_date.get_json()["occurrence"]["sourceGenerationSlotId"],
            slot_id(702),
        )
        self.assertEqual(same_date.get_json()["occurrence"]["id"], second["id"])
        with psycopg.connect(self.database_url) as connection:
            slot_times = connection.execute(
                "SELECT start_time, end_time FROM public.generation_slots WHERE id = %s",
                (slot_id(702),),
            ).fetchone()
            self.assertEqual(tuple(map(str, slot_times)), ("14:00:00", "17:00:00"))

        moved = self._patch_occurrence(
            second["id"],
            {"date": "2026-09-15", "startTime": "15:00", "endTime": "18:00"},
        )
        self.assertEqual(moved.status_code, 200, moved.get_data(as_text=True))
        occurrence = moved.get_json()["occurrence"]
        self.assertEqual(occurrence["date"], "2026-09-15")
        self.assertEqual(occurrence["sourceGenerationSlotId"], slot_id(702))
        with psycopg.connect(self.database_url) as connection:
            self.assertEqual(
                connection.execute(
                    """
                    SELECT excluded_date::text
                    FROM public.generation_slot_excluded_dates
                    WHERE slot_id = %s
                    """,
                    (slot_id(702),),
                ).fetchall(),
                [("2026-09-14",)],
            )

    def test_recurring_move_rejects_existing_source_slot_on_target_date(self):
        created = self._post(self._weekly_two_slot_payload()).get_json()
        second = next(
            occurrence
            for occurrence in created["occurrences"]
            if occurrence["sourceGenerationSlotId"] == slot_id(702)
        )
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO public.occurrences (
                    id, plan_item_id, occurrence_date, start_time, end_time,
                    status, source_generation_slot_id
                ) VALUES (
                    gen_random_uuid(), %s, '2026-09-15', '19:00', '20:00',
                    'cancelled', %s
                )
                """,
                (created["planItem"]["id"], slot_id(702)),
            )

        response = self._patch_occurrence(
            second["id"],
            {"date": "2026-09-15", "startTime": "15:00", "endTime": "18:00"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "slot_date_conflict")
        with psycopg.connect(self.database_url) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT occurrence_date::text FROM public.occurrences WHERE id = %s",
                    (second["id"],),
                ).fetchone()[0],
                "2026-09-14",
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.generation_slot_excluded_dates"
                ).fetchone()[0],
                0,
            )

    def test_manual_patch_delete_and_last_entry_protection(self):
        payload = activity(
            {
                "mode": "manual_dates",
                "entries": [
                    {
                        "id": slot_id(711),
                        "date": "2026-09-15",
                        "startTime": "08:00",
                        "endTime": "09:00",
                    },
                    {
                        "id": slot_id(712),
                        "date": "2026-09-16",
                        "startTime": "10:00",
                        "endTime": "11:00",
                    },
                ],
            }
        )
        created = self._post(payload).get_json()
        by_source = {
            occurrence["sourceGenerationSlotId"]: occurrence
            for occurrence in created["occurrences"]
        }
        second = by_source[slot_id(712)]
        response = self._patch_occurrence(
            second["id"],
            {"date": "2026-09-17", "startTime": "12:00", "endTime": "13:00"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["occurrence"]["id"], second["id"])
        self.assertEqual(
            response.get_json()["occurrence"]["sourceGenerationSlotId"],
            slot_id(712),
        )
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                SELECT slot.start_time, slot.end_time, slot_date.entry_date,
                       occurrence.occurrence_date, occurrence.start_time,
                       occurrence.end_time, occurrence.source_generation_slot_id
                FROM public.generation_slots AS slot
                JOIN public.generation_slot_dates AS slot_date ON slot_date.slot_id = slot.id
                JOIN public.occurrences AS occurrence ON occurrence.source_generation_slot_id = slot.id
                WHERE slot.id = %s
                """,
                (slot_id(712),),
            ).fetchone()
            self.assertEqual(tuple(map(str, row)), (
                "12:00:00", "13:00:00", "2026-09-17", "2026-09-17",
                "12:00:00", "13:00:00", slot_id(712),
            ))

        deleted = self._delete_occurrence(second["id"])
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))
        with psycopg.connect(self.database_url) as connection:
            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM public.generation_slots WHERE id = %s",
                    (slot_id(712),),
                ).fetchone()
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.generation_slot_dates"
                ).fetchone()[0],
                1,
            )

        last = self._delete_occurrence(by_source[slot_id(711)]["id"])
        self.assertEqual(last.status_code, 409)
        self.assertEqual(last.get_json()["code"], "last_manual_entry")
        self.assertEqual(self._counts()[2:], (1, 1))

    def test_ad_hoc_patch_and_delete_do_not_change_generation(self):
        created = self._post(
            activity(
                {
                    "mode": "manual_dates",
                    "entries": [
                        {
                            "id": slot_id(721),
                            "date": "2026-09-15",
                            "startTime": "08:00",
                            "endTime": "09:00",
                        }
                    ],
                }
            )
        ).get_json()
        plan_item_id = created["planItem"]["id"]
        with psycopg.connect(self.database_url) as connection:
            ad_hoc_id = connection.execute("SELECT gen_random_uuid()").fetchone()[0]
            connection.execute(
                """
                INSERT INTO public.occurrences (
                    id, plan_item_id, occurrence_date, start_time, end_time, status
                ) VALUES (%s, %s, '2026-09-16', '10:00', '11:00', 'pending')
                """,
                (ad_hoc_id, plan_item_id),
            )

        response = self._patch_occurrence(
            ad_hoc_id,
            {"date": "2026-09-17", "startTime": "12:00", "endTime": "13:00"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertNotIn("sourceGenerationSlotId", response.get_json()["occurrence"])
        self.assertEqual(self._counts()[2], 1)
        self.assertEqual(self._delete_occurrence(ad_hoc_id).status_code, 200)
        self.assertEqual(self._counts()[2], 1)
        with psycopg.connect(self.database_url) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.generation_slot_excluded_dates"
                ).fetchone()[0],
                0,
            )

    def test_composite_mutation_failures_roll_back_every_stage(self):
        cases = (
            ("recurring_exclusion", "INSERT", "generation_slot_excluded_dates"),
            ("recurring_move", "UPDATE", "occurrences"),
            ("recurring_delete", "DELETE", "occurrences"),
            ("manual_slot_update", "UPDATE", "generation_slots"),
            ("manual_date_update", "UPDATE", "generation_slot_dates"),
            ("manual_patch", "UPDATE", "occurrences"),
            ("manual_delete", "DELETE", "generation_slots"),
        )
        for case_name, event, table_name in cases:
            with self.subTest(case=case_name):
                with psycopg.connect(self.database_url, autocommit=True) as connection:
                    connection.execute("TRUNCATE TABLE public.plan_items CASCADE")
                if case_name.startswith("recurring"):
                    created = self._post(self._weekly_two_slot_payload(case_name)).get_json()
                    target = next(
                        occurrence for occurrence in created["occurrences"]
                        if occurrence["sourceGenerationSlotId"] == slot_id(702)
                    )
                else:
                    created = self._post(
                        activity(
                            {
                                "mode": "manual_dates",
                                "entries": [
                                    {"id": slot_id(731), "date": "2026-09-15", "startTime": "08:00", "endTime": "09:00"},
                                    {"id": slot_id(732), "date": "2026-09-16", "startTime": "10:00", "endTime": "11:00"},
                                ],
                            },
                            case_name,
                        )
                    ).get_json()
                    target = next(
                        occurrence for occurrence in created["occurrences"]
                        if occurrence["sourceGenerationSlotId"] == slot_id(732)
                    )
                trigger_name = f"reject_{case_name}"
                with psycopg.connect(self.database_url, autocommit=True) as connection:
                    connection.execute(
                        f"""
                        CREATE TRIGGER {trigger_name}
                        BEFORE {event} ON public.{table_name}
                        FOR EACH ROW EXECUTE FUNCTION public.reject_test_insert()
                        """
                    )
                try:
                    if case_name in {
                        "recurring_exclusion",
                        "recurring_move",
                        "manual_slot_update",
                        "manual_date_update",
                        "manual_patch",
                    }:
                        response = self._patch_occurrence(
                            target["id"],
                            {"date": "2026-09-17", "startTime": "12:00", "endTime": "13:00"},
                        )
                    else:
                        response = self._delete_occurrence(target["id"])
                    self.assertEqual(response.status_code, 503)
                    state = self._get_state().get_json()
                    persisted = next(
                        occurrence for occurrence in state["occurrences"]
                        if occurrence["id"] == target["id"]
                    )
                    self.assertEqual(persisted["date"], target["date"])
                    self.assertEqual(persisted["startTime"], target["startTime"])
                    self.assertEqual(
                        next(
                            slot for slot in state["planItems"][0]["generationConfig"].get(
                                "slots", state["planItems"][0]["generationConfig"].get("entries")
                            ) if slot["id"] == target["sourceGenerationSlotId"]
                        )["startTime"],
                        target["startTime"],
                    )
                    with psycopg.connect(self.database_url) as connection:
                        self.assertEqual(
                            connection.execute(
                                "SELECT COUNT(*) FROM public.generation_slot_excluded_dates"
                            ).fetchone()[0],
                            0,
                        )
                finally:
                    with psycopg.connect(self.database_url, autocommit=True) as connection:
                        connection.execute(
                            f"DROP TRIGGER IF EXISTS {trigger_name} ON public.{table_name}"
                        )

    def test_apply_week_main_batch_preserves_generation_and_next_week(self):
        created = self._post(self._weekly_apply_payload()).get_json()
        plan_item_id = created["planItem"]["id"]
        current = {
            (item["sourceGenerationSlotId"], item["date"]): item
            for item in created["occurrences"]
            if item["date"] <= "2026-09-20"
        }
        with psycopg.connect(self.database_url) as connection:
            slots_before = connection.execute(
                """
                SELECT id::text, start_time::text, end_time::text
                FROM public.generation_slots
                WHERE plan_item_id = %s
                ORDER BY id
                """,
                (plan_item_id,),
            ).fetchall()
            config_before = connection.execute(
                """
                SELECT mode, start_date::text, end_date::text, indefinite,
                       interval_days, stopped_from_date::text
                FROM public.generation_configs
                WHERE plan_item_id = %s
                """,
                (plan_item_id,),
            ).fetchone()

        response = self._apply_week(
            plan_item_id,
            {
                "anchorDate": "2026-09-16",
                "operations": [
                    {
                        "type": "update",
                        "occurrenceId": current[(slot_id(802), "2026-09-14")]["id"],
                        "date": "2026-09-14",
                        "startTime": "15:00",
                        "endTime": "18:00",
                    },
                    {
                        "type": "delete",
                        "occurrenceId": current[(slot_id(804), "2026-09-15")]["id"],
                    },
                    {
                        "type": "create",
                        "date": "2026-09-16",
                        "startTime": "20:00",
                        "endTime": "21:00",
                    },
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        result = response.get_json()
        self.assertEqual(result["weekStart"], "2026-09-14")
        self.assertEqual(result["weekEnd"], "2026-09-20")
        self.assertEqual(len(result["occurrences"]), 6)
        updated = next(
            item for item in result["occurrences"]
            if item["id"] == current[(slot_id(802), "2026-09-14")]["id"]
        )
        self.assertEqual((updated["startTime"], updated["endTime"]), ("15:00", "18:00"))
        self.assertEqual(updated["sourceGenerationSlotId"], slot_id(802))
        ad_hoc = next(item for item in result["occurrences"] if item["startTime"] == "20:00")
        self.assertNotIn("sourceGenerationSlotId", ad_hoc)
        self.assertEqual(ad_hoc["status"], "pending")

        with psycopg.connect(self.database_url) as connection:
            slots_after = connection.execute(
                """
                SELECT id::text, start_time::text, end_time::text
                FROM public.generation_slots
                WHERE plan_item_id = %s
                ORDER BY id
                """,
                (plan_item_id,),
            ).fetchall()
            config_after = connection.execute(
                """
                SELECT mode, start_date::text, end_date::text, indefinite,
                       interval_days, stopped_from_date::text
                FROM public.generation_configs
                WHERE plan_item_id = %s
                """,
                (plan_item_id,),
            ).fetchone()
            exclusions = connection.execute(
                """
                SELECT slot_id::text, excluded_date::text
                FROM public.generation_slot_excluded_dates
                ORDER BY slot_id, excluded_date
                """
            ).fetchall()
        self.assertEqual(slots_after, slots_before)
        self.assertEqual(config_after, config_before)
        self.assertEqual(exclusions, [(slot_id(804), "2026-09-15")])

        state = self._get_state().get_json()
        next_week = [
            item for item in state["occurrences"]
            if item["planItemId"] == plan_item_id and "2026-09-21" <= item["date"] <= "2026-09-27"
        ]
        self.assertEqual(len(next_week), 6)
        self.assertEqual(
            (next(item for item in next_week if item["sourceGenerationSlotId"] == slot_id(802))["startTime"]),
            "14:00",
        )
        self.assertTrue(any(item["sourceGenerationSlotId"] == slot_id(804) for item in next_week))
        self.assertFalse(any(item["startTime"] == "20:00" for item in next_week))
        drafts = materialize_occurrence_drafts(
            state["planItems"][0], date(2026, 9, 21), date(2026, 9, 27)
        )
        self.assertEqual(len(drafts), 6)

    def test_apply_week_stages_same_slot_date_swap_safely(self):
        created = self._post(
            activity(
                {
                    "mode": "interval_days",
                    "startDate": "2026-09-14",
                    "endDate": "2026-09-15",
                    "indefinite": False,
                    "intervalDays": 1,
                    "slots": [
                        {"id": slot_id(820), "startTime": "08:00", "endTime": "09:00"}
                    ],
                },
                "Interval swap",
            )
        ).get_json()
        first, second = created["occurrences"]
        response = self._apply_week(
            created["planItem"]["id"],
            {
                "anchorDate": "2026-09-14",
                "operations": [
                    {"type": "update", "occurrenceId": first["id"], "date": "2026-09-15", "startTime": "10:00", "endTime": "11:00"},
                    {"type": "update", "occurrenceId": second["id"], "date": "2026-09-14", "startTime": "08:00", "endTime": "09:00"},
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        by_id = {item["id"]: item for item in response.get_json()["occurrences"]}
        self.assertEqual(by_id[first["id"]]["date"], "2026-09-15")
        self.assertEqual(by_id[second["id"]]["date"], "2026-09-14")
        self.assertEqual(
            {item["sourceGenerationSlotId"] for item in by_id.values()},
            {slot_id(820)},
        )

    def test_apply_week_failure_rolls_back_updates_deletes_creates_and_exclusions(self):
        created = self._post(self._weekly_apply_payload("Rollback week")).get_json()
        plan_item_id = created["planItem"]["id"]
        current = {
            (item["sourceGenerationSlotId"], item["date"]): item
            for item in created["occurrences"]
            if item["date"] <= "2026-09-20"
        }
        with psycopg.connect(self.database_url) as connection:
            before = connection.execute(
                """
                SELECT id::text, occurrence_date::text, start_time::text,
                       end_time::text, source_generation_slot_id::text
                FROM public.occurrences
                WHERE plan_item_id = %s
                ORDER BY id
                """,
                (plan_item_id,),
            ).fetchall()
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_apply_week_create
                BEFORE INSERT ON public.occurrences
                FOR EACH ROW EXECUTE FUNCTION public.reject_test_insert()
                """
            )
        try:
            response = self._apply_week(
                plan_item_id,
                {
                    "anchorDate": "2026-09-14",
                    "operations": [
                        {"type": "update", "occurrenceId": current[(slot_id(802), "2026-09-14")]["id"], "date": "2026-09-14", "startTime": "15:00", "endTime": "18:00"},
                        {"type": "delete", "occurrenceId": current[(slot_id(804), "2026-09-15")]["id"]},
                        {"type": "create", "date": "2026-09-16", "startTime": "20:00", "endTime": "21:00"},
                    ],
                },
            )
            self.assertEqual(response.status_code, 503)
        finally:
            with psycopg.connect(self.database_url, autocommit=True) as connection:
                connection.execute(
                    "DROP TRIGGER IF EXISTS reject_apply_week_create ON public.occurrences"
                )
        with psycopg.connect(self.database_url) as connection:
            after = connection.execute(
                """
                SELECT id::text, occurrence_date::text, start_time::text,
                       end_time::text, source_generation_slot_id::text
                FROM public.occurrences
                WHERE plan_item_id = %s
                ORDER BY id
                """,
                (plan_item_id,),
            ).fetchall()
            exclusion_count = connection.execute(
                "SELECT COUNT(*) FROM public.generation_slot_excluded_dates"
            ).fetchone()[0]
        self.assertEqual(after, before)
        self.assertEqual(exclusion_count, 0)

    def test_apply_week_rejects_wrong_week_wrong_plan_and_mixed_frozen_batch(self):
        first = self._post(self._weekly_apply_payload("First")).get_json()
        with psycopg.connect(self.database_url) as connection:
            second_plan_item_id = connection.execute(
                "SELECT gen_random_uuid()"
            ).fetchone()[0]
            second_occurrence_id = connection.execute(
                "SELECT gen_random_uuid()"
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO public.plan_items (id, name, kind, subtype)
                VALUES (%s, 'Second', 'activity', 'periodic')
                """,
                (second_plan_item_id,),
            )
            connection.execute(
                """
                INSERT INTO public.generation_configs (plan_item_id, mode, indefinite)
                VALUES (%s, 'manual_dates', FALSE)
                """,
                (second_plan_item_id,),
            )
            connection.execute(
                """
                INSERT INTO public.generation_slots (id, plan_item_id, start_time, end_time)
                VALUES (%s, %s, '20:00', '21:00')
                """,
                (slot_id(830), second_plan_item_id),
            )
            connection.execute(
                """
                INSERT INTO public.generation_slot_dates (slot_id, entry_date)
                VALUES (%s, '2026-09-14')
                """,
                (slot_id(830),),
            )
            connection.execute(
                """
                INSERT INTO public.occurrences (
                    id, plan_item_id, occurrence_date, start_time, end_time,
                    status, source_generation_slot_id
                ) VALUES (%s, %s, '2026-09-14', '20:00', '21:00', 'pending', %s)
                """,
                (second_occurrence_id, second_plan_item_id, slot_id(830)),
            )
        first_current = [item for item in first["occurrences"] if item["date"] <= "2026-09-20"]
        before = self._get_state().get_json()

        wrong_plan = self._apply_week(
            first["planItem"]["id"],
            {
                "anchorDate": "2026-09-14",
                "operations": [
                    {"type": "update", "occurrenceId": first_current[0]["id"], "date": first_current[0]["date"], "startTime": "09:00", "endTime": "10:00"},
                    {"type": "delete", "occurrenceId": str(second_occurrence_id)},
                ],
            },
        )
        self.assertEqual(wrong_plan.status_code, 404)
        self.assertEqual(wrong_plan.get_json()["code"], "occurrence_not_found")
        self.assertEqual(self._get_state().get_json(), before)

        outside = self._apply_week(
            first["planItem"]["id"],
            {"anchorDate": "2026-09-14", "operations": [{"type": "create", "date": "2026-09-21", "startTime": "22:00", "endTime": "23:00"}]},
        )
        self.assertEqual(outside.status_code, 400)
        self.assertEqual(outside.get_json()["code"], "invalid_payload")

        editable = next(item for item in first_current if item["date"] == "2026-09-16")
        frozen = next(item for item in first_current if item["date"] == "2026-09-14")
        allowed = self._apply_week(
            first["planItem"]["id"],
            {"anchorDate": "2026-09-14", "operations": [{"type": "update", "occurrenceId": editable["id"], "date": editable["date"], "startTime": "09:00", "endTime": "10:00"}]},
            reference_date=date(2026, 9, 16),
        )
        self.assertEqual(allowed.status_code, 200, allowed.get_data(as_text=True))
        rejected = self._apply_week(
            first["planItem"]["id"],
            {"anchorDate": "2026-09-14", "operations": [
                {"type": "update", "occurrenceId": editable["id"], "date": editable["date"], "startTime": "10:00", "endTime": "11:00"},
                {"type": "delete", "occurrenceId": frozen["id"]},
            ]},
            reference_date=date(2026, 9, 16),
        )
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.get_json()["code"], "history_frozen")
        persisted_editable = next(
            item for item in self._get_state().get_json()["occurrences"]
            if item["id"] == editable["id"]
        )
        self.assertEqual(persisted_editable["startTime"], "09:00")

    def test_apply_future_weekly_preserves_history_overrides_exclusions_and_ad_hoc(self):
        created = self._post(
            activity(
                {
                    "mode": "weekly",
                    "startDate": "2026-09-14",
                    "endDate": "2026-10-05",
                    "indefinite": False,
                    "slots": [
                        {"id": slot_id(901), "isoWeekday": 1, "startTime": "08:00", "endTime": "11:00"},
                        {"id": slot_id(902), "isoWeekday": 2, "startTime": "14:00", "endTime": "17:00"},
                    ],
                },
                "Apply Future weekly",
            )
        ).get_json()
        plan_item_id = created["planItem"]["id"]
        by_slot_date = {
            (item["sourceGenerationSlotId"], item["date"]): item
            for item in created["occurrences"]
        }
        historical = {
            item["id"]: dict(item)
            for item in created["occurrences"]
            if item["date"] < "2026-09-21"
        }

        override = self._patch_occurrence(
            by_slot_date[(slot_id(902), "2026-09-22")]["id"],
            {"date": "2026-09-22", "startTime": "15:00", "endTime": "18:00"},
        )
        self.assertEqual(override.status_code, 200, override.get_data(as_text=True))
        excluded = self._delete_occurrence(
            by_slot_date[(slot_id(901), "2026-09-28")]["id"]
        )
        self.assertEqual(excluded.status_code, 200, excluded.get_data(as_text=True))
        ad_hoc_response = self._apply_week(
            plan_item_id,
            {
                "anchorDate": "2026-09-25",
                "operations": [
                    {"type": "create", "date": "2026-09-25", "startTime": "20:00", "endTime": "21:00"}
                ],
            },
        )
        self.assertEqual(ad_hoc_response.status_code, 200, ad_hoc_response.get_data(as_text=True))
        ad_hoc_id = next(
            item["id"]
            for item in ad_hoc_response.get_json()["occurrences"]
            if item["date"] == "2026-09-25"
        )
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "INSERT INTO public.generation_excluded_dates (plan_item_id, excluded_date) VALUES (%s, '2026-09-30')",
                (plan_item_id,),
            )
            connection.execute(
                "UPDATE public.generation_configs SET stopped_from_date = '2026-10-01' WHERE plan_item_id = %s",
                (plan_item_id,),
            )

        response = self._apply_future(
            plan_item_id,
            {
                "futureConfig": {
                    "mode": "weekly",
                    "startDate": "2026-09-21",
                    "endDate": "2026-10-05",
                    "indefinite": False,
                    "slots": [
                        {"id": slot_id(901), "isoWeekday": 1, "startTime": "09:00", "endTime": "12:00"},
                        {"id": slot_id(903), "isoWeekday": 3, "startTime": "20:00", "endTime": "22:00"},
                    ],
                }
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        result = response.get_json()
        config = result["planItem"]["generationConfig"]
        self.assertEqual(config["startDate"], "2026-09-21")
        self.assertEqual(config["stoppedFromDate"], "2026-10-01")
        self.assertEqual(config["excludedDates"], ["2026-09-30"])
        surviving = next(slot for slot in config["slots"] if slot["id"] == slot_id(901))
        self.assertEqual(surviving["excludedDates"], ["2026-09-28"])
        self.assertEqual({slot["id"] for slot in config["slots"]}, {slot_id(901), slot_id(903)})

        future = {item["id"]: item for item in result["occurrences"]}
        override_id = override.get_json()["occurrence"]["id"]
        self.assertEqual((future[override_id]["startTime"], future[override_id]["endTime"]), ("15:00", "18:00"))
        self.assertNotIn("sourceGenerationSlotId", future[override_id])
        self.assertEqual(future[ad_hoc_id]["startTime"], "20:00")
        self.assertNotIn("sourceGenerationSlotId", future[ad_hoc_id])
        self.assertTrue(any(
            item.get("sourceGenerationSlotId") == slot_id(903) and item["date"] == "2026-09-23"
            for item in future.values()
        ))
        self.assertFalse(any(
            item.get("sourceGenerationSlotId") == slot_id(901) and item["date"] == "2026-09-28"
            for item in future.values()
        ))
        self.assertFalse(any(
            item.get("sourceGenerationSlotId") == slot_id(903) and item["date"] == "2026-09-30"
            for item in future.values()
        ))

        state = self._get_state().get_json()
        persisted_by_id = {item["id"]: item for item in state["occurrences"]}
        for occurrence_id, before in historical.items():
            after = persisted_by_id[occurrence_id]
            for field in ("id", "date", "startTime", "endTime", "status"):
                self.assertEqual(after[field], before[field])
        removed_slot_history = historical[
            by_slot_date[(slot_id(902), "2026-09-15")]["id"]
        ]
        self.assertNotIn(
            "sourceGenerationSlotId", persisted_by_id[removed_slot_history["id"]]
        )

    def test_apply_future_interval_restarts_phase_and_preserves_history(self):
        created = self._post(
            activity(
                {
                    "mode": "interval_days",
                    "startDate": "2026-09-14",
                    "endDate": "2026-09-30",
                    "indefinite": False,
                    "intervalDays": 2,
                    "slots": [
                        {"id": slot_id(911), "startTime": "08:00", "endTime": "09:00"},
                        {"id": slot_id(912), "startTime": "18:00", "endTime": "19:00"},
                    ],
                },
                "Apply Future interval",
            )
        ).get_json()
        plan_item_id = created["planItem"]["id"]
        historical = [item for item in created["occurrences"] if item["date"] < "2026-09-21"]
        response = self._apply_future(
            plan_item_id,
            {
                "futureConfig": {
                    "mode": "interval_days",
                    "startDate": "2026-09-21",
                    "endDate": "2026-09-30",
                    "indefinite": False,
                    "intervalDays": 3,
                    "slots": [
                        {"id": slot_id(911), "startTime": "09:00", "endTime": "10:00"},
                        {"id": slot_id(913), "startTime": "20:00", "endTime": "21:00"},
                    ],
                }
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        future = response.get_json()["occurrences"]
        self.assertEqual(
            sorted({item["date"] for item in future}),
            ["2026-09-21", "2026-09-24", "2026-09-27", "2026-09-30"],
        )
        self.assertTrue(all(
            item["startTime"] in {"09:00", "20:00"} for item in future
        ))
        state = self._get_state().get_json()
        by_id = {item["id"]: item for item in state["occurrences"]}
        for before in historical:
            self.assertEqual(by_id[before["id"]]["date"], before["date"])
            self.assertEqual(by_id[before["id"]]["startTime"], before["startTime"])

    def test_apply_future_rejects_mode_change_manual_stopped_and_frozen(self):
        weekly = self._post(self._weekly_apply_payload("Future guards")).get_json()
        weekly_id = weekly["planItem"]["id"]
        before = self._get_state().get_json()
        mode_change = self._apply_future(
            weekly_id,
            {
                "futureConfig": {
                    "mode": "interval_days",
                    "startDate": "2026-09-21",
                    "endDate": "2026-09-27",
                    "indefinite": False,
                    "intervalDays": 2,
                    "slots": [
                        {"id": slot_id(801), "startTime": "08:00", "endTime": "11:00"}
                    ],
                }
            },
        )
        self.assertEqual(mode_change.status_code, 409)
        self.assertEqual(mode_change.get_json()["code"], "mode_change_not_supported")
        self.assertEqual(self._get_state().get_json(), before)

        frozen = self._apply_future(
            weekly_id,
            {
                "futureConfig": {
                    "mode": "weekly",
                    "startDate": "2026-09-12",
                    "endDate": "2026-09-27",
                    "indefinite": False,
                    "slots": [
                        {"id": slot_id(801), "isoWeekday": 1, "startTime": "08:00", "endTime": "11:00"}
                    ],
                }
            },
        )
        self.assertEqual(frozen.status_code, 409)
        self.assertEqual(frozen.get_json()["code"], "history_frozen")

        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "UPDATE public.generation_configs SET stopped_from_date = '2026-09-21' WHERE plan_item_id = %s",
                (weekly_id,),
            )
        stopped = self._apply_future(
            weekly_id,
            {
                "futureConfig": {
                    "mode": "weekly",
                    "startDate": "2026-09-21",
                    "endDate": "2026-09-27",
                    "indefinite": False,
                    "slots": [
                        {"id": slot_id(801), "isoWeekday": 1, "startTime": "08:00", "endTime": "11:00"}
                    ],
                }
            },
        )
        self.assertEqual(stopped.status_code, 409)
        self.assertEqual(stopped.get_json()["code"], "planning_stopped")

        manual = self._post(manual_payload(940, day="2026-10-10")).get_json()
        unsupported = self._apply_future(
            manual["planItem"]["id"],
            {
                "futureConfig": {
                    "mode": "weekly",
                    "startDate": "2026-09-21",
                    "endDate": "2026-09-27",
                    "indefinite": False,
                    "slots": [
                        {"id": slot_id(941), "isoWeekday": 1, "startTime": "08:00", "endTime": "09:00"}
                    ],
                }
            },
        )
        self.assertEqual(unsupported.status_code, 409)
        self.assertEqual(unsupported.get_json()["code"], "unsupported_mode")

    def test_schedule_mutations_reject_status_context_source_changes(self):
        source = self._post(
            activity(
                {
                    "mode": "weekly",
                    "startDate": "2026-09-14",
                    "endDate": "2026-09-28",
                    "indefinite": False,
                    "slots": [
                        {
                            "id": slot_id(950),
                            "isoWeekday": 1,
                            "startTime": "08:00",
                            "endTime": "09:00",
                        }
                    ],
                },
                "Priority source",
            )
        ).get_json()
        source_occurrence = next(
            item for item in source["occurrences"] if item["date"] == "2026-09-21"
        )
        dependent_occurrence = next(
            item for item in source["occurrences"] if item["date"] == "2026-09-14"
        )
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                UPDATE public.occurrences
                SET status = 'cancelled',
                    status_reason = 'priority_override',
                    source_occurrence_id = %s
                WHERE id = %s
                """,
                (source_occurrence["id"], dependent_occurrence["id"]),
            )

        before = self._get_state().get_json()
        patch_response = self._patch_occurrence(
            source_occurrence["id"],
            {"date": "2026-09-21", "startTime": "09:00", "endTime": "10:00"},
        )
        week_response = self._apply_week(
            source["planItem"]["id"],
            {
                "anchorDate": "2026-09-21",
                "operations": [
                    {
                        "type": "update",
                        "occurrenceId": source_occurrence["id"],
                        "date": "2026-09-21",
                        "startTime": "09:00",
                        "endTime": "10:00",
                    }
                ],
            },
        )
        response = self._apply_future(
            source["planItem"]["id"],
            {
                "futureConfig": {
                    "mode": "weekly",
                    "startDate": "2026-09-21",
                    "endDate": "2026-09-28",
                    "indefinite": False,
                    "slots": [
                        {
                            "id": slot_id(950),
                            "isoWeekday": 1,
                            "startTime": "09:00",
                            "endTime": "10:00",
                        }
                    ],
                }
            },
        )

        for rejected in (patch_response, week_response, response):
            self.assertEqual(rejected.status_code, 409)
            self.assertEqual(rejected.get_json()["code"], "status_context_locked")
        self.assertEqual(self._get_state().get_json(), before)

    def test_apply_future_late_failure_rolls_back_config_slots_and_occurrences(self):
        created = self._post(self._weekly_apply_payload("Rollback future")).get_json()
        plan_item_id = created["planItem"]["id"]
        with psycopg.connect(self.database_url) as connection:
            before = connection.execute(
                """
                SELECT config.start_date::text, config.end_date::text,
                       slot.id::text, slot.start_time::text, slot.end_time::text,
                       weekday.iso_weekday
                FROM public.generation_configs AS config
                JOIN public.generation_slots AS slot ON slot.plan_item_id = config.plan_item_id
                LEFT JOIN public.generation_slot_weekdays AS weekday ON weekday.slot_id = slot.id
                WHERE config.plan_item_id = %s
                ORDER BY slot.id
                """,
                (plan_item_id,),
            ).fetchall()
            occurrences_before = connection.execute(
                """
                SELECT id::text, occurrence_date::text, start_time::text,
                       end_time::text, source_generation_slot_id::text
                FROM public.occurrences WHERE plan_item_id = %s ORDER BY id
                """,
                (plan_item_id,),
            ).fetchall()
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_apply_future_create
                BEFORE INSERT ON public.occurrences
                FOR EACH ROW EXECUTE FUNCTION public.reject_test_insert()
                """
            )
        try:
            response = self._apply_future(
                plan_item_id,
                {
                    "futureConfig": {
                        "mode": "weekly",
                        "startDate": "2026-09-21",
                        "endDate": "2026-09-27",
                        "indefinite": False,
                        "slots": [
                            {"id": slot_id(802), "isoWeekday": 1, "startTime": "15:00", "endTime": "18:00"},
                            {"id": slot_id(920), "isoWeekday": 4, "startTime": "20:00", "endTime": "21:00"},
                        ],
                    }
                },
            )
            self.assertEqual(response.status_code, 503)
        finally:
            with psycopg.connect(self.database_url, autocommit=True) as connection:
                connection.execute(
                    "DROP TRIGGER IF EXISTS reject_apply_future_create ON public.occurrences"
                )
        with psycopg.connect(self.database_url) as connection:
            after = connection.execute(
                """
                SELECT config.start_date::text, config.end_date::text,
                       slot.id::text, slot.start_time::text, slot.end_time::text,
                       weekday.iso_weekday
                FROM public.generation_configs AS config
                JOIN public.generation_slots AS slot ON slot.plan_item_id = config.plan_item_id
                LEFT JOIN public.generation_slot_weekdays AS weekday ON weekday.slot_id = slot.id
                WHERE config.plan_item_id = %s
                ORDER BY slot.id
                """,
                (plan_item_id,),
            ).fetchall()
            occurrences_after = connection.execute(
                """
                SELECT id::text, occurrence_date::text, start_time::text,
                       end_time::text, source_generation_slot_id::text
                FROM public.occurrences WHERE plan_item_id = %s ORDER BY id
                """,
                (plan_item_id,),
            ).fetchall()
        self.assertEqual(after, before)
        self.assertEqual(occurrences_after, occurrences_before)

    def test_concurrent_apply_future_has_one_coherent_winner(self):
        created = self._post(
            activity(
                {
                    "mode": "weekly",
                    "startDate": "2026-09-14",
                    "endDate": "2026-09-28",
                    "indefinite": False,
                    "slots": [
                        {"id": slot_id(931), "isoWeekday": 1, "startTime": "08:00", "endTime": "09:00"}
                    ],
                },
                "Concurrent future",
            )
        ).get_json()
        plan_item_id = created["planItem"]["id"]
        barrier = __import__("threading").Barrier(2)
        original_lock = occurrence_repository.lock_plan_item_identity

        def synchronized_lock(connection, locked_plan_item_id):
            barrier.wait(timeout=5)
            return original_lock(connection, locked_plan_item_id)

        def attempt(start_time, new_slot_number, weekday):
            payload = {
                "futureConfig": {
                    "mode": "weekly",
                    "startDate": "2026-09-21",
                    "endDate": "2026-09-28",
                    "indefinite": False,
                    "slots": [
                        {"id": slot_id(931), "isoWeekday": 1, "startTime": start_time, "endTime": "12:00"},
                        {"id": slot_id(new_slot_number), "isoWeekday": weekday, "startTime": "20:00", "endTime": "21:00"},
                    ],
                }
            }
            try:
                return future_schedule_service.apply_future(
                    plan_item_id, payload, reference_date=REFERENCE_DATE
                )["planItem"]["generationConfig"]
            except future_schedule_service.FutureConflictError as error:
                return error.code

        with patch.object(database, "get_database_url", return_value=self.database_url), \
                patch.object(occurrence_repository, "lock_plan_item_identity", side_effect=synchronized_lock):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(attempt, "09:00", 932, 2),
                    executor.submit(attempt, "10:00", 933, 3),
                ]
                results = [future.result(timeout=10) for future in futures]

        winners = [result for result in results if isinstance(result, dict)]
        losers = [result for result in results if isinstance(result, str)]
        self.assertEqual(len(winners), 1)
        self.assertEqual(losers, ["concurrent_modification"])
        persisted = self._get_state().get_json()["planItems"][0]["generationConfig"]
        self.assertEqual(persisted, winners[0])

    def test_concurrent_apply_week_has_one_complete_winner(self):
        created = self._post(self._weekly_apply_payload("Concurrent week")).get_json()
        plan_item_id = created["planItem"]["id"]
        target = next(
            item for item in created["occurrences"]
            if item["sourceGenerationSlotId"] == slot_id(802) and item["date"] == "2026-09-14"
        )
        barrier = __import__("threading").Barrier(2)
        original_lock = occurrence_repository.lock_plan_item_identity

        def synchronized_lock(connection, locked_plan_item_id):
            barrier.wait(timeout=5)
            return original_lock(connection, locked_plan_item_id)

        def attempt(start_time, end_time):
            try:
                return week_mutation_service.apply_week(
                    plan_item_id,
                    {"anchorDate": "2026-09-14", "operations": [{"type": "update", "occurrenceId": target["id"], "date": "2026-09-14", "startTime": start_time, "endTime": end_time}]},
                    reference_date=REFERENCE_DATE,
                )["occurrences"]
            except week_mutation_service.WeekConflictError as error:
                return error.code

        with patch.object(database, "get_database_url", return_value=self.database_url), \
                patch.object(occurrence_repository, "lock_plan_item_identity", side_effect=synchronized_lock):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(attempt, "15:00", "18:00"),
                    executor.submit(attempt, "16:00", "19:00"),
                ]
                results = [future.result(timeout=10) for future in futures]

        winners = [result for result in results if isinstance(result, list)]
        losers = [result for result in results if isinstance(result, str)]
        self.assertEqual(len(winners), 1)
        self.assertEqual(losers, ["concurrent_modification"])
        persisted = next(
            item for item in self._get_state().get_json()["occurrences"]
            if item["id"] == target["id"]
        )
        winner = next(item for item in winners[0] if item["id"] == target["id"])
        self.assertEqual(
            (persisted["startTime"], persisted["endTime"]),
            (winner["startTime"], winner["endTime"]),
        )


if __name__ == "__main__":
    unittest.main()
