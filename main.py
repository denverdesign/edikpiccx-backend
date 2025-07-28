# main.py (Versión 6.1 - Arquitectura HÍBRIDA/LEGADO - FINAL)
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import time

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
# Es importante tener una clave secreta para la sesión.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'la-llave-mas-secreta-del-universo-123!')

# Habilitamos CORS para permitir las peticiones HTTP del panel.
CORS(app) 

# Iniciamos Socket.IO para la comunicación en tiempo real con agentes y paneles.
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# --- ALMACÉN EN MEMORIA (El "Cerebro" Temporal del Servidor) ---
# Aquí guardamos la información de agentes y sus archivos multimedia.
media_storage = {}      # Clave: agent_id, Valor: (timestamp, lista_de_miniaturas)
connected_agents = {}   # Clave: socket_id, Valor: {info del agente}
connected_panels = {}   # Clave: socket_id, Valor: {info del panel}

# --- FUNCIÓN DE LOGGING PARA CLARIDAD ---
def log_info(message):
    """Imprime un mensaje informativo con fecha y hora."""
    print(f"[INFO] {time.strftime('%Y-%m-%d %H:%M:%S')} - {message}")

# =============================================================
# --- 1. RUTAS DE LA API (ENDPOINTS HTTP) ---
# Estas son las "puertas" a las que el panel puede llamar directamente.
# =============================================================

@app.route('/')
def serve_index():
    """Página principal que muestra que el servidor está activo."""
    return "Servidor Backend Activo - MODO HÍBRIDO v6.1"

@app.route('/api/get-agents', methods=['GET'])
def get_agents_http():
    """El panel llama aquí para obtener la lista de agentes conectados."""
    log_info("Un panel ha solicitado la lista de agentes vía HTTP.")
    return jsonify(list(connected_agents.values()))

@app.route('/api/get_media_list/<agent_id>', methods=['GET'])
def get_media_list_http(agent_id):
    """
    EL CORAZÓN DEL MÉTODO ANTIGUO: El panel llama aquí para pedir los archivos
    que un agente ya ha guardado en el `media_storage`.
    """
    log_info(f"El panel pide los medios de {agent_id[:8]} vía HTTP.")
    media_list_tuple = media_storage.get(agent_id, (0, [])) # Devuelve lista vacía si no hay nada
    log_info(f"Enviando {len(media_list_tuple[1])} elementos al panel.")
    return jsonify(media_list_tuple[1]) # Enviamos solo la lista

@app.route('/api/send-command', methods=['POST'])
def send_command_http():
    """El panel envía TODOS los comandos a través de esta ruta HTTP."""
    data = request.json
    target_id = data.get('target_id')
    action = data.get('action')
    
    # Limpieza: Si se piden miniaturas, borramos las antiguas.
    if action == 'get_thumbnails' and target_id in media_storage:
        log_info(f"Limpiando caché de medios para {target_id[:8]}")
        media_storage.pop(target_id, None)

    if not target_id or target_id not in connected_agents:
        return jsonify({"status": "error", "message": "Agente no conectado"}), 404
        
    log_info(f"Reenviando comando '{action}' al agente {target_id[:8]} vía WebSocket.")
    command_to_send = {'command': action.upper(), 'payload': data.get('payload', '')}
    
    # Usamos WebSocket para el envío final al agente (esto es muy rápido)
    socketio.send(json.dumps(command_to_send), to=target_id)
    
    return jsonify({"status": "success"})


# =============================================================
# --- 2. LÓGICA DE WEBSOCKETS (SOCKET.IO) ---
# Maneja las conexiones en tiempo real.
# =============================================================

@socketio.on('connect')
def on_connect():
    """Se ejecuta cuando un nuevo cliente (panel o agente) se conecta."""
    sid = request.sid
    client_type = request.headers.get('type', 'agent')

    if client_type == 'panel':
        connected_panels[sid] = {'id': sid}
        log_info(f"PANEL CONECTADO (ID: {sid})")
        # Le enviamos la lista actual de agentes para que se actualice.
        emit('agent_list_updated', list(connected_agents.values()), to=sid)
    else: # Es un agente
        device_name = request.args.get('deviceName', 'Desconocido')
        connected_agents[sid] = {'id': sid, 'name': device_name}
        log_info(f"AGENTE CONECTADO: '{device_name}' (ID: {sid})")
        # Notificamos a todos los paneles que hay un nuevo agente.
        socketio.emit('agent_list_updated', list(connected_agents.values()))

@socketio.on('disconnect')
def on_disconnect():
    """Se ejecuta cuando un cliente se desconecta."""
    sid = request.sid
    if sid in connected_panels:
        connected_panels.pop(sid, None)
        log_info(f"PANEL DESCONECTADO (ID: {sid})")
    elif sid in connected_agents:
        agent_info = connected_agents.pop(sid)
        media_storage.pop(sid, None) # Limpiamos su caché
        log_info(f"AGENTE DESCONECTADO: '{agent_info.get('name')}'. Caché limpiado.")
        # Notificamos a los paneles que el agente se fue.
        socketio.emit('agent_list_updated', list(connected_agents.values()))

@socketio.on('panel_heartbeat')
def on_panel_heartbeat(data):
    """Mantiene viva la conexión del panel para recibir actualizaciones."""
    pass

@socketio.on('agent_response')
def on_agent_response(data):
    """
    Se ejecuta cuando un Agente envía una respuesta.
    Dependiendo del evento, la guardamos o la reenviamos.
    """
    sid = request.sid
    if sid not in connected_agents: return

    event = data.get('event')
    payload = data.get('data')

    if event == 'thumbnails_data':
        # Para las miniaturas, usamos el MÉTODO ANTIGUO: GUARDAR.
        media_storage[sid] = (time.time(), payload)
        log_info(f"Almacenados {len(payload)} elementos multimedia del agente {sid[:8]}")
    else:
        # Para TODO lo demás (SMS, GPS, Estado), usamos el MÉTODO NUEVO: REENVIAR EN TIEMPO REAL.
        log_info(f"Reenviando evento en tiempo real '{event}' del agente {sid[:8]}.")
        socketio.emit('data_from_agent', json.dumps(data), broadcast=True)

# --- INICIO DEL SERVIDOR ---
if __name__ == '__main__':
    log_info("Iniciando servidor Flask (MODO HÍBRIDO v6.1)")
    # Gunicorn lo ejecutará a través del comando de Render.
    # Esta línea es para pruebas locales.
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
