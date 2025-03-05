"""Factory for creating and managing system components."""
from typing import Dict, Any
from pathlib import Path

from . import get_logger, create_component, create_components_from_config
from .config import ConfigManager
from .entity_store import EntityStore
from .entity_mapper import EntityMapper
from .validation import ValidationEngine
from .entity_cache import EntityCache
from .entity_serializer import EntitySerializer

logger = get_logger(__name__)

class ComponentFactory:
    """Creates and manages system components with dependency injection."""
    
    def __init__(self, config: ConfigManager):
        """Initialize factory with configuration."""
        self.config = config
        self.base_path = Path(config.get('system', {}).get('io', {}).get('output', {}).get('directory', 'output'))
        self.entities_path = self.base_path / 'entities'
        self.cache = EntityCache()
        self.validation_engine = ValidationEngine(config)

    def create_entity_store(self, entity_type: str) -> EntityStore:
        """Create an EntityStore instance with all required dependencies."""
        # Create required components
        mapper = EntityMapper(self.config.config, entity_type)
        serializer = EntitySerializer(
            self.entities_path,
            entity_type,
            self.config.get('global', {}).get('encoding', 'utf-8')
        )

        # Create and return EntityStore with injected dependencies
        return EntityStore(
            str(self.entities_path),
            entity_type,
            self.config,
            self.validation_engine,
            mapper,
            self.cache,
            serializer
        )