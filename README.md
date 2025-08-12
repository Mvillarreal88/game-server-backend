# Game Server Backend (Python + Flask)

A Flask-based backend service for managing game server deployments on Azure Kubernetes Service (AKS). This service provides RESTful APIs to start, stop, and manage game servers with different resource configurations.

## Features
- Deploy game servers to AKS with configurable resource packages
- Support for multiple game types (Minecraft, Enshrouded, etc.)
- Azure AD authentication integration
- RESTful API endpoints for server management
- Kubernetes-based container orchestration
- Legacy support for Azure Container Instances (ACI)

## Prerequisites

- Python 3.12 or higher ()
- Azure CLI
- kubectl
- Azure subscription with AKS cluster
- Visual Studio Code (recommended)

## Local Development Setup

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd game-server-backend
   ```

2. Create and activate virtual environment:
   ```bash
   # Create venv
   python -m venv venv

   # Activate venv (Windows)
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Azure CLI tools:
   ```bash
   # Install Azure CLI if not already installed
   az aks install-cli
   ```

5. Configure Azure and Kubernetes credentials:
   ```bash
   # Login to Azure
   az login

   # Get AKS credentials
   az aks get-credentials --name GameServerClusterProd --resource-group GameServerRG --overwrite-existing

   # Convert kubeconfig for AAD authentication
   C:\Users\<username>\.azure-kubelogin\kubelogin.exe convert-kubeconfig
   ```

6. Create `.env` file:
   ```plaintext
   ENVIRONMENT=development
   AZURE_SUBSCRIPTION_ID=your-subscription-id
   AZURE_RESOURCE_GROUP_NAME=GameServerRG
   PORT=5000
   KUBECONFIG_CONTENT=<base64-encoded-kubeconfig>
   ```

7. Start the Flask application:
   ```bash
   python app.py
   ```

## Project Structure
game-server-backend/
├── app.py # Main Flask application
├── requirements.txt # Python dependencies
├── .env # Environment variables
├── routes/ # API route definitions
│ ├── init.py # Blueprint registration
│ ├── server_routes.py # Server management endpoints
│ ├── game_routes.py # Game information endpoints
│ └── user_routes.py # User management endpoints
├── services/ # Business logic
│ └── kubernetes_service.py # K8s integration
└── utils/ # Helper utilities
└── kubernetes_deployment_builder.py # K8s YAML generation

## Architecture

### Infrastructure Overview

```mermaid
graph TB
    subgraph "Azure Infrastructure"
        subgraph "GameServerRG (Control Plane)"
            AKS[AKS Cluster<br/>GameServerClusterProd]
            ACR[Container Registry<br/>gameregistry.azurecr.io]
            B2[B2 Cloud Storage<br/>Game Data Backup]
        end
        
        subgraph "MC_GameServerRG_..._eastus (Node Resources)"
            LB[Load Balancers]
            PIP[Public IPs]
            VM[Game Server VMs<br/>gamepool nodes]
            NSG[Network Security Groups]
        end
    end

    subgraph "Game Server Deployment Flow"
        API[Flask API<br/>POST /api/server/start-server]
        K8S[Kubernetes Service]
        POD[Game Server Pod]
        SVC[LoadBalancer Service]
    end

    API --> AKS
    AKS --> VM
    K8S --> POD
    POD --> SVC
    SVC --> LB
    LB --> PIP
    ACR --> POD
    B2 <--> POD
```

### Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as Flask API
    participant B2 as B2 Storage
    participant K8s as Kubernetes
    participant Azure as Azure Resources

    Client->>API: POST /api/server/start-server
    API->>API: Validate request (Marshmallow)
    
    API->>B2: Check existing server files
    alt No existing files
        API->>B2: Create default config files
    else Files exist
        Note over API: Will restore from backup
    end
    
    API->>K8s: Deploy game server pod
    K8s->>Azure: Create VM in gamepool
    K8s->>Azure: Create LoadBalancer service
    Azure->>Azure: Allocate static public IP
    Azure->>Azure: Configure DNS (server-id.eastus.cloudapp.azure.com)
    
    K8s-->>API: Deployment successful
    Azure-->>API: IP address assigned
    API-->>Client: Server connection info
    
    Note over Client, Azure: Player connects to game server
