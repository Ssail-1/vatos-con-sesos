"""SQL transaccional para los children y aggregate de OccurrenceSegments."""

from psycopg.rows import dict_row


def find_segment_owner(connection, segment_id):
    """Localiza el parent antes de adquirir el lock parent-first."""
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT occurrence_id
            FROM public.occurrence_segments
            WHERE id = %s
            """,
            (segment_id,),
        )
        return cursor.fetchone()


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
                conflict_reason,
                source_occurrence_id,
                source_generation_slot_id,
                origin_reason,
                last_conflict_action
            FROM public.occurrences
            WHERE id = %s
            FOR UPDATE
            """,
            (occurrence_id,),
        )
        return cursor.fetchone()


def lock_occurrence_segments(connection, occurrence_id):
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


def list_blocking_overlaps(
    connection,
    occurrence_id,
    occurrence_date,
    start_time,
    end_time,
    blocking_statuses,
):
    """Detecta blockers de otros parents usando intervals de segments [start,end)."""
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                occurrence.id AS occurrence_id,
                occurrence.plan_item_id,
                occurrence.occurrence_date,
                segment.id AS segment_id,
                segment.start_time,
                segment.end_time,
                segment.status
            FROM public.occurrence_segments AS segment
            INNER JOIN public.occurrences AS occurrence
                ON occurrence.id = segment.occurrence_id
            WHERE occurrence.occurrence_date = %s
              AND occurrence.id <> %s
              AND segment.status = ANY(%s)
              AND segment.start_time < %s
              AND segment.end_time > %s
            ORDER BY
                occurrence.id,
                segment.start_time,
                segment.end_time,
                segment.id
            """,
            (
                occurrence_date,
                occurrence_id,
                sorted(blocking_statuses),
                end_time,
                start_time,
            ),
        )
        return cursor.fetchall()


def update_segment_status(connection, segment_id, status):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.occurrence_segments
            SET status = %s
            WHERE id = %s
            """,
            (status, segment_id),
        )
        return cursor.rowcount


def update_occurrence_status(connection, occurrence_id, status):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.occurrences
            SET status = %s
            WHERE id = %s
            """,
            (status, occurrence_id),
        )
        return cursor.rowcount


def lock_historical_occurrences(connection, today):
    """Bloquea primero todos los parents históricos en orden UUID estable."""
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
            WHERE occurrence_date < %s
            ORDER BY id
            FOR UPDATE
            """,
            (today,),
        )
        return cursor.fetchall()


def lock_segments_for_occurrences(connection, occurrence_ids):
    if not occurrence_ids:
        return []
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT id, occurrence_id, start_time, end_time, status
            FROM public.occurrence_segments
            WHERE occurrence_id = ANY(%s::uuid[])
            ORDER BY occurrence_id, start_time, end_time, id
            FOR UPDATE
            """,
            (occurrence_ids,),
        )
        return cursor.fetchall()


def lock_external_blockers_for_candidates(
    connection, occurrence_id, occurrence_date, candidate_segments, blocking_statuses
):
    """Bloquea en orden todos los blockers reales del set candidato ocupante."""
    if not candidate_segments:
        return []
    starts = [segment["startTime"] for segment in candidate_segments]
    ends = [segment["endTime"] for segment in candidate_segments]
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                occurrence.id AS occurrence_id,
                occurrence.plan_item_id,
                occurrence.occurrence_date,
                segment.id AS segment_id,
                segment.start_time,
                segment.end_time,
                segment.status
            FROM public.occurrence_segments AS segment
            INNER JOIN public.occurrences AS occurrence
                ON occurrence.id = segment.occurrence_id
            WHERE occurrence.occurrence_date = %s
              AND occurrence.id <> %s
              AND segment.status = ANY(%s)
              AND EXISTS (
                  SELECT 1
                  FROM unnest(%s::time[], %s::time[])
                      AS candidate(start_time, end_time)
                  WHERE segment.start_time < candidate.end_time
                    AND segment.end_time > candidate.start_time
              )
            ORDER BY occurrence.id, segment.start_time, segment.end_time, segment.id
            FOR UPDATE OF segment
            """,
            (
                occurrence_date,
                occurrence_id,
                sorted(blocking_statuses),
                starts,
                ends,
            ),
        )
        return cursor.fetchall()


def update_segment_times(connection, segment_id, occurrence_id, start_time, end_time):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.occurrence_segments
            SET start_time = %s, end_time = %s
            WHERE id = %s AND occurrence_id = %s
            """,
            (start_time, end_time, segment_id, occurrence_id),
        )
        return cursor.rowcount


def insert_segment(connection, segment, occurrence_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.occurrence_segments
                (id, occurrence_id, start_time, end_time, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                segment["id"],
                occurrence_id,
                segment["startTime"],
                segment["endTime"],
                segment["status"],
            ),
        )
        return cursor.rowcount


def delete_segments(connection, occurrence_id, segment_ids):
    if not segment_ids:
        return 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM public.occurrence_segments
            WHERE occurrence_id = %s AND id = ANY(%s::uuid[])
            """,
            (occurrence_id, segment_ids),
        )
        return cursor.rowcount


def update_occurrence_structure(
    connection, occurrence_id, start_time, end_time, aggregate
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.occurrences
            SET start_time = %s, end_time = %s, status = %s
            WHERE id = %s
            """,
            (start_time, end_time, aggregate, occurrence_id),
        )
        return cursor.rowcount
