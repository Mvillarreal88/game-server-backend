from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from routes import api
import logging
from kubernetes import config, client
import base64
import tempfile
from services.kubernetes_service import KubernetesService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Initialize Flask app
app = Flask(__name__)

# Register the API blueprint
app.register_blueprint(api)

@app.route('/api/server/start-server', methods=['POST'])
def start_server():
    """Start a new game server instance"""
    logger.info("=== Start Server Request Received ===")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'Not Set')}")
    
    try:
        # Validate request data
        data = request.json
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
            
        server_id = data.get('server_id')
        game = data.get('game')
        
        if not server_id or not game:
            logger.error("Missing required fields")
            return jsonify({"error": "server_id and game are required"}), 400
            
        # Initialize Kubernetes service
        try:
            k8s_service = KubernetesService()
        except Exception as k8s_error:
            logger.error(f"Failed to initialize Kubernetes service: {str(k8s_error)}")
            return jsonify({
                "error": "Failed to connect to Kubernetes cluster",
                "details": str(k8s_error)
            }), 500
        
        # Test Kubernetes connection
        try:
            namespaces = k8s_service.core_v1.list_namespace()
            logger.info(f"Connected to cluster. Found {len(namespaces.items)} namespaces")
        except Exception as namespace_error:
            logger.error(f"Failed to list namespaces: {str(namespace_error)}")
            return jsonify({
                "error": "Failed to access Kubernetes cluster",
                "details": str(namespace_error)
            }), 500
        
        return jsonify({
            "message": f"Server {server_id} for {game} is starting...",
            "namespace_count": len(namespaces.items),
            "environment": "production" if os.getenv('WEBSITE_SITE_NAME') else "development"
        }), 200
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    # Use port 8000 for production (Azure), 5000 for local development
    is_production = os.getenv('WEBSITE_SITE_NAME') is not None
    default_port = 8000 if is_production else 5000
    port = int(os.getenv('PORT', default_port))
    
    app.run(host='0.0.0.0', port=port)
