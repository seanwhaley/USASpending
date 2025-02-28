"""Contract entity store implementation."""
from typing import Dict, Any, Optional, Set, cast, Union
import logging
from .entity_store import EntityStore
from .types import ContractRelationshipStats, ContractValues

logger = logging.getLogger(__name__)

class ContractEntityStore(EntityStore):
    """Manages contract data storage with parent-child relationship tracking."""
    
    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        super().__init__(base_path, entity_type, config)
        self.potential_parents: Set[str] = set()
        self.parent_flags: Dict[str, bool] = {}
        self.child_mappings: Dict[str, str] = {}
        self.relationship_stats = ContractRelationshipStats()
        self.contract_values: Dict[str, ContractValues] = {}
        self.agency_roles: Dict[str, Dict[str, str]] = {}  # contract_id -> {role -> agency_id}
        self.recipient_refs: Dict[str, Dict[str, str]] = {}  # contract_id -> {'direct': uei, 'parent': parent_uei}

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Add contract with agency and recipient relationship tracking."""
        if not entity_data:
            return None
            
        # First add the contract as a basic entity
        contract_id = super().add_entity(entity_data)
        if not contract_id:
            return None

        # Track recipient references before processing relationships
        self._track_recipient_refs(contract_id, entity_data)
            
        # Process agency relationships based on roles
        self._process_agency_relationships(contract_id, entity_data)
        
        # Process recipient relationships
        self._process_recipient_relationships(contract_id, entity_data)

        # Track contract values
        self._track_contract_values(contract_id, entity_data)
                
        return contract_id

    def _track_recipient_refs(self, contract_id: str, entity_data: Dict[str, Any]) -> None:
        """Track recipient references for both direct and parent relationships."""
        recipient_uei = entity_data.get('recipient_ref')
        recipient_parent_uei = entity_data.get('recipient_parent_ref')
        
        if recipient_uei or recipient_parent_uei:
            self.recipient_refs[contract_id] = {
                'direct': recipient_uei,
                'parent': recipient_parent_uei
            }

    def _process_recipient_relationships(self, contract_id: str, entity_data: Dict[str, Any]) -> None:
        """Process recipient relationships with parent inference."""
        recipient_uei = entity_data.get('recipient_ref')
        if recipient_uei:
            # Add direct recipient relationship
            self.add_relationship(contract_id, "AWARDED_TO", recipient_uei)
            # Track in relationship stats
            self.relationship_stats.recipient_contracts += 1
            
            # If we know the parent UEI, add that relationship too
            recipient_parent_uei = entity_data.get('recipient_parent_ref')
            if recipient_parent_uei and recipient_parent_uei != recipient_uei:
                self.add_relationship(contract_id, "PARENT_RECIPIENT", recipient_parent_uei)
                self.relationship_stats.parent_recipient_contracts += 1

    def _process_agency_relationships(self, contract_id: str, entity_data: Dict[str, Any]) -> None:
        """Process agency relationships with role tracking."""
        agencies = entity_data.get('agencies', {})
        
        # Initialize role mapping for this contract
        self.agency_roles[contract_id] = {}
        
        # Process each agency role
        for role in ['awarding', 'funding', 'parent_award']:
            agency_ref = agencies.get(role, {}).get('ref')
            if agency_ref:
                # Store the role mapping
                self.agency_roles[contract_id][role] = agency_ref
                
                # Add the appropriate relationship based on role
                if role == 'awarding':
                    self.add_relationship(contract_id, "AWARDED_BY", agency_ref)
                    self.add_relationship(agency_ref, "AWARDED", contract_id)
                elif role == 'funding':
                    self.add_relationship(contract_id, "FUNDED_BY", agency_ref)
                    self.add_relationship(agency_ref, "FUNDED", contract_id)
                elif role == 'parent_award':
                    self.add_relationship(contract_id, "PARENT_AWARDED_BY", agency_ref)
                    self.add_relationship(agency_ref, "PARENT_AWARDED", contract_id)

    def _track_contract_values(self, contract_key: str, contract_data: Dict[str, Any]) -> None:
        """Track various contract value amounts."""
        if contract_key not in self.contract_values:
            self.contract_values[contract_key] = ContractValues()
            
        values = self.contract_values[contract_key]
        
        # Get current values
        current_value = float(contract_data.get('current_value', 0))
        potential_value = float(contract_data.get('potential_value', 0))
        obligated = float(contract_data.get('obligation_amount', 0))
        
        # Update tracked values
        values.current = max(values.current, current_value)
        values.potential = max(values.potential, potential_value)
        values.obligated += obligated  # Accumulate obligations
        
        # Track modification
        if 'modification_number' in contract_data:
            values.modifications.add(contract_data['modification_number'])

    def get_contract_hierarchy(self, contract_key: str) -> Dict[str, Any]:
        """Get contract's position in contract hierarchy."""
        hierarchy = {
            'parent': self.child_mappings.get(contract_key),
            'is_parent': self.parent_flags.get(contract_key, False),
            'children': [k for k, v in self.child_mappings.items() if v == contract_key],
            'agency_roles': self.agency_roles.get(contract_key, {}),
            'recipient_refs': self.recipient_refs.get(contract_key, {}),
            'values': {
                'current': self.contract_values[contract_key].current,
                'potential': self.contract_values[contract_key].potential,
                'obligated': self.contract_values[contract_key].obligated,
                'modification_count': len(self.contract_values[contract_key].modifications)
            } if contract_key in self.contract_values else None
        }
        return hierarchy

    def finalize_relationships(self) -> None:
        """Update final relationship statistics and counts."""
        self.relationship_stats.parent_contracts = len([k for k, v in self.parent_flags.items() if v])
        self.relationship_stats.child_contracts = len(self.child_mappings)
        self.relationship_stats.orphaned_references = len(self.potential_parents - set(self.cache.keys()))
        # Add recipient relationship stats
        self.relationship_stats.recipient_relationships = len(self.recipient_refs)

    def save(self) -> None:
        """Save contracts with finalized relationship data."""
        try:
            self.finalize_relationships()
            logger.info(f"Contract: Starting save with {len(self.cache)} contracts")
            
            # Add value summaries and recipient references to entity data
            for contract_key, contract in self.cache.items():
                if contract_key in self.contract_values:
                    contract['value_summary'] = {
                        'current': self.contract_values[contract_key].current,
                        'potential': self.contract_values[contract_key].potential,
                        'obligated': self.contract_values[contract_key].obligated,
                        'modifications': list(self.contract_values[contract_key].modifications)
                    }
                
                if contract_key in self.recipient_refs:
                    contract['recipient_summary'] = self.recipient_refs[contract_key]
                    
                logger.debug(f"Contract: Processed summaries for {contract_key}")
            
            super().save()
            logger.info(f"Contract: Successfully saved {self.stats.unique} contracts")
            
        except Exception as e:
            logger.error(f"Contract: Error saving contract store: {str(e)}")
            self._cleanup_temp_files()
            raise