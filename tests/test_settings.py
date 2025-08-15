"""
Unit tests for configuration settings.
"""
import pytest
import os
from unittest.mock import patch
from config.settings import Settings

class TestSettings:
    """Tests for Settings class."""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_default_values(self):
        """Test default configuration values."""
        settings = Settings()
        
        assert settings.ENVIRONMENT == 'development'
        assert settings.PORT == 5000  # Development default
        assert settings.AZURE_RESOURCE_GROUP == 'GameServerRG'
        assert settings.B2_BUCKET_NAME == 'mc-test-v1'
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'PORT': '8080',
        'AZURE_RESOURCE_GROUP_NAME': 'CustomRG',
        'B2_BUCKET_NAME': 'custom-bucket'
    })
    def test_environment_override(self):
        """Test environment variable overrides."""
        settings = Settings()
        
        assert settings.ENVIRONMENT == 'production'
        assert settings.PORT == 8080
        assert settings.AZURE_RESOURCE_GROUP == 'CustomRG'
        assert settings.B2_BUCKET_NAME == 'custom-bucket'
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'production'}, clear=True)
    def test_production_port_default(self):
        """Test production port default."""
        settings = Settings()
        
        assert settings.PORT == 8000  # Production default
    
    def test_is_production(self):
        """Test production environment check."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            settings = Settings()
            assert settings.is_production() is True
            assert settings.is_development() is False
    
    def test_is_development(self):
        """Test development environment check."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            settings = Settings()
            assert settings.is_development() is True
            assert settings.is_production() is False
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'AZURE_SUBSCRIPTION_ID': 'test-sub-id',
        'AKS_CLUSTER_URL': 'https://test.cluster.com',
        'AKS_SERVER_ID': 'test-server-id',
        'AKS_CLUSTER_CA_CERT': 'test-cert',
        'B2_KEY_ID': 'test-key-id',
        'B2_APP_KEY': 'test-app-key'
    })
    def test_validate_required_settings_production_success(self):
        """Test successful production settings validation."""
        settings = Settings()
        
        missing = settings.validate_required_settings()
        assert len(missing) == 0
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'B2_KEY_ID': 'test-key-id'
        # Missing other required production settings
    }, clear=True)
    @patch('config.settings.KEYVAULT_AVAILABLE', False)  # Disable Key Vault for this test
    def test_validate_required_settings_production_missing(self):
        """Test production settings validation with missing values."""
        settings = Settings()
        
        missing = settings.validate_required_settings()
        assert 'AZURE_SUBSCRIPTION_ID' in missing
        assert 'AKS_CLUSTER_URL' in missing
        assert 'AKS_SERVER_ID' in missing
        assert 'AKS_CLUSTER_CA_CERT' in missing
        assert 'B2_APP_KEY' in missing
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'development'
        # Missing B2 credentials
    }, clear=True)
    def test_validate_required_settings_development_missing_b2(self):
        """Test development settings validation with missing B2 credentials."""
        settings = Settings()
        
        missing = settings.validate_required_settings()
        assert 'B2_KEY_ID' in missing
        assert 'B2_APP_KEY' in missing
    
    @patch('config.settings.logger')
    def test_log_configuration(self, mock_logger):
        """Test configuration logging."""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'test',
            'PORT': '3000',
            'AZURE_RESOURCE_GROUP_NAME': 'TestRG',
            'B2_BUCKET_NAME': 'test-bucket',
            'AZURE_SUBSCRIPTION_ID': 'test-sub',
            'B2_KEY_ID': 'test-key',
            'B2_APP_KEY': 'test-app-key'
        }):
            settings = Settings()
            settings.log_configuration()
            
            # Verify that info logs were called
            assert mock_logger.info.call_count >= 5
            
            # Check that sensitive information is not logged directly
            call_args_list = [call[0][0] for call in mock_logger.info.call_args_list]
            log_messages = ' '.join(call_args_list)
            
            assert 'test-sub' not in log_messages  # Subscription ID should not be logged
            assert 'test-key' not in log_messages  # Keys should not be logged
            assert 'test-app-key' not in log_messages  # App key should not be logged