# CURRENT TASK

## MVP 05.6.5 — Verificación integral del dominio persistente

### Propósito

Esta fase NO agrega una nueva feature principal.

Su objetivo es verificar integralmente que el dominio persistente del
Gestor de hábitos sea coherente antes de conectar el frontend real con la API.

Estado actual:

```text
05.6.1    Frontend/domain multi-slot                 ✅
05.6.2    PostgreSQL multi-slot                      ✅
05.6.3    Backend/API multi-slot                     ✅
05.6.4.1  Solo este día                              ✅
05.6.4.2  Aplicar a esta semana                      ✅
05.6.4.3  Aplicar de aquí en adelante                ✅

05.6.5    Verificación integral                      ← ACTUAL
```

Resultado esperado:

```text
Dominio persistente estable
        ↓
listo para integración frontend ↔ backend
```

---

# 1. Naturaleza de esta fase

Esta fase es principalmente:

```text
auditoría
verificación
regresión
integración
detección de huecos
```

NO:

```text
rediseño
nueva feature grande
refactorización cosmética
optimización prematura
```

Si todo está correcto:

```text
no modificar código innecesariamente
```

Si se detecta un defecto real que contradice contratos ya aprobados:

```text
corregir únicamente el defecto
añadir regresión
volver a verificar
```

Si resolverlo exige una nueva decisión arquitectónica:

```text
DETENERSE Y REPORTAR
```

No inventar la decisión.

---

# 2. Documentos normativos

Leer antes de auditar:

```text
/AGENTS.md
/docs/codex/CURRENT_TASK.md
/docs/codex/gestor_de_habitos/planeacion/MVP_05_6/MULTI_SLOT_SCHEDULING.md
```

Consultar implementaciones y tests relacionados según sea necesario.

No es obligatorio releer indiscriminadamente todo el repositorio si una
fuente concreta ya basta para comprobar un punto.

Pero verificar el código real antes de asumir contratos de:

```text
PostgreSQL
API
materialización
mutaciones
```

---

# 3. Modelo conceptual que debe quedar validado

```text
PlanItem
→ qué actividad/hábito es

generationConfig
→ reglas generales de recurrencia

GenerationSlot
→ horario/regla concreta dentro del motor

Occurrence
→ aparición concreta materializada
```

Un PlanItem puede tener:

```text
1 o múltiples GenerationSlots
```

Una fecha puede contener:

```text
0, 1 o múltiples Occurrences del mismo PlanItem
```

Cada occurrence es independiente en:

```text
date
startTime
endTime
status
```

---

# 4. sourceGenerationSlotId

Validar que su semántica permanezca:

```text
referencia operacional al GenerationSlot lógico
```

Sirve para:

```text
idempotencia
slot exclusions
Single Day
Apply Week
Apply Future
```

NO representa:

```text
una versión histórica inmutable de la regla
```

Una occurrence histórica puede conservar:

```text
sourceGenerationSlotId = S1
```

aunque S1 haya cambiado posteriormente.

Eso es válido.

---

# 5. sourceOccurrenceId

Validar independientemente:

```text
sourceOccurrenceId
```

solo para:

```text
statusContext.reason = priority_override
```

No mezclarlo con:

```text
sourceGenerationSlotId
```

Verificar que las protecciones actuales impidan modificar/eliminar
incorrectamente una occurrence necesaria por una relación de
`statusContext`.

---

# 6. Modos canónicos

Solo existen:

```text
weekly
interval_days
manual_dates
```

Buscar regresiones o restos activos de:

```text
single_date
```

No debe existir como modo persistido ni API canónica.

La UI visual:

```text
Una fecha
```

continúa representándose mediante:

```text
manual_dates
```

con una sola entry.

---

# 7. Contratos multi-slot

Validar:

## weekly

```js
{
  mode,
  startDate,
  endDate,
  indefinite,
  slots: [
    {
      id,
      isoWeekday,
      startTime,
      endTime,
      excludedDates?
    }
  ],
  excludedDates?,
  stoppedFromDate?
}
```

## interval_days

```js
{
  mode,
  startDate,
  endDate,
  indefinite,
  intervalDays,
  slots: [
    {
      id,
      startTime,
      endTime,
      excludedDates?
    }
  ],
  excludedDates?,
  stoppedFromDate?
}
```

## manual_dates

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

No introducir `slot.excludedDates` para manual_dates.

---

# 8. UUID de GenerationSlot

Validar integralmente:

```text
frontend genera UUID v4
backend valida
backend preserva
PostgreSQL persiste
GET devuelve exactamente el mismo UUID
```

No remapping.

No UUID nuevo por editar un slot lógico existente.

Slot nuevo:

```text
UUID nuevo
```

Slot eliminado:

```text
desaparece del motor
```

---

# 9. POST /api/plan-items

Auditar creación persistente para:

```text
weekly
interval_days
manual_dates
```

Verificar:

```text
atomicidad
validación estricta
UUID preservation
multi-slot
sourceGenerationSlotId
priority conflicts
rollback
```

No aceptar:

```text
single_date
modelo legacy defaultStartTime/defaultEndTime
campos desconocidos
occurrences suministradas por cliente
PlanItem.id enviado por cliente
```

---

# 10. GET /api/planner-state

Verificar round-trip real:

```text
PostgreSQL
→ repository
→ service
→ API
```

Debe reconstruir exactamente:

```text
planItems
occurrences
GenerationSlots
slot exclusions
global exclusions
statusContext
```

Usar una sola conexión y mantener la estrategia de lectura consistente
actual.

Verificar orden determinista.

No inventar estado ante inconsistencias persistidas.

---

# 11. Single Day — PATCH occurrence

Verificar:

```text
PATCH /api/occurrences/<id>
```

Casos:

```text
recurrente misma fecha
recurrente cambio de fecha
manual_dates
ad-hoc
```

Debe preservar:

```text
Occurrence.id
status
statusContext
```

según corresponda.

Recurrente misma fecha:

```text
solo cambia occurrence
GenerationSlot intacto
```

Recurrente movida:

```text
slot exclusion en fecha original
occurrence movida
sourceGenerationSlotId preservado
```

---

# 12. Single Day — DELETE occurrence

Verificar:

## recurrente

```text
slot exclusion + delete occurrence
slot permanece
```

## manual

```text
delete occurrence
delete slot/entry
```

excepto:

```text
última manual entry
→ 409 last_manual_entry
```

## ad-hoc

```text
delete occurrence únicamente
```

---

# 13. Apply Week

Verificar:

```text
POST /api/plan-items/<id>/apply-week
```

Operaciones:

```text
update
delete
create
```

Semántica:

```text
solo cambia la semana ISO seleccionada
GenerationSlots generales permanecen intactos
semana siguiente vuelve a regla normal
```

Create:

```text
ad-hoc
sourceGenerationSlotId = NULL
```

Delete recurrente:

```text
slot exclusion
```

Update recurrente:

```text
occurrence concreta
```

---

# 14. Apply Week — final state

Verificar específicamente que el batch se valide por:

```text
estado final candidato
```

y no secuencialmente contra el estado viejo.

Caso obligatorio:

```text
O1 08–09
O2 09–10

swap:
O1 → 09–10
O2 → 08–09
```

Debe funcionar si el estado final es válido.

---

# 15. Apply Future

Verificar:

```text
POST /api/plan-items/<id>/apply-future
```

Semántica:

```text
antes de futureConfig.startDate
→ occurrences intactas

desde futureConfig.startDate
→ nuevo motor
```

No existe:

```text
slot versioning
config history
effective_from
effective_until
```

---

# 16. Apply Future — slot reutilizado

Si:

```text
S1 14–17
```

cambia a:

```text
S1 15–18
```

debe:

```text
preservar UUID S1
actualizar motor actual
reconciliar baseline futuro
no tocar occurrences previas a startDate
```

---

# 17. Apply Future — slot nuevo

Verificar:

```text
nuevo UUID frontend
→ insert exacto
```

No materializarlo antes de:

```text
futureConfig.startDate
```

---

# 18. Apply Future — slot eliminado

Verificar:

```text
slot desaparece del motor
baseline future desaparece
```

pero:

```text
historia permanece
explicit override permanece
```

La FK:

```text
ON DELETE SET NULL
```

puede dejar esas occurrences sin source slot.

Eso es correcto.

---

# 19. Apply Future — overrides

Verificar que sobrevivan:

```text
Single Day edits
Apply Week edits
ad-hoc occurrences
slot exclusions
global exclusions
```

si son compatibles con el nuevo estado final.

No sobrescribir automáticamente una decisión explícita con el nuevo
baseline.

---

# 20. Interval phase

Validar:

```text
interval_days
```

después de Apply Future.

Nuevo:

```text
startDate
```

reinicia la fase.

Ejemplo:

```text
Sep 21
intervalDays = 3

→ Sep 21
→ Sep 24
→ Sep 27
```

---

# 21. Materialización

Auditar JS y Python.

Deben compartir semántica para:

```text
weekly
interval_days
manual_dates
multi-slot
global exclusions
slot exclusions
stoppedFromDate
history window
```

Cada candidate recurrente debe mantener:

```text
sourceGenerationSlotId
```

---

# 22. Idempotencia

Validar integralmente:

```text
sourceGenerationSlotId + date
```

como identidad recurrente.

No:

```text
planItemId + date
```

Debe poder existir:

```text
S1 + date
S2 + date
S3 + date
```

para un mismo PlanItem.

No duplicar un mismo:

```text
slot + date
```

al rematerializar.

---

# 23. Overrides + rematerialización

Caso obligatorio:

```text
S1 baseline 14–17

Occurrence editada:
15–18
source=S1
misma fecha
```

Rematerializar.

Esperar:

```text
NO crear adicional 14–17
```

La appearance concreta ocupa:

```text
S1 + fecha
```

---

# 24. Delete + rematerialización

Caso:

```text
S2 eliminado solo ese día
```

Persistido:

```text
slot.excludedDates incluye fecha
```

Rematerializar.

Esperar:

```text
S2 no reaparece
otros slots sí permanecen
```

---

# 25. Exclusion global vs slot exclusion

Validar diferencia:

```text
generationConfig.excludedDates
→ bloquea TODO el PlanItem esa fecha

slot.excludedDates
→ bloquea solo ese slot
```

No mezclar ambas.

---

# 26. stoppedFromDate

Validar:

```text
materialización
Single Day
Apply Week
Apply Future
```

No debe reactivar silenciosamente planificación detenida.

Apply Future incompatible:

```text
409 planning_stopped
```

según política actual.

---

# 27. Temporal integrity

Verificar:

```text
current day
yesterday
older frozen history
future
```

con la política ya aprobada.

No ampliar la ventana.

Historia congelada:

```text
visible
inmutable
```

Batch con una operación congelada:

```text
rollback completo
```

---

# 28. Status

Estados canónicos:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

Auditar transiciones relevantes y asegurar que las mutaciones de scheduling
NO cambien status arbitrariamente.

---

# 29. Priority model

Preservar:

```text
NORMAL       = 100
EVENT        = 200
UNEXPECTED   = 300
```

Verificar conflictos:

```text
pending
in_progress
completed
```

y el handshake existente:

```text
409 priority_override_required
```

No ejecutar override silencioso.

---

# 30. statusContext

Validar:

```js
{
  reason: "priority_override",
  sourceOccurrenceId: "..."
}
```

Solo debe aparecer cuando corresponde.

Manual cancellation:

```text
no statusContext priority_override
```

Proteger occurrence referenciada cuando editar/eliminar rompería el
contexto.

---

# 31. Atomicidad

Auditar operaciones compuestas:

```text
POST PlanItem
PATCH occurrence
DELETE occurrence
Apply Week
Apply Future
```

Cada una debe ser:

```text
una conexión
una transacción
todo o nada
```

Provocar fallos tardíos en integration tests.

Verificar:

```text
0 cambios parciales
```

---

# 32. SERIALIZABLE y locking

Verificar las mutations que actualmente dependen de:

```text
SERIALIZABLE
FOR UPDATE
```

No cambiar aislamiento sin una razón concreta.

Auditar orden de locks cuando corresponda.

---

# 33. Concurrencia

Ejecutar pruebas PostgreSQL reales para:

```text
creación/conflictos si aplica
Single Day
Apply Week
Apply Future
```

Especialmente:

```text
mismo PlanItem
misma ventana temporal
```

Resultado:

```text
una operación coherente completa
o conflicto controlado
```

Nunca estado mezclado.

---

# 34. Serialization failures

Auditar cómo se transforman errores de concurrencia/serialización en:

```text
409 concurrent_modification
```

cuando corresponda.

No filtrar detalles de psycopg/PostgreSQL al cliente.

---

# 35. Error contract

Auditar respuestas sanitizadas para:

```text
400 invalid_payload
400 invalid_identifier

404 plan_item_not_found
404 occurrence_not_found

409 domain conflicts
409 priority_override_required
409 history_frozen
409 last_manual_entry
409 unsupported_mode
409 mode_change_not_supported
409 planning_stopped
409 concurrent_modification
409 status_context_locked

500 persisted_state_invalid

503 database_unavailable
```

