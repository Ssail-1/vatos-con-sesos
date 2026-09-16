# CURRENT TASK

## MVP 05.6.4.2 — Persisted Apply Week / week-scoped schedule overrides

### Documento normativo

La especificación global multi-slot está en:

`docs/codex/gestor_de_habitos/planeacion/MVP_05_6/MULTI_SLOT_SCHEDULING.md`

Este documento define exclusivamente:

```text
MVP 05.6.4.2
Apply Week
```

Estado actual:

```text
05.6.1  Frontend/domain multi-slot                 ✅
05.6.2  PostgreSQL multi-slot                      ✅
05.6.3  Backend multi-slot                         ✅
05.6.4.1 Single-occurrence mutations              ✅
         ├── PATCH occurrence
         ├── DELETE occurrence
         └── slot.excludedDates

05.6.4.2 Apply Week                               ← ACTUAL
05.6.4.3 Apply Future                             → después
```

---

# 1. Semántica cerrada

Existen tres niveles distintos de edición.

## Solo este día

Modifica una occurrence concreta.

Ya implementado en MVP 05.6.4.1.

## Aplicar a esta semana

Modifica únicamente el calendario concreto de la semana seleccionada.

Puede afectar:

```text
una occurrence
varias occurrences
varios días
altas ad-hoc
eliminaciones temporales
cambios de horario
```

pero NO modifica la regla recurrente general.

La siguiente semana vuelve a obedecer normalmente:

```text
generationConfig
+
GenerationSlots
```

## Aplicar de aquí en adelante

Modificará la configuración general desde una fecha efectiva.

NO pertenece a esta fase.

Será MVP 05.6.4.3.

---

# 2. Principio fundamental de Apply Week

Apply Week representa:

```text
excepciones concretas de calendario
```

NO:

```text
una nueva configuración recurrente
```

Por tanto Apply Week NO modifica:

```text
generation_configs.mode
generation_configs.start/end
interval_days
GenerationSlot.start_time/end_time
generation_slot_weekdays
generation_slot_dates
```

para PlanItems recurrentes.

---

# 3. Semana

Utilizar semana ISO:

```text
lunes → domingo
```

Coherente con:

```text
isoWeekday 1..7
```

El request recibe:

```text
anchorDate
```

El backend deriva:

```text
weekStart = lunes
weekEnd   = domingo
```

No confiar en weekStart/weekEnd enviados por cliente.

---

# 4. Modos soportados

Apply Week persistente aplica a:

```text
weekly
interval_days
```

`manual_dates` NO necesita esta semántica porque ya representa fechas
explícitas.

Para manual_dates usar:

```text
PATCH occurrence
DELETE occurrence
```

de MVP 05.6.4.1.

Si se intenta Apply Week sobre manual_dates:

```text
409 unsupported_mode
```

o código de dominio equivalente y sanitizado.

---

# 5. API

Implementar una operación atómica de semana.

Ruta preferida:

```text
POST /api/plan-items/<plan_item_id>/apply-week
```

Contrato:

```json
{
  "anchorDate": "YYYY-MM-DD",
  "operations": []
}
```

`operations` contiene únicamente los cambios que el usuario realizó.

NO es necesario reenviar occurrences que permanecen sin cambios.

---

# 6. Tipos de operación

Tipos válidos:

```text
update
delete
create
```

No aceptar otros.

Debe existir al menos una operación.

---

# 7. Update

Contrato:

```json
{
  "type": "update",
  "occurrenceId": "UUID",
  "date": "YYYY-MM-DD",
  "startTime": "HH:MM",
  "endTime": "HH:MM"
}
```

Representa el estado final deseado de esa occurrence.

Puede:

```text
cambiar horario
cambiar fecha dentro de la misma semana
cambiar ambos
```

No cambia status.

---

# 8. Delete

Contrato:

```json
{
  "type": "delete",
  "occurrenceId": "UUID"
}
```

