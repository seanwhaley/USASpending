"""Recipient entity store implementation."""
from typing import Dict, Any, Optional, Set, Union, cast
import logging
from .entity_store import EntityStore
from .types import RecipientCharacteristics

logger = logging.getLogger(__name__)

class RecipientEntityStore(EntityStore):
    """Manages storage for recipient entities with parent-child relationships."""
    
    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        super().__init__(base_path, entity_type, config)
        self.business_characteristics: Dict[str, Set[str]] = {
            'ownership': set(),
            'structure': set(),
            'size': set()
        }
        # Track parent-child relationships
        self.parent_map: Dict[str, str] = {}  # child_uei -> parent_uei
        self.child_map: Dict[str, Set[str]] = {}  # parent_uei -> set of child_ueis

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Add recipient entity with parent-child relationship."""
        if not entity_data:
            return None

        # Process parent-child relationship before adding entity
        child_uei = entity_data.get('uei')
        parent_uei = entity_data.get('parent_uei')
        
        if not child_uei:
            logger.warning("Recipient entity missing required UEI")
            return None
            
        if parent_uei and parent_uei != child_uei:
            # Track relationship
            self.parent_map[child_uei] = parent_uei
            if parent_uei not in self.child_map:
                self.child_map[parent_uei] = set()
            self.child_map[parent_uei].add(child_uei)
            
            # Create minimal parent entity if it doesn't exist
            if parent_uei not in self.cache:
                parent_data = {
                    'uei': parent_uei,
                    'name': entity_data.get('parent_name', ''),
                    'children': [],
                    'relationships': {
                        'hierarchical': []
                    }
                }
                super().add_entity(parent_data)
                
            # Update parent's children list and add relationship
            parent_entity = self.cache.get(parent_uei)
            if parent_entity:
                if 'children' not in parent_entity:
                    parent_entity['children'] = []
                if child_uei not in parent_entity['children']:
                    parent_entity['children'].append(child_uei)
                    
                # Add hierarchical relationship
                if 'relationships' not in parent_entity:
                    parent_entity['relationships'] = {'hierarchical': []}
                parent_entity['relationships']['hierarchical'].append({
                    'from_field': parent_uei,
                    'to_field': child_uei,
                    'type': 'PARENT_OF',
                    'relationship': 'PARENT_OF',
                    'from_level': 'parent',
                    'to_level': 'child', 
                    'inverse': 'CHILD_OF'
                })

        # Update entity with relationship info
        if parent_uei:
            if 'relationships' not in entity_data:
                entity_data['relationships'] = {'hierarchical': []}
            entity_data['relationships']['hierarchical'].append({
                'from_field': child_uei,
                'to_field': parent_uei,
                'type': 'CHILD_OF',
                'relationship': 'CHILD_OF',
                'from_level': 'child',
                'to_level': 'parent',
                'inverse': 'PARENT_OF'
            })

        # Process business characteristics
        self._process_recipient_characteristics(entity_data)

        # Add the entity
        return super().add_entity(entity_data)

    def get_parent(self, uei: str) -> Optional[str]:
        """Get parent UEI for a given recipient UEI."""
        return self.parent_map.get(uei)

    def get_children(self, uei: str) -> Set[str]:
        """Get all child UEIs for a given recipient UEI."""
        return self.child_map.get(uei, set())

    def _process_recipient_characteristics(self, entity_data: Dict[str, Any]) -> None:
        """Process business characteristics for recipient entities."""
        if not self.entity_config or not entity_data:
            return
            
        characteristics = self.entity_config.get('business_characteristics', {})
        
        # Process each characteristic category
        for category, fields in characteristics.items():
            for field in fields:
                if field in entity_data and entity_data[field]:
                    self.business_characteristics[category].add(field)
                    # Add characteristic to entity data
                    if 'characteristics' not in entity_data:
                        entity_data['characteristics'] = {}
                    if category not in entity_data['characteristics']:
                        entity_data['characteristics'][category] = set()
                    entity_data['characteristics'][category].add(field)

    def add_contract_relationship(self, uei: str, contract_id: str) -> None:
        """Add contract relationship to recipient entity."""
        entity = self.cache.get(uei)
        if entity:
            if 'relationships' not in entity:
                entity['relationships'] = {}
            if 'contract' not in entity['relationships']:
                entity['relationships']['contract'] = []
            # Add relationship with required fields
            entity['relationships']['contract'].append({
                'from_field': uei,
                'to_field': contract_id,
                'type': 'RECIPIENT_OF',
                'relationship': 'RECIPIENT_OF',
                'from_level': 'recipient',
                'to_level': 'contract',
                'inverse': 'AWARDED_TO'
            })

    def save(self) -> None:
        """Save recipient entities with business characteristics stats."""
        try:
            # Convert sets to lists for JSON serialization
            for entity_data in self.cache.values():
                # Convert characteristics sets to lists
                if 'characteristics' in entity_data:
                    for category in entity_data['characteristics']:
                        entity_data['characteristics'][category] = list(
                            entity_data['characteristics'][category]
                        )
            
            super().save()
            
            if logger.isEnabledFor(logging.INFO):
                # Log relationship statistics
                logger.info(f"Parent-child relationships: {len(self.parent_map)}")
                logger.info(f"Unique parent recipients: {len(self.child_map)}")
                # Log business characteristics statistics
                for category, values in self.business_characteristics.items():
                    logger.info(f"Recipient {category} characteristics: {len(values)}")
                    
        except Exception as e:
            logger.error(f"Error saving recipient store: {str(e)}")
            self._cleanup_temp_files()
            raise