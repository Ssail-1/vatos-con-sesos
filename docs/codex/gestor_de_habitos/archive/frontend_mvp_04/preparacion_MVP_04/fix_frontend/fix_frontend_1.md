
Hubo un detalle, y puso que la documentancion era extensa y se habia truncado, no se si haya sido porque la tarea la hizo en nivel bajo :(, no me di cuenta honestamente, pero cuando revise estaba en bajo.

Me habias dicho que lo hiciera con intermedio pero yo creo que se quito.

# Fix frontend

Esta vez si falto mucha producción jaja, igual y creo que ya me habias dicho pero estamos trabajando con codex a nivel medio, eso creía pero creo que esta vez trabajo a nivel bajo.

Pudo haber sido que falto mas nivel.

Vamos a empezar por partes conforme vayan saliendo.

## Navegación Mensual

Las flechas para navegar atravez de los meses las puso en entre las el texto "Plan del día", tanto en pantalla pequeña como grande.

### Pantalla completa

![Navegacion mensual actual pantalla grande](/docs/codex/gestor_de_habitos/archive/frontend_mvp_04/preparacion_MVP_04/fix_frontend/fix-assets/fix-assets-1/Nav-mensual-grande.png)

Recordemos  que en pantalla completa, las flechas deben estar a los laterales de la matriz. Como en la siguiente imagen como ya habiamos quedado anteriormente

![Navegacion mensual esperada pantalla grande](/docs/codex/gestor_de_habitos/archive/frontend_mvp_04/preparacion_MVP_04/fix_frontend/fix-assets/fix-assets-1/flechas-para-navegar-meses-en-pantalla-completa.png)

#### Estilo

Quiero que las flechas se vean como la imagen esperada, no se como esta la estructura html, pero me imagino que tanto el encabezado como la matriz y lo que esta debajo de la matriz estan al mismo nivel, quiero que las flechas esten a los laterales pero por fuera, que todas estas piezas del encabezado, matriz y pie, sigan la misma alineacion y las flechas por fuera, porque me imagino que hay muchas opciones y no quiero que las flechas las meta dentro del mismo width y reduzca solo la matriz.

Si es necesario reducir, que se redusca todo para que tenga el mismo width y por fuera las flechas pero no que redusca la matriz para meter las flechas y queden en alineacion con el encabezado y el pie.

### Pantalla pequeña

![Navegacion mensual actual pantalla pequeña](/docs/codex/gestor_de_habitos/archive/frontend_mvp_04/preparacion_MVP_04/fix_frontend/fix-assets/fix-assets-1/Nav-mensual-pequeña.png)

En esta pues no cambia mucho y no creo que cambie en realidad, aunque sabemos que debería.

Actualmente se esta posicionando como se muestra en la pantalla encerrado en azul.

Lo ideal y la idea principal es que las flechas esten a los laterales de donde dice el mes y el año, como se muestra en la imagen anterior pero dibujado en verde.

![Navegacion mensual esperada pantalla pequeña](/docs/codex/gestor_de_habitos/archive/frontend_mvp_04/preparacion_MVP_04/fix_frontend/fix-assets/fix-assets-1/flechas-para-navegar-meses-en-pantalla-pequeña.png)

Incluso en esta imagen que se encuentra en assets, mustro dibujado con azul que a los laterales rodeando mes y año deben estar las flechas.

#### Estilo

La verdad esque no me gusta que las flechas esten encerradas en botones (Por decirlo de alguna manera), creo que van bien para cuando estan rodeando el dia "Lunes, 24 de Agosto", pero para navegar por el mes no, porque ya esta reducido el tamaño y siento que es demaciado, de hecho me gustaria que solo tengan "<" y ">" y con una animacion tipo que se encoja y vuelva a hacerse grande, así minimamente, o que baje y suba un pixel, solo como para dar la ilucion de que si se toco o se activo.

## Vista mesual y Vista diaria

Actualmente si esta funcionando, pero su estilo es un boton y pues no fue esa la vista que esperabamos.
Cuando esta desactivada, que dijimos que es el estado por defecto aparece así "○ Plan del dia", que diga "Plan del dia" significa que codex entendio su esencia y eso esta bien, pero pues no es la idea que el front se vea así.

La prioridad es que aparezca al principio en la parte izquierda y despues normal, siga aparecion "SEGUIMIENTO MENSUAL" y abajo de eso "Plan del día" aunque si esta en el modo pantalla pequeña, en lugar de decir seguimiento mensual, diga "SEGUIMIENTO DIARIO".

Y solo debería aparecer un icono que sería lo ideal, pero por ahora busque unos simbolos en internet y podemos poner algunos de estos simbolos para representar un ojo cerrado:

`⊝`, `⊖`, `⊘`, `⨷` o `●`.

A mi me gustaria que de preferencia use el primero o el segundo, pero que use cualquiero de esos mientras se pueda ver en la mayoria de navegadores y no pierda su formato, puede copiar los simbolos de aqui y simplemente darles un mayor tamaño.

Para el simbolo de la vista mensual, quiero que use el simbolo del ojo abierto, puede usar estos:

`👁`, `ⓞ`, `Ⓞ`, `⦿` o `🅞`.

Aquí claro me gustaría que usara el primer simbolo, pero si no los otros pero mejor forzar a que use el primero.

Tambien al seleccionar y hacer el cambio podemos meter una ligera animación.

Y por ende que desaparezca ese boton original, no me gusto para nada, creo que en esta parte que parece la cabezera de la matriz, en si solo debio haberse agregado este boton con los dos simbolos.

El estilo, me gustaria que tampoco este dentro de un boton, quiero que como tal solo sea el simbolo en color dorado, creo que da buen contraste o tu checalo o que lo cheque codex pero en boton no, amenos que sea parte de la animación.

## Selecion de dias

### Pantalla completa

En pantalla completa el dia actual esta con un color diferente, en este caso en amarillo.

Entonces al momento de seleccionar un dia defirente al dia actual, el dia actual debe de dejar de estar en amarillo y ponerse en el dia seleccionado, para que de esta manera, visualmente se identifique que esta seleccionado el dia escogido por el usuario.

## Pantalla pequeña

En pantalla pequeña parece que en especifico este apartado o funcion funciona bien, donde decia la fecha seleccionada y abajo se despliega el plan del dia del dia que esta elegido, ya funciona como lo veía, si le doy click, se abre un submenu como el tipo selector para seleccionar la fecha, la idea original es que se diera click en la matriz en la celda donde dice el dia, por ejemplo "LUN 24", pero esta bien donde lo implemento, de hecho me gusto.

## Avanzar al siguiente mes

Hay un tema y es que cuando avanzamos al siguiente mes, el dia seleccionado, sigue siendo el dia actual o el dia que se haya elegido por el usuario, por ejemplo, abro el modulo y esta en agosto el dia de hoy 24, pero si sigo a septiembre sigue seleccionado lunes 24 de agosto y lo se porque en pantalla pequeña tenemos en medio el dia que esta seleccionado y aparece ese dia, pero en pantalla completa, no aparecen registros y aparece como "No hay registros programados".

Pero si se selecciona un dia de esos de septiembre, ya aparecen los registros que existen para ese mes.

Tambien pasa si avanzamos a los siguientes meses.

## Selector de mes

![Selector de mes fuera de alcance](/docs/codex/gestor_de_habitos/archive/frontend_mvp_04/preparacion_MVP_04/fix_frontend/fix-assets/fix-assets-1/Selector-de-mes-fuera%20de%20alcance.png)

Cuando le damos click a la fecha de "Mes de Año" funciona bien justo como queriamos, faltan las flechas de navegación a los lados pero funciona bien.

El tema es que el selector cuando se abre, aparece muy a la derecha y en pantalla completa no permite visualizar completamente los meses, en pantalla pequeña se sobresale del tamaño del navegador.

---

# Interfaz de registros

## Actividad Ancla

![Interfaz editar ancla](/docs/codex/gestor_de_habitos/archive/frontend_mvp_04/preparacion_MVP_04/fix_frontend/fix-assets/fix-assets-1/Interfaz-editar-ancla.png)

### Interfaz para editar por dia seleccionado

La interfaz esta bien, el tema es con personalizar los horarios independientes por dia y esque cuando se abre recien la interfaz, no hay ningun dia seleccionado.

Eso puede ser bueno para cuando vas a registrar un nuevo planItem, pero cuando es una actividad ya registrada como ancla o periodica que son las que se repiten en varios dias de la semana, deberían aparecer los dias que estan activos o almenos el ultimo generationConfig(Ya no recuerdo bien como se llama) guardado, porque pues de algo tiene que servir aparte de lo que ya habiamos dicho jeje.

Tambien estoy pensando que al seleccionar un dia, tenga 3 estados.

1. (Sin seleccionar) Normal como el domingo que se ve en la imagen. Que seria cuando no esta seleccionado.
2. 1 vez seleccionado sera el momento en que se despliegue debajo la opcion para asignar su horario propio.
   1. Quiero que se distinga porque estara igual en amarillo/dorado, el color que esta ahí, pero que en su horilla inferior derecha se ponga un circulo y dentro este el simbolo de lapicito.
   2. Eso significara o dara a entender que se puede editar.
   3. Por cierto, en la imagen no se ve, pero si despliegas el detail o summary, no sale nada.
   4. Sin embargo este estado de edicion, solo sera activo 1 por dia, no pueden haber dos dias en este estado, por eso es como edición por dia.
      1. Entonces si lunes ya se encuentra en estado edicion, pero no se modifico nada y se seleccionoi otro dia, Lunes pasa a estar en  el tercer estado que será activo y el dia que se seleccione despues de este pasara a estar en modo edicion.
      2. Puede que el horario sea igual para todos, entonces digamos que selecciona de lunes a viernes y despues da guardar.
      Significa que los horarios son iguales para todos los dias, el estado de viernes que fue el ultimo dia que selecciono estara en modo edición, pero si da en guardar pasara a estar activo. No se necesita que manualmente pase al modo activo
      3. Entonces, Sin tocar(Estado:Normal), 1 toque (Estado: Editar), 2 toque (Estado: Activo), 3 toque (Estado:Normal)
   5. Habiamos quedado que hora de inicio y finalizacion debian estar antes de poder editar los horarios por dia, pero esta bien así, me gusto, y no hay tema en que a la hora de editar los dias esten sin llenar los horarios.
   6. Si es que si se puede traer los horarios actuales ya registrados y que se vean en esta interfaz sería lo mejor, era lo que te mencionaba de que deberian de aparecer activos los dias que ya estan agendados, pero si no es posible o es muy complejo, lo podemos dejar para despues. Lo ideal sería que traiga la información de la semana iso actual en la que se encuentra, pero si no almenos que traiga generationConfig. O ya nada alv, pero que funcione lo de editar por dias en especifico jaja.

Aprovechando que estamos aqui, una vez que guarde los cambios de la actividad con la que te enseñe esto, no se guardaron los cambios, o talvez si, pero no se actualizo la matriz, osea, no hubieron cambios graficos.

## Evento/Imprevisto

No se si esto ya deba de estar resuelto, yo recuerdo que si ya funcionaba, pero ahorita que quiero guardar un evento o imprevisto, alproposito que choque con otra actividad, no me permite guardarlo y pero pone que el horario cruza con la actividad X y trunca, pero deberia de si avisar que trunca con X actividad y despues pedir confirmación para cancelar la actividad y sobreescribir este evento u imprevisto.
