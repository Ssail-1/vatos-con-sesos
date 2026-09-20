# OccurrenceSegment v1 — Technical Decisions

Estado:

```text
APPROVED FOR IMPLEMENTATION
```

Este documento resuelve las decisiones técnicas abiertas detectadas en:

```text
docs/architecture/OCCURRENCE_SEGMENT_TECHNICAL_AUDIT.md
```

Debe leerse junto con:

```text
docs/architecture/STATUS_CONFLICT_RULES.md
docs/architecture/OCCURRENCE_SEGMENT_V1.md
modules/gestor_de_habitos/docs/valores.md
```

Los documentos normativos definen el comportamiento del producto.

Este documento define las decisiones técnicas elegidas para implementar ese
comportamiento.

Si existe conflicto entre una propuesta de la auditoría y este documento:

```text
OCCURRENCE_SEGMENT_DECISIONS.md
```

representa la decisión humana aprobada más reciente.

---

## 1. General architecture

OccurrenceSegment v1 utilizará una arquitectura híbrida:

```text
PostgreSQL
→ protege invariantes estructurales simples y robustas

Domain / services
→ protegen invariantes cross-row y reglas de negocio

SERIALIZABLE transactions
→ garantizan mutaciones coherentes y atómicas
```

No mover lógica principal de negocio a:

```text
stored procedures
PL/pgSQL triggers complejos
frontend
```

El backend continúa siendo la autoridad del dominio.

---

## 2. OccurrenceSegment table

Crear:

```text
occurrence_segments
```

con al menos:

```text
id UUID PRIMARY KEY

occurrence_id UUID NOT NULL
→ occurrences(id)
→ ON DELETE CASCADE

start_time TIME NOT NULL

end_time TIME NOT NULL

status VARCHAR(...) NOT NULL
```

Statuses permitidos:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

---

## 3. Local PostgreSQL constraints

PostgreSQL debe garantizar directamente:

```text
segment id válido

occurrence parent existente

ON DELETE CASCADE desde occurrence hacia segments

start_time < end_time

status dentro del conjunto permitido
```

Agregar también un índice estructural equivalente a:

```text
(
    occurrence_id,
    start_time,
    end_time,
    id
)
```

El SQL exacto se definirá en migration 004.

---

## 4. Sibling segment overlap

Dos segments pertenecientes a la misma occurrence:

```text
NO pueden superponerse
```

Adyacencia:

```text
13:00–14:00
14:00–15:00
```

sí está permitida.

La semántica temporal debe utilizar:

```text
[start, end)
```

---

## 5. Preferred database protection for sibling overlap

La opción preferida es:

```text
service/domain validation
+
PostgreSQL exclusion constraint diferible
```

si PostgreSQL 16 y el entorno permiten utilizar limpiamente:

```text
btree_gist
```

Primero debe hacerse un prototipo en una base PostgreSQL efímera.

No modificar:

```text
vcs_dev
```

para probar esta decisión.

---

## 6. Fallback if `btree_gist` is not viable

Si:

```text
btree_gist
```

no está disponible, requiere privilegios inconvenientes o complica
innecesariamente migration 004:

```text
NO bloquear la implementación
```

Usar inicialmente:

```text
service/domain final-state validation
+
parent locking
+
SERIALIZABLE
```

y documentar la exclusion constraint como hardening futuro.

OccurrenceSegment v1 no depende obligatoriamente de la extensión.

---

## 7. At least one segment

Toda occurrence debe tener:

```text
1..N segments
```

En v1 esta invariante será responsabilidad de:

```text
domain/service final-state validation
```

No implementar inicialmente:

```text
constraint trigger diferible
```

para garantizar la existencia de al menos un child.

---

## 8. Why at-least-one stays in service initially

Operaciones como:

```text
split
replace
resize
reset segmentation
delete segment
```

pueden pasar temporalmente por estados intermedios donde cambia todo el
conjunto de children.

El service debe construir primero:

```text
final candidate state
```

y validar:

```text
segments.length >= 1
```

antes del commit.

Esto simplifica v1 y evita triggers complejos prematuros.

---

## 9. Possible future DB hardening

Más adelante puede evaluarse:

```text
DEFERRABLE constraint trigger
```

para reforzar:

```text
at least one segment
```

desde PostgreSQL.

