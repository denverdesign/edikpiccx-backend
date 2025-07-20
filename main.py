from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time

app = Flask(__name__)
CORS(app)

# Diccionario para guardar comandos pendientes por dispositivo
device_commands = {}
device_info = {}

# Lock para acceso seguro entre hilos
lock = threading.Lock()


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

    print(f"📱 Dispositivo registrado: {device_id} ({device_name})")
    return jsonify({"status": "registered"}), 200


@app.route("/send-command", methods=["POST"])
def send_command():
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

