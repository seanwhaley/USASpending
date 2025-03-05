"""JSON schemas for configuration validation."""
from typing import Dict, Any

# Core schema used by all configurations
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
        "entities": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z][a-zA-Z0-9_]*$": {
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
                                "direct": {
                                    "type": "object",
                                    "patternProperties": {
                                        ".*": {
                                            "type": "object",
                                            "properties": {
                                                "field": {"type": "string"},
                                                "transformation": {"type": "object"}
                                            },
                                            "required": ["field"]
                                        }
                                    }
                                },
                                "object": {"type": "object"},
                                "reference": {"type": "object"}
                            }
                        },
                        "entity_processing": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean"},
                                "processing_order": {
                                    "type": "integer",
                                    "minimum": 1
                                }
                            },
                            "required": ["enabled", "processing_order"]
                        }
                    },
                    "required": ["key_fields", "field_mappings"]
                }
            }
        },
        "validation_groups": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z][a-zA-Z0-9_]*$": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "enabled": {"type": "boolean"},
                        "rules": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "error_level": {
                            "type": "string",
                            "enum": ["error", "warning", "info"]
                        }
                    },
                    "required": ["name", "rules"]
                }
            }
        },
        "field_properties": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["string", "integer", "decimal", "date", "boolean"]
                        },
                        "validation": {
                            "type": "object",
                            "properties": {
                                "groups": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "dependencies": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "type": {
                                                "type": "string",
                                                "enum": ["comparison", "required_field"]
                                            },
                                            "target_field": {"type": "string"},
                                            "validation_rule": {"type": "object"}
                                        },
                                        "required": ["type", "target_field"]
                                    }
                                }
                            }
                        }
                    },
                    "required": ["type"]
                }
            }
        },
        "system": {
            "type": "object",
            "properties": {
                "processing": {
                    "type": "object",
                    "properties": {
                        "records_per_chunk": {"type": "integer", "minimum": 1},
                        "max_chunk_size_mb": {"type": "integer", "minimum": 1},
                        "entity_save_frequency": {"type": "integer", "minimum": 1},
                        "incremental_save": {"type": "boolean"},
                        "log_frequency": {"type": "integer", "minimum": 1},
                        "max_workers": {"type": "integer", "minimum": 1},
                        "queue_size": {"type": "integer", "minimum": 1}
                    }
                },
                "io": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string"},
                                "batch_size": {"type": "integer", "minimum": 1},
                                "validate_input": {"type": "boolean"},
                                "skip_invalid_rows": {"type": "boolean"}
                            }
                        },
                        "output": {
                            "type": "object",
                            "properties": {
                                "directory": {"type": "string"},
                                "entities_subfolder": {"type": "string"},
                                "transaction_base_name": {"type": "string"},
                                "ensure_ascii": {"type": "boolean"},
                                "indent": {"type": ["integer", "null"]}
                            }
                        }
                    }
                }
            }
        }
    },
    "required": ["entities"]
}

# Root schema that other schemas can extend
ROOT_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "USASpending Configuration Schema",
    "description": "Schema for USASpending data processing configuration",
    **CORE_SCHEMA
}