"""Conexión PostgreSQL y comprobación mínima, sin reglas de dominio."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


class DatabaseConnectionError(RuntimeError):
    """Error seguro para comunicar sin revelar datos de conexión."""


def get_database_url():
    # La ruta no depende del directorio desde el que se ejecute Flask.
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise DatabaseConnectionError(
            "Falta DATABASE_URL. Configúrala en el entorno o en backend/.env."
        )
    return database_url


def get_connection():
    """Abre una conexión; usar con `with` para cerrarla también ante errores."""
    try:
        return psycopg.connect(get_database_url(), connect_timeout=5)
    except psycopg.Error:
        # El mensaje original del driver puede contener información privada.
        raise DatabaseConnectionError("No se pudo conectar con PostgreSQL.") from None


def check_connection():
    """Ejecuta SELECT 1 y libera cursor y conexión al salir."""
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise DatabaseConnectionError(
                        "PostgreSQL no devolvió el resultado esperado."
                    )
    except psycopg.Error:
        raise DatabaseConnectionError("No se pudo verificar PostgreSQL.") from None
