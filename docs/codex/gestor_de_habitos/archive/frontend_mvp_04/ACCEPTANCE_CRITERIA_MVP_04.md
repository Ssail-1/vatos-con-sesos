
# Criterios de aceptación — MVP 04

## Nombre general

**MVP 04 — Motor de planificación por ocurrencias**

---

# División de la entrega

El MVP 04 está dividido en dos hitos internos:

```text
MVP 04.0.1
Motor temporal, modelo y materialización

MVP 04.0.2
Navegación temporal y visualización frontend
```

---

# IMPORTANTE

La tarea actualmente autorizada es únicamente:

```text
MVP 04.0.1
```

La sección correspondiente a:

```text
MVP 04.0.2
```

se documenta en este archivo únicamente para conservar el objetivo completo
del MVP 04.

Codex NO debe implementar todavía los criterios marcados como:

```text
MVP 04.0.2 — NO EJECUTAR
```

salvo que sean estrictamente necesarios para evitar romper una función
existente.

---

# Documentos normativos relacionados

La implementación debe contrastarse con:

```text
/docs/codex/CURRENT_TASK.md
/docs/codex/SCHEDULE_MODEL_MVP_04.md
/docs/codex/MOCK_DATA_CONTRACT_MVP_04.md
/docs/codex/FRONTEND_MVP_04.md
/docs/codex/UI_REFERENCE.md
```

Las referencias visuales específicas del MVP 04 se encuentran en:

```text
/docs/codex/assets/assets-MVP04/
```

---

# Área autorizada

Todo cambio de código debe permanecer dentro de:

```text
/modules/gestor_de_habitos/
```

Codex puede:

* crear archivos;
* modificar archivos;
* mover archivos;
* eliminar código obsoleto;

únicamente dentro de ese módulo.

---

# Fuera del área autorizada

No modificar:

```text
/AGENTS.md
/docs/
/index.html
/css/
/js/
/modules/dev_notes/
/README.md
/.gitignore
```

ni ningún otro archivo externo.

---

# Git

No ejecutar:

```text
git commit
git push
git merge
git switch
git checkout
git reset
git restore
git clean
git tag
```

Se permiten únicamente operaciones de inspección no destructivas como:

```text
git status
git diff
git diff --check
```

---

# Tecnologías permitidas

MVP 04 continúa utilizando:

* HTML;
* CSS;
* JavaScript nativo;
* módulos ES;
* APIs nativas del navegador;
* datos en memoria.

No utilizar:

* Flask;
* Python para la aplicación;
* PostgreSQL;
* Supabase;
* APIs remotas;
* React;
* Vue;
* Angular;
* npm;
* frameworks;
* librerías externas;
* localStorage;
* sessionStorage;
* IndexedDB.

---

# ============================================================

# MVP 04.0.1 — CRITERIOS OBLIGATORIOS

# ============================================================

# 1. Migración completa del modelo MVP 03

La aplicación debe dejar de utilizar como fuente canónica el modelo:

```text
id
name
recordKind
recordSubtype
position
plannedStartTime
plannedEndTime
statesByDate
```

Debe migrarse a:

```text
PlanItem
+
Occurrence
```

---

# 2. No deben existir dos fuentes de verdad

Después de la migración no debe mantenerse simultáneamente:

```text
statesByDate
```

y:

```text
Occurrence.status
```

como mecanismos activos.

La única fuente válida del estado de una fecha será:

```text
Occurrence.status
```

---

# 3. Fuente canónica separada

El estado mutable debe representar conceptualmente:

```js
{
    planItems: [],
    occurrences: []
}
```

No es obligatorio utilizar exactamente esta forma externa si el store utiliza
encapsulación.

Sí es obligatorio que:

* PlanItems;
* Occurrences;

sean conceptos separados.

---

# 4. PlanItem válido

Un PlanItem debe representar:

```text
qué cosa es
```

y no:

```text
cuándo ocurre concretamente
```

No debe contener:

```text
status
position
statesByDate
startTime
endTime
```

como propiedades del calendario materializado.

---

# 5. PlanItem Activity

Cuando:

```text
kind === "activity"
```

debe existir:

```text
activityType
```

y no debe existir:

```text
habitType
```

---

# 6. PlanItem Habit

Cuando:

```text
kind === "habit"
```

debe existir:

```text
habitType
```

y no debe existir:

```text
activityType
```

---

