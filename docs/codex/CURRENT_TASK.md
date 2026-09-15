# CURRENT TASK

## MVP 05.6.3 — Backend multi-slot + JS/Python parity

### Documento normativo

La especificación global de multi-slot está en:

`docs/codex/gestor_de_habitos/planeacion/MVP_05_6/MULTI_SLOT_SCHEDULING.md`

Este `CURRENT_TASK.md` define únicamente la fase activa:

```text
MVP 05.6.3
Backend read/create multi-slot + Python materializer + JS/Python parity
```

Estado actual:

```text
Frontend/domain JavaScript
→ MVP 05.6.1 multi-slot ✅

PostgreSQL schema/migration
→ MVP 05.6.2 multi-slot ✅

Backend Python
→ todavía contrato MVP 05.5 ⏳
```

Objetivo de esta fase:

```text
Frontend
PostgreSQL
Backend
```

deben volver a compartir el mismo contrato canónico multi-slot.

---

# 1. Objetivo

Adaptar el backend Flask/Python para trabajar con el modelo relacional
introducido por:

```text
003_multi_slot_scheduling.sql
```

Debe actualizarse:

```text
GET /api/planner-state
POST /api/plan-items
Python materializer
repositories
validaciones
tests
JS/Python parity
```

Al terminar esta fase:

```text
Frontend/domain
Backend/API
PostgreSQL schema
```

deben entender el mismo modelo de GenerationSlots.

---

# 2. Alcance

Puede modificarse lo necesario dentro de:

```text
modules/gestor_de_habitos/backend/
```

incluyendo:

```text
app.py
repositories/
services
materializer Python
tests backend
```

Puede agregarse/modificarse código backend cuando sea necesario.

Puede utilizarse:

```text
modules/gestor_de_habitos/tests/
```

únicamente si hace falta adaptar o ampliar fixtures de paridad
JavaScript ↔ Python sin cambiar la semántica frontend ya aprobada.

NO modificar por iniciativa propia:

```text
frontend funcional MVP 05.6.1
migraciones 001
migración 002
migración 003
vcs_dev
```

---

# 3. Fuente de verdad contractual

El contrato canónico está definido por:

```text
MVP 05.6.1
+
MULTI_SLOT_SCHEDULING.md
```

Los únicos modos siguen siendo:

```text
weekly
interval_days
manual_dates
```

`single_date` no existe.

La UI visual "Una fecha" ya llega al backend como:

```text
manual_dates
```

---

# 4. Identidad de GenerationSlot

Esta decisión está cerrada.

El frontend genera:

```text
GenerationSlot.id
```

como UUID v4.

El backend debe:

```text
recibirlo
validarlo
preservarlo
persistirlo exactamente
devolverlo exactamente
```

NO debe:

```text
reemplazarlo por otro UUID
generar un nuevo slot ID
hacer client-id → server-id remapping
derivar identidad de horario/fecha/index
```

PostgreSQL protege la unicidad mediante:

```text
generation_slots.id PRIMARY KEY
```

---

# 5. IDs generados por backend

Durante creación persistente el backend continúa generando:

```text
PlanItem.id
Occurrence.id
```

mediante UUID v4.

Los GenerationSlots NO pertenecen a esta categoría.

---

# 6. Contrato POST — activity

`POST /api/plan-items`

Actividad:

```json
{
  "name": "Uber",
  "kind": "activity",
  "activityType": "periodic",
  "generationConfig": {}
}
```

Los `generationConfig` válidos se definen a continuación.

No aceptar:

```text
id del PlanItem enviado por cliente
occurrences enviadas por cliente
single_date
campos desconocidos
modelo legacy default-time como contrato canónico
```

---

# 7. Contrato POST — habit

Hábito:

```json
{
  "name": "Medicamento",
  "kind": "habit",
  "habitType": "scheduled",
  "generationConfig": {}
}
```

Las mismas reglas multi-slot aplican.

No crear restricciones artificiales según:

```text
activityType
habitType
```

---

# 8. POST weekly

Contrato:

```json
{
  "mode": "weekly",
  "startDate": "YYYY-MM-DD",
  "endDate": null,
  "indefinite": true,
  "slots": [
    {
      "id": "UUID-v4",
      "isoWeekday": 1,
      "startTime": "08:00",
      "endTime": "11:00"
    },
    {
      "id": "UUID-v4",
      "isoWeekday": 1,
      "startTime": "14:00",
      "endTime": "17:00"
    }
  ],
  "excludedDates": ["YYYY-MM-DD"],
  "stoppedFromDate": "YYYY-MM-DD"
}
```

