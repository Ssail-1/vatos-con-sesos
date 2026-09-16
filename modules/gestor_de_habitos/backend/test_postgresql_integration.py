"""Integración opt-in contra una base PostgreSQL 16 exclusivamente de pruebas."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import psycopg

from app import app
import database
import occurrence_mutation_service as mutation_service
import plan_item_creation_service as creation_service
from plan_item_materializer import materialize_occurrence_drafts


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


if __name__ == "__main__":
    unittest.main()
