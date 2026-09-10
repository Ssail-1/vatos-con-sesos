"""Pruebas sin PostgreSQL ni credenciales: unittest de la biblioteca estándar."""

import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from app import app
import database


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


if __name__ == "__main__":
    unittest.main()
