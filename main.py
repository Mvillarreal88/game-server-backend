from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import logging
from services.kubernetes_service import KubernetesService
from routes.server_routes import GAME_PACKAGES

# Set up logging (same as app.py)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables (same as app.py)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Initialize FastAPI app
app = FastAPI(
    title="Game Server Backend",
    description="API for managing game server deployments on AKS",
    version="1.0.0"
)

# Define request model (matches existing JSON structure)
class ServerStartRequest(BaseModel):
    package: str
    server_id: str
    namespace: str = "default"

@app.post("/api/server/start-server")
async def start_server(request: ServerStartRequest):
    """Start a new game server instance"""
    logger.info("=== Start Server Request Received ===")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'Not Set')}")
    
    if request.package not in GAME_PACKAGES:
        raise HTTPException(status_code=400, detail=f"Invalid package: {request.package}")
    
    config = GAME_PACKAGES[request.package]
    logger.info(f"Using package configuration: {config}")
    
    try:
        k8s_service = KubernetesService()
        namespaces = k8s_service.core_v1.list_namespace()
        logger.info(f"Connected to cluster. Found {len(namespaces.items)} namespaces")
        
        KubernetesService.deploy_game_server(
            server_id=request.server_id,
            namespace=request.namespace,
            image=config["image"],
            cpu=config["cpu"],
            memory=config["memory"],
            port=config["port"],
            env_vars=config["env_vars"]
        )
        
        return {
            "message": f"Server {request.server_id} for package {request.package} is starting...",
            "namespace": request.namespace,
            "config": config,
            "namespace_count": len(namespaces.items),
            "environment": "production" if os.getenv('ENVIRONMENT') == 'production' else "development"
        }
        
    except Exception as e:
        logger.error(f"Failed to deploy server: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Keep Azure health check endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/robots933456.txt")
async def robots_txt():
    return ""

if __name__ == "__main__":
    import uvicorn
    # Use different port than Flask to avoid conflicts
    uvicorn.run(app, host="0.0.0.0", port=8001) 