No forma parte obligatoria de migration 004.

---

## 10. Segment bounds

Todo segment debe quedar dentro del rango general de su occurrence:

```text
occurrence.start_time <= segment.start_time
```

y:

```text
segment.end_time <= occurrence.end_time
```

Esta es una invariante cross-table.

En v1 será responsabilidad de:

```text
domain/service final-state validation
```

No implementar triggers complejos para ella inicialmente.

---

## 11. Aggregate status authority

`Occurrence.status` se conserva físicamente.

Su nueva semántica es:

```text
materialized aggregate
```

derivado de:

```text
OccurrenceSegment.status[]
```

El backend es autoridad para derivarlo.

---

## 12. Aggregate implementation

Crear una función pura de dominio equivalente a:

```text
deriveOccurrenceStatus(segments, temporalPhase)
```

No implementar el aggregate como:

```text
frontend-only calculation
generated DB column
business trigger
```

---

## 13. Temporal phase must be explicit

No utilizar un boolean ambiguo como:

```text
isHistorical
```

La función debe recibir una fase temporal explícita compatible con:

```text
FUTURE
CURRENT_DAY
PREVIOUS_EDITABLE_DAY
FROZEN_HISTORY
```

Aunque algunas fases compartan reglas de aggregate.

Esto hace explícito qué regla temporal se está aplicando.

---

## 14. Aggregate persistence

Cada operación que modifica segment statuses debe:

```text
1. modificar candidate segments
2. derivar Occurrence.status
3. validar final state
4. persistir children
5. persistir parent aggregate
6. COMMIT
```

Todo dentro de:

```text
la misma transacción
```

Nunca recalcular el aggregate posteriormente en una segunda transacción.

---

## 15. Planner-state must not repair aggregate silently

`GET /api/planner-state` puede detectar una inconsistencia entre:

```text
occurrence.status
```

y:

```text
deriveOccurrenceStatus(segments)
```

pero no debe repararla silenciosamente.

Un GET continúa siendo:

```text
lectura
```

No una operación de reparación.

Las inconsistencias deben producir:

```text
error controlado / logging / test failure
```

según corresponda.

---

## 16. `status_reason` becomes `conflict_reason`

El concepto actual:

```text
status_reason
```

debe evolucionar a:

```text
conflict_reason
```

porque el conflicto puede modificar:

```text
status
segments
estructura temporal
```

aunque el aggregate status permanezca igual.

---

## 17. Migration strategy for `conflict_reason`

Para este proyecto se aprueba:

```text
direct coordinated rename
```

Conceptualmente:

```text
status_reason
→ conflict_reason
```

en migration 004.

No mantener dos columnas indefinidamente.

---

## 18. Coordinated rollout requirement

El rename directo es breaking para el backend actual.

Por tanto:

```text
migration 004 NO debe aplicarse a vcs_dev
hasta que el backend compatible esté preparado
```

La migration puede desarrollarse y probarse primero en:

```text
PostgreSQL efímero
```

Cuando migration + backend compatible estén listos:

```text
se aplican coordinadamente
```

al entorno de desarrollo real.

---

## 19. Conflict reason values

Valores iniciales aprobados:

```text
priority_override
user_forced_override
```

No agregar valores especulativos.

---

## 20. `source_occurrence_id`

`source_occurrence_id` representa:

> La occurrence source del último conflicto que modificó el estado o la
> estructura temporal de target.

Si:

```text
A modifica U
```

guardar:

```text
U.source_occurrence_id = A.id
```

Si posteriormente:

```text
B vuelve a modificar U
```

actualizar:

```text
U.source_occurrence_id = B.id
```

---

## 21. Latest conflict wins

No conservar:

```text
first conflict forever
```

ni:

```text
conflictSources[]
```

Las columnas:

```text
conflict_reason
source_occurrence_id
```

representan:

```text
el conflicto más reciente
```

que modificó target.

---

## 22. Moving a referenced source

Una occurrence utilizada como:

```text
source_occurrence_id
```

puede moverse posteriormente mientras las demás reglas del dominio lo
permitan.

No mantener el lock actual que prohíbe automáticamente modificar su horario
solo por ser source histórico.

Mover source:

```text
NO borra
NO modifica
```

la metadata histórica almacenada en target.

---

## 23. Deleting a referenced source

