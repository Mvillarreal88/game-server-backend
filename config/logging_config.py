"""
Centralized logging configuration.
"""
import logging
import logging.config
import os
from typing import Dict, Any

def get_logging_config(environment: str = 'development') -> Dict[str, Any]:
    """
    Get logging configuration based on environment.
    
    Args:
        environment: Environment name (development, production)
        
    Returns:
        Logging configuration dictionary
    """
    log_level = 'DEBUG' if environment == 'development' else 'INFO'
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'simple': {
                'format': '%(levelname)s - %(name)s - %(message)s'
            },
            'json': {
                'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "file": "%(filename)s", "line": %(lineno)d, "message": "%(message)s"}',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'detailed' if environment == 'development' else 'json',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': log_level,
                'formatter': 'detailed',
                'filename': 'logs/app.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf8'
            }
        },
        'loggers': {
            # Application loggers
            'app': {
                'level': log_level,
                'handlers': ['console', 'file'] if environment == 'development' else ['console'],
                'propagate': False
            },
            'routes': {
                'level': log_level,
                'handlers': ['console', 'file'] if environment == 'development' else ['console'],
                'propagate': False
            },
            'services': {
                'level': log_level,
                'handlers': ['console', 'file'] if environment == 'development' else ['console'],
                'propagate': False
            },
            'utils': {
                'level': log_level,
                'handlers': ['console', 'file'] if environment == 'development' else ['console'],
                'propagate': False
            },
            # Third-party loggers (less verbose)
            'kubernetes': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            },
            'azure': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            },
            'urllib3': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            }
        },
        'root': {
            'level': log_level,
            'handlers': ['console']
        }
    }
    
    return config

def setup_logging(environment: str = 'development') -> None:
    """
    Setup logging configuration.
    
    Args:
        environment: Environment name
    """
    # Create logs directory if it doesn't exist
    if environment == 'development':
        os.makedirs('logs', exist_ok=True)
    
    # Configure logging
    config = get_logging_config(environment)
    logging.config.dictConfig(config)
    
    # Set up root logger
    logger = logging.getLogger('app')
    logger.info(f"Logging configured for {environment} environment")

class ErrorHandler:
    """Centralized error handling utilities."""
    
    @staticmethod
    def log_and_format_error(logger: logging.Logger, error: Exception, 
                           context: str = "Operation") -> Dict[str, Any]:
        """
        Log an error and return a formatted error response.
        
        Args:
            logger: Logger instance
            error: Exception that occurred
            context: Context description for the error
            
        Returns:
            Formatted error response dictionary
        """
        error_msg = str(error)
        logger.error(f"{context} failed: {error_msg}", exc_info=True)
        
        return {
            "error": f"{context} failed",
            "details": error_msg,
            "type": error.__class__.__name__
        }
    
    @staticmethod
    def handle_validation_error(logger: logging.Logger, error: Exception) -> tuple[Dict[str, Any], int]:
        """
        Handle validation errors specifically.
        
        Args:
            logger: Logger instance  
            error: Validation error
            
        Returns:
            Tuple of (error_response, status_code)
        """
        logger.warning(f"Validation error: {str(error)}")
        
        return {
            "error": "Validation failed",
            "details": str(error),
            "type": "ValidationError"
        }, 400
    
    @staticmethod
    def handle_kubernetes_error(logger: logging.Logger, error: Exception) -> tuple[Dict[str, Any], int]:
        """
        Handle Kubernetes-specific errors.
        
        Args:
            logger: Logger instance
            error: Kubernetes error
            
        Returns:
            Tuple of (error_response, status_code)
        """
        logger.error(f"Kubernetes operation failed: {str(error)}", exc_info=True)
        
        # Map common Kubernetes errors to HTTP status codes
        status_code = 500
        if "not found" in str(error).lower():
            status_code = 404
        elif "already exists" in str(error).lower():
            status_code = 409
        elif "forbidden" in str(error).lower():
            status_code = 403
        elif "unauthorized" in str(error).lower():
            status_code = 401
        
        return {
            "error": "Kubernetes operation failed",
            "details": str(error),
            "type": "KubernetesError"
        }, status_code