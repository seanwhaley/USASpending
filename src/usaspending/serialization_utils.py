"""Utility functions for complex data serialization."""
from typing import Dict, Any, List, Set, Type, TypeVar, Optional, Union
import json
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from enum import Enum
import dataclasses
import base64
import pickle
import uuid

from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

def format_decimal(value: Union[Decimal, float, str, None], 
                  precision: int = 2,
                  rounding: str = ROUND_HALF_UP) -> Optional[str]:
    """Format decimal value with specified precision.
    
    Args:
        value: Value to format
        precision: Number of decimal places (default: 2)
        rounding: Rounding method to use (default: ROUND_HALF_UP)
        
    Returns:
        Formatted decimal string or None if input is None
    """
    if value is None:
        return None
        
    try:
        if isinstance(value, str):
            # Convert string to Decimal
            value = Decimal(value)
        elif isinstance(value, float):
            # Convert float to Decimal to avoid precision issues
            value = Decimal(str(value))
        elif not isinstance(value, Decimal):
            raise ValueError(f"Unsupported type for decimal formatting: {type(value)}")
            
        # Round to specified precision
        return str(value.quantize(Decimal(f'0.{"0" * precision}'), rounding=rounding))
        
    except (ValueError, InvalidOperation, TypeError) as e:
        logger.error(f"Error formatting decimal value {value}: {str(e)}")
        return None

def serialize_complex_value(value: Any) -> Dict[str, Any]:
    """Serialize complex Python value to JSON-compatible dict."""
    if value is None:
        return {"type": "null", "value": None}
        
    type_name = type(value).__name__
    
    if isinstance(value, (str, int, float, bool)):
        return {"type": type_name, "value": value}
        
    elif isinstance(value, (datetime, date)):
        return {
            "type": type_name,
            "value": value.isoformat()
        }
        
    elif isinstance(value, Decimal):
        return {
            "type": "decimal",
            "value": str(value)
        }
        
    elif isinstance(value, Enum):
        return {
            "type": "enum",
            "enum_type": value.__class__.__name__,
            "value": value.value
        }
        
    elif isinstance(value, (list, tuple, set)):
        return {
            "type": type_name,
            "value": [serialize_complex_value(item) for item in value]
        }
        
    elif isinstance(value, dict):
        return {
            "type": "dict",
            "value": {
                str(k): serialize_complex_value(v)
                for k, v in value.items()
            }
        }
        
    elif dataclasses.is_dataclass(value):
        return {
            "type": "dataclass",
            "class": value.__class__.__name__,
            "value": {
                f.name: serialize_complex_value(getattr(value, f.name))
                for f in dataclasses.fields(value)
            }
        }
        
    elif isinstance(value, uuid.UUID):
        return {
            "type": "uuid",
            "value": str(value)
        }
        
    # For unknown types, use pickle with base64 encoding
    try:
        return {
            "type": "pickled",
            "python_type": type_name,
            "value": base64.b64encode(pickle.dumps(value)).decode('utf-8')
        }
    except Exception as e:
        logger.warning(f"Failed to pickle value of type {type_name}: {str(e)}")
        return {
            "type": "unknown",
            "python_type": type_name,
            "value": str(value)
        }

def deserialize_complex_value(data: Dict[str, Any],
                            type_registry: Optional[Dict[str, Type]] = None) -> Any:
    """Deserialize value from serialized format."""
    if not isinstance(data, dict) or "type" not in data:
        return data
        
    type_name = data["type"]
    value = data["value"]
    
    if type_name == "null":
        return None
        
    elif type_name in ("str", "int", "float", "bool"):
        return value
        
    elif type_name in ("datetime", "date"):
        cls = datetime if type_name == "datetime" else date
        return cls.fromisoformat(value)
        
    elif type_name == "decimal":
        return Decimal(value)
        
    elif type_name == "enum":
        if type_registry and data["enum_type"] in type_registry:
            return type_registry[data["enum_type"]](value)
        return value
        
    elif type_name in ("list", "tuple", "set"):
        items = [
            deserialize_complex_value(item, type_registry)
            for item in value
        ]
        if type_name == "tuple":
            return tuple(items)
        elif type_name == "set":
            return set(items)
        return items
        
    elif type_name == "dict":
        return {
            str(k): deserialize_complex_value(v, type_registry)
            for k, v in value.items()
        }
        
    elif type_name == "dataclass":
        if type_registry and data["class"] in type_registry:
            cls = type_registry[data["class"]]
            field_values = {
                k: deserialize_complex_value(v, type_registry)
                for k, v in value.items()
            }
            return cls(**field_values)
        return value
        
    elif type_name == "uuid":
        return uuid.UUID(value)
        
    elif type_name == "pickled":
        try:
            return pickle.loads(base64.b64decode(value.encode('utf-8')))
        except Exception as e:
            logger.warning(
                f"Failed to unpickle value of type {data.get('python_type')}: {str(e)}"
            )
            return value
            
    return value

def create_type_registry(*types: Type) -> Dict[str, Type]:
    """Create type registry from list of types."""
    return {t.__name__: t for t in types}

def merge_type_registries(*registries: Dict[str, Type]) -> Dict[str, Type]:
    """Merge multiple type registries."""
    result = {}
    for registry in registries:
        result.update(registry)
    return result

class ComplexJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles complex Python types."""
    
    def default(self, obj: Any) -> Any:
        """Convert Python object to JSON-serializable format."""
        return serialize_complex_value(obj)

def serialize_to_json(obj: Any, **kwargs: Any) -> str:
    """Serialize object to JSON string."""
    return json.dumps(obj, cls=ComplexJSONEncoder, **kwargs)

def deserialize_from_json(json_str: str,
                         type_registry: Optional[Dict[str, Type]] = None,
                         **kwargs: Any) -> Any:
    """Deserialize object from JSON string."""
    data = json.loads(json_str, **kwargs)
    return deserialize_complex_value(data, type_registry)

def flatten_dict(data: Dict[str, Any], separator: str = '.',
                prefix: str = '') -> Dict[str, Any]:
    """Flatten nested dictionary with dot notation."""
    result = {}
    
    for key, value in data.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key
        
        if isinstance(value, dict):
            result.update(flatten_dict(value, separator, new_key))
        else:
            result[new_key] = value
            
    return result

def unflatten_dict(data: Dict[str, Any],
                   separator: str = '.') -> Dict[str, Any]:
    """Reconstruct nested dictionary from flattened format."""
    result = {}
    
    for key, value in data.items():
        parts = key.split(separator)
        current = result
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            
        current[parts[-1]] = value
        
    return result