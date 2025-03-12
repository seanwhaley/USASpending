import pytest
from typing import Protocol
from abc import ABC, abstractmethod
from usaspending.component_utils import (
    implements_interface,
    implements,
    create_component,
    create_component_from_config,
    create_components_from_config
)
from usaspending.core.interfaces import IConfigurable
from usaspending.core.config import ComponentConfig
from usaspending.core.exceptions import ConfigurationError

# Test interfaces and classes
class ITestInterface(Protocol):
    def test_method(self) -> str: ...

class BaseInterface(ABC):
    @abstractmethod
    def base_method(self) -> str:
        pass

class ValidImplementation:
    def test_method(self) -> str:
        return "test"

class InvalidImplementation:
    def wrong_method(self) -> str:
        return "wrong"

@implements(ITestInterface)
class DecoratedImplementation:
    def test_method(self) -> str:
        return "decorated"

class SampleComponent(IConfigurable):
    def __init__(self, param1: str = "", param2: int = 0):
        self.param1 = param1
        self.param2 = param2
        self.configured = False

    def configure(self, config: ComponentConfig) -> None:
        self.configured = True
        if config.settings:
            self.param1 = config.settings.get('param1', self.param1)
            self.param2 = config.settings.get('param2', self.param2)

def test_implements_interface_with_protocol():
    assert implements_interface(ValidImplementation, ITestInterface)
    assert not implements_interface(InvalidImplementation, ITestInterface)

def test_implements_interface_with_abc():
    class ValidABC(BaseInterface):
        def base_method(self) -> str:
            return "valid"

    class InvalidABC:
        pass

    assert implements_interface(ValidABC, BaseInterface)
    assert not implements_interface(InvalidABC, BaseInterface)

def test_implements_decorator():
    # Should not raise any exception
    obj = DecoratedImplementation()
    assert isinstance(obj, DecoratedImplementation)
    assert obj.test_method() == "decorated"

    # Should raise TypeError when implementation is invalid
    class InvalidDecoratedTemp:
        pass
    
    with pytest.raises(TypeError):
        implements(ITestInterface)(InvalidDecoratedTemp)

def test_create_component():
    config = {'param1': 'test', 'param2': 42}
    # Test with full module path
    component = create_component(
        'usaspending.tests.test_component_utils.SampleComponent',
        config
    )
    assert isinstance(component, SampleComponent)
    assert isinstance(component, TestComponent)
    assert component.param1 == 'test'
    assert component.param2 == 42

    # Test with invalid path
    with pytest.raises(ConfigurationError):
        create_component('invalid.path.Component', {})

    config = {
        'class_path': 'usaspending.tests.test_component_utils.SampleComponent',
        'settings': {
            'param1': 'from_config',
            'param2': 100
        }
    }
    existing = {}
    
    component = create_component_from_config(config, existing)
    assert isinstance(component, SampleComponent)
    assert isinstance(component, TestComponent)
    assert component.param1 == 'from_config'
    assert component.param2 == 100
    assert component.configured

def test_create_components_from_config():
    config = {
        'test1': {
            'class_path': 'usaspending.tests.test_component_utils.SampleComponent',
            'settings': {'param1': 'one'}
        },
        'test2': {
            'class_path': 'usaspending.tests.test_component_utils.SampleComponent',
            'settings': {'param1': 'two'}
        }
    }

    components = create_components_from_config(config)
    assert isinstance(components['test1'], SampleComponent)
    assert isinstance(components['test2'], SampleComponent)
    assert isinstance(components['test2'], TestComponent)
    assert components['test1'].param1 == 'one'
    assert components['test2'].param1 == 'two'

def test_component_dependency_resolution():
    config = {
        'dependent': {
            'class_path': 'usaspending.tests.test_component_utils.SampleComponent',
            'settings': {
                'param1': 'dependent',
                'dependencies': ['base']
            }
        },
        'base': {
            'class_path': 'usaspending.tests.test_component_utils.SampleComponent',
            'settings': {'param1': 'base'}
        }
    }

    components = create_components_from_config(config)
    assert len(components) == 2
    assert 'base' in components
    assert 'dependent' in components

def test_invalid_component_config():
    invalid_config = {
        'components': {
            'test': {
                'settings': {'param1': 'test'}  # Missing class_path
            }
        }
    }
    
    with pytest.raises(ConfigurationError):
        create_components_from_config(invalid_config)

def test_circular_dependency_detection():
    config = {
        'a': {
            'class_path': 'usaspending.tests.test_component_utils.SampleComponent',
            'settings': {'dependencies': ['b']}
        },
        'b': {
            'class_path': 'usaspending.tests.test_component_utils.SampleComponent',
            'settings': {'dependencies': ['a']}
        }
    }

    with pytest.raises(ConfigurationError):
        create_components_from_config(config)