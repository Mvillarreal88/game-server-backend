from kubernetes import client, config
from kubernetes.utils import create_from_yaml
from utils.kubernetes_deployment_builder import KubernetesDeploymentBuilder

class KubernetesService:
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
