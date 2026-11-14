"""Ajustes del asistente del Museo Infantil Trampolín.

Cambia aquí la regla de grupos, las franjas y las tarifas de referencia.
"""

from __future__ import annotations

import os
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

load_dotenv(BASE_DIR / ".env")

# República Dominicana no cambia el reloj: siempre UTC-4.
ZONA = timezone(timedelta(hours=-4), name="America/Santo_Domingo")

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "trampolin.db")))
FERIADOS_PATH = Path(os.getenv("FERIADOS_PATH", str(DATA_DIR / "feriados.json")))
PERMISOS_DIR = DATA_DIR / "permisos"


def _ids(nombre: str) -> list[int]:
    ids: list[int] = []
    for parte in os.getenv(nombre, "").split(","):
        parte = parte.strip()
        if parte.isdigit():
            ids.append(int(parte))
    return ids


ADMIN_IDS = _ids("ADMIN_IDS")
_staff = os.getenv("STAFF_CHAT_ID", "").strip()
STAFF_CHAT_ID = int(_staff) if _staff.isdigit() else None

MUSEO = "Museo Infantil Trampolín"
TELEFONO = "(809) 685-5551"
TELEFONO_2 = "(809) 689-0661"
EMAIL = "reservaciones@trampolin.org.do"
DIRECCION = "Casa Rodrigo de Bastidas, calle Las Damas, Zona Colonial, Santo Domingo"
WEB = "http://www.trampolin.org.do/"
MAPA = "https://www.google.com/maps/search/?api=1&query=Museo+Infantil+Trampolin+Calle+Las+Damas+Santo+Domingo"

# 200 alumnos = 8 grupos. Cada franja de 2 horas admite hasta 8 grupos.
ALUMNOS_POR_GRUPO = 25
GRUPOS_POR_FRANJA = 8
DURACION_HORAS = 2
MAX_ALUMNOS = GRUPOS_POR_FRANJA * ALUMNOS_POR_GRUPO * 3

# Referencia publicada (prensa y guías). Confirmar con el museo antes de cobrar.
TARIFA_PUBLICA = 50
TARIFA_PRIVADA = 100

HORARIO_PUBLICO = (
    "Martes a viernes: 8:30 a.m. a 4:00 p.m.\n"
    "Sábados y domingos: 9:30 a.m. a 5:30 p.m.\n"
    "Lunes: cerrado."
)

# Franjas seguidas, sin solaparse, de exactamente 2 horas.
# Entre semana el museo cierra a las 4:00 p.m.; la última entrada guiada es 12:30 p.m.
FRANJAS_ENTRE_SEMANA = (
    ("08:30", "10:30"),
    ("10:30", "12:30"),
    ("12:30", "14:30"),
)
FRANJAS_FIN_DE_SEMANA = (
    ("09:30", "11:30"),
    ("11:30", "13:30"),
    ("13:30", "15:30"),
    ("15:30", "17:30"),
)


def es_admin(user_id: int | None) -> bool:
    return bool(user_id) and user_id in ADMIN_IDS
