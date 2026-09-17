# CURRENT TASK

## MVP 05.6.4.3 — Persisted Apply Future / rewrite recurring schedule from effective date

### Documento normativo

La especificación global multi-slot está en:

`docs/codex/gestor_de_habitos/planeacion/MVP_05_6/MULTI_SLOT_SCHEDULING.md`

Este documento define exclusivamente:

```text
MVP 05.6.4.3
Aplicar de aquí en adelante
```

Estado actual:

```text
05.6.1    Frontend/domain multi-slot                 ✅
05.6.2    PostgreSQL multi-slot                      ✅
05.6.3    Backend multi-slot                         ✅
05.6.4.1  Solo este día                              ✅
05.6.4.2  Aplicar a esta semana                      ✅
05.6.4.3  Aplicar de aquí en adelante                ← ACTUAL
```

---

# 1. Decisión arquitectónica cerrada

NO se implementará versionado histórico de GenerationSlots.

NO necesitamos conservar:

```text
cómo era históricamente el GenerationSlot
cuando creó una occurrence
```

La fuente de verdad histórica es:

```text
Occurrence
```

porque almacena independientemente:

```text
date
startTime
endTime
status
```

`GenerationSlot` representa el motor/programación ACTUAL.

---

# 2. Significado de sourceGenerationSlotId

`sourceGenerationSlotId` es una referencia OPERACIONAL.

Sirve para:

```text
idempotencia slot + date
slot exclusions
single-day mutations
Apply Week
Apply Future
relacionar una occurrence recurrente con su regla lógica actual
```

NO significa:

```text
versión histórica exacta de la regla que produjo la occurrence
```

Una occurrence histórica puede apuntar a un slot cuyo horario actual ya
sea diferente.

Eso es válido.

---

# 3. Occurrence vs GenerationSlot

Mantener esta separación:

```text
PlanItem
→ qué actividad/hábito es

GenerationSlot
→ cuándo puede generarse una occurrence

Occurrence
→ aparición concreta materializada
```

Ejemplo:

```text
GenerationSlot S1
lunes 14:00–17:00

puede producir:

O1 lunes 14 Sep
O2 lunes 21 Sep
O3 lunes 28 Sep
```

No tratar occurrence y slot como la misma entidad.

---

# 4. Semántica de los tres scopes

## Solo este día

```text
Occurrence concreta
```

Ya implementado.

## Aplicar a esta semana

```text
Occurrences concretas + excepciones
```

GenerationSlots permanecen intactos.

Ya implementado.

## Aplicar de aquí en adelante

```text
Modificar el motor recurrente actual
+
reconciliar occurrences futuras materializadas
```

Esta es la tarea actual.

---

# 5. Principio de Apply Future

Apply Future significa:

> Desde una fecha efectiva, esta será la nueva programación recurrente
> del PlanItem.

La programación anterior NO necesita seguir representada por
generationConfig/GenerationSlots.

Las occurrences anteriores ya contienen la historia real.

---

# 6. No effective-dated slot versions

NO introducir:

```text
effective_from en generation_slots
effective_until
slot_versions
generation_config_versions
temporal tables
history tables de reglas
```

No crear versiones:

```text
S1 viejo
S2 nuevo
```

solo por cambiar el horario.

Si sigue siendo el mismo slot lógico:

```text
editar S1 en sitio
preservar S1.id
```

---

# 7. Identidad de slots

Regla:

```text
slot existente editado
→ conserva UUID

slot nuevo
→ nuevo UUID v4 generado por frontend

slot eliminado
→ desaparece del motor actual
```

No generar UUID nuevo únicamente porque cambió:

```text
startTime
endTime
isoWeekday
```

si el frontend conserva su identidad lógica.

---

# 8. Slots eliminados e historia

Si Apply Future elimina un GenerationSlot:

```text
generation_slots row
→ puede eliminarse
```

La FK existente:

```text
occurrences.source_generation_slot_id
ON DELETE SET NULL
```

puede desprender occurrences anteriores.

Esto es aceptable.

La occurrence histórica conserva:

```text
date
time
status
```

y sigue siendo válida.

No preservar un slot únicamente para mantener esa FK histórica.