En v1 conservar:

```text
source_occurrence_id FK
ON DELETE NO ACTION
```

Una occurrence que todavía es referenciada mediante:

```text
source_occurrence_id
```

NO puede borrarse todavía.

Esto es deliberadamente conservador.

---

## 24. Why source deletion remains restricted

Las alternativas actuales presentan problemas:

```text
SET NULL
→ pierde la única referencia causal almacenada

CASCADE
→ sería incorrecto porque borraría target

tombstone
→ todavía no existe

event log
→ fuera de v1
```

Por tanto:

```text
NO ACTION
```

es la decisión reversible más segura para v1.

La política puede revisarse cuando exista un modelo histórico más completo.

---

## 25. Remove movement lock, preserve deletion protection

La implementación debe separar:

```text
source movement protection
```

de:

```text
source deletion protection
```

Resultado aprobado:

```text
MOVE source
→ permitido si dominio lo permite

DELETE referenced source
→ rechazado en v1
```

Los tests actuales que tratan ambas cosas como el mismo lock deberán
actualizarse.

---

## 26. Conflict confirmation granularity

La confirmación de conflictos NO debe autorizar únicamente:

```text
occurrenceId
```

porque una occurrence puede tener múltiples segments y el fragmento concreto
puede cambiar entre requests.

La autorización debe identificar el blocker concreto.

---

## 27. Confirmed conflict snapshot

El contrato debe contener conceptualmente:

```text
occurrenceId
segmentId
startTime
endTime
status
```

Ejemplo:

```js
{
  occurrenceId: "...",
  segmentId: "...",
  startTime: "14:00",
  endTime: "15:00",
  status: "pending"
}
```

---

## 28. Why confirmation includes a snapshot

Si el usuario confirmó:

```text
14:00–15:00 pending
```

pero antes de ejecutar el backend encuentra:

```text
14:00–15:30 pending
```

o:

```text
14:00–15:00 completed
```

la confirmación anterior:

```text
YA NO ES VÁLIDA
```

porque la consecuencia cambió.

El backend debe volver a presentar el conflicto.

---

## 29. Revalidation remains mandatory

Después de recibir confirmación:

```text
reconsultar blockers actuales
```

dentro de la transacción.

No modificar silenciosamente:

```text
nuevos segments
nuevos blockers
blockers cuyo intervalo cambió
blockers cuyo status cambió
```

---

## 30. `not_finished` blocks schedule

Corregir la divergencia actual.

Statuses que ocupan tiempo:

```text
pending
in_progress
completed
not_finished
```

Statuses que no ocupan tiempo:

```text
cancelled
not_completed
```

Esta regla debe quedar alineada en:

```text
backend
frontend
tests
```

---

## 31. General occurrence envelope

`Occurrence.start_time` y:

```text
Occurrence.end_time
```

se conservan.

Representan:

```text
ventana general
```

No representan necesariamente:

```text
ocupación continua
```

---

## 32. Conflict authority

Los conflictos reales deben calcularse mediante:

```text
segment.start_time
segment.end_time
segment.status
```

No únicamente mediante el envelope general del parent.

---

## 33. Default segment

Toda occurrence nueva normal nace con:

```text
1 default segment
```

igual a su rango general.

Ejemplo:

```text
Occurrence:
08:00–10:00
pending
```

crea:

```text
Segment:
08:00–10:00
pending
```

---

## 34. Existing data backfill

Migration 004 debe crear exactamente un segment por occurrence existente:

```text
segment.start_time = occurrence.start_time

segment.end_time = occurrence.end_time

segment.status = occurrence.status
```

No inferir:

```text
pausas
splits
interrupciones
segmentación histórica
```

que la base actual no puede demostrar.

---

## 35. Segment IDs

Los segments persistidos utilizan:

```text
UUID
```

generado de forma canónica durante creación/backfill.

No derivar IDs usando:

```text
PlanItem
fecha
horario
ordinal
```

---

## 36. `origin_reason`

Agregar:

```text
origin_reason
```

nullable.

Valor inicial aprobado:

```text
conflict_insertion
```

---

## 37. Normal occurrence origin

Una occurrence que nace normalmente utiliza:

```text
origin_reason = NULL
```

No agregar:

```text
normal_creation
normal
regular
```

por ahora.