# 7. Tipos de Activity

Deben existir exactamente durante esta entrega:

```text
anchor
periodic
event
unexpected
```

---

# 8. Tipo de Habit

Durante MVP 04 solamente debe existir:

```text
scheduled
```

---

# 9. Nueva clasificación Event

Debe incorporarse:

```text
activity / event
```

al dominio.

No debe tratarse silenciosamente como:

```text
periodic
```

ni como:

```text
unexpected
```

---

# 10. Identidad del PlanItem

El id de un nuevo PlanItem:

* no depende del nombre;
* no depende de la fecha;
* no depende del horario;
* permanece estable al renombrar.

---

# 11. Generación de id

Debe utilizarse preferentemente:

```js
crypto.randomUUID()
```

con fallback local si resulta necesario.

---

# 12. Renombrar no cambia id

Ejemplo:

```text
Gym
↓
Gimnasio
```

debe conservar el mismo PlanItem.id.

---

# 13. Occurrence válida

Una occurrence debe representar como mínimo:

```text
id
planItemId
date
startTime
endTime
status
```

---

# 14. Occurrence no replica PlanItem

No debe copiar dentro de cada occurrence:

```text
name
kind
activityType
habitType
generationConfig
```

Estos datos se obtienen mediante:

```text
planItemId
```

---

# 15. Occurrence.id independiente

El id de una occurrence:

* no depende de su fecha;
* no depende de su horario;
* permanece estable al modificar fecha u horario.

---

# 16. Más de una occurrence del mismo PlanItem por día

La arquitectura no debe asumir:

```text
un PlanItem
=
máximo una occurrence por fecha
```

Debe poder existir conceptualmente:

```text
Medicamento
08:00

Medicamento
20:00
```

el mismo día.

No es necesario crear interfaz específica para demostrar este caso.

El store no debe impedirlo por diseño.

---

# 17. generationConfig

Debe existir como configuración del PlanItem para producir planificación
futura.

No debe tratarse como agenda materializada.

---

# 18. No crear ScheduleRule

No debe implementarse una entidad independiente:

```text
ScheduleRule
```

durante MVP 04.

---

# 19. No crear scheduleId

Occurrence no debe contener:

```text
scheduleId
scheduleVersionId
```

---

# 20. Regla fundamental de lectura

Para saber:

```text
qué está agendado en una fecha
```

la aplicación debe consultar:

```text
Occurrences
```

No debe recalcular la agenda directamente desde generationConfig durante cada
render.

---

# 21. Regla fundamental de generación

generationConfig debe utilizarse para:

```text
generar futuro
```

No para sobrescribir automáticamente una occurrence ya materializada.

---

# 22. generationConfig weekly

Debe soportar:

```text
mode
startDate
endDate
indefinite
weekdays
defaultStartTime
defaultEndTime
weekdayTimeOverrides
```

según el contrato.

---

# 23. weekly finito

Debe aceptarse:

```text
endDate definido
indefinite = false
```

---

# 24. weekly indefinido

Debe aceptarse:

```text
endDate = null
indefinite = true
```

---

# 25. Weekly inválido

Debe rechazarse una combinación equivalente a:

```text
endDate definido
+
indefinite = true
```

---

# 26. Weekdays ISO

Los días persistentes del dominio deben usar:

```text
1 lunes
2 martes
3 miércoles
4 jueves
5 viernes
6 sábado
7 domingo
```

---

# 27. Weekdays únicos

No deben aceptarse:

```js
[1, 1, 3, 5]
```

como resultado normalizado.

Deben eliminarse duplicados o rechazarse consistentemente.

---

# 28. Weekdays válidos

Debe rechazarse cualquier valor fuera de:

```text
1–7
```

---

# 29. Weekly requiere al menos un día

No aceptar:

```js
weekdays: []
```

para una configuración weekly activa.

---

# 30. Horario general weekly

Debe poder generarse utilizando:

```text
defaultStartTime
defaultEndTime
```

---

# 31. Override por weekday

Debe poder definirse un horario distinto para un día concreto.

Ejemplo:

```text
Lunes:
05:30–07:00

Viernes:
06:30–08:00
```

---

# 32. Override solamente para weekday activo

No debe aceptarse un override correspondiente a un día no incluido en:

```text
weekdays
```

---

# 33. Horario resuelto se copia a occurrence

Al materializar:

```text
generationConfig
↓
Occurrence
```

