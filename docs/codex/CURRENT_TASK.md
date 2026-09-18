# CURRENT TASK

## MVP 05.7.2 — Persistent PlanItem creation from the UI

### Propósito

Conectar la creación de PlanItems del frontend real con el backend persistente.

Por primera vez, una actividad creada mediante:

```text
+ Agregar registro
```

debe recorrer:

```text
Formulario
    ↓
POST /api/plan-items
    ↓
Flask
    ↓
PostgreSQL
    ↓
GET /api/planner-state
    ↓
hydratePlannerState()
    ↓
UI
```

y sobrevivir:

```text
reload / F5
```

Estado:

```text
05.6      Dominio persistente                    ✅
05.6.5    Verificación integral                  ✅ READY

05.7      Frontend ↔ API integration
05.7.1    Bootstrap persistente                  ✅
05.7.2    Crear PlanItem persistente             ← ACTUAL
05.7.3    Single Day persistente                 → después
05.7.4    Apply Week / Apply Future persistentes → después
05.7.5    Mutation UX / errores / conflictos     → después
05.7.6    Verificación local final               → después
```

---

# 1. Alcance

Implementar exclusivamente la persistencia HTTP de:

```text
crear PlanItem
```

mediante:

```http
POST /api/plan-items
```

Después de una creación exitosa:

```text
GET /api/planner-state
→ hydratePlannerState()
```

PostgreSQL/backend continúa siendo la fuente autoritativa.

---

# 2. Fuera de alcance

NO conectar todavía:

```text
PATCH /api/occurrences/*
DELETE /api/occurrences/*
POST .../apply-week
POST .../apply-future
```

Esas mutations continúan locales temporalmente.

NO implementar:

```text
optimistic persistence
offline queue
LocalStorage
auth
multiusuario
deployment
PlanItem deletion general
```

---

# 3. Estrategia de sincronización

Usar inicialmente la estrategia aprobada:

```text
POST mutation
    ↓
200/201 success
    ↓
GET /api/planner-state
    ↓
hydratePlannerState()
```

NO mantener manualmente una segunda versión del estado persistido.

NO insertar localmente el PlanItem usando una copia reconstruida del payload
si el servidor ya puede devolver/representar la verdad persistida.

La sincronización final debe provenir de:

```text
GET /api/planner-state
```

---

# 4. No optimistic UI

NO mostrar el nuevo PlanItem como persistido antes de recibir confirmación
del backend.

Flujo:

```text
submit
→ loading/saving
→ POST
→ refresh GET
→ hydrate
→ render success
```

Si POST falla:

```text
store persistido permanece intacto
```

---

# 5. API client

Extender la capa creada en 05.7.1.

Preferentemente:

```text
js/api/planner-api.js
```

Añadir una operación equivalente a:

```js
createPlanItem(payload)
```

Responsabilidad:

```text
HTTP
JSON
status codes
network errors
```

NO:

```text
reglas de dominio
render
manejo del formulario
store mutation directa
```

---

# 6. No fetch disperso

NO llamar `fetch()` directamente desde:

```text
views
form
planner-store
```

Arquitectura:

```text
form/controller
      ↓
app/coordinator
      ↓
planner-api
      ↓
HTTP

success
      ↓
planner-api.getPlannerState()
      ↓
hydratePlannerState()
      ↓
render
```

Puede ajustarse a la arquitectura existente si mantiene estas
responsabilidades separadas.

---

# 7. Payload

El POST debe utilizar exactamente el contrato backend ya aprobado.

NO crear una segunda representación distinta.

El frontend debe enviar el PlanItem canónico correspondiente a:

```text
weekly
interval_days
manual_dates
```

respetando:

```text
name
kind
activityType
generationConfig
GenerationSlot IDs
```

NO enviar:

```text
PlanItem.id generado por frontend
Occurrence IDs
occurrences
campos legacy
single_date
```

salvo que el contrato backend actual explícitamente requiera otra cosa.

---

# 8. GenerationSlot UUID

Preservar la política existente:

```text
frontend genera UUID v4 del GenerationSlot
backend valida
PostgreSQL persiste
GET lo devuelve intacto
```

No regenerar IDs durante POST ni después de hydration.

Casos:

```text
weekly multi-slot
interval multi-slot
manual_dates entries
```

deben preservar exactamente sus UUID.

---

# 9. Modo "Una fecha"

La UI puede seguir diciendo:

```text
Una fecha
```

pero el payload persistido debe ser:

```text
manual_dates
```

con exactamente una entry.

NO reintroducir:

```text
single_date
```

---

# 10. Formulario

Preservar el formulario y UX actuales.

El usuario debe poder seguir creando:

```text
weekly
interval_days
manual_dates
multi-slot
```

No rediseñar el formulario.

No cambiar reglas aprobadas de:

```text
overlap
intervalos contiguos
fechas
horarios
UUID
```

---

# 11. Estado submitting

Durante POST:

```text
deshabilitar submit
evitar doble submit
indicar guardando de forma pequeña
```

No permitir dos POST simultáneos causados por doble click.

Al finalizar correctamente:

```text
habilitar controles
```

---

# 12. Éxito

Una creación solo se considera completamente sincronizada cuando:

```text
POST success
+
GET planner-state success
+
hydrate success
```

Entonces:

```text
cerrar/resetear formulario
mostrar nuevo estado
```

según el comportamiento visual actual.

---

# 13. POST success + refresh failure

Este caso es crítico.

Ejemplo:

```text
POST → 201
PostgreSQL guardó el PlanItem
GET planner-state → network failure
```

NO volver a ejecutar automáticamente:

```text
POST
```

porque podría duplicar la creación.

Mostrar un estado controlado equivalente a:

```text
El registro se guardó, pero no se pudo actualizar la vista.
```

La recuperación debe intentar:

```text
GET /api/planner-state
```

NO volver a crear el PlanItem.

---

# 14. Retry semantics

Distinguir:

## POST no confirmado / POST falló antes de éxito

Puede permitirse al usuario volver a enviar manualmente.

## POST confirmado, refresh GET falló

Retry debe ser:

```text
GET planner-state
```

NO:

```text
POST otra vez
```

Evitar duplicación accidental.

---

# 15. Error 400

Errores de validación/backend como:

```text
invalid_payload
```

deben mostrarse de forma controlada.

No borrar innecesariamente los datos que el usuario escribió.

No mostrar:

```text
JSON crudo
stack traces
SQL
```

---

# 16. Error 409

Preservar los contratos actuales.

Incluyendo cuando corresponda:

```text
priority_override_required
domain conflict
planning_stopped
```

NO tratar todos los 409 como el mismo problema.

---

# 17. Priority override handshake — contrato aprobado

MVP 05.7.2 aprueba explícitamente el siguiente contrato para confirmar
priority overrides durante:

```http
POST /api/plan-items
```

No se crea un endpoint adicional.

La segunda operación utiliza el mismo endpoint y el mismo payload canónico
del PlanItem, añadiendo únicamente metadata de control opcional:

```json
{
  "name": "...",
  "kind": "activity",
  "activityType": "...",
  "generationConfig": {
    "...": "..."
  },
  "priorityOverride": {
    "confirmedOccurrenceIds": [
      "UUID",
      "UUID"
    ]
  }
}
```

`priorityOverride`:

```text
NO forma parte del PlanItem persistido
NO forma parte de generationConfig
NO se devuelve como propiedad del PlanItem
```

Es metadata de comando para esta request.

---

## Primera request

El frontend envía el POST sin:

```text
priorityOverride
```

Si no existen conflictos:

```text
crear normalmente
```

Si existen occurrences de menor prioridad que pueden ser desplazadas:

```http
409 priority_override_required
```

La respuesta debe identificar como mínimo las occurrences cuya sustitución
requiere autorización explícita.

Reutilizar el contrato de error existente siempre que sea posible.

Si actualmente la respuesta no contiene los IDs necesarios, extenderla
mínimamente con información equivalente a:

```json
{
  "error": "priority_override_required",
  "conflicts": [
    {
      "occurrenceId": "UUID",
      "planItemId": "UUID",
      "date": "YYYY-MM-DD",
      "startTime": "HH:MM",
      "endTime": "HH:MM",
      "status": "pending"
    }
  ]
}
```

No enviar información sensible ni detalles internos.

---

## Confirmación del usuario

La UI debe mostrar explícitamente que la creación desplazará registros.

Reutilizar la UX local existente de priority override si ya existe.

No ejecutar override silenciosamente.

Cuando el usuario confirma, repetir:

```http
POST /api/plan-items
```

con exactamente el mismo PlanItem lógico y:

```json
"priorityOverride": {
  "confirmedOccurrenceIds": ["..."]
}
```

Los IDs deben ser:

```text
UUID válidos
sin duplicados
```

---

## Regla de concurrencia / TOCTOU

En la segunda request el backend NO debe confiar ciegamente en los IDs
recibidos.

Dentro de la transacción normal:

```text
bloquear
recalcular conflictos actuales
comparar contra autorización
```

Sea:

```text
C = occurrences actualmente desplazables
A = occurrences confirmadas por el usuario
```

La operación puede continuar solamente si:

```text
C ⊆ A
```

Es decir:

```text
todo conflicto que se vaya a desplazar
debe haber sido confirmado por el usuario
```

Si aparece cualquier conflicto nuevo:

```text
C contiene occurrence no incluida en A
```

responder nuevamente:

```http
409 priority_override_required
```

con el conjunto actual.

No realizar cambios parciales.

El frontend debe solicitar una nueva confirmación.

---

## Conflictos desaparecidos

Si una occurrence previamente confirmada ya no entra en conflicto:

```text
no es necesario bloquear la operación solo por eso
```

Puede ignorarse como autorización sobrante.

Lo importante es:

```text
ninguna occurrence ACTUAL sea desplazada sin autorización
```

---

## Conflictos no desplazables

Las reglas existentes permanecen intactas.

Por ejemplo una occurrence:

```text
completed
```

o cualquier conflicto que la política actual no permita desplazar:

```text
NO se vuelve desplazable por incluir su UUID en priorityOverride
```

La autorización del cliente nunca puede saltarse reglas de dominio.

---

## Semántica del override

Al proceder con una creación autorizada se conservan las reglas actuales:

```text
pending
→ cancelled

in_progress
→ not_finished
```

y:

```js
statusContext = {
  reason: "priority_override",
  sourceOccurrenceId: "<new occurrence id>"
}
```

El backend continúa determinando qué nueva occurrence causa cada override.

El cliente NO envía:

```text
sourceOccurrenceId
statusContext
nuevo status de la occurrence desplazada
```

---

## Atomicidad

La creación confirmada continúa siendo:

```text
una conexión
una transacción
SERIALIZABLE
todo o nada
```

No persistir primero el nuevo PlanItem y después ejecutar overrides en una
segunda transacción.

---

## Validación

`priorityOverride` es opcional.

Si existe, aceptar únicamente:

```js
{
  confirmedOccurrenceIds: string[]
}
```

Rechazar:

```text
campos desconocidos
UUID inválidos
IDs duplicados
estructura inválida
```

con el contrato de error correspondiente.

No persistir esta metadata.

---

## Frontend flow

Flujo completo:

```text
POST normal
    ↓
409 priority_override_required
    ↓
UI muestra conflicts
    ↓
usuario confirma
    ↓
POST mismo PlanItem
+ confirmedOccurrenceIds
    ↓
backend recalcula
    ↓
success
    ↓
GET /api/planner-state
    ↓
hydrate
```

Si el usuario cancela:

```text
no realizar ninguna segunda request
```

---

## Nueva concurrencia durante confirmación

Caso obligatorio:

```text
primer 409:
A, B requieren override

usuario confirma A, B

antes del segundo POST aparece C

segundo POST:
current conflicts = A, B, C
confirmed = A, B
```

Resultado obligatorio:

```http
409 priority_override_required
```

No desplazar C silenciosamente.

---

## Tests obligatorios

Cubrir:

```text
POST sin conflicto
409 inicial
confirmación válida
usuario cancela
confirmedOccurrenceIds inválidos
IDs duplicados
conflicto nuevo entre requests
conflicto desaparecido entre requests
completed sigue protegido
pending → cancelled
in_progress → not_finished
statusContext.sourceOccurrenceId correcto
rollback
concurrencia
POST confirmado + GET hydration
```

No crear migration 004.

No cambiar schema.

# 18. Completed conflicts

No permitir que la integración frontend ignore protecciones contra
occurrences:

```text
completed
```

Preservar el comportamiento backend existente.

---

# 19. Atomicidad

La creación ya es atómica en backend.

Frontend NO debe intentar persistir por separado:

```text
PlanItem
config
slots
occurrences
```

Solo:

```text
POST /api/plan-items
```

Backend se encarga de la transacción.

---

# 20. Server IDs autoritativos

Después del POST + refresh:

```text
PlanItem.id
Occurrence.id
GenerationSlot.id
sourceGenerationSlotId
```

deben provenir del estado retornado por el servidor.

No fabricar IDs de:

```text
PlanItem
Occurrence
```

en frontend.

GenerationSlot IDs sí siguen la política frontend UUID v4 previa al POST.

---

# 21. No rematerialización

Después de crear:

```text
GET planner-state
→ hydrate
```

NO volver a materializar localmente las occurrences retornadas.

Ejemplo:

Backend devuelve:

```text
PlanItem P
Occurrence O1
Occurrence O2
```

Store:

```text
P
O1
O2
```

No:

```text
P
O1
O2
O3 duplicada
O4 duplicada
```

---

# 22. Estado local previo

La hydration posterior al POST debe reemplazar el estado completo
persistido de forma atómica.

No mezclar:

```text
server state nuevo
+
state local viejo
```

---

# 23. Mutaciones todavía locales

Single Day, Delete, Apply Week y Apply Future todavía NO persisten mediante
HTTP.

Por ello el mensaje general de UX ya no debe afirmar simplemente:

```text
todos los cambios son temporales
```

si eso deja de ser cierto.

Actualizar el mensaje de forma mínima y precisa.

Ejemplo conceptual:

```text
Los nuevos registros se guardan.
Las ediciones del calendario todavía son temporales.
```

No hacer rediseño visual.

---

# 24. Reload acceptance

Caso principal:

```text
abrir app
→ crear PlanItem
→ aparece
→ F5
→ sigue apareciendo
```

Este es un criterio obligatorio de aceptación.

---

# 25. Weekly acceptance

Desde UI real crear un PlanItem weekly multi-slot.

Ejemplo:

```text
Prueba UI weekly

Lunes
08:00–09:00

Lunes
18:00–19:00
```

Verificar:

```text
POST exitoso
GenerationSlot UUIDs preservados
occurrences persistidas
GET refleja el PlanItem
reload lo conserva
```

---

# 26. Interval acceptance

Crear desde UI:

```text
interval_days
intervalDays > 1
múltiples slots
```

Verificar:

```text
fase correcta
slots correctos
occurrences correctas
reload persistente
```

---

# 27. Manual acceptance

Crear desde UI:

```text
manual_dates
```

incluyendo:

```text
Una fecha
```

y, si la UI actual lo soporta:

```text
múltiples entries
```

Verificar round-trip exacto.

---

# 28. Multi-slot

Crear desde UI un PlanItem con múltiples slots aplicables en la misma
fecha.

Debe producir:

```text
múltiples occurrences
mismo PlanItem
misma fecha
slots distintos
```

No introducir limitación:

```text
1 PlanItem + fecha = 1 occurrence
```

---

# 29. Empty DB

Con DB temporal vacía:

```text
bootstrap → vacío
crear desde UI/API integration
→ aparece el primer PlanItem
```

No depender de seed/mocks.

---

# 30. CORS

05.7.1 permitió únicamente GET.

Para POST desde origen separado con:

```text
Content-Type: application/json
```

el navegador probablemente realizará:

```text
OPTIONS preflight
```

Extender CORS únicamente lo necesario para:

```text
OPTIONS /api/plan-items
POST /api/plan-items
```

manteniendo:

```text
allow-list VCS_ALLOWED_ORIGINS
```

NO:

```text
Access-Control-Allow-Origin: *
```

No añadir dependencia externa si no es necesaria.

---

# 31. Métodos CORS

Permitir únicamente lo requerido actualmente:

```text
GET planner-state
POST plan-items
OPTIONS necesario
```

No habilitar preventivamente:

```text
PATCH
DELETE
apply-week
apply-future
```

si todavía no se usan.

---

# 32. API base URL

Reutilizar exactamente la infraestructura de 05.7.1.

No crear otra fuente de configuración.

Debe seguir funcionando:

```text
same-origin default
```

y override explícito de desarrollo.

---

# 33. Loading global vs saving

No bloquear toda la aplicación innecesariamente durante POST si no hace
falta.

Puede existir estado de:

```text
guardando
```

asociado al formulario/mutation.

Durante el GET de resync posterior, mantener una UX coherente.

No generar flash de mocks/estado vacío.

---

# 34. Form data on failure

Si POST falla:

```text
preservar formulario
```

siempre que sea razonable.

El usuario no debe volver a escribir todo por un error de red.

---

# 35. Double submit

Caso obligatorio:

```text
click submit
click submit inmediatamente
```

Debe resultar en:

```text
1 POST
```

no dos PlanItems duplicados.

---

# 36. Network failure

Si Flask está caído durante POST:

```text
mostrar error controlado
mantener formulario
store persistido intacto
```

No crash.

No mocks.

---

# 37. Invalid server response

Si POST responde success HTTP pero JSON/contrato inesperado:

```text
no asumir persistencia local correcta
```

Dado que el servidor pudo haber escrito antes de fallar la interpretación,
la recuperación segura debe priorizar:

```text
GET planner-state
```

antes de permitir repost automático.

