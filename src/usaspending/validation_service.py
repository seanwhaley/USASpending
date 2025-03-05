"""Validation service for field and entity validation."""
from typing import Dict, Any, Optional, List, Set
from .validation_base import BaseValidator
from .validation_rules import ValidationRuleLoader
from .text_file_cache import TextFileCache
from .exceptions import ValidationError
from .logging_config import get_logger

logger = get_logger(__name__)

class ValidationService(BaseValidator):
    """Service for validating data fields using configured rules."""

    def __init__(self, rule_loader: ValidationRuleLoader):
        """Initialize validation service.
        
        Args:
            rule_loader: Loader for validation rules
        """
        super().__init__()
        self.rule_loader = rule_loader
        self._rule_cache: Dict[str, Dict[str, Any]] = {}
        self._file_cache = TextFileCache()  # For loading validation rule files
        self._required_fields: Set[str] = set()

    def validate_field(self, field_name: str, value: Any,
                      validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Validate a field value.
        
        Args:
            field_name: Name of field to validate
            value: Value to validate
            validation_context: Optional validation context
            
        Returns:
            True if valid, False otherwise
        """
        # Get validation rules for field
        rules = self._get_field_rules(field_name)
        if not rules:
            return True  # No rules means valid
            
        # Add required field tracking
        if rules.get('required', False):
            self._required_fields.add(field_name)
            
        return super().validate_field(field_name, value, validation_context)

    def _validate_field_value(self, field_name: str, value: Any,
                            validation_context: Optional[Dict[str, Any]] = None) -> bool:
        """Internal validation implementation.
        
        Args:
            field_name: Name of field to validate
            value: Value to validate
            validation_context: Optional validation context
            
        Returns:
            True if valid, False otherwise
        """
        rules = self._get_field_rules(field_name)
        if not rules:
            return True
            
        try:
            # Check if field is required
            if rules.get('required', False) and not value:
                self.errors.append(f"Required field '{field_name}' is empty")
                return False
                
            # Get appropriate adapter
            adapter = self._get_adapter(field_name)
            if not adapter:
                logger.warning(f"No adapter found for field {field_name}")
                return True
                
            # Validate using adapter
            if not adapter.validate(value, rules, validation_context):
                self.errors.extend(adapter.get_errors())
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Validation error for field {field_name}: {str(e)}")
            self.errors.append(f"Validation failed for field '{field_name}': {str(e)}")
            return False

    def _get_field_rules(self, field_name: str) -> Optional[Dict[str, Any]]:
        """Get validation rules for a field.
        
        Args:
            field_name: Field name to get rules for
            
        Returns:
            Dictionary of validation rules or None if not found
        """
        # Check cache first
        if field_name in self._rule_cache:
            return self._rule_cache[field_name]
            
        # Load from rule loader
        try:
            rules = self.rule_loader.get_field_rules(field_name)
            if rules:
                self._rule_cache[field_name] = rules
            return rules
        except Exception as e:
            logger.error(f"Failed to load rules for field {field_name}: {str(e)}")
            return None

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics.
        
        Returns:
            Dictionary of validation statistics
        """
        stats = super().get_validation_stats()
        stats.update({
            'required_fields': len(self._required_fields),
            'rule_cache_size': len(self._rule_cache)
        })
        return stats

    def clear_caches(self) -> None:
        """Clear all validation caches."""
        super().clear_cache()
        self._rule_cache.clear()
        self._file_cache.clear()
        self._required_fields.clear()