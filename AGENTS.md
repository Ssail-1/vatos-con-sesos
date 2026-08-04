# AGENTS.md

## Proyecto

Este repositorio contiene la aplicación **Vatos con Sesos**.

Vatos con Sesos crecerá como un gestor personal compuesto por módulos
independientes.

Los módulos actuales son:

- `modules/dev_notes/`
- `modules/gestor_de_habitos/`

La tarea vigente corresponde exclusivamente al segundo incremento frontend
del módulo:

```text
modules/gestor_de_habitos/
```

---

# Fuentes de instrucciones

Antes de modificar código, debes leer los documentos vigentes en este orden:

1. `/AGENTS.md`
2. `/docs/codex/CURRENT_TASK.md`
3. `/docs/codex/FRONTEND_MVP_02.md`
4. `/docs/codex/MOCK_DATA_CONTRACT_MVP_02.md`
5. `/docs/codex/UI_REFERENCE.md`
6. `/docs/codex/ACCEPTANCE_CRITERIA_MVP_02.md`

Los documentos correspondientes al Frontend MVP 01 pueden consultarse
para comprender el comportamiento ya implementado, pero la tarea actual
está definida por los documentos del Frontend MVP 02.

## Documentos históricos de planeación

La carpeta:

```text
/docs/codex/planeacion/
```

contiene únicamente:

- contexto histórico;
- conversaciones de diseño;
- ideas consideradas;
- preguntas pendientes;
- funciones futuras;
- decisiones que pueden haber sido reemplazadas.

Los archivos de esa carpeta:

- no son instrucciones vigentes;
- pueden contener contradicciones;
- no deben ampliar automáticamente el alcance;
- no deben utilizarse para introducir funciones no autorizadas.

En caso de contradicción, siempre tienen prioridad los documentos normativos
enumerados en la sección anterior.

---

# Área autorizada

Puedes crear, modificar, mover o eliminar archivos únicamente dentro de:

```text
modules/gestor_de_habitos/
```

No debes modificar archivos fuera de esa carpeta.

Esto incluye, entre otros:

```text
/index.html
/css/
/js/
/docs/
/modules/dev_notes/
/README.md
/.gitignore
/AGENTS.md
```

Puedes leer archivos externos para comprender el proyecto, sus estilos o sus
decisiones, pero no puedes modificarlos.

## Si consideras necesario un cambio externo

Debes:

1. No realizarlo.
2. Identificar el archivo afectado.
3. Explicar el cambio propuesto.
4. Explicar por qué sería necesario.
5. Esperar autorización explícita.

---

# Estado estable que debe conservarse

El Frontend MVP 01 ya fue implementado y constituye el punto de partida.

La refactorización y las nuevas funciones no deben eliminar ni deteriorar:

- el tema oscuro actual;
- la paleta actual;
- el encabezado actual;
- la matriz mensual;
- la vista completa de escritorio;
- la vista compacta;
- la navegación entre días en vista compacta;
- el resaltado del día actual;
- los cinco estados;
- el ciclo multestado;
- la leyenda de estados;
- la navegación mediante teclado;
- los nombres accesibles;
- la ausencia de desplazamiento horizontal global;
- la persistencia temporal exclusivamente en memoria.

No se autoriza un rediseño visual.

Pueden realizarse pequeños ajustes de maquetación únicamente cuando sean
necesarios para integrar las nuevas funciones y no cambien la identidad
visual del módulo.

---

# Tarea actual

La tarea vigente es:

```text
Frontend MVP 02 — Creación e inserción de actividades con refactor modular
```

La definición completa se encuentra en:

```text
/docs/codex/CURRENT_TASK.md
/docs/codex/FRONTEND_MVP_02.md
```

La implementación combina dos objetivos:

1. Reorganizar el JavaScript por responsabilidades.
2. Agregar creación e inserción de actividades en memoria.

