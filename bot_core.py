"""
Logica de negocio del chatbot (turn-based, sin I/O).
Se puede consumir tanto desde la CLI (chatbot.py) como desde la web
(app.py). Cada llamada a procesar() recibe el estado actual de la
conversacion mas el mensaje del usuario y devuelve el nuevo estado y la
lista de mensajes que el bot debe mostrar.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
EMPLEADOS_CSV = DATA_DIR / "empleados.csv"
SOLICITUDES_CSV = DATA_DIR / "solicitudes.csv"
FERIADOS_CSV = DATA_DIR / "feriados.csv"

LIMITE_DIAS_AUTO = 5
MAX_REINTENTOS = 3


# ============================================================
# PERSISTENCIA
# ============================================================

def leer_empleados():
    with open(EMPLEADOS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def buscar_empleado(legajo):
    for e in leer_empleados():
        if e["legajo"] == str(legajo):
            return e
    return None


def actualizar_dias(legajo, nuevos_dias):
    empleados = leer_empleados()
    for e in empleados:
        if e["legajo"] == str(legajo):
            e["dias_disponibles"] = str(nuevos_dias)
    with open(EMPLEADOS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=empleados[0].keys())
        w.writeheader()
        w.writerows(empleados)


def leer_solicitudes():
    with open(SOLICITUDES_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def proximo_id():
    sols = leer_solicitudes()
    if not sols:
        return "S0001"
    ultimo = max(int(s["id_solicitud"][1:]) for s in sols)
    return f"S{ultimo + 1:04d}"


def guardar_solicitud(solicitud):
    sols = leer_solicitudes()
    campos = ["id_solicitud", "legajo", "fecha_solicitud", "fecha_desde",
              "fecha_hasta", "cantidad_dias", "estado", "motivo_rechazo"]
    sols.append(solicitud)
    with open(SOLICITUDES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(sols)


def leer_feriados():
    with open(FERIADOS_CSV, newline="", encoding="utf-8") as f:
        return [datetime.strptime(r["fecha"], "%Y-%m-%d").date()
                for r in csv.DictReader(f)]


# ============================================================
# UTILIDADES DE DOMINIO
# ============================================================

def parsear_fecha(texto):
    texto = (texto or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def calcular_dias_habiles(desde, hasta, feriados):
    dias = 0
    cur = desde
    while cur <= hasta:
        if cur.weekday() < 5 and cur not in feriados:
            dias += 1
        cur += timedelta(days=1)
    return dias


def hay_solapamiento(legajo, desde, hasta):
    for s in leer_solicitudes():
        if s["legajo"] != str(legajo):
            continue
        if s["estado"] not in ("APROBADA", "PENDIENTE"):
            continue
        d = datetime.strptime(s["fecha_desde"], "%Y-%m-%d").date()
        h = datetime.strptime(s["fecha_hasta"], "%Y-%m-%d").date()
        if not (hasta < d or desde > h):
            return True
    return False


# ============================================================
# MAQUINA DE ESTADOS
# ============================================================

ESTADO_INICIO = "INICIO"
ESTADO_AUTENTICADO = "AUTENTICADO"
ESTADO_SOL_DESDE = "SOLICITANDO_DESDE"
ESTADO_SOL_HASTA = "SOLICITANDO_HASTA"
ESTADO_CONFIRMANDO = "CONFIRMANDO"
ESTADO_FIN = "FIN"


def estado_inicial():
    """Devuelve la estructura de estado inicial para una nueva conversacion."""
    return {
        "estado": ESTADO_INICIO,
        "legajo": None,
        "draft": {},
        "intentos": 0,
    }


def saludo_inicial():
    return [
        "Hola, soy VacaBot. Te ayudo a gestionar tus vacaciones.",
        "Podes escribir 'salir' para terminar o 'cancelar' para volver al menu.",
        "Ingresa tu numero de legajo:",
    ]


def menu_texto():
    return ("--- MENU ---\n"
            "1) Solicitar vacaciones\n"
            "2) Consultar saldo de dias\n"
            "3) Ver mis solicitudes\n"
            "4) Salir\n"
            "Elegi una opcion (1-4):")


# ============================================================
# ORQUESTADOR TURN-BASED
# ============================================================

def procesar(estado, mensaje):
    """Procesa un mensaje del usuario y devuelve (nuevo_estado, [respuestas_bot]).

    Esta funcion es pura desde el punto de vista del flujo: no lee teclado
    ni imprime. Cada llamada equivale a un "turno" de la conversacion.
    """
    msg = (mensaje or "").strip()
    bajo = msg.lower()

    # Comandos transversales
    if bajo in ("salir", "/salir", "exit", "quit"):
        estado["estado"] = ESTADO_FIN
        return estado, ["Sesion finalizada. Hasta luego."]

    if bajo in ("cancelar", "/cancelar") and estado["estado"] != ESTADO_INICIO:
        estado["estado"] = ESTADO_AUTENTICADO
        estado["draft"] = {}
        estado["intentos"] = 0
        return estado, ["Operacion cancelada.", menu_texto()]

    # Despacho segun estado
    handlers = {
        ESTADO_INICIO: _h_inicio,
        ESTADO_AUTENTICADO: _h_menu,
        ESTADO_SOL_DESDE: _h_sol_desde,
        ESTADO_SOL_HASTA: _h_sol_hasta,
        ESTADO_CONFIRMANDO: _h_confirmando,
    }
    handler = handlers.get(estado["estado"])
    if handler is None:
        estado["estado"] = ESTADO_AUTENTICADO
        return estado, [menu_texto()]
    return handler(estado, msg)


def _h_inicio(estado, msg):
    """Autenticacion por legajo (con reintentos)."""
    if not msg.isdigit() or buscar_empleado(msg) is None:
        estado["intentos"] += 1
        restantes = MAX_REINTENTOS - estado["intentos"]
        if restantes <= 0:
            estado["estado"] = ESTADO_FIN
            return estado, ["Se agotaron los intentos. Sesion cerrada."]
        return estado, [f"Legajo invalido o inexistente. "
                        f"Te quedan {restantes} intento(s)."]
    emp = buscar_empleado(msg)
    estado["legajo"] = emp["legajo"]
    estado["estado"] = ESTADO_AUTENTICADO
    estado["intentos"] = 0
    return estado, [
        f"Bienvenido/a {emp['nombre']} {emp['apellido']} "
        f"(area: {emp['area']}, saldo actual: {emp['dias_disponibles']} dias).",
        menu_texto(),
    ]


def _h_menu(estado, msg):
    if msg == "1":
        estado["estado"] = ESTADO_SOL_DESDE
        estado["draft"] = {}
        estado["intentos"] = 0
        return estado, [
            "Vamos a registrar una nueva solicitud.",
            "Fecha de INICIO (YYYY-MM-DD o DD/MM/YYYY):",
        ]
    if msg == "2":
        emp = buscar_empleado(estado["legajo"])
        return estado, [
            f"Tu saldo actual es de {emp['dias_disponibles']} dia(s) habiles.",
            menu_texto(),
        ]
    if msg == "3":
        mias = [s for s in leer_solicitudes() if s["legajo"] == estado["legajo"]]
        if not mias:
            return estado, ["No tenes solicitudes registradas.", menu_texto()]
        lineas = [f"Tenes {len(mias)} solicitud(es):"]
        for s in mias:
            extra = f" ({s['motivo_rechazo']})" if s["motivo_rechazo"] else ""
            lineas.append(f"  • {s['id_solicitud']} | {s['fecha_desde']} a "
                          f"{s['fecha_hasta']} | {s['cantidad_dias']} dias | "
                          f"{s['estado']}{extra}")
        lineas.append(menu_texto())
        return estado, lineas
    if msg == "4":
        estado["estado"] = ESTADO_FIN
        return estado, ["Sesion finalizada. Hasta luego."]
    return estado, ["Opcion no valida. Elegi un numero del 1 al 4.",
                    menu_texto()]


def _h_sol_desde(estado, msg):
    fecha = parsear_fecha(msg)
    hoy = datetime.now().date()
    if fecha is None or fecha < hoy:
        estado["intentos"] += 1
        restantes = MAX_REINTENTOS - estado["intentos"]
        if restantes <= 0:
            estado["estado"] = ESTADO_AUTENTICADO
            estado["intentos"] = 0
            return estado, ["Se agotaron los intentos. Vuelvo al menu.",
                            menu_texto()]
        return estado, [f"Fecha invalida o anterior a hoy. "
                        f"Te quedan {restantes} intento(s)."]
    estado["draft"]["desde"] = fecha.isoformat()
    estado["estado"] = ESTADO_SOL_HASTA
    estado["intentos"] = 0
    return estado, ["Fecha de FIN (debe ser igual o posterior a la de inicio):"]


def _h_sol_hasta(estado, msg):
    fecha = parsear_fecha(msg)
    desde = datetime.strptime(estado["draft"]["desde"], "%Y-%m-%d").date()
    if fecha is None or fecha < desde:
        estado["intentos"] += 1
        restantes = MAX_REINTENTOS - estado["intentos"]
        if restantes <= 0:
            estado["estado"] = ESTADO_AUTENTICADO
            estado["intentos"] = 0
            return estado, ["Se agotaron los intentos. Vuelvo al menu.",
                            menu_texto()]
        return estado, [f"Fecha invalida o anterior a la de inicio. "
                        f"Te quedan {restantes} intento(s)."]

    # --- Tarea Sistema: calcular dias habiles ---
    feriados = leer_feriados()
    dias = calcular_dias_habiles(desde, fecha, feriados)
    if dias == 0:
        estado["estado"] = ESTADO_AUTENTICADO
        return estado, ["El rango no tiene dias habiles. Cancelo la solicitud.",
                        menu_texto()]

    emp = buscar_empleado(estado["legajo"])
    saldo = int(emp["dias_disponibles"])

    # --- GATEWAY 1: saldo ---
    if dias > saldo:
        guardar_solicitud(_armar_solicitud(estado, desde, fecha, dias,
                                           "RECHAZADA",
                                           "Sin saldo de dias disponibles"))
        estado["estado"] = ESTADO_AUTENTICADO
        return estado, [
            f"Calcule {dias} dia(s) habil(es) en el rango.",
            f"No tenes saldo suficiente ({saldo} dias). RECHAZADA.",
            menu_texto(),
        ]

    # --- GATEWAY 2: solapamiento ---
    if hay_solapamiento(estado["legajo"], desde, fecha):
        guardar_solicitud(_armar_solicitud(estado, desde, fecha, dias,
                                           "RECHAZADA",
                                           "Solapamiento con otra solicitud"))
        estado["estado"] = ESTADO_AUTENTICADO
        return estado, [
            "Ya tenes una solicitud aprobada/pendiente en ese rango. RECHAZADA.",
            menu_texto(),
        ]

    estado["draft"]["hasta"] = fecha.isoformat()
    estado["draft"]["dias"] = dias
    estado["estado"] = ESTADO_CONFIRMANDO
    return estado, [
        f"Calcule {dias} dia(s) habil(es) (sin fines de semana ni feriados).",
        f"Resumen: del {desde} al {fecha} ({dias} dias). "
        f"Saldo restante quedaria en {saldo - dias}.",
        "Confirmas? (si/no)",
    ]


def _h_confirmando(estado, msg):
    if msg.lower() not in ("si", "s", "yes", "y"):
        estado["estado"] = ESTADO_AUTENTICADO
        estado["draft"] = {}
        return estado, ["Solicitud cancelada.", menu_texto()]

    desde = datetime.strptime(estado["draft"]["desde"], "%Y-%m-%d").date()
    hasta = datetime.strptime(estado["draft"]["hasta"], "%Y-%m-%d").date()
    dias = estado["draft"]["dias"]
    emp = buscar_empleado(estado["legajo"])
    saldo = int(emp["dias_disponibles"])
    nuevo_id = proximo_id()

    # --- GATEWAY 3: limite de dias para aprobacion automatica ---
    if dias <= LIMITE_DIAS_AUTO:
        guardar_solicitud(_armar_solicitud(estado, desde, hasta, dias,
                                           "APROBADA", "",
                                           id_forzado=nuevo_id))
        actualizar_dias(estado["legajo"], saldo - dias)
        estado["estado"] = ESTADO_AUTENTICADO
        estado["draft"] = {}
        return estado, [
            f"Solicitud {nuevo_id} APROBADA automaticamente.",
            f"Saldo restante: {saldo - dias} dias.",
            menu_texto(),
        ]

    # > 5 dias: deriva al supervisor
    guardar_solicitud(_armar_solicitud(estado, desde, hasta, dias,
                                       "PENDIENTE", "",
                                       id_forzado=nuevo_id))
    sup = buscar_empleado(emp["supervisor"])
    nombre_sup = f"{sup['nombre']} {sup['apellido']}" if sup else "tu supervisor"
    estado["estado"] = ESTADO_AUTENTICADO
    estado["draft"] = {}
    return estado, [
        f"Solicitud {nuevo_id} supera el limite de {LIMITE_DIAS_AUTO} dias "
        f"de aprobacion automatica.",
        f"Queda PENDIENTE de aprobacion de {nombre_sup}.",
        menu_texto(),
    ]


def _armar_solicitud(estado, desde, hasta, dias, est, motivo, id_forzado=None):
    return {
        "id_solicitud": id_forzado or proximo_id(),
        "legajo": estado["legajo"],
        "fecha_solicitud": datetime.now().date().isoformat(),
        "fecha_desde": desde.isoformat(),
        "fecha_hasta": hasta.isoformat(),
        "cantidad_dias": str(dias),
        "estado": est,
        "motivo_rechazo": motivo,
    }
