# IP Persistence for Game Servers

## Problem Statement

Game servers require consistent IP addresses and ports so that players can reliably connect to them. When a Kubernetes service is recreated or a pod is rescheduled, the default behavior is to assign a new IP address, which breaks player connections and bookmarks.

## Solution: Static IPs with Azure Load Balancer

Azure Kubernetes Service (AKS) allows us to maintain consistent IPs by using specific annotations with the Azure Load Balancer integration.

### Required Annotations

```yaml
annotations:
  service.beta.kubernetes.io/azure-load-balancer-resource-group: "MC_GameServerRG_GameServerClusterProd_eastus"
  service.beta.kubernetes.io/azure-pip-name: "{server-id}-pip"
  service.beta.kubernetes.io/azure-dns-label-name: "{server-id}-dns"
  service.beta.kubernetes.io/azure-load-balancer-ip-allocation-method: "static"
```

### How It Works

1. **Azure Public IP Resource**: The `azure-pip-name` annotation creates a named Public IP resource in Azure. This resource persists even if the Kubernetes service is deleted.

2. **Static Allocation**: The `azure-load-balancer-ip-allocation-method` annotation ensures the IP is allocated statically rather than dynamically.

3. **DNS Name**: The `azure-dns-label-name` annotation assigns a consistent DNS name to the service, providing an alternative to IP-based connections.

4. **Resource Group**: The `azure-load-balancer-resource-group` annotation specifies where to create the Public IP resource.

## Implementation in Code

The `create_game_service` method in `KubernetesService` class should be updated to include these annotations:

```python
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
```

## Testing IP Persistence

To verify IP persistence:

1. Create a game server service
2. Note the assigned IP address
3. Delete the service
4. Recreate the service with the same annotations
5. Verify the IP address remains the same

## Limitations and Considerations

- **Resource Limits**: Azure subscriptions have limits on the number of Public IPs
- **Costs**: Static Public IPs may incur additional costs
- **Cleanup**: Unused Public IPs should be deleted to avoid unnecessary costs
- **Region Specificity**: Public IPs are region-specific resources

## References

- [Azure Load Balancer annotations for Kubernetes](https://docs.microsoft.com/en-us/azure/aks/load-balancer-standard#additional-customizations-via-kubernetes-annotations)
- [AKS networking concepts](https://docs.microsoft.com/en-us/azure/aks/concepts-network)
- [Public IP address pricing](https://azure.microsoft.com/en-us/pricing/details/ip-addresses/) 