"""Entity mediator for coordinating entity operations."""
from typing import Dict, Any, Optional, List
import logging

from .interfaces import IEntityMediator, IEntityFactory, IEntityStore, IValidationMediator

logger = logging.getLogger(__name__)


class EntityMediator(IEntityMediator):
    """Mediates operations between entity factory and store."""

    def __init__(self, 
                 factory: IEntityFactory,
                 store: IEntityStore,
                 validator: IValidationMediator):
        """Initialize entity mediator.
        
        Args:
            factory: Entity factory implementation
            store: Entity store implementation
            validator: Validation mediator for entity validation
        """
        self._factory = factory
        self._store = store
        self._validator = validator
        self._errors: List[str] = []

    def create_entity(self, entity_type: str, data: Dict[str, Any]) -> Any:
        """Create an entity instance.
        
        Args:
            entity_type: Type of entity to create
            data: Entity data dictionary
            
        Returns:
            Created entity instance or None if creation fails
        """
        try:
            # Validate entity data first
            if not self._validator.validate_entity(entity_type, data):
                self._errors.extend(self._validator.get_validation_errors())
                return None

            # Create entity instance
            entity = self._factory.create_entity(entity_type, data)
            if not entity:
                self._errors.append(f"Failed to create entity of type {entity_type}")
                return None

            return entity

        except Exception as e:
            logger.error(f"Entity creation error: {str(e)}")
            self._errors.append(f"Entity creation failed: {str(e)}")
            return None

    def store_entity(self, entity: Any) -> str:
        """Store an entity.
        
        Args:
            entity: Entity instance to store
            
        Returns:
            Entity ID if successful, empty string otherwise
        """
        try:
            # Get entity type from instance if available
            entity_type = getattr(entity, 'entity_type', None)
            if not entity_type:
                # Try to determine type from class name
                entity_type = entity.__class__.__name__.lower()

            # Store entity
            entity_id = self._store.save(entity_type, entity)
            if not entity_id:
                self._errors.append(f"Failed to store entity of type {entity_type}")
                return ""

            return entity_id

        except Exception as e:
            logger.error(f"Entity storage error: {str(e)}")
            self._errors.append(f"Entity storage failed: {str(e)}")
            return ""

    def get_entity(self, entity_type: str, entity_id: str) -> Optional[Any]:
        """Retrieve an entity.
        
        Args:
            entity_type: Type of entity to retrieve
            entity_id: ID of entity to retrieve
            
        Returns:
            Retrieved entity instance or None if not found
        """
        try:
            return self._store.get(entity_type, entity_id)

        except Exception as e:
            logger.error(f"Entity retrieval error: {str(e)}")
            self._errors.append(f"Entity retrieval failed: {str(e)}")
            return None

    def get_errors(self) -> List[str]:
        """Get error messages.
        
        Returns:
            List of error messages
        """
        return self._errors.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get operation statistics.
        
        Returns:
            Dictionary of statistics
        """
        stats = {
            'error_count': len(self._errors)
        }
        
        # Include store stats if available
        if hasattr(self._store, 'get_stats'):
            stats.update(self._store.get_stats())
            
        return stats