No debes realizar una refactorización puramente estética ni ampliar el
producto más allá de esta entrega.

---

# Tecnologías autorizadas

Utiliza únicamente:

- HTML;
- CSS;
- JavaScript nativo;
- módulos ES de JavaScript;
- datos simulados en memoria;
- elementos nativos del navegador.

Puedes utilizar el elemento nativo:

```html
<dialog>
```

para el formulario de creación.

No utilices:

- Flask;
- Python;
- PostgreSQL;
- Supabase;
- API;
- `localStorage`;
- IndexedDB;
- archivos JSON externos;
- React;
- Vue;
- Angular;
- frameworks CSS;
- npm;
- librerías externas;
- herramientas de compilación;
- dependencias remotas.

---

# Restricción principal de la refactorización

La refactorización debe conservar el comportamiento visible existente.

Antes de agregar nuevas funciones debes comprobar que continúan funcionando:

- renderizado del mes;
- orden de actividades;
- cálculo de duración;
- cambio de estados;
- navegación compacta;
- resaltado del día seleccionado;
- accesibilidad de los controles.

No reescribas todo sin necesidad.

Reutiliza la lógica correcta del Frontend MVP 01 y distribúyela por
responsabilidades.

---

# Arquitectura JavaScript esperada

La estructura objetivo es:

```text
modules/gestor_de_habitos/
├── index.html
├── css/
│   └── gestor_habitos.css
└── js/
    ├── data/
    │   └── mock-activities.js
    ├── domain/
    │   └── activity-status.js
    ├── state/
    │   └── activity-store.js
    ├── utils/
    │   └── date-time.js
    ├── views/
    │   ├── activity-matrix.js
    │   └── activity-form.js
    └── app.js
```

Puedes realizar un ajuste menor a esta estructura si existe una razón técnica
clara, pero debes explicarlo y no crear más capas de las necesarias.

## Responsabilidades

### `data/mock-activities.js`

Contiene únicamente:

- datos iniciales de demostración;
- estados iniciales de demostración.

No debe manipular el DOM.

### `domain/activity-status.js`

Contiene:

- estados permitidos;
- símbolos;
- etiquetas;
- ciclo de estados;
- funciones relacionadas con la representación de estados.

No debe almacenar la lista de actividades.

### `state/activity-store.js`

Representa la fuente de datos en memoria.

Debe encargarse de operaciones como:

- obtener actividades;
- ordenar actividades;
- agregar una actividad;
- insertar una actividad antes de otra;
- cambiar el estado para una fecha;
- renumerar posiciones cuando sea necesario.

No debe construir elementos HTML.

### `utils/date-time.js`

Contiene:

- formato de claves `YYYY-MM-DD`;
- comparación de fechas;
- cálculo de días del mes;
- formateo de fechas;
- cálculo de duración;
- validación de horarios.

No debe manipular el estado global ni el DOM.

### `views/activity-matrix.js`

Contiene:

- creación del encabezado;
- creación de filas;
- creación de botones de estado;
- renderizado de la matriz;
- resaltado del día actual;
- resaltado del día seleccionado;
- selección visual de una fila;
- botón contextual de inserción.

No debe definir los datos iniciales.

### `views/activity-form.js`

Contiene:

- apertura del diálogo;
- cierre del diálogo;
- lectura de campos;
- mensajes de validación;
- detección de cambios;
- reinicio del formulario;
- coordinación visual del modo de inserción.

No debe insertar directamente actividades dentro del arreglo.

### `app.js`

Debe funcionar como coordinador general.

Sus responsabilidades serán:

- inicializar la aplicación;
- obtener referencias principales;
- conectar el store con las vistas;
- manejar la fecha seleccionada;
- solicitar renderizados;
- recibir una actividad validada desde el formulario;
- enviarla al store;
- volver a renderizar.

`app.js` debe quedar suficientemente pequeño para que su flujo general pueda
comprenderse mediante una lectura.

