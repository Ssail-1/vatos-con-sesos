# OccurrenceSegment v1

## 1. Purpose

`OccurrenceSegment` permite representar una sola `Occurrence` mediante uno o
varios intervalos continuos de tiempo.

El objetivo es distinguir:

```text
Occurrence
→ instancia lógica de una actividad
→ conserva su ventana general

OccurrenceSegment
→ intervalos concretos dentro de esa occurrence
→ conserva status individual
```

Ejemplo:

```text
Occurrence:
Estudiar

general:
13:00–17:00

segments:
13:00–14:00
14:30–17:00
```

Esto continúa representando:

```text
1 Occurrence
```

no:

```text
2 Occurrences
```

---

## 2. Motivation

El modelo actual:

```text
Occurrence
├── start_time
└── end_time
```

solo puede representar ocupación continua.

Sin embargo, VCS necesita representar casos como:

```text
Estudiar
13:00–17:00
```

interrumpido por:

```text
Lavar ropa
14:00–14:30
```

Resultado:

```text
Estudiar
general:
13:00–17:00

segments:
13:00–14:00
14:30–17:00
```

Esto permitirá posteriormente features como:

```text
pause
resume
live tracking
interruptions
effective duration
comparison between planned and actual time
```

sin convertir cada interrupción en una occurrence diferente.

---

## 3. Non-goals for v1

OccurrenceSegment v1 NO implementa todavía:

```text
cronómetro en vivo
pause/resume UI
fullscreen activity tracking
automatic Pomodoro
historical event log
segment templates recurrentes
analytics avanzadas
automatic habit recommendations
```

La arquitectura debe permitir esas features en el futuro, pero no
implementarlas por iniciativa en esta fase.

---

## 4. Domain model

La estructura conceptual será:

```text
PlanItem
│
├── GenerationConfig
│      │
│      └── GenerationSlot
│
└── Occurrence
       │
       ├── start_time
       ├── end_time
       ├── status
       ├── conflict_reason
       ├── source_occurrence_id
       ├── source_generation_slot_id
       ├── origin_reason
       ├── last_conflict_action
       │
       └── OccurrenceSegments
              ├── Segment 1
              ├── Segment 2
              └── ...
```

---

## 5. Occurrence remains the logical unit

`Occurrence` continúa siendo la unidad lógica principal.

Conserva:

```text
id
plan_item_id
occurrence_date
start_time
end_time
status
source_generation_slot_id
source_occurrence_id
```

y el nuevo contexto definido para conflictos/origen.

Los campos:

```text
start_time
end_time
```

NO se eliminan.

Representan:

```text
la ventana general de la occurrence
```

---

## 6. OccurrenceSegment schema

Agregar una tabla conceptual:

```text
occurrence_segments
```

con al menos:

```text
id
occurrence_id
start_time
end_time
status
```

Relación:

```text
Occurrence
1 ───── N
OccurrenceSegment
```

---

## 7. Proposed PostgreSQL table

Propuesta inicial:

```sql
CREATE TABLE occurrence_segments (
    id UUID PRIMARY KEY,
    occurrence_id UUID NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status TEXT NOT NULL,

    CONSTRAINT fk_occurrence_segment_occurrence
        FOREIGN KEY (occurrence_id)
        REFERENCES occurrences(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_occurrence_segment_time
        CHECK (start_time < end_time),

    CONSTRAINT chk_occurrence_segment_status
        CHECK (
            status IN (
                'pending',
                'in_progress',
                'completed',
                'not_completed',
                'not_finished',
                'cancelled'
            )
        )
);
```

El SQL definitivo de migration puede variar durante la implementación.

Este documento define el modelo normativo, no obliga a copiar literalmente
este snippet.

---

## 8. Segment IDs

Cada segment debe tener:

```text
UUID estable
```

Los IDs persistidos son generados por backend.

