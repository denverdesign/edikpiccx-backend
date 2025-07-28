# main.py (Versión 4.0 - FINAL - Escuchando el evento correcto)
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

# ... (las rutas @app.route no cambian, déjalas como están) ...
@app.route('/')
def serve_index():
    return "Servidor Backend para Agentes Activo v4.0"

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
    # ESTO ESTÁ CORRECTO. Enviamos un mensaje genérico al agente.
    socketio.send(json.dumps(command_to_send), to=target_sid) 
    
    agent_name = connected_agents[target_sid].get('name', 'Desconocido')
    print(f"[COMANDO] Enviando comando '{action}' al agente '{agent_name}'")
    return jsonify({"status": "success"})


# ... (las funciones de connect y disconnect no cambian) ...
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


# --- ¡AQUÍ ESTÁ LA CORRECCIÓN FINAL! ---
@socketio.on('agent_response')
def handle_agent_response(data): # 'data' ahora es un diccionario Python
    sid = request.sid
    if sid not in connected_agents:
        return

    agent_name = connected_agents[sid].get('name', 'Desconocido')
    print(f"[RESPUESTA RECIBIDA] Del agente '{agent_name}'. Reenviando al panel...")
    print(f"--> Datos: {data}")

    try:
        # Los datos ya están en el formato que el panel necesita.
        # Simplemente los convertimos a string JSON y los reenviamos.
        response_for_panel = json.dumps(data)
        socketio.emit('data_from_agent', response_for_panel, broadcast=True)
    except Exception as e:
        print(f"[ERROR] No se pudo reenviar la respuesta del agente: {e}.")

# ...
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
