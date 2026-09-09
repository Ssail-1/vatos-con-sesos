
# Current Task

## Entrega actual

**MVP 04.0.2 — Navegación temporal y experiencia frontend completa**

---

# Proyecto

**Vatos con Sesos**

Submódulo actual:

```text
Vatos con Sesos
└── Gestor de hábitos
    └── Plan del día
```

---

# Estado del proyecto

MVP 04.0.1 ya fue implementado y aprobado como checkpoint funcional.

El motor temporal actual utiliza:

```text
PlanItem
+
generationConfig
+
Occurrence
```

MVP 04.0.2 NO debe reemplazar este modelo.

Debe construir la experiencia de usuario encima del motor existente.

---

# Baseline obligatorio

La implementación de MVP 04.0.1 constituye el nuevo baseline.

Actualmente deben preservarse, entre otras cosas:

* PlanItems separados de Occurrences;
* generationConfig como generador de planificación futura;
* Occurrences como agenda materializada;
* status independiente por Occurrence;
* materialización weekly;
* materialización interval_days;
* materialización manual_dates;
* materialización single_date;
* weekdayTimeOverrides;
* horizonte de materialización;
* idempotencia;
* detección de conflictos;
* edición individual de Occurrence;
* integridad al cambiar status;
* múltiples Occurrences posibles del mismo PlanItem en una fecha;
* IDs independientes de nombre, fecha y horario;
* almacenamiento exclusivamente en memoria.

---

# Regla de estados vigente

Continúan bloqueando horario:

```text
pending
in_progress
completed
```

Continúan liberando horario:

```text
not_completed
cancelled
```

---

# Comportamiento cíclico aprobado

También debe preservarse la corrección incorporada al cierre de MVP 04.0.1.

Si una Occurrence está:

```text
cancelled
```

y avanzar normalmente a:

```text
pending
```

produciría un conflicto temporal, el control cíclico debe utilizar:

```text
not_completed
```

como fallback.

De este modo puede alternarse:

```text
not_completed
↔
cancelled
```

cuando el antiguo intervalo ya fue ocupado por otra Occurrence.

Esto NO modifica la regla explícita de:

```text
setOccurrenceStatus(..., "pending")
```

que debe continuar rechazando una reactivación que produzca conflicto.

---

# Objetivo de MVP 04.0.2

Transformar el motor temporal construido en MVP 04.0.1 en una experiencia de
planificación completa y navegable.

La interfaz debe permitir que el usuario trabaje naturalmente con:

```text
día
semana
mes
recurrencia
excepciones
eventos
imprevistos
```

sin necesitar comprender directamente:

```text
PlanItem
Occurrence
generationConfig
materialización
```

---

# Principio principal del frontend

La interfaz siempre debe responder a:

```text
¿Qué está realmente programado para esta fecha?
```

consultando:

```text
Occurrences
```

No consultar generationConfig como sustituto de una Occurrence materializada.

generationConfig continúa respondiendo únicamente:

```text
¿Qué debe generarse en el futuro?
```

---

# Documentación normativa

Antes de modificar código, leer completamente:

1. `/AGENTS.md`
2. `/docs/codex/CURRENT_TASK.md`
3. `/docs/codex/SCHEDULE_MODEL_MVP_04.md`
4. `/docs/codex/MOCK_DATA_CONTRACT_MVP_04.md`
5. `/docs/codex/FRONTEND_MVP_04.md`
6. `/docs/codex/UI_REFERENCE.md`
7. `/docs/codex/ACCEPTANCE_CRITERIA_MVP_04.md`

---

# Activación de MVP 04.0.2

Dentro de:

```text
/docs/codex/ACCEPTANCE_CRITERIA_MVP_04.md
```

existe una sección titulada:

```text
MVP 04.0.2 — NO EJECUTAR TODAVÍA
```

La prohibición contenida en ese título queda expresamente levantada por este
CURRENT_TASK.

