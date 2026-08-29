# Requerimientos

Un organigrama se queda corto cuando quieres automatizar toda tu vida y se vuelve necesario cuando enfrentas distracciones, problemas de motivación y autoestima.

Algunas personas necesitan tener un mapa o un guia que les diga que tienen que hacer cada momento porque su cabeza se abruma con cada decición. Peor aun cuando ya procrastino demaciado y se juntaron un millos de cosas por hacer.

El problema de los organigramas radica en que no todos los días son iguales, hay acitividades que rompen el esquema y personas como yo requieren tener el mayor control posible para evitar sentir que se arruino el día y la ansiedad por pensar y ahora que y que el plan se venga abajo y el sentimiento negativo provoque una caída de dias, semanas y mas.

Entonces se requiere un organigrama capaz de llevar el registro del cumplimiento de este tipo de actividades:

## Tipos de actividades

### Actividades Ancla

Estas actividades son pilares porque se repiten constantemente y necesitamos administrar el tiempo con base y alrededor de ellas.

Normalmente son actividades que no están en nuestras manos alterar o que por decisión propia queremos cumplir obligatoriamente.

Son por ejemplo:

- Horario de trabajo
    
    El organigrama debe ser capaz de asignar esta actividad:
    
    - Asignando el horario
    - Dia o dias de descanso
    - Si es un trabajo rolado la posibilidad de alterar el horario
        - Por día (obligatorio)
        - Por cada tantos dias
        - Por semana
        - Por Mes
    - Poder reducir o aumentar su duración
        - Aumentarlo por tiempo extra
        - Reducirlo por X situación
- Horario escolar
    
    Existen actividades como esta que engloban actividades diferentes, por ejemplo en este caso los dias de escuela se componen por clases diarias de diferentes materias y si es así:
    
    - El organigrama debe ser capaz de registrar sub-actividades que forman esta actividad, por ejemplo registrar las sub-actividades con:
        - Sub-actividad en orden
        - Poder marcarlas
        - Horario (opcional)
        - Los comentarios tambien pueden servir como notas para escribir pendientes de las subactividades(para este ejemplo materias)
- Gymnacio
    
    En este tipo de actividades estaría bien poder agregar un apartado o poder asignar un enfoque.
    
    - Por ejemplo poder poner:
        - Lunes enfoque Pierna
        - Martes enfoque Pecho
        - Miercoles enfoque Espalda
        - Jueves enfoque Pierna completa
        - Viernes enfoque triceps - pecho
        - Sabado enfoque biceps - espalda
        - Domingo no deberia aparecer la actividad porque es dia de descanso
    
    Y así tener un boton que pueda asignar, repetir diariamente, repetir semanalmente si al registrarse se asignaron dias donde se alterna algo, como en este caso enfoque es diferente, tambien puede ser horario diferente en días, subactividades diferentes, etc.
    

### Actividades periódicas

Son actividades que tienen un ritmo fijo, puede que estas actividades las realizes simplemente cuando te surge la necesidad de hacerlas, pero si las registras poco a poco descubriras que pueden ser planeadas.

Estas pueden tener una frecuencia:

- Semanal como
    - Dia de lavado de Ropa
    - Dia de ir al mercado
    - Doblado de Ropa
    - Lavar coche
    - Normalmente son actividades que haces 1 o 2 veces a la semana
    - Cortarse las uñas
- Quincenal
    - Visitar a la familia
- Mensual
    - Cortarse el cabello

Este tipo de actividades no siempre las tenemos claras y es comun que se salgan de las manos, pero no son activades imprevistas, porque se realizan con una determinada frecuencia.

Entonces este tipo de actividades deberían poder registrarse:

- En el momento que se realizen
- Designar un dia o dias e indicar que se repita cada cierto tiempo en caso de ya saber
- Si no asignarse manualmente, por ejemplo:
    - esta activadad la hare hoy a las 3pm y la anotare para hacerla de nuevo en 12 dias pero a las 7am

