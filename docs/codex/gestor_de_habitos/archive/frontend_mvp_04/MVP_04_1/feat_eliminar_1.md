
# Habilitando funcion Eliminar

## "🗑 Eliminar solo este día"

Solo para estar en sintonía, cuando te refieres a "Eliminar solo este día", supongo que te refieres a que el planItem que esta seleccionado eliminara la ocurrencia agendada tambien para el dia en el que se encuentra selecDate, creo que es así, no?

Y si es así si es justo a lo que me refería, es como si esa agendación nunca se hubiera agendado.

## "⏹ Detener de aquí en adelante"

Ademas de las tres acciones que genera esta opción:

```md
preservar pasado
        ↓
retirar planificación futura
        ↓
detener generación futura
```

Tambien debería eliminar la ocurrence actual del selectDate desde donde se esta solicitando esta opción.

## "🗑 Eliminar completamente el PlanItem"

Yo creo que esta no, porque presiento que el valor mas alto serán los datos... Y eliminar algo que paso antes, independientemente de si se realizo o no, es un indicativo de algo.

Y realmente no me gusta esa opción, no creo que ni yo debería tener acceso a usarla como usuario.

Lo que queda en el historial se queda en el historial, de cada usuario claro, pero se quedara.

---
---
---

## Proteccion de estados

Me parece una idea acertada bloquear la funcion de eliminar en estados diferentes a pending.

---

# Pending

Justo quiero determinar el comportamiento o acciones que se toman alrededor de este estado.

## Comportamiento general de estados anteriores a actual date

Quiero que en general no se puedan modificar los estados anteriores a una determinada distancia hacia atras del actualDate, aun no determino cuando tiempo pero siento que 1 semana es lo suficiente permisivo para dar libertad al usuario y restrictivo para conservar la integridad de los datos.

Entonces que de una semana hacia atras, queden congelados los estados para que no pueda modificarlo el usuario, sería como una manera de hacer que no haga trampa, aunque el tiempo de una semana me parece demaciado, pero puedo entenderlo porque si por imprevisto viajas a un lugar y no hay internet o la prioridad es estar desconectado se puedan modificar esos dias. 

Aun sigue sin convencerme pero por ahora una semana me parece sufiente.

## Que pasara con pending?

Ya que vamos a congelar que se puedan modificar estos estados, los planItems pasados pasaran a estar en el estado not_completed y si fuera posible que tuvieran un rojo menos intenso o un poco mas opacos o bajarle un poco a la intensidad.

### porque?

POrque de esta manera cuando el usuario vea su agenda y apenas esta en el camino o se desvio, puede que tengan muchos pending que pasados se convierten a not_completed y al ver su avance puede generar una desmotivacion, se deprime o le puede generar apatía, entonces mi idea es que solo este estado de not_completed redusca su visibilidad pero siga siendo rojo.

Sera mi manera de dejar los datos sin comprometer, que sigan ayudando al usuaio a tomar mejores deciciones, en base a estadisticas, pero tambien decirle, hey, no las cumpliste pero no importa tanto como el hoy :).

## Conclución

Entonces no, planItems ya caducados no deberían de poder modificarse.

Y ahora que yo voy a ser el primer usuario de mi app, quiero que se congenle los estados desde un dia antes del actual hacia atras, por ejemplo:

En este momento que escribo y lees esto, estamos a 29/09/2026, significa que ya no podre modificar los estados del jueves 27/09/2026.

Esto tiene que ser así Noa.

La ventana para arreglar el historial del dia anterior solo sera el dia actual.

Si se puede que esa variable la podamos controlar, sería mejor por si en un futuro quiero agrandar a esa ventana.

No se como o con que algoritmo lo haga codex pero si lo hace a travez de una variable, por ejempolo puede darle de la fecha actual hacia atras 24 horas y despues si ocupo simplemente aumento las horas o no se, algo así para que pueda entrar al codigo y manualmente cambiar esto.

