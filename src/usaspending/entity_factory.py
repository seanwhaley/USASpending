"""Entity factory for creating and managing entity stores."""
from typing import Dict, Any, Type, Optional
import logging
from pathlib import Path

from .entity_store import EntityStore
from .recipient_store import RecipientEntityStore
from .contract_store import ContractEntityStore
from .agency_store import AgencyEntityStore
from .transaction_store import TransactionEntityStore
from .types import ConfigType

logger = logging.getLogger(__name__)

class EntityFactory:
    """Factory class for creating entity stores."""
    
    _entity_types: Dict[str, Type[EntityStore]] = {
        'recipient': RecipientEntityStore,
        'contract': ContractEntityStore,
        'agency': AgencyEntityStore,
        'transaction': TransactionEntityStore
    }

    @classmethod
    def create_store(cls, entity_type: str, base_path: str, config: ConfigType) -> EntityStore:
        """Create an entity store instance.
        
        Args:
            entity_type: Type of entity store to create
            base_path: Base path for entity files
            config: Configuration dictionary
            
        Returns:
            EntityStore instance
            
        Raises:
            ValueError: If entity type is invalid or configuration is missing
        """
        if entity_type not in cls._entity_types:
            raise ValueError(f"Invalid entity type: {entity_type}")
            
        store_class = cls._entity_types[entity_type]
        
        # Get entity-specific config
        entity_config = config.get('contracts', {}).get('entity_separation', {}).get('entities', {}).get(entity_type)
        if not entity_config:
            raise ValueError(f"Missing configuration for entity type: {entity_type}")
            
        # Create store with validated configuration
        store = store_class(
            Path(base_path) / f"{entity_type}_entities.json",
            entity_config,
            config
        )
        
        logger.debug(f"Created {entity_type} store")
        return store

    @staticmethod
    def validate_save_frequency(frequency: int) -> None:
        """Validate entity save frequency.
        
        Args:
            frequency: Save frequency to validate
            
        Raises:
            ValueError: If frequency is invalid
        """
        if not isinstance(frequency, int):
            raise ValueError("Entity save frequency must be an integer")
        if frequency <= 0:
            raise ValueError("Entity save frequency must be greater than 0")
            
    @staticmethod
    def link_entities(stores: Dict[str, EntityStore]) -> None:
        """Link entities across stores based on relationships.
        
        Args:
            stores: Dictionary of entity stores to link
        """
        for entity_type, store in stores.items():
            # Get relationship configurations
            relationships = store.config.get('relationships', {})
            
            for rel_type, rel_configs in relationships.items():
                for rel_config in rel_configs:
                    try:
                        # Get target entity type and fields
                        target_type = rel_config.get('to_entity_type')
                        if not target_type or target_type not in stores:
                            continue
                            
                        target_store = stores[target_type]
                        
                        # Link entities based on relationship type
                        if rel_type == 'hierarchical':
                            store.link_hierarchical_entities(
                                target_store,
                                rel_config.get('from_level', ''),
                                rel_config.get('to_level', ''),
                                rel_config.get('type', '')
                            )
                        else:
                            store.link_entities(
                                target_store,
                                rel_config.get('from_field', ''),
                                rel_config.get('to_field', ''),
                                rel_config.get('type', '')
                            )
                    except Exception as e:
                        logger.error(f"Error linking {entity_type} entities: {str(e)}")
                        raise

    @staticmethod
    def validate_references(stores: Dict[str, EntityStore]) -> None:
        """Validate entity references across stores.
        
        Args:
            stores: Dictionary of entity stores to validate
            
        Raises:
            ValueError: If references are invalid
        """
        for entity_type, store in stores.items():
            refs = store.config.get('entity_references', {})
            for ref_type, ref_config in refs.items():
                # Validate reference configuration
                if not isinstance(ref_config, dict):
                    raise ValueError(f"Invalid reference configuration for {entity_type}.{ref_type}")
                    
                # Check required fields
                required_fields = ['target_entity', 'key_field']
                missing = [f for f in required_fields if f not in ref_config]
                if missing:
                    raise ValueError(f"Missing required fields for {entity_type}.{ref_type}: {', '.join(missing)}")
                    
                # Validate target entity exists
                target_type = ref_config['target_entity']
                if target_type not in stores:
                    raise ValueError(f"Invalid target entity type in reference {entity_type}.{ref_type}: {target_type}")
                    
                # Validate key field exists in target entity
                target_store = stores[target_type]
                key_field = ref_config['key_field']
                if key_field not in target_store.get_field_names():
                    raise ValueError(f"Key field {key_field} not found in target entity {target_type}")