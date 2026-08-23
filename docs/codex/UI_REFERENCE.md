
# Referencias visuales — MVP 04

## Proyecto

**Vatos con Sesos**

Submódulo actual:

```text
Vatos con Sesos
└── Gestor de hábitos
    └── Plan del día
```

---

# Propósito de este documento

Este archivo explica cómo deben interpretarse las referencias visuales
disponibles dentro de:

```text
/docs/codex/assets/
```

y especialmente:

```text
/docs/codex/assets/assets-MVP04/
```

Las imágenes sirven para comunicar:

* intención visual;
* posición aproximada de controles;
* comportamiento esperado;
* jerarquía;
* responsive;
* ideas futuras.

NO todas las imágenes representan funcionalidad autorizada para la entrega
actual.

---

# Regla fundamental

Las imágenes son:

```text
REFERENCIAS
```

NO son:

```text
ESPECIFICACIONES PIXEL PERFECT
```

Codex no debe intentar reproducir exactamente:

* dimensiones;
* colores;
* tipografías;
* espacios;
* bordes;
* proporciones;

cuando eso contradiga la identidad visual actual del módulo.

---

# Identidad visual vigente

La interfaz construida durante MVP 01, MVP 02 y MVP 03 es el baseline.

Debe conservarse:

* tema oscuro;
* acentos dorados;
* tabla oscura;
* bordes discretos;
* botones de estado;
* tarjetas;
* tipografía actual;
* estilo del encabezado;
* enlace Vatos con Sesos;
* fila seleccionada;
* acciones contextuales.

Las referencias nuevas deben integrarse en esta identidad.

---

# ============================================================

# REFERENCIAS GENERALES HISTÓRICAS

# ============================================================

Las siguientes imágenes existen fuera de `assets-MVP04`.

---

# `Ejemplo-objetivo-plantilla.png`

Ruta:

```text
/docs/codex/assets/Ejemplo-objetivo-plantilla.png
```

## Representa

La inspiración original basada en la hoja de cálculo utilizada anteriormente.

Ayuda a comprender conceptos como:

* filas de actividades;
* días distribuidos horizontalmente;
* matriz mensual;
* estados por día;
* estructura general tipo planificador.

## NO representa

No debe copiarse literalmente:

* diseño;
* colores;
* estructura exacta;
* estadísticas;
* fórmulas de spreadsheet.

La aplicación actual ya desarrolló una identidad propia.

---

# `Seguimiento temporal resumido sin cambios registrados.png`

Ruta:

```text
/docs/codex/assets/
Seguimiento temporal resumido sin cambios registrados.png
```

## Representa

Una versión conceptual compacta del Plan del día.

Sirve para comprender:

* horario;
* duración;
* actividad;
* filas;
* información esencial.

---

# `Seguimiento temporal colapsado con cambios registrados.png`

Ruta:

```text
/docs/codex/assets/
Seguimiento temporal colapsado con cambios registrados.png
```

## Representa

La intención histórica de adaptar la información cuando el espacio horizontal
es reducido.

Sirve como referencia conceptual para responsive.

No obliga a copiar exactamente la estructura mostrada.

---

# `acciones-contextuales-fila.png`

Ruta:

```text
/docs/codex/assets/acciones-contextuales-fila.png
```

## Importancia

Esta referencia continúa siendo relevante y debe respetarse.

Representa la intención visual para las acciones de una fila seleccionada.

---

# Botón contextual +

El botón:

```text
+
```

debe aparecer asociado visualmente a la esquina superior izquierda de la celda
del nombre de la actividad.

La intención es aproximadamente:

```text
                    +
                    │
                    ▼
┌──────────┬────────┬──────────────────────────────────────┐
│ 20:20    │ 20min  │ SQL                         ✎   🗑  │
└──────────┴────────┴──────────────────────────────────────┘
```

No debe convertirse en una columna permanente.

---

# Editar y eliminar

Las acciones:

```text
✎
🗑
```

deben permanecer dentro de la zona derecha de la celda correspondiente al
nombre.

Solo deben mostrarse cuando la fila esté seleccionada.

---

# ============================================================

# REFERENCIAS ESPECÍFICAS DEL MVP 04

# ============================================================

Las siguientes referencias se encuentran en:

