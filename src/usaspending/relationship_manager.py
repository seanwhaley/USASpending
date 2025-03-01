"""Relationship management functionality for entity stores."""
from typing import Dict, Any, Optional, Set, DefaultDict, List, Iterator
from collections import defaultdict
import logging
from itertools import chain

logger = logging.getLogger(__name__)

class RelationshipManager:
    """Manages entity relationships and validates relationship types."""

    def __init__(self, entity_type: str, config: Dict[str, Any]):
        """Initialize relationship manager."""
        self.entity_type = entity_type
        self.config = config
        self.relationships: Dict[str, DefaultDict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self._cache_relationship_configs()

    def _cache_relationship_configs(self) -> None:
        """Cache relationship configurations for faster access."""
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(self.entity_type, {}))

        self.cached_configs = {
            'hierarchical': entity_config.get('relationships', {}).get('hierarchical', []),
            'flat': entity_config.get('relationships', {}).get('flat', []),
            'valid_types': set(),
            'inverse_mappings': {},
            'relationship_rules': defaultdict(dict)
        }

        # Build valid types and inverse mappings
        for rel_config in chain(self.cached_configs['hierarchical'], self.cached_configs['flat']):
            if 'type' in rel_config:
                rel_type = rel_config['type']
                self.cached_configs['valid_types'].add(rel_type)
                
                # Cache inverse relationships
                if 'inverse_type' in rel_config:
                    inverse_type = rel_config['inverse_type']
                    self.cached_configs['valid_types'].add(inverse_type)
                    self.cached_configs['inverse_mappings'][rel_type] = inverse_type
                    self.cached_configs['inverse_mappings'][inverse_type] = rel_type

                # Cache relationship rules
                if 'rules' in rel_config:
                    self.cached_configs['relationship_rules'][rel_type].update(rel_config['rules'])

    def _get_valid_relationships(self) -> Set[str]:
        """Get valid relationship types from cached config."""
        return self.cached_configs['valid_types']

    def add_relationship(self, from_key: str, rel_type: str, to_key: str, inverse_type: Optional[str] = None) -> None:
        """Add a relationship between entities with optional inverse."""
        if not all([from_key, rel_type, to_key]):
            logger.warning("Invalid relationship parameters: empty key or type")
            return

        # Validate relationship type
        if rel_type not in self.cached_configs['valid_types']:
            logger.warning(f"Invalid relationship type '{rel_type}' for {self.entity_type}")
            return

        # Check relationship rules
        rules = self.cached_configs['relationship_rules'].get(rel_type, {})
        if rules:
            if rules.get('exclusive', False) and self.relationships[from_key][rel_type]:
                logger.warning(f"Exclusive relationship violation for {rel_type}")
                return
                
            if rules.get('max_cardinality'):
                if len(self.relationships[from_key][rel_type]) >= rules['max_cardinality']:
                    logger.warning(f"Maximum cardinality reached for {rel_type}")
                    return

        # Add forward relationship
        self.relationships[from_key][rel_type].add(to_key)
        logger.debug(f"Added relationship: {from_key} -{rel_type}-> {to_key}")

        # Add inverse relationship (from config if not specified)
        effective_inverse = inverse_type or self.cached_configs['inverse_mappings'].get(rel_type)
        if effective_inverse:
            self.relationships[to_key][effective_inverse].add(from_key)
            logger.debug(f"Added inverse relationship: {to_key} -{effective_inverse}-> {from_key}")

    def get_related_entities(self, entity_key: str, rel_type: str) -> Set[str]:
        """Get entities related to the given entity by relationship type."""
        return self.relationships.get(entity_key, {}).get(rel_type, set()).copy()

    def get_all_relationships(self, entity_key: str) -> Dict[str, Set[str]]:
        """Get all relationships for an entity."""
        return self.relationships.get(entity_key, defaultdict(set)).copy()

    def validate_relationship_types(self, relationship_types: Set[str]) -> List[str]:
        """Validate relationship types against allowed types."""
        return [rel_type for rel_type in relationship_types if rel_type not in self.cached_configs['valid_types']]

    def would_create_cycle(self, child_key: str, parent_key: str) -> bool:
        """Check if adding a parent-child relationship would create a cycle."""
        if child_key == parent_key:
            return True

        # Get all hierarchical relationship types
        hierarchical_types = {
            config['type'] for config in self.cached_configs['hierarchical']
            if 'type' in config
        }

        # Check if child is already an ancestor through any hierarchical relationship
        ancestors = set()
        to_check = {parent_key}
        
        while to_check:
            current = to_check.pop()
            if current == child_key:
                return True
                
            # Check all hierarchical relationships
            for rel_type in hierarchical_types:
                parents = self.get_related_entities(current, rel_type)
                new_ancestors = parents - ancestors
                ancestors.update(new_ancestors)
                to_check.update(new_ancestors)
                
        return False

    def process_flat_relationships(self, entity_data: Dict[str, Any], 
                                 context: Dict[str, Any],
                                 relationship_configs: Optional[List[Dict[str, Any]]] = None) -> None:
        """Process flat (non-hierarchical) relationships."""
        entity_key = context.get('key')
        if not entity_key:
            return

        configs = relationship_configs or self.cached_configs['flat']
        for rel_config in configs:
            from_field = rel_config.get('from_field')
            to_field = rel_config.get('to_field')
            rel_type = rel_config.get('type')
            inverse_type = rel_config.get('inverse_type')
            
            if not all([from_field, to_field, rel_type]):
                continue
                
            from_value = entity_data.get(from_field)
            to_value = entity_data.get(to_field)
            
            if from_value and to_value:
                if isinstance(from_value, (list, set)):
                    for value in from_value:
                        self.add_relationship(str(value), rel_type, str(to_value), inverse_type)
                else:
                    self.add_relationship(str(from_value), rel_type, str(to_value), inverse_type)

    def process_hierarchical_relationships(self, entity_data: Dict[str, Any], 
                                        entity_keys: Optional[Dict[str, str]], 
                                        relationship_configs: Optional[List[Dict[str, Any]]] = None) -> None:
        """Process hierarchical relationships."""
        if not entity_keys:
            return

        configs = relationship_configs or self.cached_configs['hierarchical']
        for rel_config in configs:
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

    def get_relationship_chain(self, start_key: str, relationship_path: List[str]) -> Iterator[str]:
        """Follow a chain of relationships from a starting entity."""
        current_keys = {start_key}
        yield start_key
        
        for rel_type in relationship_path:
            if not current_keys:
                break
                
            next_keys = set()
            for key in current_keys:
                next_keys.update(self.get_related_entities(key, rel_type))
            
            current_keys = next_keys
            for key in current_keys:
                yield key