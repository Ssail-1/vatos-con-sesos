# CURRENT TASK

## MVP 05.6.4.1 — Persisted single-occurrence editing/deletion + slot exclusions

### Documento normativo

La especificación global de multi-slot está en:

`docs/codex/gestor_de_habitos/planeacion/MVP_05_6/MULTI_SLOT_SCHEDULING.md`

Este `CURRENT_TASK.md` define únicamente la fase activa:

```text
MVP 05.6.4.1
Persisted single-occurrence editing/deletion + slot exclusions
```

Estado actual:

```text
Frontend/domain multi-slot       ✅
PostgreSQL multi-slot            ✅
Backend/API multi-slot           ✅
vcs_dev migrada a 003            ✅
POST/GET multi-slot real         ✅
```

La siguiente necesidad es poder actuar sobre UNA occurrence concreta sin
afectar accidentalmente los demás slots del mismo PlanItem.

---

# 1. Objetivo

Implementar persistencia para las operaciones:

```text
Editar únicamente esta occurrence
Eliminar únicamente esta occurrence
```

respetando su `sourceGenerationSlotId`.

Debe ser posible tener:

```text
Uber — 2026-09-20

08:00–11:00
14:00–17:00
20:00–22:00
```

y eliminar/modificar únicamente:

```text
14:00–17:00
```

sin afectar:

```text
08:00–11:00
20:00–22:00
```

---

# 2. Subdivisión deliberada

MVP 05.6.4 se implementará en varias pasadas.

Esta fase NO implementa todavía:

```text
Apply Week persistente
Apply Future persistente
reestructuración completa de semana/configuración
```

Se prevé:

```text
MVP 05.6.4.1
→ esta occurrence / este día

MVP 05.6.4.2
→ Apply Week

MVP 05.6.4.3
→ Apply Future / configuración desde fecha efectiva
```

No adelantar fases posteriores.

---

# 3. Nueva representación canónica de exclusión por slot

`generation_slot_excluded_dates` ya existe en PostgreSQL desde MVP 05.6.2.

Ahora debe tener representación en el dominio.

Para `weekly`:

```js
{
  id: "UUID",
  isoWeekday: 1,
  startTime: "14:00",
  endTime: "17:00",
  excludedDates: ["YYYY-MM-DD"]
}
```

Para `interval_days`:

```js
{
  id: "UUID",
  startTime: "14:00",
  endTime: "17:00",
  excludedDates: ["YYYY-MM-DD"]
}
```

`excludedDates` dentro del slot es opcional.

Ausente y `[]` son semánticamente equivalentes.

---

# 4. Diferencia entre exclusión global y exclusión de slot

Se mantienen DOS conceptos distintos.

## generationConfig.excludedDates

Ejemplo:

```js
{
  mode: "weekly",
  excludedDates: ["2026-12-25"]
}
```

Significa:

> No generar ninguna occurrence de este PlanItem en esta fecha.

## slot.excludedDates

Ejemplo:

```js
{
  id: "S2",
  startTime: "14:00",
  endTime: "17:00",
  excludedDates: ["2026-09-20"]
}
```

Significa:

> No generar únicamente este slot en esta fecha.

No mezclar ambas semánticas.

---

# 5. Manual dates

`manual_dates` NO utiliza `slot.excludedDates` como representación
canónica normal.

Una entry manual representa una instrucción explícita de una única fecha.

Ejemplo:

```js
{
  id: "S1",
  date: "2026-09-20",
  startTime: "14:00",
  endTime: "17:00"
}
```

Cuando se elimina una entry manual, debe eliminarse esa entry/slot
cuando hacerlo mantenga una configuración válida.

---

# 6. PlanItem siempre estructuralmente válido

Después de cualquier operación debe continuar cumpliéndose:

```text
PlanItem válido
+
generationConfig válida
+
estructura específica del mode válida
```

No dejar:

```text
manual_dates con 0 entries
weekly con 0 slots
interval_days con 0 slots
```

como resultado accidental de esta fase.

---

# 7. Última entry manual

Si el usuario intenta eliminar la ÚLTIMA entry de un PlanItem
`manual_dates`, esta fase NO debe dejar una configuración vacía.

La operación debe rechazarse de forma controlada.

Código de dominio sugerido:

```text
last_manual_entry
```

HTTP:

```text
409
```

No borrar el PlanItem automáticamente.

No introducir todavía user-facing PlanItem deletion.

La occurrence puede seguir gestionándose mediante las reglas/status
existentes, por ejemplo cancelación cuando corresponda.

---