```text
/docs/codex/assets/assets-MVP04/
```

---

# `selector-fecha-desktop.png`

## Representa

La intención de ofrecer un calendario emergente para seleccionar una fecha.

El usuario debe poder:

```text
seleccionar fecha
↓
cambiar selectedDate
↓
ver el Plan del día correspondiente
```

## Implementación esperada

Preferir controles nativos:

```html
<input type="date">
```

y:

```js
showPicker()
```

cuando exista soporte.

## NO hacer

No construir un calendario completo propio únicamente para copiar la imagen.

La imagen representa:

```text
INTERACCIÓN
```

no:

```text
IMPLEMENTACIÓN EXACTA
```

---

# `selector-fecha-mobile.png`

## Representa

La misma intención anterior aplicada a pantalla compacta.

La experiencia debe:

* caber en viewport;
* ser usable con touch;
* permitir cambiar rápidamente selectedDate.

Puede utilizar el selector nativo ofrecido por el navegador móvil.

---

# `flechas-para-navegar-meses-en-pantalla-completa.png`

## Representa

La intención de añadir navegación mensual alrededor de la matriz.

Conceptualmente:

```text
‹                                            ›

┌──────────────────────────────────────────────┐
│                 MATRIZ                       │
└──────────────────────────────────────────────┘
```

Las flechas corresponden a:

```text
navegación entre meses
```

NO:

```text
navegación entre días
```

---

# Posición aproximada

Las flechas pueden aparecer:

* a los laterales de la matriz;
* integradas dentro de su contenedor;
* visualmente flotantes;

siempre que:

* sean fáciles de encontrar;
* no cubran información;
* no generen overflow;
* mantengan accesibilidad.

---

# `flechas-para-navegar-meses-en-pantalla-pequeña.png`

## Representa

La adaptación de la navegación mensual a pantalla compacta.

Conceptualmente:

```text
‹     Agosto de 2026     ›
```

El nombre del mes puede actuar además como selector directo.

---

# Diferencia importante

En compacto existirán dos niveles de navegación.

## Navegación diaria

```text
←     Jueves, 20 de Agosto     →
```

Cambia:

```text
selectedDate ± 1 día
```

## Navegación mensual

```text
‹     Agosto de 2026     ›
```

Cambia:

```text
visibleMonth
```

Codex NO debe mezclar ambos comportamientos.

---

# `Visualizacion-por-semanas.png`

## Representa

La intención de separar visualmente las semanas dentro de la matriz mensual.

La semana lógica es:

```text
lunes → domingo
```

---

# La matriz continúa siendo una sola

NO crear:

```text
Tabla semana 1
Tabla semana 2
Tabla semana 3
Tabla semana 4
```

Debe continuar existiendo:

```text
UNA MATRIZ MENSUAL
```

con separaciones visuales.

---

# Opciones visuales permitidas

Puede utilizarse:

* borde vertical más fuerte;
* diferencia sutil de background;
* degradado discreto;
* alternancia ligera de opacidad;
* combinación de borde + fondo.

---

# Ejemplo conceptual

Si el mes comienza sábado:

```text
 S   D ║ L   M   X   J   V   S   D ║ L ...
 1   2 ║ 3   4   5   6   7   8   9 ║ 10...
```

El primer bloque puede ser parcial.

---

# Inspiración tipo spreadsheet

Puede utilizarse una diferenciación parecida a una hoja de cálculo:

```text
semana A
→ fondo base

semana B
→ misma gama con opacidad ligeramente distinta

semana C
→ fondo base
```

La diferencia debe ser sutil.

No crear un diseño multicolor.

---

# ============================================================

# REFERENCIAS DE VISIÓN FUTURA

# ============================================================

Las siguientes imágenes NO representan funcionalidad autorizada actualmente.

---

# `borrador-representación-futura-estadística.png`

Ruta:

```text
/docs/codex/assets/assets-MVP04/
borrador-representación-futura-estadística.png
```

---

# `objetivo-a-futuro-2.png`

Ruta:

```text
/docs/codex/assets/assets-MVP04/
objetivo-a-futuro-2.png
```

---

# `objetivo-a-futuro-3.png`

Ruta:

```text
/docs/codex/assets/assets-MVP04/
objetivo-a-futuro-3.png
```

