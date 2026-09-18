# CURRENT TASK

## MVP 05.7.3 — Persistent Single Day occurrence mutations

### Propósito

Conectar las mutaciones de una occurrence concreta del planner real con los
endpoints persistentes ya existentes.

Después de esta fase, editar o eliminar una occurrence desde la UI debe
recorrer:

```text
Occurrence seleccionada
    ↓
UI
    ↓
PATCH /api/occurrences/<id>
o
DELETE /api/occurrences/<id>
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
05.7.1    Bootstrap persistente                       ✅
05.7.2    Crear PlanItem persistente                  ✅
05.7.2.1  Rendering occurrence-aware                  ✅
05.7.3    Single Day persistente                      ← ACTUAL
05.7.4    Apply Week / Apply Future persistentes      → después
05.7.5    Mutation conflict resolution UX             → después
05.7.6    Verificación local final                    → después
```

---

# 1. Alcance

Implementar exclusivamente desde frontend:

```text
editar UNA occurrence
eliminar UNA occurrence
```

mediante los endpoints persistentes actuales.

Reutilizar los contratos backend ya aprobados.

NO implementar todavía el sistema completo de:

```text
multiple displacement sources
user-authorized displacement general
conflict editor embebido
desplazar todas las compatibles
cleanup de provenance
```

Eso permanece en ROADMAP / 05.7.5.

---

# 2. Endpoints

Conectar:

```http
PATCH /api/occurrences/<occurrence_id>
```

y:

```http
DELETE /api/occurrences/<occurrence_id>
```

NO conectar todavía:

```text
Apply Week
Apply Future
```

---

# 3. Fuente de verdad

Después de cualquier mutación exitosa:

```text
PATCH/DELETE
    ↓
GET /api/planner-state
    ↓
hydratePlannerState()
```

PostgreSQL/backend continúa siendo la fuente autoritativa.

NO actualizar manualmente el store como verdad persistida final.

---

# 4. No optimistic persistence

No asumir éxito antes de que el backend confirme.

Flujo:

```text
usuario edita/elimina
→ saving
→ mutation HTTP
→ GET planner-state
→ hydrate
→ render
```

Si la mutation falla:

```text
store persistido anterior permanece
```

---

# 5. Occurrence identity

La UI occurrence-aware creada en 05.7.2.1 debe permitir identificar
inequívocamente:

```text
Occurrence.id
```

de la fila seleccionada.

Editar:

```text
Uber 08:00
```

NO debe afectar:

```text
Uber 14:00
Uber 20:00
```

aunque pertenezcan al mismo PlanItem.

---

# 6. API client

Extender:

```text
js/api/planner-api.js
```

o la capa equivalente actual con operaciones conceptuales:

```js
updateOccurrence(occurrenceId, payload)
deleteOccurrence(occurrenceId)
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
materialization
store mutation directa
```

---

# 7. No fetch disperso

NO colocar `fetch()` directamente en:

```text
views
planner-store
matrix rendering
```

Mantener la separación creada en 05.7.1/05.7.2.

---

# 8. PATCH contract

Antes de implementar, inspeccionar el contrato backend real de:

```http
PATCH /api/occurrences/<id>
```

Usar exactamente el payload aprobado.

Esperado conceptualmente:

```json
{
  "date": "YYYY-MM-DD",
  "startTime": "HH:MM",
  "endTime": "HH:MM"
}
```

NO inventar campos adicionales sin respaldo del backend existente.

---

# 9. Editar misma fecha

Caso recurrente:

```text
S1 baseline
08:00–09:00

Occurrence concreta
08:00–09:00
```

Usuario cambia solo esa aparición a:

```text
08:30–09:30
```

Esperar:

```text
Occurrence.id preservado
Occurrence cambia horario
GenerationSlot NO cambia
otras fechas NO cambian
```

---

# 10. Editar y mover de fecha

Si el contrato/backend actual permite:

```text
22 Sep
08:00–09:00
```

→

```text
23 Sep
10:00–11:00
```