la occurrence debe recibir valores concretos:

```text
startTime
endTime
```

Posteriores cambios de generationConfig no deben cambiar silenciosamente la
occurrence ya creada.

---

# 34. generationConfig interval_days

Debe soportarse:

```text
mode: interval_days
startDate
endDate / indefinite
intervalDays
defaultStartTime
defaultEndTime
```

---

# 35. intervalDays válido

Debe ser:

```text
entero >= 1
```

---

# 36. intervalDays ejemplo

Una configuración equivalente a:

```text
startDate = 2026-08-20
intervalDays = 20
```

debe producir fechas conceptualmente equivalentes a:

```text
20 agosto
9 septiembre
29 septiembre
19 octubre
...
```

mientras estén dentro del rango materializado.

---

# 37. generationConfig manual_dates

Debe soportarse:

```text
mode: manual_dates
```

con varias entradas.

---

# 38. manual_dates permite horarios distintos

Debe ser posible:

```text
1 septiembre
10:00–11:00

20 noviembre
16:00–17:30
```

para el mismo PlanItem.

---

# 39. manual_dates vacío

No debe aceptarse una configuración activa con:

```js
entries: []
```

---

# 40. generationConfig single_date

Debe soportarse:

```text
mode: single_date
date
startTime
endTime
```

---

# 41. single_date materializa como máximo una aparición idéntica

Ejecutar repetidamente la materialización no debe crear duplicados de la misma
aparición automática.

---

# 42. Materializador separado

Debe existir una responsabilidad separada equivalente a:

```text
materializeOccurrences(...)
```

No implementar todas las reglas de recurrencia directamente dentro de:

```text
app.js
```

---

# 43. Materialización weekly

Debe generar únicamente fechas cuyos weekdays correspondan con la
configuración.

---

# 44. Materialización respeta startDate

No deben generarse occurrences anteriores a:

```text
generationConfig.startDate
```

---

# 45. Materialización respeta endDate

En una configuración finita no deben generarse occurrences posteriores a:

```text
generationConfig.endDate
```

---

# 46. Materialización indefinida usa horizonte

No intentar generar infinitamente.

---

# 47. Horizonte mínimo

Con una fecha de referencia en agosto de 2026, una configuración indefinida
debe poder quedar materializada al menos hasta el final de septiembre de 2026.

La implementación debe ser genérica.

No hardcodear:

```text
agosto
septiembre
2026
```

---

# 48. Horizonte calculado

Debe existir una responsabilidad clara para calcular:

```text
fin del mes siguiente
```

---

# 49. Extensión por planificación futura

Si existe una fecha explícita posterior al horizonte actual, el motor debe
poder extender las recurrencias indefinidas hasta el final del mes
correspondiente.

---

# 50. Materialización idempotente

Ejecutar dos veces el materializador para:

```text
mismo PlanItem
mismo rango
```

no debe crear occurrences automáticas idénticas duplicadas.

---

# 51. Duplicado materializado

Para idempotencia puede comprobarse conceptualmente:

```text
planItemId
date
startTime
endTime
```

---

# 52. La clave de idempotencia no es el ID

La combinación anterior NO reemplaza:

```text
Occurrence.id
```

Cada occurrence continúa teniendo identidad independiente.

---

# 53. Status por occurrence

Cada occurrence posee exactamente uno:

```text
pending
in_progress
completed
not_completed
cancelled
```

---

# 54. Status inicial

Una occurrence nueva comienza normalmente como:

```text
pending
```

---

# 55. No usar statesByDate

No debe existir código activo que mantenga:

```text
statesByDate
```

como fuente de status.

---

# 56. pending bloquea horario

Una occurrence:

```text
pending
```

debe participar en detección de conflictos.

---

# 57. in_progress bloquea horario

Una occurrence:

```text
in_progress
```

debe participar en detección de conflictos.

---

# 58. completed bloquea horario

Una occurrence:

```text
completed
```

debe participar en detección de conflictos.

---

# 59. cancelled libera horario

Una occurrence:

```text
cancelled
```

no debe impedir colocar otra occurrence superpuesta en la misma fecha.

---

# 60. not_completed libera horario

Una occurrence:

```text
not_completed
```

tampoco debe impedir colocar otra occurrence superpuesta en la misma fecha.

---

# 61. Cancelled permanece en datos

Liberar horario NO significa eliminar la occurrence.

Debe conservar:

```text
date
startTime
endTime
status = cancelled
```

---

# 62. Not completed permanece en datos

Debe conservarse igualmente:

```text
status = not_completed
```

como evidencia histórica de algo planeado que no se realizó.

---

# 63. Conflicto depende de la fecha

Dos bloques iguales:

```text
05:30–07:00
```

en fechas distintas NO entran en conflicto.

---

# 64. Conflicto en misma fecha

Dos occurrences bloqueantes de la misma fecha entran en conflicto cuando:

```text
newStart < existingEnd
AND
newEnd > existingStart
```

---

# 65. Intervalos contiguos

Debe permitirse:

```text
08:00–09:00
09:00–10:00
```

---

# 66. Superposición inicial

Debe detectarse:

```text
Existente:
08:00–10:00

Nueva:
09:30–11:00
```

---

# 67. Superposición final

Debe detectarse:

```text
Existente:
08:00–10:00

Nueva:
07:30–08:30
```

---

# 68. Intervalo contenido

Debe detectarse:

```text
Existente:
08:00–10:00

Nueva:
08:30–09:00
```

---

# 69. Intervalo contenedor

Debe detectarse:

```text
Existente:
08:00–10:00

Nueva:
07:00–11:00
```

---

# 70. Intervalo idéntico

Debe detectarse:

```text
08:00–10:00
08:00–10:00
```

si ambas occurrences bloquean horario.

---

# 71. Cancelled + nueva superpuesta

Debe permitirse:

```text
Gym
05:30–07:30
cancelled

Desayuno
06:00–06:30
pending
```

---

# 72. Not completed + nueva superpuesta

Debe permitirse:

```text
Gym
05:30–07:30
not_completed

Desayuno
06:00–06:30
pending
```

---

# 73. Completed + nueva superpuesta

Debe rechazarse:

```text
Gym
05:30–07:30
completed

Otra actividad
06:00–06:30
pending
```

---

# 74. Función de bloqueo centralizada

Debe existir una responsabilidad equivalente a:

```js
blocksSchedule(occurrence)
```

No duplicar la regla mediante condiciones incompatibles en varios módulos.

---

# 75. Cambios de status también validan integridad

No basta con validar:

* creación;
* edición.

También deben comprobarse determinadas transiciones de status.

---

# 76. Caso obligatorio de transición inválida

Estado inicial:

```text
Gym
05:30–07:30
not_completed

Desayuno
06:00–06:30
pending
```

Si se intenta cambiar Gym a:

```text
pending
```

la transición debe rechazarse porque reactivaría un intervalo en conflicto.

---

# 77. Cancelled → Pending puede fallar

Debe aplicarse la misma regla.

Una occurrence cancelada puede haber liberado un intervalo que ya fue
ocupado por otra occurrence.

---

# 78. Transición rechazada no modifica status

Si una transición produce conflicto:

* conservar status anterior;
* conservar resto del estado;
* informar fallo.

---

# 79. Ciclo multestado conserva comportamiento general

El ciclo puede continuar siendo:

```text
pending
→ in_progress
→ completed
→ not_completed
→ cancelled
→ pending
```

pero una transición ya no es necesariamente válida por definición.

---

# 80. No generar estado temporal inválido

Nunca debe existir, ni siquiera brevemente en el store:

```text
dos occurrences bloqueantes
+
misma fecha
+
intervalos superpuestos
```

por una transición de status.

---

# 81. Position deja de persistirse

No almacenar:

```text
position
```

dentro de PlanItem ni Occurrence.

---

# 82. Numeración visual

Si la tabla muestra:

```text
1
2
3
4
```

debe derivarse después de ordenar.

---

# 83. Orden diario

Las occurrences de un día deben ordenarse por:

```text
startTime
```

---

# 84. Duración no se almacena

No agregar:

```text
duration
```

a Occurrence.

---

# 85. Duración calculada

Debe derivarse mediante:

```text
endTime - startTime
```

---

# 86. Edición de occurrence

Debe existir una operación equivalente a:

```text
updateOccurrence(occurrenceId, draft)
```

---

# 87. Edición individual preserva id

Modificar:

```text
date
startTime
endTime
```

no debe crear una occurrence nueva innecesariamente.

Debe conservar:

```text
Occurrence.id
```

---

# 88. Edición preserva PlanItem

Debe conservar:

```text
planItemId
```

---

# 89. Edición preserva status

