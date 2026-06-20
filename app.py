"""
app.py â€” Campeonísimo Bíblico Â· Servidor v3
Mejoras sobre v1:
  F1-1  PUT /api/preguntas/<id>  â€” edición de preguntas
  F1-2  Penalizaciones  â€” /api/puntos acepta cantidades negativas
         + endpoint explícito POST /api/puntos/restar
  F1-3  Timer SSE con campo `ts` (timestamp) para descartar
         paquetes out-of-order en clientes con latencia alta
  F2-1  GET /api/actividad â€” cola de las últimas 10 acciones
         (también viaja en cada payload SSE)
  F2-2  POST /api/preguntas/importar â€” carga banco de preguntas
  GET  /api/preguntas/exportar     â€” descarga banco como JSON
"""

# Lock ordering (global):  _cv â†’ _suscriptores_lock â†’ state._lock
# â”€â”€ Imports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import json
import logging
import os
import queue
import random
import shutil
import tempfile
import threading
import time
from collections import deque
from datetime import datetime

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from biblia import get_biblia

try:
    from waitress import serve as waitress_serve

    HAS_WAITRESS = True
except ImportError:
    HAS_WAITRESS = False

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Logging profesional
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("competencia.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Configuración vía variables de entorno
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
DATA_FILE = os.getenv("COMP_DATA_FILE", "pym.json")
SERVER_PORT = int(os.getenv("COMP_PORT", "5000"))
SERVER_DEBUG = os.getenv("COMP_DEBUG", "false").lower() in ("true", "1")
MAX_BACKUPS = int(os.getenv("COMP_BACKUPS", "10"))
GRUPOS_BASE = {"Caballeros", "Damas", "Niños", "Jóvenes"}
GRUPOS_CONFIG_DEFAULT = [
    {"key": "Caballeros", "nombre": "Caballeros", "color": "#FF5500", "color2": "#FF8844", "fijo": True},
    {"key": "Damas", "nombre": "Damas", "color": "#FFCC00", "color2": "#FFE066", "fijo": True},
    {"key": "Niños", "nombre": "Niños", "color": "#00FF55", "color2": "#66FF99", "fijo": True},
    {"key": "Jóvenes", "nombre": "Jóvenes", "color": "#FF00FF", "color2": "#FF80FF", "fijo": True},
]

def get_grupos_validos(state):
    return {g["key"] for g in state.display_config.get("grupos_config", GRUPOS_CONFIG_DEFAULT)}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_change_qid = 0  # monotonic descending ID for change-mode questions

# Categorías predefinidas para preguntas
CATEGORIAS_PREGUNTAS = [
    "Libros de la Biblia",
    "¿Quién soy?",
    "Preguntas Bíblicas",
]

# Categorías predefinidas para preguntas



# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Persistencia atómica
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def cargar_datos() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.error("No se pudo leer %s: %s", DATA_FILE, exc, exc_info=True)
            os.rename(DATA_FILE, DATA_FILE + ".corrupted")
    return {
        "preguntas": [],
        "puntos": {"Jóvenes": 0, "Damas": 0, "Caballeros": 0, "Niños": 0},
    }


def guardar_datos(snapshot: dict) -> None:
    dir_name = os.path.dirname(os.path.abspath(DATA_FILE)) or "."
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=dir_name, delete=False, encoding="utf-8", suffix=".tmp"
        ) as tf:
            json.dump(snapshot, tf, ensure_ascii=False, indent=4)
            tmp_path = tf.name
        os.replace(tmp_path, DATA_FILE)
    except Exception as exc:
        log.error("Fallo al escribir %s: %s", DATA_FILE, exc, exc_info=True)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Backups rotativos
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def crear_backup() -> None:
    if not os.path.exists(DATA_FILE):
        return
    backup_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"pym_backup_{ts}.json")
    shutil.copy2(DATA_FILE, dest)
    log.info("Backup creado: %s", dest)
    try:
        entries = sorted(
            (e for e in os.scandir(backup_dir) if e.is_file()),
            key=lambda e: e.stat().st_mtime,
        )
    except OSError:
        entries = []
    while len(entries) > MAX_BACKUPS:
        try:
            os.remove(entries.pop(0).path)
        except OSError:
            pass


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PALABRAS_ALABANZA â€” 100+ palabras para Ruleta de Alabanzas
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
PALABRAS_ALABANZA = [
    "Fuego",
    "Cadenas",
    "Danza",
    "Poder",
    "Victoria",
    "Gozo",
    "Espada",
    "Muros",
    "Río",
    "Alegre",
    "Fiesta",
    "Grito",
    "Pueblo",
    "León",
    "Gigante",
    "Mar",
    "Libertad",
    "Aceite",
    "Roca",
    "Palmas",
    "Santo",
    "Digno",
    "Majestad",
    "Cielos",
    "Tierra",
    "Nombre",
    "Cordero",
    "Trono",
    "Altar",
    "Sangre",
    "Cruz",
    "Gracia",
    "Amor",
    "Fidelidad",
    "Paz",
    "Luz",
    "Camino",
    "Vida",
    "Presencia",
    "Habitación",
    "David",
    "Moisés",
    "Elías",
    "Jericó",
    "Egipto",
    "Monte",
    "Sion",
    "Jerusalén",
    "Israel",
    "Sol",
    "Aguas",
    "Viento",
    "Lluvia",
    "Desierto",
    "Valle",
    "Águilas",
    "Cosecha",
    "Oro",
    "Nube",
    "Estrellas",
    "Espíritu",
    "Fe",
    "Promesa",
    "Palabra",
    "Corazón",
    "Alma",
    "Manos",
    "Voz",
    "Oídos",
    "Ojos",
    "Boca",
    "Lágrimas",
    "Perdón",
    "Salvador",
    "Rey",
    "Buscar",
    "Cantar",
    "Alabar",
    "Clamar",
    "Ven",
    "Correr",
    "Caminar",
    "Levantar",
    "Postrar",
    "Saltar",
    "Brillar",
    "Seguir",
    "Vencer",
    "Rendir",
    "Sanar",
    "Alfa",
    "Omega",
    "Eternidad",
    "Refugio",
    "Escudo",
    "Unción",
    "Lléname",
    "Transformar",
    "Soberano",
    "Sublime",
    "Manantial",
    "Pastor",
    "Oveja",
    "Pan",
    "Vino",
]

