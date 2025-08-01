"""
Centralized configuration management for the game server backend.
"""
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Settings:
    """Application settings with environment variable support and validation."""
    
    def __init__(self):
        """Initialize settings from environment variables."""
        # Environment
        self.ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development')
        self.PORT: int = int(os.getenv('PORT', '8000' if self.ENVIRONMENT == 'production' else '5000'))
        
        # Azure Configuration
        self.AZURE_SUBSCRIPTION_ID: Optional[str] = os.getenv('AZURE_SUBSCRIPTION_ID')
        self.AZURE_RESOURCE_GROUP: str = os.getenv('AZURE_RESOURCE_GROUP_NAME', 'GameServerRG')
        
        # AKS Configuration
        self.AKS_CLUSTER_URL: Optional[str] = os.getenv('AKS_CLUSTER_URL')
        self.AKS_SERVER_ID: Optional[str] = os.getenv('AKS_SERVER_ID')
        self.AKS_CLUSTER_CA_CERT: Optional[str] = os.getenv('AKS_CLUSTER_CA_CERT')
        
        # B2 Storage Configuration
        self.B2_KEY_ID: Optional[str] = os.getenv('B2_KEY_ID')
        self.B2_KEY_NAME: Optional[str] = os.getenv('B2_KEY_NAME')
        self.B2_APP_KEY: Optional[str] = os.getenv('B2_APP_KEY')
        self.B2_BUCKET_NAME: str = os.getenv('B2_BUCKET_NAME', 'mc-test-v1')
        
        # Kubernetes Configuration
        self.KUBECONFIG_CONTENT: Optional[str] = os.getenv('KUBECONFIG_CONTENT')
        
        # Default Azure Resource Groups (avoid hardcoding)
        self.DEFAULT_MC_RESOURCE_GROUP: str = os.getenv(
            'MC_RESOURCE_GROUP', 
            'MC_GameServerRG_GameServerClusterProd_eastus'
        )
    
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