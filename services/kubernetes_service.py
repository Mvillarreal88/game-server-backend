from azure.identity import DefaultAzureCredential
from kubernetes import client, config
import os
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder
import logging

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logging.getLogger('kubernetes').setLevel(logging.INFO)

class KubernetesService:
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        logger.info(f"Initializing KubernetesService in {self.environment} mode")
        
        if self.environment == 'production':
            self._init_aks()
        else:
            self._init_local()
    
    def _init_aks(self):
        try:
            logger.info("Initializing KubernetesService for AKS...")
            
            # In production, use managed identity via in-cluster config
            config.load_incluster_config()
            
            # Initialize API clients
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            
            # Test connection
            logger.info("Testing cluster connection...")
            self.core_api.list_namespace()
            logger.info("Successfully connected to Kubernetes cluster")
            
        except Exception as e:
            logger.error(f"Error initializing Kubernetes client: {str(e)}")
            raise
    
    def _init_local(self):
        try:
            logger.info("Initializing KubernetesService for local development...")
            # For local development, use kubeconfig
            config.load_kube_config()
            
            # Initialize API clients
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            
            logger.info("Successfully initialized local Kubernetes client")
        except Exception as e:
            logger.error(f"Failed to initialize local client: {str(e)}")
            raise

    @classmethod
    def deploy_game_server(cls, server_id, namespace, image, cpu, memory, port, env_vars, volume=None):
        """
        Deploy a game server dynamically using provided parameters.
        """
        try:
            logger.info(f"Deploying game server with ID: {server_id}")
            
            # Create an instance to use the initialized client
            service = cls()

            # Generate deployment YAML dynamically
            deployment_yaml = KubernetesDeploymentBuilder.generate_yaml(
                deployment_name=server_id,
                namespace=namespace,
                image=image,
                cpu=cpu,
                memory=memory,
                port=port,
                env_vars=env_vars,
                volume=volume
            )

            # Apply the deployment using the existing client
            create_from_yaml(service.core_api.api_client, yaml_objects=[deployment_yaml], namespace=namespace)
            logger.info(f"Deployment {server_id} applied successfully.")
        
        except Exception as e:
            logger.error(f"Failed to deploy game server {server_id}: {str(e)}")
            raise