El frontend puede utilizar IDs temporales para drafts todavía no persistidos,
pero el backend devuelve la identidad canónica.

---

## 9. Every occurrence must have at least one segment

Invariante:

```text
Occurrence
→ 1..N segments
```

Nunca persistir:

```text
0 segments
```

---

## 10. Default materialization

Una occurrence nueva nace normalmente con:

```text
exactamente 1 segment
```

igual a su rango general.

Ejemplo:

```text
Occurrence:
08:00–10:00
status = pending
```

materializa:

```text
Segment 1:
08:00–10:00
pending
```

---

## 11. GenerationSlot remains continuous

`GenerationSlot` continúa utilizando:

```text
start_time
end_time
```

como hasta ahora.

Una configuración recurrente NO comienza automáticamente a almacenar
OccurrenceSegments.

Ejemplo:

```text
GenerationSlot:
13:00–17:00
```

materializa:

```text
Occurrence:
13:00–17:00

Segment 1:
13:00–17:00
```

---

## 12. Runtime segmentation is occurrence-local

Si esa occurrence termina posteriormente como:

```text
13:00–14:00
14:30–17:00
```

la modificación afecta únicamente a esa occurrence.

NO modificar automáticamente:

```text
GenerationSlot
GenerationConfig
future occurrences
other dates
```

---

## 13. Planned recurring segmentation is deferred

Si el usuario desea posteriormente que una segmentación sea recurrente:

```text
debe convertirla explícitamente en planificación
```

Una futura versión puede permitir:

```text
segment templates
```

asociadas a un `GenerationSlot`.

Esto queda fuera de OccurrenceSegment v1.

---

## 14. Segment boundaries

Todo segment debe cumplir:

```text
segment.start_time < segment.end_time
```

y:

```text
occurrence.start_time <= segment.start_time
```

```text
segment.end_time <= occurrence.end_time
```

---

## 15. Same occurrence date

OccurrenceSegment NO necesita:

```text
segment_date
```

en v1.

Todos los segments pertenecen a:

```text
Occurrence.occurrence_date
```

Por tanto una occurrence y todos sus segments existen dentro del mismo día.

---

## 16. Sibling segments cannot overlap

Dos segments pertenecientes a la misma occurrence no pueden superponerse.

Inválido:

```text
S1:
13:00–15:00

S2:
14:30–16:00
```

Válido:

```text
S1:
13:00–14:00

S2:
14:30–16:00
```

Adyacencia está permitida:

```text
13:00–14:00
14:00–15:00
```

---

## 17. Segment ordering

El orden se deriva mediante:

```text
start_time
end_time
```

La UI puede mostrar:

```text
Seg 1
Seg 2
Seg 3
```

pero el ordinal:

```text
NO se persiste
```

Un segment conserva su UUID aunque su ordinal visual cambie.

---

## 18. Segment statuses

Cada segment utiliza los statuses existentes:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

La semántica individual continúa siendo la misma.

---

## 19. Segment occupation

Statuses que ocupan tiempo:

```text
pending
in_progress
completed
not_finished
```

Statuses que NO ocupan tiempo:

```text
cancelled
not_completed
```

---

## 20. Conflict detection

La detección de conflictos deja de utilizar como verdad primaria:

```text
Occurrence.start_time
Occurrence.end_time
Occurrence.status
```

Debe utilizar:

```text
OccurrenceSegment.start_time
OccurrenceSegment.end_time
OccurrenceSegment.status
```

El rango general continúa siendo información importante, pero no demuestra
ocupación continua.

---

## 21. Example of non-conflicting envelopes

Pueden existir:

```text
Occurrence U:
13:00–17:00

segments:
13:00–14:00
14:30–17:00
```

y:

```text
Occurrence A:
14:00–14:30
```

sin conflicto temporal.

Aunque:

```text
A
```

se encuentre dentro del envelope general de U.

---

## 22. Occurrence.status becomes an aggregate

La columna actual:

