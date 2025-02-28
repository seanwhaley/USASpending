"""Relationship management functionality for entity stores."""
from typing import Dict, Any, Optional, Set, DefaultDict, List
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class RelationshipManager:
    """Manages entity relationships and validates relationship types."""

    def __init__(self, entity_type: str, config: Dict[str, Any]):
        """Initialize relationship manager.
        
        Args:
            entity_type: Type of entity being managed
            config: Configuration dictionary containing relationship definitions
        """
        self.entity_type = entity_type
        self.config = config
        self.relationships: Dict[str, DefaultDict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        
    def _get_valid_relationships(self) -> Set[str]:
        """Get valid relationship types from config for this entity type."""
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(self.entity_type, {}))
                        
        valid_types = set()
        if 'relationships' in entity_config:
            # Extract from hierarchical relationships
            if 'hierarchical' in entity_config['relationships']:
                for rel_config in entity_config['relationships']['hierarchical']:
                    if 'type' in rel_config:
                        valid_types.add(rel_config['type'])
                    if 'inverse_type' in rel_config:
                        valid_types.add(rel_config['inverse_type'])
                        
            # Extract from flat relationships
            if 'flat' in entity_config['relationships']:
                for rel_config in entity_config['relationships']['flat']:
                    if 'type' in rel_config:
                        valid_types.add(rel_config['type'])
                    if 'inverse_type' in rel_config:
                        valid_types.add(rel_config['inverse_type'])
                        
        return valid_types

    def add_relationship(self, from_key: str, rel_type: str, to_key: str, inverse_type: Optional[str] = None) -> None:
        """Add a relationship between entities with optional inverse."""
        # Validate relationship type against config
        valid_types = self._get_valid_relationships()
        if rel_type not in valid_types:
            logger.warning(f"Invalid relationship type '{rel_type}' for {self.entity_type}")
            return

        # Add forward relationship
        self.relationships[from_key][rel_type].add(to_key)
        logger.debug(f"Added relationship: {from_key} -{rel_type}-> {to_key}")

        # Add inverse relationship if specified
        if inverse_type:
            if inverse_type not in valid_types:
                logger.warning(f"Invalid inverse relationship type '{inverse_type}' for {self.entity_type}")
                return
            self.relationships[to_key][inverse_type].add(from_key)
            logger.debug(f"Added inverse relationship: {to_key} -{inverse_type}-> {from_key}")

    def get_related_entities(self, entity_key: str, rel_type: str) -> Set[str]:
        """Get entities related to the given entity by relationship type.
        
        Args:
            entity_key: Entity key to get relationships for
            rel_type: Type of relationship to retrieve
            
        Returns:
            Set of related entity keys
        """
        return self.relationships.get(entity_key, {}).get(rel_type, set()).copy()

    def validate_relationship_types(self, relationship_types: Set[str]) -> List[str]:
        """Validate relationship types against allowed types.
        
        Args:
            relationship_types: Set of relationship types to validate
            
        Returns:
            List of invalid relationship types
        """
        valid_types = self._get_valid_relationships()
        return [rel_type for rel_type in relationship_types if rel_type not in valid_types]

    def would_create_cycle(self, child_key: str, parent_key: str) -> bool:
        """Check if adding a parent-child relationship would create a cycle.
        
        Args:
            child_key: Child entity key
            parent_key: Parent entity key
            
        Returns:
            True if relationship would create cycle, False otherwise
        """
        # Don't allow self-referential relationships
        if child_key == parent_key:
            return True

        # Check if child is already an ancestor of parent
        ancestors = set()
        to_check = {parent_key}
        
        while to_check:
            current = to_check.pop()
            if current == child_key:  # Would create cycle
                return True
                
            # Add parent's ancestors to check
            parents = self.get_related_entities(current, "SUBSIDIARY_OF")
            new_ancestors = parents - ancestors
            ancestors.update(new_ancestors)
            to_check.update(new_ancestors)
            
        return False

    def process_flat_relationships(self, entity_data: Dict[str, Any], 
                                 context: Dict[str, Any],
                                 relationship_configs: List[Dict[str, Any]]) -> None:
        """Process flat (non-hierarchical) relationships.
        
        Args:
            entity_data: Entity data containing relationship fields
            context: Additional context data (like entity keys)
            relationship_configs: List of relationship configurations
        """
        entity_key = context.get('key')
        if not entity_key:
            return

        for rel_config in relationship_configs:
            # Get source and target fields
            from_field = rel_config.get('from_field')
            to_field = rel_config.get('to_field')
            rel_type = rel_config.get('type')
            inverse_type = rel_config.get('inverse_type')
            
            if not all([from_field, to_field, rel_type]):
                continue
                
            # Get field values
            from_value = entity_data.get(from_field)
            to_value = entity_data.get(to_field)
            
            if from_value and to_value:
                if isinstance(from_value, (list, set)):
                    # Handle multi-value relationships
                    for value in from_value:
                        self.add_relationship(str(value), rel_type, str(to_value), inverse_type)
                else:
                    self.add_relationship(str(from_value), rel_type, str(to_value), inverse_type)

    def process_hierarchical_relationships(self, entity_data: Dict[str, Any], 
                                        entity_keys: Optional[Dict[str, str]], 
                                        relationship_configs: List[Dict[str, Any]]) -> None:
        """Process hierarchical relationships.
        
        Args:
            entity_data: Entity data containing level information
            entity_keys: Dictionary mapping levels to entity keys
            relationship_configs: List of hierarchical relationship configurations
        """
        if not entity_keys:
            return

        # Process configured relationships
        for rel_config in relationship_configs:
            from_level = rel_config.get('from_level')
            to_level = rel_config.get('to_level')
            rel_type = rel_config.get('type')
            inverse_type = rel_config.get('inverse_type')
            
            if not all([from_level, to_level, rel_type]):
                continue
                
            if from_level in entity_keys and to_level in entity_keys:
                from_key = entity_keys[from_level]
                to_key = entity_keys[to_level]
                
                # Check for cycles in hierarchical relationships
                if rel_type in {'HAS_SUBSIDIARY', 'SUBSIDIARY_OF', 'HAS_SUBAGENCY', 'BELONGS_TO_AGENCY'}:
                    if self.would_create_cycle(to_key, from_key):
                        logger.warning(f"Skipping relationship that would create cycle: {from_key} -{rel_type}-> {to_key}")
                        continue
                
                self.add_relationship(from_key, rel_type, to_key, inverse_type)