`excludedDates` y `stoppedFromDate` son opcionales.

Debe existir al menos un slot.

Cada slot:

```text
UUID válido
isoWeekday 1..7
startTime < endTime
```

Slots del mismo weekday no pueden solaparse.

Intervalos contiguos sí están permitidos.

---

# 9. POST interval_days

Contrato:

```json
{
  "mode": "interval_days",
  "startDate": "YYYY-MM-DD",
  "endDate": null,
  "indefinite": true,
  "intervalDays": 1,
  "slots": [
    {
      "id": "UUID-v4",
      "startTime": "08:00",
      "endTime": "08:05"
    },
    {
      "id": "UUID-v4",
      "startTime": "14:00",
      "endTime": "14:05"
    }
  ],
  "excludedDates": ["YYYY-MM-DD"],
  "stoppedFromDate": "YYYY-MM-DD"
}
```

Debe existir al menos un slot.

Todos los slots aplican a cada fecha generada por la regla.

No pueden solaparse entre sí.

Debe cumplirse:

```text
intervalDays > 0
```

---

# 10. POST manual_dates

Contrato:

```json
{
  "mode": "manual_dates",
  "entries": [
    {
      "id": "UUID-v4",
      "date": "YYYY-MM-DD",
      "startTime": "08:00",
      "endTime": "11:00"
    },
    {
      "id": "UUID-v4",
      "date": "YYYY-MM-DD",
      "startTime": "14:00",
      "endTime": "17:00"
    }
  ],
  "stoppedFromDate": "YYYY-MM-DD"
}
```

Debe existir al menos una entry.

Varias entries pueden utilizar la misma fecha.

Entries de la misma fecha no pueden solaparse.

No aceptar `excludedDates` como parte del contrato canónico de
`manual_dates`.

Si PostgreSQL contiene `generation_excluded_dates` para un PlanItem
manual y el backend no puede representarlo sin pérdida en el contrato
actual:

```text
reportar inconsistencia persistida
```

No omitirla silenciosamente.

---

# 11. UUID validation

Los IDs de slots recibidos deben validarse como UUID v4.

Debe rechazarse:

```text
UUID inválido
UUID duplicado dentro del mismo payload
UUID utilizado para más de un slot/entry
```

No mutar silenciosamente un ID inválido.

Payload inválido:

```text
HTTP 400
invalid_payload
```

---

# 12. Persistencia weekly

Dentro de una única transacción:

```text
plan_items
        ↓
generation_configs
        ↓
generation_slots
        ↓
generation_slot_weekdays
        ↓
generation_excluded_dates
        ↓
occurrences
```

Cada:

```text
generation_slots.id
```

debe ser exactamente el UUID recibido desde frontend.

Cada slot weekly debe tener exactamente una fila en:

```text
generation_slot_weekdays
```

---

# 13. Persistencia interval_days

Dentro de la misma transacción:

```text
plan_items
generation_configs
generation_slots
generation_excluded_dates
occurrences
```

Los slots interval NO deben producir filas en:

```text
generation_slot_weekdays
generation_slot_dates
```

---

# 14. Persistencia manual_dates

Cada entry recibida se guarda como:

```text
generation_slots
+
generation_slot_dates
```

Mapeo:

```text
entry.id
→ generation_slots.id

entry.startTime/endTime
→ generation_slots

entry.date
→ generation_slot_dates.entry_date
```

NO existe ya:

```text
generation_date_entries
```

---

# 15. generation_slot_excluded_dates

La tabla existe desde MVP 05.6.2.

Sin embargo, la semántica persistente de:

```text
slot + excluded date
```

se implementará completamente en MVP 05.6.4.

En MVP 05.6.3:

```text
POST /api/plan-items
```

NO acepta exclusiones individuales por slot.

El backend puede leer la tabla para detectar estado persistido, pero no
debe inventar todavía un campo canónico frontend que no exista.

Si existen filas reales que no pueden representarse todavía:

```text
no omitirlas silenciosamente
reportar estado persistido no representable/inconsistente
```

Hasta MVP 05.6.4 la tabla debería permanecer vacía en uso normal.

---

# 16. Occurrences persistidas

Cada occurrence generada desde un slot debe guardar:

```text
source_generation_slot_id
```

igual a:

```text
GenerationSlot.id
```

Además conserva sus propios:

```text
id
plan_item_id
occurrence_date
start_time
end_time
status
status_reason
source_occurrence_id
```

La occurrence no lee posteriormente su horario desde el slot.

---

# 17. Respuesta POST correcta

HTTP:

```text
201 CREATED
```

Respuesta conceptual:

```json
{
  "planItem": {
    "id": "PLAN-ITEM-UUID",
    "name": "Uber",
    "kind": "activity",
    "activityType": "periodic",
    "generationConfig": {
      "mode": "weekly",
      "startDate": "YYYY-MM-DD",
      "endDate": null,
      "indefinite": true,
      "slots": [
        {
          "id": "SLOT-UUID",
          "isoWeekday": 1,
          "startTime": "08:00",
          "endTime": "11:00"
        }
      ]
    }
  },
  "occurrences": [
    {
      "id": "OCCURRENCE-UUID",
      "planItemId": "PLAN-ITEM-UUID",
      "sourceGenerationSlotId": "SLOT-UUID",
      "date": "YYYY-MM-DD",
      "startTime": "08:00",
      "endTime": "11:00",
      "status": "pending"
    }
  ]
}
```

Los slot IDs de respuesta deben coincidir exactamente con los recibidos.

---

# 18. GET /api/planner-state

Actualizar la reconstrucción persistente para leer el esquema `003`.

Debe leer al menos:

```text
plan_items
generation_configs
generation_slots
generation_slot_weekdays
generation_slot_dates
generation_excluded_dates
generation_slot_excluded_dates
occurrences
```

No utilizar:

```text
generation_weekdays
generation_date_entries
default_start_time
default_end_time
```

porque ya no existen después de `003`.

---

# 19. GET — weekly

Debe reconstruir:

```js
{
  mode: "weekly",
  startDate,
  endDate,
  indefinite,
  slots: [
    {
      id,
      isoWeekday,
      startTime,
      endTime
    }
  ],
  excludedDates?,
  stoppedFromDate?
}
```

Ordenar slots determinísticamente.

Orden recomendado:

```text
isoWeekday
startTime
endTime
id
```

El orden no define identidad.

---

# 20. GET — interval_days

Debe reconstruir:

```js
{
  mode: "interval_days",
  startDate,
  endDate,
  indefinite,
  intervalDays,
  slots: [
    {
      id,
      startTime,
      endTime
    }
  ],
  excludedDates?,
  stoppedFromDate?
}
```

Orden determinista:

```text
startTime
endTime
id
```

---

# 21. GET — manual_dates

Debe reconstruir:

```js
{
  mode: "manual_dates",
  entries: [
    {
      id,
      date,
      startTime,
      endTime
    }
  ],
  stoppedFromDate?
}
```

Orden determinista:

```text
date
startTime
endTime
id
```

No inventar:

```text
excludedDates
```

si no forma parte del contrato canónico manual.

---

# 22. GET — occurrences

Cada occurrence debe serializar:

```js
{
  id,
  planItemId,
  sourceGenerationSlotId?,
  date,
  startTime,
  endTime,
  status,
  statusContext?
}
```

Si:

```text
source_generation_slot_id IS NULL
```

usar la convención frontend existente:

```text
omitir campo
o
null
```

pero elegir una sola convención coherente con el dominio actual y
probarla.

No confundirlo con:

```text
statusContext.sourceOccurrenceId
```

---

# 23. Detección de inconsistencias persistidas

El mapper/service debe continuar sin inventar información.

Ejemplos de inconsistencias:

```text
PlanItem sin generation_config

weekly sin slots

weekly slot sin generation_slot_weekdays

weekly slot con generation_slot_dates

interval_days sin slots

interval slot con weekday/date detail

manual_dates sin entries/slots

manual slot sin generation_slot_dates

manual slot con weekday detail

slot perteneciente a otro PlanItem/config

dos detalles incompatibles para un mismo slot

horarios solapados dentro de la misma regla

global exclusions no representables según el mode

slot exclusions existentes antes de que el contrato pueda representarlas
```

Cuando el estado persistido no pueda reconstruirse sin pérdida:

```text
HTTP 500 controlado
```

No exponer filas SQL, DSN, credenciales ni mensajes internos del driver.

---

# 24. Python materializer — weekly

Actualizar el materializador Python al contrato multi-slot.

Por cada fecha candidata:

```text
weekday
→ todos los slots del weekday
→ una occurrence por slot
```

Cada occurrence:

```text
sourceGenerationSlotId = slot.id
```

Debe respetar:

```text
excludedDates
stoppedFromDate
rango finito
indefinite horizon
history window
```

con la misma semántica JavaScript.

---

# 25. Python materializer — interval_days

Por cada fecha válida:

```text
crear una occurrence por cada slot
```

Cada occurrence conserva:

```text
sourceGenerationSlotId
```

Respetar las mismas reglas de:

```text
intervalDays
excludedDates
stoppedFromDate
horizon
history
```

que JavaScript.

---

# 26. Python materializer — manual_dates

Cada entry:

```text
→ una occurrence
```

Varias entries en la misma fecha:

```text
→ varias occurrences
```

Cada una con:

```text
sourceGenerationSlotId = entry.id
```

---

# 27. Materialización idempotente

La lógica Python debe reconocer identidad mediante:

```text
sourceGenerationSlotId
+
date
```

No mediante:

```text
planItemId
+
date
```

La base protege además esta regla con el índice parcial creado por `003`.

No generar duplicados que dependan de que PostgreSQL los rechace.

El dominio debe ser correcto antes del INSERT.

---

# 28. Internal slot overlap validation

Backend debe validar antes de persistir/materializar:

## weekly

```text
slots del mismo isoWeekday
```

## interval_days

```text
todos los slots
```

## manual_dates

```text
entries de la misma fecha
```

Intervalos contiguos:

```text
08:00–11:00
11:00–14:00
```

son válidos.

Solapados:

```text
08:00–11:00
10:30–14:00
```

son inválidos.

---

# 29. Conflictos contra otras occurrences

Preservar las reglas existentes.

Cada occurrence candidata multi-slot debe evaluarse individualmente.

No cambiar:

```text
intervalos semiabiertos
priority model
completed conflict
history frozen
priority override requirements
```

---

# 30. Prioridad

Preservar:

```text
NORMAL       = 100
EVENT        = 200
UNEXPECTED   = 300
```

Multi-slot no modifica esta jerarquía.

Cada occurrence se evalúa por separado.

---

# 31. Priority override handshake

MVP 05.5 devuelve actualmente:

```text
409 priority_override_required
```

cuando la creación necesita confirmación de override.

Mantener esta política.

NO implementar todavía el handshake frontend completo.

Eso pertenece a integración/edición posterior.

No ejecutar overrides silenciosamente.

---

# 32. Atomicidad de POST

La creación continúa siendo completamente atómica.

Debe utilizar:

```text
una sola conexión
una sola transacción
```

Conceptualmente:

```text
BEGIN

validar conflictos/bloquear lo necesario
insert plan_item
insert generation_config
insert generation_slots
insert weekday/date details
insert global exclusions
insert occurrences

COMMIT
```

Ante cualquier fallo:

```text
ROLLBACK
```

No debe quedar:

```text
PlanItem huérfano
slot huérfano
generationConfig parcial
occurrence parcial
```

---

# 33. Concurrencia

Mantener el mecanismo existente de bloqueo de occurrences potencialmente
conflictivas mediante:

```text
FOR UPDATE
```

si continúa siendo válido.

Adaptarlo únicamente si multi-slot lo exige.

No retirar protección de concurrencia para simplificar implementación.

---

# 34. Consistencia de GET planner-state

`GET /api/planner-state` reconstruye estado desde varias tablas.

Todas las consultas de una misma reconstrucción deben utilizar:

```text
una sola conexión
```

y una vista consistente de la base.

Ahora que ya existen escrituras persistentes, preferir una transacción de
lectura consistente, idealmente:

```text
READ ONLY
REPEATABLE READ
```

si puede integrarse limpiamente con la infraestructura actual.

Si hacerlo requiere una alteración arquitectónica desproporcionada:

```text
no improvisar
reportarlo
```

Pero no utilizar conexiones separadas por tabla.

---

# 35. Errores API

Mantener respuestas sanitizadas.

Como mínimo:

```text
400
invalid_payload

409
conflicto de dominio existente

500
persisted planner state inválido/no representable

503
database_unavailable
```

No exponer:

```text
DSN
password
SQL raw
driver internals
tracebacks al cliente
```

---

# 36. Repository layer

Mantener separación:

```text
app.py
→ HTTP solamente

service/domain
→ validación/orquestación

repository
→ SQL

materializer
→ generación temporal
```

No introducir ORM.

No duplicar SQL en Flask routes.

No mover reglas de dominio a repository.

---

