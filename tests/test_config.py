"""Tests for configuration management system."""
import pytest
from src.usaspending.config import ConfigManager
from src.usaspending.exceptions import ConfigurationError

@pytest.fixture
def test_config_data():
    """Sample configuration for testing."""
    return {
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
        },
        "validation_groups": {
            "amount_validation": {
                "name": "Amount Validation",
                "rules": ["compare:less_than_equal:maximum_amount"],
                "enabled": True,
                "error_level": "error"
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

def test_load_config(create_temp_config_file, test_config_data):
    """Test loading and validating the configuration."""
    config_path = create_temp_config_file(test_config_data)
    config_manager = ConfigManager(config_path)
    
    config = config_manager.get_config()
    assert 'entities' in config
    assert 'validation_groups' in config
    assert 'field_properties' in config
    
    # Test validation manager initialization
    assert config_manager.validation_manager is not None
    assert len(config_manager.get_validation_rules('amount_validation')) == 1
    assert len(config_manager.get_field_dependencies('award_amount')) == 1
    assert 'maximum_amount' in config_manager.get_validation_order()

def test_missing_config_file():
    """Test handling of missing configuration file."""
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        ConfigManager("nonexistent_config.yaml")

def test_missing_required_fields(create_temp_config_file):
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
    
    config_path = create_temp_config_file(config)
    with pytest.raises(ConfigurationError, match="Configuration validation failed"):
        ConfigManager(config_path)

def test_invalid_validation_group(create_temp_config_file, test_config_data):
    """Test validation with invalid validation group."""
    config = dict(test_config_data)
    config['validation_groups']['invalid_group'] = {
        'name': 'Invalid Group',
        'enabled': True  # Missing required 'rules' field
    }
    
    config_path = create_temp_config_file(config)
    with pytest.raises(ConfigurationError, match="Configuration validation failed"):
        ConfigManager(config_path)

def test_entity_config_access(create_temp_config_file, test_config_data):
    """Test access to entity configurations."""
    config_path = create_temp_config_file(test_config_data)
    config_manager = ConfigManager(config_path)
    
    # Test valid entity access
    entity_config = config_manager.get_entity_config('test_entity')
    assert entity_config['key_fields'] == ['id']
    
    # Test invalid entity access
    with pytest.raises(ConfigurationError, match="No configuration found for entity type"):
        config_manager.get_entity_config('nonexistent')

def test_validation_management(create_temp_config_file, test_config_data):
    """Test validation management functionality."""
    config_path = create_temp_config_file(test_config_data)
    config_manager = ConfigManager(config_path)
    
    # Test validation rules
    rules = config_manager.get_validation_rules('amount_validation')
    assert len(rules) == 1
    assert rules[0] == 'compare:less_than_equal:maximum_amount'
    
    # Test field dependencies
    deps = config_manager.get_field_dependencies('award_amount')
    assert len(deps) == 1
    assert deps[0] == 'maximum_amount'
    
    # Test validation order
    order = config_manager.get_validation_order()
    assert 'maximum_amount' in order
    assert 'award_amount' in order
    assert order.index('maximum_amount') < order.index('award_amount')

def test_system_config_access(create_temp_config_file, test_config_data):
    """Test access to system configuration."""
    config = dict(test_config_data)
    config['system'] = {
        'processing': {
            'records_per_chunk': 100,
            'max_workers': 4
        }
    }
    
    config_path = create_temp_config_file(config)
    config_manager = ConfigManager(config_path)
    
    system_config = config_manager.get_system_config()
    assert system_config['processing']['records_per_chunk'] == 100
    assert system_config['processing']['max_workers'] == 4