```

### Resource Group Architecture

```mermaid
graph LR
    subgraph "GameServerRG (Main Resource Group)"
        direction TB
        AKS[AKS Cluster Control Plane]
        ACR[Container Registry]
        VNET[Virtual Network]
        IAM[Identity & Access Management]
    end
    
    subgraph "MC_GameServerRG_GameServerClusterProd_eastus"
        direction TB
        VMSS[Virtual Machine Scale Set<br/>gamepool nodes]
        ALB[Azure Load Balancers]
        PIPS[Static Public IPs]
        DISK[Managed Disks]
        NSG[Network Security Groups]
        RT[Route Tables]
    end
    
    AKS -.->|manages| VMSS
    AKS -.->|creates| ALB
    AKS -.->|allocates| PIPS
    VMSS -->|hosts| POD[Game Server Pods]
    POD -->|exposes via| ALB
    
    style GameServerRG fill:#e1f5fe
    style MC_GameServerRG_GameServerClusterProd_eastus fill:#f3e5f5
```

### Game Server Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Requested: API Call
    Requested --> Validating: Marshmallow Schema
    Validating --> BackupCheck: Valid Request
    Validating --> [*]: Invalid Request (400)
    
    BackupCheck --> CreatingDefaults: No Existing Files
    BackupCheck --> RestoringFiles: Files Found in B2
    
    CreatingDefaults --> Deploying: Default configs saved
    RestoringFiles --> Deploying: Backup restored
    
    Deploying --> Starting: Pod Created
    Starting --> IPAllocation: Container Running
    IPAllocation --> Running: LoadBalancer Ready
    
    Running --> Pausing: User Request
    Running --> Stopping: User Request
    Running --> Failed: Health Check Failed
    
    Pausing --> BackingUp: Save world data
    BackingUp --> Paused: Scale to 0 replicas
    Paused --> Starting: Resume Request
    
    Stopping --> BackingUp
    BackingUp --> Cleanup: Files saved to B2
    Cleanup --> [*]: Resources deleted
    
    Failed --> BackingUp: Auto-recovery
```

## API Endpoints

### Server Management
- `POST /api/server/start-server`: Start a new game server
- `POST /api/server/stop-server`: Stop a running server
- Legacy ACI endpoints:
  - `POST /start-server`
  - `POST /stop-server`
  - `GET /server-status/<server_id>`

### Game Information
- `GET /api/game/info/<game>`: Get game configuration details

### User Management
- `GET /api/user/info`: Get user information
- `GET /api/user/servers`: List user's servers

## Testing

### API Testing with Postman

1. Start a game server:
   ```http
   POST http://localhost:5000/api/server/start-server
   Content-Type: application/json

   {
       "package": "standard",
       "server_id": "minecraft-server-001",
       "namespace": "default"
   }
   ```

2. Check deployment in Azure Portal:
   - Navigate to Azure Kubernetes Service > GameServerClusterProd
   - Check Workloads > Deployments

3. Monitor with kubectl:
   ```bash
   # View nodes
   kubectl get nodes

   # View deployments
   kubectl get deployments -n default

   # View pods
   kubectl get pods -n default
   ```

## Game Packages

Currently supported package configurations:

json
"standard": {
"cpu": 2000, # 2 cores
"memory": 6144, # 6 GB in MiB
"image": "gameregistry.azurecr.io/minecraft-server:latest",
"port": 25565,
"env_vars": {
"EULA": "TRUE",
"MEMORY": "5G",
"SERVER_NAME": "Azure Test Minecraft Server"
}
}

## Deployment

The application is configured for deployment to Azure App Service via GitHub Actions. The workflow is defined in `.github/workflows/main_game-server-backend.yml` and includes:
- Python 3.12 setup
- Dependencies installation
- Build and deployment to Azure Web App
- Azure authentication using managed identity

## Common Issues and Solutions

1. Kubelogin not found:
   - Run `az aks install-cli`
   - Update kubeconfig with full path to kubelogin.exe

2. Authentication errors:
   - Run `az login`
   - Get fresh credentials with `az aks get-credentials`

3. Virtual Environment Issues:
   - Ensure you're in the correct directory
   - Activate venv before installing dependencies
   - Use the correct activation script for your OS

4. Azure Portal Access:
   - Workloads: Azure Portal > Kubernetes Services > GameServerClusterProd > Workloads
   - Monitoring: Azure Portal > Kubernetes Services > GameServerClusterProd > Insights

## Environment Variables

Required environment variables in `.env` and Azure App Service:
- `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID
- `AZURE_RESOURCE_GROUP_NAME`: Resource group containing AKS cluster
- `KUBECONFIG`: Path to your kubeconfig file
- `B2_KEY_ID`: Backblaze B2 key ID
- `B2_KEY_NAME`: Backblaze B2 key name
- `B2_APP_KEY`: Backblaze B2 application key

## License

MIT License