# main.py (VERSIÓN FINAL Y COMPLETA)
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json # Importamos json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-segura!')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

connected_agents = {}
connected_panels = {}

@app.route('/')
def serve_index():
    return "Servidor Backend para Agentes Activo v3.0"

@app.route('/api/get-agents', methods=['GET'])
def get_agents():
    return jsonify(list(connected_agents.values()))

@app.route('/api/send-command', methods=['POST'])
def send_command_to_agent():
    data = request.json
    target_sid = data.get('target_id')
    action = data.get('action')
    payload = data.get('payload', '')
    if not target_sid or not action or target_sid not in connected_agents:
        return jsonify({"status": "error", "message": "Agente no válido o desconectado"}), 404
    
    # ¡CORRECCIÓN CLAVE! Enviamos un mensaje de texto plano con el JSON
    command_to_send = {'command': action, 'payload': payload}
    socketio.send(json.dumps(command_to_send), to=target_sid)
    
    agent_name = connected_agents[target_sid].get('name', 'Desconocido')
    print(f"[COMANDO] Enviando comando '{action}' al agente '{agent_name}'")
    return jsonify({"status": "success"})

@socketio.on('connect')
def handle_connect():
    client_type = request.args.get('type', 'agent')
    sid = request.sid
    if client_type == 'panel':
        connected_panels[sid] = {'id': sid}
        print(f"[PANEL CONECTADO] (ID: {sid})")
        emit('agent_list_updated', list(connected_agents.values()), to=sid)
    else:
        device_name = request.args.get('deviceName', 'Desconocido')
        connected_agents[sid] = {'id': sid, 'name': device_name, 'status': 'connected'}
        print(f"[AGENTE CONECTADO] '{device_name}' (ID: {sid})")
        socketio.emit('agent_list_updated', list(connected_agents.values()))

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

@socketio.on('message') # ¡CORRECCIÓN CLAVE! Escuchamos mensajes de texto plano, no eventos con nombre.
def handle_agent_response(data):
    sid = request.sid
    agent_name = connected_agents.get(sid, {}).get('name', 'Desconocido')
    
    try:
        # El agente envía un string JSON, lo convertimos a un diccionario
        response_data = json.loads(data)
        event_type = response_data.get('event')
        event_payload = response_data.get('data')

        print(f"[DATOS RECIBIDOS] Del agente '{agent_name}' | Evento: '{event_type}'")
        
        data_for_panel = {
            'agent_id': sid,
            'agent_name': agent_name,
            'event': event_type,
            'data': event_payload
        }
        # Reenviamos los datos a todos los paneles conectados
        socketio.emit('data_from_agent', data_for_panel)
    except Exception as e:
        print(f"[ERROR] No se pudo procesar el mensaje del agente '{agent_name}': {e}. Datos recibidos: {data}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