---

# 9. Endpoint

Implementar:

```text
POST /api/plan-items/<plan_item_id>/apply-future
```

No usar PATCH genérico para esta operación porque es una mutación
compuesta con reconciliación.

---

# 10. Payload

Payload:

```json
{
  "futureConfig": {
    "mode": "weekly",
    "startDate": "2026-09-21",
    "endDate": null,
    "indefinite": true,
    "slots": [
      {
        "id": "UUID-v4",
        "isoWeekday": 1,
        "startTime": "15:00",
        "endTime": "18:00"
      }
    ]
  }
}
```

Para interval:

```json
{
  "futureConfig": {
    "mode": "interval_days",
    "startDate": "2026-09-21",
    "endDate": null,
    "indefinite": true,
    "intervalDays": 1,
    "slots": [
      {
        "id": "UUID-v4",
        "startTime": "08:00",
        "endTime": "09:00"
      }
    ]
  }
}
```

---

# 11. startDate ES la fecha efectiva

No agregar además:

```text
effectiveDate
```

para evitar dos fuentes de verdad.

La fecha efectiva es:

```text
futureConfig.startDate
```

Conceptualmente:

```text
antes de startDate
→ occurrences ya materializadas representan la historia/calendario previo

desde startDate
→ aplica el nuevo motor
```

---

# 12. Temporal integrity de startDate

`futureConfig.startDate` no puede estar dentro de historia congelada.

Debe pasar la política temporal existente.

Puede ser:

```text
fecha editable actual
o fecha futura
```

No reescribir occurrences congeladas.

---

# 13. Modos soportados

Soportar:

```text
weekly
interval_days
```

`manual_dates` no utiliza Apply Future.

Si se intenta:

```text
409 unsupported_mode
```

---

# 14. Cambio de mode

En esta fase NO cambiar:

```text
weekly ↔ interval_days
```

El `futureConfig.mode` debe coincidir con el mode persistido.

Si difiere:

```text
409 mode_change_not_supported
```

o código equivalente sanitizado.

La modificación de tipo de recurrencia puede diseñarse después si se
necesita.

---

# 15. Weekly futureConfig

Validar:

```text
startDate
endDate / indefinite
slots[]
```

Cada slot:

```text
UUID v4
isoWeekday 1..7
startTime < endTime
```

No solapamientos dentro del mismo weekday.

Contiguos permitidos.

Debe existir al menos un slot.

---

# 16. Interval futureConfig

Validar:

```text
startDate
endDate / indefinite
intervalDays > 0
slots[]
```

Cada slot:

```text
UUID v4
startTime < endTime
```

No solapamientos.

Debe existir al menos un slot.

---

# 17. excludedDates globales

Apply Future NO elimina automáticamente:

```text
generation_excluded_dates
```

Son excepciones explícitas del calendario y deben preservarse.

No exigir que frontend las reenvíe en `futureConfig`.

`futureConfig` NO acepta:

```text
excludedDates
```

en esta fase.

---

# 18. slot.excludedDates

Para slots que conservan el mismo UUID:

```text
generation_slot_excluded_dates
```

se preservan.

Apply Future no debe borrar excepciones de días concretos ya realizadas.

Para slots eliminados:

```text
sus slot exclusions pueden desaparecer por CASCADE
```

porque la regla ya no existe.

Los slots nuevos comienzan sin exclusiones.

`futureConfig.slots` NO necesita reenviar `excludedDates`.

---

# 19. stoppedFromDate

Apply Future NO redefine automáticamente:

```text
stoppedFromDate
```

Preservar la política persistida existente.

Si `stoppedFromDate` hace que el nuevo futureConfig no pueda aplicarse de
forma coherente:

```text
rechazar con conflicto de dominio
```

No reactivar silenciosamente un PlanItem detenido.

---

# 20. Actualización de generation_configs

Apply Future actualiza el motor ACTUAL.

Para weekly:

```text
mode permanece weekly
start_date = futureConfig.startDate
end_date
indefinite
interval_days = NULL
```

Para interval:

```text
mode permanece interval_days
start_date = futureConfig.startDate
end_date
indefinite
interval_days = futureConfig.intervalDays
```

