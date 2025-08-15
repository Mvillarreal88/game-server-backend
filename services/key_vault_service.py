"""
Azure Key Vault service for secure secret management.
"""
import logging
from typing import Optional, Dict, Any
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
import os

logger = logging.getLogger(__name__)

class KeyVaultService:
    """Service for retrieving secrets from Azure Key Vault."""
    
    def __init__(self, vault_name: str = "game-secret-vault"):
        """
        Initialize Key Vault service.
        
        Args:
            vault_name: Name of the Azure Key Vault
        """
        self.vault_name = vault_name
        self.vault_url = f"https://{vault_name}.vault.azure.net/"
        self.client: Optional[SecretClient] = None
        self._secrets_cache: Dict[str, str] = {}
        
        # Initialize client with retry logic
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the Key Vault client with proper authentication."""
        try:
            # Use DefaultAzureCredential for authentication
            # This supports multiple auth methods: Managed Identity, Azure CLI, etc.
            credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=credential)
            
            # Test connection by attempting to list secrets
            logger.info(f"Successfully connected to Key Vault: {self.vault_name}")
            
        except ClientAuthenticationError as e:
            logger.error(f"Failed to authenticate with Key Vault {self.vault_name}: {str(e)}")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Key Vault client: {str(e)}")
            self.client = None
    
    def get_secret(self, secret_name: str, fallback_env_var: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret from Key Vault with fallback to environment variable.
        
        Args:
            secret_name: Name of the secret in Key Vault
            fallback_env_var: Environment variable to use as fallback
            
        Returns:
            Secret value or None if not found
        """
        # Check cache first
        if secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]
        
        # Try Key Vault first
        if self.client:
            try:
                secret = self.client.get_secret(secret_name)
                self._secrets_cache[secret_name] = secret.value
                logger.debug(f"Retrieved secret '{secret_name}' from Key Vault")
                return secret.value
                
            except ResourceNotFoundError:
                logger.warning(f"Secret '{secret_name}' not found in Key Vault {self.vault_name}")
            except Exception as e:
                logger.error(f"Error retrieving secret '{secret_name}' from Key Vault: {str(e)}")
        
        # Fallback to environment variable
        if fallback_env_var:
            env_value = os.getenv(fallback_env_var)
            if env_value:
                logger.info(f"Using environment variable '{fallback_env_var}' as fallback for '{secret_name}'")
                self._secrets_cache[secret_name] = env_value
                return env_value
        
        logger.warning(f"Secret '{secret_name}' not found in Key Vault or environment variables")
        return None
    
    def get_multiple_secrets(self, secret_mapping: Dict[str, str]) -> Dict[str, Optional[str]]:
        """
        Retrieve multiple secrets at once.
        
        Args:
            secret_mapping: Dict of {secret_name: fallback_env_var}
            
        Returns:
            Dict of {secret_name: secret_value}
        """
        results = {}
        for secret_name, fallback_env in secret_mapping.items():
            results[secret_name] = self.get_secret(secret_name, fallback_env)
        return results
    
    def is_available(self) -> bool:
        """Check if Key Vault service is available and properly configured."""
        return self.client is not None
    
    def clear_cache(self) -> None:
        """Clear the secrets cache (useful for testing or secret rotation)."""
        self._secrets_cache.clear()
        logger.info("Key Vault secrets cache cleared")

# Global Key Vault service instance
key_vault_service = KeyVaultService()