Estas actividades y actividades imprevistas pueden romper el cronograma y si es así, las activades que esten despues de esta que se registre, haga que las demas actividades se recorran, ya sea despues del tiempo u hora estimada de finalización o poder modificarlas manualmente.

Pero! es importante que si rompe el flujo y se tienen que modificar manualmente solo se modificara el organigrama o planeación de ese dia, no afectara a los otros dias.

Porque recordemos que una cosa es la planeación y otra la ejecución de la actividad. Creo que son 2 estados diferentes, y la planeación solo es una guia o mapa pero esta fuera de nuestras manos si el dia se cumple tal cual y la app u organigrama debe estar preparado para estas situaciones.

### Actividades imprevistas

Estas actividades son situaciones que se salen de nuestras manos, pero vale la pena registrarlas porque al final todo tiene algun grado de probabilidad de ocurrir, ya sea una actividad en especifico o la frecuencia con la que suceden imprevistos, y al tenerlos registrados podemos analizar las situaciones y tiempos.

Por ejemplo si un dia faltas al trabajo por enfermedad, al llevar un registro podremos saber o aproximar cada cuando te enfermas, en que mes es mas probable, cuanto duro la enfermedad, que tan productivo fuiste en esos dias, etc.

Entonces estas actividades se registraran así como actividades imprevistas y trataremos de darle un nombre generico para futuras mediciones.

Las mediciones sera algo que implementemos a futuro…

Por ahora lo importante simplemente sera poder registrarlas.

## Conclusión

Por ahora estas son las actividades que se me vienen a la mente. La aplicacion debera ser capaz de agregar otro tipo de actividad general, por el momento al registrar una actividad, la app desplegara la posibilidad de agregar:

- Actividades ancla
- Actividad periodica
- Imprevisto (actividad)
- + agregar otro tipo de actividad

Despues de elegir el tipo de activida, asignarle:

- Nombre de actividad
- Hora actual u hora de inicio
- Hora final o estimación de tiempo de ejecución o esperar a finalizar
    - Si se selecciono la estimación o esperar a finalizar, la actividad estara abierta y se podra indicar cuando termino la actividad, registrandose la hora final como planeada, entonces se tendran 2 registros:
        1.  Hora de inicio planeado y hora final planeada
        2. Hora de inicio de ejecución y hora final de ejecución, que seria el tiempo real en que se ejecuto la actividad
    - NOTA: Si esto es mucho y puede que haya complicaciones con el desarrollo con la IA, la primera o primeras versiones MVP, podemos solo pedir el registro de inicio y hora de finalización y despues en proximas versiones agragamos estas features.
- Cada cuando se repite:
    - Diariamente y se coloque automaticamente todos los dias
    - Semanalmente, entonces seleccionar los dias que desea que se repita y poder elegir la misma hora o cambiarla dependiendo el día y despues repetir el patron cada semana futura, la planeación llegara hasta minimo 2 semanas despues o hasta donde se tenga la maxima actividad periodica planeada, ejemplo:
        - Si hay una actividad planeada destro de 6 meses, ejemplo vacaciones, la repeticion de la actividad se repetira con la frecuencia asignada hasta esa fecha de la actividad, si no hay minimo 2 semanas despues.
    - Mensualmente, si es así se repetiran todas las actividades ya registradas minimo 2 meses o hasta la maxima actividad planeada periodica.
    - Las actividades que se repetiran seran solamente las Actividades tipo “Actividades Ancla” y su registro maximo sera mandado por la actividad periodica planeada o agendada.
- Si despues en algun punto futuro, se culmina la actividad, por ejemplo:
    - Se asigno una actividad que era estudiar todos los dias 1 hora una materia, pero despues de un mes o un semestre ya se acabo la materia, se podra eliminar la actividad pero su registro anterior seguira existiendo para fines de mediciones estadisticas futuras.
