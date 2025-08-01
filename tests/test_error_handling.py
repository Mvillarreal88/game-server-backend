"""
Unit tests for error handling utilities.
"""
import pytest
import logging
from unittest.mock import Mock, patch
from config.logging_config import ErrorHandler
from marshmallow import ValidationError
from kubernetes.client.exceptions import ApiException

class TestErrorHandler:
    """Tests for ErrorHandler class."""
    
    def test_log_and_format_error(self):
        """Test error logging and formatting."""
        mock_logger = Mock(spec=logging.Logger)
        error = ValueError("Test error message")
        
        result = ErrorHandler.log_and_format_error(mock_logger, error, "Test operation")
        
        # Verify logger was called
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "Test operation failed" in call_args
        assert "Test error message" in call_args
        
        # Verify formatted response
        assert result["error"] == "Test operation failed"
        assert result["details"] == "Test error message"
        assert result["type"] == "ValueError"
    
    def test_handle_validation_error(self):
        """Test validation error handling."""
        mock_logger = Mock(spec=logging.Logger)
        error = ValidationError("Field validation failed")
        
        result, status_code = ErrorHandler.handle_validation_error(mock_logger, error)
        
        # Verify logger was called with warning level
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "Validation error" in call_args
        
        # Verify response format
        assert result["error"] == "Validation failed"
        assert result["details"] == "Field validation failed"
        assert result["type"] == "ValidationError"
        assert status_code == 400
    
    def test_handle_kubernetes_error_not_found(self):
        """Test Kubernetes not found error handling."""
        mock_logger = Mock(spec=logging.Logger)
        error = Exception("Resource not found")
        
        result, status_code = ErrorHandler.handle_kubernetes_error(mock_logger, error)
        
        # Verify logger was called
        mock_logger.error.assert_called_once()
        
        # Verify response format and status code mapping
        assert result["error"] == "Kubernetes operation failed"
        assert result["details"] == "Resource not found"
        assert result["type"] == "KubernetesError"
        assert status_code == 404
    
    def test_handle_kubernetes_error_already_exists(self):
        """Test Kubernetes already exists error handling."""
        mock_logger = Mock(spec=logging.Logger)
        error = Exception("Resource already exists")
        
        result, status_code = ErrorHandler.handle_kubernetes_error(mock_logger, error)
        
        assert status_code == 409
        assert result["details"] == "Resource already exists"
    
    def test_handle_kubernetes_error_forbidden(self):
        """Test Kubernetes forbidden error handling."""
        mock_logger = Mock(spec=logging.Logger)
        error = Exception("Access forbidden")
        
        result, status_code = ErrorHandler.handle_kubernetes_error(mock_logger, error)
        
        assert status_code == 403
        assert result["details"] == "Access forbidden"
    
    def test_handle_kubernetes_error_unauthorized(self):
        """Test Kubernetes unauthorized error handling."""
        mock_logger = Mock(spec=logging.Logger)
        error = Exception("Authentication required: unauthorized")
        
        result, status_code = ErrorHandler.handle_kubernetes_error(mock_logger, error)
        
        assert status_code == 401
        assert result["details"] == "Authentication required: unauthorized"
    
    def test_handle_kubernetes_error_generic(self):
        """Test generic Kubernetes error handling."""
        mock_logger = Mock(spec=logging.Logger)
        error = Exception("Generic Kubernetes error")
        
        result, status_code = ErrorHandler.handle_kubernetes_error(mock_logger, error)
        
        # Default to 500 for unknown errors
        assert status_code == 500
        assert result["details"] == "Generic Kubernetes error"
        assert result["type"] == "KubernetesError"

    def test_kubernetes_api_exception_handling(self):
        """Test handling of actual Kubernetes API exceptions."""
        mock_logger = Mock(spec=logging.Logger)
        
        # Create a mock ApiException with "not found" in the message
        api_error = ApiException(http_resp=Mock(status=404, reason="Not Found"))
        api_error._reason = "Resource not found"
        
        result, status_code = ErrorHandler.handle_kubernetes_error(mock_logger, api_error)
        
        # Should detect "not found" in the message and map to 404
        assert status_code == 404
        assert "Resource not found" in result["details"]