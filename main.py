import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = FastAPI(title="Agente Control Backend")

# Configuración de CORS para permitir conexiones desde cualquier origen (importante para Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
# Diccionario para mantener los agentes conectados.
# Formato: { "device_id": {"ws": websocket_object, "name": "device_name"} }
connected_agents: dict[str, dict] = {}

# Diccionario para la caché temporal de las miniaturas.
# Formato: { "device_id": [ {"filename": "...", "thumbnail_b64": "..."} ] }
device_thumbnails_cache: dict[str, list] = {}


# --- MODELOS DE DATOS (para validación) ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str

class Thumbnail(BaseModel):
    filename: str
    thumbnail_b64: str


# --- ENDPOINTS (RUTAS DE LA API) ---

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    """
    Punto de entrada para que los agentes Android se conecten.
    Mantiene la conexión abierta y gestiona las desconexiones.
    """
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: '{device_name}' (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "name": device_name}
    
    try:
        # Mantenemos la conexión viva esperando cualquier mensaje (o desconexión)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Si el agente se desconecta, lo eliminamos de nuestras listas
        print(f"[DESCONEXIÓN] Agente desconectado: '{device_name}' (ID: {device_id})")
        if device_id in connected_agents:
            del connected_agents[device_id]
        if device_id in device_thumbnails_cache:
            del device_thumbnails_cache[device_id]


@app.get("/api/get-agents")
async def get_agents():
    """Devuelve la lista de agentes actualmente conectados al panel de control."""
    if not connected_agents:
        return []
    # Creamos una lista limpia con la información que el panel necesita
    agent_list = [
        {"id": device_id, "name": data["name"]}
        for device_id, data in connected_agents.items()
    ]
    print(f"Panel solicitó la lista. Agentes conectados: {len(agent_list)}")
    return agent_list


@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    """Recibe un comando del panel y se lo reenvía al agente correcto."""
    target_id = command.target_id
    if target_id not in connected_agents:
        return {"status": "error", "message": "Agente no encontrado o no conectado."}
    
    try:
        agent_socket = connected_agents[target_id]["ws"]
        await agent_socket.send_text(command.json())
        print(f"Comando '{command.action}' enviado a '{connected_agents[target_id]['name']}'")
        return {"status": "success", "message": "Comando enviado."}
    except Exception as e:
        print(f"[ERROR] Fallo al enviar comando a {target_id}: {e}")
        return {"status": "error", "message": "Fallo de comunicación con el agente."}


@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    """Ruta para que el agente envíe la lista de sus miniaturas."""
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    
    print(f"Recibidas {len(thumbnails)} miniaturas del agente '{connected_agents[device_id]['name']}'")
    # Guardamos la lista en nuestra caché temporal
    device_thumbnails_cache[device_id] = [thumb.dict() for thumb in thumbnails]
    return {"status": "success"}


@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    """Ruta para que el panel pida la lista de miniaturas de un dispositivo."""
    print(f"Panel pide la lista de medios para el agente con ID: {device_id[:8]}...")
    # Devolvemos la lista desde la caché, o una lista vacía si no existe
    return device_thumbnails_cache.get(device_id, [])
