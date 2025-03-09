"""Validation service for field and entity validation."""
from typing import Dict, Any, Optional, List, Set, DefaultDict
from collections import defaultdict
import logging
from datetime import datetime
from threading import Lock

from .interfaces import IValidationService, IFieldValidator, IValidationMediator
from .validation_base import BaseValidator
from .exceptions import ValidationError
from .component_utils import implements

logger = logging.getLogger(__name__)

@implements(IValidationService)
class ValidationService(BaseValidator, IValidationService):
    """Service for validating data fields using configured rules."""

    def __init__(self, validation_mediator: IValidationMediator, config: Dict[str, Any]):
        """Initialize validation service with mediator and configuration."""
        super().__init__()
        self._mediator = validation_mediator
        self._config = config
        self._rules = self._load_validation_rules()
        self._dependencies = self._initialize_dependencies()
        self._validation_cache: Dict[str, Dict[str, bool]] = {}
        self._cache_lock = Lock()
        self._error_details: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0
        }
        self._max_cache_size = config.get('cache_size', 10000)
        self._strict_mode = config.get('strict_mode', False)
        
        logger.info(f"Validation service initialized with {len(self._rules)} rule sets")

    def _load_validation_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load validation rules from configuration."""
        validation_config = self._config.get('validation_rules', {})
        rules = {}
        
        try:
            for entity_type, rule_sets in validation_config.items():
                if isinstance(rule_sets, list):
                    rules[entity_type] = rule_sets
                elif isinstance(rule_sets, dict):
                    rules[entity_type] = [rule_sets]
                else:
                    logger.error(f"Invalid rule configuration for {entity_type}")
                    
            return rules
        except Exception as e:
            logger.error(f"Error loading validation rules: {str(e)}")
            raise ValidationError(f"Failed to load validation rules: {str(e)}")

    def _initialize_dependencies(self) -> Dict[str, Set[str]]:
        """Initialize field dependencies."""
        dependencies = {}
        
        try:
            for entity_type, rule_sets in self._rules.items():
                field_deps = set()
                for rule_set in rule_sets:
                    if isinstance(rule_set, dict):
                        # Extract dependent fields from rules
                        deps = rule_set.get('dependencies', [])
                        if isinstance(deps, list):
                            field_deps.update(deps)
                            
                dependencies[entity_type] = field_deps
                
            return dependencies
        except Exception as e:
            logger.error(f"Error initializing dependencies: {str(e)}")
            raise ValidationError(f"Failed to initialize dependencies: {str(e)}")

    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate an entity against rules."""
        self.errors.clear()
        validation_start = datetime.utcnow()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(entity_type, data)
            
            # Check cache first
            with self._cache_lock:
                if cache_key in self._validation_cache:
                    self._cache_stats['hits'] += 1
                    return self._validation_cache[cache_key].get('valid', False)
                self._cache_stats['misses'] += 1
            
            # Use mediator for entity validation
            is_valid = self._mediator.validate_entity(entity_type, data)
            validation_errors = self._mediator.get_validation_errors() if not is_valid else []
            
            if validation_errors:
                self.errors.extend(validation_errors)
                
                # Store detailed error information
                error_detail = {
                    'entity_type': entity_type,
                    'timestamp': datetime.utcnow().isoformat(),
                    'errors': validation_errors,
                    'data': data if self._strict_mode else None
                }
                self._error_details[entity_type].append(error_detail)
                
                # Trim error history if needed
                while len(self._error_details[entity_type]) > 100:  # Keep last 100 errors
                    self._error_details[entity_type].pop(0)
            
            # Cache validation result
            self._cache_validation_result(cache_key, is_valid)
            
            # Log validation duration for monitoring
            validation_duration = (datetime.utcnow() - validation_start).total_seconds()
            logger.debug(f"Entity validation took {validation_duration:.3f}s",
                        extra={'entity_type': entity_type, 'duration': validation_duration})
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Entity validation error: {str(e)}", exc_info=True)
            self.errors.append(f"Entity validation failed: {str(e)}")
            return False

    def _validate_field_value(self, field_name: str, value: Any,
                            validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a field value using configured rules."""
        try:
            # Get field type for validation
            field_type = self._get_field_type(field_name)
            if not field_type:
                return True  # No specific validation rules
                
            # Check dependencies if context provided
            if validation_context and field_name in self._dependencies:
                for dep_field in self._dependencies[field_name]:
                    if dep_field not in validation_context:
                        self.errors.append(f"Missing dependent field: {dep_field}")
                        return False
            
            # Validate using mediator
            is_valid = self._mediator.validate_field(field_name, value)
            if not is_valid:
                self.errors.extend(self._mediator.get_validation_errors())
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Field validation error for {field_name}: {str(e)}")
            self.errors.append(f"Field validation failed: {str(e)}")
            return False

    def _get_field_type(self, field_name: str) -> Optional[str]:
        """Get field type from configuration."""
        field_types = self._config.get('field_types', {})
        
        # Check exact match
        if field_name in field_types:
            return field_types[field_name]
            
        # Check pattern match
        for pattern, field_type in field_types.items():
            if pattern.endswith('*'):
                prefix = pattern[:-1]
                if field_name.startswith(prefix):
                    return field_type
        
        return None

    def _generate_cache_key(self, entity_type: str, data: Dict[str, Any]) -> str:
        """Generate cache key for validation results."""
        # Sort fields for consistent key generation
        sorted_items = sorted(
            (k, str(v)) for k, v in data.items()
            if v is not None and k in self._dependencies.get(entity_type, set())
        )
        return f"{entity_type}:" + ";".join(f"{k}={v}" for k, v in sorted_items)

    def _cache_validation_result(self, cache_key: str, is_valid: bool) -> None:
        """Cache validation result with size management."""
        with self._cache_lock:
            # Clear cache if size limit reached
            if len(self._validation_cache) >= self._max_cache_size:
                self._validation_cache.clear()
                self._cache_stats['invalidations'] += 1
                
            self._validation_cache[cache_key] = {
                'valid': is_valid,
                'timestamp': datetime.utcnow().isoformat()
            }

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return {
            'cache_stats': dict(self._cache_stats),
            'rules_count': len(self._rules),
            'error_counts': {
                entity_type: len(errors)
                for entity_type, errors in self._error_details.items()
            },
            'latest_errors': {
                entity_type: errors[-5:]  # Last 5 errors per type
                for entity_type, errors in self._error_details.items()
            } if self._strict_mode else None
        }

    def clear_caches(self) -> None:
        """Clear validation caches."""
        with self._cache_lock:
            self._validation_cache.clear()
            self._cache_stats['invalidations'] += 1
        super().clear_cache()