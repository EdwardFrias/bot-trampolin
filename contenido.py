"""Textos del museo y búsqueda del FAQ."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from html import escape

import config
from logica_reservas import (
    calcular_grupos,
    fecha_bonita,
    hora_bonita,
)

NECESIDADES = (
    ("ninguna", "Ninguna"),
    ("movilidad", "Movilidad"),
    ("visual", "Visión"),
    ("auditiva", "Audición"),
    ("tea", "Autismo / sensorial"),
    ("alergia", "Alergias"),
    ("lengua", "Lengua de señas"),
    ("otra", "Otra"),
)

ETIQUETAS = {
    "ninguna": "Ninguna",
    "movilidad": "Movilidad reducida",
    "visual": "Discapacidad visual",
    "auditiva": "Discapacidad auditiva",
    "tea": "Autismo o apoyo sensorial",
    "alergia": "Alergias",
    "lengua": "Lengua de señas",
    "otra": "Otra necesidad",
}

ESTADOS = {
    "pendiente_permiso": "Pendiente del permiso del MINERD",
    "confirmada": "Confirmada",
    "cancelada": "Anulada",
}

STOP = {
    "a", "al", "algo", "con", "de", "del", "el", "en", "es", "esa", "ese", "eso",
    "esta", "este", "la", "las", "lo", "los", "me", "mi", "mis", "o", "para", "por",
    "que", "se", "si", "su", "sus", "un", "una", "y", "ya", "hay", "son", "como",
    "puedo", "puede", "pueden", "quiero", "quisiera", "favor", "sobre", "no",
    "museo", "infantil", "trampolin", "porfa", "tiene", "tienen",
}

SALUDO_TOKENS = {
    "hola", "buenas", "buenos", "dias", "tardes", "noches", "klk", "hey", "saludos",
    "hi", "hello", "buen", "dia", "bro", "bros", "que", "lo", "tal", "klk",
}

FRASES_RESERVAR = (
    "quiero reservar",
    "hacer una reserva",
    "agendar una visita",
    "apartar una visita",
    "como reservo",
)

FAQ = [
    {
        "id": "que_es",
        "titulo": "Qué es el museo",
        "claves": {"historia", "fundacion", "ninos", "familia", "organizacion"},
        "frases": ("que es el museo", "sobre el museo", "que hacen"),
        "respuesta": (
            f"<b>{config.MUSEO}</b>\n"
            "Es una organización sin fines de lucro al servicio de la niñez y la familia "
            "dominicana. La visita es educativa, interactiva y sensorial: el juego sirve "
            "para trabajar valores humanos, sociales y ambientales.\n\n"
            "Está en la Casa Rodrigo de Bastidas, una casa colonial del siglo XVI. "
            "Tiene 9 salas permanentes, salas temporales, dos salones de talleres, "
            "cine-teatro y jardines. El recorrido guiado dura 2 horas."
        ),
    },
    {
        "id": "horario",
        "titulo": "Horarios",
        "claves": {
            "horario", "hora", "horas", "abren", "abre", "abierto", "abierta",
            "cierran", "cierra", "cerrado", "lunes", "sabado", "domingo", "franja", "franjas",
        },
        "frases": ("a que hora", "que horario", "cuando abren", "estan abiertos"),
        "respuesta": "",
    },
    {
        "id": "direccion",
        "titulo": "Dirección",
        "claves": {
            "direccion", "donde", "queda", "quedan", "ubicacion", "ubicado", "damas",
            "colonial", "mapa", "llegar", "bastidas",
        },
        "frases": ("como llego", "donde queda", "donde estan", "cual es la direccion"),
        "respuesta": (
            f"<b>Dónde estamos</b>\n"
            f"{escape(config.DIRECCION)}\n"
            f"<a href=\"{config.MAPA}\">Cómo llegar</a>"
        ),
    },
    {
        "id": "precio",
        "titulo": "Precios",
        "claves": {
            "precio", "precios", "cuesta", "cuanto", "costo", "entrada", "tarifa",
            "pagan", "pesos", "pago", "cobran",
        },
        "frases": ("cuanto cuesta", "precio de la entrada", "cuanto es la entrada"),
        "respuesta": (
            "<b>Entrada de referencia</b>\n"
            f"Escuelas públicas: RD${config.TARIFA_PUBLICA} por estudiante.\n"
            f"Colegios privados y entrada general: RD${config.TARIFA_PRIVADA}.\n\n"
            "Esos montos aparecen en información publicada del museo y pueden cambiar. "
            f"Confírmalos al reservar, por {config.EMAIL} o al {config.TELEFONO}. "
            "Este chat no cobra."
        ),
    },
    {
        "id": "recorrido",
        "titulo": "El recorrido",
        "claves": {"recorrido", "tour", "dura", "duracion", "visita", "guiada", "guiado"},
        "frases": ("cuanto dura", "dura la visita", "recorrido guiado"),
        "respuesta": (
            "<b>Recorrido</b>\n"
            "Cada visita guiada dura 2 horas. Ese es el tiempo máximo de una reserva.\n"
            "El grupo recorre las salas permanentes con un guía. "
            "Si vienen muchos cursos, se dividen para que cada grupo tenga su propio recorrido."
        ),
    },
    {
        "id": "salas",
        "titulo": "Las salas",
        "claves": {"salas", "sala", "exposicion", "exposiciones", "universo", "energia", "ecologia"},
        "frases": ("que salas", "cuales salas", "salas del museo"),
        "respuesta": (
            "<b>Salas permanentes</b>\n"
            "• El Universo\n"
            "• Planeta Tierra\n"
            "• Paleomundo\n"
            "• La Energía\n"
            "• Laberinto de Colores\n"
            "• Ecología\n"
            "• Naturaleza, Relación y Equilibrio\n"
            "• Ser Humano\n"
            "• La Sociedad\n\n"
            "También hay salas temporales, dos salones de talleres y cine-teatro."
        ),
    },
    {
        "id": "grupos",
        "titulo": "Grupos y reservas",
        "claves": {
            "grupo", "grupos", "alumno", "alumnos", "estudiantes", "cupo", "reserva",
            "reservar", "reservo", "colegio", "escuela", "curso", "guia", "guias",
        },
        "frases": (
            "visita guiada",
            "cuantos grupos",
            "200 alumnos",
            "reserva de grupo",
            "grupos escolares",
            "llevar estudiantes",
        ),
        "respuesta": "",
    },
    {
        "id": "permiso",
        "titulo": "Permiso del MINERD",
        "claves": {
            "permiso", "minerd", "autorizacion", "documento", "salida", "ministerio", "pdf",
        },
        "frases": ("permiso del minerd", "autorizacion de salida", "permiso para salir"),
        "respuesta": (
            "<b>Permiso del MINERD</b>\n"
            "El Ministerio de Educación (MINERD) debe autorizar la salida de los estudiantes. "
            "Cuando reservas, el asistente te pide ese permiso en foto o PDF.\n\n"
            "Hasta que no llega, la visita queda pendiente. "
            "El bot te lo recuerda solo, y también te avisa el día anterior a la visita.\n"
            "Puedes enviarlo con /permiso."
        ),
    },
    {
        "id": "necesidades",
        "titulo": "Necesidades especiales",
        "claves": {
            "silla", "ruedas", "discapacidad", "autismo", "tea", "alergia", "alergias",
            "visual", "auditiva", "senas", "accesible", "necesidades", "especiales",
        },
        "frases": ("necesidades especiales", "silla de ruedas", "lengua de senas"),
        "respuesta": (
            "<b>Necesidades especiales</b>\n"
            "Al reservar se pregunta por cada grupo: movilidad, visión, audición, "
            "apoyo sensorial o autismo, alergias, lengua de señas u otra necesidad.\n"
            "Escríbelo con detalle (cuántos estudiantes y qué apoyo necesitan) "
            "para que el equipo lo tenga antes de la visita."
        ),
    },
    {
        "id": "reglamento",
        "titulo": "Reglamento",
        "claves": {
            "reglamento", "normas", "reglas", "prohibido", "armas", "silencio",
            "mochila", "bulto", "fumar", "tocar",
        },
        "frases": ("reglamento del museo", "que no se puede", "normas del museo"),
        "respuesta": (
            "<b>Reglamento</b>\n"
            "• Bultos, abrigos y paraguas se dejan en recepción.\n"
            "• No se entra con alimentos ni bebidas, ni se come en las salas.\n"
            "• No se tocan las obras ni se fuma.\n"
            "• No se usan cámaras, trípodes ni grabadoras.\n"
            "• No entran animales ni armas. Esto incluye a policías y militares fuera de servicio.\n"
            "• Los niños entran acompañados de un adulto.\n"
            "• Hay que respetar el silencio y la distancia con las obras.\n"
            "• Quien se comporte mal puede ser invitado a salir."
        ),
    },
    {
        "id": "alimentos",
        "titulo": "Comida y bebida",
        "claves": {"comida", "alimento", "alimentos", "bebida", "bebidas", "comer", "agua", "snack", "merienda"},
        "frases": ("se puede comer", "entrar con comida", "llevar agua"),
        "respuesta": (
            "<b>Comida y bebida</b>\n"
            "No está permitido entrar con alimentos o bebidas, ni comer dentro de las salas."
        ),
    },
    {
        "id": "fotos",
        "titulo": "Fotos y video",
        "claves": {"foto", "fotos", "camara", "video", "grabar", "filmar", "selfie"},
        "frases": ("puedo tomar fotos", "se pueden tomar fotos", "entrar con camara"),
        "respuesta": (
            "<b>Fotos y video</b>\n"
            "No está permitido usar cámaras de foto o de video, trípodes ni grabadoras dentro del museo."
        ),
    },
    {
        "id": "edad",
        "titulo": "Edades",
        "claves": {"edad", "edades", "anos", "ninos", "primaria", "inicial", "secundaria", "bebes"},
        "frases": ("de que edad", "que edad", "desde que edad", "pueden ir ninos"),
        "respuesta": (
            "<b>A quién va dirigido</b>\n"
            "El museo está pensado para la niñez y la familia. "
            "Los centros educativos pueden reservar con sus docentes a cargo. "
            "Los niños no entran sin un adulto responsable."
        ),
    },
    {
        "id": "talleres",
        "titulo": "Talleres",
        "claves": {
            "taller", "talleres", "pintura", "reciclaje", "artesania", "manualidades",
            "lectura", "titeres", "teatro", "facilitador", "imparte",
        },
        "frases": ("que talleres", "talleres disponibles", "horario de talleres"),
        "respuesta": (
            "<b>Talleres</b>\n"
            "El museo tiene un programa de talleres de pintura, artesanía, reciclaje, "
            "lectura, manualidades y teatro o títeres.\n"
            "Para ver los que están cargados ahora, con horario, tema, quién los imparte "
            "y de qué institución vienen, usa el botón Talleres o escribe /talleres."
        ),
    },
    {
        "id": "contacto",
        "titulo": "Contacto",
        "claves": {"telefono", "tel", "correo", "email", "whatsapp", "contacto", "llamar", "reservaciones"},
        "frases": ("numero de telefono", "como los contacto", "correo del museo"),
        "respuesta": "",
    },
    {
        "id": "cancelacion",
        "titulo": "Cancelar una reserva",
        "claves": {"cancelar", "anular", "cancelacion", "anula", "cambiar", "reprogramar"},
        "frases": ("cancelar la reserva", "anular la visita", "cambiar la fecha"),
        "respuesta": (
            "<b>Cancelar o cambiar</b>\n"
            "Puedes anular una reserva que todavía no empieza desde Mis reservas o con /misreservas. "
            "El cupo queda libre.\n"
            f"Si el cambio es para el mismo día, llama al {config.TELEFONO}."
        ),
    },
]

_POR_ID = {item["id"]: item for item in FAQ}


def normalizar(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    sin_tilde = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tilde).strip()


def buscar(texto: str) -> tuple[str, list[dict]]:
    consulta = normalizar(texto)
    if not consulta:
        return "nada", []
    crudos = re.findall(r"[a-z0-9]+", consulta)
    if crudos and all(token in SALUDO_TOKENS for token in crudos) and len(crudos) <= 6:
        return "saludo", []
    tokens = [token for token in crudos if token not in STOP and len(token) > 1]
    if any(frase in consulta for frase in FRASES_RESERVAR) and not any(
        t in {"alumno", "alumnos", "grupo", "grupos", "cupo", "estudiantes"} for t in tokens
    ):
        return "reservar", []

    puntajes: list[tuple[int, dict]] = []
    for item in FAQ:
        score = 0
        for token in tokens:
            if token in item["claves"]:
                score += 4
        for frase in item["frases"]:
            if frase in consulta:
                score += 6
        if score:
            puntajes.append((score, item))
    if not puntajes:
        return "nada", []
    puntajes.sort(key=lambda par: par[0], reverse=True)
    mejor = puntajes[0][0]
    if mejor < 4:
        return "nada", []
    if len(puntajes) == 1 or mejor >= puntajes[1][0] + 2:
        return "una", [puntajes[0][1]]
    cercanos = [item for score, item in puntajes if score >= mejor - 1][:3]
    return "varias", cercanos


def texto_faq(faq_id: str) -> str:
    if faq_id == "horario":
        return _horario()
    if faq_id == "grupos":
        return _grupos()
    if faq_id == "contacto":
        return texto_contacto()
    item = _POR_ID.get(faq_id)
    if not item:
        return texto_sin_respuesta()
    return item["respuesta"]


def _lineas_franja(pares: tuple[tuple[str, str], ...]) -> str:
    return "\n".join(f"• {hora_bonita(inicio)} – {hora_bonita(fin)}" for inicio, fin in pares)


def _horario() -> str:
    return (
        "<b>Horario del museo</b>\n"
        f"{config.HORARIO_PUBLICO}\n\n"
        "<b>Visitas guiadas de grupos</b>\n"
        "Cada reserva dura 2 horas, para terminar dentro del horario.\n"
        "Martes a viernes:\n"
        f"{_lineas_franja(config.FRANJAS_ENTRE_SEMANA)}\n"
        "Sábados y domingos:\n"
        f"{_lineas_franja(config.FRANJAS_FIN_DE_SEMANA)}\n\n"
        "La última entrada guiada entre semana es a las 12:30 p.m. "
        "y termina a las 2:30 p.m. El museo sigue abierto al público hasta las 4:00 p.m."
    )


def _grupos() -> str:
    muestra = calcular_grupos(200)
    grupos = sum(len(franja) for franja in muestra)
    return (
        "<b>Visitas de grupos</b>\n"
        f"Cada reserva guiada dura como máximo {config.DURACION_HORAS} horas.\n"
        f"Los alumnos se dividen en grupos de hasta {config.ALUMNOS_POR_GRUPO}. "
        f"Ejemplo: 200 alumnos = {grupos} grupos.\n"
        f"En una franja caben hasta {config.GRUPOS_POR_FRANJA} grupos "
        f"({config.GRUPOS_POR_FRANJA * config.ALUMNOS_POR_GRUPO} alumnos) al mismo tiempo.\n"
        "Si el centro trae más de 200, el asistente abre las franjas seguidas que hagan falta. "
        "Cada una sigue siendo de 2 horas.\n\n"
        "Al reservar se piden las necesidades especiales y, al final, el permiso del MINERD."
    )


def texto_contacto() -> str:
    return (
        f"<b>{config.MUSEO}</b>\n"
        f"{escape(config.DIRECCION)}\n"
        f"Teléfonos: {config.TELEFONO} / {config.TELEFONO_2}\n"
        f"Reservas: {config.EMAIL}\n"
        f"Web: {config.WEB}\n"
        f"<a href=\"{config.MAPA}\">Cómo llegar</a>"
    )


def texto_bienvenida() -> str:
    return (
        f"Hola, soy el asistente del <b>{config.MUSEO}</b>. Estoy disponible a cualquier hora.\n\n"
        "Puedo responder preguntas del museo, apartar una visita guiada para un centro educativo, "
        "guardar las necesidades especiales del grupo, pedirte el permiso del MINERD "
        "y mostrarte los talleres que están disponibles."
    )


def texto_saludo() -> str:
    return texto_bienvenida()


def texto_sin_respuesta() -> str:
    return (
        "No tengo esa respuesta en la guía del museo.\n"
        f"Puedes llamar al {config.TELEFONO} o escribir a {config.EMAIL}.\n"
        "Si quieres traer un grupo, usa Reservar."
    )


def texto_calculo(alumnos: int) -> str:
    franjas = calcular_grupos(alumnos)
    total = sum(len(franja) for franja in franjas)
    lineas = [
        f"<b>{alumnos} alumnos = {total} grupos</b> de hasta {config.ALUMNOS_POR_GRUPO}.",
        (
            f"Cada reserva dura {config.DURACION_HORAS} horas y admite hasta "
            f"{config.GRUPOS_POR_FRANJA} grupos "
            f"({config.GRUPOS_POR_FRANJA * config.ALUMNOS_POR_GRUPO} alumnos)."
        ),
    ]
    if len(franjas) == 1:
        lineas.append("Cabe en una sola reserva de 2 horas.")
    else:
        lineas.append(
            f"Hacen falta {len(franjas)} franjas seguidas. Cada una dura 2 horas."
        )
    lineas.append("")
    lineas.append(_describir_sin_hora(franjas))
    return "\n".join(lineas)


def _describir_sin_hora(franjas: list[list[dict]]) -> str:
    lineas = []
    for numero, franja in enumerate(franjas, start=1):
        alumnos = sum(grupo["alumnos"] for grupo in franja)
        lineas.append(f"<b>Franja {numero}</b> · {alumnos} alumnos · {len(franja)} grupos")
        lineas.append(_compactar_grupos(franja))
    return "\n".join(lineas)


def _compactar_grupos(grupos: list[dict]) -> str:
    if len(grupos) == 1:
        grupo = grupos[0]
        return f"Grupo {grupo['letra']}: {grupo['alumnos']} alumnos"
    cantidades = {grupo["alumnos"] for grupo in grupos}
    if len(cantidades) == 1:
        return (
            f"Grupos {grupos[0]['letra']} a {grupos[-1]['letra']}: "
            f"{grupos[0]['alumnos']} alumnos cada uno"
        )
    return ", ".join(f"Grupo {grupo['letra']}: {grupo['alumnos']}" for grupo in grupos)


def ordenar_necesidades(seleccion: set[str]) -> list[str]:
    return [clave for clave, _etiqueta in NECESIDADES if clave in seleccion]


def etiqueta_opcion(plan: list[dict]) -> str:
    inicio = hora_bonita(plan[0]["hora_inicio"])
    fin = hora_bonita(plan[-1]["hora_fin"])
    if len(plan) == 1:
        libres = config.GRUPOS_POR_FRANJA - int(plan[0]["usados"])
        return f"{inicio} – {fin} · {libres} grupos libres"
    return f"{inicio} – {fin} · {len(plan)} franjas"


def bloques_de(datos: dict) -> list[dict]:
    if datos.get("plan"):
        return datos["plan"]
    bloques = []
    for franja in datos.get("franjas") or []:
        grupos = franja.get("grupos_detalle")
        if grupos is None:
            import json

            grupos = json.loads(franja["detalle_grupos"])
        bloques.append(
            {
                "hora_inicio": franja["hora_inicio"],
                "hora_fin": franja["hora_fin"],
                "grupos": grupos,
            }
        )
    return bloques


def _claves_necesidad(datos: dict) -> list[str]:
    if "necesidades_sel" in datos:
        return ordenar_necesidades(set(datos["necesidades_sel"]))
    return [parte for parte in str(datos.get("necesidades") or "").split(",") if parte]


def resumen_reserva(datos: dict, titulo: str) -> str:
    bloques = bloques_de(datos)
    grupos = sum(len(bloque["grupos"]) for bloque in bloques) or int(datos.get("grupos") or 0)
    alumnos = int(datos["alumnos"])
    tipo = "Escuela pública" if datos["tipo_centro"] == "publica" else "Colegio privado"
    tarifa = config.TARIFA_PUBLICA if datos["tipo_centro"] == "publica" else config.TARIFA_PRIVADA
    fecha = fecha_bonita(date.fromisoformat(datos["fecha"]))
    lineas = [
        f"<b>{escape(titulo)}</b>",
        f"{escape(datos['escuela'])} · {tipo}",
        f"Responsable: {escape(datos['contacto'])} · {escape(datos['telefono'])}",
        f"Grado: {escape(datos['grado'])}",
        f"Fecha: {fecha}",
        f"Alumnos: {alumnos} · Grupos: {grupos} · Recorridos guiados: {grupos}",
        f"Adultos que acompañan: {int(datos['acompanantes'])}",
        "",
    ]
    for numero, bloque in enumerate(bloques, start=1):
        subtotal = sum(grupo["alumnos"] for grupo in bloque["grupos"])
        lineas.append(
            f"<b>Franja {numero}</b> · {hora_bonita(bloque['hora_inicio'])} – "
            f"{hora_bonita(bloque['hora_fin'])} · 2 horas · {subtotal} alumnos"
        )
        lineas.append(escape(_compactar_grupos(bloque["grupos"])))
    claves = _claves_necesidad(datos)
    if not claves or claves == ["ninguna"]:
        lineas.append("<b>Necesidades especiales:</b> ninguna indicada")
    else:
        nombres = ", ".join(ETIQUETAS.get(clave, clave) for clave in claves)
        lineas.append(f"<b>Necesidades especiales:</b> {escape(nombres)}")
        detalle = datos.get("detalle") or datos.get("detalle_necesidades") or ""
        if detalle:
            lineas.append(escape(detalle))
    lineas.append(
        f"<b>Entrada de referencia:</b> RD${tarifa} × {alumnos} = RD${_monto(tarifa * alumnos)}."
    )
    lineas.append("Es un dato publicado; confírmalo con el museo. Este chat no cobra.")
    if datos.get("estado"):
        lineas.append(f"<b>Estado:</b> {escape(ESTADOS.get(datos['estado'], datos['estado']))}")
        if datos.get("permiso_file_id"):
            lineas.append("Permiso del MINERD: recibido.")
        elif datos["estado"] == "pendiente_permiso":
            lineas.append("Permiso del MINERD: todavía no llega.")
    else:
        lineas.append("Al confirmar, el siguiente paso es enviar el permiso del MINERD.")
    return "\n".join(lineas)


def texto_creada(reserva: dict) -> str:
    return (
        resumen_reserva(reserva, titulo=f"Reserva #{reserva['id']} guardada")
        + "\n\n"
        + texto_pide_permiso(reserva)
    )


def texto_pide_permiso(reserva: dict) -> str:
    return (
        f"Para confirmar la reserva #{reserva['id']}, envía ahora el permiso del "
        "<b>MINERD</b> (Ministerio de Educación) que autoriza la salida de los estudiantes. "
        "Sirve una foto clara o un PDF.\n\n"
        "Hasta que no llegue, la visita queda pendiente y te voy a escribir para recordártelo. "
        "Si la imagen no se ve bien, puedes enviar otra y la reemplazo."
    )


def texto_recordatorio(reserva: dict, tipo: str, ahora: datetime) -> str:
    fecha = fecha_bonita(date.fromisoformat(reserva["fecha"]))
    hora = hora_bonita(reserva["hora_inicio"])
    if tipo == "permiso":
        intro = (
            f"Recordatorio: la reserva #{reserva['id']} de {escape(reserva['escuela'])} "
            f"({fecha}, {hora}) todavía no tiene el permiso del MINERD."
        )
    elif tipo == "visita-24" and reserva["fecha"] == ahora.date().isoformat():
        intro = (
            f"Hoy es la visita #{reserva['id']} de {escape(reserva['escuela'])}, a las {hora}."
        )
    elif tipo == "visita-24":
        intro = (
            f"En menos de 24 horas es la visita #{reserva['id']} de "
            f"{escape(reserva['escuela'])}: {fecha}, a las {hora}."
        )
    else:
        intro = (
            f"Se acerca la visita #{reserva['id']} de {escape(reserva['escuela'])}: "
            f"{fecha}, a las {hora}."
        )
    lineas = [
        intro,
        (
            f"Llegan {reserva['alumnos']} alumnos en {reserva['grupos']} grupos. "
            "Cada franja dura 2 horas."
        ),
    ]
    if not reserva.get("permiso_file_id"):
        lineas.append(
            "Todavía no hemos recibido el permiso del MINERD. "
            "Sin ese documento el museo no puede confirmar la entrada de los estudiantes. "
            "Envíalo ahora en foto o PDF."
        )
    else:
        lineas.append("El permiso del MINERD ya está en el expediente.")
    necesidades = reserva.get("necesidades") or ""
    if necesidades and necesidades != "ninguna":
        nombres = ", ".join(
            ETIQUETAS.get(clave, clave) for clave in necesidades.split(",") if clave
        )
        lineas.append(f"Necesidades registradas: {escape(nombres)}.")
        if reserva.get("detalle_necesidades"):
            lineas.append(escape(reserva["detalle_necesidades"]))
    lineas.append(f"Los esperamos en {escape(config.DIRECCION)}.")
    return "\n".join(lineas)


def ficha_taller(taller: dict) -> str:
    lineas = [
        f"<b>{escape(taller['nombre'])}</b>",
        f"<b>De qué trata:</b> {escape(taller['descripcion'])}",
        f"<b>Horario:</b> {escape(taller['horario'])}",
        f"<b>Imparte:</b> {escape(taller['facilitador'])}",
        f"<b>Institución:</b> {escape(taller['institucion'])}",
    ]
    if taller.get("plantilla"):
        lineas.append(
            "<i>Ficha inicial del sistema. El museo confirma horario y facilitador.</i>"
        )
    return "\n".join(lineas)


def texto_reserva_completa(reserva: dict) -> str:
    return resumen_reserva(reserva, titulo=f"Reserva #{reserva['id']}")


def _monto(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")
