from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from routes import api
import logging
from kubernetes import config, client
import base64
import tempfile

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

def init_kubernetes():
    try:
        # Check if we're running in Azure
        in_azure = os.getenv('WEBSITE_INSTANCE_ID') is not None
        logger.info(f"Running in Azure: {in_azure}")

        if in_azure:
            # Use DefaultAzureCredential for managed identity
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
            
            # Configure Kubernetes client
            configuration = client.Configuration()
            configuration.host = "https://gameserverclusterprod-dns-o0owfoer.hcp.eastus.azmk8s.io:443"
            
            # Get token from Azure credential
            token = credential.get_token("https://management.azure.com/.default").token
            configuration.api_key = {"authorization": f"Bearer {token}"}
            configuration.api_key_prefix = {"authorization": "Bearer"}
            
            client.Configuration.set_default(configuration)
        else:
            # Local development - use kubeconfig
            config.load_kube_config(context="GameServerClusterProd")
            
        # Test the configuration
        v1 = client.CoreV1Api()
        v1.list_namespace()
        logger.info("Successfully initialized Kubernetes client")
        return True
        
    except Exception as e:
        logger.error(f"Error in init_kubernetes: {str(e)}")
        return False

# Initialize Flask app
app = Flask(__name__)

# Register the API blueprint
app.register_blueprint(api)

@app.route('/api/server/start-server', methods=['POST'])
def start_server():
    """Single endpoint for both local and production environments"""
    logger.info("=== Start Server Request Received ===")
    
    if not init_kubernetes():
        return jsonify({
            "error": "Failed to initialize Kubernetes configuration"
        }), 503

    try:
        data = request.json
        server_id = data.get('server_id')
        game = data.get('game')
        
        # Test Kubernetes connection
        v1 = client.CoreV1Api()
        namespaces = v1.list_namespace()
        logger.info(f"Connected to Kubernetes cluster. Found {len(namespaces.items)} namespaces")
        
        # Here you would implement your server deployment logic
        # This would be the same whether running locally or in production
        
        return jsonify({
            "message": f"Server {server_id} for {game} is starting...",
            "namespace_count": len(namespaces.items),
            "environment": "production" if os.getenv('WEBSITE_SITE_NAME') else "development"
        }), 200
        
    except Exception as e:
        logger.error(f"Error in start_server: {str(e)}")
        return jsonify({
            "error": f"Failed to start server: {str(e)}"
        }), 500

if __name__ == '__main__':
    # Use port 8000 for production (Azure), 5000 for local development
    is_production = os.getenv('WEBSITE_SITE_NAME') is not None
    default_port = 8000 if is_production else 5000
    port = int(os.getenv('PORT', default_port))
    
    app.run(host='0.0.0.0', port=port)