```text
occurrences.status
```

se conserva.

Sin embargo su semántica cambia formalmente a:

```text
aggregate materializado
```

derivado de:

```text
OccurrenceSegment.status[]
```

---

## 23. Occurrence.status cannot be edited independently

No permitir una operación de dominio donde:

```text
Occurrence.status
```

cambie sin modificar coherentemente los segments.

Flujo:

```text
mutate segment status
↓
derive occurrence aggregate
↓
persist segments + aggregate atomically
```

---

## 24. Aggregate status: identical segments

Si todos los segments tienen el mismo status:

```text
Occurrence.status = ese status
```

Ejemplos:

```text
pending + pending
→ pending
```

```text
completed + completed
→ completed
```

```text
cancelled + cancelled
→ cancelled
```

---

## 25. Aggregate status while active/editable

Si los statuses son diferentes:

```text
si existe al menos un:
completed
in_progress
not_finished

→ occurrence.status = in_progress
```

Ejemplos:

```text
completed + pending
→ in_progress
```

```text
completed + cancelled
→ in_progress
```

```text
not_finished + pending
→ in_progress
```

```text
in_progress + not_completed
→ in_progress
```

Si no existe ningún:

```text
completed
in_progress
not_finished
```

pero existe:

```text
pending
```

entonces:

```text
occurrence.status = pending
```

Ejemplo:

```text
pending + cancelled
→ pending
```

Si no existe ninguno de los anteriores pero existe:

```text
not_completed
```

entonces:

```text
occurrence.status = not_completed
```

Ejemplo:

```text
not_completed + cancelled
→ not_completed
```

Si todos son:

```text
cancelled
```

entonces:

```text
occurrence.status = cancelled
```

---

## 26. Reconciliation

Cuando TODAY pasa a PREVIOUS_EDITABLE_DAY:

```text
pending
→ not_completed
```

```text
in_progress
→ not_finished
```

se aplica:

```text
segment por segment
```

Después:

```text
deriveOccurrenceStatus(segments)
```

---

## 27. Frozen reconciliation

Antes de pasar a:

```text
FROZEN_HISTORY
```

volver a ejecutar reconciliation.

Esto debe ser:

```text
idempotente
```

Después:

```text
recalcular aggregate
validar integridad
congelar
```

---

## 28. Historical aggregate

Después de reconciliation ya no deberían existir:

```text
pending
in_progress
```

Si todos los statuses son iguales:

```text
aggregate = ese status
```

Si son diferentes y existe:

```text
completed
o
not_finished
```

entonces:

```text
aggregate = not_finished
```

Ejemplos:

```text
completed + not_finished
→ not_finished
```

```text
completed + not_completed
→ not_finished
```

```text
completed + cancelled
→ not_finished
```

Si no existe:

```text
completed
not_finished
```

pero existe:

```text
not_completed
```

entonces:

```text
aggregate = not_completed
```

Ejemplo:

```text
not_completed + cancelled
→ not_completed
```

Si todos son:

```text
cancelled
```

entonces:

```text
aggregate = cancelled
```

---

## 29. Duration

La duración visible de una occurrence segmentada es:

```text
SUM(segment.end_time - segment.start_time)
```

de TODOS sus segments.

El status no cambia este cálculo.

Ejemplo:

```text
13:00–14:00 completed
14:30–15:30 cancelled
16:00–17:00 not_completed
```

Duración:

```text
3h
```

Esto representa:

```text
duración estructural actual
```

no estadísticas de productividad.

---

## 30. General start and end remain visible

La UI compacta puede mostrar:

```text
Inicio general
Final general
Duración segmentada
Status aggregate
```

Ejemplo:

```text
Estudiar

Inicio:   13:00
Final:    17:00
Duración: 3h30
Estado:   in_progress
```

---

## 31. Single-segment behavior

Una occurrence con:

```text
1 segment
```