CANTANTES = [
    "Jesús Adrián Romero",
    "Marcos Witt",
    "Álex Campos",
    "Christine D'Clario",
    "Marcela Gándara",
    "Evan Craft",
    "Lilly Goodman",
    "Julio Melgar",
    "Miel San Marcos",
    "Barak",
    "Tercer Cielo",
    "Hillsong United",
    "Un corazón",
    "Danilo Montero",
    "Majo y Dan",
    "Los voceros de Cristo",
    "Roberto Orellana",
    "Damaris Guerra",
    "Rabito",
    "Marcos Yaroide",
    "Jonathan y Sarah Jerez",
    "Ericson Alexander Molano",
    "Marcos Barrientos",
    "Dany Berrios",
    "Oscar Medina",
    "Renato Sánchez",
    "Josh Morales",
    "Saraí Rivera",
    "Samuel Hernández",
    "Ingrid Rosario",
    "Coalo Zamorano",
    "René Gonzales",
    "Job Gonzales",
    "Marcos Vidal",
    "Génesis campos",
    "World Worship",
    "Montesanto",
    "La ibi",
    "Generacion 12",
    "New wine",
]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# AppState â€” estado centralizado y thread-safe
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class AppState:
    """Todo el estado mutable en un solo lugar, protegido por Lock."""

    def __init__(self, datos: dict):
        self._lock = threading.Lock()
        self.preguntas: list = datos.get("preguntas", [])
        gc = datos.get("grupos_config")
        if not gc or not isinstance(gc, list):
            gc = [dict(g) for g in GRUPOS_CONFIG_DEFAULT]
        # Ensure 4 base groupes always exist
        base_keys = {g["key"] for g in gc if g.get("fijo")}
        for bg in GRUPOS_CONFIG_DEFAULT:
            if bg["key"] not in base_keys:
                gc.insert(GRUPOS_CONFIG_DEFAULT.index(bg), dict(bg))
        # Initialize puntos with all group keys
        puntos_raw = datos.get("puntos", {})
        self.puntos = {}
        for g in gc:
            self.puntos[g["key"]] = puntos_raw.get(g["key"], 0)
        self.pregunta_actual = None
        self.mostrar_respuesta = False
        self.mostrar_opciones = False
        # Temporizador
        self.timer_activo = False
        self.timer_segundos = 0
        self.timer_totales = 0
        # Display config (synced to display.html via SSE)
        self.display_config = {
            "kiosko": False,
            "animations_disabled": False,
            "overlay_reset": 0,  # increment to trigger overlay clear
            "black_screen": False,
            "frozen": False,
            "eliminados": [],
            "final_round": False,
            "final_results": False,
            "grupos_config": gc,
        }
        # Animaciones
        self.anim_texto = None
        self.anim_id = 0
        self.anim_data = {"tipo": None, "grupo": None, "cantidad": 0}
        # F2-1: Cola de actividad (últimas 10 acciones)
        self._actividad: deque = deque(maxlen=10)
        # â”€â”€ RULETA (unificada) state â”€â”€
        self.ruleta_activa = False
        self.ruleta_anim_id = 0
        self.ruleta_num_palabra = 0
        self.ruleta_num_cantante = 0
        self.ruleta_categoria = None  # "palabra" | "cantante" | None
        self.ruleta_subconjunto = []  # 20 items del banco ganador
        self.ruleta_resultado = None  # item final seleccionado
        self.ruleta_historial = []  # para repesca 1/100
        # â”€â”€ Current display mode â”€â”€
        self.modo = "preguntas"  # "preguntas" | "versos" | "ruleta"

        # â”€â”€ BIBLE VERSES MODE state â”€â”€
        self.versos_activo = False
        self.versos_timer_segundos = 0
        self.versos_timer_totales = 0
        self.versos_timer_fin = 0.0  # monotonic end time for versos timer
        self.versos_categoria = None  # "quiensoy" | "libros" | "versiculos" | None
        self.versos_pregunta_actual = None
        self.versos_mostrar_respuesta = False
        self.versos_subconjunto = []  # 20 items del banco ganador
        self.versos_resultado = None  # item final seleccionado
        self.versos_historial = []  # para repesca 1/100

        # Opción múltiple: índice que el operador selecciona
        self.opcion_seleccionada = None  # 0 | 1 | 2 | None

    # â”€â”€ Registro de actividad â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _log_actividad(self, msg: str) -> None:
        """Añade entrada al log de actividad (llamar con el lock adquirido)."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._actividad.appendleft(f"[{ts}] {msg}")

    def get_actividad(self) -> list:
        with self._lock:
            return list(self._actividad)

    # â”€â”€ Snapshotters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "pregunta_actual": self.pregunta_actual,
                "mostrar_respuesta": self.mostrar_respuesta,
                "mostrar_opciones": self.mostrar_opciones,
                "opcion_seleccionada": self.opcion_seleccionada,
                "puntos": dict(self.puntos),
                "leaderboard_ordenado": sorted(
                    [{"grupo": k, "puntos": v} for k, v in self.puntos.items()],
                    key=lambda x: x["puntos"],
                    reverse=True,
                ),
                "temporizador": {
                    "activo": self.timer_activo,
                    "segundos_restantes": self.timer_segundos,
                    "segundos_totales": self.timer_totales,
                    # F1-3: timestamp para detección out-of-order en cliente
                    "ts": time.monotonic(),
                },
                "ultima_animacion": self.anim_texto,
                "ultima_animacion_id": self.anim_id,
                "anim_data": dict(self.anim_data),
                "display_config": dict(self.display_config),
                # Ruleta (unified)
                "ruleta": {
                    "activa": self.ruleta_activa,
                    "anim_id": self.ruleta_anim_id,
                    "num_palabra": self.ruleta_num_palabra,
                    "num_cantante": self.ruleta_num_cantante,
                    "categoria": self.ruleta_categoria,
                    "subconjunto": self.ruleta_subconjunto,
                    "resultado": self.ruleta_resultado,
                },
                # Bible Verses Mode state
                "versos": {
                    "activo": self.versos_activo,
                    "segundos_restantes": self.versos_timer_segundos,
                    "segundos_totales": self.versos_timer_totales,
                    "timer_fin": self.versos_timer_fin,
                    "categoria": self.versos_categoria,
                    "pregunta_actual": self.versos_pregunta_actual,
                    "mostrar_respuesta": self.versos_mostrar_respuesta,
                    "subconjunto": self.versos_subconjunto,
                    "resultado": self.versos_resultado,
                },
                # Current display mode
                "modo": self.modo,
                # Categorías disponibles
                "categorias_disponibles": CATEGORIAS_PREGUNTAS,
                "resultados_finales": sorted(
                    [{"grupo": k, "puntos": v} for k, v in self.puntos.items()],
                    key=lambda x: x["puntos"],
                    reverse=True,
                ),
                # F2-1: actividad viaja en cada push SSE
                "actividad": list(self._actividad),
            }

    def datos_persistibles(self) -> dict:
        with self._lock:
            return {
                "preguntas": list(self.preguntas),
                "puntos": dict(self.puntos),
                "grupos_config": list(self.display_config.get("grupos_config", GRUPOS_CONFIG_DEFAULT)),
            }

    # â”€â”€ Puntos (F1-2: acepta negativos para penalizar) â”€â”€â”€
    def sumar_puntos(self, grupo: str, cantidad: int) -> bool:
        """cantidad puede ser negativo (penalización)."""
        with self._lock:
            if grupo not in self.puntos:
                return False
            if grupo in self.display_config.get("eliminados", []):
                return False
            mostrar = cantidad  # original amount for animation display
            if self.display_config.get("final_round") and cantidad > 0:
                cantidad *= 2  # doubled for actual scoring
            self.puntos[grupo] += cantidad
            if mostrar >= 0:
                self.anim_texto = f"🎉 PUNTO PARA {grupo.upper()} 🎉"
                self.anim_data = {"tipo": "punto", "grupo": grupo, "cantidad": mostrar}
                msg = f"+{cantidad} pts → {grupo}"
            else:
                self.anim_texto = f"⚠️ PENALIZACIÓN {grupo.upper()} ⚠️"
                self.anim_data = {"tipo": "penalizacion", "grupo": grupo, "cantidad": mostrar}
                msg = f"{cantidad} pts → {grupo}"
            self.anim_id += 1
            self._log_actividad(msg)
            return True

    def ajustar_puntos(self, grupo: str, valor: int) -> bool:
        with self._lock:
            if grupo not in self.puntos:
                return False
            if grupo in self.display_config.get("eliminados", []):
                return False
            if self.display_config.get("final_round") and valor > 0:
                valor *= 2
            self.puntos[grupo] = valor
            self._log_actividad(f"Ajuste manual: {grupo} = {valor} pts")
            return True

    # â”€â”€ Preguntas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def set_pregunta(self, pid: int):
        with self._lock:
            for p in self.preguntas:
                if p["id"] == pid:
                    self.pregunta_actual = p
                    self.mostrar_respuesta = False
                    self.mostrar_opciones = False
                    self.opcion_seleccionada = None
                    self._log_actividad(f"Proyectando: Â«{p['texto'][:40]}Â»")
                    return p
        return None

    def siguiente_id(self) -> int:
        with self._lock:
            # Exclude change mode questions (negative IDs) from max calculation
            positive_ids = [p["id"] for p in self.preguntas if p["id"] > 0]
            return max(positive_ids, default=0) + 1

    def agregar_pregunta(self, pregunta: dict):
        with self._lock:
            self.preguntas.append(pregunta)
            self._log_actividad(f"Pregunta creada id={pregunta['id']}")

    def eliminar_pregunta(self, pid: int) -> bool:
        with self._lock:
            for i, p in enumerate(self.preguntas):
                if p["id"] == pid:
                    self.preguntas.pop(i)
                    if self.pregunta_actual and self.pregunta_actual["id"] == pid:
                        self.pregunta_actual = None
                    self._log_actividad(f"Pregunta eliminada id={pid}")
                    return True
        return False

    # F1-1: Edición de pregunta existente
    def editar_pregunta(
        self, pid: int, texto: str, respuesta: str, extra: dict = None
    ) -> bool:
        with self._lock:
            for p in self.preguntas:
                if p["id"] == pid:
                    p["texto"] = texto
                    p["respuesta"] = respuesta
                    if extra:
                        p.update(extra)
                    # Si es la pregunta actualmente proyectada, actualizar ref
                    if self.pregunta_actual and self.pregunta_actual["id"] == pid:
                        self.pregunta_actual = dict(p)
                    self._log_actividad(f"Pregunta editada id={pid}")
                    return True
        return False

    def reset(self):
        with self._lock:
            self.preguntas = []
            self.puntos = {"Jóvenes": 0, "Damas": 0, "Caballeros": 0, "Niños": 0}
            self.pregunta_actual = None
            self.mostrar_respuesta = False
            self.mostrar_opciones = False
            self.timer_activo = False
            self.timer_segundos = 0
            self.anim_texto = None
            self.anim_id = 0
            self.anim_data = {"tipo": None, "grupo": None, "cantidad": 0}
            self.ruleta_activa = False
            self.ruleta_anim_id = 0
            self.ruleta_categoria = None
            self.ruleta_resultado = None
            self.ruleta_subconjunto = []
            self.ruleta_historial = []
            self.modo = "preguntas"
            self.versos_activo = False
            self.versos_timer_segundos = 0
            self.versos_timer_totales = 0
            self.versos_timer_fin = 0.0
            self.versos_categoria = None
            self.versos_pregunta_actual = None
            self.versos_mostrar_respuesta = False
            self.versos_subconjunto = []
            self.versos_resultado = None
            self.versos_historial = []
            self.opcion_seleccionada = None
            self._log_actividad("âš  RESET COMPLETO ejecutado")


state = AppState(cargar_datos())


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SSE â€” Server-Sent Events
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
_suscriptores: list[queue.Queue] = []
_suscriptores_lock = threading.Lock()


def notificar() -> None:
    """Empuja el estado actual a TODOS los clientes SSE conectados."""
    payload = json.dumps(state.snapshot(), ensure_ascii=False)
    with _suscriptores_lock:
        muertos = []
        for q in _suscriptores:
            try:
                q.put(payload, timeout=0.05)
            except (queue.Full, queue.Empty):
                muertos.append(q)
        for q in muertos:
            _suscriptores.remove(q)


def _persist_and_notify() -> None:
    guardar_datos(state.datos_persistibles())
    notificar()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Cronómetro thread-safe con Condition
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class Cronometro(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="Cronometro")
        self._cv = threading.Condition()
        self._running = False
        self._target_end = 0.0
        self._duracion_original = 0

    def arrancar(self, segundos: int):
        # âš ï¸ Orden: _cv antes que state._lock (NUNCA invertir â€” riesgo de deadlock)
        with self._cv:
            self._duracion_original = segundos
            self._target_end = time.monotonic() + segundos
            self._running = True
            self._cv.notify()

    def reiniciar(self) -> None:
        with self._cv:
            self._target_end = time.monotonic() + self._duracion_original
            self._running = True
            self._cv.notify()

    def parar(self) -> None:
        with self._cv:
            self._running = False
            self._cv.notify()

    def parar_con_lock(self) -> None:
        """Call when state._lock is already held (lock is NOT re-entrant)."""
        with self._cv:
            self._running = False
            self._cv.notify()

    def parar_sin_lock(self) -> None:
        """Call when NO locks are held (acquires both _cv and state._lock)."""
        self.parar()

    def run(self):
        while True:
            with self._cv:
                if not self._running:
                    self._cv.wait()
                    continue
                now = time.monotonic()
                wait = max(0, self._target_end - now)
                self._cv.wait(timeout=min(wait, 1.0))
                if not self._running:
                    continue
                now = time.monotonic()
                if now >= self._target_end:
                    with state._lock:
                        state.timer_activo = False
                        state.timer_segundos = 0
                        state._log_actividad("â± Tiempo agotado")
                        # Auto-close roulette if it was active and timer expired
                        if state.ruleta_activa:
                            state.ruleta_activa = False
                            state.ruleta_categoria = None
                            state.ruleta_resultado = None
                            state.ruleta_subconjunto = []
                            state._log_actividad(
                                "ðŸŽ° Ruleta cerrada automáticamente (timer expirado)"
                            )
                    self._running = False
                else:
                    with state._lock:
                        state.timer_segundos = max(0, int(self._target_end - now))
            notificar()


cronometro = Cronometro()
cronometro.start()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Versos Timer â€” dedicated thread for Bible Verses Mode
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class VersosCronometro(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="VersosCronometro")
        self._cv = threading.Condition()
        self._running = False
        self._target_end = 0.0

    def arrancar(self, segundos: int):
        with self._cv:
            with state._lock:
                state.versos_timer_segundos = segundos
                state.versos_timer_totales = segundos
                state.versos_timer_fin = time.monotonic() + segundos
                self._target_end = state.versos_timer_fin
            self._running = True
            self._cv.notify()

    def parar(self) -> None:
        with self._cv:
            self._running = False
            with state._lock:
                state.versos_timer_segundos = 0
            self._cv.notify()

    def parar_con_lock(self) -> None:
        """Call when state._lock is already held (lock is NOT re-entrant)."""
        with self._cv:
            self._running = False
            self._cv.notify()

    def parar_sin_lock(self) -> None:
        """Call when NO locks are held (acquires both _cv and state._lock)."""
        self.parar()

    def run(self):
        while True:
            with self._cv:
                if not self._running:
                    self._cv.wait()
                    continue
                now = time.monotonic()
                with state._lock:
                    remaining = (
                        int(state.versos_timer_fin - now)
                        if state.versos_timer_fin > now
                        else 0
                    )
                    state.versos_timer_segundos = remaining
                wait = max(0, self._target_end - now)
                self._cv.wait(timeout=min(wait, 0.5))
                if not self._running:
                    continue
                now = time.monotonic()
                with state._lock:
                    remaining = (
                        int(state.versos_timer_fin - now)
                        if state.versos_timer_fin > now
                        else 0
                    )
                    state.versos_timer_segundos = remaining
                    if remaining <= 0 and self._running:
                        self._running = False
                        state.versos_mostrar_respuesta = True
                        state.mostrar_respuesta = True
                        state._log_actividad("â± Versos: Â¡TIEMPO TERMINADO!")
                notificar()


versos_cronometro = VersosCronometro()
versos_cronometro.start()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Flask App
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
app = Flask(__name__)
CORS(app)


# â”€â”€ Afterâ€‘request: charset + security headers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.after_request
def add_security_headers(resp):
    ct = resp.content_type or ""
    if ct.startswith("text/") and "charset" not in ct:
        resp.content_type = ct + "; charset=utf-8"
    elif ct == "application/json" and "charset" not in ct:
        resp.content_type = ct + "; charset=utf-8"
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    if resp.headers.get("Cache-Control") and resp.headers.get("Expires"):
        del resp.headers["Expires"]
    resp.headers.pop("X-XSS-Protection", None)
    if resp.headers.get("X-Frame-Options"):
        resp.headers["Content-Security-Policy"] = "frame-ancestors 'self';"
        del resp.headers["X-Frame-Options"]
    return resp


# â”€â”€ SSE endpoint â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/stream")
def stream():
    def event_gen():
        q: queue.Queue = queue.Queue(maxsize=30)
        with _suscriptores_lock:
            while len(_suscriptores) >= 15:
                old_q = _suscriptores.pop(0)
                try:
                    old_q.put_nowait(None)
                except Exception:
                    pass
            _suscriptores.append(q)
        try:
            yield f"data: {json.dumps(state.snapshot(), ensure_ascii=False)}\n\n"
            while True:
                try:
                    data = q.get(timeout=1)
                    if data is None:
                        break
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            # Client disconnected â€” let the generator exit cleanly
            raise
        finally:
            with _suscriptores_lock:
                if q in _suscriptores:
                    _suscriptores.remove(q)

    return Response(
        event_gen(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# â”€â”€ Preguntas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/preguntas", methods=["GET"])
def get_preguntas():
    categoria = request.args.get("categoria")
    with state._lock:
        lista = list(state.preguntas)
    if categoria:
        categoria = categoria.strip()
        lista = [p for p in lista if p.get("categoria") == categoria]
    return jsonify({
        "preguntas": lista,
        "categorias_disponibles": CATEGORIAS_PREGUNTAS,
    })


@app.route("/api/preguntas", methods=["POST"])
def crear_pregunta():
    data = request.get_json(silent=True) or {}
    texto = data.get("texto")
    respuesta = data.get("respuesta")

    if not isinstance(texto, str) or not isinstance(respuesta, str):
        return jsonify({"error": "texto y respuesta deben ser strings"}), 400
    texto = texto.strip()
    respuesta = respuesta.strip()
    if not texto or not respuesta:
        return jsonify({"error": "texto y respuesta no pueden estar vacíos"}), 400

    nueva = {"id": state.siguiente_id(), "texto": texto, "respuesta": respuesta}

    # Categoría (opcional)
    categoria = data.get("categoria")
    if isinstance(categoria, str) and categoria.strip():
        nueva["categoria"] = categoria.strip()

    # Opciones múltiples (opcional)
    opciones = data.get("opciones")
    if opciones is not None:
        if (
            not isinstance(opciones, list)
            or len(opciones) != 3
            or not all(isinstance(o, str) and o.strip() for o in opciones)
        ):
            return jsonify(
                {"error": "opciones debe ser un array de 3 strings no vacíos"}
            ), 400
        opciones = [o.strip() for o in opciones]
        rc = data.get("respuesta_correcta")
        if not type(rc) is int or rc not in (0, 1, 2):
            return jsonify({"error": "respuesta_correcta debe ser 0, 1 o 2"}), 400
        if opciones[rc] != respuesta:
            return jsonify(
                {"error": "respuesta debe coincidir con opciones[respuesta_correcta]"}
            ), 400
        nueva["opciones"] = opciones
        nueva["respuesta_correcta"] = rc

    state.agregar_pregunta(nueva)
    _persist_and_notify()
    log.info("Pregunta creada id=%d", nueva["id"])
    return jsonify(nueva), 201


# F1-1: Editar pregunta existente
@app.route("/api/preguntas/<int:pid>", methods=["PUT"])
def editar_pregunta(pid: int):
    data = request.get_json(silent=True) or {}
    texto = data.get("texto")
    respuesta = data.get("respuesta")

    if not isinstance(texto, str) or not isinstance(respuesta, str):
        return jsonify({"error": "texto y respuesta deben ser strings"}), 400
    texto = texto.strip()
    respuesta = respuesta.strip()
    if not texto or not respuesta:
        return jsonify({"error": "texto y respuesta no pueden estar vacíos"}), 400

    extra = {}
    # Si opciones está presente en el body (incluso null), procesarlo
    if "opciones" in data:
        opciones = data.get("opciones")
        if opciones is None:
            extra["opciones"] = None
            extra["respuesta_correcta"] = None
        else:
            if (
                not isinstance(opciones, list)
                or len(opciones) != 3
                or not all(isinstance(o, str) and o.strip() for o in opciones)
            ):
                return jsonify(
                    {"error": "opciones debe ser un array de 3 strings no vacíos"}
                ), 400
            opciones = [o.strip() for o in opciones]
            rc = data.get("respuesta_correcta")
            if not type(rc) is int or rc not in (0, 1, 2):
                return jsonify({"error": "respuesta_correcta debe ser 0, 1 o 2"}), 400
            if opciones[rc] != respuesta:
                return jsonify(
                    {
                        "error": "respuesta debe coincidir con opciones[respuesta_correcta]"
                    }
                ), 400
            extra["opciones"] = opciones
            extra["respuesta_correcta"] = rc

    # Categoría (opcional)
    if "categoria" in data:
        cat = data.get("categoria")
        extra["categoria"] = cat.strip() if isinstance(cat, str) and cat.strip() else None

    updated = state.editar_pregunta(pid, texto, respuesta, extra)
    if updated:
        _persist_and_notify()
        log.info("Pregunta editada id=%d", pid)
        return jsonify({"ok": True})
    return jsonify({"error": "Pregunta no encontrada"}), 404


@app.route("/api/preguntas/<int:pid>", methods=["DELETE"])
def eliminar_pregunta(pid: int):
    if state.eliminar_pregunta(pid):
        _persist_and_notify()
        log.info("Pregunta eliminada id=%d", pid)
        return jsonify({"ok": True})
    return jsonify({"error": "Pregunta no encontrada"}), 404


# F2-2: Exportar banco de preguntas
@app.route("/api/preguntas/exportar", methods=["GET"])
def exportar_preguntas():
    with state._lock:
        data = {"preguntas": list(state.preguntas)}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"preguntas_{ts}.json"
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# F2-2: Importar banco de preguntas
@app.route("/api/preguntas/importar", methods=["POST"])
def importar_preguntas():
    data = request.get_json(silent=True) or {}
    preguntas = data.get("preguntas")
    modo = data.get("modo", "reemplazar")  # "reemplazar" | "agregar"

    if not isinstance(preguntas, list):
        return jsonify({"error": "Se esperaba {preguntas: [...]}"}), 400

    nuevas = []
    for p in preguntas:
        if not isinstance(p, dict):
            continue
        texto = str(p.get("texto", "")).strip()
        respuesta = str(p.get("respuesta", "")).strip()
        if texto and respuesta:
            q = {"texto": texto, "respuesta": respuesta}
            # Preservar categoría si existe
            cat = p.get("categoria")
            if isinstance(cat, str) and cat.strip():
                q["categoria"] = cat.strip()
            if (
                p.get("opciones")
                and isinstance(p["opciones"], list)
                and len(p["opciones"]) == 3
            ):
                opciones = [str(o).strip() for o in p["opciones"]]
                rc = p.get("respuesta_correcta")
                if not type(rc) is int or rc not in (0, 1, 2):
                    continue
                if opciones[rc] != respuesta:
                    continue
                q["opciones"] = opciones
                q["respuesta_correcta"] = rc
            nuevas.append(q)

    if not nuevas:
        return jsonify({"error": "El archivo no contiene preguntas válidas"}), 400

    with state._lock:
        if modo == "reemplazar":
            state.preguntas = []
        base_id = max((p["id"] for p in state.preguntas), default=0) + 1
        for i, p in enumerate(nuevas):
            p["id"] = base_id + i
            state.preguntas.append(p)
        state._log_actividad(f"Importadas {len(nuevas)} preguntas ({modo})")

    _persist_and_notify()
    log.info("Importadas %d preguntas (modo=%s)", len(nuevas), modo)
    return jsonify({"ok": True, "importadas": len(nuevas)})


# â”€â”€ Puntos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/puntos", methods=["POST"])
def sumar_puntos():
    """F1-2: cantidad puede ser negativa para penalizar."""
    data = request.get_json(silent=True) or {}
    grupo = data.get("grupo")
    cantidad = data.get("cantidad", 10)

    if not isinstance(grupo, str) or grupo not in get_grupos_validos(state):
        return jsonify({"error": "Grupo inválido"}), 400
    if not type(cantidad) is int:
        return jsonify({"error": "cantidad debe ser entero"}), 400

    if not state.sumar_puntos(grupo, cantidad):
        return jsonify({"error": "Grupo no encontrado"}), 404

    _persist_and_notify()
    log.info("%+d pts â†’ %s", cantidad, grupo)
    with state._lock:
        pts = dict(state.puntos)
    return jsonify({"ok": True, "puntos": pts})


# F1-2: Endpoint explícito de penalización
@app.route("/api/puntos/restar", methods=["POST"])
def restar_puntos():
    data = request.get_json(silent=True) or {}
    grupo = data.get("grupo")
    cantidad = data.get("cantidad", 10)

    if not isinstance(grupo, str) or grupo not in get_grupos_validos(state):
        return jsonify({"error": "Grupo inválido"}), 400
    if not type(cantidad) is int or cantidad < 0:
        return jsonify({"error": "cantidad debe ser entero positivo (se restará)"}), 400

    if not state.sumar_puntos(grupo, -cantidad):
        return jsonify({"error": "Grupo no encontrado"}), 404

    _persist_and_notify()
    log.info("-%d pts â†’ %s", cantidad, grupo)
    with state._lock:
        pts = dict(state.puntos)
    return jsonify({"ok": True, "puntos": pts})


@app.route("/api/puntos/reset", methods=["POST"])
def reset_puntos():
    with state._lock:
        for g in get_grupos_validos(state):
            state.puntos[g] = 0
        state._log_actividad("â†º Puntos reiniciados")
    _persist_and_notify()
    return jsonify({"ok": True})


@app.route("/api/grupos/<string:grupo_key>/puntos", methods=["PATCH"])
def patch_puntos(grupo_key: str):
    data = request.get_json(silent=True) or {}
    if "cantidad" not in data:
        return jsonify({"error": "El campo 'cantidad' es obligatorio"}), 400
    cantidad = data.get("cantidad", 0)
    if not type(cantidad) is int:
        return jsonify({"error": "cantidad debe ser entero"}), 400
    if grupo_key not in get_grupos_validos(state):
        return jsonify({"error": "Grupo no encontrado"}), 404
    if not state.ajustar_puntos(grupo_key, cantidad):
        return jsonify({"error": "No se pudieron ajustar los puntos"}), 500
    _persist_and_notify()
    with state._lock:
        pts = state.puntos[grupo_key]
    return jsonify({"ok": True, "puntos": pts})


@app.route("/api/puntos/ajustar", methods=["POST"])
def ajustar_puntos():
    data = request.get_json(silent=True) or {}
    grupo = data.get("grupo")
    valor = data.get("valor")
    if not isinstance(grupo, str) or grupo not in get_grupos_validos(state):
        return jsonify({"error": "Grupo inválido"}), 400
    if not type(valor) is int:
        return jsonify({"error": "valor debe ser entero"}), 400
    if state.ajustar_puntos(grupo, valor):
        _persist_and_notify()
        return jsonify({"ok": True})
    return jsonify({"error": "Grupo no encontrado"}), 400


# â”€â”€ Proyección â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/pregunta-actual", methods=["POST"])
def set_pregunta_actual():
    data = request.get_json(silent=True) or {}
    pid = data.get("id")
    if not type(pid) is int:
        return jsonify({"error": "id debe ser entero"}), 400
    p = state.set_pregunta(pid)
    if p:
        notificar()
        return jsonify({"ok": True, "pregunta": p})
    return jsonify({"error": "No encontrada"}), 404


@app.route("/api/mostrar-respuesta", methods=["POST"])
def set_mostrar_respuesta():
    data = request.get_json(silent=True) or {}
    mostrar = data.get("mostrar", False)
    with state._lock:
        state.mostrar_respuesta = bool(mostrar)
        state.mostrar_opciones = bool(mostrar)
        if mostrar:
            state.timer_activo = False
        accion = "Respuesta revelada" if mostrar else "Respuesta ocultada"
        state._log_actividad(accion)
    if mostrar:
        cronometro.parar()
    notificar()
    return jsonify({"ok": True, "mostrar": state.mostrar_respuesta})


@app.route("/api/pregunta-actual/mostrar-opciones", methods=["POST"])
def mostrar_opciones():
    with state._lock:
        state.mostrar_opciones = True
        state.opcion_seleccionada = None
        state.timer_segundos = 15
        state.timer_totales = 15
        state.timer_activo = True
        state._log_actividad("ðŸ“‹ Opciones mostradas â€” timer 15s")
    cronometro.parar()
    cronometro.arrancar(15)
    notificar()
    return jsonify({"ok": True})


@app.route("/api/pregunta-actual/clear", methods=["POST"])
def clear_pregunta_actual():
    with state._lock:
        state.pregunta_actual = None
        state.mostrar_respuesta = False
        state.mostrar_opciones = False
    notificar()
    return jsonify({"ok": True})


# â”€â”€ Temporizador â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/temporizador/iniciar", methods=["POST"])
def iniciar_temporizador():
    data = request.get_json(silent=True) or {}
    try:
        seg = int(data.get("segundos", 45))
    except (TypeError, ValueError):
        return jsonify({"error": "segundos debe ser entero"}), 400
    with state._lock:
        state.timer_segundos = seg
        state.timer_totales = seg
    cronometro.arrancar(seg)
    notificar()
    return jsonify({"ok": True})


@app.route("/api/temporizador/reiniciar", methods=["POST"])
def reiniciar_temporizador():
    cronometro.reiniciar()
    notificar()
    with state._lock:
        seg = state.timer_totales
    return jsonify({"ok": True, "segundos": seg})


@app.route("/api/temporizador/parar", methods=["POST"])
def parar_temporizador():
    cronometro.parar()
    notificar()
    return jsonify({"ok": True})


# â”€â”€ Actividad (F2-1) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/actividad", methods=["GET"])
def get_actividad():
    return jsonify({"actividad": state.get_actividad()})


# â”€â”€ Estado completo (polling legacy) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/estado-actual", methods=["GET"])
def estado_actual():
    return jsonify(state.snapshot())


# â”€â”€ Display Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/display/theme", methods=["POST"])
def set_display_theme():
    data = request.get_json(silent=True) or {}
    theme = data.get("theme", "brutal")
    valid_themes = {"brutal", "calm"}
    if theme not in valid_themes:
        return jsonify(
            {"error": f"tema inválido. Válidos: {', '.join(valid_themes)}"}
        ), 400
    with state._lock:
        state.display_config["theme"] = theme
        state._log_actividad(f"ðŸŽ¨ Tema display: {theme}")
    notificar()
    return jsonify({"ok": True, "theme": theme})


@app.route("/api/display/kiosko", methods=["POST"])
def toggle_kiosko():
    data = request.get_json(silent=True) or {}
    active = data.get("active")
    with state._lock:
        if active is not None:
            state.display_config["kiosko"] = bool(active)
        else:
            state.display_config["kiosko"] = not state.display_config["kiosko"]
        kiosko = state.display_config["kiosko"]
        state._log_actividad(f"Modo kiosko: {'ON' if kiosko else 'OFF'}")
    notificar()
    return jsonify({"ok": True, "kiosko": kiosko})


@app.route("/api/display/animations", methods=["POST"])
def toggle_animations():
    data = request.get_json(silent=True) or {}
    disabled = data.get("disabled")
    with state._lock:
        if disabled is not None:
            state.display_config["animations_disabled"] = bool(disabled)
        else:
            state.display_config["animations_disabled"] = not state.display_config[
                "animations_disabled"
            ]
        d = state.display_config["animations_disabled"]
        state._log_actividad(f"Animaciones: {'OFF' if d else 'ON'}")
    notificar()
    return jsonify({"ok": True, "disabled": d})


@app.route("/api/display/reset-overlays", methods=["POST"])
def reset_overlays():
    with state._lock:
        state.display_config["overlay_reset"] += 1
        state._log_actividad("Overlays reiniciados")
    notificar()
    return jsonify({"ok": True})


@app.route("/api/display/black-screen", methods=["POST"])
def toggle_black_screen():
    data = request.get_json(silent=True) or {}
    active = data.get("active")
    with state._lock:
        if active is not None:
            state.display_config["black_screen"] = bool(active)
        else:
            state.display_config["black_screen"] = not state.display_config[
                "black_screen"
            ]
        bs = state.display_config["black_screen"]
        state._log_actividad(f"Pantalla negra: {'ON' if bs else 'OFF'}")
    notificar()
    return jsonify({"ok": True, "black_screen": bs})


@app.route("/api/display/freeze", methods=["POST"])
def toggle_freeze():
    data = request.get_json(silent=True) or {}
    active = data.get("active")
    with state._lock:
        if active is not None:
            state.display_config["frozen"] = bool(active)
        else:
            state.display_config["frozen"] = not state.display_config["frozen"]
        fz = state.display_config["frozen"]
        state._log_actividad(f"Pantalla congelada: {'ON' if fz else 'OFF'}")
    notificar()
    return jsonify({"ok": True, "frozen": fz})


@app.route("/api/display/clean", methods=["POST"])
def display_clean():
    with state._lock:
        state.display_config["clean"] = not state.display_config.get("clean", False)
        clean = state.display_config["clean"]
        state._log_actividad(f"ðŸ§¹ Modo clean: {'ON' if clean else 'OFF'}")
    notificar()
    return jsonify({"ok": True, "clean": clean})


@app.route("/api/display/final-round", methods=["POST"])
def toggle_final_round():
    with state._lock:
        state.display_config["final_round"] = not state.display_config.get("final_round", False)
        fr = state.display_config["final_round"]
        estado = "ON" if fr else "OFF"
        state._log_actividad(f"🏆 Ronda final: {estado}")
    notificar()
    return jsonify({"ok": True, "final_round": fr})


@app.route("/api/display/eliminar", methods=["POST"])
def toggle_eliminar():
    data = request.get_json(silent=True) or {}
    grupo = data.get("grupo")
    if not isinstance(grupo, str) or grupo not in get_grupos_validos(state):
        return jsonify({"error": "Grupo inválido"}), 400
    with state._lock:
        elim = state.display_config.setdefault("eliminados", [])
        if grupo in elim:
            elim.remove(grupo)
            state._log_actividad(f"♻️ {grupo} reinstado")
        else:
            elim.append(grupo)
            state._log_actividad(f"🚫 {grupo} eliminado")
    notificar()
    return jsonify({"ok": True, "eliminados": state.display_config.get("eliminados", [])})


@app.route("/api/grupos/config", methods=["POST"])
def grupos_config():
    data = request.get_json(silent=True) or {}
    grupos = data.get("grupos")
    if not isinstance(grupos, list) or len(grupos) < 4 or len(grupos) > 6:
        return jsonify({"error": "Se requieren 4-6 grupos"}), 400
    base_keys = {g["key"] for g in grupos if g.get("fijo")}
    for bg in GRUPOS_CONFIG_DEFAULT:
        if bg["key"] not in base_keys:
            return jsonify({"error": f"El grupo base '{bg['key']}' es obligatorio"}), 400
    ids = set()
    for g in grupos:
        if "key" not in g or "nombre" not in g:
            return jsonify({"error": "Cada grupo necesita key y nombre"}), 400
        kid = g["key"]
        if kid in ids:
            return jsonify({"error": f"Grupo duplicado: {kid}"}), 400
        ids.add(kid)
        if not g.get("color") or not g.get("color2"):
            g["color"] = "#888888"
            g["color2"] = "#AAAAAA"
    with state._lock:
        state.display_config["grupos_config"] = grupos
        # Add any new groups to puntos with 0
        for g in grupos:
            if g["key"] not in state.puntos:
                state.puntos[g["key"]] = 0
        # Remove puntos for deleted groups (skip base groups)
        active_keys = {g["key"] for g in grupos}
        for k in list(state.puntos.keys()):
            if k not in active_keys and k not in {bg["key"] for bg in GRUPOS_CONFIG_DEFAULT}:
                del state.puntos[k]
        state._log_actividad(f"Configuración de grupos actualizada ({len(grupos)} grupos)")
    _persist_and_notify()
    return jsonify({"ok": True, "grupos_config": grupos})


@app.route("/api/display/final-results", methods=["POST"])
def show_final_results():
    with state._lock:
        state.display_config["final_results"] = True
        state.display_config["overlay_reset"] += 1
        state._log_actividad("🏆 Resultados finales mostrados")
    notificar()
    return jsonify({"ok": True})


@app.route("/api/display/final-results/hide", methods=["POST"])
def hide_final_results():
    with state._lock:
        state.display_config["final_results"] = False
        state._log_actividad("Resultados finales ocultados")
    notificar()
    return jsonify({"ok": True})


@app.route("/api/exportar/resultados", methods=["GET"])
def exportar_resultados():
    with state._lock:
        puntos = dict(state.puntos)
        actividad = list(state._actividad)
    ranking = sorted(
        [{"grupo": k, "puntos": v} for k, v in puntos.items()],
        key=lambda x: x["puntos"],
        reverse=True,
    )
    data = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "puntos": puntos,
        "ranking": ranking,
        "actividad": actividad,
    }
    return jsonify(data)


@app.route("/api/exportar/resultados/imagen", methods=["GET"])
def exportar_resultados_imagen():
    with state._lock:
        puntos = dict(state.puntos)
    ranking = sorted(
        [{"grupo": k, "puntos": v} for k, v in puntos.items()],
        key=lambda x: x["puntos"],
        reverse=True,
    )
    cards_html = ""
    icons = ["🥇", "🥈", "🥉", "🏅"]
    for i, r in enumerate(ranking):
        color = "#FFD700" if i == 0 else "#C0C0C0" if i == 1 else "#CD7F32" if i == 2 else "#fff"
        text_color = "#000" if i < 3 else "#333"
        cards_html += f"""
        <div style="background:{color};border:4px solid #000;padding:20px 30px;text-align:center;min-width:200px;border-radius:4px;">
            <div style="font-size:3rem;">{icons[i] if i < len(icons) else "🏅"}</div>
            <div style="font-size:2rem;font-weight:900;color:{text_color};">{r['grupo']}</div>
            <div style="font-size:3rem;font-weight:900;color:{text_color};">{r['puntos']} pts</div>
            <div style="font-size:1.2rem;font-weight:700;color:{text_color};background:#000;color:#fff;display:inline-block;padding:2px 16px;margin-top:4px;">#{i + 1}</div>
        </div>
        """
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Resultados</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0038ff;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:40px;}}
h1{{color:#FFD700;font-size:3rem;text-shadow:4px 4px 0 #000;margin-bottom:30px;}}
.podium{{display:flex;gap:20px;align-items:flex-end;flex-wrap:wrap;justify-content:center;}}
.footer{{color:#fff;margin-top:30px;font-size:1rem;opacity:0.7;}}
</style></head>
<body>
<h1>🏆 RESULTADOS FINALES</h1>
<div class="podium">{cards_html}</div>
<div class="footer">Generado el {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
</body></html>"""
    return Response(html, mimetype="text/html; charset=utf-8")


