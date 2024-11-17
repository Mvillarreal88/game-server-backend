from flask import Blueprint, request, jsonify
from services.kubernetes_service import KubernetesService

server_routes = Blueprint("server_routes", __name__)

# Example Game Configuration (mocked; replace with DB lookup later)
GAME_PACKAGES = {
    "standard": {
        "cpu": 2000,  # 2 cores
        "memory": 6144,  # 6 GB in MiB
        "image": "gameregistry.azurecr.io/minecraft-server:latest",
        "port": 25565,
        "env_vars": {
            "EULA": "TRUE",
            "MEMORY": "5G",
            "SERVER_NAME": "Azure Test Minecraft Server",
        }
        # "volume": {
        #     "name": "data-volume",
        #     "mount_path": "/data",
        #     "azure_file": {
        #         "secretName": "azure-secret",  # Secret storing account key
        #         "shareName": "data",  # File share name
        #         "readOnly": False
        #     }
        # }
    }
}


@server_routes.route("/start-server", methods=["POST"])
def start_server():
    data = request.json
    package = data.get("package")  # Game package purchased
    server_id = data.get("server_id")  # Unique server ID
    namespace = data.get("namespace", "default")  # Optional namespace

    # Validate package
    if package not in GAME_PACKAGES:
        return jsonify({"error": f"Invalid package: {package}"}), 400

    config = GAME_PACKAGES[package]

    try:
        KubernetesService.deploy_game_server(
            server_id=server_id,
            namespace=namespace,
            image=config["image"],
            cpu=config["cpu"],
            memory=config["memory"],
            port=config["port"],
            env_vars=config["env_vars"]
        )
        return jsonify({"message": f"Server {server_id} for package {package} is starting..."}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to start server: {str(e)}"}), 500


# @server_routes.route('/stop', methods=['POST'])
# def stop_server():
#     data = request.json
#     server_id = data.get('server_id')

#     try:
#         stop_game_server(server_id)
#         return jsonify({"message": f"Server {server_id} is stopping..."}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
