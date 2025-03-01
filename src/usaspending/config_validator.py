"""Configuration validation utilities for USASpending."""
from typing import Dict, Any, List, Union, get_type_hints, get_origin, get_args, Optional, TypeVar, Type
import inspect

from .types import ConfigType, ValidationTypeConfig, GlobalConfig, EntityConfig
from .types import ValidationErrorConfig, NumericValidationConfig, DateValidationConfig

T = TypeVar('T')

class ConfigValidationError(Exception):
    """Exception raised for configuration validation errors."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        message = "\n".join([f"- {error}" for error in errors])
        super().__init__(f"Configuration validation failed:\n{message}")


def validate_config_structure(config: Dict[str, Any]) -> None:
    """Validate the entire configuration structure against ConfigType."""
    errors = _validate_against_type(config, ConfigType, path="")
    if errors:
        raise ConfigValidationError(errors)


def _validate_against_type(value: Any, expected_type: Type[T], path: str = "") -> List[str]:
    """Recursively validate a value against an expected type."""
    errors = []
    
    # Handle None for Optional types
    if value is None:
        if get_origin(expected_type) is Union and type(None) in get_args(expected_type):
            return []  # Valid None for Optional
        else:
            return [f"'{path}' is None but expected {expected_type.__name__}"]
    
    # Handle Union types
    if get_origin(expected_type) is Union:
        # Try each type in the union
        for arg_type in get_args(expected_type):
            if arg_type is type(None):  # Skip None type
                continue
            sub_errors = _validate_against_type(value, arg_type, path)
            if not sub_errors:
                return []  # Valid if it matches any union type
        return [f"'{path}' with value '{value}' doesn't match any of {get_args(expected_type)}"]
    
    # Handle Dict types
    if get_origin(expected_type) is dict:
        if not isinstance(value, dict):
            return [f"'{path}' must be a dictionary, got {type(value).__name__}"]
        
        key_type, val_type = get_args(expected_type)
        
        # Check all keys and values
        for k, v in value.items():
            # Validate key type (simplified for common types)
            if key_type is str and not isinstance(k, str):
                errors.append(f"'{path}.{k}' key must be a string, got {type(k).__name__}")
                
            # Validate value type recursively
            sub_path = f"{path}.{k}" if path else k
            sub_errors = _validate_against_type(v, val_type, sub_path)
            errors.extend(sub_errors)
            
        return errors
    
    # Handle List types
    if get_origin(expected_type) is list:
        if not isinstance(value, list):
            return [f"'{path}' must be a list, got {type(value).__name__}"]
        
        item_type = get_args(expected_type)[0]
        for i, item in enumerate(value):
            sub_path = f"{path}[{i}]"
            sub_errors = _validate_against_type(item, item_type, sub_path)
            errors.extend(sub_errors)
            
        return errors
    
    # Handle TypedDict
    if hasattr(expected_type, "__annotations__"):
        if not isinstance(value, dict):
            return [f"'{path}' must be a dictionary, got {type(value).__name__}"]
        
        annotations = get_type_hints(expected_type)
        
        # Check for required fields from TypedDict
        for field, field_type in annotations.items():
            field_path = f"{path}.{field}" if path else field
            
            # Check if field is required
            is_optional = expected_type.__total__ is False or \
                          (get_origin(field_type) is Union and type(None) in get_args(field_type))
            
            if field not in value:
                if is_optional:
                    continue  # Skip optional fields if not present
                else:
                    errors.append(f"Missing required field '{field_path}'")
                    continue
            
            # Recursively validate field
            sub_errors = _validate_against_type(value[field], field_type, field_path)
            errors.extend(sub_errors)
        
        # Check for unknown fields (optional warning)
        for field in value:
            if field not in annotations:
                errors.append(f"Unknown field '{path}.{field}' not defined in {expected_type.__name__}")
        
        return errors
    
    # Basic type validation for primitive types
    if expected_type in (str, int, float, bool) and not isinstance(value, expected_type):
        # Special case: allow int for float
        if expected_type is float and isinstance(value, int):
            return []
        return [f"'{path}' must be {expected_type.__name__}, got {type(value).__name__}"]
    
    # Assume it's valid if we can't determine the type
    return []


def get_schema_description(type_class: Type[T]) -> Dict[str, Any]:
    """Generate a human-readable schema description from a TypedDict."""
    schema = {}
    
    # Handle primitive types
    if type_class in (str, int, float, bool):
        return {"type": type_class.__name__}
    
    # Handle Union types
    if get_origin(type_class) is Union:
        types = [t.__name__ if hasattr(t, "__name__") else str(t) for t in get_args(type_class)]
        return {"oneOf": types}
    
    # Handle Dict types
    if get_origin(type_class) is dict:
        key_type, val_type = get_args(type_class)
        return {
            "type": "object",
            "keyType": key_type.__name__ if hasattr(key_type, "__name__") else str(key_type),
            "valueType": get_schema_description(val_type)
        }
    
    # Handle List types
    if get_origin(type_class) is list:
        item_type = get_args(type_class)[0]
        return {
            "type": "array",
            "items": get_schema_description(item_type)
        }
    
    # Handle TypedDict
    if hasattr(type_class, "__annotations__"):
        properties = {}
        annotations = get_type_hints(type_class)
        
        for field, field_type in annotations.items():
            properties[field] = get_schema_description(field_type)
            
            # Mark as required or optional
            is_optional = type_class.__total__ is False or \
                         (get_origin(field_type) is Union and type(None) in get_args(field_type))
            properties[field]["required"] = not is_optional
            
        schema["type"] = "object"
        schema["properties"] = properties
        schema["description"] = type_class.__doc__ if type_class.__doc__ else None
        
        return schema
    
    # Default case
    return {"type": str(type_class)}