---

# Qué representan

Estas imágenes muestran ideas futuras relacionadas con:

* porcentaje diario;
* porcentaje semanal;
* porcentaje mensual;
* progreso;
* gráficas;
* rachas;
* premios;
* histórico.

---

# IMPORTANTE

Estas imágenes existen únicamente para garantizar que el diseño actual no
bloquee esa evolución.

Codex NO debe implementar a partir de ellas:

* gráficas;
* SVG estadísticos;
* porcentajes;
* barras;
* rachas;
* premios;
* dashboards;
* cálculos de productividad.

---

# Su valor actual

Sí pueden utilizarse para comprender que el modelo futuro necesitará:

```text
día
↓
semana
↓
mes
```

y que por ello la separación semanal de la matriz tiene valor.

Nada más.

---

# ============================================================

# MATRIZ MENSUAL

# ============================================================

La matriz actual es una pieza central del producto.

No sustituirla por:

* cards independientes;
* calendario tradicional;
* lista vertical completa;
* layout tipo agenda externo;

durante MVP 04.

---

# Escritorio

En espacio amplio debe mantenerse la idea:

```text
# | Inicio | Duración | Actividad | días del mes...
```

---

# Compacto

En espacio reducido debe mantenerse:

```text
# | Inicio | Duración | Actividad | fecha seleccionada
```

No intentar comprimir 31 columnas dentro de una pantalla pequeña.

---

# Día seleccionado

La columna seleccionada utiliza actualmente acento dorado.

Conservar esta intención.

---

# Encabezados de fecha en MVP 04.0.2

En escritorio los encabezados deben convertirse en controles.

Ejemplo:

```text
LUN
17
```

Debe poder pulsarse para seleccionar esa fecha.

Visualmente continúa pareciendo una celda del encabezado.

---

# ============================================================

# MODO OJO CERRADO / OJO ABIERTO

# ============================================================

Aunque no existe todavía una captura específica obligatoria, la intención
visual debe integrarse dentro del encabezado de:

```text
SEGUIMIENTO MENSUAL
Plan del día
```

---

# Ojo cerrado

Representa:

```text
mostrar solamente registros correspondientes a selectedDate
```

Es el estado inicial.

---

# Ojo abierto

Representa:

```text
mostrar todos los PlanItems presentes en visibleMonth
```

---

# Control visual

Puede usarse:

* ojo abierto/cerrado;
* icono equivalente;
* botón de alternancia.

Debe incluir nombre accesible.

No depender únicamente del icono.

---

# ============================================================

# CELDAS NO PROGRAMADAS

# ============================================================

Con ojo abierto existirán PlanItems visibles en fechas donde no poseen
Occurrence.

Estas celdas deben diferenciarse visualmente.

---

# Apariencia esperada

Conceptualmente:

```text
fondo gris
sin símbolo
sin interacción
```

---

# No confundir

La celda no programada:

```text
NO ES pending
NO ES cancelled
NO ES not_completed
```

Representa únicamente:

```text
No existe Occurrence.
```

---

# ============================================================

# DIÁLOGOS

# ============================================================

El diseño actual de `<dialog>` construido durante MVP 02/MVP 03 debe
conservarse como baseline.

No reemplazarlo por una librería de modal.

---

# Diálogo de edición

Debe evolucionar hacia una única interfaz dinámica.

Conceptualmente:

```text
┌────────────────────────────────────────────┐
│ Editar — Gym                               │
│                                            │
│ Hora de inicio       Hora final            │
│ [05:30]              [07:00]               │
│                                            │
│ Fecha                                      │
│ [20/08/2026]                               │
│                                            │
│ Repetición                                 │
│ ☑ L  ☐ M  ☑ X  ☐ J  ☑ V  ☐ S  ☐ D       │
│                                            │
│ [Solo esta semana]                         │
│ [De aquí en adelante]                      │
│                                            │
│                     [Cancelar] [Aceptar]   │
└────────────────────────────────────────────┘
```

Esta representación es conceptual.

No copiar tamaños exactos.

---

# Interfaz progresiva

El diálogo debe mostrar complejidad solamente cuando sea necesaria.

Ejemplo:

Si se cambia únicamente:

```text
05:30
↓
06:00
```

