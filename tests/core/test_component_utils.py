import pytest
from typing import Dict, Any, Optional
from src.usaspending.core.component_utils import (
    implements_interface,
    implements,
    create_component,
    create_component_from_config,
    create_components_from_config
)
from src.usaspending.core.interfaces import IConfigurable
from src.usaspending.core.config import ComponentConfig
from src.usaspending.core.exceptions import ConfigurationError

# Test interfaces and implementations
class ITestComponent:
    def process(self) -> str:
        raise NotImplementedError

class IParameterizedComponent:
    def __init__(self, param1: str, param2: int):
        raise NotImplementedError

class TestComponent(ITestComponent):
    def process(self) -> str:
        return "processed"

class ConfigurableComponent(ITestComponent, IConfigurable):
    def __init__(self):
        self.configured = False
        self.settings = {}
    
    def configure(self, config: ComponentConfig) -> None:
        self.configured = True
        self.settings = config.settings
    
    def process(self) -> str:
        return "configured" if self.configured else "unconfigured"

class ParameterizedComponent(IParameterizedComponent):
    def __init__(self, param1: str, param2: int):
        self.param1 = param1
        self.param2 = param2

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    return {
        'test_component': {
            'class_path': 'tests.core.test_component_utils.TestComponent',
            'settings': {}
        },
        'configurable_component': {
            'class_path': 'tests.core.test_component_utils.ConfigurableComponent',
            'settings': {
                'option1': 'value1',
                'option2': 'value2'
            }
        },
        'parameterized_component': {
            'class_path': 'tests.core.test_component_utils.ParameterizedComponent',
            'settings': {},
            'parameters': {
                'param1': 'test',
                'param2': 42
            }
        }
    }

def test_implements_interface_check():
    # Test valid implementation
    assert implements_interface(TestComponent, ITestComponent)
    
    # Test invalid implementation
    class InvalidComponent:
        pass
    
    assert not implements_interface(InvalidComponent, ITestComponent)

def test_implements_decorator():
    # Test valid implementation
    @implements(ITestComponent)
    class ValidComponent:
        def process(self) -> str:
            return "valid"
    
    component = ValidComponent()
    assert component.process() == "valid"
    
    # Test invalid implementation
    with pytest.raises(TypeError):
        @implements(ITestComponent)
        class InvalidComponent:
            pass

def test_create_component_basic():
    # Test creating basic component
    component = create_component(
        'tests.core.test_component_utils.TestComponent',
        {}
    )
    assert isinstance(component, TestComponent)
    assert component.process() == "processed"

def test_create_component_with_parameters():
    # Test creating component with constructor parameters
    component = create_component(
        'tests.core.test_component_utils.ParameterizedComponent',
        {},
        param1="test",
        param2=42
    )
    assert isinstance(component, ParameterizedComponent)
    assert component.param1 == "test"
    assert component.param2 == 42

def test_create_component_configurable():
    # Test creating configurable component
    config = {'option1': 'value1'}
    component = create_component(
        'tests.core.test_component_utils.ConfigurableComponent',
        config
    )
    
    assert isinstance(component, ConfigurableComponent)
    assert component.configured
    assert component.settings == config
    assert component.process() == "configured"

def test_create_component_from_config(sample_config):
    # Test creating basic component
    component = create_component_from_config(
        sample_config['test_component'],
        {}
    )
    assert isinstance(component, TestComponent)
    
    # Test creating configurable component
    component = create_component_from_config(
        sample_config['configurable_component'],
        {}
    )
    assert isinstance(component, ConfigurableComponent)
    assert component.configured
    assert component.settings == sample_config['configurable_component']['settings']
    
    # Test creating parameterized component
    component = create_component_from_config(
        sample_config['parameterized_component'],
        {}
    )
    assert isinstance(component, ParameterizedComponent)
    assert component.param1 == 'test'
    assert component.param2 == 42

def test_create_components_from_config(sample_config):
    # Create all components
    components = create_components_from_config(sample_config)
    
    assert len(components) == 3
    assert isinstance(components['test_component'], TestComponent)
    assert isinstance(components['configurable_component'], ConfigurableComponent)
    assert isinstance(components['parameterized_component'], ParameterizedComponent)

def test_component_creation_errors():
    # Test invalid class path
    with pytest.raises(ConfigurationError):
        create_component('invalid.class.path', {})
    
    # Test missing required parameter
    with pytest.raises(TypeError):
        create_component(
            'tests.core.test_component_utils.ParameterizedComponent',
            {}
        )
    
    # Test invalid configuration
    with pytest.raises(ConfigurationError):
        create_component_from_config({}, {})

def test_component_dependencies():
    # Test component creation with dependencies
    config = {
        'component1': {
            'class_path': 'tests.core.test_component_utils.TestComponent',
            'settings': {}
        },
        'component2': {
            'class_path': 'tests.core.test_component_utils.ConfigurableComponent',
            'settings': {},
            'dependencies': ['component1']
        }
    }
    
    components = create_components_from_config(config)
    assert len(components) == 2
    assert isinstance(components['component1'], TestComponent)
    assert isinstance(components['component2'], ConfigurableComponent)

def test_component_dependency_resolution():
    # Test circular dependency detection
    config = {
        'component1': {
            'class_path': 'tests.core.test_component_utils.TestComponent',
            'settings': {},
            'dependencies': ['component2']
        },
        'component2': {
            'class_path': 'tests.core.test_component_utils.TestComponent',
            'settings': {},
            'dependencies': ['component1']
        }
    }
    
    with pytest.raises(ConfigurationError) as exc_info:
        create_components_from_config(config)
    assert "circular dependency" in str(exc_info.value).lower()

def test_component_inheritance():
    # Test component inheritance handling
    class BaseComponent:
        def base_method(self):
            return "base"
    
    class DerivedComponent(BaseComponent, IConfigurable):
        def configure(self, config: ComponentConfig) -> None:
            self.configured = True
    
    # Create derived component
    component = create_component(
        'tests.core.test_component_utils.DerivedComponent',
        {}
    )
    
    assert isinstance(component, DerivedComponent)
    assert isinstance(component, BaseComponent)
    assert component.base_method() == "base"
    assert component.configured
