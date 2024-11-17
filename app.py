from flask import Flask, request, jsonify
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
import os
from dotenv import load_dotenv
from routes import api
import logging

# Explicitly load the .env file from the current directory
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

print(f"Loaded Subscription ID: {os.getenv('AZURE_SUBSCRIPTION_ID')}")
print(f"Loaded Resource Group: {os.getenv('AZURE_RESOURCE_GROUP_NAME')}")

# Initialize Flask app
app = Flask(__name__)

# Azure SDK setup
credential = DefaultAzureCredential()
subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
resource_group_name = os.getenv("AZURE_RESOURCE_GROUP_NAME")
client = ContainerInstanceManagementClient(credential, subscription_id)

# Register the API blueprint for Kubernetes-based deployments
app.register_blueprint(api)

# Legacy ACI Endpoints
# API Endpoint: Start a game server
@app.route('/api/server/start-server', methods=['POST'])
def start_server():
    logger = logging.getLogger(__name__)
    logger.info("=== Start Server Request Received ===")
    try:
        logger.info(f"KUBECONFIG path: {os.getenv('KUBECONFIG')}")
        logger.info(f"Config exists: {os.path.exists(os.getenv('KUBECONFIG'))}")
        logger.info("Creating container group...")
        data = request.json
        server_id = data.get('server_id')
        game = data.get('game')
        client.container_groups.begin_start(resource_group_name, server_id).wait()
        return jsonify({"message": f"Server {server_id} for {game} is starting..."}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to start server for {game}: {str(e)}"}), 500

# API Endpoint: Stop a game server
@app.route('/stop-server', methods=['POST'])
def stop_server():
    data = request.json
    server_id = data.get('server_id')
    game = data.get('game')

    try:
        client.container_groups.begin_stop(resource_group_name, server_id).wait()
        return jsonify({"message": f"Server {server_id} for {game} is stopping..."}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to stop server for {game}: {str(e)}"}), 500

# API Endpoint: Check server status
@app.route('/server-status/<server_id>', methods=['GET'])
def server_status(server_id):
    try:
        result = client.container_groups.get(resource_group_name, server_id)
        return jsonify({"status": result.instance_view.state}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to get server status: {str(e)}"}), 500

# Start the Flask server
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
