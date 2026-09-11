"""SQL de lectura y creación de PlanItems."""

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


def list_blocking_occurrences(connection, occurrence_dates):
    """Bloquea y devuelve occurrences que pueden impedir la creación."""
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
            WHERE occurrence.occurrence_date = ANY(%s::date[])
              AND occurrence.status IN ('pending', 'in_progress', 'completed')
            ORDER BY
                occurrence.occurrence_date,
                occurrence.start_time,
                occurrence.end_time,
                occurrence.id
            FOR UPDATE OF occurrence
            """,
            (occurrence_dates,),
        )
        return cursor.fetchall()


def insert_plan_item_graph(connection, plan_item, occurrences, entry_ids):
    """Inserta el agregado completo usando la transacción de la conexión recibida."""
    config = plan_item["generationConfig"]
    subtype = (
        plan_item["activityType"]
        if plan_item["kind"] == "activity"
        else plan_item["habitType"]
    )
    recurring = config["mode"] in {"weekly", "interval_days"}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.plan_items (id, name, kind, subtype)
            VALUES (%s, %s, %s, %s)
            """,
            (plan_item["id"], plan_item["name"], plan_item["kind"], subtype),
        )
        cursor.execute(
            """
            INSERT INTO public.generation_configs (
                plan_item_id,
                mode,
                start_date,
                end_date,
                indefinite,
                default_start_time,
                default_end_time,
                interval_days,
                stopped_from_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                plan_item["id"],
                config["mode"],
                config.get("startDate") if recurring else None,
                config.get("endDate") if recurring else None,
                config["indefinite"] if recurring else False,
                config.get("defaultStartTime") if recurring else None,
                config.get("defaultEndTime") if recurring else None,
                config.get("intervalDays")
                if config["mode"] == "interval_days"
                else None,
                config.get("stoppedFromDate"),
            ),
        )

        if config["mode"] == "weekly":
            cursor.executemany(
                """
                INSERT INTO public.generation_weekdays (
                    plan_item_id,
                    iso_weekday,
                    override_start_time,
                    override_end_time
                )
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (
                        plan_item["id"],
                        weekday,
                        config["weekdayTimeOverrides"].get(str(weekday), {}).get(
                            "startTime"
                        ),
                        config["weekdayTimeOverrides"].get(str(weekday), {}).get(
                            "endTime"
                        ),
                    )
                    for weekday in config["weekdays"]
                ],
            )

        if config["mode"] == "manual_dates":
            cursor.executemany(
                """
                INSERT INTO public.generation_date_entries (
                    id,
                    plan_item_id,
                    entry_date,
                    start_time,
                    end_time
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        entry_id,
                        plan_item["id"],
                        entry["date"],
                        entry["startTime"],
                        entry["endTime"],
                    )
                    for entry_id, entry in zip(entry_ids, config["entries"])
                ],
            )

        if config.get("excludedDates"):
            cursor.executemany(
                """
                INSERT INTO public.generation_excluded_dates (
                    plan_item_id,
                    excluded_date
                )
                VALUES (%s, %s)
                """,
                [
                    (plan_item["id"], excluded_date)
                    for excluded_date in config["excludedDates"]
                ],
            )

        if occurrences:
            cursor.executemany(
                """
                INSERT INTO public.occurrences (
                    id,
                    plan_item_id,
                    occurrence_date,
                    start_time,
                    end_time,
                    status,
                    status_reason,
                    source_occurrence_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL)
                """,
                [
                    (
                        occurrence["id"],
                        occurrence["planItemId"],
                        occurrence["date"],
                        occurrence["startTime"],
                        occurrence["endTime"],
                        occurrence["status"],
                    )
                    for occurrence in occurrences
                ],
            )
