import yaml

class KubernetesDeploymentBuilder:
    @staticmethod
    def generate_yaml(deployment_name, namespace, image, cpu, memory, port, env_vars, volume=None):
        """
        Generate Kubernetes Deployment YAML dynamically.
        """
        container_spec = {
            "name": deployment_name,
            "image": image,
            "resources": {
                "requests": {
                    "cpu": f"{cpu}m",  # Convert cores to millicores
                    "memory": f"{memory}Mi"  # Convert GB to MiB
                },
                "limits": {
                    "cpu": f"{cpu}m",
                    "memory": f"{memory}Mi"
                }
            },
            "ports": [{"containerPort": port}],
            "env": [{"name": k, "value": v} for k, v in env_vars.items()],
        }

        if volume:
            container_spec["volumeMounts"] = [
                {"name": volume["name"], "mountPath": volume["mount_path"]}
            ]

        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": deployment_name,
                "namespace": namespace
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "app": deployment_name
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": deployment_name
                        }
                    },
                    "spec": {
                        "containers": [container_spec],
                    }
                }
            }
        }

        if volume:
            deployment["spec"]["template"]["spec"]["volumes"] = [
                {"name": volume["name"], "azureFile": volume["azure_file"]}
            ]

        return deployment

    @staticmethod
    def save_to_file(data, file_path):
        """
        Save YAML data to a file (optional for debugging).
        """
        with open(file_path, "w") as file:
            yaml.dump(data, file)
