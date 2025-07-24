import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time
from flask_socketio import SocketIO
from flask_cors import CORS  # Añadimos la importación

# --- CONFIGURACIÓN ---
app = Flask(__name__)
CORS(app)
# La 'SECRET_KEY' es necesaria para SocketIO
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-para-probar')

# Diccionario para guardar comandos pendientes por dispositivo
device_commands = {}
device_info = {}
# Habilitamos CORS para todas las rutas, permitiendo que tu panel se conecte
CORS(app) 

# Lock para acceso seguro entre hilos
lock = threading.Lock()
# Usamos el modo 'eventlet' que es compatible con gunicorn
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Diccionario para mantener un registro de los agentes conectados
connected_agents = {}

@app.route("/register", methods=["POST"])
def register_device():
    data = request.json
    device_id = data.get("device_id")
    device_name = data.get("device_name")

    if not device_id:
        return jsonify({"error": "device_id is required"}), 400

    with lock:
        device_info[device_id] = device_name or "Anónimo"
        device_commands.setdefault(device_id, None)
# --- RUTAS HTTP (Para el Panel de Control) ---

    print(f"📱 Dispositivo registrado: {device_id} ({device_name})")
    return jsonify({"status": "registered"}), 200
@app.route('/')
def serve_index():
    return "Servidor Backend para Agentes Activo"

@app.route('/api/get-agents', methods=['GET'])
def get_agents():
    return jsonify(list(connected_agents.values()))

@app.route("/send-command", methods=["POST"])
def send_command():
@app.route('/api/send-command', methods=['POST'])
def send_command_to_agent():
    data = request.json
    device_id = data.get("device_id")
    command = data.get("command")

    if not device_id or not command:
        return jsonify({"error": "device_id and command are required"}), 400

    with lock:
        device_commands[device_id] = command

    print(f"📤 Comando '{command}' enviado a {device_id}")
    return jsonify({"status": "command sent"}), 200


@app.route("/get-command", methods=["GET"])
def get_command():
    device_id = request.args.get("deviceId")
    device_name = request.args.get("deviceName")

    if not device_id:
        return jsonify({"error": "Missing deviceId"}), 400

    print(f"🛰️  Long Polling iniciado desde {device_id} ({device_name})")

    # Esperar hasta 30 segundos o recibir comando
    timeout = 30
    start = time.time()

    while time.time() - start < timeout:
        with lock:
            command = device_commands.get(device_id)

            if command:
                device_commands[device_id] = None
                return jsonify({"command": command})

        time.sleep(1)

    return jsonify({"command": None})


@app.route("/devices", methods=["GET"])
def list_devices():
    with lock:
        return jsonify(device_info), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    target_sid = data.get('target_id')
    action = data.get('action')
    payload = data.get('payload', '')

    if not target_sid or not action:
        return jsonify({"status": "error", "message": "Faltan target_id o action"}), 400

    if target_sid not in connected_agents:
        return jsonify({"status": "error", "message": "Agente no encontrado o desconectado"}), 404

    socketio.emit('server_command', {'command': action, 'payload': payload}, to=target_sid)
    print(f"[COMANDO] Enviando '{action}' al agente {connected_agents[target_sid].get('name')}")
    return jsonify({"status": "success"})

# --- EVENTOS DE WEBSOCKET (Para los Agentes de Android) ---

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    device_name = request.args.get('deviceName', 'Dispositivo Desconocido')
    
    connected_agents[sid] = {'id': sid, 'name': device_name, 'status': 'connected'}
    print(f"[CONEXIÓN] Nuevo agente conectado: {device_name} (ID: {sid})")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    agent_info = connected_agents.pop(sid, None)
    if agent_info:
        print(f"[DESCONEXIÓN] Agente desconectado: {agent_info.get('name')} (ID: {sid})")

@socketio.on('agent_response')
def handle_agent_response(data):
    sid = request.sid
    agent_name = connected_agents.get(sid, {}).get('name', 'Desconocido')
    print(f"Respuesta recibida del agente {agent_name}: {data}")

# --- INICIALIZACIÓN ---
if __name__ == '__main__':
    print("Iniciando servidor Flask con SocketIO...")
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=False)

