"""Opt-in: handshake segmentario real sobre PostgreSQL 16 aislado."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from app import app
import database
import plan_item_creation_service
from segment_conflict_service import (
    SegmentConflictError,
    resolve_source_conflicts,
    validate_confirmations,
)


MIGRATIONS = Path(__file__).resolve().parents[1] / "db" / "migrations"
TEST_URL = "VCS_TEST_DATABASE_URL"


class SegmentConflictSchema004IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.getenv(TEST_URL)
        if not cls.url:
            raise unittest.SkipTest(f"{TEST_URL} no está configurada.")
        with psycopg.connect(cls.url, autocommit=True) as connection:
            database_name = connection.execute("SELECT current_database()").fetchone()[0]
            if not database_name.startswith("vcs_test_"):
                raise RuntimeError("La base de integración debe empezar con vcs_test_.")
            connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
            connection.execute("CREATE SCHEMA public")
            for filename in (
                "001_initial_schema.sql", "002_fix_occurrence_status_context.sql",
                "003_multi_slot_scheduling.sql", "004_occurrence_segments.sql",
            ):
                connection.execute((MIGRATIONS / filename).read_text(encoding="utf-8"))

    def setUp(self):
        with psycopg.connect(self.url, autocommit=True) as connection:
            connection.execute("TRUNCATE public.plan_items CASCADE")
        self.client = app.test_client()
        self.today = date.today()
        self.day = self.today + timedelta(days=1)

    def request(self, method, path, **kwargs):
        with patch.object(database, "get_database_url", return_value=self.url), \
                patch.object(plan_item_creation_service, "_today", return_value=self.today):
            return getattr(self.client, method)(path, **kwargs)

    def payload(self, name, start, end, *, subtype="periodic", day=None):
        return {
            "name": name, "kind": "activity", "activityType": subtype,
            "generationConfig": {
                "mode": "manual_dates",
                "entries": [{"id": str(uuid4()), "date": (day or self.day).isoformat(),
                             "startTime": start, "endTime": end}],
            },
        }

    def create(self, name, start, end, **kwargs):
        response = self.request("post", "/api/plan-items", json=self.payload(
            name, start, end, **kwargs
        ))
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["occurrences"][0]

    def create_deletable(self, name="Deletable", start="08:00", end="09:00", **kwargs):
        payload = self.payload(name, start, end, **kwargs)
        payload["generationConfig"]["entries"].append({
            "id": str(uuid4()), "date": (self.day + timedelta(days=1)).isoformat(),
            "startTime": start, "endTime": end,
        })
        response = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["occurrences"][0]

    def state(self):
        response = self.request("get", "/api/planner-state")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    @staticmethod
    def confirmation(conflict, *, realized=False):
        blocker = conflict["blocker"]
        entry = {
            "blocker": {key: blocker[key] for key in (
                "occurrenceId", "segmentId", "startTime", "endTime", "status"
            )},
            "confirmed": True,
        }
        if realized:
            entry["confirmRealizedTimeCorrection"] = True
        return entry

    def test_first_409_has_segment_snapshot_and_zero_writes_then_split(self):
        target = self.create("Target", "08:00", "12:00")
        payload = self.payload("Source", "09:00", "10:00", subtype="unexpected")
        before = self.state()
        first = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        body = first.get_json()
        self.assertEqual(body["code"], "segment_conflict_resolution_required")
        conflict = body["conflicts"][0]
        self.assertEqual(conflict["blocker"]["occurrenceId"], target["id"])
        self.assertEqual(conflict["blocker"]["segmentId"], target["segments"][0]["id"])
        self.assertEqual(conflict["requiredAuthorization"], "priority_override")
        self.assertEqual(conflict["resolutionKind"], "split_segment")
        self.assertEqual(self.state(), before)
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        second = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(second.status_code, 201, second.get_data(as_text=True))
        self.assertEqual(second.get_json()["occurrences"][0]["originReason"], "conflict_insertion")
        self.assertEqual(second.get_json()["occurrences"][0]["lastConflictAction"], "conflict_insertion")
        rows = self.state()["occurrences"]
        changed = next(row for row in rows if row["id"] == target["id"])
        self.assertEqual(
            [(segment["startTime"], segment["endTime"], segment["status"])
             for segment in changed["segments"]],
            [("08:00", "09:00", "pending"), ("10:00", "12:00", "pending")],
        )
        self.assertEqual(changed["segments"][0]["id"], target["segments"][0]["id"])
        self.assertEqual(changed["conflictContext"], {
            "reason": "priority_override",
            "sourceOccurrenceId": second.get_json()["occurrences"][0]["id"],
        })
        new_source = next(row for row in rows if row["id"] == second.get_json()["occurrences"][0]["id"])
        self.assertEqual(new_source["originReason"], "conflict_insertion")
        self.assertEqual(new_source["lastConflictAction"], "conflict_insertion")

    def test_delete_single_and_multi_segment_parents_cascades_children(self):
        single = self.create_deletable("Single", "08:00", "09:00")
        multi = self.create_deletable("Multi", "10:00", "12:00")
        changed = self.request("put", f"/api/occurrences/{multi['id']}/structure", json={
            "startTime": "10:00", "endTime": "12:00",
            "segments": [
                {"id": multi["segments"][0]["id"], "startTime": "10:00", "endTime": "10:30"},
                {"startTime": "11:00", "endTime": "12:00", "status": "pending"},
            ],
        })
        self.assertEqual(changed.status_code, 200, changed.get_data(as_text=True))
        for occurrence in (single, multi):
            deleted = self.request("delete", f"/api/occurrences/{occurrence['id']}")
            self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))
            self.assertEqual(deleted.get_json()["deletedOccurrenceId"], occurrence["id"])
        with psycopg.connect(self.url) as connection:
            for occurrence in (single, multi):
                self.assertEqual(connection.execute(
                    "SELECT count(*) FROM public.occurrence_segments WHERE occurrence_id = %s",
                    (occurrence["id"],),
                ).fetchone()[0], 0)

    def test_delete_referenced_source_rejected_without_clearing_provenance(self):
        target = self.create("Target", "08:00", "10:00")
        source = self.create_deletable("Source", "11:00", "12:00", subtype="unexpected")
        # The initial creation cannot overlap. Move after both graphs exist.
        path = f"/api/occurrences/{source['id']}/translate"
        first = self.request("post", path, json={"startTime": "08:30", "endTime": "09:30"})
        self.assertEqual(first.status_code, 409)
        confirmation = self.confirmation(first.get_json()["conflicts"][0])
        moved = self.request("post", path, json={
            "startTime": "08:30", "endTime": "09:30",
            "conflictResolution": {"confirmations": [confirmation]},
        })
        self.assertEqual(moved.status_code, 200, moved.get_data(as_text=True))
        before = self.state()
        rejected = self.request("delete", f"/api/occurrences/{source['id']}")
        self.assertEqual(rejected.status_code, 409, rejected.get_data(as_text=True))
        self.assertEqual(rejected.get_json()["code"], "deletion_status_locked")
        self.assertEqual(self.state(), before)
        self.assertEqual(next(row for row in before["occurrences"] if row["id"] == target["id"])[
            "conflictContext"]["sourceOccurrenceId"], source["id"])

    def test_stale_snapshot_does_not_mutate(self):
        target = self.create("Target", "08:00", "12:00")
        payload = self.payload("Source", "09:00", "10:00")
        first = self.request("post", "/api/plan-items", json=payload).get_json()
        conflict = first["conflicts"][0]
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET end_time = '11:30' WHERE id = %s",
                (target["segments"][0]["id"],),
            )
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        response = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["code"], "conflict_resolution_stale")
        self.assertEqual(len(self.state()["planItems"]), 1)

    def test_confirmed_translate_trims_target_and_records_move(self):
        target = self.create("Target", "08:00", "12:00")
        source = self.create("Source", "13:00", "14:00", subtype="unexpected")
        path = f"/api/occurrences/{source['id']}/translate"
        command = {"startTime": "11:00", "endTime": "12:00"}
        first = self.request("post", path, json=command)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        conflict = first.get_json()["conflicts"][0]
        self.assertEqual(conflict["resolutionKind"], "trim_segment")
        self.assertEqual(self.state()["occurrences"][-1]["startTime"], "13:00")
        command["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        second = self.request("post", path, json=command)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        rows = self.state()["occurrences"]
        moved = next(row for row in rows if row["id"] == source["id"])
        changed = next(row for row in rows if row["id"] == target["id"])
        self.assertEqual((moved["startTime"], moved["endTime"]), ("11:00", "12:00"))
        self.assertEqual(moved["lastConflictAction"], "conflict_move")
        self.assertEqual(changed["segments"][0]["id"], target["segments"][0]["id"])
        self.assertEqual(changed["segments"][0]["endTime"], "11:00")

    def test_full_overlap_cancels_pending_with_user_forced_reason(self):
        target = self.create("Target", "09:00", "10:00", subtype="event")
        payload = self.payload("Source", "08:00", "11:00", subtype="periodic")
        first = self.request("post", "/api/plan-items", json=payload)
        conflict = first.get_json()["conflicts"][0]
        self.assertEqual(conflict["requiredAuthorization"], "user_forced_override")
        self.assertEqual(conflict["resolutionKind"], "cancel_segment")
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        second = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(second.status_code, 201, second.get_data(as_text=True))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(changed["segments"][0]["status"], "cancelled")
        self.assertEqual(changed["status"], "cancelled")
        self.assertEqual(changed["conflictContext"]["reason"], "user_forced_override")

    def test_completed_requires_strong_snapshot_bound_acknowledgement(self):
        target = self.create("Target", "00:01", "00:03", day=self.today)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET status = 'completed' WHERE id = %s",
                (target["segments"][0]["id"],),
            )
            connection.execute(
                "UPDATE public.occurrences SET status = 'completed' WHERE id = %s",
                (target["id"],),
            )
        payload = self.payload("Source", "00:02", "00:04", subtype="unexpected", day=self.today)
        first = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        conflict = first.get_json()["conflicts"][0]
        self.assertEqual(conflict["requiredAuthorization"], "user_forced_override")
        self.assertTrue(conflict["requiresRealizedTimeConfirmation"])
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        weak = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(weak.status_code, 409, weak.get_data(as_text=True))
        self.assertEqual(len(self.state()["planItems"]), 1)
        payload["conflictResolution"] = {"confirmations": [
            self.confirmation(conflict, realized=True)
        ]}
        strong = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(strong.status_code, 201, strong.get_data(as_text=True))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(changed["segments"][0]["status"], "completed")
        self.assertEqual(changed["segments"][0]["endTime"], "00:02")
        self.assertEqual(changed["conflictContext"]["reason"], "user_forced_override")

    def test_in_progress_internal_split_is_controlled_rejection(self):
        target = self.create("Target", "08:00", "12:00", day=self.today)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET status = 'in_progress' WHERE id = %s",
                (target["segments"][0]["id"],),
            )
            connection.execute(
                "UPDATE public.occurrences SET status = 'in_progress' WHERE id = %s",
                (target["id"],),
            )
        payload = self.payload("Source", "09:00", "10:00", day=self.today)
        first = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        conflict = first.get_json()["conflicts"][0]
        self.assertEqual(conflict["resolutionKind"], "undefined_in_progress")
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        second = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(second.status_code, 409, second.get_data(as_text=True))
        self.assertEqual(second.get_json()["code"], "segment_resolution_undefined")
        self.assertEqual(len(self.state()["planItems"]), 1)

    def test_put_structure_conflict_then_confirmed_trim(self):
        target = self.create("Target", "08:00", "10:00")
        source = self.create("Source", "11:00", "13:00")
        path = f"/api/occurrences/{source['id']}/structure"
        command = {
            "startTime": "09:00", "endTime": "11:00",
            "segments": [{"id": source["segments"][0]["id"],
                          "startTime": "09:00", "endTime": "11:00"}],
        }
        first = self.request("put", path, json=command)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        command["conflictResolution"] = {"confirmations": [
            self.confirmation(first.get_json()["conflicts"][0])
        ]}
        second = self.request("put", path, json=command)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        rows = self.state()["occurrences"]
        changed = next(row for row in rows if row["id"] == target["id"])
        moved = next(row for row in rows if row["id"] == source["id"])
        self.assertEqual(changed["segments"][0]["endTime"], "09:00")
        self.assertEqual(moved["lastConflictAction"], "conflict_move")

    def test_reset_conflict_after_real_gap(self):
        source = self.create("Source", "08:00", "12:00")
        path = f"/api/occurrences/{source['id']}/structure"
        custom = self.request("put", path, json={
            "startTime": "08:00", "endTime": "12:00",
            "segments": [
                {"id": source["segments"][0]["id"],
                 "startTime": "08:00", "endTime": "09:00"},
                {"startTime": "11:00", "endTime": "12:00", "status": "pending"},
            ],
        })
        self.assertEqual(custom.status_code, 200, custom.get_data(as_text=True))
        target = self.create("Gap target", "09:00", "11:00")
        reset_path = f"/api/occurrences/{source['id']}/reset-segmentation"
        command = {"startTime": "08:00", "endTime": "12:00"}
        first = self.request("post", reset_path, json=command)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        self.assertEqual(first.get_json()["conflicts"][0]["blocker"]["occurrenceId"], target["id"])
        command["conflictResolution"] = {"confirmations": [
            self.confirmation(first.get_json()["conflicts"][0])
        ]}
        second = self.request("post", reset_path, json=command)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        rows = self.state()["occurrences"]
        changed = next(row for row in rows if row["id"] == target["id"])
        reset = next(row for row in rows if row["id"] == source["id"])
        self.assertEqual(changed["segments"][0]["status"], "cancelled")
        self.assertEqual(len(reset["segments"]), 1)
        self.assertEqual(reset["lastConflictAction"], "conflict_move")

    def test_custom_source_intervals_leave_gap_unoccupied(self):
        source = self.create("Source", "13:00", "17:00")
        custom = self.request("put", f"/api/occurrences/{source['id']}/structure", json={
            "startTime": "13:00", "endTime": "17:00",
            "segments": [
                {"id": source["segments"][0]["id"],
                 "startTime": "13:00", "endTime": "14:00"},
                {"startTime": "16:00", "endTime": "17:00", "status": "pending"},
            ],
        })
        self.assertEqual(custom.status_code, 200, custom.get_data(as_text=True))
        target = self.create("Gap target", "09:00", "11:00")
        move = self.request("post", f"/api/occurrences/{source['id']}/translate", json={
            "startTime": "08:00", "endTime": "12:00",
        })
        self.assertEqual(move.status_code, 200, move.get_data(as_text=True))
        self.assertEqual(next(row for row in self.state()["occurrences"] if row["id"] == target["id"])["status"], "pending")

    def test_new_adjacent_blocker_requires_fresh_confirmation(self):
        first_target = self.create("First target", "09:00", "10:00")
        payload = self.payload("Source", "09:00", "11:00")
        first = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        old_conflict = first.get_json()["conflicts"][0]
        second_target = self.create("New target", "10:00", "11:00")
        payload["conflictResolution"] = {"confirmations": [self.confirmation(old_conflict)]}
        retry = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(retry.status_code, 409, retry.get_data(as_text=True))
        self.assertEqual(retry.get_json()["code"], "segment_conflict_resolution_required")
        self.assertEqual(
            {item["blocker"]["occurrenceId"] for item in retry.get_json()["conflicts"]},
            {first_target["id"], second_target["id"]},
        )
        self.assertEqual(len(self.state()["planItems"]), 2)

    def test_removed_blocker_makes_confirmation_stale(self):
        target = self.create("Target", "08:00", "12:00")
        payload = self.payload("Source", "09:00", "10:00")
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET status = 'cancelled' WHERE id = %s",
                (target["segments"][0]["id"],),
            )
            connection.execute(
                "UPDATE public.occurrences SET status = 'cancelled' WHERE id = %s",
                (target["id"],),
            )
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        response = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["code"], "conflict_resolution_stale")
        self.assertEqual(len(self.state()["planItems"]), 1)

    def test_wrong_sibling_segment_cannot_authorize_blocker(self):
        target = self.create("Target", "08:00", "12:00")
        custom = self.request("put", f"/api/occurrences/{target['id']}/structure", json={
            "startTime": "08:00", "endTime": "12:00",
            "segments": [
                {"id": target["segments"][0]["id"],
                 "startTime": "08:00", "endTime": "09:00"},
                {"startTime": "09:00", "endTime": "12:00", "status": "pending"},
            ],
        })
        self.assertEqual(custom.status_code, 200, custom.get_data(as_text=True))
        payload = self.payload("Source", "10:00", "11:00")
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        wrong = self.confirmation(conflict)
        wrong["blocker"]["segmentId"] = target["segments"][0]["id"]
        payload["conflictResolution"] = {"confirmations": [wrong]}
        response = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["code"], "conflict_resolution_stale")

    def test_repeated_segmentation_latest_context_and_source_move(self):
        target = self.create("Target", "08:00", "12:00")
        first_payload = self.payload("Source A", "09:00", "10:00", subtype="unexpected")
        first_conflict = self.request("post", "/api/plan-items", json=first_payload).get_json()["conflicts"][0]
        first_payload["conflictResolution"] = {"confirmations": [self.confirmation(first_conflict)]}
        created_a = self.request("post", "/api/plan-items", json=first_payload)
        self.assertEqual(created_a.status_code, 201, created_a.get_data(as_text=True))
        source_a = created_a.get_json()["occurrences"][0]
        move = self.request("post", f"/api/occurrences/{source_a['id']}/translate", json={
            "startTime": "13:00", "endTime": "14:00",
        })
        self.assertEqual(move.status_code, 200, move.get_data(as_text=True))
        after_move = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(after_move["conflictContext"]["sourceOccurrenceId"], source_a["id"])
        moved_source = next(row for row in self.state()["occurrences"] if row["id"] == source_a["id"])
        self.assertEqual(moved_source["originReason"], "conflict_insertion")
        self.assertEqual(moved_source["lastConflictAction"], "conflict_insertion")
        first_fragment_id = after_move["segments"][0]["id"]

        second_payload = self.payload("Source B", "10:30", "11:00", subtype="unexpected")
        second_conflict = self.request("post", "/api/plan-items", json=second_payload).get_json()["conflicts"][0]
        second_payload["conflictResolution"] = {"confirmations": [self.confirmation(second_conflict)]}
        created_b = self.request("post", "/api/plan-items", json=second_payload)
        self.assertEqual(created_b.status_code, 201, created_b.get_data(as_text=True))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(changed["segments"][0]["id"], first_fragment_id)
        self.assertEqual(len(changed["segments"]), 3)
        self.assertEqual(changed["conflictContext"]["sourceOccurrenceId"], created_b.get_json()["occurrences"][0]["id"])

    def test_rollback_at_source_child_and_target_parent_failure_points(self):
        target = self.create("Target", "08:00", "12:00")
        payload = self.payload("Source", "09:00", "10:00")
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        before = self.state()
        cases = (
            ("occurrences", "INSERT", "NEW.id <> '%s'" % target["id"]),
            ("occurrence_segments", "UPDATE", "NEW.occurrence_id = '%s'" % target["id"]),
            ("occurrence_segments", "INSERT", "NEW.occurrence_id = '%s'" % target["id"]),
            ("occurrences", "UPDATE", "NEW.id = '%s'" % target["id"]),
        )
        for table, event, condition in cases:
            with self.subTest(table=table, event=event):
                with psycopg.connect(self.url, autocommit=True) as connection:
                    connection.execute("""
                        CREATE OR REPLACE FUNCTION public.reject_conflict_test()
                        RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN RAISE EXCEPTION 'injected conflict failure'; END $$
                    """)
                    connection.execute(
                        f"CREATE TRIGGER reject_conflict_test BEFORE {event} "
                        f"ON public.{table} FOR EACH ROW WHEN ({condition}) "
                        "EXECUTE FUNCTION public.reject_conflict_test()"
                    )
                try:
                    response = self.request("post", "/api/plan-items", json=payload)
                    self.assertEqual(response.status_code, 503, response.get_data(as_text=True))
                    self.assertNotIn("injected conflict failure", response.get_data(as_text=True))
                finally:
                    with psycopg.connect(self.url, autocommit=True) as connection:
                        connection.execute(f"DROP TRIGGER reject_conflict_test ON public.{table}")
                        connection.execute("DROP FUNCTION public.reject_conflict_test()")
                self.assertEqual(self.state(), before)

    def test_competing_confirmed_inserts_do_not_share_stale_snapshot(self):
        target = self.create("Target", "08:00", "12:00")
        payloads = [
            self.payload("Source A", "09:00", "10:00"),
            self.payload("Source B", "10:00", "11:00"),
        ]
        for payload in payloads:
            first = self.request("post", "/api/plan-items", json=payload)
            self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
            payload["conflictResolution"] = {"confirmations": [
                self.confirmation(first.get_json()["conflicts"][0])
            ]}

        def submit(payload):
            return app.test_client().post("/api/plan-items", json=payload)

        with patch.object(database, "get_database_url", return_value=self.url), \
                patch.object(plan_item_creation_service, "_today", return_value=self.today):
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(executor.map(submit, payloads))
        self.assertEqual(sorted(response.status_code for response in responses), [201, 409])
        self.assertIn(
            next(response for response in responses if response.status_code == 409).get_json()["code"],
            {"concurrent_conflict", "conflict_resolution_stale"},
        )
        self.assertEqual(len(self.state()["planItems"]), 2)
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(len(changed["segments"]), 2)

    def test_not_finished_requires_strong_ack_and_keeps_realized_prefix(self):
        target = self.create("Target", "08:00", "10:00", day=self.today)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET status = 'not_finished' WHERE id = %s",
                (target["segments"][0]["id"],),
            )
            connection.execute(
                "UPDATE public.occurrences SET status = 'not_finished' WHERE id = %s",
                (target["id"],),
            )
        payload = self.payload("Source", "09:00", "11:00", subtype="unexpected", day=self.today)
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        self.assertEqual(conflict["requiredAuthorization"], "user_forced_override")
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        weak = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(weak.status_code, 409, weak.get_data(as_text=True))
        payload["conflictResolution"] = {"confirmations": [
            self.confirmation(conflict, realized=True)
        ]}
        strong = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(strong.status_code, 201, strong.get_data(as_text=True))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(changed["segments"][0]["endTime"], "09:00")
        self.assertEqual(changed["segments"][0]["status"], "not_finished")

    def test_in_progress_clear_end_becomes_not_finished(self):
        target = self.create("Target", "08:00", "10:00", day=self.today)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET status = 'in_progress' WHERE id = %s",
                (target["segments"][0]["id"],),
            )
            connection.execute(
                "UPDATE public.occurrences SET status = 'in_progress' WHERE id = %s",
                (target["id"],),
            )
        payload = self.payload("Source", "09:00", "11:00", day=self.today)
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        self.assertEqual(conflict["resolutionKind"], "interrupt_in_progress")
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        response = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual((changed["segments"][0]["endTime"], changed["segments"][0]["status"]),
                         ("09:00", "not_finished"))

    def test_cancelled_and_not_completed_segments_do_not_block(self):
        for status in ("cancelled", "not_completed"):
            with self.subTest(status=status):
                day = self.day if status == "cancelled" else self.today
                target = self.create("Target " + status, "00:01", "00:03", day=day)
                with psycopg.connect(self.url) as connection:
                    connection.execute(
                        "UPDATE public.occurrence_segments SET status = %s WHERE id = %s",
                        (status, target["segments"][0]["id"]),
                    )
                    connection.execute(
                        "UPDATE public.occurrences SET status = %s WHERE id = %s",
                        (status, target["id"]),
                    )
                source = self.request("post", "/api/plan-items", json=self.payload(
                    "Source " + status, "00:01", "00:03", day=day
                ))
                self.assertEqual(source.status_code, 201, source.get_data(as_text=True))

    def test_all_blockers_require_confirmation_before_any_write(self):
        first_target = self.create("First", "09:00", "10:00")
        second_target = self.create("Second", "11:00", "12:00")
        payload = self.payload("Source", "09:00", "12:00", subtype="unexpected")
        first = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        conflicts = first.get_json()["conflicts"]
        self.assertEqual(len(conflicts), 2)
        before = self.state()
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflicts[0])]}
        partial = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(partial.status_code, 409, partial.get_data(as_text=True))
        self.assertEqual(self.state(), before)
        payload["conflictResolution"] = {"confirmations": [
            self.confirmation(conflict) for conflict in conflicts
        ]}
        complete = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(complete.status_code, 201, complete.get_data(as_text=True))
        rows = self.state()["occurrences"]
        for target in (first_target, second_target):
            changed = next(row for row in rows if row["id"] == target["id"])
            self.assertEqual(changed["status"], "cancelled")

    def test_custom_source_subtracts_both_segments_not_parent_envelope(self):
        target = self.create("Target", "08:00", "12:00")
        source = self.create("Source", "13:00", "17:00", subtype="unexpected")
        custom = self.request("put", f"/api/occurrences/{source['id']}/structure", json={
            "startTime": "13:00", "endTime": "17:00",
            "segments": [
                {"id": source["segments"][0]["id"],
                 "startTime": "13:00", "endTime": "14:00"},
                {"startTime": "16:00", "endTime": "17:00", "status": "pending"},
            ],
        })
        self.assertEqual(custom.status_code, 200, custom.get_data(as_text=True))
        path = f"/api/occurrences/{source['id']}/translate"
        command = {"startTime": "08:00", "endTime": "12:00"}
        first = self.request("post", path, json=command)
        self.assertEqual(first.status_code, 409, first.get_data(as_text=True))
        command["conflictResolution"] = {"confirmations": [
            self.confirmation(first.get_json()["conflicts"][0])
        ]}
        confirmed = self.request("post", path, json=command)
        self.assertEqual(confirmed.status_code, 200, confirmed.get_data(as_text=True))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(
            [(segment["startTime"], segment["endTime"]) for segment in changed["segments"]],
            [("09:00", "11:00")],
        )
        self.assertEqual((changed["startTime"], changed["endTime"]), ("08:00", "12:00"))

    def test_completed_full_coverage_requires_strong_ack_then_cancels(self):
        target = self.create("Target", "00:01", "00:03", day=self.today)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET status = 'completed' WHERE id = %s",
                (target["segments"][0]["id"],),
            )
            connection.execute(
                "UPDATE public.occurrences SET status = 'completed' WHERE id = %s",
                (target["id"],),
            )
        payload = self.payload("Source", "00:01", "00:03", subtype="unexpected", day=self.today)
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        self.assertEqual(conflict["resolutionKind"], "cancel_segment")
        payload["conflictResolution"] = {"confirmations": [
            self.confirmation(conflict, realized=True)
        ]}
        response = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(changed["segments"], [{
            "id": target["segments"][0]["id"], "startTime": "00:01",
            "endTime": "00:03", "status": "cancelled",
        }])
        self.assertEqual(changed["conflictContext"]["reason"], "user_forced_override")

    def test_frozen_target_cannot_be_rewritten_even_with_confirmation(self):
        target = self.create("Target", "08:00", "10:00")
        payload = self.payload("Source", "09:00", "10:00", subtype="unexpected")
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        confirmations = validate_confirmations({"confirmations": [self.confirmation(conflict)]})
        before = self.state()
        with psycopg.connect(self.url) as connection:
            with connection.transaction():
                with self.assertRaises(SegmentConflictError) as error:
                    resolve_source_conflicts(
                        connection,
                        source_id=uuid4(), source_date=self.day,
                        source_segments=[{
                            "id": uuid4(), "startTime": time(9), "endTime": time(10),
                            "status": "pending",
                        }],
                        source_priority=300, confirmations=confirmations,
                        action="conflict_insertion",
                        now=datetime.combine(self.day + timedelta(days=3), time(12)),
                    )
        self.assertEqual(error.exception.code, "conflict_resolution_frozen")
        self.assertEqual(self.state(), before)

    def test_in_progress_beginning_correction_retains_active_suffix(self):
        target = self.create("Target", "09:00", "12:00", day=self.today)
        with psycopg.connect(self.url) as connection:
            connection.execute(
                "UPDATE public.occurrence_segments SET status = 'in_progress' WHERE id = %s",
                (target["segments"][0]["id"],),
            )
            connection.execute(
                "UPDATE public.occurrences SET status = 'in_progress' WHERE id = %s",
                (target["id"],),
            )
        payload = self.payload("Source", "08:00", "11:00", day=self.today)
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        result = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(result.status_code, 201, result.get_data(as_text=True))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual((changed["segments"][0]["startTime"], changed["segments"][0]["status"]),
                         ("11:00", "in_progress"))

    def test_referenced_source_delete_remains_restricted_by_fk(self):
        target = self.create("Target", "08:00", "12:00")
        payload = self.payload("Source", "09:00", "10:00", subtype="unexpected")
        conflict = self.request("post", "/api/plan-items", json=payload).get_json()["conflicts"][0]
        payload["conflictResolution"] = {"confirmations": [self.confirmation(conflict)]}
        created = self.request("post", "/api/plan-items", json=payload)
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        source_id = created.get_json()["occurrences"][0]["id"]
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with psycopg.connect(self.url) as connection:
                connection.execute("DELETE FROM public.occurrences WHERE id = %s", (source_id,))
        changed = next(row for row in self.state()["occurrences"] if row["id"] == target["id"])
        self.assertEqual(changed["conflictContext"]["sourceOccurrenceId"], source_id)
