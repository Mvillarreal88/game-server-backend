"""
Centralized configuration management for the game server backend.
"""
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Import Key Vault service (with fallback if not available)
try:
    from services.key_vault_service import key_vault_service
    KEYVAULT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Key Vault service not available: {e}")
    key_vault_service = None
    KEYVAULT_AVAILABLE = False

class Settings:
    """Application settings with environment variable support and validation."""
    
    def __init__(self):
        """Initialize settings from environment variables and Key Vault."""
        # Environment (always from env vars)
        self.ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development')
        self.PORT: int = int(os.getenv('PORT', '8000' if self.ENVIRONMENT == 'production' else '5000'))
        
        # Load secrets from Key Vault or environment variables
        self._load_secrets()
        
        # Non-sensitive configuration (can stay as env vars)
        self.AZURE_RESOURCE_GROUP: str = os.getenv('AZURE_RESOURCE_GROUP_NAME', 'GameServerRG')
        self.B2_BUCKET_NAME: str = os.getenv('B2_BUCKET_NAME', 'mc-test-v1')
        
        # Default Azure Resource Groups (avoid hardcoding)
        self.DEFAULT_MC_RESOURCE_GROUP: str = os.getenv(
            'MC_RESOURCE_GROUP', 
            'MC_GameServerRG_GameServerClusterProd_eastus'
        )
    
    def _load_secrets(self):
        """Load sensitive configuration from Key Vault with environment variable fallbacks."""
        # Define secret mappings: {key_vault_secret_name: env_var_fallback}
        secret_mappings = {
            'azure-subscription-id': 'AZURE_SUBSCRIPTION_ID',
            'aks-cluster-url': 'AKS_CLUSTER_URL', 
            'aks-server-id': 'AKS_SERVER_ID',
            'aks-cluster-ca-cert': 'AKS_CLUSTER_CA_CERT',
            'b2-key-id': 'B2_KEY_ID',
            'b2-key-name': 'B2_KEY_NAME',
            'b2-app-key': 'B2_APP_KEY',
            'kubeconfig-content': 'KUBECONFIG_CONTENT'
        }
        
        if (KEYVAULT_AVAILABLE and key_vault_service and key_vault_service.is_available() 
            and self.ENVIRONMENT == 'production'):
            logger.info("Loading secrets from Azure Key Vault")
            secrets = key_vault_service.get_multiple_secrets(secret_mappings)
            
            # Assign secrets to instance variables
            self.AZURE_SUBSCRIPTION_ID = secrets.get('azure-subscription-id')
            self.AKS_CLUSTER_URL = secrets.get('aks-cluster-url')
            self.AKS_SERVER_ID = secrets.get('aks-server-id')
            self.AKS_CLUSTER_CA_CERT = secrets.get('aks-cluster-ca-cert')
            self.B2_KEY_ID = secrets.get('b2-key-id')
            self.B2_KEY_NAME = secrets.get('b2-key-name')
            self.B2_APP_KEY = secrets.get('b2-app-key')
            self.KUBECONFIG_CONTENT = secrets.get('kubeconfig-content')
            
        else:
            if self.ENVIRONMENT == 'production':
                logger.info("Key Vault not available, using environment variables")
            else:
                logger.info("Development mode, using environment variables")
            # Fallback to environment variables
            self.AZURE_SUBSCRIPTION_ID = os.getenv('AZURE_SUBSCRIPTION_ID')
            self.AKS_CLUSTER_URL = os.getenv('AKS_CLUSTER_URL')
            self.AKS_SERVER_ID = os.getenv('AKS_SERVER_ID')
            self.AKS_CLUSTER_CA_CERT = os.getenv('AKS_CLUSTER_CA_CERT')
            self.B2_KEY_ID = os.getenv('B2_KEY_ID')
            self.B2_KEY_NAME = os.getenv('B2_KEY_NAME')
            self.B2_APP_KEY = os.getenv('B2_APP_KEY')
            self.KUBECONFIG_CONTENT = os.getenv('KUBECONFIG_CONTENT')
    
    def validate_required_settings(self) -> list[str]:
        """
        Validate that required settings are present.
        Returns list of missing required settings.
        """
        missing = []
        
        if self.ENVIRONMENT == 'production':
            required_production = [
                ('AZURE_SUBSCRIPTION_ID', self.AZURE_SUBSCRIPTION_ID),
                ('AKS_CLUSTER_URL', self.AKS_CLUSTER_URL),
                ('AKS_SERVER_ID', self.AKS_SERVER_ID),
                ('AKS_CLUSTER_CA_CERT', self.AKS_CLUSTER_CA_CERT),
                ('B2_KEY_ID', self.B2_KEY_ID),
                ('B2_APP_KEY', self.B2_APP_KEY),
            ]
            
            for name, value in required_production:
                if not value:
                    missing.append(name)
        
        # Always required
        if not self.B2_KEY_ID or not self.B2_APP_KEY:
            if 'B2_KEY_ID' not in missing:
                missing.append('B2_KEY_ID')
            if 'B2_APP_KEY' not in missing:
                missing.append('B2_APP_KEY')
        
        return missing
    
    def log_configuration(self) -> None:
        """Log current configuration (without sensitive values)."""
        logger.info(f"Environment: {self.ENVIRONMENT}")
        logger.info(f"Port: {self.PORT}")
        logger.info(f"Azure Resource Group: {self.AZURE_RESOURCE_GROUP}")
        logger.info(f"B2 Bucket: {self.B2_BUCKET_NAME}")
        logger.info(f"Has Azure Subscription ID: {bool(self.AZURE_SUBSCRIPTION_ID)}")
        logger.info(f"Has B2 Credentials: {bool(self.B2_KEY_ID and self.B2_APP_KEY)}")
        
        if self.ENVIRONMENT == 'production':
            logger.info(f"Has AKS Config: {bool(self.AKS_CLUSTER_URL and self.AKS_SERVER_ID)}")
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == 'development'

# Create a global settings instance
settings = Settings()

# Validate settings on import
missing_settings = settings.validate_required_settings()
if missing_settings:
    logger.warning(f"Missing required environment variables: {', '.join(missing_settings)}")
    if settings.is_production():
        logger.error("Cannot start in production without required settings!")
        # In production, you might want to raise an exception here
        # raise ValueError(f"Missing required settings: {', '.join(missing_settings)}")