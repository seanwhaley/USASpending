"""Core configuration components."""
from typing import Dict, Any, Optional, List, Protocol, runtime_checkable
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ComponentConfig:
    """Configuration for a component."""
    settings: Dict[str, Any]
    class_path: Optional[str] = None
    enabled: bool = True

@runtime_checkable
class IConfigurable(Protocol):
    """Interface for configurable components."""
    @abstractmethod
    def configure(self, config: ComponentConfig) -> None:
        """Configure the component with structured configuration."""
        pass

@runtime_checkable
class IConfigurationProvider(Protocol):
    """Interface for configuration providers."""
    
    @abstractmethod
    def get_config(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration data."""
        pass
        
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate configuration."""
        pass
        
    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages."""
        pass

class BaseConfigProvider(ABC, IConfigurationProvider):
    """Base class for configuration providers."""
    
    @abstractmethod
    def get_config(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration data."""
        pass
        
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate configuration."""
        pass

    @abstractmethod
    def get_validation_errors(self) -> List[str]:
        """Get validation error messages."""
        pass

class ConfigRegistry:
    """Registry for configurable components."""
    
    def __init__(self) -> None:
        self._components: Dict[str, Any] = {}
    
    def register(self, name: str, component: Any) -> None:
        """Register a component."""
        self._components[name] = component
    
    def get(self, name: str) -> Optional[Any]:
        """Get a registered component."""
        return self._components.get(name)
    
    def clear(self) -> None:
        """Clear all registered components."""
        self._components.clear()
