"""Aplicación HTTP para exponer el backend mínimo del Gestor de hábitos."""

import os

from flask import Flask, jsonify, request

import database
import future_schedule_service
import occurrence_mutation_service
import plan_item_creation_service
import planner_state_service
import week_mutation_service
from repositories import plan_item_repository


app = Flask(__name__)


def _allowed_frontend_origins():
    return {
        origin.strip()
        for origin in os.getenv("VCS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    }


@app.after_request
def add_planner_state_cors(response):
    """Permite únicamente la lectura inicial desde orígenes autorizados."""
    origin = request.headers.get("Origin")
    if (
        request.method == "GET"
        and request.path == "/api/planner-state"
        and origin in _allowed_frontend_origins()
    ):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.vary.add("Origin")
    return response


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/health/db")
def database_health():
    try:
        database.check_connection()
    except database.DatabaseConnectionError:
        return jsonify(
            status="error",
            database="unavailable",
            message="No se pudo verificar la conexión con PostgreSQL.",
        ), 503
    return jsonify(status="ok", database="ok")


def serialize_plan_item(plan_item):
    """Convierte tipos nativos de PostgreSQL a valores JSON explícitos."""
    return {
        "id": str(plan_item["id"]),
        "name": plan_item["name"],
        "kind": plan_item["kind"],
        "subtype": plan_item["subtype"],
        "created_at": plan_item["created_at"].isoformat(),
    }


@app.get("/api/plan-items")
def get_plan_items():
    try:
        plan_items = plan_item_repository.list_plan_items()
    except plan_item_repository.PlanItemRepositoryError:
        return jsonify(
            status="error",
            message="No se pudieron obtener los PlanItems.",
        ), 503
    return jsonify([serialize_plan_item(plan_item) for plan_item in plan_items])


@app.post("/api/plan-items")
def create_plan_item():
    payload = request.get_json(silent=True)
    try:
        result = plan_item_creation_service.create_plan_item(payload)
    except plan_item_creation_service.PlanItemValidationError:
        return jsonify(
            status="error",
            code="invalid_payload",
            message="El PlanItem enviado no es válido.",
        ), 400
    except plan_item_creation_service.PlanItemConflictError as error:
        return jsonify(
            status="error",
            code=error.code,
            message=str(error),
        ), 409
    except plan_item_creation_service.PlanItemCreationUnavailableError:
        return jsonify(
            status="error",
            code="database_unavailable",
            message="No se pudo crear el PlanItem.",
        ), 503
    return jsonify(result), 201


@app.get("/api/planner-state")
def get_planner_state():
    try:
        planner_state = planner_state_service.get_planner_state()
    except planner_state_service.PlannerStateUnavailableError:
        return jsonify(
            status="error",
            message="No se pudo cargar el estado del planner.",
        ), 503
    except planner_state_service.PlannerStateConsistencyError:
        return jsonify(
            status="error",
            message="El estado persistido del planner no es válido.",
        ), 500
    return jsonify(planner_state)


def _occurrence_mutation_error_response(error):
    if isinstance(error, occurrence_mutation_service.OccurrenceValidationError):
        return jsonify(
            status="error",
            code="invalid_payload",
            message="El identificador o payload de la occurrence no es válido.",
        ), 400
    if isinstance(error, occurrence_mutation_service.OccurrenceNotFoundError):
        return jsonify(
            status="error",
            code="occurrence_not_found",
            message="La occurrence no existe.",
        ), 404
    if isinstance(error, occurrence_mutation_service.OccurrenceConflictError):
        return jsonify(status="error", code=error.code, message=str(error)), 409
    if isinstance(error, occurrence_mutation_service.OccurrenceConsistencyError):
        return jsonify(
            status="error",
            code="persisted_state_invalid",
            message="El estado persistido del planner no es válido.",
        ), 500
    return jsonify(
        status="error",
        code="database_unavailable",
        message="No se pudo completar la operación sobre la occurrence.",
    ), 503


@app.patch("/api/occurrences/<occurrence_id>")
def patch_occurrence(occurrence_id):
    try:
        result = occurrence_mutation_service.patch_occurrence(
            occurrence_id, request.get_json(silent=True)
        )
    except occurrence_mutation_service.OccurrenceMutationError as error:
        return _occurrence_mutation_error_response(error)
    return jsonify(result)


@app.delete("/api/occurrences/<occurrence_id>")
def delete_occurrence(occurrence_id):
    try:
        result = occurrence_mutation_service.delete_occurrence(occurrence_id)
    except occurrence_mutation_service.OccurrenceMutationError as error:
        return _occurrence_mutation_error_response(error)
    return jsonify(result)


def _week_mutation_error_response(error):
    if isinstance(error, week_mutation_service.WeekValidationError):
        return jsonify(
            status="error",
            code=error.code,
            message="El identificador o payload de Apply Week no es válido.",
        ), 400
    if isinstance(error, week_mutation_service.WeekPlanItemNotFoundError):
        return jsonify(
            status="error",
            code="plan_item_not_found",
            message="El PlanItem no existe.",
        ), 404
    if isinstance(error, week_mutation_service.WeekOccurrenceNotFoundError):
        return jsonify(
            status="error",
            code="occurrence_not_found",
            message="Una occurrence no existe en la semana solicitada.",
        ), 404
    if isinstance(error, week_mutation_service.WeekConflictError):
        return jsonify(status="error", code=error.code, message=str(error)), 409
    if isinstance(error, week_mutation_service.WeekConsistencyError):
        return jsonify(
            status="error",
            code="persisted_state_invalid",
            message="El estado persistido del planner no es válido.",
        ), 500
    return jsonify(
        status="error",
        code="database_unavailable",
        message="No se pudo aplicar el cambio semanal.",
    ), 503


@app.post("/api/plan-items/<plan_item_id>/apply-week")
def apply_week(plan_item_id):
    try:
        result = week_mutation_service.apply_week(
            plan_item_id, request.get_json(silent=True)
        )
    except week_mutation_service.WeekMutationError as error:
        return _week_mutation_error_response(error)
    return jsonify(result)


def _future_schedule_error_response(error):
    if isinstance(error, future_schedule_service.FutureValidationError):
        return jsonify(
            status="error",
            code=error.code,
            message="El identificador o payload de Apply Future no es válido.",
        ), 400
    if isinstance(error, future_schedule_service.FuturePlanItemNotFoundError):
        return jsonify(
            status="error",
            code="plan_item_not_found",
            message="El PlanItem no existe.",
        ), 404
    if isinstance(error, future_schedule_service.FutureConflictError):
        return jsonify(status="error", code=error.code, message=str(error)), 409
    if isinstance(error, future_schedule_service.FutureConsistencyError):
        return jsonify(
            status="error",
            code="persisted_state_invalid",
            message="El estado persistido del planner no es válido.",
        ), 500
    return jsonify(
        status="error",
        code="database_unavailable",
        message="No se pudo aplicar la planificación futura.",
    ), 503


@app.post("/api/plan-items/<plan_item_id>/apply-future")
def apply_future(plan_item_id):
    try:
        result = future_schedule_service.apply_future(
            plan_item_id, request.get_json(silent=True)
        )
    except future_schedule_service.FutureScheduleError as error:
        return _future_schedule_error_response(error)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
