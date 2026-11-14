"""Asistente de Telegram del Museo Infantil Trampolín.

Uso: copia .env.example a .env, pega el token de @BotFather y ejecuta python bot.py.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import contenido
import database as db
import feriados
import recordatorios
from logica_reservas import (
    calcular_grupos,
    etiqueta_dia,
    opciones_de_reserva,
    parse_fecha,
    primer_entero,
    proximos_dias,
    validar_telefono,
    visita_ya_empezo,
)

logger = logging.getLogger(__name__)

(
    ESCUELA,
    TIPO,
    CONTACTO,
    TELEFONO,
    ALUMNOS,
    GRADO,
    ACOMP,
    FECHA,
    FRANJA,
    NECESIDADES,
    DETALLE,
    CONFIRMAR,
) = range(12)
(T_NOMBRE, T_DESC, T_HORARIO, T_QUIEN, T_INST) = range(12, 17)
FIN = ConversationHandler.END

PRIVADO = filters.ChatType.PRIVATE
TEXTO = PRIVADO & filters.TEXT & ~filters.COMMAND


def teclado_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Preguntar", callback_data="menu:faq")],
            [InlineKeyboardButton("Reservar visita guiada", callback_data="menu:reservar")],
            [InlineKeyboardButton("Mis reservas", callback_data="menu:mis")],
            [InlineKeyboardButton("Talleres disponibles", callback_data="menu:talleres")],
            [InlineKeyboardButton("Enviar permiso MINERD", callback_data="menu:permiso")],
            [InlineKeyboardButton("Horario y contacto", callback_data="menu:contacto")],
        ]
    )


def teclado_tipo() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Escuela pública", callback_data="tipo:publica")],
            [InlineKeyboardButton("Colegio privado", callback_data="tipo:privada")],
        ]
    )


def teclado_dias(dias) -> InlineKeyboardMarkup:
    filas = []
    fila = []
    for dia in dias:
        fila.append(InlineKeyboardButton(etiqueta_dia(dia), callback_data=f"dia:{dia.isoformat()}"))
        if len(fila) == 2:
            filas.append(fila)
            fila = []
    if fila:
        filas.append(fila)
    filas.append([InlineKeyboardButton("Escribir otra fecha", callback_data="dia:otra")])
    return InlineKeyboardMarkup(filas)


def teclado_necesidades(seleccion: set[str]) -> InlineKeyboardMarkup:
    filas = []
    fila = []
    for clave, etiqueta in contenido.NECESIDADES:
        marca = "✓ " if clave in seleccion else ""
        fila.append(InlineKeyboardButton(f"{marca}{etiqueta}", callback_data=f"ne:{clave}"))
        if len(fila) == 2:
            filas.append(fila)
            fila = []
    if fila:
        filas.append(fila)
    filas.append([InlineKeyboardButton("Listo", callback_data="ne:listo")])
    return InlineKeyboardMarkup(filas)


def teclado_confirmar() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Confirmar reserva", callback_data="ok:si")],
            [InlineKeyboardButton("Cancelar", callback_data="ok:no")],
        ]
    )


async def reply(update: Update, texto: str, markup=None) -> None:
    await update.effective_message.reply_text(
        texto,
        parse_mode="HTML",
        reply_markup=markup,
    )


async def enviar_bienvenida(update: Update) -> None:
    await reply(update, contenido.texto_bienvenida(), teclado_menu())


def reserva_de(context: ContextTypes.DEFAULT_TYPE) -> dict:
    reserva = context.user_data.get("reserva")
    if reserva is None:
        reserva = {}
        context.user_data["reserva"] = reserva
    return reserva


def hoy() -> datetime:
    return datetime.now(config.ZONA)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()
    await enviar_bienvenida(update)


async def salir_al_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reserva_en_curso"] = False
    context.user_data["taller_en_curso"] = False
    context.user_data.pop("reserva", None)
    context.user_data["guardando"] = False
    if update.callback_query:
        await update.callback_query.answer()
    await enviar_bienvenida(update)
    return FIN


async def cancelar_flujo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reserva_en_curso"] = False
    context.user_data["taller_en_curso"] = False
    context.user_data.pop("reserva", None)
    context.user_data.pop("taller", None)
    context.user_data["guardando"] = False
    await reply(
        update,
        "Listo, salí del formulario. Lo que no se confirmó no quedó guardado.",
        teclado_menu(),
    )
    return FIN


async def al_vencer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reserva_en_curso"] = False
    context.user_data["taller_en_curso"] = False
    context.user_data.pop("reserva", None)
    context.user_data.pop("taller", None)
    mensaje = update.effective_message
    texto = (mensaje.text or "") if mensaje else ""
    if update.callback_query:
        await update.callback_query.answer("El formulario se venció.", show_alert=True)
        await enviar_bienvenida(update)
        return FIN
    if texto.startswith("/start"):
        await enviar_bienvenida(update)
        return FIN
    if texto and not texto.startswith("/"):
        return FIN
    if mensaje:
        await reply(update, "El formulario se venció. Escribe /start para volver al menú.")
    return FIN


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    opcion = update.callback_query.data.split(":")[1]
    if opcion == "inicio":
        await enviar_bienvenida(update)
    elif opcion == "faq":
        await reply(
            update,
            "Pregúntame lo que quieras del museo: horarios, precios, salas, grupos, "
            "el permiso del MINERD o los talleres.",
        )
    elif opcion == "talleres":
        await enviar_talleres(update, context)
    elif opcion == "mis":
        await enviar_reservas(update, context)
    elif opcion == "contacto":
        await reply(update, contenido.texto_contacto(), teclado_menu())
    elif opcion == "permiso":
        await pedir_permiso(update, context)


async def responder_pregunta(update: Update, texto: str) -> None:
    tipo, items = contenido.buscar(texto)
    if tipo == "saludo":
        await enviar_bienvenida(update)
        return
    if tipo == "reservar":
        await reply(
            update,
            "Para apartar una visita guiada pulsa el botón. "
            "Cada franja dura 2 horas y 200 alumnos forman 8 grupos.",
            InlineKeyboardMarkup(
                [[InlineKeyboardButton("Reservar visita guiada", callback_data="menu:reservar")]]
            ),
        )
        return
    if tipo == "nada" or not items:
        await reply(update, contenido.texto_sin_respuesta(), teclado_menu())
        return
    if tipo == "varias":
        botones = [
            [InlineKeyboardButton(item["titulo"], callback_data=f"faq:{item['id']}")]
            for item in items
        ]
        await reply(update, "Encontré varios temas. Elige uno:", InlineKeyboardMarkup(botones))
        return
    faq_id = items[0]["id"]
    await reply(update, contenido.texto_faq(faq_id), teclado_tras_faq(faq_id))


def teclado_tras_faq(faq_id: str) -> InlineKeyboardMarkup:
    fila = [InlineKeyboardButton("Menú", callback_data="menu:inicio")]
    if faq_id in {"grupos", "permiso", "horario", "precio", "recorrido"}:
        fila.insert(0, InlineKeyboardButton("Reservar visita", callback_data="menu:reservar"))
    return InlineKeyboardMarkup([fila])


async def texto_libre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("reserva_en_curso") or context.user_data.get("taller_en_curso"):
        return
    await responder_pregunta(update, update.message.text)


async def cb_faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    faq_id = update.callback_query.data.split(":", 1)[1]
    await reply(update, contenido.texto_faq(faq_id), teclado_tras_faq(faq_id))


async def enviar_talleres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    talleres = db.listar_talleres()
    if not talleres:
        await reply(
            update,
            "Ahora mismo no hay talleres publicados. "
            f"Escribe a {config.EMAIL} o llama al {config.TELEFONO}.",
            teclado_menu(),
        )
        return
    await reply(
        update,
        "<b>Talleres disponibles</b>\n"
        "Cada ficha dice de qué trata, el horario, quién lo imparte y la institución. "
        "Puedes reenviarla a tu centro.",
    )
    for indice, taller in enumerate(talleres):
        markup = teclado_menu() if indice == len(talleres) - 1 else None
        await reply(update, contenido.ficha_taller(taller), markup)


async def enviar_reservas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    desde = (hoy().date() - timedelta(days=30)).isoformat()
    reservas = db.reservas_de_usuario(update.effective_user.id, desde)
    if not reservas:
        await reply(update, "No tienes reservas en los últimos 30 días.", teclado_menu())
        return
    ahora = hoy()
    for reserva in reservas:
        fila = []
        empezo = visita_ya_empezo(reserva["fecha"], reserva["hora_inicio"], ahora)
        if reserva["estado"] != "cancelada" and not empezo:
            fila.append(InlineKeyboardButton("Anular", callback_data=f"can:{reserva['id']}"))
        if reserva["estado"] == "pendiente_permiso":
            fila.append(
                InlineKeyboardButton("Enviar permiso", callback_data=f"per:{reserva['id']}")
            )
        markup = InlineKeyboardMarkup([fila]) if fila else None
        await reply(update, contenido.texto_reserva_completa(reserva), markup)


async def pedir_permiso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("reserva_en_curso"):
        await reply(update, "Termina la reserva primero. Al final te pido el permiso.")
        return
    pendientes = db.pendientes_permiso(update.effective_user.id, hoy().date().isoformat())
    if not pendientes:
        await reply(
            update,
            "No tienes reservas esperando el permiso del MINERD. "
            "Si quieres una visita, usa Reservar.",
            teclado_menu(),
        )
        return
    if len(pendientes) == 1:
        await marcar_espera_permiso(context, pendientes[0]["id"])
        await reply(update, contenido.texto_pide_permiso(pendientes[0]))
        return
    botones = [
        [
            InlineKeyboardButton(
                f"#{reserva['id']} · {reserva['fecha']} · {reserva['escuela'][:28]}",
                callback_data=f"per:{reserva['id']}",
            )
        ]
        for reserva in pendientes
    ]
    await reply(update, "Elige la reserva y luego envía la foto o el PDF.", InlineKeyboardMarkup(botones))


async def marcar_espera_permiso(context: ContextTypes.DEFAULT_TYPE, reserva_id: int) -> None:
    context.user_data["permiso_reserva_id"] = reserva_id
    context.user_data["permiso_hasta"] = time.time() + 3600


def permiso_vigente(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    hasta = context.user_data.get("permiso_hasta")
    if not hasta or time.time() > float(hasta):
        context.user_data.pop("permiso_reserva_id", None)
        context.user_data.pop("permiso_hasta", None)
        return None
    return context.user_data.get("permiso_reserva_id")


async def elegir_permiso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    reserva_id = int(update.callback_query.data.split(":")[1])
    reserva = db.obtener_reserva(reserva_id, update.effective_user.id)
    if not reserva or reserva["estado"] == "cancelada":
        await reply(update, "No encontré esa reserva.")
        return
    await marcar_espera_permiso(context, reserva_id)
    await reply(update, contenido.texto_pide_permiso(reserva))


async def preguntar_anular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    reserva_id = int(update.callback_query.data.split(":")[1])
    await reply(
        update,
        f"¿Anulo la reserva #{reserva_id}? El cupo queda libre.",
        InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Sí, anular", callback_data=f"canok:{reserva_id}")],
                [InlineKeyboardButton("No", callback_data=f"cann:{reserva_id}")],
            ]
        ),
    )


async def confirmar_anular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    reserva_id = int(update.callback_query.data.split(":")[1])
    resultado = db.cancelar_reserva(reserva_id, update.effective_user.id, forzar=False)
    textos = {
        "ok": f"Anulé la reserva #{reserva_id}. El cupo quedó libre.",
        "ya": "Esa reserva ya estaba anulada.",
        "pasada": f"Esa visita ya empezó. Si necesitas un cambio, llama al {config.TELEFONO}.",
        "ajena": "Esa reserva no es tuya.",
        "no": "No encontré esa reserva.",
    }
    await reply(update, textos.get(resultado, "No pude anularla."), teclado_menu())


async def no_anular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await reply(update, "La reserva sigue vigente.")


def nombre_seguro(nombre: str, reserva_id: int) -> str:
    base = Path(nombre).name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:80]
    if not base or base.startswith("."):
        base = f"permiso_{reserva_id}"
    return f"reserva_{reserva_id}_{base}"


async def recibir_permiso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("reserva_en_curso"):
        await reply(update, "Termina o cancela la reserva. El permiso se envía al final.")
        return
    if context.user_data.get("taller_en_curso"):
        await reply(update, "Primero terminemos la ficha del taller. /cancelar para salir.")
        return

    mensaje = update.message
    if mensaje.photo:
        file_id = mensaje.photo[-1].file_id
        nombre = f"permiso_{int(time.time())}.jpg"
    elif mensaje.document:
        documento = mensaje.document
        mime = documento.mime_type or ""
        archivo_nombre = (documento.file_name or "").lower()
        permitido = mime in {
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/webp",
        } or archivo_nombre.endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp"))
        if not permitido:
            await reply(update, "Envíame el permiso en PDF o en una foto.")
            return
        file_id = documento.file_id
        nombre = documento.file_name or f"permiso_{int(time.time())}"
    else:
        return

    usuario = update.effective_user
    reserva_id = permiso_vigente(context)
    if not reserva_id:
        pendientes = db.pendientes_permiso(usuario.id, hoy().date().isoformat())
        if pendientes:
            await reply(
                update,
                "Para adjuntar el permiso, escribe /permiso o pulsa Enviar permiso y después manda la foto o el PDF.",
            )
        else:
            await reply(
                update,
                "No tengo una reserva tuya esperando el permiso. Revisa /misreservas o crea una con /reservar.",
            )
        return
    reserva = db.obtener_reserva(reserva_id, usuario.id)
    if not reserva or reserva["estado"] == "cancelada":
        await reply(update, "Esa reserva ya no está activa. Revisa /misreservas.")
        return

    ya_tenia = bool(reserva.get("permiso_file_id"))
    config.PERMISOS_DIR.mkdir(parents=True, exist_ok=True)
    destino = config.PERMISOS_DIR / nombre_seguro(nombre, reserva["id"])
    ruta = ""
    try:
        archivo = await context.bot.get_file(file_id)
        try:
            await archivo.download_to_drive(custom_path=str(destino))
            ruta = str(destino)
        except Exception:
            logger.exception("No pude guardar el permiso en disco")
    except Exception:
        logger.exception("No pude descargar el permiso")
        await reply(update, "No pude leer ese archivo. Envíalo otra vez, en foto o PDF.")
        return

    if not db.guardar_permiso(reserva["id"], usuario.id, file_id, nombre, ruta):
        await reply(update, "Esa reserva ya no se puede actualizar.")
        return

    await marcar_espera_permiso(context, reserva["id"])
    if ya_tenia:
        texto = f"Reemplacé el permiso de la reserva #{reserva['id']}."
    else:
        texto = (
            f"Permiso recibido. La reserva #{reserva['id']} quedó confirmada. "
            "Si la imagen no se ve bien, envía otra y la reemplazo."
        )
    await reply(update, texto, teclado_menu())
    await avisar_permiso(context, reserva, mensaje)


async def avisar_equipo(bot, texto: str) -> None:
    if not config.STAFF_CHAT_ID:
        return
    try:
        await bot.send_message(config.STAFF_CHAT_ID, texto, parse_mode="HTML")
    except Exception:
        logger.exception("No pude avisar al chat del museo")


async def avisar_permiso(context, reserva: dict, mensaje) -> None:
    if not config.STAFF_CHAT_ID:
        return
    caption = f"Permiso MINERD · reserva #{reserva['id']} · {reserva['escuela']}"[:1000]
    try:
        await context.bot.copy_message(
            chat_id=config.STAFF_CHAT_ID,
            from_chat_id=mensaje.chat_id,
            message_id=mensaje.message_id,
            caption=caption,
        )
    except Exception:
        logger.exception("No pude reenviar el permiso al equipo")


async def reservar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reserva_en_curso"] = True
    context.user_data["reserva"] = {}
    context.user_data["guardando"] = False
    context.user_data.pop("opciones", None)
    if update.callback_query:
        await update.callback_query.answer()
    await reply(
        update,
        "<b>Reserva de visita guiada</b>\n"
        "Cada franja dura como máximo 2 horas. "
        "Los alumnos se dividen en grupos de 25. "
        "200 alumnos = 8 grupos.\n\n"
        "¿Cómo se llama el centro educativo?\n"
        "Si quieres salir, escribe /cancelar.",
    )
    return ESCUELA


async def paso_escuela(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = " ".join(update.message.text.split())
    if len(nombre) < 3 or len(nombre) > 120:
        await reply(update, "Escribe el nombre del centro, entre 3 y 120 caracteres.")
        return ESCUELA
    reserva_de(context)["escuela"] = nombre
    await reply(
        update,
        f"Centro: <b>{escape(nombre)}</b>\n¿Es escuela pública o colegio privado?",
        teclado_tipo(),
    )
    return TIPO


async def paso_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    tipo = update.callback_query.data.split(":")[1]
    reserva_de(context)["tipo_centro"] = tipo
    etiqueta = "escuela pública" if tipo == "publica" else "colegio privado"
    await reply(update, f"Anoté: {etiqueta}.\n¿Nombre y apellido de la persona responsable?")
    return CONTACTO


async def texto_en_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await reply(update, "Elige con los botones si es escuela pública o colegio privado.", teclado_tipo())
    return TIPO


async def paso_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = " ".join(update.message.text.split())
    if len(nombre) < 3 or len(nombre) > 80:
        await reply(update, "Escribe el nombre del responsable, entre 3 y 80 caracteres.")
        return CONTACTO
    reserva_de(context)["contacto"] = nombre
    await reply(
        update,
        "¿Teléfono? Usa un número 809, 829 o 849. Ejemplo: 809-555-1234.",
    )
    return TELEFONO


async def paso_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telefono = validar_telefono(update.message.text)
    if not telefono:
        await reply(update, "No reconocí el teléfono. Ejemplo: 809-555-1234.")
        return TELEFONO
    reserva_de(context)["telefono"] = telefono
    await reply(update, "¿Cuántos alumnos vienen? Escribe el número. Ejemplo: 200.")
    return ALUMNOS


async def paso_alumnos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    numero = primer_entero(update.message.text or "")
    if numero is None or numero < 1:
        await reply(update, "Escribe la cantidad de alumnos. Ejemplo: 200.")
        return ALUMNOS
    if numero > config.MAX_ALUMNOS:
        await reply(
            update,
            f"Por este chat se reservan hasta {config.MAX_ALUMNOS} alumnos. "
            f"Para un grupo mayor llama al {config.TELEFONO}.",
        )
        return ALUMNOS
    reserva = reserva_de(context)
    reserva["alumnos"] = numero
    reserva["modelo"] = calcular_grupos(numero)
    await reply(
        update,
        contenido.texto_calculo(numero) + "\n\n¿Qué grado o nivel viene? Por ejemplo: 4to de primaria.",
    )
    return GRADO


async def paso_grado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    grado = " ".join(update.message.text.split())
    if len(grado) < 2 or len(grado) > 80:
        await reply(update, "Escribe el grado o el nivel. Por ejemplo: 3ro de secundaria.")
        return GRADO
    reserva_de(context)["grado"] = grado
    await reply(
        update,
        "¿Cuántos docentes o adultos acompañan? Los alumnos ocupan el cupo de los grupos; "
        "los adultos no. Escribe un número, aunque sea 0.",
    )
    return ACOMP


async def paso_acomp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    numero = primer_entero(update.message.text or "")
    if numero is None or not 0 <= numero <= 100:
        await reply(update, "Escribe cuántos adultos acompañan, de 0 a 100.")
        return ACOMP
    reserva_de(context)["acompanantes"] = numero
    return await pedir_fecha(update, context)


async def pedir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reserva = reserva_de(context)
    cantidad = len(reserva.get("modelo") or [])
    dias = proximos_dias(hoy().date(), 8, feriados.listar())
    texto = "franja" if cantidad == 1 else "franjas"
    await reply(
        update,
        f"Esta visita necesita {cantidad} {texto} de 2 horas.\n"
        "Elige el día o escribe la fecha como DD/MM/AAAA.",
        teclado_dias(dias),
    )
    return FECHA


async def ofrecer_franjas(update: Update, context: ContextTypes.DEFAULT_TYPE, fecha) -> int:
    reserva = reserva_de(context)
    ahora = hoy()
    if fecha < ahora.date() or fecha > ahora.date() + timedelta(days=365):
        await reply(update, "Elige una fecha entre hoy y los próximos 12 meses.")
        return FECHA
    if fecha.isoformat() in feriados.listar() or fecha.weekday() == 0:
        await reply(
            update,
            "Ese día no hay visitas guiadas: el museo cierra los lunes y los feriados cargados.",
        )
        return FECHA
    opciones = opciones_de_reserva(
        fecha,
        reserva["modelo"],
        db.ocupacion(fecha.isoformat()),
        ahora,
        feriados.listar(),
    )
    if not opciones:
        await reply(
            update,
            "Ese día no quedan franjas con cupo para este grupo. Elige otra fecha.",
        )
        return FECHA
    reserva["fecha"] = fecha.isoformat()
    context.user_data["opciones"] = opciones
    botones = [
        [InlineKeyboardButton(contenido.etiqueta_opcion(plan), callback_data=f"fr:{indice}")]
        for indice, plan in enumerate(opciones)
    ]
    botones.append([InlineKeyboardButton("Otra fecha", callback_data="dia:otra")])
    await reply(
        update,
        "Elige la hora de entrada. Cada franja dura 2 horas.",
        InlineKeyboardMarkup(botones),
    )
    return FRANJA


async def paso_fecha_boton(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    valor = update.callback_query.data.split(":", 1)[1]
    if valor == "otra":
        await reply(update, "Escribe la fecha como DD/MM/AAAA. Ejemplo: 20/11/2026.")
        return FECHA
    return await ofrecer_franjas(update, context, datetime.strptime(valor, "%Y-%m-%d").date())


async def paso_fecha_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    fecha = parse_fecha(update.message.text or "")
    if not fecha:
        await reply(update, "No entendí la fecha. Usa DD/MM/AAAA, por ejemplo 20/11/2026.")
        return FECHA
    return await ofrecer_franjas(update, context, fecha)


async def volver_a_fechas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await pedir_fecha(update, context)


async def paso_franja(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    indice = int(update.callback_query.data.split(":")[1])
    opciones = context.user_data.get("opciones") or []
    if indice >= len(opciones):
        await reply(update, "Esa opción ya no está. Elige la fecha otra vez.")
        return await pedir_fecha(update, context)
    reserva_de(context)["plan"] = opciones[indice]
    return await pedir_necesidades(update, context)


async def texto_en_franja(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await reply(update, "Elige una franja con los botones. Si quieres otro día, pulsa Otra fecha.")
    return FRANJA


async def pedir_necesidades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reserva = reserva_de(context)
    reserva["necesidades_sel"] = set()
    await reply(
        update,
        "¿El grupo tiene necesidades especiales? Marca todas las que apliquen y pulsa Listo. "
        "Esto queda guardado en la reserva.",
        teclado_necesidades(set()),
    )
    return NECESIDADES


async def paso_necesidad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    clave = query.data.split(":", 1)[1]
    reserva = reserva_de(context)
    seleccion = set(reserva.get("necesidades_sel") or set())
    if clave == "listo":
        if not seleccion:
            await query.answer("Elige al menos una opción.", show_alert=True)
            return NECESIDADES
        await query.answer()
        reserva["necesidades_sel"] = seleccion
        if seleccion == {"ninguna"}:
            reserva["detalle"] = ""
            return await ir_a_confirmar(update, context)
        await reply(
            update,
            "Describe las necesidades: cuántos estudiantes, qué apoyo requieren y, si lo sabes, en qué grupo van.",
            InlineKeyboardMarkup(
                [[InlineKeyboardButton("Sin más detalles", callback_data="det:no")]]
            ),
        )
        return DETALLE
    if clave not in contenido.ETIQUETAS:
        await query.answer()
        return NECESIDADES
    await query.answer()
    if clave == "ninguna":
        seleccion = set() if "ninguna" in seleccion else {"ninguna"}
    else:
        seleccion.discard("ninguna")
        if clave in seleccion:
            seleccion.remove(clave)
        else:
            seleccion.add(clave)
    reserva["necesidades_sel"] = seleccion
    try:
        await query.edit_message_reply_markup(reply_markup=teclado_necesidades(seleccion))
    except Exception:
        logger.exception("No pude actualizar los botones de necesidades")
    return NECESIDADES


async def texto_en_necesidades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await reply(update, "Usa los botones para marcar y luego pulsa Listo.")
    return NECESIDADES


async def paso_detalle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    detalle = " ".join(update.message.text.split())
    if len(detalle) < 3:
        await reply(update, "Cuéntame un poco más, aunque sea una frase corta.")
        return DETALLE
    if len(detalle) > 500:
        await reply(update, "Resúmelo en menos de 500 caracteres.")
        return DETALLE
    reserva_de(context)["detalle"] = detalle
    return await ir_a_confirmar(update, context)


async def paso_detalle_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    reserva_de(context)["detalle"] = ""
    return await ir_a_confirmar(update, context)


async def ir_a_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await reply(
        update,
        contenido.resumen_reserva(reserva_de(context), titulo="Revisa la reserva"),
        teclado_confirmar(),
    )
    return CONFIRMAR


async def texto_en_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await reply(update, "Pulsa Confirmar reserva o Cancelar.", teclado_confirmar())
    return CONFIRMAR


def armar_datos(update: Update, reserva: dict) -> dict:
    claves = contenido.ordenar_necesidades(set(reserva.get("necesidades_sel") or {"ninguna"}))
    return {
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id,
        "escuela": reserva["escuela"],
        "tipo_centro": reserva["tipo_centro"],
        "contacto": reserva["contacto"],
        "telefono": reserva["telefono"],
        "fecha": reserva["fecha"],
        "alumnos": reserva["alumnos"],
        "grado": reserva["grado"],
        "acompanantes": reserva["acompanantes"],
        "necesidades": ",".join(claves) if claves else "ninguna",
        "detalle_necesidades": reserva.get("detalle") or "",
        "plan": reserva["plan"],
    }


async def paso_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query.data.endswith(":no"):
        await query.answer()
        context.user_data["reserva_en_curso"] = False
        context.user_data.pop("reserva", None)
        context.user_data["guardando"] = False
        await reply(update, "Reserva cancelada. No guardé nada.", teclado_menu())
        return FIN
    if context.user_data.get("guardando"):
        await query.answer("Ya la estoy guardando.")
        return CONFIRMAR
    reserva = context.user_data.get("reserva") or {}
    if "plan" not in reserva:
        await query.answer()
        context.user_data["reserva_en_curso"] = False
        await reply(update, "Se perdió el formulario. Empieza de nuevo con /reservar.")
        return FIN
    context.user_data["guardando"] = True
    await query.answer()
    try:
        reserva_id = db.crear_reserva(armar_datos(update, reserva))
    except db.CupoAgotado:
        context.user_data["guardando"] = False
        await reply(update, "Esa franja se acaba de llenar. Elige otro día.")
        return await pedir_fecha(update, context)
    except Exception:
        context.user_data["guardando"] = False
        logger.exception("No pude guardar la reserva")
        await reply(update, "No pude guardar la reserva. Inténtalo otra vez en un momento.")
        return CONFIRMAR

    context.user_data["guardando"] = False
    context.user_data["reserva_en_curso"] = False
    context.user_data.pop("reserva", None)
    await marcar_espera_permiso(context, reserva_id)
    guardada = db.obtener_reserva(reserva_id)
    await reply(update, contenido.texto_creada(guardada))
    quien = update.effective_user
    mencion = f"@{quien.username}" if quien.username else f"id {quien.id}"
    await avisar_equipo(
        context.bot,
        contenido.resumen_reserva(guardada, titulo=f"Nueva reserva #{reserva_id}")
        + f"\nTelegram: {escape(mencion)}",
    )
    logger.info("Reserva %s creada", reserva_id)
    return FIN


async def taller_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not config.es_admin(update.effective_user.id):
        await reply(update, "Ese comando es del equipo del museo.")
        return FIN
    context.user_data["taller_en_curso"] = True
    context.user_data["taller"] = {}
    await reply(
        update,
        "<b>Nueva ficha de taller</b>\n¿Cómo se llama?\n/cancelar para salir.",
    )
    return T_NOMBRE


async def _guardar_campo(update, context, campo, minimo, estado, siguiente) -> int:
    valor = " ".join(update.message.text.split())
    if len(valor) < minimo or len(valor) > 400:
        await reply(update, f"Escríbelo con al menos {minimo} caracteres.")
        return estado
    context.user_data["taller"][campo] = valor
    await reply(update, siguiente)
    return {
        "nombre": T_DESC,
        "descripcion": T_HORARIO,
        "horario": T_QUIEN,
        "facilitador": T_INST,
    }[campo]


async def taller_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _guardar_campo(
        update,
        context,
        "nombre",
        3,
        T_NOMBRE,
        "¿De qué trata? Escríbelo en una o dos frases.",
    )


async def taller_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _guardar_campo(
        update,
        context,
        "descripcion",
        10,
        T_DESC,
        "¿Cuál es el horario? Ejemplo: Martes y jueves, 10:00 a.m. a 11:30 a.m.",
    )


async def taller_horario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _guardar_campo(
        update,
        context,
        "horario",
        3,
        T_HORARIO,
        "¿Quién lo imparte?",
    )


async def taller_quien(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _guardar_campo(
        update,
        context,
        "facilitador",
        3,
        T_QUIEN,
        "¿De qué institución viene quien lo imparte?",
    )


async def taller_inst(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    valor = " ".join(update.message.text.split())
    if len(valor) < 3 or len(valor) > 400:
        await reply(update, "Escribe la institución, con al menos 3 caracteres.")
        return T_INST
    ficha = context.user_data.get("taller") or {}
    ficha["institucion"] = valor
    taller_id = db.crear_taller(
        ficha["nombre"],
        ficha["descripcion"],
        ficha["horario"],
        ficha["facilitador"],
        ficha["institucion"],
    )
    context.user_data["taller_en_curso"] = False
    context.user_data.pop("taller", None)
    guardado = next(item for item in db.listar_talleres(False) if item["id"] == taller_id)
    await reply(update, f"Taller #{taller_id} publicado.\n\n" + contenido.ficha_taller(guardado))
    return FIN


async def cmd_miid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply(update, f"Tu ID de Telegram es <code>{update.effective_user.id}</code>.")


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    usuario = update.effective_user
    if not config.es_admin(usuario.id):
        await reply(
            update,
            f"Tu ID es <code>{usuario.id}</code>. "
            "Para entrar al equipo, agrégalo en ADMIN_IDS dentro del archivo .env y reinicia el bot.",
        )
        return
    talleres = db.listar_talleres(solo_activos=False)
    lineas = [
        "<b>Comandos del equipo</b>",
        "/nuevo_taller — publica una ficha",
        "/quitar_taller 2 — oculta una ficha",
        "/agenda — reservas de los próximos 14 días",
        "/anular 12 — anula cualquier reserva",
        "/feriado 03/04/2026 — cierra ese día",
        "/feriados — lista los feriados",
        "/quitar_feriado 2026-04-03",
        "",
        "<b>Talleres</b>",
    ]
    if not talleres:
        lineas.append("No hay fichas.")
    for taller in talleres:
        estado = "activo" if taller["activo"] else "oculto"
        lineas.append(f"#{taller['id']} {escape(taller['nombre'])} · {estado}")
    await reply(update, "\n".join(lineas))


async def cmd_quitar_taller(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.es_admin(update.effective_user.id):
        await reply(update, "Ese comando es del equipo del museo.")
        return
    if not context.args or not context.args[0].isdigit():
        await reply(update, "Uso: /quitar_taller 2")
        return
    if db.desactivar_taller(int(context.args[0])):
        await reply(update, f"Oculté el taller #{context.args[0]}.")
    else:
        await reply(update, "No encontré un taller activo con ese número.")


async def cmd_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.es_admin(update.effective_user.id):
        await reply(update, "Ese comando es del equipo del museo.")
        return
    inicio = hoy().date()
    fin = inicio + timedelta(days=14)
    reservas = db.reservas_entre(inicio.isoformat(), fin.isoformat())
    if not reservas:
        await reply(update, "No hay reservas en los próximos 14 días.")
        return
    from logica_reservas import hora_bonita

    lineas = ["<b>Agenda de los próximos 14 días</b>"]
    for reserva in reservas:
        lineas.append(
            f"#{reserva['id']} · {reserva['fecha']} {hora_bonita(reserva['hora_inicio'])} · "
            f"{escape(reserva['escuela'])} · {reserva['alumnos']} alumnos · "
            f"{reserva['grupos']} grupos · {contenido.ESTADOS.get(reserva['estado'], reserva['estado'])}"
        )
        if reserva.get("necesidades") and reserva["necesidades"] != "ninguna":
            lineas.append(f"Necesidades: {escape(reserva['necesidades'])}")
            if reserva.get("detalle_necesidades"):
                lineas.append(escape(reserva["detalle_necesidades"]))
    await enviar_por_bloques(update, "\n".join(lineas))


async def enviar_por_bloques(update: Update, texto: str) -> None:
    bloque: list[str] = []
    largo = 0
    for linea in texto.split("\n"):
        if largo + len(linea) > 3500 and bloque:
            await reply(update, "\n".join(bloque))
            bloque = [linea]
            largo = len(linea)
        else:
            bloque.append(linea)
            largo += len(linea) + 1
    if bloque:
        await reply(update, "\n".join(bloque))


async def cmd_anular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.es_admin(update.effective_user.id):
        await reply(update, "Ese comando es del equipo del museo.")
        return
    if not context.args or not context.args[0].isdigit():
        await reply(update, "Uso: /anular 12")
        return
    reserva_id = int(context.args[0])
    reserva = db.obtener_reserva(reserva_id)
    resultado = db.cancelar_reserva(reserva_id, update.effective_user.id, forzar=True)
    if resultado == "ok" and reserva and reserva["chat_id"] != update.effective_chat.id:
        try:
            await context.bot.send_message(
                reserva["chat_id"],
                f"El museo anuló la reserva #{reserva_id}. Si fue un error, escribe a {config.EMAIL}.",
            )
        except Exception:
            logger.exception("No pude avisar la anulación al docente")
    textos = {
        "ok": f"Anulé la reserva #{reserva_id}.",
        "ya": "Ya estaba anulada.",
        "no": "No encontré esa reserva.",
    }
    await reply(update, textos.get(resultado, "No pude anularla."))


async def cmd_feriado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.es_admin(update.effective_user.id):
        await reply(update, "Ese comando es del equipo del museo.")
        return
    if not context.args:
        await reply(update, "Uso: /feriado 03/04/2026")
        return
    fecha = parse_fecha(" ".join(context.args))
    if not fecha:
        await reply(update, "No entendí la fecha. Ejemplo: /feriado 03/04/2026")
        return
    feriados.agregar(fecha.isoformat())
    await reply(update, f"Cerré las reservas del {fecha.isoformat()}. Los lunes ya estaban cerrados.")


async def cmd_feriados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.es_admin(update.effective_user.id):
        await reply(update, "Ese comando es del equipo del museo.")
        return
    fechas = sorted(feriados.listar())
    if not fechas:
        await reply(
            update,
            "No hay feriados cargados. Los lunes ya están cerrados.\n"
            "Agrega uno con /feriado 03/04/2026.",
        )
        return
    await reply(update, "<b>Días cerrados</b>\n" + "\n".join(fechas))


async def cmd_quitar_feriado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.es_admin(update.effective_user.id):
        await reply(update, "Ese comando es del equipo del museo.")
        return
    if not context.args:
        await reply(update, "Uso: /quitar_feriado 2026-04-03")
        return
    fecha = parse_fecha(" ".join(context.args))
    if not fecha:
        await reply(update, "No entendí la fecha.")
        return
    if feriados.quitar(fecha.isoformat()):
        await reply(update, f"Quité el cierre del {fecha.isoformat()}.")
    else:
        await reply(update, "Ese día no estaba en la lista.")


async def boton_vencido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer(
        "Ese botón ya no está activo. Escribe /start.",
        show_alert=True,
    )


async def al_fallar(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Error procesando un mensaje", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Ocurrió un error. Inténtalo otra vez o escribe /start."
            )
        except Exception:
            logger.exception("No pude avisar el error")


def conversacion_reserva() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("reservar", reservar_inicio, filters=PRIVADO),
            CallbackQueryHandler(reservar_inicio, pattern=r"^menu:reservar$"),
        ],
        states={
            ESCUELA: [MessageHandler(TEXTO, paso_escuela)],
            TIPO: [
                CallbackQueryHandler(paso_tipo, pattern=r"^tipo:(publica|privada)$"),
                MessageHandler(TEXTO, texto_en_tipo),
            ],
            CONTACTO: [MessageHandler(TEXTO, paso_contacto)],
            TELEFONO: [MessageHandler(TEXTO, paso_telefono)],
            ALUMNOS: [MessageHandler(TEXTO, paso_alumnos)],
            GRADO: [MessageHandler(TEXTO, paso_grado)],
            ACOMP: [MessageHandler(TEXTO, paso_acomp)],
            FECHA: [
                CallbackQueryHandler(paso_fecha_boton, pattern=r"^dia:"),
                MessageHandler(TEXTO, paso_fecha_texto),
            ],
            FRANJA: [
                CallbackQueryHandler(paso_franja, pattern=r"^fr:\d+$"),
                CallbackQueryHandler(volver_a_fechas, pattern=r"^dia:otra$"),
                MessageHandler(TEXTO, texto_en_franja),
            ],
            NECESIDADES: [
                CallbackQueryHandler(paso_necesidad, pattern=r"^ne:"),
                MessageHandler(TEXTO, texto_en_necesidades),
            ],
            DETALLE: [
                CallbackQueryHandler(paso_detalle_no, pattern=r"^det:no$"),
                MessageHandler(TEXTO, paso_detalle),
            ],
            CONFIRMAR: [
                CallbackQueryHandler(paso_confirmar, pattern=r"^ok:(si|no)$"),
                MessageHandler(TEXTO, texto_en_confirmar),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, al_vencer),
                CallbackQueryHandler(al_vencer),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar_flujo),
            CommandHandler("start", salir_al_menu),
            CallbackQueryHandler(salir_al_menu, pattern=r"^menu:inicio$"),
        ],
        conversation_timeout=1200,
        per_chat=True,
        per_user=True,
        per_message=False,
        name="reserva",
        allow_reentry=True,
        block=True,
    )


def conversacion_taller() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("nuevo_taller", taller_inicio, filters=PRIVADO)],
        states={
            T_NOMBRE: [MessageHandler(TEXTO, taller_nombre)],
            T_DESC: [MessageHandler(TEXTO, taller_desc)],
            T_HORARIO: [MessageHandler(TEXTO, taller_horario)],
            T_QUIEN: [MessageHandler(TEXTO, taller_quien)],
            T_INST: [MessageHandler(TEXTO, taller_inst)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, al_vencer)],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar_flujo),
            CommandHandler("start", salir_al_menu),
        ],
        conversation_timeout=1200,
        per_chat=True,
        per_user=True,
        per_message=False,
        name="taller",
        allow_reentry=True,
        block=True,
    )


def registrar(aplicacion: Application) -> None:
    aplicacion.add_handler(conversacion_reserva(), group=0)
    aplicacion.add_handler(conversacion_taller(), group=0)
    aplicacion.add_handler(CommandHandler("start", start, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("ayuda", start, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("faq", menu_faq, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("talleres", enviar_talleres, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("misreservas", enviar_reservas, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("permiso", pedir_permiso, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("miid", cmd_miid, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("admin", cmd_admin, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("quitar_taller", cmd_quitar_taller, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("agenda", cmd_agenda, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("anular", cmd_anular, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("feriado", cmd_feriado, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("feriados", cmd_feriados, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("quitar_feriado", cmd_quitar_feriado, filters=PRIVADO), group=0)
    aplicacion.add_handler(CommandHandler("cancelar", cancelar_ocioso, filters=PRIVADO), group=0)
    aplicacion.add_handler(CallbackQueryHandler(menu, pattern=r"^menu:(inicio|faq|talleres|mis|contacto|permiso)$"), group=0)
    aplicacion.add_handler(CallbackQueryHandler(cb_faq, pattern=r"^faq:"), group=0)
    aplicacion.add_handler(CallbackQueryHandler(elegir_permiso, pattern=r"^per:\d+$"), group=0)
    aplicacion.add_handler(CallbackQueryHandler(preguntar_anular, pattern=r"^can:\d+$"), group=0)
    aplicacion.add_handler(CallbackQueryHandler(confirmar_anular, pattern=r"^canok:\d+$"), group=0)
    aplicacion.add_handler(CallbackQueryHandler(no_anular, pattern=r"^cann:\d+$"), group=0)
    aplicacion.add_handler(CallbackQueryHandler(boton_vencido), group=0)
    aplicacion.add_handler(MessageHandler(TEXTO, texto_libre), group=1)
    aplicacion.add_handler(MessageHandler(PRIVADO & (filters.PHOTO | filters.Document.ALL), recibir_permiso), group=1)
    aplicacion.add_error_handler(al_fallar)


async def menu_faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply(
        update,
        "Pregúntame lo que quieras del museo: horarios, precios, salas, grupos, "
        "el permiso del MINERD o los talleres.",
    )


async def cancelar_ocioso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply(update, "No hay un formulario en curso.", teclado_menu())


async def al_iniciar(aplicacion: Application) -> None:
    await aplicacion.bot.set_my_commands(
        [
            BotCommand("start", "Menú principal"),
            BotCommand("faq", "Preguntar sobre el museo"),
            BotCommand("reservar", "Reservar una visita guiada"),
            BotCommand("misreservas", "Ver mis reservas"),
            BotCommand("talleres", "Ver talleres disponibles"),
            BotCommand("permiso", "Enviar el permiso del MINERD"),
            BotCommand("cancelar", "Salir del formulario"),
            BotCommand("miid", "Ver mi ID de Telegram"),
        ]
    )


def main() -> None:
    import warnings

    from telegram.warnings import PTBUserWarning

    warnings.filterwarnings("ignore", category=PTBUserWarning)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not config.TOKEN or config.TOKEN.startswith("pega_"):
        raise SystemExit(
            "Falta BOT_TOKEN en el archivo .env. Crea el bot con @BotFather y pega el token."
        )
    db.iniciar()
    config.PERMISOS_DIR.mkdir(parents=True, exist_ok=True)
    if not config.FERIADOS_PATH.exists():
        config.FERIADOS_PATH.write_text("[]\n", encoding="utf-8")
    aplicacion = Application.builder().token(config.TOKEN).post_init(al_iniciar).build()
    if aplicacion.job_queue is None:
        raise SystemExit(
            'Instala las tareas programadas: pip install "python-telegram-bot[job-queue]"'
        )
    registrar(aplicacion)
    aplicacion.job_queue.run_repeating(
        recordatorios.revisar,
        interval=1800,
        first=15,
        name="recordatorios",
    )
    logger.info("Asistente del %s listo", config.MUSEO)
    aplicacion.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
