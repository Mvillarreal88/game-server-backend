# Azure Key Vault Secret Setup Script (PowerShell)
# Run this script to migrate your secrets from environment variables to Azure Key Vault

param(
    [string]$VaultName = "servervault",
    [string]$ResourceGroup = "GameServerRG"
)

$ErrorActionPreference = "Stop"

Write-Host "🔐 Setting up Azure Key Vault secrets for Game Server Backend" -ForegroundColor Cyan
Write-Host "Vault: $VaultName" -ForegroundColor White
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host ""

# Check if user is logged in to Azure
Write-Host "Checking Azure CLI authentication..." -ForegroundColor Yellow
try {
    az account show | Out-Null
    Write-Host "✅ Azure CLI authenticated" -ForegroundColor Green
} catch {
    Write-Host "❌ Not logged in to Azure CLI. Please run 'az login' first." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Verify Key Vault exists
Write-Host "Verifying Key Vault exists..." -ForegroundColor Yellow
try {
    az keyvault show --name $VaultName --resource-group $ResourceGroup | Out-Null
    Write-Host "✅ Key Vault '$VaultName' found" -ForegroundColor Green
} catch {
    Write-Host "❌ Key Vault '$VaultName' not found in resource group '$ResourceGroup'" -ForegroundColor Red
    Write-Host "Please create the Key Vault first:" -ForegroundColor Yellow
    Write-Host "az keyvault create --name $VaultName --resource-group $ResourceGroup --location eastus" -ForegroundColor White
    exit 1
}

Write-Host ""

# Function to set secret if environment variable exists
function Set-SecretFromEnv {
    param(
        [string]$SecretName,
        [string]$EnvVar,
        [string]$Description
    )
    
    $envValue = [Environment]::GetEnvironmentVariable($EnvVar)
    
    if ($envValue) {
        Write-Host "📝 Setting secret '$SecretName' from $EnvVar" -ForegroundColor Yellow
        az keyvault secret set `
            --vault-name $VaultName `
            --name $SecretName `
            --value $envValue `
            --description $Description `
            --only-show-errors
        Write-Host "✅ Secret '$SecretName' set successfully" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Environment variable $EnvVar not set, skipping secret '$SecretName'" -ForegroundColor Yellow
        Write-Host "   You can set it manually later with:" -ForegroundColor Gray
        Write-Host "   az keyvault secret set --vault-name $VaultName --name $SecretName --value 'YOUR_VALUE'" -ForegroundColor Gray
    }
    Write-Host ""
}

# Set secrets from environment variables
Write-Host "🚀 Creating secrets in Key Vault..." -ForegroundColor Cyan
Write-Host ""

Set-SecretFromEnv -SecretName "azure-subscription-id" -EnvVar "AZURE_SUBSCRIPTION_ID" -Description "Azure subscription ID for resource management"
Set-SecretFromEnv -SecretName "aks-cluster-url" -EnvVar "AKS_CLUSTER_URL" -Description "AKS cluster API server URL"
Set-SecretFromEnv -SecretName "aks-server-id" -EnvVar "AKS_SERVER_ID" -Description "AKS server identifier for authentication"
Set-SecretFromEnv -SecretName "aks-cluster-ca-cert" -EnvVar "AKS_CLUSTER_CA_CERT" -Description "AKS cluster CA certificate for secure communication"
Set-SecretFromEnv -SecretName "b2-key-id" -EnvVar "B2_KEY_ID" -Description "B2 Cloud Storage application key ID"
Set-SecretFromEnv -SecretName "b2-key-name" -EnvVar "B2_KEY_NAME" -Description "B2 Cloud Storage key name"
Set-SecretFromEnv -SecretName "b2-app-key" -EnvVar "B2_APP_KEY" -Description "B2 Cloud Storage application key"
Set-SecretFromEnv -SecretName "kubeconfig-content" -EnvVar "KUBECONFIG_CONTENT" -Description "Kubernetes configuration content"

Write-Host "🎉 Key Vault setup complete!" -ForegroundColor Green
Write-Host ""

# Display next steps
Write-Host "📋 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Grant your Azure App Service Managed Identity access to Key Vault:" -ForegroundColor White
Write-Host "   az keyvault set-policy --name $VaultName --object-id <APP_MANAGED_IDENTITY_ID> --secret-permissions get list" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Deploy your application with ENVIRONMENT=production" -ForegroundColor White
Write-Host ""
Write-Host "3. Remove environment variables from your deployment (they'll fallback to Key Vault)" -ForegroundColor White
Write-Host ""

# List all secrets for verification
Write-Host "🔍 Secrets created in Key Vault:" -ForegroundColor Cyan
az keyvault secret list --vault-name $VaultName --query "[].{Name:name, Enabled:attributes.enabled}" --output table

Write-Host ""
Write-Host "✅ All done! Your secrets are now securely stored in Azure Key Vault." -ForegroundColor Green