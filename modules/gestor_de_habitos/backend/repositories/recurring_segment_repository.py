"""Lectura de blockers para batches recurrentes sobre schema 004."""

from psycopg.rows import dict_row


def lock_external_blocking_segments(connection, excluded_occurrence_ids, dates, blocking_statuses):
    if not dates:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT occurrence.id AS occurrence_id, occurrence.plan_item_id,
                   occurrence.occurrence_date, segment.id AS segment_id,
                   segment.start_time, segment.end_time, segment.status
            FROM public.occurrence_segments AS segment
            JOIN public.occurrences AS occurrence ON occurrence.id = segment.occurrence_id
            WHERE occurrence.occurrence_date = ANY(%s::date[])
              AND occurrence.id <> ALL(%s::uuid[])
              AND segment.status = ANY(%s::text[])
            ORDER BY occurrence.id, segment.start_time, segment.end_time, segment.id
            FOR UPDATE OF segment
            """,
            (dates, excluded_occurrence_ids, sorted(blocking_statuses)),
        )
        return cursor.fetchall()
