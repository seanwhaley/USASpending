"""Base entity store implementation."""
from typing import Dict, Any, Optional, Set, List, Union
import json
import logging
from pathlib import Path

from .base_entity_store import BaseEntityStore
from .entity_cache import EntityCache
from .entity_mapper import EntityMapper
from .entity_serializer import EntitySerializer
from .relationship_manager import RelationshipManager
from .utils import generate_entity_key
from .types import (
    ValidationRule,
    EntityData,
    get_registered_type,
    load_types_from_config
)
from .validation import ValidationEngine  # Add this import

logger = logging.getLogger(__name__)

class EntityStore(BaseEntityStore):
    """Basic entity store implementation using consolidated components."""

    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        """Initialize entity store with validation.
        
        Args:
            base_path: Base path for entity storage
            entity_type: Type of entity being stored
            config: Configuration dictionary
        """
        self.config = config
        self.entity_type = entity_type
        self.cache = EntityCache()
        
        # Load types from configuration
        load_types_from_config(config)
        self.entity_class = get_registered_type(entity_type) or EntityData
        
        # Initialize components
        self.mapper = EntityMapper(config, entity_type)
        self.serializer = EntitySerializer(
            Path(base_path), 
            entity_type,
            config['global']['encoding']
        )
        self.relationship_manager = RelationshipManager(entity_type, config)
        
        # Load validation rules from config
        self.validation_rules = self._load_validation_rules()
        self.validator = ValidationEngine(config)  # Replace validation setup
            
    def _load_validation_rules(self) -> List[ValidationRule]:
        """Load validation rules from configuration."""
        rules = []
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(self.entity_type, {}))
                        
        validation_config = entity_config.get('validation', {})
        for field, field_rules in validation_config.items():
            if isinstance(field_rules, dict):
                rules.append(ValidationRule.from_yaml({
                    'field': field,
                    **field_rules
                }))
            elif isinstance(field_rules, str) and field_rules.startswith('$ref:'):
                rule_config = self._get_validation_rule(field_rules[5:].strip()) #Fixed typo here
                if rule_config:
                    rules.append(ValidationRule.from_yaml({
                        'field': field,
                        **rule_config
                    }))
        return rules
                    
    def _get_validation_rule(self, rule_path: str) -> Optional[Dict[str, Any]]:
        """Get validation rule configuration from reference path."""
        parts = rule_path.split('.')
        current = self.config.get('validation_types', {})
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                logger.warning(f"Invalid validation rule reference: {rule_path}")
                return None
                
        return current if isinstance(current, dict) else None
            
    def extract_entity_data(self, row_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entity data from row."""
        try:
            entity_data = self.mapper.extract_entity_data(row_data)
            
            if entity_data:
                # Validate against entity type if available
                if self.entity_class is not EntityData:
                    try:
                        entity_data = self.entity_class(**entity_data)
                    except (TypeError, ValueError) as e:
                        logger.warning(f"Invalid {self.entity_type} data: {str(e)}")
                        self.cache.add_skipped("invalid_data")
                        return None
                
                # Apply validation rules to individual fields
                for field, value in entity_data.items():
                    rules = [rule for rule in self.validation_rules if rule.field == field]
                    validation_result = self.validator.validate_field(field, value, rules)
                    if not validation_result.valid:
                        entity_key = entity_data.get('id', 'unknown')  # Attempt to get entity key
                        logger.warning(
                            f"Validation failed for {self.entity_type} with key {entity_key}, field {field}: {validation_result.message}"
                        )
                        self.cache.add_skipped("invalid_data")
                        return None
                    
            return entity_data
            
        except Exception as e:
            logger.exception(f"Error extracting {self.entity_type} entity: {str(e)}")  # Use logger.exception
            self.cache.add_skipped("extraction_error")
            return None
            
    def add_entity(self, data: Optional[Dict[str, Any]]) -> Optional[Union[str, Dict[str, str]]]:
        """Add an entity to the store."""
        if not data:
            self.cache.add_skipped("invalid_data")
            return None

        entity_key = self._generate_entity_key(data)
        if not entity_key:
            self.cache.add_skipped("missing_key_fields")
            return None
            
        is_update = isinstance(entity_key, str) and entity_key in self.cache.cache
        self.cache.add_entity(entity_key, data, is_update)
        
        # Process relationships if configured
        if data and entity_key:
            self.process_relationships(data, {"key": entity_key})
                
        return entity_key
            
    def _generate_entity_key(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """Generate a unique key for an entity using configured key fields."""
        if not entity_data:
            return None
            
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(self.entity_type, {}))
                        
        key_fields = entity_config.get('key_fields', [])
        if not key_fields:
            logger.warning(f"No key fields configured for {self.entity_type}")
            return None
            
        key_data = {}
        for field in key_fields:
            if field not in entity_data:
                logger.debug(f"Missing key field {field}")
                return None
            key_data[field] = entity_data[field]
            
        key = generate_entity_key(self.entity_type, key_data, key_fields)
        if key:
            if self.entity_type == "agency":
                self.cache.stats.natural_keys_used += 1
            else:
                self.cache.stats.hash_keys_used += 1
        return key

    def process_relationships(self, entity_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        """Process entity relationships based on configuration."""
        if not entity_data or not context:
            return
            
        entity_config = (self.config.get('contracts', {})
                        .get('entity_separation', {})
                        .get('entities', {})
                        .get(self.entity_type, {}))
                        
        if not entity_config or 'relationships' not in entity_config:
            return
            
        relationships = entity_config['relationships']
        
        # Process relationships by type
        for rel_type in ('flat', 'hierarchical'):
            if rel_type in relationships:
                rel_configs = relationships[rel_type]
                if rel_type == 'flat':
                    self.relationship_manager.process_flat_relationships(
                        entity_data, context, rel_configs
                    )
                else:
                    self.relationship_manager.process_hierarchical_relationships(
                        entity_data, 
                        entity_keys=context.get('key'), 
                        relationship_configs=rel_configs
                    )

    def save(self) -> None:
        """Save entities and relationships."""
        self.serializer.save(
            self.cache.cache,
            self.relationship_manager.relationships,
            self.cache.get_stats()
        )