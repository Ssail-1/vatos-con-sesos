# CURRENT TASK

## MVP 05.7.4 — Persistent Apply Week / Apply Future

### Propósito

Conectar las mutaciones de alcance recurrente que ya existen en backend:

```text
Apply Week
Apply Future
```

con la UI real.

Después de esta fase:

```text
usuario edita planificación
→ elige Apply Week o Apply Future
→ POST backend correspondiente
→ PostgreSQL
→ GET /api/planner-state
→ hydratePlannerState()
→ render
→ F5
→ cambio permanece
```

Estado:

```text
05.7.1    Bootstrap persistente                       ✅
05.7.2    Crear PlanItem persistente                  ✅
05.7.2.1  Rendering occurrence-aware                  ✅
05.7.3    Single Day persistente                      ✅
05.7.3.1  Monthly aggregate occurrence status         ✅
05.7.4    Apply Week / Apply Future persistentes      ← ACTUAL
05.7.5    Mutation conflict resolution UX             → después
05.7.6    Verificación local final                    → después
```

---

# 1. Alcance

Conectar exclusivamente:

```http
POST /api/plan-items/<plan_item_id>/apply-week
```

y:

```http
POST /api/plan-items/<plan_item_id>/apply-future
```

Reutilizar los contratos backend ya implementados y probados en MVP 05.6.4.2
y 05.6.4.3.

NO rediseñar su semántica.

---

# 2. Regla arquitectónica principal

Después de cualquier mutación exitosa:

```text
POST Apply Week / Apply Future
        ↓
GET /api/planner-state
        ↓
hydratePlannerState()
        ↓
render
```

PostgreSQL/backend continúa siendo la fuente autoritativa.

NO mantener manualmente dos versiones persistentes del planner.

---

# 3. No optimistic persistence

No aplicar al store persistido el resultado definitivo antes de que backend
confirme.

Flujo:

```text
usuario confirma
→ saving
→ POST
→ GET
→ hydrate
→ render
```

Si POST falla:

```text
store anterior permanece
```

---

# 4. Inspeccionar contratos reales

Antes de modificar frontend, inspeccionar los contratos backend actuales de:

```text
/apply-week
/apply-future
```

Usar exactamente:

```text
payload
response shape
error codes
restricciones
```

existentes.

NO inventar campos.

NO reimplementar reglas backend en frontend.

---

# 5. Planner API

Extender:

```text
js/api/planner-api.js
```

o capa equivalente con operaciones conceptuales:

```js
applyWeek(planItemId, payload)
applyFuture(planItemId, payload)
```

Responsabilidad:

```text
HTTP
JSON
network errors
status codes
```

NO:

```text
materialization
domain mutation
render
direct store mutation
```

---

# 6. Mutation coordinator

Preferir reutilizar/generalizar la arquitectura ya usada por:

```text
PlanItem creation
Single Day mutation
```

Debe manejar:

```text
una mutación activa
double-submit
mutation confirmed vs refresh pending
safe GET retry
```

No convertir `app.js` en un monolito.

---

# 7. Apply Week — semántica

Apply Week modifica únicamente el alcance semanal aprobado por backend.

Debe preservar la semántica existente:

```text
week-scoped scheduling overrides
```

No convertir Apply Week en:

```text
Apply Future
```

ni modificar GenerationSlots globales cuando el contrato no lo indica.

---

# 8. Apply Week — identidad

Las occurrences existentes deben conservar identidad según las reglas backend.

Frontend NO debe:

```text
generar Occurrence IDs
rematerializar
recrear semana manualmente
```

Backend decide la mutación persistente.

---

# 9. Apply Week — multi-slot

Caso obligatorio:

```text
PlanItem Uber

08:00–11:00
14:00–17:00
20:00–22:00
```

Modificar una semana concreta.

Verificar:

```text
esa semana cambia
otras semanas permanecen
GenerationSlots base permanecen según contrato
F5 conserva el cambio
```

---

# 10. Apply Week — swaps / horarios

Preservar la capacidad backend existente para validar el estado FINAL de la
semana.

No rechazar en frontend una operación únicamente porque durante un paso
intermedio dos intervals se cruzarían si el estado final aprobado es válido.

Backend continúa siendo autoridad.

---

# 11. Apply Future — modos soportados

Apply Future soporta únicamente los modos aprobados por backend.

Según contrato actual:

```text
weekly
interval_days
```

NO inventar soporte para:

```text
manual_dates
```

Si manual_dates intenta usar Apply Future:

```text
UI debe impedirlo o mostrar error backend controlado
```

según el diseño existente.

---

# 12. Apply Future — no mode change

Preservar la restricción backend existente:

```text
no cambiar mode
```

Apply Future NO convierte:

```text
weekly → interval_days
interval_days → weekly
```

salvo que un contrato backend futuro lo permita.

No ampliar esta fase.

---

# 13. Effective boundary

Apply Future usa una frontera efectiva:

```text
futureConfig.startDate
```

Frontend debe enviar exactamente la fecha efectiva aprobada por el flujo
actual.

Todo lo anterior a esa frontera debe permanecer histórico/inmutable según las
reglas backend.

---

# 14. Historical preservation

Caso obligatorio:

```text
occurrences anteriores a future start
```

deben permanecer sin cambios.

Frontend NO debe sustituir horarios históricos con los GenerationSlots nuevos.

---

# 15. Future generation

Después de Apply Future:

```text
nuevo motor recurrente
→ nuevas occurrences futuras
```

según backend.

Frontend NO ejecuta materialization local después del GET.

---

# 16. Explicit overrides

Preservar semántica backend existente para:

```text
explicit occurrence overrides
```

Apply Future NO debe destruir por accidente una occurrence previamente
modificada cuando backend ya la protege.

---

# 17. Ad-hoc occurrences

Occurrences con:

```text
sourceGenerationSlotId = null
```

deben preservarse según la política backend existente.

Frontend no debe filtrarlas ni reconstruirlas.

---

# 18. Exclusions

Preservar:

```text
global exclusions
slot exclusions
```

según backend.

No reconstruir exclusions en frontend.

---

# 19. UUID de GenerationSlots

Frontend continúa siendo responsable de UUID v4 para slots nuevos cuando el
flujo existente así lo requiera.

Backend debe preservar esos UUID exactamente.

No remapear IDs.

Un slot lógico editado debe conservar UUID cuando corresponda.

Delete + recreate implica UUID nuevo según política existente.

---

# 20. Apply Future multi-slot

Caso obligatorio:

```text
S1 08:00–11:00
S2 14:00–17:00
S3 20:00–22:00
```

Cambiar futuro a:

```text
S1 09:00–12:00
S3 20:00–21:00
```

y eliminar S2.

Verificar:

```text
historia anterior intacta
futuro refleja motor nuevo
S1 conserva UUID si fue editado
S2 desaparece del motor futuro
S3 conserva UUID
F5 mantiene resultado
```

siempre conforme al contrato real actual.

---

# 21. Selected date

Después de:

```text
POST
→ GET
→ hydrate
```

mantener:

```text
selectedDate
```

cuando siga siendo válida.

No saltar automáticamente al currentDay.

---

# 22. Rendering

Después de hydration, dejar que:

```text
buildPlannerRows
aggregate occurrence display
```

se recalculen naturalmente.

No parchear DOM manualmente.

05.7.2.1 y 05.7.3.1 siguen siendo responsables de visualización derivada.

---

# 23. Monthly aggregate regression

Después de Apply Week/Future:

```text
□³
✓³
◐³
!³
```

deben representar el nuevo estado hidratado sin lógica especial.

No almacenar aggregate badges.

---

# 24. Double-submit

Dos clicks rápidos en:

```text
Apply Week
```

→ un solo POST.

Dos clicks rápidos en:

```text
Apply Future
```

→ un solo POST.

Añadir pruebas.

---

# 25. POST success + GET failure

Caso crítico:

```text
POST Apply Week/Future → success
GET planner-state → failure
```

La mutación YA pudo haberse persistido.

NO repetir automáticamente POST.

Recovery:

```text
GET /api/planner-state
```

únicamente.

---

# 26. Retry

Distinguir:

```text
POST no confirmado
```

de:

```text
POST confirmado + refresh falló
```

En el segundo caso:

```text
retry = GET solamente
```

Nunca duplicar Apply Week/Future.

---

# 27. Invalid success response

Si backend responde HTTP success pero el cliente no puede interpretar la
respuesta:

tratar la mutación como potencialmente confirmada.

Priorizar:

```text
GET planner-state
```

antes de permitir reenviar el POST.

---

# 28. 400

Manejar:

```text
invalid_payload
```

y demás validaciones existentes de forma controlada.

No borrar el formulario.

