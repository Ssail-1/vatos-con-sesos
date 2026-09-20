# OccurrenceSegment v1 — Technical audit

Estado: propuesta técnica para revisión humana. Este documento no implementa el
rediseño, no es una migración y no modifica contratos vigentes.

Fuentes normativas leídas completamente:

- `docs/architecture/OCCURRENCE_SEGMENT_V1.md`
- `docs/architecture/STATUS_CONFLICT_RULES.md`
- `modules/gestor_de_habitos/docs/valores.md`

Fuentes de implementación auditadas: migraciones `001`, `002` y `003`, backend,
frontend y pruebas actuales de `modules/gestor_de_habitos/`. El esquema se dedujo
de las migraciones; no se consultó ni modificó `vcs_dev`.

## 1. Executive summary

El modelo actual persiste cada `Occurrence` como un único intervalo
`start_time`–`end_time` con un único `status`. Esa suposición atraviesa SQL,
repositories, serialización, materialización, conflictos, priority override,
mutaciones, reconciliación, store y renderizado. OccurrenceSegment v1 no puede
resolverse añadiendo solo una tabla: cambia la unidad que ocupa agenda y la unidad
que cambia de estado.

Sí existe una ruta incremental segura. Los campos generales de `occurrences`
pueden conservarse, `occurrences.status` puede seguir siendo el aggregate
materializado y cada fila actual puede backfillearse sin pérdida conocida a un
solo segment con el mismo intervalo y estado. Esto permite introducir primero el
modelo de lectura compatible y posponer las mutaciones estructurales más riesgosas.

Las incompatibilidades principales son:

1. `scheduling_policy.BLOCKING_STATUSES` y
   `js/domain/occurrence-status.js::blocksSchedule()` excluyen `not_finished`,
   aunque v1 lo considera ocupante.
2. Todos los motores de conflicto comparan envelopes de occurrences; v1 exige
   comparar únicamente segments ocupantes.
3. El frontend cambia `occurrence.status` directamente y la reconciliación actúa
   sobre la occurrence; v1 exige cambiar/reconciliar segments y volver a derivar
   el aggregate.
4. `status_reason` solo admite `priority_override` y está acoplado a los estados
   `cancelled/not_finished`; `conflict_reason` será metadato histórico estructural,
   admitirá también `user_forced_override` y no debe depender del aggregate actual.
5. `source_occurrence_id` tiene FK `NO ACTION` implícita y los services bloquean
   cambios del source. Preservar historial ya no justifica bloquear su movimiento;
   su política de borrado sí necesita una decisión explícita.
6. `Apply Week`, `Apply Future` y `PATCH occurrence` presuponen un único intervalo.
   Un simple traslado puede traducir todos los segments, pero un resize no puede
   escalarlos ni recortarlos automáticamente.

**Recomendación para revisión:** arquitectura híbrida. PostgreSQL debe proteger
estructura local (PK, FK con cascade, estados, duración positiva) y, si se aprueba
`btree_gist`, el no-overlap entre hermanos con una exclusion constraint diferible.
Una capa de dominio pura debe validar el estado final, derivar el aggregate y
orquestar cada mutación en una transacción `SERIALIZABLE`. La existencia de al
menos un segment y los bounds respecto del parent deben validarse inicialmente en
service; un constraint trigger diferible puede evaluarse más adelante, no entrar
por defecto en la primera implementación.

No se comprobó el catálogo de una base desplegada. En particular, disponibilidad
y privilegios para `CREATE EXTENSION btree_gist` deben validarse en una base
efímera antes de decidir la migration 004.

## 2. Current database model

### Modelo resultante de 001 + 002 + 003

`modules/gestor_de_habitos/db/migrations/001_initial_schema.sql` crea
`public.occurrences` con:

| Columna | Tipo/null actual | Función |
|---|---|---|
| `id` | `UUID NOT NULL`, PK `occurrences_pkey` | identidad lógica |
| `plan_item_id` | `UUID NOT NULL` | FK a `plan_items(id)` |
| `occurrence_date` | `DATE NOT NULL` | día local |
| `start_time` | `TIME NOT NULL` | inicio del único intervalo actual |
| `end_time` | `TIME NOT NULL` | fin del único intervalo actual |
| `status` | `VARCHAR(30) NOT NULL` | estado único actual |
| `status_reason` | `VARCHAR(30)` | solo priority override |
| `source_occurrence_id` | `UUID` | self-FK al source del override |
| `source_generation_slot_id` | `UUID`, añadida por 003 | procedencia de generación |

Constraints vigentes:

- `occurrences_pkey (id)`.
- `chk_occurrence_time_range`: `start_time < end_time`.
- `chk_occurrence_status`: los seis valores `pending`, `in_progress`,
  `completed`, `not_completed`, `not_finished`, `cancelled`.
- `chk_occurrence_status_context`: 002 reemplaza la versión susceptible a
  `UNKNOWN`; exige ambos campos nulos o `status_reason IS NOT NULL AND
  status_reason = 'priority_override' AND source_occurrence_id IS NOT NULL`.
- `chk_occurrence_override_status`: con reason no nulo, el estado debe ser
  `cancelled` o `not_finished`.
- `chk_occurrence_source_not_self`: no puede apuntarse a sí misma.
- `fk_occurrence_plan_item`: FK a `plan_items(id)`, sin cláusula `ON DELETE`, por
  tanto `NO ACTION`.
- `fk_occurrence_source`: self-FK, también `NO ACTION` implícito.
- `fk_occurrence_source_generation_slot`: FK a `generation_slots(id) ON DELETE
  SET NULL`.

El único índice adicional específico de occurrences creado por estas migraciones
es el partial unique index
`uq_occurrences_source_generation_slot_date(source_generation_slot_id,
occurrence_date) WHERE source_generation_slot_id IS NOT NULL`. Garantiza como
máximo una occurrence por slot/fecha para filas con procedencia conocida. No hay
índice general por `plan_item_id/date/status`, constraint de conflicto temporal ni
tabla `occurrence_segments`.

`public.generation_configs` conserva una relación 1:1 con `plan_items` mediante
PK/FK `plan_item_id`; 003 elimina `default_start_time/default_end_time`, reemplaza
`chk_generation_mode_rules` y mantiene `weekly`, `interval_days` y
`manual_dates`. La FK `fk_generation_config_plan_item` usa `NO ACTION` implícito.

`003_multi_slot_scheduling.sql` crea:

- `generation_slots(id UUID PK, plan_item_id UUID, start_time TIME, end_time
  TIME)`, con `chk_generation_slot_time_range`, FK
  `fk_generation_slots_generation_configs ... ON DELETE CASCADE` e índice
  `idx_generation_slots_plan_item_id`;
