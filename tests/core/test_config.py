import pytest
from typing import Dict, Any
from pathlib import Path
import yaml
from src.usaspending.core.config import (
    ComponentConfig,
    ConfigurationProvider,
    ConfigRegistry
)
from src.usaspending.core.exceptions import ConfigurationError
from src.usaspending.core.interfaces import IConfigurable

class MockConfigurable(IConfigurable):
    def __init__(self):
        self.configured = False
        self.settings = {}
    
    def configure(self, config: ComponentConfig) -> None:
        self.configured = True
        self.settings = config.settings

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    return {
        'version': '1.0',
        'system': {
            'io': {
                'input': {
                    'path': 'input',
                    'formats': ['csv', 'json']
                },
                'output': {
                    'path': 'output',
                    'format': 'json'
                }
            },
            'processing': {
                'batch_size': 1000,
                'max_threads': 4
            }
        },
        'components': {
            'validator': {
                'class_path': 'test.validator.Validator',
                'settings': {
                    'strict_mode': True,
                    'rules': ['required', 'format']
                }
            },
            'mapper': {
                'class_path': 'test.mapper.Mapper',
                'settings': {
                    'mappings': {
                        'field1': 'value1',
                        'field2': 'value2'
                    }
                },
                'dependencies': ['validator']
            }
        }
    }

@pytest.fixture
def config_provider():
    provider = ConfigurationProvider()
    return provider

@pytest.fixture
def config_file(tmp_path, sample_config):
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(sample_config, f)
    return config_path

def test_component_config_initialization():
    config = ComponentConfig(
        class_path="test.Component",
        settings={'option1': 'value1'},
        enabled=True
    )
    assert config.class_path == "test.Component"
    assert config.settings == {'option1': 'value1'}
    assert config.enabled

def test_provider_initialization(config_provider):
    assert not config_provider._initialized
    assert len(config_provider._config) == 0
    assert len(config_provider._validation_errors) == 0
    assert isinstance(config_provider._registry, ConfigRegistry)

def test_load_config(config_provider, config_file):
    config_provider.load_config(str(config_file))
    assert config_provider._initialized
    assert 'system' in config_provider._config
    assert 'components' in config_provider._config

def test_get_config(config_provider, sample_config):
    config_provider._config = sample_config.copy()
    config_provider._initialized = True
    
    # Test full config retrieval
    assert config_provider.get_config() == sample_config
    
    # Test section retrieval
    assert config_provider.get_config('system') == sample_config['system']
    
    # Test missing section
    assert config_provider.get_config('nonexistent') == {}

def test_get_config_section(config_provider, sample_config):
    config_provider._config = sample_config.copy()
    config_provider._initialized = True
    
    # Test dot notation access
    section = config_provider.get_config_section('system.io.input')
    assert section == sample_config['system']['io']['input']
    
    # Test missing section
    assert config_provider.get_config_section('nonexistent', default={}) == {}
    
    # Test invalid path
    assert config_provider.get_config_section('system.invalid.path', default=None) is None

def test_validate_config(config_provider, sample_config):
    config_provider._config = sample_config.copy()
    assert config_provider.validate_config()
    assert len(config_provider.get_validation_errors()) == 0

def test_validate_missing_required_sections(config_provider):
    # Test with empty config
    config_provider._config = {}
    assert not config_provider.validate_config()
    errors = config_provider.get_validation_errors()
    assert any('Missing required section' in err for err in errors)

def test_component_dependency_validation(config_provider, sample_config):
    config_provider._config = sample_config.copy()
    
    # Add circular dependency
    config_provider._config['components']['circular1'] = {
        'class_path': 'test.Component1',
        'settings': {},
        'dependencies': ['circular2']
    }
    config_provider._config['components']['circular2'] = {
        'class_path': 'test.Component2',
        'settings': {},
        'dependencies': ['circular1']
    }
    
    assert not config_provider.validate_component_dependencies()
    errors = config_provider.get_validation_errors()
    assert any('Circular dependency' in err for err in errors)

def test_register_component(config_provider):
    component = MockConfigurable()
    config_provider.register_component('test', MockConfigurable)
    
    # Verify registration
    assert 'test' in config_provider._registry._components

def test_configure_component(config_provider, sample_config):
    config_provider._config = sample_config.copy()
    config_provider._initialized = True
    
    # Register and configure component
    component = MockConfigurable()
    config_provider.register_component('validator', MockConfigurable)
    config_provider.configure_component('validator', component)
    
    # Verify configuration
    assert component.configured
    assert component.settings == sample_config['components']['validator']['settings']

def test_load_invalid_config_file(config_provider, tmp_path):
    invalid_path = tmp_path / "invalid.yaml"
    with open(invalid_path, 'w') as f:
        f.write("invalid: yaml: content")
    
    with pytest.raises(ConfigurationError):
        config_provider.load_config(str(invalid_path))

def test_config_registry():
    registry = ConfigRegistry()
    
    # Test registration
    registry.register('test', MockConfigurable)
    assert 'test' in registry._components
    
    # Test retrieval
    component_class = registry.get('test')
    assert component_class == MockConfigurable
    
    # Test missing component
    assert registry.get('nonexistent') is None

def test_component_config_validation():
    # Test valid config
    valid_config = ComponentConfig(
        class_path="test.Component",
        settings={'valid': 'settings'}
    )
    assert valid_config.class_path == "test.Component"
    
    # Test missing class path
    with pytest.raises(ConfigurationError):
        ComponentConfig(settings={})

def test_config_schema_validation(config_provider, sample_config):
    config_provider._config = sample_config.copy()
    
    # Add invalid type for batch_size
    config_provider._config['system']['processing']['batch_size'] = "invalid"
    
    assert not config_provider.validate_config()
    errors = config_provider.get_validation_errors()
    assert any('batch_size' in err for err in errors)