Por ende lo que dijiste de poder borrar un pending viejo, no sera posible porque ni siquiera van a existir los pending en el pasado, unicamente los que permita la ventana, despues de que se cierre esa ventana serán not_completed, lo que refuerza lo que te dije, el pasado registrado no puede alterarse.

## 3. Detener de aquí en adelante

Justo así como lo aclaraste así quiero que funcione.

---
---
---

## estado in_progress despues de congelarse

Si lo podemos dejar para despues, pero si ya vamos a editar esta parte, creo que vale la pena meter de una vez un estado para la situcion o caso en la que el usuario la ponga in_progress pero se le haya olvidado cerrarla, podria se como not_finished y puede sere el mismo simbolo que tiene actualmente mas un "!" y el signo de admiracion cerrando este en rojo, así se identifica.

Por tanto, tambien not_finished debería limitar que se elimine su respectivo ocurrence.

## Estados futuros editables

Como la actual matriz permite tambien editar o alterar los estados de los dias siguientes, me refiero a sus estados (pending, in_progress,completed, not_completed, not_finished, cancelled), tambien deberiamos restringir que se puedan modificar los estados posteriores a currentDate, pero que si puedan variar entre pending y cancelled.

## Pending y canceled

Eso si deberia poderse porque se puede cancelar una actividad en el futuro e incluso nuestra regla de prioridades tambien cancelan actividades por debajo de su prioridad. No deberían entrar en conflicto estas reglas.

Actividades canceladas por eventos, imprevistos o por jerarquia en el currentDate pueden variar entre cancelled y not_completed, eso deberia de seguir funcionando así y quisiera agregar en ese flujo, solo cuando algo esta cancelado por prioridad que pueda variar con not_finished.

Lo de agregar not_finished lo digo porque talvez estaba estudiando, pero se atraveso un imprevisto, significa que la activida comenzo pero no termino. 

O solo se pueda variar si por ejemplo una actividad empieza a las 9:00 y deberia terminar a las 11:00 pero un imprevisto se atraveso a las 10:00 osea entre su horario, pueda variar entre cancelled, not_completed y not_finished solo si un imprevisto o evento nacio entre un horario, pero si el evento u horario opaca totalmente un horario de activida o habito, si se cancellen porque ni siquiera empezo.

## currentDate y selectDate

Tienes razon, gracias por corregirme, es importante porque así estamos mas en sintonia y conosco el sistema. Todo es mas claro, gracias Noa.

## user.timezone

Tienes razon, esas cosas ya en producción cuentan muchisimo, si quieres ese tipo de cosass importantes, podemos darles un espacio en los docs para no pasarlas por alto  y cuando llegue el momento de dar un paso, te paso los docs actuales y despues me devuelves anotado lo que no vas a implementar para dejarlo para despues y eliminas lo que ya vas a tomar en cuenta, justo como hacemos para codex. Me suena a buena idea pero si no se te olvida podemos seguir sin mantener registro, en mi no confies mucho porque algunas cosas se me van y me acuerdo sobre la marcha o se me olvidan.

---

Se aplicaron los cambios anteriores, exepto del feat Eliminar.

[Prompt de los cambios](/docs/codex/gestor_de_habitos/planeacion/MVP_04/INTEGRIDAD_TEMPORAL.md)

---
---
---

## Que pasa con cancelled

Creo que con si aplicamos un "Detener de aquí en adelante" si el ocurrence del currentDate tiene canceled, este no debe de desaparecer, pero los canceled futuros si deberian de desaparecer al igual que pending porque se esta tomando concientemente el eliminar ese planItem.

Esto tambien me pone a pensar que si estamos posicionados en un selectDate antes de la ventana de edición se podrían eliminar, pero ya no se puede porque codex desabilito editar, tambien estaria desabilitado eliminar y que esa funcion de eliminar solo se pueda dentro de la ventana y en el futuro, porque si esta en un selecDate futuro podemos eliminar el planItem pero fuera de estos no.