No conservar el startDate histórico anterior como metadata.

Las occurrences anteriores ya representan la historia.

---

# 21. Reconciliación

Apply Future debe reconciliar:

```text
occurrences materializadas
con date >= futureConfig.startDate
```

dentro del horizonte actualmente materializado.

No intentar materializar infinito.

El materializador normal utilizará el nuevo motor para extender el futuro
más adelante.

---

# 22. No tocar occurrences anteriores

Toda occurrence con:

```text
date < futureConfig.startDate
```

permanece intacta.

No cambiar:

```text
date
time
status
statusContext
```

aunque su GenerationSlot actual cambie.

---

# 23. Clasificar occurrences futuras

Antes de mutar slots/config, clasificar las occurrences futuras del
PlanItem.

Distinguir:

```text
baseline recurring occurrence
explicit override occurrence
ad-hoc occurrence
```

---

# 24. Ad-hoc occurrence

Si:

```text
sourceGenerationSlotId = NULL
```

es una aparición explícita.

Apply Future debe preservarla.

NO borrarla únicamente por cambiar el motor recurrente.

---

# 25. Baseline recurring occurrence

Una occurrence recurrente se considera baseline si coincide con la regla
persistida ANTES del Apply Future.

Conceptualmente:

```text
source slot existente
+
fecha válida según config/slot anterior
+
start/end iguales al slot anterior
```

Estas occurrences pueden ser reconciliadas con el nuevo motor.

---

# 26. Explicit recurring override

Una occurrence con source slot puede ser una excepción concreta si ya fue
modificada por:

```text
Solo este día
Apply Week
```

Ejemplos:

```text
horario distinto del slot original
fecha movida
```

Estas occurrences son verdad explícita del calendario.

Apply Future debe preservarlas cuando sea posible.

No sobrescribir automáticamente una excepción concreta únicamente porque
cambió el baseline.

---

# 27. Slot exclusions existentes

Una occurrence eliminada mediante:

```text
Solo este día
Apply Week
```

puede estar representada por:

```text
generation_slot_excluded_dates
```

Estas exclusiones se preservan para slots que sobreviven.

Por tanto Apply Future NO debe recrear una occurrence explícitamente
eliminada para esa fecha.

---

# 28. Slot existente modificado

Ejemplo:

```text
S1 viejo
14:00–17:00

futureConfig:
S1
15:00–18:00
```

Actualizar:

```text
generation_slots.start_time
generation_slots.end_time
```

preservando:

```text
S1.id
```

Las occurrences históricas previas no cambian.

---

# 29. Weekly weekday edit

Si S1 cambia:

```text
lunes
→ martes
```

preservar S1.id si el frontend mantuvo ese UUID.

Actualizar:

```text
generation_slot_weekdays.iso_weekday
```

Reconciliar baseline future occurrences.

No tocar historia anterior a startDate.

---

# 30. Slot nuevo

Un slot presente en futureConfig pero inexistente en DB:

```text
insert generation_slots
```

y weekday detail cuando corresponda.

Debe utilizar exactamente el UUID recibido.

Generar sus baseline occurrences únicamente desde:

```text
futureConfig.startDate
```

Nunca antes.

---

# 31. Slot eliminado

Un slot existente que no aparece en futureConfig:

```text
deja de formar parte del motor
```

Eliminar sus baseline occurrences desde startDate.

Las explicit overrides asociadas a ese slot NO deben perderse.

Antes de eliminar el slot:

```text
preservar esas occurrences
```

Después la FK:

```text
ON DELETE SET NULL
```

puede convertirlas en ad-hoc.

Luego eliminar GenerationSlot.

---

# 32. Historia de slot eliminado

Occurrences anteriores a startDate pueden quedar:

```text
sourceGenerationSlotId = NULL
```

tras eliminar el slot.

Esto es aceptable.

NO crear una copia/version histórica del slot.

---

# 33. Reused slot + baseline occurrence

Si un slot sigue existiendo y una baseline occurrence futura corresponde
todavía a una fecha válida:

```text
preservar occurrence.id si es razonable
actualizar horario al nuevo baseline
preservar sourceGenerationSlotId
```

