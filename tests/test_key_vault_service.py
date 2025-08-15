"""
Tests for Azure Key Vault service integration.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
from services.key_vault_service import KeyVaultService


class TestKeyVaultService:
    """Test cases for Key Vault service."""

    @pytest.fixture
    def mock_secret_client(self):
        """Create a mock SecretClient."""
        return Mock()

    @pytest.fixture
    def mock_credential(self):
        """Create a mock DefaultAzureCredential."""
        return Mock()

    def test_initialization_success(self, mock_secret_client, mock_credential):
        """Test successful Key Vault initialization."""
        with patch('services.key_vault_service.DefaultAzureCredential', return_value=mock_credential), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client):
            
            service = KeyVaultService("test-vault")
            
            assert service.vault_name == "test-vault"
            assert service.vault_url == "https://test-vault.vault.azure.net/"
            assert service.client == mock_secret_client
            assert service.is_available() is True

    def test_initialization_auth_failure(self, mock_credential):
        """Test Key Vault initialization with authentication failure."""
        mock_credential.side_effect = ClientAuthenticationError("Auth failed")
        
        with patch('services.key_vault_service.DefaultAzureCredential', return_value=mock_credential), \
             patch('services.key_vault_service.SecretClient', side_effect=ClientAuthenticationError("Auth failed")):
            
            service = KeyVaultService("test-vault")
            
            assert service.client is None
            assert service.is_available() is False

    def test_get_secret_success(self, mock_secret_client):
        """Test successful secret retrieval."""
        # Mock secret response
        mock_secret = Mock()
        mock_secret.value = "secret-value-123"
        mock_secret_client.get_secret.return_value = mock_secret
        
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client):
            
            service = KeyVaultService("test-vault")
            result = service.get_secret("test-secret")
            
            assert result == "secret-value-123"
            mock_secret_client.get_secret.assert_called_once_with("test-secret")

    def test_get_secret_not_found_with_fallback(self, mock_secret_client):
        """Test secret not found with environment variable fallback."""
        mock_secret_client.get_secret.side_effect = ResourceNotFoundError("Secret not found")
        
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client), \
             patch('os.getenv', return_value="env-fallback-value"):
            
            service = KeyVaultService("test-vault")
            result = service.get_secret("test-secret", "TEST_ENV_VAR")
            
            assert result == "env-fallback-value"

    def test_get_secret_not_found_no_fallback(self, mock_secret_client):
        """Test secret not found without fallback."""
        mock_secret_client.get_secret.side_effect = ResourceNotFoundError("Secret not found")
        
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client):
            
            service = KeyVaultService("test-vault")
            result = service.get_secret("test-secret")
            
            assert result is None

    def test_get_secret_caching(self, mock_secret_client):
        """Test that secrets are cached properly."""
        mock_secret = Mock()
        mock_secret.value = "cached-secret-value"
        mock_secret_client.get_secret.return_value = mock_secret
        
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client):
            
            service = KeyVaultService("test-vault")
            
            # First call
            result1 = service.get_secret("test-secret")
            # Second call (should use cache)
            result2 = service.get_secret("test-secret")
            
            assert result1 == "cached-secret-value"
            assert result2 == "cached-secret-value"
            # Should only call Key Vault once due to caching
            mock_secret_client.get_secret.assert_called_once_with("test-secret")

    def test_get_multiple_secrets(self, mock_secret_client):
        """Test retrieving multiple secrets at once."""
        def mock_get_secret(secret_name):
            mock_secret = Mock()
            if secret_name == "secret1":
                mock_secret.value = "value1"
            elif secret_name == "secret2":
                mock_secret.value = "value2"
            else:
                raise ResourceNotFoundError("Not found")
            return mock_secret
        
        mock_secret_client.get_secret.side_effect = mock_get_secret
        
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client), \
             patch('os.getenv', return_value="env-value"):
            
            service = KeyVaultService("test-vault")
            
            secret_mapping = {
                "secret1": "ENV1",
                "secret2": "ENV2", 
                "secret3": "ENV3"  # This one will fail and use env fallback
            }
            
            results = service.get_multiple_secrets(secret_mapping)
            
            assert results["secret1"] == "value1"
            assert results["secret2"] == "value2"
            assert results["secret3"] == "env-value"  # Fallback to env var

    def test_clear_cache(self, mock_secret_client):
        """Test cache clearing functionality."""
        mock_secret = Mock()
        mock_secret.value = "secret-value"
        mock_secret_client.get_secret.return_value = mock_secret
        
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client):
            
            service = KeyVaultService("test-vault")
            
            # Get secret (will be cached)
            service.get_secret("test-secret")
            assert "test-secret" in service._secrets_cache
            
            # Clear cache
            service.clear_cache()
            assert len(service._secrets_cache) == 0

    def test_client_unavailable_fallback(self):
        """Test behavior when Key Vault client is unavailable."""
        with patch('services.key_vault_service.DefaultAzureCredential', side_effect=Exception("No connection")), \
             patch('os.getenv', return_value="fallback-value"):
            
            service = KeyVaultService("test-vault")
            
            assert service.client is None
            assert service.is_available() is False
            
            result = service.get_secret("test-secret", "TEST_ENV_VAR")
            assert result == "fallback-value"


class TestKeyVaultIntegration:
    """Integration tests for Key Vault with settings."""

    @patch('config.settings.key_vault_service')
    def test_settings_with_key_vault_available(self, mock_kv_service):
        """Test settings initialization with Key Vault available."""
        # Mock Key Vault service
        mock_kv_service.is_available.return_value = True
        mock_kv_service.get_multiple_secrets.return_value = {
            'azure-subscription-id': 'kv-subscription-123',
            'b2-key-id': 'kv-b2-key-456',
            'b2-app-key': 'kv-b2-app-789',
            'aks-cluster-url': 'https://kv-cluster.eastus.azmk8s.io',
            'aks-server-id': 'kv-server-id',
            'aks-cluster-ca-cert': 'kv-ca-cert-data',
            'b2-key-name': 'kv-b2-key-name',
            'kubeconfig-content': 'kv-kubeconfig-content'
        }
        
        # Import and reinitialize settings
        import importlib
        import config.settings
        importlib.reload(config.settings)
        
        from config.settings import Settings
        settings = Settings()
        
        # Verify secrets loaded from Key Vault
        assert settings.AZURE_SUBSCRIPTION_ID == 'kv-subscription-123'
        assert settings.B2_KEY_ID == 'kv-b2-key-456'
        assert settings.B2_APP_KEY == 'kv-b2-app-789'
        assert settings.AKS_CLUSTER_URL == 'https://kv-cluster.eastus.azmk8s.io'

    @patch('config.settings.KEYVAULT_AVAILABLE', False)
    @patch.dict('os.environ', {
        'AZURE_SUBSCRIPTION_ID': 'env-subscription-123',
        'B2_KEY_ID': 'env-b2-key-456',
        'B2_APP_KEY': 'env-b2-app-789'
    })
    def test_settings_with_key_vault_unavailable(self):
        """Test settings fallback to environment variables when Key Vault unavailable."""
        # Import and reinitialize settings
        import importlib
        import config.settings
        importlib.reload(config.settings)
        
        from config.settings import Settings
        settings = Settings()
        
        # Verify fallback to environment variables
        assert settings.AZURE_SUBSCRIPTION_ID == 'env-subscription-123'
        assert settings.B2_KEY_ID == 'env-b2-key-456'
        assert settings.B2_APP_KEY == 'env-b2-app-789'

    def test_key_vault_service_singleton(self):
        """Test that key_vault_service is properly initialized as singleton."""
        from services.key_vault_service import key_vault_service
        
        # Should be initialized with default vault name
        assert key_vault_service.vault_name == "servervault"
        assert key_vault_service.vault_url == "https://servervault.vault.azure.net/"


class TestKeyVaultErrorHandling:
    """Test error handling scenarios for Key Vault service."""

    def test_network_timeout(self, mock_secret_client):
        """Test handling of network timeouts."""
        from azure.core.exceptions import ServiceRequestTimeoutError
        
        mock_secret_client.get_secret.side_effect = ServiceRequestTimeoutError("Timeout")
        
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client), \
             patch('os.getenv', return_value="timeout-fallback"):
            
            service = KeyVaultService("test-vault")
            result = service.get_secret("test-secret", "TEST_ENV_VAR")
            
            assert result == "timeout-fallback"

    def test_permission_denied(self, mock_secret_client):
        """Test handling of permission denied errors."""
        from azure.core.exceptions import HttpResponseError
        
        mock_response = Mock()
        mock_response.status_code = 403
        mock_secret_client.get_secret.side_effect = HttpResponseError("Forbidden", response=mock_response)
        
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', return_value=mock_secret_client):
            
            service = KeyVaultService("test-vault")
            result = service.get_secret("test-secret")
            
            assert result is None

    def test_malformed_vault_url(self):
        """Test handling of malformed vault URLs."""
        with patch('services.key_vault_service.DefaultAzureCredential'), \
             patch('services.key_vault_service.SecretClient', side_effect=ValueError("Invalid URL")):
            
            service = KeyVaultService("invalid-vault-name!")
            
            assert service.client is None
            assert service.is_available() is False