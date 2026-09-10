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
            default_start_time,
            default_end_time,
            interval_days,
            stopped_from_date
        FROM public.generation_configs
        ORDER BY plan_item_id
        """,
    ),
    (
        "generation_weekdays",
        """
        SELECT
            plan_item_id,
            iso_weekday,
            override_start_time,
            override_end_time
        FROM public.generation_weekdays
        ORDER BY plan_item_id, iso_weekday
        """,
    ),
    (
        "generation_date_entries",
        """
        SELECT id, plan_item_id, entry_date, start_time, end_time
        FROM public.generation_date_entries
        ORDER BY plan_item_id, entry_date, start_time, end_time, id
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
            status_reason,
            source_occurrence_id
        FROM public.occurrences
        ORDER BY occurrence_date, start_time, end_time, id
        """,
    ),
)


def read_planner_state_rows():
    """Lee todas las tablas del estado usando una sola conexión."""
    try:
        with database.get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
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