@app.route("/api/salir", methods=["POST"])
def salir():
    with state._lock:
        if state.versos_activo:
            versos_cronometro.parar_con_lock()
            state.versos_timer_segundos = 0
            state.versos_activo = False
            state.versos_pregunta_actual = None
            state.versos_mostrar_respuesta = False
        if state.ruleta_activa:
            state.ruleta_activa = False
            state.ruleta_categoria = None
            state.ruleta_resultado = None
            state.ruleta_subconjunto = []
        cronometro.parar_con_lock()
        state.modo = "preguntas"
        state.pregunta_actual = None
        state.mostrar_respuesta = False
        state.mostrar_opciones = False
        state.timer_activo = False
        state._log_actividad("🚪 Salir — todos los modos cerrados")
    notificar()
    return jsonify({"ok": True})


@app.route("/api/ruleta/iniciar", methods=["POST"])
def iniciar_ruleta():
    """Genera dos números aleatorios y determina la categoría ganadora."""
    with state._lock:
        if state.ruleta_activa:
            return jsonify({"error": "La ruleta ya está activa"}), 400

        num_palabra = random.randint(1, 99)
        num_cantante = random.randint(1, 99)
        categoria = "palabra" if num_palabra > num_cantante else "cantante"

        if categoria not in ("palabra", "cantante"):
            return jsonify({"error": "Categoría inválida"}), 500

        fuente = PALABRAS_ALABANZA if categoria == "palabra" else CANTANTES
        if not fuente:
            return jsonify(
                {"error": "No hay elementos disponibles en la fuente seleccionada"}
            ), 500

        state.ruleta_activa = True
        state.ruleta_num_palabra = num_palabra
        state.ruleta_num_cantante = num_cantante
        state.ruleta_categoria = categoria
        state.ruleta_resultado = None
        state.ruleta_subconjunto = []
        state.ruleta_anim_id += 1
        state.modo = "ruleta"
        state._log_actividad(f"ðŸŽ° Ruleta iniciada â†’ {categoria}")
    notificar()
    return jsonify(
        {
            "ok": True,
            "num_palabra": num_palabra,
            "num_cantante": num_cantante,
            "categoria": categoria,
        }
    )


