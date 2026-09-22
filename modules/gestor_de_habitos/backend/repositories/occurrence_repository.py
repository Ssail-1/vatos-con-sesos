"""SQL transaccional para mutaciones de una sola Occurrence."""

from psycopg.rows import dict_row


def set_serializable_transaction(connection):
    """Evita que dos validaciones concurrentes confirmen estados incompatibles."""
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")


def lock_plan_item_identity(connection, plan_item_id):
    """Serializa todas las mutaciones semanales del mismo PlanItem."""
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id
            FROM public.plan_items
            WHERE id = %s
            FOR UPDATE
            """,
            (plan_item_id,),
        )
        return cursor.fetchone()


def find_occurrence_owner(connection, occurrence_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT plan_item_id
            FROM public.occurrences
            WHERE id = %s
            """,
            (occurrence_id,),
        )
        return cursor.fetchone()


def lock_plan_item_context(connection, plan_item_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                plan_item.id,
                plan_item.kind,
                plan_item.subtype,
                config.mode,
                config.start_date,
                config.end_date,
                config.indefinite,
                config.interval_days,
                config.stopped_from_date,
                (
                    SELECT COUNT(*)
                    FROM public.generation_slots AS slot
                    WHERE slot.plan_item_id = plan_item.id
                ) AS slot_count,
                (
                    SELECT COUNT(*)
                    FROM public.generation_excluded_dates AS excluded
                    WHERE excluded.plan_item_id = plan_item.id
                ) AS global_exclusion_count
            FROM public.plan_items AS plan_item
            INNER JOIN public.generation_configs AS config
                ON config.plan_item_id = plan_item.id
            WHERE plan_item.id = %s
            FOR UPDATE OF plan_item, config
            """,
            (plan_item_id,),
        )
        return cursor.fetchone()


def lock_plan_item_week_occurrences(connection, plan_item_id, week_start, week_end):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                id,
                plan_item_id,
                occurrence_date,
                start_time,
                end_time,
                status,
                conflict_reason,
                source_occurrence_id,
                source_generation_slot_id,
                origin_reason,
                last_conflict_action
            FROM public.occurrences
            WHERE plan_item_id = %s
              AND occurrence_date BETWEEN %s AND %s
            ORDER BY occurrence_date, start_time, end_time, id
            FOR UPDATE
            """,
            (plan_item_id, week_start, week_end),
        )
        return cursor.fetchall()


def lock_external_blocking_occurrences(connection, plan_item_id, occurrence_dates):
    if not occurrence_dates:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                occurrence.id,
                occurrence.plan_item_id,
                occurrence.occurrence_date,
                occurrence.start_time,
                occurrence.end_time,
                occurrence.status,
                plan_item.kind,
                plan_item.subtype
            FROM public.occurrences AS occurrence
            INNER JOIN public.plan_items AS plan_item
                ON plan_item.id = occurrence.plan_item_id
            WHERE occurrence.plan_item_id <> %s
              AND occurrence.occurrence_date = ANY(%s::date[])
              AND occurrence.status IN ('pending', 'in_progress', 'completed')
            ORDER BY
                occurrence.occurrence_date,
                occurrence.start_time,
                occurrence.end_time,
                occurrence.id
            FOR UPDATE OF occurrence
            """,
            (plan_item_id, occurrence_dates),
        )
        return cursor.fetchall()


def lock_status_context_dependents_for_sources(connection, occurrence_ids):
    if not occurrence_ids:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, source_occurrence_id
            FROM public.occurrences
            WHERE source_occurrence_id = ANY(%s::uuid[])
            ORDER BY id
            FOR UPDATE
            """,
            (occurrence_ids,),
        )
        return cursor.fetchall()


def lock_occurrences_for_slots(connection, slot_ids):
    if not slot_ids:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, source_generation_slot_id, occurrence_date
            FROM public.occurrences
            WHERE source_generation_slot_id = ANY(%s::uuid[])
            ORDER BY source_generation_slot_id, occurrence_date, id
            FOR UPDATE
            """,
            (slot_ids,),
        )
        return cursor.fetchall()


def lock_occurrence(connection, occurrence_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                id,
                plan_item_id,
                occurrence_date,
                start_time,
                end_time,
                status,
                status_reason,
                source_occurrence_id,
                source_generation_slot_id
            FROM public.occurrences
            WHERE id = %s
            FOR UPDATE
            """,
            (occurrence_id,),
        )
        return cursor.fetchone()


