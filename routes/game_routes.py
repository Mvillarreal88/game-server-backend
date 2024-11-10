from flask import Blueprint, jsonify

game_routes = Blueprint('game_routes', __name__)

@game_routes.route('/info/<game>', methods=['GET'])
def game_info(game):
    # Logic to fetch game info from config or database
    return jsonify({"game": game, "status": "active"})