- Tambien pueden existir tiempos muertos sin designar, no es obligatorio que haya una actividad tras otra.
- Despues habra un boton tipo toggle-switch que diga “contiene Sub-actividades?” y si se activa:
    - Poder registrar las subactividades y ya solo se registrara
        - Nombre de la subactividad
        - hora inicio
        - hora final
        - cada cuando se repite con base en los dias de la actividad principal, no tipo de activida.
        - Porque?
            - Porque por ejemplo, tengo clases solo los dias Lunes, martes, jueves y viernes
            - Pero los lunes y jueves tengo un tipo de materias
            - los martes y viernes otras materias diferentes
            - Y los viernes otras dos materias adicionales
            - Entonces la actividad principal solo se repetira los dias que son y pueda registrar como actividades secundarias, las materias y tambien a la hora que se repiten, los dias en que la actividad principal se cumple o incluso si hay solo una actividad.
            - Pongo el ejemplo anterior para dar claridad de como quiero que funcione

## Reglas para todas las actividades

Todas las actividades por dia deben poder permitir agregar comentarios por cualquier situación, como por ejemplo en la siguiente captura:

![image.png](image.png)

- Puede ser que al seleccionar como culminada la actividad o aun sin culminar, un botonsito con el que se pueda agregar un comentario y si se pasa el mouse encipa sobre salga el comentario y ya en el comentario igual un algo que diga mostrar mas o ocultar comentario. Asi como funcionan los comentarios de google sheets.

Si a la actividad se le asigna una hora de inicio y final, se calcule automaticamente el tiempo estimado de duración.

Tambien se muestre el tiempo real de ejecución

Poder registrar el tiempo que tomo la actividad

- Una cosa es el tiempo estimado
- Otra el tiempo real de ejecución
- Se podra acceder al resumen del dia con las actividades reales hechas
    - Asi como el mapa de las actividades en:
    - lista
    - hora que inicio y finalizo
    - tiempo de ejecución
    - Otro apartado de actividades que lamentablemente no se pudieron cumplir
        - Si no se cumplio la actividad se podra registrar otro tipo de comentario que explique que fallo o x situación que impidio su ejecución.

Las actividades van a poder registrarse asignando cada cuando se repiten, puede que al registrarse, asignar los dias, los horarios, subactividades, estas subactividades tambien pueden depender del dia, así como los dias que no se registren no deben aparecer porque pueden ser dia de descanso o simplemente ese dia no se hace y ya.

## Como se vera el organigrama y funciones

Por ahora busco mas que nada que funcione, esta es una imagen de un organigrama que tengo en google sheets y quiero algo así:

![image.png](image%201.png)

Lo primero es que en donde dice DIA ACTUAL, debe estar el nombre del dia actual y fecha.

Debajo deben aparecer las actividades registradas acorde al dia actual las actividades planeadas en orden desde la que inicia mas temprano en adelante. Deben estar su nombre de la actividad, no el tipo de actividad.

Todos los dias deben aparecer sus actividades planeadas, por eso esque los dias siempre seran diferentes…

A la izquierda de cada actividad debera estar la hora de inicio y hora final y tiempo estimado

Si hay sub-actividades deben estar escalonadas como tipo viñetas y subviñetas, estas tambien tendran su propio renglon y podran tambien marcarse como cumplidas y tambien se podran hacer comentarios

En el ejemplo se mira el mes completo, tambien en aqui en esta app se debera ver todos los dias así como en la cap, pero si por ejemplo como en la cap, hoy es 25 de julio, los dias anteriores al no haber registro de actividades no deberan aparecer o estar desactivados, tu decide que es mas fácil.

Ahí por ejemplo se puede marcar el dia activo y se podran registrar las actividades realizadas o no.

Tambien quiero que se vea las primeras 3 letras del dia y abajo el numero de la fecha como en la cap. lo de porcentajes por ahora no es necesario, despues lo haremos en una actualización.