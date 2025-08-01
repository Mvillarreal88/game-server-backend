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
from config.settings import settings
from config.logging_config import setup_logging, ErrorHandler
from utils.validators import StartServerSchema, format_validation_errors
from marshmallow import ValidationError

# Load environment variables first
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Set up logging
setup_logging(settings.ENVIRONMENT)
logger = logging.getLogger('app')

# Initialize Flask app
app = Flask(__name__)

# Log configuration on startup
settings.log_configuration()

# Register the API blueprint
app.register_blueprint(api)

# Global error handlers
@app.errorhandler(400)
def handle_bad_request(e):
    """Handle bad request errors with JSON response"""
    logger.warning(f"Bad request: {str(e)}")
    # Check if this is a request to our API endpoints
    if request.path.startswith('/api/'):
        return jsonify({"error": "No data provided"}), 400
    return jsonify({"error": "Bad request"}), 400

@app.route('/health')
def health_check():
    """Health check endpoint for Azure App Service"""
    return jsonify({"status": "healthy"}), 200

@app.route('/robots933456.txt')
def robots_txt():
    """Required for Azure App Service health checks"""
    return '', 200

@app.route('/api/server/start-server-test', methods=['POST'])
def start_server():
    """Start a new game server instance with improved validation and error handling"""
    logger.info("=== Start Server Request Received ===")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    try:
        # Validate request data
        try:
            data = request.get_json(force=True)
        except Exception:
            logger.error("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
            
        if data is None:
            logger.error("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
        
        # Use marshmallow for validation
        try:
            validated_data = StartServerSchema().load(data)
            package = validated_data['package']
            server_id = validated_data['server_id']
            namespace = validated_data['namespace']
            logger.info(f"Request validated: server_id={server_id}, package={package}, namespace={namespace}")
        except ValidationError as e:
            error_response, status_code = ErrorHandler.handle_validation_error(logger, e)
            return jsonify(error_response), status_code
        
        config = GAME_PACKAGES[package]
        logger.info(f"Using package configuration: {config}")
            
        # Initialize Kubernetes service
        try:
            k8s_service = KubernetesService()
        except Exception as k8s_error:
            error_response, status_code = ErrorHandler.handle_kubernetes_error(logger, k8s_error)
            return jsonify(error_response), status_code
        
        # Test Kubernetes connection
        try:
            namespaces = k8s_service.core_api.list_namespace()
            logger.info(f"Connected to cluster. Found {len(namespaces.items)} namespaces")
            
            return jsonify({
                "success": True,
                "message": f"Server {server_id} for package {package} is starting...",
                "server_id": server_id,
                "package": package,
                "namespace": namespace,
                "config": config,
                "namespace_count": len(namespaces.items),
                "environment": settings.ENVIRONMENT
            }), 200
            
        except Exception as namespace_error:
            error_response, status_code = ErrorHandler.handle_kubernetes_error(logger, namespace_error)
            return jsonify(error_response), status_code
        
    except Exception as e:
        error_response = ErrorHandler.log_and_format_error(logger, e, "Start server")
        return jsonify(error_response), 500


if __name__ == '__main__':
    # Validate required settings before starting
    missing_settings = settings.validate_required_settings()
    if missing_settings and settings.is_production():
        logger.error(f"Cannot start in production without required settings: {missing_settings}")
        exit(1)
    elif missing_settings:
        logger.warning(f"Missing optional settings: {missing_settings}")
    
    logger.info(f"Starting server on port {settings.PORT} in {settings.ENVIRONMENT} mode")
    app.run(host='0.0.0.0', port=settings.PORT)
