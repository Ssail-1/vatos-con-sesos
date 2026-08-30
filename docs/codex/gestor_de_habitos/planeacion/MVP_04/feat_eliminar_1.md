
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
---
---