- `generation_slot_weekdays`, `generation_slot_dates` y
  `generation_slot_excluded_dates`, todas con FK al slot `ON DELETE CASCADE`;
- elimina las tablas legacy `generation_weekdays` y `generation_date_entries`;
- backfillea slots y `source_generation_slot_id` solo cuando la procedencia es
  demostrable.

No hay `ON DELETE CASCADE` desde occurrence hacia sus datos porque aún no existen
datos hijos. En v1, un segment sí es componente del parent y la FK natural es
`occurrence_segments.occurrence_id REFERENCES occurrences(id) ON DELETE CASCADE`.

### Precisión temporal observada

SQL acepta `TIME` con segundos/fracciones, mientras
`planner_state_service.py::_time_string()` y sus pruebas rechazan valores
subminuto en vez de truncarlos (`test_subminute_time_is_rejected_instead_of_truncated`).
El nuevo esquema debe conservar `TIME`, pero la API/service debe seguir imponiendo
la precisión canónica `HH:MM` o la migration debe decidir explícitamente si
normaliza datos. No se encontró evidencia para cambiar esa regla.

## 3. Current backend assumptions

Los siguientes puntos asumen actualmente `1 Occurrence = 1 intervalo + 1 status`:

- `repositories/planner_state_repository.py` selecciona directamente
  `occurrences.start_time`, `end_time`, `status`, `status_reason` y
  `source_occurrence_id`; no existe query hija. La lectura usa una sola conexión
  `REPEATABLE READ READ ONLY`.
- `planner_state_service.py::_build_occurrences()` serializa esos campos como
  `startTime`, `endTime`, `status` y opcional `statusContext`. Exige reason
  `priority_override`, status desplazado y source existente. No puede reconstruir
  segments, `originReason` ni `lastConflictAction`.
- `plan_item_materializer.py::_draft()` y
  `materialize_occurrence_drafts()` generan un draft plano pending por horario.
- `plan_item_creation_service.py::_validate_internal_conflicts()` y
  `_current_conflicts()` comparan drafts/rows planos. `create_plan_item()` usa una
  conexión y `SERIALIZABLE`, inserta el grafo y aplica overrides atómicamente.
- `repositories/plan_item_repository.py::list_blocking_occurrences()` filtra por
  status del parent y devuelve su envelope. `insert_plan_item_graph()` inserta
  parents, no hijos. `apply_priority_overrides()` cambia directamente
  `occurrences.status/status_reason/source_occurrence_id`.
- `scheduling_policy.py::BLOCKING_STATUSES` contiene `pending`, `in_progress` y
  `completed`; `not_finished` falta respecto de v1. El overlap usa los tiempos de
  la occurrence.
- `occurrence_mutation_service.py::patch_occurrence()` actualiza un único
  envelope; no distingue translate de resize. `_validate_occurrence_conflicts()`
  trabaja con parents. `delete_occurrence()` decide por aggregate actual y borra
  el parent; un futuro cascade de segments sería compatible.
- `repositories/occurrence_repository.py` bloquea y actualiza parents mediante
  `FOR UPDATE`. `lock_blocking_occurrences()` no obtiene segments. Las funciones
  `lock_status_context_dependents*()` impiden mutar/borrar un source referenciado.
- `week_mutation_service.py::_candidate_state()`,
  `_validate_final_internal_state()` y `_validate_external_conflicts()` modelan
  cada candidato como un intervalo/status. `apply_week()` sí valida el estado final
  de un batch en una transacción, una base reutilizable para v1.
- `future_schedule_service.py::_is_old_baseline()` identifica baseline comparando
  el envelope con el GenerationSlot. `_candidate_state()` y
  `_validate_final_state()` no conocen custom segmentation. `apply_future()`
  preserva overrides/ad-hoc/history y usa `SERIALIZABLE`, pero puede clasificar
  erróneamente una occurrence segmentada como baseline simple.
- `app.py` coordina HTTP y mapea errores sanitizados. Sus rutas no contienen la
  lógica de dominio; esa separación puede preservarse.

No se encontró un proceso backend persistente de reconciliación temporal. La
reconciliación existente está en memoria en el frontend, por lo que hoy puede
desaparecer al recargar y no constituye autoridad persistente.

Priority override ya protege TOCTOU de creación: el segundo POST vuelve a leer y
exige conflictos actuales contenidos en los IDs confirmados. Sin embargo, su
granularidad es occurrence completa y el efecto cambia todo el status del blocker.
Con segments, deben recalcularse intervalos ocupantes y aplicarse consecuencias a
los fragments/segments afectados antes de recalcular ambos aggregates.

## 4. Current frontend assumptions

- `js/state/planner-store.js::cloneOccurrence()` clona `statusContext`, no una
  colección hija. `validateOccurrenceDraft()` y `buildHydratedPlannerState()`
  validan un solo intervalo/status y una referencia source a nivel occurrence.
- `planner-store.js::findOccurrenceConflict()` y la copia local de priority
  override comparan/cambian occurrences completas.
- `planner-store.js::setOccurrenceStatus()` y
  `advanceOccurrenceStatus()` escriben directamente `occurrence.status`. En v1
  esos controles deben apuntar a un segment; el parent se deriva.
- `planner-store.js::reconcileTemporalState()` solo reconcilia cuando la fecha ya
  está `FROZEN` y cambia el parent. V1 exige reconciliar cada segment al pasar de
  hoy a pasado y repetir la reconciliación antes de congelar.
- `js/domain/occurrence-status.js::blocksSchedule()` duplica la lista backend y
  también omite `not_finished`.
- `js/domain/temporal-integrity.js` conserva utilidades valiosas de ventana, pero
  solo expone `EDITABLE/FROZEN/FUTURE`; current day se infiere aparte. La función
  `reconcileFrozenStatus()` es de un status plano.
- `js/scheduling/conflict-detector.js` usa envelopes y aggregate status.
- `js/scheduling/materializer.js` produce un intervalo pending. Puede reinterpretarse
  como “parent + default segment” sin cambiar las reglas de GenerationSlot.
- `js/views/planner-matrix.js::buildPlannerRows()` crea una fila por occurrence en
  la fecha seleccionada, usando el start general y
  `calculateDuration(startTime,endTime)`. V1 exige expandir segments y mostrar la
  suma de todas sus duraciones, no solo la amplitud del envelope.