Espero haberme dado a entender, si no preguntame.

## generationConfig

Independientemente de como se haya configurado generationConfig si deberia eliminar todo lo que viene despues del selectDate, aunque solo sea una solo fecha, porque detener de aqui en adelante aunque sea unico puede interpretarse como terminar con este planItem independiente de como sea, porque si hacemos algo especifico para cada caso puede ser engorroso para el usuario y realmente no tiene relevancia si al final el resultado que buscamos es el mismo.

---

## excludedDates

Para lo de excluir una fecha por eliminar este día, tiene todo el sentido y me agrada, pero hay dos situaciones que se desencadenan.

La primera, es que despues de pasar la fecha excluida de la ventana de edicion, ejemplo:

Se elimina una actividad el dia 3 de septiembre y se registra la excepcion y cuando sea 5 de septiembre ya estara fuera de peligro pero el dato en excludedDates ya no será relevante, eso creo, entonces tambien deberiamos pedir a codex crear un algoritmo que elimine las fechas que ya pasaron y se ejecuten almenos cada fin de mes para que no este corriendo todo el tiempo.

La segunda es que si se elimina un planItem de un selectDate y se registra en excludedDates pero despues el usuaio se arrepiente o si va a realizar la actividad y quiere volver a registrarla, deberia poder hacerlo sin problema y eliminarse la fecha en excludedDates.

## Eliminar solo este día

Lo que mencionaste de:

```md
MVP 04.1.2 — Papelera

🗑 Eliminar solo este día
│
├── solo zona editable/futuro
├── requiere Occurrence identificable
├── solo status pending
├── elimina Occurrence
├── añade excepción para selectedDate
├── NO elimina PlanItem
└── NO vuelve a materializarse
```

Es importante que si esta selectDate despues de currentDate, aunque este canceled, tambien debe permitir eliminar


## Dudas

No se que deciciones te refieres guardar en ELIMINACION.md jaja.

---
---
---

# promp final

Implementa MVP 04.1.2 — Gestión de eliminación del Gestor de hábitos de
Vatos con Sesos.

NO hagas commit.
NO hagas push.
NO cambies de rama.
NO modifiques documentación salvo que sea estrictamente necesario corregir
una contradicción normativa; si encuentras una, detente e infórmala antes de
continuar.

Área autorizada de implementación:

modules/gestor_de_habitos/

==================================================
0. FUENTES DE VERDAD
==================================================

Antes de modificar cualquier archivo:

1. Lee AGENTS.md.
2. Lee docs/codex/CURRENT_TASK.md.
3. Lee íntegramente el documento normativo de eliminación referenciado desde
   CURRENT_TASK.
4. Lee la documentación normativa adicional que CURRENT_TASK referencie.
5. NO trates archive/, proximas-features/ ni planeaciones no referenciadas como
   alcance vigente.
6. Inspecciona git status antes de modificar.
7. Ejecuta TODOS los tests actuales como línea base.

La implementación vigente de MVP 04 + MVP 04.1.1 es baseline aprobado.

No reconstruyas por iniciativa:

- navegación;
- recurrencia;
- prioridades;
- override;
- temporal integrity;
- not_finished;
- manual_dates;
- matriz;

salvo cambios mínimos necesarios para integrar correctamente la eliminación.

==================================================
1. OBJETIVO
==================================================

Habilitar la papelera existente mediante dos operaciones:

A. "Eliminar solo este día"
B. "Detener de aquí en adelante"

NO implementar:

"Eliminar completamente PlanItem".

PlanItem debe permanecer como identidad histórica.

==================================================
2. RESPETAR INTEGRIDAD TEMPORAL
==================================================

Reutilizar la política temporal existente.

No duplicar lógica de cutoff en la vista.

Una selectedDate frozen:

→ no permite ninguna operación destructiva.

