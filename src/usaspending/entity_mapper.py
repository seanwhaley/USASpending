"""Entity data mapping and conversion functionality."""
from typing import Dict, Any, Optional, List, Set
import logging
from .utils import TypeConverter

logger = logging.getLogger(__name__)

class EntityMapper:
    """Handles entity data mapping and type conversion."""

    def __init__(self, config: Dict[str, Any], entity_type: str):
        """Initialize entity mapper.
        
        Args:
            config: Configuration dictionary
            entity_type: Type of entity being mapped
        """
        self.config = config
        self.entity_type = entity_type
        self.entity_config = (config.get('contracts', {})
                            .get('entity_separation', {})
                            .get('entities', {})
                            .get(entity_type, {}))
        self.type_converter = TypeConverter(config)
        
    def _get_field_mappings(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get field mappings from config for the current entity type.
        
        Args:
            category: Optional category of fields to get (e.g. 'date_fields', 'value_fields')
            
        Returns:
            Dictionary of field mappings
        """
        if not self.entity_config:
            return {}
            
        mappings = self.entity_config.get("field_mappings", {})
        
        if category:
            # For specific categories, look in the type_conversion section
            type_mappings = self.config.get('type_conversion', {}).get(category, {})
            return {k: v for k, v in mappings.items() if k in type_mappings}
            
        return mappings

    def extract_entity_data(self, row_data: Dict[str, Any], stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entity data from row data."""
        if not isinstance(row_data, dict) or not row_data:
            stats.setdefault("skipped", {}).setdefault("invalid_input", 0)
            stats["skipped"]["invalid_input"] += 1
            return None
            
        # Special case: Handle hierarchical agencies
        if self.entity_type == "agency":
            return self._extract_agency_data(row_data, stats)
            
        # Handle contracts
        if self.entity_type == "contract":
            return self._extract_contract_data(row_data, stats)
            
        # Handle transactions
        if self.entity_type == "transaction":
            return self._extract_transaction_data(row_data, stats)

        # Standard entity extraction for other types
        return self._extract_standard_entity_data(row_data, stats)

    def _extract_agency_data(self, row_data: Dict[str, Any], stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract hierarchical agency data."""
        if not row_data:
            return None
            
        agency_data: Dict[str, Dict[str, Any]] = {}
        agency_mappings = self._get_field_mappings()
        
        # Extract data for each agency level using config
        if 'agency' in agency_mappings:
            for role_mappings in agency_mappings['agency'].values():
                for level, fields in role_mappings.items():
                    code_field = fields.get('code')
                    name_field = fields.get('name')
                    
                    if isinstance(code_field, list):
                        for field in code_field:
                            if field in row_data and row_data[field]:
                                level_data = {
                                    'code': self._process_field_value(row_data[field], 'code'),
                                    'name': None
                                }
                                
                                # Try to find matching name field
                                if isinstance(name_field, list):
                                    name_idx = code_field.index(field)
                                    if name_idx < len(name_field):
                                        name_val = row_data.get(name_field[name_idx])
                                        if name_val:
                                            level_data['name'] = self._process_field_value(name_val, 'name')
                                
                                agency_data.setdefault(level, {}).update(level_data)

        if not agency_data:
            stats.setdefault("skipped", {}).setdefault("no_relevant_data", 0)
            stats["skipped"]["no_relevant_data"] += 1
            return None
            
        return agency_data

    def _extract_contract_data(self, row_data: Dict[str, Any], stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract contract entity data."""
        contract_data = {}
        
        # First ensure we have or can construct a unique key
        if "contract_award_unique_key" in row_data:
            contract_data["id"] = row_data["contract_award_unique_key"]
            contract_data["piid"] = row_data.get("award_id_piid", "")
        elif all(k in row_data for k in ["award_id_piid", "awarding_agency_code"]):
            contract_data["id"] = f"CONT_AWD_{row_data['award_id_piid']}_{row_data['awarding_agency_code']}"
            contract_data["piid"] = row_data["award_id_piid"]
        else:
            stats.setdefault("skipped", {}).setdefault("missing_key_fields", 0)
            stats["skipped"]["missing_key_fields"] += 1
            return None

        # Map fields using config
        for category in ['date_fields', 'value_fields']:
            mappings = self._get_field_mappings(category)
            for target, source in mappings.items():
                if isinstance(source, (list, tuple)):
                    for src in source:
                        if src in row_data and row_data[src]:
                            contract_data[target] = self._process_field_value(row_data[src], target)
                            break
                elif source in row_data and row_data[source]:
                    contract_data[target] = self._process_field_value(row_data[source], target)

        # Map remaining fields
        for target_field, source_field in self._get_field_mappings().items():
            if target_field not in contract_data:
                source_fields = [source_field] if isinstance(source_field, str) else source_field
                for src in source_fields:
                    if src in row_data and row_data[src]:
                        contract_data[target_field] = self._process_field_value(row_data[src], target_field)
                        break

        if contract_data:
            return contract_data

        stats.setdefault("skipped", {}).setdefault("no_relevant_data", 0)
        stats["skipped"]["no_relevant_data"] += 1
        return None

    def _extract_transaction_data(self, row_data: Dict[str, Any], stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction entity data."""
        transaction_data = {}
        
        # Build transaction key
        if "contract_transaction_unique_key" in row_data:
            transaction_data["transaction_key"] = row_data["contract_transaction_unique_key"]
        elif all(k in row_data for k in ["award_id_piid", "modification_number", "awarding_agency_code"]):
            base_key = f"CONT_AWD_{row_data['award_id_piid']}_{row_data['awarding_agency_code']}"
            transaction_data["transaction_key"] = f"{base_key}_MOD_{row_data['modification_number']}"
        else:
            stats.setdefault("skipped", {}).setdefault("missing_key_fields", 0)
            stats["skipped"]["missing_key_fields"] += 1
            return None

        # Map fields using config
        for category in ['date_fields', 'value_fields']:
            mappings = self._get_field_mappings(category)
            for target, source in mappings.items():
                if isinstance(source, (list, tuple)):
                    for src in source:
                        if src in row_data and row_data[src]:
                            transaction_data[target] = self._process_field_value(row_data[src], target)
                            break
                elif source in row_data and row_data[source]:
                    transaction_data[target] = self._process_field_value(row_data[source], target)

        # Map remaining fields
        for target_field, source_field in self._get_field_mappings().items():
            if target_field not in transaction_data:
                source_fields = [source_field] if isinstance(source_field, str) else source_field
                for src in source_fields:
                    if src in row_data and row_data[src]:
                        transaction_data[target_field] = self._process_field_value(row_data[src], target_field)
                        break

        if transaction_data:
            return transaction_data

        stats.setdefault("skipped", {}).setdefault("no_relevant_data", 0)
        stats["skipped"]["no_relevant_data"] += 1
        return None

    def _extract_standard_entity_data(self, row_data: Dict[str, Any], stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract standard entity data."""
        entity_result: Dict[str, Any] = {}
        
        # Apply field mappings from config
        field_mappings = self._get_field_mappings()
        for target_field, source_fields in field_mappings.items():
            source_field_list = [source_fields] if isinstance(source_fields, str) else source_fields
            
            for source_field in source_field_list:
                if source_field in row_data and row_data[source_field]:
                    entity_result[target_field] = self._process_field_value(
                        row_data[source_field],
                        target_field
                    )
                    break

        # Process entity references
        if self.entity_config.get("entity_references"):
            self._extract_entity_references(row_data, entity_result)
                
        if not entity_result:
            stats.setdefault("skipped", {}).setdefault("no_relevant_data", 0)
            stats["skipped"]["no_relevant_data"] += 1
            return None
            
        return entity_result
                
    def _extract_entity_references(self, row_data: Dict[str, Any], entity_result: Dict[str, Any]) -> None:
        """Extract entity references."""
        refs = self.entity_config.get("entity_references", {})
        
        for ref_type, ref_config in refs.items():
            ref_data = {}
            
            # Extract all specified fields with their processors
            for field in ref_config["fields"]:
                if field in row_data and row_data[field]:
                    value = row_data[field]
                    if "field_processors" in ref_config:
                        processor = ref_config["field_processors"].get(field)
                        if processor:
                            value = self._process_field_value(value, field)
                    ref_data[field] = value
                    
            # Add reference if any data was found
            if ref_data:
                entity_result[ref_type] = ref_data
                
    def _process_field_value(self, value: Any, field_name: str) -> Any:
        """Process field value with type conversion."""
        return self.type_converter.convert_value(value, field_name)