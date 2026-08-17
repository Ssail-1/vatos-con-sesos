
# Fix about implementation

## Registrar habito

Al agregar un habito, solo deberia de registrarse la hora en la que se debe realizar, eso creo, no estoy seguro, creo que debemos hablar de esto.

Pero lo digo porque se supone que es un tipo de alarma. Por ejemplo:

Habito: Despertar

Hora inicio: 4:00 am

Igual y puede funcionar poner hora de finalizacion, pero no lo se...

sigo pensando si es buena idea...

## Temporalidad de hábitos programados

Evaluar si un hábito programado puede tener dos modalidades:

- Evento puntual:
  solo tiene una hora programada.
  Ejemplo: tomar medicamento a las 08:00.

- Bloque temporal:
  tiene hora inicial y final.
  Ejemplo: rutina de preparación 21:30–21:45.

Debe definirse posteriormente cómo interactúan los eventos puntuales
con las reglas de superposición del Plan del día.

Por ahora todos los registros continúan utilizando inicio y final.