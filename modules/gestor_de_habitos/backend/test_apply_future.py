"""Pruebas sin secretos para Apply Future persistente."""

from datetime import date, time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from app import app
import database
import future_schedule_service as service


REFERENCE_DATE = date(2026, 9, 17)
PLAN_ITEM_ID = UUID("00000000-0000-0000-0000-000000000010")


def slot_id(number):
    return UUID(f"00000000-0000-4000-8000-{number:012d}")


def occurrence_id(number):
    return UUID(f"00000000-0000-0000-0000-{number:012d}")


def row(number, slot_number, day, start, end, **changes):
    result = {
        "id": occurrence_id(number),
        "plan_item_id": PLAN_ITEM_ID,
        "occurrence_date": day,
        "start_time": time.fromisoformat(start),
        "end_time": time.fromisoformat(end),
        "status": "pending",
        "status_reason": None,
        "source_occurrence_id": None,
        "source_generation_slot_id": (
            slot_id(slot_number) if slot_number is not None else None
        ),
    }
    result.update(changes)
    return result


def plan_item(config):
    return {
        "id": str(PLAN_ITEM_ID),
        "name": "Trabajo",
        "kind": "activity",
        "activityType": "periodic",
        "generationConfig": config,
    }


class PayloadTests(unittest.TestCase):
    def test_accepts_exact_weekly_and_interval_contracts(self):
        weekly = service.validate_apply_future_payload(
            {
                "futureConfig": {
                    "mode": "weekly",
                    "startDate": "2026-09-21",
                    "endDate": None,
                    "indefinite": True,
                    "slots": [
                        {
                            "id": str(slot_id(1)),
                            "isoWeekday": 1,
                            "startTime": "09:00",
                            "endTime": "12:00",
                        }
                    ],
                }
            }
        )
        self.assertEqual(weekly["mode"], "weekly")
        interval = service.validate_apply_future_payload(
            {
                "futureConfig": {
                    "mode": "interval_days",
                    "startDate": "2026-09-21",
                    "endDate": None,
                    "indefinite": True,
                    "intervalDays": 3,
                    "slots": [
                        {
                            "id": str(slot_id(1)),
                            "startTime": "09:00",
                            "endTime": "10:00",
                        }
                    ],
                }
            }
        )
        self.assertEqual(interval["intervalDays"], 3)

    def test_rejects_extra_fields_overlap_bad_uuid_and_manual_dates(self):
        base = {
            "mode": "weekly",
            "startDate": "2026-09-21",
            "endDate": None,
            "indefinite": True,
            "slots": [
                {
                    "id": str(slot_id(1)),
                    "isoWeekday": 1,
                    "startTime": "09:00",
                    "endTime": "12:00",
                }
            ],
        }
        invalid = (
            {"futureConfig": {**base, "excludedDates": []}},
            {
                "futureConfig": {
                    **base,
                    "slots": [
                        *base["slots"],
                        {
                            "id": str(slot_id(2)),
                            "isoWeekday": 1,
                            "startTime": "11:00",
                            "endTime": "13:00",
                        },
                    ],
                }
            },
            {
                "futureConfig": {
                    **base,
                    "slots": [{**base["slots"][0], "id": "not-a-uuid"}],
                }
            },
        )
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(
                service.FutureValidationError
            ):
                service.validate_apply_future_payload(payload)

        with self.assertRaises(service.FutureConflictError) as error:
            service.validate_apply_future_payload(
                {
                    "futureConfig": {
                        "mode": "manual_dates",
                        "entries": [
                            {
                                "id": str(slot_id(1)),
                                "date": "2026-09-21",
                                "startTime": "09:00",
                                "endTime": "10:00",
                            }
                        ],
                    }
                }
            )
        self.assertEqual(error.exception.code, "unsupported_mode")

    def test_invalid_identifier_and_frozen_boundary_fail_before_database(self):
        payload = {
            "futureConfig": {
                "mode": "weekly",
                "startDate": "2026-09-14",
                "endDate": None,
                "indefinite": True,
                "slots": [
                    {
                        "id": str(slot_id(1)),
                        "isoWeekday": 1,
                        "startTime": "09:00",
                        "endTime": "10:00",
                    }
                ],
            }
        }
        with patch.object(database, "get_connection") as connect, self.assertRaises(
            service.FutureValidationError
        ) as invalid:
            service.apply_future("invalid", payload, reference_date=REFERENCE_DATE)
        self.assertEqual(invalid.exception.code, "invalid_identifier")
        connect.assert_not_called()

        with patch.object(database, "get_connection") as connect, self.assertRaises(
            service.FutureConflictError
        ) as frozen:
            service.apply_future(
                str(PLAN_ITEM_ID), payload, reference_date=REFERENCE_DATE
            )
        self.assertEqual(frozen.exception.code, "history_frozen")
        connect.assert_not_called()


