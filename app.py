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
#test
@app.route('/api/server/start-server', methods=['POST'])
def start_server():
    """Single endpoint for both local and production environments"""
    logger.info("=== Start Server Request Received ===")
    
    try:
        # Initialize Kubernetes service (will handle both local and Azure environments)
        k8s_service = KubernetesService()
        
        data = request.json
        server_id = data.get('server_id')
        game = data.get('game')
        
        # Test Kubernetes connection
        namespaces = k8s_service.core_v1.list_namespace()
        logger.info(f"Connected to Kubernetes cluster. Found {len(namespaces.items)} namespaces")
        
        # Here you would implement your server deployment logic
        # This would be the same whether running locally or in production
        
        return jsonify({
            "message": f"Server {server_id} for {game} is starting...",
            "namespace_count": len(namespaces.items),
            "environment": "production" if os.getenv('WEBSITE_SITE_NAME') else "development"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        return jsonify({
            "error": f"Failed to start server: {str(e)}"
        }), 503

if __name__ == '__main__':
    # Use port 8000 for production (Azure), 5000 for local development
    is_production = os.getenv('WEBSITE_SITE_NAME') is not None
    default_port = 8000 if is_production else 5000
    port = int(os.getenv('PORT', default_port))
    
    app.run(host='0.0.0.0', port=port)