La papelera puede permanecer visible si eso ayuda a consistencia visual, pero
debe comunicar claramente que el historial está bloqueado y no permitir
mutaciones.

Con HISTORY_EDIT_WINDOW_DAYS = 1:

currentDate
→ editable

currentDate - 1
→ editable

currentDate - 2 o anterior
→ frozen

Fechas futuras
→ planificación editable según sus reglas específicas.

==================================================
3. ACCIÓN: ELIMINAR SOLO ESTE DÍA
==================================================

Semántica:

"La aparición de este PlanItem para esta fecha no debió haber sido
planificada."

No equivale a cancelled.

Debe eliminar físicamente una Occurrence concreta.

No eliminar:

- PlanItem;
- otras Occurrences;
- historial ajeno;
- generationConfig general.

Debe impedir que el materializador regenere posteriormente esa fecha.

==================================================
4. ESTADOS PERMITIDOS PARA ELIMINAR SOLO ESTE DÍA
==================================================

FROZEN:

ningún estado
→ rechazo.

CURRENTDATE o pasado dentro de la ventana editable:

pending
→ permitido.

cancelled
in_progress
completed
not_completed
not_finished
→ rechazo.

FUTURO:

pending
→ permitido.

cancelled
→ permitido.

Los demás estados futuros ya están prohibidos por temporal integrity.

==================================================
5. IDENTIDAD DE LA OCCURRENCE
==================================================

La operación debe trabajar sobre occurrence.id.

NO implementar algo equivalente a:

DELETE WHERE planItemId = X AND date = Y

El dominio continúa permitiendo conceptualmente múltiples Occurrences del mismo
PlanItem en una fecha.

Si la matriz detecta múltiples Occurrences ambiguas para PlanItem/date:

- no adivinar;
- no eliminar;
- mostrar feedback;
- conservar la protección de ambigüedad ya existente.

La operación date-level descrita mediante excludedDates solo es válida cuando
la aparición del PlanItem para esa fecha es inequívoca en esta UI.

==================================================
6. EXCLUDEDDATES
==================================================

Agregar a la configuración de generación una representación coherente de
fechas excluidas.

Conceptualmente:

excludedDates: [
    "2026-09-03"
]

Puede utilizarse otro nombre únicamente si mejora claramente la arquitectura,
pero debe existir una sola fuente de verdad.

Al ejecutar "Eliminar solo este día":

1. validar temporal integrity;
2. validar status;
3. validar que la Occurrence sea inequívoca;
4. validar la operación completa;
5. eliminar Occurrence;
6. registrar selectedDate como excludedDate;
7. aplicar todo atómicamente.

No permitir duplicados en excludedDates.

==================================================
7. MATERIALIZADOR + EXCLUDEDDATES
==================================================

Antes de generar una Occurrence candidata:

- respetar stoppedFromDate;
- respetar excludedDates;
- respetar frozen history;
- después aplicar las reglas normales del modo.

Si candidateDate está excluida:

→ no materializar.

No romper idempotencia.

No generar Occurrences nuevas en historia frozen.

El historial frozen existente es autoritativo.

==================================================
8. RESTAURAR UNA FECHA EXCLUIDA
==================================================

La operación existente:

"Agregar solo este día"

debe poder restaurar una fecha previamente eliminada mientras dicha fecha siga
siendo editable o futura.

Si selectedDate está en excludedDates:

1. NO quitarla inmediatamente;
2. preparar la nueva Occurrence;
3. validar horario;
4. validar conflictos;
5. validar prioridades;
6. validar temporal integrity;
7. si todo es válido:
   - retirar selectedDate de excludedDates;
   - crear la Occurrence;
8. aplicar ambas mutaciones atómicamente.

Si falla:

- excludedDate permanece;
- no crear Occurrence;
- no dejar cambios parciales.

Reutilizar el flujo de creación/override ya existente.

No reimplementar prioridades.

La futura materialización no debe producir una Occurrence equivalente duplicada
después de restaurar la fecha.

