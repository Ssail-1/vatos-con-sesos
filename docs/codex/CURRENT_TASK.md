# CURRENT TASK

## MVP 05.7.3.1 — Monthly aggregate occurrence status

### Propósito

Mejorar el resumen visual de múltiples occurrences del mismo PlanItem en una
fecha NO seleccionada de la vista mensual.

Actualmente:

```text
N > 1 occurrences
→ —ᴺ
```

Esto informa cuántas occurrences existen, pero pierde información útil sobre
sus estados.

La nueva representación debe derivar un badge agregado exclusivamente para
presentación.

Ejemplo:

```text
pending + pending + pending
→ □³

completed + completed + completed
→ ✓³

completed + cancelled + not_completed
→ resumen mixto según contexto temporal
```

Estado:

```text
05.7.1    Bootstrap persistente                       ✅
05.7.2    Crear PlanItem persistente                  ✅
05.7.2.1  Rendering occurrence-aware                  ✅
05.7.3    Single Day persistente                      ✅
05.7.3.1  Monthly aggregate occurrence status         ← ACTUAL
05.7.4    Apply Week / Apply Future persistentes      → después
05.7.5    Mutation conflict resolution UX             → después
```

---

# 1. Principio fundamental

Este feature es exclusivamente PRESENTACIÓN DERIVADA.

NO crear nuevos estados de dominio.

NO persistir aggregate status.

NO modificar las occurrences para producir el badge.

La entrada es:

```text
PlanItem
+
Occurrences de una fecha
+
selectedDate
+
contexto temporal
```

y la salida es únicamente:

```text
representación visual mensual
```

---

# 2. Alcance

Modificar exclusivamente el rendering del planner mensual y sus tests/UI
relacionados.

Preferentemente esta fase debe completarse únicamente en frontend.

NO modificar:

```text
PostgreSQL
schema
backend contracts
materialization
generation rules
priority rules
status rules de dominio
```

---

# 3. Día seleccionado

Cuando la fecha está seleccionada:

```text
NO cambiar el comportamiento de 05.7.2.1
```

Continuar mostrando:

```text
1 fila = 1 occurrence
```

Ejemplo:

```text
08:00 Uber □¹
14:00 Uber ✓²
20:00 Uber ⚠³
```

Cada occurrence conserva:

```text
status individual
Occurrence.id individual
ordinal individual
```

NO agregar un status colectivo en el selected day.

---

# 4. Fecha NO seleccionada con cero occurrences

Mantener:

```text
—
```

---

# 5. Fecha NO seleccionada con una occurrence

Mantener el control/status individual actual.

Ejemplos:

```text
□
◷
✓
✕
◷!
⚠
```

No agregar superíndice `1`.

---

# 6. Fecha NO seleccionada con N > 1 occurrences

Sustituir el actual:

```text
—ᴺ
```

por un resumen derivado del grupo.

El superíndice:

```text
N
```

representa únicamente el número de occurrences del mismo PlanItem en esa
fecha.

Debe utilizar:

```html
<sup>N</sup>
```

o equivalente semántico.

NO limitarse a Unicode `¹²³`.

---

# 7. Status reales existentes

Los statuses de dominio continúan siendo únicamente:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

Este feature NO añade:

```text
mixed
today
warning
frozen_mixed
```

como statuses reales.

Esos conceptos son únicamente presentación derivada.

---

# 8. Grupo uniforme

Si TODAS las occurrences del grupo poseen exactamente el mismo status,
representar ese status de forma agregada.

Regla base:

```text
pending
→ □ᴺ

in_progress
→ ◷ᴺ

completed
→ ✓ᴺ

not_completed
→ ✕ᴺ

not_finished
→ ◷!ᴺ

cancelled
→ ⚠ᴺ
```

Ejemplo:

```text
completed
completed
completed

→ ✓³
```

La cantidad NO altera el significado del status.

---

# 9. Prioridad del estado uniforme

