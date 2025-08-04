import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from urllib.parse import unquote
import zipfile # <-- ¡NUEVO IMPORT! Para crear el ZIP
from io import BytesIO # <-- ¡NUEVO IMPORT! Para manejar el ZIP en memoria

app = FastAPI(title="Agente Control Backend (vFINAL - Descarga ZIP)")
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
# ... (Todas las rutas hasta get_large_media se quedan igual que en la versión final anterior) ...

# --- ¡RUTA MEJORADA PARA MOSTRAR LA GALERÍA Y EL BOTÓN DE DESCARGA! ---
@app.get("/media/{device_id}/{filename:path}")
async def get_large_media(device_id: str, filename: str):
    decoded_filename = unquote(filename)
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(decoded_filename)

    if not media_item:
        return Response(content='{"detail":"Contenido no encontrado"}', status_code=404)

    # Si es una IMAGEN, la mostramos directamente
    if 'original_b64' in media_item:
        try:
            image_bytes = base64.b64decode(media_item['original_b64'])
            return Response(content=image_bytes, media_type="image/jpeg")
        except Exception as e: return Response(content=f'{{"detail":"Error: {e}"}}', status_code=500)

    # Si es un VIDEO, generamos la galería con el nuevo botón de descarga
    if 'frames_b64' in media_item:
        # URL para el nuevo endpoint de descarga
        download_url = f"/download_frames/{device_id}/{filename}"
        
        html_content = f"""
        <html>
            <head><title>Frames de {decoded_filename}</title></head>
            <body style='background-color:#222; color:white; font-family: sans-serif; text-align: center;'>
                <h1>Fotogramas de: {decoded_filename}</h1>
                <p>Total de frames: {len(media_item['frames_b64'])}</p>
                
                <!-- ¡NUEVO BOTÓN DE DESCARGA! -->
                <a href="{download_url}" download="{decoded_filename}_frames.zip" 
                   style="display:inline-block; background-color:#4CAF50; color:white; padding:14px 25px; text-align:center; text-decoration:none; font-size:16px; margin:20px; border-radius:8px;">
                   Descargar Todos los Frames (ZIP)
                </a>
                
                <div style='display: flex; flex-wrap: wrap; justify-content: center;'>
        """
        for frame_b64 in media_item['frames_b64']:
            html_content += f"<img src='data:image/jpeg;base64,{frame_b64}' style='margin:8px; border:2px solid #444; max-width: 400px;'/>"
        html_content += "</div></body></html>"
        return HTMLResponse(content=html_content)

    return Response(content='{"detail":"Contenido no disponible para este archivo"}', status_code=404)

# --- ¡NUEVA RUTA PARA CREAR Y SERVIR EL ARCHIVO ZIP! ---
@app.get("/download_frames/{device_id}/{filename:path}")
async def download_frames_as_zip(device_id: str, filename: str):
    decoded_filename = unquote(filename)
    cache = device_media_cache.get(device_id, {})
    media_item = cache.get(decoded_filename)

    if not media_item or 'frames_b64' not in media_item:
        return Response(content='{"detail":"No se encontraron frames para este video"}', status_code=404)

    # Creamos un archivo ZIP en memoria
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Iteramos sobre cada frame, lo decodificamos y lo añadimos al ZIP
        for i, frame_b64 in enumerate(media_item['frames_b64']):
            try:
                frame_bytes = base64.b64decode(frame_b64)
                # Le damos un nombre secuencial a cada imagen dentro del ZIP
                frame_filename = f"frame_{i:04d}.jpg" 
                zipf.writestr(frame_filename, frame_bytes)
            except Exception as e:
                print(f"Error al añadir frame {i} al ZIP: {e}")

    # Nos preparamos para enviar la respuesta
    zip_buffer.seek(0)
    
    # Creamos los headers para que el navegador sepa que es un archivo para descargar
    headers = {
        'Content-Disposition': f'attachment; filename="{decoded_filename}_frames.zip"'
    }
    
    return Response(content=zip_buffer.getvalue(), media_type="application/zip", headers=headers)

# --- (El resto de las rutas @app.post, @app.get, etc. se quedan igual que en la versión final anterior) ---
# ...
