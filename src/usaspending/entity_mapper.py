"""Entity mapping implementation."""
from typing import Dict, Any, Optional, List, Callable, cast, TypeVar, Union, Generic, overload, Sequence
import logging
from decimal import Decimal
from datetime import datetime
from .core.interfaces import IEntityMapper
from .core.types import MappingResult, EntityType, ComponentConfig, FieldType, ValidationRule, EntityData
from .core.validation import BaseValidator
from .core.exceptions import MappingError

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=EntityData)
CalcFunc = Callable[[Sequence[Any]], Any]

class EntityMapper(BaseValidator, IEntityMapper, Generic[T]):
    """Implements entity mapping functionality."""

    def __init__(self) -> None:
        """Initialize entity mapper."""
        super().__init__()
        self._mappings: Dict[str, Dict[str, Any]] = {}
        self._initialized: bool = False
        self._errors: List[str] = []
        self._calculation_functions: Dict[str, CalcFunc] = {
            'sum': lambda values, **_: sum(Decimal(str(v)) for v in values if v is not None),
            'avg': lambda values, **_: (sum(Decimal(str(v)) for v in values if v is not None) / 
                                   len([v for v in values if v is not None])) if any(v is not None for v in values) else None,
            'concat': lambda values, **kwargs: kwargs.get('separator', '').join(str(v) for v in values if v is not None),
            'first_non_null': lambda values, **_: next((v for v in values if v is not None), None),
            'coalesce': lambda values, **_: next((v for v in values if v is not None), None),
            'count': lambda values, **_: len([v for v in values if v is not None]),
            'min': lambda values, **_: min((Decimal(str(v)) for v in values if v is not None), default=None),
            'max': lambda values, **_: max((Decimal(str(v)) for v in values if v is not None), default=None)
        }

    def configure(self, config: ComponentConfig) -> None:
        """Configure mapper with settings."""
        if not config or not isinstance(config.settings, dict):
            raise ValueError("Invalid mapper configuration")
        
        self._mappings = config.settings.get('mappings', {})
        self._initialized = True

    def add_validation_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        if rule not in self._rules:
            self._rules.append(rule)

    def remove_validation_rule(self, rule_id: str) -> None:
        """Remove a validation rule."""
        self._rules = [r for r in self._rules if getattr(r, 'id', None) != rule_id]

    def get_errors(self) -> List[str]:
        """Get error messages."""
        return self._errors.copy()

    def validate(self, entity_id: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate entity data before mapping."""
        if not self._initialized:
            self._errors.append("Mapper not initialized")
            return False
            
        if entity_id not in self._mappings:
            self._errors.append(f"No mapping configuration for entity type: {entity_id}")
            return False
            
        mapping_config = self._mappings[entity_id]
        required_fields = mapping_config.get('required_fields', [])
        
        for field in required_fields:
            if field not in data:
                self._errors.append(f"Required field missing: {field}")
                return False
                
        return True

    def map_entity(self, entity_type: EntityType, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map source data to target entity format."""
        if not self.validate(str(entity_type), data, {}):
            return {}
            
        result: Dict[str, Any] = {}
        mapping_config = self._mappings[str(entity_type)]
        
        # Direct field mappings
        field_mappings = mapping_config.get('field_mappings', {})
        for target_field, source_info in field_mappings.items():
            source_field = source_info.get('field')
            if source_field in data:
                result[target_field] = data[source_field]
                
        # Derived fields
        derived_mappings = mapping_config.get('derived_mappings', {})
        for target_field, calculation in derived_mappings.items():
            try:
                result[target_field] = self._calculate_derived_field(
                    calculation, data
                )
            except Exception as e:
                self._errors.append(f"Error calculating derived field {target_field}: {str(e)}")
                
        return result

    def _calculate_derived_field(self, calculation: Dict[str, Any], data: Dict[str, Any]) -> Any:
        """Calculate derived field value based on calculation rules."""
        calc_type = calculation.get('type')
        if not calc_type:
            raise MappingError("Calculation type is required")

        source_fields = calculation.get('source_fields', [])
        field_values = [data.get(field) for field in source_fields]

        # Handle empty source fields based on configuration
        if not any(v is not None for v in field_values):
            default_value = calculation.get('default')
            if default_value is not None:
                return default_value
            if calculation.get('required', False):
                raise MappingError("Required derived field has no source values")
            return None

        try:
            if calc_type == 'custom':
                func_name = calculation.get('function')
                if not func_name or func_name not in self._calculation_functions:
                    raise MappingError(f"Unknown calculation function: {func_name}")
                params = calculation.get('parameters', {})
                return self._calculation_functions[func_name](field_values, **params)

            if calc_type == 'formula':
                formula = calculation.get('formula')
                if not formula:
                    raise MappingError("Formula is required for formula calculation type")
                # Basic formula evaluation - extend this based on requirements
                return eval(formula, {"__builtins__": {}}, {
                    f"val{i}": v for i, v in enumerate(field_values)
                })

            if calc_type in self._calculation_functions:
                params = calculation.get('parameters', {})
                return self._calculation_functions[calc_type](field_values, **params)

            raise MappingError(f"Unsupported calculation type: {calc_type}")

        except Exception as e:
            raise MappingError(f"Calculation failed: {str(e)}")

    def register_calculation_function(self, name: str, func: CalcFunc) -> None:
        """Register a custom calculation function."""
        self._calculation_functions[name] = func

    def clear_errors(self) -> None:
        """Clear error messages."""
        self._errors.clear()

__all__ = ['EntityMapper']