Un status uniforme significativo debe conservarse aunque la fecha sea pasada,
actual o futura.

Ejemplos:

```text
hoy:
completed + completed + completed
→ ✓³
```

```text
ayer:
cancelled + cancelled + cancelled
→ ⚠³
```

```text
fecha congelada:
not_completed + not_completed + not_completed
→ ✕³
```

No reemplazar estos resultados únicamente por el contexto temporal.

---

# 10. Pending uniforme futuro

Para fecha futura no seleccionada:

```text
pending + pending + ... + pending
→ □ᴺ
```

Ejemplo:

```text
□³
```

---

# 11. Pending uniforme en currentDay

Si:

```text
date == currentDay
selectedDate != currentDay
N > 1
todos siguen pending
```

mostrar un indicador temporal equivalente a:

```text
◷ᴺ
```

PERO el reloj debe tener estilo temporal/muted/gris para distinguirlo de:

```text
in_progress uniforme
```

que representa status real.

Conceptualmente:

```text
◷³ gris
→ 3 occurrences programadas para hoy
```

NO cambiar sus statuses reales de:

```text
pending
```

a:

```text
in_progress
```

---

# 12. Distinción visual de currentDay vs in_progress

Debe existir diferencia visual y accesible entre:

```text
◷³
```

por:

```text
todas in_progress
```

y:

```text
◷³
```

por:

```text
currentDay temporal
```

Ejemplo conceptual:

```text
in_progress real
→ icono/status normal

today pending
→ icono muted/gris
```

El `aria-label` debe dejar clara la diferencia.

---

# 13. Grupo mixto

Un grupo es mixto cuando:

```text
existen al menos dos statuses diferentes
```

Ejemplo:

```text
completed
pending
cancelled
```

No seleccionar arbitrariamente uno de los statuses como representante.

No calcular "mayoría".

No marcar el grupo completed solo porque 2 de 3 lo estén.

---

# 14. Grupo mixto futuro

Para una fecha futura:

```text
statuses diferentes
→ ◐ᴺ
```

o el símbolo equivalente ya aprobado visualmente para:

```text
estados mixtos
```

Ejemplo:

```text
completed
cancelled
pending

→ ◐³
```

Significado:

```text
3 occurrences con estados distintos
```

No representa un nuevo status.

---

# 15. Grupo mixto currentDay

Para:

```text
date == currentDay
selectedDate != currentDay
statuses diferentes
```

usar el contexto temporal de hoy sin fingir que el grupo posee un status
individual único.

Puede utilizarse visualmente el reloj muted/gris:

```text
◷ᴺ
```

siempre que:

```text
aria-label
tooltip
clase visual
```

indiquen que representa:

```text
N occurrences hoy con estados mixtos
```

y NO:

```text
todas in_progress
```

No modificar los statuses reales.

---

# 16. Día editable anterior / alerta temporal

Dentro de la ventana temporal todavía editable, cuando una fecha pasada
contiene N > 1 occurrences y el resultado del grupo requiere revisión,
mostrar un indicador equivalente a:

```text
⚠!ᴺ
```

Estilo conceptual:

```text
⚠ = muted/gris
! = rojo/attention
N = contador neutro
```

Significado:

```text
hay occurrences de este grupo que requieren revisión
y la fecha todavía es editable
```

No usarlo si todas las occurrences tienen un status uniforme significativo,
porque la regla de grupo uniforme tiene prioridad.

Ejemplos:

```text
completed + completed + completed
→ ✓³
```

```text
cancelled + cancelled + cancelled
→ ⚠³
```

```text
completed + cancelled + not_finished
→ ⚠!³
```

---

# 17. Historia congelada con status uniforme

Cuando la fecha ya está fuera de la ventana de edición:

si todas las occurrences tienen el mismo status, continuar mostrando el status
agregado real.

Ejemplos:

```text
completed x3
→ ✓³

not_completed x3
→ ✕³

not_finished x3
→ ◷!³

cancelled x3
→ ⚠³
```

