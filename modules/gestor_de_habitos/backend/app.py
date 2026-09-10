"""Aplicación HTTP mínima para comprobar Flask y PostgreSQL local."""

from flask import Flask, jsonify

import database


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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
