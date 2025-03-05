"""Validation service for field and entity validation."""
from typing import Dict, Any, Optional, List, Set, Tuple
from collections import defaultdict

from . import get_logger, ConfigurationError, implements
from .validation_base import BaseValidator
from .validation_rules import ValidationRuleLoader
from .text_file_cache import TextFileCache
from .interfaces import IValidationService, ISchemaAdapter, IDependencyManager

logger = get_logger(__name__)

@implements(IValidationService)
class ValidationService(IValidationService):
    """Service for validating data fields using configured rules."""
    
    def __init__(self, dependency_manager: IDependencyManager, rule_loader: Optional[ValidationRuleLoader] = None):
        """Initialize validation service."""
        self.dependency_manager = dependency_manager
        self.rule_loader = rule_loader
        self.adapters: Dict[str, ISchemaAdapter] = {}
        self.rules: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.validation_errors: List[str] = []
        self._rule_cache: Dict[str, Dict[str, Any]] = {}
        self._file_cache = TextFileCache()
        self._stats: Dict[str, int] = defaultdict(int)
        
    def validate_field(self, field_name: str, value: Any) -> List[str]:
        """Validate a single field value.
        
        Args:
            field_name: Name of field to validate
            value: Value to validate
            
        Returns:
            List of validation error messages
        """
        self.validation_errors.clear()
        
        # Get validation rules for the field
        field_rules = self.rules.get(field_name, [])
        if not field_rules and self.rule_loader:
            field_rules = self._get_field_rules(field_name)
            
        # Perform validation
        if not self._validate_field(field_name, value, field_rules):
            return self.validation_errors.copy()
            
        return []
        
    def validate_record(self, record: Dict[str, Any]) -> List[str]:
        """Validate an entire record.
        
        Args:
            record: Record to validate
            
        Returns:
            List of validation error messages
        """
        self.validation_errors.clear()
        
        # Get validation order considering dependencies
        validation_order = self.dependency_manager.get_validation_order(list(record.keys()))
        
        # Validate fields in order
        for field_name in validation_order:
            if field_name not in record:
                continue
                
            # Validate dependencies
            dep_errors = self.dependency_manager.validate_dependencies(record, field_name, self.adapters)
            if dep_errors:
                self.validation_errors.extend(dep_errors)
                self._stats['dependency_errors'] += len(dep_errors)
                continue
            
            # Validate the field
            field_value = record[field_name]
            field_rules = self.rules.get(field_name, [])
            if not field_rules and self.rule_loader:
                field_rules = self._get_field_rules(field_name)
                
            if not self._validate_field(field_name, field_value, field_rules):
                self._stats['field_validation_failures'] += 1
                
        return self.validation_errors.copy()
        
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics.
        
        Returns:
            Dictionary of validation statistics
        """
        return dict(self._stats)
        
    def _validate_field(self, field_name: str, value: Any, rules: List[Dict[str, Any]]) -> bool:
        """Validate a single field value.
        
        Args:
            field_name: Name of field to validate
            value: Value to validate
            rules: List of validation rules
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Get appropriate adapter
            adapter = self.adapters.get(field_name)
            if not adapter:
                return True  # No adapter means valid
                
            # Apply each rule
            for rule in rules:
                if not adapter.validate(value, rule):
                    errors = adapter.get_validation_errors()
                    self.validation_errors.extend(errors)
                    self._stats['field_errors'] += len(errors)
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error validating field {field_name}: {str(e)}")
            self.validation_errors.append(f"Validation failed for field '{field_name}': {str(e)}")
            self._stats['validation_errors'] += 1
            return False
            
    def _get_field_rules(self, field_name: str) -> List[Dict[str, Any]]:
        """Get validation rules for a field.
        
        Args:
            field_name: Field name to get rules for
            
        Returns:
            List of validation rules
        """
        # Check cache first
        if field_name in self._rule_cache:
            return self._rule_cache[field_name]
            
        # Load from rule loader
        try:
            if self.rule_loader:
                rules = self.rule_loader.get_field_rules(field_name)
                if rules:
                    self._rule_cache[field_name] = rules if isinstance(rules, list) else [rules]
                    return self._rule_cache[field_name]
        except Exception as e:
            logger.error(f"Failed to load rules for field {field_name}: {str(e)}")
            
        return []

