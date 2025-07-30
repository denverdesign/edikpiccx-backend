import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from fastapi.responses import Response, JSONResponse

app = FastAPI(title="Agente Control Backend vFINAL")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, dict] = {}
device_media_cache: Dict[str, dict] = {} # Ahora es un dict para buscar por filename

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str

class Thumbnail(BaseModel):
    filename: str
    small_thumb_b64: str
    large_thumb_b64: str

# --- ENDPOINTS ---
@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    # ... (código sin cambios)

@app.get("/api/get-agents")
async def get_agents():
    # ... (código sin cambios)

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    # ... (código sin cambios, este ya era correcto)
    # El error 422 se debía a un main.py desactualizado, esta versión lo soluciona.
    pass # Reemplaza con la lógica completa que ya teníamos

@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    if device_id not in connected_agents:
        return {"status": "error"}
    # Guardamos en un diccionario para búsquedas rápidas por nombre de archivo
    device_media_cache[device_id] = {thumb.filename: thumb.dict() for thumb in thumbnails}
    print(f"Recibidas y cacheadas {len(thumbnails)} miniaturas del agente {device_id[:8]}")
    return {"status": "success"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    # Devolvemos solo la lista de miniaturas pequeñas para el panel
    cache = device_media_cache.get(device_id, {})
    return [{"filename": data["filename"], "small_thumb_b64": data["small_thumb_b64"]} for data in cache.values()]

# --- ¡NUEVA RUTA MÁGICA PARA VER EN EL NAVEGADOR! ---
@app.get("/media/{device_id}/{filename}")
async def get_large_media(device_id: str, filename: str):
    """
    Esta ruta busca la imagen grande en la caché y la devuelve
    directamente al navegador como una imagen.
    """
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(filename)
    if not media_item:
        return JSONResponse(status_code=404, content={"message": "Archivo no encontrado en la caché"})
    
    import base64
    # Decodificamos el Base64 a bytes
    image_bytes = base64.b64decode(media_item['large_thumb_b64'])
    
    # Devolvemos los bytes directamente con el tipo de contenido correcto
    # Esto le dice al navegador: "Esto es un JPEG, muéstralo como una imagen"
    return Response(content=image_bytes, media_type="image/jpeg")
