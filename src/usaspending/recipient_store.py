"""Recipient entity store implementation."""
from typing import Dict, Any, Optional, Set, cast
import logging
from collections import defaultdict
from .entity_store import EntityStore 
from .types import RecipientCharacteristics

logger = logging.getLogger(__name__)

class RecipientEntityStore(EntityStore):
    """Manages storage for recipient entities with business characteristics tracking."""
    
    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        super().__init__(base_path, entity_type, config)
        self.business_characteristics: Dict[str, Set[str]] = defaultdict(set)

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Add recipient entity with business characteristics processing."""
        if not entity_data:
            return None

        # Process business characteristics first
        self._process_recipient_characteristics(entity_data)
        
        # Add/update recipient using parent class
        recipient_key = cast(str, super().add_entity(entity_data))
        if not recipient_key:
            return None

        # Process parent-subsidiary relationships
        parent_uei = entity_data.get('parent_uei')
        if parent_uei:
            self.relationship_manager.add_relationship(
                recipient_key,
                "SUBSIDIARY_OF",
                parent_uei,
                "HAS_SUBSIDIARY"
            )

        # Process location relationships
        if location_ref := entity_data.get('location_ref'):
            self.relationship_manager.add_relationship(
                recipient_key,
                "LOCATED_AT",
                location_ref
            )
        
        return recipient_key

    def _process_recipient_characteristics(self, entity_data: Dict[str, Any]) -> None:
        """Process business characteristics."""
        if not self.entity_config or not entity_data:
            return

        characteristics = self.entity_config.get('business_characteristics', {})
        if not characteristics:
            return

        # Initialize characteristics in entity data if needed
        if 'characteristics' not in entity_data:
            entity_data['characteristics'] = defaultdict(set)

        # Process each characteristic category
        for category, fields in characteristics.items():
            for field in fields:
                if field in entity_data:
                    value = entity_data[field]
                    if isinstance(value, str):
                        # Convert string values to boolean
                        is_true = value.lower() in ('true', 'yes', 'y', '1', 't')
                        if is_true:
                            # Track characteristic at both levels
                            self.business_characteristics[category].add(field)
                            entity_data['characteristics'][category].add(field)

    def get_recipient_tree(self, root_uei: str, depth: int = -1) -> Optional[Dict[str, Any]]:
        """Get recipient's tree of parent/child relationships."""
        if root_uei not in self.cache.cache:
            return None

        tree: Dict[str, Any] = {
            'uei': root_uei,
            'data': self.cache.cache[root_uei].copy(),
            'children': []
        }

        if depth != 0:
            # Get child entities
            children = self.relationship_manager.get_related_entities(root_uei, "HAS_SUBSIDIARY")
            next_depth = depth - 1 if depth > 0 else -1

            # Recursively process children
            for child_uei in children:
                child_tree = self.get_recipient_tree(child_uei, next_depth)
                if child_tree:
                    tree['children'].append(child_tree)

        return tree

    def get_business_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics about business characteristics."""
        stats = {}
        for category, characteristics in self.business_characteristics.items():
            stats[category] = {
                char: sum(1 for entity in self.cache.cache.values()
                         if 'characteristics' in entity and
                         category in entity['characteristics'] and
                         char in entity['characteristics'][category])
                for char in characteristics
            }
        return stats

    def save(self) -> None:
        """Save recipients with characteristics and stats."""
        try:
            logger.info(f"Recipient: Starting save with {len(self.cache.cache)} recipients")

            # Convert sets to lists for JSON serialization
            for entity_data in self.cache.cache.values():
                if 'characteristics' in entity_data:
                    entity_data['characteristics'] = {
                        category: list(chars) 
                        for category, chars in entity_data['characteristics'].items()
                    }
                # Add relationship data
                entity_data['relationships'] = {
                    'parent': next(iter(self.relationship_manager.get_related_entities(
                        entity_data['key'], "SUBSIDIARY_OF")), None),
                    'subsidiaries': list(self.relationship_manager.get_related_entities(
                        entity_data['key'], "HAS_SUBSIDIARY")),
                    'location': next(iter(self.relationship_manager.get_related_entities(
                        entity_data['key'], "LOCATED_AT")), None)
                }

            # Save using parent class
            super().save()
            
            # Log statistics
            stats = self.get_business_stats()
            for category, counts in stats.items():
                logger.info(f"Recipient {category} characteristics:")
                for char, count in counts.items():
                    logger.info(f"  {char}: {count}")
                    
            logger.info(f"Recipient: Successfully saved {self.cache.stats.unique} recipients")

        except Exception as e:
            logger.error(f"Recipient: Error saving recipient store: {str(e)}")
            raise