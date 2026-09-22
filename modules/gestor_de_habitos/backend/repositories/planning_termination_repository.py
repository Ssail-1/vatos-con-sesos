"""SQL for durable, occurrence-anchored planning termination commands."""

from psycopg.rows import dict_row


def lock_slots(connection, plan_item_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """SELECT id, plan_item_id, last_generation_date
               FROM public.generation_slots
               WHERE plan_item_id = %s
               ORDER BY id FOR UPDATE""",
            (plan_item_id,),
        )
        return cursor.fetchall()


def lock_future_occurrences(connection, plan_item_id, cutoff_date):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """SELECT id, plan_item_id, occurrence_date, source_generation_slot_id
               FROM public.occurrences
               WHERE plan_item_id = %s AND occurrence_date > %s
               ORDER BY occurrence_date, id FOR UPDATE""",
            (plan_item_id, cutoff_date),
        )
        return cursor.fetchall()


def external_source_dependents(connection, deletion_ids):
    if not deletion_ids:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """SELECT id, source_occurrence_id
               FROM public.occurrences
               WHERE source_occurrence_id = ANY(%s::uuid[])
                 AND NOT (id = ANY(%s::uuid[]))
               ORDER BY id FOR UPDATE""",
            (deletion_ids, deletion_ids),
        )
        return cursor.fetchall()


def shorten_slot(connection, slot_id, cutoff_date):
    with connection.cursor() as cursor:
        cursor.execute(
            """UPDATE public.generation_slots
               SET last_generation_date = CASE
                   WHEN last_generation_date IS NULL OR last_generation_date > %s
                   THEN %s ELSE last_generation_date END
               WHERE id = %s""",
            (cutoff_date, cutoff_date, slot_id),
        )
        return cursor.rowcount


def shorten_schedule(connection, plan_item_id, next_date):
    with connection.cursor() as cursor:
        cursor.execute(
            """UPDATE public.generation_configs
               SET stopped_from_date = CASE
                   WHEN stopped_from_date IS NULL OR stopped_from_date > %s
                   THEN %s ELSE stopped_from_date END
               WHERE plan_item_id = %s""",
            (next_date, next_date, plan_item_id),
        )
        return cursor.rowcount


def delete_occurrences(connection, deletion_ids):
    if not deletion_ids:
        return 0
    with connection.cursor() as cursor:
        # One statement permits NO ACTION references entirely inside this set.
        cursor.execute(
            "DELETE FROM public.occurrences WHERE id = ANY(%s::uuid[])",
            (deletion_ids,),
        )
        return cursor.rowcount
