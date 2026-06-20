"""
biblia.py — Bible parser and question generator for "Change" mode
Parses .bib files in format:  Book Chapter:Verse|text
Also provides an embedded verse collection as fallback.
"""
import re
import random
import json
import os
import threading

# ── Embedded RV1960 verses (key verses for "Versículos" category) ──
EMBEDDED_VERSES = [
    ("Génesis 1:1", "En el principio creó Dios los cielos y la tierra."),
    ("Génesis 1:3", "Y dijo Dios: Sea la luz; y fue la luz."),
    ("Génesis 1:27", "Y creó Dios al hombre a su imagen, a imagen de Dios lo creó; varón y hembra los creó."),
    ("Génesis 2:7", "Entonces Jehová Dios formó al hombre del polvo de la tierra, y sopló en su nariz aliento de vida, y fue el hombre un ser viviente."),
    ("Génesis 2:18", "Y dijo Jehová Dios: No es bueno que el hombre esté solo; le haré ayuda idónea para él."),
    ("Génesis 3:15", "Y pondré enemistad entre ti y la mujer, y entre tu simiente y la simiente suya; ésta te herirá en la cabeza, y tú le herirás en el calcañar."),
    ("Génesis 6:5", "Y vio Jehová que la maldad de los hombres era mucha en la tierra, y que todo designio de los pensamientos del corazón de ellos era de continuo solamente el mal."),
    ("Génesis 9:13", "Mi arco pondré en las nubes, el cual será por señal del pacto entre mí y la tierra."),
    ("Génesis 12:1", "Pero Jehová había dicho a Abram: Vete de tu tierra y de tu parentela, y de la casa de tu padre, a la tierra que te mostraré."),
    ("Génesis 12:2", "Y haré de ti una nación grande, y te bendeciré, y engrandeceré tu nombre, y serás bendición."),
    ("Génesis 15:6", "Y creyó a Jehová, y le fue contado por justicia."),
    ("Génesis 17:5", "Y no se llamará más tu nombre Abram, sino que será tu nombre Abraham, porque te he puesto por padre de muchedumbre de gentes."),
    ("Génesis 22:14", "Y llamó Abraham el nombre de aquel lugar, Jehová proveerá."),
    ("Génesis 28:12", "Y soñó: y he aquí una escalera que estaba apoyada en tierra, y su extremo tocaba en el cielo; y he aquí ángeles de Dios que subían y descendían por ella."),
    ("Génesis 32:28", "Y el varón dijo: No se dirá más tu nombre Jacob, sino Israel; porque has luchado con Dios y con los hombres, y has vencido."),
    ("Génesis 37:3", "Y amaba Israel a José más que a todos sus hijos, porque era el hijo de su vejez; y le hizo una túnica de diversos colores."),
    ("Génesis 50:20", "Vosotros pensasteis mal contra mí, mas Dios lo encaminó a bien, para hacer lo que vemos hoy, para mantener en vida a mucho pueblo."),
    ("Éxodo 3:14", "Y respondió Dios a Moisés: YO SOY EL QUE SOY. Y dijo: Así dirás a los hijos de Israel: YO SOY me envió a vosotros."),
    ("Éxodo 14:14", "Jehová peleará por vosotros, y vosotros estaréis tranquilos."),
    ("Éxodo 20:3", "No tendrás dioses ajenos delante de mí."),
    ("Éxodo 20:8", "Acuérdate del día de reposo para santificarlo."),
    ("Éxodo 20:12", "Honra a tu padre y a tu madre, para que tus días se alarguen en la tierra que Jehová tu Dios te da."),
    ("Éxodo 34:6", "Jehová, Jehová, Dios fuerte, misericordioso y piadoso; tardo para la ira y grande en misericordia y verdad."),
    ("Levítico 19:18", "No te vengarás, ni guardarás rencor a los hijos de tu pueblo, sino amarás a tu prójimo como a ti mismo."),
    ("Números 6:24", "Jehová te bendiga, y te guarde."),
    ("Números 6:25", "Jehová haga resplandecer su rostro sobre ti, y tenga de ti misericordia."),
    ("Deuteronomio 6:4", "Oye, Israel: Jehová nuestro Dios, Jehová uno es."),
    ("Deuteronomio 6:5", "Y amarás a Jehová tu Dios de todo tu corazón, y de toda tu alma, y con todas tus fuerzas."),
    ("Deuteronomio 6:7", "Y las repetirás a tus hijos, y hablarás de ellas estando en tu casa, y andando por el camino, y al acostarte, y cuando te levantes."),
    ("Deuteronomio 7:9", "Conoce, pues, que Jehová tu Dios es Dios, Dios fiel, que guarda el pacto y la misericordia a los que le aman y guardan sus mandamientos, hasta mil generaciones."),
    ("Deuteronomio 31:6", "Esforzaos y cobrad ánimo; no temáis, ni tengáis miedo de ellos, porque Jehová tu Dios es el que va contigo; no te dejará, ni te desamparará."),
    ("Josué 1:9", "Esfuérzate y sé valiente; no temas ni desmayes, porque Jehová tu Dios estará contigo en dondequiera que vayas."),
    ("Josué 24:15", "Escogeos hoy a quién sirváis; pero yo y mi casa serviremos a Jehová."),
    ("Jueces 6:12", "Jehová está contigo, varón esforzado y valiente."),
    ("Rut 1:16", "No me ruegues que te deje, y me aparte de ti; porque a dondequiera que tú fueres, iré yo, y dondequiera que vivieres, viviré."),
    ("1 Samuel 3:10", "Habla, porque tu siervo oye."),
    ("1 Samuel 15:22", "Ciertamente el obedecer es mejor que los sacrificios, y el prestar atención que la grosura de los carneros."),
    ("1 Samuel 16:7", "Jehová no mira lo que mira el hombre; pues el hombre mira lo que está delante de sus ojos, pero Jehová mira el corazón."),
    ("2 Samuel 22:31", "En cuanto a Dios, perfecto es su camino, y acrisolada la palabra de Jehová. Escudo es a todos los que en él esperan."),
    ("1 Reyes 3:9", "Da, pues, a tu siervo corazón entendido para juzgar a tu pueblo, y para discernir entre lo bueno y lo malo."),
    ("1 Reyes 18:21", "¿Hasta cuándo claudicaréis vosotros entre dos pensamientos? Si Jehová es Dios, seguidle."),
    ("2 Reyes 6:16", "No tengas miedo, porque más son los que están con nosotros que los que están con ellos."),
    ("1 Crónicas 4:10", "Oh, si me dieras bendición, y ensancharas mi territorio, y tu mano estuviera conmigo."),
    ("2 Crónicas 7:14", "Si se humillare mi pueblo, sobre el cual mi nombre es invocado, y oraren, y buscaren mi rostro, y se convirtieren de sus malos caminos; entonces yo oiré desde los cielos."),
    ("Esdras 7:10", "Porque Esdras había preparado su corazón para inquirir la ley de Jehová y para cumplirla, y para enseñar en Israel sus estatutos y decretos."),
    ("Nehemías 8:10", "No os entristezcáis, porque el gozo de Jehová es vuestra fortaleza."),
    ("Job 1:21", "Jehová dio, y Jehová quitó; sea el nombre de Jehová bendito."),
    ("Job 19:25", "Yo sé que mi Redentor vive, y al fin se levantará sobre el polvo."),
    ("Job 42:2", "Yo conozco que todo lo puedes, y que no hay pensamiento que se esconda de ti."),
    ("Salmos 1:1", "Bienaventurado el varón que no anduvo en consejo de malos, ni estuvo en camino de pecadores, ni en silla de escarnecedores se ha sentado."),
    ("Salmos 1:2", "Sino que en la ley de Jehová está su delicia, y en su ley medita de día y de noche."),
    ("Salmos 8:4", "Digo: ¿Qué es el hombre, para que tengas de él memoria, y el hijo del hombre, para que lo visites?"),
    ("Salmos 14:1", "Dice el necio en su corazón: No hay Dios."),
    ("Salmos 19:1", "Los cielos cuentan la gloria de Dios, y el firmamento anuncia la obra de sus manos."),
    ("Salmos 23:1", "Jehová es mi pastor; nada me faltará."),
    ("Salmos 23:4", "Aunque ande en valle de sombra de muerte, no temeré mal alguno, porque tú estarás conmigo."),
    ("Salmos 24:1", "De Jehová es la tierra y su plenitud; el mundo, y los que en él habitan."),
    ("Salmos 27:1", "Jehová es mi luz y mi salvación; ¿de quién temeré?"),
    ("Salmos 37:4", "Deléitate asimismo en Jehová, y él te concederá las peticiones de tu corazón."),
    ("Salmos 46:10", "Estad quietos, y conoced que yo soy Dios."),
    ("Salmos 51:10", "Crea en mí, oh Dios, un corazón limpio, y renueva un espíritu recto dentro de mí."),
    ("Salmos 91:1", "El que habita al abrigo del Altísimo morará bajo la sombra del Omnipotente."),
    ("Salmos 100:1", "Cantad alegres a Dios, habitantes de toda la tierra."),
    ("Salmos 103:1", "Bendice, alma mía, a Jehová, y bendiga todo mi ser su santo nombre."),
    ("Salmos 119:11", "En mi corazón he guardado tus dichos, para no pecar contra ti."),
    ("Salmos 119:105", "Lámpara es a mis pies tu palabra, y lumbrera a mi camino."),
    ("Salmos 121:1", "Alzaré mis ojos a los montes; ¿de dónde vendrá mi socorro?"),
    ("Salmos 121:2", "Mi socorro viene de Jehová, que hizo los cielos y la tierra."),
    ("Salmos 127:1", "Si Jehová no edificare la casa, en vano trabajan los que la edifican."),
    ("Salmos 139:14", "Te alabaré; porque formidables, maravillosas son tus obras."),
    ("Salmos 139:23", "Examíname, oh Dios, y conoce mi corazón; pruébame y conoce mis pensamientos."),
    ("Salmos 150:6", "Todo lo que respira alabe a Jehová."),
    ("Proverbios 1:7", "El principio de la sabiduría es el temor de Jehová."),
    ("Proverbios 3:5", "Fíate de Jehová de todo tu corazón, y no te apoyes en tu propia prudencia."),
    ("Proverbios 3:6", "Reconócelo en todos tus caminos, y él enderezará tus veredas."),
    ("Proverbios 4:23", "Sobre toda cosa guardada, guarda tu corazón; porque de él mana la vida."),
    ("Proverbios 9:10", "El temor de Jehová es el principio de la sabiduría, y el conocimiento del Santísimo es la inteligencia."),
    ("Proverbios 18:10", "Torre fuerte es el nombre de Jehová; a él correrá el justo y será levantado."),
    ("Proverbios 22:6", "Instruye al niño en su camino, y aun cuando fuere viejo no se apartará de él."),
    ("Eclesiastés 3:1", "Todo tiene su tiempo, y todo lo que se quiere debajo del cielo tiene su hora."),
    ("Eclesiastés 12:13", "El fin de todo el discurso oído es este: Teme a Dios, y guarda sus mandamientos; porque esto es el todo del hombre."),
    ("Isaías 1:18", "Venid luego, dice Jehová, y estemos a cuenta: si vuestros pecados fueren como la grana, como la nieve serán emblanquecidos."),
    ("Isaías 6:8", "Después oí la voz del Señor, que decía: ¿A quién enviaré, y quién irá por nosotros? Entonces respondí yo: Heme aquí, envíame a mí."),
    ("Isaías 7:14", "He aquí que la virgen concebirá, y dará a luz un hijo, y llamará su nombre Emanuel."),
    ("Isaías 9:6", "Porque un niño nos es nacido, hijo nos es dado, y el principado sobre su hombro; y se llamará su nombre Admirable, Consejero, Dios Fuerte, Padre Eterno, Príncipe de Paz."),
    ("Isaías 11:2", "Y reposará sobre él el Espíritu de Jehová; espíritu de sabiduría y de inteligencia, espíritu de consejo y de poder, espíritu de conocimiento y de temor de Jehová."),
    ("Isaías 26:3", "Tú guardarás en completa paz a aquel cuyo pensamiento en ti persevera; porque en ti ha confiado."),
    ("Isaías 40:31", "Pero los que esperan a Jehová tendrán nuevas fuerzas; levantarán alas como las águilas; correrán, y no se cansarán; caminarán, y no se fatigarán."),
    ("Isaías 41:10", "No temas, porque yo estoy contigo; no desmayes, porque yo soy tu Dios que te esfuerzo."),
    ("Isaías 43:2", "Cuando pases por las aguas, yo estaré contigo; y por los ríos, no te anegarán."),
    ("Isaías 53:5", "Mas él herido fue por nuestras rebeliones, molido por nuestros pecados; el castigo de nuestra paz fue sobre él, y por su llaga fuimos nosotros curados."),
    ("Isaías 55:11", "Así será mi palabra que sale de mi boca; no volverá a mí vacía, sino que hará lo que yo quiero, y será prosperada en aquello para que la envié."),
    ("Isaías 59:1", "He aquí que no se ha acortado la mano de Jehová para salvar, ni se ha agravado su oído para oír."),
    ("Jeremías 1:5", "Antes que te formase en el vientre te conocí, y antes que nacieses te santifiqué."),
    ("Jeremías 17:7", "Bendito el varón que confía en Jehová, y cuya confianza es Jehová."),
    ("Jeremías 29:11", "Porque yo sé los pensamientos que tengo acerca de vosotros, dice Jehová, pensamientos de paz, y no de mal, para daros el fin que esperáis."),
    ("Jeremías 33:3", "Clama a mí, y yo te responderé, y te enseñaré cosas grandes y ocultas que tú no conoces."),
    ("Lamentaciones 3:22", "Por la misericordia de Jehová no hemos sido consumidos, porque nunca decayeron sus misericordias."),
    ("Lamentaciones 3:23", "Nuevas son cada mañana; grande es tu fidelidad."),
    ("Ezequiel 11:19", "Y les daré un corazón, y un espíritu nuevo pondré dentro de ellos."),
    ("Ezequiel 18:4", "El alma que pecare, esa morirá."),
    ("Ezequiel 36:26", "Os daré corazón nuevo, y pondré espíritu nuevo dentro de vosotros."),
    ("Daniel 1:17", "Y a estos cuatro muchachos Dios les dio conocimiento e inteligencia en todas las letras y ciencias."),
    ("Daniel 2:21", "Él muda los tiempos y las edades; quita reyes, y pone reyes; da la sabiduría a los sabios, y la ciencia a los entendidos."),
    ("Daniel 3:17", "He aquí nuestro Dios a quien servimos puede librarnos del horno de fuego ardiente."),
    ("Daniel 6:22", "Mi Dios envió su ángel, el cual cerró la boca de los leones."),
    ("Daniel 12:3", "Los entendidos resplandecerán como el resplandor del firmamento; y los que enseñan a muchos la justicia, como las estrellas a perpetua eternidad."),
    ("Oseas 4:6", "Mi pueblo fue destruido, porque le faltó conocimiento."),
    ("Oseas 6:6", "Misericordia quiero, y no sacrificio, y conocimiento de Dios más que holocaustos."),
    ("Joel 2:28", "Derramaré mi Espíritu sobre toda carne, y profetizarán vuestros hijos y vuestras hijas."),
    ("Amós 3:3", "¿Andarán dos juntos, si no estuvieren de acuerdo?"),
    ("Amós 3:7", "Porque no hará nada Jehová el Señor, sin que revele su secreto a sus siervos los profetas."),
    ("Jonás 2:1", "Entonces oró Jonás a Jehová su Dios desde el vientre del pez."),
    ("Jonás 2:10", "Y mandó Jehová al pez, y vomitó a Jonás en tierra."),
    ("Miqueas 5:2", "Mas tú, Belén Efrata, pequeña para estar entre las familias de Judá, de ti me saldrá el que será Señor en Israel."),
    ("Miqueas 6:8", "Oh hombre, él te ha declarado lo que es bueno, y qué pide Jehová de ti: solamente hacer justicia, y amar misericordia, y humillarte ante tu Dios."),
    ("Habacuc 2:14", "La tierra será llena del conocimiento de la gloria de Jehová, como las aguas cubren el mar."),
    ("Sofonías 3:17", "Jehová está en medio de ti, poderoso, él salvará; se gozará sobre ti con alegría."),
    ("Hageo 2:9", "La gloria postrera de esta casa será mayor que la primera, ha dicho Jehová de los ejércitos."),
    ("Zacarías 4:6", "No con ejército, ni con fuerza, sino con mi Espíritu, ha dicho Jehová de los ejércitos."),
    ("Zacarías 9:9", "Alégrate mucho, hija de Sion; da voces de júbilo, hija de Jerusalén; he aquí tu rey vendrá a ti, justo y salvador."),
    ("Malaquías 3:10", "Traed todos los diezmos al alfolí y haya alimento en mi casa; y probadme ahora en esto, dice Jehová de los ejércitos, si no os abriré las ventanas de los cielos."),
    ("Malaquías 4:2", "Mas a vosotros los que teméis mi nombre, nacerá el Sol de justicia, y en sus alas traerá salvación."),
    ("Mateo 1:23", "He aquí, una virgen concebirá y dará a luz un hijo, y llamarán su nombre Emanuel, que traducido es: Dios con nosotros."),
    ("Mateo 4:4", "No solo de pan vivirá el hombre, sino de toda palabra que sale de la boca de Dios."),
    ("Mateo 5:3", "Bienaventurados los pobres en espíritu, porque de ellos es el reino de los cielos."),
    ("Mateo 5:5", "Bienaventurados los mansos, porque ellos recibirán la tierra por heredad."),
    ("Mateo 5:6", "Bienaventurados los que tienen hambre y sed de justicia, porque ellos serán saciados."),
    ("Mateo 5:7", "Bienaventurados los misericordiosos, porque ellos alcanzarán misericordia."),
    ("Mateo 5:8", "Bienaventurados los de limpio corazón, porque ellos verán a Dios."),
    ("Mateo 5:9", "Bienaventurados los pacificadores, porque ellos serán llamados hijos de Dios."),
    ("Mateo 5:14", "Vosotros sois la luz del mundo; una ciudad asentada sobre un monte no se puede esconder."),
    ("Mateo 5:16", "Así alumbre vuestra luz delante de los hombres, para que vean vuestras buenas obras, y glorifiquen a vuestro Padre que está en los cielos."),
    ("Mateo 6:3", "Mas cuando tú des limosna, no sepa tu izquierda lo que hace tu derecha."),
    ("Mateo 6:9", "Vosotros, pues, oraréis así: Padre nuestro que estás en los cielos, santificado sea tu nombre."),
    ("Mateo 6:10", "Venga tu reino. Hágase tu voluntad, como en el cielo, así también en la tierra."),
    ("Mateo 6:19", "No os hagáis tesoros en la tierra, donde la polilla y el orín corrompen."),
    ("Mateo 6:20", "Sino haceos tesoros en el cielo, donde ni la polilla ni el orín corrompen."),
    ("Mateo 6:21", "Porque donde esté vuestro tesoro, allí estará también vuestro corazón."),
    ("Mateo 6:24", "Ninguno puede servir a dos señores; porque o aborrecerá al uno y amará al otro, o estimará al uno y menospreciará al otro. No podéis servir a Dios y a las riquezas."),
    ("Mateo 7:7", "Pedid, y se os dará; buscad, y hallaréis; llamad, y se os abrirá."),
    ("Mateo 7:12", "Así que, todas las cosas que queráis que los hombres hagan con vosotros, así también haced vosotros con ellos."),
    ("Mateo 7:13", "Entrad por la puerta estrecha; porque ancha es la puerta, y espacioso el camino que lleva a la perdición."),
    ("Mateo 7:21", "No todo el que me dice: Señor, Señor, entrará en el reino de los cielos, sino el que hace la voluntad de mi Padre que está en los cielos."),
    ("Mateo 10:32", "A cualquiera, pues, que me confiese delante de los hombres, yo también le confesaré delante de mi Padre que está en los cielos."),
    ("Mateo 11:28", "Venid a mí todos los que estáis trabajados y cargados, y yo os haré descansar."),
    ("Mateo 11:29", "Llevad mi yugo sobre vosotros, y aprended de mí, que soy manso y humilde de corazón; y hallaréis descanso para vuestras almas."),
    ("Mateo 14:27", "Pero en seguida Jesús les habló, diciendo: ¡Tened ánimo; yo soy, no temáis!"),
    ("Mateo 16:18", "Y yo también te digo, que tú eres Pedro, y sobre esta roca edificaré mi iglesia; y las puertas del Hades no prevalecerán contra ella."),
    ("Mateo 17:5", "Este es mi Hijo amado, en quien tengo complacencia; a él oíd."),
    ("Mateo 19:14", "Dejad a los niños venir a mí, y no se lo impidáis; porque de los tales es el reino de los cielos."),
    ("Mateo 22:14", "Porque muchos son llamados, mas pocos escogidos."),
    ("Mateo 22:37", "Amarás al Señor tu Dios con todo tu corazón, y con toda tu alma, y con toda tu mente."),
    ("Mateo 22:39", "Amarás a tu prójimo como a ti mismo."),
    ("Mateo 24:35", "El cielo y la tierra pasarán, pero mis palabras no pasarán."),
    ("Mateo 28:19", "Por tanto, id, y haced discípulos a todas las naciones, bautizándolos en el nombre del Padre, y del Hijo, y del Espíritu Santo."),
    ("Mateo 28:20", "Enseñándoles que guarden todas las cosas que os he mandado; y he aquí yo estoy con vosotros todos los días, hasta el fin del mundo."),
    ("Marcos 10:27", "Para los hombres es imposible, mas para Dios todo es posible."),
    ("Marcos 11:24", "Por tanto, os digo que todo lo que pidieréis orando, creed que lo recibiréis, y os vendrá."),
    ("Marcos 12:30", "Amarás al Señor tu Dios con todo tu corazón, y con toda tu alma, y con toda tu mente, y con todas tus fuerzas."),
    ("Marcos 16:15", "Id por todo el mundo y predicad el evangelio a toda criatura."),
    ("Marcos 16:16", "El que creyere y fuere bautizado, será salvo; mas el que no creyere, será condenado."),
    ("Lucas 1:37", "Porque nada hay imposible para Dios."),
    ("Lucas 2:11", "Que os ha nacido hoy, en la ciudad de David, un Salvador, que es Cristo el Señor."),
    ("Lucas 2:14", "Gloria a Dios en las alturas, y en la tierra paz, buena voluntad para con los hombres."),
    ("Lucas 6:31", "Y como queréis que hagan los hombres con vosotros, así también haced vosotros con ellos."),
    ("Lucas 6:38", "Dad, y se os dará; medida buena, apretada, remecida y rebosando darán en vuestro regazo."),
    ("Lucas 10:27", "Amarás al Señor tu Dios con todo tu corazón, y con toda tu alma, y con todas tus fuerzas, y con todo tu entendimiento; y a tu prójimo como a ti mismo."),
    ("Lucas 15:10", "Así os digo que hay gozo delante de los ángeles de Dios por un pecador que se arrepiente."),
    ("Lucas 19:10", "Porque el Hijo del Hombre vino a buscar y a salvar lo que se había perdido."),
    ("Lucas 24:6", "No está aquí, sino que ha resucitado."),
    ("Juan 1:1", "En el principio era el Verbo, y el Verbo era con Dios, y el Verbo era Dios."),
    ("Juan 1:3", "Todas las cosas por él fueron hechas, y sin él nada de lo que ha sido hecho, fue hecho."),
    ("Juan 1:12", "Mas a todos los que le recibieron, a los que creen en su nombre, les dio potestad de ser hechos hijos de Dios."),
    ("Juan 1:14", "Y aquel Verbo fue hecho carne, y habitó entre nosotros, y vimos su gloria, gloria como del unigénito del Padre, lleno de gracia y de verdad."),
    ("Juan 1:29", "He aquí el Cordero de Dios, que quita el pecado del mundo."),
    ("Juan 3:3", "De cierto, de cierto te digo, que el que no naciere de nuevo, no puede ver el reino de Dios."),
    ("Juan 3:16", "Porque de tal manera amó Dios al mundo, que ha dado a su Hijo unigénito, para que todo aquel que en él cree, no se pierda, mas tenga vida eterna."),
    ("Juan 3:17", "Porque no envió Dios a su Hijo al mundo para condenar al mundo, sino para que el mundo sea salvo por él."),
    ("Juan 8:32", "Y conoceréis la verdad, y la verdad os hará libres."),
    ("Juan 10:10", "Yo he venido para que tengan vida, y para que la tengan en abundancia."),
    ("Juan 10:11", "Yo soy el buen pastor; el buen pastor su vida da por las ovejas."),
    ("Juan 11:25", "Yo soy la resurrección y la vida; el que cree en mí, aunque esté muerto, vivirá."),
    ("Juan 13:34", "Un mandamiento nuevo os doy: Que os améis unos a otros; como yo os he amado."),
    ("Juan 14:6", "Yo soy el camino, y la verdad, y la vida; nadie viene al Padre, sino por mí."),
    ("Juan 14:15", "Si me amáis, guardad mis mandamientos."),
    ("Juan 14:27", "La paz os dejo, mi paz os doy; yo no os la doy como el mundo la da. No se turbe vuestro corazón, ni tenga miedo."),
    ("Juan 15:5", "Yo soy la vid, vosotros los pámpanos; el que permanece en mí, y yo en él, éste lleva mucho fruto; porque separados de mí nada podéis hacer."),
    ("Juan 15:13", "Nadie tiene mayor amor que este, que uno ponga su vida por sus amigos."),
    ("Juan 16:33", "En el mundo tendréis aflicción; pero confiad, yo he vencido al mundo."),
    ("Juan 20:31", "Pero estas se han escrito para que creáis que Jesús es el Cristo, el Hijo de Dios, y para que creyendo, tengáis vida en su nombre."),
    ("Hechos 1:8", "Pero recibiréis poder, cuando haya venido sobre vosotros el Espíritu Santo, y me seréis testigos en Jerusalén, en toda Judea, en Samaria, y hasta lo último de la tierra."),
    ("Hechos 2:38", "Arrepentíos, y bautícese cada uno de vosotros en el nombre de Jesucristo para perdón de los pecados; y recibiréis el don del Espíritu Santo."),
    ("Hechos 4:12", "Y en ningún otro hay salvación; porque no hay otro nombre bajo el cielo, dado a los hombres, en que podamos ser salvos."),
    ("Hechos 5:29", "Es necesario obedecer a Dios antes que a los hombres."),
    ("Hechos 8:39", "Y el Espíritu Santo arrebató a Felipe; y el eunuco no le vio más."),
    ("Hechos 9:4", "Saulo, Saulo, ¿por qué me persigues?"),
    ("Hechos 9:15", "Instrumento escogido me es éste, para llevar mi nombre en presencia de los gentiles."),
    ("Hechos 10:34", "En verdad comprendo que Dios no hace acepción de personas."),
    ("Hechos 16:31", "Cree en el Señor Jesucristo, y serás salvo, tú y tu casa."),
    ("Hechos 17:11", "Y éstos eran más nobles que los que estaban en Tesalónica, pues recibieron la palabra con toda solicitud, escudriñando cada día las Escrituras."),
    ("Romanos 1:16", "Porque no me avergüenzo del evangelio, porque es poder de Dios para salvación a todo aquel que cree."),
    ("Romanos 3:23", "Por cuanto todos pecaron, y están destituidos de la gloria de Dios."),
    ("Romanos 5:8", "Mas Dios muestra su amor para con nosotros, en que siendo aún pecadores, Cristo murió por nosotros."),
    ("Romanos 6:23", "Porque la paga del pecado es muerte, mas la dádiva de Dios es vida eterna en Cristo Jesús Señor nuestro."),
    ("Romanos 8:1", "Ahora, pues, ninguna condenación hay para los que están en Cristo Jesús."),
    ("Romanos 8:15", "Pues no habéis recibido el espíritu de esclavitud para estar otra vez en temor, sino que habéis recibido el espíritu de adopción, por el cual clamamos: ¡Abba, Padre!"),
    ("Romanos 8:28", "A los que aman a Dios, todas las cosas les ayudan a bien."),
    ("Romanos 8:31", "Si Dios es por nosotros, ¿quién contra nosotros?"),
    ("Romanos 8:37", "En todas estas cosas somos más que vencedores por medio de aquel que nos amó."),
    ("Romanos 8:38", "Por lo cual estoy seguro de que ni la muerte, ni la vida, ni ángeles, ni principados, ni potestades, ni lo presente, ni lo por venir."),
    ("Romanos 8:39", "Ni lo alto, ni lo profundo, ni ninguna otra cosa creada nos podrá separar del amor de Dios, que es en Cristo Jesús Señor nuestro."),
    ("Romanos 10:9", "Si confesares con tu boca que Jesús es el Señor, y creyeres en tu corazón que Dios le levantó de los muertos, serás salvo."),
    ("Romanos 10:17", "Así que la fe es por el oír, y el oír, por la palabra de Dios."),
    ("Romanos 12:1", "Que presentéis vuestros cuerpos en sacrificio vivo, santo, agradable a Dios, que es vuestro culto racional."),
    ("Romanos 12:2", "No os conforméis a este siglo, sino transformaos por medio de la renovación de vuestro entendimiento."),
    ("Romanos 12:21", "No seas vencido de lo malo, sino vence con el bien el mal."),
    ("Romanos 14:11", "Toda lengua confesará que Jesús es el Señor, para gloria de Dios Padre."),
    ("1 Corintios 1:18", "Porque la palabra de la cruz es locura a los que se pierden; pero a los que se salvan, esto es, a nosotros, es poder de Dios."),
    ("1 Corintios 2:9", "Cosas que ojo no vio, ni oído oyó, ni han subido en corazón de hombre, son las que Dios ha preparado para los que le aman."),
    ("1 Corintios 3:16", "¿No sabéis que sois templo de Dios, y que el Espíritu de Dios mora en vosotros?"),
    ("1 Corintios 6:19", "¿O ignoráis que vuestro cuerpo es templo del Espíritu Santo, el cual está en vosotros?"),
    ("1 Corintios 10:13", "Fiel es Dios, que no os dejará ser tentados más de lo que podéis resistir."),
    ("1 Corintios 13:4", "El amor es sufrido, es benigno; el amor no tiene envidia, el amor no es jactancioso, no se envanece."),
    ("1 Corintios 13:5", "No hace nada indebido, no busca lo suyo, no se irrita, no guarda rencor."),
    ("1 Corintios 13:7", "Todo lo sufre, todo lo cree, todo lo espera, todo lo soporta."),
    ("1 Corintios 13:8", "El amor nunca deja de ser."),
    ("1 Corintios 15:58", "Así que, hermanos míos amados, estad firmes y constantes, creciendo en la obra del Señor siempre."),
    ("2 Corintios 5:17", "De modo que si alguno está en Cristo, nueva criatura es; las cosas viejas pasaron; he aquí todas son hechas nuevas."),
    ("2 Corintios 6:2", "He aquí ahora el tiempo aceptable; he aquí ahora el día de salvación."),
    ("2 Corintios 9:7", "Dios ama al dador alegre."),
    ("Gálatas 2:20", "Con Cristo estoy juntamente crucificado, y ya no vivo yo, mas vive Cristo en mí."),
    ("Gálatas 5:22", "Mas el fruto del Espíritu es amor, gozo, paz, paciencia, benignidad, bondad, fe."),
    ("Gálatas 5:23", "Mansedumbre, templanza; contra tales cosas no hay ley."),
    ("Efesios 2:8", "Porque por gracia sois salvos por medio de la fe; y esto no de vosotros, pues es don de Dios."),
    ("Efesios 2:9", "No por obras, para que nadie se gloríe."),
    ("Efesios 4:26", "Airaos, pero no pequéis; no se ponga el sol sobre vuestro enojo."),
    ("Efesios 5:18", "No os embriaguéis con vino, en lo cual hay disolución; antes bien sed llenos del Espíritu."),
    ("Efesios 6:10", "Fortaleceos en el Señor, y en el poder de su fuerza."),
    ("Efesios 6:11", "Vestíos de toda la armadura de Dios, para que podáis estar firmes contra las asechanzas del diablo."),
    ("Efesios 6:17", "Tomad el yelmo de la salvación, y la espada del Espíritu, que es la palabra de Dios."),
    ("Filipenses 1:21", "Porque para mí el vivir es Cristo, y el morir es ganancia."),
    ("Filipenses 2:10", "Para que en el nombre de Jesús se doble toda rodilla de los que están en los cielos, y en la tierra, y debajo de la tierra."),
    ("Filipenses 2:11", "Y toda lengua confiese que Jesucristo es el Señor, para gloria de Dios Padre."),
    ("Filipenses 4:13", "Todo lo puedo en Cristo que me fortalece."),
    ("Filipenses 4:19", "Mi Dios, pues, suplirá todo lo que os falta conforme a sus riquezas en gloria en Cristo Jesús."),
    ("Colosenses 3:2", "Poned la mira en las cosas de arriba, no en las de la tierra."),
    ("Colosenses 3:14", "Sobre todas estas cosas vestíos de amor, que es el vínculo perfecto."),
    ("1 Tesalonicenses 5:17", "Orad sin cesar."),
    ("1 Tesalonicenses 5:18", "Dad gracias en todo, porque esta es la voluntad de Dios para con vosotros en Cristo Jesús."),
    ("1 Timoteo 2:5", "Porque hay un solo Dios, y un solo mediador entre Dios y los hombres, Jesucristo hombre."),
    ("1 Timoteo 4:12", "Ninguno tenga en poco tu juventud, sino sé ejemplo de los creyentes en palabra, conducta, amor, espíritu, fe y pureza."),
    ("1 Timoteo 6:10", "Porque raíz de todos los males es el amor al dinero."),
    ("2 Timoteo 1:7", "Porque no nos ha dado Dios espíritu de cobardía, sino de poder, de amor y de dominio propio."),
    ("2 Timoteo 3:16", "Toda la Escritura es inspirada por Dios, y útil para enseñar, para redargüir, para corregir, para instruir en justicia."),
    ("Tito 2:13", "Aguardando la esperanza bienaventurada y la manifestación gloriosa de nuestro gran Dios y Salvador Jesucristo."),
    ("Hebreos 1:1", "Dios, habiendo hablado muchas veces y de muchas maneras en otro tiempo a los padres por los profetas."),
    ("Hebreos 4:12", "Porque la palabra de Dios es viva y eficaz, y más cortante que toda espada de dos filos."),
    ("Hebreos 11:1", "Es, pues, la fe la certeza de lo que se espera, la convicción de lo que no se ve."),
    ("Hebreos 11:6", "Sin fe es imposible agradar a Dios; porque es necesario que el que se acerca a Dios crea que le hay, y que es galardonador de los que le buscan."),
    ("Hebreos 12:2", "Puestos los ojos en Jesús, el autor y consumador de la fe."),
    ("Hebreos 12:11", "Ninguna disciplina al presente parece ser causa de gozo, sino de tristeza; pero después da fruto apacible de justicia a los que en ella han sido ejercitados."),
    ("Hebreos 13:8", "Jesucristo es el mismo ayer, y hoy, y por los siglos."),
    ("Santiago 1:2", "Hermanos míos, tened por sumo gozo cuando os halléis en diversas pruebas."),
    ("Santiago 1:3", "Sabiendo que la prueba de vuestra fe produce paciencia."),
    ("Santiago 1:17", "Toda buena dádiva y todo don perfecto desciende de lo alto, del Padre de las luces."),
    ("Santiago 2:17", "Así también la fe, si no tiene obras, es muerta en sí misma."),
    ("Santiago 2:26", "Como el cuerpo sin espíritu está muerto, así también la fe sin obras está muerta."),
    ("Santiago 4:7", "Someteos, pues, a Dios; resistid al diablo, y huirá de vosotros."),
    ("Santiago 4:8", "Acercaos a Dios, y él se acercará a vosotros."),
    ("1 Pedro 1:3", "Bendito el Dios y Padre de nuestro Señor Jesucristo, que según su grande misericordia nos hizo renacer para una esperanza viva."),
    ("1 Pedro 2:24", "Cristo llevó nuestros pecados en su cuerpo sobre el madero."),
    ("1 Pedro 3:15", "Santificad a Dios el Señor en vuestros corazones, y estad siempre preparados para presentar defensa con mansedumbre y reverencia ante todo el que os demande razón de la esperanza que hay en vosotros."),
    ("1 Pedro 5:7", "Echad toda vuestra ansiedad sobre él, porque él tiene cuidado de vosotros."),
    ("2 Pedro 1:21", "Los santos hombres de Dios hablaron siendo inspirados por el Espíritu Santo."),
    ("2 Pedro 3:9", "El Señor no retarda su promesa, según algunos la tienen por tardanza, sino que es paciente para con nosotros, no queriendo que ninguno perezca, sino que todos procedan al arrepentimiento."),
    ("1 Juan 1:7", "La sangre de Jesucristo su Hijo nos limpia de todo pecado."),
    ("1 Juan 1:9", "Si confesamos nuestros pecados, él es fiel y justo para perdonar nuestros pecados, y limpiarnos de toda maldad."),
    ("1 Juan 3:1", "Mirad cuál amor nos ha dado el Padre, para que seamos llamados hijos de Dios."),
    ("1 Juan 3:16", "En esto hemos conocido el amor, en que él puso su vida por nosotros; también nosotros debemos poner nuestras vidas por los hermanos."),
    ("1 Juan 4:8", "Dios es amor."),
    ("1 Juan 4:19", "Nosotros le amamos a él, porque él nos amó primero."),
    ("1 Juan 5:11", "Dios nos ha dado vida eterna; y esta vida está en su Hijo."),
    ("1 Juan 5:13", "Estas cosas os he escrito a vosotros que creéis en el nombre del Hijo de Dios, para que sepáis que tenéis vida eterna."),
    ("2 Juan 1:6", "Este es el amor, que andemos según sus mandamientos."),
    ("Judas 1:24", "Aquél que es poderoso para guardaros sin caída, y presentaros sin mancha delante de su gloria con gran alegría."),
    ("Apocalipsis 1:8", "Yo soy el Alfa y la Omega, principio y fin, dice el Señor, el que es y que era y que ha de venir, el Todopoderoso."),
    ("Apocalipsis 1:18", "Yo soy el que vivo, y estuve muerto; mas he aquí que vivo por los siglos de los siglos."),
    ("Apocalipsis 3:20", "He aquí, yo estoy a la puerta y llamo; si alguno oye mi voz y abre la puerta, entraré a él, y cenaré con él, y él conmigo."),
    ("Apocalipsis 4:11", "Señor, digno eres de recibir la gloria y la honra y el poder; porque tú creaste todas las cosas."),
    ("Apocalipsis 7:14", "Estos son los que han salido de la gran tribulación, y han lavado sus ropas, y las han emblanquecido en la sangre del Cordero."),
    ("Apocalipsis 21:1", "Vi un cielo nuevo y una tierra nueva; porque el primer cielo y la primera tierra pasaron."),
    ("Apocalipsis 21:4", "Enjugará Dios toda lágrima de los ojos de ellos; y ya no habrá muerte, ni habrá más llanto, ni clamor, ni dolor."),
    ("Apocalipsis 21:6", "Yo soy el Alfa y la Omega, el principio y el fin. Al que tuviere sed, yo le daré gratuitamente de la fuente del agua de la vida."),
    ("Apocalipsis 22:13", "Yo soy el Alfa y la Omega, el primero y el último, el principio y el fin."),
    ("Apocalipsis 22:17", "El que tiene sed, venga; y el que quiera, tome del agua de la vida gratuitamente."),
    ("Apocalipsis 22:20", "Sí, vengo pronto. Amén; sí, ven, Señor Jesús."),
]

