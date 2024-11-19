from azure.identity import DefaultAzureCredential, AzureCliCredential
from kubernetes import client, config
import os
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder
import logging
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from jose import jwt  # For decoding and validating JWT tokens

# Set up logging
logger = logging.getLogger(__name__)
logging.getLogger('kubernetes').setLevel(logging.DEBUG)

class KubernetesService:
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        logger.info(f"Initializing KubernetesService in {self.environment} mode")
        
        if self.environment == 'production':
            self._init_aks()
        else:
            self._init_aci()
    
    def _init_aks(self):
        try:
            logger.info("Initializing KubernetesService for AKS...")
            
            self.subscription_id = "8c4ca0fa-4be5-467a-b493-72094f192334"
            self.resource_group = "GameServerRG"
            self.cluster_name = "gameserverclusterprod"
            self.cluster_url = "https://gameserverclusterprod-dns-o0owfoer.hcp.eastus.azmk8s.io"
            
            logger.info(f"Using Subscription: {self.subscription_id}")
            logger.info(f"Resource Group: {self.resource_group}")
            logger.info(f"Cluster Name: {self.cluster_name}")
            
            # Retrieve a token specifically for AKS
            credential = DefaultAzureCredential()
            token = credential.get_token("https://aks.azure.com/.default")
            
            # Decode and log the token audience for validation
            decoded_token = jwt.get_unverified_claims(token.token)
            audience = decoded_token.get("aud", "No Audience Found")
            logger.info(f"Token audience (aud): {audience}")
            
            if audience != "https://aks.azure.com":
                raise ValueError(f"Incorrect token audience: {audience}. Expected 'https://aks.azure.com'.")
            
            logger.info("Token successfully retrieved for AKS.")
            
            # Configure Kubernetes client with the retrieved token
            configuration = client.Configuration()
            configuration.host = self.cluster_url
            configuration.api_key = {"authorization": f"Bearer {token.token}"}
            configuration.verify_ssl = False
            
            client.Configuration.set_default(configuration)
            
            # Test connection to the Kubernetes cluster
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            logger.info("Testing cluster connection...")
            self.core_api.list_namespace()
            logger.info("Successfully connected to Kubernetes cluster.")
        
        except Exception as e:
            logger.error(f"Error initializing Kubernetes client: {str(e)}")
            raise
    
    def _init_aci(self):
        try:
            logger.info("Initializing KubernetesService for ACI...")
            credential = AzureCliCredential()
            self.aci_client = ContainerInstanceManagementClient(
                credential, 
                self.subscription_id
            )
            logger.info("Successfully initialized ACI client.")
        except Exception as e:
            logger.error(f"Failed to initialize ACI: {str(e)}")
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