"""Recordatorios de permiso del MINERD y de la visita."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import config
import contenido
import database as db

logger = logging.getLogger(__name__)


@dataclass
class Aviso:
    tipo: str
    marcar: tuple[str, ...]


def plan_recordatorios(reserva: dict, ahora: datetime, enviados: set[str]) -> Aviso | None:
    salida = datetime.combine(
        datetime.strptime(reserva["fecha"], "%Y-%m-%d").date(),
        datetime.strptime(reserva["hora_inicio"], "%H:%M").time(),
        tzinfo=config.ZONA,
    )
    horas = (salida - ahora).total_seconds() / 3600
    if horas <= 0:
        return None

    creado = datetime.fromisoformat(reserva["creado_en"])
    if creado.tzinfo is None:
        creado = creado.replace(tzinfo=config.ZONA)
    falta_permiso = not reserva.get("permiso_file_id")
    permiso_hoy = f"permiso-{ahora.date().isoformat()}"

    if 0 < horas <= 24 and "visita-24" not in enviados:
        marcar = ["visita-24"]
        if falta_permiso:
            marcar.append(permiso_hoy)
        return Aviso("visita-24", tuple(marcar))

    if 24 < horas <= 78 and "visita-72" not in enviados:
        marcar = ["visita-72"]
        if falta_permiso:
            marcar.append(permiso_hoy)
        return Aviso("visita-72", tuple(marcar))

    if (
        falta_permiso
        and reserva.get("estado") == "pendiente_permiso"
        and ahora - creado >= timedelta(hours=4)
        and permiso_hoy not in enviados
    ):
        return Aviso("permiso", (permiso_hoy,))
    return None


async def revisar(context) -> None:
    try:
        await _revisar(context)
    except Exception:
        logger.exception("No pude revisar los recordatorios")


async def _revisar(context) -> None:
    ahora = datetime.now(config.ZONA)
    if ahora.hour < 8 or ahora.hour >= 19:
        return
    desde = (ahora.date() - timedelta(days=1)).isoformat()
    for reserva in db.reservas_vigentes(desde):
        enviados = db.tipos_enviados(reserva["id"])
        aviso = plan_recordatorios(reserva, ahora, enviados)
        if aviso is None:
            continue
        texto = contenido.texto_recordatorio(reserva, aviso.tipo, ahora)
        markup = None
        if not reserva.get("permiso_file_id"):
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            markup = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(
                        "Enviar permiso del MINERD",
                        callback_data=f"per:{reserva['id']}",
                    )
                ]]
            )
        try:
            await context.bot.send_message(
                reserva["chat_id"],
                texto,
                parse_mode="HTML",
                reply_markup=markup,
            )
        except Exception:
            logger.exception("No pude escribir el recordatorio de la reserva %s", reserva["id"])
            continue
        for tipo in aviso.marcar:
            db.marcar_recordatorio(reserva["id"], tipo)
