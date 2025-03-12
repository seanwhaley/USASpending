"""Entity storage system."""
from typing import Dict, Any, Optional, List, Generator, cast, TypeVar, Generic
import logging
from .core.entity_base import IEntityStore, EntityData
from .core.interfaces import IConfigurable
from .core.config import ComponentConfig
from .core.types import EntityType
from .core.storage import IStorageStrategy, SQLiteStorage, FileSystemStorage
from .core.exceptions import StorageError
from .core.utils import safe_operation

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=EntityData)

class EntityStore(IEntityStore, IConfigurable):
    """Entity storage manager using strategy pattern."""
    
    def __init__(self) -> None:
        """Initialize entity store."""
        self._storage: Optional[IStorageStrategy] = None
        self._strict_mode: bool = False
        self._initialized: bool = False
    
    def configure(self, config: ComponentConfig) -> None:
        """Configure the store with settings."""
        if not config or not isinstance(config.settings, dict):
            raise StorageError("Entity store configuration is required")
            
        settings = config.settings
        self._strict_mode = settings.get('strict_mode', False)
        
        # Initialize storage strategy
        storage_type = settings.get('storage_type', 'filesystem')
        if storage_type == "sqlite":
            self._storage = SQLiteStorage(
                settings.get('path', 'entities.db'),
                max_connections=settings.get('max_connections', 5)
            )
        else:
            self._storage = FileSystemStorage(
                settings.get('path', 'entities'),
                max_files_per_dir=settings.get('max_files_per_dir', 1000),
                compression=settings.get('compression', True)
            )
            
        self._initialized = True

    def _check_initialized(self) -> None:
        """Check if store is initialized."""
        if not self._initialized or not self._storage:
            raise StorageError("Entity store is not initialized")
        
    @safe_operation
    def save_entity(self, entity_type: EntityType, entity: Dict[str, Any]) -> str:
        """Save an entity and return its ID."""
        self._check_initialized()
        assert self._storage is not None  # For mypy
        return self._storage.save_entity(str(entity_type), entity)
        
    @safe_operation
    def get_entity(self, entity_type: EntityType, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get an entity by ID."""
        self._check_initialized()
        assert self._storage is not None  # For mypy
        return self._storage.get_entity(str(entity_type), entity_id)
        
    @safe_operation
    def delete_entity(self, entity_type: EntityType, entity_id: str) -> bool:
        """Delete an entity."""
        self._check_initialized()
        assert self._storage is not None  # For mypy
        return self._storage.delete_entity(str(entity_type), entity_id)
        
    @safe_operation
    def list_entities(self, entity_type: EntityType) -> Generator[Dict[str, Any], None, None]:
        """Stream entities of a type."""
        self._check_initialized()
        assert self._storage is not None  # For mypy
        yield from self._storage.list_entities(str(entity_type))
        
    @safe_operation
    def count_entities(self, entity_type: EntityType) -> int:
        """Count entities of a type."""
        self._check_initialized()
        assert self._storage is not None  # For mypy
        return self._storage.count_entities(str(entity_type))
        
    def cleanup(self) -> None:
        """Clean up resources."""
        if self._storage:
            self._storage.cleanup()

__all__ = ['EntityStore']