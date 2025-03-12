"""Utilities for component creation and management."""
from typing import Dict, Any, Optional, List, Type, TypeVar, Callable
import importlib
import inspect
import threading
import abc
from functools import wraps

from .core.logging_config import get_logger
from .core.exceptions import ConfigurationError
from .core.config import ComponentConfig

logger = get_logger(__name__)

T = TypeVar('T')

def implements_interface(cls: Type, interface: Type) -> bool:
    """Check if a class implements an interface.
    
    Args:
        cls: The class to check
        interface: The interface class that should be implemented
        
    Returns:
        True if cls implements interface, False otherwise
    """
    # Get all abstract attributes (methods and properties)
    interface_abstracts = {
        name: attr for name, attr in inspect.getmembers(interface)
        if not name.startswith('_') and (
            getattr(attr, '__isabstractmethod__', False) or
            isinstance(attr, property) and getattr(attr.fget, '__isabstractmethod__', False)
        )
    }
    
    # Check all abstract attributes are implemented
    for name, attr in interface_abstracts.items():
        if not hasattr(cls, name):
            return False
        
        cls_attr = getattr(cls, name)
        # Check if it's still abstract in the implementing class
        if getattr(cls_attr, '__isabstractmethod__', False):
            return False
            
        # For properties, check if the getter is implemented
        if isinstance(attr, property):
            if not isinstance(cls_attr, property) or getattr(cls_attr.fget, '__isabstractmethod__', False):
                return False
                
    return True

def implements(interface: Type) -> Callable[[Type[T]], Type[T]]:
    """Decorator to verify a class implements an interface.
    
    Args:
        interface: The interface class that should be implemented
        
    Returns:
        A class decorator that verifies interface implementation
        
    Raises:
        TypeError: If the decorated class doesn't properly implement the interface
    """
    def decorator(cls: Type[T]) -> Type[T]:
        if not implements_interface(cls, interface):
            missing = []
            for name, method in inspect.getmembers(interface):
                if not name.startswith('_') and hasattr(method, '__isabstractmethod__'):
                    if not hasattr(cls, name) or getattr(getattr(cls, name), '__isabstractmethod__', False):
                        missing.append(name)
            raise TypeError(f"{cls.__name__} must implement abstract methods: {', '.join(missing)}")
        return cls
    return decorator

def create_component(class_path: str, config: Dict[str, Any], **kwargs: Any) -> Any:
    """Create a component instance from class path and configuration.
    
    Args:
        class_path: Fully qualified class path (module.Class)
        config: Configuration dictionary for the component
        **kwargs: Additional constructor parameters
        
    Returns:
        Component instance
    """
    try:
        # Split into module and class parts
        module_path, class_name = class_path.rsplit('.', 1)
        
        # Import module
        module = importlib.import_module(module_path)
        
        # Get class
        class_type = getattr(module, class_name)
        
        # Create instance with constructor args
        instance = class_type(**kwargs)
        
        # Configure if component is configurable
        if hasattr(instance, 'configure'):
            instance.configure(ComponentConfig(
                settings=config,
                class_path=class_path
            ))
            
        return instance
        
    except Exception as e:
        logger.error(f"Error creating component {class_path}: {str(e)}")
        raise ConfigurationError(f"Failed to create component {class_path}: {str(e)}")

def create_component_from_config(component_config: Dict[str, Any], existing_components: Dict[str, Any]) -> Any:
    """Create a component instance from configuration with dependency injection.
    
    Args:
        component_config: Component configuration dictionary
        existing_components: Dictionary of already created components for dependency injection
        
    Returns:
        Component instance
    """
    class_path = component_config.get('class')
    if not class_path:
        raise ConfigurationError("Missing 'class' in component configuration")
    
    try:
        # Split into module and class parts
        module_path, class_name = class_path.rsplit('.', 1)
        
        # Import module
        module = importlib.import_module(module_path)
        
        # Get class
        class_type = getattr(module, class_name)
        
        # Prepare constructor kwargs
        kwargs = component_config.get('config', {}).copy()
        
        # Inject dependencies based on constructor signature
        sig = inspect.signature(class_type.__init__)
        
        # For each parameter in the constructor
        for param_name, param in list(sig.parameters.items())[1:]:  # Skip 'self'
            # Check if parameter name matches an existing component
            if param_name in existing_components:
                kwargs[param_name] = existing_components[param_name]
        
        # Create instance
        instance = class_type(**kwargs)
        
        # Configure if component is configurable
        if hasattr(instance, 'configure'):
            instance.configure(ComponentConfig(
                settings=component_config.get('config', {}),
                class_path=class_path,
                enabled=component_config.get('enabled', True)
            ))
            
        return instance
        
    except Exception as e:
        logger.error(f"Error creating component from {class_path}: {str(e)}")
        raise ConfigurationError(f"Failed to create component: {str(e)}")

def create_components_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Create component instances from configuration.
    
    Args:
        config: Complete configuration dictionary
        
    Returns:
        Dictionary of created components
    """
    components = {}
    
    if 'system' not in config:
        raise ValueError("Missing 'system' section in configuration")
    
    system_config = config['system']
    
    # Load standard components in dependency order
    component_names = [
        'entity_factory',
        'entity_store',
        'validation_service'
    ]
    
    # First create entity_factory as it's needed by entity_store
    if 'entity_factory' in system_config:
        entity_factory_config = system_config['entity_factory']
        components['entity_factory'] = create_component(
            entity_factory_config.get('class', 'usaspending.entity_factory.EntityFactory'),
            entity_factory_config.get('config', {})
        )
    
    # Create remaining components with dependency injection
    for name in component_names[1:]:  # Skip entity_factory as it's already created
        try:
            if name in system_config:
                component_config = system_config[name]
                if name == 'entity_store':
                    # Special case for entity_store which needs factory
                    components[name] = create_component(
                        component_config.get('class', f'usaspending.{name}.{name.title()}'),
                        component_config.get('config', {}),
                        factory=components.get('entity_factory')
                    )
                else:
                    # For other components, use general pattern
                    components[name] = create_component_from_config(component_config, components)
            else:
                logger.warning(f"Component configuration missing for {name}")
        except Exception as e:
            logger.error(f"Error loading component {name}: {str(e)}")
            raise
    
    return components