Evitar borrar/recrear innecesariamente si puede actualizarse de forma
segura.

---

# 34. Baseline occurrence ya no válida

Si después del nuevo futureConfig:

```text
una fecha ya no debe tener ese slot
```

eliminar esa baseline occurrence.

No crear slot exclusion, porque esto no es una excepción:

```text
la regla general cambió
```

---

# 35. Nueva baseline occurrence

Si el nuevo futureConfig requiere:

```text
slot + fecha
```

y no existe baseline/override/exclusion que la cubra:

```text
crear occurrence
```

con:

```text
UUID v4 backend
sourceGenerationSlotId = slot.id
status = pending
```

---

# 36. Override con slot reutilizado

Si existe una explicit override:

```text
S1 baseline viejo 14–17
Occurrence concreta 15–18
```

y Apply Future cambia S1:

```text
16–19
```

la occurrence concreta:

```text
15–18
```

se preserva.

Su:

```text
sourceGenerationSlotId = S1
```

también puede preservarse.

Por `slot + date` idempotency, no crear además una baseline 16–19 ese mismo
día.

---

# 37. Override cuyo slot se elimina

Si una explicit override pertenece a un slot que Apply Future elimina:

```text
preservar occurrence
```

y permitir que:

```text
sourceGenerationSlotId → NULL
```

por eliminación del slot.

La appearance explícita sigue existiendo.

---

# 38. Apply Week previo

Apply Future NO debe destruir automáticamente decisiones previas de:

```text
Apply Week
```

Los siguientes datos son excepciones explícitas:

```text
ad-hoc occurrences
edited recurring occurrences
slot exclusions
```

y deben sobrevivir cuando sea coherente.

---

# 39. Materializer boundary

Después de Apply Future:

```text
generation_configs.start_date
=
futureConfig.startDate
```

Esto es crítico.

El materializador nunca debe aplicar nuevos slots antes de esa fecha.

Por eso no necesitamos:

```text
effective_from por slot
```

---

# 40. Interval phase

Para `interval_days`, el nuevo:

```text
startDate
```

define también el nuevo origen del intervalo.

Ejemplo:

```text
startDate = Sep 21
intervalDays = 3
```

produce:

```text
Sep 21
Sep 24
Sep 27
...
```

Esto es intencional.

Apply Future redefine el motor desde su nueva fecha efectiva.

---

# 41. Final-state validation

Como Apply Week, validar conceptualmente:

```text
estado persistido actual
+
nuevo motor
+
reconciliación
=
estado final candidato
```

antes de confirmar.

No depender de un orden accidental de UPDATE/DELETE/INSERT.

---

# 42. Conflictos internos

El estado final del PlanItem no puede contener:

```text
solapamientos inválidos
duplicados source slot + date
```

Intervalos contiguos permanecen válidos.

Preservar explicit overrides y ad-hoc únicamente si el estado final sigue
siendo válido.

---

# 43. Conflictos externos

Validar las nuevas/actualizadas occurrences contra otros PlanItems.

Mantener:

```text
priority
completed conflict
intervalos semiabiertos
priority_override_required
```

Si el nuevo motor requiere un override no confirmado:

```text
rechazar TODO Apply Future
```

No aplicar parcialmente.

---

# 44. Status

No cambiar automáticamente status de occurrences preservadas.

Baseline occurrences nuevas:

```text
pending
```

Si una occurrence futura existente tiene un status que impide
reconciliación:

```text
respetar scheduling_policy
```

y rechazar la operación completa si corresponde.

No forzar cambios de status para hacer pasar la operación.

---

# 45. statusContext / sourceOccurrenceId

Preservar las protecciones existentes.

No eliminar/modificar una occurrence requerida por un:

```text
priority_override
sourceOccurrenceId
```

sin respetar las reglas actuales.

`sourceOccurrenceId` NO tiene relación con GenerationSlot versioning.

---

# 46. Atomicidad

Apply Future debe ser:

```text
TODO O NADA
```

Una sola:

```text
connection
transaction
```

Mantener:

```text
SERIALIZABLE
```

salvo razón técnica documentada.

---

# 47. Locking

Antes de modificar:

```text
lock PlanItem
lock generation_config
lock GenerationSlots actuales
lock occurrences relevantes desde startDate
lock dependencias/statusContext necesarias
lock conflictos externos pertinentes
```

Evitar:

```text
lost update
partial reconciliation
slot/config mismatch
concurrent Apply Future mezclado
```

---

# 48. Concurrencia

Dos Apply Future concurrentes sobre el mismo PlanItem:

```text
no pueden mezclarse
```

Resultado esperado:

```text
una transacción completa gana
otra falla/reintenta de manera controlada
```

Usar el mecanismo de:

```text
concurrent_modification
```

ya establecido cuando corresponda.

---

# 49. No migración 004

Con la decisión arquitectónica actual:

```text
NO necesitamos migración 004
para versionar slots.
```

No modificar:

```text
001
002
003
```

No crear migración nueva salvo que se descubra una imposibilidad REAL del
schema.

En ese caso:

```text
DETENERSE Y REPORTAR
```

No improvisar.

---

# 50. GET planner-state

Después de Apply Future debe devolver:

```text
generationConfig actualizada
GenerationSlots actuales
occurrences históricas intactas
future occurrences reconciliadas
explicit overrides preservadas
```

No intentar reconstruir la configuración histórica anterior.

---

# 51. Respuesta endpoint

HTTP:

```text
200
```

Respuesta sugerida:

```json
{
  "planItem": {},
  "occurrences": []
}
```

`planItem` contiene el contrato canónico actual después del Apply Future.

`occurrences` contiene las occurrences del PlanItem dentro del horizonte
persistido relevante desde `futureConfig.startDate`.

Orden determinista.

No es necesario devolver historia anterior completa.

---

# 52. Frontend/domain local

Eliminar el bloqueo multi-slot de:

```text
Apply Future
```

y adaptar el dominio local a la misma semántica.

El frontend genera/preserva IDs de GenerationSlots.

Cuando se edita un slot existente:

```text
preservar id
```

Cuando se agrega uno:

```text
crypto.randomUUID()
```

Cuando se elimina:

```text
dejar de incluirlo en futureConfig
```

---

# 53. Frontend HTTP

NO conectar todavía el frontend real al endpoint si la integración
frontend/backend continúa fuera de alcance.

La semántica local debe quedar preparada y probada.

---

# 54. PlanItem identity

Apply Future NO crea otro PlanItem.

Preservar:

```text
PlanItem.id
name
kind
activityType/habitType
```

Solo cambia su motor recurrente.

---

# 55. No PlanItem deletion

Un futureConfig recurrente debe conservar al menos un slot.

No usar Apply Future para:

```text
eliminar el PlanItem
```

El stop/delete general continúa siendo una operación separada.

---

# 56. Caso principal weekly

Estado actual:

```text
S1 lunes 08–11
S2 lunes 14–17
S3 martes 08–11
S4 martes 14–17
```

Apply Future desde Sep 21:

```text
S1 lunes 09–12       # mismo ID
S2 lunes 15–18       # mismo ID
S3 martes 08–11      # igual
S4 eliminado
S5 miércoles 20–22   # nuevo UUID
```

Verificar:

```text
occurrences < Sep 21 intactas

S1/S2/S3 conservan UUID

S4 se elimina del motor

baseline future de S4 desaparece

explicit override de S4, si existe, sobrevive y queda source NULL

S5 solo genera desde Sep 21

no aparece S5 antes de Sep 21
```

---

# 57. Caso principal interval

Antes:

```text
startDate Sep 1
intervalDays 2

S1 08–09
S2 18–19
```

Apply Future:

```text
startDate Sep 21
intervalDays 3

S1 09–10
S2 eliminado
S3 20–21
```

Verificar nueva fase:

```text
Sep 21
Sep 24
Sep 27
...
```

Historia anterior intacta.

---

# 58. Test historical occurrence

Crear:

```text
S1 viejo = 14–17

Occurrence histórica:
Sep 10
14–17
source=S1
```

Apply Future:

```text
S1 = 15–18
startDate Sep 21
```

Verificar:

```text
Occurrence Sep 10 sigue 14–17
source puede seguir S1
```

