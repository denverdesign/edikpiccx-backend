import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = FastAPI(title="Agente Control Backend vFINAL")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, dict] = {}
device_thumbnails_cache: Dict[str, list] = {}

# --- MODELOS DE DATOS (COMPLETOS) ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str

class Thumbnail(BaseModel):
    filename: str
    small_thumb_b64: str # Nuevo campo
    large_thumb_b64: str # Nuevo campo

class ErrorLog(BaseModel):
    error: str

# --- ENDPOINTS (RUTAS DE LA API) ---

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: '{device_name}' (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "name": device_name}
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        print(f"[DESCONEXIÓN] Agente desconectado: '{name_to_print}'")
        if device_id in connected_agents: del connected_agents[device_id]
        if device_id in device_thumbnails_cache: del device_thumbnails_cache[device_id]

@app.get("/api/get-agents")
async def get_agents():
    """Devuelve la lista de agentes actualmente conectados."""
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    """Recibe un comando del panel y se lo reenvía al agente correcto."""
    target_id = command.target_id
    if target_id not in connected_agents:
        return {"status": "error", "message": "Agente no conectado."}
    try:
        await connected_agents[target_id]["ws"].send_text(command.json())
        print(f"Comando '{command.action}' enviado a '{connected_agents.get(target_id, {}).get('name', 'Desconocido')}'")
        return {"status": "success", "message": "Comando enviado."}
    except Exception as e:
        print(f"[ERROR] Fallo al enviar comando a {target_id}: {e}")
        return {"status": "error", "message": "Fallo de comunicación con el agente."}

@app.post("/api/submit_media_list/{device_id}")
async def submit_media_list(device_id: str, thumbnails: List[Thumbnail]):
    """Ruta para que el agente envíe la lista de sus miniaturas."""
    if device_id not in connected_agents:
        return {"status": "error", "message": "Agente no registrado."}
    device_thumbnails_cache[device_id] = [thumb.dict() for thumb in thumbnails]
    print(f"Recibidas {len(thumbnails)} miniaturas del agente '{connected_agents.get(device_id, {}).get('name', 'Desconocido')}'")
    return {"status": "success"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    """Ruta para que el panel pida la lista de miniaturas de un dispositivo."""
    return device_thumbnails_cache.get(device_id, [])

# En tu clase ControlPanelApp en control_panel.py

def create_widgets(self):
    # ... (código para crear la lista de agentes) ...

    # --- NUEVO: Panel de Logs de Errores ---
    logs_frame = ttk.LabelFrame(self, text="Log de Errores de Agentes", padding=10)
    logs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    log_cols = ('time', 'device', 'message')
    self.log_tree = ttk.Treeview(logs_frame, columns=log_cols, show='headings')
    self.log_tree.heading('time', text='Hora')
    self.log_tree.heading('device', text='Dispositivo')
    self.log_tree.heading('message', text='Error Reportado')
    self.log_tree.pack(fill=tk.BOTH, expand=True)

    # ... (resto de widgets) ...

def refresh_data(self): # Nueva función que actualiza todo
    self.threaded_task(self._do_refresh_agents)
    self.threaded_task(self._do_refresh_errors)

def _do_refresh_errors(self):
    try:
        response = requests.get(f"{SERVER_URL}/api/get_error_logs", timeout=10)
        logs = response.json()
        self.after(0, self._update_log_tree, logs)
    except Exception as e:
        Logger.error(f"No se pudieron obtener los logs de error: {e}")

def _update_log_tree(self, logs):
    self.log_tree.delete(*self.log_tree.get_children())
    for log in logs:
        self.log_tree.insert('', 'end', values=(log['timestamp'], log.get('device_id', 'N/A')[:8], log['message']))


@app.post("/api/log_error/{device_id}")
async def log_error_from_agent(device_id: str, error_log: ErrorLog):
    """Ruta para que los agentes reporten errores para depuración remota."""
    print(f"[ERROR REMOTO] Dispositivo {device_id[:8]}: {error_log.error}")
    return {"status": "log recibido"}
