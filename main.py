from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware  # <-- NUEVA IMPORTACIÓN
import json

app = FastAPI()

# --- NUEVA SECCIÓN DE CONFIGURACIÓN DE SEGURIDAD ---
# Definimos los orígenes permitidos. El asterisco "*" significa "cualquiera".
# Esto le dice a FastAPI que acepte conexiones de cualquier fuente.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- FIN DE LA NUEVA SECCIÓN ---


# El diccionario para la información de los agentes
connected_agents: dict[str, dict] = {}

# --- EL RESTO DEL CÓDIGO NO CAMBIA ---

@app.get("/api/get-agents")
async def get_agents():
    return [agent_data["details"] for agent_data in connected_agents.values() if "details" in agent_data]

@app.post("/api/send-command")
async def send_command(command: dict):
    target_id = command.get("target_id")
    if not target_id or target_id not in connected_agents:
        return {"status": "error", "message": "Agente no conectado"}
    
    agent_socket = connected_agents[target_id]["ws"]
    try:
        await agent_socket.send_text(json.dumps(command))
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e:
        return {"status": "error", "message": f"Fallo al enviar: {e}"}

@app.websocket("/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    await websocket.accept()
    connected_agents[device_id] = {"ws": websocket}
    try:
        device_info_json = await websocket.receive_text()
        device_details = json.loads(device_info_json)
        connected_agents[device_id]["details"] = device_details
        print(f"[CONEXIÓN] Agente presentado: {device_details.get('name')}")
        while True:
            response_from_agent = await websocket.receive_text()
            data = json.loads(response_from_agent)
            if data.get("type") == "image_list":
                print(f"Recibidas {len(data.get('images', []))} imágenes del agente {device_id}")
                if "details" in connected_agents[device_id]:
                    connected_agents[device_id]["details"]["images"] = data.get("images", [])
    except WebSocketDisconnect:
        name = connected_agents.get(device_id, {}).get("details", {}).get("name", "ID: " + device_id)
        print(f"[DESCONEXIÓN] Agente desconectado: {name}")
        if device_id in connected_agents:
            del connected_agents[device_id]