debe conservarse la semántica existente:

```text
slot exclusion en fecha original
Occurrence movida
sourceGenerationSlotId preservado cuando corresponda
```

No reimplementar esta lógica en frontend.

---

# 11. Manual dates

Editar una occurrence proveniente de:

```text
manual_dates
```

debe usar el endpoint existente y preservar la sincronización correcta entre:

```text
manual entry
slot
occurrence
```

según el backend ya aprobado.

Frontend no debe conocer ni reproducir esa lógica interna.

---

# 12. Ad-hoc

Una occurrence con:

```text
sourceGenerationSlotId = null
```

debe poder editarse mediante el mismo flujo.

No exigir source slot para habilitar el editor.

---

# 13. DELETE recurrente

Eliminar una occurrence recurrente mediante:

```http
DELETE /api/occurrences/<id>
```

debe conservar la semántica backend actual:

```text
crear slot exclusion
eliminar occurrence concreta
mantener GenerationSlot
```

Después de:

```text
GET + hydrate
```

la occurrence no debe reaparecer.

---

# 14. DELETE manual

Para una occurrence `manual_dates`:

```text
delete occurrence
delete entry/slot correspondiente
```

según contrato actual.

Caso última entry:

```text
409 last_manual_entry
```

debe mostrarse de forma controlada.

No borrar el PlanItem automáticamente.

---

# 15. DELETE ad-hoc

Una occurrence ad-hoc:

```text
sourceGenerationSlotId = null
```

debe eliminar únicamente esa occurrence.

---

# 16. Status preservation

Las mutaciones de scheduling de esta fase NO deben cambiar arbitrariamente:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

Preservar el status existente salvo que el contrato backend aprobado
especifique una transición obligatoria.

---

# 17. Status mutation NO se inventa

Antes de conectar persistencia de cambios de status, inspeccionar si existe
un endpoint/contrato backend explícito para ello.

Si NO existe:

```text
NO inventar endpoint
NO ampliar PATCH silenciosamente
```

Mantener temporalmente el comportamiento local existente y REPORTAR que la
persistencia de status requiere una fase/contrato separado.

Si SÍ existe un contrato ya aprobado y cubierto por backend actual:

```text
puede conectarse únicamente si forma claramente parte de Single Day
```

y debe reportarse.

---

# 18. Cancelled / not_completed y ocupación temporal

Preservar las reglas backend ya existentes.

Especialmente:

```text
cancelled
not_completed
```

no deben convertirse accidentalmente en blockers temporales si la política
actual ya los considera no ocupantes.

No rediseñar la política en esta fase.

Las ampliaciones sobre provenance múltiple están en ROADMAP.

---

# 19. Conflict handling

Si PATCH provoca un conflicto:

```text
mostrar el error/control actual de forma comprensible
```

No ignorar el conflicto.

No ejecutar desplazamientos silenciosos.

---

# 20. Priority override existente

Inspeccionar el contrato backend real de PATCH.

Si ya existe un mecanismo completo y explícito para confirmar un
`priority_override_required`:

```text
conectarlo respetando exactamente ese contrato
```

Si el backend solo puede DETECTAR el conflicto pero NO existe una operación
inequívoca para confirmarlo:

```text
NO inventar un mecanismo nuevo
```

En ese caso:

```text
mostrar el conflicto
mantener formulario/editor
reportar la limitación
```

y continuar el resto de 05.7.3 si es posible.

La UX avanzada de resolución queda para 05.7.5.

---

# 21. User-authorized displacement futuro

NO implementar todavía la regla futura que permitirá:

```text
una occurrence de igual o menor prioridad
desplazar otra
por decisión explícita del usuario
```

Eso está documentado en ROADMAP.

No modificar ahora las reglas de prioridad para anticiparlo.

---

# 22. Conflict details

Si el backend actual devuelve información estructurada sobre conflicts:

```text
nombre/PlanItem
occurrenceId
date
startTime
endTime
status
```

puede mostrarse de manera mínima.

