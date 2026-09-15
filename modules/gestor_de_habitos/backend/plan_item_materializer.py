"""Materialización pura del contrato canónico de generationConfig."""

from calendar import monthrange
from datetime import date, timedelta


def _month_start(value):
    return value.replace(day=1)


def _month_end(value, month_offset=0):
    month_index = value.year * 12 + value.month - 1 + month_offset
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    return date(year, month, monthrange(year, month)[1])


def get_materialization_range(plan_item, reference_date):
    """Replica el rango que usa el store al crear un PlanItem."""
    config = plan_item["generationConfig"]
    if config["mode"] == "manual_dates":
        dates = [date.fromisoformat(entry["date"]) for entry in config["entries"]]
        return min(dates), max(dates)
    if config["indefinite"]:
        return _month_start(reference_date), _month_end(reference_date, 1)
    return date.fromisoformat(config["startDate"]), date.fromisoformat(
        config["endDate"]
    )


def _draft(
    plan_item_id,
    source_generation_slot_id,
    occurrence_date,
    start_time,
    end_time,
):
    return {
        "planItemId": plan_item_id,
        "sourceGenerationSlotId": source_generation_slot_id,
        "date": occurrence_date.isoformat(),
        "startTime": start_time,
        "endTime": end_time,
        "status": "pending",
    }


def materialize_occurrence_drafts(plan_item, range_start, range_end):
    """Genera las mismas occurrences base que materializer.js para un rango."""
    config = plan_item["generationConfig"]
    mode = config["mode"]
    drafts = []

    if mode == "weekly":
        configured_start = date.fromisoformat(config["startDate"])
        effective_start = max(configured_start, range_start)
        configured_end = (
            range_end
            if config["indefinite"]
            else date.fromisoformat(config["endDate"])
        )
        effective_end = min(configured_end, range_end)
        current_date = effective_start
        while current_date <= effective_end:
            weekday = current_date.isoweekday()
            for slot in config["slots"]:
                if slot["isoWeekday"] != weekday:
                    continue
                drafts.append(
                    _draft(
                        plan_item["id"],
                        slot["id"],
                        current_date,
                        slot["startTime"],
                        slot["endTime"],
                    )
                )
            current_date += timedelta(days=1)

    elif mode == "interval_days":
        current_date = date.fromisoformat(config["startDate"])
        configured_end = (
            range_end
            if config["indefinite"]
            else date.fromisoformat(config["endDate"])
        )
        effective_end = min(configured_end, range_end)
        step = timedelta(days=config["intervalDays"])
        while current_date <= effective_end:
            if current_date >= range_start:
                for slot in config["slots"]:
                    drafts.append(
                        _draft(
                            plan_item["id"],
                            slot["id"],
                            current_date,
                            slot["startTime"],
                            slot["endTime"],
                        )
                    )
            current_date += step

    elif mode == "manual_dates":
        for entry in config["entries"]:
            entry_date = date.fromisoformat(entry["date"])
            if range_start <= entry_date <= range_end:
                drafts.append(
                    _draft(
                        plan_item["id"],
                        entry["id"],
                        entry_date,
                        entry["startTime"],
                        entry["endTime"],
                    )
                )

    excluded_dates = set(config.get("excludedDates", []))
    stopped_from_date = config.get("stoppedFromDate")
    return [
        draft
        for draft in drafts
        if draft["date"] not in excluded_dates
        and (stopped_from_date is None or draft["date"] < stopped_from_date)
    ]