No exigir que S1 histórico diga 14–17.

---

# 59. Test removed slot history

Slot S2 tiene:

```text
occurrence histórica
occurrence baseline futura
explicit override futura
```

Eliminar S2 mediante Apply Future.

Esperar:

```text
histórica permanece, source NULL
baseline futura desaparece
override futura permanece, source NULL
```

---

# 60. Test explicit override preservation

Antes:

```text
S1 baseline 14–17

Sep 23 occurrence override:
15–18
source=S1
```

Apply Future:

```text
S1 → 16–19
startDate Sep 21
```

Esperar:

```text
Sep 23 sigue 15–18
source=S1

no generar además 16–19 para Sep 23
```

---

# 61. Test slot exclusion preservation

Antes:

```text
S1 excludedDates:
Sep 24
```

Apply Future conserva S1.

Esperar:

```text
Sep 24 sigue excluida
```

No regenerar baseline de S1 ese día.

---

# 62. Test ad-hoc preservation

Occurrence:

```text
Sep 25
20–21
source=NULL
```

Apply Future cambia motor.

Esperar:

```text
20–21 permanece
```

salvo que produzca un conflicto real con el estado final, caso en el que
debe rechazarse Apply Future completo.

---

# 63. Test startDate boundary

Agregar nuevo S5 con:

```text
futureConfig.startDate = Sep 21
```

Verificar:

```text
Sep 20 → NO S5
Sep 21+ → S5 según regla
```

Esto demuestra que no hace falta effective_from por slot.

---

# 64. Test frozen boundary

Intentar:

```text
futureConfig.startDate
```

en historia congelada.

Esperar rechazo controlado.

No cambiar config, slots ni occurrences.

---

# 65. Test rollback

Provocar fallo después de:

```text
config update
slot update
slot insert
slot delete preparation
occurrence reconciliation
```

Esperar:

```text
ROLLBACK completo
```

El motor y calendario quedan exactamente como antes.

---

# 66. Test concurrency

Dos Apply Future concurrentes sobre el mismo PlanItem con configuraciones
distintas.

No permitir estado mezclado como:

```text
config de A
slots de B
occurrences de ambos
```

Debe quedar una versión completa coherente.

---

# 67. PostgreSQL test

Usar PostgreSQL 16 aislado/efímero.

Aplicar:

```text
001
002
003
```

No utilizar:

```text
vcs_dev
```

---

# 68. Regression

Ejecutar:

```text
todas las pruebas backend
todas las suites frontend
JS/Python parity
PostgreSQL integration
health
POST plan-items
GET planner-state
PATCH occurrence
DELETE occurrence
Apply Week
git diff --check
```

No introducir regresiones.

---

# 69. Fuera de alcance

NO implementar:

```text
slot versioning
generationConfig history
effective_from/effective_until
mode change weekly ↔ interval_days
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

# 70. Git

Codex NO debe:

```text
commit
push
merge
cambiar rama
```

El usuario controla Git.

---

# 71. Reporte requerido

Al terminar reportar:

1. archivos creados/modificados;
2. endpoint exacto;
3. payload exacto;
4. respuesta exacta;
5. uso de `futureConfig.startDate` como fecha efectiva;
6. cómo actualiza generationConfig;
7. cómo actualiza slots preservando UUID;
8. cómo agrega slots;
9. cómo elimina slots;
10. qué ocurre con sourceGenerationSlotId histórico;
11. clasificación baseline/override/ad-hoc;
12. reconciliación de baseline future occurrences;
13. preservación de single-day/Apply Week overrides;
14. preservación de slot exclusions;
15. comportamiento interval_days;
16. final-state validation;
17. conflictos;
18. atomicidad;
19. locking/SERIALIZABLE;
20. concurrencia;
21. frontend/domain Apply Future;
22. resultado de boundary startDate;
23. resultado historia intacta;
24. rollback real;
25. número/resultados tests backend;
26. resultado frontend;
27. JS/Python parity;
28. integración PostgreSQL;
29. riesgos/limitaciones.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
001/002/003 no fueron modificadas
no se creó migration 004
no se implementó slot versioning
no se implementó mode change
no se hizo commit/push/merge
```