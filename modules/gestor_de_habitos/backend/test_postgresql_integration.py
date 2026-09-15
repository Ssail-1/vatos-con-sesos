"""Integración opt-in contra una base PostgreSQL 16 exclusivamente de pruebas."""

from datetime import date
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import psycopg

from app import app
import database
import plan_item_creation_service as creation_service


TEST_DATABASE_ENV = "VCS_TEST_DATABASE_URL"
REFERENCE_DATE = date(2026, 9, 14)


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
            connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
            connection.execute("CREATE SCHEMA public")

        migration_directory = Path(__file__).resolve().parents[1] / "db" / "migrations"
        with psycopg.connect(cls.database_url, autocommit=True) as connection:
            for migration_name in (
                "001_initial_schema.sql",
                "002_fix_occurrence_status_context.sql",
                "003_multi_slot_scheduling.sql",
            ):
                connection.execute(
                    (migration_directory / migration_name).read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
