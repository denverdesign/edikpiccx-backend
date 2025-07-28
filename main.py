# main.py (Versión 6.2 - Arquitectura HÍBRIDA - A PRUEBA DE BALAS)
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-12345')
CORS(app)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

media_storage = {}
connected_agents = {}
connected_panels = {}

def log_info(message):
    print(f"[INFO] {time.strftime('%Y-%m-%d %H:%M:%S')} - {message}")

def log_error(message):
    print(f"[ERROR] {time.strftime('%Y-%m-%d %H:%M:%S')} - {message}")

# --- RUTAS HTTP (No cambian) ---
@app.route('/')
def serve_index(): return "Servidor Backend Activo - MODO HÍBRIDO v6.2"
@app.route('/api/get-agents', methods=['GET'])
def get_agents_http(): return jsonify(list(connected_agents.values()))
@app.route('/api/get_media_list/<agent_id>', methods=['GET'])
def get_media_list_http(agent_id):
    media_list_tuple = media_storage.get(agent_id, (0, []))
    return jsonify(media_list_tuple[1])
@app.route('/api/send-command', methods=['POST'])
def send_command_http():
    data = request.json
    target_id = data.get('target_id')
    action = data.get('action')
    if action == 'get_thumbnails' and target_id in media_storage: media_storage.pop(target_id, None)
    if not target_id or target_id not in connected_agents: return jsonify({"status": "error", "message": "Agente no conectado"}), 404
    command_to_send = {'command': action.upper(), 'payload': data.get('payload', '')}
    socketio.send(json.dumps(command_to_send), to=target_id)
    return jsonify({"status": "success"})

# --- LÓGICA DE WEBSOCKETS (Con mejoras) ---
@socketio.on('connect')
def on_connect():
    sid = request.sid
    client_type = request.headers.get('type', 'agent')
    if client_type == 'panel':
        connected_panels[sid] = {'id': sid}
        log_info(f"PANEL CONECTADO (ID: {sid})")
        emit('agent_list_updated', list(connected_agents.values()), to=sid)
    else:
        device_name = request.args.get('deviceName', 'Desconocido')
        connected_agents[sid] = {'id': sid, 'name': device_name}
        log_info(f"AGENTE CONECTADO: '{device_name}' (ID: {sid})")
        socketio.emit('agent_list_updated', list(connected_agents.values()))

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    if sid in connected_panels:
        connected_panels.pop(sid, None)
        log_info(f"PANEL DESCONECTADO (ID: {sid})")
    elif sid in connected_agents:
        agent_info = connected_agents.pop(sid)
        media_storage.pop(sid, None)
        log_info(f"AGENTE DESCONECTADO: '{agent_info.get('name')}'.")
        socketio.emit('agent_list_updated', list(connected_agents.values()))

@socketio.on('panel_heartbeat')
def on_panel_heartbeat(data): pass

# --- ¡AQUÍ ESTÁ LA MODIFICACIÓN CLAVE! ---
@socketio.on('agent_response')
def on_agent_response(data):
    sid = request.sid
    if sid not in connected_agents: return

    try:
        # 1. Verificamos si 'data' es un diccionario.
        if not isinstance(data, dict):
            log_error(f"El agente {sid[:8]} envió una respuesta en un formato inesperado (no es un diccionario). Datos: {data}")
            return

        log_info(f"Respuesta recibida del agente {sid[:8]}. Datos: {str(data)[:200]}...") # Imprimimos solo una parte por si es muy grande

        event = data.get('event')
        payload = data.get('data')

        # 2. Verificamos que las claves 'event' y 'data' existan.
        if event is None or payload is None:
            log_error(f"La respuesta del agente {sid[:8]} no contiene las claves 'event' o 'data'.")
            return

        if event == 'thumbnails_data':
            media_storage[sid] = (time.time(), payload)
            log_info(f"Almacenados {len(payload) if isinstance(payload, list) else 'N/A'} elementos del agente {sid[:8]}")
        else:
            log_info(f"Reenviando evento en tiempo real '{event}' del agente {sid[:8]}.")
            socketio.emit('data_from_agent', json.dumps(data), broadcast=True)

    except Exception as e:
        # 3. Si cualquier otra cosa falla, lo capturamos y lo registramos en lugar de caernos.
        log_error(f"¡EXCEPCIÓN CRÍTICA al procesar 'agent_response' de {sid[:8]}! Error: {e}")
        # No hacemos nada más para evitar un bucle de errores.

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
