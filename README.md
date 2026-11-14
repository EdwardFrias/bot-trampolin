# Asistente del Museo Infantil Trampolín

Bot de Telegram para el museo. Responde preguntas a cualquier hora, reserva visitas guiadas de grupos, guarda necesidades especiales, pide el permiso del MINERD y muestra los talleres disponibles.

## Cómo reserva los grupos

- Cada grupo lleva hasta **25 alumnos**.
- **200 alumnos = 8 grupos**.
- Una franja dura **2 horas** y admite hasta **8 grupos** (200 alumnos) a la vez.
- Si el centro trae más de 200, el bot abre las franjas seguidas que hagan falta. Cada una sigue siendo de 2 horas.

Martes a viernes: 8:30 a.m., 10:30 a.m. y 12:30 p.m.
Sábados y domingos: 9:30 a.m., 11:30 a.m., 1:30 p.m. y 3:30 p.m.
Los lunes no hay visitas. El horario público que usa el bot es el de trampolin.org.do: martes a viernes de 8:30 a.m. a 4:00 p.m., y sábados y domingos de 9:30 a.m. a 5:30 p.m.

Si el museo cambia la regla, edita `ALUMNOS_POR_GRUPO` y `GRUPOS_POR_FRANJA` en `config.py`.

## Permiso del MINERD

Al confirmar, la reserva queda pendiente hasta que el docente envíe la autorización del Ministerio de Educación en foto o PDF. El bot la guarda en `data/permisos/` y, si configuraste `STAFF_CHAT_ID`, se la reenvía al equipo.

Los recordatorios salen entre 8:00 a.m. y 7:00 p.m.:

- uno al día mientras falte el permiso
- otro cuando faltan unos 3 días
- otro cuando falta menos de 24 horas

## Talleres

`/talleres` muestra cada ficha con el tema, el horario, quién lo imparte y la institución. El programa que viene cargado es una plantilla: el sitio del museo no publica el calendario ni los facilitadores actuales. Antes de usarlo con el público, oculta esas fichas con `/quitar_taller` y carga las reales con `/nuevo_taller`.

La entrada de RD$50 (escuela pública) y RD$100 (colegio privado) es una referencia publicada. Conviene confirmarla; el bot no cobra.

## Ponerlo a correr

1. En Telegram, habla con [@BotFather](https://t.me/BotFather), crea un bot y copia el token.
2. En esta carpeta, copia `.env.example` a `.env` y pega el token en `BOT_TOKEN`.
3. Doble clic en `run.bat`, o en una terminal:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

4. Abre el bot en Telegram y escribe `/start`.
5. Escribe `/miid`, pon ese número en `ADMIN_IDS` y reinicia el bot. Con `/admin` ves los comandos del equipo.

`STAFF_CHAT_ID` es opcional. Si pones tu propio ID, te llegan las reservas nuevas y los permisos. En un grupo, agrega el bot y usa el ID del grupo (suele empezar con `-100`).

Para comprobar la regla de grupos sin abrir Telegram:

```bat
python test_logica.py
```

La ventana de `run.bat` tiene que quedarse abierta. Si se cierra, el bot deja de contestar.