# ── Personajes bíblicos para "¿Quién soy?" ──
PERSONAJES = [
    {
        "nombre": "Adán",
        "pistas": [
            "Fue formado del polvo de la tierra",
            "Fue puesto en un jardín al oriente del Edén",
            "Puso nombre a todos los animales",
            "Su desobediencia trajo el pecado al mundo"
        ],
        "libro": "Génesis",
        "epoca": "Creación (~4000 a.C.)"
    },
    {
        "nombre": "Eva",
        "pistas": [
            "Fue creada de una costilla",
            "La serpiente le engañó en el huerto",
            "Fue llamada madre de todos los vivientes",
            "Comió del fruto prohibido y se lo dio a su esposo"
        ],
        "libro": "Génesis",
        "epoca": "Creación (~4000 a.C.)"
    },
    {
        "nombre": "Noé",
        "pistas": [
            "Halló gracia ante los ojos de Jehová",
            "Construyó un arca de madera de gofer",
            "Dios hizo un pacto con él usando un arcoíris",
            "Por su fe, su familia se salvó del diluvio"
        ],
        "libro": "Génesis",
        "epoca": "~2500 a.C."
    },
    {
        "nombre": "Abraham",
        "pistas": [
            "Dios le llamó a salir de Ur de los Caldeos",
            "Se le prometió una descendencia numerosa como las estrellas",
            "Dios cambió su nombre de Abram a este nombre",
            "Estuvo dispuesto a sacrificar a su hijo Isaac"
        ],
        "libro": "Génesis",
        "epoca": "~2000 a.C."
    },
    {
        "nombre": "Sara",
        "pistas": [
            "Era estéril y de edad avanzada",
            "Dios le prometió un hijo y ella se rió",
            "Dio a luz a Isaac a los 90 años",
            "Su nombre significa 'princesa'"
        ],
        "libro": "Génesis",
        "epoca": "~2000 a.C."
    },
    {
        "nombre": "Isaac",
        "pistas": [
            "Su nombre significa 'risa'",
            "Su padre casi le sacrifica en un monte",
            "Se casó con Rebeca",
            "Fue padre de Esaú y Jacob"
        ],
        "libro": "Génesis",
        "epoca": "~1900 a.C."
    },
    {
        "nombre": "Jacob",
        "pistas": [
            "Compró la primogenitura a su hermano por un plato de lentejas",
            "Engañó a su padre para recibir la bendición",
            "Luchó con un ángel toda la noche",
            "Dios le cambió el nombre a Israel"
        ],
        "libro": "Génesis",
        "epoca": "~1800 a.C."
    },
    {
        "nombre": "José",
        "pistas": [
            "Su padre le hizo una túnica de diversos colores",
            "Fue vendido como esclavo por sus hermanos",
            "Interpretó los sueños del faraón",
            "Dijo: 'Vosotros pensasteis mal contra él, mas Dios lo encaminó a bien'"
        ],
        "libro": "Génesis",
        "epoca": "~1700 a.C."
    },
    {
        "nombre": "Moisés",
        "pistas": [
            "Fue salvado de las aguas del Nilo en una cesta",
            "Dios le habló desde una zarza ardiente",
            "Partió el Mar Rojo con su vara",
            "Recibió los Diez Mandamientos en el Monte Sinaí"
        ],
        "libro": "Éxodo",
        "epoca": "~1440 a.C."
    },
    {
        "nombre": "Aarón",
        "pistas": [
            "Fue el hermano mayor de un gran profeta",
            "Fue portavoz porque su hermano era lento de palabra",
            "Su vara floreció como señal del sacerdocio",
            "Fue el primer sumo sacerdote de Israel"
        ],
        "libro": "Éxodo",
        "epoca": "~1440 a.C."
    },
    {
        "nombre": "Josué",
        "pistas": [
            "Fue el ayudante de Moisés desde joven",
            "Fue uno de los doce espías que trajeron buen informe",
            "Cruzó el Jordán con el arca del pacto",
            "Derribó los muros de Jericó con trompetas"
        ],
        "libro": "Josué",
        "epoca": "~1400 a.C."
    },
    {
        "nombre": "Gedeón",
        "pistas": [
            "Le llamaban el menor de la casa de su padre",
            "Dios le llamó 'varón esforzado y valiente'",
            "Redujo su ejército de 32,000 a 300 hombres",
            "Venció a los madianitas con cántaros y trompetas"
        ],
        "libro": "Jueces",
        "epoca": "~1200 a.C."
    },
    {
        "nombre": "Sansón",
        "pistas": [
            "Su fuerza estaba en su cabello",
            "Mató un león con sus manos",
            "Mató a 1,000 filisteos con una quijada de asno",
            "Derribó el templo de Dagón sobre sus enemigos"
        ],
        "libro": "Jueces",
        "epoca": "~1100 a.C."
    },
    {
        "nombre": "Rut",
        "pistas": [
            "Era moabita, no israelita",
            "Dijo: 'A dondequiera que tú fueres, iré yo'",
            "Espigó en los campos de Booz",
            "Fue bisabuela del rey David"
        ],
        "libro": "Rut",
        "epoca": "~1100 a.C."
    },
    {
        "nombre": "Samuel",
        "pistas": [
            "Su madre Ana le dedicó al Señor desde niño",
            "Dios le llamó tres veces en la noche",
            "Respondió: 'Habla, porque tu siervo oye'",
            "Fue el último juez de Israel y ungió a sus primeros reyes"
        ],
        "libro": "1 Samuel",
        "epoca": "~1050 a.C."
    },
    {
        "nombre": "David",
        "pistas": [
            "Era pastor de ovejas cuando fue ungido rey",
            "Venció a un gigante con una honda y cinco piedras",
            "Escribió muchos salmos",
            "Dios dijo que era un hombre conforme a su corazón"
        ],
        "libro": "1 Samuel / Salmos",
        "epoca": "~1000 a.C."
    },
    {
        "nombre": "Salomón",
        "pistas": [
            "Pidió sabiduría a Dios en lugar de riquezas",
            "Construyó el templo de Jerusalén",
            "Escribió Proverbios y Eclesiastés",
            "Fue conocido por su sabiduría y riquezas"
        ],
        "libro": "1 Reyes / Proverbios",
        "epoca": "~950 a.C."
    },
    {
        "nombre": "Elías",
        "pistas": [
            "Profetizó una sequía de tres años",
            "Fue alimentado por cuervos",
            "Venció a 450 profetas de Baal en el Monte Carmelo",
            "Fue llevado al cielo en un carro de fuego"
        ],
        "libro": "1 Reyes",
        "epoca": "~870 a.C."
    },
    {
        "nombre": "Eliseo",
        "pistas": [
            "Recibió una doble porción del espíritu de su maestro",
            "Sanó las aguas de Jericó con sal",
            "Hizo flotar el hierro de un hacha",
            "Resucitó al hijo de la sunamita"
        ],
        "libro": "2 Reyes",
        "epoca": "~850 a.C."
    },
    {
        "nombre": "Isaías",
        "pistas": [
            "Vio al Señor alto y sublime sobre un trono",
            "Dijo: 'Heme aquí, envíame a mí'",
            "Profetizó el nacimiento virginal del Mesías",
            "Escribió sobre el Siervo Sufriente"
        ],
        "libro": "Isaías",
        "epoca": "~740 a.C."
    },
    {
        "nombre": "Jeremías",
        "pistas": [
            "Fue llamado desde el vientre de su madre",
            "Es conocido como el profeta llorón",
            "Dios le dijo: 'No digas: soy niño'",
            "Escribió Lamentaciones"
        ],
        "libro": "Jeremías",
        "epoca": "~600 a.C."
    },
    {
        "nombre": "Daniel",
        "pistas": [
            "Fue llevado cautivo a Babilonia",
            "Interpretó los sueños de Nabucodonosor",
            "Fue echado al foso de los leones",
            "Dios cerró la boca de los leones"
        ],
        "libro": "Daniel",
        "epoca": "~550 a.C."
    },
    {
        "nombre": "Jonás",
        "pistas": [
            "Dios le dijo que fuera a Nínive, pero huyó",
            "Fue tragado por un gran pez",
            "Estuvo tres días en el vientre del pez",
            "Predicó arrepentimiento a Nínive"
        ],
        "libro": "Jonás",
        "epoca": "~780 a.C."
    },
    {
        "nombre": "Zacarías",
        "pistas": [
            "Era sacerdote y quedó mudo por su incredulidad",
            "Recibió la visita del ángel Gabriel en el templo",
            "Su esposa Elisabet concibió en su vejez",
            "Fue padre de Juan el Bautista"
        ],
        "libro": "Lucas",
        "epoca": "~5 a.C."
    },
    {
        "nombre": "María",
        "pistas": [
            "El ángel Gabriel le saludó como 'muy favorecida'",
            "Dijo: 'He aquí la sierva del Señor'",
            "Su alma engrandece al Señor",
            "Fue la madre de Jesús"
        ],
        "libro": "Lucas",
        "epoca": "~5 a.C."
    },
    {
        "nombre": "Juan el Bautista",
        "pistas": [
            "Vestía pelo de camello y comía langostas",
            "Bautizó en el río Jordán",
            "Dijo: 'Arrepentíos, porque el reino de los cielos se ha acercado'",
            "Bautizó a Jesús y vio al Espíritu descender como paloma"
        ],
        "libro": "Los Evangelios",
        "epoca": "~27 d.C."
    },
    {
        "nombre": "Pedro",
        "pistas": [
            "Era pescador en el mar de Galilea",
            "Anduvo sobre las aguas hacia Jesús",
            "Dijo: 'Tú eres el Cristo, el Hijo del Dios viviente'",
            "Negó a Jesús tres veces y luego fue restaurado"
        ],
        "libro": "Los Evangelios / Hechos",
        "epoca": "~30-60 d.C."
    },
    {
        "nombre": "Juan (Apóstol)",
        "pistas": [
            "Le llamaban 'el discípulo amado'",
            "Fue el único apóstol que no murió mártir",
            "Escribió un evangelio, tres epístolas y Apocalipsis",
            "Escribió: 'Dios es amor'"
        ],
        "libro": "Juan / Apocalipsis",
        "epoca": "~30-100 d.C."
    },
    {
        "nombre": "Pablo",
        "pistas": [
            "Antes le llamaba Saulo",
            "Perseguía a los cristianos hasta que Jesús le cegó",
            "Fue derribado en el camino a Damasco",
            "Escribió la mayoría de las epístolas del Nuevo Testamento"
        ],
        "libro": "Hechos / Epístolas",
        "epoca": "~35-65 d.C."
    },
    {
        "nombre": "Timoteo",
        "pistas": [
            "Su madre Eunice y su abuela Loida le enseñaron las Escrituras",
            "Pablo le llamó su 'verdadero hijo en la fe'",
            "Le dijeron: 'Ninguno tenga en poco tu juventud'",
            "Fue compañero de Pablo en sus viajes misioneros"
        ],
        "libro": "Hechos / 1-2 Timoteo",
        "epoca": "~50-65 d.C."
    },
    {
        "nombre": "Esteban",
        "pistas": [
            "Fue elegido como uno de los primeros diáconos",
            "Su rostro brillaba como el de un ángel",
            "Predicó un largo sermón de la historia de Israel",
            "Fue apedreado mientras veía los cielos abiertos"
        ],
        "libro": "Hechos",
        "epoca": "~35 d.C."
    },
    {
        "nombre": "Lázaro",
        "pistas": [
            "Era hermano de Marta y María",
            "Jesús lloró cuando él murió",
            "Estuvo cuatro días en el sepulcro",
            "Jesús le resucitó de entre los muertos"
        ],
        "libro": "Juan",
        "epoca": "~30 d.C."
    },
]

