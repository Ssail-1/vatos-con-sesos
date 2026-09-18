# CURRENT TASK

## MVP 05.7.2.1 — Occurrence-aware monthly planner rendering

### Propósito

Corregir la representación visual del planner mensual para que el modelo
multi-slot se represente de forma clara y escalable.

Esta fase NO modifica persistencia ni reglas de dominio.

Estado:

```text
05.7.1    Bootstrap persistente                       ✅
05.7.2    Crear PlanItem persistente desde UI         ✅
05.7.2.1  Rendering occurrence-aware                  ← ACTUAL
05.7.3    Single Day persistente                      → después
```

La nueva regla visual fundamental es:

```text
día seleccionado
→ detalle por Occurrence

días no seleccionados
→ resumen por PlanItem
```

---

# 1. Alcance

Modificar exclusivamente la representación del planner/matriz.

No cambiar:

```text
PostgreSQL
schema
API contracts
materialization
generation rules
priority rules
temporal integrity
```

---

# 2. Fuente de verdad visual

La UI debe renderizar utilizando:

```text
PlanItems
+
Occurrences persistidas/hidratadas
```

NO inferir occurrences nuevas desde `generationConfig`.

NO rematerializar.

---

# 3. Problema actual

Actualmente un PlanItem con múltiples occurrences el mismo día puede
renderizarse conceptualmente como:

```text
Uber     □
         □
         □
```

dentro de una única fila.

Esto no escala y además oculta el orden cronológico real del día.

Con muchas occurrences produce una celda excesivamente alta.

Ese comportamiento debe desaparecer.

---

# 4. Día seleccionado

Para la fecha actualmente seleccionada:

```text
1 fila = 1 Occurrence
```

NO:

```text
1 fila = 1 PlanItem
```

Cada occurrence debe tener su propia:

```text
fila
hora de inicio
duración
actividad
control de status
```

---

# 5. Orden cronológico global

Las occurrences del día seleccionado deben ordenarse globalmente por:

```text
startTime
```

No agrupar primero por PlanItem.

Ejemplo:

```text
04:25 Despertar
06:30 Prueba recurrente multi-slot
08:00 Uber
12:00 Prueba recurrente multi-slot
14:00 Uber
20:00 Uber
```

No:

```text
Despertar
Prueba recurrente occurrence 1
Prueba recurrente occurrence 2
Uber occurrence 1
Uber occurrence 2
Uber occurrence 3
```

si eso rompe el orden temporal.

Como desempate usar de forma determinista:

```text
endTime
PlanItem name/id
Occurrence.id
```

o equivalente estable.

---

# 6. Columnas Inicio y Duración

En una fila de occurrence del día seleccionado:

```text
Inicio
```

debe provenir de:

```text
occurrence.startTime
```

y:

```text
Duración
```

de:

```text
occurrence.endTime - occurrence.startTime
```

Usar la occurrence concreta, NO el GenerationSlot actual.

Esto es importante porque una occurrence puede haber sido editada.

---

# 7. Actividad

Cada occurrence debe repetir el nombre del PlanItem.

Ejemplo:

```text
08:00 Uber
14:00 Uber
20:00 Uber
```

No fusionar visualmente las tres filas únicamente porque pertenecen al
mismo PlanItem.

---

# 8. Ordinal de occurrence del mismo PlanItem

Si el mismo PlanItem posee más de una occurrence en la fecha seleccionada,
los controles de status deben mostrar ordinal:

```text
□¹
□²
□³
...
```

El ordinal corresponde únicamente a las occurrences de ESE PlanItem en
la fecha seleccionada, ordenadas por hora.

Ejemplo:

```text
06:30 Prueba recurrente multi-slot  □¹
08:00 Uber                           □¹
12:00 Prueba recurrente multi-slot  □²
14:00 Uber                           □²
20:00 Uber                           □³
```

Los ordinales de diferentes PlanItems son independientes.

---

# 9. Una sola occurrence

Si un PlanItem tiene exactamente una occurrence en la fecha seleccionada:

```text
□
```

No mostrar:

```text
□¹
```

El superíndice solo aporta información cuando existen múltiples
occurrences del mismo PlanItem ese día.

---

# 10. Superíndice

Renderizar el ordinal semánticamente.

Preferir HTML equivalente a:

```html
<sup>2</sup>
```

No depender de una lista limitada de caracteres Unicode como:

```text
¹²³⁴...
```

porque un día podría contener más occurrences.

Debe soportar conceptualmente:

```text
1...N
```

---

# 11. Fechas no seleccionadas

Para cualquier fecha del mes que NO sea la fecha seleccionada:

```text
NO expandir occurrences en filas adicionales
```

Mantener una representación compacta por:

```text
PlanItem + fecha
```

---

# 12. Fecha no seleccionada con cero occurrences

Renderizar:

```text
—
```

o el marcador vacío actual equivalente.

---

# 13. Fecha no seleccionada con una occurrence

Si existe exactamente una occurrence:

```text
mostrar el control/status individual actual
```

Ejemplo conceptual:

```text
□
```

Debe continuar representando el estado de esa occurrence concreta.

---

# 14. Fecha no seleccionada con múltiples occurrences

Si existen N > 1 occurrences del mismo PlanItem:

NO renderizar:

```text
□
□
□
```

NO aumentar verticalmente la celda.

Mostrar una representación compacta:

```text
—²
—³
—⁴
...
```

conceptualmente:

```html
<span>—<sup>N</sup></span>
```

Este marcador indica:

```text
ese PlanItem tiene N occurrences esa fecha
```

No representa un status agregado.

---

# 15. Multi-occurrence compacta no es control colectivo

Un marcador:

```text
—³
```

NO significa:

```text
cambiar las 3 occurrences juntas
```

No debe mutar status de varias occurrences.

El detalle/status individual aparece al seleccionar esa fecha.

No inventar semántica colectiva.

---

# 16. Seleccionar esa fecha

Cuando el usuario seleccione una fecha que previamente mostraba:

```text
—³
```

el planner debe expandir esas tres occurrences en filas independientes.

Ejemplo:

```text
08:00 Uber □¹
14:00 Uber □²
20:00 Uber □³
```

---

# 17. PlanItems sin occurrence en el día seleccionado

Los PlanItems que existen en el mes pero NO poseen occurrence en la fecha
seleccionada deben seguir visibles en la vista mensual.

Deben renderizarse como UNA fila compacta.

Ejemplo:

```text
#   Inicio   Duración   Actividad
7     —        —       Plan item ejemplo
8     —        —       Otro plan item
```

No crear una fila por GenerationSlot.

No crear una fila por occurrence de otros días.

---

# 18. Orden de filas

Primero:

```text
todas las occurrences del día seleccionado
```

ordenadas cronológicamente.

Después:

```text
PlanItems sin occurrence en la fecha seleccionada
```

como filas compactas.

Para las filas compactas usar orden estable, preferentemente el orden
actual aprobado del planner.

---

# 19. Numeración #

La columna:

```text
#
```

debe numerar las filas visuales actuales.

Ejemplo:

```text
1 occurrence
2 occurrence
3 occurrence
...
7 summary PlanItem
8 summary PlanItem
```

No representar PlanItem.id ni occurrence ordinal en esta columna.

---

# 20. Celdas mensuales de una fila expandida

Un PlanItem puede tener varias filas porque tiene varias occurrences el día
seleccionado.

Para evitar repetir la misma información mensual N veces:

- la primera fila cronológica de ese PlanItem en el día seleccionado puede
  actuar como fila portadora del resumen de fechas NO seleccionadas;
- las filas adicionales del mismo PlanItem deben dejar vacías esas celdas
  de resumen o usar una representación visual equivalente que no duplique
  información.

La columna de la fecha seleccionada sí debe contener el control individual
de cada occurrence en su respectiva fila.

NO duplicar:

```text
—² —² —²
```

en cada fila expandida del mismo PlanItem.

---

# 21. Ejemplo normativo

Fecha seleccionada:

```text
22 de septiembre
```

