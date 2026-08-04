# Tarea actual

## Nombre

Frontend MVP 02 — Creación e inserción de actividades con refactor modular.

## Estado previo

El Frontend MVP 01 está implementado y funciona correctamente.

Actualmente permite:

- mostrar el mes actual;
- representar una matriz mensual;
- renderizar siete actividades simuladas;
- calcular duración estimada;
- mostrar todos los días en escritorio;
- mostrar una sola fecha en vista compacta;
- navegar entre días en vista compacta;
- resaltar la fecha actual;
- cambiar entre cinco estados;
- utilizar los controles mediante teclado;
- conservar cambios en memoria hasta recargar.

Esta entrega debe construirse sobre esa implementación.

No se autoriza reemplazarla por una interfaz diferente.

---

# Objetivo general

Realizar una segunda entrega funcional que combine:

1. Refactor modular del JavaScript existente.
2. Creación de actividades mediante formulario.
3. Inserción de actividades al final de la lista.
4. Inserción contextual antes de una fila seleccionada.
5. Actualización inmediata de la matriz.
6. Conservación de los datos exclusivamente en memoria.

La finalidad del refactor es hacer que el código sea comprensible y
prepararlo para las siguientes funciones, no crear arquitectura innecesaria.

---

# Objetivo visible para el usuario

Al terminar la entrega, el usuario podrá:

1. Abrir el Gestor de Hábitos.
2. Ver exactamente la matriz que ya existe.
3. Pulsar un botón general `Agregar actividad`.
4. Completar nombre, hora inicial y hora final.
5. Guardar la actividad.
6. Verla inmediatamente dentro de la matriz.
7. Seleccionar una fila.
8. Pulsar un botón circular `+` relacionado con esa fila.
9. Crear una actividad tomando esa fila como referencia.
10. Continuar cambiando estados como antes.

Al recargar la página, las actividades agregadas desaparecerán.

Eso es correcto para esta entrega.

---

# Refactor obligatorio

El JavaScript actual debe reorganizarse usando módulos ES.

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

Los archivos anteriores:

```text
js/mock-data.js
js/status-control.js
```

pueden moverse, dividirse o eliminarse después de que su contenido haya sido
integrado correctamente en la nueva estructura.

No deben quedar dos implementaciones activas de la misma función.

---

# Regla de preservación

Antes de implementar el formulario, debe comprobarse que la versión
refactorizada conserva:

- el mismo conjunto inicial de actividades;
- el mismo orden;
- las mismas duraciones;
- los mismos estados de demostración;
- el mismo ciclo de estados;
- el mismo mes;
- la misma fecha seleccionada;
- el mismo responsive;
- la misma apariencia;
- la misma accesibilidad básica.

El refactor no se considera correcto si solamente “se ve parecido”, pero
pierde alguna interacción existente.

---

# Botón general para crear una actividad

Debe agregarse un botón visible con texto equivalente a:

```text
+ Agregar actividad
```

Debe ubicarse en un lugar coherente con el encabezado de la matriz.

El botón:

- debe ser visible en escritorio;
- debe ser visible en vista compacta;
- debe funcionar con teclado;
- debe tener foco visible;
- debe abrir el formulario en modo normal;
- debe crear la actividad sin una referencia contextual.

Al guardar desde este botón, la actividad se integra y posteriormente se
ordena cronológicamente.

---

# Selección de una fila

Una fila puede seleccionarse mediante clic.

La fila seleccionada debe recibir una clase visual equivalente a:

```text
is-selected
```

Solo puede existir una fila seleccionada a la vez.

La selección debe:

- identificar la actividad de referencia;
- distinguirse mediante borde, fondo o acento sutil;
- no alterar los estados;
- no activar accidentalmente un cambio de estado;
- no impedir el uso de los botones de la fila.

Pulsar un control de estado no debe considerarse una solicitud de inserción.

---

# Botón contextual `+`

Cuando exista una fila seleccionada se mostrará un botón circular con el
símbolo:

```text
+
```

Su intención visual es representar:

> Agregar una nueva actividad antes de esta fila.

Debe aparecer cerca del inicio superior de la fila seleccionada.

La adaptación exacta a HTML y a una tabla queda a criterio técnico, siempre
que:

- sea visible;
- no tape información;
- no cambie el ancho general de todas las filas;
- mantenga la personalidad visual existente;
- funcione con teclado;
- tenga un `aria-label` descriptivo.

Ejemplo de etiqueta:

```text
Agregar una actividad antes de Gym - Pecho
```

Al pulsarlo:

1. Se abre el formulario.
2. El formulario entra en modo `insert-before`.
3. Se conserva el identificador de la actividad de referencia.
4. Se puede sugerir la hora inicial de esa actividad.
5. Guardar inserta la nueva actividad con una posición previa.
6. Las posiciones se renumeran.
7. El resultado final se ordena por hora y posición.

