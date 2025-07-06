from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import time

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = FastAPI(title="Agente Control Backend vFINAL")
@@ -19,10 +18,16 @@
)

# --- "BASE DE DATOS" EN MEMORIA ---
# Diccionario para mantener los agentes conectados.
# Formato: { "device_id": {"ws": websocket_object, "name": "device_name"} }
connected_agents: Dict[str, dict] = {}

# Diccionario para la caché temporal de las miniaturas.
# Formato: { "device_id": [ {"filename": "...", "thumbnail_b64": "..."} ] }
device_thumbnails_cache: Dict[str, list] = {}

# --- MODELOS DE DATOS ---

# --- MODELOS DE DATOS (para validación automática) ---
class Command(BaseModel):
    target_id: str
    action: str
@@ -35,18 +40,24 @@ class Thumbnail(BaseModel):
class ErrorLog(BaseModel):
    error: str


# --- ENDPOINTS (RUTAS DE LA API) ---

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    """
    Punto de entrada para que los agentes Android se conecten.
    Acepta la conexión, la registra y la mantiene abierta.
    """
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: '{device_name}' (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "name": device_name}
    try:
        # Mantenemos la conexión viva esperando a que se desconecte.
        # Mantenemos la conexión viva esperando a que el cliente se desconecte.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Si el agente se desconecta, lo eliminamos de nuestras listas para mantener todo limpio.
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        print(f"[DESCONEXIÓN] Agente desconectado: '{name_to_print}'")
        if device_id in connected_agents:
@@ -57,7 +68,7 @@ async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name:

@app.get("/api/get-agents")
async def get_agents():
    """Devuelve la lista de agentes actualmente conectados."""
    """Devuelve la lista de agentes actualmente conectados para el panel de control."""
    if not connected_agents:
        return []
    agent_list = [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]
@@ -66,30 +77,36 @@ async def get_agents():

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    """Recibe un comando del panel y se lo reenvía al agente correcto."""
    """Recibe un comando del panel y se lo reenvía al agente correcto vía WebSocket."""
    target_id = command.target_id
    if target_id not in connected_agents:
        return {"status": "error", "message": "Agente no conectado."}
    try:
        await connected_agents[target_id]["ws"].send_text(command.json())
        print(f"Comando '{command.action}' enviado a '{connected_agents[target_id]['name']}'")
        return {"status": "success", "message": "Comando enviado."}
    except Exception as e:
        print(f"[ERROR] Fallo al enviar comando a {target_id}: {e}")
        return {"status": "error", "message": "Fallo de comunicación."}
        return {"status": "error", "message": "Fallo de comunicación con el agente."}


@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    """Ruta para que el agente envíe la lista de sus miniaturas."""
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    
    # Guardamos la lista de miniaturas en nuestra caché temporal
    device_thumbnails_cache[device_id] = [thumb.dict() for thumb in thumbnails]
    print(f"Recibidas {len(thumbnails)} miniaturas del agente '{connected_agents.get(device_id, {}).get('name', 'Desconocido')}'")
    return {"status": "success"}


@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    """Ruta para que el panel pida la lista de miniaturas de un dispositivo."""
    print(f"Panel pide la lista de medios para el agente con ID: {device_id[:8]}...")
    # Devolvemos la lista desde la caché, o una lista vacía si no existe
    return device_thumbnails_cache.get(device_id, [])