- La selección global de `js/app.js` es `selectedPlanItemId`; no existen todavía
  `selectedOccurrenceId` y `selectedSegmentId`. El status button llama
  `plannerStore.advanceOccurrenceStatus(id)` con un occurrence ID.
- `js/views/aggregate-occurrence-display.js::deriveAggregateOccurrenceDisplay()`
  agrega **múltiples occurrences del mismo PlanItem/día** para la celda mensual.
  No es el aggregate interno de segments. Puede seguir consumiendo el aggregate
  persistido de cada occurrence, pero ambos conceptos deben conservar nombres y
  tests distintos.
- `js/views/plan-item-form.js` edita el envelope de una sola occurrence. Debe
  distinguir traslado de igual duración, resize y edición explícita de segments.
- Los coordinadores `js/mutations/occurrence-mutation.js` y
  `recurring-schedule-mutation.js` ya implementan POST/PATCH → GET → hydrate,
  protección de double submit y recovery solo GET. Esa orquestación es reusable;
  los payloads y la unidad de edición no lo son.
- `js/api/planner-api.js::validatePlannerStateResponse()` es superficial. Hoy
  toleraría campos aditivos, pero no garantiza el contrato de `segments`.
- `js/domain/deletion-policy.js` decide sobre parent status; necesitará reglas
  separadas para borrar un segment y para impedir que quede cero.
- `js/domain/scheduling-priority.js::wasDisplacedByPriorityOverride()` consulta
  `statusContext.reason`; necesitará una transición controlada a
  `conflictContext`.

La compatibilidad de una occurrence con un solo segment es alta para bootstrap,
hydrate, filas mensuales, creación desde GenerationSlots y eliminación del parent.
No es compatible sin cambios para status controls, selected row, duración,
conflictos, reconciliación, split/trim ni resize.

## 5. Differences vs OccurrenceSegment v1

| Regla v1 | Estado real | Consecuencia |
|---|---|---|
| Parent conserva envelope | Ya existe | Se preserva; deja de ser unidad de ocupación |
| `1..N occurrence_segments` | No existe | Nueva tabla, queries, mapper, domain model |
| Aggregate materializado | `status` es estado único | Semántica cambia; debe derivarse y persistirse atómicamente |
| Conflicto por segment ocupante | Parent envelope y parent status | Reescribir queries/policies; incluir `not_finished` |
| Backfill exacto 1:1 | Posible con datos actuales | No inferir huecos, splits ni historia |
| Hermanos no overlap | Sin representación | DB/service nuevos |
| Segments dentro de envelope | Sin representación | Invariante cross-table |
| Move igual duración traduce todos | PATCH reemplaza envelope | Adaptar comando y update batch |
| Resize no escala | PATCH permite cualquier rango | Requiere decisión explícita de UX/comando |
| Reconcile por segment | Frontend muta parent al Frozen | Nuevo servicio persistente/idempotente |
| Reconcile antes de Frozen | No ocurre en la fase hoy→pasado | Nueva etapa temporal |
| `conflict_reason` histórico | `status_reason` ligado a status | Migrar nombre, values y checks |
| Last source | Source solo priority override | Relajar semántica y lock de movimiento |
| `origin_reason` | No existe | Columna/contrato nuevo |
| `last_conflict_action` | No existe | Columna/contrato nuevo |
| Sin `conflictSources[]` | No existe | Mantener así |
| Sin event log | No existe | Mantener así |
| Sin pause/resume/live | No existe | No incorporarlo indirectamente |
| Sin recurring segment templates | GenerationSlots continuos | No agregar templates; materializar un default segment |

## 6. Existing behavior that can be preserved

- Identidades UUID de PlanItem, GenerationSlot y Occurrence.
- Envelope general y fecha local de `occurrences`.
- Los seis valores de status, reutilizados también por segments.
- `source_generation_slot_id`, su `ON DELETE SET NULL` y el partial unique index.
- Modos/slots/exclusions/stopped date y materialización de fechas. Cada intervalo
  generado se convierte en un parent con un segment pending.
- API → GET planner-state → hydrate y recovery sin repetir una mutación confirmada.
- Transacciones `SERIALIZABLE` de creación y mutaciones, y lectura coherente
  `REPEATABLE READ READ ONLY`.
- Validación de estado final de Apply Week, sanitización de errores, CORS y capa
  HTTP delgada de `app.py`.
- Regla de adyacencia: `end == next.start` no es overlap. La representación de
  rangos debe usar bounds `[start,end)`.
- Monthly aggregate entre occurrences. Debe seguir leyendo el aggregate del
  parent, no inspeccionar cada segment desde la vista.
- Borrado de occurrence como operación padre; `ON DELETE CASCADE` puede limpiar
  sus segments en la misma transacción.
- Principio de `valores.md`: durante la ventana editable se protege integridad
  temporal pero se permite corrección.

## 7. Required breaking changes

1. El modelo backend/frontend de occurrence gana `segments[]`; clonado,
   validación, orden y selección pasan a ser profundos.
2. La unidad para status control será el segment. Cambiar el aggregate del parent
   directamente debe dejar de ser una operación pública.
3. Queries de blockers y detectores de conflicto deben devolver/operar por segment
   ocupante, aunque el conflicto siga reportando el parent para contexto UX.
4. `BLOCKING_STATUSES` debe incorporar `not_finished` en ambos runtimes.
5. La reconciliación deja de ser una mutación local al render/bootstrap y se vuelve
   persistente, idempotente y segmentaria.
6. `PATCH occurrence` actual es ambiguo para un parent multi-segment. La API debe
   distinguir translate de resize; no puede conservarse su semántica general tal
   cual sin riesgo de corrupción.
7. Apply Week/Future deben distinguir parents simples de custom-segmented y no
   reducir silenciosamente estos últimos a un solo intervalo.
8. Priority/user-forced override debe transformar los segments solapados, mantener
   IDs según split/trim, actualizar metadata del parent y derivar aggregates.
9. `statusContext` debe evolucionar hacia `conflictContext`; el despliegue necesita
   una ventana de compatibilidad explícita.
10. Las reglas `chk_occurrence_status_context` y
    `chk_occurrence_override_status` actuales son incompatibles con metadata
    histórica desacoplada del aggregate.

## 8. Database design alternatives

### Opción A — DB estructural mínima; service como autoridad cross-row

Schema: tabla `occurrence_segments` con PK/FK/cascade, `TIME NOT NULL`, status y
checks locales. Índice B-tree por `(occurrence_id,start_time,end_time,id)`. Bounds,
no-overlap, “al menos uno” y aggregate se validan en el service dentro de una
transacción que bloquea parent/children.

