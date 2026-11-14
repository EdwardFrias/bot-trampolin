"""Comprueba la regla de grupos, el cupo, el FAQ y los recordatorios."""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

_tmp = Path(tempfile.mkdtemp())
os.environ["DB_PATH"] = str(_tmp / "trampolin.db")
os.environ["FERIADOS_PATH"] = str(_tmp / "feriados.json")

import config
import contenido
import database as db
import feriados
from logica_reservas import (
    calcular_grupos,
    opciones_de_reserva,
    validar_telefono,
)
from recordatorios import plan_recordatorios


def minutos(inicio: str, fin: str) -> int:
    hora_a, minuto_a = map(int, inicio.split(":"))
    hora_b, minuto_b = map(int, fin.split(":"))
    return (hora_b * 60 + minuto_b) - (hora_a * 60 + minuto_a)


def proximo(weekday: int, desde: date | None = None) -> date:
    dia = desde or datetime.now(config.ZONA).date()
    while dia.weekday() != weekday:
        dia += timedelta(days=1)
    return dia


def base(fecha: str, alumnos: int, plan: list) -> dict:
    return {
        "user_id": 7,
        "chat_id": 7,
        "escuela": "Escuela Duarte",
        "tipo_centro": "publica",
        "contacto": "Ana Pérez",
        "telefono": "809-555-1234",
        "fecha": fecha,
        "alumnos": alumnos,
        "grado": "4to de primaria",
        "acompanantes": 4,
        "necesidades": "movilidad",
        "detalle_necesidades": "Dos sillas de ruedas",
        "plan": plan,
    }


def plan_de(alumnos: int, horas: list[tuple[str, str]]) -> list[dict]:
    modelo = calcular_grupos(alumnos)
    assert len(modelo) == len(horas)
    return [
        {
            "hora_inicio": inicio,
            "hora_fin": fin,
            "grupos": franja,
            "usados": 0,
        }
        for franja, (inicio, fin) in zip(modelo, horas)
    ]


def test_doscientos_alumnos() -> None:
    franjas = calcular_grupos(200)
    assert len(franjas) == 1
    assert len(franjas[0]) == 8
    assert [grupo["letra"] for grupo in franjas[0]] == list("ABCDEFGH")
    assert all(grupo["alumnos"] == 25 for grupo in franjas[0])
    assert "200 alumnos = 8 grupos" in contenido.texto_calculo(200)


def test_sobran_alumnos() -> None:
    franjas = calcular_grupos(201)
    assert len(franjas) == 2
    assert len(franjas[0]) == 8
    assert franjas[1] == [{"letra": "I", "alumnos": 1}]


def test_franjas_duran_dos_horas() -> None:
    for pares in (config.FRANJAS_ENTRE_SEMANA, config.FRANJAS_FIN_DE_SEMANA):
        for inicio, fin in pares:
            assert minutos(inicio, fin) == 120
        for indice in range(len(pares) - 1):
            assert pares[indice][1] <= pares[indice + 1][0]


def test_cupo_y_horario() -> None:
    jueves = proximo(3)
    sabado = proximo(5)
    lunes = proximo(0)
    referencia = min(jueves, sabado)
    ahora = datetime.combine(referencia, datetime.strptime("07:00", "%H:%M").time(), config.ZONA)
    opciones = opciones_de_reserva(jueves, calcular_grupos(200), {}, ahora, set())
    assert len(opciones) == 3
    assert opciones[0][0]["hora_inicio"] == "08:30"
    assert opciones[0][0]["hora_fin"] == "10:30"
    assert len(opciones[0][0]["grupos"]) == 8

    grandes = opciones_de_reserva(jueves, calcular_grupos(201), {}, ahora, set())
    assert len(grandes) == 2
    assert [bloque["hora_inicio"] for bloque in grandes[0]] == ["08:30", "10:30"]
    assert [bloque["hora_inicio"] for bloque in grandes[1]] == ["10:30", "12:30"]

    tarde = datetime.combine(jueves, datetime.strptime("11:00", "%H:%M").time(), config.ZONA)
    tarde_opciones = opciones_de_reserva(jueves, calcular_grupos(25), {}, tarde, set())
    assert [opcion[0]["hora_inicio"] for opcion in tarde_opciones] == ["12:30"]

    lleno = opciones_de_reserva(jueves, calcular_grupos(25), {"08:30": 8}, ahora, set())
    assert all(opcion[0]["hora_inicio"] != "08:30" for opcion in lleno)
    assert len(lleno) == 2

    assert opciones_de_reserva(lunes, calcular_grupos(25), {}, ahora, set()) == []
    assert opciones_de_reserva(jueves, calcular_grupos(25), {}, ahora, {jueves.isoformat()}) == []
    assert len(opciones_de_reserva(sabado, calcular_grupos(25), {}, ahora, set())) == 4
    assert validar_telefono("(809) 685-5551") == "809-685-5551"
    assert validar_telefono("123") is None


