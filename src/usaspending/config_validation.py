"""Configuration validation system."""
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
import yaml
import json
import jsonschema
from dataclasses import dataclass

from .logging_config import get_logger
from .exceptions import ConfigurationError

logger = get_logger(__name__)

@dataclass
class ValidationError:
    """Configuration validation error."""
    path: str
    message: str
    severity: str = "error"

def _load_config_file(file_path: str) -> Dict[str, Any]:
    """Load configuration from file."""
    path = Path(file_path)
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {file_path}")
    
    try:
        with open(path, 'r') as f:
            if path.suffix in ('.yml', '.yaml'):
                return yaml.safe_load(f)
            elif path.suffix == '.json':
                return json.load(f)
            else:
                raise ConfigurationError(f"Unsupported config file format: {path.suffix}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration file: {str(e)}")

def _validate_schema(config: Dict[str, Any], schema: Dict[str, Any]) -> List[ValidationError]:
    """Validate configuration against JSON schema."""
    errors: List[ValidationError] = []
    
    try:
        jsonschema.validate(config, schema)
    except jsonschema.exceptions.ValidationError as e:
        path = '.'.join(str(p) for p in e.path) if e.path else 'root'
        errors.append(ValidationError(path=path, message=str(e.message)))
    except Exception as e:
        errors.append(ValidationError(path='root', message=f"Schema validation error: {str(e)}"))
    
    return errors

def _validate_paths(config: Dict[str, Any]) -> List[ValidationError]:
    """Validate path configurations."""
    errors: List[ValidationError] = []
    paths = config.get('paths', {})
    
    for key, path in paths.items():
        path_obj = Path(path)
        
        # Handle directory paths
        if key.endswith('_dir'):
            try:
                if not path_obj.exists():
                    if key in ('output_dir', 'log_dir'):
                        # Create output and log directories if they don't exist
                        path_obj.mkdir(parents=True, exist_ok=True)
                    else:
                        errors.append(ValidationError(
                            path=f"paths.{key}",
                            message=f"Path does not exist: {path}"
                        ))
                        continue
                
                # Check permissions
                if not os.access(path, os.R_OK):
                    errors.append(ValidationError(
                        path=f"paths.{key}",
                        message=f"Path not readable: {path}"
                    ))
                
                if key in ('output_dir', 'log_dir'):
                    if not os.access(path, os.W_OK):
                        errors.append(ValidationError(
                            path=f"paths.{key}",
                            message=f"Path not writable: {path}"
                        ))
                
            except Exception as e:
                errors.append(ValidationError(
                    path=f"paths.{key}",
                    message=f"Error checking path: {str(e)}"
                ))
    
    return errors

def _validate_field_dependencies(config: Dict[str, Any]) -> List[ValidationError]:
    """Validate field dependency configurations."""
    errors: List[ValidationError] = []
    field_props = config.get('field_properties', {})
    
    for field_name, props in field_props.items():
        validation = props.get('validation', {})
        dependencies = validation.get('dependencies', [])
        
        for i, dep in enumerate(dependencies):
            dep_path = f"field_properties.{field_name}.validation.dependencies[{i}]"
            
            # Required properties
            if 'type' not in dep:
                errors.append(ValidationError(
                    path=dep_path,
                    message="Missing required property 'type'"
                ))
                continue
            
            if 'target_field' not in dep:
                errors.append(ValidationError(
                    path=dep_path,
                    message="Missing required property 'target_field'"
                ))
                continue
            
            # Valid dependency types
            valid_types = {'comparison', 'required_field'}
            if dep['type'] not in valid_types:
                errors.append(ValidationError(
                    path=f"{dep_path}.type",
                    message=f"'{dep['type']}' is not one of {list(valid_types)}"
                ))
            
            # Target field must exist
            target = dep['target_field']
            if target not in field_props:
                errors.append(ValidationError(
                    path=f"{dep_path}.target_field",
                    message=f"Referenced field '{target}' does not exist"
                ))
            
            # Validation rule for comparison type
            if dep['type'] == 'comparison' and 'validation_rule' not in dep:
                errors.append(ValidationError(
                    path=dep_path,
                    message="Comparison dependency requires 'validation_rule'"
                ))
    
    return errors

def validate_configuration(file_path: str, schema: Dict[str, Any]) -> List[ValidationError]:
    """Validate configuration file against schema and additional rules."""
    try:
        # Load configuration
        config = _load_config_file(file_path)
        
        # Collect all validation errors
        errors: List[ValidationError] = []
        
        # Schema validation
        errors.extend(_validate_schema(config, schema))
        if errors:
            return errors  # Stop if schema validation fails
        
        # Path validation
        errors.extend(_validate_paths(config))
        
        # Field dependency validation
        errors.extend(_validate_field_dependencies(config))
        
        return errors
        
    except ConfigurationError as e:
        # Re-raise configuration errors
        raise
    except Exception as e:
        # Wrap other errors
        raise ConfigurationError(f"Validation failed: {str(e)}")