---

## 38. Conflict insertion origin

Si una occurrence nace y su creación provoca modificación conflictiva de otra
occurrence:

```text
origin_reason = conflict_insertion
```

---

## 39. `last_conflict_action`

Agregar:

```text
last_conflict_action
```

nullable.

Valores iniciales aprobados:

```text
conflict_insertion
conflict_move
```

---

## 40. Conflict caused by creation

Si A nace provocando conflicto:

```text
A.origin_reason = conflict_insertion
A.last_conflict_action = conflict_insertion
```

---

## 41. Conflict caused by movement

Si A ya existía y posteriormente se mueve provocando conflicto:

```text
A.origin_reason
```

NO cambia.

Actualizar:

```text
A.last_conflict_action = conflict_move
```

---

## 42. Metadata is intentionally incomplete history

Los campos:

```text
conflict_reason
source_occurrence_id
origin_reason
last_conflict_action
```

NO forman un event log.

No pueden responder preguntas como:

```text
¿Cuántas veces se movió esta occurrence?
¿Cuántos conflictos produjo?
¿Qué conflicts tuvo históricamente?
```

Eso requerirá posteriormente:

```text
event log
o
analytics
```

No implementar todavía.

---

## 43. Time precision

Mantener como precisión canónica de VCS:

```text
HH:MM
```

Aunque PostgreSQL `TIME` pueda almacenar segundos/fracciones.

No introducir precisión a segundos en OccurrenceSegment v1.

Backend y API deben continuar rechazando datos temporales no canónicos en
lugar de truncarlos silenciosamente.

---

## 44. Pure movement

Si cambia:

```text
Occurrence.start_time
Occurrence.end_time
```

pero la duración general permanece exactamente igual:

```text
translate all segments by same delta
```

Mantener:

```text
segment IDs
segment statuses
distancias internas
huecos
duraciones
```

---

## 45. Resize

Si cambia la duración general:

```text
NO escalar
NO comprimir
NO expandir
```

automáticamente los segments.

El usuario puede elegir:

```text
ajustar segments manualmente
```

o:

```text
Restablecer segmentación
```

---

## 46. Resize editor behavior

El editor puede aceptar temporalmente un draft donde algunos segments queden
fuera del nuevo rango.

Ese draft:

```text
NO puede persistirse todavía
```

La UI debe señalar qué segments requieren corrección.

---

## 47. Reset segmentation

La acción:

```text
Restablecer segmentación
```

debe:

```text
1. eliminar la segmentación actual
2. crear exactamente un nuevo Segment
3. start = occurrence.start_time
4. end = occurrence.end_time
5. status inicial = aggregate anterior
6. volver a validar dominio
```

El nuevo segment puede recibir:

```text
nuevo UUID
```

No es necesario conservar artificialmente el ID de un antiguo fragmento.

---

## 48. Reset validation

Después del reset volver a validar:

```text
temporal phase
completed future rule
conflicts
bounds
status
aggregate
```

Heredar el aggregate anterior no garantiza que siga siendo válido en el nuevo
rango.

---

## 49. Apply Week / Apply Future — simple occurrences

Una occurrence simple cumple:

```text
segment_count = 1

segment.start_time = occurrence.start_time

segment.end_time = occurrence.end_time
```

Las mutaciones recurrentes pueden seguir trabajando casi como ahora sobre
estas occurrences, actualizando coherentemente:

```text
parent
+
single segment
```

---

## 50. Apply Week / Apply Future — custom segmented pure movement

Si una occurrence custom-segmented solamente se mueve manteniendo la misma
duración:

```text
trasladar todos sus segments por el mismo delta
```

siguiendo las reglas normales.

---

## 51. Apply Week / Apply Future — custom segmented resize

En la primera implementación:

```text
RECHAZAR resize automático
```

de una occurrence custom-segmented dentro de una operación batch.

No:

```text
resetear silenciosamente
escalar
recortar
```

sus segments.

La UI debe informar que esa occurrence necesita resolución explícita.

Una UX batch más avanzada puede diseñarse posteriormente.

---

## 52. Recurring segmentation

OccurrenceSegment v1 NO implementa:

```text
segment templates recurrentes
```

La segmentación runtime de una occurrence:

```text
NO se hereda
```

a futuras occurrences.

---