class ValidationServiceBuilder:
    """Builder for creating configured ValidationService instances."""
    
    def __init__(self):
        """Initialize builder."""
        self.dependency_manager = None
        self.rule_loader = None
        self.strict_mode = False
        self.cache_size = 1000
        self.parallel = True
        self.max_errors = 100
    
    def with_dependency_manager(self, dependency_manager: IDependencyManager) -> 'ValidationServiceBuilder':
        """Set dependency manager."""
        self.dependency_manager = dependency_manager
        return self
    
    def with_rule_loader(self, rule_loader: ValidationRuleLoader) -> 'ValidationServiceBuilder':
        """Set rule loader."""
        self.rule_loader = rule_loader
        return self
    
    def with_strict_mode(self, strict_mode: bool) -> 'ValidationServiceBuilder':
        """Set strict mode."""
        self.strict_mode = strict_mode
        return self
    
    def with_cache_size(self, cache_size: int) -> 'ValidationServiceBuilder':
        """Set cache size."""
        self.cache_size = cache_size
        return self
    
    def with_parallel_validation(self, parallel: bool) -> 'ValidationServiceBuilder':
        """Set parallel validation."""
        self.parallel = parallel
        return self
    
    def with_max_errors(self, max_errors: int) -> 'ValidationServiceBuilder':
        """Set maximum errors."""
        self.max_errors = max_errors
        return self
    
    def build(self) -> ValidationService:
        """Create ValidationService instance."""
        if not self.dependency_manager:
            # Create a simple default dependency manager instead of importing
            # This avoids the dependency on a specific module
            class SimpleDependencyManager(IDependencyManager):
                def __init__(self):
                    self.dependencies = {}
                
                def add_dependency(self, field_name, target_field, dependency_type="", validation_rule=None):
                    if field_name not in self.dependencies:
                        self.dependencies[field_name] = []
                    self.dependencies[field_name].append((target_field, dependency_type))
                
                def get_validation_order(self, fields):
                    # Simple implementation that doesn't do topological sorting
                    return list(fields)
                
                def validate_dependencies(self, data, field_name, adapters):
                    return []  # No validation errors by default
            
            self.dependency_manager = SimpleDependencyManager()
            
        service = ValidationService(self.dependency_manager, self.rule_loader)
        
        # Configure file cache size
        if hasattr(service._file_cache, 'set_max_size'):
            service._file_cache.set_max_size(self.cache_size)
            
        return service

# Factory method to create an instance from the configuration
def create_validation_service_from_config(config: Dict[str, Any]) -> IValidationService:
    """Create a ValidationService instance from configuration."""
    # Extract config from system.validation_service section if needed
    if isinstance(config, dict) and "config" in config:
        config = config["config"]
    
    # Get validation service configuration options
    strict_mode = config.get("strict_mode", False)
    cache_size = config.get("cache_size", 1000)
    parallel = config.get("parallel", True)
    max_errors = config.get("max_errors", 100)
    
    # Create dependency manager - needed for dependency validation
    from .field_dependencies import FieldDependencyManager
    dependency_manager = FieldDependencyManager()
    
    # Create rule loader if schema path is provided
    rule_loader = None
    if "schema_path" in config:
        from .validation_rules import ValidationRuleLoader
        rule_loader = ValidationRuleLoader(config["schema_path"])
    
    # If we have field dependencies defined in config, add them
    if isinstance(config, dict) and "field_dependencies" in config:
        for field_name, dependencies in config["field_dependencies"].items():
            for dep in dependencies:
                target_field = dep.get("target_field")
                dep_type = dep.get("type", "required")
                if target_field:
                    dependency_manager.add_dependency(
                        field_name=field_name,
                        target_field=target_field,
                        dependency_type=dep_type,
                        validation_rule=dep.get("validation_rule")
                    )
    
    # Create and configure validation service
    builder = ValidationServiceBuilder()
    return (builder
            .with_dependency_manager(dependency_manager)
            .with_rule_loader(rule_loader)
            .with_strict_mode(strict_mode)
            .with_cache_size(cache_size)
            .with_parallel_validation(parallel)
            .with_max_errors(max_errors)
            .build())