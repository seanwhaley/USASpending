"""Entity factory for store creation."""
from typing import Dict, Any, Optional
import logging
from .entity_store import EntityStore
from .config import ConfigManager
from .exceptions import EntityStoreError, ConfigurationError

logger = logging.getLogger(__name__)

class EntityFactory:
    """Factory class for creating entity stores."""
    
    @classmethod
    def create_store(cls, base_path: str, entity_type: str, config_manager: ConfigManager) -> Optional[EntityStore]:
        """Create an entity store instance."""
        try:
            if not config_manager.validate_entity(entity_type):
                raise EntityStoreError(f"Invalid or disabled entity type: {entity_type}")
            
            return EntityStore(base_path, entity_type, config_manager)
            
        except Exception as e:
            logger.error(f"Error creating store for {entity_type}: {str(e)}")
            return None
    
    @classmethod
    def create_stores_from_config(cls, base_path: str, config_manager: ConfigManager) -> Dict[str, EntityStore]:
        """Create all entity stores defined in configuration."""
        stores = {}
        
        try:
            # Get ordered entities (includes dependency validation)
            processing_order = config_manager.get_processing_order()
            
            # Create stores in order
            for _, entity_type in processing_order:
                store = cls.create_store(base_path, entity_type, config_manager)
                if store:
                    stores[entity_type] = store
                else:
                    logger.error(f"Failed to create store for {entity_type}")
                    
            return stores
            
        except Exception as e:
            logger.error(f"Unexpected error creating stores: {str(e)}")
            return {}