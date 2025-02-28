"""Transaction data store implementation."""
from typing import Dict, Any, Optional, Tuple, Set
import logging
from .entity_store import EntityStore
from .types import ContractData, TransactionEntity

logger = logging.getLogger(__name__)

class TransactionStore(EntityStore):
    """Manages storage for transaction data with relationship tracking."""

    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        super().__init__(base_path, entity_type, config)
        self.parent_agency_refs: Dict[str, Tuple[str, str]] = {}
        self.award_refs: Dict[str, Dict[str, Any]] = {}
        self.modification_sequence: Dict[str, Set[str]] = {}

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Add transaction with relationship tracking."""
        if not entity_data:
            self.stats.skipped["invalid_data"] += 1
            return None

        # Track total records
        self.stats.total += 1

        # Generate key from transaction unique key
        transaction_id = str(entity_data.get('contract_transaction_unique_key'))
        award_id = str(entity_data.get('contract_award_unique_key'))
        piid = str(entity_data.get('award_id_piid'))

        # Validate required fields
        if not all([transaction_id, award_id, piid]):
            self.stats.skipped["missing_key_fields"] += 1
            return None

        # Add or update in cache
        if transaction_id not in self.cache:
            self.cache[transaction_id] = entity_data
            self.stats.unique += 1
            logger.debug(f"Transaction: Added new transaction {transaction_id}")
        else:
            # Update existing transaction while preserving relationships
            existing_data = self.cache[transaction_id]
            existing_data.update(entity_data)
            logger.debug(f"Transaction: Updated existing transaction {transaction_id}")

        # Track contract award relationships
        if award_id not in self.award_refs:
            self.award_refs[award_id] = {
                "modification_number": entity_data.get("modification_number"),
                "action_date": entity_data.get("action_date"),
                "transactions": set(),
                "piid": piid
            }
            logger.debug(f"Transaction: Created new award reference for {award_id}")
        
        self.award_refs[award_id]["transactions"].add(transaction_id)
        
        # Track modification sequence
        if award_id not in self.modification_sequence:
            self.modification_sequence[award_id] = set()
            
        self.modification_sequence[award_id].add(transaction_id)

        return transaction_id

    def update_parent_agency_reference(self, transaction_key: str, level: str, agency_id: str) -> None:
        """Update transaction's parent agency reference after resolution."""
        if transaction_key not in self.cache:
            logger.debug(f"Transaction: Cannot update parent agency ref - transaction {transaction_key} not found")
            return
            
        # Store the parent agency reference for this transaction
        if transaction_key not in self.parent_agency_refs:
            self.parent_agency_refs[transaction_key] = ("", "")
            
        # Convert agency_id to string for consistency
        agency_id = str(agency_id)
            
        if level == "agency":
            self.parent_agency_refs[transaction_key] = (agency_id, self.parent_agency_refs[transaction_key][1])
            logger.debug(f"Transaction: Updated agency parent ref for {transaction_key} to {agency_id}")
        elif level == "subagency":
            self.parent_agency_refs[transaction_key] = (self.parent_agency_refs[transaction_key][0], agency_id)
            logger.debug(f"Transaction: Updated subagency parent ref for {transaction_key} to {agency_id}")

    def get_award_stats(self, award_id: str) -> Dict[str, Any]:
        """Get statistics for an award's transactions."""
        if award_id not in self.award_refs:
            return {}
            
        award_data = self.award_refs[award_id]
        transaction_count = len(award_data["transactions"])
        
        return {
            "transaction_count": transaction_count,
            "modification_count": len(self.modification_sequence.get(award_id, set())),
            "first_action_date": award_data.get("action_date"),
            "modification_number": award_data.get("modification_number"),
            "piid": award_data.get("piid")
        }

    def save(self) -> None:
        """Save transactions with resolved references and stats."""
        try:
            logger.info(f"Transaction: Starting save with {len(self.cache)} transactions")
            
            # Add relationship statistics
            for award_id, transactions in self.modification_sequence.items():
                for transaction_id in transactions:
                    if transaction_id in self.cache:
                        self.cache[transaction_id]["award_stats"] = self.get_award_stats(award_id)
                        logger.debug(f"Transaction: Added award stats for {transaction_id} under award {award_id}")
                        
            # Add parent agency references
            for transaction_id, (agency_id, subagency_id) in self.parent_agency_refs.items():
                if transaction_id in self.cache:
                    self.cache[transaction_id]["parent_agencies"] = {
                        "agency_id": agency_id,
                        "subagency_id": subagency_id
                    }
                    logger.debug(f"Transaction: Added parent agency refs for {transaction_id}")
                    
            super().save()
            logger.info(f"Transaction: Successfully saved {self.stats.unique} transactions")
            
        except Exception as e:
            logger.error(f"Transaction: Error saving transaction store: {str(e)}")
            self._cleanup_temp_files()
            raise