No construir todavía el diálogo avanzado:

```text
Ajustar
Desplazar
Desplazar todas
```

Eso pertenece a 05.7.5.

---

# 23. Mutation coordinator

Preferir una capa/coordinador equivalente a la creada para PlanItem create.

Responsabilidades:

```text
una mutation activa por acción
distinguir mutation vs refresh
evitar doble submit
resync seguro
```

No convertir `app.js` en un archivo monolítico.

---

# 24. Double submit

Editar:

```text
Guardar
Guardar
```

rápidamente debe producir:

```text
1 PATCH
```

Eliminar:

```text
Eliminar
Eliminar
```

debe producir:

```text
1 DELETE
```

---

# 25. Mutation success + GET failure

Caso crítico igual que 05.7.2:

```text
PATCH/DELETE → success
GET planner-state → failure
```

La mutación puede YA estar persistida.

NO repetir automáticamente:

```text
PATCH
DELETE
```

Recovery:

```text
GET /api/planner-state
```

únicamente.

---

# 26. Invalid success response

Si la mutation devuelve success HTTP pero el frontend no puede interpretar
correctamente la respuesta:

```text
asumir que pudo haberse persistido
```

Priorizar:

```text
GET planner-state
```

antes de permitir repetir la mutación.

---

# 27. Error de red antes de confirmación

Si PATCH/DELETE no obtiene confirmación:

```text
mostrar error controlado
mantener estado/formulario necesario
no alterar store persistido
```

Puede permitirse un reintento manual.

---

# 28. Error 404

Manejar:

```text
occurrence_not_found
```

de forma controlada.

Puede ocurrir por:

```text
concurrencia
estado desactualizado
```

La recuperación puede ofrecer:

```text
refrescar planner
```

No crash.

---

# 29. Error 409

Distinguir al menos cuando corresponda:

```text
history_frozen
last_manual_entry
priority_override_required
priority_conflict
completed_conflict
status_context_locked
concurrent_modification
planning_stopped
```

No mostrar todos como:

```text
"No se pudo guardar"
```

si el backend proporciona un código útil.

---

# 30. history_frozen

Una occurrence fuera de ventana editable:

```text
NO debe modificarse/eliminarse
```

Si UI intenta hacerlo y backend responde:

```text
409 history_frozen
```

mostrar feedback claro.

No modificar localmente para fingir éxito.

---

# 31. status_context_locked

Si una occurrence necesaria como:

```text
sourceOccurrenceId
```

de otra occurrence no puede modificarse/eliminarse:

```text
409 status_context_locked
```

debe preservarse.

No saltarse la protección desde frontend.

---

# 32. Concurrency

Si backend responde:

```text
409 concurrent_modification
```

mostrar feedback y permitir:

```text
GET planner-state
```

para recuperar el estado actual.

No reintentar mutation automáticamente.

---

# 33. CORS

Extender la allow-list existente únicamente lo necesario para:

```text
PATCH /api/occurrences/*
DELETE /api/occurrences/*
OPTIONS correspondiente
```

Mantener:

```text
VCS_ALLOWED_ORIGINS
```

NO usar:

```text
Access-Control-Allow-Origin: *
```

No habilitar todavía Apply Week/Future si no es necesario.

---

# 34. UI edit flow

Desde una fila occurrence-aware:

```text
seleccionar occurrence
→ Editar
→ editor muestra datos de ESA occurrence
→ Guardar
→ PATCH
→ GET
→ hydrate
```

El editor debe mostrar:

```text
date
startTime
endTime
```

de la occurrence concreta.

No del GenerationSlot actual.

---

# 35. UI delete flow

Desde una fila occurrence-aware:

```text
seleccionar occurrence
→ Eliminar
→ confirmación existente
→ DELETE
→ GET
→ hydrate
```

No eliminar todo el PlanItem.

---

# 36. Occurrence ordinal

Los ordinales visuales:

```text
□¹
□²
□³
```

son presentación.

NO usarlos como identidad para PATCH/DELETE.