La occurrence debe:

```text
pertenecer al PlanItem de la URL
estar actualmente dentro de la semana objetivo
```

---

# 9. Create

Contrato:

```json
{
  "type": "create",
  "date": "YYYY-MM-DD",
  "startTime": "HH:MM",
  "endTime": "HH:MM"
}
```

Representa una aparición excepcional solo para esa semana.

Backend genera:

```text
Occurrence.id UUID v4
```

y persiste:

```text
source_generation_slot_id = NULL
status = pending
```

NO crear GenerationSlot.

Una creación de semana es:

```text
ad-hoc
```

porque no modifica la programación general.

---

# 10. Ejemplo

Configuración general:

```text
Uber

lunes
08–11
14–17
20–22

martes
08–11
14–17
20–22
```

El usuario cambia únicamente esta semana:

```text
martes
14–17
→ 15–18

miércoles
elimina 20–22

jueves
agrega 12–13
```

Apply Week debe persistir conceptualmente:

```text
martes existing occurrence
→ update

miércoles generated occurrence
→ slot exclusion + delete

jueves new schedule
→ ad-hoc occurrence
```

GenerationSlots siguen intactos.

---

# 11. Reutilización de 05.6.4.1

No duplicar semántica.

Las operaciones individuales deben reutilizar, cuando sea razonable, las
reglas ya implementadas en:

```text
occurrence_mutation_service
scheduling_policy
repository layer
```

Pero Apply Week NO debe ejecutar varias transacciones independientes.

Debe existir una única transacción para TODO el batch.

---

# 12. Atomicidad de semana

Apply Week es:

```text
TODO O NADA
```

Ejemplo:

```text
5 updates
2 deletes
1 create
```

Si falla el último create:

```text
ninguna de las 8 operaciones queda aplicada
```

Usar:

```text
una conexión
una transacción
```

Preferir el nivel de aislamiento coherente con 05.6.4.1.

Actualmente las mutations utilizan:

```text
SERIALIZABLE
```

Mantenerlo salvo razón técnica documentada.

---

# 13. Locking

Antes de mutar:

```text
lock PlanItem
lock generation config
lock occurrences relevantes
lock slots relevantes
```

y cualquier otra fila necesaria.

Evitar:

```text
lost updates
double deletes
concurrent week replacement
inconsistent exclusions
```

Dos Apply Week concurrentes sobre el mismo PlanItem/semana no deben
producir estado mezclado.

---

# 14. Validación de pertenencia

Todo `occurrenceId` de update/delete debe:

```text
existir
pertenecer al plan_item_id de URL
```

Si no:

```text
404 occurrence_not_found
```

o conflicto/identificador apropiado sin revelar información sensible.

No permitir modificar una occurrence de otro PlanItem mediante un batch.

---

# 15. Validación de semana

Para update:

```text
la occurrence ORIGINAL debe estar dentro de la semana objetivo
```

y:

```text
la nueva date también debe quedar dentro de esa misma semana
```

Para create:

```text
date debe quedar dentro de la semana objetivo
```

No permitir que Apply Week modifique otra semana.

---

# 16. No duplicar occurrenceId

Un occurrenceId puede aparecer como máximo UNA vez en el batch.

Inválido:

```text
update O1
delete O1
```

o:

```text
update O1
update O1
```

Responder:

```text
400 invalid_payload
```

---

# 17. Update recurrente — misma fecha

Misma semántica que 05.6.4.1:

```text
Occurrence cambia date/time solicitado
GenerationSlot NO cambia
sourceGenerationSlotId se conserva
```

Si la fecha no cambia:

```text
no crear slot exclusion
```

---

# 18. Update recurrente — fecha distinta dentro de semana

Misma semántica que 05.6.4.1:

```text
slot exclusion
→ fecha original

Occurrence
→ fecha nueva

sourceGenerationSlotId
→ preservado
```

