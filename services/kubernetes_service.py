from azure.identity import DefaultAzureCredential
from kubernetes import client, config
import os
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder
import ssl
import certifi

class KubernetesService:
    def __init__(self):
        try:
            # Try to load from kubeconfig first (for local development)
            try:
                config.load_kube_config()
            except:
                print("Local config failed, using Managed Identity...")
                # Use Managed Identity for authentication
                credential = DefaultAzureCredential()
                configuration = client.Configuration()
                
                # AKS cluster endpoint
                configuration.host = "https://gameserverclusterprod-dns-o0owfoer.hcp.eastus.azmk8s.io:443"
                
                # Get token with original working scope
                token = credential.get_token("https://management.azure.com/.default").token
                configuration.api_key = {"authorization": f"Bearer {token}"}
                configuration.api_key_prefix = {"authorization": "Bearer"}
                
                # Configure SSL context properly
                configuration.ssl_ca_cert = certifi.where()
                configuration.verify_ssl = True
                
                # If you need to debug SSL issues, you can enable these:
                configuration.debug = True
                configuration.assert_hostname = False
                
                client.Configuration.set_default(configuration)
            
            # Initialize the API client with SSL configuration
            self.api_client = client.ApiClient()
            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            
            # Test the connection by listing namespaces
            self.core_v1.list_namespace(_preload_content=False)
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
