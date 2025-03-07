"""Configuration schema and validation system."""
from typing import Dict, Any, List, Optional, Union, ForwardRef
from dataclasses import dataclass
import os
from pathlib import Path
import json
import yaml
import jsonschema
from pydantic import BaseModel, Field, ConfigDict

# For Pydantic v2 compatibility
def list_factory():
    """Factory function for creating empty lists."""
    return []

from .logging_config import get_logger
from .config_validation import ConfigValidator, ValidationError

logger = get_logger(__name__)

# Core configuration schema
CORE_SCHEMA = {
    "type": "object",
    "properties": {
        "paths": {
            "type": "object",
            "properties": {
                "data_dir": {"type": "string"},
                "output_dir": {"type": "string"},
                "log_dir": {"type": "string"}
            },
            "required": ["data_dir", "output_dir"]
        },
        "entity_factory": {
            "type": "object",
            "properties": {
                "class": {"type": "string"},
                "config": {"type": "object"}
            },
            "required": ["class"]
        },
        "entity_store": {
            "type": "object",
            "properties": {
                "class": {"type": "string"},
                "config": {
                    "type": "object",
                    "properties": {
                        "storage_type": {"enum": ["sqlite", "filesystem"]},
                        "path": {"type": "string"}
                    },
                    "required": ["storage_type", "path"]
                }
            },
            "required": ["class", "config"]
        },
        "validation_service": {
            "type": "object",
            "properties": {
                "class": {"type": "string"},
                "config": {
                    "type": "object",
                    "properties": {
                        "rules_path": {"type": "string"},
                        "strict_mode": {"type": "boolean"}
                    }
                }
            },
            "required": ["class"]
        },
        "transformer_factory": {
            "type": "object",
            "properties": {
                "class": {"type": "string"},
                "config": {"type": "object"}
            }
        },
        "processing": {
            "type": "object",
            "properties": {
                "chunk_size": {"type": "integer", "minimum": 1},
                "worker_threads": {"type": "integer", "minimum": 1},
                "max_retries": {"type": "integer", "minimum": 0}
            }
        },
        "logging": {
            "type": "object",
            "properties": {
                "level": {"enum": ["DEBUG", "INFO", "WARNING", "ERROR"]},
                "format": {"type": "string"},
                "file": {"type": "string"}
            }
        }
    },
    "required": ["paths", "entity_factory", "entity_store", "validation_service"]
}

