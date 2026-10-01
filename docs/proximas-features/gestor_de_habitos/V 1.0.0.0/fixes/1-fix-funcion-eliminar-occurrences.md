
# Funcion DELETE

## fix: Habilitar funcion DELETE en toda la ventana de edición

### Problema

No me permite hacer DELETE en el tiempo `Dia/dias antes del Current Day` y no pude borrar las actividades que habia puesto en el dia anterior justo por eso y como ya no corregí este error y ya pasaron dias, ahora esos plan_items mal registrados ya forman parte de frozen o del historial, entonces quiero primero que habilitemos la funciones de DELETE tambien en este tiempo, codex debe de entender que si se pueden hacer ajustes dentro de la ventana de edición, incluso borrar, solo ya no cuando forman parte de frozen.

Lo segundo que quiero que me ayudes es a borrar esos plan_items que cree el dia 22 de septiembre para dejar bien el cronograma, dejaría las actividades pero ya sabemos que en un futuro todos lo plan_items que dejemos tienen peso, entonces quiero hacerlo bien

Actualmente definimos 4 tiempos: 

### Frozen

- (Estan fuera de la ventana de edición y no se pueden editar estas occurrences)

- Representa el historial.
- Solo se permiten cambios generales del plan_item como tipo, subtipo, etc, mientras no afecten la información atomica. No se si me de a entender, esto creo que es mas profundo pero por ahora creo que no tenemos tema con esto, si ya definimos una plan_item va a ser laborioso si el usuario quiere cambiar el subtipo, deberiamos mejor restringir. Por ejemplo solo se pueden cambiar de Ancla a periodica y viceversa y así. pero por ahora no.

### Dia/dias antes del Current Day

- Estan dentro de la ventana de edición (Aun no forman parte de Frozen)

- Actualmente solo permitimos un dia antes del current day para que el usuario pueda modificar sus occurrences.

### Current Day

- Aqui es donde tenemos la mayoria de libertad de manipular una occurrence

### Future Days

- Es el tiempo despues de Current Day