"""Entity store implementation."""
from typing import Dict, Any, Optional, Union, Set, DefaultDict, TypeVar, List, Callable, cast
from collections import defaultdict
import os
import json
import logging
from datetime import datetime
from pathlib import Path

from .base_entity_store import BaseEntityStore 
from .types import EntityData, EntityStats
from .utils import generate_entity_key, TypeConverter

logger = logging.getLogger(__name__)

# Add TypeVar for generic types
K = TypeVar('K', bound=str)
V = TypeVar('V', bound=Any)

class EntityStore(BaseEntityStore):
    """Basic entity store implementation with simplified processing."""

    # Valid relationship types by entity type
    VALID_RELATIONSHIPS = {
        'transaction': {'MODIFIES', 'MODIFIED_BY', 'REFERENCES'},
        'contract': {'CHILD_OF', 'PARENT_OF', 'AWARDED_TO', 'AWARDED_BY', 'PERFORMED_AT'},
        'recipient': {'HAS_SUBSIDIARY', 'SUBSIDIARY_OF', 'LOCATED_AT'},
        'agency': {'HAS_SUBAGENCY', 'BELONGS_TO_AGENCY', 'HAS_OFFICE', 'BELONGS_TO_SUBAGENCY', 'LOCATED_AT'},
        'location': {'CONTAINS', 'PART_OF'},
        'solicitation': {'DEFINES', 'RECEIVES', 'RESULTS_IN'}
    }
    
    # Track cycle prevention statistics
    _cycle_counts: Dict[str, int] = {}  
    # Cache cycle detection results with proper nesting
    _cycle_cache: DefaultDict[str, DefaultDict[str, bool]] = defaultdict(lambda: defaultdict(bool))

    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        """Initialize entity store with validation."""
        # Initialize base class first
        super().__init__()
        
        # Set base attributes
        self.base_path = base_path
        self.entity_type = entity_type
        self.config = config
        self.file_path = f"{base_path}_{entity_type}.json"
        self.temp_file_path = f"{self.file_path}.tmp"
        
        # Initialize validation engine
        from .validation import ValidationEngine
        self.validation_engine = ValidationEngine(config)
        
        # Initialize type converter for field processing
        self.type_converter = TypeConverter(config)
        
        # Get entity config from main config
        self.entity_config = (config.get('contracts', {})
                            .get('entity_separation', {})
                            .get('entities', {})
                            .get(entity_type, {}))
        
        # Initialize file partitioning settings
        self.max_file_size = config.get('global', {}).get('max_file_size_mb', 50) * 1024 * 1024  # Convert to bytes
        self.current_part = 1
        self.current_file_size = 0
        
        # Initialize and validate configuration
        self._validate_entity_config(self.entity_config)
        self._validate_field_mappings()
        self._validate_relationships_structure()
        self._validate_entity_references()
            
        # Now initialize data structures
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.relationships: DefaultDict[str, DefaultDict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self.stats = EntityStats()
        self.pending_parents: Dict[str, Dict[str, Any]] = {}

    def _validate_base_config(self, config: Dict[str, Any]) -> None:
        """Validate basic configuration structure."""
        required_sections = ['contracts', 'global']
        for section in required_sections:
            if (section not in config):
                raise ValueError(f"Missing required config section: {section}")
        
        if 'contracts' in config:
            if not isinstance(config['contracts'], dict):
                raise ValueError("Contracts section must be a dictionary")
                
            if 'entity_separation' not in config['contracts']:
                raise ValueError("Missing entity_separation in contracts config")

    def _initialize_entity_config(self) -> Dict[str, Any]:
        """Initialize and validate entity configuration."""
        try:
            # Get entity config from configuration
            if (
                'contracts' in self.config 
                and 'entity_separation' in self.config['contracts']
                and 'entities' in self.config['contracts']['entity_separation']
                and self.entity_type in self.config['contracts']['entity_separation']['entities']
            ):
                entity_config = cast(Dict[str, Any], 
                    self.config['contracts']['entity_separation']['entities'][self.entity_type])
                self._validate_entity_config(entity_config)
                return entity_config
            else:
                logger.warning(f"No configuration found for entity type: {self.entity_type}")
                return {}
                
        except Exception as e:
            logger.error(f"Error initializing entity config: {str(e)}")
            return {}

    def _validate_relationships_structure(self) -> None:
        """Pre-validate relationships structure."""
        if not self.entity_config:
            return
            
        relationships = self.entity_config.get('relationships', {})
        if not isinstance(relationships, dict):
            raise ValueError(f"Invalid relationships format for {self.entity_type}")
        
        for rel_type, rel_configs in relationships.items():
            if not isinstance(rel_configs, list):
                raise ValueError(f"Relationship configurations for {self.entity_type}.{rel_type} must be a list")
            for rel_config in rel_configs:
                self._validate_relationship_config(rel_type, rel_config)

    def _validate_relationship_config(self, rel_type: Optional[str], rel_config: Dict[str, Any]) -> None:
        """Validate a single relationship configuration."""
        # For hierarchical relationships
        if rel_type == 'hierarchical':
            required = ['from_level', 'to_level', 'type']
        else:
            required = ['from_field', 'to_field', 'type']
        
        missing = [field for field in required if field not in rel_config]
        if missing:
            context = f"{self.entity_type}.{rel_type}" if rel_type else self.entity_type
            raise ValueError(f"Relationship in {context} missing {', '.join(missing)} fields")

    def _validate_field_mappings(self) -> None:
        """Pre-validate field mapping structures."""
        if not self.entity_config:
            return
            
        # Validate top-level field mappings
        field_mappings = self.entity_config.get('field_mappings', {})
        if not isinstance(field_mappings, dict):
            raise ValueError("Field mappings must be a dictionary")
        
        # Validate each field mapping is either a string or list of strings
        for target, source in field_mappings.items():
            if not isinstance(target, str):
                raise ValueError(f"Field mapping target '{target}' must be a string")
            if isinstance(source, str):
                continue
            if isinstance(source, (list, tuple)):
                if not all(isinstance(s, str) for s in source):
                    raise ValueError(f"All source fields for target '{target}' must be strings")
            else:
                raise ValueError(f"Field mapping for '{target}' must be a string or list of strings")
            
        # Validate hierarchical level field mappings
        levels = self.entity_config.get('levels', {})
        if not isinstance(levels, dict):
            raise ValueError("Levels configuration must be a dictionary")
            
        for level, config in levels.items():
            if not isinstance(config, dict):
                raise ValueError(f"Invalid config for level: {level}")
                
            level_mappings = config.get('field_mappings', {})
            if not isinstance(level_mappings, dict):
                raise ValueError(f"Invalid field mappings for level: {level}")
                
            # Validate each level's field mappings
            for target, source in level_mappings.items():
                if not isinstance(target, str):
                    raise ValueError(f"Field mapping target '{target}' in level '{level}' must be a string")
                if isinstance(source, str):
                    continue
                if isinstance(source, (list, tuple)):
                    if not all(isinstance(s, str) for s in source):
                        raise ValueError(f"All source fields for target '{target}' in level '{level}' must be strings")
                else:
                    raise ValueError(f"Field mapping for '{target}' in level '{level}' must be a string or list of strings")
            
            # Validate key fields are present and valid
            key_fields = config.get('key_fields', [])
            if not isinstance(key_fields, (list, tuple)):
                raise ValueError(f"key_fields for level '{level}' must be a list")
            if not all(isinstance(k, str) for k in key_fields):
                raise ValueError(f"All key fields for level '{level}' must be strings")
            
            # Validate all key fields have corresponding mappings
            missing_mappings = [k for k in key_fields if k not in level_mappings]
            if missing_mappings:
                raise ValueError(f"Key fields {missing_mappings} in level '{level}' missing from field_mappings")

    def _validate_entity_data(self, entity_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]: 
        """Validate entity data structure with YAML rules."""
        if not isinstance(entity_data, dict) or not entity_data:
            return None

        # First do core validation based on entity type
        if self.entity_type == "recipient":
            if 'uei' not in entity_data:
                return None
        elif self.entity_type == "agency":
            if not any(k in entity_data for k in ["agency", "subagency", "office"]):
                return None

        # Now do YAML-based validation
        validation_results = self.validation_engine.validate_entity(
            self.entity_type, 
            entity_data,
            context=entity_data  # Pass full entity data as context for cross-field validation
        )

        # Log validation failures but don't reject data unless critical
        for result in validation_results:
            if not result.valid:
                logger.warning(f"Validation warning for {self.entity_type}: {result.message}")

        # Special handling for business characteristics if recipient
        if self.entity_type == "recipient":
            characteristic_results = self.validation_engine.validate_business_characteristics(entity_data)
            for result in characteristic_results:
                if not result.valid:
                    logger.warning(f"Business characteristic validation warning: {result.message}")

        return entity_data

    def add_relationship(self, from_key: str, rel_type: str, to_key: str, inverse_type: Optional[str] = None) -> None:
        """Add a relationship between entities with optional inverse."""
        if not from_key or not to_key or not rel_type:
            return
            
        if from_key != to_key:  # Prevent self-relationships
            self.relationships[rel_type][from_key].add(to_key)
            self.stats.relationships[rel_type] += 1
            
            if inverse_type:
                self.relationships[inverse_type][to_key].add(from_key)
                self.stats.relationships[inverse_type] += 1

    def validate_relationship_types(self, relationship_types: Set[str]) -> List[str]:
        """Validate relationship types against allowed types."""
        if self.entity_type not in self.VALID_RELATIONSHIPS:
            return list(relationship_types)  # All invalid if entity type not recognized
            
        allowed_types = self.VALID_RELATIONSHIPS[self.entity_type]
        return [rel_type for rel_type in relationship_types if rel_type not in allowed_types]

    def get_related_entities(self, entity_key: str, rel_type: str) -> Set[str]:
        """Get entities related to the given entity by relationship type."""
        if rel_type not in self.relationships:
            return set()
            
        return self.relationships[rel_type].get(entity_key, set()).copy()

    def add_parent_child_relationship(self, child_key: str, parent_key: str, parent_data: Optional[Dict[str, Any]] = None) -> None:
        """Add a parent-child relationship with cycle prevention."""
        if not child_key or not parent_key:
            raise ValueError("Both child and parent keys are required")
        if child_key == parent_key:
            raise ValueError("Child and parent keys cannot be the same")

        # Check for cycles
        if self._would_create_cycle(child_key, parent_key):
            logger.warning(f"Preventing cycle in parent-child relationship: {child_key} -> {parent_key}")
            return

        # Create parent placeholder if needed
        if parent_key not in self.cache:
            if parent_data:
                self.cache[parent_key] = parent_data.copy()
                if "subsidiaries" not in self.cache[parent_key]:
                    self.cache[parent_key]["subsidiaries"] = []
            else:
                self.cache[parent_key] = {"subsidiaries": []}
            self.stats.unique += 1
        elif "subsidiaries" not in self.cache[parent_key]:
            self.cache[parent_key]["subsidiaries"] = []

        # Add child to parent's subsidiaries if not already there
        subsidiaries = self.cache[parent_key]["subsidiaries"]
        if not isinstance(subsidiaries, list):
            subsidiaries = []
            self.cache[parent_key]["subsidiaries"] = subsidiaries

        if child_key not in subsidiaries:
            subsidiaries.append(child_key)

        # Add relationship
        self.add_relationship(parent_key, "HAS_SUBSIDIARY", child_key)
        self.add_relationship(child_key, "SUBSIDIARY_OF", parent_key)

    def _would_create_cycle(self, child_key: str, parent_key: str, visited: Optional[Set[str]] = None) -> bool:
        """Check if adding a parent-child relationship would create a cycle."""
        # Initialize visited set if not provided
        if visited is None:
            visited = set()
        
        # Base case 1: If child is same as parent, it's a direct cycle
        if child_key == parent_key:
            return True
            
        # Base case 2: If we've seen this child before, we have a cycle
        if child_key in visited:
            return True
            
        # Add the child to visited set
        visited.add(child_key)
        
        # Get the current ancestor chain length
        chain_length = len(visited)
        
        # If chain gets too long, assume it's not a cycle to prevent false positives
        if chain_length > 10:  # Reasonable maximum depth for most hierarchies
            return False
        
        # Cache common cycle pairs to avoid redundant checks
        cycle_key = f"{child_key} -> {parent_key}"
        
        # Check cache first
        if cycle_key in self._cycle_cache and parent_key in self._cycle_cache[cycle_key]:
            return bool(self._cycle_cache[cycle_key][parent_key])
        
        # Track stats less frequently to reduce noise
        if cycle_key not in self._cycle_counts:
            self._cycle_counts[cycle_key] = 0
        self._cycle_counts[cycle_key] += 1
        
        # Only log first occurrence and then at larger intervals
        if self._cycle_counts[cycle_key] == 1 or self._cycle_counts[cycle_key] % 1000 == 0:
            logger.warning(f"Checking cycle in parent-child relationship: {child_key} -> {parent_key} (occurred {self._cycle_counts[cycle_key]} times)")
        
        # Check if proposed parent has this entity as an ancestor
        current = self.cache.get(parent_key)
        if not current:
            self._cycle_cache[cycle_key][parent_key] = False
            return False
        
        # Check relationship types that could form cycles
        cycle_forming_relations = {"SUBSIDIARY_OF", "BELONGS_TO", "PARENT_OF", "CHILD_OF"}
        
        # Check only relationships that could form cycles
        is_cycle = False
        for rel_type in cycle_forming_relations:
            if rel_type in self.relationships:
                for ancestor_key in self.relationships[rel_type].get(parent_key, set()):
                    if self._would_create_cycle(child_key, ancestor_key, visited.copy()):
                        is_cycle = True
                        break
                if is_cycle:
                    break
                    
        # Cache the result
        self._cycle_cache[cycle_key][parent_key] = is_cycle
        return is_cycle

    def add_entity_and_get_refs(self, entity_data: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """Add entity and return reference mapping."""
        refs: Dict[str, str] = {}
        entity_key = self.add_entity(entity_data)
        
        if not entity_key:
            return refs

        # Handle hierarchical agencies
        if self.entity_type == 'agency' and isinstance(entity_key, dict):
            for level, key in entity_key.items():
                if level == 'office' and key and entity_data:
                    # Add office reference with role based on data context
                    if entity_data.get('is_awarding'):
                        refs['awarding_office_ref'] = key
                    if entity_data.get('is_funding'):
                        refs['funding_office_ref'] = key
                else:
                    # Add reference for agency and subagency levels
                    refs[f"{self.entity_type}_{level}_ref"] = key
        
        # Handle recipients
        elif self.entity_type == 'recipient' and isinstance(entity_key, str):
            refs['recipient_ref'] = entity_key
            
        # Handle transactions
        elif self.entity_type == 'transaction' and isinstance(entity_key, str):
            refs['transaction_ref'] = entity_key
            
        # Generic entity handling
        elif isinstance(entity_key, dict):
            for level, key in entity_key.items():
                if key:
                    refs[f"{self.entity_type}_{level}_ref"] = key
        elif entity_key:
            refs[f"{self.entity_type}_ref"] = entity_key
            
        return refs

    def process_relationships(self, entity_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        """Process all entity relationships."""
        if not entity_data or not isinstance(entity_data, dict):
            return
            
        if context is None:
            context = {}
            
        # Skip if no relationship config
        if not self.entity_config or 'relationships' not in self.entity_config:
            return
            
        relationships = self.entity_config['relationships']
        
        # Process flat relationships
        if 'flat' in relationships:
            self._process_flat_relationships(entity_data, context, relationships['flat'])
            
        # Process hierarchical relationships
        if 'hierarchical' in relationships and isinstance(entity_data, dict):
            self._process_hierarchical_relationships(entity_data, relationships['hierarchical'])

    def _process_flat_relationships(self,
                                  entity_data: Dict[str, Any],
                                  context: Dict[str, Any],
                                  relationships: List[Dict[str, Any]]) -> None:
        """Process flat (direct) relationships between entities."""
        if not relationships:
            return
            
        # Config validation ensures all required fields exist and are strings
        for rel_config in relationships:
            from_key = str(entity_data.get(rel_config['from_field'], context.get('key', '')))
            to_key = str(entity_data.get(rel_config['to_field'], ''))
            
            if from_key and to_key and from_key != to_key:
                self.add_relationship(from_key, rel_config['type'], to_key)
                if 'inverse' in rel_config:
                    self.add_relationship(to_key, rel_config['inverse'], from_key)

    def _process_hierarchical_relationships(self, entity_data: Dict[str, Any], level_keys: Dict[str, str]) -> None:
        """Process relationships between hierarchical entity levels.
        
        Args:
            entity_data: Entity data for each level
            level_keys: Keys generated for each level
        """
        if not self.entity_config or 'relationships' not in self.entity_config:
            return
            
        # Config validation ensures this exists and has correct structure
        hierarchical = self.entity_config['relationships'].get('hierarchical', [])
        
        # Process each relationship
        for rel in hierarchical:
            from_level = rel['from_level']
            to_level = rel['to_level']
            
            # Get keys for the levels
            from_key = level_keys.get(from_level)
            to_key = level_keys.get(to_level)
            
            # Add relationships if both keys exist and are different
            if from_key and to_key and from_key != to_key:
                self.add_relationship(from_key, rel['type'], to_key)
                if 'inverse' in rel:
                    self.add_relationship(to_key, rel['inverse'], from_key)

    def _cleanup_temp_files(self) -> None:
        """Clean up any temporary files."""
        try:
            if os.path.exists(self.temp_file_path):
                os.remove(self.temp_file_path)
        except Exception as e:
            logger.warning(f"Error cleaning up temp file: {str(e)}")

    def get_encoding(self) -> str:
        """Get file encoding from config."""
        encoding = self.config.get('global', {}).get('encoding')
        if not encoding:
            return 'utf-8'
        return str(encoding)  # Ensure string type

    def _validate_entity_config(self, config: Dict[str, Any]) -> None:
        """Validate entity configuration."""
        if not config:
            return  # Empty config is valid, will use defaults
            
        # Validate levels if present
        if 'levels' in config:
            if not isinstance(config['levels'], dict):
                raise ValueError(f"Invalid 'levels' configuration for {self.entity_type}")
                
            for level, level_config in config['levels'].items():
                if not isinstance(level_config, dict):
                    raise ValueError(f"Invalid level configuration for {level}")
                if 'field_mappings' not in level_config:
                    raise ValueError(f"Missing field_mappings for {level}")
                if 'key_fields' not in level_config:
                    raise ValueError(f"Missing key_fields for {level}")
                    
        # Validate key_fields if present at root level
        if 'key_fields' in config:
            if not isinstance(config['key_fields'], (list, tuple)):
                raise ValueError("key_fields must be a list")
            if not all(isinstance(k, str) for k in config['key_fields']):
                raise ValueError("All key fields must be strings")
                
            # Check key fields have mappings if field_mappings exists
            if 'field_mappings' in config:
                missing_keys: Set[str] = set()
                for key in config['key_fields']:
                    if key not in config['field_mappings']:
                        missing_keys.add(key)
                if missing_keys:
                    raise ValueError(f"Key fields missing from field_mappings: {', '.join(missing_keys)}")
                    
        # Validate that either levels or key_fields is present
        if 'levels' not in config and 'key_fields' not in config:
            raise ValueError(f"Entity type {self.entity_type} requires either levels or key_fields configuration")
                    
        # Validate relationships if present
        if 'relationships' in config:
            if not isinstance(config['relationships'], dict):
                raise ValueError(f"Invalid relationships format for {self.entity_type}")
            self._validate_relationships_structure()

    def _validate_entity_references(self) -> None:
        """Validate entity reference configuration at initialization."""
        if not self.entity_config:
            return
            
        refs = self.entity_config.get("entity_references", {})
        if not isinstance(refs, dict):
            raise ValueError("Entity references configuration must be a dictionary")
            
        for ref_type, ref_config in refs.items():
            if not isinstance(ref_type, str):
                raise ValueError(f"Entity reference type must be a string: {ref_type}")
            if not isinstance(ref_config, dict):
                raise ValueError(f"Configuration for reference '{ref_type}' must be a dictionary")
            
            # Validate fields list
            fields = ref_config.get("fields", [])
            if not isinstance(fields, (list, tuple)):
                raise ValueError(f"Fields for reference '{ref_type}' must be a list")
            if not all(isinstance(f, str) for f in fields):
                raise ValueError(f"All fields in reference '{ref_type}' must be strings")
                
            # Validate field processors if present
            if "field_processors" in ref_config:
                procs = ref_config["field_processors"]
                if not isinstance(procs, dict):
                    raise ValueError(f"Field processors for reference '{ref_type}' must be a dictionary")
                valid_processors = {"boolean", "int", "float", "date"}
                for field, proc in procs.items():
                    if not isinstance(field, str):
                        raise ValueError(f"Field name in processors for '{ref_type}' must be a string")
                    if proc not in valid_processors:
                        raise ValueError(f"Invalid processor '{proc}' for field '{field}' in reference '{ref_type}'. Valid processors: {', '.join(valid_processors)}")

    def extract_entity_data(self, row_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entity data with improved contract and transaction handling."""
        if not isinstance(row_data, dict) or not row_data:
            self.stats.skipped["invalid_input"] += 1
            return None
            
        # Special case: Handle hierarchical agencies
        if self.entity_type == "agency":
            return self._extract_agency_data(row_data)
            
        # Handle contracts
        if self.entity_type == "contract":
            contract_data = {}
            field_mappings = self.entity_config.get("field_mappings", {})
            
            # First ensure we have or can construct a unique key
            if "contract_award_unique_key" in row_data:
                contract_data["id"] = row_data["contract_award_unique_key"]
                contract_data["piid"] = row_data.get("award_id_piid", "")
            elif all(k in row_data for k in ["award_id_piid", "awarding_agency_code"]):
                contract_data["id"] = f"CONT_AWD_{row_data['award_id_piid']}_{row_data['awarding_agency_code']}"
                contract_data["piid"] = row_data["award_id_piid"]
            else:
                self.stats.skipped["missing_key_fields"] += 1
                return None
            
            # Add core contract fields with proper field names
            core_fields = {
                "current_value": "base_and_exercised_options_value",  # Fixed field name
                "potential_value": "base_and_all_options_value",
                "total_obligation": "total_dollars_obligated",
                "type": "contract_award_type",  # Fixed name to match CSV
                "type_code": "contract_award_type_code",
                "description": "award_description"
            }
            
            for target, source in core_fields.items():
                if source in row_data and row_data[source]:
                    contract_data[target] = self._process_field_value(row_data[source], target)
            
            # Add date fields
            date_fields = {
                "performance_start": "period_of_performance_start_date",
                "performance_end": "period_of_performance_current_end_date",
                "potential_end": "period_of_performance_potential_end_date"
            }
            
            for target, source in date_fields.items():
                if source in row_data and row_data[source]:
                    contract_data[target] = self._process_field_value(row_data[source], target)
            
            # Add reference fields for relationships
            reference_fields = {
                "recipient_ref": "recipient_uei",
                "awarding_agency_ref": "awarding_agency_code",
                "funding_agency_ref": "funding_agency_code"
            }
            
            for target, source in reference_fields.items():
                if source in row_data and row_data[source]:
                    contract_data[target] = row_data[source]
            
            # Map remaining custom fields from config
            for target_field, source_field in field_mappings.items():
                if target_field not in contract_data:  # Don't override core fields
                    source_fields = [source_field] if isinstance(source_field, str) else source_field
                    for src in source_fields:
                        if src in row_data and row_data[src]:
                            contract_data[target_field] = self._process_field_value(
                                row_data[src],
                                target_field
                            )
                            break
            
            if contract_data:
                return contract_data
            
            self.stats.skipped["no_relevant_data"] += 1
            return None

        # Handle transactions
        if self.entity_type == "transaction":
            transaction_data = {}
            field_mappings = self.entity_config.get("field_mappings", {})
            
            # Ensure we have a unique transaction key
            if "contract_transaction_unique_key" in row_data:
                transaction_data["transaction_key"] = row_data["contract_transaction_unique_key"]
            else:
                # Try to construct from modification number if available
                if all(k in row_data for k in ["award_id_piid", "modification_number", "awarding_agency_code"]):
                    base_key = f"CONT_AWD_{row_data['award_id_piid']}_{row_data['awarding_agency_code']}"
                    transaction_data["transaction_key"] = f"{base_key}_MOD_{row_data['modification_number']}"
                else:
                    self.stats.skipped["missing_key_fields"] += 1
                    return None
            
            # Map remaining transaction fields
            for target_field, source_field in field_mappings.items():
                source_fields = [source_field] if isinstance(source_field, str) else source_field
                
                for src in source_fields:
                    if src in row_data and row_data[src]:
                        transaction_data[target_field] = self._process_field_value(
                            row_data[src],
                            target_field
                        )
                        break
                        
            if transaction_data:
                return transaction_data
                
            self.stats.skipped["no_relevant_data"] += 1
            return None
            
        # Standard entity extraction for other types
        entity_result: Dict[str, Any] = {}
        
        # Apply field mappings from config
        if self.entity_config and "field_mappings" in self.entity_config:
            field_mappings = self.entity_config["field_mappings"]
            for target_field, source_fields in field_mappings.items():
                source_field_list = [source_fields] if isinstance(source_fields, str) else source_fields
                
                for source_field in source_field_list:
                    if source_field in row_data and row_data[source_field]:
                        entity_result[target_field] = self._process_field_value(
                            row_data[source_field],
                            target_field
                        )
                        break
        
        # Process recipient-specific fields
        if self.entity_type == "recipient" and "recipient_uei" in row_data:
            entity_result["uei"] = row_data["recipient_uei"]
            if "recipient_parent_uei" in row_data and row_data["recipient_parent_uei"]:
                entity_result["parent_uei"] = row_data["recipient_parent_uei"]
                
        # Process entity references
        if self.entity_config.get("entity_references"):
            self._extract_entity_references(row_data, entity_result)
                
        if not entity_result:
            self.stats.skipped["no_relevant_data"] += 1
            return None
            
        return entity_result

    def _process_field_value(self, value: Any, field_name: str) -> Any:
        """Process field value with type conversion.
        
        Args:
            value: Raw field value
            field_name: Name of field being processed
            
        Returns:
            Processed field value
        """
        return self.type_converter.convert_value(value, field_name)
        
    def _extract_entity_references(self, row_data: Dict[str, Any], entity_result: Dict[str, Any]) -> None:
        """Extract references to other entities.
        
        Args:
            row_data: Raw CSV record
            entity_result: Entity data being built
        """
        # Config validation ensures this is a dict with correct structure
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

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[Union[str, Dict[str, str]]]:
        """Add an entity to the store with streamlined processing."""
        if not entity_data:
            self.stats.skipped["invalid_data"] += 1
            logger.debug(f"{self.entity_type}: Skipping invalid entity data")
            return None

        self.stats.total += 1
        
        # Add detailed logging for entity processing
        logger.debug(f"{self.entity_type}: Processing entity with data keys: {list(entity_data.keys())}")
        
        # Handle hierarchical agencies
        if (self.entity_type == "agency" and 
            isinstance(entity_data, dict) and 
            any(k in ["agency", "subagency", "office"] for k in entity_data)):
            
            result = self.process_hierarchical_entity(entity_data)
            if result:
                level_keys: Dict[str, str] = {}
                for level, level_data in result.items():
                    key = self._get_level_key(level, level_data)
                    logger.debug(f"{self.entity_type}: Generated key for {level}: {key}")
                    if key:
                        level_keys[level] = key
                        if key not in self.cache:
                            self.cache[key] = level_data
                            self.stats.unique += 1
                            logger.info(f"{self.entity_type}: Added new {level} entity with key {key}")
                
                # Process relationships if we found keys
                if len(level_keys) > 1:
                    self._process_hierarchical_relationships(entity_data, level_keys)
                    logger.debug(f"{self.entity_type}: Processed hierarchical relationships for keys: {level_keys}")
                
                return level_keys if level_keys else None
                
            return None

        # Generate entity key
        entity_key = self._generate_entity_key(entity_data)
        if not entity_key:
            self.stats.skipped["missing_key_fields"] += 1
            logger.debug(f"{self.entity_type}: Failed to generate key for entity")
            return None
            
        # Add or update entity in cache
        if entity_key not in self.cache:
            self.cache[entity_key] = entity_data
            self.stats.unique += 1
            logger.info(f"{self.entity_type}: Added new entity with key {entity_key}")
        else:
            self.cache[entity_key].update(entity_data)
            logger.debug(f"{self.entity_type}: Updated existing entity with key {entity_key}")
        
        # Process relationships with correct context
        self.process_relationships(entity_data, {"key": entity_key})
            
        # Handle recipient parent-child relationships
        if (self.entity_type == "recipient" and
            "parent_uei" in entity_data and
            entity_data["parent_uei"] and
            entity_data["parent_uei"] != entity_data.get("uei")):
            
            self.add_parent_child_relationship(
                entity_data["uei"], 
                entity_data["parent_uei"]
            )
            logger.debug(f"{self.entity_type}: Added parent-child relationship: {entity_data['uei']} -> {entity_data['parent_uei']}")
                
        return entity_key

    def save(self) -> None:
        """Save entities with atomic file operations and batched processing."""
        try:
            logger.info(f"Starting save for {self.entity_type} store with {len(self.cache)} entities")
            
            # Get output settings
            output_config = self.config.get('contracts', {}).get('output', {})
            indent = output_config.get('indent', 2)
            encoding = self.get_encoding()

            # Prepare base metadata
            base_metadata = {
                "entity_type": self.entity_type,
                "total_references": self.stats.total,
                "unique_entities": self.stats.unique,
                "relationship_counts": dict(self.stats.relationships),
                "skipped_entities": dict(self.stats.skipped),
                "natural_keys_used": self.stats.natural_keys_used,
                "hash_keys_used": self.stats.hash_keys_used,
                "generated_date": datetime.now().isoformat()
            }
            
            # Create directory if needed
            output_dir = os.path.dirname(self.file_path)
            if not os.path.exists(output_dir):
                logger.info(f"Creating output directory: {output_dir}")
                os.makedirs(output_dir, exist_ok=True)

            # Estimate size and determine save strategy
            estimated_size = self._estimate_json_size()
            logger.info(f"Estimated output size: {estimated_size/(1024*1024):.2f}MB")
            
            if len(self.cache) > 10000 or estimated_size > self.max_file_size:
                logger.info("Using partitioned save strategy")
                self._save_partitioned(base_metadata, indent, encoding)
            else:
                logger.info("Using single file save strategy")
                self._save_single_file(base_metadata, indent, encoding)

            logger.info(f"Successfully saved {self.stats.unique} {self.entity_type} entities")

        except Exception as e:
            logger.error(f"Error saving entity store: {str(e)}", exc_info=True)
            self._cleanup_temp_files()
            raise

    def _estimate_json_size(self) -> int:
        """Estimate JSON output size in bytes."""
        # Sample a few entities to estimate average size
        sample_size = min(100, len(self.cache))
        if sample_size == 0:
            return 0
            
        sample_keys = list(self.cache.keys())[:sample_size]
        sample_data = {k: self.cache[k] for k in sample_keys}
        
        # Create sample output
        sample_output = {
            "metadata": {"sample": True},
            "entities": sample_data,
            "relationships": {k: {sk: list(v[sk]) for sk in list(v.keys())[:10]} 
                            for k, v in self.relationships.items()}
        }
        
        # Get sample size and extrapolate
        sample_json = json.dumps(sample_output)
        avg_entity_size = len(sample_json) / sample_size
        
        return int(avg_entity_size * len(self.cache))

    def _save_partitioned(self, base_metadata: Dict[str, Any], indent: int, encoding: str) -> None:
        """Save large datasets in partitioned files with an index."""
        try:
            base_path = self.file_path.rsplit('.', 1)[0]
            logger.info(f"Starting partitioned save to {base_path}")
            
            # Calculate partition size
            target_size = 25 * 1024 * 1024  # 25MB target size per partition
            sample_size = min(1000, len(self.cache))
            sample_keys = list(self.cache.keys())[:sample_size]
            sample_data = {k: self.cache[k] for k in sample_keys}
            sample_json = json.dumps({"entities": sample_data})
            avg_entity_size = len(sample_json) / sample_size
            partition_size = max(100, min(10000, int(target_size / avg_entity_size)))
            
            logger.info(f"Calculated partition size: {partition_size} entities")
            
            # Create and save partitions
            entities = list(self.cache.items())
            partition_count = (len(entities) + partition_size - 1) // partition_size
            
            # Prepare index data
            index_data: Dict[str, Any] = {
                "metadata": base_metadata,
                "partitions": [],
                "relationships": {}
            }
            
            # Create temporary directory for atomic operations
            temp_dir = Path(base_path).parent / ".tmp"
            temp_dir.mkdir(exist_ok=True)
            
            created_files = []
            try:
                for i in range(0, len(entities), partition_size):
                    partition_num = (i // partition_size) + 1
                    logger.info(f"Processing partition {partition_num}/{partition_count}")
                    
                    partition = dict(entities[i:i + partition_size])
                    partition_file = f"{base_path}_part{partition_num}.json"
                    temp_partition_file = temp_dir / f"part{partition_num}.json.tmp"
                    
                    # Save partition and get metadata
                    partition_meta = self._save_partition(str(temp_partition_file), partition, partition_num, indent, encoding)
                    index_data["partitions"].append(partition_meta)
                    
                    # Atomically rename temporary partition file
                    os.replace(temp_partition_file, partition_file)
                    created_files.append(partition_file)
                
                # Add relationship information to index
                for rel_type, rel_map in self.relationships.items():
                    # Convert relationship sets to lists for JSON serialization
                    index_data["relationships"][rel_type] = {
                        k: list(v) for k, v in rel_map.items()
                    }
                
                # Save index file atomically
                index_file = f"{base_path}_index.json"
                temp_index_file = temp_dir / "index.json.tmp"
                logger.info(f"Writing index file to {index_file}")
                
                with open(temp_index_file, 'w', encoding=encoding) as f:
                    json.dump(index_data, f, indent=indent, ensure_ascii=False)
                
                os.replace(temp_index_file, index_file)
                created_files.append(index_file)
                
                logger.info(f"Successfully saved {partition_count} partitions with index")
                
            except Exception as e:
                # Clean up any created files on error
                for file in created_files:
                    try:
                        if os.path.exists(file):
                            os.remove(file)
                    except Exception:
                        pass
                raise
            finally:
                # Clean up temporary directory
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
            
        except Exception as e:
            logger.error(f"Error in partitioned save: {str(e)}", exc_info=True)
            raise

    def _save_single_file(self, base_metadata: Dict[str, Any], indent: int, encoding: str) -> None:
        """Save all entities to a single file."""
        try:
            # Clean up any existing temp file first
            self._cleanup_temp_files()
            
            # Ensure target file is not locked/readonly if it exists
            if os.path.exists(self.file_path):
                try:
                    os.chmod(self.file_path, 0o666)
                except OSError:
                    pass  # Ignore permission errors, will handle during replace
            
            # Prepare output data
            output_data = {
                "metadata": base_metadata,
                "entities": self.cache,
                "relationships": {k: {sk: list(v[sk]) for sk in v.keys()} for k, v in self.relationships.items()}
            }
            
            # Write to temporary file first
            with open(self.temp_file_path, 'w', encoding=encoding) as f:
                json.dump(output_data, f, indent=indent, ensure_ascii=False)
            
            # Ensure temp file has right permissions
            try:
                os.chmod(self.temp_file_path, 0o666)
            except OSError:
                pass
                
            # Rename temp file to final file
            try:
                os.replace(self.temp_file_path, self.file_path)
            except OSError as e:
                # If replace fails, try removing target first
                try:
                    if os.path.exists(self.file_path):
                        os.remove(self.file_path)
                    os.rename(self.temp_file_path, self.file_path)
                except OSError:
                    raise e  # Re-raise original error if cleanup fails
            
        except Exception as e:
            logger.error(f"Error saving single file: {str(e)}", exc_info=True)
            self._cleanup_temp_files()
            raise

    def _save_partition(self, partition_file: str, partition: Dict[str, Dict[str, Any]], partition_num: int, indent: int, encoding: str) -> Dict[str, Any]:
        """Save a single partition to file."""
        try:
            # Prepare partition metadata
            partition_metadata = {
                "partition_number": partition_num,
                "entity_count": len(partition),
                "file_path": partition_file
            }
            
            # Write partition to file
            with open(partition_file, 'w', encoding=encoding) as f:
                json.dump({"entities": partition}, f, indent=indent, ensure_ascii=False)
            
            return partition_metadata
            
        except Exception as e:
            logger.error(f"Error saving partition {partition_num}: {str(e)}", exc_info=True)
            raise

    def _extract_agency_data(self, row_data: Dict[str, Any]) -> Optional[Dict[str, Any]]: 
        """Extract hierarchical agency data from a row."""
        if not row_data or not isinstance(row_data, dict):
            return None
            
        agency_data: Dict[str, Dict[str, Any]] = {}
        
        # Define the field patterns we'll look for
        field_patterns = {
            'agency': {
                'code': ['awarding_agency_code', 'funding_agency_code', 'parent_award_agency_id'],
                'name': ['awarding_agency_name', 'funding_agency_name', 'parent_award_agency_name']
            },
            'sub_agency': {
                'code': ['awarding_sub_agency_code', 'funding_sub_agency_code'],
                'name': ['awarding_sub_agency_name', 'funding_sub_agency_name']
            },
            'office': {
                'code': ['awarding_office_code', 'funding_office_code'],
                'name': ['awarding_office_name', 'funding_office_name']
            }
        }

        # Extract data for each level
        for level, fields in field_patterns.items():
            level_data = {}
            
            # Try each possible field name for code and name
            for field_type, possible_fields in fields.items():
                for field in possible_fields:
                    if field in row_data and row_data[field]:
                        level_data[field_type] = self._process_field_value(row_data[field], field_type)
                        # Capture the role from the field name
                        role = None
                        if 'awarding' in field:
                            role = 'awarding'
                        elif 'funding' in field:
                            role = 'funding'
                        elif 'parent_award' in field:
                            role = 'parent_award'
                        
                        if role:
                            level_data['roles'] = level_data.get('roles', set())
                            level_data['roles'].add(role)
                        break

            # Only add level if we found both code and name
            if 'code' in level_data and ('name' in level_data or 'parent_award' in next(iter(level_data.get('roles', [])), '')):
                level_data['level'] = level
                agency_data[level] = level_data

        if not agency_data:
            self.stats.skipped["no_relevant_data"] += 1
            return None
            
        return agency_data

    def _get_level_key(self, level: str, level_data: Dict[str, Any]) -> Optional[str]:
        """Generate a key for a hierarchical entity level."""
        if not level_data:
            return None
            
        level_config = self.entity_config.get('levels', {}).get(level)
        if not level_config:
            return None
            
        key_fields = level_config.get('key_fields', [])
        if not key_fields:
            return None
            
        # Get fields and values for key generation
        key_data = {}
        for field in key_fields:
            if field not in level_data:
                return None
            key_data[field] = level_data[field]
            
        # Generate key
        return generate_entity_key(level, key_data, key_fields)

    def process_hierarchical_entity(self, entity_data: Dict[str, Any]) -> Optional[Dict[str, Dict[str, Any]]]:
        """Process a hierarchical entity into separate levels.
        
        Args:
            entity_data: Entity data organized by level
            
        Returns:
            Dictionary mapping level names to their processed entity data, or None if invalid
        """
        if not entity_data or not isinstance(entity_data, dict):
            return None
            
        # Get levels configuration
        levels = self.entity_config.get('levels', {})
        if not levels:
            return None
            
        result: Dict[str, Dict[str, Any]] = {}
        
        # Process each level
        for level, level_data in entity_data.items():
            if level not in levels or not isinstance(level_data, dict):
                continue
                
            # Validate required fields
            level_config = levels[level]
            key_fields = level_config.get('key_fields', [])
            if not all(field in level_data for field in key_fields):
                continue
                
            # Add level-specific context
            level_data['level'] = level
            
            # Add to result
            result[level] = level_data
            
        return result if result else None

    def _generate_entity_key(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """Generate a unique key for an entity using configured key fields.
        
        Args:
            entity_data: Entity data to generate key from
            
        Returns:
            Generated key or None if required fields are missing
        """
        if not entity_data or not self.entity_config:
            return None
            
        # Get key fields from config
        key_fields = self.entity_config.get('key_fields', [])
        if not key_fields:
            logger.warning(f"No key fields configured for {self.entity_type}")
            return None
            
        # Get fields and values for key generation
        key_data = {}
        for field in key_fields:
            if field not in entity_data:
                self.stats.skipped["missing_key_fields"] += 1
                return None
            key_data[field] = entity_data[field]
            
        # Generate key
        return generate_entity_key(self.entity_type, key_data, key_fields)