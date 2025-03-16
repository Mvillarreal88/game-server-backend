# Game Server Backend Architecture

## Overview
The Game Server Backend is a cloud-native application running on Azure that dynamically provisions and manages game servers. It uses Kubernetes (AKS) for orchestration, Azure Container Registry for images, and Azure Storage for persistence.

## Core Components

### 1. API Layer
- **Flask API**: Handles requests for server provisioning, management, and status
- **Authentication**: Azure AD integration for secure access

### 2. Orchestration Layer
- **Kubernetes Service**: Manages game server deployments on AKS
- **Service Management**: Creates LoadBalancer services with static IPs
- **Scaling**: Handles auto-scaling based on demand

### 3. Storage Layer
- **B2 Storage Service**: Manages game saves and configuration files
- **Azure Storage**: Used for persistent volumes in Kubernetes

### 4. Database Layer
- **PostgreSQL**: Stores server metadata, user information, and usage statistics

## Infrastructure

### Azure Kubernetes Service (AKS)
- **Cluster**: GameServerClusterProd in East US
- **Node Pools**:
  - System pool: For core services
  - Game pool: For game server instances (labeled with `workload=gameserver`)

### Networking
- **Load Balancer**: Azure Load Balancer with static IPs for game servers
- **IP Persistence**: Using annotations to maintain consistent IPs:
  ```
  service.beta.kubernetes.io/azure-pip-name
  service.beta.kubernetes.io/azure-dns-label-name
  service.beta.kubernetes.io/azure-load-balancer-ip-allocation-method
  ```

### Storage
- **Azure Storage Account**: gameserversa
- **File Shares**: For persistent game data
- **B2 Storage**: For backups and configuration

### Container Registry
- **ACR**: gameregistry.azurecr.io
- **Images**: Game server images with various configurations

## Deployment Flow
1. User requests game server via API
2. System provisions Kubernetes deployment with appropriate resources
3. System creates LoadBalancer service with static IP
4. System configures storage and mounts volumes
5. Game server starts and becomes available
6. Monitoring begins for activity and resource usage 

flowchart TD
    User[User/Client] --> API[API Layer]
    
    subgraph "API Layer"
        API --> ServerRoutes[Server Routes]
        API --> UserRoutes[User Routes]
        API --> GameRoutes[Game Routes]
        API --> BucketRoutes[B2 Storage Routes]
    end
    
    subgraph "Service Layer"
        ServerRoutes --> KubeService[Kubernetes Service]
        BucketRoutes --> B2Service[B2 Storage Service]
        KubeService --> DeployBuilder[K8s Deployment Builder]
    end
    
    subgraph "Azure Infrastructure"
        KubeService --> AKS[Azure Kubernetes Service]
        AKS --> SystemPool[System Node Pool]
        AKS --> GamePool[Game Node Pool]
        AKS --> AzureLB[Azure Load Balancer]
        AzureLB --> StaticIP[Static IP]
    end
    
    subgraph "Storage"
        B2Service --> B2[Backblaze B2 Storage]
        AKS --> AzureStorage[Azure Storage]
    end
    
    subgraph "Database"
        API --> PostgreSQL[PostgreSQL Database]
    end
    
    subgraph "Container Registry"
        AKS --> ACR[Azure Container Registry]
    end
    
    %% Deployment Flow
    User -- "1. Request Server" --> API
    API -- "2. Provision Server" --> KubeService
    KubeService -- "3. Create Deployment" --> AKS
    KubeService -- "4. Create Service with Static IP" --> AzureLB
    B2Service -- "5. Configure Game Files" --> B2
    AKS -- "6. Pull Game Image" --> ACR
    AKS -- "7. Mount Storage" --> AzureStorage
    AzureLB -- "8. Expose Server" --> User
    KubeService -- "9. Monitor Activity" --> AKS 