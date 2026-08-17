
# New implementation

## Visualizacion por dias

Tambien quiero que hagamos una implementacion, sin embargo no se que tan posible sea hacerlo antes de la siguiente entrega o en conjunto con la entrega. En caso de que no se pueda ninguna de las dos anteriores opciones, pues nos esperamos y hay que documentar esta implementación para despues.

Me gustaria que se pueda seleccionar un dia y se desplieguen las actividades correspondientes de ese dia, se deben de desplegar en la parte del plan del dia como si fueran las actividades del dia actual.

Cuando se seleccione el dia en la pantalla completa sera atravez de dar click en el dia correspondiente, en la columna encabezado que contenga el dia a seleccionar, puse la captura donde encierro en color verde donde se debe dar click y en color azul cielo donde se van a desplegar las actividades, creo que no hay pierde, pero por si acaso...

Cuando se este en pantalla pequeña, me gustaria que donde esta la columna del dia, en la celda del encabezado, que en el ejemplo es LUN 17, funcione como un detail summary, algo parecido a esa funcion, para que al dar click, se despliegue un calendario y se pueda seleccionar el dia, ademas de que las flechas tambien deberian ajustar las actividades correspondientes al dia.

No se si esta implementación ya esta, pero es importante.

Tambien hay que tener en cuenta que va a ver actividades que al solo realizarlas cierto dias, en los demas dias van a existir casillas vacias, esas casillas vacias podemos hacer que se pongan en gris como el estilo de una tarea cancelada, pero no quiero que dentro contenga ningun simbolo, así se puede ver que estan desabilitadas esas casillas.

Lo que propongo es que unicamente se vean las actividades corespondientes a esos dias, para el caso de pantalla completa, porque en la pantalla pequeña, pues si o si solo se ven las actidades de ese día y lo que te comento de desabilitar las casillas faltantes va a ser cuando las actividades pues se tengan que ver pero en otros dias no esten.

La consecuencia de esto es que cuando los renglones o actividades correspondientes a ese dia seleccionado esten visibles, estaran para otras casillas correspondientes a dias diferentes y eso esta bien, lo que no quiero, esque las actividades de otros dias esten visibles en el dia seleccionado, esas quiero que se escondan para el dia seleccionado.

Con esto, se me ocurre que antes de donde dice seguimiento actual y plan del dia, exista un boton con el signo se ojo abierto que indicara que se muestren o desplieguen todas las actividades planeadas para ese mes y que el ojo cerrado que sera el estado por defecto y cada que se cargue la pagina debera estar con el ojo cerrado, hara que se muestren unicamente las actividades correspondientes a ese dia.



What kind of music does memo ochoa like