debe continuar sintiéndose prácticamente igual al modelo actual.

Ejemplo:

```text
Estudiar
13:00–17:00
pending
```

El control visible de status modifica realmente:

```text
Segment 1.status
```

y el aggregate resulta automáticamente igual.

---

## 32. Multi-segment UI

Cuando existen múltiples segments:

```text
Occurrence.status
```

es principalmente informativo.

Los controles operativos pertenecen a:

```text
cada segment
```

Ejemplo conceptual:

```text
▾ Estudiar | 13:00 | 17:00 | 3h30 | in_progress

    Seg 1 · Estudiar | 13:00–14:00 | 1h   | completed
    Seg 2 · Estudiar | 14:30–15:30 | 1h   | completed
    Seg 3 · Estudiar | 16:00–17:00 | 1h   | pending
```

---

## 33. Selection model

La UI debe distinguir:

```text
selectedOccurrenceId
selectedSegmentId
```

Seleccionar cualquier segment:

```text
selecciona visualmente toda la occurrence
```

pero:

```text
el segment específico recibe un énfasis adicional
```

---

## 34. Expanded row behavior

Solo la fila principal utiliza:

```text
▾
```

para contraer.

Los segments:

```text
se muestran indentados
```

y visualmente deben sentirse como filas temporales completas.

No deben verse como un único bloque gigante de texto.

---

## 35. Pure occurrence movement

Si una occurrence cambia de horario manteniendo exactamente su duración:

```text
08:00–12:00
→
13:00–17:00
```

calcular:

```text
delta = +5h
```

y trasladar todos los segments:

```text
segment.start_time += delta
segment.end_time   += delta
```

Ejemplo:

```text
08:00–10:00
10:30–12:00
```

pasa a:

```text
13:00–15:00
15:30–17:00
```

---

## 36. Resize behavior

Si cambia la duración general:

```text
08:00–12:00
→
08:00–11:00
```

o:

```text
08:00–12:00
→
08:00–14:00
```

NO escalar automáticamente los segments.

El usuario debe elegir entre:

```text
ajustar segments manualmente
```

o:

```text
Restablecer segmentación
```

---

## 37. Manual resize editing

El editor puede permitir temporalmente:

```text
segments fuera del nuevo rango
```

mientras el usuario continúa editando el draft.

No persistir hasta que todos vuelvan a cumplir:

```text
occurrence.start_time <= segment.start_time
segment.end_time <= occurrence.end_time
```

---

## 38. Reset segmentation

`Restablecer segmentación` debe:

```text
1. eliminar la segmentación actual
2. dejar exactamente un Segment 1
3. usar el nuevo rango general
4. heredar el aggregate anterior como status inicial
5. volver a validar el resultado
```

Ejemplo:

```text
Occurrence:
08:00–11:00

Segment 1:
08:00–11:00
status = previousAggregate
```

---

## 39. Reset validation

Heredar el aggregate NO implica que siempre sea válido.

Después del reset deben volver a verificarse:

```text
temporal zone
completed future rule
conflicts
segment bounds
aggregate
```

---

## 40. Segment split

Cuando un conflicto divide un segment:

```text
Original:
08:00–12:00

Conflict:
09:00–10:00
```

resultado:

```text
08:00–09:00
10:00–12:00
```

El fragmento izquierdo conserva preferentemente:

```text
el ID original
```

El nuevo fragmento recibe:

```text
nuevo UUID
```

---

## 41. Segment trimming

Si la resta deja un único fragmento:

```text
actualizar el segment existente
```

y conservar su ID.

Ejemplo:

```text
Original:
08:00–10:00

Conflict:
09:15–11:00
```

resultado:

```text
08:00–09:15
```

con:

```text
same segment id
```

---

## 42. Segment full coverage

Si el conflicto cubre completamente un segment:

```text
NO crear un fragmento vacío
```

La resolución de status sigue las reglas normativas de
`STATUS_CONFLICT_RULES.md`.