@app.route("/api/ruleta/seleccionar", methods=["POST"])
def seleccionar_ruleta():
    """Elige 20 items del banco ganador y selecciona uno al azar."""
    with state._lock:
        if not state.ruleta_categoria or not state.ruleta_activa:
            return jsonify({"error": "No hay ruleta activa"}), 400

        fuente = PALABRAS_ALABANZA if state.ruleta_categoria == "palabra" else CANTANTES
        if not fuente:
            return jsonify(
                {"error": "No hay elementos disponibles en la fuente seleccionada"}
            ), 500

        subconjunto = random.sample(fuente, min(20, len(fuente)))
        resultado = random.choice(subconjunto)

        if state.ruleta_historial and random.random() < 0.01:
            if state.ruleta_historial:
                resultado = random.choice(state.ruleta_historial[-10:])

        state.ruleta_historial.append(resultado)
        if len(state.ruleta_historial) > 50:
            state.ruleta_historial = state.ruleta_historial[-50:]
        state.ruleta_subconjunto = subconjunto
        state.ruleta_resultado = resultado
        state.ruleta_anim_id += 1
        state.timer_segundos = 120
        state.timer_totales = 120
        state.timer_activo = True
        state._log_actividad(f"ðŸŽ° Ruleta resultado: {resultado}")
    cronometro.arrancar(120)
    notificar()
    return jsonify(
        {
            "ok": True,
            "subconjunto": subconjunto,
            "resultado": resultado,
            "segundos": 120,
        }
    )