- Complejidad: baja-media.
- Ventajas: migration simple; split/swap/resize fáciles de expresar como estado
  final; no requiere extensión ni triggers; lógica testeable en Python.
- Desventajas: SQL directo puede crear estado inválido; cada write path debe usar
  exactamente la misma validación.
- Riesgos: olvidar un path o una lock; drift entre service y scripts futuros.
- Impacto: repositories y services cambian de forma amplia, DB poco.
- Testing: unit tests puros sencillos más integración obligatoria para locks.
- Pause/resume: neutral; agregar timestamps/eventos después no se bloquea.
- Multiusuario: correcto si todas las escrituras pasan por service y la estrategia
  de locks está bien definida; débil ante writers externos.
- Migración: la más fácil.

### Opción B — Híbrida: estructura y sibling overlap en DB, semántica en service

Igual que A, más una exclusion constraint GiST diferible por
`(occurrence_id, [start_time,end_time))`. PostgreSQL 16 no incluye un `timerange`;
la implementación debe elegir y probar una expresión/rango derivado estable, por
ejemplo un `int4range` de segundos desde medianoche, o definir un tipo de rango
propio. UUID con igualdad en GiST normalmente requiere `btree_gist`; disponibilidad
y permisos deben comprobarse antes.

- Complejidad: media.
- Ventajas: dos writers concurrentes o SQL accidental no pueden superponer
  hermanos; una constraint `DEFERRABLE INITIALLY DEFERRED` admite swaps/splits
  evaluando el resultado al commit; el service mantiene reglas de producto.
- Desventajas: extensión/expresión adicional y errores SQL que deben mapearse; no
  resuelve bounds ni “al menos uno”.
- Riesgos: precisión/canonicalización del rango; deploy donde no se pueda crear la
  extensión; lock/deadlock si además se bloquea desordenadamente.
- Impacto: similar a A, con repository/error mapping adicional.
- Testing: excelente cobertura de no-overlap en integración PostgreSQL; unit tests
  del resto.
- Pause/resume: neutral.
- Multiusuario: mejor defensa ante concurrencia y writers adicionales.
- Migración: media; primero extensión/tabla/backfill, luego constraint validada.

### Opción C — DB intensiva con constraint triggers diferibles

Además de B, constraint triggers diferibles verifican al commit que todo parent
existente tenga al menos un child, que todos estén dentro del envelope y, quizás,
que el aggregate coincida.

- Complejidad: alta.
- Ventajas: máxima defensa independiente de la aplicación.
- Desventajas: lógica de aggregate/temporalidad duplicada en PL/pgSQL; creación y
  cascade requieren triggers cuidadosos en parent y child; errores y debugging más
  difíciles; dumps/imports y pruebas requieren más atención.
- Riesgos: trigger incompleto para parent borrado, cambio de ownership, bulk
  backfill o una nueva regla de aggregate; contención y comportamiento sorpresivo.
- Impacto: DB y service cambian; el service sigue siendo necesario para UX.
- Testing: integración extensa y matrices de orden de statements.
- Pause/resume: puede volver rígida la evolución del status.
- Multiusuario: alta integridad, pero mayor contención y complejidad operacional.
- Migración: la más difícil.

