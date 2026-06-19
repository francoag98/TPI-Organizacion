"""
TPI - Organizacion Empresarial - UTN TUPaD
Chatbot simulado: Gestion de Vacaciones
Autor: Franco Aglieri

Simulador de un chatbot administrativo que implementa el proceso de
solicitud de vacaciones siguiendo un modelo BPMN 2.0. La logica responde
a una maquina de estados que refleja los carriles (lanes) del diagrama:
Usuario y Sistema/Bot.

Persistencia: archivos CSV en ./data/ (empleados, solicitudes, feriados).
"""

import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
EMPLEADOS_CSV = DATA_DIR / "empleados.csv"
SOLICITUDES_CSV = DATA_DIR / "solicitudes.csv"
FERIADOS_CSV = DATA_DIR / "feriados.csv"

LIMITE_DIAS_AUTO = 5
MAX_REINTENTOS = 3


# ============================================================
# CAPA DE PERSISTENCIA  (simula la BD: lee y escribe los CSV)
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
    """Devuelve un date si el texto es una fecha valida, o None."""
    texto = (texto or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def calcular_dias_habiles(desde, hasta, feriados):
    """Cuenta dias habiles entre dos fechas inclusive, excluyendo fines de semana y feriados."""
    dias = 0
    cur = desde
    while cur <= hasta:
        if cur.weekday() < 5 and cur not in feriados:
            dias += 1
        cur += timedelta(days=1)
    return dias


def hay_solapamiento(legajo, desde, hasta):
    """True si el empleado ya tiene una solicitud APROBADA o PENDIENTE que se cruza."""
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
# INTERFAZ (capa de presentacion del bot)
# ============================================================

def bot(msg):
    print(f"[BOT] {msg}")


def pedir(prompt):
    try:
        return input(f"[TU] {prompt} ").strip()
    except EOFError:
        return ""


def pedir_con_reintentos(prompt, validar, mensaje_error):
    """Pide entrada hasta MAX_REINTENTOS veces. Devuelve None si se agotan."""
    for intento in range(1, MAX_REINTENTOS + 1):
        valor = pedir(prompt)
        if valor.lower() in ("salir", "cancelar", "/cancelar"):
            return "__CANCEL__"
        resultado = validar(valor)
        if resultado is not None:
            return resultado
        restantes = MAX_REINTENTOS - intento
        if restantes > 0:
            bot(f"{mensaje_error} Te quedan {restantes} intento(s). "
                f"Escribi 'cancelar' para volver al menu.")
        else:
            bot("Se agotaron los intentos. Vuelvo al menu principal.")
    return None


# ============================================================
# MAQUINA DE ESTADOS - refleja los pasos del BPMN
# ============================================================

ESTADOS = {
    "INICIO": "Saludo y pedido de identificacion",
    "AUTENTICADO": "Menu principal disponible",
    "SOLICITANDO_DESDE": "Esperando fecha de inicio",
    "SOLICITANDO_HASTA": "Esperando fecha de fin",
    "VALIDANDO": "Sistema validando saldo y solapamientos",
    "CONFIRMANDO": "Esperando confirmacion del usuario",
    "DERIVADO_SUPERVISOR": "Solicitud derivada por superar el limite automatico",
    "FIN": "Sesion finalizada",
}


class Sesion:
    """Encapsula la memoria del bot para cada usuario (Maquina de Estados)."""

    def __init__(self):
        self.estado = "INICIO"
        self.empleado = None
        self.draft = {}  # datos parciales de la solicitud en curso

    def set_estado(self, nuevo):
        self.estado = nuevo


# ============================================================
# FLUJOS (cada bloque corresponde a una tarea/gateway del BPMN)
# ============================================================

def flujo_autenticacion(sesion):
    bot("Hola, soy VacaBot. Te ayudo a gestionar tus vacaciones.")
    bot("En cualquier momento podes escribir 'salir' para terminar o "
        "'cancelar' para volver al menu.")

    def validar_legajo(v):
        if not v.isdigit():
            return None
        emp = buscar_empleado(v)
        return emp if emp else None

    emp = pedir_con_reintentos(
        "Ingresa tu numero de legajo:",
        validar_legajo,
        "Legajo invalido o inexistente.",
    )
    if emp in (None, "__CANCEL__"):
        sesion.set_estado("FIN")
        return
    sesion.empleado = emp
    sesion.set_estado("AUTENTICADO")
    bot(f"Bienvenido/a {emp['nombre']} {emp['apellido']} "
        f"(area: {emp['area']}, saldo actual: {emp['dias_disponibles']} dias).")


def mostrar_menu():
    print("\n--- MENU ---")
    print(" 1) Solicitar vacaciones")
    print(" 2) Consultar saldo de dias")
    print(" 3) Ver mis solicitudes")
    print(" 4) Salir")


def flujo_menu(sesion):
    mostrar_menu()
    opcion = pedir("Elegi una opcion (1-4):")
    if opcion == "1":
        sesion.set_estado("SOLICITANDO_DESDE")
        flujo_solicitar(sesion)
    elif opcion == "2":
        flujo_consultar_saldo(sesion)
    elif opcion == "3":
        flujo_ver_solicitudes(sesion)
    elif opcion in ("4", "salir"):
        sesion.set_estado("FIN")
    else:
        bot("Opcion no valida. Elegi un numero del 1 al 4.")


def flujo_consultar_saldo(sesion):
    emp = buscar_empleado(sesion.empleado["legajo"])
    sesion.empleado = emp
    bot(f"Tu saldo actual es de {emp['dias_disponibles']} dia(s) habiles.")


def flujo_ver_solicitudes(sesion):
    mias = [s for s in leer_solicitudes()
            if s["legajo"] == sesion.empleado["legajo"]]
    if not mias:
        bot("No tenes solicitudes registradas todavia.")
        return
    bot(f"Tenes {len(mias)} solicitud(es) registrada(s):")
    for s in mias:
        linea = (f"  - {s['id_solicitud']} | {s['fecha_desde']} a "
                 f"{s['fecha_hasta']} | {s['cantidad_dias']} dias | "
                 f"{s['estado']}")
        if s["motivo_rechazo"]:
            linea += f" ({s['motivo_rechazo']})"
        print(linea)


def flujo_solicitar(sesion):
    """Flujo principal: refleja las tareas y gateways del BPMN."""
    bot("Vamos a registrar una nueva solicitud de vacaciones.")
    hoy = datetime.now().date()

    # --- Tarea Usuario: fecha desde ---
    def validar_desde(v):
        d = parsear_fecha(v)
        if d is None:
            return None
        if d < hoy:
            return None
        return d

    desde = pedir_con_reintentos(
        "Fecha de INICIO (formato YYYY-MM-DD o DD/MM/YYYY):",
        validar_desde,
        "Fecha invalida o anterior a hoy.",
    )
    if desde in (None, "__CANCEL__"):
        sesion.set_estado("AUTENTICADO")
        return

    sesion.draft["desde"] = desde
    sesion.set_estado("SOLICITANDO_HASTA")

    # --- Tarea Usuario: fecha hasta ---
    def validar_hasta(v):
        d = parsear_fecha(v)
        if d is None:
            return None
        if d < desde:
            return None
        return d

    hasta = pedir_con_reintentos(
        "Fecha de FIN (debe ser igual o posterior a la de inicio):",
        validar_hasta,
        "Fecha invalida o anterior a la fecha de inicio.",
    )
    if hasta in (None, "__CANCEL__"):
        sesion.set_estado("AUTENTICADO")
        return

    sesion.draft["hasta"] = hasta
    sesion.set_estado("VALIDANDO")

    # --- Tarea Sistema: calcular dias habiles ---
    feriados = leer_feriados()
    dias = calcular_dias_habiles(desde, hasta, feriados)
    bot(f"El periodo abarca {dias} dia(s) habil(es) "
        f"(se excluyen fines de semana y feriados).")

    if dias == 0:
        bot("El rango seleccionado no tiene dias habiles. Cancelo la solicitud.")
        sesion.set_estado("AUTENTICADO")
        return

    # --- GATEWAY 1: tiene saldo suficiente? ---
    emp_actual = buscar_empleado(sesion.empleado["legajo"])
    saldo = int(emp_actual["dias_disponibles"])
    if dias > saldo:
        bot(f"No tenes saldo suficiente. Pedis {dias} dias y tenes {saldo}.")
        bot("La solicitud se registra como RECHAZADA automaticamente.")
        guardar_solicitud({
            "id_solicitud": proximo_id(),
            "legajo": sesion.empleado["legajo"],
            "fecha_solicitud": hoy.isoformat(),
            "fecha_desde": desde.isoformat(),
            "fecha_hasta": hasta.isoformat(),
            "cantidad_dias": str(dias),
            "estado": "RECHAZADA",
            "motivo_rechazo": "Sin saldo de dias disponibles",
        })
        sesion.set_estado("AUTENTICADO")
        return

    # --- GATEWAY 2: hay solapamiento con otra solicitud? ---
    if hay_solapamiento(sesion.empleado["legajo"], desde, hasta):
        bot("Ya tenes otra solicitud aprobada o pendiente en ese rango.")
        bot("La solicitud queda RECHAZADA por solapamiento.")
        guardar_solicitud({
            "id_solicitud": proximo_id(),
            "legajo": sesion.empleado["legajo"],
            "fecha_solicitud": hoy.isoformat(),
            "fecha_desde": desde.isoformat(),
            "fecha_hasta": hasta.isoformat(),
            "cantidad_dias": str(dias),
            "estado": "RECHAZADA",
            "motivo_rechazo": "Solapamiento con otra solicitud",
        })
        sesion.set_estado("AUTENTICADO")
        return

    # --- Tarea Usuario: confirmar ---
    sesion.set_estado("CONFIRMANDO")
    bot(f"Resumen: del {desde} al {hasta} ({dias} dias habiles). "
        "Saldo restante quedaria en "
        f"{saldo - dias}.")
    conf = pedir("Confirmas? (si/no):").lower()
    if conf not in ("si", "s", "yes", "y"):
        bot("Solicitud cancelada por el usuario.")
        sesion.set_estado("AUTENTICADO")
        return

    # --- GATEWAY 3: aprobacion automatica o derivacion al supervisor ---
    nuevo_id = proximo_id()
    if dias <= LIMITE_DIAS_AUTO:
        # Tarea Sistema: aprobar y descontar saldo
        guardar_solicitud({
            "id_solicitud": nuevo_id,
            "legajo": sesion.empleado["legajo"],
            "fecha_solicitud": hoy.isoformat(),
            "fecha_desde": desde.isoformat(),
            "fecha_hasta": hasta.isoformat(),
            "cantidad_dias": str(dias),
            "estado": "APROBADA",
            "motivo_rechazo": "",
        })
        actualizar_dias(sesion.empleado["legajo"], saldo - dias)
        bot(f"Solicitud {nuevo_id} APROBADA automaticamente. "
            f"Saldo restante: {saldo - dias} dias.")
    else:
        # Tarea Sistema: dejar pendiente para supervisor
        sup = buscar_empleado(emp_actual["supervisor"])
        sesion.set_estado("DERIVADO_SUPERVISOR")
        guardar_solicitud({
            "id_solicitud": nuevo_id,
            "legajo": sesion.empleado["legajo"],
            "fecha_solicitud": hoy.isoformat(),
            "fecha_desde": desde.isoformat(),
            "fecha_hasta": hasta.isoformat(),
            "cantidad_dias": str(dias),
            "estado": "PENDIENTE",
            "motivo_rechazo": "",
        })
        nombre_sup = f"{sup['nombre']} {sup['apellido']}" if sup else "tu supervisor"
        bot(f"Solicitud {nuevo_id} supera el limite de {LIMITE_DIAS_AUTO} dias "
            f"de aprobacion automatica. Queda PENDIENTE de aprobacion "
            f"de {nombre_sup}.")

    sesion.set_estado("AUTENTICADO")


# ============================================================
# ORQUESTADOR PRINCIPAL
# ============================================================

def main():
    print("=" * 60)
    print("  TPI Organizacion Empresarial - UTN TUPaD")
    print("  Chatbot Simulado - Gestion de Vacaciones")
    print("=" * 60)

    sesion = Sesion()
    flujo_autenticacion(sesion)

    while sesion.estado != "FIN":
        try:
            flujo_menu(sesion)
        except KeyboardInterrupt:
            print()
            bot("Interrupcion detectada, cierro la sesion.")
            sesion.set_estado("FIN")
        except Exception as e:
            bot(f"Ocurrio un error inesperado: {e}. Vuelvo al menu.")
            sesion.set_estado("AUTENTICADO")

    bot("Hasta luego. Sesion finalizada.")


if __name__ == "__main__":
    main()
