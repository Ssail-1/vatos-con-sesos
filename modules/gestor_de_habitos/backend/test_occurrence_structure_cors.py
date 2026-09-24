"""CORS mínimo para los tres comandos estructurales."""

import os
import unittest
from unittest.mock import patch

from app import app
import occurrence_structure_service as service


OCCURRENCE_ID = "00000000-0000-4000-8000-000000000101"
RESULT = {
    "status": "ok",
    "occurrenceId": OCCURRENCE_ID,
    "occurrenceStatus": "pending",
    "segmentIds": ["00000000-0000-4000-8000-000000000102"],
}


class StructureCorsTests(unittest.TestCase):
    def test_only_configured_origin_gets_structural_methods_and_preflight(self):
        origin = "http://127.0.0.1:8000"
        routes = (
            ("translate", "POST", {"startTime": "13:00", "endTime": "17:00"}),
            ("structure", "PUT", {"startTime": "13:00", "endTime": "17:00", "segments": []}),
            ("reset-segmentation", "POST", {"startTime": "13:00", "endTime": "17:00"}),
        )
        with patch.dict(os.environ, {"VCS_ALLOWED_ORIGINS": origin}), patch.object(
            service, "translate_occurrence", return_value=RESULT
        ), patch.object(
            service, "replace_occurrence_structure", return_value=RESULT
        ), patch.object(
            service, "reset_occurrence_segmentation", return_value=RESULT
        ):
            client = app.test_client()
            for suffix, method, payload in routes:
                path = f"/api/occurrences/{OCCURRENCE_ID}/{suffix}"
                with self.subTest(path=path):
                    preflight = client.options(path, headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": method,
                        "Access-Control-Request-Headers": "content-type",
                    })
                    actual = client.open(path, method=method, json=payload, headers={"Origin": origin})
                    self.assertEqual(actual.status_code, 200)
                    for response in (preflight, actual):
                        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)
                        self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), f"{method}, OPTIONS")
                        self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), "Content-Type")
                        self.assertEqual(response.headers.get("Vary"), "Origin")
                    rejected = client.options(path, headers={"Origin": "http://unapproved.invalid"})
                    self.assertNotIn("Access-Control-Allow-Origin", rejected.headers)


if __name__ == "__main__":
    unittest.main()
