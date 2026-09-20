"""PostgreSQL 16 integration tests for migration 004 only.

The suite starts an isolated temporary cluster under /tmp, creates a dedicated
non-superuser database owner, and never reads DATABASE_URL or backend/.env.
"""

from pathlib import Path
import subprocess
import tempfile
import unittest
from uuid import UUID

import psycopg
from psycopg import sql


MIGRATION_DIRECTORY = Path(__file__).resolve().parent / "migrations"
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


def migration_sql(name):
    return (MIGRATION_DIRECTORY / name).read_text(encoding="utf-8")


class OccurrenceSegmentMigrationTests(unittest.TestCase):
    """Exercise 001 → 004 against a real disposable PostgreSQL 16 cluster."""

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
