"""Configuration schemas and defaults."""
from typing import Dict, Any
import copy

from . import get_logger

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
        "transformer_factory": {
            "type": "object",
            "properties": {
                "class": {"type": "string"},
                "config": {"type": "object"}
            }
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
                },
                "caching": {
                    "type": "object",
                    "properties": {
                        "memory_size": {"type": "integer", "minimum": 1},
                        "ttl_seconds": {"type": "integer", "minimum": 1},
                        "file_fallback": {"type": "boolean"}
                    }
                }
            },
            "required": ["processing", "io"]
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
        "field_properties": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "validation": {
                            "type": "object",
                            "properties": {
                                "format": {"type": "string"},
                                "pattern": {"type": "string"},
                                "min_value": {"type": ["number", "string"]},
                                "max_value": {"type": ["number", "string"]},
                                "precision": {"type": "integer"},
                                "values": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "error_message": {"type": "string"},
                                "groups": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "dependencies": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["type", "target_field"],
                                        "properties": {
                                            "type": {"enum": ["comparison", "required_field"]},
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
                    }
                }
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
    "required": ["system"]
}

# Root schema includes any additional top-level configurations
ROOT_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        **CORE_SCHEMA["properties"],
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
        },
        "data_dictionary": {
            "type": "object",
            "properties": {
                "crosswalk": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string"},
                                "required_columns": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        },
                        "output": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string"},
                                "indent": {"type": "integer"},
                                "ensure_ascii": {"type": "boolean"}
                            }
                        },
                        "parsing": {
                            "type": "object"
                        },
                        "mapping": {
                            "type": "object"
                        }
                    }
                }
            }
        },
        "entities": {
            "type": "object"
        },
        "documentation": {
            "type": "object"
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object"
            }
        }
    },
    "required": ["system"]
}

# Default component implementations to inject when not defined in config
DEFAULT_ENTITY_FACTORY = {
    "class": "usaspending.entity_factory.EntityFactory",
    "config": {
        "type_adapters": {
            "string": "usaspending.schema_adapters.StringAdapter",
            "integer": "usaspending.schema_adapters.IntegerAdapter",
            "decimal": "usaspending.schema_adapters.DecimalAdapter",
            "money": "usaspending.schema_adapters.MoneyAdapter",
            "date": "usaspending.schema_adapters.DateAdapter",
            "boolean": "usaspending.boolean_adapters.BooleanAdapter",
            "enum": "usaspending.enum_adapters.EnumAdapter"
        }
    }
}

DEFAULT_ENTITY_STORE = {
    "class": "usaspending.entity_store.FileSystemEntityStore",
    "config": {
        "storage_type": "filesystem",
        "path": "output/entities",
        "max_files_per_dir": 1000,
        "compression": True
    }
}

DEFAULT_VALIDATION_SERVICE = {
    "class": "usaspending.validation_service.ValidationService",
    "config": {
        "strict_mode": False,
        "cache_size": 1000,
        "parallel": True,
        "max_errors": 100
    }
}