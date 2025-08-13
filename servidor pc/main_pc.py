
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote

app = FastAPI(title="Agente PC - Backend (Flexible)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_media_cache: Dict[str, Dict[str, Any]] = {}
fetch_status: Dict[str, str] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = ""

# --- ¡MODELO MODIFICADO PARA SER MÁS FLEXIBLE! ---
class Thumbnail(BaseModel):
    filename: str
    small_thumb_b64: str
    # Heredamos de BaseModel, lo que nos permite añadir campos extra sin que Pydantic se queje.
    # Esto es una forma de hacerlo. La otra es usar un diccionario genérico.
    # Por ahora, vamos a simplificarlo aún más.

class ThumbnailChunk(BaseModel):
    # En lugar de una lista de 'Thumbnail', aceptamos una lista de diccionarios.
    # Esto hace que la validación sea mucho más flexible.
    thumbnails: List[Dict[str, Any]] 
    is_final_chunk: bool

# --- ENDPOINTS ---
# ... (El resto de las rutas @app.get, @app.post se quedan igual que en la versión que ya funciona) ...

# --- ¡RUTA MODIFICADA PARA ACEPTAR DATOS FLEXIBLES! ---
@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    if device_id not in device_media_cache:
        device_media_cache[device_id] = {}
    
    # Como ahora 'chunk.thumbnails' es una lista de diccionarios, podemos iterar directamente.
    for thumb_data in chunk.thumbnails:
        filename = thumb_data.get("filename")
        if filename:
            # Guardamos el diccionario completo, incluyendo el 'filepath' si viene.
            device_media_cache[device_id][filename] = thumb_data
            
    if chunk.is_final_chunk:
        fetch_status[device_id] = "complete"
        print(f"Recepción de lotes para {device_id[:8]} completada.")
    
    return {"status": "chunk received"}

# ... (El resto de tu main_pc.py completo y sin cambios)
