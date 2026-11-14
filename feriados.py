"""Feriados en los que no se abren reservas de grupos."""

from __future__ import annotations

import json

import config


def listar() -> set[str]:
    ruta = config.FERIADOS_PATH
    if not ruta.exists():
        return set()
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(item) for item in datos}


def _guardar(fechas: set[str]) -> None:
    ruta = config.FERIADOS_PATH
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(sorted(fechas), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def agregar(fecha_iso: str) -> None:
    fechas = listar()
    fechas.add(fecha_iso)
    _guardar(fechas)


def quitar(fecha_iso: str) -> bool:
    fechas = listar()
    if fecha_iso not in fechas:
        return False
    fechas.remove(fecha_iso)
    _guardar(fechas)
    return True