No modificar GenerationSlot.

---

# 19. Delete recurrente

Misma semántica que 05.6.4.1:

```text
generation_slot_excluded_dates
slot + occurrence original date

delete occurrence
```

El slot sigue existiendo.

---

# 20. Update/Delete ad-hoc

Si:

```text
sourceGenerationSlotId IS NULL
```

Update:

```text
modifica solo occurrence
```

Delete:

```text
elimina solo occurrence
```

No crear slot exclusion.

---

# 21. Create de semana

Cada create produce:

```text
Occurrence nueva
sourceGenerationSlotId = NULL
```

No modificar:

```text
GenerationSlots
generation_config
```

La próxima semana NO aparece esa occurrence automáticamente.

---

# 22. Final-state validation

Este punto es crítico.

NO validar el batch simplemente ejecutando cada operación una por una
contra el estado original.

Debe construirse conceptualmente:

```text
estado inicial de la semana
+
todas las operaciones
=
estado final candidato
```

y validar ese estado final.

---

# 23. Evitar falsos conflictos internos

Ejemplo:

```text
O1 08–09
O2 09–10
```

Batch:

```text
O1 → 09–10
O2 → 08–09
```

El resultado final no se solapa.

Una validación secuencial ingenua podría rechazar el primer update porque
O2 todavía ocupa 09–10.

Apply Week debe considerar:

```text
el resultado FINAL del batch
```

No el orden accidental de las operaciones.

---

# 24. Conflictos internos

Después de aplicar conceptualmente todas las operaciones:

```text
occurrences del mismo PlanItem
```

no deben quedar con solapamientos inválidos según las reglas actuales.

Intervalos contiguos continúan permitidos.

---

# 25. Conflictos externos

Validar el estado final contra occurrences de otros PlanItems.

Preservar:

```text
priority
completed conflict
intervalos semiabiertos
priority override requirement
```

Si cualquier cambio del batch requiere confirmación de priority override:

```text
rechazar batch completo con 409
```

No aplicar parcialmente.

No implementar todavía un nuevo handshake batch si no existe diseño
aprobado.

---

# 26. Unicidad slot + date

Preservar:

```text
sourceGenerationSlotId + date
```

como identidad lógica recurrente.

El estado final no puede contener:

```text
dos occurrences del mismo source slot
en la misma fecha
```

salvo que alguna sea ad-hoc con source NULL.

---

# 27. Batch moves y constraint intermedia

La validación debe basarse en el estado final.

Si dos movimientos forman un resultado final válido pero el orden SQL
podría chocar temporalmente con:

```text
UNIQUE(source_generation_slot_id, occurrence_date)
```

no rechazar únicamente por orden de ejecución.

Implementar una estrategia transaccional segura para preservar:

```text
occurrence.id
sourceGenerationSlotId
```

sin exponer estado intermedio.

No eliminar procedencia como resultado final.

Documentar la estrategia utilizada.

---

# 28. Temporal integrity

Apply Week sigue sujeto a la política temporal existente.

No modificar historia congelada.

Para una semana que contiene fechas editables y congeladas:

```text
las occurrences congeladas pueden permanecer sin cambios
```

pero cualquier operación que intente modificarlas/eliminarlas debe fallar.

No fallar únicamente porque la semana contiene una fecha congelada si el
batch no intenta tocarla.

---

# 29. Status

No modificar:

```text
status
statusContext
```

mediante operaciones update.

Create inicia:

```text
pending
```

Delete respeta las reglas actuales de status.

Occurrences protegidas por relaciones/statusContext deben conservar las
protecciones implementadas en 05.6.4.1.

---

# 30. Slot exclusions

Apply Week puede producir:

```text
slot.excludedDates
```

mediante deletes/moves de occurrences recurrentes.

Estas exclusiones continúan reconstruyéndose por:

```text
GET /api/planner-state
```

