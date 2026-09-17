# CURRENT TASK

## MVP 05.7.1 — Frontend API client + persisted planner bootstrap

### Propósito

Conectar por primera vez el frontend real del Gestor de hábitos con el
backend Flask.

Esta fase implementa exclusivamente el flujo de LECTURA inicial:

```text
PostgreSQL
    ↓
Flask API
    ↓
GET /api/planner-state
    ↓
API client JavaScript
    ↓
Planner Store
    ↓
UI
```

Estado actual:

```text
05.6      Dominio persistente                         ✅
05.6.5    Verificación integral                       ✅ READY

05.7      Frontend ↔ API integration                  ← NUEVO BLOQUE
05.7.1    Bootstrap persistente                       ← ACTUAL
05.7.2    Crear PlanItem persistente                  → después
05.7.3    Single Day persistente                      → después
05.7.4    Apply Week / Apply Future persistentes      → después
05.7.5    Mutations UX / errores / conflictos         → después
05.7.6    Verificación local final                    → después
```

---

# 1. Principio de esta fase

El backend/PostgreSQL pasa a ser la fuente inicial de verdad del planner.

Al abrir la aplicación:

```text
NO:
mockPlanItems → store → UI

SÍ:
GET /api/planner-state
→ store
→ UI
```

---

# 2. Alcance estricto

Implementar únicamente:

```text
API client frontend
GET planner-state
bootstrap async
hydrate/replace store
loading inicial
error inicial
empty state persistido
configuración central de API base URL
soporte local de CORS si realmente es necesario
tests
```

NO conectar todavía ninguna escritura HTTP.

---

# 3. Endpoints permitidos en frontend

En esta fase el frontend puede consumir únicamente:

```text
GET /api/planner-state
```

NO conectar todavía:

```text
POST /api/plan-items
PATCH /api/occurrences/*
DELETE /api/occurrences/*
POST /api/plan-items/*/apply-week
POST /api/plan-items/*/apply-future
```

Estos pertenecen a las siguientes subfases.

---

# 4. Estado persistido recibido

Contrato esperado:

```js
{
  planItems: [...],
  occurrences: [...]
}
```

Debe utilizar exactamente el contrato canónico que ya devuelve el backend.

NO crear un segundo formato de transporte.

NO mapear IDs a nuevos IDs frontend.

---

# 5. Hydration del store

Crear una operación explícita de store equivalente conceptualmente a:

```text
hydratePlannerState(serverState)
```

o:

```text
replacePlannerState(serverState)
```

Debe reemplazar ATÓMICAMENTE:

```text
planItems
occurrences
```

por el estado recibido.

No insertar primero uno y después otro dejando temporalmente un estado
inconsistente.

---

# 6. PostgreSQL/API son autoritativos durante bootstrap

Durante hydration:

```text
NO regenerar occurrences
NO volver a materializar PlanItems
NO generar UUID nuevos
NO inferir occurrences faltantes
NO reconstruir estado a partir de generationConfig
```

Las occurrences recibidas por:

```text
GET /api/planner-state
```

son las occurrences materializadas persistidas.

El frontend debe mostrarlas tal cual.

---

# 7. No duplicación por materializer

Auditar el flujo de inicialización actual.

Si actualmente al registrar PlanItems en el store se ejecuta
materialización automática:

```text
NO reutilizar ese camino para hydration si provoca regeneración.
```

Crear una ruta de hydration que preserve exactamente:

```text
server planItems
server occurrences
```

Caso obligatorio:

Servidor devuelve:

```text
1 PlanItem
3 occurrences
```

Después de bootstrap:

```text
store debe contener exactamente
1 PlanItem
3 occurrences
```

No:

```text
6 occurrences
```

por rematerialización accidental.

---

# 8. Empty database

Si backend devuelve:

```json
{
  "planItems": [],
  "occurrences": []
}
```

el frontend debe mostrar correctamente un planner vacío.

NO cargar automáticamente:

```text
mock data
demo data
seed data
```

como fallback.

DB vacía significa:

```text
planner vacío
```

---

# 9. Mocks

Los mocks existentes pueden mantenerse para:

```text
tests
fixtures
desarrollo explícito
```

pero NO deben ser la fuente automática de estado del runtime integrado.

No eliminarlos si siguen siendo útiles para tests.

---

# 10. Error de bootstrap

