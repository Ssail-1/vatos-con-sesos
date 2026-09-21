"""Aplicación HTTP para exponer el backend mínimo del Gestor de hábitos."""

import os

from flask import Flask, jsonify, request

import database
import future_schedule_service
import occurrence_mutation_service
import occurrence_segment_service
import occurrence_structure_service
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
def add_frontend_cors(response):
    """Permite solo las operaciones frontend conectadas y autorizadas."""
    origin = request.headers.get("Origin")
    if origin not in _allowed_frontend_origins():
        return response
    planner_read = (
        request.method == "GET" and request.path == "/api/planner-state"
    )
    plan_item_creation = (
        request.method in {"POST", "OPTIONS"}
        and request.path == "/api/plan-items"
    )
    occurrence_mutation = (
        request.method in {"PATCH", "DELETE", "OPTIONS"}
        and request.path.startswith("/api/occurrences/")
        and request.path.count("/") == 3
    )
    structural_mutation = (
        request.path.startswith("/api/occurrences/")
        and request.path.count("/") == 4
        and (
            (
                request.path.endswith("/structure")
                and request.method in {"PUT", "OPTIONS"}
            )
            or (
                request.path.rsplit("/", 1)[-1] in {"translate", "reset-segmentation"}
                and request.method in {"POST", "OPTIONS"}
            )
        )
    )
    recurring_schedule_mutation = (
        request.method in {"POST", "OPTIONS"}
        and request.path.startswith("/api/plan-items/")
        and request.path.count("/") == 4
        and request.path.rsplit("/", 1)[-1] in {"apply-week", "apply-future"}
    )
    segment_status_mutation = (
        request.method in {"PATCH", "OPTIONS"}
        and request.path.startswith("/api/occurrence-segments/")
        and request.path.count("/") == 4
        and request.path.endswith("/status")
    )
    planner_reconciliation = (
        request.method in {"POST", "OPTIONS"}
        and request.path == "/api/planner/reconcile"
    )
    if (
        not planner_read
        and not plan_item_creation
        and not occurrence_mutation
        and not structural_mutation
        and not recurring_schedule_mutation
        and not segment_status_mutation
        and not planner_reconciliation
    ):
        return response
    response.headers["Access-Control-Allow-Origin"] = origin
    response.vary.add("Origin")
    if plan_item_creation:
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    if occurrence_mutation:
        response.headers["Access-Control-Allow-Methods"] = "PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    if structural_mutation:
        response.headers["Access-Control-Allow-Methods"] = (
            "PUT, OPTIONS" if request.path.endswith("/structure") else "POST, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    if recurring_schedule_mutation:
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    if segment_status_mutation:
        response.headers["Access-Control-Allow-Methods"] = "PATCH, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    if planner_reconciliation:
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
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
        body = dict(
            status="error",
            code=error.code,
            message=str(error),
        )
        if error.conflicts is not None:
            body["conflicts"] = error.conflicts
        return jsonify(body), 409
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


def _occurrence_segment_error_response(error):
    if isinstance(
        error, occurrence_segment_service.OccurrenceSegmentValidationError
    ):
        return jsonify(
            status="error",
            code="invalid_payload",
            message="El identificador o payload de OccurrenceSegment no es válido.",
        ), 400
    if isinstance(
        error, occurrence_segment_service.OccurrenceSegmentNotFoundError
    ):
        return jsonify(
            status="error",
            code="segment_not_found",
            message="El OccurrenceSegment no existe.",
        ), 404
    if isinstance(error, occurrence_segment_service.OccurrenceSegmentConflictError):
        body = {
            "status": "error",
            "code": error.code,
            "message": str(error),
        }
        if error.blockers is not None:
            body["blockers"] = error.blockers
        return jsonify(body), 409
    if isinstance(
        error, occurrence_segment_service.OccurrenceSegmentConsistencyError
    ):
        return jsonify(
            status="error",
            code="persisted_state_invalid",
            message="El estado persistido del planner no es válido.",
        ), 500
    return jsonify(
        status="error",
        code="database_unavailable",
        message="No se pudo completar la operación de OccurrenceSegment.",
    ), 503


@app.patch("/api/occurrence-segments/<segment_id>/status")
def patch_occurrence_segment_status(segment_id):
    try:
        result = occurrence_segment_service.mutate_segment_status(
            segment_id, request.get_json(silent=True)
        )
    except occurrence_segment_service.OccurrenceSegmentServiceError as error:
        return _occurrence_segment_error_response(error)
    return jsonify(result)


@app.post("/api/planner/reconcile")
def reconcile_planner():
    try:
        result = occurrence_segment_service.reconcile_planner(
            request.get_json(silent=True)
        )
    except occurrence_segment_service.OccurrenceSegmentServiceError as error:
        return _occurrence_segment_error_response(error)
    return jsonify(result)


def _occurrence_structure_error_response(error):
    if isinstance(error, occurrence_structure_service.OccurrenceStructureValidationError):
        return jsonify(status="error", code=error.code, message=str(error)), 400
    if isinstance(error, occurrence_structure_service.OccurrenceStructureNotFoundError):
        return jsonify(
            status="error", code="occurrence_not_found", message="La occurrence no existe."
        ), 404
    if isinstance(error, occurrence_structure_service.OccurrenceStructureConflictError):
        body = {"status": "error", "code": error.code, "message": str(error)}
        if error.blockers is not None:
            body["blockers"] = error.blockers
        return jsonify(body), 409
    if isinstance(error, occurrence_structure_service.OccurrenceStructureConsistencyError):
        return jsonify(
            status="error", code="persisted_state_invalid",
            message="El estado persistido del planner no es válido.",
        ), 500
    return jsonify(
        status="error", code="database_unavailable",
        message="No se pudo completar la operación estructural.",
    ), 503


@app.post("/api/occurrences/<occurrence_id>/translate")
def translate_occurrence(occurrence_id):
    try:
        result = occurrence_structure_service.translate_occurrence(
            occurrence_id, request.get_json(silent=True)
        )
    except occurrence_structure_service.OccurrenceStructureError as error:
        return _occurrence_structure_error_response(error)
    return jsonify(result)


@app.put("/api/occurrences/<occurrence_id>/structure")
def replace_occurrence_structure(occurrence_id):
    try:
        result = occurrence_structure_service.replace_occurrence_structure(
            occurrence_id, request.get_json(silent=True)
        )
    except occurrence_structure_service.OccurrenceStructureError as error:
        return _occurrence_structure_error_response(error)
    return jsonify(result)


@app.post("/api/occurrences/<occurrence_id>/reset-segmentation")
def reset_occurrence_segmentation(occurrence_id):
    try:
        result = occurrence_structure_service.reset_occurrence_segmentation(
            occurrence_id, request.get_json(silent=True)
        )
    except occurrence_structure_service.OccurrenceStructureError as error:
        return _occurrence_structure_error_response(error)
    return jsonify(result)


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
        body = {"status": "error", "code": error.code, "message": str(error)}
        if error.occurrences is not None:
            body["occurrences"] = error.occurrences
        if error.blockers is not None:
            body["blockers"] = error.blockers
        return jsonify(body), 409
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
        body = {"status": "error", "code": error.code, "message": str(error)}
        if error.occurrences is not None:
            body["occurrences"] = error.occurrences
        if error.blockers is not None:
            body["blockers"] = error.blockers
        return jsonify(body), 409
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