# 8. API — editar una occurrence

Implementar:

```text
PATCH /api/occurrences/<occurrence_id>
```

Esta ruta modifica únicamente la aparición seleccionada.

Payload canónico:

```json
{
  "date": "YYYY-MM-DD",
  "startTime": "HH:MM",
  "endTime": "HH:MM"
}
```

Los tres campos representan el estado horario final deseado.

No aceptar campos adicionales.

Esta ruta NO modifica:

```text
status
statusContext
PlanItem name
kind/subtype
generationConfig general
```

salvo los metadatos/exclusiones necesarios para preservar la semántica de
la occurrence cuando se mueve de fecha.

---

# 9. PATCH — occurrence recurrente, misma fecha

Para una occurrence proveniente de:

```text
weekly
interval_days
```

si únicamente cambia el horario manteniendo la misma fecha:

```text
GenerationSlot
→ NO cambia

Occurrence
→ cambia start_time/end_time

sourceGenerationSlotId
→ se conserva
```

Ejemplo:

```text
Slot S2
lunes 14:00–17:00

Occurrence O10
2026-09-21 14:00–17:00
```

editar solo ese día:

```text
Occurrence O10
2026-09-21 15:00–18:00
sourceGenerationSlotId = S2
```

Las demás occurrences de S2 siguen usando:

```text
14:00–17:00
```

---

# 10. PATCH — occurrence recurrente movida de fecha

Si una occurrence proveniente de:

```text
weekly
interval_days
```

cambia de fecha:

```text
fecha original
→ debe quedar excluida para ese slot

occurrence
→ se mueve a nueva fecha

sourceGenerationSlotId
→ se conserva
```

Ejemplo:

```text
S2 genera:
2026-09-21 14:00–17:00
```

el usuario mueve solo esa occurrence a:

```text
2026-09-22 15:00–18:00
```

Debe persistirse:

```text
generation_slot_excluded_dates
S2 | 2026-09-21
```

y actualizar la occurrence.

Esto impide que el materializador vuelva a crear S2 el día original.

---

# 11. PATCH — colisión de source slot en nueva fecha

La base contiene:

```text
UNIQUE(source_generation_slot_id, occurrence_date)
WHERE source_generation_slot_id IS NOT NULL
```

Si mover una occurrence provoca que el mismo slot ya tenga otra
occurrence en la fecha destino:

```text
rechazar operación
```

No quitar procedencia para evadir la constraint.

No duplicar la occurrence.

Responder con conflicto de dominio controlado.

---

# 12. PATCH — manual_dates

Una entry `manual_dates` representa exactamente una instrucción explícita.

Por tanto, editar su única occurrence debe mantener sincronizados:

```text
generation_slots
generation_slot_dates
occurrence
```

Preservar:

```text
slot.id
sourceGenerationSlotId
occurrence.id
```

Si cambia horario:

```text
generation_slots.start/end
→ actualizar

occurrence.start/end
→ actualizar
```

Si cambia fecha:

```text
generation_slot_dates.entry_date
→ actualizar

occurrence.occurrence_date
→ actualizar
```

No crear un slot nuevo por una edición normal de esa misma entry.

---

# 13. PATCH — occurrence ad-hoc

Si:

```text
sourceGenerationSlotId = null
```

la occurrence no tiene regla generadora.

Editar:

```text
date
startTime
endTime
```

modifica únicamente la occurrence.

No crear GenerationSlot.

No crear slot exclusion.

---

# 14. PATCH — conflictos

Antes de confirmar el horario/fecha nueva:

```text
revalidar conflictos
```

contra las occurrences relevantes.

Preservar exactamente las reglas actuales:

```text
intervalos semiabiertos
completed conflict
priority
history frozen
priority override requirement
```

No permitir que una occurrence choque consigo misma durante la validación.

Excluir su propio ID de la búsqueda de conflictos.

---

# 15. PATCH — atomicidad

Toda edición debe ser atómica.

Usar:

```text
una sola conexión
una sola transacción
```

Ejemplo recurrente movido:

```text
BEGIN

lock occurrence
validate
insert slot exclusion original date
update occurrence

COMMIT
```

Manual:

```text
BEGIN

lock occurrence / slot
validate
update generation slot
update slot date si aplica
update occurrence

COMMIT
```

Ante cualquier fallo:

```text
ROLLBACK
```

No dejar exclusión sin edición ni edición sin exclusión.

---

# 16. PATCH — respuesta

Respuesta correcta:

```text
HTTP 200
```

Contrato mínimo:

```json
{
  "occurrence": {
    "id": "UUID",
    "planItemId": "UUID",
    "sourceGenerationSlotId": "UUID",
    "date": "YYYY-MM-DD",
    "startTime": "HH:MM",
    "endTime": "HH:MM",
    "status": "pending"
  }
}
```

Si `sourceGenerationSlotId` es NULL, seguir la convención API ya existente.

La integración frontend persistente todavía no se implementa en esta fase.

---

# 17. API — eliminar una occurrence

Implementar:

```text
DELETE /api/occurrences/<occurrence_id>
```

La semántica depende del origen de la occurrence.

---

# 18. DELETE — weekly / interval_days

Si la occurrence proviene de un GenerationSlot recurrente:

```text
sourceGenerationSlotId != null
```

y el mode es:

```text
weekly
interval_days
```

debe ocurrir atómicamente:

```text
insert generation_slot_excluded_dates
    slot_id
    occurrence_date

delete occurrence
```

Resultado:

```text
solo ese slot desaparece ese día
```

Los demás slots del mismo PlanItem/fecha permanecen.

---

# 19. DELETE — manual_dates

Si la occurrence proviene de:

```text
manual_dates
```

y NO es la última entry del PlanItem:

```text
delete occurrence
delete GenerationSlot
```

La eliminación del slot debe limpiar mediante CASCADE:

```text
generation_slot_dates
```

y cualquier detalle dependiente.

No afectar otras manual entries.

---

# 20. DELETE — última manual entry

Si es la última entry del PlanItem:

```text
rechazar
```

No dejar:

```text
manual_dates entries=[]
```

No borrar automáticamente PlanItem.

Respuesta:

```text
409
```

con error de dominio sanitizado.

---

# 21. DELETE — occurrence ad-hoc

Si:

```text
sourceGenerationSlotId IS NULL
```

y la política temporal/status permite eliminación:

```text
delete occurrence
```

No crear exclusión.

No modificar configuration.

---

# 22. DELETE — atomicidad

La eliminación completa debe utilizar:

```text
una sola conexión
una sola transacción
```

Ejemplo recurring:

```text
BEGIN

lock occurrence
validate temporal/status
insert slot exclusion
delete occurrence

COMMIT
```

Si cualquier paso falla:

```text
ROLLBACK
```

---

# 23. DELETE — respuesta

Respuesta correcta:

```text
HTTP 200
```

Contrato mínimo:

```json
{
  "deletedOccurrenceId": "UUID"
}
```

No es necesario devolver todo planner-state.

La futura integración frontend podrá refrescar:

```text
GET /api/planner-state
```

después de una mutación.

---

# 24. GET /api/planner-state — slot exclusions

Actualizar el contrato de lectura para que:

```text
generation_slot_excluded_dates
```

ya NO se considere automáticamente inconsistencia.

Debe reconstruirse en cada slot recurrente.

Weekly:

```js
{
  id,
  isoWeekday,
  startTime,
  endTime,
  excludedDates: ["YYYY-MM-DD"]
}
```

Interval:

```js
{
  id,
  startTime,
  endTime,
  excludedDates: ["YYYY-MM-DD"]
}
```

Omitir `excludedDates` cuando esté vacío si esa es la convención ya usada
por el frontend.

---

# 25. GET manual_dates

Una fila en:

```text
generation_slot_excluded_dates
```

asociada a un slot `manual_dates` sigue considerándose estado persistido
no canónico para esta fase.

No inventar semántica.

Debe producir error de integridad controlado.

---

# 26. JavaScript domain — slot exclusions

Adaptar el dominio local para aceptar:

```text
slot.excludedDates
```

en:

```text
weekly
interval_days
```

El materializador JavaScript debe verificar:

```text
config.excludedDates
OR
slot.excludedDates
```

antes de generar una occurrence.

---

# 27. Python materializer — slot exclusions

El materializador Python debe aplicar exactamente la misma semántica.

Para cada candidate:

```text
si candidateDate está en config.excludedDates
→ no generar ningún slot

si candidateDate está en slot.excludedDates
→ no generar ese slot

si no
→ generar normalmente
```

Mantener paridad JS ↔ Python.

---

# 28. Materialización idempotente después de edición

Una occurrence recurrente editada solo en horario conserva:

```text
sourceGenerationSlotId + date
```

Por tanto, una rematerialización NO debe generar otra occurrence con el
horario original.

Ejemplo:

```text
S2 = 14:00–17:00

O2 editada:
15:00–18:00
source=S2
date=2026-09-21
```

Materializar nuevamente:

```text
NO crear otro 14:00–17:00
```

---

# 29. Materialización después de DELETE

Después de eliminar:

```text
S2
2026-09-21
```

debe existir:

```text
slot.excludedDates includes 2026-09-21
```

Por tanto una rematerialización:

```text
NO recrea S2 ese día
```

Los demás slots continúan generándose.

---

# 30. Temporal integrity

Preservar las reglas actuales.

No ampliar la ventana editable.

No permitir cambios en historia congelada.

No permitir borrar/modificar statuses protegidos si actualmente están
protegidos.

Usar las mismas funciones/reglas existentes cuando sea posible.

---

# 31. Status

PATCH de esta fase modifica:

```text
date/time
```

NO modifica status.

DELETE respeta las reglas de status existentes.

No implementar persistencia general de status en esta tarea si todavía
pertenece a otra fase.

---

# 32. UUIDs

Validar:

```text
occurrence_id de URL
```

como UUID válido según la política backend actual.

Los slot IDs existentes se preservan.

PATCH no genera slot UUID salvo que otra operación existente lo requiera,
lo cual no debería suceder en esta fase.

DELETE no reutiliza IDs.

---

# 33. Repository layer

Mantener arquitectura:

```text
app.py
→ HTTP

service/domain
→ reglas/orquestación

repository
→ SQL
```

No poner reglas de mode en Flask route.

No poner lógica temporal en repository.

No introducir ORM.

---

# 34. Bloqueos/concurrencia

Las mutations deben bloquear las filas relevantes.

Utilizar:

```text
SELECT ... FOR UPDATE
```

o el mecanismo equivalente ya existente.

Evitar que dos ediciones/eliminaciones concurrentes produzcan:

```text
duplicated exclusions
lost update
partial mutation
```

La PK:

```text
(slot_id, excluded_date)
```

protege también la exclusión.

La operación puede insertar exclusión de forma idempotente cuando sea
apropiado.

---

# 35. Error handling

Mantener respuestas sanitizadas.

Como mínimo:

```text
400
invalid_payload / invalid identifier

404
occurrence_not_found

409
domain conflict
history frozen
status conflict
last_manual_entry
slot/date uniqueness conflict

500
persisted state invalid

503
database unavailable
```

No exponer:

```text
SQL
DSN
password
driver messages
traceback
```

---

# 36. Frontend persistente

NO conectar todavía el frontend a:

```text
PATCH /api/occurrences
DELETE /api/occurrences
```

La UI/local domain puede adaptarse para representar correctamente
slot exclusions.

La integración HTTP pertenece a una fase posterior.

---

# 37. Apply Week

NO implementar todavía la persistencia de:

```text
Apply Week
```

Si el código local existente necesita adaptación mínima para no perder
`slot.excludedDates`, hacerlo.

No diseñar todavía su endpoint persistente.

---

# 38. Apply Future

NO implementar todavía:

```text
Apply Future persistente
modificación masiva de generation_slots
effectiveDate
reconciliación futura completa
```

Eso pertenece a MVP 05.6.4.3.

---

# 39. PostgreSQL

NO crear nuevas migraciones.

El esquema 003 ya contiene:

```text
generation_slot_excluded_dates
source_generation_slot_id
```

No modificar:

```text
001
002
003
```

Si se detecta un defecto real del esquema:

```text
detenerse y reportarlo
```

No crear `004` por iniciativa propia.

---

# 40. vcs_dev

Codex NO debe modificar:

```text
vcs_dev
```

No usar credenciales reales.

Utilizar PostgreSQL 16 aislado/efímero para integración.

Aplicar:

```text
001
002
003
```

---

# 41. Tests — DELETE recurrente multi-slot

Probar:

```text
PlanItem
S1 08:00–11:00
S2 14:00–17:00

misma fecha
O1 ← S1
O2 ← S2
```

Eliminar O2.

Verificar:

```text
O1 permanece
O2 desaparece

slot S1 permanece
slot S2 permanece

generation_slot_excluded_dates:
S2 + date

NO:
S1 + date
```

Rematerializar.

Verificar:

```text
O2 NO reaparece
O1 no se duplica
```

---

# 42. Tests — PATCH recurrente

Probar:

```text
S2 14:00–17:00
O2 14:00–17:00
```

PATCH:

```text
O2 → 15:00–18:00
```

Verificar:

```text
S2 sigue 14:00–17:00
O2 es 15:00–18:00
sourceGenerationSlotId = S2
```

Rematerializar:

```text
no aparece duplicado 14:00–17:00
```

