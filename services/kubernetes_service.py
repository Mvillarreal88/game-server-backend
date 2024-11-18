from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from kubernetes import client, config
import os
import urllib3
import warnings
import requests
from kubernetes.utils import create_from_yaml
import ssl
import certifi
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder

# Suppress SSL warnings temporarily (use only in development)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

class KubernetesService:
    def __init__(self):
        try:
            # Load Kubernetes configuration
            try:
                # Local kubeconfig for development
                config.load_kube_config()
                print("Loaded local kubeconfig")
            except Exception as local_config_error:
                print(f"Local config failed: {local_config_error}, switching to Managed Identity...")
                
                # Use Managed Identity for Azure-hosted environments
                credential = ManagedIdentityCredential(client_id=os.getenv('AZURE_CLIENT_ID'))
                token = credential.get_token("https://management.azure.com/.default").token
                print("Successfully obtained token from Managed Identity")
                
                # Set up Kubernetes client configuration
                configuration = client.Configuration()
                configuration.host = os.getenv('KUBERNETES_HOST', 
                    'https://gameserverclusterprod-dns-o0owfoer.hcp.eastus.azmk8s.io:443')
                configuration.verify_ssl = False  # Temporarily disable SSL verification
                configuration.api_key = {"authorization": f"Bearer {token}"}
                
                # Test connection before proceeding
                try:
                    response = requests.get(
                        f"{configuration.host}/api", 
                        headers={"Authorization": f"Bearer {token}"}, 
                        verify=False,
                        timeout=10  # Add timeout
                    )
                    if response.status_code == 200:
                        print("Successfully connected to AKS API")
                    else:
                        print(f"Failed connection to AKS API: {response.status_code}")
                        raise Exception(f"Unable to connect to Kubernetes API: {response.text}")
                except requests.exceptions.RequestException as e:
                    print(f"Connection test failed: {str(e)}")
                    raise
                
                client.Configuration.set_default(configuration)
            
            # Initialize Kubernetes API clients
            self.api_client = client.ApiClient()
            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            
            # Verify access by listing namespaces
            namespaces = self.core_v1.list_namespace()
            print(f"Connected to cluster. Available namespaces: {[ns.metadata.name for ns in namespaces.items]}")
            
        except Exception as init_error:
            error_msg = f"Error initializing Kubernetes client: {str(init_error)}"
            print(error_msg)
            raise Exception(error_msg)

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