Los criterios pertenecientes a MVP 04.0.2 pasan a estar ACTIVOS para esta
entrega.

Los criterios de MVP 04.0.1 continúan vigentes como:

```text
criterios de regresión
```

y no como trabajo que deba reconstruirse desde cero.

---

# FRONTEND_MVP_04

Todas las secciones correspondientes a:

```text
MVP 04.0.2
```

dentro de:

```text
/docs/codex/FRONTEND_MVP_04.md
```

quedan autorizadas para implementación.

---

# Documentación no normativa

Las carpetas:

```text
/docs/codex/planeacion/
/docs/codex/proximas-features/
/docs/codex/archive/
```

pueden utilizarse para comprender contexto.

NO deben ampliar el alcance actual.

En particular:

```text
/docs/codex/planeacion/ROADMAP_PENDING_FEATURES.md
```

contiene funciones futuras o pendientes.

No implementarlas únicamente porque estén documentadas allí.

---

# Referencias visuales

Utilizar:

```text
/docs/codex/UI_REFERENCE.md
```

para interpretar las imágenes.

Las referencias activas del MVP 04 se encuentran principalmente en:

```text
/docs/codex/assets/assets-MVP04/
```

Las imágenes estadísticas continúan siendo visión futura.

NO implementar a partir de ellas:

* gráficas;
* porcentajes;
* rachas;
* premios;
* dashboard estadístico.

---

# Área autorizada

Codex puede crear, modificar, mover o eliminar código únicamente dentro de:

```text
/modules/gestor_de_habitos/
```

---

# No modificar

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

ni ningún archivo fuera del módulo autorizado.

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

No cambiar de rama.

Puede utilizarse:

```text
git status
git diff
git diff --check
git log
```

como inspección no destructiva.

---

# Tecnologías

Continuar utilizando:

* HTML;
* CSS;
* JavaScript nativo;
* módulos ES;
* APIs nativas del navegador;
* datos exclusivamente en memoria.

No introducir:

* Flask;
* PostgreSQL;
* Supabase;
* API;
* localStorage;
* sessionStorage;
* IndexedDB;
* React;
* Vue;
* Angular;
* npm;
* frameworks;
* librerías externas.

---

# ============================================================

# 1. ESTADO TEMPORAL DE INTERFAZ

# ============================================================

La interfaz debe utilizar conceptualmente:

```text
selectedDate
visibleMonth
showAllMonthRecords
```

Estos valores pertenecen al frontend.

No agregarlos a:

```text
PlanItem
Occurrence
generationConfig
```

---

# selectedDate

Representa la fecha actualmente seleccionada.

La planificación diaria visible debe resolverse utilizando las Occurrences de
esa fecha.

---

# visibleMonth

Representa el mes mostrado actualmente en la matriz.

Debe poder cambiar mediante navegación mensual y selección directa.

---

# showAllMonthRecords

Controla:

```text
false
→ Plan del día

true
→ visión completa del mes
```

Valor inicial:

```text
false
```

---

# Carga inicial

Al cargar:

```text
selectedDate = fecha local actual
visibleMonth = mes de selectedDate
showAllMonthRecords = false
```

No asumir UTC para resolver la fecha local.

---

# ============================================================

# 2. SELECCIÓN DE DÍA

# ============================================================

En escritorio, los encabezados de fecha de la matriz deben poder seleccionar
directamente un día.

Ejemplo:

```text
LUN
17
```

Al activarlo:

```text
selectedDate = esa fecha
```

---

# Columna seleccionada

La fecha seleccionada debe conservar un resaltado coherente con el acento
dorado actual.

No depender exclusivamente del color para comunicar selección.

---

# Vista compacta

Las flechas diarias existentes continúan representando:

```text
día anterior
día siguiente
```

Deben permitir cruzar correctamente entre:

* meses;
* años.

Al cruzar un mes debe sincronizarse:

