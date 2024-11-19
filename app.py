from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from routes import api
import logging
from kubernetes import config, client
import base64
import tempfile
from services.kubernetes_service import KubernetesService
from routes.server_routes import GAME_PACKAGES

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
#test
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
            
        package = data.get('package')
        server_id = data.get('server_id')
        namespace = data.get('namespace', 'default')
        
        if not package or not server_id:
            logger.error("Missing required fields")
            return jsonify({"error": "package and server_id are required"}), 400
            
        # Validate package
        if package not in GAME_PACKAGES:
            logger.error(f"Invalid package: {package}")
            return jsonify({"error": f"Invalid package: {package}"}), 400
            
        # Get package configuration
        config = GAME_PACKAGES[package]
        logger.info(f"Using package configuration: {config}")
            
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
            
            return jsonify({
                "message": f"Server {server_id} for package {package} is starting...",
                "namespace": namespace,
                "config": config,
                "namespace_count": len(namespaces.items),
                "environment": "production" if os.getenv('ENVIRONMENT') == 'production' else "development"
            }), 200
            
        except Exception as namespace_error:
            logger.error(f"Failed to list namespaces: {str(namespace_error)}")
            return jsonify({
                "error": "Failed to access Kubernetes cluster",
                "details": str(namespace_error)
            }), 500
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    # Use port 8000 for production (Azure), 5000 for local development
    is_production = os.getenv('ENVIRONMENT') == 'production'
    default_port = 8000 if is_production else 5000
    port = int(os.getenv('PORT', default_port))
    
    app.run(host='0.0.0.0', port=port)