@app.route("/api/ruleta/cerrar", methods=["POST"])
def cerrar_ruleta():
    """Cierra la ruleta y limpia todo el estado."""
    cronometro.parar()
    with state._lock:
        if not state.ruleta_activa:
            return jsonify({"error": "La ruleta no está activa"}), 400

        state.ruleta_activa = False
        state.ruleta_categoria = None
        state.ruleta_resultado = None
        state.ruleta_subconjunto = []
        state.modo = "preguntas"
        state._log_actividad("ðŸŽ° Ruleta cerrada")
    notificar()
    return jsonify({"ok": True})


# â”€â”€ Opción múltiple: seleccionar opción â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/pregunta-actual/seleccionar-opcion", methods=["POST"])
def seleccionar_opcion():
    """El operador selecciona una opción (0, 1, 2)."""
    data = request.get_json(silent=True) or {}
    indice = data.get("indice")
    if not type(indice) is int or indice not in (0, 1, 2):
        return jsonify({"error": "indice debe ser 0, 1 o 2"}), 400
    with state._lock:
        state.opcion_seleccionada = indice
        if state.pregunta_actual and state.pregunta_actual.get("opciones"):
            if indice == state.pregunta_actual.get("respuesta_correcta"):
                state._log_actividad(
                    f"Opción {['A', 'B', 'C'][indice]} seleccionada â€” correcta"
                )
            else:
                state._log_actividad(
                    f"Opción {['A', 'B', 'C'][indice]} seleccionada â€” incorrecta"
                )
    notificar()
    return jsonify({"ok": True, "opcion_seleccionada": indice})


