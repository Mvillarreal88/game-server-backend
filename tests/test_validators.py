"""
Unit tests for input validation schemas.
"""
import pytest
from marshmallow import ValidationError
from utils.validators import (
    StartServerSchema, StopServerSchema, PauseServerSchema, ResumeServerSchema,
    ServerIdValidator, NamespaceValidator, validate_json_request, format_validation_errors
)

class TestServerIdValidator:
    """Tests for ServerIdValidator."""
    
    def test_valid_server_ids(self):
        """Test valid server IDs."""
        validator = ServerIdValidator()
        
        valid_ids = [
            'minecraft-server-001',
            'test-server',
            'server123',
            'my-game-server',
            'a'
        ]
        
        for server_id in valid_ids:
            assert validator(server_id) == server_id
    
    def test_invalid_server_ids(self):
        """Test invalid server IDs."""
        validator = ServerIdValidator()
        
        invalid_ids = [
            'Server_123',  # Uppercase and underscore
            'server 123',  # Space
            '-server',     # Starts with hyphen
            'server-',     # Ends with hyphen
            'server@123',  # Special character
            'a' * 51,      # Too long
            ''             # Empty
        ]
        
        for server_id in invalid_ids:
            with pytest.raises(ValidationError):
                validator(server_id)

class TestNamespaceValidator:
    """Tests for NamespaceValidator."""
    
    def test_valid_namespaces(self):
        """Test valid namespace names."""
        validator = NamespaceValidator()
        
        valid_namespaces = [
            'default',
            'game-servers',
            'test123',
            'a' * 63  # Max length
        ]
        
        for namespace in valid_namespaces:
            assert validator(namespace) == namespace
    
    def test_invalid_namespaces(self):
        """Test invalid namespace names."""
        validator = NamespaceValidator()
        
        invalid_namespaces = [
            'Default',     # Uppercase
            'test_ns',     # Underscore
            'a' * 64,      # Too long
            ''             # Empty
        ]
        
        for namespace in invalid_namespaces:
            with pytest.raises(ValidationError):
                validator(namespace)

class TestStartServerSchema:
    """Tests for StartServerSchema."""
    
    def test_valid_start_server_request(self):
        """Test valid start server request."""
        schema = StartServerSchema()
        
        valid_data = {
            'package': 'standard',
            'server_id': 'minecraft-server-001',
            'namespace': 'default'
        }
        
        result = schema.load(valid_data)
        assert result == valid_data
    
    def test_start_server_missing_namespace_uses_default(self):
        """Test that missing namespace defaults to 'default'."""
        schema = StartServerSchema()
        
        data = {
            'package': 'standard',
            'server_id': 'minecraft-server-001'
        }
        
        result = schema.load(data)
        assert result['namespace'] == 'default'
    
    def test_start_server_missing_required_fields(self):
        """Test validation with missing required fields."""
        schema = StartServerSchema()
        
        # Missing package
        with pytest.raises(ValidationError) as exc_info:
            schema.load({'server_id': 'test-server'})
        assert 'package' in exc_info.value.messages
        
        # Missing server_id
        with pytest.raises(ValidationError) as exc_info:
            schema.load({'package': 'standard'})
        assert 'server_id' in exc_info.value.messages
    
    def test_start_server_invalid_package(self):
        """Test validation with invalid package."""
        schema = StartServerSchema()
        
        data = {
            'package': 'invalid-package',
            'server_id': 'test-server'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert 'package' in exc_info.value.messages

class TestStopServerSchema:
    """Tests for StopServerSchema."""
    
    def test_valid_stop_server_request(self):
        """Test valid stop server request."""
        schema = StopServerSchema()
        
        valid_data = {
            'server_id': 'minecraft-server-001',
            'namespace': 'default'
        }
        
        result = schema.load(valid_data)
        assert result == valid_data
    
    def test_stop_server_missing_namespace_uses_default(self):
        """Test that missing namespace defaults to 'default'."""
        schema = StopServerSchema()
        
        data = {'server_id': 'minecraft-server-001'}
        
        result = schema.load(data)
        assert result['namespace'] == 'default'

class TestValidationUtilities:
    """Tests for validation utility functions."""
    
    def test_validate_json_request_success(self):
        """Test successful JSON request validation."""
        data = {
            'package': 'standard',
            'server_id': 'test-server'
        }
        
        result = validate_json_request(StartServerSchema, data)
        assert result['package'] == 'standard'
        assert result['server_id'] == 'test-server'
        assert result['namespace'] == 'default'
    
    def test_validate_json_request_failure(self):
        """Test failed JSON request validation."""
        data = {'invalid': 'data'}
        
        with pytest.raises(ValidationError):
            validate_json_request(StartServerSchema, data)
    
    def test_format_validation_errors(self):
        """Test error message formatting."""
        errors = {
            'server_id': ['Server ID is required'],
            'package': ['Invalid package type', 'Package must be specified']
        }
        
        formatted = format_validation_errors(errors)
        assert 'server_id: Server ID is required' in formatted
        assert 'package: Invalid package type' in formatted
        assert 'package: Package must be specified' in formatted
    
    def test_format_validation_errors_string(self):
        """Test error message formatting with string errors."""
        errors = {
            'field1': 'Single error message',
            'field2': ['Multiple', 'error', 'messages']
        }
        
        formatted = format_validation_errors(errors)
        assert 'field1: Single error message' in formatted
        assert 'field2: Multiple' in formatted