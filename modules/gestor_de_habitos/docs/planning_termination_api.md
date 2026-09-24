# Terminación persistente de planificación (schema 005)

Los comandos derivan `D`, PlanItem y procedencia desde el ID de la Occurrence
seleccionada. No aceptan payload de alcance. Respuesta exitosa:

```json
{"status":"ok","scope":"slot","selectedOccurrenceId":"<uuid>","planItemId":"<uuid>","cutoffDate":"YYYY-MM-DD","deletedOccurrenceIds":[]}
```

| Intención | Endpoint | Corte y limpieza (`date > D`) |
| --- | --- | --- |
| Solo esta aparición | `DELETE /api/occurrences/<id>` | Reutiliza exclusión por slot o borrado manual existente. |
| Este horario | `POST /api/occurrences/<id>/stop-slot-after` | `generation_slots.last_generation_date = min(actual, D)`; borra solo occurrences con ese `source_generation_slot_id`. |
| Toda la recurrencia | `POST /api/occurrences/<id>/stop-recurring-after` | Corta todos los slots y `generation_configs.stopped_from_date = min(actual, D+1)`; borra solo occurrences con procedencia de slot. |
| Todas las apariciones | `POST /api/occurrences/<id>/delete-future-after` | Igual corte recurrente y borra todas las occurrences del PlanItem, también manuales. |

`date == D` y fechas previas se conservan. El backend exige `D >= hoy` local.
Los comandos nuevos usan una transacción `SERIALIZABLE`. Un `source_occurrence_id`
externo al conjunto de borrado produce `409 source_provenance_locked`, sin limpiar
la referencia. Referencias íntegramente dentro del conjunto se borran en una
sola sentencia SQL (ver prueba PostgreSQL). Los segmentos se borran únicamente
por `ON DELETE CASCADE` de la occurrence.

Respuestas controladas: 400 (`invalid_identifier`/`invalid_payload`), 404
(`occurrence_not_found`), 409 (`history_frozen`, `slot_not_applicable`,
`recurring_not_applicable`, `source_provenance_locked`, `concurrent_conflict`),
500 (`persisted_state_invalid`) y 503 (`database_unavailable`). No se exponen
DSN, SQL ni credenciales.

## Generación y edición

`GET /api/planner-state` expone `lastGenerationDate` solo cuando existe.
El materializador Python y JS respetan el corte por slot junto con el corte
global ya existente. Apply Future rechaza un plan con algún slot detenido
(`409 planning_stopped`) porque reemplazarlo podría perder la identidad de
procedencia o reactivar la recurrencia. Apply Week conserva su rechazo de
creaciones después de `stopped_from_date`; sus apariciones ad-hoc no reactivan
un slot detenido. Reiniciar planificación deliberadamente queda fuera de esta
fase.

## Inventario de escritores activos

Todos los escritores de esta tabla son schema-005-ready, segment-aware y
aggregate-safe: escriben los children/aggregate apropiados o eliminan el grafo
entero por cascada, nunca establecen un status parent arbitrario. “N/A” en
cutoff significa que el comando no genera ni reprograma recurrencia.

| Endpoint | Servicio | Tablas modificadas | Segment-aware | Aggregate-safe | Alcance | Schema ready | Cutoff-aware |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST /api/plan-items` | `plan_item_creation_service` | `plan_items`, `generation_configs`, slots/detalles/exclusiones, `occurrences`, `occurrence_segments`; conflicto autorizado también toca blockers | Sí | Sí | Creación atómica del PlanItem | 005 | Sí, el schedule nuevo inicia sin cutoff |
| `PATCH /api/occurrence-segments/<id>/status` | `occurrence_segment_service` | `occurrence_segments`, `occurrences` (aggregate derivado) | Sí | Sí | Un segment | 005 | N/A |
| `POST /api/planner/reconcile` | `occurrence_segment_service` | `occurrence_segments`, `occurrences` (aggregate derivado) | Sí | Sí | Reconciliación temporal | 005 | N/A |
| `POST /api/occurrences/<id>/translate` | `occurrence_structure_service` | `occurrences`, `occurrence_segments`; blockers cuando autorizados | Sí | Sí | Traslación de un grafo | 005 | Sí, conserva fecha/slot dentro de reglas vigentes |
| `PUT /api/occurrences/<id>/structure` | `occurrence_structure_service` | `occurrences`, `occurrence_segments`; blockers cuando autorizados | Sí | Sí | Estructura de un grafo | 005 | N/A |
| `POST /api/occurrences/<id>/reset-segmentation` | `occurrence_structure_service` | `occurrences`, `occurrence_segments`; blockers cuando autorizados | Sí | Sí | Reset de un grafo | 005 | N/A |
| `DELETE /api/occurrences/<id>` | `occurrence_mutation_service` | `occurrences`, segments por cascada, exclusión de slot o entry manual | Sí | Sí | Una aparición | 005 | Sí, impide regeneración mediante exclusión/entry |
| `POST /api/occurrences/<id>/stop-slot-after` | `planning_termination_service` | `generation_slots`, `occurrences`, segments por cascada | Sí | Sí | Un slot, `date > D` | 005 | Sí, escribe cutoff inclusivo |
| `POST /api/occurrences/<id>/stop-recurring-after` | `planning_termination_service` | `generation_slots`, `generation_configs`, `occurrences`, segments por cascada | Sí | Sí | Toda la recurrencia, `date > D`; manuales intactas | 005 | Sí, corta slots y config |
| `POST /api/occurrences/<id>/delete-future-after` | `planning_termination_service` | `generation_slots`, `generation_configs`, `occurrences`, segments por cascada | Sí | Sí | Todas las apariciones del PlanItem, `date > D` | 005 | Sí, corta recurrencia y limpia manuales |
| `POST /api/plan-items/<id>/apply-week` | `week_mutation_service` | `occurrences`, `occurrence_segments`, exclusiones de slot | Sí | Sí | Edición semanal | 005 | Sí, rechaza mover un slot detenido tras el cutoff |
| `POST /api/plan-items/<id>/apply-future` | `future_schedule_service` | `generation_configs`, slots/detalles/exclusiones, `occurrences`, `occurrence_segments` | Sí | Sí | Reescritura futura | 005 | Sí, rechaza planes con slots detenidos |

`PATCH /api/occurrences/<id>` está retirado (`410`), no es escritor activo.

No queda un escritor activo que dependa del schema 003 como destino real.
`vcs_dev` sigue pendiente de rollout coordinado 004→005.
