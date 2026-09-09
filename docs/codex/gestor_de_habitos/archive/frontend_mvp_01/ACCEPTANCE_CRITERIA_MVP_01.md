
# Criterios de aceptación — Frontend MVP 01

La entrega se considera terminada cuando se cumplen todos los puntos.

## Estructura

- Todo el código nuevo permanece dentro de `modules/gestor_de_habitos/`.
- HTML, CSS y JavaScript están separados.
- No se usan frameworks ni dependencias externas.
- No se modifican archivos de la aplicación principal.

## Renderizado

- Las actividades se generan desde un arreglo JavaScript.
- No existe una fila HTML repetida manualmente por actividad.
- Las actividades aparecen ordenadas por hora.
- La duración estimada se calcula correctamente.

## Escritorio

- Se muestra el mes actual.
- Se muestran los días y números de fecha del mes.
- Se muestran todas las columnas del mes en una pantalla amplia.
- El día actual está resaltado.
- No aparecen estadísticas, rachas ni porcentajes.

## Vista compacta

- Solo aparece la columna del día seleccionado.
- El día seleccionado inicialmente es hoy.
- Se conservan nombre, hora, duración y estado.
- La página no produce scroll horizontal global.
- Los textos no se superponen.

## Estados

- Cada estado tiene un símbolo reconocible.
- Cada estado tiene una etiqueta accesible.
- Cada clic avanza al siguiente estado.
- Después de `cancelled`, vuelve a `pending`.
- El cambio afecta únicamente la actividad y fecha pulsadas.
- Los cinco estados pueden demostrarse.

## Calidad

- No existen errores en la consola.
- Los botones funcionan mediante teclado.
- El foco es visible.
- La interfaz mantiene una apariencia oscura coherente.
- El código está comentado por bloques funcionales.
- Codex explica cómo abrir y probar la entrega.