Editar horario o fecha no debe resetear automáticamente:

```text
status
```

---

# 90. Edición valida nueva fecha

Si una occurrence se mueve de:

```text
20 agosto
```

a:

```text
21 agosto
```

debe comprobar conflictos contra las occurrences bloqueantes del día 21.

---

# 91. Edición ignora solo a sí misma

Al buscar conflictos durante edición:

```text
ignoredOccurrenceId
```

debe ser únicamente el id editado.

No ignorar todas las occurrences del mismo PlanItem.

---

# 92. Crear PlanItem es operación coherente

Crear un PlanItem con generationConfig debe:

1. validar PlanItem;
2. validar generación;
3. calcular occurrences;
4. comprobar el conjunto;
5. insertar de forma coherente.

---

# 93. No dejar PlanItem huérfano por fallo accidental

Si el flujo de creación exige materialización inicial y esta falla por datos
inválidos, no debe quedar silenciosamente un PlanItem parcial no solicitado.

---

# 94. Validar antes de insertar conjunto

La estrategia preferida es:

```text
generar drafts
↓
validar todos
↓
insertar
```

---

# 95. Mock inicial migrado

Los siete registros del MVP 03 deben existir como:

```text
PlanItems
```

---

# 96. Mock demuestra distintos días

No todos los PlanItems deben ocurrir todos los días.

Debe poder demostrarse como mínimo:

```text
Gym
L / X / V

CCNA
L / X / V

algún hábito
todos los días
```

---

# 97. Status demostrativos migrados

Los estados visuales de demostración deben aplicarse sobre occurrences
concretas.

---

# 98. No crear occurrence solo para status demo

Si el fixture intenta aplicar un status a una fecha donde el PlanItem no
ocurre:

no debe materializar una occurrence ficticia para satisfacer el fixture.

---

# 99. Consultar occurrences por fecha

Debe existir una responsabilidad equivalente a:

```text
getOccurrencesForDate(date)
```

---

# 100. Consulta diaria ordenada

El resultado debe estar ordenado temporalmente.

---

# 101. Consultar occurrences por mes

Debe existir una responsabilidad equivalente a:

```text
getOccurrencesForMonth(...)
```

---

# 102. Month y year son derivados

No almacenar:

```text
month
year
```

en Occurrence.

---

# 103. Consultar por PlanItem

Debe existir una responsabilidad equivalente a:

```text
getOccurrencesForPlanItem(planItemId)
```

---

# 104. Store encapsulado

Las vistas no deben mutar directamente:

```text
planItems[]
occurrences[]
```

---

# 105. app.js continúa siendo coordinador

No trasladar a `app.js`:

* materialización;
* detección completa de conflictos;
* reglas de status;
* clasificación;
* store completo.

---

# 106. Modularización

Debe existir separación razonable entre:

```text
domain
scheduling
state
views
utils
data
```

sin crear archivos vacíos o innecesarios.

---

# 107. Event pertenece al dominio

Debe poder existir un PlanItem:

```text
activity / event
```

sin error de clasificación.

---

# 108. Unexpected pertenece al dominio

Debe continuar pudiendo existir:

```text
activity / unexpected
```

---

# 109. Prioridad no se almacena

No agregar:

```text
priority
```

a PlanItem ni Occurrence.

---

# 110. Prioridad derivable

Debe existir una regla conceptual equivalente a:

```text
NORMAL
EVENT
UNEXPECTED
```

---

# 111. Valores sugeridos

Puede utilizarse:

```text
NORMAL = 100
EVENT = 200
UNEXPECTED = 300
```

o valores equivalentes que preserven el orden.

---

# 112. UI MVP 03 continúa cargando

Después del cambio de modelo la aplicación debe seguir abriendo correctamente.

---

# 113. No rediseñar todavía la aplicación

MVP 04.0.1 no debe utilizarse como excusa para rehacer:

* colores;
* header;
* matriz;
* botones;
* layout.

---

# 114. Creación sigue utilizable

El usuario debe continuar pudiendo crear registros mediante la interfaz,
aunque el flujo visible completo de recurrencias quede reservado para 04.0.2.

---

# 115. Edición sigue utilizable

La edición de la occurrence actual debe continuar siendo funcional.

---

# 116. Estados siguen utilizables

Los botones multestado deben continuar funcionando con las nuevas reglas.

---

# 117. Navegación VCS se conserva

El enlace hacia:

```text
Vatos con Sesos
```

debe continuar funcionando.

---

# 118. Responsive existente

La página debe continuar siendo utilizable aproximadamente en:

```text
1440 × 900
390 × 844
```

---

# 119. Sin scroll horizontal global nuevo

La migración del dominio no debe introducir un desbordamiento global que antes
no existía.

---

# 120. Consola limpia

No deben quedar:

* errores JavaScript;
* imports rotos;
* referencias a módulos eliminados;
* rutas inexistentes.

---

# 121. Módulos eliminados correctamente

Si se eliminan archivos de MVP 03:

* sus imports deben eliminarse;
* su responsabilidad debe estar cubierta;
* no deben quedar referencias muertas.

---

# 122. Sintaxis

Los módulos JavaScript deben superar cuando corresponda:

```text
node --check
```

---

# 123. Imports reales

La aplicación debe probarse mediante servidor HTTP local para comprobar los
módulos ES.

---

# 124. Materialización weekly comprobada

Codex debe probar al menos un caso real de:

```text
L / X / V
```

y confirmar que no aparecen occurrences:

```text
martes
jueves
sábado
domingo
```

si no corresponden.

---

# 125. Override weekly comprobado

Debe probarse al menos un weekday con horario distinto al default.

---

# 126. interval_days comprobado

Debe verificarse la secuencia de al menos tres occurrences.

---

# 127. manual_dates comprobado

Debe verificarse materialización de varias fechas explícitas.

---

# 128. single_date comprobado

Debe verificarse una sola occurrence.

---

# 129. Idempotencia comprobada

Debe ejecutarse materialización repetida y confirmar que el número de
occurrences no aumenta incorrectamente.

---

# 130. Ausencia de occurrence

La arquitectura debe reconocer:

```text
PlanItem sin occurrence en esa fecha
```

como:

```text
NO PROGRAMADO
```

No como:

```text
pending
```

---

# 131. No crear status disabled

No agregar:

```text
disabled
```

a los estados del dominio.

La casilla deshabilitada futura representa ausencia de occurrence.

---

# 132. Persistencia sigue siendo memoria

Después de recargar:

* vuelven los mocks iniciales;
* desaparecen cambios temporales.

No implementar persistencia todavía.

---

# 133. Informe final de Codex para 04.0.1

Al terminar debe informar:

1. archivos creados;
2. archivos modificados;
3. archivos eliminados;
4. estructura final del módulo;
5. representación final de PlanItem;
6. representación final de Occurrence;
7. representación de generationConfig;
8. migración desde MVP 03;
9. eliminación de statesByDate;
10. eliminación de position;
11. generación de IDs;
12. materialización weekly;
13. materialización interval_days;
14. materialización manual_dates;
15. materialización single_date;
16. funcionamiento de weekday overrides;
17. horizonte de materialización;
18. idempotencia;
19. detección de conflictos;
20. comportamiento de cancelled;
21. comportamiento de not_completed;
22. comportamiento de completed;
23. validación de transiciones de status;
24. edición de occurrence;
25. pruebas de regresión;
26. pruebas responsive;
27. criterios no comprobados;
28. limitaciones;
29. instrucciones para ejecutar.

---

# Definición de terminado — MVP 04.0.1

La entrega se considera terminada cuando se puede demostrar:

```text
PlanItem
↓
generationConfig
↓
materializador
↓
Occurrences independientes
↓
agenda consultable por fecha
```

además:

```text
Occurrence
↓
status propio
```

y:

```text
cancelled
not_completed
↓
liberan horario
```

mientras:

```text
pending
in_progress
completed
↓
bloquean horario
```

y el MVP 03 continúa siendo utilizable sobre la nueva arquitectura.

---

# ============================================================

# MVP 04.0.2 — NO EJECUTAR TODAVÍA

# ============================================================

La siguiente sección registra los criterios previstos para la segunda mitad.

Codex debe leerla como contexto.

NO debe implementarla durante la tarea MVP 04.0.1.

---

# 200. Día seleccionado

La interfaz deberá mantener:

```text
selectedDate
```

como eje de navegación.

---

# 201. Mes visible

La interfaz deberá mantener:

```text
visibleMonth
```

independientemente del modelo persistente.

---

# 202. Carga inicial

Al cargar la aplicación:

```text
selectedDate = fecha actual
visibleMonth = mes de selectedDate
```

---