==================================================
9. LIMPIEZA DE EXCLUDEDDATES
==================================================

No implementar:

- timers;
- setInterval mensual;
- cron;
- jobs;
- infraestructura externa.

Integrar una limpieza idempotente con temporal integrity/reconciliation.

Cuando una excludedDate ya esté frozen:

puede eliminarse de excludedDates porque el materializador tiene prohibido
crear historia frozen.

La limpieza debe poder ocurrir oportunistamente al reconciliar/inicializar.

Ejemplo:

3 septiembre:
se elimina una aparición
→ excludedDates incluye 3 sep.

5 septiembre:
3 sep ya quedó frozen
→ reconciliación puede retirar 3 sep de excludedDates.

El resultado histórico permanece:
no aparece Occurrence nueva.

==================================================
10. ACCIÓN: DETENER DE AQUÍ EN ADELANTE
==================================================

Semántica:

"Desde selectedDate este PlanItem deja de formar parte de la planificación."

NO elimina PlanItem.

NO elimina historia.

NO equivale a cancelled.

Puede ejecutarse cuando selectedDate está:

- dentro de la ventana editable;
- currentDate;
- futuro.

No puede ejecutarse desde frozen.

NO requiere una Occurrence exactamente en selectedDate.

Esto es importante para vista mensual/eye-open, donde un PlanItem puede estar
visible aunque no ocurra en selectedDate.

==================================================
11. STOPPEDFROMDATE
==================================================

Agregar una frontera común a generationConfig.

Conceptualmente:

stoppedFromDate: "YYYY-MM-DD"

Debe funcionar independientemente de:

- weekly;
- interval_days;
- manual_dates;
- single_date.

Regla universal del materializador:

candidateDate >= stoppedFromDate
→ no materializar.

No destruir la configuración anterior.

La generación histórica sigue describiendo cómo se planificaba el PlanItem
antes de detenerlo.

==================================================
12. STOPPEDFROMDATE ES MONÓTONA
==================================================

"Detener de aquí en adelante" nunca debe reactivar implícitamente un intervalo.

Si no existe stoppedFromDate:

→ selectedDate.

Si existe una fecha posterior y ahora se detiene desde una fecha anterior:

→ mover stoppedFromDate hacia la fecha anterior.

Si ya existe una fecha anterior y se intenta detener desde una fecha posterior:

→ conservar la fecha anterior.

Conceptualmente:

earliest(existingStoppedFromDate, selectedDate)

No implementar reanudación.

==================================================
13. OCCURRENCES AL DETENER
==================================================

Todas las Occurrences anteriores a selectedDate:

→ conservar intactas.

Desde selectedDate inclusive:

PENDING
→ eliminar.

CANCELLED:

si occurrence.date > currentDate
→ eliminar.

si occurrence.date <= currentDate
→ conservar.

IN_PROGRESS
→ conservar.

COMPLETED
→ conservar.

NOT_COMPLETED
→ conservar.

NOT_FINISHED
→ conservar.

Estas reglas aplican independientemente del modo de generationConfig.

No convertir las eliminadas a cancelled.

==================================================
14. EJEMPLO CANCELLED
==================================================

currentDate = 2026-09-29
selectedDate = 2026-09-29

29 sep cancelled
→ conservar.

30 sep cancelled
→ eliminar.

1 oct pending
→ eliminar.

Un cancelled de currentDate/pasado representa una decisión ya registrada.

Un cancelled futuro deja de ser relevante cuando conscientemente se termina
toda la planificación futura.

==================================================
15. STOP DESDE PASADO EDITABLE
==================================================

Ejemplo:

currentDate = 29
selectedDate = 28
window = 1

La operación es válida.

Todo antes del 28:
→ preservar.

Desde 28:

aplicar las reglas anteriores.

Por tanto, por ejemplo:

28 completed
→ conservar.

29 cancelled
→ conservar porque date <= currentDate.

