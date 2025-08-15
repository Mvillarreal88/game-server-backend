#!/bin/bash

# Azure Key Vault Secret Setup Script
# Run this script to migrate your secrets from environment variables to Azure Key Vault

set -e  # Exit on any error

# Configuration
VAULT_NAME="servervault"
RESOURCE_GROUP="GameServerRG"

echo "🔐 Setting up Azure Key Vault secrets for Game Server Backend"
echo "Vault: $VAULT_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo ""

# Check if user is logged in to Azure
echo "Checking Azure CLI authentication..."
if ! az account show &> /dev/null; then
    echo "❌ Not logged in to Azure CLI. Please run 'az login' first."
    exit 1
fi

echo "✅ Azure CLI authenticated"
echo ""

# Verify Key Vault exists
echo "Verifying Key Vault exists..."
if ! az keyvault show --name "$VAULT_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo "❌ Key Vault '$VAULT_NAME' not found in resource group '$RESOURCE_GROUP'"
    echo "Please create the Key Vault first:"
    echo "az keyvault create --name $VAULT_NAME --resource-group $RESOURCE_GROUP --location eastus"
    exit 1
fi

echo "✅ Key Vault '$VAULT_NAME' found"
echo ""

# Function to set secret if environment variable exists
set_secret_from_env() {
    local secret_name="$1"
    local env_var="$2"
    local description="$3"
    
    if [ -n "${!env_var}" ]; then
        echo "📝 Setting secret '$secret_name' from $env_var"
        az keyvault secret set \
            --vault-name "$VAULT_NAME" \
            --name "$secret_name" \
            --value "${!env_var}" \
            --description "$description" \
            --only-show-errors
        echo "✅ Secret '$secret_name' set successfully"
    else
        echo "⚠️  Environment variable $env_var not set, skipping secret '$secret_name'"
        echo "   You can set it manually later with:"
        echo "   az keyvault secret set --vault-name $VAULT_NAME --name $secret_name --value 'YOUR_VALUE'"
    fi
    echo ""
}

# Set secrets from environment variables
echo "🚀 Creating secrets in Key Vault..."
echo ""

set_secret_from_env "azure-subscription-id" "AZURE_SUBSCRIPTION_ID" "Azure subscription ID for resource management"
set_secret_from_env "aks-cluster-url" "AKS_CLUSTER_URL" "AKS cluster API server URL"
set_secret_from_env "aks-server-id" "AKS_SERVER_ID" "AKS server identifier for authentication"
set_secret_from_env "aks-cluster-ca-cert" "AKS_CLUSTER_CA_CERT" "AKS cluster CA certificate for secure communication"
set_secret_from_env "b2-key-id" "B2_KEY_ID" "B2 Cloud Storage application key ID"
set_secret_from_env "b2-key-name" "B2_KEY_NAME" "B2 Cloud Storage key name"
set_secret_from_env "b2-app-key" "B2_APP_KEY" "B2 Cloud Storage application key"
set_secret_from_env "kubeconfig-content" "KUBECONFIG_CONTENT" "Kubernetes configuration content"

echo "🎉 Key Vault setup complete!"
echo ""

# Display next steps
echo "📋 Next Steps:"
echo "1. Grant your Azure App Service Managed Identity access to Key Vault:"
echo "   az keyvault set-policy --name $VAULT_NAME --object-id <APP_MANAGED_IDENTITY_ID> --secret-permissions get list"
echo ""
echo "2. Deploy your application with ENVIRONMENT=production"
echo ""
echo "3. Remove environment variables from your deployment (they'll fallback to Key Vault)"
echo ""

# List all secrets for verification
echo "🔍 Secrets created in Key Vault:"
az keyvault secret list --vault-name "$VAULT_NAME" --query "[].{Name:name, Enabled:attributes.enabled}" --output table

echo ""
echo "✅ All done! Your secrets are now securely stored in Azure Key Vault."