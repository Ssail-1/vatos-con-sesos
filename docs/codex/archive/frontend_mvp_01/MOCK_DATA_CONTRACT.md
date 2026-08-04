# Contrato de datos simulados

## Propósito

Durante el Frontend MVP 01, la interfaz debe funcionar con datos simulados almacenados en JavaScript.

Todavía no se utilizarán:

- Flask;
- PostgreSQL;
- Supabase;
- API;
- `localStorage`;
- persistencia definitiva.

Los datos solamente permanecerán mientras la página esté abierta. Al recargarla, podrán regresar a su estado inicial.

## Regla principal

Las actividades deben renderizarse desde objetos JavaScript.

No se debe escribir manualmente una fila HTML diferente para cada actividad.

El flujo esperado es:

```text
Datos simulados
    ↓
Función de renderizado
    ↓
Interfaz visual
```

En una implementación futura, los datos simulados podrán sustituirse por datos obtenidos desde una API sin tener que reconstruir toda la interfaz.

---

# Estructura de una actividad simulada

Cada actividad tendrá una estructura conceptual como esta:

```js
{
    id: "gym-pecho",
    name: "Gym - Pecho",
    position: 1,
    plannedStartTime: "05:30",
    plannedEndTime: "07:15",
    statesByDate: {
        "2026-08-01": "completed",
        "2026-08-02": "pending"
    }
}
```

## Campos

### `id`

Identificador único de la actividad.

Debe ser un texto estable y no repetido.

Ejemplo:

```js
id: "gym-pecho"
```

### `name`

Nombre que se mostrará dentro de la fila.

Ejemplo:

```js
name: "Gym - Pecho"
```

### `position`

Número utilizado como orden secundario cuando dos actividades tengan la misma hora de inicio.

Ejemplo:

```js
position: 1
```

### `plannedStartTime`

Hora planeada de inicio.

Debe utilizar formato de 24 horas:

```text
HH:MM
```

Ejemplo:

```js
plannedStartTime: "05:30"
```

### `plannedEndTime`

Hora planeada de finalización.

Debe utilizar formato de 24 horas:

```text
HH:MM
```

Ejemplo:

```js
plannedEndTime: "07:15"
```

### `statesByDate`

Objeto que relaciona una fecha concreta con el estado de la actividad para ese día.

Las fechas deben utilizar el formato:

```text
YYYY-MM-DD
```

Ejemplo:

```js
statesByDate: {
    "2026-08-01": "completed",
    "2026-08-02": "in_progress",
    "2026-08-03": "not_completed"
}
```

Si una fecha no tiene un estado registrado, debe considerarse:

```text
pending
```

---

# Estados permitidos

Los únicos estados aceptados en esta entrega son:

```text
pending
in_progress
completed
not_completed
cancelled
```

## Ciclo de estados

Cada clic sobre el control multestado debe avanzar así:

```text
pending
    ↓
in_progress
    ↓
completed
    ↓
not_completed
    ↓
cancelled
    ↓
pending
```

## Representación visual esperada

### `pending`

- cuadro vacío;
- color neutro;
- significado: pendiente.

### `in_progress`

- símbolo de reloj;
- color amarillo;
- significado: en progreso.

### `completed`

- marca de verificación;
- color verde;
- significado: completada.

### `not_completed`

- símbolo X;
- color rojo;
- significado: no realizada.

### `cancelled`

- símbolo de advertencia;
- color gris;
- significado: cancelada.

No debe utilizarse un `input type="checkbox"` nativo, porque el control representa cinco estados y no solamente marcado o desmarcado.

Debe implementarse mediante un botón accesible.

---

# Duración estimada

La duración estimada no debe guardarse como un campo independiente dentro del objeto simulado.

Debe calcularse en JavaScript utilizando:

```text
plannedEndTime - plannedStartTime
```

Ejemplos:

```text
05:30 → 07:15 = 1h 45min
07:50 → 07:55 = 5min
08:45 → 09:45 = 1h
```

La función debe devolver un texto legible.

Ejemplos:

```text
1h 45min
5min
1h
```

En esta entrega no deben admitirse actividades que crucen la medianoche.

La hora final debe ser posterior a la inicial dentro del mismo día.

---

# Orden de las actividades

