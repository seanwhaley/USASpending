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
from .exceptions import TransformationError
from .keys import CompositeKey
from .field_dependencies import FieldDependency
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
        logger.debug(f"Initializing EntityStore for {entity_type}")
        self.config_manager = config
        self.entity_type = entity_type
        self.config = self.config_manager.config
        self.entity_config = self.config_manager.get_entity_config(entity_type)
        
        if not self.entity_config:
            logger.error(f"No configuration found for entity type: {entity_type}")
            raise ValueError(f"No configuration found for entity type: {entity_type}")
        
        logger.debug(f"Entity config for {entity_type}: {json.dumps(self.entity_config, indent=2)}")
            
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
        logger.info(f"EntityStore initialized for {entity_type} with {len(self.validation_rules)} validation rules")

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
            
    def extract_entity_data(self, source_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entity data from source data according to mapping rules."""
        if not source_data:
            return None
            
        result = {}
        field_mappings = self.entity_config.get('field_mappings', {})
        
        # Process direct mappings
        for target_field, mapping in field_mappings.get('direct', {}).items():
            if isinstance(mapping, str):
                # Simple direct field mapping
                if mapping in source_data:
                    result[target_field] = source_data[mapping]
            elif isinstance(mapping, dict):
                source_field = mapping.get("field")
                if source_field and source_field in source_data:
                    value = source_data[source_field]
                    # Apply transformations if defined
                    if "transformation" in mapping:
                        try:
                            value = self._apply_transformation(value, mapping["transformation"])
                        except TransformationError as e:
                            logger.warning(f"Transformation error for {target_field}: {str(e)}")
                            continue
                    result[target_field] = value

        # Process multi-source mappings
        for target_field, mapping in field_mappings.get('multi_source', {}).items():
            if not isinstance(mapping, dict):
                continue
                
            sources = mapping.get('sources', [])
            strategy = mapping.get('strategy', 'first_non_empty')
            
            if strategy == 'first_non_empty':
                for source in sources:
                    if source in source_data and source_data[source]:
                        result[target_field] = source_data[source]
                        break
            elif strategy == 'concatenate':
                values = [str(source_data.get(s, '')) for s in sources if s in source_data]
                if values:
                    result[target_field] = mapping.get('separator', ' ').join(values)

        # Process object mappings
        for target_field, mapping in field_mappings.get('object', {}).items():
            if not isinstance(mapping, dict):
                continue
                
            obj_data = {}
            for obj_field, source_field in mapping.get('fields', {}).items():
                if source_field in source_data:
                    obj_data[obj_field] = source_data[source_field]
                    
            # Handle nested objects
            for nested_name, nested_config in mapping.get('nested_objects', {}).items():
                if isinstance(nested_config, dict):
                    nested_data = {}
                    for nested_field, nested_source in nested_config.get('fields', {}).items():
                        if nested_source in source_data:
                            nested_data[nested_field] = source_data[nested_source]
                    if nested_data:
                        obj_data[nested_name] = nested_data
                        
            if obj_data:
                result[target_field] = obj_data

        # Process reference mappings
        for target_field, mapping in field_mappings.get('reference', {}).items():
            if not isinstance(mapping, dict):
                continue
                
            entity = mapping.get('entity')
            key_field = mapping.get('key_field')
            if entity and key_field and key_field in source_data:
                result[f"{target_field}_ref"] = {
                    "entity": entity,
                    "key": source_data[key_field]
                }
                
            # Handle composite keys
            key_fields = mapping.get('key_fields', [])
            key_prefix = mapping.get('key_prefix', '')
            if entity and key_fields:
                ref_key = {}
                for field in key_fields:
                    source_field = f"{key_prefix}_{field}" if key_prefix else field
                    if source_field in source_data:
                        ref_key[field] = source_data[source_field]
                if ref_key:
                    result[f"{target_field}_ref"] = {
                        "entity": entity,
                        "key": ref_key
                    }

        # Process template mappings
        for target_field, mapping in field_mappings.get('template', {}).items():
            if not isinstance(mapping, dict):
                continue
                
            templates = mapping.get('templates', {})
            for template_name, template_str in templates.items():
                try:
                    filled_template = template_str.format(**source_data)
                    if filled_template:
                        if target_field not in result:
                            result[target_field] = {}
                        result[target_field][template_name] = filled_template
                except (KeyError, ValueError) as e:
                    logger.warning(f"Template error for {target_field}.{template_name}: {str(e)}")
                    continue

        # Add validation after all mappings are processed
        if result and self.validator:
            validation_results = self.validator.validate_record(result)
            if not all(r.valid for r in validation_results):
                logger.warning(f"Validation failed for {self.entity_type}")
                return None

        return result if result else None
            
    def add_entity(self, data: Optional[Dict[str, Any]]) -> Optional[Union[str, Dict[str, str], CompositeKey]]:
        """Add an entity to the store."""
        if not data:
            logger.debug(f"Skipping empty entity data for {self.entity_type}")
            self.cache.add_skipped("invalid_data")
            return None

        logger.debug(f"Generating key for {self.entity_type} entity")
        entity_key = self._generate_entity_key(data)
        if not entity_key:
            error_template = self.config.get('validation_messages', {}).get('entity', {}).get(
                'missing_key_fields', "Missing required key fields for {entity_type}"
            )
            logger.warning(error_template.format(entity_type=self.entity_type))
            self.cache.add_skipped("missing_key_fields")
            return None
            
        # Convert to hashable format if needed
        cache_key = self._make_hashable_key(entity_key)
        is_update = cache_key in self.cache.cache
        
        if is_update:
            logger.debug(f"Updating existing {self.entity_type} entity with key: {cache_key}")
        else:
            logger.debug(f"Adding new {self.entity_type} entity with key: {cache_key}")
        
        # Store the original key format for external references
        original_key = entity_key if isinstance(entity_key, dict) else cache_key
        self.cache.add_entity(cache_key, data, is_update)
        
        # Process relationships if configured
        if data and cache_key:
            logger.debug(f"Processing relationships for {self.entity_type} entity: {cache_key}")
            self.process_relationships(data, {"key": cache_key})
                
        return original_key

    def _make_hashable_key(self, key: Union[str, Dict[str, str], CompositeKey]) -> Union[str, CompositeKey]:
        """Convert a key into a hashable format.
        
        Args:
            key: The key to convert. Can be a string, dictionary, or CompositeKey
            
        Returns:
            A hashable version of the key (either string or CompositeKey)
            
        Raises:
            ValueError: If the key is neither a string, dictionary, nor CompositeKey
        """
        if isinstance(key, (str, CompositeKey)):
            return key
        elif isinstance(key, dict):
            # Convert all dictionary values to strings to ensure consistent hashing
            key_dict = {str(k): str(v) for k, v in key.items()}
            return CompositeKey(key_dict)
        else:
            raise ValueError(f"Invalid key type: {type(key)}")

    def _generate_entity_key(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """Generate entity key using mapper."""
        return self.mapper.build_key(entity_data)

    def process_relationships(self, entity_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        """Process entity relationships based on configuration."""
        if not entity_data or not context:
            logger.debug(f"Skipping relationship processing for {self.entity_type} - missing data or context")
            return
            
        entity_key = context.get('key')
        if not entity_key:
            logger.warning(f"Invalid entity key in context for {self.entity_type}")
            return

        logger.debug(f"Processing relationships for {self.entity_type} with key: {entity_key}")

        # Ensure key is hashable
        if isinstance(entity_key, dict):
            entity_key = self._make_hashable_key(entity_key)

        self._process_flat_relationships(entity_data, entity_key)
        self._process_hierarchical_relationships(entity_data, entity_key)
        
        # Log relationship stats
        rel_count = sum(len(rels) for rels in self.relationships[entity_key].values())
        logger.debug(f"Processed {rel_count} relationships for {self.entity_type} entity: {entity_key}")

    def _process_flat_relationships(self, entity_data: Dict[str, Any], entity_key: Union[str, CompositeKey]) -> None:
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
                # Handle composite keys in relationship values
                if isinstance(from_value, dict):
                    from_value = self._make_hashable_key(from_value)
                if isinstance(to_value, dict):
                    to_value = self._make_hashable_key(to_value)
                    
                if isinstance(from_value, (list, set)):
                    for value in from_value:
                        self.add_relationship(
                            self._make_hashable_key(value) if isinstance(value, dict) else str(value),
                            rel_type,
                            self._make_hashable_key(to_value) if isinstance(to_value, dict) else str(to_value),
                            inverse_type
                        )
                else:
                    self.add_relationship(
                        self._make_hashable_key(from_value) if isinstance(from_value, dict) else str(from_value),
                        rel_type,
                        self._make_hashable_key(to_value) if isinstance(to_value, dict) else str(to_value),
                        inverse_type
                    )

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

    def _extract_entity_keys(self, entity_data: Dict[str, Any]) -> Dict[str, Union[str, CompositeKey]]:
        """Extract entity keys from data for hierarchical relationships."""
        keys = {}
        for level, key_field in self.entity_config.get('key_fields', {}).items():
            if isinstance(key_field, list):
                # Handle composite keys
                key_parts = {}
                for field in key_field:
                    if field in entity_data:
                        key_parts[field] = str(entity_data[field])
                if key_parts:
                    keys[level] = self._make_hashable_key(key_parts)
            elif key_field in entity_data:
                keys[level] = str(entity_data[key_field])
        return keys

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
        logger.info(f"Saving {self.entity_type} store")
        logger.debug(f"Entity count: {len(self.cache.cache)}")
        logger.debug(f"Relationship count: {sum(len(v) for v in self.relationships.values())}")
        
        try:
            self.serializer.save(
                self.cache.cache,
                dict(self.relationships),  # Convert defaultdict to regular dict
                self.cache.get_stats()
            )
            logger.info(f"Successfully saved {self.entity_type} store")
        except Exception as e:
            logger.error(f"Error saving {self.entity_type} store: {str(e)}", exc_info=True)
            raise

class FieldDependencyManager:
    def __init__(self):
        self.dependencies = {}

    def add_dependency(self, field_name, target_field, dependency_type, metadata=None):
        """Add dependency with cycle detection."""
        # Check if adding this dependency would create a cycle
        if metadata and metadata.get('bidirectional') and self._has_path(target_field, field_name):
            # For bidirectional dependencies, mark them specially
            if metadata is None:
                metadata = {}
            metadata['circular'] = True
        
        # Add to dependency graph
        if field_name not in self.dependencies:
            self.dependencies[field_name] = []
        self.dependencies[field_name].append({
            'target': target_field,
            'type': dependency_type,
            'metadata': metadata
        })

    def _has_path(self, start, end, visited=None):
        """Check if there's a path from start to end in dependency graph."""
        if visited is None:
            visited = set()
        
        if start == end:
            return True
        
        if start in visited:
            return False
        
        visited.add(start)
        
        for dep in self.dependencies.get(start, []):
            if self._has_path(dep['target'], end, visited):
                return True
                
        return False

    def get_dependencies(self, field_name: str):
        return self.dependencies.get(field_name, set())

    def get_dependent_fields(self, target_field: str):
        dependents = set()
        for field, deps in self.dependencies.items():
            if any(target_field in dep.dependencies for dep in deps):
                dependents.add(field)
        return dependents