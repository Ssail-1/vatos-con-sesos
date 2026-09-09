# Frontend MVP 01

## Vista principal

La interfaz representa una matriz de seguimiento mensual.

Cada fila corresponde a una actividad.

Cada columna de seguimiento corresponde a un día del mes actual.

La aplicación utiliza datos simulados mediante JavaScript.

## Encabezado

Debe mostrar:

- título `Hábitos`;
- nombre del mes actual;
- un área para la información temporal;
- encabezados abreviados de los días;
- número de fecha de cada día.

No mostrar:

- porcentaje general;
- porcentajes diarios;
- días activos;
- rachas;
- gráficas;
- notas generales.

## Información de cada actividad

Cada fila debe mostrar:

- posición dentro de la lista;
- nombre de la actividad;
- hora planeada de inicio;
- duración estimada;
- control de estado correspondiente a cada día visible.

La duración estimada se calcula a partir de:

`plannedEndTime - plannedStartTime`

No debe almacenarse como dato independiente dentro del objeto simulado.

## Escritorio amplio

En una pantalla suficientemente amplia se muestran:

- información resumida de cada actividad a la izquierda;
- todos los días del mes actual a la derecha;
- un control de estado por actividad y por día;
- el día actual resaltado visualmente.

La interfaz debe inspirarse en:

`assets/Ejemplo-objetivo-plantilla.png`

No debe copiar literalmente Google Sheets.

## Vista compacta

Cuando el espacio horizontal sea reducido:

- se ocultan las columnas correspondientes a otros días;
- se muestra únicamente la columna del día seleccionado;
- inicialmente el día seleccionado es el día actual;
- se conserva el nombre de la actividad;
- se conserva la hora inicial;
- se conserva la duración estimada;
- se conserva el control de estado del día seleccionado;
- no debe existir desplazamiento horizontal de toda la página.

Debe inspirarse en la captura compacta proporcionada.

## Control multestado

No debe utilizarse un checkbox HTML nativo.

Debe utilizarse un botón multestado.

Cada aparición diaria comienza en:

`PENDING`

Cada clic avanza en este orden:

1. `PENDING`
2. `IN_PROGRESS`
3. `COMPLETED`
4. `NOT_COMPLETED`
5. `CANCELLED`
6. regreso a `PENDING`

## Representación visual

### PENDING

- símbolo de cuadro vacío;
- color neutro;
- significado: pendiente.

### IN_PROGRESS

- símbolo de reloj;
- color amarillo;
- significado: en progreso.

### COMPLETED

- símbolo de paloma o marca de verificación;
- color verde;
- significado: completada.

### NOT_COMPLETED

- símbolo X;
- color rojo;
- significado: no realizada.

### CANCELLED

- símbolo de advertencia;
- color gris;
- significado: cancelada.

El control debe actualizar también:

- `data-status`;
- `aria-label`;
- título o ayuda visible al pasar el cursor.

## Estado interno

Cambiar un estado modifica únicamente los datos simulados en memoria.

Al recargar la página, los datos pueden regresar a su estado inicial.

Eso es correcto para esta entrega.

## Orden

Las actividades deben renderizarse en orden ascendente según:

1. hora planeada de inicio;
2. posición original.

## Accesibilidad mínima

Los controles deben:

- ser botones;
- poder usarse con teclado;
- incluir un nombre accesible;
- mostrar foco visible;
- no depender exclusivamente del color.