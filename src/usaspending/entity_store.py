"""Entity store implementation with integrated relationship management."""
from typing import Dict, Any, Optional, Set, List, Union, Iterator, Tuple, DefaultDict
from collections import defaultdict
from itertools import chain
import json
import logging
from pathlib import Path

from .config import ConfigManager
from .validation import ValidationEngine
from .entity_cache import EntityCache, get_entity_cache
from .entity_mapper import EntityMapper
from .entity_serializer import EntitySerializer
from .utils import generate_entity_key
from .types import (
    ValidationRule,
    EntityData,
    get_registered_type,
    get_type_manager,
    EntityStats,
    RelationshipMap
)

logger = logging.getLogger(__name__)

class EntityStore:
    """Entity store implementation with integrated validation and relationship management."""

    def __init__(self, base_path: str, entity_type: str, config: ConfigManager) -> None:
        """Initialize entity store with validation."""
        self.config_manager = config
        self.entity_type = entity_type
        self.config = self.config_manager.config
        self.entity_config = self.config_manager.get_entity_config(entity_type)
        
        if not self.entity_config:
            raise ValueError(f"No configuration found for entity type: {entity_type}")
            
        # Core components initialization
        self.cache = get_entity_cache()
        self.type_manager = get_type_manager()
        self.type_manager.load_from_config(self.config)
        self.entity_class = self.type_manager.get_type(entity_type) or EntityData
        
        # Component managers
        self.mapper = EntityMapper(self.config_manager, entity_type)
        self.serializer = EntitySerializer(
            Path(base_path), 
            entity_type,
            self.config.get('global', {}).get('encoding', 'utf-8')
        )
        
        # Initialize relationship management
        self._init_relationship_management()
        
        # Load validation rules
        self.validation_rules = self._load_validation_rules()
        self.validator = ValidationEngine(self.config_manager)

    def _init_relationship_management(self) -> None:
        """Initialize relationship management capabilities."""
        self.relationships: DefaultDict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self._relationship_configs = self._cache_relationship_configs()
        
    def _cache_relationship_configs(self) -> Dict[str, Any]:
        """Cache relationship configurations for faster access."""
        configs = {
            'hierarchical': self.entity_config.get('relationships', {}).get('hierarchical', []),
            'flat': self.entity_config.get('relationships', {}).get('flat', []),
            'valid_types': set(),
            'inverse_mappings': {},
            'relationship_rules': defaultdict(dict)
        }

        # Process relationship configurations
        for rel_config in chain(configs['hierarchical'], configs['flat']):
            if 'type' in rel_config:
                rel_type = rel_config['type']
                configs['valid_types'].add(rel_type)
                
                if 'inverse_type' in rel_config:
                    inverse_type = rel_config['inverse_type']
                    configs['valid_types'].add(inverse_type)
                    configs['inverse_mappings'][rel_type] = inverse_type
                    configs['inverse_mappings'][inverse_type] = rel_type

                if 'rules' in rel_config:
                    configs['relationship_rules'][rel_type].update(rel_config['rules'])
                    
        return configs

    def _load_validation_rules(self) -> List[ValidationRule]:
        """Load validation rules from configuration."""
        rules = []
        validation_config = self.entity_config.get('validation', {})
        error_messages = self.config.get('validation_messages', {})  # Fix property access
        
        for field, field_rules in validation_config.items():
            try:
                if isinstance(field_rules, dict):
                    # Add error message handling
                    if 'error' in field_rules:
                        error_key = field_rules['error']
                        if error_key in error_messages:
                            field_rules['error_text'] = error_messages[error_key]
                    rules.append(ValidationRule.from_yaml({
                        'field': field,
                        **field_rules
                    }))
                elif isinstance(field_rules, str) and field_rules.startswith('$ref:'):
                    rule_config = self._get_validation_rule(field_rules[5:].trip())
                    if rule_config:
                        # Add error message handling for referenced rules
                        if 'error' in rule_config:
                            error_key = rule_config['error']
                            if error_key in error_messages:
                                rule_config['error_text'] = error_messages[error_key]
                        rules.append(ValidationRule.from_yaml({
                            'field': field,
                            **rule_config
                        }))
            except Exception as e:
                error_template = self.config.get('validation_messages', {}).get('rules', {}).get(
                    'loading_error', "Error loading validation rule for field {field}: {error}"
                )
                logger.error(error_template.format(field=field, error=str(e)))
                continue
                
        return rules
                    
    def _get_validation_rule(self, rule_path: str) -> Optional[Dict[str, Any]]: 
        """Get validation rule configuration from reference path."""
        parts = rule_path.split('.')
        current = self.config.get('validation_types', {})  # Fix config access
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                error_template = self.config.get('validation_messages', {}).get('rules', {}).get(
                    'invalid_reference', "Invalid validation rule reference: {path}"
                )
                logger.warning(error_template.format(path=rule_path))
                return None
                
        return current if isinstance(current, dict) else None
            
    def extract_entity_data(self, row_data: Dict[str, Any]) -> Optional[Dict[str, Any]]: 
        """Extract entity data from row."""
        try:
            entity_data = self.mapper.extract_entity_data(row_data)
            
            if entity_data:
                if self.entity_class is not EntityData:
                    try:
                        entity_data = self.entity_class(**entity_data)
                    except (TypeError, ValueError) as e:
                        logger.warning(
                            self.config.get('validation_messages', {}).get('entity', {}).get('invalid_data', 
                            "Invalid data for {entity_type}: {error}").format(  # Fix config access
                                entity_type=self.entity_type,
                                error=str(e)
                            )
                        )
                        self.cache.add_skipped("invalid_data")
                        return None
                        
        except Exception as e:
            logger.exception(
                self.config.get('validation_messages', {}).get('entity', {}).get('extraction_error',
                "Error extracting {entity_type}: {error}").format(  # Fix config access
                    entity_type=self.entity_type, 
                    error=str(e)
                )
            )
            self.cache.add_skipped("extraction_error")
            return None
            
    def add_entity(self, data: Optional[Dict[str, Any]]) -> Optional[Union[str, Dict[str, str]]]:
        """Add an entity to the store."""
        if not data:
            self.cache.add_skipped("invalid_data")
            return None

        entity_key = self._generate_entity_key(data)
        if not entity_key:
            error_template = self.config.get('validation_messages', {}).get('entity', {}).get(
                'missing_key_fields', "Missing required key fields for {entity_type}"
            )
            logger.warning(error_template.format(entity_type=self.entity_type))
            self.cache.add_skipped("missing_key_fields")
            return None
            
        is_update = isinstance(entity_key, str) and entity_key in self.cache.cache
        self.cache.add_entity(entity_key, data, is_update)
        
        # Process relationships if configured
        if data and entity_key:
            self.process_relationships(data, {"key": entity_key})
                
        return entity_key
            
    def _generate_entity_key(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """Generate entity key using mapper."""
        return self.mapper.build_key(entity_data)

    def process_relationships(self, entity_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        """Process entity relationships based on configuration."""
        if not entity_data or not context:
            return
            
        entity_key = context.get('key')
        if not entity_key or not isinstance(entity_key, str):
            logger.warning(f"Invalid entity key in context for {self.entity_type}")
            return

        self._process_flat_relationships(entity_data, entity_key)
        self._process_hierarchical_relationships(entity_data, entity_key)

    def _process_flat_relationships(self, entity_data: Dict[str, Any], entity_key: str) -> None:
        """Process flat relationships."""
        for rel_config in self._relationship_configs['flat']:
            from_field = rel_config.get('from_field')
            to_field = rel_config.get('to_field')
            rel_type = rel_config.get('type')
            inverse_type = rel_config.get('inverse_type')
            
            if not all([from_field, to_field, rel_type]):
                continue
                
            from_value = entity_data.get(from_field)
            to_value = entity_data.get(to_field)
            
            if from_value and to_value:
                if isinstance(from_value, (list, set)):
                    for value in from_value:
                        self.add_relationship(str(value), rel_type, str(to_value), inverse_type)
                else:
                    self.add_relationship(str(from_value), rel_type, str(to_value), inverse_type)

    def _process_hierarchical_relationships(self, entity_data: Dict[str, Any], entity_key: str) -> None:
        """Process hierarchical relationships."""
        entity_keys = self._extract_entity_keys(entity_data)
        if not entity_keys:
            return

        for rel_config in self._relationship_configs['hierarchical']:
            from_level = rel_config.get('from_level')
            to_level = rel_config.get('to_level')
            rel_type = rel_config.get('type')
            inverse_type = rel_config.get('inverse_type')
            
            if not all([from_level, to_level, rel_type]):
                continue
                
            if from_level in entity_keys and to_level in entity_keys:
                from_key = entity_keys[from_level]
                to_key = entity_keys[to_level]
                
                if self.would_create_cycle(to_key, from_key):
                    logger.warning(f"Skipping cyclic relationship: {from_key} -{rel_type}-> {to_key}")
                    continue
                
                self.add_relationship(from_key, rel_type, to_key, inverse_type)

    def _extract_entity_keys(self, entity_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract entity keys from data for hierarchical relationships."""
        return {
            level: str(entity_data[key_field])
            for level, key_field in self.entity_config.get('key_fields', {}).items()
            if key_field in entity_data
        }

    def add_relationship(self, from_key: str, rel_type: str, to_key: str, inverse_type: Optional[str] = None) -> None:
        """Add a relationship between entities."""
        if not all([from_key, rel_type, to_key]):
            logger.warning("Invalid relationship parameters")
            return

        if rel_type not in self._relationship_configs['valid_types']:
            logger.warning(f"Invalid relationship type '{rel_type}' for {self.entity_type}")
            return

        # Apply relationship rules
        rules = self._relationship_configs['relationship_rules'].get(rel_type, {})
        if rules:
            if rules.get('exclusive', False) and self.relationships[from_key][rel_type]:
                logger.warning(f"Exclusive relationship violation for {rel_type}")
                return
                
            if rules.get('max_cardinality'):
                if len(self.relationships[from_key][rel_type]) >= rules['max_cardinality']:
                    logger.warning(f"Maximum cardinality reached for {rel_type}")
                    return

        # Add relationships
        self.relationships[from_key][rel_type].add(to_key)
        
        effective_inverse = inverse_type or self._relationship_configs['inverse_mappings'].get(rel_type)
        if effective_inverse:
            self.relationships[to_key][effective_inverse].add(from_key)

    def get_related_entities(self, entity_key: str, rel_type: str) -> Set[str]:
        """Get related entities by type."""
        return self.relationships[entity_key][rel_type].copy()

    def get_all_relationships(self, entity_key: str) -> Dict[str, Set[str]]:
        """Get all relationships for an entity."""
        return {k: v.copy() for k, v in self.relationships[entity_key].items()}

    def would_create_cycle(self, child_key: str, parent_key: str) -> bool:
        """Check for relationship cycles."""
        if child_key == parent_key:
            return True

        hierarchical_types = {
            config['type'] for config in self._relationship_configs['hierarchical']
            if 'type' in config
        }

        ancestors = set()
        to_check = {parent_key}
        
        while to_check:
            current = to_check.pop()
            if current == child_key:
                return True
                
            for rel_type in hierarchical_types:
                parents = self.get_related_entities(current, rel_type)
                new_ancestors = parents - ancestors
                ancestors.update(new_ancestors)
                to_check.update(new_ancestors)
                
        return False

    def save(self) -> None:
        """Save entities and relationships."""
        self.serializer.save(
            self.cache.cache,
            dict(self.relationships),  # Convert defaultdict to regular dict
            self.cache.get_stats()
        )