
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
from fastapi.encoders import jsonable_encoder

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = FastAPI(title="Agente Control Backend vFINAL")

# Configuración de CORS para permitir conexiones desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, dict] = {}
device_thumbnails_cache: Dict[str, list] = {}

# --- MODELOS DE DATOS ---
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
    print(f"[CONEXIÓN] Agente conectado: '{device_name}' (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "name": device_name}
    try:
        while True:
            data = await websocket.receive_text()
            print(f"[MENSAJE] De {device_id}: {data}")
    except WebSocketDisconnect:
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        print(f"[DESCONEXIÓN] Agente desconectado: '{name_to_print}'")
        connected_agents.pop(device_id, None)
        device_thumbnails_cache.pop(device_id, None)


@app.get("/api/get-agents")
async def get_agents():
    """Devuelve la lista de agentes actualmente conectados."""
    agent_list = [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]
    return agent_list


@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    """Recibe un comando del panel y se lo reenvía al agente correcto."""
    target_id = command.target_id
    if target_id not in connected_agents:
        return {"status": "error", "message": "Agente no conectado."}
    try:
        await connected_agents[target_id]["ws"].send_text(command.json())
        return {"status": "success", "message": "Comando enviado."}
    except WebSocketDisconnect:
        return {"status": "error", "message": "Agente desconectado. WebSocket falló."}
    except Exception as e:
        print(f"[ERROR] Fallo al enviar comando a {target_id}: {e}")
        return {"status": "error", "message": f"Fallo de comunicación con el agente: {str(e)}"}


@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    """Ruta para que el agente envíe la lista de sus miniaturas."""
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    device_thumbnails_cache[device_id] = jsonable_encoder(thumbnails)
    return {"status": "success"}


@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    """Ruta para que el panel pida la lista de miniaturas de un dispositivo."""
    return device_thumbnails_cache.get(device_id, [])


@app.post("/api/log_error/{device_id}")
async def log_error_from_agent(device_id: str, error_log: ErrorLog):
    """Ruta para que los agentes reporten errores para depuración remota."""
    print(f"[ERROR REMOTO] Dispositivo {device_id[:8]}: {error_log.error}")
    return {"status": "log recibido"}

@app.get("/")
def read_root():
    return {"status": "API backend funcionando correctamente"}