## 53. Future recurring segmentation

Más adelante el usuario podrá decidir explícitamente convertir una
segmentación en planificación de:

```text
GenerationSlot
```

pero esa feature queda fuera de v1.

---

## 54. Persistent reconciliation

La reconciliación temporal debe dejar de depender únicamente del frontend.

Crear una autoridad persistente backend para:

```text
pending → not_completed
in_progress → not_finished
```

segment por segment.

Después:

```text
derive aggregate
persist aggregate
```

---

## 55. Two reconciliation moments

Ejecutar reconciliation:

```text
CURRENT_DAY
→ PREVIOUS_EDITABLE_DAY
```

y volver a ejecutarla antes de:

```text
PREVIOUS_EDITABLE_DAY
→ FROZEN_HISTORY
```

La segunda ejecución debe ser:

```text
idempotente
```

---

## 56. GET planner-state must remain read-only

No convertir:

```text
GET /api/planner-state
```

en una operación que modifique silenciosamente PostgreSQL.

La reconciliación debe ser una operación explícita del backend.

---

## 57. Initial reconciliation orchestration

Para la primera implementación se aprueba conceptualmente:

```text
client/bootstrap
→ request reconciliation
→ reconciliation backend transaction
→ GET planner-state
→ hydrate
```

El endpoint/nombre HTTP exacto puede definirse durante la fase correspondiente.

Ejemplo conceptual:

```text
POST /api/planner/reconcile
GET  /api/planner-state
```

No considerar este nombre como contrato definitivo todavía.

---

## 58. Future reconciliation scheduling

En producción futura:

```text
job
worker
scheduler
```

puede invocar el mismo service de reconciliación.

No duplicar reglas temporales para el job.

---

## 59. Frontend reconciliation authority

Cuando la reconciliación persistente backend esté activa:

```text
el frontend deja de ser autoridad
```

para reconciliar estados.

Puede:

```text
previsualizar
mostrar
actualizar UI
```

pero no mantener una segunda fuente de verdad independiente.

---

## 60. Planner-state contract

Mantener los campos actuales:

```text
id
planItemId
date
startTime
endTime
status
sourceGenerationSlotId
```

y agregar:

```text
segments[]
```

---

## 61. Segments contract

Cada segment debe exponer al menos:

```text
id
startTime
endTime
status
```

Orden:

```text
startTime
endTime
id
```

de forma determinista.

---

## 62. Conflict context API

La API debe evolucionar desde:

```text
statusContext
```

hacia:

```text
conflictContext
```

conceptualmente:

```js
{
  reason,
  sourceOccurrenceId
}
```

`conflictContext` es la representación API de:

```text
conflict_reason
source_occurrence_id
```

---

## 63. API migration strategy

Como VCS todavía no está desplegado públicamente y frontend/backend se
controlan juntos:

```text
no mantener compatibilidad legacy indefinida
```

Durante una fase corta de implementación puede existir un alias técnico si
facilita el rollout/tests.

El objetivo final debe ser:

```text
conflictContext
```

como único nombre público.

---

## 64. Mutation API must express intent

El PATCH actual:

```text
{date,startTime,endTime}
```

resulta ambiguo para una occurrence multi-segment.

La nueva arquitectura debe distinguir explícitamente:

```text
translate occurrence

resize occurrence

mutate segment

split/trim segment

reset segmentation
```

No inferir operaciones destructivas basándose únicamente en diferencias entre
horarios.

---

## 65. Endpoint design

Los endpoints/payloads exactos se diseñarán durante la fase de mutaciones.

Principio obligatorio:

```text
la intención de la operación debe ser explícita
```

especialmente para:

```text
resize
segment mutation
conflict resolution
```

---

## 66. Transaction isolation

Mantener:

```text
SERIALIZABLE
```

para mutaciones estructurales/conflictivas.

No asumir que SERIALIZABLE reemplaza:

```text
locks deterministas
final-state validation
retry controlado
```

---

## 67. Lock ordering

Orden conceptual recomendado:

```text
1. PlanItem/config cuando aplique
2. occurrences afectadas ordenadas determinísticamente
3. segments afectados ordenados determinísticamente
4. reconsultar blockers
5. construir final state
6. validar
7. persistir
8. COMMIT
```

El orden exacto debe ser uniforme entre services para reducir deadlocks.

