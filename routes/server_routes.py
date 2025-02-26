from flask import Blueprint, request, jsonify
from services.kubernetes_service import KubernetesService
from services.b2_storage_service import B2StorageService
import logging

server_routes = Blueprint("server_routes", __name__)

# Example Game Configuration (mocked; replace with DB lookup later)
GAME_PACKAGES = {
    "standard": {
        "cpu": 4000,  # 4 cores
        "memory": 8192,  # 8 GB in MiB
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

logger = logging.getLogger(__name__)

@server_routes.route("/start-server", methods=["POST"])
def start_server():
    data = request.json
    package = data.get("package")
    server_id = data.get("server_id")
    namespace = data.get("namespace", "default")

    if package not in GAME_PACKAGES:
        return jsonify({"error": f"Invalid package: {package}"}), 400

    config = GAME_PACKAGES[package]
    
    try:
        # Initialize B2 storage and check for existing files
        b2_service = B2StorageService()
        existing_files = b2_service.list_files(server_id)
        
        # Only create default files if this is a new server
        if not existing_files:
            logger.info(f"New server detected. Creating default files for {server_id}")
            default_files = {
                "server.properties": "server-name=My Minecraft Server\ndifficulty=normal\ngamemode=survival",
                "ops.json": "[]",
                "whitelist.json": "[]",
                "banned-players.json": "[]",
                "banned-ips.json": "[]"
            }
            for filename, content in default_files.items():
                b2_service.update_file(server_id, filename, content)
        else:
            logger.info(f"Existing server detected. Will restore files for {server_id}: {existing_files}")
        
        # Deploy the server
        KubernetesService.deploy_game_server(
            server_id=server_id,
            namespace=namespace,
            image=config["image"],
            cpu=config["cpu"],
            memory=config["memory"],
            port=config["port"],
            env_vars=config["env_vars"],
            # TODO: Add volume mount for B2 files
        )
        
        # After deploying the server
        node_ip, node_port = KubernetesService.create_game_service(
            server_id=server_id,
            namespace=namespace,
            port=config["port"]
        )
        
        return jsonify({
            "message": f"Server {server_id} for package {package} is starting...",
            "files_restored": bool(existing_files),
            "existing_files": existing_files if existing_files else [],
            "connection_info": {
                "ip": node_ip,
                "port": node_port
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to start server: {str(e)}"}), 500


@server_routes.route("/stop-server", methods=["POST"])
def stop_server():
    data = request.json
    server_id = data.get("server_id")
    namespace = data.get("namespace", "default")

    try:
        # Save files to B2 before stopping
        b2_service = B2StorageService()
        files_to_save = [
            "server.properties",
            "ops.json",
            "whitelist.json",
            "banned-players.json",
            "banned-ips.json",
            "world/"  # This will need special handling for directories
        ]
        
        # TODO: Add logic to get files from running container
        # This will require adding a method to KubernetesService to copy files from pod
        
        # Stop the server
        KubernetesService.delete_deployment(server_id, namespace)
        
        return jsonify({
            "message": f"Server {server_id} stopped and files saved",
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to stop server: {str(e)}"}), 500