---

# 18. Historia congelada con estados diferentes

Si:

```text
fecha congelada
+
N > 1
+
statuses diferentes
```

mostrar:

```text
!ᴺ
```

Ejemplo:

```text
08:00 completed
14:00 not_completed
20:00 cancelled

→ !³
```

Este badge significa:

```text
N occurrences
resultado histórico mixto
fecha no editable
```

NO significa un status nuevo.

---

# 19. Frozen mixed NO debe parecer control

En una fecha congelada:

```text
!ᴺ
```

debe sentirse visualmente como INFORMACIÓN HISTÓRICA.

No como checkbox.

No como control editable.

Principio visual:

```text
editable
→ puede parecer control/contexto activo

frozen
→ debe parecer información
```

---

# 20. Estilo de !ᴺ

Preferencia visual:

```text
! = rojo / atención
N = neutro
```

Ejemplo conceptual:

```text
!³
↑ ↑
│ └ cantidad
└ resultado histórico mixto
```

No colorear innecesariamente todo el badge de rojo si basta con resaltar `!`.

---

# 21. Estados inesperados en historia congelada

Según las reglas de reconciliación existentes, un frozen day no debería
conservar normalmente:

```text
pending
in_progress
```

sin reconciliar.

NO implementar reconciliación nueva en esta fase.

Si el frontend recibe una combinación imposible/inconsistente en fecha
congelada:

```text
usar un fallback seguro/informativo
```

preferentemente:

```text
!ᴺ
```

y añadir cobertura de regresión.

NO mutar el store para "corregirlo".

---

# 22. Tabla conceptual normativa

Para fecha NO seleccionada y N > 1:

```text
TODAS pending + futuro
→ □ᴺ

TODAS pending + currentDay
→ ◷ᴺ muted/gris

TODAS in_progress
→ ◷ᴺ status normal

TODAS completed
→ ✓ᴺ

TODAS not_completed
→ ✕ᴺ

TODAS not_finished
→ ◷!ᴺ

TODAS cancelled
→ ⚠ᴺ

MIXED + futuro
→ ◐ᴺ

MIXED + currentDay
→ indicador temporal de hoy, visualmente distinto de in_progress real

MIXED + fecha pasada todavía editable
→ ⚠!ᴺ

MIXED + fecha congelada
→ !ᴺ
```

---

# 23. No majority status

Está expresamente prohibido derivar:

```text
2 completed
1 pending
→ completed
```

o:

```text
3 cancelled
2 completed
→ cancelled
```

No existe "status ganador".

Si no son iguales:

```text
grupo mixto
```

---

# 24. No status mutation

Renderizar:

```text
◷³
⚠!³
!³
◐³
```

NO debe ejecutar ni implicar:

```text
setStatus()
updateOccurrence()
PATCH
POST
DELETE
```

Son badges derivados.

---

# 25. No collective status control

Cuando N > 1:

el badge agregado NO cambia los statuses de todas las occurrences juntas.

Ejemplo:

```text
✓³
```

NO debe convertirse en un botón que cambie las tres.

Para editar status individual:

```text
seleccionar la fecha
→ ver occurrence rows
→ operar occurrence individual
```

La UX colectiva futura no pertenece a esta fase.

---

# 26. Interacción con selección de fecha

Si la celda/fecha ya permite seleccionar el día:

```text
preservar esa navegación
```

Puede permitirse que el badge ayude a abrir/seleccionar la fecha si el
comportamiento existente lo soporta.

Pero:

```text
click badge
```

NO debe significar:

```text
cambiar status de todas
```

---

# 27. Accesibilidad

Cada aggregate badge debe exponer descripción comprensible.

Ejemplos conceptuales:

```text
□³
aria-label:
"3 occurrences pendientes"
```

```text
✓³
aria-label:
"3 occurrences completadas"
```

```text
◷³ muted currentDay
aria-label:
"3 occurrences programadas para hoy"
```

