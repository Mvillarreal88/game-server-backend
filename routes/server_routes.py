from flask import Blueprint, request, jsonify
from services.azure_aks import start_game_server, stop_game_server

server_routes = Blueprint('server_routes', __name__)

@server_routes.route('/start', methods=['POST'])
def start_server():
    data = request.json
    server_id = data.get('server_id')
    game = data.get('game')

    try:
        start_game_server(server_id, game)
        return jsonify({"message": f"Server {server_id} for {game} is starting..."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@server_routes.route('/stop', methods=['POST'])
def stop_server():
    data = request.json
    server_id = data.get('server_id')

    try:
        stop_game_server(server_id)
        return jsonify({"message": f"Server {server_id} is stopping..."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