No mostrar internals.

---

# 29. 404

Manejar:

```text
plan_item_not_found
```

o código real equivalente.

Puede ser estado desactualizado/concurrencia.

Permitir refresh seguro.

---

# 30. 409

Inspeccionar códigos reales de ambos endpoints.

Manejar diferenciadamente cuando existan:

```text
history_frozen
planning_stopped
priority_override_required
priority_conflict
completed_conflict
slot_date_conflict
status_context_locked
concurrent_conflict
concurrent_modification
unsupported_mode
```

No inventar nombres si backend usa otros.

---

# 31. Conflict confirmation

NO implementar el sistema futuro general del ROADMAP.

Si Apply Week/Future ya poseen un contrato backend inequívoco para confirmar
priority override:

```text
puede conectarse exactamente
```

Si únicamente detectan conflictos pero no existe handshake completo:

```text
mostrar conflicto
mantener editor
NO inventar autorización
```

Reportar la limitación.

---

# 32. User-authorized displacement

NO implementar todavía:

```text
igual/menor prioridad desplazando otra occurrence
por decisión explícita del usuario
```

Eso pertenece a 05.7.5.

---

# 33. Multiple displacement sources

NO modificar schema/statusContext para soportar múltiples sources en esta
fase.

Eso permanece en ROADMAP.

---

# 34. Status persistence

NO conectar persistencia de status.

05.7.3 confirmó que no existe todavía contrato aprobado.

Los cambios de status siguen con la semántica temporal actual.

No ampliar PATCH.

---

# 35. Apply Week UX

Reutilizar el flujo existente de edición.

Cuando usuario seleccione:

```text
Aplicar semana
```

mostrar saving state equivalente a:

```text
Guardando…
```

Deshabilitar controles necesarios durante la mutación.

Cerrar/limpiar únicamente después de:

```text
POST
+
GET
+
hydrate
```

exitosos.

---

# 36. Apply Future UX

Misma política:

```text
Guardar
→ POST
→ GET
→ hydrate
→ cerrar
```

No cerrar inmediatamente tras POST si todavía no se pudo resincronizar.

---

# 37. Refresh pending UX

Si POST fue confirmado pero GET falló:

mostrar mensaje equivalente a:

```text
El cambio se guardó, pero no se pudo actualizar la vista.
```

Botón retry:

```text
GET only
```

---

# 38. CORS

Extender allow-list únicamente para:

```text
POST /api/plan-items/<id>/apply-week
POST /api/plan-items/<id>/apply-future
OPTIONS correspondientes
```

Mantener:

```text
VCS_ALLOWED_ORIGINS
```

NO usar:

```text
Access-Control-Allow-Origin: *
```

---

# 39. No nuevas rutas

NO crear nuevos endpoints.

Los endpoints ya existen.

Si un contrato resulta insuficiente:

```text
DETENERSE Y REPORTAR
```

antes de inventar una ruta nueva.

---

# 40. Apply Week acceptance

Caso mínimo obligatorio con PostgreSQL real efímero:

```text
weekly/multi-slot PlanItem
```

1. observar semana A;
2. Apply Week sobre semana A;
3. GET + hydrate;
4. verificar semana A modificada;
5. verificar semana B no modificada;
6. F5;
7. resultado permanece.

---

# 41. Apply Future weekly acceptance

Caso:

```text
weekly
```

con:

```text
historia previa
future boundary
multi-slot
```

Verificar:

```text
antes de boundary intacto
después de boundary nuevo schedule
F5 persiste
```

---

# 42. Apply Future interval acceptance

Caso:

```text
interval_days
intervalDays > 1
```

Verificar:

```text
fase correcta
boundary correcta
slots correctos
historia previa intacta
F5
```

---

# 43. Apply Future manual rejection

Caso:

```text
manual_dates
```

No debe ejecutar exitosamente Apply Future.

Verificar UX/error controlado.

---

# 44. Overrides/ad-hoc acceptance

Cuando sea viable:

crear fixture con:

```text
explicit occurrence override
ad-hoc occurrence
```

antes del boundary.

Apply Future.

Verificar que sobreviven conforme a contrato backend existente.

---

# 45. No rematerialization

Después de:

```text
POST
GET
hydrate
```

NO ejecutar materializer frontend.

Los IDs retornados por backend son autoritativos.

---

# 46. Browser acceptance

Usar aplicación real:

```text
index.html
→ app.js
→ Flask
→ PostgreSQL 16 efímero
```