```text
◐³
aria-label:
"3 occurrences con estados diferentes"
```

```text
⚠!³
aria-label:
"3 occurrences con estados diferentes; fecha todavía editable"
```

```text
!³
aria-label:
"3 occurrences con estados diferentes; historial congelado"
```

No depender solo de color.

---

# 28. Tooltip

Si la UI ya utiliza `title`, tooltip o equivalente accesible:

puede añadirse una explicación breve.

No introducir una librería de tooltips.

No saturar visualmente la matriz.

---

# 29. Colores

Reutilizar tokens/clases actuales cuando sea posible.

No hardcodear colores aislados si ya existen variables CSS.

Necesidades mínimas:

```text
status normal
today muted/gris
warning attention
frozen mixed
```

El signo `!` de alertas puede utilizar la semántica visual de error/attention
existente.

---

# 30. Derivación clara y testeable

Preferir una función pura/equivalente como:

```text
deriveAggregateOccurrenceDisplay(
  occurrences,
  date,
  selectedDate,
  currentDate,
  editWindow
)
```

o una extensión limpia del modelo de rendering actual.

La función debería devolver información conceptual equivalente a:

```js
{
  count,
  type,
  status,
  temporalContext,
  icon,
  interactive,
  ariaLabel
}
```

No es obligatorio usar exactamente esta shape.

Lo importante es:

```text
regla derivada centralizada
```

y NO múltiples `if` dispersos por DOM/CSS/app.js.

---

# 31. Fuente de currentDay

Reutilizar las utilidades temporales existentes.

NO crear lógica temporal duplicada.

NO asumir UTC para decidir el día local del usuario.

NO introducir `new Date().toISOString().slice(0, 10)` si eso puede romper
la fecha local.

Seguir la política temporal frontend ya aprobada.

---

# 32. Ventana editable

Reutilizar:

```text
HISTORY_EDIT_WINDOW_DAYS
```

o la política/helper equivalente existente.

NO hardcodear:

```text
ayer
```

si ya existe una función normativa para determinar:

```text
editable
frozen
```

La UI debe derivar del mismo concepto temporal que el dominio actual.

---

# 33. Reconciliación

NO implementar reconciliación dentro del renderer.

El renderer:

```text
observa estados
+
observa contexto temporal
+
representa
```

No transforma:

```text
pending → not_completed
in_progress → not_finished
```

Eso pertenece a reglas de dominio/reconciliation existentes.

---

# 34. Status persistence sigue fuera de alcance

Aunque esta fase visualiza mejor los statuses:

```text
NO conectar persistencia de status
```

si 05.7.3 confirmó que aún no existe contrato backend aprobado.

Los status changes pueden continuar siendo temporales según el comportamiento
actual.

No inventar endpoint.

---

# 35. Crear/editar/eliminar persistence regression

05.7.2 y 05.7.3 deben seguir intactos.

Verificar:

```text
POST PlanItem
PATCH occurrence schedule
DELETE occurrence
GET
hydrate
reload
```

La nueva representación agregada no debe interferir.

---

# 36. Cambio de count después de DELETE

Caso obligatorio:

```text
3 occurrences
→ aggregate badge con superíndice 3
```

Eliminar una occurrence persistentemente:

```text
GET + hydrate
```

Resultado:

```text
2 occurrences
→ aggregate badge con superíndice 2
```

Eliminar otra:

```text
1 occurrence
→ volver al control/status individual normal
```

No mostrar:

```text
status¹
```

---

# 37. Cambio de status local

Mientras los cambios de status sigan siendo locales:

si el usuario modifica individualmente statuses y después observa la fecha
como no seleccionada, el aggregate badge debe recalcularse desde el store
actual.

Ejemplo:

```text
pending
pending
pending
→ □³
```

después:

```text
completed
pending
pending
→ mixed
```

El renderer debe reaccionar sin persistir nada nuevo.

---

# 38. Cambio de selectedDate

Al seleccionar una fecha:

```text
aggregate badge
→ occurrence rows individuales
```

Al seleccionar otra fecha:

la fecha anterior vuelve a:

```text
aggregate badge
```

derivado del estado actual.

No persistir expanded/collapsed state.

---

# 39. Caso obligatorio — uniform completed

```text
Uber:
08:00 completed
14:00 completed
20:00 completed
```

Fecha no seleccionada:

```text
✓³
```

Fecha seleccionada:

```text
08:00 Uber ✓¹
14:00 Uber ✓²
20:00 Uber ✓³
```

---

# 40. Caso obligatorio — uniform pending future

```text
Uber:
08:00 pending
14:00 pending
20:00 pending
```

Fecha futura no seleccionada:

```text
□³
```

---

# 41. Caso obligatorio — currentDay pending

Current day no seleccionado:

```text
08:00 pending
14:00 pending
20:00 pending
```

Mostrar:

```text
◷³
```

con estilo muted/gris y semántica:

```text
programadas para hoy
```

NO `in_progress`.

---

# 42. Caso obligatorio — uniform in_progress

```text
08:00 in_progress
14:00 in_progress
20:00 in_progress
```

Mostrar:

```text
◷³
```

pero con estilo normal de status `in_progress`.

Debe poder distinguirse visual y accesiblemente del caso currentDay pending.

---

# 43. Caso obligatorio — mixed future

```text
completed
pending
cancelled
```

fecha futura:

```text
◐³
```

---

# 44. Caso obligatorio — mixed editable past

Dentro de ventana editable:

```text
completed
cancelled
not_finished
```

Mostrar:

```text
⚠!³
```

con:

```text
warning muted
! attention/red
count neutral
```

---

# 45. Caso obligatorio — mixed frozen

Fuera de ventana editable:

```text
completed
not_completed
cancelled
```

Mostrar:

```text
!³
```

NO:

```text
□!³
```

NO:

```text
◐³
```

porque la información principal ahora es:

```text
resultado histórico mixto
+
no editable
```

---

# 46. Caso obligatorio — frozen uniform

Fuera de ventana:

```text
not_completed
not_completed
not_completed
```

Mostrar:

```text
✕³
```

NO:

```text
!³
```

porque el grupo NO es mixto.

---

# 47. Multi-PlanItem independence

Dos PlanItems en la misma fecha se agregan independientemente.

Ejemplo:

```text
Uber:
completed completed completed
→ ✓³

Medicamento:
pending pending
→ □²
```

No mezclar occurrences de distintos PlanItems.

---

# 48. Ad-hoc

Occurrences con:

```text
sourceGenerationSlotId = null
```

participan normalmente en el aggregate si pertenecen al mismo:

```text
PlanItem + date
```

No tratarlas diferente visualmente.

---

# 49. Manual / weekly / interval

El aggregate renderer NO depende de:

```text
manual_dates
weekly
interval_days
```

Trabaja únicamente con occurrences concretas.

---

# 50. Responsive

Verificar:

```text
desktop
mobile
```

Los nuevos badges:

```text
✓³
⚠!³
!³
◐³
```

no deben:

```text
aumentar excesivamente ancho/alto
crear overflow global
romper alineación
superponerse
```

---

# 51. Legend / help

Si existe una leyenda actual de statuses y resulta necesario aclarar los
aggregate badges, hacer únicamente una ampliación mínima.

No añadir un panel grande ni nueva navegación.

Preferir:

```text
aria-label
title
tooltip nativo
```

si es suficiente.

---

# 52. Tests

Añadir cobertura útil para:

```text
N=0
N=1
N>1

uniform pending future
uniform pending currentDay
uniform in_progress
uniform completed
uniform not_completed
uniform not_finished
uniform cancelled

mixed future
mixed currentDay
mixed editable past
mixed frozen

frozen uniform
frozen impossible pending fallback

count 2
count 3
count >9

independent PlanItems
ad-hoc included
selectedDate expansion
return to aggregate after changing selectedDate
delete 3→2→1
local status change recalculates aggregate
accessibility labels
```

