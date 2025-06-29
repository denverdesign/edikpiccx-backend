from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import json

app = FastAPI()

# --- Diccionarios en memoria para guardar el estado ---
# Guarda los agentes conectados y sus detalles
connected_agents: dict[str, dict] = {}
# Guarda las listas de miniaturas que envían los agentes
device_media_cache: dict[str, list] = {}


# --- Modelo Pydantic para validar los datos de las miniaturas ---
# Esto asegura que los datos que llegan del agente tienen la estructura correcta
class Thumbnail(BaseModel):
    filename: str
    thumbnail_b64: str


# --- Rutas de la API (las "oficinas" de nuestro servidor) ---

@app.get("/api/get-agents")
async def get_agents():
    """
    Endpoint para que el Panel de Control pida la lista de agentes conectados.
    Devuelve una lista de los detalles de cada agente.
    """
    return [agent_data.get("details", {}) for agent_data in connected_agents.values()]

@app.post("/api/send-command")
async def send_command(command: dict):
    """
    Endpoint para que el Panel de Control envíe un comando a un agente específico.
    Recibe el comando y lo reenvía por el WebSocket correcto.
    """
    target_id = command.get("target_id")
    if not target_id or target_id not in connected_agents:
        return {"status": "error", "message": "Agente no conectado"}
    try:
        await connected_agents[target_id]["ws"].send_text(json.dumps(command))
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e:
        return {"status": "error", "message": f"Fallo al enviar: {e}"}

@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, media_list: list[Thumbnail]):
    """
    Endpoint para que el AGENTE envíe la lista de sus archivos y miniaturas.
    Las guarda en la caché temporal.
    """
    print(f"Recibida lista de medios ({len(media_list)} archivos) del dispositivo {device_id}")
    # Guardamos los datos en la caché, convirtiendo los objetos Pydantic a diccionarios
    device_media_cache[device_id] = [item.dict() for item in media_list]
    return {"status": "success", "message": f"{len(media_list)} items recibidos."}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    """
    Endpoint para que el PANEL DE CONTROL pida la lista de medios de un dispositivo.
    Devuelve la lista desde la caché.
    """
    print(f"Panel de control pide la lista de medios para {device_id}")
    return device_media_cache.get(device_id, [])


# --- WebSocket Endpoint (La "puerta de entrada" para los agentes) ---
# Esta es la versión que espera el ID y el Nombre en la URL.
@app.websocket("/ws/{device_id}/{device_name}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    """
    Mantiene la conexión WebSocket abierta con los agentes y guarda sus detalles.
    """
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: {device_name} (ID: {device_id})")
    
    # Guardamos la conexión y los detalles directamente desde la URL
    connected_agents[device_id] = {
        "ws": websocket,
        "details": {"id": device_id, "name": device_name}
    }
    
    try:
        # Mantenemos la conexión viva esperando cualquier mensaje o la desconexión
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Si el agente se desconecta, lo eliminamos de la lista
        name_to_log = connected_agents.get(device_id, {}).get("details", {}).get("name", device_id)
        print(f"[DESCONEXIÓN] Agente desconectado: {name_to_log}")
        if device_id in connected_agents:
            del connected_agents[device_id]
        if device_id in device_media_cache:
            del device_media_cache[device_id] # Limpiamos también su caché de miniaturas