Si:

```text
backend no responde
network error
HTTP != 2xx
JSON inválido
contrato inválido
```

NO:

```text
caer silenciosamente a mocks
mostrar planner falso
ignorar error
```

Debe mostrarse un estado de error controlado.

Ejemplo conceptual:

```text
No se pudo cargar el planner.
```

No mostrar detalles internos de backend.

---

# 11. Retry

Puede existir una acción simple:

```text
Reintentar
```

que vuelva a ejecutar:

```text
GET /api/planner-state
```

sin recargar toda la página.

Si implementarlo exige complejidad desproporcionada:

```text
reportarlo
```

pero una implementación pequeña es preferible.

---

# 12. Loading inicial

Mientras se realiza el GET inicial:

```text
mostrar estado loading
```

No renderizar momentáneamente mocks ni un planner falso.

Evitar:

```text
flash de datos mock
flash de estado vacío incorrecto
```

antes de recibir respuesta.

---

# 13. Inicialización de UI

El bootstrap debe ser explícitamente async.

Flujo conceptual:

```text
DOM ready
    ↓
inicializar componentes/listeners una sola vez
    ↓
mostrar loading
    ↓
GET planner-state
    ↓
validar respuesta
    ↓
hydrate store
    ↓
render
```

Evitar registrar listeners múltiples por retry.

---

# 14. API client

Crear una capa frontend dedicada.

Ubicación sugerida:

```text
modules/gestor_de_habitos/js/api/
```

Ejemplo:

```text
planner-api.js
```

Responsabilidad:

```text
HTTP
JSON
status codes
errores de transporte
```

NO poner reglas de negocio allí.

---

# 15. No fetch disperso

No colocar llamadas directas a `fetch()` dentro de:

```text
views
planner-store
componentes visuales
```

La UI consume una API client/service clara.

Arquitectura esperada:

```text
app/bootstrap
      ↓
planner-api
      ↓
HTTP

app/bootstrap
      ↓
planner-store
      ↓
views
```

---

# 16. API base URL

Debe existir UNA sola fuente de configuración para el backend URL.

No repetir:

```text
http://127.0.0.1:5000
```

por varios archivos.

Diseñar una configuración central pequeña.

Preferir:

```text
same-origin por defecto
```

con posibilidad explícita de override para desarrollo local si frontend y
Flask corren en orígenes diferentes.

No introducir build system nuevo únicamente para esto.

---

# 17. Local development

El frontend se ha trabajado históricamente como sitio estático/local.

Si el frontend y Flask utilizan orígenes distintos en desarrollo:

```text
frontend → localhost/Live Server
backend  → localhost:5000
```

resolver únicamente el CORS mínimo necesario para la integración.

No añadir una dependencia externa si puede evitarse limpiamente.

---

# 18. CORS policy

Si CORS es necesario:

```text
NO Access-Control-Allow-Origin: *
```

como política general indiscriminada.

Usar una allow-list configurable para desarrollo.

Puede utilizarse una variable documentada equivalente a:

```text
VCS_ALLOWED_ORIGINS
```

Añadir únicamente a:

```text
.env.example
```

si hace falta.

Codex NO debe:

```text
leer
mostrar
modificar
```

el `.env` real.

---

# 19. CORS alcance 05.7.1

Solo necesitamos garantizar correctamente:

```text
GET /api/planner-state
```

desde el frontend local.

No implementar una gran capa CORS para todas las futuras mutations si aún
no es necesaria.

Las próximas fases pueden ampliar:

```text
OPTIONS
POST
PATCH
DELETE
```

cuando se conecten.

---

# 20. Error model frontend

Definir errores frontend distinguibles al menos conceptualmente entre:

```text
network error
HTTP error
invalid response
```

No hace falta crear una jerarquía compleja.

No exponer al usuario:

```text
stack traces
SQL
driver errors
```

---

# 21. Validación de response

No asumir ciegamente que cualquier JSON recibido es planner-state válido.

Validar como mínimo:

```text
objeto
planItems array
occurrences array
```

y cualquier invariant estructural mínima necesaria para hidratar
seguramente el store.

NO duplicar todo el dominio validator del backend.

La validación frontend es defensiva, no una segunda implementación completa
del dominio.

---

# 22. Store como estado en memoria

Después del bootstrap:

```text
planner-store
```

