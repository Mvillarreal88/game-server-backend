from azure.identity import DefaultAzureCredential
from kubernetes import client, config
import os
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder
import logging
import time
import tempfile
import base64
from azure.mgmt.network import NetworkManagementClient

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
    def create_game_service(cls, server_id, namespace, port, game_type="minecraft"):
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

            # For Minecraft servers, use a shared load balancer approach
            if game_type == "minecraft":
                # Get or create a static IP for this server
                static_ip_name = f"{server_id}-pip"
                
                # Actually create the IP resource in Azure
                cls._get_or_create_static_ip(server_id)
                
                logger.info(f"Creating service {service_name} with shared AKS load balancer")
                service_manifest = {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {
                        "name": service_name,
                        "annotations": {
                            "service.beta.kubernetes.io/azure-load-balancer-resource-group": "MC_GameServerRG_GameServerClusterProd_eastus",
                            "service.beta.kubernetes.io/azure-pip-name": static_ip_name,
                            "service.beta.kubernetes.io/azure-load-balancer-internal": "false"
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
            else:
                # For high-performance games, use dedicated IPs with full annotations
                logger.info(f"Creating service {service_name} with dedicated static IP")
                service_manifest = {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {
                        "name": service_name,
                        "annotations": {
                            "service.beta.kubernetes.io/azure-load-balancer-resource-group": "MC_GameServerRG_GameServerClusterProd_eastus",
                            "service.beta.kubernetes.io/azure-pip-name": f"{server_id}-pip",
                            "service.beta.kubernetes.io/azure-dns-label-name": f"{server_id}-dns",
                            "service.beta.kubernetes.io/azure-load-balancer-ip-allocation-method": "static"
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

    @classmethod
    def _get_or_create_static_ip(cls, server_id):
        """Get an existing static IP from pool or create a new one"""
        from azure.mgmt.network import NetworkManagementClient
        from azure.identity import DefaultAzureCredential
        import os
        
        # Get Azure resource group from environment or use the same one as in annotations
        resource_group = os.getenv('AZURE_RESOURCE_GROUP', 'MC_GameServerRG_GameServerClusterProd_eastus')
        subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not subscription_id:
            raise ValueError("AZURE_SUBSCRIPTION_ID environment variable is required")
        
        # Create Azure Network client
        credential = DefaultAzureCredential()
        network_client = NetworkManagementClient(credential, subscription_id)
        
        # Name for the public IP resource
        ip_name = f"{server_id}-pip"
        
        logger.info(f"Checking if public IP {ip_name} exists in resource group {resource_group}")
        
        # Check if IP already exists
        try:
            existing_ip = network_client.public_ip_addresses.get(
                resource_group_name=resource_group,
                public_ip_address_name=ip_name
            )
            logger.info(f"Found existing public IP: {ip_name}")
            return ip_name
        except Exception as e:
            logger.info(f"Public IP {ip_name} not found, creating new one: {str(e)}")
        
        # Create new public IP
        logger.info(f"Creating new public IP: {ip_name}")
        ip_poller = network_client.public_ip_addresses.begin_create_or_update(
            resource_group_name=resource_group,
            public_ip_address_name=ip_name,
            parameters={
                "location": "eastus",  # Should match your AKS cluster region
                "sku": {
                    "name": "Standard"  # Required for AKS load balancers
                },
                "public_ip_allocation_method": "Static",
                "idle_timeout_in_minutes": 4
            }
        )
        ip = ip_poller.result()
        
        logger.info(f"Created public IP: {ip_name}")
        
        # Add a short delay to ensure the IP is fully provisioned
        logger.info("Waiting for IP to be fully provisioned...")
        time.sleep(10)
        
        return ip_name

    @classmethod
    def delete_deployment(cls, server_id, namespace="default"):
        """Delete a game server deployment and its associated service"""
        try:
            logger.info(f"Deleting deployment and service for server {server_id} in namespace {namespace}")
            
            # Create an instance to use the initialized client
            service = cls()
            
            # Delete the deployment
            service.apps_api.delete_namespaced_deployment(
                name=server_id,
                namespace=namespace
            )
            logger.info(f"Deployment {server_id} deleted successfully")
            
            # Delete the associated service
            service_name = f"{server_id}-svc"
            service.core_api.delete_namespaced_service(
                name=service_name,
                namespace=namespace
            )
            logger.info(f"Service {service_name} deleted successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete deployment {server_id}: {str(e)}")
            raise

    @classmethod
    def copy_files_from_pod(cls, server_id, namespace="default", file_paths=None):
        """
        Copy files from a running pod to local storage
        Returns a dictionary of {file_path: file_content}
        """
        try:
            logger.info(f"Copying files from pod {server_id} in namespace {namespace}")
            
            # Create an instance to use the initialized client
            service = cls()
            
            # Get pod name from deployment
            pod_list = service.core_api.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={server_id}"
            )
            
            if not pod_list.items:
                logger.error(f"No pods found for deployment {server_id}")
                return {}
            
            pod_name = pod_list.items[0].metadata.name
            logger.info(f"Found pod {pod_name} for deployment {server_id}")
            
            # Default file paths if none provided
            if not file_paths:
                file_paths = [
                    "server.properties",
                    "ops.json",
                    "whitelist.json",
                    "banned-players.json",
                    "banned-ips.json"
                ]
            
            # Copy each file
            file_contents = {}
            
            # Try to list files in the /data directory to see what's available
            try:
                import subprocess
                import json
                
                # Use kubectl to list files in the /data directory
                logger.info(f"Listing files in /data directory using kubectl")
                list_cmd = [
                    "kubectl", "exec", "-n", namespace, pod_name, "--", 
                    "find", "/data", "-type", "f", "-o", "-type", "d"
                ]
                
                result = subprocess.run(list_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    available_files = result.stdout.strip().split('\n')
                    logger.info(f"Files in /data directory: {available_files}")
                else:
                    logger.error(f"Failed to list files: {result.stderr}")
                    available_files = []
            except Exception as e:
                logger.error(f"Error listing files: {str(e)}")
                available_files = []
            
            # Copy each file using kubectl
            for file_path in file_paths:
                try:
                    # For Minecraft server, files are in /data directory
                    full_path = f"/data/{file_path}"
                    
                    # Use kubectl to read file content
                    logger.info(f"Reading {full_path} using kubectl")
                    cmd = [
                        "kubectl", "exec", "-n", namespace, pod_name, "--", 
                        "cat", full_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        file_contents[file_path] = result.stdout
                        logger.info(f"Successfully read file {file_path}")
                    else:
                        logger.warning(f"File {file_path} not found or empty: {result.stderr}")
                        
                except Exception as e:
                    logger.error(f"Failed to read file {file_path}: {str(e)}")
            
            # Special handling for world directory
            # This would require more complex logic to handle directory structures
            # For now, we'll just log that it's not implemented
            logger.warning("World directory backup not implemented yet")
            
            return file_contents
            
        except Exception as e:
            logger.error(f"Failed to copy files from pod {server_id}: {str(e)}")
            raise

    @classmethod
    def scale_deployment(cls, server_id, namespace="default", replicas=0):
        """
        Scale a deployment to the specified number of replicas
        Used primarily to pause (scale to 0) or resume (scale to 1) a server
        """
        try:
            logger.info(f"Scaling deployment {server_id} to {replicas} replicas")
            
            # Create an instance to use the initialized client
            service = cls()
            
            # Get the current deployment
            deployment = service.apps_api.read_namespaced_deployment(
                name=server_id,
                namespace=namespace
            )
            
            # Update the replica count
            deployment.spec.replicas = replicas
            
            # Apply the update
            service.apps_api.patch_namespaced_deployment(
                name=server_id,
                namespace=namespace,
                body=deployment
            )
            
            logger.info(f"Deployment {server_id} scaled to {replicas} replicas successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to scale deployment {server_id}: {str(e)}")
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