# ── Datos de libros de la Biblia para categoría "Libros de la Biblia" ──
LIBROS_BIBLICOS = [
    {"nombre": "Génesis", "autor": "Moisés", "capitulos": 50, "testamento": "Antiguo", "contexto": "Creación, patriarcas"},
    {"nombre": "Éxodo", "autor": "Moisés", "capitulos": 40, "testamento": "Antiguo", "contexto": "Liberación de Egipto, la Ley"},
    {"nombre": "Levítico", "autor": "Moisés", "capitulos": 27, "testamento": "Antiguo", "contexto": "Leyes sacerdotales y sacrificios"},
    {"nombre": "Números", "autor": "Moisés", "capitulos": 36, "testamento": "Antiguo", "contexto": "Peregrinaje en el desierto"},
    {"nombre": "Deuteronomio", "autor": "Moisés", "capitulos": 34, "testamento": "Antiguo", "contexto": "Segunda entrega de la Ley"},
    {"nombre": "Josué", "autor": "Josué", "capitulos": 24, "testamento": "Antiguo", "contexto": "Conquista de Canaán"},
    {"nombre": "Jueces", "autor": "Samuel (trad.)", "capitulos": 21, "testamento": "Antiguo", "contexto": "Ciclo de jueces en Israel"},
    {"nombre": "Rut", "autor": "Samuel (trad.)", "capitulos": 4, "testamento": "Antiguo", "contexto": "Historia de Rut y Noemí"},
    {"nombre": "1 Samuel", "autor": "Samuel/Profetas", "capitulos": 31, "testamento": "Antiguo", "contexto": "Samuel, Saúl, David joven"},
    {"nombre": "2 Samuel", "autor": "Profetas", "capitulos": 24, "testamento": "Antiguo", "contexto": "Reinado de David"},
    {"nombre": "1 Reyes", "autor": "Jeremías (trad.)", "capitulos": 22, "testamento": "Antiguo", "contexto": "Salomón, reino dividido"},
    {"nombre": "2 Reyes", "autor": "Jeremías (trad.)", "capitulos": 25, "testamento": "Antiguo", "contexto": "Caída de Israel y Judá"},
    {"nombre": "1 Crónicas", "autor": "Esdras (trad.)", "capitulos": 29, "testamento": "Antiguo", "contexto": "Genealogías, reinado de David"},
    {"nombre": "2 Crónicas", "autor": "Esdras (trad.)", "capitulos": 36, "testamento": "Antiguo", "contexto": "Historia del templo y reyes de Judá"},
    {"nombre": "Esdras", "autor": "Esdras", "capitulos": 10, "testamento": "Antiguo", "contexto": "Regreso del exilio, reconstrucción del templo"},
    {"nombre": "Nehemías", "autor": "Nehemías", "capitulos": 13, "testamento": "Antiguo", "contexto": "Reconstrucción de los muros de Jerusalén"},
    {"nombre": "Ester", "autor": "Mardoqueo (trad.)", "capitulos": 10, "testamento": "Antiguo", "contexto": "Reina Ester salva a los judíos"},
    {"nombre": "Job", "autor": "Moisés/Desconocido", "capitulos": 42, "testamento": "Antiguo", "contexto": "Sufrimiento y soberanía de Dios"},
    {"nombre": "Salmos", "autor": "David y varios", "capitulos": 150, "testamento": "Antiguo", "contexto": "Libro de alabanzas y oraciones"},
    {"nombre": "Proverbios", "autor": "Salomón", "capitulos": 31, "testamento": "Antiguo", "contexto": "Sabiduría práctica"},
    {"nombre": "Eclesiastés", "autor": "Salomón", "capitulos": 12, "testamento": "Antiguo", "contexto": "Vanidad de la vida sin Dios"},
    {"nombre": "Cantares", "autor": "Salomón", "capitulos": 8, "testamento": "Antiguo", "contexto": "Poema de amor nupcial"},
    {"nombre": "Isaías", "autor": "Isaías", "capitulos": 66, "testamento": "Antiguo", "contexto": "Profecía del Mesías"},
    {"nombre": "Jeremías", "autor": "Jeremías", "capitulos": 52, "testamento": "Antiguo", "contexto": "Profecía de juicio y restauración"},
    {"nombre": "Lamentaciones", "autor": "Jeremías", "capitulos": 5, "testamento": "Antiguo", "contexto": "Lamento por la caída de Jerusalén"},
    {"nombre": "Ezequiel", "autor": "Ezequiel", "capitulos": 48, "testamento": "Antiguo", "contexto": "Visiones proféticas del exilio"},
    {"nombre": "Daniel", "autor": "Daniel", "capitulos": 12, "testamento": "Antiguo", "contexto": "Profecías y fe en Babilonia"},
    {"nombre": "Oseas", "autor": "Oseas", "capitulos": 14, "testamento": "Antiguo", "contexto": "Amor de Dios por Israel infiel"},
    {"nombre": "Joel", "autor": "Joel", "capitulos": 3, "testamento": "Antiguo", "contexto": "Derramamiento del Espíritu Santo"},
    {"nombre": "Amós", "autor": "Amós", "capitulos": 9, "testamento": "Antiguo", "contexto": "Justicia social y juicio divino"},
    {"nombre": "Abdías", "autor": "Abdías", "capitulos": 1, "testamento": "Antiguo", "contexto": "Profecía contra Edom"},
    {"nombre": "Jonás", "autor": "Jonás", "capitulos": 4, "testamento": "Antiguo", "contexto": "Arrepentimiento de Nínive"},
    {"nombre": "Miqueas", "autor": "Miqueas", "capitulos": 7, "testamento": "Antiguo", "contexto": "Profecía del nacimiento en Belén"},
    {"nombre": "Nahúm", "autor": "Nahúm", "capitulos": 3, "testamento": "Antiguo", "contexto": "Juicio contra Nínive"},
    {"nombre": "Habacuc", "autor": "Habacuc", "capitulos": 3, "testamento": "Antiguo", "contexto": "El justo por la fe vivirá"},
    {"nombre": "Sofonías", "autor": "Sofonías", "capitulos": 3, "testamento": "Antiguo", "contexto": "Día de Jehová"},
    {"nombre": "Hageo", "autor": "Hageo", "capitulos": 2, "testamento": "Antiguo", "contexto": "Reconstrucción del templo"},
    {"nombre": "Zacarías", "autor": "Zacarías", "capitulos": 14, "testamento": "Antiguo", "contexto": "Profecías mesiánicas"},
    {"nombre": "Malaquías", "autor": "Malaquías", "capitulos": 4, "testamento": "Antiguo", "contexto": "Diezmos, fidelidad, Elías"},
    {"nombre": "Mateo", "autor": "Mateo", "capitulos": 28, "testamento": "Nuevo", "contexto": "Evangelio del Rey, Sermón del Monte"},
    {"nombre": "Marcos", "autor": "Juan Marcos", "capitulos": 16, "testamento": "Nuevo", "contexto": "Evangelio del Siervo"},
    {"nombre": "Lucas", "autor": "Lucas", "capitulos": 24, "testamento": "Nuevo", "contexto": "Evangelio del Hijo del Hombre"},
    {"nombre": "Juan", "autor": "Juan", "capitulos": 21, "testamento": "Nuevo", "contexto": "Evangelio del Hijo de Dios"},
    {"nombre": "Hechos", "autor": "Lucas", "capitulos": 28, "testamento": "Nuevo", "contexto": "Nacimiento y expansión de la iglesia"},
    {"nombre": "Romanos", "autor": "Pablo", "capitulos": 16, "testamento": "Nuevo", "contexto": "Justificación por la fe"},
    {"nombre": "1 Corintios", "autor": "Pablo", "capitulos": 16, "testamento": "Nuevo", "contexto": "Problemas en la iglesia, amor"},
    {"nombre": "2 Corintios", "autor": "Pablo", "capitulos": 13, "testamento": "Nuevo", "contexto": "Defensa del apostolado"},
    {"nombre": "Gálatas", "autor": "Pablo", "capitulos": 6, "testamento": "Nuevo", "contexto": "Libertad en Cristo"},
    {"nombre": "Efesios", "autor": "Pablo", "capitulos": 6, "testamento": "Nuevo", "contexto": "La iglesia como cuerpo de Cristo"},
    {"nombre": "Filipenses", "autor": "Pablo", "capitulos": 4, "testamento": "Nuevo", "contexto": "Gozo en Cristo"},
    {"nombre": "Colosenses", "autor": "Pablo", "capitulos": 4, "testamento": "Nuevo", "contexto": "Supremacía de Cristo"},
    {"nombre": "1 Tesalonicenses", "autor": "Pablo", "capitulos": 5, "testamento": "Nuevo", "contexto": "Segunda venida de Cristo"},
    {"nombre": "2 Tesalonicenses", "autor": "Pablo", "capitulos": 3, "testamento": "Nuevo", "contexto": "El día del Señor"},
    {"nombre": "1 Timoteo", "autor": "Pablo", "capitulos": 6, "testamento": "Nuevo", "contexto": "Instrucciones pastorales"},
    {"nombre": "2 Timoteo", "autor": "Pablo", "capitulos": 4, "testamento": "Nuevo", "contexto": "Últimas instrucciones de Pablo"},
    {"nombre": "Tito", "autor": "Pablo", "capitulos": 3, "testamento": "Nuevo", "contexto": "Liderazgo en la iglesia"},
    {"nombre": "Filemón", "autor": "Pablo", "capitulos": 1, "testamento": "Nuevo", "contexto": "Carta sobre Onésimo"},
    {"nombre": "Hebreos", "autor": "Pablo/Desconocido", "capitulos": 13, "testamento": "Nuevo", "contexto": "Supremacía de Cristo sobre el Antiguo Pacto"},
    {"nombre": "Santiago", "autor": "Santiago", "capitulos": 5, "testamento": "Nuevo", "contexto": "Fe y obras"},
    {"nombre": "1 Pedro", "autor": "Pedro", "capitulos": 5, "testamento": "Nuevo", "contexto": "Esperanza en medio del sufrimiento"},
    {"nombre": "2 Pedro", "autor": "Pedro", "capitulos": 3, "testamento": "Nuevo", "contexto": "Falsa doctrina y la venida de Cristo"},
    {"nombre": "1 Juan", "autor": "Juan", "capitulos": 5, "testamento": "Nuevo", "contexto": "Amor, luz, y verdad"},
    {"nombre": "2 Juan", "autor": "Juan", "capitulos": 1, "testamento": "Nuevo", "contexto": "Andar en la verdad"},
    {"nombre": "3 Juan", "autor": "Juan", "capitulos": 1, "testamento": "Nuevo", "contexto": "Hospitalidad cristiana"},
    {"nombre": "Judas", "autor": "Judas", "capitulos": 1, "testamento": "Nuevo", "contexto": "Contra los falsos maestros"},
    {"nombre": "Apocalipsis", "autor": "Juan", "capitulos": 22, "testamento": "Nuevo", "contexto": "Revelación del fin de los tiempos"},
]