# 203. Encabezados de día clicables en escritorio

Los encabezados:

```text
LUN 17
MAR 18
MIÉ 19
...
```

deberán actuar como controles para cambiar selectedDate.

---

# 204. Día seleccionado resaltado

La columna correspondiente deberá mostrar claramente qué fecha se encuentra
seleccionada.

---

# 205. Plan del día filtrado

Con el modo filtrado activo deberán mostrarse únicamente occurrences cuya:

```text
date === selectedDate
```

---

# 206. Filtrado por occurrence

No decidir visibilidad mediante generationConfig.

La existencia real se obtiene desde:

```text
Occurrences
```

---

# 207. Flechas compactas por día

En pantalla pequeña:

```text
←
→
```

deberán mover selectedDate un día.

---

# 208. Cruce entre meses con flechas diarias

Desde:

```text
31 agosto
```

al avanzar:

```text
1 septiembre
```

deberán actualizarse:

```text
selectedDate
visibleMonth
```

---

# 209. Selector de fecha

La celda o control correspondiente a la fecha seleccionada deberá permitir
abrir un selector de fecha.

---

# 210. Preferencia por control nativo

Se utilizará preferentemente:

```html
<input type="date">
```

con integración visual propia.

---

# 211. showPicker

Puede utilizarse:

```js
input.showPicker()
```

cuando esté disponible.

Debe existir fallback.

---

# 212. Referencias visuales

Consultar:

```text
/docs/codex/assets/assets-MVP04/selector-fecha-desktop.png
/docs/codex/assets/assets-MVP04/selector-fecha-mobile.png
```

como intención de interacción.

No copiar necesariamente el aspecto exacto del navegador mostrado.

---

# 213. Navegación mensual escritorio

La matriz deberá disponer de controles equivalentes a:

```text
‹                          ›
```

en sus laterales.

---

# 214. Referencia visual mensual

Consultar:

```text
flechas-para-navegar-meses-en-pantalla-completa.png
```

---

# 215. Navegación mensual compacta

En pantalla pequeña deberán existir controles alrededor o asociados al nombre
del mes.

Consultar:

```text
flechas-para-navegar-meses-en-pantalla-pequeña.png
```

---

# 216. Mes seleccionable

El texto:

```text
Agosto de 2026
```

podrá funcionar como control para seleccionar otro mes.

---

# 217. Mes vacío accesible manualmente

El selector manual debe permitir navegar a un mes sin occurrences.

---

# 218. Mensaje de mes/día vacío

Debe mostrarse un estado vacío equivalente a:

```text
No hay registros programados.
```

---

# 219. Flecha al siguiente mes con planificación

Cuando se use navegación inteligente, la aplicación podrá saltar al siguiente
mes que contenga planificación.

---

# 220. Flecha al mes anterior con planificación

Debe poder realizar la operación inversa.

---

# 221. Repetición indefinida y navegación futura

Una generationConfig indefinida significa que existe planificación futura
conceptual aunque todavía no esté materializada.

La navegación podrá extender el horizonte cuando resulte necesario.

---

# 222. Ojo cerrado por defecto

Cada carga de aplicación deberá iniciar conceptualmente con:

```js
showAllMonthRecords = false
```

---

# 223. Modo filtrado

Con ojo cerrado:

mostrar únicamente los PlanItems que tengan occurrences en selectedDate.

---

# 224. Ojo abierto

Permitirá mostrar todos los PlanItems con al menos una occurrence dentro del
visibleMonth.

---

# 225. Celdas sin occurrence

Cuando un PlanItem sea visible por otras fechas del mes pero no exista en una
fecha concreta:

la celda deberá aparecer:

* deshabilitada;
* gris;
* sin símbolo.

---

# 226. Casilla gris no es cancelled

La celda deshabilitada representa:

```text
NO PROGRAMADO
```

No:

```text
cancelled
```

---

# 227. Casilla gris no es not_completed

Tampoco representa:

```text
not_completed
```

---

# 228. Casilla gris no crea datos

No debe generarse una occurrence ficticia para dibujar la celda.

---

# 229. Casilla no programada no interactiva

No debe permitir recorrer estados.

---

# 230. Occurrence cancelled visible

Una occurrence cancelada sí existe.

Debe poder mostrarse con su estado correspondiente.

---

# 231. Occurrence not_completed visible

También existe y debe conservarse visualmente.

---

# 232. Filas de otros días ocultas

