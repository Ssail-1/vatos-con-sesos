# Instalación local y pruebas

[Presentación](/README.md) · [Funcionamiento](/docs/funcionamiento.md) · [Modelo PostgreSQL](/modules/gestor_de_habitos/db/README.md)

Los comandos siguientes se ejecutan desde la raíz del repositorio, salvo donde
se indique lo contrario. La preparación de PostgreSQL utiliza como ejemplo
Linux con una instalación local administrada mediante el usuario `postgres`.

## 1. Requisitos y dependencias

- Python 3.10 o posterior, con `pip` y `venv` disponibles.
- PostgreSQL 16 en ejecución y sus herramientas de línea de comandos.
- Extensión `btree_gist` disponible en la instalación de PostgreSQL; la migración
  004 la crea en la base de datos.
- Un navegador moderno. Node.js 22.19 o posterior para ejecutar las pruebas JS.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r modules/gestor_de_habitos/backend/requirements.txt
```

## 2. Preparar una base de datos nueva

El código actual requiere las migraciones **001 a 005**, en ese orden. Para una
instalación nueva, crea un rol local sin privilegios de superusuario y una base
vacía de su propiedad. La contraseña se introduce de forma interactiva:

```bash
sudo -u postgres createuser --pwprompt --no-superuser --no-createdb --no-createrole vcs_app
sudo -u postgres createdb --owner=vcs_app vcs_dev
```

Si esos nombres ya existen, comprueba su configuración y el esquema antes de
continuar. **No repitas estas migraciones sobre una base ya inicializada.** Para
una base con datos, prepara un respaldo y revisa primero las migraciones pendientes.

Solo sobre la base nueva y vacía, aplica los archivos con parada ante el primer error:

```bash
psql -X -h localhost -U vcs_app -d vcs_dev -v ON_ERROR_STOP=1 \
  -f modules/gestor_de_habitos/db/migrations/001_initial_schema.sql \
  -f modules/gestor_de_habitos/db/migrations/002_fix_occurrence_status_context.sql \
  -f modules/gestor_de_habitos/db/migrations/003_multi_slot_scheduling.sql \
  -f modules/gestor_de_habitos/db/migrations/004_occurrence_segments.sql \
  -f modules/gestor_de_habitos/db/migrations/005_generation_slot_cutoff.sql
```

Cada archivo delimita su propia transacción. Si uno falla, los anteriores pueden
haber quedado aplicados: revisa el estado antes de reintentar.
Consulta también la [documentación de la base de datos](/modules/gestor_de_habitos/db/README.md).

## 3. Configurar la conexión

Si todavía no tienes un `.env` local, copia la plantilla:

```bash
cp -n modules/gestor_de_habitos/backend/.env.example modules/gestor_de_habitos/backend/.env
```

Edita ese `.env` local para configurar `DATABASE_URL` con tu rol, contraseña y
base de datos. Si la contraseña contiene caracteres reservados de una URL,
codifícalos en el componente correspondiente. No compartas ni versiones ese archivo.
Las variables ya definidas en el entorno tienen prioridad sobre `.env`.

La plantilla permite los orígenes `http://127.0.0.1:8000` y
`http://localhost:8000` mediante `VCS_ALLOWED_ORIGINS`. Si cambias el puerto del
frontend, actualiza también esa configuración.

## 4. Iniciar backend y frontend

En una terminal, con el entorno virtual activo:

```bash
cd modules/gestor_de_habitos/backend
flask --app app run --host 127.0.0.1 --port 5000
```

En otra terminal, desde la raíz del repositorio:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

- Portada y Dev Notes: <http://127.0.0.1:8000/>.
- Gestor conectado: <http://127.0.0.1:8000/modules/gestor_de_habitos/index.html?apiBaseUrl=http://127.0.0.1:5000>.
- Comprobación de conexión a PostgreSQL: <http://127.0.0.1:5000/api/health/db>.

Usa el enlace completo del gestor: `apiBaseUrl` indica dónde está Flask cuando
los dos servidores usan puertos diferentes. El enlace de la portada no agrega
ese parámetro. El gestor necesita el backend y la base de datos; sus fixtures
de pruebas no se cargan como demostración automática.

Estos servidores son para desarrollo local. Al abrir el gestor, la reconciliación
puede actualizar estados en la base configurada.

**Alcance de verificación de esta guía:** las rutas, opciones de los comandos y
variables se contrastaron con el código y las herramientas locales. Queda pendiente
validar la instalación completa en un entorno limpio; para preparar esta guía
no se ejecutaron migraciones ni se inició la aplicación.

## 5. Pruebas

Desde la raíz, con Node.js disponible:

```bash
(
  for test_file in modules/gestor_de_habitos/tests/*.test.mjs; do
    node "$test_file" || exit 1
  done
)
```

Para ejecutar las pruebas Python sin activar las integraciones PostgreSQL:

```bash
env -u VCS_TEST_DATABASE_URL .venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend -p 'test_*.py'
```

Las pruebas de integración requieren `VCS_TEST_DATABASE_URL` y una base
**desechable de pruebas**, con nombre `vcs_test_…`: recrean esquemas y eliminan
datos. No deben apuntar a la base de uso personal. Existen además pruebas de
migración en `modules/gestor_de_habitos/db/test_migration_004.py`.

## Alcance y seguridad

El backend actual no incluye autenticación ni autorización por usuario. Esta guía
es para un entorno local; publicar el código no equivale a disponer de un
despliegue seguro. Antes de abrir el backend a otras personas se requieren esos
controles y una configuración de producción. CORS no sustituye la autorización.

Los archivos `.env`, respaldos y logs deben permanecer privados. Las reglas de
[`.gitignore`](/.gitignore) ayudan a evitar incorporaciones accidentales, pero no
retiran datos que ya estén presentes en el historial Git. Guarda los respaldos
fuera del repositorio.