Las constraints `CHECK` no deben consultar otras filas/tablas. La documentación
oficial de PostgreSQL 16 señala que esa forma no garantiza consistencia y recomienda
`UNIQUE`, `EXCLUDE`, `FOREIGN KEY` o triggers para restricciones cross-row:
[Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html). Los rangos
built-in no incluyen `timerange`, aunque sí soportan overlap y bounds semánticos:
[Range Types](https://www.postgresql.org/docs/16/rangetypes.html).

## 9. Backend architecture alternatives

### Servicio de aplicación con módulo de dominio puro (recomendada)

Crear una responsabilidad central, no un repository genérico:

- funciones puras como `validate_segment_set(parent, segments)`,
  `derive_occurrence_status(segments, temporal_phase)` y
  `translate_segments(segments, delta)`;
- services existentes orquestan autorización, locks y transacción;
- repositories solo leen/escriben parent/children;
- mapper de planner-state serializa el aggregate persistido y `segments`.

Ventajas: una sola semántica reusable por Create/PATCH/Week/Future/conflicts;
pruebas rápidas; `app.py` permanece coordinador. Riesgo: cada service debe invocar
la validación final y persistir aggregate en la misma transacción.

### Modelo activo en repositories

Encapsular mutaciones (`split`, `trim`, `translate`) dentro de un repository de
occurrence graph. Reduce SQL repetido, pero mezcla semántica temporal/conflictos
con persistencia y dificulta probar sin PostgreSQL. No se recomienda para este
proyecto educativo ni para futuras reglas de pause/resume.

### Stored procedures como autoridad

Procedimientos PostgreSQL efectuarían split/trim/aggregate. Son atómicos y fuertes
ante multiusuario, pero duplicarían validación para UX/frontend, desplazarían mucha
lógica de negocio a PL/pgSQL y harían más costosos pause/resume y evolución. No se
recomiendan para v1; solo tendrían sentido si múltiples servicios independientes
escribieran el mismo esquema.

## 10. status_reason/conflict_reason migration analysis

Dependencias reales:

- SQL: `status_reason`, `chk_occurrence_status_context` y
  `chk_occurrence_override_status` en 001/002.
- Lectura: `planner_state_repository.py`, `planner_state_service.py` y
  `occurrence_mutation_service.py`.
- Escritura: `plan_item_repository.py::apply_priority_overrides()`.
- Snapshot/mutation repositories: `occurrence_repository.py` y
  `future_schedule_repository.py`.
- Frontend: `planner-store.js`, `scheduling-priority.js`, mocks y
  `statusContext.reason`.
- Pruebas: `test_planner_state.py`, `test_plan_item_creation.py`,
  `test_occurrence_mutation.py`, `test_apply_week.py`, `test_apply_future.py`,
  `test_postgresql_integration.py`, además de bootstrap, temporal integrity,
  deletion y multi-slot frontend.

### Alternativa 1: rename directo

`ALTER TABLE ... RENAME COLUMN status_reason TO conflict_reason`, reemplazar checks
y desplegar backend/frontend coordinadamente.

- Pro: modelo final limpio, sin duplicación ni backfill de columna.
- Contra: app antigua falla inmediatamente; migration/app no pueden desplegarse de
  forma independiente; rollback operativo difícil.
- Adecuada solo para un deploy atómico con downtime/control total.

### Alternativa 2: conservar nombre físico temporalmente

Mantener `status_reason`, ampliar values/checks y mapearlo en backend como
`conflict_reason`/`conflictContext`.

- Pro: menor riesgo de compatibilidad SQL y migración más pequeña.
- Contra: deuda semántica, consultas nuevas usando el nombre equivocado y futura
  migration adicional inevitable.
- Puede ser útil si migration 004 debe ser estrictamente aditiva.

### Alternativa 3: add/copy/read-fallback/drop en fases

Añadir `conflict_reason`, copiar `status_reason`, desplegar readers nuevos con
fallback, cambiar writers, verificar y eliminar la columna vieja en una migration
posterior. No conviene dual-write indefinido.

- Pro: despliegue gradual y reversible; frontend/backend pueden migrarse por fases.
- Contra: dos columnas temporalmente, constraints/sincronización delicadas y no
  cabe limpiamente en una única migration 004.

En cualquier alternativa deben desaparecer o cambiar:

- `chk_occurrence_override_status`, porque metadata histórica no implica que el
  aggregate actual sea `cancelled/not_finished`;
- el value único de `chk_occurrence_status_context`; v1 requiere al menos
  `priority_override` y `user_forced_override`;
- el nombre/forma API `statusContext`, mediante una transición a
  `conflictContext`.

Recomendación condicionada: para un entorno local controlado y release coordinado,
rename directo es el estado final más simple. Si backend y migration deben coexistir
con versiones distintas, usar add/copy/drop en dos migraciones/releases. La
decisión de deployment debe tomarse antes de escribir 004.

## 11. source_occurrence_id compatibility analysis

La FK actual `fk_occurrence_source` usa `NO ACTION` implícito. La aplicación refuerza
esa restricción: `occurrence_repository.py::lock_status_context_dependents*()` y
los services devuelven `status_context_locked` al intentar mover o borrar un source.
Esto se prueba en:

- `test_occurrence_mutation.py::test_status_context_dependents_protect_patch_source`;
- `test_occurrence_mutation.py::test_status_context_dependents_protect_the_source_occurrence`;
- `test_postgresql_integration.py::test_schedule_mutations_reject_status_context_source_changes`;
- casos Apply Future de `multi-slot-scheduling.test.mjs`.

Con v1, el source es el último conflicto estructural y su relación es histórica:

- **Mover el source:** no debería invalidar el hecho histórico. El lock actual deja
  de tener justificación y esos tests deben cambiar.
- **Borrar el source:** sigue sin una respuesta aprobada. Mantener `NO ACTION`
  protege la referencia pero restringe UX; `SET NULL` pierde el source y choca con
  un check que empareje reason/source; cascade sería incorrecto porque borraría la
  occurrence afectada. Un tombstone/event log resolvería historial, pero está fuera
  de v1.

Por tanto, migration 004 debería conservar inicialmente `NO ACTION`, como opción
reversible, y separar el lock de movimiento del lock de borrado. La política final
de borrado debe aprobarse explícitamente antes de relajar la FK. `source_occurrence_id
<> id` sigue siendo válida. No se propone `conflictSources[]`.

## 12. Aggregate status design

`deriveOccurrenceStatus(segments, phase)` debe ser una función pura en dominio
backend, compartida por todos los services. Debe ordenar/validar inputs y aplicar
exactamente:

1. si todos los segments tienen el mismo status, ese status;
2. mixto editable: `completed/in_progress/not_finished` → `in_progress`; si no,
   `pending`; si no, `not_completed`; si no, `cancelled`;
3. mixto histórico tras reconciliación: `completed/not_finished` →
   `not_finished`; si no, `not_completed`; si no, `cancelled`.

El parámetro no debe ser un boolean ambiguo: debe representar la fase temporal
normativa (`editable` o `historical_after_reconciliation`) derivada usando la fecha
local y la ventana vigente. El resultado se persiste en `occurrences.status` en la
misma transacción que modifica children. El frontend puede portar la función para
preview, pero el backend es autoridad.

Alternativas descartadas como autoridad primaria:

- generated column: PostgreSQL no puede derivar una columna del parent mediante
  subquery a children;
- view-only/render: contradice el aggregate materializado normativo;
- trigger: duplicaría reglas temporales y de precedencia, y el “día actual” cambia
  sin que una fila sea actualizada.

Debe existir además una verificación de consistencia al leer: si el aggregate
persistido no coincide con children bajo la fase aplicable, responder error
sanitizado y registrar internamente la inconsistencia; no corregir silenciosamente
en un GET. Una herramienta/test de auditoría puede detectar drift.

## 13. Cross-row integrity strategy

### Schema conceptual propuesto para A (no es migration 004 ejecutable)

```sql
public.occurrence_segments (
    id UUID PRIMARY KEY,
    occurrence_id UUID NOT NULL
        REFERENCES public.occurrences(id) ON DELETE CASCADE,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status VARCHAR(30) NOT NULL,
    CONSTRAINT chk_occurrence_segment_time_range
        CHECK (start_time < end_time),
    CONSTRAINT chk_occurrence_segment_status
        CHECK (status IN (
            'pending', 'in_progress', 'completed',
            'not_completed', 'not_finished', 'cancelled'
        ))
);

CREATE INDEX idx_occurrence_segments_occurrence_time
    ON public.occurrence_segments
       (occurrence_id, start_time, end_time, id);
```

No se necesita `UNIQUE (occurrence_id,id)` porque `id` ya es globalmente único.
Los IDs se generan en backend, coherente con v1 y con respuestas autoritativas.

### Invariantes limpias en PostgreSQL

- identidad/no-null;
- parent existente y cascade;
- duración positiva;
- enum de status;
- no-overlap de hermanos mediante exclusion constraint, si se aprueba Opción B.

La exclusion debe modelar `[start,end)` para permitir adyacencia. Dado que no hay
`timerange` built-in, el SQL exacto debe prototiparse en PostgreSQL 16 efímero y
verificar inmutabilidad/precisión antes de incluirse en 004.

### Invariantes recomendadas en service/domain

- todos los segments dentro del envelope del parent;
- al menos uno en el estado final;
- aggregate correcto para la fase temporal;
- traducción con delta sin overflow/cambio de fecha;
- reglas de split/trim/ID;
- ocupación/conflictos con otros parents;
- metadata de conflicto coherente con la operación.

### At least one segment (pregunta B)

1. **Validación final en service:** construir estado candidato, asegurar `length >=
   1`, bloquear parent y children y escribir atómicamente. Flexible para split,
   replace y delete. Recomendación inicial.
2. **Constraint trigger diferible:** al commit consulta cada parent afectado. Cubre
   SQL externo, pero debe dispararse desde inserts del parent y deletes/moves del
   child, ignorar parents borrados y manejar cascade. Viable como hardening posterior.
3. **FK circular a primary segment:** garantiza que exista un child solo con FKs
   diferibles, pero introduce un “segment privilegiado”, complica split/delete y no
   representa el dominio. No recomendada.

### Sibling overlap (pregunta C)

Service validation es necesaria para mensajes de dominio y preview, pero bajo
concurrencia dos writers pueden validar contra snapshots diferentes. Una exclusion
constraint diferible brinda una segunda barrera robusta. Esa combinación es mejor
que un trigger de overlap hecho a mano. Si `btree_gist` no está disponible, usar
service + parent lock determinista como fallback documentado.

## 14. Migration 004 conceptual plan

Este es un orden conceptual, no SQL listo para ejecutar:

1. `BEGIN`; validar precondiciones de datos actuales: rangos positivos, statuses
   admitidos y ausencia de IDs requeridos nulos.
2. Crear `occurrence_segments` y su índice estructural, todavía sin una constraint
   de existencia que impida el backfill.
3. Backfill exactamente un segment por occurrence, con UUID nuevo generado de
   forma no derivada y `start/end/status` copiados.
4. Verificar conteos: occurrences = segments, cero parents sin child y cero
   children huérfanos.
5. Introducir/validar no-overlap si se aprobó Opción B. En el backfill 1:1 es
   trivial, pero la definición debe probarse antes.
6. Añadir `origin_reason` y `last_conflict_action` nullable con checks de values
   aprobados; no inventar valores históricos.
7. Ejecutar la estrategia aprobada para `status_reason → conflict_reason` y
   reemplazar checks incompatibles.
8. Conservar inicialmente `source_occurrence_id` y su FK `NO ACTION` hasta resolver
   la política de borrado.
9. Verificar nuevamente invariantes y `COMMIT`.

Una migration no debe depender de que el backend antiguo escriba parents durante
el backfill. El deploy necesita ventana de mantenimiento o compatibilidad dual
preparada previamente. No se debe añadir un default segment por trigger como puente
indefinido: oculta writers no migrados.

## 15. Existing data backfill

Para cada fila actual:

```text
Occurrence(id=O, start=X, end=Y, status=S)
→
Occurrence(id=O, start=X, end=Y, status=S)
Segment(id=nuevo UUID, occurrence_id=O, start=X, end=Y, status=S)
```

No se infieren pausas, huecos, duración efectiva, splits históricos, causa de
status ni templates recurrentes. `status_reason/source_occurrence_id` permanecen
en el parent. `origin_reason` y `last_conflict_action` quedan `NULL` para historia
legacy, salvo que una regla aprobada posterior indique algo demostrable.

El UUID debe ser verdaderamente nuevo. Usar nombre/fecha/horario para derivarlo
violaría la política de identidad. Si se usa `gen_random_uuid()`, hay que confirmar
la disponibilidad en PostgreSQL 16 del entorno; alternativamente generar IDs en
un script controlado y verificable. El backfill debe ser idempotente solo a nivel
de migration aplicada una vez; no usar `ON CONFLICT` para ocultar una ejecución
parcial.

Pruebas mínimas de migration: DB vacía, varios statuses, provenance nula/no nula,
priority override existente, conteos/igualdad exacta, rollback ante fallo y
planner-state sin rematerialización.

## 16. Transaction/concurrency analysis

Las transacciones `SERIALIZABLE` existentes son una base correcta, no una solución
completa. Una mutación v1 puede tocar parent, varios children propios, children
blockers, aggregates y metadata.

Orden de lock recomendado:

1. lock de PlanItem/config si la operación los modifica;
2. locks de occurrences afectadas, ordenadas por UUID;
3. locks de sus segments, ordenados por `(occurrence_id,start_time,id)`;
4. volver a consultar blockers actuales dentro de la misma transacción;
5. construir y validar el estado final completo;
6. escribir children, aggregates y metadata; commit con retry controlado ante
   serialization failure.

Riesgos concretos:

- **Phantoms de blockers:** `FOR UPDATE` no bloquea un intervalo inexistente. La
  isolation serializable debe producir/reintentar conflictos de serialización; un
  lock lógico por fecha/PlanItem o advisory lock puede evaluarse si la carga futura
  lo exige, no añadirse por anticipado.
- **Lost aggregate:** dos updates a segments del mismo parent deben bloquear el
  parent antes de derivar; así solo un writer deriva a la vez.
- **Split concurrente:** ambos writers pueden preservar el mismo left-ID o crear
  fragments incompatibles. Parent lock + exclusion constraint + retry.
- **Override TOCTOU:** mantener el patrón actual: después de confirmación,
  recalcular segments ocupantes y exigir que los conflictos actuales sean subset
  de lo autorizado. IDs de occurrence pueden ser insuficientes si cambió el
  fragment; el contrato de confirmación necesita decidir granularidad segmentaria.
- **Reconciliation vs mutation:** reconciliación debe ser idempotente, bloquear el
  parent/segments y volver a evaluar la fase temporal dentro de la transacción.
- **Apply Week/Future:** lock order debe coincidir con PATCH/conflict engine para
  evitar deadlocks. La validación debe considerar el estado final del batch, como
  ya hace Apply Week.
- **Delete source:** la FK `NO ACTION` y los dependents deben resolverse antes del
  delete; no cambiar metadata a medias.
- **Planner-state:** `REPEATABLE READ READ ONLY` sigue siendo adecuado para obtener
  parent/children del mismo snapshot; las queries deben ejecutarse en esa misma
  conexión.

Cada operación estructural debe confirmar o revertir en conjunto: segment changes,
parent envelope/aggregate, blockers y `conflict_reason/source/origin/action`. Nunca
recalcular el aggregate en una segunda transacción.

## 17. API/planner-state evolution

Contrato aditivo mínimo propuesto:

```json
{
  "id": "occurrence-uuid",
  "planItemId": "plan-item-uuid",
  "date": "YYYY-MM-DD",
  "startTime": "08:00",
  "endTime": "12:00",
  "status": "in_progress",
  "segments": [
    {
      "id": "segment-uuid",
      "startTime": "08:00",
      "endTime": "09:00",
      "status": "completed"
    },
    {
      "id": "segment-uuid",
      "startTime": "11:00",
      "endTime": "12:00",
      "status": "pending"
    }
  ],
  "conflictContext": {
    "reason": "priority_override",
    "sourceOccurrenceId": "source-uuid"
  },
  "originReason": "conflict_insertion",
  "lastConflictAction": "conflict_move"
}
```

`sourceGenerationSlotId` permanece cuando aplique. Campos metadata opcionales se
omiten cuando son nulos. `segments` no debe omitirse en el contrato final y debe
ordenarse determinísticamente por `startTime`, `endTime`, `id`.

### Impacto por mutación existente (pregunta H)

| Operación | Lo que funciona casi igual con un segment | Adaptación necesaria | Qué conviene posponer / peligro de hacerlo todo junto |
|---|---|---|---|
| Create PlanItem | Materialización de fechas, IDs de slots, atomicidad y handshake POST pueden conservarse | Insertar parent + default segment pending; validar/derivar aggregate antes del commit; blockers por segment | Posponer templates recurrentes de segments; mezclar creación con el nuevo conflict engine completo aumenta el riesgo de rollback incompleto |
| PATCH occurrence | Autorización temporal, provenance, exclusions y una transacción siguen siendo útiles | Un move de igual duración traduce todos los children por el mismo delta; un resize exige comando/decisión explícita; bloquear parent+children | No reinterpretar el PATCH actual como resize automático; escalar/recortar children silenciosamente destruiría intención/historia |
| DELETE occurrence | La política del parent y el manejo recurring/manual/ad-hoc pueden conservarse; cascade elimina children | Validar metadata dependiente y aggregate antes de borrar; distinguir en otra operación delete segment y prohibir el último | Posponer delete-segment hasta que “al menos uno” esté reforzado; no mezclar el debate del source FK con cascade de children |
| Apply Week | Batch final-state validation, swaps y transacción son reutilizables | Los parents simples siguen el comportamiento actual; custom segments se traducen para moves iguales; conflictos usan children | Posponer custom resize o bloquearlo de forma explícita; recrear todo como single segment perdería custom segmentation |
| Apply Future | Preservación de history/override/ad-hoc y actualización de config/slots continúan | `_is_old_baseline()` debe exigir parent simple/default; los nuevos parents nacen con un segment; custom parents se preservan o traducen según operación | Posponer reescritura custom compleja; comparar solo envelope puede clasificar y sobrescribir falsamente un parent custom |
| Reconciliation | Utilidades de fecha/ventana y mappings `pending→not_completed`, `in_progress→not_finished` se reutilizan | Ejecutar por child, persistir, derivar aggregate y repetir antes de Frozen; servicio idempotente transaccional | No mantener simultáneamente reconciliación local y backend; dos autoridades producirían drift |
| Conflict resolution | Clasificación de prioridad, confirmación y recheck `SERIALIZABLE`/TOCTOU son una buena base | Detectar solo segments ocupantes; split/trim/cancel por fragmento; IDs normativos; actualizar blockers, aggregates y conflict metadata juntos | Posponer `user_forced_override` UX hasta fijar contrato segmentario; cambiar en un solo salto Create/PATCH/Week/Future y conflictos multiplica superficie de carrera |

Compatibilidad incremental:

1. Backend empieza a leer/backfillear y emitir `segments` manteniendo los campos
   generales y aggregate. El frontend actual ignora el campo aditivo.
2. Frontend actualiza validator/deep clone/store y consume `segments`; single
   segment debe verse igual.
3. Introducir `conflictContext` como campo nuevo. Durante una ventana breve se
   puede emitir `statusContext` como alias derivado de la misma fuente, nunca como
   segunda fuente mutable. Después migrar consumers y eliminar alias.
4. Solo después conectar status/mutations segmentarios. Un cliente antiguo no debe
   poder escribir parents multi-segment con el PATCH ambiguo; versionar/restringir
   el endpoint o rechazar esas mutaciones con conflicto controlado.

No deben fabricarse IDs de segments en hydrate para respuestas legacy: parecerían
persistidos y romperían mutaciones. La compatibilidad debe venir del backfill y del
backend autoritativo.

## 18. Test impact

### Suites que pueden preservarse con expectativas aditivas

- `test_backend.py`: health/list PlanItems.
- bootstrap/hydration y recovery de `planner-bootstrap.test.mjs`.
- coordinadores de `plan-item-creation.test.mjs`,
  `occurrence-mutation.test.mjs` y `recurring-schedule-mutation.test.mjs`.
- generación weekly/interval/manual/multi-slot, una vez que cada parent incluya un
  default segment.
- `aggregate-occurrence-display.test.mjs`, aclarando que prueba aggregate mensual
  entre occurrences, no aggregate interno.

### Tests que necesariamente cambian o se amplían

- `test_planner_state.py`: rows de segments, orden, exactitud de aggregate,
  parent sin segment y segment fuera de bounds/no-overlap.
- `test_plan_item_creation.py` y parity JS/Python: grafo debe incluir un segment
  pending por draft y rollback debe cubrir la nueva tabla.
- `test_occurrence_mutation.py`: translate de todos los segments, resize explícito,
  último segment, status segmentario y nuevo lock de source.
- `test_apply_week.py` / `test_apply_future.py`: simple vs custom segmented,
  preservación de IDs, translation y rechazo/flujo explícito de resize.
- `test_postgresql_integration.py`: migration/backfill, constraints, aggregate
  atómico, concurrent split/override/reconcile y serializable retries.
- `temporal-integrity.test.mjs`: reconciliación segmentaria en dos momentos.
- `planner-engine.test.mjs`, `editor-matrix-coherence.test.mjs` y
  `occurrence-aware-rendering.test.mjs`: selección occurrence+segment, filas y suma
  de duración.
- `scheduling-priority.test.mjs`: blockers segmentarios y metadata nueva.
- `deletion-management.test.mjs`: delete segment/último segment/parent cascade.
- tests hoy basados en `status_context_locked` deben separar move permitido y
  delete restringido.

### Nueva matriz mínima

- 1, 2 y N segments; adyacentes válidos y overlap inválido;
- bounds exactos y fuera de envelope;
- seis uniformes y mixed editable/historical;
- `not_finished` ocupa agenda;
- translate conserva IDs/deltas; resize no escala;
- split preserva left ID y crea UUID; trim conserva ID; full coverage aplica la
  consecuencia aprobada;
- reconciliation pending/in_progress por segment y segunda pasada pre-Frozen;
- planner-state round trip sin rematerialización;
- rollback en cada etapa y dos writers concurrentes;
- DB vacía y backfill exacto de todos los statuses/contexts.

No se ejecutaron suites en esta auditoría porque no se modificó comportamiento; la
evidencia se obtuvo por inspección de código y tests. La futura implementación debe
usar PostgreSQL 16 aislado, no `vcs_dev`.

## 19. Suggested implementation phases

1. **DB/backfill aislado:** prototipo PostgreSQL 16, decision record de constraints,
   migration 004 y pruebas desde 001→004. Sin activar UI segmentaria.
2. **Backend read compatibility:** repository lee children; planner-state emite
   `segments` aditivo y valida integridad. Aggregate actual sigue funcionando.
3. **Frontend read/display:** deep clone/validator, selection IDs, filas y duración;
   single segment visualmente sin regresión. Mantener controles de escritura
   bloqueados donde sean ambiguos.
4. **Creación + aggregate domain:** crear parent/segment, función pura de aggregate
   y auditoría de consistencia. Corregir lista ocupante incluyendo `not_finished`.
5. **Reconciliation persistente:** proceso idempotente segmentario hoy→pasado y
   pre-Frozen, con aggregate en la misma transacción.
6. **Mutaciones de segment:** status, split/trim/delete y translate. Definir resize
   explícito antes de habilitarlo.
7. **Apply Week/Future:** compatibilidad para single segment, translate de custom
   segments y política aprobada para resize/custom baselines.
8. **Conflict engine:** blockers segmentarios, priority/user-forced override,
   metadata y handshake con recheck TOCTOU.
9. **Conflict UX y limpieza:** `conflictContext`, retiro de alias/legacy local
   writes, tests browser desktop/mobile.
10. **Verificación final:** suites completas, integración/concurrencia, consistency
    audit y decisión sobre hardening con deferred trigger.

Separar lectura antes de escritura hace reversible el despliegue y evita cambiar a
la vez schema, motor de conflictos, recurring mutations y UI.

## 20. Risks

- Confundir envelope con ocupación produciría falsos conflictos en huecos.
- Confundir aggregate interno con monthly aggregate mezclaría dos niveles distintos.
- Olvidar `not_finished` perpetuaría una divergencia normativa ya presente.
- Un resize implícito podría mover/recortar trabajo realizado.
- Un GET que “repare” aggregate ocultaría corrupción y convertiría una lectura en
  escritura no auditada.
- Dual-write prolongado de reason/context crearía dos fuentes de verdad.
- Exclusion constraint incorrecta podría rechazar adyacencia o perder precisión.
- Locks en orden diferente entre services pueden introducir deadlocks.
- `SERIALIZABLE` sin retry controlado se manifestaría como errores esporádicos.
- Backfill concurrente con writers legacy podría dejar parents sin segments.
- Cambiar `source_occurrence_id` a `SET NULL` sin rediseñar checks perdería contexto.
- Apply Future podría sobrescribir custom segmentation si su detector baseline solo
  compara envelope.
- Reconciliación local y persistente coexistiendo producirían drift.
- Un cliente antiguo podría modificar un parent multi-segment sin conocer children.

## 21. Open questions

Estas decisiones deben resolverse antes de implementar la parte correspondiente:

1. ¿Migration 004 puede requerir `btree_gist` y el rol de deployment puede crear la
   extensión? Si no, ¿se acepta service + parent lock como primera etapa?
2. ¿“Al menos un segment” queda inicialmente como invariante de service o se exige
   un constraint trigger diferible desde 004?
3. ¿El deploy es atómico con downtime suficiente para rename directo de
   `status_reason`, o requiere add/copy/drop en fases?
4. Al borrar una occurrence que es `source_occurrence_id`, ¿se restringe el borrado,
   se conserva un tombstone futuro o se acepta perder el link? V1 no aprueba event
   log y `SET NULL` por sí solo es insuficiente.
5. ¿La confirmación de conflicto identifica occurrences, segments o pares
   `(occurrenceId,segmentId,interval)`? Occurrence-only puede autorizar demasiado si
   el segment cambia entre requests.
6. ¿Qué endpoint/payload explícito representa translate, resize y mutation de un
   segment? El PATCH actual no distingue intención.
7. Para resize de un parent multi-segment, ¿la UI exige reparar manualmente o ofrece
   “reset a un segment con aggregate previo”, como permite la norma?
8. ¿Apply Week/Future bloquea custom-segmented resizes inicialmente o incorpora UX
   de reparación en la misma fase?
9. ¿Cómo se dispara reconciliación persistente: bootstrap/lazy command, job local o
   endpoint operacional? Debe seguir siendo idempotente y transaccional.
10. ¿Se mantiene precisión canónica a minutos aunque SQL sea `TIME`, y se añadirá un
    check de segundos cero para segments/parents?
11. ¿`origin_reason` y `last_conflict_action` deben tener solo los valores mínimos
    aprobados en v1 y ser nullable, o existe un valor normal explícito?
12. ¿Cuándo se elimina completamente el frontend local legacy de materialización,
    conflictos y reconciliación para no mantener dos autoridades?

## 22. Recommended architecture

Se recomienda **Opción B híbrida**, condicionada a un prototipo exitoso de la
exclusion constraint en PostgreSQL 16:

1. `occurrence_segments` como componente con UUID backend, FK `ON DELETE CASCADE`,
   checks locales e índice `(occurrence_id,start_time,end_time,id)`.
2. Exclusion constraint diferible de rangos `[start,end)` por parent para impedir
   sibling overlap; si `btree_gist` no es viable, comenzar con Opción A y documentar
   el hardening pendiente.
3. Dominio Python puro como autoridad de bounds, al menos uno, aggregate,
   translate/split/trim y reglas de conflicto. No stored procedures de negocio.
4. Services existentes como orquestadores `SERIALIZABLE`, con parent-first locking,
   orden determinista, final-state validation y retry de serialization failures.
5. Aggregate materializado en el parent y actualizado en la misma transacción que
   children; planner-state valida, pero no repara.
6. Read contract aditivo primero: conservar `startTime/endTime/status` y añadir
   `segments[]`; luego migrar selección/render y solo después writes.
7. `status_reason → conflict_reason` mediante rename coordinado si el deploy es
   atómico, o add/copy/drop si exige coexistencia. No dual-write indefinido.
8. Conservar inicialmente la FK `source_occurrence_id NO ACTION`; permitir mover el
   source sin limpiar metadata, pero resolver su borrado antes de relajar el lock.
9. Crear un default segment por occurrence generada; no introducir recurring
   segment templates.
10. Implementar en fases pequeñas y verificables; conflict engine y recurring
    mutations multi-segment van después de read/display/aggregate/reconciliation.

Las cinco decisiones humanas que desbloquean el diseño son: estrategia de
no-overlap/extensión, garantía de “al menos uno”, rollout de `conflict_reason`,
política de borrado del source y granularidad del contrato de confirmación/mutación
segmentaria. Hasta resolverlas no conviene redactar migration 004 definitiva.
