from azure.identity import DefaultAzureCredential
from kubernetes import client, config
import os
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder
import logging
import time
import tempfile
import base64

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
            
            # Get cluster details from environment variables
            cluster_url = os.getenv('AKS_CLUSTER_URL')
            server_id = os.getenv('AKS_SERVER_ID')
            cluster_ca_cert = os.getenv('AKS_CLUSTER_CA_CERT')
            
            if not all([cluster_url, server_id, cluster_ca_cert]):
                raise ValueError("Missing required environment variables: AKS_CLUSTER_URL, AKS_SERVER_ID, or AKS_CLUSTER_CA_CERT")
            
            logger.info(f"Using AKS cluster URL: {cluster_url.split('.')[0]}.*****")
            
            # Get token using Managed Identity
            credential = DefaultAzureCredential()
            token = credential.get_token(f"{server_id}/.default")
            
            # Configure Kubernetes client
            configuration = client.Configuration()
            configuration.host = cluster_url
            configuration.api_key = {"authorization": f"Bearer {token.token}"}
            
            # Write CA cert to temp file
            with tempfile.NamedTemporaryFile(delete=False) as cert_file:
                cert_file.write(base64.b64decode(cluster_ca_cert))
                configuration.ssl_ca_cert = cert_file.name
                configuration.verify_ssl = True
            
            client.Configuration.set_default(configuration)
            
            # Initialize API clients
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            
            # Test connection
            logger.info("Testing cluster connection...")
            namespaces = self.core_api.list_namespace()
            logger.info(f"Successfully connected to Kubernetes cluster. Found {len(namespaces.items)} namespaces")
            
        except Exception as e:
            logger.error(f"Error initializing Kubernetes client: {str(e)}", exc_info=True)
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

            # Log node pool targeting
            logger.info("Targeting gamepool for deployment...")
            logger.info(f"Deployment {server_id} will be scheduled on nodes with label: workload=gameserver")

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

@classmethod
def create_game_service(cls, server_id, namespace, port):
    """Create service for game server using existing AKS infrastructure"""
    try:
        service = cls()
        service_name = f"{server_id}-svc"
        
        # Check if service already exists
        logger.info(f"Checking for existing service: {service_name} in namespace {namespace}")
        try:
            existing_svc = service.core_api.read_namespaced_service(
                name=service_name,
                namespace=namespace
            )
            if existing_svc:
                logger.info(f"Found existing service {service_name}")
                if existing_svc.status.load_balancer.ingress:
                    ip = existing_svc.status.load_balancer.ingress[0].ip
                    logger.info(f"Reusing existing IP: {ip}")
                    return ip, port
                
        except client.exceptions.ApiException as e:
            if e.status != 404:
                raise
            logger.info(f"No existing service found for {service_name}")

        # Create new service using cluster's load balancer
        logger.info(f"Creating new service {service_name} using cluster load balancer")
        service_manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": service_name,
                "annotations": {
                    "service.beta.kubernetes.io/azure-load-balancer-resource-group": "MC_GameServerRG_GameServerClusterProd_eastus"
                }
            },
            "spec": {
                "type": "LoadBalancer",
                "ports": [{
                    "port": port,
                    "targetPort": port,
                    "protocol": "TCP"
                }],
                "selector": {"app": server_id}
            }
        }
        
        new_svc = service.core_api.create_namespaced_service(
            namespace=namespace,
            body=service_manifest
        )
        logger.info(f"Service {service_name} created successfully")
        
        # Wait for IP assignment
        external_ip = None
        logger.info("Waiting for IP assignment...")
        for attempt in range(12):  # 60-second timeout
            svc = service.core_api.read_namespaced_service(service_name, namespace)
            if svc.status.load_balancer.ingress:
                external_ip = svc.status.load_balancer.ingress[0].ip
                logger.info(f"IP assigned: {external_ip}")
                break
            logger.info(f"Waiting for IP... Attempt {attempt + 1}/12")
            time.sleep(5)
            
        if not external_ip:
            raise TimeoutError("Failed to get external IP after 60 seconds")
            
        return external_ip, port
            
    except Exception as e:
        logger.error(f"Failed to create service: {str(e)}")
        raise


    # TODO: Implement server activity check
    # def check_server_activity(self, server_id, namespace="default"):
    #     """Check if server has been inactive"""
    #     try:
    #         # Get pod logs to check for player activity
    #         pod = self.core_api.read_namespaced_pod(
    #             name=f"{server_id}",
    #             namespace=namespace
    #         )
            
    #         logs = self.core_api.read_namespaced_pod_log(
    #             name=f"{server_id}",
    #             namespace=namespace,
    #             tail_lines=1000  # Last 1000 lines
    #         )
            
    #         # Check for player activity in logs
    #         last_player_activity = None
    #         for line in logs.split('\n'):
    #             if "logged in with entity" in line or "lost connection" in line:
    #                 last_player_activity = line.split('[')[0].strip()
            
    #         if last_player_activity:
    #             # Calculate time since last activity
    #             # If > 3 hours, trigger backup and shutdown
    #             pass
            
    #     except Exception as e:
    #         logger.error(f"Failed to check server activity: {str(e)}")
    #         raise