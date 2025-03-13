import pytest
import os
from unittest.mock import Mock, MagicMock
from typing import Dict, Any
from src.usaspending.config import ConfigurationProvider
from src.usaspending.core.config import ComponentConfig
from src.usaspending.core.interfaces import IConfigurable
from src.usaspending.core.exceptions import ConfigurationError

class MockConfigurable(IConfigurable):
    def configure(self, config: ComponentConfig) -> None:
        pass

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    return {
        'paths': {
            'data': 'data',
            'output': 'output'
        },
        'components': {
            'test_component': {
                'class_path': 'test.MockComponent',
                'settings': {
                    'option1': 'value1'
                }
            }
        },
        'entities': {
            'test_entity': {
                'key_fields': ['id'],
                'field_mappings': {
                    'direct': {
                        'target': 'source'
                    }
                }
            }
        }
    }

@pytest.fixture
def config_provider(tmp_path):
    provider = ConfigurationProvider()
    # Create a temporary config file
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, 'w') as f:
        f.write("""
paths:
  data: data
  output: output
components:
  test_component:
    class_path: test.MockComponent
    settings:
      option1: value1
entities:
  test_entity:
    key_fields: [id]
    field_mappings:
      direct:
        target: source
""")
    provider.load_config(str(config_path))
    return provider

def test_initialization():
    provider = ConfigurationProvider()
    assert not provider._initialized
    assert len(provider._config) == 0
    assert len(provider._validation_errors) == 0

def test_load_config(config_provider):
    assert config_provider._initialized
    assert 'paths' in config_provider._config
    assert 'components' in config_provider._config
    assert 'entities' in config_provider._config

def test_get_config_section(config_provider):
    # Test dot notation access
    result = config_provider.get_config_section('components.test_component.settings')
    assert result == {'option1': 'value1'}
    
    # Test missing section
    assert config_provider.get_config_section('nonexistent', 'default') == 'default'

def test_validate_config(config_provider):
    assert config_provider.validate_config()
    assert len(config_provider.get_validation_errors()) == 0

def test_validate_missing_required_sections(config_provider):
    config_provider._config = {}  # Clear config
    assert not config_provider.validate_config()
    errors = config_provider.get_validation_errors()
    assert any('Missing required section' in err for err in errors)

def test_validate_entity_config(config_provider):
    # Test invalid entity config
    config_provider._config['entities']['invalid_entity'] = {
        'field_mappings': 'not_a_dict'  # Should be a dict
    }
    assert not config_provider.validate_config()
    errors = config_provider.get_validation_errors()
    assert any('Invalid field_mappings' in err for err in errors)

def test_component_dependency_validation(config_provider):
    # Setup circular dependency
    config_provider._config['components']['a'] = {
        'class_path': 'test.Component',
        'settings': {'dependencies': ['b']}
    }
    config_provider._config['components']['b'] = {
        'class_path': 'test.Component',
        'settings': {'dependencies': ['a']}
    }
    config_provider._initialize_component_configs()
    
    assert not config_provider.validate_component_dependencies()
    errors = config_provider.get_validation_errors()
    assert any('Circular dependency' in err for err in errors)

def test_register_and_configure_component(config_provider):
    # Register a component
    mock_component = MockConfigurable()
    config_provider.register_component('test_component', MockConfigurable)
    
    # Configure it
    config_provider.configure_component('test_component', mock_component)
    
    # Get its config
    config = config_provider.get_component_config('test_component')
    assert config is not None
    assert config.settings == {'option1': 'value1'}

@pytest.mark.parametrize('invalid_path', [
    'nonexistent.json',
    'config.txt'  # Unsupported format
])
def test_load_config_errors(invalid_path):
    provider = ConfigurationProvider()
    with pytest.raises(ConfigurationError):
        provider.load_config(invalid_path)

def test_entity_config_cache(config_provider):
    # Get config first time
    config1 = config_provider.get_entity_config('test_entity')
    assert config1 is not None
    
    # Should return cached version
    config2 = config_provider.get_entity_config('test_entity')
    assert config2 is config1
    
    # Clear cache and get again
    config_provider.clear_entity_config_cache()
    config3 = config_provider.get_entity_config('test_entity')
    assert config3 is not None
    assert config3 is not config1