No crear exclusiones globales de PlanItem para representar cambios
semanales de slots concretos.

---

# 31. Generación general permanece intacta

Después de Apply Week:

```text
generation_slots
```

debe ser idéntico al anterior salvo que una operación fuera explícitamente
de otro tipo permitido, lo cual esta fase NO contempla.

Verificar mediante test SQL.

---

# 32. Semana siguiente

Caso obligatorio:

Regla:

```text
lunes 14–17
```

Esta semana:

```text
lunes → update 15–18
```

Semana siguiente:

```text
materialización debe seguir produciendo 14–17
```

Apply Week nunca debe convertir 15–18 en la nueva regla recurrente.

---

# 33. Frontend/domain local

La funcionalidad local Apply Week que quedó bloqueada para multi-slot en
MVP 05.6.1 puede adaptarse ahora.

Debe compartir la misma semántica:

```text
update
delete
create
```

dentro de una semana.

NO conectar todavía HTTP fetch si la integración frontend/backend sigue
fuera del alcance actual.

No implementar Apply Future.

---

# 34. UI

Preservar conceptualmente las opciones:

```text
Solo este día
Aplicar a esta semana
Aplicar de aquí en adelante
```

En esta fase:

```text
Solo este día
→ comportamiento existente

Aplicar a esta semana
→ habilitar semántica multi-slot correspondiente

Aplicar de aquí en adelante
→ puede continuar bloqueado/controlado hasta 05.6.4.3
```

No rediseñar visualmente la aplicación salvo adaptación mínima necesaria.

---

# 35. Manual dates en frontend

No ofrecer Apply Week como una transformación especial para:

```text
manual_dates
```

si puede evitarse limpiamente.

Las entries manuales ya son instrucciones explícitas.

Mantener edición/eliminación individual.

---

# 36. Backend architecture

Mantener:

```text
app.py
→ HTTP

services
→ orquestación/domain

scheduling_policy
→ reglas compartidas

repositories
→ SQL
```

Crear un servicio de week mutation si mejora claridad.

No convertir:

```text
app.py
```

en implementación de reglas de negocio.

---

# 37. Endpoint response

Respuesta correcta:

```text
HTTP 200
```

Contrato sugerido:

```json
{
  "weekStart": "YYYY-MM-DD",
  "weekEnd": "YYYY-MM-DD",
  "occurrences": []
}
```

`occurrences` contiene el estado persistido final de ESE PlanItem dentro
de la semana después del batch.

Cada occurrence usa el contrato canónico existente:

```text
id
planItemId
sourceGenerationSlotId?
date
startTime
endTime
status
statusContext?
```

Orden determinista:

```text
date
startTime
endTime
id
```

---

# 38. Error handling

Mantener errores sanitizados.

Como mínimo:

```text
400 invalid_payload
400 invalid_identifier

404 plan_item_not_found
404 occurrence_not_found

409 unsupported_mode
409 history_frozen
409 status conflict
409 schedule conflict
409 slot_date_conflict
409 priority_override_required
409 concurrent_modification

500 persisted state invalid
503 database unavailable
```

No exponer:

```text
SQL
DSN
password
driver internals
traceback
```

---

# 39. PostgreSQL

No modificar:

```text
001
002
003
```

No crear migración 004 para Apply Week.

El modelo actual ya permite representar:

```text
updates concretos
slot exclusions
ad-hoc occurrences
```

Si se descubre que el esquema NO puede representar correctamente una
semántica necesaria:

```text
detenerse y reportarlo
```

No improvisar migración.

---

# 40. vcs_dev

NO modificar:

```text
vcs_dev
```

durante implementación automática.

Usar PostgreSQL 16 aislado/efímero.

Aplicar:

```text
001
002
003
```

---

# 41. Test principal

PlanItem recurring con:

```text
lunes
S1 08–11
S2 14–17

martes
S3 08–11
S4 14–17

miércoles
S5 08–11
S6 14–17
```

