"""Entity factory for creating and managing entity stores."""
import os
from typing import Dict, Any, Optional, cast
from .entity_store import EntityStore
from .recipient_store import RecipientEntityStore
from .contract_store import ContractEntityStore
from .agency_store import AgencyEntityStore

class EntityFactory:
    """Factory for creating and managing entity stores."""
    
    @staticmethod
    def create_store(entity_type: str, base_path: str, config: Dict[str, Any]) -> EntityStore:
        """Create appropriate entity store based on type.
        
        Args:
            entity_type: Type of entity store to create
            base_path: Base path for entity storage
            config: Configuration dictionary
            
        Returns:
            EntityStore instance
        """
        # Create output directory if it doesn't exist
        os.makedirs(base_path, exist_ok=True)
        
        store_path = os.path.join(base_path, f"{entity_type}s.json")
        
        if entity_type == 'recipient':
            return RecipientEntityStore(store_path, entity_type, config)
        elif entity_type == 'contract':
            return ContractEntityStore(store_path, entity_type, config)
        elif entity_type == 'agency':
            return AgencyEntityStore(store_path, entity_type, config)
        else:
            return EntityStore(store_path, entity_type, config)

    @staticmethod
    def link_entities(stores: Dict[str, EntityStore]) -> None:
        """Link entities across stores based on relationships.
        
        Args:
            stores: Dictionary of entity stores by type
        """
        contract_store = stores.get('contract')
        recipient_store = stores.get('recipient')
        
        if not (contract_store and recipient_store):
            return
            
        # Cast to correct types for better type hints
        contract_store = cast(ContractEntityStore, contract_store)
        recipient_store = cast(RecipientEntityStore, recipient_store)
        
        # Process recipient relationships
        for contract_id, refs in contract_store.recipient_refs.items():
            direct_uei = refs.get('direct')
            parent_uei = refs.get('parent')
            
            if direct_uei:
                # Link contract to direct recipient
                recipient_store.add_contract_relationship(direct_uei, contract_id)
                
            if parent_uei and parent_uei != direct_uei:
                # Link contract to parent recipient
                recipient_store.add_contract_relationship(parent_uei, contract_id)