---

# Módulos ES

El punto de entrada debe cargarse mediante:

```html
<script type="module" src="./js/app.js"></script>
```

Los demás archivos deben utilizar:

```js
export
import
```

No deben cargarse todos individualmente desde el HTML.

La aplicación debe probarse mediante Live Server o un servidor local.

---

# Estilo de código

## Organización

- Mantener funciones pequeñas.
- Una función debe tener una responsabilidad principal.
- Evitar código duplicado.
- Evitar variables globales innecesarias.
- No crear clases cuando una función o un objeto sean suficientes.
- No fragmentar una operación trivial en numerosos archivos.
- No agregar abstracciones preparadas para funciones todavía inexistentes.

## Nombres

Utilizar nombres técnicos en inglés dentro del código.

Ejemplos:

```js
selectedDate
selectedActivityId
plannedStartTime
plannedEndTime
insertActivityBefore
renderActivityMatrix
openActivityForm
```

El contenido visible de la interfaz debe estar en español.

## Comentarios

Comentar por bloques funcionales.

Los comentarios deben explicar:

- propósito;
- regla de negocio;
- comportamiento poco evidente;
- decisión responsive;
- interacción entre módulos.

Ejemplo correcto:

```js
// Inserta la actividad antes de la fila seleccionada y renumera posiciones
```

Evitar:

```js
// Se crea una constante
```

---

# Creación de actividades

La entrega debe permitir registrar una nueva actividad con:

- nombre;
- hora planeada de inicio;
- hora planeada de finalización.

La duración se calculará a partir de las horas.

La actividad nueva:

- existirá únicamente en memoria;
- tendrá un identificador único generado en el frontend;
- comenzará con estado `pending`;
- conservará la estructura del contrato de datos vigente;
- podrá insertarse al final o antes de una actividad seleccionada.

No se deben agregar todavía:

- tipo de actividad;
- recurrencia;
- subactividades;
- comentarios;
- tiempos reales;
- prioridades;
- categorías;
- unidades cuantitativas.

---

# Inserción contextual

Cada fila puede seleccionarse mediante:

- clic;
- foco mediante teclado, cuando corresponda.

La fila seleccionada debe distinguirse visualmente sin cambiar la identidad
general del diseño.

Cuando exista una fila seleccionada debe mostrarse un botón circular `+`
asociado a esa fila.

El botón:

- debe tener borde visible;
- debe mantener un fondo claro o contrastante;
- debe mostrar un símbolo `+`;
- debe tener nombre accesible;
- debe poder usarse con teclado;
- debe abrir el formulario en modo `insert-before`;
- debe indicar que la nueva actividad se insertará antes de esa fila.

No debe ocultar el nombre, la hora ni los controles de estado.

La posición exacta puede adaptarse a la tabla web, pero debe conservar la
idea visual de un control contextual ubicado cerca del comienzo superior
de la fila.

---

# Orden de las actividades

La matriz debe mantener orden cronológico:

1. `plannedStartTime`;
2. `position`.

El botón contextual registra la intención de insertar antes de una fila.

Para mantener coherencia:

- el formulario debe tomar como referencia la actividad seleccionada;
- puede sugerir inicialmente la hora de la fila seleccionada;
- la nueva actividad recibe una posición anterior a la referencia;
- después se renumeran las posiciones;
- el orden cronológico por hora sigue teniendo prioridad.

Si el usuario introduce una hora posterior, la actividad debe aparecer en
la posición cronológica correspondiente, aunque haya abierto el formulario
desde una fila anterior.

No se deben inventar ni recorrer horarios automáticamente.

---

# Formulario de actividad

El formulario puede presentarse mediante un `<dialog>` nativo.

Debe incluir:

- campo de nombre;
- campo de hora inicial;
- campo de hora final;
- botón para guardar;
- botón para cancelar;
- mensaje de error accesible.

## Validaciones

