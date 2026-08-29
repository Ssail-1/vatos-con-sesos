
# Modulo gestor de Habitos

## Objetivo

Será crear el organigrama dinamico inicial del gestor de hábitos, quiero que tengas en cuenta que el siguiente contenido seŕa el primer mvp funcional, la version inicial, pero el modulo se dirige hacia muchas mas funciones descritas en los otros documentos que te pedi leer como AGENTS.md en la raiz de este repo y los que se encuentran dentro de /vcs/codex pero principalmente del documento `HISTORIA_DEL_NEGOCIO.md` que fue de aqui donde redacte el porque y que problemas quiero resolver con este modulo.

Así como basarte el diseño principal de la siguiente imagen: 
!["Ejemplo del objetivo del organizador personal"](/docs/codex/assets/Ejemplo-objetivo-plantilla.png "Ejemplo de como quiero el organigrama")
Obviamente para nosotros en la version darkmode, siguiendo el patron o haciendo juego con la pagina principal.

## Ubicación de la implementación

### Donde se va a ver?

La implementacion de este modulo como dijimos sera en la ruta: `/vcs/modules/gestor_de_habitos/`

### Como se accedera al modulo?

Se accedera desde el panel de navegación, por ahora la ruta que le dí es esta `"/modules/gestor_de_habitos/index.html"` y el contenido se devera visualizar en `main`, quiero que hagas la implementación para que funcione y se vea bien.

Para el contenido responsive...

## Principal función

Es realizar el mapa y trakeo o seguimiento de los habitos y actividades que se planean para construir diciplina estrategica y visualizar los resultados de manera grafica.

Es por eso que las actividades las desglose en varios tipos porque no todas son iguales y no se comportan de la misma manera.

Mencionado lo anterior, te dare lo que yo considero mi vision de como seran las entidades de las actividades y habitos que se tienen que resgistrar.

## TrackeableItem (Entidad padre)

- id_trakeable_item
- Nombre
- Fecha_de_registro (fecha en la que se creo el habito)
- is_done (Será tipo booleado y dependera si el checkbox correspondiente se marco y significara que False = no se realizo, True = se realizo)

> [!note]
> No se como se deberia guardar el atributo is done, porque un TrackeableItem dependiendo desde su creación hasta su eliminación tiene que guardar un historial de los dias que se cumplio y los que no, sería como un arreglo, lista o no se si deba guardarlo en algun tipo de estructura por dia...

### Activities (Hereda de TrakeableItem y es hermano de "Habit")

- planned_start_time
- planned_end_time
- real_start_time
- real_end_time

> [!note]
> Aquí estos tambien son atributos, pero no son unicos porque almenos real_start_time y real_end_time pueden cambiar por dia u si en algun momento se modifica la rutina o actividad en general, tamgbien debera guardar los cambios de planned_start_time y planned_end_time, sera como guardar el historial de los tiempos cumplidos, no se como se deberia guardar en la base de datos...

> [!note]
> real_start_time y real_end_time serán opcionales en caso de que el usuario(que por ahora solo soy yo) haya tenido que realizar la activida fuera de las horas planeadas o la activida le tomo menos tiempo o mas tiempo de lo esperado.
>
> De aqui saldran 2 variables:
> 
> - `estimated_duration` y `real_duration`
>
> Y quiero que se vea en la interfaz cuando la pantalla este completa de esta manera:
>
> +---------------------------------------+  
> |                TIEMPO                 |  
> +-------------------+-------------------+  
> |     Estimado      |       Real        |  
> +---------------------------------------+  
> |      1h 30m       |      1h 45m       |  
> +-------------------+-------------------+  
>
> Ese registro es opcional y solo cambiara si el usuario desea cambiar el tiempo real que le tomo, de otra manera el tiempo real tambien sera el mismo que el estimado y de igual manera los tiempos real_start_time y real_end_time tambien seran los mismos que los registrados inicialmente o planned_start_time y planned_end_time respectivamente.
>

Honestamente no se si debería guardar los datos `estimated_duration` y `real_duration` en la base de datos, porque a mi pensamiento si en algun momento necesito hacer un analisis de datos con estos datos, los puedo sacar con los atributos anteriores. Aqui desearía que tu me ayudes a decidir si guardar estos datos o no.

> [!note]
> Las actividades que heredan de esta, son realmente reglas de negocio, lo estoy analizando y no encuentro atributos limitantes reales que no sean definidos por mi o naturalmente.

#### Anchor_Activity (Hereda de activities)

>[!note]
> Tenemos que encontrar los atributos que constituyen la entidad de esta clase o entidad de la base de datos para hacerla funcionar

Este tipo de actividades se repiten semanalmente por lo que a la hora de registrarla tenemos que hacerlo mediante un formulario donde se registre 