class ReconciliationTests(unittest.TestCase):
    def test_snapshot_rejects_occurrence_owned_by_another_slot_set(self):
        config = {
            "mode": "weekly",
            "startDate": "2026-09-01",
            "endDate": None,
            "indefinite": True,
            "slots": [
                {
                    "id": str(slot_id(1)),
                    "isoWeekday": 1,
                    "startTime": "08:00",
                    "endTime": "09:00",
                }
            ],
        }
        inconsistent = row(1, 99, date(2026, 9, 21), "08:00", "09:00")
        with self.assertRaises(service.FutureConsistencyError):
            service._validate_snapshot_occurrences([inconsistent], config)

    def test_weekly_snapshot_classifies_baseline_override_and_ad_hoc(self):
        old = plan_item(
            {
                "mode": "weekly",
                "startDate": "2026-09-01",
                "endDate": None,
                "indefinite": True,
                "slots": [
                    {
                        "id": str(slot_id(1)),
                        "isoWeekday": 1,
                        "startTime": "08:00",
                        "endTime": "11:00",
                    },
                    {
                        "id": str(slot_id(2)),
                        "isoWeekday": 2,
                        "startTime": "14:00",
                        "endTime": "17:00",
                    },
                ],
            }
        )
        candidate = plan_item(
            {
                "mode": "weekly",
                "startDate": "2026-09-21",
                "endDate": None,
                "indefinite": True,
                "slots": [
                    {
                        "id": str(slot_id(1)),
                        "isoWeekday": 1,
                        "startTime": "09:00",
                        "endTime": "12:00",
                    },
                    {
                        "id": str(slot_id(3)),
                        "isoWeekday": 3,
                        "startTime": "20:00",
                        "endTime": "22:00",
                    },
                ],
            }
        )
        baseline_one = row(1, 1, date(2026, 9, 21), "08:00", "11:00")
        baseline_removed = row(2, 2, date(2026, 9, 22), "14:00", "17:00")
        override_removed = row(3, 2, date(2026, 9, 29), "15:00", "18:00")
        ad_hoc = row(4, None, date(2026, 9, 25), "18:00", "19:00")
        snapshot = {
            "occurrences": [baseline_one, baseline_removed, override_removed, ad_hoc]
        }

        result = service._candidate_state(
            snapshot,
            old,
            candidate,
            date(2026, 9, 21),
            REFERENCE_DATE,
            uuid4,
        )
        by_id = {item["id"]: item for item in result["final_rows"]}
        self.assertEqual(by_id[baseline_one["id"]]["start_time"], time(9))
        self.assertNotIn(baseline_removed["id"], by_id)
        self.assertIsNone(by_id[override_removed["id"]]["source_generation_slot_id"])
        self.assertEqual(by_id[override_removed["id"]]["start_time"], time(15))
        self.assertEqual(by_id[ad_hoc["id"]], ad_hoc)
        new_slot_rows = [
            item
            for item in result["creates"]
            if item["source_generation_slot_id"] == slot_id(3)
        ]
        self.assertTrue(new_slot_rows)
        self.assertTrue(
            all(item["occurrence_date"] >= date(2026, 9, 21) for item in new_slot_rows)
        )

    def test_interval_start_date_restarts_phase(self):
        old = plan_item(
            {
                "mode": "interval_days",
                "startDate": "2026-09-01",
                "endDate": None,
                "indefinite": True,
                "intervalDays": 2,
                "slots": [
                    {"id": str(slot_id(1)), "startTime": "08:00", "endTime": "09:00"}
                ],
            }
        )
        candidate = plan_item(
            {
                "mode": "interval_days",
                "startDate": "2026-09-21",
                "endDate": None,
                "indefinite": True,
                "intervalDays": 3,
                "slots": [
                    {"id": str(slot_id(1)), "startTime": "09:00", "endTime": "10:00"}
                ],
            }
        )
        result = service._candidate_state(
            {"occurrences": []},
            old,
            candidate,
            date(2026, 9, 21),
            REFERENCE_DATE,
            uuid4,
        )
        dates = [item["occurrence_date"].isoformat() for item in result["creates"][:3]]
        self.assertEqual(dates, ["2026-09-21", "2026-09-24", "2026-09-27"])

    def test_override_for_reused_slot_survives_and_suppresses_new_baseline(self):
        old = plan_item(
            {
                "mode": "weekly",
                "startDate": "2026-09-01",
                "endDate": "2026-09-30",
                "indefinite": False,
                "slots": [
                    {
                        "id": str(slot_id(1)),
                        "isoWeekday": 3,
                        "startTime": "14:00",
                        "endTime": "17:00",
                    }
                ],
            }
        )
        candidate = plan_item(
            {
                "mode": "weekly",
                "startDate": "2026-09-21",
                "endDate": "2026-09-30",
                "indefinite": False,
                "slots": [
                    {
                        "id": str(slot_id(1)),
                        "isoWeekday": 3,
                        "startTime": "16:00",
                        "endTime": "19:00",
                    }
                ],
            }
        )
        override = row(1, 1, date(2026, 9, 23), "15:00", "18:00")

        result = service._candidate_state(
            {"occurrences": [override]},
            old,
            candidate,
            date(2026, 9, 21),
            REFERENCE_DATE,
            uuid4,
        )

        same_slot_date = [
            item
            for item in result["final_rows"]
            if item["source_generation_slot_id"] == slot_id(1)
            and item["occurrence_date"] == date(2026, 9, 23)
        ]
        self.assertEqual(same_slot_date, [override])
        self.assertFalse(
            any(
                item["source_generation_slot_id"] == slot_id(1)
                and item["occurrence_date"] == date(2026, 9, 23)
                for item in result["creates"]
            )
        )

    def test_non_pending_baseline_is_preserved_with_status(self):
        config = {
            "mode": "weekly",
            "startDate": "2026-09-01",
            "endDate": None,
            "indefinite": True,
            "slots": [
                {
                    "id": str(slot_id(1)),
                    "isoWeekday": 1,
                    "startTime": "08:00",
                    "endTime": "09:00",
                }
            ],
        }
        protected = row(
            1,
            1,
            date(2026, 9, 21),
            "08:00",
            "09:00",
            status="completed",
        )
        candidate = plan_item(
            {
                **config,
                "startDate": "2026-09-21",
                "slots": [{**config["slots"][0], "startTime": "10:00", "endTime": "11:00"}],
            }
        )
        result = service._candidate_state(
            {"occurrences": [protected]},
            plan_item(config),
            candidate,
            date(2026, 9, 21),
            REFERENCE_DATE,
            uuid4,
        )
        preserved = next(item for item in result["final_rows"] if item["id"] == protected["id"])
        self.assertEqual(preserved["status"], "completed")
        self.assertEqual(preserved["start_time"], time(8))
        self.assertNotIn(protected, result["updates"])


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_success_and_sanitized_error_mapping(self):
        expected = {"planItem": {"id": str(PLAN_ITEM_ID)}, "occurrences": []}
        with patch.object(service, "apply_future", return_value=expected):
            response = self.client.post(
                f"/api/plan-items/{PLAN_ITEM_ID}/apply-future",
                json={"futureConfig": {}},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)

        cases = (
            (service.FutureValidationError("invalid_payload", "PRIVATE"), 400, "invalid_payload"),
            (service.FuturePlanItemNotFoundError("PRIVATE"), 404, "plan_item_not_found"),
            (service.FutureConflictError("unsupported_mode", "No disponible."), 409, "unsupported_mode"),
            (service.FutureConsistencyError("PRIVATE"), 500, "persisted_state_invalid"),
            (service.FutureUnavailableError("PRIVATE"), 503, "database_unavailable"),
        )
        for error, status, code in cases:
            with self.subTest(code=code), patch.object(
                service, "apply_future", side_effect=error
            ):
                response = self.client.post(
                    f"/api/plan-items/{PLAN_ITEM_ID}/apply-future", json={}
                )
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.get_json()["code"], code)
            if status != 409:
                self.assertNotIn("PRIVATE", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