```text
visibleMonth
```

---

# ============================================================

# 3. SELECTOR DE FECHA

# ============================================================

Implementar selección directa de fecha.

Preferir:

```html
<input type="date">
```

y:

```js
showPicker()
```

cuando exista soporte.

Debe existir fallback razonable.

No construir un calendario complejo propio.

Consultar:

```text
selector-fecha-desktop.png
selector-fecha-mobile.png
```

según UI_REFERENCE.

---

# ============================================================

# 4. NAVEGACIÓN MENSUAL

# ============================================================

Implementar navegación independiente para:

```text
visibleMonth
```

No confundirla con la navegación diaria.

---

# Escritorio

Integrar controles mensuales siguiendo la intención de:

```text
flechas-para-navegar-meses-en-pantalla-completa.png
```

---

# Compacto

Integrar navegación aproximadamente como:

```text
‹   Agosto de 2026   ›
```

siguiendo:

```text
flechas-para-navegar-meses-en-pantalla-pequeña.png
```

---

# Selector de mes

El nombre del mes debe permitir selección directa cuando sea razonable.

Preferir:

```html
<input type="month">
```

con fallback si resulta necesario.

---

# Mes vacío

La selección manual debe permitir visitar un mes sin Occurrences.

Mostrar un estado vacío comprensible.

No impedir la navegación.

---

# Recurrencias indefinidas

Si el usuario navega más allá del horizonte materializado y existen
generationConfigs indefinidas:

utilizar el motor existente para extender materialización de manera finita.

No reconstruir todo el calendario.

No generar infinitamente.

---

# ============================================================

# 5. MODO PLAN DEL DÍA — OJO CERRADO

# ============================================================

Estado inicial:

```text
showAllMonthRecords = false
```

Mostrar únicamente PlanItems que tengan al menos una Occurrence en:

```text
selectedDate
```

---

# Regla importante

Si un PlanItem no posee Occurrence ese día:

NO debe aparecer en modo Plan del día.

No consultar weekdays de generationConfig para decidirlo.

Consultar Occurrences.

---

# Orden

Ordenar por horario concreto de la Occurrence:

```text
startTime
```

---

# ============================================================

# 6. MODO MENSUAL — OJO ABIERTO

# ============================================================

Implementar un control accesible para alternar:

```text
Plan del día
↔
Vista mensual completa
```

---

# Ojo abierto

Con:

```text
showAllMonthRecords = true
```

mostrar todos los PlanItems que tengan al menos una Occurrence dentro de:

```text
visibleMonth
```

---

# Inicio y duración

Si un PlanItem visible no posee Occurrence en:

```text
selectedDate
```

mostrar:

```text
Inicio: —
Duración: —
```

No tomar el horario de otra fecha.

---

# Horario concreto

Si sí existe una Occurrence en selectedDate:

Inicio y Duración deben derivarse de ESA Occurrence.

No de generationConfig.

---

# ============================================================

# 7. CELDAS NO PROGRAMADAS

# ============================================================

Con ojo abierto, una celda sin Occurrence debe representar:

```text
NO PROGRAMADO
```

---

# Apariencia

Debe utilizar una representación equivalente a:

```text
gris
sin símbolo
deshabilitada
```

---

# No crear estado nuevo

No implementar:

```text
status = disabled
```

---

# No crear Occurrence falsa

La ausencia de programación se representa mediante:

```text
ausencia de Occurrence
```

No mediante un registro artificial.

---

# Diferencias semánticas

```text
no programado
≠ pending

no programado
≠ cancelled

no programado
≠ not_completed
```

---

# ============================================================

# 8. SEMANAS VISUALES

# ============================================================

Integrar separación visual dentro de la matriz mensual según semanas:

```text
lunes → domingo
```

Consultar:

```text
Visualizacion-por-semanas.png
```

---

# Mantener una sola matriz

NO dividir el mes en varias tablas.

