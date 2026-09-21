"""Opt-in: Apply Week/Future contra PostgreSQL 16 aislado con schema 004."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg

from app import app
import database
import plan_item_creation_service
import week_mutation_service


MIGRATIONS = Path(__file__).resolve().parents[1] / "db" / "migrations"
TEST_URL = "VCS_TEST_DATABASE_URL"


class RecurringSchema004IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.getenv(TEST_URL)
        if not cls.url:
            raise unittest.SkipTest(f"{TEST_URL} no está configurada.")
        with psycopg.connect(cls.url, autocommit=True) as connection:
            name = connection.execute("SELECT current_database()").fetchone()[0]
            if not name.startswith("vcs_test_"):
                raise RuntimeError("La base de integración debe empezar con vcs_test_.")
            connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
            connection.execute("CREATE SCHEMA public")
            for filename in (
                "001_initial_schema.sql",
                "002_fix_occurrence_status_context.sql",
                "003_multi_slot_scheduling.sql",
                "004_occurrence_segments.sql",
            ):
                connection.execute((MIGRATIONS / filename).read_text(encoding="utf-8"))

    def setUp(self):
        with psycopg.connect(self.url, autocommit=True) as connection:
            connection.execute("TRUNCATE public.plan_items CASCADE")
        self.today = date.today()
        self.first = self.today + timedelta(days=1)
        self.second = self.first + timedelta(days=7)
        self.third = self.second + timedelta(days=7)
        self.client = app.test_client()

    def _request(self, method, path, **kwargs):
        with patch.object(database, "get_database_url", return_value=self.url):
            return getattr(self.client, method)(path, **kwargs)

    def _create(self, *, start="08:00", end="10:00", name="Recurring"):
        slot_id = str(uuid4())
        payload = {
            "name": name, "kind": "activity", "activityType": "periodic",
            "generationConfig": {
                "mode": "weekly", "startDate": self.first.isoformat(),
                "endDate": self.third.isoformat(), "indefinite": False,
                "slots": [{"id": slot_id, "isoWeekday": self.first.isoweekday(),
                           "startTime": start, "endTime": end}],
            },
        }
        with patch.object(database, "get_database_url", return_value=self.url), \
                patch.object(plan_item_creation_service, "_today", return_value=self.today):
            response = self.client.post("/api/plan-items", json=payload)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json(), slot_id

    def _week(self, plan_id, operations):
        return self._request("post", f"/api/plan-items/{plan_id}/apply-week", json={
            "anchorDate": self.first.isoformat(), "operations": operations,
        })

    def _future(self, plan_id, slot_id, start, end, extra_slots=()):
        return self._request("post", f"/api/plan-items/{plan_id}/apply-future", json={
            "futureConfig": {
                "mode": "weekly", "startDate": self.first.isoformat(),
                "endDate": self.third.isoformat(), "indefinite": False,
                "slots": [{"id": slot_id, "isoWeekday": self.first.isoweekday(),
                           "startTime": start, "endTime": end}, *extra_slots],
            },
        })

    def _state(self):
        response = self._request("get", "/api/planner-state")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def _customize(self, occurrence):
        """Persist two pending children with a gap, keeping the parent envelope."""
        first = occurrence["segments"][0]["id"]
        second = str(uuid4())
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET end_time = '08:30' WHERE id = %s",
                (first,),
            )
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '09:00', '10:00', 'pending')""",
                (second, occurrence["id"]),
            )
        return first, second

    def test_week_simple_move_and_new_ad_hoc_segment_round_trip(self):
        created, slot_id = self._create()
        plan_id = created["planItem"]["id"]
        old = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        old_segment_id = old["segments"][0]["id"]
        result = self._week(plan_id, [
            {"type": "update", "occurrenceId": old["id"], "date": self.first.isoformat(),
             "startTime": "09:00", "endTime": "11:30"},
            {"type": "create", "date": self.first.isoformat(),
             "startTime": "13:00", "endTime": "14:00"},
        ])
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        rows = self._state()["occurrences"]
        moved = next(row for row in rows if row["id"] == old["id"])
        self.assertEqual((moved["startTime"], moved["endTime"]), ("09:00", "11:30"))
        self.assertEqual(moved["segments"], [{"id": old_segment_id, "startTime": "09:00",
                                              "endTime": "11:30", "status": "pending"}])
        self.assertEqual(moved["sourceGenerationSlotId"], slot_id)
        adhoc = next(row for row in rows if row["date"] == self.first.isoformat()
                     and row["startTime"] == "13:00")
        self.assertEqual(len(adhoc["segments"]), 1)
        self.assertEqual(adhoc["segments"][0]["startTime"], "13:00")
        self.assertNotIn("sourceGenerationSlotId", adhoc)

    def test_future_simple_resize_and_new_default_segment(self):
        created, slot_id = self._create()
        plan_id = created["planItem"]["id"]
        old = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        old_child = old["segments"][0]["id"]
        new_slot = str(uuid4())
        result = self._future(plan_id, slot_id, "09:00", "11:00", [{
            "id": new_slot, "isoWeekday": (self.first + timedelta(days=1)).isoweekday(),
            "startTime": "13:00", "endTime": "14:00",
        }])
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        state = self._state()
        moved = next(row for row in state["occurrences"] if row["id"] == old["id"])
        self.assertEqual(moved["segments"][0]["id"], old_child)
        self.assertEqual(moved["segments"][0]["startTime"], "09:00")
        self.assertEqual(moved["sourceGenerationSlotId"], slot_id)
        self.assertTrue(all(len(row["segments"]) == 1 for row in state["occurrences"]))
        generated = [row for row in state["occurrences"] if row.get("sourceGenerationSlotId") == new_slot]
        self.assertTrue(generated)
        self.assertTrue(all(row["segments"][0]["startTime"] == "13:00"
                            and row["segments"][0]["endTime"] == "14:00"
                            and row["segments"][0]["status"] == row["status"] == "pending"
                            and UUID(row["segments"][0]["id"]).version == 4
                            and row["segments"][0]["id"] != row["id"]
                            for row in generated))
        self.assertEqual(len({row["segments"][0]["id"] for row in generated}), len(generated))

    def test_week_custom_translation_preserves_graph_and_gap(self):
        created, _slot_id = self._create()
        plan_id = created["planItem"]["id"]
        old = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        first, second = self._customize(old)
        result = self._week(plan_id, [{
            "type": "update", "occurrenceId": old["id"], "date": self.first.isoformat(),
            "startTime": "11:00", "endTime": "13:00",
        }])
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        moved = next(row for row in self._state()["occurrences"] if row["id"] == old["id"])
        self.assertEqual([(segment["id"], segment["startTime"], segment["endTime"])
                          for segment in moved["segments"]], [
            (first, "11:00", "11:30"), (second, "12:00", "13:00"),
        ])
        self.assertEqual(moved["status"], "pending")

    def test_future_custom_translation_and_resize_rollback(self):
        created, slot_id = self._create()
        plan_id = created["planItem"]["id"]
        old = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        first, second = self._customize(old)
        rejected = self._future(plan_id, slot_id, "11:00", "14:00")
        self.assertEqual(rejected.status_code, 409, rejected.get_data(as_text=True))
        body = rejected.get_json()
        self.assertEqual(body["code"], "segmented_recurring_resize_requires_resolution")
        self.assertEqual(body["occurrences"][0]["occurrenceId"], old["id"])
        after_rejection = self._state()
        self.assertEqual(after_rejection["planItems"][0]["generationConfig"]["slots"][0]["startTime"], "08:00")
        self.assertEqual(next(row for row in after_rejection["occurrences"] if row["id"] == old["id"])["segments"][0]["startTime"], "08:00")

        new_slot = str(uuid4())
        accepted = self._future(plan_id, slot_id, "11:00", "13:00", [{
            "id": new_slot, "isoWeekday": (self.first + timedelta(days=1)).isoweekday(),
            "startTime": "15:00", "endTime": "16:00",
        }])
        self.assertEqual(accepted.status_code, 200, accepted.get_data(as_text=True))
        state = self._state()
        moved = next(row for row in state["occurrences"] if row["id"] == old["id"])
        self.assertEqual([(segment["id"], segment["startTime"], segment["endTime"])
                          for segment in moved["segments"]], [
            (first, "11:00", "11:30"), (second, "12:00", "13:00"),
        ])
        generated = [row for row in state["occurrences"] if row.get("sourceGenerationSlotId") == new_slot]
        self.assertTrue(generated)
        self.assertTrue(all(len(row["segments"]) == 1 for row in generated),
                        "La segmentación custom runtime no se hereda al slot nuevo.")

    def test_week_conflict_uses_real_children_and_rolls_back(self):
        target, _ = self._create(start="06:00", end="07:00", name="Target")
        blocker, _ = self._create(start="09:00", end="11:00", name="Blocker")
        target_id = target["planItem"]["id"]
        target_old = next(row for row in target["occurrences"] if row["date"] == self.first.isoformat())
        blocker_old = next(row for row in blocker["occurrences"] if row["date"] == self.first.isoformat())
        blocker_segment = blocker_old["segments"][0]["id"]
        with psycopg.connect(self.url) as connection:
            connection.execute("UPDATE public.occurrence_segments SET end_time='09:30' WHERE id=%s", (blocker_segment,))
            connection.execute("""INSERT INTO public.occurrence_segments
                (id, occurrence_id, start_time, end_time, status)
                VALUES (%s, %s, '10:30', '11:00', 'pending')""",
                (str(uuid4()), blocker_old["id"]),
            )
        free_gap = self._week(target_id, [{
            "type": "update", "occurrenceId": target_old["id"], "date": self.first.isoformat(),
            "startTime": "09:30", "endTime": "10:30",
        }])
        self.assertEqual(free_gap.status_code, 200, free_gap.get_data(as_text=True))
        blocked = self._week(target_id, [{
            "type": "update", "occurrenceId": target_old["id"], "date": self.first.isoformat(),
            "startTime": "09:00", "endTime": "10:00",
        }])
        self.assertEqual(blocked.status_code, 409, blocked.get_data(as_text=True))
        self.assertEqual(blocked.get_json()["code"], "recurring_schedule_conflict")
        self.assertEqual(blocked.get_json()["blockers"][0]["segmentId"], blocker_segment)
        current = next(row for row in self._state()["occurrences"] if row["id"] == target_old["id"])
        self.assertEqual(current["segments"][0]["startTime"], "09:30")

    def test_week_late_segment_insert_failure_rolls_back_parent_and_update(self):
        created, _ = self._create()
        plan_id = created["planItem"]["id"]
        old = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        before = self._state()
        with psycopg.connect(self.url) as connection:
            connection.execute("""CREATE FUNCTION public.reject_recurring_child() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test failure'; END $$""")
            connection.execute("""CREATE TRIGGER reject_recurring_child_insert
                BEFORE INSERT ON public.occurrence_segments FOR EACH ROW
                EXECUTE FUNCTION public.reject_recurring_child()""")
        try:
            result = self._week(plan_id, [
                {"type": "update", "occurrenceId": old["id"], "date": self.first.isoformat(),
                 "startTime": "11:00", "endTime": "13:00"},
                {"type": "create", "date": self.first.isoformat(),
                 "startTime": "15:00", "endTime": "16:00"},
            ])
            self.assertEqual(result.status_code, 503, result.get_data(as_text=True))
            self.assertEqual(self._state(), before)
        finally:
            with psycopg.connect(self.url) as connection:
                connection.execute("DROP TRIGGER reject_recurring_child_insert ON public.occurrence_segments")
                connection.execute("DROP FUNCTION public.reject_recurring_child()")

    def test_future_late_segment_insert_failure_rolls_back_generation_slots(self):
        created, slot_id = self._create()
        plan_id = created["planItem"]["id"]
        before = self._state()
        new_slot = str(uuid4())
        with psycopg.connect(self.url) as connection:
            connection.execute("""CREATE FUNCTION public.reject_recurring_child() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test failure'; END $$""")
            connection.execute("""CREATE TRIGGER reject_recurring_child_insert
                BEFORE INSERT ON public.occurrence_segments FOR EACH ROW
                EXECUTE FUNCTION public.reject_recurring_child()""")
        try:
            result = self._future(plan_id, slot_id, "09:00", "11:00", [{
                "id": new_slot, "isoWeekday": (self.first + timedelta(days=1)).isoweekday(),
                "startTime": "13:00", "endTime": "14:00",
            }])
            self.assertEqual(result.status_code, 503, result.get_data(as_text=True))
            self.assertEqual(self._state(), before)
            with psycopg.connect(self.url) as connection:
                self.assertEqual(connection.execute(
                    "SELECT COUNT(*) FROM public.generation_slots WHERE id=%s", (new_slot,)
                ).fetchone()[0], 0)
        finally:
            with psycopg.connect(self.url) as connection:
                connection.execute("DROP TRIGGER reject_recurring_child_insert ON public.occurrence_segments")
                connection.execute("DROP FUNCTION public.reject_recurring_child()")

    def test_referenced_source_can_move_without_rewriting_conflict_metadata(self):
        created, _ = self._create()
        plan_id = created["planItem"]["id"]
        source = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        dependent = next(row for row in created["occurrences"] if row["date"] == self.second.isoformat())
        with psycopg.connect(self.url) as connection:
            connection.execute("""UPDATE public.occurrences
                SET conflict_reason='priority_override', source_occurrence_id=%s
                WHERE id=%s""", (source["id"], dependent["id"]))
        result = self._week(plan_id, [{
            "type": "update", "occurrenceId": source["id"], "date": self.first.isoformat(),
            "startTime": "11:00", "endTime": "13:00",
        }])
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        state = self._state()
        moved = next(row for row in state["occurrences"] if row["id"] == source["id"])
        linked = next(row for row in state["occurrences"] if row["id"] == dependent["id"])
        self.assertEqual(moved["segments"][0]["startTime"], "11:00")
        self.assertEqual(linked["conflictContext"], {
            "reason": "priority_override", "sourceOccurrenceId": source["id"],
        })

    def test_custom_date_move_is_controlled_rejection_without_changes(self):
        created, _ = self._create()
        plan_id = created["planItem"]["id"]
        old = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        self._customize(old)
        before = self._state()
        next_day = self.first + timedelta(days=1)
        if next_day.isocalendar().week != self.first.isocalendar().week:
            self.skipTest("La fecha del fixture cae al final de la semana.")
        response = self._week(plan_id, [{
            "type": "update", "occurrenceId": old["id"], "date": next_day.isoformat(),
            "startTime": "08:00", "endTime": "10:00",
        }])
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["code"], "segmented_recurring_date_move_requires_resolution")
        self.assertEqual(self._state(), before)

    def test_concurrent_week_updates_keep_one_coherent_parent_child_graph(self):
        created, _ = self._create()
        plan_id = created["planItem"]["id"]
        old = next(row for row in created["occurrences"] if row["date"] == self.first.isoformat())
        child_id = old["segments"][0]["id"]

        def attempt(start, end):
            payload = {"anchorDate": self.first.isoformat(), "operations": [{
                "type": "update", "occurrenceId": old["id"], "date": self.first.isoformat(),
                "startTime": start, "endTime": end,
            }]}
            try:
                return week_mutation_service.apply_week(
                    plan_id, payload, reference_date=self.today
                )
            except week_mutation_service.WeekConflictError as error:
                if error.code != "concurrent_conflict":
                    raise
                return error.code

        with patch.object(database, "get_database_url", return_value=self.url), \
                ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda schedule: attempt(*schedule),
                [("11:00", "13:00"), ("14:00", "16:00")],
            ))
        self.assertTrue(any(isinstance(result, dict) for result in results))
        current = next(row for row in self._state()["occurrences"] if row["id"] == old["id"])
        self.assertIn((current["startTime"], current["endTime"]),
                      {("11:00", "13:00"), ("14:00", "16:00")})
        self.assertEqual(current["segments"], [{
            "id": child_id, "startTime": current["startTime"],
            "endTime": current["endTime"], "status": "pending",
        }])


if __name__ == "__main__":
    unittest.main()
