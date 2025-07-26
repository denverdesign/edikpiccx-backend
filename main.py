# main.py (Versión Final para FastAPI v2.1)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import json
import asyncio

app = FastAPI(title="Agente Control Backend vFINAL")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_agents: Dict[str, WebSocket] = {}
        self.active_panels: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, client_id: str, client_type: str):
        await websocket.accept()
        if client_type == "agent":
            self.active_agents[client_id] = websocket
            print(f"[AGENTE CONECTADO] {client_id}")
            await self.broadcast_agent_list()
        else: # Es un panel
            self.active_panels.append(websocket)
            print(f"[PANEL CONECTADO] Nuevo panel de control.")
            # Enviamos la lista actual al panel que acaba de conectarse
            await self.send_agent_list(websocket)

    async def disconnect(self, websocket: WebSocket, client_id: str, client_type: str):
        if client_type == "agent":
            if client_id in self.active_agents:
                del self.active_agents[client_id]
            print(f"[AGENTE DESCONECTADO] {client_id}")
            await self.broadcast_agent_list()
        else: # Es un panel
            if websocket in self.active_panels:
                self.active_panels.remove(websocket)
            print(f"[PANEL DESCONECTADO] Un panel se ha desconectado.")

    async def send_to_agent(self, message: str, client_id: str):
        if client_id in self.active_agents:
            await self.active_agents[client_id].send_text(message)
    
    async def broadcast_to_panels(self, message: str):
        for connection in self.active_panels:
            await connection.send_text(message)

    async def send_agent_list(self, websocket: WebSocket):
        agent_list = [{"id": client_id, "name": client_id.split('_')[0]} for client_id in self.active_agents.keys()]
        await websocket.send_text(json.dumps({"event": "agent_list_updated", "data": agent_list}))

    async def broadcast_agent_list(self):
        agent_list = [{"id": client_id, "name": client_id.split('_')[0]} for client_id in self.active_agents.keys()]
        await self.broadcast_to_panels(json.dumps({"event": "agent_list_updated", "data": agent_list}))

manager = ConnectionManager()

@app.get("/")
def read_root():
    return {"Status": "Servidor Backend Activo"}

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_agent_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    client_id = f"{device_name}_{device_id}"
    await manager.connect(websocket, client_id, "agent")
    try:
        while True:
            data = await websocket.receive_json()
            # Reenviamos los datos del agente a los paneles
            data_for_panel = {'agent_id': client_id, 'agent_name': device_name, **data}
            await manager.broadcast_to_panels(json.dumps({"event": "data_from_agent", "data": data_for_panel}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id, "agent")

@app.websocket("/ws/panel/control")
async def websocket_panel_endpoint(websocket: WebSocket):
    await manager.connect(websocket, "panel", "panel")
    try:
        while True:
            await websocket.receive_text() # Mantenemos la conexión viva
    except WebSocketDisconnect:
        manager.disconnect(websocket, "panel", "panel")

@app.get("/api/get-agents")
async def get_agents():
    agent_list = [{"id": client_id, "name": client_id.split('_')[0]} for client_id in manager.active_agents.keys()]
    return agent_list

@app.post("/api/send-command")
async def send_command_to_agent(command: Dict[str, Any]):
    target_id = command.get("target_id")
    if target_id not in manager.active_agents:
        return {"status": "error", "message": "Agente no conectado."}
    
    command_to_send = {"command": command.get("action"), "payload": command.get("payload")}
    await manager.send_to_agent(json.dumps(command_to_send), target_id)
    return {"status": "success"}