# â”€â”€ Versos Bíblicos â€” 5 endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/versos/iniciar", methods=["POST"])
def versos_iniciar():
    """Inicia el modo versos bíblicos."""
    data = request.get_json(silent=True) or {}
    categoria = data.get("categoria", "quiensoy")
    if categoria not in ("quiensoy", "libros", "versiculos"):
        return jsonify({"error": "Categoría inválida"}), 400
    with state._lock:
        if state.versos_activo:
            return jsonify({"error": "El modo versos ya está activo"}), 400
        state.versos_activo = True
        state.versos_categoria = categoria
        state.modo = "versos"
        # Load a random verse for display
        try:
            biblia = get_biblia()
            ref, texto = biblia.get_random_verse()
            state.versos_pregunta_actual = {"referencia": ref, "texto": texto}
        except Exception as e:
            app.logger.error("Error loading Bible verse: %s", e, exc_info=True)
            state.versos_pregunta_actual = None
        state.versos_mostrar_respuesta = False
        state.versos_subconjunto = []
        state.versos_resultado = None
        state.versos_timer_segundos = 0
        state.versos_timer_totales = 0
        state.versos_timer_fin = 0.0
        state._log_actividad(f"ðŸ“– Versos modo iniciado â€” {categoria}")
    notificar()
    return jsonify({"ok": True, "categoria": categoria})