def test_faq() -> None:
    assert contenido.buscar("hola")[0] == "saludo"
    assert contenido.buscar("klk")[0] == "saludo"
    tipo, items = contenido.buscar("a que hora abren")
    assert tipo == "una" and items[0]["id"] == "horario"
    tipo, items = contenido.buscar("permiso del minerd")
    assert tipo == "una" and items[0]["id"] == "permiso"
    tipo, items = contenido.buscar("200 alumnos")
    assert tipo == "una" and items[0]["id"] == "grupos"
    assert "8 grupos" in contenido.texto_faq("grupos")
    assert contenido.buscar("asdfqwer")[0] == "nada"


def test_recordatorios() -> None:
    ahora = datetime(2026, 11, 10, 10, 0, tzinfo=config.ZONA)
    reserva = {
        "fecha": "2026-11-20",
        "hora_inicio": "08:30",
        "creado_en": "2026-11-10T09:00:00-04:00",
        "permiso_file_id": None,
        "estado": "pendiente_permiso",
    }
    assert plan_recordatorios(reserva, ahora, set()) is None

    reserva["creado_en"] = "2026-11-10T05:00:00-04:00"
    aviso = plan_recordatorios(reserva, ahora, set())
    assert aviso is not None and aviso.tipo == "permiso"
    assert plan_recordatorios(reserva, ahora, {"permiso-2026-11-10"}) is None

    reserva["fecha"] = "2026-11-11"
    aviso = plan_recordatorios(reserva, ahora, set())
    assert aviso is not None and aviso.tipo == "visita-24"
    assert any(tipo.startswith("permiso-") for tipo in aviso.marcar)

    reserva["permiso_file_id"] = "abc"
    reserva["estado"] = "confirmada"
    aviso = plan_recordatorios(reserva, ahora, set())
    assert aviso is not None and aviso.tipo == "visita-24"
    assert all(not tipo.startswith("permiso") for tipo in aviso.marcar)

    reserva["fecha"] = "2026-11-12"
    aviso = plan_recordatorios(reserva, ahora, set())
    assert aviso is not None and aviso.tipo == "visita-72"


def test_base_de_datos() -> None:
    db.iniciar()
    fecha = (datetime.now(config.ZONA).date() + timedelta(days=20)).isoformat()
    primera = db.crear_reserva(base(fecha, 200, plan_de(200, [("08:30", "10:30")])))
    guardada = db.obtener_reserva(primera)
    assert guardada is not None
    assert guardada["grupos"] == 8
    assert guardada["estado"] == "pendiente_permiso"
    assert db.ocupacion(fecha)["08:30"] == 8
    try:
        db.crear_reserva(
            base(
                fecha,
                25,
                [
                    {
                        "hora_inicio": "08:30",
                        "hora_fin": "10:30",
                        "grupos": [{"letra": "A", "alumnos": 25}],
                    }
                ],
            )
        )
        raise AssertionError("El cupo debió agotarse")
    except db.CupoAgotado:
        pass
    assert db.cancelar_reserva(primera, 7, forzar=True) == "ok"
    assert db.ocupacion(fecha).get("08:30", 0) == 0
    segunda = db.crear_reserva(base(fecha, 25, plan_de(25, [("08:30", "10:30")])))
    assert db.guardar_permiso(segunda, 7, "file", "permiso.pdf", "")
    assert db.obtener_reserva(segunda)["estado"] == "confirmada"
    assert len(db.listar_talleres()) == 6
    feriados.agregar("2026-04-03")
    assert "2026-04-03" in feriados.listar()
    assert feriados.quitar("2026-04-03")


def main() -> None:
    test_doscientos_alumnos()
    test_sobran_alumnos()
    test_franjas_duran_dos_horas()
    test_cupo_y_horario()
    test_faq()
    test_recordatorios()
    test_base_de_datos()
    print("Todo en orden")


if __name__ == "__main__":
    main()