no debe obligar al usuario a tomar decisiones sobre toda la recurrencia.

---

# Cambio de recurrencia

Si cambia:

```text
L X V
↓
L J
```

entonces sí aparecen las decisiones de alcance.

---

# ============================================================

# FORMULARIOS POR CLASIFICACIÓN

# ============================================================

Las interfaces deben adaptarse según:

```text
Activity / Anchor
Activity / Periodic
Activity / Event
Activity / Unexpected
Habit / Scheduled
```

No mostrar todos los campos posibles simultáneamente.

---

# Anchor

Interfaz orientada a:

```text
días de semana
horarios
desde
hasta / indefinidamente
```

---

# Periodic

Interfaz orientada a elegir:

```text
Días de semana

Cada N días

Fechas específicas
```

---

# Event

Interfaz orientada a:

```text
fecha concreta
+
horario
```

o varias fechas manuales.

---

# Unexpected

Interfaz simple orientada a:

```text
selectedDate
+
horario
```

---

# Scheduled Habit

Interfaz orientada inicialmente a:

```text
días
+
horario
```

Continúa siendo un bloque temporal durante MVP 04.

---

# ============================================================

# ELIMINACIÓN

# ============================================================

La referencia:

```text
🗑
```

forma parte del diseño contextual.

Debe conservarse.

---

# Estado actual

La semántica definitiva de eliminación todavía no está cerrada.

Por tanto la existencia visual de la papelera:

```text
NO autoriza borrar historial de forma destructiva.
```

---

# Futuro

La acción probablemente deberá distinguir:

```text
Quitar esta aparición

Detener de aquí en adelante

Cancelar
```

Esto se documentará en una entrega posterior.

---

# ============================================================

# RESPONSIVE

# ============================================================

Las referencias deben interpretarse bajo la siguiente prioridad:

## Escritorio

```text
máxima información temporal visible
```

## Compacto

```text
máxima legibilidad del día seleccionado
```

No intentar preservar la misma cantidad de columnas en ambos tamaños.

---

# Touch

En compacto:

* fechas;
* flechas;
* botones de estado;
* acciones contextuales;

deben tener áreas razonables de interacción.

---

# No superposición

Ningún control debe cubrir información relevante.

Especialmente:

```text
+
✎
🗑
```

---

# ============================================================

# ACCESIBILIDAD VISUAL

# ============================================================

Las imágenes muestran intención estética.

La implementación real debe respetar además:

* foco visible;
* teclado;
* labels;
* aria-label cuando corresponda;
* contraste suficiente;
* símbolos además de color.

---

# Prioridad en caso de conflicto

Si copiar exactamente una referencia visual perjudica:

* accesibilidad;
* responsive;
* legibilidad;
* integridad de layout;

debe preferirse la solución funcional y accesible.

---

# ============================================================

# REFERENCIA VS REQUISITO

# ============================================================

Interpretar las imágenes según estas categorías.

---

# Categoría A — Referencia activa

Puede influir directamente en MVP 04:

```text
acciones-contextuales-fila.png

selector-fecha-desktop.png

selector-fecha-mobile.png

flechas-para-navegar-meses-en-pantalla-completa.png

flechas-para-navegar-meses-en-pantalla-pequeña.png

Visualizacion-por-semanas.png
```

---

# Categoría B — Referencia histórica

Sirve para comprender el origen del producto:

```text
Ejemplo-objetivo-plantilla.png

Seguimiento temporal resumido sin cambios registrados.png

Seguimiento temporal colapsado con cambios registrados.png
```

No copiar literalmente.

---

# Categoría C — Visión futura

NO implementar actualmente:

```text
borrador-representación-futura-estadística.png

objetivo-a-futuro-2.png

objetivo-a-futuro-3.png
```

---

# Regla final

Las referencias visuales deben ayudar a responder:

```text
¿qué experiencia espera el usuario?
```

No deben utilizarse para inventar:

```text
¿qué otras funciones podríamos agregar?
```

Cuando una imagen muestre una función no autorizada por:

```text
CURRENT_TASK.md
FRONTEND_MVP_04.md
ACCEPTANCE_CRITERIA_MVP_04.md
```

prevalece el alcance normativo.

La referencia visual nunca amplía por sí sola el MVP.