@app.route("/api/versos/timer/set", methods=["POST"])
def versos_timer_set():
    """Configura el timer del modo versos (sin iniciarlo)."""
    data = request.get_json(silent=True) or {}
    try:
        seg = int(data.get("segundos", 60))
    except (TypeError, ValueError):
        return jsonify({"error": "segundos debe ser entero"}), 400
    if seg < 5 or seg > 600:
        return jsonify({"error": "segundos debe estar entre 5 y 600"}), 400
    with state._lock:
        state.versos_timer_segundos = seg
        state.versos_timer_totales = seg
        state.versos_timer_fin = time.monotonic() + seg
    notificar()
    return jsonify({"ok": True, "segundos": seg})


@app.route("/api/versos/timer/start", methods=["POST"])
def versos_timer_start():
    """Inicia la cuenta regresiva del modo versos."""
    with state._lock:
        if not state.versos_activo:
            return jsonify({"error": "El modo versos no está activo"}), 400
        if state.versos_timer_segundos <= 0:
            return jsonify(
                {"error": "Configure el timer primero con /versos/timer/set"}
            ), 400
        timer_seg = state.versos_timer_segundos
    versos_cronometro.arrancar(timer_seg)
    notificar()
    return jsonify({"ok": True, "segundos": timer_seg})