No perseguir cantidad de tests.

---

# 53. Existing regression

Ejecutar:

```text
frontend completo
05.7.1 bootstrap
05.7.2 create
05.7.2.1 occurrence-aware rendering
05.7.3 occurrence mutations
JS/Python parity
node --check
git diff --check
```

Backend completo NO es necesario si backend no cambia.

---

# 54. Browser verification

Verificar en UI real:

```text
desktop 1440×900
mobile 390×844
```

Casos mínimos:

```text
✓³
□³
today muted ◷³
mixed ◐³
editable warning ⚠!³
frozen !³
```

Comprobar cambio:

```text
selected day
↔
non-selected day
```

sin hard reload especial más allá del necesario por cache durante desarrollo.

No usar un harness como única aceptación.

Verificar también la aplicación real:

```text
index.html
→ app.js
→ planner matrix real
```

---

# 55. Backend

Preferencia:

```text
NO backend changes
```

Si aparece un bug inequívoco del contrato:

```text
DETENERSE Y REPORTAR
```

antes de ampliar alcance.

---

# 56. CORS

No modificar CORS.

Esta fase no añade HTTP methods.

---

# 57. PostgreSQL

No se necesita PostgreSQL nuevo para la lógica agregada.

Puede reutilizarse estado fixture/frontend para pruebas.

Si se realiza verificación persistente complementaria:

```text
usar PostgreSQL efímero
```

NO `vcs_dev`.

---

# 58. Migrations

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

---

# 59. ROADMAP

NO implementar anticipadamente:

```text
multiple displacement sources
user-authorized displacement
conflict resolution dialog
status persistence
automatic recovery
Apply Week
Apply Future
```

La representación agregada debe permanecer desacoplada de esas features.

---

# 60. Definition of done

MVP 05.7.3.1 queda completo cuando:

```text
fecha seleccionada
→ occurrences individuales, sin cambio
```

y:

```text
fecha NO seleccionada
+
N > 1 occurrences
→ aggregate badge derivado
```

siguiendo:

```text
uniforme
→ status agregado

mixto futuro
→ ◐ᴺ

currentDay temporal
→ indicador today muted

mixto pasado editable
→ ⚠!ᴺ

mixto congelado
→ !ᴺ
```

sin crear nuevos statuses ni persistir información derivada.

---

# 61. Git

Codex NO debe:

```text
commit
push
merge
cambiar rama
```

El usuario controla Git.

---

# 62. Reporte requerido

Al finalizar reportar:

1. archivos modificados/creados;
2. función/modelo derivado usado;
3. tratamiento N=0;
4. tratamiento N=1;
5. tratamiento N>1;
6. uniform pending future;
7. currentDay pending;
8. diferencia currentDay vs real in_progress;
9. completed;
10. not_completed;
11. not_finished;
12. cancelled;
13. mixed future;
14. mixed currentDay;
15. mixed editable past;
16. mixed frozen;
17. frozen uniform;
18. fallback frozen inconsistente;
19. cálculo de count;
20. accesibilidad;
21. CSS/colores;
22. comportamiento al seleccionar el día;
23. recalculado al cambiar status local;
24. recalculado 3→2→1;
25. multi-PlanItem independence;
26. ad-hoc;
27. weekly/manual/interval;
28. desktop;
29. mobile;
30. frontend tests;
31. regresiones 05.7.1/05.7.2/05.7.2.1/05.7.3;
32. parity/static checks;
33. bugs encontrados;
34. riesgos/limitaciones.

Confirmar explícitamente:

```text
backend no fue modificado
vcs_dev no fue modificado
001/002/003 intactas
no migration 004
no nuevos endpoints
status persistence no fue implementada
Apply Week no fue conectado
Apply Future no fue conectado
ROADMAP future conflict system no fue implementado
no commit/push/merge
```
