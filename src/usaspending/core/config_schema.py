"""Core configuration schema definitions."""
from typing import Dict, Any

# Base schemas
COMPONENT_SCHEMA = {
    "type": "object",
    "required": ["class_path"],
    "properties": {
        "class_path": {"type": "string"},
        "settings": {
            "type": "object",
            "additionalProperties": True
        }
    }
}

FIELD_SCHEMA = {
    "type": "object",
    "required": ["name", "data_type"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "data_type": {
            "type": "string",
            "enum": [
                "string", "integer", "float", "decimal",
                "date", "datetime", "boolean", "enum",
                "list", "dict", "any"
            ]
        },
        "source_field": {"type": "string"},
        "is_required": {"type": "boolean"},
        "is_nullable": {"type": "boolean"},
        "default_value": {"type": "any"},
        "validation_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rule_type", "parameters", "error_message"],
                "properties": {
                    "rule_type": {"type": "string"},
                    "parameters": {"type": "object"},
                    "error_message": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["error", "warning", "info"]
                    }
                }
            }
        },
        "transformation_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["transform_type", "parameters"],
                "properties": {
                    "transform_type": {"type": "string"},
                    "parameters": {"type": "object"},
                    "description": {"type": "string"}
                }
            }
        },
        "dependencies": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

ENTITY_SCHEMA = {
    "type": "object",
    "required": ["entity_type", "key_fields"],
    "properties": {
        "entity_type": {"type": "string"},
        "description": {"type": "string"},
        "key_fields": {
            "type": "array",
            "items": {"type": "string"}
        },
        "field_definitions": {
            "type": "object",
            "additionalProperties": FIELD_SCHEMA
        },
        "relationships": {
            "type": "array",
            "items": {"type": "string"}
        },
        "processing_rules": {
            "type": "array",
            "items": {"type": "string"}
        },
        "storage_settings": {
            "type": "object",
            "additionalProperties": True
        }
    }
}

RELATIONSHIP_SCHEMA = {
    "type": "object",
    "required": [
        "id",
        "source_entity",
        "target_entity",
        "relationship_type",
        "source_fields",
        "target_fields"
    ],
    "properties": {
        "id": {"type": "string"},
        "source_entity": {"type": "string"},
        "target_entity": {"type": "string"},
        "relationship_type": {
            "type": "string",
            "enum": ["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
        },
        "source_fields": {
            "type": "array",
            "items": {"type": "string"}
        },
        "target_fields": {
            "type": "array",
            "items": {"type": "string"}
        },
        "is_required": {"type": "boolean"},
        "is_unique": {"type": "boolean"},
        "validation_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rule_type", "parameters", "error_message"],
                "properties": {
                    "rule_type": {"type": "string"},
                    "parameters": {"type": "object"},
                    "error_message": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["error", "warning", "info"]
                    }
                }
            }
        },
        "metadata": {
            "type": "object",
            "additionalProperties": True
        }
    }
}

# Core configuration schema
CORE_SCHEMA = {
    "type": "object",
    "required": ["system", "entities"],
    "properties": {
        "system": {
            "type": "object",
            "required": ["data_dir", "output_dir"],
            "properties": {
                "data_dir": {"type": "string"},
                "output_dir": {"type": "string"},
                "cache_dir": {"type": "string"},
                "temp_dir": {"type": "string"},
                "log_level": {
                    "type": "string",
                    "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]
                },
                "max_workers": {"type": "integer", "minimum": 1},
                "batch_size": {"type": "integer", "minimum": 1}
            }
        },
        "entities": {
            "type": "object",
            "additionalProperties": ENTITY_SCHEMA
        },
        "relationships": {
            "type": "array",
            "items": RELATIONSHIP_SCHEMA
        },
        "components": {
            "type": "object",
            "properties": {
                "entity_factory": COMPONENT_SCHEMA,
                "entity_store": COMPONENT_SCHEMA,
                "validation_service": COMPONENT_SCHEMA,
                "cache_provider": COMPONENT_SCHEMA,
                "event_emitter": COMPONENT_SCHEMA,
                "logger": COMPONENT_SCHEMA
            }
        }
    }
}

# Default component configurations
DEFAULT_ENTITY_FACTORY = {
    "class_path": "usaspending.core.entities.EntityFactory",
    "settings": {}
}

DEFAULT_ENTITY_STORE = {
    "class_path": "usaspending.core.storage.FileSystemEntityStore",
    "settings": {
        "base_path": "output/entities",
        "file_format": "json"
    }
}

DEFAULT_VALIDATION_SERVICE = {
    "class_path": "usaspending.core.validation.ValidationService",
    "settings": {}
}

__all__ = [
    'CORE_SCHEMA',
    'COMPONENT_SCHEMA',
    'FIELD_SCHEMA',
    'ENTITY_SCHEMA',
    'RELATIONSHIP_SCHEMA',
    'DEFAULT_ENTITY_FACTORY',
    'DEFAULT_ENTITY_STORE',
    'DEFAULT_VALIDATION_SERVICE'
]