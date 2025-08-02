import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
app = FastAPI(title="Agente Control Backend (Corregido)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_thumbnails_cache: Dict[str, List[Dict[str, Any]]] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = "" # Hacemos el payload opcional por defecto

class Thumbnail(BaseModel):
    filename: str
    thumbnail_b64: str

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
            await websocket.receive_text() # Mantenemos la conexión abierta
    except WebSocketDisconnect:
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        print(f"[DESCONEXIÓN] Agente desconectado: '{name_to_print}'")
        if device_id in connected_agents:
            del connected_agents[device_id]
        if device_id in device_thumbnails_cache:
            del device_thumbnails_cache[device_id] # Buena práctica: limpiar también su caché

@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

# --- ¡ENDPOINT DE COMANDO MODIFICADO CON LÓGICA DE CACHÉ! ---
@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    agent = connected_agents.get(command.target_id)
    if not agent:
        return {"status": "error", "message": "Agente no conectado."}

    # <<< CORRECCIÓN DE LÓGICA DE CACHÉ >>>
    # Si la acción es pedir miniaturas, limpiamos la caché ANTES de enviar el comando.
    # Esto asegura que cada petición sea fresca.
    if command.action == "get_thumbnails":
        print(f"Limpiando caché antigua para el agente {command.target_id[:8]} antes de la nueva solicitud.")
        device_thumbnails_cache[command.target_id] = []

    try:
        await agent["ws"].send_text(command.json())
        return {"status": "success", "message": "Comando enviado."}
    except Exception as e:
        print(f"Error al enviar comando al agente {command.target_id}: {e}")
        return {"status": "error", "message": "Fallo al enviar el comando."}

# La ruta ya es correcta, no necesita cambios.
@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}

    # Gracias a la corrección de arriba, la caché ya debería estar inicializada y vacía.
    # Simplemente añadimos las miniaturas.
    if device_id not in device_thumbnails_cache:
        device_thumbnails_cache[device_id] = []

    device_thumbnails_cache[device_id].extend([thumb.dict() for thumb in chunk.thumbnails])
    
    print(f"Recibido lote de {len(chunk.thumbnails)} miniaturas de {device_id[:8]}. Total en caché: {len(device_thumbnails_cache.get(device_id, []))}")

    if chunk.is_final_chunk:
        print(f"Recepción de lotes para {device_id[:8]} completada.")

    return {"status": "chunk received"}


@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    return device_thumbnails_cache.get(device_id, [])

