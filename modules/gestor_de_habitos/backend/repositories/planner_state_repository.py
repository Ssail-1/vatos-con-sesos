"""Lectura coordinada de las tablas que forman el estado del planner."""

import psycopg
from psycopg.rows import dict_row

import database


class PlannerStateRepositoryError(RuntimeError):
    """Error seguro al leer el estado persistido."""


_QUERIES = (
    (
        "plan_items",
        """
        SELECT id, name, kind, subtype, created_at
        FROM public.plan_items
        ORDER BY created_at, id
        """,
    ),
    (
        "generation_configs",
        """
        SELECT
            plan_item_id,
            mode,
            start_date,
            end_date,
            indefinite,
            interval_days,
            stopped_from_date
        FROM public.generation_configs
        ORDER BY plan_item_id
        """,
    ),
    (
        "generation_slots",
        """
        SELECT id, plan_item_id, start_time, end_time, last_generation_date
        FROM public.generation_slots
        ORDER BY plan_item_id, start_time, end_time, id
        """,
    ),
    (
        "generation_slot_weekdays",
        """
        SELECT slot_id, iso_weekday
        FROM public.generation_slot_weekdays
        ORDER BY slot_id
        """,
    ),
    (
        "generation_slot_dates",
        """
        SELECT slot_id, entry_date
        FROM public.generation_slot_dates
        ORDER BY slot_id
        """,
    ),
    (
        "generation_slot_excluded_dates",
        """
        SELECT slot_id, excluded_date
        FROM public.generation_slot_excluded_dates
        ORDER BY slot_id, excluded_date
        """,
    ),
    (
        "generation_excluded_dates",
        """
        SELECT plan_item_id, excluded_date
        FROM public.generation_excluded_dates
        ORDER BY plan_item_id, excluded_date
        """,
    ),
    (
        "occurrences",
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
        ORDER BY occurrence_date, start_time, end_time, id
        """,
    ),
    (
        "occurrence_segments",
        """
        SELECT id, occurrence_id, start_time, end_time, status
        FROM public.occurrence_segments
        ORDER BY occurrence_id, start_time, end_time, id
        """,
    ),
)


def read_planner_state_rows():
    """Lee todas las tablas con una sola vista repeatable-read y read-only."""
    try:
        with database.get_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                    )
                    result = {}
                    for collection_name, query in _QUERIES:
                        cursor.execute(query)
                        result[collection_name] = cursor.fetchall()
                    return result
    except (database.DatabaseConnectionError, psycopg.Error):
        # Los detalles del driver pueden contener datos privados de conexión.
        raise PlannerStateRepositoryError(
            "No se pudo leer el estado persistido."
        ) from None
