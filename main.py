# main.py (Versión 3.3 - Corrección final del reenvío)
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
    return "Servidor Backend para Agentes Activo v3.3"

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

# <-- ESTA ES LA VERSIÓN CORRECTA Y LIMPIA DE LA FUNCIÓN
@socketio.on('message')
def handle_agent_response(data): # 'data' aquí es el STRING JSON de Android
    sid = request.sid
    if sid not in connected_agents:
        print(f"[ADVERTENCIA] Mensaje recibido de un SID desconocido: {sid}")
        return

    agent_name = connected_agents[sid].get('name', 'Desconocido')
    
    # 1. Imprime lo que recibes para estar seguro
    print(f"[DATOS RECIBIDOS] Del agente '{agent_name}'. Reenviando al panel...")
    print(f"--> Datos brutos: {data}")

    try:
        # 2. Reenvía los mismos datos brutos (el string JSON) a TODOS los paneles.
        #    El panel ya sabe cómo interpretar este string, por el canal 'data_from_agent'.
        socketio.emit('data_from_agent', data, broadcast=True)
        
    except Exception as e:
        print(f"[ERROR] No se pudo reenviar el mensaje del agente '{agent_name}': {e}.")


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
