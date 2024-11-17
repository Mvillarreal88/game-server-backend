from azure.identity import DefaultAzureCredential
from kubernetes import client, config
import os
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder

class KubernetesService:
    def __init__(self):
        try:
            # Try to load from kubeconfig first (for local development)
            try:
                config.load_kube_config()
            except:
                # If that fails, use Azure managed identity
                credential = DefaultAzureCredential()
                configuration = client.Configuration()
                
                # Get these values from your App Settings
                configuration.host = os.getenv('KUBE_HOST')  # Your AKS API server endpoint
                
                # Get token from Azure credential
                token = credential.get_token("https://management.azure.com/.default").token
                configuration.api_key = {"authorization": f"Bearer {token}"}
                configuration.api_key_prefix = {"authorization": "Bearer"}
                
                client.Configuration.set_default(configuration)
            
            # Initialize the API client
            self.api_client = client.ApiClient()
            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            
            print("Successfully initialized Kubernetes client")
        except Exception as e:
            print(f"Error initializing Kubernetes client: {str(e)}")
            raise

    @staticmethod
    def deploy_game_server(server_id, namespace, image, cpu, memory, port, env_vars, volume=None):
        """
        Deploy a game server dynamically using provided parameters.
        """
        # Load Kubernetes configuration
        config.load_kube_config()

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

        # Apply the deployment
        api_client = client.ApiClient()
        create_from_yaml(api_client, yaml_objects=[deployment_yaml], namespace=namespace)

        print(f"Deployment {server_id} applied successfully.")