30 cancelled
→ eliminar.

30 pending
→ eliminar.

stoppedFromDate
→ 28.

==================================================
16. EXCLUDEDDATES REDUNDANTES AL DETENER
==================================================

Al establecer stoppedFromDate:

cualquier excludedDate >= stoppedFromDate es redundante.

Puede eliminarse de excludedDates dentro de la misma operación atómica.

Las excludedDates anteriores permanecen si todavía son necesarias según la
política temporal.

La normalización no debe alterar historia.

==================================================
17. SINGLE_DATE
==================================================

No crear comportamiento especial visible para single_date.

"Detener de aquí en adelante" significa lo mismo:

stoppedFromDate = selectedDate o frontera anterior existente.

Si la única Occurrence futura queda dentro de la región detenida y es pending
o cancelled futuro:

→ retirarla según las reglas generales.

PlanItem permanece.

No eliminar PlanItem.

==================================================
18. MANUAL_DATES
==================================================

No mutilar manualmente entries por iniciativa si stoppedFromDate ya ofrece la
frontera universal necesaria.

El materializador debe simplemente dejar de producir entries cuya fecha esté
en o después de stoppedFromDate.

Preservar generationConfig histórica.

==================================================
19. PRIORIDADES
==================================================

No romper statusContext ni procedencia de priority override.

Al eliminar un cancelled FUTURO mediante las operaciones autorizadas:

se elimina toda la Occurrence, incluido su statusContext, porque esa aparición
futura deja de formar parte de la planificación.

Nunca modificar la Occurrence superior que produjo el override.

Eliminar una occurrence inferior no elimina Event/Unexpected.

==================================================
20. NOT_FINISHED
==================================================

not_finished contiene historia.

No permitir:

"Eliminar solo este día"

sobre not_finished.

"Detener de aquí en adelante":

not_finished existente
→ preservar.

No modificar su statusContext ni horario.

==================================================
21. UI DE PAPELERA
==================================================

Habilitar el control visual de papelera ya reservado.

Preferir un único dialog/modal reutilizable y coherente con el tema oscuro/dorado.

NO utilizar window.confirm() si puede evitarse.

El diálogo debe ofrecer:

- Eliminar solo este día
- Detener de aquí en adelante
- Volver

Pero cada opción debe estar disponible/deshabilitada según el contexto.

==================================================
22. DISPONIBILIDAD DE "ELIMINAR SOLO ESTE DÍA"
==================================================

Si no existe Occurrence en selectedDate:

→ opción deshabilitada/no disponible.

Si existe ambigüedad:

→ deshabilitada y explicar.

Si status/temporal zone no permiten delete:

→ deshabilitada y explicar.

Ejemplos:

currentDate + completed
→ no delete individual.

future + cancelled
→ sí delete individual.

frozen + pending/not_completed/etc.
→ no delete.

==================================================
23. DISPONIBILIDAD DE "DETENER DE AQUÍ EN ADELANTE"
==================================================

Puede estar disponible aunque no exista Occurrence en selectedDate.

Requiere:

- PlanItem identificable;
- selectedDate no frozen;
- operación coherente con stoppedFromDate actual.

Si el PlanItem ya está detenido desde una fecha igual o anterior:

la operación no debe aparentar que extenderá nuevamente la planificación.

Puede informar que ya está detenido desde una fecha anterior.

No reactivar.

==================================================
24. CONFIRMACIÓN
==================================================

Antes de ejecutar una acción destructiva mostrar consecuencias claras.

Para "Eliminar solo este día":

indicar:

- PlanItem;
- selectedDate;
- horario;
- que esa aparición desaparecerá;
- que el resto de la planificación permanece.

Para "Detener de aquí en adelante":

indicar:

- PlanItem;
- selectedDate;
- que dejará de planificarse desde esa fecha;
- que el historial existente permanecerá;
- que las apariciones futuras elegibles serán retiradas.