Ejemplo posible:

```text
same segment interval
status → cancelled
```

---

## 43. Repeated segmentation

Una occurrence puede ser segmentada múltiples veces.

Ejemplo:

```text
U:
13:00–17:00
```

A produce:

```text
13:00–14:00
14:30–17:00
```

B posteriormente produce:

```text
13:00–14:00
15:00–17:00
```

C podría volver a modificar alguno de esos segments.

No establecer:

```text
maximum_segments
```

arbitrario en v1.

---

## 44. Conflict context remains occurrence-level

OccurrenceSegment NO almacena:

```text
conflict_reason
source_occurrence_id
```

El conflicto pertenece a la occurrence lógica.

Persistir en `occurrences`:

```text
conflict_reason
source_occurrence_id
```

según las reglas normativas.

---

## 45. `status_reason` migration

La columna actual:

```text
status_reason
```

debe evolucionar conceptualmente a:

```text
conflict_reason
```

porque un conflicto puede modificar:

```text
status
segments
estructura temporal
```

sin necesariamente explicar únicamente el status.

Una migration nueva debe realizar esta evolución.

No modificar migrations:

```text
001
002
003
```

---

## 46. Conflict reasons

Valores iniciales:

```text
priority_override
user_forced_override
```

`conflict_reason` conserva:

```text
el último conflicto que modificó la occurrence
```

---

## 47. Source occurrence

`source_occurrence_id` conserva:

```text
la occurrence source del último conflicto
```

Si A modifica U:

```text
U.source_occurrence_id = A.id
```

Si después B vuelve a modificar U:

```text
U.source_occurrence_id = B.id
```

---

## 48. No conflict genealogy

OccurrenceSegment v1 NO implementa:

```text
conflictSources[]
occurrence_conflict_sources
```

Los conflictos actuales se derivan de los segments actuales.

La historia completa podrá pertenecer a un futuro:

```text
event log
```

---

## 49. Origin reason

Agregar conceptualmente:

```text
origin_reason
```

en `occurrences`.

Valor inicial necesario:

```text
conflict_insertion
```

---

## 50. Conflict insertion

Si una occurrence nace y su creación provoca una resolución de conflicto:

```text
origin_reason = conflict_insertion
```

Ejemplo:

```text
Comprar tortillas
```

es creada dentro de una occurrence de Estudiar y provoca su segmentación.

---

## 51. Normal origin

Una occurrence creada sin provocar conflicto puede utilizar:

```text
origin_reason = null
```

No es necesario crear una razón para cada creación normal.

---

## 52. Last conflict action

Agregar conceptualmente:

```text
last_conflict_action
```

Valores iniciales:

```text
conflict_insertion
conflict_move
```

---

## 53. Conflict caused by creation

Si A nace causando un conflicto:

```text
A.origin_reason = conflict_insertion
A.last_conflict_action = conflict_insertion
```

---

## 54. Conflict caused by movement

Si A ya existía y es movida para provocar un conflicto:

```text
A.origin_reason
```

no cambia.

Actualizar:

```text
A.last_conflict_action = conflict_move
```

---

## 55. Metadata is not an event log

Campos como:

```text
conflict_reason
source_occurrence_id
origin_reason
last_conflict_action
```

NO permiten reconstruir toda la historia.

Conservan únicamente metadata útil actual/histórica mínima.

Para responder preguntas como:

```text
¿Cuántas veces moví esta actividad?
¿Cuántas veces interrumpió a otra?
```

será necesario un futuro:

```text
event log
o sistema de métricas
```

---

## 56. Planner-state representation

La API debe continuar devolviendo la occurrence completa.

Ejemplo conceptual:

```js
{
  id,
  planItemId,
  date,
  startTime,
  endTime,
  status,

  segments: [
    {
      id,
      startTime,
      endTime,
      status
    }
  ],

  conflictContext: {
    reason,
    sourceOccurrenceId
  },

  originReason,
  lastConflictAction
}
```

