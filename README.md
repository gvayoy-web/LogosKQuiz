# LogosKQuiz
LogosKQuiz es una plataforma web completa, robusta y optimizada para la gestión, automatización y proyección en vivo de concursos de trivias bíblicas. Desarrollado con un backend en Python (Flask/Waitress) y un frontend dinámico e interactivo, maneja de forma transparente las puntuaciones, el banco de preguntas y el control del tiempo.


Introducción

En la organización de eventos y concursos bíblicos tradicionales, la gestión de puntuaciones, el control estricto del tiempo y la proyección de las preguntas suelen delegarse en hojas de cálculo manuales o diapositivas de PowerPoint rígidas. Esto ralentiza el ritmo del juego y da margen a errores humanos.

**LogosKQuiz** nace para digitalizar esta experiencia por completo. Proporciona una interfaz centralizada basada en web donde el moderador tiene el control total de la competencia con un clic, mientras la audiencia y los competidores disfrutan de una pantalla fluida, automatizada y con animaciones dinámicas que elevan el nivel del evento.



 ¿Por qué mi programa?

A diferencia de otros scripts sencillos de trivias, **LogosKQuiz** fue diseñado bajo estándares profesionales de desarrollo de software:

* **Sincronización en Tiempo Real Fluida (SSE):** En lugar de recargar la página constantemente o saturar el servidor con peticiones innecesarias, utiliza *Server-Sent Events*. El servidor envía los cambios de estado (temporizador, puntajes, preguntas) inmediatamente a las pantallas conectadas.
* **Servidor de Producción Integrado:** Se ejecuta nativamente sobre **Waitress (WSGI)**, un servidor diseñado para producción en Windows que garantiza estabilidad, alta concurrencia y un consumo de recursos sumamente bajo.
* **Persistencia Atómica y Segura:** Los puntajes y configuraciones se guardan de forma atómica en `pym.json` mediante el uso de archivos temporales. Si el servidor se apaga inesperadamente o hay un corte de energía, los datos de la competencia **no se corrompen**.
* **Respaldos Rotativos:** Cada vez que el programa inicia o hay cambios importantes, genera una copia de seguridad en la carpeta `backups/` con una marca de tiempo, limitando de manera automática el número de archivos para optimizar el almacenamiento.

---

##  Guía de Instalación y Uso

¡Configurar el sistema es sumamente sencillo! Sigue estos tres pasos:

### 1. Instalar Python 
1. Descarga el instalador oficial desde [python.org](https://www.python.org/downloads/).
2. **¡CRUCIAL!** Al abrir el instalador, marca la casilla que dice **"Add python.exe to PATH"** en la parte inferior de la ventana antes de dar clic en instalar.
3. Completa la instalación de forma normal.

### 2. Descargar el Repositorio 
1. Da clic en el botón verde **"Code"** ubicado en la parte superior derecha de esta página y selecciona **"Download ZIP"**.
2. Descarga Winrar (https://www.win-rar.com/start.html?&L=6) para poder descomprimir el archivo
3. Descomprime el archivo en la carpeta que prefieras de tu computadora (por ejemplo, el Escritorio).

### 3. Ejecutar y Iniciar LogosKQuiz
1. Abre la carpeta del proyecto y dale doble clic al archivo **`iniciar.bat`**.
2. Se abrirá una consola que instalará automáticamente las dependencias necesarias (`Flask`, `Flask-CORS`, `Waitress`) y encenderá el servidor. **No cierres esa ventana.**
3. Abre tu navegador web (Chrome, Edge, etc.) e ingresa a las siguientes rutas locales:
    * **Panel del Moderador / Administrador:** `http://localhost:5000/control`
    * **Pantalla para el Público / Proyector:** `http://localhost:5000/display`

*Nota: Cualquier otro dispositivo (como un celular o tablet) conectado a la misma red Wi-Fi puede acceder al Panel de Control ingresando la IP local de tu computadora en lugar de `localhost`.*

---

##  Características Principales (Features Detectados)

* **Ecosistema de Pantalla Dual:** El administrador controla el flujo de manera privada desde `/control` con soporte completo de atajos de teclado, mientras que `/display` ofrece una vista limpia de cara al público, optimizada para proyectores.
* **Efectos de Animación Avanzados:** Integración de un motor tipográfico (*Typewriter Effect*) para revelar preguntas y respuestas de forma fluida, transiciones dinámicas para las tarjetas de los equipos y soporte para **Modo Kiosko** (activable mediante doble clic).
* **Consola de Actividad Reciente:** Monitoreo en vivo de los últimos 10 eventos o acciones del sistema (logs visuales como sumas de puntos, inicio de timers o bloqueos) accesibles desde el endpoint `/api/actividad`.
* **Carga y Modificación "En Caliente":** Modificación en vivo de preguntas individuales usando peticiones `PUT /api/preguntas/<id>`, además de endpoints dedicados para importar y exportar el banco completo en formato JSON de manera instantánea.
* **Control Total de Marcadores:** Soporte para sumas de puntuación instantáneas, multiplicadores, y penalizaciones con valores negativos (`/api/puntos/restar`).

---

##  Modos de Juego y Herramientas Especiales

El motor visual del frontend y la flexibilidad de la API permiten transicionar dinámicamente entre múltiples mecánicas integradas:

1. **Modo Trivia Estándar (Selección Múltiple o Abierta):** Muestra preguntas categorizadas en pantalla. El moderador tiene el poder de ocultar o mostrar las opciones de respuesta, iluminar la opción seleccionada por un equipo y revelar la respuesta correcta de forma remota.
2. **Modo Ruleta (The Wheel Mode):** ¡Una de las mejores joyas visuales del proyecto! Una ruleta interactiva construida con matemáticas CSS dinámicas (`--label-angle`, `--label-radius`) que gira con animaciones físicas configuradas desde el panel de control para seleccionar categorías, puntajes o retos al azar.
3. **Modo Versículos ("Cambio"):** Potenciado por el script `biblia.py`. Procesa archivos de texto bíblico (`.bib`) y cuenta con una colección nativa de la Reina-Valera 1960 para generar dinámicas de completar textos, adivinar la cita o rellenar palabras faltantes.
4. **Módulo Sampler de Audio Integrado (Live Soundboard):** El panel del moderador cuenta con una matriz de lanzamiento de audio (*Audio Sampler Slots*). Permite cargar audios en búfer al instante y lanzarlos mediante atajos de teclado numéricos (1-9) para reproducir efectos de sonido (aplausos, sonidos de error, suspenso) enriqueciendo la atmósfera del evento en vivo.
---

## 📄 Licencia

Este proyecto está bajo la **Licencia MIT**. Siéntete libre de usarlo en tu iglesia, escuela o comunidad, modificarlo y adaptarlo a tus necesidades.
