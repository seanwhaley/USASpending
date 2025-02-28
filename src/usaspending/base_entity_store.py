"""Interface definition for entity stores."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, Set, List

class BaseEntityStore(ABC):
    """Interface defining the contract for entity stores."""
    
    @abstractmethod
    def extract_entity_data(self, row_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entity data from row.
        
        Args:
            row_data: Raw data from CSV row
            
        Returns:
            Extracted entity data or None if no valid data found
        """
        pass
        
    @abstractmethod
    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[Union[str, Dict[str, str]]]:
        """Add an entity to the store.
        
        Args:
            entity_data: Entity data to store
            
        Returns:
            Entity key or dict of keys for hierarchical entities
        """
        pass
        
    @abstractmethod
    def add_relationship(self, from_key: str, rel_type: str, to_key: str, inverse_type: Optional[str] = None) -> None:
        """Add a relationship between entities with optional inverse.
        
        Args:
            from_key: Key of source entity
            rel_type: Type of relationship
            to_key: Key of target entity
            inverse_type: Optional inverse relationship type
        """
        pass

    @abstractmethod
    def save(self) -> None:
        """Save entities and relationships to disk."""
        pass
    
    @abstractmethod
    def validate_relationship_types(self, relationship_types: Set[str]) -> List[str]:
        """Validate relationship types against allowed types.
        
        Args:
            relationship_types: Set of relationship types to validate
            
        Returns:
            List of invalid relationship types
        """
        pass
        
    @abstractmethod
    def get_related_entities(self, entity_key: str, rel_type: str) -> Set[str]:
        """Get entities related to the given entity by relationship type.
        
        Args:
            entity_key: Key of entity to get relationships for
            rel_type: Type of relationship to look for
            
        Returns:
            Set of related entity keys
        """
        pass
