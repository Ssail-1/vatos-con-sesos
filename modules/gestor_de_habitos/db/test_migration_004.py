"""PostgreSQL 16 integration tests for migration 004 only.

The suite starts an isolated temporary cluster under /tmp, creates a dedicated
non-superuser database owner, and never reads DATABASE_URL or backend/.env.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import UUID

import psycopg
from psycopg import sql


MIGRATION_DIRECTORY = Path(__file__).resolve().parent / "migrations"
BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))

import database as backend_database
from app import app as backend_app
import plan_item_creation_service as backend_creation_service
import occurrence_segment_service as backend_segment_service
import occurrence_structure_service as backend_structure_service
from repositories import plan_item_repository as backend_plan_item_repository
from repositories import occurrence_segment_repository as backend_segment_repository


MIGRATIONS_001_TO_003 = (
    "001_initial_schema.sql",
    "002_fix_occurrence_status_context.sql",
    "003_multi_slot_scheduling.sql",
)
MIGRATION_004 = "004_occurrence_segments.sql"

POSTGRESQL_BIN = Path("/usr/lib/postgresql/16/bin")
INITDB = POSTGRESQL_BIN / "initdb"
PG_CTL = POSTGRESQL_BIN / "pg_ctl"

ADMIN_ROLE = "vcs_segment_test_admin"
MIGRATION_ROLE = "vcs_segment_migration_test"

STATUS_VALUES = {
    "pending",
    "in_progress",
    "completed",
    "not_completed",
    "not_finished",
    "cancelled",
}


def generation_slot_id(number):
    return f"00000000-0000-4000-8000-{number:012d}"


def manual_creation_payload(entries, *, name="Segment creation", subtype="periodic"):
    return {
        "name": name,
        "kind": "activity",
        "activityType": subtype,
        "generationConfig": {
            "mode": "manual_dates",
            "entries": [
                {"id": generation_slot_id(index), **entry}
                for index, entry in enumerate(entries, start=700)
            ],
        },
    }


def migration_sql(name):
    return (MIGRATION_DIRECTORY / name).read_text(encoding="utf-8")


class OccurrenceSegmentMigrationHarness(unittest.TestCase):
    """Infraestructura compartida de PostgreSQL 16 efímero para schema 004."""

    @classmethod
    def setUpClass(cls):
        missing = [path for path in (INITDB, PG_CTL) if not path.is_file()]
        if missing:
            raise unittest.SkipTest(
                "PostgreSQL 16 server binaries are unavailable: "
                + ", ".join(str(path) for path in missing)
            )

        cls._temporary_directory = tempfile.TemporaryDirectory(
            prefix="vcs-occurrence-segments-pg16-",
            dir="/tmp",
        )
        cls._temporary_path = Path(cls._temporary_directory.name)
        cls._data_directory = cls._temporary_path / "data"
        cls._socket_directory = cls._temporary_path / "socket"
        cls._socket_directory.mkdir()
        cls._server_log = cls._temporary_path / "postgresql.log"
        # The cluster listens only on its private Unix socket. Reusing the
        # conventional port is safe because socket_directory is unique.
        cls._port = 5432
        cls._database_counter = 0

        subprocess.run(
            [
                str(INITDB),
                "-D",
                str(cls._data_directory),
                "--auth=trust",
                "--encoding=UTF8",
                "--no-locale",
                f"--username={ADMIN_ROLE}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        server_options = " ".join(
            (
                "-F",
                f"-p {cls._port}",
                f"-k {cls._socket_directory}",
                "-h ''",
            )
        )
        try:
            subprocess.run(
                [
                    str(PG_CTL),
                    "-D",
                    str(cls._data_directory),
                    "-l",
                    str(cls._server_log),
                    "-o",
                    server_options,
                    "-w",
                    "start",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            server_log = cls._server_log.read_text(encoding="utf-8") if cls._server_log.exists() else ""
            cls._temporary_directory.cleanup()
            raise RuntimeError(
                f"PostgreSQL 16 isolated startup failed: {error.stderr}\n{server_log}"
            ) from error

        cls._admin_dsn = cls._dsn("postgres", ADMIN_ROLE)
        try:
            with psycopg.connect(cls._admin_dsn, autocommit=True) as connection:
                version_number = int(
                    connection.execute(
                        "SELECT current_setting('server_version_num')"
                    ).fetchone()[0]
                )
                if not 160000 <= version_number < 170000:
                    raise RuntimeError(
                        f"Expected PostgreSQL 16, found server_version_num={version_number}."
                    )
                connection.execute(
                    sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER").format(
                        sql.Identifier(MIGRATION_ROLE)
                    )
                )
        except Exception:
            cls._stop_cluster()
            cls._temporary_directory.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls._stop_cluster()
        cls._temporary_directory.cleanup()

    @classmethod
    def _dsn(cls, database_name, role):
        return (
            f"host={cls._socket_directory} "
            f"port={cls._port} "
            f"dbname={database_name} "
            f"user={role}"
        )

    @classmethod
    def _stop_cluster(cls):
        if not getattr(cls, "_data_directory", None):
            return
        subprocess.run(
            [
                str(PG_CTL),
                "-D",
                str(cls._data_directory),
                "-m",
                "immediate",
                "-w",
                "stop",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def _create_database(self):
        type(self)._database_counter += 1
        database_name = (
            "vcs_test_occurrence_segments_"
            f"{type(self)._database_counter}"
        )
        with psycopg.connect(self._admin_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(database_name),
                    sql.Identifier(MIGRATION_ROLE),
                )
            )
        self.addCleanup(self._drop_database, database_name)
        return self._dsn(database_name, MIGRATION_ROLE)

    def _drop_database(self, database_name):
        with psycopg.connect(self._admin_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(database_name)
                )
            )

    def _apply(self, connection, migration_names):
        for migration_name in migration_names:
            connection.execute(migration_sql(migration_name))

    def _apply_001_to_003(self, connection):
        self._apply(connection, MIGRATIONS_001_TO_003)

    def _apply_001_to_004(self, connection):
        self._apply(connection, (*MIGRATIONS_001_TO_003, MIGRATION_004))

    @staticmethod
    def _insert_plan_item(connection, plan_item_id):
        connection.execute(
            """
            INSERT INTO public.plan_items (id, name, kind, subtype)
            VALUES (%s, 'Migration fixture', 'activity', 'periodic')
            """,
            (plan_item_id,),
        )

    @staticmethod
    def _insert_occurrence(
        connection,
        occurrence_id,
        plan_item_id,
        *,
        day="2026-09-20",
        start_time="08:00",
        end_time="09:00",
        status="pending",
        conflict_reason=None,
        source_occurrence_id=None,
        origin_reason=None,
        last_conflict_action=None,
    ):
        connection.execute(
            """
            INSERT INTO public.occurrences (
                id,
                plan_item_id,
                occurrence_date,
                start_time,
                end_time,
                status,
                conflict_reason,
                source_occurrence_id,
                origin_reason,
                last_conflict_action
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                occurrence_id,
                plan_item_id,
                day,
                start_time,
                end_time,
                status,
                conflict_reason,
                source_occurrence_id,
                origin_reason,
                last_conflict_action,
            ),
        )

    @staticmethod
    def _insert_manual_config(connection, plan_item_id, entries):
        connection.execute(
            """
            INSERT INTO public.generation_configs (
                plan_item_id,
                mode,
                start_date,
                end_date,
                indefinite,
                interval_days,
                stopped_from_date
            )
            VALUES (%s, 'manual_dates', NULL, NULL, FALSE, NULL, NULL)
            """,
            (plan_item_id,),
        )
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO public.generation_slots (
                    id, plan_item_id, start_time, end_time
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    (slot_id, plan_item_id, start_time, end_time)
                    for slot_id, _, start_time, end_time in entries
                ),
            )
            cursor.executemany(
                """
                INSERT INTO public.generation_slot_dates (slot_id, entry_date)
                VALUES (%s, %s)
                """,
                ((slot_id, day) for slot_id, day, _, _ in entries),
            )

