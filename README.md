# TPI Organización Empresarial — VacaBot (Web)

Trabajo Práctico Integrador — UTN TUPaD — Cátedra Organización Empresarial.

Simulación de un chatbot administrativo que automatiza el proceso de
**solicitud de vacaciones**. La lógica responde a un modelo **BPMN 2.0**
con carriles (Usuario / Sistema / Supervisor) y tres compuertas
exclusivas (saldo de días, solapamiento, límite para aprobación
automática).

> No usa un servicio de IA real: es una **simulación** estructurada
> como máquina de estados, según lo permite la consigna del TPI.

## Stack

- **Lenguaje:** Python 3
- **Plataforma:** Aplicación web sobre **Flask 3** (mini-server local)
- **Front-end:** HTML + CSS + JavaScript (fetch a la API)
- **Persistencia:** archivos CSV en `data/` que simulan la base de datos

## Estructura del repositorio

```
proyecto/
├── app.py              # Servidor Flask (rutas / y /api/chat)
├── bot_core.py         # Lógica de negocio (máquina de estados, gateways)
├── chatbot.py          # Versión CLI (alternativa de prueba)
├── generar_bpmn.py     # Genera los BPMN as-is y to-be (PDF + PNG)
├── generar_mockup.py   # Genera la captura del chat (PDF + PNG)
├── templates/
│   └── chat.html       # Vista del chat
├── static/
│   └── style.css       # Estilos de la UI
├── data/
│   ├── empleados.csv   # Empleados, saldos y supervisores
│   ├── solicitudes.csv # Historial de solicitudes
│   └── feriados.csv    # Feriados nacionales
├── bpmn/
│   └── diagramas_bpmn.pdf  # PDF vectorial con AS-IS (p.1) y TO-BE (p.2)
└── img/                    # Mismos diagramas en PNG (embebidos en el informe)
    ├── bpmn_as_is.png
    ├── bpmn_to_be.png
    └── chatbot_mockup.png
```

## Cómo correrlo

Requiere Python 3.9+ y Flask:

```bash
pip install flask
cd proyecto
python3 app.py
```

Luego abrir el navegador en **http://127.0.0.1:5050/**.

Si preferís ver el mismo bot en consola para debug:

```bash
python3 chatbot.py
```

## Legajos de prueba

| Legajo | Empleado          | Saldo | Caso que ilustra              |
|--------|-------------------|-------|-------------------------------|
| 1001   | Franco Aglieri    | 14    | Camino feliz / derivación     |
| 1003   | Lucas Pérez       | 0     | Rechazo por sin saldo         |
| 1004   | Sofía Martínez    | 21    | Derivación al supervisor (>5) |
| 1002   | María Gómez       | 7     | Solapamiento con S0003        |

## Comandos especiales del bot

- `salir` — termina la sesión.
- `cancelar` — vuelve al menú principal desde un sub-flujo.
- Botón ⟲ en la cabecera — reinicia la conversación en la UI web.

## API

| Método | Ruta         | Descripción                                      |
|--------|--------------|--------------------------------------------------|
| GET    | `/`          | Sirve la vista del chat                          |
| POST   | `/api/chat`  | Recibe `{mensaje}` y devuelve `{respuestas, estado, fin}` |
| POST   | `/api/reset` | Limpia la sesión y reinicia la conversación      |

## Documentación adicional

El informe PDF (`Aglieri_Franco_TPI_OE.pdf` en la raíz del repo) incluye
el análisis del proceso, los diagramas BPMN AS-IS y TO-BE, el
diccionario de datos, el manual de uso y las pruebas del camino infeliz.
