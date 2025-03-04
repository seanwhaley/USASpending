"""Entity factory for creating and managing entity stores."""
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .config import ConfigManager
from .entity_store import EntityStore
from .entity_mapper import EntityMapper
from .validation import ValidationEngine
from .exceptions import EntityError

class EntityFactory:
    """Factory for creating and managing entity stores."""

    def __init__(self, config: Union[ConfigManager, Dict[str, Any]]):
        """Initialize with configuration."""
        if isinstance(config, dict):
            self.config_manager = ConfigManager(config)
        else:
            self.config_manager = config
            
        self.config = self.config_manager.get_config()
        output_dir = Path(self.config['system']['io']['output']['directory'])
        self.base_path = str(output_dir / 'entities')
        self.validator = ValidationEngine(self.config)

    def create_store(self, entity_type: str) -> EntityStore:
        """Create a new entity store instance."""
        try:
            return EntityStore(self.base_path, entity_type, self.config_manager)
        except Exception as e:
            raise EntityError(f"Failed to create entity store for {entity_type}: {str(e)}") from e

    def _make_hashable_key(self, key: Union[str, Dict[str, str]]) -> str:
        """Convert a key into a hashable format."""
        if isinstance(key, str):
            return key
        elif isinstance(key, dict):
            return tuple(sorted(key.items())).__str__()
        else:
            raise ValueError(f"Invalid key type: {type(key)}")