- El nombre es obligatorio.
- El nombre no debe quedar compuesto únicamente por espacios.
- La hora inicial es obligatoria.
- La hora final es obligatoria.
- La hora final debe ser posterior a la inicial.
- No se admiten actividades que crucen la medianoche.
- No se admite `24:00`.
- No se debe guardar si existen errores.

## Cancelación

Cancelar o cerrar el diálogo:

- no agrega actividades;
- no modifica datos;
- limpia los errores;
- limpia el modo de inserción anterior.

En esta entrega no se requiere confirmación por cambios sin guardar.

---

# Estados de actividad

Los únicos estados continúan siendo:

```text
pending
in_progress
completed
not_completed
cancelled
```

El ciclo obligatorio continúa siendo:

```text
pending
→ in_progress
→ completed
→ not_completed
→ cancelled
→ pending
```

La refactorización no debe alterar símbolos, colores, etiquetas ni
accesibilidad actuales.

---

# Responsive

## Escritorio amplio

Debe conservar:

- todos los días del mes;
- matriz completa;
- información temporal;
- nombre de la actividad;
- controles de estado;
- día actual resaltado.

Los nuevos botones no deben deformar la matriz.

## Vista compacta

Debe conservar:

- una sola fecha visible;
- navegación entre días;
- posición;
- hora;
- duración;
- nombre;
- estado de la fecha seleccionada.

El formulario debe caber dentro del viewport.

No debe aparecer scroll horizontal global.

El botón contextual debe ser utilizable sin tapar contenido.

---

# Accesibilidad mínima

- Utilizar botones reales para acciones.
- Utilizar etiquetas asociadas a campos.
- Mantener foco visible.
- Gestionar correctamente el foco al abrir y cerrar el diálogo.
- Proporcionar mensajes de error comprensibles.
- No depender únicamente del color.
- Permitir el uso mediante teclado.
- Dar un nombre accesible al botón contextual `+`.
- Dar un nombre accesible al botón general de agregar.

---

# Fuera de alcance

No implementar en esta entrega:

- edición de actividades existentes;
- eliminación de actividades;
- seguimiento temporal expandido;
- horas reales;
- comentarios;
- subactividades;
- recurrencias;
- hábitos cuantitativos;
- persistencia;
- backend;
- base de datos;
- API;
- estadísticas;
- porcentajes;
- rachas;
- reajuste de horarios;
- autenticación;
- integración con la aplicación principal;
- despliegue.

---

# Forma de trabajo

Antes de modificar código debes responder con:

1. Tu comprensión de la entrega.
2. Los archivos que crearás, moverás o modificarás.
3. El mapa de responsabilidades después del refactor.
4. Cómo comprobarás que no cambió el comportamiento del MVP 01.
5. Cómo implementarás el formulario.
6. Cómo implementarás el botón contextual.

Después debes esperar autorización explícita antes de editar, salvo que el
prompt del usuario indique claramente que ya estás autorizado para comenzar.

---

# Git

No debes:

- ejecutar `git commit`;
- ejecutar `git push`;
- ejecutar `git merge`;
- cambiar de rama;
- modificar `main`;
- borrar historial;
- usar comandos destructivos;
- restaurar archivos sin autorización.

Puedes utilizar comandos no destructivos para inspeccionar y probar.

---

# Seguridad

- No crear credenciales.
- No usar servicios externos.
- No introducir datos personales reales.
- No crear archivos `.env`.
- No ejecutar comandos destructivos.

---

# Finalización

La tarea se considera terminada únicamente cuando cumple todos los criterios
de:

```text
/docs/codex/ACCEPTANCE_CRITERIA_MVP_02.md
```

Al finalizar debes informar:

- archivos creados;
- archivos movidos;
- archivos modificados;
- pruebas realizadas;
- comportamiento conservado;
- nueva funcionalidad implementada;
- limitaciones;
- criterios que no pudiste verificar.
