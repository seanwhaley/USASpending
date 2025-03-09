"""Validation mediation and coordination."""
from typing import Dict, Any, List, Optional, Type
from threading import Lock
import logging
from collections import defaultdict

from .interfaces import (
    IValidationMediator, IFieldValidator,
    IValidationService, IConfigurationProvider
)
from .validation_base import BaseValidator
from .field_validators import (
    PatternValidator, DateValidator,
    NumericValidator, CodeValidator,
    CompositeValidator
)

logger = logging.getLogger(__name__)

class ValidationMediator(BaseValidator, IValidationMediator):
    """Coordinates validation between components."""

    def __init__(self, config_provider: IConfigurationProvider):
        """Initialize mediator with configuration provider."""
        super().__init__()
        self._config = config_provider
        self._validators: Dict[str, Dict[str, IFieldValidator]] = {}
        self._validator_cache: Dict[str, IFieldValidator] = {}
        self._cache_lock = Lock()
        self._validator_stats = defaultdict(lambda: {
            'total': 0,
            'failed': 0,
            'cache_hits': 0
        })
        self._initialize_validators()
        
        logger.info(f"Validation mediator initialized with {len(self._validators)} validator types")

    def _initialize_validators(self) -> None:
        """Initialize validator registry from configuration."""
        validation_config = self._config.get_config().get('validation', {})
        
        # Register basic validators
        self._validators['pattern'] = {
            'class': PatternValidator,
            'config': validation_config.get('patterns', {})
        }
        self._validators['date'] = {
            'class': DateValidator,
            'config': validation_config.get('date_formats', {})
        }
        self._validators['numeric'] = {
            'class': NumericValidator,
            'config': validation_config.get('numeric_ranges', {})
        }
        self._validators['code'] = {
            'class': CodeValidator,
            'config': validation_config.get('valid_codes', {})
        }
        
        # Initialize composite validators from config
        composite_config = validation_config.get('composite_validators', {})
        for name, config in composite_config.items():
            validator_specs = config.get('validators', [])
            validators = []
            
            for spec in validator_specs:
                validator_type = spec.get('type')
                if validator_type in self._validators:
                    validator_class = self._validators[validator_type]['class']
                    validator_config = spec.get('config', {})
                    try:
                        validators.append(validator_class(**validator_config))
                    except Exception as e:
                        logger.error(f"Failed to create validator {validator_type}: {str(e)}")
                        
            if validators:
                self._validators[name] = {
                    'class': CompositeValidator,
                    'instance': CompositeValidator(
                        validators,
                        require_all=config.get('require_all', True)
                    )
                }

    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate an entity."""
        self.errors.clear()
        validation_config = self._config.get_config().get('entities', {}).get(entity_type, {})
        
        if not validation_config:
            logger.warning(f"No validation configuration for entity type: {entity_type}")
            return True
            
        field_rules = validation_config.get('field_rules', {})
        is_valid = True
        
        for field_name, rules in field_rules.items():
            value = data.get(field_name)
            
            # Skip validation if field is optional and value is None/empty
            if not rules.get('required', False) and (value is None or value == ''):
                continue
                
            # Get validator for field
            validator = self._get_validator_for_field(field_name, rules)
            if not validator:
                continue
                
            # Validate field
            if not validator.validate(value, context=data):
                is_valid = False
                self.errors.extend(validator.errors)
                
        return is_valid

    def validate_field(self, field_name: str, value: Any,
                      entity_type: Optional[str] = None) -> bool:
        """Validate a field value."""
        self.errors.clear()
        
        # Get validation rules for field
        rules = self._get_field_rules(field_name, entity_type)
        if not rules:
            return True
            
        # Get validator
        validator = self._get_validator_for_field(field_name, rules)
        if not validator:
            return True
            
        # Perform validation
        is_valid = validator.validate(value)
        if not is_valid:
            self.errors.extend(validator.errors)
            
        return is_valid

    def _get_field_rules(self, field_name: str,
                        entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Get validation rules for a field."""
        config = self._config.get_config()
        rules = {}
        
        # Check entity-specific rules
        if entity_type:
            entity_rules = config.get('entities', {}).get(entity_type, {})
            rules.update(entity_rules.get('field_rules', {}).get(field_name, {}))
            
        # Check global field rules
        global_rules = config.get('field_rules', {}).get(field_name, {})
        rules.update(global_rules)
        
        # Check pattern-based rules
        for pattern, pattern_rules in config.get('field_patterns', {}).items():
            if re.match(pattern, field_name):
                rules.update(pattern_rules)
                
        return rules

    def _get_validator_for_field(self, field_name: str,
                                rules: Dict[str, Any]) -> Optional[IFieldValidator]:
        """Get or create validator for field."""
        validator_type = rules.get('type', 'pattern')
        
        # Generate cache key
        cache_key = f"{field_name}:{validator_type}:{hash(str(rules))}"
        
        # Check cache
        with self._cache_lock:
            if cache_key in self._validator_cache:
                self._validator_stats[validator_type]['cache_hits'] += 1
                return self._validator_cache[cache_key]
        
        # Create new validator
        validator_info = self._validators.get(validator_type)
        if not validator_info:
            logger.warning(f"Unknown validator type: {validator_type}")
            return None
            
        try:
            if 'instance' in validator_info:
                validator = validator_info['instance']
            else:
                validator_class = validator_info['class']
                validator_config = {**validator_info['config'], **rules}
                validator = validator_class(**validator_config)
                
            # Cache validator
            with self._cache_lock:
                self._validator_cache[cache_key] = validator
                
            return validator
            
        except Exception as e:
            logger.error(f"Failed to create validator for {field_name}: {str(e)}")
            return None

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        stats = super().get_validation_stats()
        stats.update({
            'validator_stats': dict(self._validator_stats),
            'registered_validators': list(self._validators.keys()),
            'cache_size': len(self._validator_cache)
        })
        return stats