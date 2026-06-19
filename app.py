"""
TPI - Organizacion Empresarial - UTN TUPaD
VacaBot - version web (Flask)

Expone el chatbot simulado sobre HTTP. La logica de negocio vive en
bot_core.py; este archivo solo se ocupa del transporte HTTP y de mantener
el estado de cada conversacion en la sesion del navegador.
"""

import uuid

from flask import Flask, jsonify, render_template, request, session

import bot_core

app = Flask(__name__)
app.secret_key = "tpi-utn-organizacion-empresarial-2026"

# Estado de cada conversacion en memoria del servidor, indexado por el id
# que se guarda en la cookie firmada de Flask. La cookie del navegador
# no contiene los datos, solo la referencia (mas liviano y seguro).
SESIONES = {}


def _obtener_sesion():
    sid = session.get("sid")
    if sid is None or sid not in SESIONES:
        sid = str(uuid.uuid4())
        session["sid"] = sid
        SESIONES[sid] = bot_core.estado_inicial()
    return sid, SESIONES[sid]


@app.route("/")
def index():
    sid, estado = _obtener_sesion()
    saludo = bot_core.saludo_inicial() if estado["estado"] == bot_core.ESTADO_INICIO else []
    return render_template("chat.html", saludo=saludo)


@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    mensaje = payload.get("mensaje", "")
    sid, estado = _obtener_sesion()

    nuevo_estado, respuestas = bot_core.procesar(estado, mensaje)
    SESIONES[sid] = nuevo_estado

    return jsonify({
        "respuestas": respuestas,
        "estado": nuevo_estado["estado"],
        "fin": nuevo_estado["estado"] == bot_core.ESTADO_FIN,
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    sid = session.get("sid")
    if sid in SESIONES:
        del SESIONES[sid]
    session.pop("sid", None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
