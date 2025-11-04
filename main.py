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
    # ... (Esta función se queda igual)
    pass
@app.get("/api/get-agents")
async def get_agents():
    # ... (Esta función se queda igual)
    pass
@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    # ... (Esta función se queda igual)
    pass
@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    # ... (Esta función se queda igual)
    pass
@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    # ... (Esta función se queda igual)
    pass
@app.post("/api/set_daily_message/{device_id}")
async def set_daily_message(device_id: str, data: dict):
    # ... (Esta función se queda igual)
    pass
@app.get("/api/get_daily_message/{device_id}")
async def get_daily_message(device_id: str):
    # ... (Esta función se queda igual)
    pass
@app.post("/api/broadcast_message")
async def broadcast_message(data: BroadcastMessage):
    # ... (Esta función se queda igual)
    pass

# --- ¡RUTAS RESTAURADAS PARA LA VISTA MAXIMIZADA! ---
@app.post("/api/upload_original_file/{device_id}/{filename:path}")
async def upload_original_file(device_id: str, filename: str, file: UploadFile = File(...)):
    decoded_filename = unquote(filename)
    if device_id not in device_media_cache or decoded_filename not in device_media_cache[device_id]:
        return Response(content="Archivo no solicitado", status_code=400)
    
    file_bytes = await file.read()
    original_b64 = base64.b64encode(file_bytes).decode('utf-8')
    device_media_cache[device_id][decoded_filename]['original_b64'] = original_b64
    
    print(f"Recibido archivo original '{decoded_filename}' de {device_id[:8]}.")
    return {"status": "success"}

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    decoded_filename = unquote(filename)
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(decoded_filename)
    
    if not media_item or 'original_b64' not in media_item:
        return Response(content='{"detail":"Not Found"}', status_code=404, media_type="application/json")
    
    try:
        file_bytes = base64.b64decode(media_item['original_b64'])
        media_type = "image/jpeg"
        return Response(content=file_bytes, media_type=media_type)
    except Exception as e:
        return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500, media_type="application/json")
