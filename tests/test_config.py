import pytest
from usaspending.config import ConfigManager, ConfigurationError

def test_load_config():
    """Test loading and validating the configuration."""
    config_path = "d:/VS Code Projects/USASpending/conversion_config.yaml"
    config_manager = ConfigManager(config_path)
    
    config = config_manager.get_config()
    
    assert 'entities' in config
    for entity_name, entity_config in config['entities'].items():
        assert 'key_fields' in entity_config
        assert isinstance(entity_config['key_fields'], list)

def test_missing_key_fields():
    """Test configuration with missing key_fields."""
    invalid_config = {
        "entities": {
            "test_entity": {
                "enabled": True,
                "field_mappings": {
                    "direct": {
                        "id_field": {"field": "source_id"},
                        "name": {"field": "source_name"}
                    }
                }
            }
        }
    }
    
    with pytest.raises(ConfigurationError, match="Invalid configuration: 'key_fields' is a required property for entity 'test_entity'"):
        ConfigManager(invalid_config)

def test_invalid_key_fields_type():
    """Test configuration with invalid key_fields type."""
    invalid_config = {
        "entities": {
            "test_entity": {
                "enabled": True,
                "key_fields": "id_field",  # Should be a list
                "field_mappings": {
                    "direct": {
                        "id_field": {"field": "source_id"},
                        "name": {"field": "source_name"}
                    }
                }
            }
        }
    }
    
    with pytest.raises(ConfigurationError, match="Invalid configuration: 'key_fields' must be a list for entity 'test_entity'"):
        ConfigManager(invalid_config)