@app.route("/api/versos/stop", methods=["POST"])
def versos_stop():
    """Detiene el timer del modo versos."""
    versos_cronometro.parar()
    with state._lock:
        state.versos_mostrar_respuesta = True
        state._log_actividad("â¹ Versos: timer detenido manualmente")
    notificar()
    return jsonify({"ok": True})


@app.route("/api/versos/timer/reset", methods=["POST"])
def versos_timer_reset():
    """Reinicia el timer versos sin revelar respuesta."""
    data = request.get_json(silent=True) or {}
    try:
        segundos = int(data.get("segundos", 30))
    except (TypeError, ValueError):
        return jsonify({"error": "segundos debe ser entero"}), 400
    if segundos < 5 or segundos > 600:
        return jsonify({"error": "segundos debe estar entre 5 y 600"}), 400
    versos_cronometro.parar()
    with state._lock:
        state.versos_timer_segundos = segundos
        state.versos_timer_totales = segundos
        state.versos_timer_fin = time.monotonic() + segundos
        state._log_actividad(f"ðŸ”„ Versos: Timer reiniciado a {segundos}s")
    versos_cronometro.arrancar(segundos)
    notificar()
    return jsonify({"ok": True, "segundos": segundos})


@app.route("/api/versos/close", methods=["POST"])
def versos_close():
    """Cierra el modo versos y limpia todo el estado."""
    versos_cronometro.parar()
    with state._lock:
        state.versos_activo = False
        state.versos_categoria = None
        state.versos_pregunta_actual = None
        state.modo = "preguntas"
        state.versos_mostrar_respuesta = False
        state.versos_subconjunto = []
        state.versos_resultado = None
        state.versos_historial = []
        state.versos_timer_segundos = 0
        state.versos_timer_totales = 0
        state.versos_timer_fin = 0.0
        state._log_actividad("ðŸ“– Versos modo cerrado")
    notificar()
    return jsonify({"ok": True})


# â”€â”€ Reset total â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/reset-todo", methods=["POST"])
def reset_todo():
    cronometro.parar()
    versos_cronometro.parar()
    state.reset()
    _persist_and_notify()
    log.warning("RESET TOTAL ejecutado")
    return jsonify({"ok": True})

@app.route("/api/bible/load", methods=["POST"])
def bible_load():
    """Upload a .bib file for parsing."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    path = os.path.join(BASE_DIR, "uploaded_bible.bib")
    file.save(path)
    try:
        get_biblia(path)
        return jsonify({"ok": True, "message": "Biblia cargada exitosamente"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bible/versiculo/random", methods=["GET"])
def bible_versiculo_random():
    """Get a random verse: show reference, answer is the text."""
    biblia = get_biblia()
    ref, text = biblia.get_random_verse()
    return jsonify({"referencia": ref, "texto": text})


@app.route("/api/bible/versiculo/completar", methods=["GET"])
def bible_versiculo_completar():
    """Get a verse with words blanked for completion."""
    biblia = get_biblia()
    ref, hint, answers = biblia.get_verse_completion()
    return jsonify({"referencia": ref, "pista": hint, "respuesta": answers})


@app.route("/api/bible/personaje/random", methods=["GET"])
def bible_personaje_random():
    """Get a random character question."""
    p = get_biblia().get_random_personaje()
    return jsonify(
        {
            "nombre": p["nombre"],
            "pista_inicial": p["pistas"][0],
            "pistas": p["pistas"][1:],
            "libro": p["libro"],
            "epoca": p["epoca"],
        }
    )


@app.route("/api/bible/pista", methods=["POST"])
def bible_pista():
    """Get next hint for current character."""
    data = request.get_json(silent=True) or {}
    nombre = data.get("nombre")
    nivel = data.get("nivel", 0)
    biblia = get_biblia()
    for p in biblia.personajes:
        if p["nombre"] == nombre:
            pista_text, is_final = biblia.get_pista(p, nivel)
            return jsonify({"pista": pista_text, "is_final": is_final, "nivel": nivel})
    return jsonify({"error": "Personaje no encontrado"}), 404


# â”€â”€ Rutas estáticas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Fix: quiz-renderer.js no tenía ruta propia â€” el navegador recibía 404
# y renderQuestion nunca se definía, rompiendo toda la proyección.
@app.route("/quiz-renderer.js")
def quiz_renderer_js():
    resp = send_from_directory(BASE_DIR, "quiz-renderer.js")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/control")
def control():
    resp = send_from_directory(BASE_DIR, "control.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/display")
def display():
    resp = send_from_directory(BASE_DIR, "display.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/")
def index():
    if os.path.exists(os.path.join(BASE_DIR, "index.html")):
        resp = send_from_directory(BASE_DIR, "index.html")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        return resp
    return (
        "<meta charset='utf-8'>"
        "<style>body{background:#080808;color:#fff;font-family:sans-serif;"
        "display:flex;flex-direction:column;align-items:center;justify-content:center;"
        "height:100vh;gap:20px;margin:0}</style>"
        "<h1>Campeonísimo Bíblico</h1>"
        "<div style='display:flex;gap:30px'>"
        "<a href='/control' style='color:#7C3AED'>Panel de Control</a>"
        "<a href='/display' style='color:#10B981'>Pantalla Display</a>"
        "</div>"
    )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ARRANQUE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
if __name__ == "__main__":
    if not os.path.exists(DATA_FILE):
        guardar_datos(state.datos_persistibles())
        log.info("Archivo de datos creado: %s", DATA_FILE)
    crear_backup()

    log.info("=" * 56)
    log.info("  Campeonísimo Bíblico â€” Servidor v2 listo")
    log.info("  Panel:   http://localhost:%d/control", SERVER_PORT)
    log.info("  Display: http://localhost:%d/display", SERVER_PORT)
    log.info("  Datos:   %s  |  Debug: %s", DATA_FILE, SERVER_DEBUG)
    log.info("=" * 56)

    if HAS_WAITRESS and not SERVER_DEBUG:
        log.info("Usando Waitress (servidor de producción WSGI)")
        waitress_serve(app, host="0.0.0.0", port=SERVER_PORT, threads=100)
    else:
        if not HAS_WAITRESS:
            log.warning("Waitress no instalado â€” usando servidor de desarrollo Flask.")
        app.run(
            debug=SERVER_DEBUG,
            host="0.0.0.0",
            port=SERVER_PORT,
            use_reloader=False,
            threaded=True,
        )






