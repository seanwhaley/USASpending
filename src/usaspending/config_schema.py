"""Schema definitions for configuration validation."""
from typing import Dict, Any

ENTITY_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "processing": {
            "type": "object",
            "properties": {
                "store_type": {"type": "string"},
                "enabled": {"type": "boolean"},
                "options": {"type": "object", "additionalProperties": True}
            },
            "required": ["enabled"],
            "additionalProperties": False
        },
        "entity_processing": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "processing_order": {"type": "integer", "minimum": 0},
                "dependencies": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["enabled"],
            "additionalProperties": False
        }
    },
    "required": ["processing", "entity_processing"],
    "additionalProperties": False
}
