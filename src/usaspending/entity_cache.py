"""Entity cache implementation using singleton pattern."""
from typing import Dict, Any, Optional, Set, DefaultDict
from collections import defaultdict

class EntityStats:
    """Track entity statistics."""
    def __init__(self):
        self.total = 0  # Total entities processed
        self.unique = 0  # Unique entities stored
        self.natural_keys_used = 0  # Keys generated from natural fields
        self.hash_keys_used = 0  # Keys generated using hashing
        self.skipped: Dict[str, int] = defaultdict(int)  # Counts of skipped entities by reason
        self.relationships: Dict[str, int] = defaultdict(int)  # Counts by relationship type

class EntityCache:
    """Singleton cache for storing entities."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.stats = EntityStats()
        self.pending_parents: Dict[str, Dict[str, Any]] = {}
        self._entity_index: Dict[str, Set[str]] = defaultdict(set)  # Field value to entity key mapping

    def add_entity(self, entity_key: str, entity_data: Dict[str, Any], is_update: bool = False) -> None:
        """Add or update an entity in the cache.
        
        Args:
            entity_key: Unique key for the entity
            entity_data: Entity data to store
            is_update: Whether this is an update to an existing entity
        """
        # Track statistics
        self.stats.total += 1
        if not is_update:
            self.stats.unique += 1

        # Remove old index entries if updating
        if is_update and entity_key in self.cache:
            self._remove_from_index(entity_key, self.cache[entity_key])

        # Store entity data
        self.cache[entity_key] = entity_data

        # Update index
        self._add_to_index(entity_key, entity_data)

    def get_entity(self, entity_key: str) -> Optional[Dict[str, Any]]:
        """Get entity data by key.
        
        Args:
            entity_key: Key of entity to retrieve
            
        Returns:
            Entity data if found, None otherwise
        """
        return self.cache.get(entity_key)

    def find_entities(self, field: str, value: Any) -> Set[str]:
        """Find entities by field value.
        
        Args:
            field: Field to search
            value: Value to search for
            
        Returns:
            Set of entity keys matching the search
        """
        index_key = f"{field}:{value}"
        return self._entity_index.get(index_key, set()).copy()

    def update_entity(self, entity_key: str, updates: Dict[str, Any]) -> None:
        """Update an existing entity.
        
        Args:
            entity_key: Key of entity to update
            updates: Fields to update
        """
        if entity_key in self.cache:
            existing = self.cache[entity_key]
            # Remove from index before update
            self._remove_from_index(entity_key, existing)
            # Update data
            existing.update(updates)
            # Re-index
            self._add_to_index(entity_key, existing)
        else:
            self.add_entity(entity_key, updates)

    def clear(self) -> None:
        """Clear all cached data."""
        self.cache.clear()
        self._entity_index.clear()
        self.pending_parents.clear()
        self.stats = EntityStats()

    def _add_to_index(self, entity_key: str, entity_data: Dict[str, Any]) -> None:
        """Add entity to field value index.
        
        Args:
            entity_key: Key of entity to index
            entity_data: Entity data containing field values
        """
        for field, value in entity_data.items():
            if isinstance(value, (str, int, float, bool)):
                index_key = f"{field}:{value}"
                self._entity_index[index_key].add(entity_key)

    def _remove_from_index(self, entity_key: str, entity_data: Dict[str, Any]) -> None:
        """Remove entity from field value index.
        
        Args:
            entity_key: Key of entity to remove
            entity_data: Entity data containing field values
        """
        for field, value in entity_data.items():
            if isinstance(value, (str, int, float, bool)):
                index_key = f"{field}:{value}"
                self._entity_index[index_key].discard(entity_key)
                # Clean up empty sets
                if not self._entity_index[index_key]:
                    del self._entity_index[index_key]

    def add_skipped(self, reason: str) -> None:
        """Track a skipped entity.
        
        Args:
            reason: Reason entity was skipped
        """
        self.stats.skipped[reason] += 1

    def add_relationship_count(self, rel_type: str) -> None:
        """Track a relationship.
        
        Args:
            rel_type: Type of relationship
        """
        self.stats.relationships[rel_type] += 1

    def get_siblings(self, entity_key: str, field_name: str) -> Set[str]:
        """Get entities sharing the same field value.
        
        Args:
            entity_key: Key of entity to find siblings for
            field_name: Field to check for shared values
            
        Returns:
            Set of entity keys sharing the same field value
        """
        if entity_key in self.cache:
            entity = self.cache[entity_key]
            if field_name in entity:
                value = entity[field_name]
                index_key = f"{field_name}:{value}"
                siblings = self._entity_index.get(index_key, set()).copy()
                siblings.discard(entity_key)  # Exclude self
                return siblings
        return set()

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            "total": self.stats.total,
            "unique": self.stats.unique,
            "natural_keys_used": self.stats.natural_keys_used,
            "hash_keys_used": self.stats.hash_keys_used,
            "skipped": dict(self.stats.skipped),
            "relationships": dict(self.stats.relationships)
        }

def get_entity_cache() -> EntityCache:
    """Get the global EntityCache instance."""
    return EntityCache()