Debe continuar existiendo:

```text
una sola matriz mensual
```

---

# Estilo permitido

Puede utilizarse:

* borde ligeramente más fuerte;
* fondos alternos discretos;
* variaciones suaves de opacidad;
* degradados muy sutiles;

manteniendo la identidad oscura actual.

No convertir las semanas en bloques multicolor llamativos.

---

# ============================================================

# 9. FORMULARIO DE CREACIÓN DINÁMICO

# ============================================================

La interfaz debe implementar durante esta entrega los tipos actualmente
aceptados por el dominio.

---

# Selección principal

Permitir elegir:

```text
Actividad
Hábito
```

---

# Activity

Tipos:

```text
anchor
periodic
event
unexpected
```

---

# Habit

Tipo actual:

```text
scheduled
```

---

# Activity / Anchor

Interfaz orientada principalmente a:

```text
weekly
```

Debe permitir como mínimo:

```text
Nombre
Fecha inicial
Días L–D
Horario general
Horarios diferentes por weekday
Fecha final o indefinidamente
```

---

# Activity / Periodic

Debe permitir elegir:

```text
Días de la semana
Cada N días
Fechas específicas
```

correspondientes a:

```text
weekly
interval_days
manual_dates
```

---

# Activity / Event

Debe utilizar principalmente:

```text
single_date
manual_dates
```

para fechas conocidas anticipadamente.

---

# Activity / Unexpected

Debe utilizar principalmente:

```text
single_date
```

La fecha inicial sugerida debe ser:

```text
selectedDate
```

---

# Habit / Scheduled

Continúa siendo un bloque temporal.

Debe soportar principalmente:

```text
weekly
```

con:

```text
fecha inicial
weekdays
inicio
fin
fecha final / indefinido
```

---

# No implementar hábito puntual

Todos los hábitos continúan teniendo:

```text
startTime
endTime
```

durante MVP 04.

La semántica de hábito puntual pertenece al roadmap futuro.

---

# ============================================================

# 10. DIÁLOGO DE EDICIÓN DINÁMICO

# ============================================================

El botón:

```text
✎
```

debe abrir:

```text
UN SOLO DIÁLOGO
```

No crear una cadena de ventanas consecutivas.

---

# Jerarquía

La interfaz debe organizarse conceptualmente:

```text
1. Horario
2. Fecha
3. Repetición
4. Alcance cuando corresponda
5. Cancelar / Aceptar
```

---

# Horario

Los primeros controles deben permitir cambiar:

```text
startTime
endTime
```

de la Occurrence observada.

---

# Fecha

Debe poder cambiarse:

```text
date
```

para cualquier Occurrence.

Mover una Occurrence mediante:

```text
Solo esta fecha
```

representa una excepción individual.

No modifica automáticamente generationConfig.

---

# Repetición

Cuando exista una configuración semanal, mostrar los weekdays de manera
interactiva.

Debe distinguirse visualmente:

```text
día activo en la recurrencia
```

de:

```text
día actualmente seleccionado dentro del editor
```

No utilizar un único estado visual ambiguo para ambos conceptos.

---

# Cambio entre días

Si el usuario selecciona otro weekday activo dentro del editor, los campos de
horario deben representar la Occurrence concreta correspondiente a ese día de
la semana observada, cuando exista.

No utilizar automáticamente el horario global de generationConfig como si
fuera una Occurrence.

---

# ============================================================

# 11. ALCANCE DE EDICIÓN

# ============================================================

El diálogo debe ser progresivo.

Si únicamente se modifica:

```text
hora
fecha
```

de la Occurrence actual y no se cambia la recurrencia:

el comportamiento corresponde a:

```text
Solo esta fecha
```

y basta el botón final:

```text
Aceptar
```

---

# Cambio de recurrencia

Si el usuario modifica:

* weekdays;
* patrón;
* configuración repetitiva;