class OccurrenceSegmentMigrationTests(OccurrenceSegmentMigrationHarness):
    """Exercise 001 → 004 against a real disposable PostgreSQL 16 cluster."""

    def test_empty_database_applies_001_through_004_with_btree_gist(self):
        database_url = self._create_database()

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_003(connection)

            self.assertFalse(
                connection.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto')"
                ).fetchone()[0]
            )
            generated_uuid = connection.execute("SELECT gen_random_uuid()").fetchone()[0]
            self.assertIsInstance(generated_uuid, UUID)
            self.assertEqual(generated_uuid.version, 4)

            available_btree_gist = connection.execute(
                """
                SELECT default_version IS NOT NULL
                FROM pg_available_extensions
                WHERE name = 'btree_gist'
                """
            ).fetchone()
            self.assertEqual(available_btree_gist, (True,))

            self._apply(connection, (MIGRATION_004,))

            self.assertFalse(
                connection.execute(
                    "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
                ).fetchone()[0]
            )
            self.assertEqual(
                connection.execute(
                    """
                    SELECT extowner::regrole::text
                    FROM pg_extension
                    WHERE extname = 'btree_gist'
                    """
                ).fetchone()[0],
                MIGRATION_ROLE,
            )
            self.assertTrue(
                connection.execute(
                    "SELECT to_regclass('public.occurrence_segments') IS NOT NULL"
                ).fetchone()[0]
            )

            columns = {
                row[0]: (row[1], row[2])
                for row in connection.execute(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                        AND table_name = 'occurrences'
                        AND column_name IN (
                            'status_reason',
                            'conflict_reason',
                            'origin_reason',
                            'last_conflict_action'
                        )
                    """
                ).fetchall()
            }
            self.assertNotIn("status_reason", columns)
            self.assertEqual(columns["conflict_reason"], ("character varying", "YES"))
            self.assertEqual(columns["origin_reason"], ("character varying", "YES"))
            self.assertEqual(
                columns["last_conflict_action"],
                ("character varying", "YES"),
            )

            segment_columns = {
                row[0]: (row[1], row[2])
                for row in connection.execute(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                        AND table_name = 'occurrence_segments'
                    """
                ).fetchall()
            }
            self.assertEqual(
                segment_columns,
                {
                    "id": ("uuid", "NO"),
                    "occurrence_id": ("uuid", "NO"),
                    "start_time": ("time without time zone", "NO"),
                    "end_time": ("time without time zone", "NO"),
                    "status": ("character varying", "NO"),
                },
            )

            exclusion = connection.execute(
                """
                SELECT condeferrable, condeferred, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname = 'excl_occurrence_segments_sibling_overlap'
                """
            ).fetchone()
            self.assertEqual(exclusion[:2], (True, True))
            self.assertIn("EXCLUDE USING gist", exclusion[2])
            self.assertIn("'[)'::text", exclusion[2])

            constraint_names = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE conrelid IN (
                        'public.occurrences'::regclass,
                        'public.occurrence_segments'::regclass
                    )
                    """
                ).fetchall()
            }
            self.assertFalse(
                {
                    "chk_occurrence_status_context",
                    "chk_occurrence_override_status",
                }
                & constraint_names
            )
            self.assertTrue(
                {
                    "chk_occurrence_conflict_reason",
                    "chk_occurrence_conflict_context",
                    "chk_occurrence_origin_reason",
                    "chk_occurrence_last_conflict_action",
                    "occurrence_segments_pkey",
                    "chk_occurrence_segment_time_range",
                    "chk_occurrence_segment_status",
                    "fk_occurrence_segments_occurrence",
                    "excl_occurrence_segments_sibling_overlap",
                }
                <= constraint_names
            )

            index_definition = connection.execute(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                    AND indexname = 'idx_occurrence_segments_occurrence_time'
                """
            ).fetchone()[0]
            self.assertIn(
                "(occurrence_id, start_time, end_time, id)",
                index_definition,
            )

    def test_populated_legacy_database_backfills_one_exact_segment_each(self):
        database_url = self._create_database()
        plan_item_id = UUID("00000000-0000-4000-8000-000000000001")
        generation_slot_id = UUID("00000000-0000-4000-8000-000000000002")
        occurrence_ids = [UUID(int=100 + index) for index in range(6)]
        statuses = (
            "pending",
            "in_progress",
            "completed",
            "not_completed",
            "not_finished",
            "cancelled",
        )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_003(connection)
            self._insert_plan_item(connection, plan_item_id)
            connection.execute(
                """
                INSERT INTO public.generation_configs (
                    plan_item_id,
                    mode,
                    start_date,
                    end_date,
                    indefinite,
                    interval_days,
                    stopped_from_date
                )
                VALUES (%s, 'weekly', '2026-09-20', NULL, TRUE, NULL, NULL)
                """,
                (plan_item_id,),
            )
            connection.execute(
                """
                INSERT INTO public.generation_slots (
                    id, plan_item_id, start_time, end_time
                )
                VALUES (%s, %s, '08:00', '09:00')
                """,
                (generation_slot_id, plan_item_id),
            )

            for index, (occurrence_id, status) in enumerate(
                zip(occurrence_ids, statuses, strict=True)
            ):
                connection.execute(
                    """
                    INSERT INTO public.occurrences (
                        id,
                        plan_item_id,
                        occurrence_date,
                        start_time,
                        end_time,
                        status,
                        status_reason,
                        source_occurrence_id,
                        source_generation_slot_id
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        occurrence_id,
                        plan_item_id,
                        f"2026-09-{20 + index:02d}",
                        f"{8 + index:02d}:00",
                        f"{9 + index:02d}:00",
                        status,
                        "priority_override" if status == "cancelled" else None,
                        occurrence_ids[0] if status == "cancelled" else None,
                        generation_slot_id if index == 0 else None,
                    ),
                )

            self._apply(connection, (MIGRATION_004,))

            occurrence_count, segment_count = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM public.occurrences),
                    (SELECT COUNT(*) FROM public.occurrence_segments)
                """
            ).fetchone()
            self.assertEqual((occurrence_count, segment_count), (6, 6))

            backfill_rows = connection.execute(
                """
                SELECT
                    occurrences.id,
                    occurrences.start_time,
                    occurrences.end_time,
                    occurrences.status,
                    occurrences.conflict_reason,
                    occurrences.source_occurrence_id,
                    occurrences.source_generation_slot_id,
                    occurrences.origin_reason,
                    occurrences.last_conflict_action,
                    segments.id,
                    segments.start_time,
                    segments.end_time,
                    segments.status
                FROM public.occurrences AS occurrences
                JOIN public.occurrence_segments AS segments
                    ON segments.occurrence_id = occurrences.id
                ORDER BY occurrences.id
                """
            ).fetchall()

            self.assertEqual(len(backfill_rows), 6)
            self.assertEqual({row[3] for row in backfill_rows}, STATUS_VALUES)
            self.assertEqual({row[12] for row in backfill_rows}, STATUS_VALUES)
            self.assertEqual(len({row[9] for row in backfill_rows}), 6)
            self.assertTrue(all(row[9] not in occurrence_ids for row in backfill_rows))
            self.assertTrue(
                all(
                    (row[1], row[2], row[3]) == (row[10], row[11], row[12])
                    for row in backfill_rows
                )
            )
            self.assertTrue(all(row[7] is None for row in backfill_rows))
            self.assertTrue(all(row[8] is None for row in backfill_rows))

            overridden = next(row for row in backfill_rows if row[3] == "cancelled")
            self.assertEqual(overridden[4], "priority_override")
            self.assertEqual(overridden[5], occurrence_ids[0])

            with_provenance = next(
                row for row in backfill_rows if row[0] == occurrence_ids[0]
            )
            self.assertEqual(with_provenance[6], generation_slot_id)
            self.assertTrue(
                all(
                    row[6] is None
                    for row in backfill_rows
                    if row[0] != occurrence_ids[0]
                )
            )

            self.assertEqual(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.occurrence_segments AS segments
                    LEFT JOIN public.occurrences AS occurrences
                        ON occurrences.id = segments.occurrence_id
                    WHERE occurrences.id IS NULL
                    """
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.occurrences AS occurrences
                    LEFT JOIN public.occurrence_segments AS segments
                        ON segments.occurrence_id = occurrences.id
                    WHERE segments.id IS NULL
                    """
                ).fetchone()[0],
                0,
            )

    def test_local_constraints_overlap_and_cascade(self):
        database_url = self._create_database()
        plan_item_id = UUID(int=200)
        first_occurrence_id = UUID(int=201)
        second_occurrence_id = UUID(int=202)

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            self._insert_plan_item(connection, plan_item_id)
            self._insert_occurrence(connection, first_occurrence_id, plan_item_id)
            self._insert_occurrence(connection, second_occurrence_id, plan_item_id)

        invalid_segments = (
            (UUID(int=210), first_occurrence_id, "10:00", "10:00", "pending"),
            (UUID(int=211), first_occurrence_id, "11:00", "10:00", "pending"),
            (UUID(int=212), first_occurrence_id, "10:00", "11:00", "unknown"),
            (UUID(int=213), UUID(int=999), "10:00", "11:00", "pending"),
        )
        expected_errors = (
            psycopg.errors.CheckViolation,
            psycopg.errors.CheckViolation,
            psycopg.errors.CheckViolation,
            psycopg.errors.ForeignKeyViolation,
        )
        for segment, expected_error in zip(
            invalid_segments,
            expected_errors,
            strict=True,
        ):
            with self.subTest(segment=segment):
                with self.assertRaises(expected_error):
                    with psycopg.connect(database_url) as connection:
                        connection.execute(
                            """
                            INSERT INTO public.occurrence_segments (
                                id, occurrence_id, start_time, end_time, status
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            segment,
                        )

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO public.occurrence_segments (
                        id, occurrence_id, start_time, end_time, status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        (UUID(int=220), first_occurrence_id, "13:00", "14:00", "pending"),
                        (UUID(int=221), first_occurrence_id, "14:00", "15:00", "completed"),
                        (UUID(int=222), second_occurrence_id, "13:30", "14:30", "pending"),
                    ),
                )

        # A deferred constraint permits a temporarily overlapping statement
        # order when the complete transaction finishes with valid siblings.
        with psycopg.connect(database_url) as connection:
            connection.execute(
                """
                UPDATE public.occurrence_segments
                SET start_time = '14:00', end_time = '15:00'
                WHERE id = %s
                """,
                (UUID(int=220),),
            )
            connection.execute(
                """
                UPDATE public.occurrence_segments
                SET start_time = '13:00', end_time = '14:00'
                WHERE id = %s
                """,
                (UUID(int=221),),
            )

        overlap_connection = psycopg.connect(database_url)
        try:
            with self.assertRaises(psycopg.errors.ExclusionViolation):
                overlap_connection.execute(
                    """
                    INSERT INTO public.occurrence_segments (
                        id, occurrence_id, start_time, end_time, status
                    )
                    VALUES (%s, %s, '13:30', '14:30', 'pending')
                    """,
                    (UUID(int=223), first_occurrence_id),
                )
                # The exclusion constraint is INITIALLY DEFERRED, so the
                # violation is intentionally observed at transaction commit.
                overlap_connection.commit()
        finally:
            overlap_connection.close()

        with self.assertRaises(psycopg.errors.UniqueViolation):
            with psycopg.connect(database_url) as connection:
                connection.execute(
                    """
                    INSERT INTO public.occurrence_segments (
                        id, occurrence_id, start_time, end_time, status
                    )
                    VALUES (%s, %s, '16:00', '17:00', 'pending')
                    """,
                    (UUID(int=220), second_occurrence_id),
                )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self.assertEqual(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.occurrence_segments
                    WHERE occurrence_id = %s
                    """,
                    (first_occurrence_id,),
                ).fetchone()[0],
                2,
            )
            connection.execute(
                "DELETE FROM public.occurrences WHERE id = %s",
                (first_occurrence_id,),
            )
            self.assertEqual(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.occurrence_segments
                    WHERE occurrence_id = %s
                    """,
                    (first_occurrence_id,),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.occurrence_segments
                    WHERE occurrence_id = %s
                    """,
                    (second_occurrence_id,),
                ).fetchone()[0],
                1,
            )

    def test_metadata_constraints_and_source_no_action(self):
        database_url = self._create_database()
        plan_item_id = UUID(int=300)
        source_occurrence_id = UUID(int=301)
        target_occurrence_id = UUID(int=302)

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            self._insert_plan_item(connection, plan_item_id)
            self._insert_occurrence(connection, source_occurrence_id, plan_item_id)
            self._insert_occurrence(
                connection,
                target_occurrence_id,
                plan_item_id,
                status="pending",
                conflict_reason="user_forced_override",
                source_occurrence_id=source_occurrence_id,
                origin_reason="conflict_insertion",
                last_conflict_action="conflict_move",
            )

            foreign_key_delete_action = connection.execute(
                """
                SELECT confdeltype
                FROM pg_constraint
                WHERE conname = 'fk_occurrence_source'
                """
            ).fetchone()[0]
            self.assertEqual(foreign_key_delete_action, "a")

        invalid_occurrences = (
            {
                "occurrence_id": UUID(int=310),
                "conflict_reason": "invalid_reason",
                "source_occurrence_id": source_occurrence_id,
            },
            {
                "occurrence_id": UUID(int=311),
                "conflict_reason": "priority_override",
                "source_occurrence_id": None,
            },
            {
                "occurrence_id": UUID(int=312),
                "conflict_reason": None,
                "source_occurrence_id": source_occurrence_id,
            },
            {
                "occurrence_id": UUID(int=313),
                "origin_reason": "normal_creation",
            },
            {
                "occurrence_id": UUID(int=314),
                "last_conflict_action": "conflict_resize",
            },
            {
                "occurrence_id": UUID(int=315),
                "conflict_reason": "priority_override",
                "source_occurrence_id": UUID(int=315),
            },
        )
        for fixture in invalid_occurrences:
            with self.subTest(fixture=fixture):
                with self.assertRaises(psycopg.errors.CheckViolation):
                    with psycopg.connect(database_url) as connection:
                        occurrence_id = fixture["occurrence_id"]
                        self._insert_occurrence(
                            connection,
                            occurrence_id,
                            plan_item_id,
                            **{
                                key: value
                                for key, value in fixture.items()
                                if key != "occurrence_id"
                            },
                        )

        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with psycopg.connect(database_url) as connection:
                connection.execute(
                    "DELETE FROM public.occurrences WHERE id = %s",
                    (source_occurrence_id,),
                )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.occurrences"
                ).fetchone()[0],
                2,
            )

    def test_backend_planner_state_reads_schema_004_graph(self):
        database_url = self._create_database()
        plan_item_id = UUID(int=400)
        generation_slot_id = UUID("00000000-0000-4000-8000-000000000401")
        segmented_generation_slot_id = UUID(
            "00000000-0000-4000-8000-000000000405"
        )
        source_occurrence_id = UUID(int=402)
        priority_occurrence_id = UUID(int=403)
        segmented_occurrence_id = UUID(int=404)

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            self._insert_plan_item(connection, plan_item_id)
            connection.execute(
                """
                INSERT INTO public.generation_configs (
                    plan_item_id,
                    mode,
                    start_date,
                    end_date,
                    indefinite,
                    interval_days,
                    stopped_from_date
                )
                VALUES (%s, 'manual_dates', NULL, NULL, FALSE, NULL, NULL)
                """,
                (plan_item_id,),
            )
            connection.execute(
                """
                INSERT INTO public.generation_slots (
                    id, plan_item_id, start_time, end_time
                )
                VALUES
                    (%s, %s, '08:00', '10:00'),
                    (%s, %s, '13:00', '17:00')
                """,
                (
                    generation_slot_id,
                    plan_item_id,
                    segmented_generation_slot_id,
                    plan_item_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO public.generation_slot_dates (slot_id, entry_date)
                VALUES
                    (%s, '2026-09-20'),
                    (%s, '2026-09-20')
                """,
                (generation_slot_id, segmented_generation_slot_id),
            )
            self._insert_occurrence(
                connection,
                source_occurrence_id,
                plan_item_id,
                start_time="08:00",
                end_time="10:00",
            )
            connection.execute(
                """
                UPDATE public.occurrences
                SET source_generation_slot_id = %s
                WHERE id = %s
                """,
                (generation_slot_id, source_occurrence_id),
            )
            self._insert_occurrence(
                connection,
                priority_occurrence_id,
                plan_item_id,
                start_time="10:30",
                end_time="11:30",
                status="completed",
                conflict_reason="priority_override",
                source_occurrence_id=source_occurrence_id,
                origin_reason="conflict_insertion",
                last_conflict_action="conflict_insertion",
            )
            self._insert_occurrence(
                connection,
                segmented_occurrence_id,
                plan_item_id,
                start_time="13:00",
                end_time="17:00",
                status="in_progress",
                conflict_reason="user_forced_override",
                source_occurrence_id=source_occurrence_id,
                origin_reason="conflict_insertion",
                last_conflict_action="conflict_move",
            )
            connection.execute(
                """
                UPDATE public.occurrences
                SET source_generation_slot_id = %s
                WHERE id = %s
                """,
                (segmented_generation_slot_id, segmented_occurrence_id),
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO public.occurrence_segments (
                        id, occurrence_id, start_time, end_time, status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        (
                            UUID(int=410),
                            source_occurrence_id,
                            "08:00",
                            "10:00",
                            "pending",
                        ),
                        (
                            UUID(int=411),
                            priority_occurrence_id,
                            "10:30",
                            "11:30",
                            "completed",
                        ),
                        (
                            UUID(int=413),
                            segmented_occurrence_id,
                            "14:30",
                            "17:00",
                            "pending",
                        ),
                        (
                            UUID(int=412),
                            segmented_occurrence_id,
                            "13:00",
                            "14:00",
                            "completed",
                        ),
                    ),
                )

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ):
            response = backend_app.test_client().get("/api/planner-state")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        state = response.get_json()

        occurrences = {item["id"]: item for item in state["occurrences"]}
        source = occurrences[str(source_occurrence_id)]
        self.assertEqual(source["sourceGenerationSlotId"], str(generation_slot_id))
        self.assertNotIn("originReason", source)
        self.assertNotIn("lastConflictAction", source)
        self.assertEqual(
            source["segments"],
            [
                {
                    "id": str(UUID(int=410)),
                    "startTime": "08:00",
                    "endTime": "10:00",
                    "status": "pending",
                }
            ],
        )

        priority = occurrences[str(priority_occurrence_id)]
        self.assertEqual(priority["status"], "completed")
        self.assertEqual(
            priority["conflictContext"],
            {
                "reason": "priority_override",
                "sourceOccurrenceId": str(source_occurrence_id),
            },
        )
        self.assertEqual(priority["statusContext"], priority["conflictContext"])
        self.assertEqual(priority["originReason"], "conflict_insertion")
        self.assertEqual(priority["lastConflictAction"], "conflict_insertion")

        segmented = occurrences[str(segmented_occurrence_id)]
        self.assertEqual(
            segmented["sourceGenerationSlotId"],
            str(segmented_generation_slot_id),
        )
        self.assertEqual(
            segmented["conflictContext"],
            {
                "reason": "user_forced_override",
                "sourceOccurrenceId": str(source_occurrence_id),
            },
        )
        self.assertNotIn("statusContext", segmented)
        self.assertEqual(segmented["originReason"], "conflict_insertion")
        self.assertEqual(segmented["lastConflictAction"], "conflict_move")
        self.assertEqual(
            segmented["segments"],
            [
                {
                    "id": str(UUID(int=412)),
                    "startTime": "13:00",
                    "endTime": "14:00",
                    "status": "completed",
                },
                {
                    "id": str(UUID(int=413)),
                    "startTime": "14:30",
                    "endTime": "17:00",
                    "status": "pending",
                },
            ],
        )

    def test_backend_creation_round_trip_persists_stable_default_segments(self):
        database_url = self._create_database()
        payload = manual_creation_payload(
            [
                {"date": "2026-09-20", "startTime": "08:00", "endTime": "09:00"},
                {"date": "2026-09-20", "startTime": "10:00", "endTime": "11:00"},
                {"date": "2026-09-21", "startTime": "14:00", "endTime": "15:00"},
            ]
        )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_creation_service, "_today", return_value=date(2026, 9, 20)
        ):
            client = backend_app.test_client()
            created_response = client.post("/api/plan-items", json=payload)
            first_state_response = client.get("/api/planner-state")
            second_state_response = client.get("/api/planner-state")

        self.assertEqual(
            created_response.status_code,
            201,
            created_response.get_data(as_text=True),
        )
        self.assertEqual(first_state_response.status_code, 200)
        self.assertEqual(second_state_response.status_code, 200)
        created = created_response.get_json()
        self.assertEqual(len(created["occurrences"]), 3)
        for occurrence in created["occurrences"]:
            self.assertEqual(len(occurrence["segments"]), 1)
            segment = occurrence["segments"][0]
            self.assertEqual(segment["occurrenceId"], occurrence["id"])
            self.assertEqual(UUID(segment["id"]).version, 4)

        first_occurrences = first_state_response.get_json()["occurrences"]
        second_occurrences = second_state_response.get_json()["occurrences"]
        first_segments = {
            occurrence["id"]: occurrence["segments"]
            for occurrence in first_occurrences
        }
        second_segments = {
            occurrence["id"]: occurrence["segments"]
            for occurrence in second_occurrences
        }
        self.assertEqual(first_segments, second_segments)
        self.assertEqual(len(first_segments), 3)
        segment_ids = set()
        for occurrence in first_occurrences:
            self.assertEqual(len(occurrence["segments"]), 1)
            segment = occurrence["segments"][0]
            self.assertEqual(segment["startTime"], occurrence["startTime"])
            self.assertEqual(segment["endTime"], occurrence["endTime"])
            self.assertEqual(segment["status"], occurrence["status"])
            segment_ids.add(segment["id"])
        self.assertEqual(len(segment_ids), 3)

        with psycopg.connect(database_url) as connection:
            persisted = connection.execute(
                """
                SELECT
                    occurrence.id,
                    occurrence.source_generation_slot_id,
                    occurrence.start_time,
                    occurrence.end_time,
                    segment.id,
                    segment.occurrence_id,
                    segment.start_time,
                    segment.end_time,
                    segment.status,
                    occurrence.status
                FROM public.occurrences AS occurrence
                INNER JOIN public.occurrence_segments AS segment
                    ON segment.occurrence_id = occurrence.id
                ORDER BY occurrence.occurrence_date, occurrence.start_time
                """
            ).fetchall()
            metadata = connection.execute(
                """
                SELECT
                    conflict_reason,
                    source_occurrence_id,
                    origin_reason,
                    last_conflict_action
                FROM public.occurrences
                """
            ).fetchall()
        self.assertEqual(len(persisted), 3)
        self.assertEqual(len({row[4] for row in persisted}), 3)
        self.assertTrue(all(row[0] == row[5] for row in persisted))
        self.assertTrue(
            all(
                row[2] == row[6] and row[3] == row[7] and row[8] == row[9]
                for row in persisted
            )
        )
        self.assertEqual(
            {str(row[1]) for row in persisted},
            {entry["id"] for entry in payload["generationConfig"]["entries"]},
        )
        self.assertTrue(all(row == (None, None, None, None) for row in metadata))

    def test_backend_creation_rolls_back_if_default_segment_insert_fails(self):
        database_url = self._create_database()
        payload = manual_creation_payload(
            [{"date": "2026-09-20", "startTime": "08:00", "endTime": "09:00"}]
        )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            connection.execute(
                """
                CREATE FUNCTION public.reject_default_segment()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $$
                BEGIN
                    RAISE EXCEPTION 'intentional segment failure';
                END
                $$
                """
            )
            connection.execute(
                """
                CREATE TRIGGER reject_default_segment
                BEFORE INSERT ON public.occurrence_segments
                FOR EACH ROW
                EXECUTE FUNCTION public.reject_default_segment()
                """
            )

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_creation_service, "_today", return_value=date(2026, 9, 20)
        ):
            response = backend_app.test_client().post("/api/plan-items", json=payload)

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("intentional segment failure", response.get_data(as_text=True))
        with psycopg.connect(database_url) as connection:
            counts = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM public.plan_items),
                    (SELECT COUNT(*) FROM public.generation_configs),
                    (SELECT COUNT(*) FROM public.generation_slots),
                    (SELECT COUNT(*) FROM public.occurrences),
                    (SELECT COUNT(*) FROM public.occurrence_segments)
                """
            ).fetchone()
        self.assertEqual(counts, (0, 0, 0, 0, 0))

    def test_schema_004_blocking_policy_and_legacy_override_guard(self):
        database_url = self._create_database()
        payload = manual_creation_payload(
            [
                {"date": "2026-09-20", "startTime": "08:00", "endTime": "09:00"},
                {"date": "2026-09-20", "startTime": "10:00", "endTime": "11:00"},
                {"date": "2026-09-20", "startTime": "12:00", "endTime": "13:00"},
            ],
            name="Blocking statuses",
        )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_creation_service, "_today", return_value=date(2026, 9, 20)
        ):
            client = backend_app.test_client()
            created_response = client.post("/api/plan-items", json=payload)
        self.assertEqual(created_response.status_code, 201)
        created_occurrences = created_response.get_json()["occurrences"]

        target_statuses = ("not_finished", "not_completed", "cancelled")
        with psycopg.connect(database_url) as connection:
            for occurrence, status in zip(created_occurrences, target_statuses):
                connection.execute(
                    "UPDATE public.occurrences SET status = %s WHERE id = %s",
                    (status, occurrence["id"]),
                )
                connection.execute(
                    "UPDATE public.occurrence_segments SET status = %s WHERE occurrence_id = %s",
                    (status, occurrence["id"]),
                )
            blocking_rows = backend_plan_item_repository.list_blocking_occurrences(
                connection, ["2026-09-20"]
            )
        self.assertEqual(
            [(str(row["id"]), row["status"]) for row in blocking_rows],
            [(created_occurrences[0]["id"], "not_finished")],
        )

        event_payload = manual_creation_payload(
            [{"date": "2026-09-20", "startTime": "08:30", "endTime": "09:30"}],
            name="Guarded event",
            subtype="event",
        )
        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_creation_service, "_today", return_value=date(2026, 9, 20)
        ):
            client = backend_app.test_client()
            first = client.post("/api/plan-items", json=event_payload)
            confirmed = client.post(
                "/api/plan-items",
                json={
                    **event_payload,
                    "priorityOverride": {
                        "confirmedOccurrenceIds": [created_occurrences[0]["id"]]
                    },
                },
            )
        self.assertEqual(first.status_code, 409)
        first_body = first.get_json()
        confirmed_body = confirmed.get_json()
        expected_conflicts = [
            {
                "occurrenceId": created_occurrences[0]["id"],
                "planItemId": created_response.get_json()["planItem"]["id"],
                "date": "2026-09-20",
                "startTime": "08:00",
                "endTime": "09:00",
                "status": "not_finished",
            }
        ]
        self.assertEqual(first_body["code"], "priority_override_required")
        self.assertEqual(first_body["conflicts"], expected_conflicts)
        self.assertEqual(confirmed.status_code, 409)
        self.assertEqual(
            confirmed_body["code"],
            "segment_conflict_resolution_unavailable",
        )
        self.assertEqual(confirmed_body["conflicts"], expected_conflicts)

        with psycopg.connect(database_url) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM public.plan_items WHERE name = 'Guarded event'"
                ).fetchone()[0],
                0,
            )
            blocker = connection.execute(
                """
                SELECT occurrence.status, occurrence.conflict_reason,
                       segment.status
                FROM public.occurrences AS occurrence
                INNER JOIN public.occurrence_segments AS segment
                    ON segment.occurrence_id = occurrence.id
                WHERE occurrence.id = %s
                """,
                (created_occurrences[0]["id"],),
            ).fetchone()
        self.assertEqual(blocker, ("not_finished", None, "not_finished"))

    def test_segment_status_endpoint_round_trip_preserves_structure_and_metadata(self):
        database_url = self._create_database()
        payload = manual_creation_payload(
            [
                {
                    "date": "2026-09-20",
                    "startTime": "08:00",
                    "endTime": "12:00",
                }
            ],
            name="Segment status round trip",
        )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_creation_service, "_today", return_value=date(2026, 9, 20)
        ):
            client = backend_app.test_client()
            created_response = client.post("/api/plan-items", json=payload)
        self.assertEqual(created_response.status_code, 201)
        plan_item_id = UUID(created_response.get_json()["planItem"]["id"])
        created_occurrence = created_response.get_json()["occurrences"][0]
        occurrence_id = UUID(created_occurrence["id"])
        first_segment_id = UUID(int=810)
        second_segment_id = UUID(int=811)
        source_occurrence_id = UUID(int=812)
        source_segment_id = UUID(int=813)

        with psycopg.connect(database_url) as connection:
            self._insert_occurrence(
                connection,
                source_occurrence_id,
                plan_item_id,
                start_time="06:00",
                end_time="07:00",
                status="completed",
            )
            connection.execute(
                """
                INSERT INTO public.occurrence_segments (
                    id, occurrence_id, start_time, end_time, status
                ) VALUES (%s, %s, '06:00', '07:00', 'completed')
                """,
                (source_segment_id, source_occurrence_id),
            )
            connection.execute(
                "DELETE FROM public.occurrence_segments WHERE occurrence_id = %s",
                (occurrence_id,),
            )
            connection.execute(
                """
                UPDATE public.occurrences
                SET conflict_reason = 'user_forced_override',
                    source_occurrence_id = %s,
                    origin_reason = 'conflict_insertion',
                    last_conflict_action = 'conflict_move'
                WHERE id = %s
                """,
                (source_occurrence_id, occurrence_id),
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO public.occurrence_segments (
                        id, occurrence_id, start_time, end_time, status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        (first_segment_id, occurrence_id, "08:00", "10:00", "pending"),
                        (second_segment_id, occurrence_id, "10:00", "12:00", "pending"),
                    ),
                )

        fixed_now = datetime(2026, 9, 20, 12, 0)
        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(backend_segment_service, "_now", return_value=fixed_now):
            client = backend_app.test_client()
            mutation = client.patch(
                f"/api/occurrence-segments/{first_segment_id}/status",
                json={"status": "completed"},
            )
            first_state = client.get("/api/planner-state")
            second_state = client.get("/api/planner-state")

        self.assertEqual(mutation.status_code, 200, mutation.get_data(as_text=True))
        self.assertEqual(
            mutation.get_json(),
            {
                "status": "ok",
                "occurrenceId": str(occurrence_id),
                "segmentId": str(first_segment_id),
                "segmentStatus": "completed",
                "occurrenceStatus": "in_progress",
            },
        )
        self.assertEqual(first_state.status_code, 200)
        self.assertEqual(second_state.status_code, 200)
        first_occurrence = next(
            occurrence
            for occurrence in first_state.get_json()["occurrences"]
            if occurrence["id"] == str(occurrence_id)
        )
        second_occurrence = next(
            occurrence
            for occurrence in second_state.get_json()["occurrences"]
            if occurrence["id"] == str(occurrence_id)
        )
        self.assertEqual(first_occurrence, second_occurrence)
        self.assertEqual(first_occurrence["status"], "in_progress")
        self.assertEqual(first_occurrence["startTime"], "08:00")
        self.assertEqual(first_occurrence["endTime"], "12:00")
        self.assertEqual(first_occurrence["originReason"], "conflict_insertion")
        self.assertEqual(first_occurrence["lastConflictAction"], "conflict_move")
        self.assertEqual(
            first_occurrence["conflictContext"],
            {
                "reason": "user_forced_override",
                "sourceOccurrenceId": str(source_occurrence_id),
            },
        )
        self.assertEqual(
            first_occurrence["sourceGenerationSlotId"],
            payload["generationConfig"]["entries"][0]["id"],
        )
        self.assertEqual(
            first_occurrence["segments"],
            [
                {
                    "id": str(first_segment_id),
                    "startTime": "08:00",
                    "endTime": "10:00",
                    "status": "completed",
                },
                {
                    "id": str(second_segment_id),
                    "startTime": "10:00",
                    "endTime": "12:00",
                    "status": "pending",
                },
            ],
        )

    def test_segment_status_conflict_guard_uses_child_intervals_and_is_atomic(self):
        database_url = self._create_database()
        blocker_plan_id = UUID(int=820)
        blocker_occurrence_id = UUID(int=821)
        target_plan_id = UUID(int=822)
        target_occurrence_id = UUID(int=823)
        blocker_segment_id = UUID(int=824)
        target_segment_id = UUID(int=825)

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            self._insert_plan_item(connection, blocker_plan_id)
            self._insert_plan_item(connection, target_plan_id)
            self._insert_occurrence(
                connection,
                blocker_occurrence_id,
                blocker_plan_id,
                start_time="08:00",
                end_time="09:00",
            )
            self._insert_occurrence(
                connection,
                target_occurrence_id,
                target_plan_id,
                start_time="08:30",
                end_time="09:30",
                status="cancelled",
            )
            connection.execute(
                """
                INSERT INTO public.occurrence_segments (
                    id, occurrence_id, start_time, end_time, status
                ) VALUES
                    (%s, %s, '08:00', '09:00', 'pending'),
                    (%s, %s, '08:30', '09:30', 'cancelled')
                """,
                (
                    blocker_segment_id,
                    blocker_occurrence_id,
                    target_segment_id,
                    target_occurrence_id,
                ),
            )

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_segment_service,
            "_now",
            return_value=datetime(2026, 9, 20, 12, 0),
        ):
            response = backend_app.test_client().patch(
                f"/api/occurrence-segments/{target_segment_id}/status",
                json={"status": "pending"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(),
            {
                "status": "error",
                "code": "segment_status_conflict",
                "message": "El status solicitado solapa otro segmento ocupante.",
                "blockers": [
                    {
                        "occurrenceId": str(blocker_occurrence_id),
                        "segmentId": str(blocker_segment_id),
                        "planItemId": str(blocker_plan_id),
                        "date": "2026-09-20",
                        "startTime": "08:00",
                        "endTime": "09:00",
                        "status": "pending",
                    }
                ],
            },
        )
        with psycopg.connect(database_url) as connection:
            target = connection.execute(
                """
                SELECT occurrence.status, segment.status
                FROM public.occurrences AS occurrence
                INNER JOIN public.occurrence_segments AS segment
                    ON segment.occurrence_id = occurrence.id
                WHERE segment.id = %s
                """,
                (target_segment_id,),
            ).fetchone()
            blocker = connection.execute(
                "SELECT status FROM public.occurrence_segments WHERE id = %s",
                (blocker_segment_id,),
            ).fetchone()
        self.assertEqual(target, ("cancelled", "cancelled"))
        self.assertEqual(blocker, ("pending",))

    def test_segment_status_guard_allows_parent_gap_and_adjacency(self):
        database_url = self._create_database()
        plan_ids = (UUID(int=830), UUID(int=831), UUID(int=832))
        occurrence_ids = (UUID(int=833), UUID(int=834), UUID(int=835))
        segment_ids = (UUID(int=836), UUID(int=837), UUID(int=838), UUID(int=839))

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            for plan_id in plan_ids:
                self._insert_plan_item(connection, plan_id)
            self._insert_occurrence(
                connection, occurrence_ids[0], plan_ids[0], start_time="08:00", end_time="12:00"
            )
            self._insert_occurrence(
                connection,
                occurrence_ids[1],
                plan_ids[1],
                start_time="09:30",
                end_time="10:30",
                status="cancelled",
            )
            self._insert_occurrence(
                connection,
                occurrence_ids[2],
                plan_ids[2],
                start_time="12:00",
                end_time="13:00",
                status="cancelled",
            )
            connection.execute(
                """
                INSERT INTO public.occurrence_segments (
                    id, occurrence_id, start_time, end_time, status
                ) VALUES
                    (%s, %s, '08:00', '09:00', 'pending'),
                    (%s, %s, '11:00', '12:00', 'pending'),
                    (%s, %s, '09:30', '10:30', 'cancelled'),
                    (%s, %s, '12:00', '13:00', 'cancelled')
                """,
                (
                    segment_ids[0], occurrence_ids[0],
                    segment_ids[1], occurrence_ids[0],
                    segment_ids[2], occurrence_ids[1],
                    segment_ids[3], occurrence_ids[2],
                ),
            )

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_segment_service,
            "_now",
            return_value=datetime(2026, 9, 20, 12, 0),
        ):
            client = backend_app.test_client()
            gap = client.patch(
                f"/api/occurrence-segments/{segment_ids[2]}/status",
                json={"status": "pending"},
            )
            adjacent = client.patch(
                f"/api/occurrence-segments/{segment_ids[3]}/status",
                json={"status": "pending"},
            )
        self.assertEqual(gap.status_code, 200, gap.get_data(as_text=True))
        self.assertEqual(adjacent.status_code, 200, adjacent.get_data(as_text=True))

    def test_segment_status_rolls_back_child_when_parent_update_fails(self):
        database_url = self._create_database()
        plan_item_id = UUID(int=890)
        occurrence_id = UUID(int=891)
        segment_id = UUID(int=892)

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            self._insert_plan_item(connection, plan_item_id)
            self._insert_occurrence(connection, occurrence_id, plan_item_id)
            connection.execute(
                """
                INSERT INTO public.occurrence_segments (
                    id, occurrence_id, start_time, end_time, status
                ) VALUES (%s, %s, '08:00', '09:00', 'pending')
                """,
                (segment_id, occurrence_id),
            )
            connection.execute(
                """
                CREATE FUNCTION public.reject_parent_status_update()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'intentional parent failure';
                END
                $$
                """
            )
            connection.execute(
                """
                CREATE TRIGGER reject_parent_status_update
                BEFORE UPDATE OF status ON public.occurrences
                FOR EACH ROW EXECUTE FUNCTION public.reject_parent_status_update()
                """
            )

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_segment_service,
            "_now",
            return_value=datetime(2026, 9, 20, 12, 0),
        ):
            response = backend_app.test_client().patch(
                f"/api/occurrence-segments/{segment_id}/status",
                json={"status": "completed"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("intentional parent failure", response.get_data(as_text=True))

        with psycopg.connect(database_url) as connection:
            row = connection.execute(
                """
                SELECT occurrence.status, segment.status
                FROM public.occurrences AS occurrence
                INNER JOIN public.occurrence_segments AS segment
                    ON segment.occurrence_id = occurrence.id
                WHERE occurrence.id = %s
                """,
                (occurrence_id,),
            ).fetchone()
        self.assertEqual(row, ("pending", "pending"))

    def test_reconciliation_endpoint_is_persistent_idempotent_and_skips_today(self):
        database_url = self._create_database()
        plan_item_id = UUID(int=840)
        occurrence_ids = tuple(UUID(int=841 + index) for index in range(5))
        segment_ids = tuple(UUID(int=846 + index) for index in range(6))
        slot_ids = tuple(
            UUID(generation_slot_id(860 + index)) for index in range(5)
        )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            self._insert_plan_item(connection, plan_item_id)
            self._insert_manual_config(
                connection,
                plan_item_id,
                (
                    (slot_ids[0], "2026-09-19", "08:00", "10:00"),
                    (slot_ids[1], "2026-09-18", "11:00", "12:00"),
                    (slot_ids[2], "2026-09-15", "13:00", "14:00"),
                    (slot_ids[3], "2026-09-20", "15:00", "16:00"),
                    (slot_ids[4], "2026-09-21", "17:00", "18:00"),
                ),
            )
            for occurrence_id, slot_id, day, start, end, status in (
                (occurrence_ids[0], slot_ids[0], "2026-09-19", "08:00", "10:00", "pending"),
                (occurrence_ids[1], slot_ids[1], "2026-09-18", "11:00", "12:00", "in_progress"),
                (occurrence_ids[2], slot_ids[2], "2026-09-15", "13:00", "14:00", "completed"),
                (occurrence_ids[3], slot_ids[3], "2026-09-20", "15:00", "16:00", "pending"),
                (occurrence_ids[4], slot_ids[4], "2026-09-21", "17:00", "18:00", "pending"),
            ):
                self._insert_occurrence(
                    connection,
                    occurrence_id,
                    plan_item_id,
                    day=day,
                    start_time=start,
                    end_time=end,
                    status=status,
                )
                connection.execute(
                    "UPDATE public.occurrences SET source_generation_slot_id = %s WHERE id = %s",
                    (slot_id, occurrence_id),
                )
            connection.execute(
                """
                INSERT INTO public.occurrence_segments (
                    id, occurrence_id, start_time, end_time, status
                ) VALUES
                    (%s, %s, '08:00', '09:00', 'completed'),
                    (%s, %s, '09:00', '10:00', 'pending'),
                    (%s, %s, '11:00', '12:00', 'in_progress'),
                    (%s, %s, '13:00', '14:00', 'completed'),
                    (%s, %s, '15:00', '16:00', 'pending'),
                    (%s, %s, '17:00', '18:00', 'pending')
                """,
                (
                    segment_ids[0], occurrence_ids[0],
                    segment_ids[1], occurrence_ids[0],
                    segment_ids[2], occurrence_ids[1],
                    segment_ids[3], occurrence_ids[2],
                    segment_ids[4], occurrence_ids[3],
                    segment_ids[5], occurrence_ids[4],
                ),
            )

        fixed_now = datetime(2026, 9, 20, 12, 0)
        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(backend_segment_service, "_now", return_value=fixed_now):
            client = backend_app.test_client()
            first = client.post("/api/planner/reconcile")
            first_state = client.get("/api/planner-state")
            second = client.post("/api/planner/reconcile")
            second_state = client.get("/api/planner-state")

        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        self.assertEqual(
            first.get_json(),
            {"status": "ok", "updatedOccurrences": 2, "updatedSegments": 2},
        )
        self.assertEqual(
            second.get_json(),
            {"status": "ok", "updatedOccurrences": 0, "updatedSegments": 0},
        )
        self.assertEqual(
            first_state.status_code, 200, first_state.get_data(as_text=True)
        )
        self.assertEqual(
            second_state.status_code, 200, second_state.get_data(as_text=True)
        )
        self.assertEqual(first_state.get_json(), second_state.get_json())
        by_id = {
            item["id"]: item
            for item in first_state.get_json()["occurrences"]
        }
        self.assertEqual(by_id[str(occurrence_ids[0])]["status"], "not_finished")
        self.assertEqual(
            [segment["status"] for segment in by_id[str(occurrence_ids[0])]["segments"]],
            ["completed", "not_completed"],
        )
        self.assertEqual(by_id[str(occurrence_ids[1])]["status"], "not_finished")
        self.assertEqual(by_id[str(occurrence_ids[2])]["status"], "completed")
        self.assertEqual(by_id[str(occurrence_ids[3])]["status"], "pending")
        self.assertEqual(by_id[str(occurrence_ids[4])]["status"], "pending")

    def test_reconciliation_rolls_back_all_parents_on_late_failure(self):
        database_url = self._create_database()
        plan_item_id = UUID(int=860)
        occurrence_ids = (UUID(int=861), UUID(int=862))
        segment_ids = (UUID(int=863), UUID(int=864))

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            self._insert_plan_item(connection, plan_item_id)
            for occurrence_id, segment_id, day in zip(
                occurrence_ids,
                segment_ids,
                ("2026-09-18", "2026-09-19"),
                strict=True,
            ):
                self._insert_occurrence(
                    connection,
                    occurrence_id,
                    plan_item_id,
                    day=day,
                    status="pending",
                )
                connection.execute(
                    """
                    INSERT INTO public.occurrence_segments (
                        id, occurrence_id, start_time, end_time, status
                    ) VALUES (%s, %s, '08:00', '09:00', 'pending')
                    """,
                    (segment_id, occurrence_id),
                )
            connection.execute(
                """
                CREATE FUNCTION public.reject_late_reconciliation()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.id = '00000000-0000-0000-0000-00000000035e'::uuid THEN
                        RAISE EXCEPTION 'intentional reconciliation failure';
                    END IF;
                    RETURN NEW;
                END
                $$
                """
            )
            connection.execute(
                """
                CREATE TRIGGER reject_late_reconciliation
                BEFORE UPDATE OF status ON public.occurrences
                FOR EACH ROW EXECUTE FUNCTION public.reject_late_reconciliation()
                """
            )

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_segment_service,
            "_now",
            return_value=datetime(2026, 9, 20, 12, 0),
        ):
            response = backend_app.test_client().post("/api/planner/reconcile")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "intentional reconciliation failure", response.get_data(as_text=True)
        )

        with psycopg.connect(database_url) as connection:
            rows = connection.execute(
                """
                SELECT occurrence.status, segment.status
                FROM public.occurrences AS occurrence
                INNER JOIN public.occurrence_segments AS segment
                    ON segment.occurrence_id = occurrence.id
                ORDER BY occurrence.id
                """
            ).fetchall()
        self.assertEqual(rows, [("pending", "pending"), ("pending", "pending")])

    def test_concurrent_overlapping_activations_cannot_both_commit(self):
        database_url = self._create_database()
        plan_ids = (UUID(int=870), UUID(int=871))
        occurrence_ids = (UUID(int=872), UUID(int=873))
        segment_ids = (UUID(int=874), UUID(int=875))

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            for plan_id, occurrence_id, segment_id, start, end in zip(
                plan_ids,
                occurrence_ids,
                segment_ids,
                ("08:00", "08:30"),
                ("09:00", "09:30"),
                strict=True,
            ):
                self._insert_plan_item(connection, plan_id)
                self._insert_occurrence(
                    connection,
                    occurrence_id,
                    plan_id,
                    start_time=start,
                    end_time=end,
                    status="cancelled",
                )
                connection.execute(
                    """
                    INSERT INTO public.occurrence_segments (
                        id, occurrence_id, start_time, end_time, status
                    ) VALUES (%s, %s, %s, %s, 'cancelled')
                    """,
                    (segment_id, occurrence_id, start, end),
                )

        both_read = Barrier(2)
        original_list_overlaps = backend_segment_repository.list_blocking_overlaps

        def synchronized_list_overlaps(*args, **kwargs):
            both_read.wait(timeout=5)
            return original_list_overlaps(*args, **kwargs)

        def activate(segment_id):
            try:
                return backend_segment_service.mutate_segment_status(
                    str(segment_id),
                    {"status": "pending"},
                    now=datetime(2026, 9, 20, 12, 0),
                )
            except backend_segment_service.OccurrenceSegmentConflictError as error:
                return error.code

        with patch.object(
            backend_database, "get_database_url", return_value=database_url
        ), patch.object(
            backend_segment_repository,
            "list_blocking_overlaps",
            side_effect=synchronized_list_overlaps,
        ), ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(activate, segment_ids))

        self.assertEqual(
            sum(isinstance(result, dict) for result in results),
            1,
        )
        self.assertEqual(results.count("concurrent_conflict"), 1)
        with psycopg.connect(database_url) as connection:
            rows = connection.execute(
                """
                SELECT occurrence.status, segment.status
                FROM public.occurrences AS occurrence
                INNER JOIN public.occurrence_segments AS segment
                    ON segment.occurrence_id = occurrence.id
                ORDER BY occurrence.id
                """
            ).fetchall()
        self.assertEqual(sorted(rows), [("cancelled", "cancelled"), ("pending", "pending")])

    def test_migration_is_atomic_when_a_late_step_fails(self):
        database_url = self._create_database()
        migration = migration_sql(MIGRATION_004)
        before_commit, separator, after_commit = migration.rpartition("COMMIT;")
        self.assertEqual(separator, "COMMIT;")
        self.assertFalse(after_commit.strip())
        deliberately_broken_migration = (
            before_commit
            + "SELECT 1 / 0; -- test-only failure before commit\n"
            + separator
        )

        with psycopg.connect(database_url, autocommit=True) as connection:
            self._apply_001_to_003(connection)
            extension_existed_before = connection.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'
                )
                """
            ).fetchone()[0]

            with self.assertRaises(psycopg.errors.DivisionByZero):
                connection.execute(deliberately_broken_migration)

        with psycopg.connect(database_url, autocommit=True) as connection:
            self.assertEqual(
                connection.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'
                    )
                    """
                ).fetchone()[0],
                extension_existed_before,
            )
            self.assertFalse(
                connection.execute(
                    "SELECT to_regclass('public.occurrence_segments') IS NOT NULL"
                ).fetchone()[0]
            )
            columns = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                        AND table_name = 'occurrences'
                    """
                ).fetchall()
            }
            self.assertIn("status_reason", columns)
            self.assertNotIn("conflict_reason", columns)
            self.assertNotIn("origin_reason", columns)
            self.assertNotIn("last_conflict_action", columns)


class OccurrenceStructurePostgreSQLTests(OccurrenceSegmentMigrationHarness):
    """Comandos estructurales reales sobre schema 001→004 desechable."""

    def _fixture(self, *, with_blocker=False):
        dsn = self._create_database()
        plan_id, occurrence_id = UUID(int=9001), UUID(int=9002)
        first_id, second_id = UUID(int=9003), UUID(int=9004)
        blocker_plan, blocker_id, blocker_segment = UUID(int=9005), UUID(int=9006), UUID(int=9007)
        with psycopg.connect(dsn, autocommit=True) as connection:
            self._apply_001_to_004(connection)
            self._insert_plan_item(connection, plan_id)
            self._insert_manual_config(connection, plan_id, [(generation_slot_id(9008), "2026-09-20", "08:00", "12:00")])
            self._insert_occurrence(connection, occurrence_id, plan_id, start_time="08:00", end_time="12:00")
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '08:00', '09:00', 'pending'),
                          (%s, %s, '11:00', '12:00', 'pending')""",
                (first_id, occurrence_id, second_id, occurrence_id),
            )
            if with_blocker:
                self._insert_plan_item(connection, blocker_plan)
                self._insert_manual_config(connection, blocker_plan, [(generation_slot_id(9009), "2026-09-20", "09:30", "10:30")])
                self._insert_occurrence(connection, blocker_id, blocker_plan, start_time="09:30", end_time="10:30")
                connection.execute(
                    """INSERT INTO public.occurrence_segments
                       (id, occurrence_id, start_time, end_time, status)
                       VALUES (%s, %s, '09:30', '10:30', 'pending')""",
                    (blocker_segment, blocker_id),
                )
        return dsn, occurrence_id, first_id, second_id, blocker_id, blocker_segment

    def test_translate_structure_reset_round_trip_and_status_regression(self):
        dsn, occurrence_id, first_id, second_id, _, _ = self._fixture()
        with patch.object(backend_database, "get_database_url", return_value=dsn), patch.object(
            backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 18, 0)
        ):
            client = backend_app.test_client()
            path = f"/api/occurrences/{occurrence_id}"
            mismatch = client.post(path + "/translate", json={"startTime": "13:00", "endTime": "18:00"})
            self.assertEqual((mismatch.status_code, mismatch.get_json()["code"]), (400, "occurrence_translate_duration_mismatch"))
            wrapping = client.post(path + "/translate", json={"startTime": "23:00", "endTime": "03:00"})
            self.assertEqual(wrapping.status_code, 400)
            moved = client.post(path + "/translate", json={"startTime": "13:00", "endTime": "17:00"})
            self.assertEqual(moved.status_code, 200, moved.get_json())
            state_response = client.get("/api/planner-state")
            self.assertEqual(state_response.status_code, 200, state_response.get_json())
            state = state_response.get_json()
            occurrence = state["occurrences"][0]
            self.assertEqual(occurrence["date"], "2026-09-20")
            self.assertEqual((occurrence["startTime"], occurrence["endTime"]), ("13:00", "17:00"))
            self.assertEqual(
                [(row["id"], row["startTime"], row["endTime"], row["status"]) for row in occurrence["segments"]],
                [(str(first_id), "13:00", "14:00", "pending"), (str(second_id), "16:00", "17:00", "pending")],
            )

            changed = client.put(path + "/structure", json={
                "startTime": "13:00", "endTime": "17:00",
                "segments": [
                    {"id": str(first_id), "startTime": "13:00", "endTime": "14:30"},
                    {"startTime": "15:00", "endTime": "17:00", "status": "pending"},
                ],
            })
            self.assertEqual(changed.status_code, 200, changed.get_json())
            new_id = changed.get_json()["segmentIds"][1]
            self.assertNotIn(new_id, (str(first_id), str(second_id)))
            self.assertEqual(UUID(new_id).version, 4)
            occurrence = client.get("/api/planner-state").get_json()["occurrences"][0]
            self.assertEqual([row["id"] for row in occurrence["segments"]], [str(first_id), new_id])
            self.assertEqual(occurrence["segments"][0]["endTime"], "14:30")
            self.assertEqual(client.patch(f"/api/occurrence-segments/{second_id}/status", json={"status": "cancelled"}).status_code, 404)
            self.assertEqual(client.patch(f"/api/occurrence-segments/{first_id}/status", json={"status": "completed"}).status_code, 200)

            reset = client.post(path + "/reset-segmentation", json={"startTime": "13:00", "endTime": "17:00"})
            self.assertEqual(reset.status_code, 200, reset.get_json())
            final = client.get("/api/planner-state").get_json()["occurrences"][0]
            self.assertEqual(len(final["segments"]), 1)
            self.assertEqual(final["segments"][0]["id"], reset.get_json()["segmentIds"][0])
            self.assertNotIn(final["segments"][0]["id"], (str(first_id), new_id))
            self.assertEqual((final["segments"][0]["startTime"], final["segments"][0]["endTime"]), ("13:00", "17:00"))
            self.assertEqual(final["segments"][0]["status"], "in_progress")
            self.assertEqual(final["status"], "in_progress")

    def test_gap_aware_conflict_and_atomic_rejection(self):
        dsn, occurrence_id, first_id, second_id, blocker_id, blocker_segment = self._fixture(with_blocker=True)
        with patch.object(backend_database, "get_database_url", return_value=dsn), patch.object(
            backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 18, 0)
        ):
            client = backend_app.test_client()
            path = f"/api/occurrences/{occurrence_id}"
            # El envelope 08–12 solapa 09:30–10:30, pero sus children no.
            accepted = client.put(path + "/structure", json={
                "startTime": "08:00", "endTime": "12:00",
                "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": "09:00"},
                    {"id": str(second_id), "startTime": "11:00", "endTime": "12:00"},
                ],
            })
            self.assertEqual(accepted.status_code, 200, accepted.get_json())
            rejected = client.post(path + "/reset-segmentation", json={"startTime": "08:00", "endTime": "12:00"})
            self.assertEqual(rejected.status_code, 409, rejected.get_json())
            self.assertEqual(rejected.get_json()["code"], "occurrence_structure_conflict")
            self.assertEqual(rejected.get_json()["blockers"][0]["occurrenceId"], str(blocker_id))
            self.assertEqual(rejected.get_json()["blockers"][0]["segmentId"], str(blocker_segment))
            state = client.get("/api/planner-state").get_json()
            target = next(row for row in state["occurrences"] if row["id"] == str(occurrence_id))
            self.assertEqual([row["id"] for row in target["segments"]], [str(first_id), str(second_id)])

    def test_identity_validation_and_rollback_at_each_write_boundary(self):
        dsn, occurrence_id, first_id, second_id, _, _ = self._fixture()
        foreign_occurrence, foreign_segment = UUID(int=9011), UUID(int=9012)
        with psycopg.connect(dsn, autocommit=True) as connection:
            self._insert_occurrence(
                connection, foreign_occurrence, UUID(int=9001),
                start_time="15:00", end_time="16:00", status="cancelled",
            )
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '15:00', '16:00', 'cancelled')""",
                (foreign_segment, foreign_occurrence),
            )
        with patch.object(backend_database, "get_database_url", return_value=dsn), patch.object(
            backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 18, 0)
        ):
            client = backend_app.test_client()
            path = f"/api/occurrences/{occurrence_id}/structure"
            initial = client.get("/api/planner-state").get_json()
            invalid_payloads = [
                ([], "occurrence_requires_segment"),
                ([{"id": str(UUID(int=9010)), "startTime": "08:00", "endTime": "09:00"}], "segment_not_owned"),
                ([{"id": str(foreign_segment), "startTime": "08:00", "endTime": "09:00"}], "segment_not_owned"),
                ([{"id": str(first_id), "startTime": "08:00", "endTime": "09:00", "status": "cancelled"}], "invalid_payload"),
                ([{"id": str(first_id), "startTime": "08:00", "endTime": "09:00"}] * 2, "duplicate_segment_id"),
            ]
            for segments, code in invalid_payloads:
                with self.subTest(code=code):
                    response = client.put(path, json={"startTime": "08:00", "endTime": "12:00", "segments": segments})
                    self.assertEqual(response.status_code, 400, response.get_json())
                    self.assertEqual(response.get_json()["code"], code)
            valid = {
                "startTime": "08:00", "endTime": "12:00",
                "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": "09:30"},
                    {"startTime": "10:00", "endTime": "12:00", "status": "pending"},
                ],
            }
            for function_name in (
                "insert_segment", "delete_segments", "update_occurrence_structure"
            ):
                with self.subTest(function_name=function_name), patch.object(
                    backend_segment_repository, function_name,
                    side_effect=psycopg.Error("forced isolated failure"),
                ):
                    response = client.put(path, json=valid)
                    self.assertEqual(response.status_code, 503, response.get_json())
                self.assertEqual(client.get("/api/planner-state").get_json(), initial)

            # Resize explícito: los children enviados caben; no hay escalado.
            outside = client.put(path, json={
                "startTime": "08:00", "endTime": "11:00",
                "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": "09:00"},
                    {"id": str(second_id), "startTime": "11:00", "endTime": "12:00"},
                ],
            })
            self.assertEqual((outside.status_code, outside.get_json()["code"]), (400, "segment_outside_occurrence"))
            resized = client.put(path, json={
                "startTime": "08:00", "endTime": "11:00",
                "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": "09:15"},
                    {"id": str(second_id), "startTime": "10:00", "endTime": "11:00"},
                ],
            })
            self.assertEqual(resized.status_code, 200, resized.get_json())
            target = next(row for row in client.get("/api/planner-state").get_json()["occurrences"] if row["id"] == str(occurrence_id))
            self.assertEqual((target["startTime"], target["endTime"]), ("08:00", "11:00"))
            self.assertEqual([(row["id"], row["startTime"], row["endTime"]) for row in target["segments"]], [
                (str(first_id), "08:00", "09:15"), (str(second_id), "10:00", "11:00")
            ])

            # Un split manual conserva la identidad izquierda y crea otra derecha.
            split = client.put(path, json={
                "startTime": "08:00", "endTime": "11:00",
                "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": "08:30"},
                    {"startTime": "08:45", "endTime": "09:15", "status": "pending"},
                    {"startTime": "09:30", "endTime": "10:00", "status": "pending"},
                    {"id": str(second_id), "startTime": "10:00", "endTime": "11:00"},
                ],
            })
            self.assertEqual(split.status_code, 200, split.get_json())
            new_ids = split.get_json()["segmentIds"][1:3]
            self.assertEqual(len(set(new_ids)), 2)
            self.assertTrue(all(UUID(value).version == 4 for value in new_ids))
            # La omisión de los dos nuevos children los elimina en un único PUT.
            deleted = client.put(path, json={
                "startTime": "08:00", "endTime": "11:00",
                "segments": [{"id": str(first_id), "startTime": "08:00", "endTime": "08:30"}],
            })
            self.assertEqual(deleted.status_code, 200, deleted.get_json())
            target = next(row for row in client.get("/api/planner-state").get_json()["occurrences"] if row["id"] == str(occurrence_id))
            self.assertEqual([row["id"] for row in target["segments"]], [str(first_id)])

    def test_temporal_guards_and_completed_time(self):
        dsn, occurrence_id, first_id, _, _, _ = self._fixture()
        with patch.object(backend_database, "get_database_url", return_value=dsn):
            client = backend_app.test_client()
            path = f"/api/occurrences/{occurrence_id}"
            with patch.object(backend_segment_service, "_now", return_value=datetime(2026, 9, 22, 12, 0)):
                for method, suffix, payload in (
                    (client.post, "/translate", {"startTime": "13:00", "endTime": "17:00"}),
                    (client.put, "/structure", {"startTime": "08:00", "endTime": "12:00", "segments": [{"id": str(first_id), "startTime": "08:00", "endTime": "09:00"}]}),
                    (client.post, "/reset-segmentation", {"startTime": "08:00", "endTime": "12:00"}),
                ):
                    response = method(path + suffix, json=payload)
                    self.assertEqual((response.status_code, response.get_json()["code"]), (409, "history_frozen"))
            with patch.object(backend_segment_service, "_now", return_value=datetime(2026, 9, 21, 12, 0)):
                response = client.post(path + "/translate", json={"startTime": "13:00", "endTime": "17:00"})
                self.assertEqual((response.status_code, response.get_json()["code"]), (409, "temporal_reconciliation_required"))
            with patch.object(backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 8, 30)):
                # Completed before its end is rejected by the existing status API.
                response = client.patch(f"/api/occurrence-segments/{first_id}/status", json={"status": "completed"})
                self.assertEqual((response.status_code, response.get_json()["code"]), (409, "segment_not_ended"))
            with patch.object(backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 18, 0)):
                response = client.patch(f"/api/occurrence-segments/{first_id}/status", json={"status": "completed"})
                self.assertEqual(response.status_code, 200, response.get_json())
            with patch.object(backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 10, 0)):
                response = client.put(path + "/structure", json={
                    "startTime": "08:00", "endTime": "12:00", "segments": [
                        {"id": str(first_id), "startTime": "08:00", "endTime": "11:00"},
                    ],
                })
                self.assertEqual((response.status_code, response.get_json()["code"]), (409, "segment_not_ended"))
                allowed = client.put(path + "/structure", json={
                    "startTime": "08:00", "endTime": "12:00", "segments": [
                        {"id": str(first_id), "startTime": "08:00", "endTime": "09:30"},
                    ],
                })
                self.assertEqual(allowed.status_code, 200, allowed.get_json())

    def test_multiple_blockers_are_ordered_and_nonblocking_candidates_are_free(self):
        dsn, occurrence_id, first_id, second_id, blocker_id, blocker_segment = self._fixture(with_blocker=True)
        other_plan, other_id, other_segment = UUID(int=9020), UUID(int=9021), UUID(int=9022)
        with psycopg.connect(dsn, autocommit=True) as connection:
            self._insert_plan_item(connection, other_plan)
            self._insert_manual_config(connection, other_plan, [(generation_slot_id(9023), "2026-09-20", "10:30", "11:30")])
            self._insert_occurrence(connection, other_id, other_plan, start_time="10:30", end_time="11:30", status="not_finished")
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '10:30', '11:30', 'not_finished')""",
                (other_segment, other_id),
            )
        with patch.object(backend_database, "get_database_url", return_value=dsn), patch.object(
            backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 18, 0)
        ):
            client = backend_app.test_client()
            path = f"/api/occurrences/{occurrence_id}/structure"
            conflict = client.put(path, json={
                "startTime": "08:00", "endTime": "12:00",
                "segments": [{"id": str(first_id), "startTime": "08:00", "endTime": "12:00"}],
            })
            self.assertEqual(conflict.status_code, 409, conflict.get_json())
            self.assertEqual(
                [row["segmentId"] for row in conflict.get_json()["blockers"]],
                [str(blocker_segment), str(other_segment)],
            )
            nonblocking = client.put(path, json={
                "startTime": "08:00", "endTime": "12:00",
                "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": "09:00"},
                    {"id": str(second_id), "startTime": "09:00", "endTime": "12:00"},
                ],
            })
            self.assertEqual(nonblocking.status_code, 409, nonblocking.get_json())
            # El status de un child existente no se puede cambiar por structure.
            cancelled = client.patch(f"/api/occurrence-segments/{second_id}/status", json={"status": "cancelled"})
            self.assertEqual(cancelled.status_code, 200, cancelled.get_json())
            free = client.put(path, json={
                "startTime": "08:00", "endTime": "12:00",
                "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": "09:00"},
                    {"id": str(second_id), "startTime": "09:00", "endTime": "12:00"},
                ],
            })
            self.assertEqual(free.status_code, 200, free.get_json())
            self.assertEqual(free.get_json()["occurrenceStatus"], "pending")
            noncompleted = client.patch(
                f"/api/occurrence-segments/{second_id}/status",
                json={"status": "not_completed"},
            )
            self.assertEqual(noncompleted.status_code, 200, noncompleted.get_json())
            still_free = client.put(path, json={
                "startTime": "08:00", "endTime": "12:00",
                "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": "09:00"},
                    {"id": str(second_id), "startTime": "09:00", "endTime": "12:00"},
                ],
            })
            self.assertEqual(still_free.status_code, 200, still_free.get_json())

    def test_yesterday_reconciliation_then_structure_and_metadata_preservation(self):
        dsn, occurrence_id, first_id, second_id, _, _ = self._fixture()
        source_id = UUID(int=9030)
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(
                """UPDATE public.occurrences
                   SET origin_reason = 'conflict_insertion', last_conflict_action = 'conflict_move',
                       source_generation_slot_id = %s
                   WHERE id = %s""",
                (generation_slot_id(9008), occurrence_id),
            )
            self._insert_occurrence(
                connection, source_id, UUID(int=9001),
                start_time="14:00", end_time="15:00", status="cancelled",
                conflict_reason="priority_override", source_occurrence_id=occurrence_id,
            )
            connection.execute(
                """INSERT INTO public.occurrence_segments
                   (id, occurrence_id, start_time, end_time, status)
                   VALUES (%s, %s, '14:00', '15:00', 'cancelled')""",
                (UUID(int=9031), source_id),
            )
        with patch.object(backend_database, "get_database_url", return_value=dsn), patch.object(
            backend_segment_service, "_now", return_value=datetime(2026, 9, 21, 12, 0)
        ):
            client = backend_app.test_client()
            reconciled = client.post("/api/planner/reconcile")
            self.assertEqual(reconciled.status_code, 200, reconciled.get_json())
            moved = client.post(
                f"/api/occurrences/{occurrence_id}/translate",
                json={"startTime": "09:00", "endTime": "13:00"},
            )
            self.assertEqual(moved.status_code, 200, moved.get_json())
            state = client.get("/api/planner-state").get_json()
            target = next(row for row in state["occurrences"] if row["id"] == str(occurrence_id))
            referenced = next(row for row in state["occurrences"] if row["id"] == str(source_id))
            self.assertEqual(target["sourceGenerationSlotId"], generation_slot_id(9008))
            self.assertEqual(target["originReason"], "conflict_insertion")
            self.assertEqual(target["lastConflictAction"], "conflict_move")
            self.assertEqual(referenced["conflictContext"]["sourceOccurrenceId"], str(occurrence_id))
            self.assertEqual(
                [(row["id"], row["status"]) for row in target["segments"]],
                [(str(first_id), "not_completed"), (str(second_id), "not_completed")],
            )

    def test_future_new_status_and_reset_completed_time(self):
        dsn, occurrence_id, first_id, second_id, _, _ = self._fixture()
        with patch.object(backend_database, "get_database_url", return_value=dsn):
            client = backend_app.test_client()
            path = f"/api/occurrences/{occurrence_id}"
            with patch.object(backend_segment_service, "_now", return_value=datetime(2026, 9, 19, 12, 0)):
                invalid = client.put(path + "/structure", json={
                    "startTime": "08:00", "endTime": "12:00", "segments": [
                        {"id": str(first_id), "startTime": "08:00", "endTime": "09:00"},
                        {"startTime": "10:00", "endTime": "12:00", "status": "completed"},
                    ],
                })
                self.assertEqual((invalid.status_code, invalid.get_json()["code"]), (409, "segment_status_not_allowed"))
                valid = client.put(path + "/structure", json={
                    "startTime": "08:00", "endTime": "12:00", "segments": [
                        {"id": str(first_id), "startTime": "08:00", "endTime": "09:00"},
                        {"startTime": "10:00", "endTime": "12:00", "status": "cancelled"},
                    ],
                })
                self.assertEqual(valid.status_code, 200, valid.get_json())
                self.assertEqual(valid.get_json()["occurrenceStatus"], "pending")
            with patch.object(backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 18, 0)):
                for segment_id in valid.get_json()["segmentIds"]:
                    response = client.patch(f"/api/occurrence-segments/{segment_id}/status", json={"status": "completed"})
                    self.assertEqual(response.status_code, 200, response.get_json())
            previous = client.get("/api/planner-state").get_json()
            with patch.object(backend_segment_service, "_now", return_value=datetime(2026, 9, 20, 10, 0)):
                rejected = client.post(path + "/reset-segmentation", json={"startTime": "08:00", "endTime": "12:00"})
                self.assertEqual((rejected.status_code, rejected.get_json()["code"]), (409, "segment_not_ended"))
            self.assertEqual(client.get("/api/planner-state").get_json(), previous)

    def test_concurrent_structure_writes_keep_one_complete_graph(self):
        dsn, occurrence_id, first_id, second_id, _, _ = self._fixture()
        barrier = Barrier(2)
        original_lock = backend_segment_repository.lock_occurrence

        def synchronized_lock(*args, **kwargs):
            barrier.wait(timeout=5)
            return original_lock(*args, **kwargs)

        def replace(index):
            payload = {
                "startTime": "08:00", "endTime": "12:00", "segments": [
                    {"id": str(first_id), "startTime": "08:00", "endTime": f"09:{index}0"},
                    {"startTime": f"10:{index}0", "endTime": "12:00", "status": "pending"},
                ],
            }
            try:
                return backend_structure_service.replace_occurrence_structure(
                    str(occurrence_id), payload, now=datetime(2026, 9, 20, 18, 0)
                )
            except backend_structure_service.OccurrenceStructureConflictError as error:
                return error.code

        with patch.object(backend_database, "get_database_url", return_value=dsn), patch.object(
            backend_segment_repository, "lock_occurrence", side_effect=synchronized_lock
        ), ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(replace, (1, 2)))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(results.count("concurrent_conflict"), 1)
        with patch.object(backend_database, "get_database_url", return_value=dsn):
            target = backend_app.test_client().get("/api/planner-state").get_json()["occurrences"][0]
        self.assertEqual(len(target["segments"]), 2)
        self.assertEqual(target["segments"][0]["id"], str(first_id))
        self.assertNotEqual(target["segments"][1]["id"], str(second_id))
        self.assertEqual(target["status"], "pending")


if __name__ == "__main__":
    unittest.main(verbosity=2)