Siempre usar:

```text
Occurrence.id
```

---

# 37. Selected day after mutation

Después de hydration:

```text
mantener selectedDate
```

si sigue siendo válida.

No saltar arbitrariamente al día actual.

Si la occurrence se movió de fecha:

```text
no cambiar selectedDate automáticamente
```

salvo que el comportamiento actual aprobado ya lo haga.

Preferencia:

```text
mantener contexto del usuario
```

---

# 38. Expanded rows after mutation

Después de mover/eliminar una occurrence:

```text
recalcular displayRows
```

desde el nuevo store hidratado.

No parchear manualmente filas.

---

# 39. Non-selected compact cells

Una eliminación/movimiento persistente debe reflejar inmediatamente:

```text
—³ → —²
—² → □
□ → —
```

según el número real de occurrences después del GET.

---

# 40. Persistence acceptance — edit

Caso obligatorio:

```text
Uber 14:00–17:00
```

editar solo esa occurrence:

```text
14:30–17:30
```

Esperar:

```text
Uber 08:00 intacta
Uber 20:00 intacta
Occurrence editada persiste
F5 conserva 14:30–17:30
```

---

# 41. Persistence acceptance — delete recurrent

Eliminar una occurrence recurrente concreta.

Esperar:

```text
desaparece
F5 no reaparece
slot general permanece
otras fechas permanecen
```

---

# 42. Persistence acceptance — manual

Editar/eliminar una manual entry concreta.

Verificar:

```text
round-trip exacto
F5
última entry protegida
```

---

# 43. Persistence acceptance — ad-hoc

Editar y eliminar una occurrence ad-hoc.

Verificar:

```text
sourceGenerationSlotId continúa null cuando corresponde
F5 refleja estado persistido
```

---

# 44. Same PlanItem multi-occurrence

Caso:

```text
08:00 Uber
14:00 Uber
20:00 Uber
```

Editar/eliminar la occurrence de las 14:00.

Resultado:

```text
08:00 intacta
14:00 modificada/eliminada
20:00 intacta
```

Caso obligatorio.

---

# 45. Reload

Después de cada mutation persistente:

```text
F5
```

debe conservar el resultado.

---

# 46. Existing creation regression

05.7.2 debe seguir funcionando:

```text
crear PlanItem
→ POST
→ GET
→ hydrate
→ F5
```

No romper create al ampliar CORS/API client.

---

# 47. Existing rendering regression

05.7.2.1 debe seguir funcionando:

```text
selected day
→ occurrence rows

non-selected
→ compact summary
```

No volver a checkboxes apilados.

---

# 48. No rematerialization

Después de PATCH/DELETE:

```text
GET planner-state
→ hydrate
```

NO ejecutar materializer frontend sobre las occurrences retornadas.

---

# 49. PostgreSQL

Automatización:

```text
PostgreSQL 16 aislado/efímero
```

NO usar:

```text
vcs_dev
```

---

# 50. Migrations

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

No cambiar schema en esta fase.

Si el schema actual hace imposible un contrato aprobado:

```text
DETENERSE Y REPORTAR
```

---

# 51. Backend

Los endpoints PATCH/DELETE ya fueron declarados READY durante 05.6.x.

No rediseñar backend para acomodar una UI incorrecta.

Si integración descubre un bug inequívoco:

```text
corregir mínimo
añadir regresión
reportar
```

---

# 52. Tests frontend

Añadir pruebas útiles para:

```text
PATCH success + GET + hydrate
DELETE success + GET + hydrate

same PlanItem multiple occurrences
edit exact occurrence
delete exact occurrence

manual
recurrent
ad-hoc

double PATCH
double DELETE

network failure

404
409 history_frozen
409 last_manual_entry
409 status_context_locked
409 concurrent_modification

mutation success + GET failure
retry GET only

selectedDate preserved
compact counter updates

reload/bootstrap compatibility
```

No perseguir número de tests.

---

# 53. PostgreSQL integration

Verificar al menos:

```text
recurrent edit same date
recurrent move date
recurrent delete + exclusion
manual edit/delete
last manual entry
ad-hoc edit/delete
rollback
concurrency
```

Reutilizar tests existentes cuando ya cubran correctamente el backend.

No duplicar pruebas innecesariamente.

---

# 54. Browser verification

Con frontend estático + Flask + PostgreSQL 16 efímero, si es viable:

```text
crear fixture multi-occurrence
editar una occurrence
F5
verificar persistencia

eliminar otra occurrence
F5
verificar persistencia
```

Comprobar:

```text
desktop
mobile
```

No inventar resultados.

---

# 55. Regression suite

Ejecutar:

```text
frontend completo
backend relevante/completo según cambios
PostgreSQL integration
JS/Python parity
node --check
compileall si backend cambia
git diff --check
```

---

# 56. Definition of done

MVP 05.7.3 queda completo cuando:

```text
Occurrence seleccionada
→ edit/delete
→ HTTP
→ PostgreSQL
→ GET
→ hydrate
→ UI
→ F5
→ resultado permanece
```

para:

```text
recurrent
manual
ad-hoc
multi-occurrence same PlanItem
```

sin conectar todavía:

```text
Apply Week
Apply Future
```

---

# 57. Fuera de alcance

NO implementar todavía:

```text
multiple displacement sources
user-authorized displacement general
conflict editor inline
desplazar todas las compatibles
provenance cleanup
persistent Apply Week
persistent Apply Future
auth
multiuser
deployment
analytics
```

---

# 58. ROADMAP decisions

Las decisiones recién añadidas al ROADMAP sobre:

```text
conflict resolution
multiple displacement sources
cancelled/not_completed non-blocking
manual recovery
inline Adjust/Displace actions
```

son contexto FUTURO.

NO implementarlas por iniciativa propia en 05.7.3.

Si una de ellas resulta necesaria para completar un contrato actual:

```text
DETENERSE Y REPORTAR
```

---

# 59. Git

Codex NO debe:

```text
commit
push
merge
cambiar rama
```

El usuario controla Git.

---

# 60. Reporte requerido

Al finalizar reportar:

1. archivos creados/modificados;
2. arquitectura/coordinador de Single Day;
3. cambios en planner-api;
4. flujo PATCH → GET → hydrate;
5. flujo DELETE → GET → hydrate;
6. CORS PATCH/DELETE;
7. double-submit protection;
8. mutation success + GET failure;
9. retry semantics;
10. 404 handling;
11. 409 handling por código;
12. history_frozen;
13. last_manual_entry;
14. status_context_locked;
15. concurrent_modification;
16. recurrent same-date edit;
17. recurrent moved-date edit;
18. recurrent delete/exclusion;
19. manual edit/delete;
20. ad-hoc edit/delete;
21. same PlanItem multi-occurrence;
22. selectedDate preservation;
23. compact counter updates;
24. F5 persistence;
25. browser verification;
26. frontend tests;
27. backend tests;
28. PostgreSQL integration;
29. parity/checks;
30. bugs encontrados;
31. riesgos/limitaciones;
32. si status persistence tiene o no contrato backend actual;
33. si priority override de PATCH tiene o no confirmación backend completa.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
001/002/003 no fueron modificadas
no se creó migration 004
Apply Week no fue conectado
Apply Future no fue conectado
ROADMAP future conflict system no fue implementado anticipadamente
no se añadieron secretos
no se hizo commit/push/merge
```




---

Ya entendí a que te referias cuando me decias que en lugar de estos —³  para ti sería mejor □³  y si, porque ahorita me quede como confundido, y pues cuando estemos en vista mensual las occurrences que no existan en el dia seleccionado si deberia tener esta apariencia □³ como control de estado y es justo por lo que me decias que no podia tener un status porque no representaría la n occurrences, entonces estoy pensando que si todas los status de ese plan_item en el mismo dia son iguales, pues que si se ponga en ese estado porque representa globalmente los estados, pero si no que aparezca 