---

# 43. Tests — mover fecha recurrente

Mover:

```text
O2
2026-09-20
```

a:

```text
2026-09-21
```

Verificar:

```text
slot exclusion:
S2 + 2026-09-20

occurrence:
date = 2026-09-21

sourceGenerationSlotId = S2
```

Rematerializar fecha original:

```text
no reaparece
```

---

# 44. Tests — manual_dates edit

Verificar que PATCH actualiza coherentemente:

```text
generation_slots
generation_slot_dates
occurrence
```

preservando:

```text
slot.id
occurrence.id
sourceGenerationSlotId
```

---

# 45. Tests — manual_dates delete

Con dos entries:

```text
S1
S2
```

eliminar S2.

Verificar:

```text
S1 permanece
S2 desaparece
O2 desaparece
PlanItem sigue válido
```

Intentar luego eliminar S1 como última entry:

```text
409
last_manual_entry
```

y verificar rollback completo.

---

# 46. Tests — ad-hoc

Occurrence con:

```text
sourceGenerationSlotId = null
```

PATCH:

```text
actualiza solo occurrence
```

DELETE:

```text
elimina solo occurrence
```

No crea:

```text
GenerationSlot
slot exclusion
```

---

# 47. Tests — slot excludedDates GET

Insertar:

```text
S2 + 2026-09-20
```

en:

```text
generation_slot_excluded_dates
```

GET planner-state debe devolver:

```js
{
  id: "S2",
  ...
  excludedDates: ["2026-09-20"]
}
```

sin HTTP 500.

---

# 48. Tests — slot exclusions materializer parity

JS y Python deben producir exactamente la misma semántica.

Fixture:

```text
S1
S2 excluded on selected date
S3
```

Resultado:

```text
S1 generated
S2 omitted
S3 generated
```

La prueba JS ↔ Python debe continuar verde.

---

# 49. Tests — rollback

Probar rollback real si falla:

```text
insert slot exclusion
update occurrence
delete occurrence
manual slot update
manual slot delete
```

No dejar mutaciones parciales.

---

# 50. Regresión

Ejecutar:

```text
todas las pruebas backend
9 suites frontend
JS/Python parity
PostgreSQL integration
git diff --check
```

Health endpoints deben permanecer verdes.

POST y GET existentes deben continuar funcionando.

---

# 51. Caso de aceptación principal

Dado:

```text
Prueba multi-slot
2026-09-20

08:00–11:00 ← S1
14:00–17:00 ← S2
```

debe ser posible eliminar únicamente:

```text
14:00–17:00
```

y obtener:

```text
08:00–11:00 permanece

S2 sigue siendo regla válida
pero:
S2.excludedDates incluye 2026-09-20
```

La rematerialización no debe recrear el segundo horario.

---

# 52. Segundo caso de aceptación

Dado:

```text
S2 recurrente
14:00–17:00
```

una occurrence concreta puede cambiar a:

```text
15:00–18:00
```

sin cambiar S2.

Las siguientes occurrences siguen:

```text
14:00–17:00
```

---

# 53. Fuera de alcance

NO implementar:

```text
PlanItem deletion
Apply Week persistente
Apply Future persistente
mass slot replacement
slot versioning
soft-delete de slots
frontend fetch integration
auth
multiusuario
Supabase
deployment
notifications
timezone por usuario
```

---

# 54. Git

Codex NO debe:

```text
commit
push
merge
cambiar de rama
```

El usuario controla Git.

---

# 55. Reporte requerido

Al terminar reportar:

1. archivos creados/modificados;
2. contrato exacto de PATCH occurrence;
3. contrato exacto de DELETE occurrence;
4. cómo se representan `slot.excludedDates`;
5. cómo se reconstruyen desde PostgreSQL;
6. cómo JS materializer aplica exclusión por slot;
7. cómo Python materializer aplica exclusión por slot;
8. comportamiento PATCH recurrente misma fecha;
9. comportamiento PATCH recurrente movida de fecha;
10. comportamiento PATCH manual;
11. comportamiento PATCH ad-hoc;
12. comportamiento DELETE recurring;
13. comportamiento DELETE manual;
14. protección de última manual entry;
15. comportamiento DELETE ad-hoc;
16. atomicidad/rollback;
17. locking/concurrencia;
18. resultado JS/Python parity;
19. número y resultado de tests backend;
20. resultado de suites frontend;
21. resultado PostgreSQL integration;
22. cualquier limitación o riesgo encontrado.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
001/002/003 no fueron modificadas
no se hizo commit/push/merge
```