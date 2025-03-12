"""USASpending entity mediation system."""
from typing import Dict, Any, Optional, List, cast
import logging
from .core.interfaces import IConfigurable
from .core.entity_base import BaseEntityMediator
from .core.config import ComponentConfig
from .core.types import EntityData, EntityType, ValidationRule
from .core.exceptions import EntityError
from .core.utils import safe_operation
from .core.entity_base import IEntityFactory, IEntityStore, IEntityMapper

logger = logging.getLogger(__name__)

class USASpendingEntityMediator(BaseEntityMediator, IConfigurable):
    """USASpending-specific entity mediation."""

    def __init__(self, 
                factory: IEntityFactory,
                store: IEntityStore,
                mapper: IEntityMapper) -> None:
        """Initialize entity mediator."""
        super().__init__()
        self._factory = factory
        self._store = store
        self._mapper = mapper
        self._entity_configs: Dict[str, Dict[str, Any]] = {}
        self._validation_rules: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._strict_mode = False
        self._batch_size = 1000
        self._errors: List[str] = []
        self._stats: Dict[str, int] = {
            "created": 0,
            "stored": 0,
            "retrieved": 0,
            "validated": 0,
            "errors": 0
        }
        
    def configure(self, config: ComponentConfig) -> None:
        """Configure with settings."""
        if not config or not isinstance(config.settings, dict):
            raise EntityError("Entity mediator configuration is required")
            
        settings = config.settings
        self._strict_mode = settings.get('strict_mode', False)
        self._batch_size = settings.get('batch_size', 1000)
        self._entity_configs = settings.get('entities', {})
        self._initialized = True

    def add_validation_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        if not rule:
            raise EntityError("Validation rule is required")
        rule_id = getattr(rule, 'id', None) or str(len(self._validation_rules))
        self._validation_rules[rule_id] = {
            'type': rule.rule_type.value.lower(),
            'field_name': rule.field_name,
            'parameters': rule.parameters,
            'message': rule.message,
            'enabled': rule.enabled
        }

    def remove_validation_rule(self, rule_id: str) -> None:
        """Remove a validation rule."""
        if rule_id in self._validation_rules:
            del self._validation_rules[rule_id]

    def _validate_entity_data(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Implementation of entity validation."""
        validation_context = {
            'entity_type': entity_type,
            'config': self._entity_configs.get(entity_type, {})
        }

        for rule_id, rule in self._validation_rules.items():
            if not self._validate_rule(data, rule, validation_context):
                return False
        return True

    def _validate_field_value(self, field_name: str, value: Any, entity_type: Optional[str] = None) -> bool:
        """Implementation of field validation."""
        validation_context = {'entity_type': entity_type} if entity_type else {}
        applicable_rules = [rule for rule in self._validation_rules.values() 
                          if rule.get('field_name') == field_name]
        
        for rule in applicable_rules:
            if not self._validate_rule({field_name: value}, rule, validation_context):
                return False
        return True

    def _validate_rule(self, data: Dict[str, Any], rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Validate data against a rule configuration."""
        try:
            rule_type = rule.get('type')
            if not rule_type:
                logger.warning("Rule missing type")
                return True

            field_name = rule.get('field_name')
            if not field_name or field_name not in data:
                return True

            value = data[field_name]
            
            if rule_type == 'required' and (value is None or (isinstance(value, str) and not value.strip())):
                self._errors.append(rule.get('message', f"Field {field_name} is required"))
                return False
                
            elif rule_type == 'pattern':
                import re
                pattern = rule.get('pattern')
                if pattern and not re.match(pattern, str(value)):
                    self._errors.append(rule.get('message', f"Field {field_name} does not match pattern"))
                    return False
                    
            elif rule_type == 'range':
                try:
                    num_value = float(value)
                    min_val = rule.get('min')
                    max_val = rule.get('max')
                    
                    if min_val is not None and num_value < min_val:
                        self._errors.append(rule.get('message', f"Value below minimum {min_val}"))
                        return False
                        
                    if max_val is not None and num_value > max_val:
                        self._errors.append(rule.get('message', f"Value above maximum {max_val}"))
                        return False
                except (ValueError, TypeError):
                    self._errors.append(rule.get('message', f"Invalid numeric value for {field_name}"))
                    return False
                    
            elif rule_type == 'custom' and 'validate' in rule:
                validate_func = rule['validate']
                if not validate_func(value, context):
                    self._errors.append(rule.get('message', f"Custom validation failed for {field_name}"))
                    return False

            return True

        except Exception as e:
            logger.error(f"Rule validation error: {str(e)}")
            self._errors.append(f"Rule validation error: {str(e)}")
            if self._strict_mode:
                raise
            return False

    @safe_operation
    def process_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Optional[str]:
        """Process an entity."""
        try:
            # Map raw data using configuration-driven mapping
            mapped_data = self._mapper.map_entity(entity_type, data)
            if not mapped_data:
                self._errors.extend(self._mapper.get_errors())
                self._stats["errors"] += 1
                return None

            # Validate mapped data
            self._stats["validated"] += 1
            if not self.validate_entity(str(entity_type), mapped_data):
                self._stats["errors"] += 1
                return None

            # Create and store entity
            entity = self._factory.create_entity(entity_type, mapped_data)
            if not entity:
                self._stats["errors"] += 1
                return None

            self._stats["created"] += 1
            entity_id = self._store.save_entity(entity_type, cast(EntityData, entity))
            if entity_id:
                self._stats["stored"] += 1
                return entity_id

            self._errors.append(f"Failed to store {entity_type}")
            self._stats["errors"] += 1
            return None

        except Exception as e:
            logger.error(f"Entity processing failed: {str(e)}")
            self._errors.append(f"Processing failed: {str(e)}")
            self._stats["errors"] += 1
            if self._strict_mode:
                raise
            return None

    def cleanup(self) -> None:
        """Clean up resources."""
        self._entity_configs.clear()
        self._validation_rules.clear()
        self._stats = {
            "created": 0,
            "stored": 0, 
            "retrieved": 0,
            "validated": 0,
            "errors": 0
        }
        self._errors.clear()
        self._initialized = False

__all__ = ['USASpendingEntityMediator']