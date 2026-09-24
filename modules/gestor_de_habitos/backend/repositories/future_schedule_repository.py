"""SQL transaccional para reemplazar el motor recurrente vigente."""

from psycopg.rows import dict_row


def lock_plan_item_schedule(connection, plan_item_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                plan_item.id,
                plan_item.name,
                plan_item.kind,
                plan_item.subtype,
                config.plan_item_id,
                config.mode,
                config.start_date,
                config.end_date,
                config.indefinite,
                config.interval_days,
                config.stopped_from_date
            FROM public.plan_items AS plan_item
            INNER JOIN public.generation_configs AS config
                ON config.plan_item_id = plan_item.id
            WHERE plan_item.id = %s
            FOR UPDATE OF plan_item, config
            """,
            (plan_item_id,),
        )
        return cursor.fetchone()


def lock_generation_slots(connection, plan_item_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, plan_item_id, start_time, end_time, last_generation_date
            FROM public.generation_slots
            WHERE plan_item_id = %s
            ORDER BY id
            FOR UPDATE
            """,
            (plan_item_id,),
        )
        return cursor.fetchall()


def lock_slot_weekdays(connection, slot_ids):
    if not slot_ids:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT slot_id, iso_weekday
            FROM public.generation_slot_weekdays
            WHERE slot_id = ANY(%s::uuid[])
            ORDER BY slot_id
            FOR UPDATE
            """,
            (slot_ids,),
        )
        return cursor.fetchall()


def lock_slot_dates(connection, slot_ids):
    if not slot_ids:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT slot_id, entry_date
            FROM public.generation_slot_dates
            WHERE slot_id = ANY(%s::uuid[])
            ORDER BY slot_id
            FOR UPDATE
            """,
            (slot_ids,),
        )
        return cursor.fetchall()


def lock_slot_exclusions(connection, slot_ids):
    if not slot_ids:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT slot_id, excluded_date
            FROM public.generation_slot_excluded_dates
            WHERE slot_id = ANY(%s::uuid[])
            ORDER BY slot_id, excluded_date
            FOR UPDATE
            """,
            (slot_ids,),
        )
        return cursor.fetchall()


def lock_global_exclusions(connection, plan_item_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT plan_item_id, excluded_date
            FROM public.generation_excluded_dates
            WHERE plan_item_id = %s
            ORDER BY excluded_date
            FOR UPDATE
            """,
            (plan_item_id,),
        )
        return cursor.fetchall()


def lock_plan_item_occurrences(connection, plan_item_id):
    """Incluye historia porque borrar un slot cambia su FK a NULL."""
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
            ORDER BY occurrence_date, start_time, end_time, id
            FOR UPDATE
            """,
            (plan_item_id,),
        )
        return cursor.fetchall()


def lock_requested_slot_identities(connection, slot_ids):
    if not slot_ids:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, plan_item_id
            FROM public.generation_slots
            WHERE id = ANY(%s::uuid[])
            ORDER BY id
            FOR UPDATE
            """,
            (slot_ids,),
        )
        return cursor.fetchall()


def update_generation_config(connection, plan_item_id, config):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.generation_configs
            SET start_date = %s,
                end_date = %s,
                indefinite = %s,
                interval_days = %s
            WHERE plan_item_id = %s
            """,
            (
                config["startDate"],
                config["endDate"],
                config["indefinite"],
                config.get("intervalDays"),
                plan_item_id,
            ),
        )
        return cursor.rowcount


def update_generation_slot(connection, slot):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.generation_slots
            SET start_time = %s,
                end_time = %s
            WHERE id = %s
            """,
            (slot["startTime"], slot["endTime"], slot["id"]),
        )
        return cursor.rowcount


def update_slot_weekday(connection, slot_id, iso_weekday):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.generation_slot_weekdays
            SET iso_weekday = %s
            WHERE slot_id = %s
            """,
            (iso_weekday, slot_id),
        )
        return cursor.rowcount


def insert_generation_slots(connection, plan_item_id, slots, mode):
    if not slots:
        return
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO public.generation_slots (
                id, plan_item_id, start_time, end_time
            )
            VALUES (%s, %s, %s, %s)
            """,
            [
                (slot["id"], plan_item_id, slot["startTime"], slot["endTime"])
                for slot in slots
            ],
        )
        if mode == "weekly":
            cursor.executemany(
                """
                INSERT INTO public.generation_slot_weekdays (slot_id, iso_weekday)
                VALUES (%s, %s)
                """,
                [(slot["id"], slot["isoWeekday"]) for slot in slots],
            )


def delete_generation_slots(connection, slot_ids):
    if not slot_ids:
        return 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM public.generation_slots
            WHERE id = ANY(%s::uuid[])
            """,
            (slot_ids,),
        )
        return cursor.rowcount


def delete_occurrences(connection, occurrence_ids):
    if not occurrence_ids:
        return 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM public.occurrences
            WHERE id = ANY(%s::uuid[])
            """,
            (occurrence_ids,),
        )
        return cursor.rowcount


def update_occurrence_schedules(connection, occurrences):
    if not occurrences:
        return
    with connection.cursor() as cursor:
        for occurrence in occurrences:
            cursor.execute(
                """
                UPDATE public.occurrences
                SET start_time = %s,
                    end_time = %s
                WHERE id = %s
                """,
                (
                    occurrence["start_time"],
                    occurrence["end_time"],
                    occurrence["id"],
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("No se pudo actualizar una occurrence bloqueada.")


def insert_occurrences(connection, occurrences):
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
                conflict_reason,
                source_occurrence_id,
                source_generation_slot_id
            )
            VALUES (%s, %s, %s, %s, %s, 'pending', NULL, NULL, %s)
            """,
            [
                (
                    occurrence["id"],
                    occurrence["plan_item_id"],
                    occurrence["occurrence_date"],
                    occurrence["start_time"],
                    occurrence["end_time"],
                    occurrence["source_generation_slot_id"],
                )
                for occurrence in occurrences
            ],
        )


def list_occurrences_from(connection, plan_item_id, effective_date):
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
              AND occurrence_date >= %s
            ORDER BY occurrence_date, start_time, end_time, id
            """,
            (plan_item_id, effective_date),
        )
        return cursor.fetchall()
