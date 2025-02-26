# Game Server Backend - Deployment Notes

## Azure Resources

### AKS Cluster
- **Name**: GameServerClusterProd
- **Resource Group**: GameServerRG
- **Region**: East US
- **Node Pools**:
  - **System Pool**: Standard_D2s_v3 (2 nodes)
  - **Game Pool**: Standard_D4s_v3 (3+ nodes, autoscaling enabled)
  - **Labels**: All game nodes have `workload=gameserver` label

### Container Registry
- **Name**: gameregistry
- **SKU**: Standard
- **Region**: East US

### Storage Account
- **Name**: gameserversa
- **SKU**: Standard LRS
- **Region**: East US
- **File Shares**: Used for persistent game data

### Database
- **Type**: Azure Database for PostgreSQL
- **Name**: game-server-db
- **SKU**: General Purpose, 4 vCores

## Deployment Process

### Initial Setup
1. Create Resource Group
2. Deploy AKS Cluster
3. Deploy Container Registry
4. Deploy Storage Account
5. Deploy Database
6. Configure networking and security

### Application Deployment
1. Build and push container images to ACR
2. Deploy backend API to AKS
3. Configure environment variables
4. Set up monitoring and logging

## IP Address Management

### Static IP Configuration
To ensure game servers maintain consistent IP addresses:

1. Use the following annotations in service definitions:
```yaml
annotations:
  service.beta.kubernetes.io/azure-load-balancer-resource-group: "MC_GameServerRG_GameServerClusterProd_eastus"
  service.beta.kubernetes.io/azure-pip-name: "{server-id}-pip"
  service.beta.kubernetes.io/azure-dns-label-name: "{server-id}-dns"
  service.beta.kubernetes.io/azure-load-balancer-ip-allocation-method: "static"
```

2. This creates:
   - A static Public IP resource in Azure
   - A consistent DNS name for each server
   - IP persistence across service recreation

3. Access servers via:
   - IP: The assigned static IP
   - DNS: `{server-id}-dns.eastus.cloudapp.azure.com`

## Monitoring

### Azure Monitor
- Set up monitoring for AKS cluster
- Configure alerts for resource utilization
- Set up log analytics workspace

### Application Insights
- Implement for API monitoring
- Track server performance
- Set up availability tests

## Backup Strategy

### Game Server Data
- Regular backups to B2 Storage
- Scheduled backups based on activity
- On-demand backups before updates

### Database
- Automated backups via Azure
- Point-in-time restore capability
- Geo-redundant backup storage 