mostrar antes de Aceptar:

```text
Aplicar solo esta semana

Aplicar de aquí en adelante
```

---

# Alcance no ejecuta inmediatamente

El flujo debe ser:

```text
editar
↓
elegir alcance
↓
Aceptar
```

Los botones de alcance representan selección.

No deben guardar por sí solos.

---

# Aplicar solo esta semana

Utilizar semana lógica:

```text
lunes → domingo
```

Modificar únicamente las Occurrences del mismo PlanItem dentro de esa semana.

NO modificar generationConfig general para semanas posteriores.

---

# Integridad semanal

La operación debe validarse como conjunto antes de mutar el store.

No dejar una semana parcialmente modificada si alguna nueva Occurrence produce
conflicto.

---

# Aplicar de aquí en adelante

Debe actualizar la configuración futura del PlanItem y regenerar planificación
desde la fecha efectiva.

Principio obligatorio:

```text
historia
→ preservar

futuro pendiente regenerable
→ retirar y volver a materializar
```

---

# No reescribir historia

No modificar automáticamente Occurrences históricas con valor real como:

```text
completed
not_completed
cancelled
in_progress
```

---

# Pending futuro

Las principales candidatas a regeneración son:

```text
fecha futura
+
status === pending
```

---

# ============================================================

# 12. CONFLICTOS Y PRIORIDADES

# ============================================================

Conservar:

```text
NORMAL      = 100
EVENT       = 200
UNEXPECTED  = 300
```

como regla derivada del dominio.

No guardar prioridad en PlanItem ni Occurrence.

---

# Override permitido

Una Occurrence nueva solamente puede desplazar automáticamente mediante
confirmación a otra cuando su prioridad sea:

```text
ESTRICTAMENTE MAYOR
```

que la prioridad de la Occurrence conflictiva.

---

# Misma prioridad

Si ambas poseen la misma prioridad:

```text
rechazar conflicto
```

No cancelar una de ellas arbitrariamente.

---

# Prioridad inferior

Si la nueva Occurrence posee prioridad menor:

```text
rechazar conflicto
```

---

# EVENT

Un Event puede desplazar mediante confirmación una Occurrence NORMAL.

---

# UNEXPECTED

Un Unexpected puede desplazar mediante confirmación:

```text
NORMAL
EVENT
```

si la regla de prioridad aplicable lo permite.

---

# Completed

No realizar override automático sobre una Occurrence:

```text
completed
```

durante MVP 04.

Aunque la nueva Occurrence tenga prioridad superior:

```text
rechazar
```

El historial realizado no se reescribe automáticamente.

---

# Confirmación

Antes de modificar la Occurrence desplazada, mostrar información equivalente a:

```text
Este registro entra en conflicto con:

Trabajo
08:00–17:00

Si continúas, Trabajo será cancelado únicamente para esta fecha.
```

Opciones:

```text
Volver
Continuar
```

---

# No cancelar silenciosamente

La Occurrence existente solo cambia a:

```text
cancelled
```

después de confirmación explícita.

---

# Cancelled / not_completed

Si la Occurrence existente ya está:

```text
cancelled
```

o:

```text
not_completed
```

su intervalo está libre.

No requiere override.

---

# ============================================================

# 13. ACCIONES CONTEXTUALES

# ============================================================

Conservar:

```text
+
✎
🗑
```

como lenguaje visual de la fila seleccionada.

---

# +

Debe continuar permitiendo una creación contextual.

Su implementación debe utilizar el nuevo formulario dinámico.

---

# Lápiz

Utiliza el diálogo de edición definido en esta tarea.

---

# Papelera

Conservar visualmente.

NO implementar todavía eliminación destructiva del historial.

No inventar su semántica definitiva durante 04.0.2.

La eliminación completa permanece en roadmap.

---

# ============================================================

# 14. RESPONSIVE

# ============================================================

MVP 04.0.2 debe funcionar aproximadamente en:

```text
1440 × 900
390 × 844
```

---

# Escritorio

Priorizar:

```text
matriz mensual completa
+
selección directa de fecha
+
navegación mensual
+
acciones contextuales
```

---

# Compacto

Priorizar:

```text
una fecha visible
+
navegación diaria
+
selector de fecha
+
navegación mensual compacta
```

---

# Formularios largos

Los formularios dinámicos pueden utilizar:

```text
scroll vertical interno del dialog
```

cuando sea necesario.

No generar overflow horizontal global.

---

# ============================================================

# 15. ACCESIBILIDAD

# ============================================================

Mantener y ampliar:

* HTML semántico;
* buttons reales;
* inputs asociados a labels;
* foco visible;
* teclado;
* Escape;
* restauración de foco;
* nombres accesibles;
* símbolos además de color.

---

# Encabezados interactivos

Los días seleccionables deben tener nombres accesibles equivalentes a:

```text
Ver planificación del lunes 17 de agosto de 2026
```

---

# Ojo

Debe anunciar su acción.

Ejemplo:

```text
Mostrar todos los registros del mes
```

y:

```text
Mostrar solo el Plan del día
```

---

# ============================================================

# 16. ARQUITECTURA

# ============================================================

No deshacer la modularización aprobada en MVP 04.0.1.

Mantener responsabilidades claras entre:

```text
data
domain
scheduling
state
utils
views
app.js
```

---

# app.js

Debe continuar siendo coordinador.

No trasladar allí:

* reglas completas de recurrencia;
* store;
* conflictos;
* renderizado completo;
* prioridad;
* cálculos temporales extensos.

---

# Store

Continúa siendo la única fuente mutable de:

```text
planItems
occurrences
```

Las vistas no deben mutar colecciones directamente.

---

# Operaciones compuestas

Las operaciones:

```text
editar semana
editar futuro
override
```

deben validarse antes de aplicar mutaciones definitivas.

Evitar estados parciales.

---

# ============================================================

# 17. NO REGRESIONES DE MVP 04.0.1

# ============================================================

Debe continuar funcionando:

* materialización weekly;
* interval_days;
* manual_dates;
* single_date;
* weekdayTimeOverrides;
* horizonte;
* extensión de horizonte;
* idempotencia;
* múltiples Occurrences por día;
* edición individual preservando ID;
* cancelled liberando horario;
* not_completed liberando horario;
* completed bloqueando;
* validación al reactivar status;
* fallback cancelled → not_completed cuando pending entra en conflicto.

---

# ============================================================

# 18. FUERA DE ALCANCE

# ============================================================

No implementar durante MVP 04.0.2:

* PostgreSQL;
* Flask;
* API;
* Supabase;
* usuarios;
* autenticación;
* despliegue;
* localStorage;
* IndexedDB;
* sincronización remota;
* estadísticas;
* gráficas;
* porcentajes;
* rachas;
* premios;
* subactividades;
* hábitos puntuales;
* hábitos por cantidad;
* actualStartTime;
* actualEndTime;
* comentarios sobre Occurrences;
* autocompletado histórico de PlanItems;
* eliminación destructiva avanzada;
* restauración automática mediante cancelledByOccurrenceId.

---

# 19. PRUEBAS OBLIGATORIAS

Antes de terminar debe contrastarse la implementación contra TODOS los
criterios activos de MVP 04.0.2 en:

```text
ACCEPTANCE_CRITERIA_MVP_04.md
```

y comprobar regresión de MVP 04.0.1.

Como mínimo comprobar:

* carga inicial;
* fecha local;
* selección de día en escritorio;
* flechas diarias;
* cruce de mes;
* selector de fecha;
* navegación mensual;
* selector de mes;
* mes vacío;
* extensión de recurrencias indefinidas;
* ojo cerrado;
* ojo abierto;
* celda no programada;
* diferentes horarios por fecha;
* separación visual semanal;
* creación Anchor;
* creación Periodic / weekly;
* creación Periodic / interval_days;
* creación Periodic / manual_dates;
* creación Event;
* creación Unexpected;
* creación Habit / scheduled;
* weekdayTimeOverrides;
* edición solo esta fecha;
* cambio de fecha;
* edición solo esta semana;
* edición de aquí en adelante;
* conservación de historia;
* regeneración de pending futuro;
* conflictos normales;
* Event sobre NORMAL;
* Unexpected sobre NORMAL;
* Unexpected sobre EVENT;
* rechazo de misma prioridad;
* rechazo de prioridad inferior;
* rechazo sobre completed;
* confirmación antes de cancelar por override;
* cancelled y not_completed liberando horario;
* transición de status inválida;
* fallback cancelled ↔ not_completed;
* teclado;
* foco;
* responsive;
* ausencia de overflow horizontal global;
* consola sin errores.

---

# 20. VERIFICACIÓN TÉCNICA

Cuando corresponda ejecutar:

```text
node --check
```

sobre todos los módulos JavaScript.

Ejecutar las pruebas existentes.

Añadir pruebas nuevas para las nuevas reglas del store/scheduling cuando la
funcionalidad sea comprobable sin navegador.

Ejecutar:

```text
git diff --check
```

---

# 21. VERIFICACIÓN VISUAL

Probar mediante servidor HTTP real.

Cuando el entorno lo permita verificar aproximadamente:

```text
1440 × 900
390 × 844
```

No afirmar funcionamiento visual basándose únicamente en lectura del código.

---

# 22. INFORME FINAL

Al terminar informar claramente:

1. archivos creados;
2. archivos modificados;
3. archivos eliminados;
4. arquitectura final;
5. selectedDate;
6. visibleMonth;
7. showAllMonthRecords;
8. selección de fecha en escritorio;
9. navegación diaria;
10. selector de fecha;
11. navegación mensual;
12. selector de mes;
13. comportamiento en meses vacíos;
14. extensión de materialización;
15. ojo cerrado;
16. ojo abierto;
17. celdas no programadas;
18. separación semanal;
19. formulario Anchor;
20. formulario Periodic;
21. formulario Event;
22. formulario Unexpected;
23. formulario Scheduled Habit;
24. weekdayTimeOverrides;
25. diálogo único de edición;
26. edición solo esta fecha;
27. edición solo esta semana;
28. edición de aquí en adelante;
29. regeneración futura;
30. conservación de historial;
31. prioridades;
32. confirmaciones de override;
33. conflictos con completed;
34. acciones contextuales;
35. comportamiento responsive;
36. accesibilidad;
37. pruebas automáticas;
38. pruebas visuales;
39. criterios no comprobados;
40. limitaciones conocidas;
41. funciones deliberadamente aplazadas;
42. instrucciones exactas para probar manualmente.

No declarar como terminado algo que no fue comprobado.

---

# Definición de terminado — MVP 04.0.2

MVP 04.0.2 está terminado cuando el usuario puede:

```text
seleccionar una fecha
↓
ver las Occurrences reales de ese día
↓
navegar entre días y meses
↓
crear planificación según su tipo
↓
editar una aparición o su recurrencia
↓
resolver conflictos de manera explícita
```

y puede alternar entre:

```text
Plan del día
```

y:

```text
Vista mensual completa
```

sin destruir:

* historial;
* integridad temporal;
* comportamiento aprobado de MVP 04.0.1.

---

# Resultado del MVP 04 completo

Al cerrar esta entrega debe existir:

```text
MVP 04.0.1
Motor temporal
        +
MVP 04.0.2
Experiencia de planificación
        =
MVP 04 completo
```

Después de este checkpoint podrá evaluarse el siguiente MVP sin necesidad de
reconstruir nuevamente el dominio temporal ni la experiencia principal de
planificación.