# 37. planner-state repository

Actualizar las consultas al esquema nuevo.

Usar:

```text
dict_row
```

o la convención existente.

Consultas deterministas.

No depender del orden natural de PostgreSQL.

---

# 38. plan-item creation repository

Actualizar inserts al esquema nuevo.

Debe aceptar los slot IDs ya validados.

No generar UUID de slot en repository.

No modificar los IDs recibidos.

No insertar detalles incompatibles con el `mode`.

---

# 39. JS ↔ Python parity

La prueba de paridad que temporalmente quedó roja en MVP 05.6.1 debe
volver a quedar verde.

Utilizar fixtures multi-slot con IDs de slot fijos/deterministas.

Comparar la semántica materializada equivalente.

Debe incluir al menos:

```text
weekly un slot

weekly varios slots mismo weekday

weekly slots distintos por weekday

interval_days varios slots

manual_dates varias entries mismo día

slots contiguos

excludedDates

stoppedFromDate

sourceGenerationSlotId
```

Si JavaScript y Python generan `Occurrence.id` aleatorios de forma
independiente:

```text
NO exigir igualdad de UUID de occurrence
```

para considerar equivalencia.

Comparar los campos semánticos apropiados:

```text
planItemId
sourceGenerationSlotId
date
startTime
endTime
status
```

y cualquier otro campo determinista relevante.

No debilitar la prueba simplemente para hacerla pasar.

---

# 40. Casos de prueba POST weekly

Cubrir:

```text
un slot

múltiples slots mismo weekday

slots diferentes por weekday

UUIDs preservados

override visual no existe en API canónica

excludedDates

stoppedFromDate

slots contiguos

slots solapados rechazados

slot UUID inválido

slot UUID duplicado
```

---

# 41. Casos de prueba POST interval_days

Cubrir:

```text
un slot

varios slots

intervalDays válido

intervalDays inválido

UUIDs preservados

solapamiento rechazado

excludedDates

stoppedFromDate
```

---

# 42. Casos de prueba POST manual_dates

Cubrir:

```text
una entry

varias entries

varias entries misma fecha

horarios contiguos

horarios solapados rechazados

UUIDs preservados

stoppedFromDate

excludedDates rechazado si aparece

single_date rechazado
```

---

# 43. Casos de prueba planner-state

Cubrir:

```text
DB vacía

weekly multi-slot

interval_days multi-slot

manual_dates multi-slot

varios PlanItems

múltiples occurrences mismo PlanItem/día

sourceGenerationSlotId presente

sourceGenerationSlotId NULL

statusContext

excludedDates global

stoppedFromDate

orden determinista

estado inconsistente
```

---

# 44. Tests de atomicidad

Con PostgreSQL aislado verificar rollback si falla:

```text
generation_config

generation_slot

weekday/date detail

global exclusion

occurrence
```

Después del fallo no debe quedar:

```text
PlanItem
GenerationSlot
Occurrence
```

parcialmente persistido.

---

# 45. Tests de idempotencia DB

Verificar que:

```text
mismo source_generation_slot_id
+
misma occurrence_date
```

no pueda duplicarse.

Y que:

```text
slot A + fecha X
slot B + fecha X
```

sí sea válido para el mismo PlanItem.

---

# 46. Tests de procedencia histórica

Verificar que una occurrence con:

```text
source_generation_slot_id
```

conserva:

```text
date
start/end
status
```

independientemente del slot.

No es necesario implementar edición persistente todavía.

---

# 47. PostgreSQL de pruebas

Utilizar PostgreSQL 16 aislado/efímero cuando esté disponible.

Aplicar siempre:

```text
001
002
003
```

antes de tests de integración.

NO utilizar:

```text
vcs_dev
```

No utilizar credenciales reales del usuario.

---

# 48. vcs_dev

Codex NO debe aplicar:

```text
003
```

sobre `vcs_dev`.

NO debe modificar los datos reales/locales del usuario.

La aplicación de `003` a `vcs_dev` se hará manualmente después de revisar
MVP 05.6.3.

---

# 49. Backend tests legacy

Actualizar tests backend que todavía construyan fixtures con:

```text
defaultStartTime
defaultEndTime
weekdays
weekdayTimeOverrides
generation_date_entries
```

cuando esos tests estén validando el contrato canónico actual.

No borrar tests de regresión útiles.

Los tests específicamente históricos/de migración pueden conservar el
modelo legacy si están probando 001/002 → 003.

---

# 50. Rutas existentes