Los nombres JSON definitivos deben permanecer consistentes con las
convenciones existentes del frontend/backend.

---

## 57. Backward compatibility during migration

El frontend actual espera:

```text
Occurrence.startTime
Occurrence.endTime
Occurrence.status
```

Estos campos permanecen disponibles.

Agregar:

```text
Occurrence.segments[]
```

permite migrar progresivamente la UI sin eliminar la representación existente
de forma inmediata.

---

## 58. Migration strategy

La nueva migration puede denominarse conceptualmente:

```text
004_occurrence_segments.sql
```

Debe ser nueva e inmutable una vez aplicada.

No modificar:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
```

---

## 59. Existing occurrence backfill

Cada occurrence existente debe recibir:

```text
exactamente un initial segment
```

utilizando sus datos actuales.

Para cada occurrence existente:

```text
segment.id
→ nuevo UUID

segment.occurrence_id
→ occurrence.id

segment.start_time
→ occurrence.start_time

segment.end_time
→ occurrence.end_time

segment.status
→ occurrence.status
```

Esto preserva el comportamiento actual.

---

## 60. Backfill invariant

Después de la migration:

```text
COUNT(occurrence_segments)
>=
COUNT(occurrences)
```

y cada occurrence debe tener:

```text
at least one segment
```

---

## 61. No historical reconstruction during migration

La migration NO debe intentar inferir:

```text
interrupciones pasadas
segmentos históricos
tiempo efectivo real
```

a partir de datos anteriores.

Los datos existentes se consideran:

```text
single-segment occurrences
```

porque es lo único que la base actual puede demostrar.

---

## 62. Proposed occurrence metadata changes

Migration 004 probablemente necesitará también:

```text
status_reason
→ conflict_reason
```

y agregar:

```text
origin_reason
last_conflict_action
```

Los CHECK constraints correspondientes deben admitir únicamente los valores
aprobados.

---

## 63. Initial enum-like values

Conceptualmente:

```text
conflict_reason:
- priority_override
- user_forced_override
```

```text
origin_reason:
- conflict_insertion
```

```text
last_conflict_action:
- conflict_insertion
- conflict_move
```

Todos pueden ser:

```text
NULL
```

cuando no aplique contexto.

---

## 64. Source occurrence FK

`source_occurrence_id` continúa siendo una FK hacia:

```text
occurrences.id
```

OccurrenceSegment v1 NO redefine todavía la política completa de borrado de
esa relación.

Hasta que exista una decisión específica:

```text
preservar la semántica actual
```

y no cambiarla incidentalmente durante la migration.

---

## 65. Structural database integrity

PostgreSQL debe garantizar directamente cuando sea razonable:

```text
segment PK
segment → occurrence FK
ON DELETE CASCADE
start_time < end_time
valid segment status
valid metadata enum-like values
```

---

## 66. Cross-row integrity

Reglas como:

```text
segments dentro del rango de occurrence
siblings no superpuestos
at least one segment per occurrence
```

requieren validación que cruza rows/tablas.

La implementación puede utilizar:

```text
domain/service validation
+
transactional final-state validation
```

y, si resulta conveniente durante migration implementation:

```text
deferred constraint triggers
```

para reforzar estructuralmente PostgreSQL.

No introducir triggers complejos sin necesidad antes de validar el diseño de
la transacción.

---

## 67. Final-state validation

Las mutaciones deben validar:

```text
el estado final completo
```

no cada paso intermedio.

Esto permite operaciones como:

```text
split
swap
resize
multiple blocker resolution
```

dentro de una transacción sin rechazar estados temporales que nunca serán
persistidos.

---

## 68. Atomicity

Cualquier operación que modifique segments debe ser atómica.

Ejemplo de conflict resolution:

```text
create/move source
+
trim target segment
+
create additional fragments
+
change segment status
+
derive occurrence aggregate
+
update conflict metadata
```

debe ejecutar:

```text
COMMIT completo
```

o:

```text
ROLLBACK completo
```

---

## 69. Segment status mutation flow

Flujo conceptual:

```text
user changes segment status
↓
validate temporal zone
↓
validate completed/current-time rule
↓
validate occupying conflicts
↓
persist segment status
↓
derive occurrence aggregate
↓
persist occurrence.status
↓
commit
```

---

## 70. Single-segment status compatibility

La UX actual puede continuar utilizando el control ya existente.

Internamente:

```text
status control
→ Segment 1.status
```

y después:

```text
Occurrence.status = derived Segment 1.status
```

Esto permite migrar sin romper la experiencia simple.

---

## 71. Recurring schedule mutations

`Apply Week` y `Apply Future` continúan trabajando principalmente con:

```text
Occurrence.start_time
Occurrence.end_time
GenerationSlot
```

Pero cuando afectan occurrences ya segmentadas deben respetar las nuevas
reglas de movimiento/resize.

---

## 72. Recurring pure movement

Si una mutación recurrente mueve una occurrence:

```text
sin cambiar su duración
```

sus segments pueden trasladarse mediante el mismo delta.

---

## 73. Recurring resize

Si una mutación recurrente cambia la duración de una occurrence que posee
segmentación personalizada:

```text
NO escalar automáticamente los segments
```

La operación necesita una estrategia explícita equivalente a:

```text
adjust manually
reset segmentation
```

La UX batch definitiva debe diseñarse antes de implementar este caso sobre
múltiples occurrences segmentadas.

---

## 74. Simple future occurrences

Una occurrence futura todavía no personalizada normalmente tendrá:

```text
1 pending segment
```

igual a su general range.

En esos casos un cambio recurrente puede actualizar coherentemente:

```text
occurrence general range
+
single pending segment
```

sin perder información personalizada.

---

## 75. Custom segmentation detection

Conceptualmente se puede considerar una occurrence como:

```text
simple/unsegmented
```

cuando:

```text
segment count = 1
segment.start_time = occurrence.start_time
segment.end_time   = occurrence.end_time
```

Una occurrence es:

```text
custom segmented
```

cuando esa condición deja de cumplirse.

No es necesario persistir un boolean:

```text
is_segmented
```

porque puede derivarse.

---

## 76. Deletion

Eliminar una occurrence:

```text
DELETE occurrence
```

debe eliminar automáticamente:

```text
sus occurrence_segments
```

mediante:

```text
ON DELETE CASCADE
```

Las demás restricciones existentes sobre deletion de occurrences siguen
aplicando.

---

## 77. Manual segment deletion

Eliminar un segment individual nunca puede dejar:

```text
0 segments
```

Si el usuario intenta eliminar el último segment:

```text
rechazar
```

o transformar la intención mediante una acción de occurrence definida
explícitamente.

No eliminar implícitamente toda la occurrence.

---

## 78. Segment creation

Crear un segment manual debe validar:

```text
same parent occurrence
inside general range
positive duration
no sibling overlap
valid temporal status
conflict integrity
```

Después:

```text
derive aggregate
```

---

## 79. Future segment statuses

En una fecha futura los segments solo pueden utilizar:

```text
pending
cancelled
```

de acuerdo con las reglas temporales existentes.

No permitir:

```text
completed
in_progress
not_completed
not_finished
```

como estado futuro persistido.

---

## 80. Current-day segment statuses

En el día actual pueden utilizarse los seis statuses:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

sujetos a reglas de integridad.

---

## 81. Previous editable day segment statuses

Después de reconciliation, el día anterior editable utiliza:

```text
completed
not_completed
not_finished
cancelled
```

No debe conservar:

```text
pending
in_progress
```

como estado estable.

El usuario todavía puede corregir los segments mientras la fecha siga
editable.

---

## 82. Frozen segments

Cuando la fecha está frozen:

```text
Occurrence
OccurrenceSegment
```

son read-only.

No permitir:

```text
create
update
delete
status mutation
split
trim
resize
```

---

## 83. Completed current-time validation

Para cada segment:

```text
status = completed
```

debe cumplirse:

```text
segment.endDateTime <= currentDateTime
```

La validación se realiza a nivel segment.

Una occurrence puede tener:

```text
completed segment anterior
+
pending segment futuro
```

durante el día actual.

---

## 84. Advice and analytics compatibility

Este modelo permitirá posteriormente analizar:

```text
planned window
segment duration
interruptions
spontaneous conflict insertions
frequent conflict moves
completed partial work
actual segmentation patterns
```

Sin embargo:

```text
OccurrenceSegment v1
```

no implementa todavía el sistema de consejos.

Solo preserva la estructura necesaria para hacerlo posible.

---

## 85. Testing requirements

Antes de considerar OccurrenceSegment v1 terminado deben existir tests para:

```text
single-segment backfill

