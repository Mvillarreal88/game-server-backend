from azure.identity import DefaultAzureCredential, AzureCliCredential
from kubernetes import client, config
import os
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder

class KubernetesService:
    def __init__(self):
        try:
            # Try to load from kubeconfig first
            try:
                config.load_kube_config()
                print("Using local kubeconfig...")
                
            except:
                print("Local config failed, using Azure credentials...")
                # Choose credential based on environment
                if os.getenv("ENVIRONMENT") == "local":
                    credential = AzureCliCredential()
                    print("Using Azure CLI credentials...")
                else:
                    credential = DefaultAzureCredential()
                    print("Using Managed Identity...")
                
                configuration = client.Configuration()
                configuration.host = "https://gameserverclusterprod-dns-o0owfoer.hcp.eastus.azmk8s.io:443"
                
                # Get token from credential
                token = credential.get_token("https://management.azure.com/.default").token
                
                # Set up the configuration
                configuration.verify_ssl = False
                configuration.ssl_ca_cert = None
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
