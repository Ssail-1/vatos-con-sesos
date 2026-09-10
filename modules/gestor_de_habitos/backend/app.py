"""Aplicación HTTP para exponer el backend mínimo del Gestor de hábitos."""

from flask import Flask, jsonify

import database
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
