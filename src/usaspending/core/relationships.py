"""Core relationship functionality."""
from typing import Dict, Any, Optional, List, Set
from enum import Enum
from .types import EntityType, RelationType, Cardinality  # Import from types instead of redefining

class RelationshipManager:
    """Manages entity relationships."""
    
    _cardinality_map = {
        (Cardinality.ONE_TO_ONE, True): RelationType.REFERENCE,
        (Cardinality.ONE_TO_MANY, True): RelationType.HIERARCHICAL,
        (Cardinality.MANY_TO_ONE, True): RelationType.HIERARCHICAL,
        (Cardinality.MANY_TO_MANY, False): RelationType.ASSOCIATIVE
    }

    def __init__(self) -> None:
        self._relationships: Dict[str, Dict[str, Any]] = {}
        
    def add_relationship(self, source: EntityType, target: EntityType, 
                        cardinality: Cardinality, is_hierarchical: bool = False) -> None:
        """Add entity relationship."""
        rel_type = self._get_relationship_type(cardinality, is_hierarchical)
        key = self._get_relationship_key(source, target)
        
        self._relationships[key] = {
            'source': source,
            'target': target,
            'type': rel_type,
            'cardinality': cardinality
        }
        
    def get_relationship(self, source: EntityType, target: EntityType) -> Optional[Dict[str, Any]]:
        """Get relationship between entities."""
        key = self._get_relationship_key(source, target)
        return self._relationships.get(key)
        
    def get_related_entities(self, entity_type: EntityType) -> Set[EntityType]:
        """Get all entities related to given entity."""
        related = set()
        for rel in self._relationships.values():
            if rel['source'] == entity_type:
                related.add(rel['target'])
            elif rel['target'] == entity_type:
                related.add(rel['source'])
        return related
        
    def _get_relationship_type(self, cardinality: Cardinality, is_hierarchical: bool) -> RelationType:
        """Determine relationship type based on cardinality."""
        rel_type = self._cardinality_map.get((cardinality, is_hierarchical))
        if rel_type is None:
            rel_type = RelationType.ASSOCIATIVE
        return rel_type
        
    @staticmethod
    def _get_relationship_key(source: EntityType, target: EntityType) -> str:
        """Generate unique key for relationship."""
        return f"{source}:{target}"

__all__ = ['RelationshipManager']