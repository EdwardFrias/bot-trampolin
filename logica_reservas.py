"""Regla de grupos y cupo de las visitas guiadas.

200 alumnos = 8 grupos de 25. Cada franja dura 2 horas y admite 8 grupos.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import config

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
MESES_CORTOS = [
    "",
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
]


def calcular_grupos(alumnos: int) -> list[list[dict]]:
    """Devuelve franjas. Cada franja es una lista de grupos {letra, alumnos}."""
    if alumnos < 1:
        raise ValueError("La cantidad de alumnos tiene que ser mayor que cero.")

    tamanos: list[int] = []
    restante = alumnos
    while restante:
        tamanos.append(min(config.ALUMNOS_POR_GRUPO, restante))
        restante -= tamanos[-1]

    franjas: list[list[dict]] = []
    for inicio in range(0, len(tamanos), config.GRUPOS_POR_FRANJA):
        bloque = tamanos[inicio : inicio + config.GRUPOS_POR_FRANJA]
        franja = []
        for desplazamiento, cantidad in enumerate(bloque):
            indice = inicio + desplazamiento
            franja.append({"letra": chr(ord("A") + indice), "alumnos": cantidad})
        franjas.append(franja)
    return franjas


def franjas_del_dia(fecha: date) -> tuple[tuple[str, str], ...]:
    if fecha.weekday() == 0:
        return ()
    if fecha.weekday() >= 5:
        return config.FRANJAS_FIN_DE_SEMANA
    return config.FRANJAS_ENTRE_SEMANA


def es_dia_abierto(fecha: date, feriados: set[str]) -> bool:
    if fecha.isoformat() in feriados:
        return False
    return bool(franjas_del_dia(fecha))


def opciones_de_reserva(
    fecha: date,
    modelo: list[list[dict]],
    ocupados: dict[str, int],
    ahora: datetime,
    feriados: set[str],
) -> list[list[dict]]:
    """Inicios posibles. Cada opción es la lista de franjas seguidas con su hora."""
    if ahora.tzinfo is None:
        raise ValueError("La hora actual tiene que incluir la zona horaria.")
    if not es_dia_abierto(fecha, feriados):
        return []

    slots = franjas_del_dia(fecha)
    necesarias = len(modelo)
    opciones: list[list[dict]] = []
    for indice in range(len(slots) - necesarias + 1):
        plan: list[dict] = []
        sirve = True
        for paso in range(necesarias):
            hora_inicio, hora_fin = slots[indice + paso]
            salida = datetime.combine(
                fecha,
                datetime.strptime(hora_inicio, "%H:%M").time(),
                tzinfo=config.ZONA,
            )
            if salida <= ahora:
                sirve = False
                break
            usados = int(ocupados.get(hora_inicio, 0))
            necesita = len(modelo[paso])
            if usados + necesita > config.GRUPOS_POR_FRANJA:
                sirve = False
                break
            plan.append(
                {
                    "hora_inicio": hora_inicio,
                    "hora_fin": hora_fin,
                    "grupos": modelo[paso],
                    "usados": usados,
                }
            )
        if sirve:
            opciones.append(plan)
    return opciones


def proximos_dias(desde: date, cantidad: int, feriados: set[str], horizonte: int = 70) -> list[date]:
    encontrados: list[date] = []
    dia = desde
    for _ in range(horizonte):
        if es_dia_abierto(dia, feriados):
            encontrados.append(dia)
            if len(encontrados) >= cantidad:
                break
        dia += timedelta(days=1)
    return encontrados


def hora_bonita(hhmm: str) -> str:
    hora, minuto = map(int, hhmm.split(":"))
    sufijo = "a.m." if hora < 12 else "p.m."
    hora12 = hora % 12 or 12
    return f"{hora12}:{minuto:02d} {sufijo}"


def fecha_bonita(fecha: date) -> str:
    return f"{DIAS[fecha.weekday()]} {fecha.day} de {MESES[fecha.month]} de {fecha.year}"


def etiqueta_dia(fecha: date) -> str:
    return f"{DIAS_CORTOS[fecha.weekday()]} {fecha.day} {MESES_CORTOS[fecha.month]}"


def parse_fecha(texto: str) -> date | None:
    limpio = texto.strip()
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(limpio, formato).date()
        except ValueError:
            continue
    return None


def primer_entero(texto: str) -> int | None:
    hallado = re.search(r"\d+", texto)
    if not hallado:
        return None
    return int(hallado.group())


def validar_telefono(texto: str) -> str | None:
    digitos = re.sub(r"\D", "", texto)
    if len(digitos) == 11 and digitos.startswith("1"):
        digitos = digitos[1:]
    if len(digitos) == 10 and digitos[:3] in {"809", "829", "849"}:
        return f"{digitos[:3]}-{digitos[3:6]}-{digitos[6:]}"
    return None


def visita_ya_empezo(fecha_iso: str, hora_inicio: str, ahora: datetime) -> bool:
    salida = datetime.combine(
        date.fromisoformat(fecha_iso),
        datetime.strptime(hora_inicio, "%H:%M").time(),
        tzinfo=config.ZONA,
    )
    return salida <= ahora
