from azure.identity import DefaultAzureCredential, AzureCliCredential
from kubernetes import client, config
import os
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder
import logging

class KubernetesService:
    def __init__(self):
        try:
            logger = logging.getLogger(__name__)
            logger.info("Initializing KubernetesService...")
            
            # Log environment variables (safely)
            subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "Not Set")
            resource_group = os.getenv("AZURE_RESOURCE_GROUP_NAME", "Not Set")
            cluster_name = os.getenv("AKS_CLUSTER_NAME", "Not Set")
            
            logger.info(f"Using Subscription: {subscription_id}")
            logger.info(f"Resource Group: {resource_group}")
            logger.info(f"Cluster Name: {cluster_name}")
            
            # Try to load from kubeconfig first
            try:
                config.load_kube_config()
                logger.info("Successfully loaded local kubeconfig")
                
            except Exception as config_error:
                logger.warning(f"Local config failed: {str(config_error)}")
                logger.info("Falling back to Azure credentials...")
                
                # Choose credential based on environment
                if os.getenv("ENVIRONMENT") == "local":
                    credential = AzureCliCredential()
                    logger.info("Using Azure CLI credentials")
                else:
                    credential = DefaultAzureCredential()
                    logger.info("Using Managed Identity")
                
                configuration = client.Configuration()
                cluster_url = f"https://gameserverclusterprod-dns-o0owfoer.hcp.eastus.azmk8s.io"
                configuration.host = cluster_url
                logger.info(f"Connecting to cluster at: {cluster_url}")
                
                # Get token with specific scope for AKS
                logger.info("Requesting token...")
                token = credential.get_token("https://management.azure.com/.default").token
                logger.info(f"Token received (length: {len(token)})")
                
                configuration.verify_ssl = False  # TODO: Enable SSL verification in production
                configuration.api_key = {"authorization": f"Bearer {token}"}
                configuration.api_key_prefix = {"authorization": "Bearer"}
                
                client.Configuration.set_default(configuration)
            
            # Initialize the API client
            self.core_v1 = client.CoreV1Api()
            
            # Test the connection
            logger.info("Testing cluster connection...")
            try:
                namespaces = self.core_v1.list_namespace()
                logger.info(f"Successfully connected to Kubernetes cluster. Found {len(namespaces.items)} namespaces")
                for ns in namespaces.items:
                    logger.info(f"Found namespace: {ns.metadata.name}")
            except Exception as e:
                logger.error(f"Failed to list namespaces: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                if hasattr(e, 'status') and hasattr(e.status, 'message'):
                    logger.error(f"Status message: {e.status.message}")
                raise
                
        except Exception as e:
            logger.error(f"Error initializing Kubernetes client: {str(e)}")
            raise

    @classmethod
    def deploy_game_server(cls, server_id, namespace, image, cpu, memory, port, env_vars, volume=None):
        """
        Deploy a game server dynamically using provided parameters.
        """
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
        create_from_yaml(service.api_client, yaml_objects=[deployment_yaml], namespace=namespace)
        print(f"Deployment {server_id} applied successfully.")