Preservar:

```text
GET /api/health
GET /api/health/db
GET /api/plan-items
GET /api/planner-state
POST /api/plan-items
```

No romper health endpoints.

`GET /api/plan-items` puede continuar devolviendo únicamente los datos
básicos que ya devolvía si ese es su contrato actual.

---

# 51. Frontend

NO modificar el comportamiento frontend aprobado en MVP 05.6.1.

Si para las pruebas de paridad hace falta tocar exclusivamente un helper
de tests:

```text
permitido
```

Si se detecta un defecto real del frontend/domain:

```text
detenerse
reportarlo
```

No corregir silenciosamente una feature ya cerrada desde backend.

---

# 52. Database migrations

NO modificar:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
```

Si se detecta un defecto REAL en `003`:

```text
detenerse
reportarlo
```

No crear `004` por iniciativa propia en esta fase.

Primero debe revisarse la incompatibilidad.

---

# 53. Fuera de alcance

NO implementar todavía:

```text
PATCH plan-items
DELETE persistente
edición persistente de slots
generation_slot_excluded_dates writes
eliminar solo este slot hoy
Apply week persistente multi-slot
Apply Future persistente multi-slot
frontend fetch integration
auth
multiusuario
Supabase
deployment
notifications
timezone por usuario
```

Esas operaciones pertenecen a fases posteriores.

---

# 54. Caso de aceptación principal — Uber

El backend debe aceptar un solo PlanItem:

```text
Uber
```

con slots weekly equivalentes a:

```text
lunes-viernes

08:00–11:00
14:00–17:00
20:00–22:00

sábado-domingo

08:00–21:00
```

Debe:

```text
preservar todos los slot UUIDs
persistirlos
materializar 17 occurrences en una semana completa equivalente
asignar sourceGenerationSlotId correcto
permitir múltiples occurrences mismo PlanItem/día
```

sin crear varios PlanItems.

---

# 55. Caso de aceptación — Medicamento

Debe aceptar:

```text
interval_days = 1

08:00–08:05
14:00–14:05
22:00–22:05
```

como tres slots del mismo PlanItem.

---

# 56. Caso de aceptación — manual_dates

Debe aceptar:

```text
2026-09-15

08:00–11:00
14:00–17:00
```

como dos entries con dos UUIDs distintos.

Debe persistir dos GenerationSlots y dos occurrences independientes.

---

# 57. Criterios de aceptación

MVP 05.6.3 queda completo cuando:

```text
GET planner-state
→ reconstruye contrato multi-slot

POST plan-items
→ persiste contrato multi-slot

GenerationSlot UUID frontend
→ preservado hasta PostgreSQL y respuesta

Python materializer
→ multi-slot

sourceGenerationSlotId
→ persistido y serializado

JS/Python parity
→ verde

múltiples occurrences mismo PlanItem/día
→ válidas

rollback
→ conserva atomicidad

health routes
→ sin regresión
```

---

# 58. Resultado arquitectónico esperado

Al finalizar:

```text
Frontend
GenerationSlots
      │
      ▼
Flask/API
      │
      ▼
Service/domain Python
      │
      ├── materializer Python
      │
      ▼
Repository
      │
      ▼
PostgreSQL 003
```

Los tres niveles comparten el mismo modelo.

---

# 59. Git

Codex NO debe:

```text
commit
push
merge
cambiar de rama
```

El usuario controla Git.

---

# 60. Reporte requerido

Al terminar reportar:

1. archivos creados/modificados;
2. contrato exacto aceptado por POST weekly;
3. contrato exacto aceptado por POST interval_days;
4. contrato exacto aceptado por POST manual_dates;
5. contrato exacto devuelto por planner-state;
6. cómo se validan los UUID de slots;
7. evidencia de que se preservan;
8. estrategia SQL de persistencia;
9. cómo se insertan weekday/date details;
10. cómo se persiste `source_generation_slot_id`;
11. cómo funciona el materializador Python;
12. cómo funciona la idempotencia;
13. cómo se detectan estados persistidos inconsistentes;
14. estrategia de transacción/rollback;
15. resultado de JS/Python parity;
16. número y resultado de tests backend;
17. resultado de tests frontend como regresión;
18. resultado de integración PostgreSQL `001+002+003`;
19. prueba del caso Uber;
20. cualquier limitación/riesgo encontrado.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
frontend funcional no fue modificado
001/002/003 no fueron modificadas
no se hizo commit/push/merge
```
