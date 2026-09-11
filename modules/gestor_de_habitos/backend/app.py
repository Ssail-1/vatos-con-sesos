"""Aplicación HTTP para exponer el backend mínimo del Gestor de hábitos."""

from flask import Flask, jsonify, request

import database
import plan_item_creation_service
import planner_state_service
from repositories import plan_item_repository


app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
