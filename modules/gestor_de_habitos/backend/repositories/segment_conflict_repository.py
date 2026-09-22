"""Lectura y escritura SQL para resolución segmentaria de un solo source."""

from psycopg.rows import dict_row

from scheduling_policy import BLOCKING_STATUSES


def get_plan_item_priority_fields(connection, plan_item_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT kind, subtype FROM public.plan_items WHERE id = %s",
            (plan_item_id,),
        )
        return cursor.fetchone()


def list_blockers(connection, source_id, occurrence_date, segments):
    """Descubre solapes ocupantes; no bloquea hasta conocer los parents."""
    if not segments:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT occurrence.id AS occurrence_id,
                   occurrence.plan_item_id,
                   occurrence.occurrence_date,
                   segment.id AS segment_id,
                   segment.start_time,
                   segment.end_time,
                   segment.status,
                   plan_item.kind,
                   plan_item.subtype
            FROM public.occurrence_segments AS segment
            JOIN public.occurrences AS occurrence
              ON occurrence.id = segment.occurrence_id
            JOIN public.plan_items AS plan_item
              ON plan_item.id = occurrence.plan_item_id
            WHERE occurrence.occurrence_date = %s
              AND occurrence.id <> %s
              AND segment.status = ANY(%s)
              AND EXISTS (
                SELECT 1
                FROM unnest(%s::time[], %s::time[])
                     AS source(start_time, end_time)
                WHERE segment.start_time < source.end_time
                  AND segment.end_time > source.start_time
              )
            ORDER BY occurrence.id, segment.start_time, segment.end_time, segment.id
            """,
            (
                occurrence_date, source_id,
                sorted(BLOCKING_STATUSES),
                [item["startTime"] for item in segments],
                [item["endTime"] for item in segments],
            ),
        )
        return cursor.fetchall()


def lock_target_parent(connection, occurrence_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, plan_item_id, occurrence_date, start_time, end_time,
                   status, conflict_reason, source_occurrence_id,
                   origin_reason, last_conflict_action
            FROM public.occurrences
            WHERE id = %s
            FOR UPDATE
            """,
            (occurrence_id,),
        )
        return cursor.fetchone()


def lock_target_segments(connection, occurrence_id):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, occurrence_id, start_time, end_time, status
            FROM public.occurrence_segments
            WHERE occurrence_id = %s
            ORDER BY occurrence_id, start_time, end_time, id
            FOR UPDATE
            """,
            (occurrence_id,),
        )
        return cursor.fetchall()


def update_target_segment(connection, occurrence_id, old_id, new):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.occurrence_segments
            SET start_time = %s, end_time = %s, status = %s
            WHERE occurrence_id = %s AND id = %s
            """,
            (new["startTime"], new["endTime"], new["status"], occurrence_id, old_id),
        )
        return cursor.rowcount


def insert_target_segment(connection, occurrence_id, segment):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.occurrence_segments
                (id, occurrence_id, start_time, end_time, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (segment["id"], occurrence_id, segment["startTime"],
             segment["endTime"], segment["status"]),
        )
        return cursor.rowcount


def update_target_context(connection, target_id, aggregate, reason, source_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.occurrences
            SET status = %s, conflict_reason = %s, source_occurrence_id = %s
            WHERE id = %s
            """,
            (aggregate, reason, source_id, target_id),
        )
        return cursor.rowcount


def update_source_context(connection, source_id, action):
    with connection.cursor() as cursor:
        if action == "conflict_insertion":
            cursor.execute(
                """
                UPDATE public.occurrences
                SET origin_reason = 'conflict_insertion',
                    last_conflict_action = 'conflict_insertion'
                WHERE id = %s
                """,
                (source_id,),
            )
        else:
            cursor.execute(
                """
                UPDATE public.occurrences
                SET last_conflict_action = 'conflict_move'
                WHERE id = %s
                """,
                (source_id,),
            )
        return cursor.rowcount