- la actividad
- los dias que se repite
- las horas en que inicia y termina, (tambien puede variar, dependiendo el día puede programarse en un horario diferente)
  - Esto lo menciono porque hay actividades como trabajos rolados, donde una semana tengas el primer turno, la otra el turno nocturno, o incluso si en la misma semana tienen diferentes turnos.
  - Es por esta necesidad que haremos un sobmodulo para modificar rutina. (despues lo especificare)
- Y una vez establecida los dias y el horario en que se repite la actividad cada semana se repetira como se registro y solo cambiara si se modifica la actividad o la rutina.

#### Periodic_Activity (Hereda de activities)

La diferencia y la necesidad de esta actividad es que forma parte de la rutina pero no se repite constantemente y sería bueno tener el registro de esta actividad para agendarizarla posteriormente. Por ejemplo:

- **Cortarse el cabello**, asi como esta, hay otras actividades que se repiten cada cierto tiempo y pueden ser agendadas o simplemente colarse el mismo dia que se van a realizar, por eso, al registrarse estas actividades se va a especificar si:
  - desea agendarse dias especificos, cada cierto tiempo o talvez cierto dia del mes.
  - O simplemente agendarse para un dia
    - Y cuando se tenga o se vaya a agregar una actividad como esta al seleccionar Actividad Periodica, se deben desplegar las actividades ya registradas para seleccionarla simplemente y se va ir haciendo un registro para posteriormente hace un submodulo o vista donde se visualizara o se hara un estudio analisis de las actividades...

#### Unforenseen_Activity (Hereda de activities)

Estas actividades, son mas bien imprevistos, situaciones que salen de la nada o que no estan en nuestro control como, visita al doctor por gripa, ponchadura de llanta, ayuda a un amigo, fiesta inesperada, etc.

Su objetivo es poder registrarla literalmente como imprevisto y solo se registraran en el momento, pero al igual que las periodicas nos sirve tener el registro porque apesar de ser imprevistos, puede que exista una repetición, por ejemplo enfermarse lo que lleva a una visita al doctor.

### Habit (Hermano de Activities)

#### TimeBoundHabit

Esta clase va a ser para un tipo de habito que sirva como checkpoint o alarma, por ejemplo

name = Despertarse
planned_start_time = 4:30
real_start_time = if (user not change){real_start_time = planned_star_time}  // Poniendo un ejemplo rapido y burdo

#### QuantitativeHabit

Este habito sera un habito algo como un logro, digamos que nos proponemos no fumar, si se logra simplemente se pone en el checbox una palomita, pero si se falla, que se pueda poneer cuantos cigarros se fumo.

Es por eso que quiero implementar algo como estos atributos:

- unit_type
- consumed_amount

Para que el usuario pueda definir las unidades, en este ejemplo (cigarros) y en consumed_amount la cantidad con la que fallo.

Este habito por ahora no es importante y no es necesario incluirlo en el mvp, porque sera visto en otra vista o submodulo y por ahora no es necesario pero va a existir...

## Hasta ahora como se verian estos datos graficamente...

Algunos de estos atributos en la interfaz o graficamente se deben ver algo así:

### Seguimiento temporal cerrado o resumido

!["Seguimiento temporal resumido sin cambios registrados"](/docs/codex/assets/Seguimiento%20temporal%20resumido%20sin%20cambios%20registrados.png "Seguimiento temporal resumido sin cambios registrados")

#### Datos sin modificaciones

Así es como quiero que se vean esta parte de los datos, solo se debe mostrar la hora de inicio que sería planned_start_time y estimado que sería el stimated_duration.

#### Con datos modificados

Si ya se agrego un tiempo real de inicio, ejecucion o ambos, debe mostrar la hora de inicio real y en lugar del estimado el tiempo real que le tomo, aunque los encabezados hablen del otro, pero solo si ya hubo un registro o modificaciones de tiempos reales.

### Seguimiento temporal abierto

Al dar click en > seguimiento temporal o en alguno de los signos de interrogacion correspondiente a cada habito o actividada, se abrira o collapsaran para mostrar mas datos o visualizar mas a fondo y detalladamente lo referentemente al tiempo estimado de una actividad y el tiempo real de ejecucion.  
Se debe ver de esta manera:

!["Seguimiento temporal collapsado con cambios registrados"](/docs/codex/assets/Seguimiento%20temporal%20collapsado%20con%20cambios%20registrados.png "Seguimiento temporal collapsado con cambios registrados")

### Click al signo de interrogación...

Si se le da click en los signos de interrogación, y el estado de seguimiento temporal esta cerrado o resumido pasara a estar abierto o collapsarse(no se si este bien dicho, si collapsado sea igual a abierto), en fin pasara abrirse para mostrar los datos mas amplios y si esta abierto se queda abierto.

