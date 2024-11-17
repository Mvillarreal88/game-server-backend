from flask import Blueprint, jsonify, request

user_routes = Blueprint('user_routes', __name__)

@user_routes.route('/info', methods=['GET'])
def get_user_info():
    # Placeholder for user info - can be expanded later
    return jsonify({
        "message": "User info endpoint",
        "status": "Not implemented yet"
    })

@user_routes.route('/servers', methods=['GET'])
def get_user_servers():
    # Placeholder for getting user's servers - can be expanded later
    return jsonify({
        "message": "User servers endpoint",
        "servers": []
    })
