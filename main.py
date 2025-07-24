import os
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS

# ===================================================================
# CONFIGURACIÓN INICIAL DE LA APLICACIÓN
# ===================================================================

# 1. Inicializamos la aplicación Flask
app = Flask(__name__)

# 2. Habilitamos CORS para permitir que tu panel de control (en otro dominio)
#    pueda hacer peticiones a esta API.
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 3. Configuramos una clave secreta, necesaria para Flask-SocketIO
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-segura!')

# 4. Inicializamos SocketIO, especificando el modo asíncrono 'eventlet'
#    que es compatible con Gunicorn en Render.
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# 5. Creamos un diccionario en memoria para guardar los agentes conectados.
#    La clave será el ID de sesión (sid) y el valor será la información del agente.
connected_agents = {}

# ===================================================================
# RUTA DE ESTADO (Para verificar que el servidor está vivo)
# ===================================================================

@app.route('/')
def serve_index():
    """
    Una ruta simple para confirmar que el servidor backend está funcionando.
    No es para usuarios, solo para pruebas.
    """
    return "Servidor Backend para Agentes Activo"

# ===================================================================
# RUTAS DE LA API (Para el Panel de Control)
# ===================================================================

@app.route('/api/get-agents', methods=['GET'])
def get_agents():
    """
    Endpoint para que el panel de control obtenga la lista de agentes conectados.
    Devuelve una lista de diccionarios, cada uno representando un agente.
    """
    # Convertimos los valores del diccionario de agentes en una lista y la devolvemos como JSON
    return jsonify(list(connected_agents.values()))

@app.route('/api/send-command', methods=['POST'])
def send_command_to_agent():
    """
    Endpoint para que el panel de control envíe un comando a un agente específico.
    Recibe un JSON con el ID del agente (target_id) y la acción a realizar.
    """
    data = request.json
    target_sid = data.get('target_id')  # El 'id' en el panel es el 'sid' de la conexión
    action = data.get('action')
    payload = data.get('payload', '')

    # Verificamos que el agente al que queremos enviar el comando exista y esté conectado
    if not target_sid or not action or target_sid not in connected_agents:
        return jsonify({"status": "error", "message": "Agente no válido o desconectado"}), 404

    # Usamos socketio.emit para enviar un evento ('server_command') al cliente específico
    socketio.emit('server_command', {'command': action, 'payload': payload}, to=target_sid)
    
    agent_name = connected_agents[target_sid].get('name', 'Desconocido')
    print(f"[COMANDO] Enviando comando '{action}' al agente '{agent_name}' (ID: {target_sid})")
    
    return jsonify({"status": "success", "message": f"Comando '{action}' enviado."})

# ===================================================================
# EVENTOS DE WEBSOCKET (Para los Agentes de Android)
# ===================================================================

@socketio.on('connect')
def handle_connect():
    """
    Se ejecuta automáticamente cuando un nuevo agente de Android establece una conexión WebSocket.
    """
    sid = request.sid  # ID de sesión único para esta conexión
    device_name = request.args.get('deviceName', 'Dispositivo Desconocido')
    
    # Guardamos la información del nuevo agente en nuestro diccionario
    connected_agents[sid] = {
        'id': sid,  # Usamos el sid como el ID único que verá el panel de control
        'name': device_name,
        'status': 'connected'
    }
    print(f"[CONEXIÓN] Nuevo agente conectado: '{device_name}' (ID: {sid})")

@socketio.on('disconnect')
def handle_disconnect():
    """
    Se ejecuta automáticamente cuando un agente de Android se desconecta.
    """
    sid = request.sid
    # Eliminamos al agente de nuestro diccionario para que ya no aparezca en el panel
    agent_info = connected_agents.pop(sid, None)
    if agent_info:
        print(f"[DESCONEXIÓN] Agente desconectado: '{agent_info.get('name')}' (ID: {sid})")

# ===================================================================
# BLOQUE DE EJECUCIÓN PRINCIPAL
# ===================================================================

if __name__ == '__main__':
    # Esta parte se usa para pruebas locales. Render usará el comando de Gunicorn.
    print("Iniciando servidor en modo de desarrollo...")
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