No presentar "Cancelar actividad" dentro de esta UI.

cancelled es status, no delete.

==================================================
25. ACCESIBILIDAD
==================================================

Dialog semántico o estructura equivalente.

Debe:

- tener título accesible;
- manejar foco;
- atrapar Tab/Shift+Tab si corresponde;
- permitir Escape;
- restaurar foco al botón que abrió la papelera;
- usar botones reales;
- no depender únicamente del color;
- ser utilizable en móvil.

==================================================
26. ATOMICIDAD — ELIMINAR SOLO ESTE DÍA
==================================================

Validar antes de mutar.

La operación:

delete Occurrence
+
add excludedDate

es una única operación conceptual.

Si falla cualquier paso:

- Occurrence permanece;
- excludedDates permanece igual.

==================================================
27. ATOMICIDAD — DETENER
==================================================

Preparar primero:

- nuevo stoppedFromDate;
- Occurrences que deben eliminarse;
- Occurrences que deben preservarse;
- excludedDates redundantes a limpiar.

Validar todo.

Aplicar después.

Si falla:

- stoppedFromDate anterior permanece;
- no borrar Occurrences;
- no modificar excludedDates;
- no dejar cambios parciales.

==================================================
28. RECONCILIACIÓN
==================================================

Integrar excludedDates con la reconciliación temporal existente sin crear una
segunda política paralela.

La política temporal debe continuar siendo responsabilidad de dominio/store,
no de la vista.

Evitar que app.js duplique reglas de status/cutoff.

==================================================
29. NO IMPLEMENTAR
==================================================

No implementar:

- eliminar completamente PlanItem;
- reactivar/reanudar PlanItem detenido;
- restore histórico frozen;
- PostgreSQL;
- Flask;
- persistencia;
- backend;
- cron;
- timezone por usuario;
- estadísticas;
- subactividades;
- funcionalidades de roadmap.

==================================================
30. PRUEBAS AUTOMÁTICAS — DELETE INDIVIDUAL
==================================================

Añadir cobertura como mínimo para:

A. currentDate pending
→ eliminar permitido.

B. ayer dentro de ventana + pending
→ permitido.

C. frozen pending
→ rechazo.

D. currentDate cancelled
→ rechazo.

E. future cancelled
→ permitido.

F. in_progress
→ rechazo.

G. completed
→ rechazo.

H. not_completed
→ rechazo.

I. not_finished
→ rechazo.

J. eliminar occurrence
→ occurrence desaparece.

K. eliminar occurrence
→ excludedDates registra fecha.

L. volver a materializar
→ fecha excluida no reaparece.

M. otra fecha recurrente
→ continúa materializándose.

==================================================
31. PRUEBAS — RESTAURAR EXCLUSIÓN
==================================================

N. Agregar solo este día sobre excludedDate válida
→ quita exclusión + crea occurrence.

O. conflicto al restaurar
→ excludedDate permanece.

P. fallo de creación
→ excludedDate permanece.

Q. restauración no produce duplicado equivalente al rematerializar.

==================================================
32. PRUEBAS — LIMPIEZA
==================================================

R. excludedDate editable
→ permanece.

S. excludedDate frozen
→ se limpia durante reconciliación.

T. después de limpiar una excludedDate frozen
→ el materializador NO reconstruye esa fecha.

U. reconciliación repetida
→ idempotente.

==================================================
33. PRUEBAS — DETENER
==================================================

V. detener desde currentDate.

W. detener desde yesterday editable.

X. intentar desde frozen
→ rechazo.

Y. detener desde fecha futura.

Z. no existe occurrence en selectedDate
→ puede detener PlanItem.

AA. pending desde selectedDate
→ se elimina.

AB. cancelled futuro
→ se elimina.

AC. cancelled currentDate
→ se conserva.

AD. cancelled ayer editable
→ se conserva.

AE. completed futuro/materializado
→ conservar según integridad actual.

