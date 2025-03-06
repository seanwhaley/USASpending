"""Tests for configuration validation system."""
import pytest
from pathlib import Path
import yaml
import json
from src.usaspending.config_validation import validate_configuration, ValidationError
from src.usaspending.config_schemas import ROOT_CONFIG_SCHEMA, CORE_SCHEMA
from src.usaspending.exceptions import ConfigurationError

@pytest.fixture
def create_temp_config(tmp_path):
    """Create a temporary config file with given content."""
    def _create_config(content):
        config_path = tmp_path / "test_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(content, f)
        return str(config_path)
    return _create_config

def test_valid_minimal_config(create_temp_config):
    """Test validation of a minimal valid configuration."""
    config = {
        "entities": {
            "test_entity": {
                "key_fields": ["id"],
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"},
                        "name": {"field": "source_name"}
                    }
                },
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 1
                }
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert not errors, f"Unexpected validation errors: {errors}"

def test_missing_required_fields(create_temp_config):
    """Test validation when required fields are missing."""
    config = {
        "entities": {
            "test_entity": {
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                }
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert errors
    assert any("key_fields" in error.message for error in errors)

def test_invalid_processing_order(create_temp_config):
    """Test validation of invalid processing order."""
    config = {
        "entities": {
            "test_entity": {
                "key_fields": ["id"],
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                },
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 0  # Invalid - must be >= 1
                }
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert errors
    assert any("processing_order" in error.message for error in errors)

def test_invalid_file_format(create_temp_config):
    """Test validation of a file with invalid format."""
    config = {"invalid": "config"}
    config_path = create_temp_config(config)
    
    # Rename to unsupported extension
    invalid_path = Path(config_path).with_suffix('.txt')
    Path(config_path).rename(invalid_path)
    
    with pytest.raises(ConfigurationError, match="Unsupported config file format"):
        validate_configuration(str(invalid_path), ROOT_CONFIG_SCHEMA)

def test_schema_validation_error(create_temp_config):
    """Test handling of JSON schema validation errors."""
    config = {
        "entities": {
            "test_entity": {
                "key_fields": "not_a_list",  # Should be a list
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                }
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert errors
    assert any("'not_a_list' is not of type 'array'" in error.message for error in errors)

def test_path_validation(create_temp_config, tmp_path):
    """Test validation of path configurations."""
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    log_dir = tmp_path / "logs"
    
    # Create data directory
    data_dir.mkdir()
    
    config = {
        "entities": {
            "test_entity": {
                "key_fields": ["id"],
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                },
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 1
                }
            }
        },
        "paths": {
            "data_dir": str(data_dir),
            "output_dir": str(output_dir),
            "log_dir": str(log_dir)
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert not errors, f"Unexpected validation errors: {errors}"
    
    # Verify output and log directories were created
    assert output_dir.exists()
    assert log_dir.exists()

def test_nonexistent_data_dir(create_temp_config, tmp_path):
    """Test validation with nonexistent data directory."""
    data_dir = tmp_path / "nonexistent"
    
    config = {
        "entities": {
            "test_entity": {
                "key_fields": ["id"],
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                },
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 1
                }
            }
        },
        "paths": {
            "data_dir": str(data_dir),
            "output_dir": str(tmp_path / "output"),
            "log_dir": str(tmp_path / "logs")
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert errors
    assert any("Path does not exist" in error.message for error in errors)

def test_validation_group_config(create_temp_config):
    """Test validation of validation group configurations."""
    config = {
        "entities": {
            "test_entity": {
                "key_fields": ["id"],
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                },
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 1
                }
            }
        },
        "validation_groups": {
            "amount_validation": {
                "name": "Amount Validation",
                "rules": ["compare:less_than_equal:maximum_amount"],
                "enabled": True,
                "error_level": "error"
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert not errors, f"Unexpected validation errors: {errors}"

def test_invalid_validation_group(create_temp_config):
    """Test validation of invalid validation group configuration."""
    config = {
        "entities": {
            "test_entity": {
                "key_fields": ["id"],
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                },
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 1
                }
            }
        },
        "validation_groups": {
            "amount_validation": {
                "name": "Amount Validation",
                "enabled": True,  # Missing required "rules" field
                "error_level": "invalid_level"  # Invalid error level
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert errors
    assert any("'rules' is a required property" in error.message for error in errors)
    assert any("'invalid_level' is not one of ['error', 'warning', 'info']" in error.message for error in errors)

def test_field_dependencies_config(create_temp_config):
    """Test validation of field dependency configurations."""
    config = {
        "entities": {
            "test_entity": {
                "key_fields": ["id"],
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                },
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 1
                }
            }
        },
        "field_properties": {
            "award_amount": {
                "type": "decimal",
                "validation": {
                    "groups": ["amount_validation"],
                    "dependencies": [
                        {
                            "type": "comparison",
                            "target_field": "maximum_amount",
                            "validation_rule": {
                                "operator": "less_than_equal"
                            }
                        }
                    ]
                }
            },
            "maximum_amount": {
                "type": "decimal"
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert not errors, f"Unexpected validation errors: {errors}"

def test_invalid_field_dependencies(create_temp_config):
    """Test validation of invalid field dependency configuration."""
    config = {
        "entities": {
            "test_entity": {
                "key_fields": ["id"],
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                },
                "entity_processing": {
                    "enabled": True,
                    "processing_order": 1
                }
            }
        },
        "field_properties": {
            "award_amount": {
                "type": "decimal",
                "validation": {
                    "groups": ["amount_validation"],
                    "dependencies": [
                        {
                            "type": "invalid_type",  # Invalid dependency type
                            "target_field": "maximum_amount"
                        }
                    ]
                }
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert errors
    assert any("'invalid_type' is not one of ['comparison', 'required_field']" in error.message for error in errors)

def test_multiple_validation_errors(create_temp_config):
    """Test handling of multiple validation errors."""
    config = {
        "entities": {
            "test_entity": {
                "key_fields": "invalid",  # Should be a list
                "field_mappings": {
                    "direct": {
                        "id": {"field": "source_id"}
                    }
                },
                "entity_processing": {
                    "enabled": "invalid",  # Should be boolean
                    "processing_order": -1  # Invalid order
                }
            }
        },
        "validation_groups": {
            "test_group": {
                "name": 123,  # Should be string
                "rules": "invalid"  # Should be list
            }
        }
    }
    
    config_path = create_temp_config(config)
    errors = validate_configuration(config_path, ROOT_CONFIG_SCHEMA)
    assert len(errors) > 1, "Expected multiple validation errors"
    
    error_messages = [error.message for error in errors]
    assert any("'invalid' is not of type 'array'" in msg for msg in error_messages)
    assert any("'invalid' is not of type 'boolean'" in msg for msg in error_messages)
    assert any("-1 is less than the minimum of 1" in msg for msg in error_messages)
    assert any("123 is not of type 'string'" in msg for msg in error_messages)
    assert any("'invalid' is not of type 'array'" in msg for msg in error_messages)