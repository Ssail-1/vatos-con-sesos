"""Lectura de PlanItems desde PostgreSQL."""

import psycopg
from psycopg.rows import dict_row

import database


class PlanItemRepositoryError(RuntimeError):
    """Error seguro al consultar PlanItems."""


def list_plan_items():
    """Devuelve todos los PlanItems en un orden estable."""
    try:
        with database.get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, kind, subtype, created_at
                    FROM public.plan_items
                    ORDER BY created_at, id
                    """
                )
                return cursor.fetchall()
    except (database.DatabaseConnectionError, psycopg.Error):
        # Los errores del driver pueden incluir host, usuario u otros datos privados.
        raise PlanItemRepositoryError(
            "No se pudieron consultar los PlanItems."
        ) from None