La hora elegida por el usuario tiene prioridad cronológica.

---

# Formulario de creación

Debe implementarse con un elemento nativo:

```html
<dialog>
```

El formulario debe incluir:

## Nombre

```html
<input type="text">
```

Reglas:

- obligatorio;
- eliminar espacios exteriores;
- no aceptar únicamente espacios;
- límite razonable de caracteres.

## Hora inicial

```html
<input type="time">
```

Reglas:

- obligatoria;
- formato de 24 horas administrado por el control nativo.

## Hora final

```html
<input type="time">
```

Reglas:

- obligatoria;
- posterior a la hora inicial;
- no puede representar una actividad que cruce la medianoche.

## Acciones

Debe incluir:

- Guardar;
- Cancelar.

Guardar solo está permitido cuando el formulario es válido.

Cancelar:

- cierra el diálogo;
- no modifica datos;
- limpia errores;
- elimina la referencia contextual;
- reinicia los campos.

---

# Mensajes de validación

Los errores deben mostrarse dentro del diálogo.

No deben utilizarse únicamente:

```js
alert()
```

Debe existir una región accesible para mensajes.

Ejemplos:

```text
Escribe el nombre de la actividad.
Selecciona una hora de inicio.
Selecciona una hora de finalización.
La hora final debe ser posterior a la hora inicial.
```

El primer campo inválido debe recibir foco cuando sea razonable.

---

# Creación del objeto

Una actividad nueva debe respetar el contrato del Frontend MVP 02.

Conceptualmente:

```js
{
    id: "identificador-generado",
    name: "Nombre de la actividad",
    position: 8,
    plannedStartTime: "10:00",
    plannedEndTime: "10:30",
    statesByDate: {}
}
```

El identificador puede generarse usando:

```js
crypto.randomUUID()
```

Debe existir una alternativa segura si el entorno no ofrece esa función.

La actividad comienza en estado `pending` para todas las fechas sin registro.

---

# Actualización de la matriz

Después de guardar:

1. El diálogo se cierra.
2. El store actualiza sus datos.
3. Las actividades se ordenan.
4. Las posiciones se renumeran.
5. La matriz se vuelve a renderizar.
6. La actividad nueva aparece sin recargar.
7. Los controles de estado continúan funcionando.
8. La fecha seleccionada continúa siendo la misma.
9. La fila anteriormente seleccionada puede dejar de estar seleccionada.
10. No aparece scroll horizontal global.

---

# Responsive

## Escritorio

Debe conservarse la matriz completa con todos los días.

Los botones nuevos deben integrarse sin desplazar o deformar excesivamente
las columnas.

## Vista compacta

Debe conservarse una sola fecha visible.

El botón general debe seguir disponible.

El diálogo debe:

- caber dentro del viewport;
- permitir desplazamiento interno si fuera necesario;
- no generar scroll horizontal;
- mantener campos y botones legibles.

El botón contextual debe permanecer accesible sin cubrir el nombre de la
actividad.

---

# Persistencia

No existe persistencia definitiva.

Todos los cambios viven en memoria.

Al recargar:

- se restauran las actividades iniciales;
- desaparecen las actividades creadas;
- se restauran los estados iniciales.

La interfaz debe seguir mostrando el aviso correspondiente.

---

# Fuera de alcance

No implementar todavía:

- edición;
- eliminación;
- comentarios;
- seguimiento temporal expandido;
- tiempos reales;
- recurrencias;
- calendario configurable;
- subactividades;
- actividad ancla;
- actividad periódica;
- actividad imprevista;
- hábitos cuantitativos;
- persistencia;
- Flask;
- PostgreSQL;
- API;
- estadísticas;
- reajuste automático;
- integración con Vatos con Sesos.

---

# Resultado esperado

La entrega debe demostrar un flujo vertical completo:

```text
Usuario abre formulario
        ↓
Ingresa datos
        ↓
Frontend valida
        ↓
Store agrega la actividad
        ↓
Matriz vuelve a renderizar
        ↓
Usuario cambia su estado
```

No basta con construir solamente el formulario o solamente reorganizar
archivos.

---

# Entrega de Codex

Al finalizar debe informar:

1. Archivos creados.
2. Archivos movidos.
3. Archivos eliminados.
4. Archivos modificados.
5. Mapa final de responsabilidades.
6. Pruebas de regresión del MVP 01.
7. Pruebas de creación.
8. Pruebas de validación.
9. Pruebas del botón contextual.
10. Pruebas responsive.
11. Criterios no comprobados.
12. Instrucciones para abrir y probar.