segment creation

segment update

segment deletion

last-segment protection

segment bounds

sibling overlap rejection

status aggregate

editable mixed aggregate

historical aggregate

today → previous reconciliation

previous → frozen reconciliation

completed future validation

pure occurrence movement

multi-segment translation

resize manual validation

reset segmentation

left trim

right trim

internal split

full coverage

repeated segmentation

conflict detection using segments

aggregate recomputation after conflict

atomic rollback
```

---

## 86. PostgreSQL verification

Los tests con PostgreSQL real deben verificar al menos:

```text
migration applies cleanly

existing occurrences receive one segment

FK integrity

ON DELETE CASCADE

time CHECK

status CHECK

rollback behavior

multi-segment persistence

planner-state round trip
```

---

## 87. Frontend verification

La integración frontend debe verificar:

```text
single-segment occurrence remains visually simple

multi-segment occurrence can expand/collapse

only parent row owns expand/collapse control

segments appear as temporal rows

selected occurrence + selected segment are distinguishable

status control mutates segment

aggregate status updates after refresh

duration sums segments

general start/end remain visible

F5 preserves segmentation
```

---

## 88. Implementation sequence

Orden recomendado:

```text
1. freeze normative rules
2. write migration 004
3. add repository/domain representation
4. backfill and planner-state serialization
5. aggregate status service
6. segment mutation services
7. segment-based conflict detection
8. adapt single-day mutations
9. adapt Apply Week / Apply Future
10. integrate frontend display
11. segment editor
12. full PostgreSQL + browser verification
```

No implementar:

```text
pause/resume tracking
segment recurrence templates
analytics
advice system
```

durante este scope salvo que un CURRENT_TASK posterior lo autorice.

---

## 89. Migration compatibility principle

La migration debe transformar:

```text
modelo anterior
```

en:

```text
modelo segmentado
```

sin reinterpretar historia.

Cada occurrence existente se convierte en:

```text
Occurrence
+
1 equivalent Segment
```

Por tanto, inmediatamente después de migration 004:

```text
el comportamiento observable debe seguir siendo equivalente
```

hasta que el usuario o nuevas reglas comiencen a crear múltiples segments.

---

## 90. Final principle

OccurrenceSegment v1 debe preservar cuatro niveles distintos:

```text
PlanItem
→ qué actividad es

GenerationSlot
→ cuándo debe generarse normalmente

Occurrence
→ una instancia lógica de esa actividad en una fecha

OccurrenceSegment
→ cómo esa instancia ocupa o ocupó tiempo dentro de su ventana general
```

Principio rector:

> Una occurrence conserva la intención y unidad lógica de la actividad.
> Sus segments permiten representar interrupciones, pausas y correcciones
> temporales sin destruir esa identidad ni convertir cada fragmento en una
> occurrence independiente.
