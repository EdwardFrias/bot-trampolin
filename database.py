"""SQLite: reservas, franjas, recordatorios y talleres."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import config

SEMILLA_TALLERES = [
    (
        "Pintura y color",
        "Los estudiantes trabajan color y forma para desarrollar creatividad e imaginación. El museo mantiene talleres de pintura dentro de su programa educativo.",
        "Martes y jueves, 10:00 a.m. a 11:30 a.m.",
        "Equipo educativo del Museo Infantil Trampolín",
        "Museo Infantil Trampolín",
    ),
    (
        "Artesanía",
        "Arman piezas sencillas con las manos. Forma parte de los talleres de artesanía del museo.",
        "Miércoles, 10:00 a.m. a 11:30 a.m.",
        "Equipo educativo del Museo Infantil Trampolín",
        "Museo Infantil Trampolín",
    ),
    (
        "Reciclaje creativo",
        "Reutilizan materiales para crear objetos nuevos, en la línea de los talleres y la feria artesanal de reciclaje del museo.",
        "Jueves, 1:00 p.m. a 2:30 p.m.",
        "Equipo educativo del Museo Infantil Trampolín",
        "Museo Infantil Trampolín",
    ),
    (
        "Lectura compartida",
        "Lectura en voz alta y conversación para acercar a los niños a los libros.",
        "Viernes, 9:00 a.m. a 10:00 a.m.",
        "Equipo educativo del Museo Infantil Trampolín",
        "Museo Infantil Trampolín",
    ),
    (
        "Manualidades",
        "Construyen objetos sencillos trabajando motricidad e imaginación.",
        "Sábados, 10:00 a.m. a 11:30 a.m.",
        "Equipo educativo del Museo Infantil Trampolín",
        "Museo Infantil Trampolín",
    ),
    (
        "Teatro y títeres",
        "Juego escénico y títeres. El museo incluye obras de teatro y títeres en su programación cultural.",
        "Sábados, 2:00 p.m. a 3:30 p.m.",
        "Equipo educativo del Museo Infantil Trampolín",
        "Museo Infantil Trampolín",
    ),
]


class CupoAgotado(Exception):
    """La franja ya no tiene grupos libres."""


@contextmanager
def conexion():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None
    try:
        conn.execute("PRAGMA journal_mode = WAL").fetchall()
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def iniciar() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL").fetchall()
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                escuela TEXT NOT NULL,
                tipo_centro TEXT NOT NULL,
                contacto TEXT NOT NULL,
                telefono TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora_inicio TEXT NOT NULL,
                hora_fin TEXT NOT NULL,
                alumnos INTEGER NOT NULL,
                grupos INTEGER NOT NULL,
                grado TEXT NOT NULL,
                acompanantes INTEGER NOT NULL,
                necesidades TEXT NOT NULL,
                detalle_necesidades TEXT NOT NULL DEFAULT '',
                estado TEXT NOT NULL,
                permiso_file_id TEXT,
                permiso_nombre TEXT,
                permiso_ruta TEXT,
                permiso_en TEXT,
                creado_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS franjas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reserva_id INTEGER NOT NULL REFERENCES reservas(id),
                orden INTEGER NOT NULL,
                hora_inicio TEXT NOT NULL,
                hora_fin TEXT NOT NULL,
                alumnos INTEGER NOT NULL,
                grupos INTEGER NOT NULL,
                detalle_grupos TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reserva_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                enviado_en TEXT NOT NULL,
                UNIQUE (reserva_id, tipo)
            );

            CREATE TABLE IF NOT EXISTS talleres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                horario TEXT NOT NULL,
                facilitador TEXT NOT NULL,
                institucion TEXT NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1,
                plantilla INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_reservas_fecha
                ON reservas (fecha, estado);
            CREATE INDEX IF NOT EXISTS idx_franjas_reserva
                ON franjas (reserva_id);
            """
        )
        cantidad = conn.execute("SELECT COUNT(*) AS n FROM talleres").fetchone()["n"]
        if cantidad == 0:
            conn.executemany(
                """
                INSERT INTO talleres
                    (nombre, descripcion, horario, facilitador, institucion, activo, plantilla)
                VALUES (?, ?, ?, ?, ?, 1, 1)
                """,
                SEMILLA_TALLERES,
            )
        conn.commit()
    finally:
        conn.close()