No exigir exactamente todos si algunos códigos equivalentes ya están
normalizados de forma coherente.

No exponer:

```text
SQL
DSN
password
traceback
driver internals
```

---

# 36. Persisted-state integrity

Verificar que GET falle de forma controlada ante estados imposibles como:

```text
PlanItem sin config
mode sin slots
slot detail incompatible
manual slot sin date
weekly slot sin weekday
overlaps persistidos inválidos
slot perteneciente a otro PlanItem
```

No inventar datos para reparar lectura.

---

# 37. PostgreSQL schema

Auditar el modelo actual tras:

```text
001
002
003
```

No modificar migraciones por iniciativa propia.

No crear:

```text
004
```

salvo que se descubra una imposibilidad REAL que invalide un contrato ya
aprobado.

Si ocurre:

```text
DETENERSE Y REPORTAR
```

---

# 38. Migration 003 regression

Ejecutar una prueba real desde legado:

```text
001
002
legacy fixture
003
```

Cubrir:

```text
weekly
interval
manual_dates
múltiples manual entries misma fecha
occurrences
global exclusions
```

Verificar:

```text
datos históricos conservados
GenerationSlots creados correctamente
source_generation_slot_id backfill solo cuando seguro
```

Ambiguo:

```text
NULL
```

No asociación inventada.

---

# 39. Empty database

Con:

```text
001 + 002 + 003
```

y DB vacía:

```text
GET /api/planner-state
→ 200
→ planItems []
→ occurrences []
```

---

# 40. Full lifecycle weekly

Crear test end-to-end:

```text
POST weekly multi-slot
→ GET
→ Single Day edit/delete
→ GET
→ Apply Week
→ GET
→ Apply Future
→ GET
```

Verificar invariants después de cada etapa.

---

# 41. Full lifecycle interval_days

Mismo flujo:

```text
POST
GET
Single Day
Apply Week
Apply Future
GET
```

incluyendo cambio de:

```text
startDate
intervalDays
slots
```

---

# 42. Full lifecycle manual_dates

Verificar:

```text
POST múltiples entries misma fecha
GET
PATCH una entry
DELETE una entry
GET
protección última entry
```

No Apply Week/Future.

---

# 43. Multi-slot acceptance

Caso Uber:

```text
Lun–Vie
08–11
14–17
20–22

Sáb–Dom
08–21
```

Un solo PlanItem.

Una semana completa:

```text
17 occurrences
```

Verificar:

```text
cada occurrence ligada al slot correcto
```

---

# 44. Habit multi-slot acceptance

Caso:

```text
Medicamento
interval_days = 1

08:00–08:05
14:00–14:05
22:00–22:05
```

Un PlanItem.

Tres occurrences por fecha válida.

No restricciones artificiales por ser habit.

---

# 45. Adjacent intervals

Debe seguir siendo válido:

```text
08–11
11–14
14–17
```

Overlap real:

```text
08–11
10:30–14
```

debe rechazarse.

Validar:

```text
frontend
backend
materializadores
```

---

# 46. JS ↔ Python parity

Debe permanecer verde.

Cubrir:

```text
weekly
interval
manual
multi-slot
slot exclusions
global exclusions
stoppedFromDate
sourceGenerationSlotId
```

No comparar UUID de occurrences aleatorios cuando no son deterministas.

---

# 47. Frontend/domain local

Auditar que el dominio local soporte coherentemente:

```text
Single Day
Apply Week
Apply Future
multi-slot
slot exclusions
```

y que no siga existiendo un bloqueo temporal que ya debió desaparecer en
05.6.4.x.

---

# 48. NO conectar frontend ↔ API todavía

Esta fase NO realiza la integración real HTTP.

No añadir:

```text
fetch startup
fetch POST
fetch PATCH
fetch DELETE
Apply Week fetch
Apply Future fetch
```

La siguiente fase se encargará de eso.

---

# 49. UI regression

Comprobar al menos:

```text
desktop
mobile
```

Sin:

```text
overflow inesperado
errores JS
pantalla rota
regresiones obvias
```

No rediseñar UI.

---

# 50. Legacy terminology audit

Buscar únicamente en código activo relevante restos que indiquen
contratos obsoletos como:

```text
single_date
default_start_time
default_end_time
generation_weekdays
generation_date_entries
```

Distinguir:

```text
legacy migration tests
```

donde estos nombres sí pueden ser correctos.

No borrar historia/tests legítimos.

