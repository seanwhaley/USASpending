"""Transaction data store implementation."""
from typing import Dict, Any, Optional, Set, cast
import logging
from .entity_store import EntityStore
from .types import TransactionStats

logger = logging.getLogger(__name__)

class TransactionStore(EntityStore):
    """Manages transaction data storage and tracks modification sequences."""

    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        super().__init__(base_path, entity_type, config)
        # Only keep specialized tracking
        self.award_refs: Dict[str, Dict[str, Any]] = {}  # award_id -> award metadata

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Add transaction with modification sequence tracking."""
        if not entity_data:
            return None

        transaction_key = cast(str, super().add_entity(entity_data))
        if not transaction_key:
            return None

        # Track specialized award data
        award_id = str(entity_data.get('contract_award_unique_key'))
        if award_id:
            if award_id not in self.award_refs:
                self.award_refs[award_id] = {
                    "modification_number": entity_data.get("modification_number"),
                    "action_date": entity_data.get("action_date"),
                    "piid": entity_data.get("award_id_piid")
                }

            # Add relationships
            if entity_data.get("modification_number") == "0":
                # Base transaction creates award
                self.relationship_manager.add_relationship(
                    transaction_key,
                    "CREATES",
                    award_id
                )
            else:
                # Modification references award
                self.relationship_manager.add_relationship(
                    transaction_key,
                    "MODIFIES",
                    award_id,
                    "MODIFIED_BY"
                )

            # Add relationship to previous modification if exists
            if prev_mods := self.get_previous_modifications(award_id, entity_data.get("modification_number")):
                for prev_mod in prev_mods:
                    self.relationship_manager.add_relationship(
                        transaction_key,
                        "REFERENCES",
                        prev_mod
                    )

        return transaction_key

    def get_previous_modifications(self, award_id: str, current_mod: str) -> Set[str]:
        """Get previous modifications for an award."""
        if not current_mod or current_mod == "0":
            return set()

        # Find transactions that modify this award
        award_mods = self.relationship_manager.get_related_entities(award_id, "MODIFIED_BY")
        
        # Filter to get only previous modifications
        prev_mods = set()
        for mod_id in award_mods:
            mod_data = self.cache.cache.get(mod_id, {})
            mod_num = mod_data.get("modification_number", "")
            if mod_num and mod_num < current_mod:
                prev_mods.add(mod_id)
        
        return prev_mods

    def get_award_stats(self, award_id: str) -> Dict[str, Any]:
        """Get statistics for an award's transactions."""
        if award_id not in self.award_refs:
            return {}

        # Get all transactions for this award
        modifications = self.relationship_manager.get_related_entities(award_id, "MODIFIED_BY")
        base_transaction = next(iter(self.relationship_manager.get_related_entities(award_id, "CREATES")), None)
        
        if base_transaction:
            modifications.add(base_transaction)

        award_data = self.award_refs[award_id]
        return {
            "transaction_count": len(modifications),
            "first_action_date": award_data.get("action_date"),
            "modification_number": award_data.get("modification_number"),
            "piid": award_data.get("piid")
        }

    def save(self) -> None:
        """Save transactions with metadata."""
        try:
            logger.info(f"Transaction: Starting save with {len(self.cache.cache)} transactions")

            # Add award statistics to each transaction
            for transaction_id, transaction in self.cache.cache.items():
                # Find award this transaction relates to
                creates = self.relationship_manager.get_related_entities(transaction_id, "CREATES")
                modifies = self.relationship_manager.get_related_entities(transaction_id, "MODIFIES")
                
                award_id = next(iter(creates | modifies), None)
                if award_id:
                    transaction["award_stats"] = self.get_award_stats(award_id)
                    transaction["references"] = list(self.relationship_manager.get_related_entities(transaction_id, "REFERENCES"))

            super().save()
            logger.info(f"Transaction: Successfully saved {self.cache.stats.unique} transactions")

        except Exception as e:
            logger.error(f"Transaction: Error saving transaction store: {str(e)}")
            raise
