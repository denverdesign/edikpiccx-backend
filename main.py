# main.py (Versión Final v3.2 - Con Registro Post-Conexión)
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-segura!')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

connected_agents = {}
connected_panels = {}

@app.route('/')
def serve_index():
    return "Servidor Backend para Agentes Activo v3.2"

# ... (Las rutas /api/get-agents y /api/send-command se quedan igual) ...

@socketio.on('connect')
def handle_connect():
    client_type = request.args.get('type', 'agent')
    sid = request.sid
    if client_type == 'panel':
        connected_panels[sid] = {'id': sid}
        print(f"[PANEL CONECTADO] (ID: {sid})")
        emit('agent_list_updated', list(connected_agents.values()), to=sid)
    else:
        # El agente se conecta anónimamente al principio
        connected_agents[sid] = {'id': sid, 'name': 'Conectando...', 'status': 'connecting'}
        print(f"[CONEXIÓN INICIAL] Nuevo agente (ID: {sid}). Esperando registro...")
        # No notificamos al panel todavía, esperamos a que el agente se identifique.

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in connected_panels:
        connected_panels.pop(sid, None)
        print(f"[PANEL DESCONECTADO] (ID: {sid})")
    elif sid in connected_agents:
        agent_info = connected_agents.pop(sid, None)
        if agent_info:
            print(f"[AGENTE DESCONECTADO] '{agent_info.get('name')}'")
            socketio.emit('agent_list_updated', list(connected_agents.values()))

# --- ¡NUEVO MÉTODO ADICIONAL! El manejador de registro ---
@socketio.on('register_agent')
def handle_agent_registration(data):
    """
    Se ejecuta cuando un agente envía su información de identificación
    justo después de conectarse.
    """
    sid = request.sid
    if sid in connected_agents:
        device_name = data.get('deviceName', 'Desconocido')
        # Actualizamos la entrada del agente con su nombre real
        connected_agents[sid]['name'] = device_name
        connected_agents[sid]['status'] = 'connected'
        print(f"[AGENTE REGISTRADO] '{device_name}' (ID: {sid})")
        # Ahora que tenemos el nombre, notificamos a los paneles
        socketio.emit('agent_list_updated', list(connected_agents.values()))

@socketio.on('message')
def handle_agent_response(data):
    # ... (esta función se queda igual) ...
