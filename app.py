from flask import Flask, request, jsonify
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
import os
from dotenv import load_dotenv
from routes import api
import logging
from kubernetes import config, client
from kubernetes.client import ApiClient
import base64
import tempfile

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

def init_kubernetes():
    try:
        # Check for base64 encoded config in environment
        kube_config_content = os.getenv('KUBECONFIG_CONTENT')
        if kube_config_content:
            logger.info("Found KUBECONFIG_CONTENT, attempting to use it...")
            try:
                # Decode and save to temp file
                config_data = base64.b64decode(kube_config_content)
                
                # Create a temporary file that will be automatically cleaned up
                with tempfile.NamedTemporaryFile(delete=False) as temp_config:
                    temp_config.write(config_data)
                    temp_config_path = temp_config.name
                
                # Load the config from our temporary file
                config.load_kube_config(config_file=temp_config_path)
                
                # Test the configuration
                v1 = client.CoreV1Api()
                v1.list_namespace()
                
                logger.info("Successfully initialized Kubernetes client with provided config")
                return True
                
            except Exception as e:
                logger.error(f"Error loading provided kubeconfig: {str(e)}")
                return False
                
        logger.info("No KUBECONFIG_CONTENT found, trying default config locations...")
        # Try loading from default location
        config.load_kube_config()
        logger.info("Successfully loaded config from default location")
        return True
        
    except Exception as e:
        logger.warning(f"Could not load kube config from default location: {str(e)}")
        try:
            # Try loading from in-cluster config (when running in a pod)
            config.load_incluster_config()
            logger.info("Successfully loaded in-cluster config")
            return True
        except Exception as e:
            logger.error(f"Could not load any Kubernetes config: {str(e)}")
            return False

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/start', methods=['POST'])
def start_server():
    try:
        if not init_kubernetes():
            return jsonify({
                "status": "error",
                "message": "Could not initialize Kubernetes client. Check logs for details."
            }), 503

        # Test the connection
        try:
            v1 = client.CoreV1Api()
            namespaces = v1.list_namespace()
            logger.info(f"Successfully connected to Kubernetes. Found {len(namespaces.items)} namespaces.")
            
            return jsonify({
                "status": "success",
                "message": "Kubernetes client initialized successfully",
                "namespace_count": len(namespaces.items)
            }), 200
            
        except Exception as e:
            logger.error(f"Error testing Kubernetes connection: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Could not connect to Kubernetes cluster: {str(e)}"
            }), 503

    except Exception as e:
        logger.error(f"Error in start_server: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500

# Start the Flask server
if __name__ == '__main__':
    # Get port from environment variable or default to 8000
    port = int(os.getenv('PORT', 8000))
    logger = logging.getLogger(__name__)
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port)