Estado conceptual:

```text
#  Inicio  Duración  Actividad
-------------------------------------------------------------
1  04:25    5 min    Despertar                         □
2  06:30    1 h      Prueba recurrente multi-slot     □¹
3  08:00    3 h      Uber                              □¹
4  12:00    1 h      Prueba recurrente multi-slot     □²
5  14:00    3 h      Uber                              □²
6  20:00    2 h      Uber                              □³
7    —       —       Plan item ejemplo
8    —       —       Otro plan item
```

Mientras otras fechas permanecen compactas:

```text
Actividad       22   23   24   25   26
----------------------------------------
Uber             *    —    —²    —    —²
Despertar         *    □     □     □     □
```

`*` representa aquí únicamente las occurrences expandidas de la fecha
seleccionada; la implementación real usa sus controles individuales en
sus respectivas filas.

---

# 22. Status independientes

Cada occurrence expandida conserva su propio:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

Cambiar visualmente una occurrence no debe afectar automáticamente otra
occurrence del mismo PlanItem.

En esta fase las mutations de status pueden continuar con la semántica
local existente.

Persistencia de Single Day pertenece a 05.7.3.

---

# 23. sourceGenerationSlotId

El rendering NO debe depender de que:

```text
sourceGenerationSlotId
```

esté presente.

Una occurrence ad-hoc:

```text
sourceGenerationSlotId = null
```

debe renderizarse exactamente igual como occurrence concreta.

---

# 24. Overrides

Occurrences editadas previamente deben mostrarse utilizando:

```text
occurrence.date
occurrence.startTime
occurrence.endTime
```

No reemplazar visualmente sus horarios con el GenerationSlot actual.

---

# 25. Manual dates

`manual_dates` debe seguir las mismas reglas visuales.

Varias entries del mismo PlanItem en una fecha:

```text
→ varias occurrence rows cuando esa fecha está seleccionada
→ contador compacto cuando no está seleccionada
```

---

# 26. Weekly / interval

No debe existir diferencia de rendering basada en:

```text
weekly
interval_days
manual_dates
```

La matriz renderiza occurrences concretas.

---

# 27. Habit / activity

No crear reglas especiales que impidan múltiples occurrences para:

```text
habit
activity
```

Ambos usan el mismo principio occurrence-aware.

---

# 28. Responsive

Mantener comportamiento:

```text
desktop
mobile
```

La expansión por occurrence no debe introducir:

```text
overflow horizontal global
celdas gigantes
controles superpuestos
```

La vista móvil debe continuar siendo usable.

---

# 29. Accesibilidad

El contador/superíndice debe disponer de significado accesible.

Ejemplo conceptual:

```text
3 occurrences
```

No depender únicamente del tamaño pequeño del superíndice para transmitir
información.

Los controles de occurrence deben seguir siendo identificables de forma
individual.

---

# 30. Arquitectura

Preferir construir un modelo derivado de rendering:

```text
planItems
+
occurrences
+
selectedDate
↓
display rows
```

en una función clara/testeable.

NO mutar el store únicamente para acomodar la vista.

El store conserva el modelo canónico.

---

# 31. No persistir estado derivado

NO guardar en PostgreSQL ni store como dominio:

```text
row number
occurrence ordinal
compact count
expanded/collapsed representation
```

Todo eso es estado derivado de presentación.

---

# 32. No backend

Esta fase debe poder completarse solo en frontend.

NO modificar backend salvo que se descubra un bug inequívoco del contrato.

No cambiar:

```text
GET planner-state
POST plan-items
```

---

# 33. No migrations

NO modificar:

```text
001
002
003
```

NO crear migration 004.

---

# 34. No nuevas mutations HTTP

NO conectar todavía:

```text
PATCH occurrence
DELETE occurrence
Apply Week
Apply Future
```

Eso comienza en 05.7.3 y siguientes.

---

# 35. Persisted creation regression

05.7.2 debe continuar funcionando.

Verificar:

```text
crear PlanItem
→ POST
→ GET
→ hydrate
→ F5
→ permanece
```

