"""
Input validation schemas and utilities using marshmallow.
"""
from marshmallow import Schema, fields, validate, ValidationError, post_load
import re
from typing import Dict, Any

class ServerIdValidator:
    """Custom validator for server IDs."""
    
    def __call__(self, value: str) -> str:
        if not re.match(r'^[a-z0-9\-]+$', value):
            raise ValidationError(
                'Server ID must contain only lowercase letters, numbers, and hyphens'
            )
        if len(value) > 50:
            raise ValidationError('Server ID must be 50 characters or less')
        if value.startswith('-') or value.endswith('-'):
            raise ValidationError('Server ID cannot start or end with a hyphen')
        return value

class NamespaceValidator:
    """Custom validator for Kubernetes namespaces."""
    
    def __call__(self, value: str) -> str:
        if not re.match(r'^[a-z0-9\-]+$', value):
            raise ValidationError(
                'Namespace must contain only lowercase letters, numbers, and hyphens'
            )
        if len(value) > 63:
            raise ValidationError('Namespace must be 63 characters or less')
        return value

class StartServerSchema(Schema):
    """Schema for start server request validation."""
    
    package = fields.Str(
        required=True,
        validate=validate.OneOf(['standard']),  # Add more packages as needed
        error_messages={'required': 'Package is required'}
    )
    server_id = fields.Str(
        required=True,
        validate=ServerIdValidator(),
        error_messages={'required': 'Server ID is required'}
    )
    namespace = fields.Str(
        load_default='default',
        validate=NamespaceValidator()
    )
    
    @post_load
    def make_request(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Post-process validated data."""
        return data

class StopServerSchema(Schema):
    """Schema for stop server request validation."""
    
    server_id = fields.Str(
        required=True,
        validate=ServerIdValidator(),
        error_messages={'required': 'Server ID is required'}
    )
    namespace = fields.Str(
        load_default='default',
        validate=NamespaceValidator()
    )

class PauseServerSchema(Schema):
    """Schema for pause server request validation."""
    
    server_id = fields.Str(
        required=True,
        validate=ServerIdValidator(),
        error_messages={'required': 'Server ID is required'}
    )
    namespace = fields.Str(
        load_default='default',
        validate=NamespaceValidator()
    )

class ResumeServerSchema(Schema):
    """Schema for resume server request validation."""
    
    server_id = fields.Str(
        required=True,
        validate=ServerIdValidator(),
        error_messages={'required': 'Server ID is required'}
    )
    namespace = fields.Str(
        load_default='default',
        validate=NamespaceValidator()
    )

def validate_json_request(schema_class: Schema, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate request data against a schema.
    
    Args:
        schema_class: Marshmallow schema class
        request_data: Request data to validate
        
    Returns:
        Validated and processed data
        
    Raises:
        ValidationError: If validation fails
    """
    schema = schema_class()
    try:
        return schema.load(request_data)
    except ValidationError as e:
        raise ValidationError(f"Validation failed: {e.messages}")

def format_validation_errors(errors: Dict[str, Any]) -> str:
    """
    Format validation errors into a readable string.
    
    Args:
        errors: Validation errors from marshmallow
        
    Returns:
        Formatted error string
    """
    error_messages = []
    for field, messages in errors.items():
        if isinstance(messages, list):
            for message in messages:
                error_messages.append(f"{field}: {message}")
        else:
            error_messages.append(f"{field}: {messages}")
    
    return "; ".join(error_messages)