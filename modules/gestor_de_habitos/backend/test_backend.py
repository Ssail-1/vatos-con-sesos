"""Pruebas sin PostgreSQL ni credenciales: unittest de la biblioteca estándar."""

import os
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app import app
import database
from repositories import plan_item_repository


class DatabaseTests(unittest.TestCase):
    def test_missing_url_has_clear_message_without_connecting(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(database, "load_dotenv"), \
                patch.object(database.psycopg, "connect") as connect:
            with self.assertRaisesRegex(database.DatabaseConnectionError, "Falta DATABASE_URL"):
                database.check_connection()
            connect.assert_not_called()

    def test_environment_configuration_and_local_dotenv_path(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://example.invalid/test"}), \
                patch.object(database, "load_dotenv") as load:
            self.assertEqual(database.get_database_url(), "postgresql://example.invalid/test")
            load.assert_called_once_with(
                Path(database.__file__).with_name(".env"), override=False
            )

    def test_connection_uses_timeout(self):
        with patch.object(database, "get_database_url", return_value="mock-dsn"), \
                patch.object(database.psycopg, "connect") as connect:
            self.assertIs(database.get_connection(), connect.return_value)
            connect.assert_called_once_with("mock-dsn", connect_timeout=5)

    def test_connection_errors_are_sanitized(self):
        with patch.object(database, "get_database_url", return_value="mock-dsn"), \
                patch.object(database.psycopg, "connect", side_effect=psycopg.OperationalError("PRIVATE_DRIVER_DETAIL")):
            with self.assertRaises(database.DatabaseConnectionError) as error:
                database.check_connection()
            self.assertNotIn("PRIVATE_DRIVER_DETAIL", str(error.exception))

    def test_select_one_and_resource_cleanup_on_success_and_failure(self):
        for fail_query in (False, True):
            with self.subTest(fail_query=fail_query):
                connection = MagicMock()
                connection.__enter__.return_value = connection
                cursor = connection.cursor.return_value.__enter__.return_value
                cursor.fetchone.return_value = (1,)
                if fail_query:
                    cursor.execute.side_effect = psycopg.OperationalError("PRIVATE_QUERY_DETAIL")
                with patch.object(database, "get_connection", return_value=connection):
                    if fail_query:
                        with self.assertRaises(database.DatabaseConnectionError) as error:
                            database.check_connection()
                        self.assertNotIn("PRIVATE_QUERY_DETAIL", str(error.exception))
                    else:
                        database.check_connection()
                cursor.execute.assert_called_once_with("SELECT 1")
                connection.cursor.return_value.__exit__.assert_called_once()
                connection.__exit__.assert_called_once()

    def test_unexpected_query_result_is_not_healthy(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = None
        with patch.object(database, "get_connection", return_value=connection):
            with self.assertRaises(database.DatabaseConnectionError):
                database.check_connection()


class PlanItemRepositoryTests(unittest.TestCase):
    def test_list_plan_items_queries_table_in_deterministic_order(self):
        rows = [
            {
                "id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "Meditar",
                "kind": "habit",
                "subtype": "scheduled",
                "created_at": datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc),
            }
        ]
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor_context = connection.cursor.return_value
        cursor = cursor_context.__enter__.return_value
        cursor.fetchall.return_value = rows

        with patch.object(database, "get_connection", return_value=connection):
            result = plan_item_repository.list_plan_items()

        self.assertEqual(result, rows)
        connection.cursor.assert_called_once_with(row_factory=dict_row)
        query = cursor.execute.call_args.args[0]
        self.assertIn("FROM public.plan_items", query)
        self.assertIn("ORDER BY created_at, id", query)
        cursor_context.__exit__.assert_called_once()
        connection.__exit__.assert_called_once()

    def test_query_errors_are_sanitized_and_resources_are_closed(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor_context = connection.cursor.return_value
        cursor = cursor_context.__enter__.return_value
        cursor.execute.side_effect = psycopg.OperationalError("PRIVATE_QUERY_DETAIL")

        with patch.object(database, "get_connection", return_value=connection):
            with self.assertRaises(plan_item_repository.PlanItemRepositoryError) as error:
                plan_item_repository.list_plan_items()

        self.assertNotIn("PRIVATE_QUERY_DETAIL", str(error.exception))
        cursor_context.__exit__.assert_called_once()
        connection.__exit__.assert_called_once()


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_application_health_does_not_access_database(self):
        with patch.object(database, "check_connection") as check:
            response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})
        check.assert_not_called()

    def test_database_health_success(self):
        with patch.object(database, "check_connection") as check:
            response = self.client.get("/api/health/db")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "database": "ok"})
        check.assert_called_once_with()

    def test_database_failure_response_does_not_expose_exception(self):
        with patch.object(database, "check_connection", side_effect=database.DatabaseConnectionError("PRIVATE_DETAIL")):
            response = self.client.get("/api/health/db")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["database"], "unavailable")
        self.assertNotIn("PRIVATE_DETAIL", response.get_data(as_text=True))

    def test_missing_database_url_returns_controlled_json(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(database, "load_dotenv"), \
                patch.object(database.psycopg, "connect") as connect:
            response = self.client.get("/api/health/db")
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.is_json)
        connect.assert_not_called()


class PlanItemEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_plan_items_serializes_uuid_and_timestamp(self):
        plan_items = [
            {
                "id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "Meditar",
                "kind": "habit",
                "subtype": "scheduled",
                "created_at": datetime(
                    2026, 9, 10, 8, 30, 45, 123456, tzinfo=timezone.utc
                ),
            }
        ]
        with patch.object(
            plan_item_repository, "list_plan_items", return_value=plan_items
        ) as list_items:
            response = self.client.get("/api/plan-items")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "name": "Meditar",
                    "kind": "habit",
                    "subtype": "scheduled",
                    "created_at": "2026-09-10T08:30:45.123456+00:00",
                }
            ],
        )
        list_items.assert_called_once_with()

    def test_plan_items_returns_empty_list(self):
        with patch.object(
            plan_item_repository, "list_plan_items", return_value=[]
        ):
            response = self.client.get("/api/plan-items")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_database_failure_returns_controlled_json(self):
        with patch.object(
            plan_item_repository,
            "list_plan_items",
            side_effect=plan_item_repository.PlanItemRepositoryError(
                "PRIVATE_DATABASE_DETAIL"
            ),
        ):
            response = self.client.get("/api/plan-items")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {
                "status": "error",
                "message": "No se pudieron obtener los PlanItems.",
            },
        )
        self.assertNotIn("PRIVATE_DATABASE_DETAIL", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
