from flask import Flask, request, jsonify
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv(dotenv_path='.env')  # Specify the .env file path
print("Loaded Subscription ID:", os.getenv("AZURE_SUBSCRIPTION_ID"))
# Initialize Flask app
app = Flask(__name__)

# Azure SDK setup
credential = DefaultAzureCredential()
subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
resource_group_name = os.getenv("AZURE_RESOURCE_GROUP")
client = ContainerInstanceManagementClient(credential, subscription_id)

# API Endpoint: Start a game server
@app.route('/start-server', methods=['POST'])
def start_server():
    data = request.json
    server_id = data.get('server_id')
    game = data.get('game')

    try:
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
