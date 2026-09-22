"""Pruebas de validación, materialización y escritura atómica."""

from datetime import date, time
import json
import os
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


def slot_id(number):
    return f"00000000-0000-4000-8000-{number:012d}"


def weekly_config(**changes):
    config = {
        "mode": "weekly",
        "startDate": "2026-09-11",
        "endDate": None,
        "indefinite": True,
        "slots": [
            {
                "id": slot_id(index),
                "isoWeekday": weekday,
                "startTime": "08:00",
                "endTime": "09:00",
            }
            for index, weekday in enumerate((1, 3, 5), start=1)
        ],
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
        "slots": [
            {
                "id": slot_id(20),
                "startTime": "12:00",
                "endTime": "13:00",
            }
        ],
    }
    config.update(changes)
    return config


def manual_config(entries=None, **controls):
    source_entries = entries if entries is not None else [
        {
            "date": "2026-09-11",
            "startTime": "10:00",
            "endTime": "11:00",
        }
    ]
    return {
        "mode": "manual_dates",
        "entries": [
            {
                "id": entry.get("id", slot_id(30 + index)),
                **entry,
            }
            for index, entry in enumerate(source_entries)
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

    def test_segment_conflict_resolution_is_optional_command_metadata(self):
        occurrence_id = str(UUID(int=700))
        segment_id = str(UUID(int=701))
        payload = {
            **activity_payload(),
            "conflictResolution": {
                "confirmations": [{
                    "blocker": {
                        "occurrenceId": occurrence_id,
                        "segmentId": segment_id,
                        "startTime": "10:00",
                        "endTime": "11:00",
                        "status": "pending",
                    },
                    "confirmed": True,
                }],
            },
        }
        normalized, confirmed = creation_service.validate_plan_item_command(payload)
        self.assertNotIn("conflictResolution", normalized)
        self.assertEqual(set(confirmed), {(UUID(occurrence_id), UUID(segment_id))})
        self.assertIsNone(
            creation_service.validate_plan_item_command(activity_payload())[1]
        )

    def test_rejects_legacy_priority_override_and_invalid_confirmations(self):
        with self.assertRaises(creation_service.PlanItemValidationError):
            creation_service.validate_plan_item_command({
                **activity_payload(),
                "priorityOverride": {"confirmedOccurrenceIds": [str(UUID(int=701))]},
            })
        invalid_values = (
            None,
            {},
            {"confirmations": "not-a-list"},
            {"confirmations": [{"blocker": {}, "confirmed": True}]},
            {"confirmations": [], "unexpected": True},
        )
        for conflict_resolution in invalid_values:
            with self.subTest(conflict_resolution=conflict_resolution), self.assertRaises(
                creation_service.PlanItemValidationError
            ):
                creation_service.validate_plan_item_command(
                    {
                        **activity_payload(),
                        "conflictResolution": conflict_resolution,
                    }
                )

    def test_recurring_slots_accept_excluded_dates_but_manual_entries_do_not(self):
        config = weekly_config()
        config["slots"][0]["excludedDates"] = ["2026-09-18", "2026-09-15"]
        normalized = creation_service.validate_plan_item_payload(
            activity_payload(config)
        )
        self.assertEqual(
            normalized["generationConfig"]["slots"][0]["excludedDates"],
            ["2026-09-15", "2026-09-18"],
        )

        manual = manual_config()
        manual["entries"][0]["excludedDates"] = ["2026-09-11"]
        with self.assertRaises(creation_service.PlanItemValidationError):
            creation_service.validate_plan_item_payload(activity_payload(manual))

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
        first_weekly_slot = weekly_config()["slots"][0]
        invalid_payloads = [
            {**activity_payload(), "name": " "},
            {**activity_payload(), "activityType": "unknown"},
            {**habit_payload(), "activityType": "periodic"},
            activity_payload(weekly_config(slots=[])),
            activity_payload(weekly_config(slots=[first_weekly_slot, first_weekly_slot])),
            activity_payload(weekly_config(slots=[{**first_weekly_slot, "endTime": "07:00"}])),
            activity_payload(weekly_config(slots=[{**first_weekly_slot, "id": "not-a-uuid"}])),
            activity_payload(interval_config(intervalDays=0)),
            activity_payload(manual_config(entries=[])),
            activity_payload(manual_config(entries=[
                {"date": "2026-09-11", "startTime": "10:00", "endTime": "12:00"},
                {"date": "2026-09-11", "startTime": "11:00", "endTime": "13:00"},
            ])),
            activity_payload(manual_config(excludedDates=["2026-09-12"])),
            activity_payload(manual_config(stoppedFromDate="invalid")),
            activity_payload(weekly_config(defaultStartTime="08:00")),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(creation_service.PlanItemValidationError):
                    creation_service.validate_plan_item_payload(payload)

    def test_normalizes_name_order_and_optional_controls(self):
        payload = activity_payload(
            weekly_config(
                slots=[
                    {"id": slot_id(5), "isoWeekday": 5, "startTime": "10:00", "endTime": "11:00"},
                    {"id": slot_id(1), "isoWeekday": 1, "startTime": "08:00", "endTime": "09:00"},
                ],
                excludedDates=["2026-09-25", "2026-09-12"],
                stoppedFromDate="2026-10-01",
            )
        )
        payload["name"] = "  Actividad normalizada  "
        result = creation_service.validate_plan_item_payload(payload)
        self.assertEqual(result["name"], "Actividad normalizada")
        self.assertEqual(
            [slot["isoWeekday"] for slot in result["generationConfig"]["slots"]],
            [1, 5],
        )
        self.assertEqual(
            result["generationConfig"]["excludedDates"],
            ["2026-09-12", "2026-09-25"],
        )

    def test_adjacent_slots_are_valid_and_overlapping_slots_are_rejected(self):
        valid_cases = (
            weekly_config(slots=[
                {"id": slot_id(1), "isoWeekday": 1, "startTime": "08:00", "endTime": "09:00"},
                {"id": slot_id(2), "isoWeekday": 1, "startTime": "09:00", "endTime": "10:00"},
            ]),
            interval_config(slots=[
                {"id": slot_id(20), "startTime": "08:00", "endTime": "09:00"},
                {"id": slot_id(21), "startTime": "09:00", "endTime": "10:00"},
            ]),
            manual_config(entries=[
                {"date": "2026-09-11", "startTime": "08:00", "endTime": "09:00"},
                {"date": "2026-09-11", "startTime": "09:00", "endTime": "10:00"},
            ]),
        )
        for config in valid_cases:
            with self.subTest(mode=config["mode"]):
                creation_service.validate_plan_item_payload(activity_payload(config))

        overlapping_cases = (
            weekly_config(slots=[
                {"id": slot_id(1), "isoWeekday": 1, "startTime": "08:00", "endTime": "10:00"},
                {"id": slot_id(2), "isoWeekday": 1, "startTime": "09:00", "endTime": "11:00"},
            ]),
            interval_config(slots=[
                {"id": slot_id(20), "startTime": "08:00", "endTime": "10:00"},
                {"id": slot_id(21), "startTime": "09:00", "endTime": "11:00"},
            ]),
        )
        for config in overlapping_cases:
            with self.subTest(mode=config["mode"]), self.assertRaises(
                creation_service.PlanItemValidationError
            ):
                creation_service.validate_plan_item_payload(activity_payload(config))

    def test_slot_ids_are_preserved_and_duplicates_are_rejected(self):
        config = weekly_config(slots=[
            {"id": slot_id(101), "isoWeekday": 1, "startTime": "08:00", "endTime": "09:00"},
            {"id": slot_id(102), "isoWeekday": 2, "startTime": "10:00", "endTime": "11:00"},
        ])
        normalized = creation_service.validate_plan_item_payload(
            activity_payload(config)
        )
        self.assertEqual(
            [slot["id"] for slot in normalized["generationConfig"]["slots"]],
            [slot_id(101), slot_id(102)],
        )

        config["slots"][1]["id"] = slot_id(101)
        with self.assertRaises(creation_service.PlanItemValidationError):
            creation_service.validate_plan_item_payload(activity_payload(config))


class MaterializationTests(unittest.TestCase):
    def test_weekly_interval_and_manual_dates(self):
        cases = (
            (
                activity_payload(
                    weekly_config(
                        slots=[
                            {"id": slot_id(5), "isoWeekday": 5, "startTime": "10:00", "endTime": "11:30"}
                        ]
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
                for occurrence in result["occurrences"]:
                    self.assertEqual(len(occurrence["segments"]), 1)
                    segment = occurrence["segments"][0]
                    self.assertEqual(segment["occurrenceId"], occurrence["id"])
                    self.assertEqual(segment["startTime"], occurrence["startTime"])
                    self.assertEqual(segment["endTime"], occurrence["endTime"])
                    self.assertEqual(segment["status"], occurrence["status"])
                    self.assertEqual(
                        occurrence["sourceGenerationSlotId"],
                        next(
                            item["id"]
                            for item in (
                                payload["generationConfig"].get("slots")
                                or payload["generationConfig"].get("entries")
                            )
                            if item["startTime"] == occurrence["startTime"]
                            and item["endTime"] == occurrence["endTime"]
                        ),
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

    def test_multiple_occurrences_same_day_keep_slot_provenance(self):
        config = manual_config(entries=[
            {"id": slot_id(31), "date": "2026-09-11", "startTime": "08:00", "endTime": "09:00"},
            {"id": slot_id(32), "date": "2026-09-11", "startTime": "10:00", "endTime": "11:00"},
        ])
        result, _, _ = create_without_database(activity_payload(config))
        self.assertEqual(len(result["occurrences"]), 2)
        self.assertEqual(
            [item["sourceGenerationSlotId"] for item in result["occurrences"]],
            [slot_id(31), slot_id(32)],
        )
        self.assertEqual(
            len({(item["sourceGenerationSlotId"], item["date"]) for item in result["occurrences"]}),
            2,
        )
        segment_ids = set()
        for occurrence in result["occurrences"]:
            self.assertEqual(len(occurrence["segments"]), 1)
            segment = occurrence["segments"][0]
            self.assertEqual(segment["occurrenceId"], occurrence["id"])
            self.assertEqual(segment["startTime"], occurrence["startTime"])
            self.assertEqual(segment["endTime"], occurrence["endTime"])
            self.assertEqual(segment["status"], occurrence["status"])
            self.assertEqual(UUID(segment["id"]).version, 4)
            self.assertNotEqual(segment["id"], occurrence["id"])
            segment_ids.add(segment["id"])
        self.assertEqual(len(segment_ids), len(result["occurrences"]))

    def test_uber_week_materializes_seventeen_occurrences(self):
        slots = []
        sequence = 200
        for weekday in range(1, 6):
            for start_time, end_time in (
                ("08:00", "11:00"),
                ("14:00", "17:00"),
                ("20:00", "22:00"),
            ):
                sequence += 1
                slots.append({
                    "id": slot_id(sequence),
                    "isoWeekday": weekday,
                    "startTime": start_time,
                    "endTime": end_time,
                })
        for weekday in (6, 7):
            sequence += 1
            slots.append({
                "id": slot_id(sequence),
                "isoWeekday": weekday,
                "startTime": "08:00",
                "endTime": "21:00",
            })
        config = weekly_config(
            startDate="2026-09-14",
            endDate="2026-09-20",
            indefinite=False,
            slots=slots,
        )
        result, _, _ = create_without_database(
            activity_payload(config), reference_date=date(2026, 9, 14)
        )
        self.assertEqual(len(result["occurrences"]), 17)
        self.assertEqual(
            {item["sourceGenerationSlotId"] for item in result["occurrences"]},
            {slot["id"] for slot in slots},
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
                            slots=[
                                {"id": slot_id(1), "isoWeekday": 1, "startTime": "08:00", "endTime": "09:00"},
                                {"id": slot_id(2), "isoWeekday": 1, "startTime": "09:00", "endTime": "10:00", "excludedDates": ["2026-09-21"]},
                                {"id": slot_id(4), "isoWeekday": 1, "startTime": "10:00", "endTime": "11:00"},
                                {"id": slot_id(3), "isoWeekday": 3, "startTime": "14:00", "endTime": "15:00"},
                                {"id": slot_id(5), "isoWeekday": 5, "startTime": "10:00", "endTime": "11:30"},
                            ],
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
                        interval_config(
                            slots=[
                                {"id": slot_id(20), "startTime": "08:00", "endTime": "09:00"},
                                {"id": slot_id(21), "startTime": "12:00", "endTime": "13:00"},
                            ],
                            excludedDates=["2026-09-17"],
                            stoppedFromDate="2026-09-25",
                        )
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
    @staticmethod
    def _existing(occurrence_id=900, status="pending", start=time(10, 30)):
        return {
            "id": UUID(int=occurrence_id),
            "plan_item_id": UUID(int=occurrence_id + 100),
            "occurrence_date": REFERENCE_DATE,
            "start_time": start,
            "end_time": time(11, 30),
            "status": status,
            "kind": "activity",
            "subtype": "periodic",
        }

    def test_overlapping_manual_entries_are_invalid_payload(self):
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
        with self.assertRaises(creation_service.PlanItemValidationError):
            creation_service.create_plan_item(payload, reference_date=REFERENCE_DATE)

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


class RepositoryWriteTests(unittest.TestCase):
    def test_weekly_graph_includes_slots_details_exclusions_and_occurrences(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        plan_item = {
            "id": str(UUID(int=1)),
            **activity_payload(
                weekly_config(
                    slots=[
                        {"id": slot_id(1), "isoWeekday": 1, "startTime": "08:00", "endTime": "09:00"},
                        {"id": slot_id(5), "isoWeekday": 5, "startTime": "10:00", "endTime": "11:00"},
                    ],
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
            "sourceGenerationSlotId": slot_id(5),
            "segments": [
                {
                    "id": str(UUID(int=3)),
                    "occurrenceId": str(UUID(int=2)),
                    "startTime": "10:00",
                    "endTime": "11:00",
                    "status": "pending",
                }
            ],
        }

        plan_item_repository.insert_plan_item_graph(
            connection, plan_item, [occurrence]
        )

        executed = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        batches = {
            call.args[0]: call.args[1] for call in cursor.executemany.call_args_list
        }
        self.assertIn("public.plan_items", executed)
        self.assertIn("public.generation_configs", executed)
        weekday_query = next(
            query
            for query in batches
            if "public.generation_slot_weekdays" in query
        )
        self.assertEqual(
            batches[weekday_query],
            [
                (slot_id(1), 1),
                (slot_id(5), 5),
            ],
        )
        slot_query = next(
            query for query in batches if "public.generation_slots" in query
        )
        self.assertEqual(
            [parameters[0] for parameters in batches[slot_query]],
            [slot_id(1), slot_id(5)],
        )
        self.assertTrue(
            any("public.generation_excluded_dates" in query for query in batches)
        )
        self.assertTrue(any("public.occurrences" in query for query in batches))
        occurrence_query = next(
            query
            for query in batches
            if "INSERT INTO public.occurrences" in query
        )
        self.assertIn("conflict_reason", occurrence_query)
        self.assertNotIn("status_reason", occurrence_query)
        segment_query = next(
            query for query in batches if "public.occurrence_segments" in query
        )
        self.assertEqual(
            batches[segment_query],
            [
                (
                    str(UUID(int=3)),
                    str(UUID(int=2)),
                    "10:00",
                    "11:00",
                    "pending",
                )
            ],
        )

    def test_recurring_graph_persists_slot_exclusions(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        config = weekly_config()
        config["slots"][0]["excludedDates"] = ["2026-09-15"]
        plan_item = {"id": str(UUID(int=1)), **activity_payload(config)}

        plan_item_repository.insert_plan_item_graph(connection, plan_item, [])

        exclusion_call = next(
            call
            for call in cursor.executemany.call_args_list
            if "public.generation_slot_excluded_dates" in call.args[0]
        )
        self.assertEqual(
            exclusion_call.args[1],
            [(config["slots"][0]["id"], "2026-09-15")],
        )

    def test_manual_graph_preserves_entry_ids_in_slot_and_date_detail(self):
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
        plan_item_repository.insert_plan_item_graph(
            connection, plan_item, []
        )

        entry_call = next(
            call
            for call in cursor.executemany.call_args_list
            if "public.generation_slot_dates" in call.args[0]
        )
        self.assertEqual(
            [parameters[0] for parameters in entry_call.args[1]],
            [entry["id"] for entry in plan_item["generationConfig"]["entries"]],
        )

    def test_priority_overrides_map_status_and_source_occurrence(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        source_id = str(UUID(int=800))
        pending_id = str(UUID(int=801))
        in_progress_id = str(UUID(int=802))

        plan_item_repository.apply_priority_overrides(
            connection,
            [
                {
                    "occurrenceId": pending_id,
                    "currentStatus": "pending",
                    "sourceOccurrenceId": source_id,
                },
                {
                    "occurrenceId": in_progress_id,
                    "currentStatus": "in_progress",
                    "sourceOccurrenceId": source_id,
                },
            ],
        )

        parameters = [call.args[1] for call in cursor.execute.call_args_list]
        self.assertEqual(
            parameters,
            [
                ("cancelled", source_id, pending_id, "pending"),
                ("not_finished", source_id, in_progress_id, "in_progress"),
            ],
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
            ("generation_configs", activity_payload()),
            ("generation_slots", activity_payload()),
            ("generation_slot_dates", activity_payload()),
            ("generation_slot_weekdays", activity_payload(weekly_config())),
            (
                "generation_excluded_dates",
                activity_payload(
                    weekly_config(excludedDates=["2026-09-14"])
                ),
            ),
            (
                "generation_slot_excluded_dates",
                activity_payload(
                    weekly_config(
                        slots=[
                            {
                                "id": slot_id(91),
                                "isoWeekday": 1,
                                "startTime": "08:00",
                                "endTime": "09:00",
                                "excludedDates": ["2026-09-14"],
                            }
                        ]
                    )
                ),
            ),
            ("occurrences", activity_payload()),
            ("occurrence_segments", activity_payload()),
        )
        for table_name, payload in cases:
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
                            payload, reference_date=REFERENCE_DATE
                        )
                self.assertNotIn("PRIVATE_DATABASE_DETAIL", str(error.exception))
                transaction.__exit__.assert_called_once()
                self.assertIsNotNone(transaction.__exit__.call_args.args[0])
                connection.__exit__.assert_called_once()

    def test_success_uses_one_connection_and_one_transaction(self):
        result, connection, insert = create_without_database(activity_payload())
        connection.transaction.assert_called_once_with()
        self.assertEqual(
            connection.isolation_level,
            creation_service.IsolationLevel.SERIALIZABLE,
        )
        insert.assert_called_once()
        persisted_connection, plan_item, occurrences = insert.call_args.args
        self.assertIs(persisted_connection, connection)
        self.assertEqual(plan_item, result["planItem"])
        self.assertEqual(occurrences, result["occurrences"])


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

    def test_cors_allows_only_plan_item_post_and_preflight(self):
        origin = "http://127.0.0.1:8000"
        with patch.dict(os.environ, {"VCS_ALLOWED_ORIGINS": origin}), patch.object(
            creation_service,
            "create_plan_item",
            return_value={"planItem": {}, "occurrences": []},
        ):
            preflight = self.client.options(
                "/api/plan-items",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
            post = self.client.post(
                "/api/plan-items", json=activity_payload(), headers={"Origin": origin}
            )
            unrelated = self.client.get("/api/health", headers={"Origin": origin})
            rejected = self.client.options(
                "/api/plan-items",
                headers={"Origin": "http://example.invalid"},
            )

        for response in (preflight, post):
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Origin"), origin
            )
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Methods"),
                "POST, OPTIONS",
            )
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Headers"),
                "Content-Type",
            )
        self.assertNotIn("Access-Control-Allow-Origin", unrelated.headers)
        self.assertNotIn("Access-Control-Allow-Origin", rejected.headers)

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

    def test_priority_override_409_includes_confirmable_conflicts(self):
        conflicts = [
            {
                "occurrenceId": str(UUID(int=10)),
                "planItemId": str(UUID(int=11)),
                "date": "2026-09-11",
                "startTime": "10:00",
                "endTime": "11:00",
                "status": "pending",
            }
        ]
        with patch.object(
            creation_service,
            "create_plan_item",
            side_effect=creation_service.PlanItemConflictError(
                "priority_override_required",
                "Se requiere confirmación.",
                conflicts,
            ),
        ):
            response = self.client.post("/api/plan-items", json=activity_payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(),
            {
                "status": "error",
                "code": "priority_override_required",
                "message": "Se requiere confirmación.",
                "conflicts": conflicts,
            },
        )

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