NO depender únicamente de harness.

Verificar:

```text
Apply Week
F5

Apply Future weekly
F5

Apply Future interval
F5
```

Desktop y mobile cuando el flujo sea accesible.

---

# 47. PostgreSQL

Automatización:

```text
PostgreSQL 16 aislado/efímero
```

NO usar:

```text
vcs_dev
```

---

# 48. Migrations

NO modificar:

```text
001
002
003
```

NO crear:

```text
004
```

No cambiar schema.

---

# 49. Backend

Los servicios de Apply Week/Future ya fueron verificados en 05.6.x.

No rediseñar backend.

Si frontend integration descubre un bug inequívoco:

```text
corregir mínimo
añadir regresión
reportar
```

No ampliar semántica.

---

# 50. Regression — create

05.7.2 debe seguir funcionando:

```text
POST PlanItem
GET
hydrate
F5
```

---

# 51. Regression — Single Day

05.7.3 debe seguir funcionando:

```text
PATCH occurrence
DELETE occurrence
GET
hydrate
F5
```

---

# 52. Regression — rendering

Mantener:

```text
selected day
→ occurrence rows

non-selected multi-occurrence
→ aggregate status badge
```

---

# 53. Tests frontend

Añadir pruebas útiles para:

```text
Apply Week POST → GET → hydrate
Apply Future POST → GET → hydrate

double Apply Week
double Apply Future

POST success + GET failure
retry GET only

network failure
400
404
409

selectedDate preserved

manual Apply Future rejected

weekly future
interval future

multi-slot
```

No perseguir cantidad.

---

# 54. Backend/PostgreSQL tests

Reutilizar cobertura existente cuando ya pruebe correctamente:

```text
Apply Week
Apply Future
SERIALIZABLE
rollback
concurrency
historical preservation
overrides
ad-hoc
exclusions
```

Añadir solo regresiones necesarias por bugs reales encontrados durante
integración.

---

# 55. Full regression

Ejecutar:

```text
frontend completo
backend relevante/completo según cambios
PostgreSQL integration
05.7.1 bootstrap
05.7.2 create
05.7.2.1 rendering
05.7.3 Single Day
05.7.3.1 aggregate status
JS/Python parity
node --check
compileall si backend cambia
git diff --check
```

---

# 56. Definition of done

MVP 05.7.4 queda completo cuando:

```text
Apply Week
→ POST
→ PostgreSQL
→ GET
→ hydrate
→ F5
```

y:

```text
Apply Future
→ POST
→ PostgreSQL
→ GET
→ hydrate
→ F5
```

funcionan desde la UI real para los modos soportados sin rematerialización
frontend ni cambios fuera de alcance.

---

# 57. Fuera de alcance

NO implementar:

```text
status persistence
multiple displacement sources
user-authorized displacement general
inline conflict editor
desplazar todas las compatibles
provenance cleanup
auth
multiuser
deployment
analytics
```

---

# 58. Git

Codex NO debe:

```text
commit
push
merge
cambiar rama
```

El usuario controla Git.

---

# 59. Reporte requerido

Al finalizar reportar:

1. archivos creados/modificados;
2. arquitectura/coordinador;
3. planner-api Apply Week;
4. planner-api Apply Future;
5. payload real de Apply Week;
6. payload real de Apply Future;
7. POST → GET → hydrate;
8. double-submit;
9. POST success + GET failure;
10. retry GET only;
11. CORS;
12. errores 400;
13. errores 404;
14. errores 409;
15. conflict confirmation disponible/no disponible;
16. Apply Week multi-slot;
17. Apply Week scope isolation;
18. Apply Future weekly;
19. Apply Future interval;
20. manual rejection;
21. effective boundary;
22. historical preservation;
23. explicit overrides;
24. ad-hoc;
25. exclusions;
26. GenerationSlot UUID preservation;
27. selectedDate;
28. rendering/aggregate regression;
29. F5 persistence;
30. browser desktop;
31. browser mobile;
32. frontend tests;
33. backend tests;
34. PostgreSQL integration;
35. parity/static checks;
36. bugs encontrados;
37. riesgos/limitaciones.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
001/002/003 no fueron modificadas
no se creó migration 004
no se añadieron nuevos endpoints
status persistence no fue implementada
ROADMAP future conflict system no fue implementado anticipadamente
no se añadieron secretos
no se hizo commit/push/merge
```