---

# 38. Backend READY

No modificar semántica de:

```text
POST /api/plan-items
GET /api/planner-state
```

para facilitar un frontend incorrecto.

Si se descubre un bug real:

```text
corregir solo si inequívoco
añadir regresión
reportar
```

---

# 39. No domain redesign

No modificar:

```text
materializer semantics
GenerationSlot model
idempotency
temporal policy
Apply Week
Apply Future
Single Day
priority rules
```

salvo defecto inequívoco descubierto durante integración.

---

# 40. Tests frontend

Añadir pruebas útiles para:

```text
successful create + refresh
weekly
interval
manual
multi-slot
server IDs preserved
double submit
network failure
400
409
priority override flow
POST success + GET failure
retry GET without duplicate POST
no rematerialization
reload/bootstrap compatibility
```

No perseguir cantidad de tests.

---

# 41. Integration tests

Usar PostgreSQL 16 aislado/efímero para demostrar al menos:

```text
empty DB
→ POST
→ GET
→ estado persistido exacto
```

y round-trip representativo multi-slot.

---

# 42. Browser verification

Realizar fetch real:

```text
static frontend
→ Flask
→ PostgreSQL temporal
```

si el entorno lo permite.

Verificar al menos:

```text
weekly o multi-slot
loading/saving
success
F5/reload
error de red cuando sea viable
desktop
mobile
```

No inventar resultados si alguna parte no puede automatizarse.

---

# 43. Existing bootstrap regression

05.7.1 debe permanecer funcionando:

```text
loading
persisted state
empty state
error
retry
no mocks
atomic hydration
```

---

# 44. Security

NO introducir:

```text
DB credentials
DATABASE_URL frontend
passwords
secrets
```

Frontend conoce solo HTTP API.

No leer/modificar `.env` real.

`.env.example` puede actualizarse si CORS necesita documentar algo nuevo.

---

# 45. PostgreSQL

NO modificar:

```text
001
002
003
```

NO crear migration 004.

NO modificar schema.

---

# 46. vcs_dev

Codex NO modifica:

```text
vcs_dev
```

Automatización:

```text
PostgreSQL 16 aislado/efímero
```

Después el usuario realizará la prueba manual final en `vcs_dev`.

---

# 47. Regression suite

Ejecutar:

```text
frontend completo
backend relevante
PostgreSQL integration relevante
JS/Python parity
node --check
compileall si backend cambia
git diff --check
```

---

# 48. Definition of done

MVP 05.7.2 queda completo cuando pueda demostrarse:

```text
UI
↓
crear PlanItem
↓
POST /api/plan-items
↓
PostgreSQL
↓
GET /api/planner-state
↓
hydrate
↓
UI
↓
F5
↓
PlanItem sigue ahí
```

para:

```text
weekly
interval_days
manual_dates
multi-slot
```

sin duplicaciones ni rematerialización accidental.

---

# 49. Fuera de alcance reiterado

NO conectar:

```text
PATCH occurrence
DELETE occurrence
Apply Week HTTP
Apply Future HTTP
```

NO implementar:

```text
optimistic mutations
offline
auth
multiuser
deployment
notifications
analytics
```

---

# 50. Git

Codex NO debe:

```text
commit
push
merge
cambiar rama
```

El usuario controla Git.

---

# 51. Reporte requerido

Al finalizar reportar:

1. archivos creados/modificados;
2. flujo exacto de creación;
3. cambios en planner-api;
4. estrategia POST → GET → hydrate;
5. CORS POST/OPTIONS;
6. estado submitting;
7. protección double-submit;
8. comportamiento success;
9. comportamiento POST failure;
10. comportamiento POST success + GET failure;
11. retry semantics;
12. error 400;
13. error 409;
14. priority override flow;
15. preservación del formulario en error;
16. UUID GenerationSlot;
17. IDs autoritativos del servidor;
18. no rematerialización;
19. UX del mensaje de cambios temporales;
20. weekly acceptance;
21. interval acceptance;
22. manual acceptance;
23. multi-slot acceptance;
24. empty DB create;
25. reload/F5 persistence;
26. browser verification;
27. frontend tests;
28. backend tests relevantes;
29. PostgreSQL integration;
30. parity/checks;
31. bugs descubiertos;
32. riesgos/limitaciones.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
001/002/003 no fueron modificadas
no se creó migration 004
PATCH/DELETE no fueron conectados
Apply Week/Apply Future no fueron conectados
no se añadieron secretos
no se implementaron features fuera de alcance
no se hizo commit/push/merge
```