def lock_occurrence_for_delete(connection, occurrence_id):
    """Schema-004 read path for whole-graph deletion; no legacy status_reason."""
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, plan_item_id, occurrence_date, start_time, end_time,
                   status, conflict_reason, source_occurrence_id,
                   source_generation_slot_id, origin_reason, last_conflict_action
            FROM public.occurrences
            WHERE id = %s
            FOR UPDATE
            """,
            (occurrence_id,),
        )
        return cursor.fetchone()


def lock_generation_slot(connection, slot_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                slot.id,
                slot.plan_item_id,
                slot.start_time,
                slot.end_time,
                (
                    SELECT COUNT(*)
                    FROM public.generation_slot_weekdays AS weekday
                    WHERE weekday.slot_id = slot.id
                ) AS weekday_count,
                (
                    SELECT COUNT(*)
                    FROM public.generation_slot_dates AS slot_date
                    WHERE slot_date.slot_id = slot.id
                ) AS date_count,
                (
                    SELECT COUNT(*)
                    FROM public.generation_slot_excluded_dates AS excluded
                    WHERE excluded.slot_id = slot.id
                ) AS excluded_date_count
            FROM public.generation_slots AS slot
            WHERE slot.id = %s
            FOR UPDATE
            """,
            (slot_id,),
        )
        return cursor.fetchone()


def lock_plan_item_slots(connection, plan_item_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                slot.id,
                slot.plan_item_id,
                slot.start_time,
                slot.end_time,
                (
                    SELECT COUNT(*)
                    FROM public.generation_slot_weekdays AS weekday
                    WHERE weekday.slot_id = slot.id
                ) AS weekday_count,
                (
                    SELECT COUNT(*)
                    FROM public.generation_slot_dates AS slot_date
                    WHERE slot_date.slot_id = slot.id
                ) AS date_count,
                (
                    SELECT MIN(slot_date.entry_date)
                    FROM public.generation_slot_dates AS slot_date
                    WHERE slot_date.slot_id = slot.id
                ) AS entry_date,
                (
                    SELECT COUNT(*)
                    FROM public.generation_slot_excluded_dates AS excluded
                    WHERE excluded.slot_id = slot.id
                ) AS excluded_date_count
            FROM public.generation_slots AS slot
            WHERE slot.plan_item_id = %s
            ORDER BY slot.id
            FOR UPDATE
            """,
            (plan_item_id,),
        )
        return cursor.fetchall()


def lock_manual_slot_date(connection, slot_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT slot_id, entry_date
            FROM public.generation_slot_dates
            WHERE slot_id = %s
            FOR UPDATE
            """,
            (slot_id,),
        )
        return cursor.fetchone()


def lock_manual_sibling_slots_on_date(
    connection, plan_item_id, entry_date, ignored_slot_id
):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT slot.id, slot.start_time, slot.end_time
            FROM public.generation_slots AS slot
            INNER JOIN public.generation_slot_dates AS slot_date
                ON slot_date.slot_id = slot.id
            WHERE slot.plan_item_id = %s
              AND slot_date.entry_date = %s
              AND slot.id <> %s
            ORDER BY slot.start_time, slot.end_time, slot.id
            FOR UPDATE OF slot, slot_date
            """,
            (plan_item_id, entry_date, ignored_slot_id),
        )
        return cursor.fetchall()


def lock_occurrences_for_slot(connection, slot_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id
            FROM public.occurrences
            WHERE source_generation_slot_id = %s
            ORDER BY id
            FOR UPDATE
            """,
            (slot_id,),
        )
        return cursor.fetchall()


def lock_status_context_dependents(connection, occurrence_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id
            FROM public.occurrences
            WHERE source_occurrence_id = %s
            ORDER BY id
            FOR UPDATE
            """,
            (occurrence_id,),
        )
        return cursor.fetchall()


def lock_source_occurrence_on_date(
    connection, slot_id, occurrence_date, ignored_occurrence_id
):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id
            FROM public.occurrences
            WHERE source_generation_slot_id = %s
              AND occurrence_date = %s
              AND id <> %s
            FOR UPDATE
            """,
            (slot_id, occurrence_date, ignored_occurrence_id),
        )
        return cursor.fetchone()


