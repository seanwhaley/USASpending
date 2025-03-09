"""Configuration schemas and defaults."""
from typing import Dict, Any
from dataclasses import dataclass
from pathlib import Path
import copy
import yaml
import jsonschema
from pydantic import BaseModel, Field, ConfigDict

from . import get_logger
from .exceptions import ConfigurationError

logger = get_logger(__name__)

# Core schema used by all configurations
CORE_SCHEMA = {
    "type": "object",
    "properties": {
        "paths": {
            "type": "object",
            "properties": {
                "data_dir": {"type": "string"},
                "output_dir": {"type": "string"},
                "log_dir": {"type": "string"},
                "temp_dir": {"type": "string"}
            },
            "required": ["data_dir", "output_dir"]
        },
        "entity_factory": {
            "type": "object",
            "properties": {
                "class": {"type": "string"},
                "config": {
                    "type": "object",
                    "properties": {
                        "type_adapters": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z][a-zA-Z0-9_]*$": {"type": "string"}
                            }
                        }
                    }
                }
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
                        "path": {"type": "string"},
                        "pool_size": {"type": "integer", "minimum": 1},
                        "timeout_seconds": {"type": "integer", "minimum": 1},
                        "journal_mode": {"enum": ["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"]},
                        "max_files_per_dir": {"type": "integer", "minimum": 1},
                        "compression": {"type": "boolean"}
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
                        "strict_mode": {"type": "boolean"},
                        "cache_size": {"type": "integer", "minimum": 1},
                        "parallel": {"type": "boolean"},
                        "max_errors": {"type": "integer", "minimum": 0},
                        "cycle_detection": {"type": "boolean"},
                        "max_depth": {"type": "integer", "minimum": 1}
                    }
                }
            },
            "required": ["class"]
        },
        "system": {
            "type": "object",
            "properties": {
                "processing": {
                    "type": "object",
                    "properties": {
                        "batch_size": {"type": "integer", "minimum": 1},
                        "max_retries": {"type": "integer", "minimum": 0},
                        "error_threshold": {"type": "number", "minimum": 0, "maximum": 1},
                        "validation_mode": {"enum": ["strict", "lenient"]},
                        "records_per_chunk": {"type": "integer", "minimum": 1},
                        "max_chunk_size_mb": {"type": "integer", "minimum": 1},
                        "entity_save_frequency": {"type": "integer", "minimum": 1},
                        "incremental_save": {"type": "boolean"},
                        "log_frequency": {"type": "integer", "minimum": 1},
                        "max_workers": {"type": "integer", "minimum": 1},
                        "queue_size": {"type": "integer", "minimum": 1},
                        "max_memory_mb": {"type": "integer", "minimum": 100}
                    }
                },
                "io": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string"},
                                "encoding": {"type": "string"},
                                "validate_input": {"type": "boolean"},
                                "skip_invalid_rows": {"type": "boolean"},
                                "csv": {
                                    "type": "object",
                                    "properties": {
                                        "delimiter": {"type": "string"},
                                        "quotechar": {"type": "string"},
                                        "escapechar": {"type": "string"},
                                        "has_header": {"type": "boolean"}
                                    }
                                }
                            },
                            "required": ["file"]
                        },
                        "output": {
                            "type": "object",
                            "properties": {
                                "directory": {"type": "string"},
                                "format": {"enum": ["json", "csv"]},
                                "atomic": {"type": "boolean"},
                                "compression": {"type": "boolean"},
                                "json": {
                                    "type": "object",
                                    "properties": {
                                        "indent": {"type": ["integer", "null"]},
                                        "ensure_ascii": {"type": "boolean"}
                                    }
                                }
                            },
                            "required": ["directory"]
                        }
                    },
                    "required": ["input", "output"]
                }
            }
        },
        "security": {
            "type": "object",
            "properties": {
                "file_operations": {
                    "type": "object",
                    "properties": {
                        "validate_permissions": {"type": "boolean"},
                        "prevent_traversal": {"type": "boolean"},
                        "secure_temp_files": {"type": "boolean"}
                    }
                },
                "data_validation": {
                    "type": "object",
                    "properties": {
                        "sanitize_input": {"type": "boolean"},
                        "validate_content": {"type": "boolean"},
                        "enforce_limits": {"type": "boolean"}
                    }
                },
                "configuration": {
                    "type": "object",
                    "properties": {
                        "encrypt_sensitive": {"type": "boolean"},
                        "verify_integrity": {"type": "boolean"},
                        "restrict_access": {"type": "boolean"}
                    }
                }
            }
        }
    },
    "required": ["paths", "system"]
}

class ConfigLoader:
    """Loads and validates configuration from files."""
    
    def __init__(self) -> None:
        self.config: Dict[str, Any] = {}
        
    def load_config(self, config_path: Path) -> None:
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to configuration file
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            with open(config_path) as f:
                self.config = yaml.safe_load(f)
            
            jsonschema.validate(instance=self.config, schema=CORE_SCHEMA)
            
        except (yaml.YAMLError, jsonschema.exceptions.ValidationError) as e:
            raise ConfigurationError(f"Invalid configuration: {str(e)}")
            
    def get_config(self) -> Dict[str, Any]:
        """Get the loaded configuration.
        
        Returns:
            The configuration dictionary
        """
        return copy.deepcopy(self.config)

# Pydantic models for config validation
class TransformOperation(BaseModel):
    """Schema for transformation operations."""
    operation: str
    params: Dict[str, Any] = Field(default_factory=dict)

class TransformationConfig(BaseModel):
    """Schema for field transformation configuration."""
    enabled: bool = True
    operations: list[TransformOperation]

class DependencyConfig(BaseModel):
    """Schema for field dependency configuration."""
    type: str
    target_field: str
    validation_rule: Dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    error_level: str = "error"

class ValidationGroup(BaseModel):
    """Schema for validation group configuration."""
    name: str
    description: str = ""
    enabled: bool = True
    rules: list[str]
    dependencies: list[str] = Field(default_factory=list)
    error_level: str = "error"

__all__ = [
    'CORE_SCHEMA',
    'ConfigLoader',
    'TransformOperation',
    'TransformationConfig', 
    'DependencyConfig',
    'ValidationGroup'
]