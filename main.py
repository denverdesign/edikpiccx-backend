from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()

# Diccionario para mantener un registro de los agentes conectados.
# Clave: device_id, Valor: { "name": device_name, "ws": websocket_object }
connected_agents: dict[str, dict] = {}

# Endpoint para que TU PANEL DE CONTROL PYTHON pida la lista de agentes
@app.get("/api/get-agents")
async def get_agents():
    """Devuelve una lista simple de los agentes conectados."""
    return [{"id": id, "name": data["name"]} for id, data in connected_agents.items()]

# Endpoint para que TU PANEL DE CONTROL PYTHON envíe un comando
@app.post("/api/send-command")
async def send_command(command: dict):
    """Recibe un comando y lo reenvía al agente correcto vía WebSocket."""
    target_id = command.get("target_id")
    if not target_id or target_id not in connected_agents:
        return {"status": "error", "message": "Agente no encontrado"}
    
    agent_socket = connected_agents[target_id]["ws"]
    try:
        await agent_socket.send_text(json.dumps(command))
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e:
        return {"status": "error", "message": f"Fallo al enviar: {e}"}

# Endpoint para que los AGENTES ANDROID se conecten
@app.websocket("/ws/{device_id}/{device_name}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    """Mantiene la conexión WebSocket abierta con los agentes."""
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: {device_name} (ID: {device_id})")
    connected_agents[device_id] = {"name": device_name, "ws": websocket}
    
    try:
        while True:
            await websocket.receive_text() # Espera pasivamente
    except WebSocketDisconnect:
        print(f"[DESCONEXIÓN] Agente desconectado: {device_name} (ID: {device_id})")
        del connected_agents[device_id]