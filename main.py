# ¡¡¡LA SOLUCIÓN!!!
# Estas dos líneas DEBEN ser lo primero en todo el archivo.
import eventlet
eventlet.monkey_patch()

# Ahora, el resto del código viene después.
import os
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# ===================================================================
# CONFIGURACIÓN INICIAL DE LA APLICACIÓN
# ===================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-segura!')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

connected_agents = {}
connected_panels = {}

# ===================================================================
# RUTA DE ESTADO
# ===================================================================
@app.route('/')
def serve_index():
    return "Servidor Backend para Agentes Activo v2.2"

# ===================================================================
# RUTAS DE LA API (Para el Panel de Control)
# ===================================================================
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
    socketio.emit('server_command', {'command': action, 'payload': payload}, to=target_sid)
    agent_name = connected_agents[target_sid].get('name', 'Desconocido')
    print(f"[COMANDO] Enviando comando '{action}' al agente '{agent_name}' (ID: {target_sid})")
    return jsonify({"status": "success", "message": f"Comando '{action}' enviado."})

# ===================================================================
# EVENTOS DE WEBSOCKET (Para Agentes y Paneles)
# ===================================================================
@socketio.on('connect')
def handle_connect():
    client_type = request.args.get('type', 'agent')
    sid = request.sid
    if client_type == 'panel':
        connected_panels[sid] = {'id': sid}
        print(f"[PANEL CONECTADO] Nuevo panel de control conectado (ID: {sid})")
        emit('agent_list_updated', list(connected_agents.values()), to=sid)
    else:
        device_name = request.args.get('deviceName', 'Desconocido')
        connected_agents[sid] = {'id': sid, 'name': device_name, 'status': 'connected'}
        print(f"[AGENTE CONECTADO] Nuevo agente: '{device_name}' (ID: {sid})")
        socketio.emit('agent_list_updated', list(connected_agents.values()))

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in connected_panels:
        connected_panels.pop(sid, None)
        print(f"[PANEL DESCONECTADO] Un panel de control se ha desconectado (ID: {sid})")
    elif sid in connected_agents:
        agent_info = connected_agents.pop(sid, None)
        if agent_info:
            print(f"[AGENTE DESCONECTADO] Agente: '{agent_info.get('name')}' (ID: {sid})")
            socketio.emit('agent_list_updated', list(connected_agents.values()))

@socketio.on('agent_response')
def handle_agent_response(data):
    sid = request.sid
    agent_name = connected_agents.get(sid, {}).get('name', 'Desconocido')
    event_type = data.get('event')
    event_data = data.get('data')
    print(f"[DATOS RECIBIDOS] Del agente '{agent_name}' | Evento: '{event_type}'")
    data_for_panel = {'agent_id': sid, 'agent_name': agent_name, 'event': event_type, 'data': event_data}
    socketio.emit('data_from_agent', data_for_panel)

# ===================================================================
# BLOQUE DE EJECUCIÓN PRINCIPAL
# ===================================================================
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
