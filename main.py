import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Agente Control Backend v3.1")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "Base de Datos" en Memoria ---
connected_agents: dict[str, dict] = {}
device_media_cache: dict[str, list] = {}

class Command(BaseModel): # ... (sin cambios)
class Thumbnail(BaseModel): # ... (sin cambios)

# --- ENDPOINT WEBSOCKET SIMPLIFICADO ---
@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    """
    Punto de entrada para los agentes. Acepta la conexión y la mantiene abierta.
    Toda la info que necesitamos ya viene en la URL.
    """
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: '{device_name}' (ID: {device_id})")
    # Guardamos la información directamente
    connected_agents[device_id] = {"ws": websocket, "name": device_name}
    
    try:
        # Mantenemos la conexión viva esperando a que se desconecte.
        while True:
            await websocket.receive_text() # Esto simplemente espera, no hace nada con el texto.
    except WebSocketDisconnect:
        print(f"[DESCONEXIÓN] Agente desconectado: '{device_name}' (ID: {device_id})")
        if device_id in connected_agents: del connected_agents[device_id]
        if device_id in device_media_cache: del device_media_cache[device_id]

# --- EL RESTO DE RUTAS HTTP NO CAMBIAN ---
@app.get("/api/get-agents")
async def get_agents(): # ... (sin cambios)
@app.post("/api/send-command")
async def send_command_to_agent(command: Command): # ... (sin cambios)
@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]): # ... (sin cambios)
@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str): # ... (sin cambios)
