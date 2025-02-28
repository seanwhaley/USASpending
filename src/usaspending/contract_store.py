"""Contract entity store implementation."""
from typing import Dict, Any, Optional, Set, cast
import logging
from .entity_store import EntityStore
from .types import ContractValues

logger = logging.getLogger(__name__)

class ContractEntityStore(EntityStore):
    """Manages contract data storage with value tracking."""
    
    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        super().__init__(base_path, entity_type, config)
        # Only keep specialized tracking
        self.contract_values: Dict[str, ContractValues] = {}

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Add contract with value tracking."""
        if not entity_data:
            return None

        contract_key = cast(str, super().add_entity(entity_data))
        if not contract_key:
            return None

        # Track contract values
        self._track_contract_values(contract_key, entity_data)

        # Process relationships if parent reference exists
        parent_key = entity_data.get('parent_award_id')
        if parent_key:
            self.relationship_manager.add_relationship(
                contract_key, 
                "CHILD_OF", 
                parent_key, 
                "PARENT_OF"
            )

        # Add recipient relationship
        recipient_ref = entity_data.get('recipient_ref')
        if recipient_ref:
            self.relationship_manager.add_relationship(
                contract_key, 
                "AWARDED_TO", 
                recipient_ref
            )

        # Add agency relationships
        awarding_agency = entity_data.get('awarding_agency_ref')
        if awarding_agency:
            self.relationship_manager.add_relationship(
                contract_key, 
                "AWARDED_BY", 
                awarding_agency
            )

        # Add location relationship if present
        if entity_data.get('place_of_performance'):
            self.relationship_manager.add_relationship(
                contract_key,
                "PERFORMED_AT",
                str(entity_data['place_of_performance'])
            )

        return contract_key

    def _track_contract_values(self, contract_key: str, contract_data: Dict[str, Any]) -> None:
        """Track contract value fields for analysis."""
        self.contract_values[contract_key] = ContractValues(
            current=float(contract_data.get('current_value', 0)),
            potential=float(contract_data.get('potential_value', 0)),
            obligation=float(contract_data.get('total_obligation', 0))
        )

    def get_contract_hierarchy(self, contract_key: str) -> Dict[str, Any]:
        """Get contract's position in contract hierarchy."""
        parents = self.relationship_manager.get_related_entities(contract_key, "CHILD_OF")
        children = self.relationship_manager.get_related_entities(contract_key, "PARENT_OF")
        
        hierarchy = {
            'parent_award': next(iter(parents)) if parents else None,
            'child_awards': list(children) if children else [],
            'values': self._get_contract_values(contract_key),
            'relationships': {
                'recipient': next(iter(self.relationship_manager.get_related_entities(contract_key, "AWARDED_TO")), None),
                'awarding_agency': next(iter(self.relationship_manager.get_related_entities(contract_key, "AWARDED_BY")), None),
                'performance_location': next(iter(self.relationship_manager.get_related_entities(contract_key, "PERFORMED_AT")), None)
            }
        }
        return hierarchy

    def _get_contract_values(self, contract_key: str) -> Optional[Dict[str, float]]:
        """Get contract value summary."""
        if contract_key not in self.contract_values:
            return None
            
        values = self.contract_values[contract_key]
        return {
            'current': values.current,
            'potential': values.potential,
            'obligated': values.obligation
        }

    def save(self) -> None:
        """Save contracts with value summaries."""
        try:
            logger.info(f"Contract: Starting save with {len(self.cache.cache)} contracts")
            
            for contract_key, contract in self.cache.cache.items():
                if contract_key in self.contract_values:
                    contract['value_summary'] = self._get_contract_values(contract_key)
                contract['hierarchy'] = self.get_contract_hierarchy(contract_key)
            
            super().save()
            logger.info(f"Contract: Successfully saved {self.cache.stats.unique} contracts")
            
        except Exception as e:
            logger.error(f"Contract: Error saving contract store: {str(e)}")
            raise