---

# 51. Duplication / architecture audit

Revisar únicamente problemas que puedan causar divergencia funcional.

Especial atención a:

```text
materializer JS
materializer Python
scheduling policy
mutation services
```

NO hacer refactor cosmético simplemente por detectar duplicación.

La duplicación JS/Python es un riesgo conocido actualmente mitigado por
paridad.

Reportarlo, no rediseñarlo salvo defecto real.

---

# 52. PostgreSQL de pruebas

Usar:

```text
PostgreSQL 16 aislado/efímero
```

Aplicar:

```text
001
002
003
```

NO utilizar:

```text
vcs_dev
```

No utilizar credenciales reales.

---

# 53. vcs_dev

Codex NO modifica:

```text
vcs_dev
```

Después de la auditoría, el usuario podrá realizar pruebas manuales reales
si son necesarias.

---

# 54. Regression suite

Ejecutar como mínimo:

```text
backend completo
PostgreSQL integration
frontend completo
JS/Python parity
compileall
node --check donde corresponda
git diff --check
```

Además verificar endpoints existentes.

---

# 55. No perseguir número de tests

No crear tests artificiales únicamente para incrementar el contador.

Añadir tests cuando:

```text
cubran una invariant importante
cubran un lifecycle integral
cubran un bug encontrado
cubran un hueco real
```

La calidad importa más que la cantidad.

---

# 56. Defect classification

Cada hallazgo debe clasificarse:

```text
A. bug real
B. test faltante
C. documentación desactualizada
D. riesgo conocido/no bloqueante
E. nueva decisión de producto/arquitectura
```

Para E:

```text
NO decidir por iniciativa propia
reportar
```

---

# 57. Bug fixes permitidos

Si se encuentra un bug inequívoco respecto a contratos ya cerrados:

```text
corregir
añadir test de regresión
ejecutar suites afectadas
```

Mantener el cambio mínimo.

---

# 58. No features nuevas

NO implementar:

```text
frontend ↔ backend integration
auth
multiusuario
PlanItem deletion general
mode change Apply Future
notifications
timezone por usuario
Supabase
deployment
analytics
new UX features
```

---

# 59. Criterio principal de salida

MVP 05.6.5 queda completo cuando pueda afirmarse con evidencia:

```text
El dominio persistente del planner es coherente entre:

Frontend/domain JS
Backend/domain Python
API
PostgreSQL

para creación, materialización y los tres scopes de edición.
```

Y:

```text
no existen defectos conocidos bloqueantes
para iniciar integración frontend ↔ backend.
```

---

# 60. Resultado esperado

Al terminar, clasificar la fase como una de estas dos:

## READY

```text
Persisted planner domain ready for frontend/API integration.
```

No hay defectos bloqueantes conocidos.

## NOT READY

Indicar exactamente:

```text
qué bloquea
por qué
qué contrato está afectado
qué decisión/corrección necesita
```

No declarar READY si existe un defecto conocido bloqueante.

---

# 61. Git

Codex NO debe:

```text
commit
push
merge
cambiar rama
```

El usuario controla Git.

---

# 62. Reporte requerido

Al terminar reportar:

1. clasificación final READY / NOT READY;
2. archivos modificados, si hubo;
3. bugs reales encontrados;
4. tests añadidos por huecos reales;
5. documentación desactualizada encontrada;
6. riesgos conocidos no bloqueantes;
7. resultado creación weekly;
8. resultado creación interval_days;
9. resultado creación manual_dates;
10. resultado Single Day;
11. resultado Apply Week;
12. resultado Apply Future;
13. resultado multi-slot;
14. resultado exclusiones globales/slot;
15. resultado temporal integrity;
16. resultado priority/statusContext;
17. resultado idempotencia/rematerialización;
18. resultado full lifecycle weekly;
19. resultado full lifecycle interval;
20. resultado full lifecycle manual;
21. resultado Uber;
22. resultado medicamento;
23. resultado migration 003 legacy;
24. resultado empty database;
25. resultado rollback;
26. resultado concurrencia;
27. resultado errores sanitizados;
28. resultado JS/Python parity;
29. resultado frontend regression;
30. número/resultados backend;
31. número/resultados PostgreSQL integration;
32. cualquier nueva decisión arquitectónica que requiera al usuario.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
001/002/003 no fueron modificadas
no se creó migration 004
frontend no fue conectado a la API
no se implementaron features fuera de alcance
no se hizo commit/push/merge
```