class ConfigLoader:
    """Loads and validates configuration from files."""
    
    def __init__(self, schema: Dict[str, Any]):
        """Initialize with schema."""
        self.validator = ConfigValidator(schema)
        
    def load_file(self, path: str) -> Optional[Dict[str, Any]]:
        """Load configuration from file."""
        try:
            with open(path, 'r') as f:
                if path.endswith('.json'):
                    config = json.load(f)
                elif path.endswith(('.yml', '.yaml')):
                    config = yaml.safe_load(f)
                else:
                    raise ValueError(
                        f"Unsupported config file format: {path}"
                    )
                    
            validation_errors = self.validator.validate_config(config)
            if not validation_errors:
                return config
                
            for error in validation_errors:
                logger.error(
                    f"Config validation error at {error.path}: "
                    f"{error.message}"
                )
                
            return None
            
        except Exception as e:
            logger.error(f"Error loading config file: {str(e)}")
            return None
            
    def merge_configs(self, base: Dict[str, Any],
                     override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configurations, override taking precedence."""
        merged = base.copy()
        
        def merge_dict(target: Dict[str, Any],
                      source: Dict[str, Any]) -> None:
            for key, value in source.items():
                if (key in target and isinstance(target[key], dict)
                        and isinstance(value, dict)):
                    merge_dict(target[key], value)
                else:
                    target[key] = value
                    
        merge_dict(merged, override)
        return merged

class TransformOperation(BaseModel):
    """Schema for transformation operations."""
    model_config = ConfigDict(extra='allow')
    
    type: str = Field(..., description="Type of transformation operation")
    # Common parameters
    input_formats: Optional[List[str]] = Field(None, description="Input date formats to try")
    output_format: Optional[str] = Field(None, description="Output format for dates/numbers")
    
    # String operations
    characters: Optional[str] = Field(None, description="Characters for strip operation")
    length: Optional[int] = Field(None, description="Length for padding/truncation")
    character: Optional[str] = Field(None, description="Character for padding")
    pattern: Optional[str] = Field(None, description="Pattern for extraction/matching")
    
    # Numeric operations
    precision: Optional[int] = Field(None, description="Decimal precision")
    places: Optional[int] = Field(None, description="Rounding places")
    currency: Optional[bool] = Field(None, description="Format as currency")
    grouping: Optional[bool] = Field(None, description="Use grouping separators")
    
    # Date operations
    dayfirst: Optional[bool] = Field(None, description="Parse dates with day first")
    yearfirst: Optional[bool] = Field(None, description="Parse dates with year first")
    fuzzy: Optional[bool] = Field(None, description="Allow fuzzy date parsing")
    fiscal_year_start_month: Optional[int] = Field(None, description="Fiscal year start month")
    components: Optional[List[str]] = Field(None, description="Date components to extract")
    
    # Mapping operations
    mapping: Optional[Dict[str, Any]] = Field(None, description="Value mapping dictionary")
    case_sensitive: Optional[bool] = Field(None, description="Case-sensitive mapping")
    default: Optional[Any] = Field(None, description="Default value for mapping")
    valid_values: Optional[List[str]] = Field(None, description="Valid enum values")
    replacements: Optional[Dict[str, str]] = Field(None, description="Character replacement map")

class TransformationConfig(BaseModel):
    """Schema for field transformation configuration."""
    model_config = ConfigDict(extra='forbid')
    
    timing: str = Field("before_validation", description="When to apply transformations")
    operations: List[TransformOperation] = Field(default_factory=list, description="List of transformation operations")

class DependencyConfig(BaseModel):
    """Schema for field dependency configuration."""
    model_config = ConfigDict(extra='forbid')
    
    type: str = Field(..., description="Type of dependency relationship")
    target_field: str = Field(..., description="Field that this field depends on")
    validation_rule: Optional[Dict[str, Any]] = Field(None, description="Validation rule for dependency")
    error_message: Optional[str] = Field(None, description="Custom error message")
    error_level: str = Field(default="error", description="How to handle validation failures")

class ValidationGroup(BaseModel):
    """Schema for validation group configuration."""
    model_config = ConfigDict(extra='forbid')
    
    name: str = Field(..., description="Name of validation group")
    description: Optional[str] = Field(None, description="Description of validation group purpose")
    enabled: bool = Field(default=True, description="Whether this group is active")
    rules: List[str] = Field(default_factory=list_factory, description="Validation rules in this group")
    dependencies: List[str] = Field(default_factory=list_factory, description="Other groups this depends on")
    error_level: str = Field(default="error", description="How to handle validation failures")

class ValidationConfig(BaseModel):
    """Schema for field validation configuration."""
    model_config = ConfigDict(extra='forbid')
    
    format: Optional[str] = Field(None, description="Format string for validation")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    min_value: Optional[Union[int, float]] = Field(None, description="Minimum allowed value")
    max_value: Optional[Union[int, float]] = Field(None, description="Maximum allowed value")
    precision: Optional[int] = Field(None, description="Required decimal precision")
    values: Optional[List[str]] = Field(None, description="Valid enum values")
    error_message: Optional[str] = Field(None, description="Custom error message")
    dependencies: Optional[List[DependencyConfig]] = Field(None, description="Field dependencies")
    groups: Optional[List[str]] = Field(None, description="Validation groups this field belongs to")
    conditional_rules: Optional[Dict[str, 'ValidationConfig']] = Field(None, description="Conditional validation rules")

ValidationConfig.model_rebuild()  # Update forward refs

class FieldProperties(BaseModel):
    """Schema for field property configuration."""
    model_config = ConfigDict(extra='forbid')
    
    type: str = Field(..., description="Field type")
    validation: Optional[ValidationConfig] = Field(None, description="Validation rules")
    transformation: Optional[TransformationConfig] = Field(None, description="Transformation rules")

# JSON Schema for entity configuration validation
ENTITY_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "key_fields": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "field_mappings": {
            "type": "object",
            "properties": {
                "direct": {"type": "object"},
                "multi_source": {"type": "object"},
                "object": {"type": "object"},
                "reference": {"type": "object"},
                "template": {"type": "object"}
            }
        },
        "entity_processing": {
            "type": "object",
            "required": ["enabled", "processing_order"],
            "properties": {
                "enabled": {"type": "boolean"},
                "processing_order": {"type": "integer", "minimum": 1},
                "store_type": {"type": "string"},
                "dependencies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["entity", "type"],
                        "properties": {
                            "entity": {"type": "string"},
                            "type": {"type": "string"},
                            "relationship": {"type": "string"}
                        }
                    }
                },
                "processing_options": {
                    "type": "object",
                    "properties": {
                        "validation_level": {"type": "string", "enum": ["strict", "warn", "none"]},
                        "error_handling": {"type": "string", "enum": ["abort", "skip", "log"]}
                    }
                },
                "concurrency": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "max_workers": {"type": "integer", "minimum": 1}
                    }
                }
            }
        },
        "relationships": {
            "type": "array",
            "items": {"type": "string"}
        },
        "validation_groups": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                    "type": "object",
                    "required": ["name", "rules"],
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "enabled": {"type": "boolean"},
                        "rules": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "error_level": {
                            "type": "string",
                            "enum": ["error", "warning", "info"]
                        }
                    }
                }
            }
        },
        "field_dependencies": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["type", "target_field"],
                        "properties": {
                            "type": {"type": "string"},
                            "target_field": {"type": "string"},
                            "validation_rule": {"type": "object"},
                            "error_message": {"type": "string"},
                            "error_level": {
                                "type": "string",
                                "enum": ["error", "warning", "info"]
                            }
                        }
                    }
                }
            }
        }
    },
    "required": ["key_fields", "field_mappings", "entity_processing"]
}

# Add Root Configuration Schema
ROOT_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "system": {"type": "object"},
        "validation_groups": {"type": "object"},
        "data_dictionary": {"type": "object"},
        "field_properties": {"type": "object"},
        "relationships": {
            "type": "array",
            "items": {"type": "object"}
        },
        "entities": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z_][a-zA-Z0-9_]*$": ENTITY_CONFIG_SCHEMA
            }
        },
        "documentation": {"type": "object"}
    },
    "required": ["entities"]
}

# Add export of schemas
__all__ = [
    'CORE_SCHEMA',
    'ROOT_CONFIG_SCHEMA',
    'ENTITY_CONFIG_SCHEMA',
    'ConfigLoader',
    'TransformOperation',
    'TransformationConfig',
    'DependencyConfig',
    'ValidationGroup',
    'ValidationConfig',
    'FieldProperties'
]