Con ojo cerrado no deben aparecer PlanItems que no tengan occurrence para
selectedDate.

---

# 233. Modo mensual muestra otros PlanItems

Con ojo abierto pueden mostrarse PlanItems que no existan en selectedDate pero
sí en otra fecha del visibleMonth.

---

# 234. Horario en modo mensual

Si el PlanItem no existe en selectedDate:

no mostrar un horario de otra fecha como si perteneciera al día seleccionado.

Puede mostrarse:

```text
—
```

en Inicio/Duración según defina FRONTEND_MVP_04.

---

# 235. Diferentes horarios por fecha

La interfaz debe utilizar el horario de la occurrence concreta.

No generationConfig.

---

# 236. Semana lógica visual

La matriz podrá mostrar divisiones basadas en:

```text
lunes → domingo
```

---

# 237. Semana parcial al inicio del mes

Si el mes comienza a mitad de semana, el primer bloque visual puede ser
parcial.

---

# 238. Referencia visual semanal

Consultar:

```text
/docs/codex/assets/assets-MVP04/Visualizacion-por-semanas.png
```

---

# 239. Edición solo esta fecha

La interfaz deberá ofrecer explícitamente:

```text
Solo esta fecha
```

---

# 240. Edición solo esta semana

La interfaz deberá poder ofrecer:

```text
Solo esta semana
```

utilizando lunes-domingo.

---

# 241. Edición de aquí en adelante

La interfaz deberá poder ofrecer:

```text
De aquí en adelante
```

---

# 242. Solo esta fecha

Modifica únicamente la occurrence seleccionada.

---

# 243. Solo esta semana

Modifica únicamente occurrences del mismo PlanItem dentro del rango semanal
seleccionado.

---

# 244. Solo esta semana no cambia generationConfig general

Las semanas posteriores deben conservar la planificación general.

---

# 245. De aquí en adelante actualiza generationConfig

Debe:

* preservar historia;
* retirar/regenerar futuro pendiente;
* aplicar nueva configuración.

---

# 246. Futuro regenerable

La principal candidata a regeneración es:

```text
fecha futura
+
status === pending
```

---

# 247. No regenerar historia

No eliminar automáticamente:

```text
completed
not_completed
cancelled
in_progress
```

con valor histórico.

---

# 248. Formulario especializado por tipo

La interfaz de creación deberá adaptarse al:

```text
activityType / habitType
```

---

# 249. Anchor

Deberá ofrecer programación principalmente semanal.

---

# 250. Periodic

Podrá ofrecer:

```text
weekly
interval_days
manual_dates
```

---

# 251. Event

Podrá ofrecer:

```text
single_date
manual_dates
```

---

# 252. Unexpected

Utilizará principalmente:

```text
single_date
```

---

# 253. Habit scheduled

Continuará utilizando bloques programados.

---

# 254. Override Event

Un Event que choque con una occurrence normal deberá poder generar una
advertencia.

---

# 255. Override Unexpected

Un Unexpected deberá disponer de mayor prioridad conceptual.

---

# 256. No cancelar silenciosamente

Ninguna occurrence debe cambiar a cancelled por prioridad sin una acción
confirmada del usuario.

---

# 257. Referencias estadísticas

Las imágenes:

```text
borrador-representación-futura-estadística.png
objetivo-a-futuro-2.png
objetivo-a-futuro-3.png
```

son únicamente referencias futuras.

NO forman parte de MVP 04.0.2 salvo decisión posterior.

---

# 258. Estadísticas fuera de MVP 04

No implementar todavía:

* porcentajes;
* rachas;
* gráficas;
* premios;
* progreso mensual.

---

# Definición prevista de terminado — MVP 04 completo

Después de finalizar 04.0.2 deberá poder demostrarse:

```text
seleccionar fecha
↓
consultar occurrences reales
↓
mostrar únicamente el plan correspondiente
```

además:

```text
cambiar de día
cambiar de mes
abrir calendario
```

y:

```text
ojo cerrado
↓
solo plan del día

ojo abierto
↓
visión mensual completa
```

sobre el motor temporal aprobado en MVP 04.0.1.

---

# Regla final

MVP 04.0.1 construye:

```text
el motor
```

MVP 04.0.2 construye:

```text
la experiencia para navegar ese motor
```

No mezclar ambas responsabilidades antes de tener un checkpoint estable entre
las dos entregas.