import threading

class Biblia:
    """Parser and question generator for Bible data."""

    def __init__(self, filepath=None):
        self._lock = threading.Lock()
        self.versiculos = list(EMBEDDED_VERSES)
        self.personajes = PERSONAJES
        self.libros = LIBROS_BIBLICOS
        self._used_seeds = set()

        if filepath and os.path.exists(filepath):
            self._parse_file(filepath)

    def _parse_file(self, filepath):
        """Parse a .bib file in format: Book Chapter:Verse|text"""
        try:
            import gzip
            try:
                with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                    content = f.read()
            except (Exception,):
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            self._parse_content(content)
        except Exception as e:
            print(f"Could not parse .bib file: {e}")

    def _parse_content(self, content):
        """Parse text content with format: Book Chapter:Verse|text"""
        verses = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if '|' in line:
                ref, text = line.split('|', 1)
                ref = ref.strip()
                text = text.strip()
                if ref and text:
                    verses.append((ref, text))
        if verses:
            self.versiculos = verses

    def mark_used(self, seed):
        with self._lock:
            self._used_seeds.add(seed)

    def clear_used(self):
        with self._lock:
            self._used_seeds.clear()

    def get_random_verse(self):
        """Get a random verse (referencia, texto)."""
        with self._lock:
            available = [v for v in self.versiculos if v[0] not in self._used_seeds]
            if not available:
                verse = random.choice(self.versiculos)
            else:
                verse = random.choice(available)
            self._used_seeds.add(verse[0])
        return verse

    def get_verse_completion(self):
        """Get a verse with some words blanked for completion."""
        ref, text = self.get_random_verse()
        words = text.split()
        if len(words) < 4:
            return ref, text, text

        num_blank = min(random.randint(2, 4), len(words) // 2)
        indices = sorted(random.sample(range(len(words)), num_blank))
        blanked = []
        answers = []
        for i, w in enumerate(words):
            if i in indices:
                blanked.append('_' * len(w))
                answers.append(w)
            else:
                blanked.append(w)

        hint = ' '.join(blanked)
        return ref, hint, ' '.join(answers)

    def get_random_personaje(self):
        """Get a random character question."""
        with self._lock:
            available = [p for p in self.personajes if p['nombre'] not in self._used_seeds]
            if not available:
                personaje = random.choice(self.personajes)
            else:
                personaje = random.choice(available)
            self._used_seeds.add(personaje['nombre'])
        
        # Ensure personaje has at least 3 pistas to avoid IndexError
        if 'pistas' not in personaje or len(personaje['pistas']) < 3:
            # Filter out personajes with insufficient pistas
            valid_personajes = [p for p in self.personajes if len(p.get('pistas', [])) >= 3]
            if not valid_personajes:
                raise ValueError("No hay personajes con al menos 3 pistas disponibles")
            
            # Choose a valid personaje and mark it as used
            personaje = random.choice(valid_personajes)
            self._used_seeds.add(personaje['nombre'])
        
        return personaje

    def get_pista(self, personaje, nivel):
        """Get hint at given level (0-3). Returns (pista_text, is_final)."""
        if 0 <= nivel < len(personaje['pistas']):
            return personaje['pistas'][nivel], False
        return personaje['nombre'], True

    def get_random_libro_question(self):
        """Generate a trivia question about a book of the Bible."""
        libro = random.choice(self.libros)
        q_type = random.randint(0, 4)

        if q_type == 0:
            q = f"¿Quién escribió el libro de {libro['nombre']}?"
            a = libro['autor']
        elif q_type == 1:
            q = f"¿Cuántos capítulos tiene el libro de {libro['nombre']}?"
            a = str(libro['capitulos'])
        elif q_type == 2:
            q = f"El libro de {libro['nombre']} pertenece a qué testamento?"
            a = libro['testamento']
        elif q_type == 3:
            q = f"¿Cuál es el contexto principal del libro de {libro['nombre']}?"
            a = libro['contexto']
        else:
            q = f"¿Qué libro de la Biblia tiene {libro['capitulos']} capítulos y trata sobre {libro['contexto'].lower()}?"
            a = libro['nombre']

        return {'pregunta': q, 'respuesta': a, 'libro': libro['nombre']}

    def get_versiculo_donde_esta(self):
        """Show verse text without reference → ¿dónde está escrito?"""
        ref, text = self.get_random_verse()
        # Pick a famous-enough verse (length > 30 chars)
        attempts = 0
        while len(text) < 30 and attempts < 10:
            ref, text = self.get_random_verse()
            attempts += 1
        return ref, text

    def get_versiculos_mezclados(self, count=3):
        """Get N references shuffled → order them chronologically."""
        verses = []
        with self._lock:
            pool = [v for v in self.versiculos if v[0] not in self._used_seeds]
            if len(pool) < count:
                pool = list(self.versiculos)
            selected = random.sample(pool, min(count, len(pool)))
            for v in selected:
                self._used_seeds.add(v[0])
                verses.append(v)

        # Parse references to extract book+chapter for chronological order
        book_order = [
            "Génesis","Éxodo","Levítico","Números","Deuteronomio",
            "Josué","Jueces","Rut","1 Samuel","2 Samuel","1 Reyes","2 Reyes",
            "1 Crónicas","2 Crónicas","Esdras","Nehemías","Ester","Job",
            "Salmos","Proverbios","Eclesiastés","Cantares",
            "Isaías","Jeremías","Lamentaciones","Ezequiel","Daniel",
            "Oseas","Joel","Amós","Abdías","Jonás","Miqueas","Nahúm",
            "Habacuc","Sofonías","Hageo","Zacarías","Malaquías",
            "Mateo","Marcos","Lucas","Juan","Hechos",
            "Romanos","1 Corintios","2 Corintios","Gálatas","Efesios",
            "Filipenses","Colosenses","1 Tesalonicenses","2 Tesalonicenses",
            "1 Timoteo","2 Timoteo","Tito","Filemón","Hebreos",
            "Santiago","1 Pedro","2 Pedro","1 Juan","2 Juan","3 Juan","Judas","Apocalipsis"
        ]

        def sort_key(v):
            ref = v[0]
            parts = ref.split(" ")
            book_name = " ".join(parts[:-1]) if len(parts) > 1 else parts[0]
            try:
                bk_idx = book_order.index(book_name)
            except ValueError:
                bk_idx = 999
            try:
                ch = int(parts[-1].split(":")[0])
            except (ValueError, IndexError):
                ch = 0
            return (bk_idx, ch)

        shuffled = list(verses)
        random.shuffle(shuffled)
        correct = sorted(verses, key=sort_key)
        return shuffled, correct


# Singleton
_biblia = None

def get_biblia(filepath=None):
    global _biblia
    if _biblia is None:
        _biblia = Biblia(filepath)
    return _biblia