Antes de renderizarse, las actividades deben ordenarse mediante:

1. `plannedStartTime`;
2. `position`.

Ejemplo:

```text
05:30 — Gym
07:50 — Cepillado de dientes
08:45 — Hybridge
```

Si dos actividades comienzan a la misma hora, se utiliza `position`.

---

# Datos mínimos de demostración

Debe incluirse un conjunto de entre cinco y ocho actividades simuladas.

Puede utilizarse una estructura parecida a esta:

```js
const mockActivities = [
    {
        id: "gym-pecho",
        name: "Gym - Pecho",
        position: 1,
        plannedStartTime: "05:30",
        plannedEndTime: "07:15",
        statesByDate: {}
    },
    {
        id: "cepillado-dientes",
        name: "Cepillado de dientes",
        position: 2,
        plannedStartTime: "07:50",
        plannedEndTime: "07:55",
        statesByDate: {}
    },
    {
        id: "meditar",
        name: "Meditar",
        position: 3,
        plannedStartTime: "08:00",
        plannedEndTime: "08:15",
        statesByDate: {}
    },
    {
        id: "hybridge-programacion",
        name: "Hybridge - Programación",
        position: 4,
        plannedStartTime: "08:45",
        plannedEndTime: "09:45",
        statesByDate: {}
    },
    {
        id: "comida",
        name: "Comida",
        position: 5,
        plannedStartTime: "14:00",
        plannedEndTime: "14:30",
        statesByDate: {}
    },
    {
        id: "ccna-estudio",
        name: "CCNA / Estudio",
        position: 6,
        plannedStartTime: "19:15",
        plannedEndTime: "20:15",
        statesByDate: {}
    },
    {
        id: "preparacion-dia-siguiente",
        name: "Preparación del día siguiente",
        position: 7,
        plannedStartTime: "21:15",
        plannedEndTime: "21:45",
        statesByDate: {}
    }
];
```

Codex puede completar algunos estados de ejemplo para demostrar visualmente los cinco estados disponibles.

Sin embargo, cada fecha sin estado explícito debe comenzar como `pending`.

---

# Fecha seleccionada

La aplicación debe mantener una fecha seleccionada en memoria.

Inicialmente será la fecha actual del dispositivo.

Ejemplo conceptual:

```js
let selectedDate = getCurrentLocalDate();
```

En escritorio amplio se muestran todos los días del mes.

En vista compacta se muestra únicamente la columna correspondiente a `selectedDate`.

---

# Modificación del estado

Cuando el usuario cambie un estado:

1. identificar la actividad;
2. identificar la fecha;
3. obtener el estado actual;
4. calcular el siguiente estado;
5. actualizar `statesByDate`;
6. volver a renderizar únicamente lo necesario o actualizar el control;
7. actualizar `data-status`, símbolo, título y `aria-label`.

Ejemplo conceptual:

```js
activity.statesByDate[selectedDate] = "completed";
```

El cambio solo debe afectar:

```text
una actividad
+
una fecha
```

No debe modificar otros días de la misma actividad.

---

# Responsabilidad de los archivos

La estructura esperada es:

```text
modules/gestor_de_habitos/
├── index.html
├── css/
│   └── gestor_habitos.css
└── js/
    ├── mock-data.js
    ├── status-control.js
    └── app.js
```

## `mock-data.js`

Responsable de:

- declarar los datos simulados;
- proporcionar actividades de demostración;
- no manipular directamente el DOM.

## `status-control.js`

Responsable de:

- declarar los estados disponibles;
- definir símbolos y etiquetas;
- devolver el siguiente estado;
- actualizar la representación visual de un control.

## `app.js`

Responsable de:

- obtener la fecha actual;
- calcular los días del mes;
- ordenar actividades;
- calcular duraciones;
- renderizar la matriz;
- reaccionar a los clics;
- controlar el comportamiento responsive.

---

# Restricciones

Durante esta entrega no se debe:

- consumir una API;
- utilizar archivos JSON externos;
- guardar en `localStorage`;
- crear una base de datos;
- usar frameworks;
- crear filas manuales repetidas en HTML;
- agregar propiedades que pertenezcan a funciones futuras;
- implementar recurrencias reales;
- implementar horas reales de ejecución;
- implementar estadísticas;
- implementar rachas o porcentajes.