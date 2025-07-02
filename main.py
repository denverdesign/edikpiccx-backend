
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import time

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
app = FastAPI(title="Centro de Operaciones de Agentes v4.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA MEJORADA ---
# Guardaremos más que solo el websocket
# Formato: { "device_id": {"ws": ws_obj, "name": "...", "connect_time": timestamp} }
connected_agents: Dict[str, dict] = {}

# Una lista para registrar los últimos 20 eventos importantes (errores, conexiones, etc.)
server_events: List[Dict] = []

# --- FUNCIÓN DE AYUDA PARA LOGS ---
def log_event(event_type: str, message: str, device_id: str = None):
    """Añade un evento a nuestra lista en memoria con timestamp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = {"timestamp": timestamp, "type": event_type, "message": message, "device_id": device_id}
    print(f"[{event_type.upper()}] {message}")
    server_events.insert(0, log_entry) # Insertamos al principio
    # Mantenemos la lista con un tamaño manejable
    if len(server_events) > 20:
        server_events.pop()

# --- MODELOS DE DATOS ---
class Command(BaseModel): # ... (sin cambios)
class Thumbnail(BaseModel): # ... (sin cambios)
class ErrorLog(BaseModel):
    error: str

# --- ENDPOINTS (RUTAS DE LA API) ---

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    await websocket.accept()
    log_event("CONNECT", f"Agente conectado: '{device_name}'", device_id)
    connected_agents[device_id] = {"ws": websocket, "name": device_name, "connect_time": time.time()}
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        log_event("DISCONNECT", f"Agente desconectado: '{name_to_print}'", device_id)
        if device_id in connected_agents: del connected_agents[device_id]


# --- NUEVO ENDPOINT DE DIAGNÓSTICO ---
@app.get("/api/health_check")
async def health_check():
    """
    Devuelve un informe completo del estado del sistema:
    - Estado del servidor ("Activo" o "Dormido" - simulado).
    - Lista de agentes conectados.
    - Log de los últimos eventos.
    """
    return {
        "server_status": "Activo", # Si esta ruta responde, el servidor está activo.
        "server_time_utc": datetime.utcnow().isoformat(),
        "connected_agents": [
            {"id": dev_id, "name": data["name"]} for dev_id, data in connected_agents.items()
        ],
        "recent_events": server_events
    }

# --- Ruta para que los agentes reporten sus errores ---
@app.post("/api/log_error/{device_id}")
async def log_error_from_agent(device_id: str, error_log: ErrorLog):
    log_event("AGENT_ERROR", error_log.error, device_id)
    return {"status": "log recibido"}

# El resto de las rutas no cambian, pero ahora usan log_event
@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    target_id = command.target_id
    if target_id not in connected_agents:
        log_event("ERROR", f"Intento de enviar comando a un agente no conectado: {target_id}")
        return {"status": "error", "message": "Agente no conectado."}
    try:
        agent_socket = connected_agents[target_id]["ws"]
        await agent_socket.send_text(command.json())
        log_event("COMMAND", f"Comando '{command.action}' enviado a '{connected_agents[target_id]['name']}'", target_id)
        return {"status": "success", "message": "Comando enviado."}
    except Exception as e:
        log_event("ERROR", f"Fallo al enviar comando a {target_id}: {e}", target_id)
        return {"status": "error", "message": "Fallo de comunicación."}

# Las rutas de miniaturas no necesitan grandes cambios
@app.post("/api/submit_media_list/{device_id}") # ... (sin cambios)
@app.get("/api/get_media_list/{device_id}") # ... (sin cambios)

log_event("STARTUP", "El servidor se ha iniciado correctamente.")