Despues se abrira una ventana encima de esta vista con un overlay detras.

#### overlay

Si se le da click en alguna parte del overlay, esta ventana emergente para registrar cambios se cerrara amenos que ya se haya escrito algo, en caso de que se haya escrito algo el boton de descartar debera animarse para hacerse mas grande sobre su posicion y regresar a su posicion. Ya despues de dar click en descartar si se cerrara la ventana y desaparecera el overlay.

#### ventana emergente de registro o cambios

La ventana que se abrio debido a tocar algun signo de interrogación saldra con el proposito de modificar el tiempo real de inicio y finalización, porque hasta este punto planned_start_time y planned_end_time tienen el mismo valor que real_start_time y real_end_time.

Pero tambien tendra otras funciones como que al inicio debe de tener un boton que tenga la función de **Agregar un Habito/Actividad  ↑** y el habito que se agregue estara antes del habito al respecto de donde se selecciono el habito y actividad (mas adelante definimos el boton para agregar habito)

Debajo de ese boton estara el formulario que ingresara los nuevos datos del inicio real y final de ejecución. Visualmente quiero que parezca una tabla, de 3 x 2, la primera fila estaran combinadas las dos celdas y dira "Tiempo real de ejecución", debajo la segunda primera dira Inicio y la otra finalizacioń... en las celdas de abajo ya se podra ingresar la hora real que tomo realizar la actividad, por defecto deberan mostrar el mismo tiempo que el registrado al planeado, osea planned_start_time y planned_end_time (al registrarse sera con un `input type="time"` creo que si esa es la etiqueta correcta para seleccionar hora, minutos y si es am o pm, se puede usar el formato que sea mas facil de implementar, pero de preferencia me gusta el formato de 24hr), en caso de haber alguna modificacion ya se podra seleccionar un boton que estara debajo llamado **Actualizar**.

##### Funcion de boton actualizar

El boton se encontrara con un color opaco y no hara nada al dar click y so depues de que haya alguna modificacion se quitara lo opaco y ya podra actualizar los datos ingresados, despues de dar click la ventana se cerrara automaticamente.

La confirmación del boton actualizara el y mostrara el real_duration con base en la información actualizada y si despues se cierra el modo seguimieto temporal para mostrar menos detalles, ya mostrar la hora real de inicio y el tiempo real de ejecución, si no hay cambios se sigue mostrando la hora de inicio planeada y estimado de tiempo.
Independiente si se ingreso el tiempo final real de ejecucion, el checkbox correspondiente a ese dia se marcara palomeado.

alado del boton actualizar habra un boton que diga descartar.

##### Boton descartar dentro de Seguimiento temporal

Este boton tendrá la misma funcion del overlay, solo que apesar de que haya cambios, este si cerrara la ventana emergente y no se guardara o actualizaran los datos.

Debajo de los dos botones habra un boton que abarque el ancho de boton actualizar y descartar y este dira, eliminar actividad/habito.

##### Boton eliminar actividad/habito

Este boton al dar click, minimizara la ventana emergente y cambiara a otra ventana emergente que le pregunte al usuario si esta seguro de eliminar actividad o habito, dependiendo la naturaleza del trakeableItem, si es actividad dira actividad, si es habito dira habito. Abajo de los dos botones abrá otro para elegir eliminar la actividad actual, si decide eliminar, se elimina el renglon o la activida o habito de la vista del dia actual , seria como eliminar el renglon, pero esta actividad solo se eliminara para el dia actual y si esta programada en dias posteriores seguira apareciendo en los otros dias. Como tal la actividad solo podra ser eliminada a futuro desde otra submodulo dentro del modulo gestor de habitos, talvez lo agregue mas adelante en este documento o en una contrucción posterior.

Si se decicio eliminar la actividad, simplemente desaparece pero en la base de datos, la actividad el atributo is_done valdra false ese dia como si no se hubiera completado.

## Comportamiento esperado al ingresar real_start_time y real_end_time

Cuando se ingrese la hora final real en la que se termino la actividad, si la hora es menor a la planeada, las siguientes actividades se tendran que recorres hacia atras para empezar antes pero si la activada se termina mas tarde de lo planeado, las siguientes actividades se tienen que recorrer automaticamente, ejemplo:

digamos que la actividad esta planeada para terminar a las 10:00 pero se termina 10:35, entonces la siguiente actividad que talvez empezava 10:10, ahora automaticamente se pondra que empieza 10:35, porque a esa hora se termino la otra activida y rebaso su limite, de igual manera las siguiente actividades se van recorriendo.

Pero se recorren modificando su real_star_time y real_end_time, el planned_start_time y planned_end_time no se mueven.

### Boton "Agregar un Habito/Actividad  ↑" en ventana emergente de registro o cambios

Pendiente...
