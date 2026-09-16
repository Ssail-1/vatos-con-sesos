"""Reglas compartidas de conflicto, prioridad e integridad temporal."""

from datetime import timedelta


HISTORY_EDIT_WINDOW_DAYS = 1
BLOCKING_STATUSES = frozenset({"pending", "in_progress", "completed"})


def time_ranges_overlap(first_start, first_end, second_start, second_end):
    """Los intervalos son semiabiertos: los extremos contiguos no chocan."""
    return first_start < second_end and first_end > second_start


def occurrence_items_overlap(first, second):
    return first["date"] == second["date"] and time_ranges_overlap(
        first["startTime"],
        first["endTime"],
        second["startTime"],
        second["endTime"],
    )


def scheduling_priority(kind, subtype):
    if kind == "activity" and subtype == "unexpected":
        return 300
    if kind == "activity" and subtype == "event":
        return 200
    return 100


def is_frozen_date(value, reference_date):
    return value < reference_date - timedelta(days=HISTORY_EDIT_WINDOW_DAYS)


def can_delete_occurrence(value, status, reference_date):
    if is_frozen_date(value, reference_date):
        return False
    if value > reference_date:
        return status in {"pending", "cancelled"}
    return status == "pending"