def lock_blocking_occurrences(
    connection, occurrence_date, ignored_occurrence_id
):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                occurrence.id,
                occurrence.occurrence_date,
                occurrence.start_time,
                occurrence.end_time,
                occurrence.status,
                plan_item.kind,
                plan_item.subtype
            FROM public.occurrences AS occurrence
            INNER JOIN public.plan_items AS plan_item
                ON plan_item.id = occurrence.plan_item_id
            WHERE occurrence.occurrence_date = %s
              AND occurrence.id <> %s
              AND occurrence.status IN ('pending', 'in_progress', 'completed')
            ORDER BY occurrence.start_time, occurrence.end_time, occurrence.id
            FOR UPDATE OF occurrence
            """,
            (occurrence_date, ignored_occurrence_id),
        )
        return cursor.fetchall()


def insert_slot_exclusion(connection, slot_id, excluded_date):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.generation_slot_excluded_dates (
                slot_id,
                excluded_date
            )
            VALUES (%s, %s)
            ON CONFLICT (slot_id, excluded_date) DO NOTHING
            """,
            (slot_id, excluded_date),
        )


def insert_slot_exclusions(connection, exclusions):
    if not exclusions:
        return
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO public.generation_slot_excluded_dates (
                slot_id,
                excluded_date
            )
            VALUES (%s, %s)
            ON CONFLICT (slot_id, excluded_date) DO NOTHING
            """,
            exclusions,
        )


def update_occurrence_schedule(
    connection, occurrence_id, occurrence_date, start_time, end_time
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.occurrences
            SET occurrence_date = %s,
                start_time = %s,
                end_time = %s
            WHERE id = %s
            """,
            (occurrence_date, start_time, end_time, occurrence_id),
        )
        return cursor.rowcount


def stage_occurrence_dates(connection, staged_dates):
    """Libera claves slot+date antes de aplicar movimientos finales."""
    with connection.cursor() as cursor:
        for occurrence_id, temporary_date in staged_dates:
            cursor.execute(
                """
                UPDATE public.occurrences
                SET occurrence_date = %s
                WHERE id = %s
                """,
                (temporary_date, occurrence_id),
            )
            if cursor.rowcount != 1:
                return False
    return True


def insert_ad_hoc_occurrences(connection, occurrences):
    if not occurrences:
        return
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO public.occurrences (
                id,
                plan_item_id,
                occurrence_date,
                start_time,
                end_time,
                status,
                source_generation_slot_id
            )
            VALUES (%s, %s, %s, %s, %s, 'pending', NULL)
            """,
            [
                (
                    occurrence["id"],
                    occurrence["plan_item_id"],
                    occurrence["occurrence_date"],
                    occurrence["start_time"],
                    occurrence["end_time"],
                )
                for occurrence in occurrences
            ],
        )


def list_plan_item_week_occurrences(connection, plan_item_id, week_start, week_end):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                id,
                plan_item_id,
                occurrence_date,
                start_time,
                end_time,
                status,
                conflict_reason,
                source_occurrence_id,
                source_generation_slot_id,
                origin_reason,
                last_conflict_action
            FROM public.occurrences
            WHERE plan_item_id = %s
              AND occurrence_date BETWEEN %s AND %s
            ORDER BY occurrence_date, start_time, end_time, id
            """,
            (plan_item_id, week_start, week_end),
        )
        return cursor.fetchall()


def update_generation_slot_schedule(connection, slot_id, start_time, end_time):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.generation_slots
            SET start_time = %s,
                end_time = %s
            WHERE id = %s
            """,
            (start_time, end_time, slot_id),
        )
        return cursor.rowcount


def update_manual_slot_date(connection, slot_id, entry_date):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.generation_slot_dates
            SET entry_date = %s
            WHERE slot_id = %s
            """,
            (entry_date, slot_id),
        )
        return cursor.rowcount


def delete_occurrence(connection, occurrence_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM public.occurrences
            WHERE id = %s
            """,
            (occurrence_id,),
        )
        return cursor.rowcount


def delete_generation_slot(connection, slot_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM public.generation_slots
            WHERE id = %s
            """,
            (slot_id,),
        )
        return cursor.rowcount