def _con_franjas(conn: sqlite3.Connection, filas: list[sqlite3.Row]) -> list[dict]:
    salida = []
    for fila in filas:
        item = dict(fila)
        franjas = conn.execute(
            "SELECT * FROM franjas WHERE reserva_id = ? ORDER BY orden",
            (item["id"],),
        ).fetchall()
        item["franjas"] = []
        for franja in franjas:
            datos = dict(franja)
            datos["grupos_detalle"] = json.loads(datos["detalle_grupos"])
            item["franjas"].append(datos)
        salida.append(item)
    return salida


def ocupacion(fecha: str) -> dict[str, int]:
    with conexion() as conn:
        filas = conn.execute(
            """
            SELECT f.hora_inicio AS hora, COALESCE(SUM(f.grupos), 0) AS grupos
            FROM franjas f
            JOIN reservas r ON r.id = f.reserva_id
            WHERE r.fecha = ? AND r.estado != 'cancelada'
            GROUP BY f.hora_inicio
            """,
            (fecha,),
        ).fetchall()
    return {fila["hora"]: int(fila["grupos"]) for fila in filas}


def crear_reserva(datos: dict) -> int:
    plan = datos["plan"]
    if not plan:
        raise ValueError("La reserva no tiene franjas.")
    suma = sum(grupo["alumnos"] for bloque in plan for grupo in bloque["grupos"])
    if suma != int(datos["alumnos"]):
        raise ValueError("Los grupos no cuadran con los alumnos.")

    grupos_total = sum(len(bloque["grupos"]) for bloque in plan)
    with conexion() as conn:
        for bloque in plan:
            fila = conn.execute(
                """
                SELECT COALESCE(SUM(f.grupos), 0) AS grupos
                FROM franjas f
                JOIN reservas r ON r.id = f.reserva_id
                WHERE r.fecha = ? AND r.estado != 'cancelada' AND f.hora_inicio = ?
                """,
                (datos["fecha"], bloque["hora_inicio"]),
            ).fetchone()
            usados = int(fila["grupos"])
            if usados + len(bloque["grupos"]) > config.GRUPOS_POR_FRANJA:
                raise CupoAgotado(bloque["hora_inicio"])

        cursor = conn.execute(
            """
            INSERT INTO reservas (
                user_id, chat_id, escuela, tipo_centro, contacto, telefono,
                fecha, hora_inicio, hora_fin, alumnos, grupos, grado,
                acompanantes, necesidades, detalle_necesidades, estado, creado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente_permiso', ?)
            """,
            (
                datos["user_id"],
                datos["chat_id"],
                datos["escuela"],
                datos["tipo_centro"],
                datos["contacto"],
                datos["telefono"],
                datos["fecha"],
                plan[0]["hora_inicio"],
                plan[-1]["hora_fin"],
                int(datos["alumnos"]),
                grupos_total,
                datos["grado"],
                int(datos["acompanantes"]),
                datos["necesidades"],
                datos.get("detalle_necesidades") or "",
                datetime.now(config.ZONA).isoformat(timespec="seconds"),
            ),
        )
        reserva_id = int(cursor.lastrowid)
        for orden, bloque in enumerate(plan, start=1):
            conn.execute(
                """
                INSERT INTO franjas (
                    reserva_id, orden, hora_inicio, hora_fin, alumnos, grupos, detalle_grupos
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reserva_id,
                    orden,
                    bloque["hora_inicio"],
                    bloque["hora_fin"],
                    sum(grupo["alumnos"] for grupo in bloque["grupos"]),
                    len(bloque["grupos"]),
                    json.dumps(bloque["grupos"], ensure_ascii=False),
                ),
            )
    return reserva_id


def obtener_reserva(reserva_id: int, user_id: int | None = None) -> dict | None:
    with conexion() as conn:
        if user_id is None:
            fila = conn.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
        else:
            fila = conn.execute(
                "SELECT * FROM reservas WHERE id = ? AND user_id = ?",
                (reserva_id, user_id),
            ).fetchone()
        if fila is None:
            return None
        return _con_franjas(conn, [fila])[0]


def reservas_de_usuario(user_id: int, desde: str) -> list[dict]:
    with conexion() as conn:
        filas = conn.execute(
            """
            SELECT * FROM reservas
            WHERE user_id = ? AND fecha >= ?
            ORDER BY fecha, hora_inicio
            """,
            (user_id, desde),
        ).fetchall()
        return _con_franjas(conn, list(filas))


def pendientes_permiso(user_id: int, desde: str) -> list[dict]:
    with conexion() as conn:
        filas = conn.execute(
            """
            SELECT * FROM reservas
            WHERE user_id = ? AND estado = 'pendiente_permiso' AND fecha >= ?
            ORDER BY fecha, hora_inicio
            """,
            (user_id, desde),
        ).fetchall()
        return _con_franjas(conn, list(filas))


def reservas_vigentes(desde: str) -> list[dict]:
    with conexion() as conn:
        filas = conn.execute(
            """
            SELECT * FROM reservas
            WHERE estado != 'cancelada' AND fecha >= ?
            ORDER BY fecha, hora_inicio
            """,
            (desde,),
        ).fetchall()
        return _con_franjas(conn, list(filas))


def reservas_entre(desde: str, hasta: str) -> list[dict]:
    with conexion() as conn:
        filas = conn.execute(
            """
            SELECT * FROM reservas
            WHERE estado != 'cancelada' AND fecha >= ? AND fecha <= ?
            ORDER BY fecha, hora_inicio
            """,
            (desde, hasta),
        ).fetchall()
        return _con_franjas(conn, list(filas))


def cancelar_reserva(reserva_id: int, user_id: int, forzar: bool = False) -> str:
    with conexion() as conn:
        fila = conn.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
        if fila is None:
            return "no"
        if not forzar and int(fila["user_id"]) != user_id:
            return "ajena"
        if fila["estado"] == "cancelada":
            return "ya"
        if not forzar:
            from logica_reservas import visita_ya_empezo

            if visita_ya_empezo(fila["fecha"], fila["hora_inicio"], datetime.now(config.ZONA)):
                return "pasada"
        conn.execute(
            "UPDATE reservas SET estado = 'cancelada' WHERE id = ?",
            (reserva_id,),
        )
    return "ok"


def guardar_permiso(reserva_id: int, user_id: int, file_id: str, nombre: str, ruta: str) -> bool:
    with conexion() as conn:
        cursor = conn.execute(
            """
            UPDATE reservas
            SET permiso_file_id = ?, permiso_nombre = ?, permiso_ruta = ?,
                permiso_en = ?, estado = 'confirmada'
            WHERE id = ? AND user_id = ? AND estado != 'cancelada'
            """,
            (
                file_id,
                nombre,
                ruta,
                datetime.now(config.ZONA).isoformat(timespec="seconds"),
                reserva_id,
                user_id,
            ),
        )
        return cursor.rowcount == 1


def tipos_enviados(reserva_id: int) -> set[str]:
    with conexion() as conn:
        filas = conn.execute(
            "SELECT tipo FROM recordatorios WHERE reserva_id = ?",
            (reserva_id,),
        ).fetchall()
    return {fila["tipo"] for fila in filas}


def marcar_recordatorio(reserva_id: int, tipo: str) -> None:
    with conexion() as conn:
        conn.execute(
            """
            INSERT INTO recordatorios (reserva_id, tipo, enviado_en)
            VALUES (?, ?, ?)
            ON CONFLICT (reserva_id, tipo) DO NOTHING
            """,
            (reserva_id, tipo, datetime.now(config.ZONA).isoformat(timespec="seconds")),
        )


def listar_talleres(solo_activos: bool = True) -> list[dict]:
    with conexion() as conn:
        if solo_activos:
            filas = conn.execute(
                "SELECT * FROM talleres WHERE activo = 1 ORDER BY id"
            ).fetchall()
        else:
            filas = conn.execute("SELECT * FROM talleres ORDER BY id").fetchall()
    return [dict(fila) for fila in filas]


def crear_taller(nombre: str, descripcion: str, horario: str, facilitador: str, institucion: str) -> int:
    with conexion() as conn:
        cursor = conn.execute(
            """
            INSERT INTO talleres
                (nombre, descripcion, horario, facilitador, institucion, activo, plantilla)
            VALUES (?, ?, ?, ?, ?, 1, 0)
            """,
            (nombre, descripcion, horario, facilitador, institucion),
        )
        return int(cursor.lastrowid)


def desactivar_taller(taller_id: int) -> bool:
    with conexion() as conn:
        cursor = conn.execute(
            "UPDATE talleres SET activo = 0 WHERE id = ? AND activo = 1",
            (taller_id,),
        )
        return cursor.rowcount == 1
