from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
import asyncio
import json

app = FastAPI()

# --- Clase para manejar las conexiones de los agentes ---
class ConnectionManager:
    def __init__(self):
        # El diccionario guardará la información completa de cada agente
        # Clave: device_id, Valor: { "ws": websocket_object, "details": { ...info... } }
        self.active_connections: dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, device_id: str):
        await websocket.accept()
        self.active_connections[device_id] = {"ws": websocket}

    def disconnect(self, device_id: str):
        if device_id in self.active_connections:
            del self.active_connections[device_id]
            print(f"[DESCONEXIÓN] Agente desconectado: {device_id}")

    async def handle_first_message(self, device_id: str, data: str):
        """Maneja el paquete de bienvenida con los detalles del dispositivo."""
        device_details = json.loads(data)
        if device_id in self.active_connections:
            self.active_connections[device_id]["details"] = device_details
            print(f"[CONEXIÓN] Agente presentado: {device_details.get('name')}")

    async def handle_image_list(self, device_id: str, data: str):
        """Maneja la respuesta con la lista de imágenes."""
        image_data = json.loads(data)
        if device_id in self.active_connections and "details" in self.active_connections[device_id]:
            self.active_connections[device_id]["details"]["images"] = image_data.get("images", [])
            print(f"Recibidas {len(image_data.get('images', []))} imágenes de {device_id}")

    async def send_command(self, command: dict):
        """Envía un comando a un agente específico."""
        target_id = command.get("target_id")
        if target_id and target_id in self.active_connections:
            websocket = self.active_connections[target_id]["ws"]
            try:
                await websocket.send_text(json.dumps(command))
                return True
            except Exception as e:
                print(f"Error al enviar a {target_id}: {e}")
                return False
        return False

# Creamos una única instancia del manejador de conexiones para toda la aplicación
manager = ConnectionManager()

# --- Rutas de la API (Endpoints HTTP) ---

@app.get("/api/get-agents")
async def get_agents():
    """Devuelve la lista de agentes conectados con sus detalles."""
    return [conn["details"] for conn in manager.active_connections.values() if "details" in conn]

@app.post("/api/send-command")
async def send_command_endpoint(command: dict):
    """Recibe un comando del panel y se lo pasa al manejador."""
    success = await manager.send_command(command)
    if success:
        return {"status": "success", "message": "Comando enviado al agente."}
    else:
        return {"status": "error", "message": "Agente no conectado o fallo al enviar."}

# --- Endpoint de WebSocket ---

@app.websocket("/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    await manager.connect(websocket, device_id)
    try:
        # --- Lógica de Recepción ---
        # 1. El primer mensaje DEBE ser la información del dispositivo.
        first_message = await websocket.receive_text()
        await manager.handle_first_message(device_id, first_message)
        
        # 2. Después, nos quedamos en un bucle escuchando por más mensajes (como la lista de imágenes).
        while True:
            data = await websocket.receive_text()
            # Podríamos añadir lógica para diferentes tipos de mensajes
            # pero por ahora asumimos que es la lista de imágenes
            await manager.handle_image_list(device_id, data)

    except WebSocketDisconnect:
        manager.disconnect(device_id)
    except Exception as e:
        print(f"Error inesperado con el agente {device_id}: {e}")
        manager.disconnect(device_id)
