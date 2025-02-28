"""Base entity store implementation."""
from typing import Dict, Any, Optional, Union, Set, List
import logging
from pathlib import Path
from datetime import datetime

from .base_entity_store import BaseEntityStore
from .entity_cache import EntityCache
from .entity_mapper import EntityMapper
from .entity_serializer import EntitySerializer
from .relationship_manager import RelationshipManager
from .utils import generate_entity_key

logger = logging.getLogger(__name__)

class EntityStore(BaseEntityStore):
    """Basic entity store implementation using consolidated components."""

    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        """Initialize entity store with validation.
        
        Args:
            base_path: Base path for entity storage
            entity_type: Type of entity being stored
            config: Configuration dictionary
        """
        # Initialize components
        self.config = config
        self.entity_type = entity_type
        self.cache = EntityCache()
        self.mapper = EntityMapper(config, entity_type)
        self.serializer = EntitySerializer(base_path, entity_type, 
                                        config['global']['encoding'])
        self.relationship_manager = RelationshipManager(entity_type, config)
            
    def extract_entity_data(self, row_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entity data from row."""
        return self.mapper.extract_entity_data(row_data, self.cache.stats)
            
    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[Union[str, Dict[str, str]]]:
        """Add an entity to the store."""
        if not entity_data:
            self.cache.add_skipped("invalid_data")
            logger.debug(f"{self.entity_type}: Skipping invalid entity data")
            return None

        # Generate entity key
        entity_key = self._generate_entity_key(entity_data)
        if not entity_key:
            self.cache.add_skipped("missing_key_fields")
            logger.debug(f"{self.entity_type}: Failed to generate key for entity")
            return None
            
        # Add to cache
        is_update = isinstance(entity_key, str) and entity_key in self.cache.cache
        self.cache.add_entity(entity_key, entity_data, is_update)
        logger.debug(f"{self.entity_type}: {'Updated' if is_update else 'Added'} entity with key {entity_key}")
        
        # Process any configured relationships
        self.process_relationships(entity_data, {"key": entity_key})
                
        return entity_key
            
    def add_relationship(self, from_key: str, rel_type: str, to_key: str, inverse_type: Optional[str] = None) -> None:
        """Add a relationship between entities with optional inverse."""
        self.relationship_manager.add_relationship(from_key, rel_type, to_key, inverse_type)
            
    def validate_relationship_types(self, relationship_types: Set[str]) -> List[str]:
        """Validate relationship types against allowed types."""
        return self.relationship_manager.validate_relationship_types(relationship_types)
            
    def get_related_entities(self, entity_key: str, rel_type: str) -> Set[str]:
        """Get entities related to the given entity by relationship type."""
        return self.relationship_manager.get_related_entities(entity_key, rel_type)
            
    def process_relationships(self, entity_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        """Process all entity relationships."""
        if not entity_data:
            return
            
        if context is None:
            context = {}
            
        # Skip if no relationship config
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(self.entity_type, {}))
                        
        if not entity_config or 'relationships' not in entity_config:
            return
            
        relationships = entity_config['relationships']
        
        # Process flat relationships
        if 'flat' in relationships:
            self.relationship_manager.process_flat_relationships(entity_data, context, relationships['flat'])
            
        # Process hierarchical relationships
        if 'hierarchical' in relationships and isinstance(entity_data, dict):
            self.relationship_manager.process_hierarchical_relationships(entity_data, entity_keys=context.get('key'), relationship_configs=relationships['hierarchical'])
            
    def _generate_entity_key(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """Generate a unique key for an entity using configured key fields."""
        if not entity_data:
            return None
            
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(self.entity_type, {}))
                        
        if not entity_config:
            logger.warning(f"No configuration found for {self.entity_type}")
            return None
            
        # Get key fields from config
        key_fields = entity_config.get('key_fields', [])
        if not key_fields:
            logger.warning(f"No key fields configured for {self.entity_type}")
            return None
            
        # Get fields and values for key generation
        key_data = {}
        for field in key_fields:
            if field not in entity_data:
                logger.debug(f"Missing key field {field} for {self.entity_type}")
                return None
            key_data[field] = entity_data[field]
            
        # Generate key
        key = generate_entity_key(self.entity_type, key_data, key_fields)
        if key:
            if self.entity_type == "agency":
                self.cache.stats.natural_keys_used += 1
            else:
                self.cache.stats.hash_keys_used += 1
        return key

    def save(self) -> None:
        """Save entities and relationships."""
        self.serializer.save(
            self.cache.cache,
            self.relationship_manager.relationships,
            self.cache.get_stats()
        )