Batch de esta semana:

```text
update S2 occurrence
14–17 → 15–18

delete S4 occurrence

create miércoles
20–21
```

Verificar:

```text
S2 GenerationSlot sigue 14–17

S4 GenerationSlot sigue existiendo
S4 excludedDates incluye martes de esta semana

miércoles ad-hoc:
sourceGenerationSlotId = NULL

demás occurrences intactas
```

---

# 42. Semana siguiente test

Materializar semana siguiente.

Esperar:

```text
S2 vuelve 14–17
S4 vuelve a aparecer normalmente
ad-hoc 20–21 no reaparece
```

---

# 43. Batch rollback

Crear batch con:

```text
varias operaciones válidas
+
una inválida al final
```

Verificar:

```text
0 cambios persistidos
```

Incluyendo:

```text
0 slot exclusions nuevas
0 updates parciales
0 deletes parciales
0 creates parciales
```

---

# 44. Batch final-state conflict

Crear escenario donde:

```text
operaciones individuales parecen chocar con estado viejo
pero estado final es válido
```

Debe aceptar.

Crear otro donde:

```text
estado final realmente se solapa
```

Debe rechazar todo.

---

# 45. Wrong week

Intentar:

```text
anchorDate semana A
update occurrence semana B
```

Debe rechazarse.

Create fuera de semana:

```text
rechazado
```

Update que mueve occurrence fuera de semana:

```text
rechazado
```

---

# 46. Wrong PlanItem

Intentar incluir occurrence de:

```text
PlanItem B
```

en Apply Week de:

```text
PlanItem A
```

Debe rechazarse y hacer rollback completo.

---

# 47. Frozen history

Semana actual con algún día congelado.

Cambiar solo fechas editables:

```text
permitido
```

Intentar modificar occurrence congelada:

```text
rechazado
```

Batch completo hace rollback.

---

# 48. Concurrency test

Dos transacciones Apply Week concurrentes sobre:

```text
mismo PlanItem
misma semana
```

no deben mezclar parcialmente sus resultados.

Probar comportamiento real bajo PostgreSQL.

---

# 49. Regression

Ejecutar:

```text
todas las pruebas backend
todas las suites frontend
JS/Python parity
PostgreSQL integration
health routes
POST plan-items
GET planner-state
PATCH occurrence
DELETE occurrence
git diff --check
```

No introducir regresiones de 05.6.4.1.

---

# 50. Fuera de alcance

NO implementar:

```text
Apply Future
effective-dated GenerationSlot versions
PlanItem deletion
auth
multiusuario
Supabase
deployment
notifications
timezone por usuario
frontend/backend fetch integration completa
```

---

# 51. Git

Codex NO debe:

```text
commit
push
merge
cambiar rama
```

El usuario controla Git.

---

# 52. Reporte requerido

Al terminar reportar:

1. archivos creados/modificados;
2. endpoint exacto de Apply Week;
3. payload exacto;
4. respuesta exacta;
5. cálculo de semana ISO;
6. semántica update;
7. semántica delete;
8. semántica create ad-hoc;
9. cómo preserva GenerationSlots;
10. cómo utiliza slot exclusions;
11. estrategia de final-state validation;
12. cómo evita falsos conflictos entre operaciones del batch;
13. cómo resuelve `sourceGenerationSlotId + date`;
14. atomicidad;
15. locking y SERIALIZABLE;
16. comportamiento temporal;
17. comportamiento con status/statusContext;
18. frontend/domain local Apply Week;
19. resultado de semana siguiente;
20. rollback real;
21. prueba de concurrencia;
22. número/resultados de tests backend;
23. resultado frontend;
24. resultado JS/Python parity;
25. resultado PostgreSQL integration;
26. limitaciones/riesgos.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
001/002/003 no fueron modificadas
Apply Future no fue implementado
no se hizo commit/push/merge
```