continúa siendo el estado reactivo/en memoria utilizado por la UI.

PostgreSQL no se consulta directamente desde views.

Arquitectura:

```text
PostgreSQL
    ↓
API
    ↓
store
    ↓
views
```

---

# 23. Mutaciones locales durante esta fase

Las mutations HTTP todavía NO están conectadas.

No fingir que:

```text
crear
editar
eliminar
Apply Week
Apply Future
```

ya persisten desde la UI.

El comportamiento local existente puede permanecer temporalmente para
desarrollo, pero:

```text
reload
→ servidor vuelve a ser la fuente de verdad
```

No implementar LocalStorage como puente.

No crear una cola offline.

---

# 24. No optimistic persistence todavía

NO implementar aún:

```text
optimistic POST
optimistic PATCH
optimistic DELETE
rollback UI de mutations
```

Eso pertenece a fases posteriores.

---

# 25. Estrategia futura de sincronización

No implementar todavía, pero mantener compatibilidad con esta decisión
provisional:

Después de una mutation persistente, inicialmente podremos preferir:

```text
mutation API
    ↓
GET /api/planner-state
    ↓
replace/hydrate store
```

en lugar de mantener manualmente dos estados paralelos.

No optimizar esto todavía.

---

# 26. app.js

`app.js` debe coordinar bootstrap.

No convertirlo en:

```text
HTTP client
repository
domain validator
```

Separar responsabilidades.

---

# 27. planner-store

El store puede conocer:

```text
cómo reemplazar estado canónico
```

pero NO:

```text
cómo llamar HTTP
```

No importar `fetch` ni API client dentro del store salvo que exista una
razón arquitectónica fuerte.

Preferencia:

```text
bootstrap/service llama API
→ bootstrap entrega resultado al store
```

---

# 28. Rendering

Después de hydration deben seguir funcionando las vistas existentes:

```text
planner matrix
forms
status visualization
multi-slot
```

No rediseñar UI.

---

# 29. Estado de loading/error

La UI de loading/error debe ser pequeña y coherente con el estilo actual.

No realizar un rediseño visual.

Debe funcionar en:

```text
desktop
mobile
```

---

# 30. Runtime errors

No debe haber en consola:

```text
uncaught promise rejection
undefined access
duplicate listener errors
```

durante:

```text
loading
success
empty state
error
retry
```

---

# 31. Backend contract

NO modificar semántica de:

```text
GET /api/planner-state
```

para acomodar un frontend incorrecto.

El backend ya fue declarado:

```text
READY
```

Si la integración descubre un bug real de contrato:

```text
reportarlo
```

y corregir únicamente si es inequívoco.

---

# 32. No backend domain changes

Esta fase NO debe modificar:

```text
materializer semantics
Single Day semantics
Apply Week
Apply Future
priorities
temporal integrity
```

Salvo bug inequívoco descubierto por integración.

---

# 33. PostgreSQL

No modificar:

```text
001
002
003
```

No crear migration 004.

No cambiar schema.

---

# 34. vcs_dev

Codex NO modifica:

```text
vcs_dev
```

Las pruebas automáticas deben usar:

```text
PostgreSQL 16 aislado/efímero
```

cuando necesiten DB real.

Después el usuario podrá probar manualmente contra `vcs_dev`.

---

# 35. Integration test — datos persistidos

Crear un test/integration scenario con PostgreSQL temporal:

```text
insert/create persisted PlanItem
+
persisted occurrences
```

Llamar:

```text
GET /api/planner-state
```

y alimentar esa respuesta al flujo frontend de hydration.

Verificar que el store final coincida semánticamente.

No es obligatorio montar un browser real para toda esta prueba si una
combinación backend integration + frontend test demuestra el contrato.

---

# 36. Browser integration

Realizar al menos una verificación real en navegador de:

```text
loading
success
empty state o persisted state
```

Si el entorno permite Flask + frontend local:

```text
verificar fetch real
```

Si no puede automatizarse limpiamente:

```text
reportar la limitación
```

sin inventar resultados.

---

# 37. Success acceptance

Con backend disponible y datos persistidos:

```text
abrir frontend
→ loading
→ GET planner-state
→ datos aparecen
```

IDs, horarios y statuses deben corresponder al servidor.

---

# 38. Empty acceptance

Con DB temporal vacía:

```text
abrir frontend
→ loading
→ GET 200 empty
→ planner vacío
```

No mocks.

---

# 39. Failure acceptance

Con backend no disponible o request fallido:

```text
abrir frontend
→ loading
→ error controlado
```

No:

```text
mock fallback
crash
uncaught promise
```

---

# 40. Retry acceptance

Si se implementa retry:

```text
primer request falla
backend vuelve
Reintentar
→ GET
→ hydrate
→ render normal
```

No duplicar listeners ni estado.

---

# 41. Reload semantics

Después de bootstrap exitoso, cualquier cambio solamente local que todavía
no esté conectado a API puede perderse al recargar.

Eso es aceptable temporalmente en 05.7.1.

El reload debe recuperar nuevamente:

```text
verdad persistida del backend
```

---

# 42. Regression

Ejecutar:

```text
frontend suites
backend suites afectadas
JS/Python parity
PostgreSQL integration relevante
node --check
compileall si backend cambia
git diff --check
```

No es necesario repetir pruebas costosas no relacionadas si nada backend
cambió, salvo las necesarias para demostrar integración.

---

# 43. Tests frontend nuevos

Cubrir al menos:

```text
bootstrap success
empty state
network failure
HTTP failure
invalid payload
retry si existe
no materialization duplicate
server IDs preserved
```

---

# 44. Mocks regression

Verificar que los mocks sigan disponibles para tests si se requieren.

Pero runtime integrado:

```text
NO debe importarlos/inyectarlos automáticamente
```

como estado inicial.

---

# 45. Existing planner behavior

Después de hydration deben mantenerse:

```text
sorting
matrix rendering
status controls
multi-slot rendering
responsive behavior
```

No hacer cambios funcionales no relacionados.

---

# 46. Security / privacy

No introducir:

```text
credenciales DB en frontend
DATABASE_URL en JS
passwords
secrets
```

Frontend conoce únicamente:

```text
HTTP API base URL
```

---

# 47. No direct DB access

El navegador NUNCA conecta directamente a PostgreSQL.

Siempre:

```text
Browser
→ Flask
→ PostgreSQL
```

---

# 48. Observability mínima

Los errores técnicos pueden registrarse de forma útil en consola durante
desarrollo.

El mensaje mostrado al usuario debe ser controlado.

No saturar consola en success path.

---

# 49. No libraries nuevas

Mantener:

```text
native JavaScript
```

No introducir:

```text
Axios
React Query
Redux
framework HTTP
```

para una sola llamada GET.

Usar `fetch`.

---

# 50. Definition of done

MVP 05.7.1 queda completo cuando se demuestre:

```text
Frontend startup
    ↓
GET /api/planner-state
    ↓
persisted state
    ↓
atomic store hydration
    ↓
correct UI render
```

para:

```text
datos existentes
DB vacía
error de red/API
```

sin mocks silenciosos ni rematerialización accidental.

---

# 51. Fuera de alcance

NO implementar todavía:

```text
POST frontend integration
PATCH frontend integration
DELETE frontend integration
Apply Week HTTP integration
Apply Future HTTP integration
optimistic mutations
offline mode
auth
multiusuario
deployment
Supabase
notifications
analytics
```

---

# 52. Git

Codex NO debe:

```text
commit
push
merge
cambiar de rama
```

El usuario controla Git.

---

# 53. Reporte requerido

Al terminar reportar:

1. archivos creados/modificados;
2. arquitectura del API client;
3. estrategia de API base URL;
4. si fue necesario CORS y cómo se configuró;
5. secuencia exacta de bootstrap;
6. método de store hydration;
7. cómo evita rematerialización;
8. qué ocurrió con mocks runtime;
9. loading behavior;
10. empty-state behavior;
11. error behavior;
12. retry behavior;
13. validación defensiva de response;
14. cómo preserva IDs del servidor;
15. prueba con datos persistidos;
16. prueba DB vacía;
17. prueba backend unavailable;
18. browser verification;
19. resultado frontend suites;
20. resultado backend/integration relevante;
21. resultado node/compile/diff checks;
22. cualquier bug real descubierto;
23. riesgos/limitaciones.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
001/002/003 no fueron modificadas
no se creó migration 004
no se conectaron mutations HTTP
no se añadieron secretos al frontend
no se implementaron features fuera de alcance
no se hizo commit/push/merge
```