---

## 68. Parent lock before aggregate mutation

Dos writers que modifican segments de la misma occurrence deben bloquear el
parent antes de:

```text
deriveOccurrenceStatus(...)
```

Solo un writer deriva/persiste el aggregate del parent a la vez.

---

## 69. Final-state validation

Las operaciones complejas deben validar:

```text
el resultado final completo
```

No exigir que cada estado intermedio dentro de la transacción sea un estado
que pudiera persistirse aisladamente.

Esto permite:

```text
split
replace
swap
multi-blocker resolution
```

de manera coherente.

---

## 70. Atomicity

Una operación que modifica:

```text
source occurrence
target occurrence
segments
aggregates
conflict metadata
origin/action metadata
```

debe ejecutar:

```text
COMMIT completo
```

o:

```text
ROLLBACK completo
```

Nunca persistir resultados parciales.

---

## 71. No direct occurrence status mutation

Eliminar progresivamente las operaciones públicas que hacen:

```text
Occurrence.status = X
```

directamente.

Los controles operan sobre:

```text
Segment.status
```

y después:

```text
Occurrence.status = deriveOccurrenceStatus(...)
```

---

## 72. Single-segment compatibility

Para:

```text
Occurrence
└── Segment 1
```

la UI puede seguir comportándose visualmente casi igual.

El status control aparentemente general:

```text
realmente modifica Segment 1.status
```

y el parent aggregate resulta igual.

---

## 73. Multi-segment status UI

Cuando una occurrence tenga múltiples segments:

```text
Occurrence.status
```

es un resumen informativo.

Cada segment conserva:

```text
su propio status control
```

Las operaciones globales sobre todos los segments deben ser acciones bulk
explícitas.

---

## 74. Selection model

Frontend debe evolucionar hacia:

```text
selectedOccurrenceId
selectedSegmentId
```

Seleccionar un segment:

```text
resalta visualmente toda su occurrence
```

y además:

```text
identifica específicamente el segment activo
```

---

## 75. Duration

La duración visible de una occurrence es:

```text
SUM(end_time - start_time)
```

de todos sus segments.

No excluir del cálculo por ahora segments:

```text
cancelled
not_completed
```

La duración estructural es distinta de futuras métricas estadísticas.

---

## 76. Monthly aggregate remains separate

No confundir:

```text
Occurrence.status
```

derivado de sus segments

con:

```text
deriveAggregateOccurrenceDisplay(...)
```

que resume múltiples occurrences del mismo PlanItem/día para la vista
mensual.

Son dos aggregates distintos.

Deben mantener:

```text
nombres
responsabilidades
tests
```

separados.

---

## 77. No event log in v1

No implementar:

```text
event log
conflict history table
conflictSources[]
movement history
```

durante OccurrenceSegment v1.

La arquitectura debe permitir incorporarlos posteriormente.

---

## 78. No pause/resume implementation in v1

OccurrenceSegment v1 hace posible posteriormente:

```text
pause
resume
live tracking
```

pero no debe implementar todavía esa UX ni timers.

---

## 79. No advice system in v1

Metadata como:

```text
origin_reason
last_conflict_action
```

puede ser útil para futuros consejos.

OccurrenceSegment v1 NO implementa todavía:

```text
habit suggestions
automatic planning recommendations
pattern detection
```

---

## 80. Multiuser compatibility

OccurrenceSegment v1 debe seguir siendo compatible con la futura evolución
de VCS hacia:

```text
users
ownership
multiuser PostgreSQL
```

No diseñar una base separada para este módulo únicamente por introducir
segments.

El modelo seguirá formando parte de la base principal de VCS.

---

## 81. Implementation sequence

Implementar OccurrenceSegment de forma incremental.

### Phase 1 — PostgreSQL prototype

Probar en PostgreSQL efímero:

```text
occurrence_segments schema
backfill
btree_gist availability
sibling exclusion constraint
001 → 004 migration path
rollback/failure behavior
```

No modificar `vcs_dev`.

---

### Phase 2 — Migration 004

Crear:

```text
004_occurrence_segments.sql
```

incluyendo las decisiones aprobadas.

No modificar:

```text
001
002
003
```

---

### Phase 3 — Backend read compatibility

Backend debe:

```text
leer segments
serializar segments[]
preservar parent fields
validar consistencia
```

Todavía evitar mutaciones segmentarias ambiguas.

---

### Phase 4 — Frontend read/display compatibility

Frontend debe:

```text
deep clone segments
validar segments
render single segment sin regresión
expandir multi-segment
mostrar duración sumada
manejar selectedOccurrenceId/selectedSegmentId
```

---

### Phase 5 — Aggregate domain

Implementar:

```text
deriveOccurrenceStatus(...)
```

como autoridad backend.

Actualizar:

```text
not_finished
```

para que bloquee agenda.

---

### Phase 6 — Persistent reconciliation

Implementar reconciliation segmentaria:

```text
TODAY → PREVIOUS_EDITABLE_DAY
```

y:

```text
PREVIOUS_EDITABLE_DAY → FROZEN_HISTORY
```

con aggregate en la misma transacción.

---

### Phase 7 — Segment mutations

Implementar de forma explícita:

```text
segment status mutation
segment create
segment delete
trim
split
translate
resize
reset segmentation
```

según scope aprobado.

---

### Phase 8 — Apply Week / Apply Future

Adaptar recurring mutations:

```text
simple parents
custom translate
custom resize rejection/explicit resolution
```

sin perder custom segmentation.

---

### Phase 9 — Segment-aware conflict engine

Implementar:

```text
segment blockers
priority_override
user_forced_override
confirmed conflict snapshots
split/trim/full coverage
aggregate recalculation
metadata
TOCTOU revalidation
```

---

### Phase 10 — Conflict UX

Implementar:

```text
Ajustar
Segmentar y continuar
Finalizar y continuar
Cancelar y continuar
Confirmar corrección
```

según las reglas normativas.

---

### Phase 11 — Cleanup

Retirar:

```text
legacy occurrence-level status writes
legacy conflict authority
legacy frontend reconciliation authority
statusContext naming
```

cuando todos los consumers hayan migrado.

---

### Phase 12 — Final verification

Ejecutar:

```text
unit tests
frontend tests
backend tests
PostgreSQL integration
migration 001→004
concurrency tests
desktop browser verification
mobile browser verification
F5 persistence
consistency audit
```

---

## 82. Migration 004 application to real `vcs_dev`

No aplicar migration 004 al `vcs_dev` real únicamente porque el archivo SQL
ya exista.

Primero deben estar preparados:

```text
migration verified in ephemeral PostgreSQL
backend compatible with renamed conflict_reason
backend capable of reading required segments
```

Después puede programarse la aplicación controlada sobre:

```text
vcs_dev
```

---

## 83. Decision hierarchy

Para OccurrenceSegment v1 utilizar:

```text
STATUS_CONFLICT_RULES.md
→ comportamiento del producto

OCCURRENCE_SEGMENT_V1.md
→ modelo normativo

OCCURRENCE_SEGMENT_TECHNICAL_AUDIT.md
→ evidencia del estado actual y alternativas

OCCURRENCE_SEGMENT_DECISIONS.md
→ alternativas técnicas elegidas
```

Si una nueva implementación descubre una incompatibilidad técnica:

```text
NO cambiar silenciosamente la regla
```

Documentar:

```text
problema
consecuencia
alternativas
```

y solicitar revisión humana.

---

## 84. Final technical direction

La arquitectura aprobada para OccurrenceSegment v1 es:

```text
PostgreSQL
├── strong local structural constraints
├── occurrence_segments
├── FK ON DELETE CASCADE
├── positive interval CHECK
├── status CHECK
└── sibling exclusion constraint when btree_gist is viable

Python domain
├── segment bounds
├── at least one segment
├── aggregate status
├── temporal phase
├── split / trim / translate
├── conflict rules
└── final-state validation

Application services
├── SERIALIZABLE transactions
├── deterministic locking
├── atomic graph mutations
├── blocker revalidation
└── controlled retry

Frontend
├── visualization
├── draft editing
├── explicit user confirmation
└── no independent domain authority
```

Principio técnico rector:

> PostgreSQL protege las invariantes estructurales que puede expresar de forma
> simple y robusta. El dominio backend protege las reglas que dependen del
> estado completo, del tiempo y de la intención del usuario. Ninguna capa debe
> mantener una segunda interpretación independiente del mismo dato.