AF. not_completed
→ conservar.

AG. not_finished
→ conservar.

AH. in_progress
→ conservar.

AI. occurrences anteriores a selectedDate
→ intactas.

AJ. materializar horizonte posterior
→ nada >= stoppedFromDate reaparece.

==================================================
34. PRUEBAS — MODOS
==================================================

Comprobar stop con:

- weekly;
- interval_days;
- manual_dates;
- single_date.

No requiere algoritmos UI diferentes.

Todos deben respetar stoppedFromDate.

==================================================
35. PRUEBAS — MONOTONÍA
==================================================

AK. sin stoppedFromDate
→ se establece selectedDate.

AL. stoppedFromDate posterior + nueva fecha anterior
→ se adelanta.

AM. stoppedFromDate anterior + nueva fecha posterior
→ NO se mueve hacia adelante.

AN. no existe reactivación implícita.

==================================================
36. PRUEBAS — ATOMICIDAD
==================================================

AO. fallo en delete individual
→ occurrence/excludedDates intactos.

AP. fallo durante stop
→ occurrences/generationConfig/excludedDates intactos.

AQ. ambigüedad de múltiples occurrences
→ no delete accidental.

==================================================
37. REGRESIÓN
==================================================

Ejecutar TODOS los tests anteriores.

Verificar específicamente que no se rompa:

- HISTORY_EDIT_WINDOW_DAYS;
- frozen;
- pending → not_completed;
- in_progress → not_finished;
- future pending ↔ cancelled;
- not_finished;
- statusContext;
- override Event/Unexpected;
- completed protection;
- Apply week;
- Apply future;
- Agregar solo este día;
- manual_dates;
- múltiples occurrences;
- horizonte;
- navegación;
- selectedDate;
- visibleMonth;
- eye open/closed.

==================================================
38. QA DE NAVEGADOR
==================================================

Mediante HTTP real probar:

CASO 1
currentDate + pending
→ eliminar solo este día
→ desaparece.

CASO 2
recargar/re-render/materializar
→ no reaparece.

CASO 3
Agregar solo este día nuevamente
→ reaparece y la exclusión desaparece.

CASO 4
future + cancelled
→ eliminar solo este día permitido.

CASO 5
currentDate + cancelled
→ individual delete bloqueado.

CASO 6
frozen
→ papelera no permite mutar.

CASO 7
Detener desde currentDate.

CASO 8
Detener desde un día futuro sin occurrence exacta.

CASO 9
navegar/extender horizonte después de detener
→ no reaparece.

CASO 10
manual_dates/single_date
→ misma semántica de stop.

CASO 11
desktop 1440×900.

CASO 12
mobile 390×844.

Comprobar:

- sin overflow horizontal;
- diálogo completamente usable;
- Escape;
- Tab;
- Shift+Tab;
- restauración de foco;
- sin errores JS de aplicación.

==================================================
39. VERIFICACIÓN FINAL
==================================================

Ejecutar:

- TODOS los tests del módulo;
- nuevas pruebas de eliminación;
- node --check sobre todos los JS/MJS;
- git diff --check.

No borrar pruebas anteriores.

==================================================
40. REPORTE
==================================================

NO hagas commit.

En el reporte final indica:

1. archivos creados/modificados/eliminados;
2. representación final de excludedDates;
3. cómo se evita rematerializar fechas eliminadas;
4. cómo se restauran exclusiones;
5. cómo se limpian excludedDates frozen;
6. representación final de stoppedFromDate;
7. tratamiento de cada status al detener;
8. comportamiento de cancelled currentDate vs cancelled futuro;
9. atomicidad;
10. ambigüedad;
11. integración con temporal integrity;
12. integración con prioridades;
13. UI y accesibilidad;
14. tests automáticos;
15. QA de navegador;
16. limitaciones restantes.

No declares automáticamente terminado MVP 04.1.2.
No implementes ninguna feature fuera de esta pasada.
