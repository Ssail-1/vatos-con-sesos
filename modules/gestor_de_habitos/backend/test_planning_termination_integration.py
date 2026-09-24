"""Opt-in PostgreSQL 16 coverage of durable planning termination (schema 005)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from app import app
import database
import planning_termination_service as service
from plan_item_materializer import materialize_occurrence_drafts


MIGRATIONS = Path(__file__).resolve().parents[1] / "db" / "migrations"


class PlanningTerminationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.getenv("VCS_TEST_DATABASE_URL")
        if not cls.url:
            raise unittest.SkipTest("VCS_TEST_DATABASE_URL no está configurada.")
        with psycopg.connect(cls.url, autocommit=True) as connection:
            name = connection.execute("SELECT current_database()").fetchone()[0]
            if not name.startswith("vcs_test_"):
                raise RuntimeError("La base de integración debe empezar con vcs_test_.")
            connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
            connection.execute("CREATE SCHEMA public")
            for number, filename in enumerate((
                "001_initial_schema.sql", "002_fix_occurrence_status_context.sql",
                "003_multi_slot_scheduling.sql", "004_occurrence_segments.sql",
                "005_generation_slot_cutoff.sql",
            ), 1):
                connection.execute((MIGRATIONS / filename).read_text(encoding="utf-8"))
                if number == 4:
                    legacy_plan_id = "00000000-0000-4000-8000-000000000901"
                    legacy_slot_id = "00000000-0000-4000-8000-000000000902"
                    connection.execute(
                        """INSERT INTO public.plan_items (id, name, kind, subtype)
                           VALUES (%s, 'Pre-005', 'activity', 'periodic')""",
                        (legacy_plan_id,),
                    )
                    connection.execute(
                        """INSERT INTO public.generation_configs
                           (plan_item_id, mode, start_date, end_date, indefinite)
                           VALUES (%s, 'weekly', CURRENT_DATE, CURRENT_DATE + 14, FALSE)""",
                        (legacy_plan_id,),
                    )
                    connection.execute(
                        """INSERT INTO public.generation_slots
                           (id, plan_item_id, start_time, end_time)
                           VALUES (%s, %s, '08:00', '09:00')""",
                        (legacy_slot_id, legacy_plan_id),
                    )
                    connection.execute(
                        """INSERT INTO public.generation_slot_weekdays (slot_id, iso_weekday)
                           VALUES (%s, 1)""",
                        (legacy_slot_id,),
                    )
                if number == 5:
                    columns = connection.execute(
                        """SELECT column_name, is_nullable, column_default
                           FROM information_schema.columns
                           WHERE table_schema = 'public' AND table_name = 'generation_slots'
                             AND column_name = 'last_generation_date'"""
                    ).fetchall()
                    if columns != [("last_generation_date", "YES", None)]:
                        raise AssertionError("Migration 005 no creó el cutoff de slot.")
                    cutoff = connection.execute(
                        "SELECT last_generation_date FROM public.generation_slots WHERE id = %s",
                        (legacy_slot_id,),
                    ).fetchone()[0]
                    if cutoff is not None:
                        raise AssertionError("Migration 005 detuvo un horario preexistente.")

    def setUp(self):
        with psycopg.connect(self.url, autocommit=True) as connection:
            connection.execute("TRUNCATE public.plan_items CASCADE")
        self.client = app.test_client()
        self.today = date.today()
        self.first = self.today + timedelta(days=1)
        self.second = self.first + timedelta(days=7)
        self.third = self.second + timedelta(days=7)

    def request(self, method, path, **kwargs):
        with patch.object(database, "get_database_url", return_value=self.url):
            return getattr(self.client, method)(path, **kwargs)

    def create_weekly(self, name="Weekly", start_date=None):
        start_date = start_date or self.first
        slot_a, slot_b, slot_c = str(uuid4()), str(uuid4()), str(uuid4())
        config = {
            "mode": "weekly", "startDate": start_date.isoformat(),
            "endDate": (start_date + timedelta(days=14)).isoformat(), "indefinite": False,
            "slots": [
                {"id": slot_a, "isoWeekday": start_date.isoweekday(),
                 "startTime": "08:00", "endTime": "09:00"},
                {"id": slot_b, "isoWeekday": start_date.isoweekday(),
                 "startTime": "14:00", "endTime": "15:00"},
                {"id": slot_c, "isoWeekday": start_date.isoweekday(),
                 "startTime": "20:00", "endTime": "21:00"},
            ],
        }
        result = self.request("post", "/api/plan-items", json={
            "name": name, "kind": "activity", "activityType": "periodic",
            "generationConfig": config,
        })
        self.assertEqual(result.status_code, 201, result.get_data(as_text=True))
        return result.get_json(), slot_a, slot_b

    def create_manual(self):
        payload = {
            "name": "Manual", "kind": "activity", "activityType": "event",
            "generationConfig": {"mode": "manual_dates", "entries": [
                {"id": str(uuid4()), "date": day.isoformat(),
                 "startTime": "18:00", "endTime": "19:00"}
                for day in (self.first, self.second)
            ]},
        }
        result = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(result.status_code, 201, result.get_data(as_text=True))
        return result.get_json()

    def state(self):
        result = self.request("get", "/api/planner-state")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        return result.get_json()

    def command(self, occurrence_id, suffix):
        return self.request("post", f"/api/occurrences/{occurrence_id}/{suffix}")

    def test_slot_cutoff_follows_provenance_and_keeps_other_slots(self):
        created, slot_a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        future_b = next(row for row in created["occurrences"] if row["date"] == self.second.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        manual_id = str(uuid4())
        with psycopg.connect(self.url) as connection:
            connection.execute("UPDATE public.occurrences SET start_time = '13:00', end_time = '16:00' WHERE id = %s",
                               (future_b["id"],))
            connection.execute("UPDATE public.occurrence_segments SET start_time = '13:00', end_time = '16:00' WHERE occurrence_id = %s",
                               (future_b["id"],))
            connection.execute(
                """INSERT INTO public.occurrences
                   (id, plan_item_id, occurrence_date, start_time, end_time, status)
                   VALUES (%s, %s, %s, '22:00', '23:00', 'pending')""",
                (manual_id, created["planItem"]["id"], self.second),
            )
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '22:00', '23:00', 'pending')""",
                (str(uuid4()), manual_id),
            )
        result = self.command(selected["id"], "stop-slot-after")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertIn(future_b["id"], result.get_json()["deletedOccurrenceIds"])
        state = self.state()
        rows = state["occurrences"]
        self.assertTrue(any(row["id"] == selected["id"] for row in rows))
        self.assertFalse(any(row.get("sourceGenerationSlotId") == slot_b
                             and row["date"] > self.first.isoformat() for row in rows))
        other_slot_ids = {
            slot["id"] for slot in state["planItems"][0]["generationConfig"]["slots"]
            if slot["id"] != slot_b
        }
        self.assertEqual(len(other_slot_ids), 2)
        self.assertTrue(all(any(row.get("sourceGenerationSlotId") == slot_id
                                and row["date"] > self.first.isoformat() for row in rows)
                            for slot_id in other_slot_ids))
        self.assertTrue(any(row["id"] == manual_id for row in rows))
        slot = next(slot for slot in state["planItems"][0]["generationConfig"]["slots"] if slot["id"] == slot_b)
        self.assertEqual(slot["lastGenerationDate"], self.first.isoformat())
        drafts = materialize_occurrence_drafts(state["planItems"][0], self.first, self.third)
        self.assertFalse(any(draft["sourceGenerationSlotId"] == slot_b and draft["date"] > self.first.isoformat()
                             for draft in drafts))
        self.assertEqual(self.state(), state)  # restart/reload read is stable

    def test_recurring_stop_preserves_manual_provenance(self):
        created, _a, _b = self.create_weekly()
        plan_id = created["planItem"]["id"]
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        manual_id = str(uuid4())
        customized = next(
            row for row in created["occurrences"]
            if row["date"] == self.second.isoformat()
        )
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrences SET start_time = '12:30', end_time = '13:30' WHERE id = %s",
                (customized["id"],),
            )
            connection.execute(
                "UPDATE public.occurrence_segments SET start_time = '12:30', end_time = '13:30' WHERE occurrence_id = %s",
                (customized["id"],),
            )
            connection.execute(
                """INSERT INTO public.occurrences
                   (id, plan_item_id, occurrence_date, start_time, end_time, status)
                   VALUES (%s, %s, %s, '22:00', '23:00', 'pending')""",
                (manual_id, plan_id, self.second),
            )
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '22:00', '23:00', 'pending')""",
                (str(uuid4()), manual_id),
            )
        result = self.command(selected["id"], "stop-recurring-after")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        state = self.state()
        self.assertTrue(any(row["id"] == manual_id for row in state["occurrences"]))
        self.assertFalse(any(row["id"] == customized["id"] for row in state["occurrences"]))
        self.assertFalse(any(row.get("sourceGenerationSlotId") and row["date"] > self.first.isoformat()
                             for row in state["occurrences"]))
        self.assertEqual(state["planItems"][0]["generationConfig"]["stoppedFromDate"],
                         (self.first + timedelta(days=1)).isoformat())
        self.assertTrue(all(
            slot["lastGenerationDate"] == self.first.isoformat()
            for slot in state["planItems"][0]["generationConfig"]["slots"]
        ))
        self.assertFalse(any(draft["date"] > self.first.isoformat() for draft in
                             materialize_occurrence_drafts(state["planItems"][0], self.first, self.third)))

    def test_delete_future_includes_manual_and_stops_manual_config(self):
        created = self.create_manual()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        result = self.command(selected["id"], "delete-future-after")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        state = self.state()
        self.assertEqual([row["id"] for row in state["occurrences"]], [selected["id"]])
        self.assertEqual(state["planItems"][0]["generationConfig"]["stoppedFromDate"],
                         (self.first + timedelta(days=1)).isoformat())
        self.assertEqual(materialize_occurrence_drafts(state["planItems"][0], self.first, self.second)[0]["date"],
                         self.first.isoformat())
        self.assertEqual(len(materialize_occurrence_drafts(state["planItems"][0], self.first, self.second)), 1)

    def test_delete_future_cleans_recurring_and_manual_for_same_plan_item(self):
        created, _a, _b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        manual_id = str(uuid4())
        history_id = str(uuid4())
        customized = next(row for row in created["occurrences"] if row["date"] == self.second.isoformat())
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrences SET start_time = '12:30', end_time = '13:30' WHERE id = %s",
                (customized["id"],),
            )
            connection.execute(
                "UPDATE public.occurrence_segments SET start_time = '12:30', end_time = '13:30' WHERE occurrence_id = %s",
                (customized["id"],),
            )
            connection.execute(
                """INSERT INTO public.occurrences
                   (id, plan_item_id, occurrence_date, start_time, end_time, status)
                   VALUES (%s, %s, %s, '22:00', '23:00', 'pending')""",
                (manual_id, created["planItem"]["id"], self.second),
            )
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '22:00', '23:00', 'pending')""",
                (str(uuid4()), manual_id),
            )
            connection.execute(
                """INSERT INTO public.occurrences
                   (id, plan_item_id, occurrence_date, start_time, end_time, status)
                   VALUES (%s, %s, %s, '22:00', '23:00', 'pending')""",
                (history_id, created["planItem"]["id"], self.today),
            )
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '22:00', '23:00', 'pending')""",
                (str(uuid4()), history_id),
            )
        result = self.command(selected["id"], "delete-future-after")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertIn(manual_id, result.get_json()["deletedOccurrenceIds"])
        self.assertIn(customized["id"], result.get_json()["deletedOccurrenceIds"])
        state = self.state()
        self.assertFalse(any(row["date"] > self.first.isoformat() for row in state["occurrences"]))
        self.assertTrue(any(row["id"] == history_id for row in state["occurrences"]))
        self.assertTrue(any(row["id"] == selected["id"] for row in state["occurrences"]))
        self.assertTrue(any(item["id"] == created["planItem"]["id"] for item in state["planItems"]))
        plan_item = next(item for item in state["planItems"] if item["id"] == created["planItem"]["id"])
        self.assertFalse(any(draft["date"] > self.first.isoformat() for draft in
                             materialize_occurrence_drafts(plan_item, self.today, self.third)))

    def test_apply_future_rejects_stopped_slot_without_reopening_it(self):
        created, slot_a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        self.assertEqual(self.command(selected["id"], "stop-slot-after").status_code, 200)
        result = self.request("post", f"/api/plan-items/{created['planItem']['id']}/apply-future", json={
            "futureConfig": {
                "mode": "weekly", "startDate": self.first.isoformat(),
                "endDate": self.third.isoformat(), "indefinite": False,
                "slots": [
                    {"id": slot_a, "isoWeekday": self.first.isoweekday(),
                     "startTime": "08:00", "endTime": "09:00"},
                    {"id": slot_b, "isoWeekday": self.first.isoweekday(),
                     "startTime": "14:00", "endTime": "15:00"},
                ],
            },
        })
        self.assertEqual(result.status_code, 409, result.get_data(as_text=True))
        self.assertEqual(result.get_json()["code"], "planning_stopped")
        slot = next(slot for slot in self.state()["planItems"][0]["generationConfig"]["slots"] if slot["id"] == slot_b)
        self.assertEqual(slot["lastGenerationDate"], self.first.isoformat())

    def test_apply_week_cannot_move_stopped_slot_beyond_cutoff(self):
        created, _a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        self.assertEqual(self.command(selected["id"], "stop-slot-after").status_code, 200)
        target_date = self.first + timedelta(days=1)
        if target_date.isoweekday() == 1:
            self.skipTest("La fecha siguiente no está en la misma semana de Apply Week.")
        result = self.request("post", f"/api/plan-items/{created['planItem']['id']}/apply-week", json={
            "anchorDate": self.first.isoformat(),
            "operations": [{"type": "update", "occurrenceId": selected["id"],
                            "date": target_date.isoformat(), "startTime": "14:00", "endTime": "15:00"}],
        })
        self.assertEqual(result.status_code, 409, result.get_data(as_text=True))
        self.assertEqual(result.get_json()["code"], "planning_stopped")
        self.assertTrue(any(row["id"] == selected["id"] and row["date"] == self.first.isoformat()
                            for row in self.state()["occurrences"]))

    def test_individual_delete_remains_distinct(self):
        created, _a, slot_b = self.create_weekly()
        future = next(row for row in created["occurrences"] if row["date"] == self.second.isoformat()
                      and row["sourceGenerationSlotId"] == slot_b)
        result = self.request("delete", f"/api/occurrences/{future['id']}")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        state = self.state()
        self.assertFalse(any(row["id"] == future["id"] for row in state["occurrences"]))
        self.assertTrue(any(row["sourceGenerationSlotId"] == slot_b and row["date"] == self.third.isoformat()
                            for row in state["occurrences"]))
        slot = next(slot for slot in state["planItems"][0]["generationConfig"]["slots"] if slot["id"] == slot_b)
        self.assertNotIn("lastGenerationDate", slot)

    def test_failed_delete_rolls_back_slot_cutoff(self):
        created, _a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                """CREATE FUNCTION public.reject_termination_delete() RETURNS trigger
                   LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test failure'; END $$"""
            )
            connection.execute(
                """CREATE TRIGGER reject_termination_delete BEFORE DELETE ON public.occurrences
                   FOR EACH ROW EXECUTE FUNCTION public.reject_termination_delete()"""
            )
        try:
            result = self.command(selected["id"], "stop-slot-after")
            self.assertEqual(result.status_code, 503, result.get_data(as_text=True))
            state = self.state()
            slot = next(slot for slot in state["planItems"][0]["generationConfig"]["slots"] if slot["id"] == slot_b)
            self.assertNotIn("lastGenerationDate", slot)
            self.assertTrue(any(row["sourceGenerationSlotId"] == slot_b and row["date"] > self.first.isoformat()
                                for row in state["occurrences"]))
        finally:
            with psycopg.connect(self.url) as connection:
                connection.execute("DROP TRIGGER reject_termination_delete ON public.occurrences")
                connection.execute("DROP FUNCTION public.reject_termination_delete()")

    def test_manual_slot_scope_rejected_and_past_cutoff_rejected(self):
        created = self.create_manual()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        self.assertEqual(self.command(selected["id"], "stop-slot-after").status_code, 409)
        with self.assertRaises(service.PlanningTerminationConflictError) as caught:
            with patch.object(database, "get_database_url", return_value=self.url):
                service.terminate_after_occurrence(selected["id"], "future", reference_date=self.second)
        self.assertEqual(caught.exception.code, "history_frozen")

    def test_today_cutoff_is_allowed_and_today_is_preserved(self):
        created, _a, slot_b = self.create_weekly(start_date=self.today)
        selected = next(
            row for row in created["occurrences"]
            if row["date"] == self.today.isoformat()
            and row["sourceGenerationSlotId"] == slot_b
        )
        result = self.command(selected["id"], "stop-slot-after")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        state = self.state()
        self.assertTrue(any(row["id"] == selected["id"] for row in state["occurrences"]))
        self.assertFalse(any(row.get("sourceGenerationSlotId") == slot_b
                             and row["date"] > self.today.isoformat()
                             for row in state["occurrences"]))

    def test_manual_selected_occurrence_can_stop_its_recurring_plan_item(self):
        created, _a, _b = self.create_weekly()
        manual_id = str(uuid4())
        with psycopg.connect(self.url) as connection:
            connection.execute(
                """INSERT INTO public.occurrences
                   (id, plan_item_id, occurrence_date, start_time, end_time, status)
                   VALUES (%s, %s, %s, '22:00', '23:00', 'pending')""",
                (manual_id, created["planItem"]["id"], self.first),
            )
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '22:00', '23:00', 'pending')""",
                (str(uuid4()), manual_id),
            )
        result = self.command(manual_id, "stop-recurring-after")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        state = self.state()
        self.assertTrue(any(row["id"] == manual_id for row in state["occurrences"]))
        self.assertFalse(any(row.get("sourceGenerationSlotId") is not None
                             and row["date"] > self.first.isoformat()
                             for row in state["occurrences"]))

    def test_external_source_reference_blocks_atomically(self):
        created, _a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        target = next(row for row in created["occurrences"] if row["date"] == self.second.isoformat()
                      and row["sourceGenerationSlotId"] == slot_b)
        other = self.create_manual()
        external = other["occurrences"][0]
        with psycopg.connect(self.url) as connection:
            connection.execute(
                """UPDATE public.occurrences SET conflict_reason = 'priority_override',
                   source_occurrence_id = %s WHERE id = %s""",
                (target["id"], external["id"]),
            )
        result = self.command(selected["id"], "stop-slot-after")
        self.assertEqual(result.status_code, 409, result.get_data(as_text=True))
        self.assertEqual(result.get_json()["code"], "source_provenance_locked")
        state = self.state()
        self.assertTrue(any(row["id"] == target["id"] for row in state["occurrences"]))
        plan_item = next(item for item in state["planItems"] if item["id"] == created["planItem"]["id"])
        slot = next(slot for slot in plan_item["generationConfig"]["slots"] if slot["id"] == slot_b)
        self.assertNotIn("lastGenerationDate", slot)

    def test_same_set_source_reference_deletes_in_one_statement(self):
        created, _a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        later = sorted((row for row in created["occurrences"] if row["sourceGenerationSlotId"] == slot_b
                        and row["date"] > self.first.isoformat()), key=lambda row: row["date"])
        with psycopg.connect(self.url) as connection:
            connection.execute(
                """UPDATE public.occurrences SET conflict_reason = 'priority_override',
                   source_occurrence_id = %s WHERE id = %s""",
                (later[0]["id"], later[1]["id"]),
            )
        result = self.command(selected["id"], "stop-slot-after")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertEqual(set(result.get_json()["deletedOccurrenceIds"]), {row["id"] for row in later})

    def test_cutoff_write_failure_leaves_future_occurrences_untouched(self):
        created, _a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                """CREATE FUNCTION public.reject_cutoff_write() RETURNS trigger
                   LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'cutoff failure'; END $$"""
            )
            connection.execute(
                """CREATE TRIGGER reject_cutoff_write BEFORE UPDATE OF last_generation_date
                   ON public.generation_slots FOR EACH ROW
                   EXECUTE FUNCTION public.reject_cutoff_write()"""
            )
        try:
            result = self.command(selected["id"], "stop-slot-after")
            self.assertEqual(result.status_code, 503, result.get_data(as_text=True))
            state = self.state()
            slot = next(slot for slot in state["planItems"][0]["generationConfig"]["slots"]
                        if slot["id"] == slot_b)
            self.assertNotIn("lastGenerationDate", slot)
            self.assertTrue(any(row.get("sourceGenerationSlotId") == slot_b
                                and row["date"] > self.first.isoformat()
                                for row in state["occurrences"]))
        finally:
            with psycopg.connect(self.url) as connection:
                connection.execute("DROP TRIGGER reject_cutoff_write ON public.generation_slots")
                connection.execute("DROP FUNCTION public.reject_cutoff_write()")

    def test_deferred_commit_failure_rolls_back_cutoff_and_cleanup(self):
        created, _a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                """CREATE FUNCTION public.reject_termination_commit() RETURNS trigger
                   LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'commit failure'; END $$"""
            )
            connection.execute(
                """CREATE CONSTRAINT TRIGGER reject_termination_commit
                   AFTER UPDATE OF last_generation_date ON public.generation_slots
                   DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
                   EXECUTE FUNCTION public.reject_termination_commit()"""
            )
        try:
            result = self.command(selected["id"], "stop-slot-after")
            self.assertEqual(result.status_code, 503, result.get_data(as_text=True))
            state = self.state()
            slot = next(slot for slot in state["planItems"][0]["generationConfig"]["slots"]
                        if slot["id"] == slot_b)
            self.assertNotIn("lastGenerationDate", slot)
            self.assertTrue(any(row.get("sourceGenerationSlotId") == slot_b
                                and row["date"] > self.first.isoformat()
                                for row in state["occurrences"]))
        finally:
            with psycopg.connect(self.url) as connection:
                connection.execute("DROP TRIGGER reject_termination_commit ON public.generation_slots")
                connection.execute("DROP FUNCTION public.reject_termination_commit()")

    def test_concurrent_termination_remains_consistent(self):
        created, _a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        with patch.object(database, "get_database_url", return_value=self.url):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(service.terminate_after_occurrence,
                                       selected["id"], "slot", self.today) for _ in range(2)]
                outcomes = []
                for future in futures:
                    try:
                        outcomes.append(future.result())
                    except service.PlanningTerminationConflictError as error:
                        self.assertEqual(error.code, "concurrent_conflict")
        self.assertGreaterEqual(len(outcomes), 1)
        state = self.state()
        self.assertFalse(any(row.get("sourceGenerationSlotId") == slot_b
                             and row["date"] > self.first.isoformat() for row in state["occurrences"]))
        slot = next(slot for slot in state["planItems"][0]["generationConfig"]["slots"] if slot["id"] == slot_b)
        self.assertEqual(slot["lastGenerationDate"], self.first.isoformat())

    def test_cors_only_authorized_origin_and_exact_command_paths(self):
        created, _a, slot_b = self.create_weekly()
        selected = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat()
                        and row["sourceGenerationSlotId"] == slot_b)
        path = f"/api/occurrences/{selected['id']}/stop-slot-after"
        with patch.dict(os.environ, {"VCS_ALLOWED_ORIGINS": "http://127.0.0.1:8017"}):
            approved = self.request("options", path, headers={
                "Origin": "http://127.0.0.1:8017",
                "Access-Control-Request-Method": "POST",
            })
            denied = self.request("options", path, headers={
                "Origin": "http://example.invalid",
                "Access-Control-Request-Method": "POST",
            })
        self.assertEqual(approved.headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:8017")
        self.assertEqual(approved.headers.get("Access-Control-Allow-Methods"), "POST, OPTIONS")
        self.assertIsNone(denied.headers.get("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