El nuevo rendering no debe romper creación persistente.

---

# 36. Caso Uber obligatorio

Usar un escenario equivalente a:

```text
Uber

08:00–11:00
14:00–17:00
20:00–22:00
```

En fecha seleccionada:

```text
08:00 Uber □¹
14:00 Uber □²
20:00 Uber □³
```

En fecha no seleccionada:

```text
—³
```

No tres controles apilados.

---

# 37. Intercalación obligatoria

Caso:

```text
04:25 Despertar
06:30 A
08:00 Uber
10:00 Estudiar
12:00 A
14:00 Uber
16:00 Inglés
20:00 Uber
```

Debe renderizarse exactamente en orden temporal global.

No agrupar A ni Uber.

---

# 38. Caso PlanItem ausente del día seleccionado

Si:

```text
PlanItem X
```

tiene occurrences durante el mes pero ninguna el día seleccionado:

```text
una sola fila compacta
Inicio = —
Duración = —
```

Sus otras fechas siguen mostrando:

```text
□
—²
—³
```

según corresponda.

---

# 39. Tests

Añadir pruebas útiles para:

```text
selected day single occurrence
selected day multi occurrence
ordinal per PlanItem
independent ordinals across PlanItems
global chronological order
non-selected zero occurrence
non-selected single occurrence
non-selected multi occurrence compact counter
PlanItem absent selected day
ad-hoc occurrence
manual_dates multi-entry
weekly multi-slot
interval multi-slot
status independence
no duplicate summary cells
responsive rendering if practical
```

No perseguir cantidad de tests.

---

# 40. Regression

Ejecutar:

```text
frontend completo
05.7.1 bootstrap tests
05.7.2 creation tests
JS/Python parity
node --check
git diff --check
```

Backend completo no es necesario si backend no cambia.

---

# 41. Browser verification

Verificar en navegador real:

```text
desktop
mobile
```

con:

```text
fecha con 0 occurrences
fecha con 1 occurrence por PlanItem
fecha con múltiples occurrences del mismo PlanItem
varios PlanItems intercalados por horario
PlanItems sin occurrence en fecha seleccionada
```

No inventar resultados.

---

# 42. Definition of done

MVP 05.7.2.1 queda completo cuando:

```text
DÍA SELECCIONADO
→ filas por occurrence
→ orden cronológico
→ status individual
→ ordinal por PlanItem cuando N > 1
```

y:

```text
DÍAS NO SELECCIONADOS
→ resumen compacto por PlanItem
→ 0 = —
→ 1 = control individual
→ N > 1 = —ᴺ
```

sin cambiar el modelo persistente.

---

# 43. Fuera de alcance

NO implementar:

```text
persistent Single Day
persistent DELETE
Apply Week HTTP
Apply Future HTTP
PlanItem delete
auth
multiuser
deployment
analytics
```

---

# 44. Git

Codex NO debe:

```text
commit
push
merge
cambiar rama
```

El usuario controla Git.

---

# 45. Reporte requerido

Al finalizar reportar:

1. archivos modificados;
2. modelo derivado usado para rendering;
3. regla exacta de filas del día seleccionado;
4. orden cronológico;
5. cálculo de duración;
6. ordinal por PlanItem;
7. representación con una occurrence;
8. representación compacta N > 1;
9. PlanItems ausentes del selected day;
10. tratamiento de otras fechas en filas expandidas;
11. status individual;
12. ad-hoc;
13. manual_dates;
14. weekly;
15. interval_days;
16. Uber acceptance;
17. intercalación cronológica;
18. mobile;
19. desktop;
20. pruebas frontend;
21. regresión 05.7.1;
22. regresión 05.7.2;
23. node/diff checks;
24. bugs encontrados;
25. riesgos/limitaciones.

Confirmar explícitamente:

```text
backend no fue modificado salvo bug inequívoco
vcs_dev no fue modificado
001/002/003 no fueron modificadas
no se creó migration 004
no se conectaron nuevas mutations HTTP
no se implementaron features fuera de alcance
no se hizo commit/push/merge
```
