"""Enhanced validation module for USASpending data."""
from typing import Dict, Any, List, Optional, TYPE_CHECKING, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from decimal import Decimal
from datetime import date, datetime

from .validator import Validator, ValidationResult
from .field_dependencies import FieldDependencyManager
from .logging_config import get_logger

if TYPE_CHECKING:
    from .entity_store import EntityStore

logger = get_logger(__name__)


@dataclass
class ValidationGroup:
    """Represents a validation group configuration."""
    name: str
    rules: List[str]
    enabled: bool = True
    dependencies: List[str] = None
    error_level: str = "error"
    description: Optional[str] = None


class ValidationGroupManager:
    """Manages validation groups and their dependencies."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize validation group manager."""
        self.groups: Dict[str, ValidationGroup] = {}
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._init_groups(config.get('validation_groups', {}))
        self._check_circular_dependencies()
        
    def _init_groups(self, group_config: Dict[str, Any]) -> None:
        """Initialize validation groups from configuration."""
        for group_name, config in group_config.items():
            if not isinstance(config, dict):
                continue
                
            # Create group object
            group = ValidationGroup(
                name=config.get('name', group_name),
                rules=config.get('rules', []),
                enabled=config.get('enabled', True),
                dependencies=config.get('dependencies', []),
                error_level=config.get('error_level', 'error'),
                description=config.get('description')
            )
            
            self.groups[group_name] = group
            
            # Track dependencies
            if group.dependencies:
                for dep in group.dependencies:
                    self.dependencies[group_name].add(dep)
    
    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies in validation groups."""
        visited = set()
        path = []
        
        def detect_cycle(node: str) -> bool:
            """Detect cycle in graph using DFS."""
            if node in path:
                cycle = path[path.index(node):] + [node]
                logger.error(f"Circular dependency detected in validation groups: {' -> '.join(cycle)}")
                return True
                
            if node in visited:
                return False
                
            visited.add(node)
            path.append(node)
            
            for neighbor in self.dependencies.get(node, set()):
                if detect_cycle(neighbor):
                    return True
                    
            path.pop()
            return False
            
        # Check all groups
        for group_name in self.groups:
            if detect_cycle(group_name):
                raise ValueError(f"Circular dependency detected in validation groups involving: {group_name}")
    
    def get_group_rules(self, group_name: str) -> List[str]:
        """Get all validation rules for a group including dependencies."""
        if group_name not in self.groups:
            return []
            
        rules = set(self.groups[group_name].rules)
        for dep in self.dependencies.get(group_name, set()):
            rules.update(self.get_group_rules(dep))
            
        return list(rules)
    
    def is_group_enabled(self, group_name: str) -> bool:
        """Check if a validation group is enabled."""
        if group_name not in self.groups:
            return False
            
        # Check if group is enabled and all its dependencies are enabled
        if not self.groups[group_name].enabled:
            return False
            
        # Group is only enabled if all its dependencies are enabled
        for dep in self.dependencies.get(group_name, set()):
            if not self.is_group_enabled(dep):
                return False
                
        return True
    
    def get_group_error_level(self, group_name: str) -> str:
        """Get the error level for a validation group."""
        if group_name not in self.groups:
            return "error"
            
        return self.groups[group_name].error_level
        
    def get_all_enabled_groups(self) -> List[str]:
        """Get list of all enabled validation groups."""
        return [name for name, group in self.groups.items() if self.is_group_enabled(name)]


class ValidationEngine:
    """Enhanced validation engine with integrated data validation capabilities."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize validation engine with configuration."""
        self.config = config
        self.field_properties = config.get('field_properties', {})
        self.validator = Validator(self.field_properties)
        self.dependency_manager = FieldDependencyManager()
        self.group_manager = ValidationGroupManager(config)
        
        # Initialize field dependencies from config
        self._init_field_dependencies()
        
    def _init_field_dependencies(self) -> None:
        """Initialize field dependencies from configuration."""
        # Load dependencies from configuration
        self.dependency_manager.from_config(self.config)
        
        # Add dependencies from validation groups
        validation_groups = self.config.get('validation_groups', {})
        for group_name, group_config in validation_groups.items():
            if isinstance(group_config, dict):
                rules = group_config.get('rules', [])
                for rule in rules:
                    components = rule.split(':')
                    if len(components) >= 3 and components[0] == 'compare':
                        # Add dependency between compared fields
                        target_field = components[2]
                        # Find fields that belong to this group
                        for field_name, field_config in self.field_properties.items():
                            field_groups = field_config.get('validation', {}).get('groups', [])
                            if group_name in field_groups:
                                self.dependency_manager.add_dependency(
                                    field_name,
                                    target_field,
                                    'comparison',
                                    {'operator': components[1]}
                                )
        
        # Add additional dependencies from field comparisons
        self._add_comparison_dependencies()
        
    def _add_comparison_dependencies(self) -> None:
        """Add dependencies for field comparison rules."""
        for field_type, type_config in self.field_properties.items():
            if not isinstance(type_config, dict):
                continue
                
            for subtype, subtype_config in type_config.items():
                if not isinstance(subtype_config, dict):
                    continue
                    
                # Handle field comparison rules
                validation = subtype_config.get('validation', {})
                if validation.get('type') == 'field_comparison' and 'comparisons' in validation:
                    fields = subtype_config.get('fields', [])
                    
                    for comparison in validation['comparisons']:
                        operator = comparison.get('operator')
                        if not operator:
                            continue
                            
                        for field_pair in comparison.get('field_pairs', []):
                            field = field_pair.get('field')
                            compare_to = field_pair.get('compare_to')
                            
                            if field and compare_to and field in fields:
                                self.dependency_manager.add_dependency(
                                    field, 
                                    compare_to,
                                    'comparison',
                                    {'operator': operator}
                                )
    
    def validate_record(self, record: Dict[str, Any], 
                       stores: Optional[Dict[str, 'EntityStore']] = None) -> List[ValidationResult]:
        """Validate a complete record with dependency awareness."""
        results = []
        validated_fields: Set[str] = set()
        
        try:
            # Get validation order that respects dependencies
            validation_order = self.dependency_manager.get_validation_order()
            
            # First validate fields that have no dependencies
            independent_fields = set(record.keys()) - set(validation_order)
            for field_name in independent_fields:
                result = self.validate_field(field_name, record[field_name], record)
                if not result.valid:
                    results.append(result)
                validated_fields.add(field_name)
            
            # Then validate dependent fields in correct order
            for field_name in validation_order:
                if field_name not in record or field_name in validated_fields:
                    continue
                    
                # Check if all dependencies are validated
                deps = self.dependency_manager.get_dependencies(field_name)
                deps_ready = all(dep.target_field in validated_fields for dep in deps)
                
                if deps_ready:
                    result = self.validate_field(field_name, record[field_name], record)
                    if not result.valid:
                        results.append(result)
                    validated_fields.add(field_name)
                else:
                    logger.warning(f"Skipping validation of {field_name} due to unvalidated dependencies")
                    
        except ValueError as e:
            logger.error(f"Validation order error: {str(e)}")
            # Fall back to basic validation if dependency resolution fails
            return self.validator.validate_record(record)
            
        return results

    def _validate_field(self, field_name: str, value: Any, full_record: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a single field including any conditional rules."""
        field_config = self._get_field_config(field_name)
        validation = field_config.get('validation', {})
        
        # Check if there are conditional rules
        conditional_rules = validation.get('conditional_rules', {})
        if conditional_rules and full_record:
            for condition_field, condition_value in conditional_rules.items():
                if condition_field in full_record and str(full_record[condition_field]) == str(value):
                    pattern = condition_value.get('pattern')
                    if pattern and not re.match(pattern, str(full_record.get('payment_code', ''))):
                        return ValidationResult(
                            valid=False,
                            field_name=field_name,
                            error_message=condition_value.get('error_message', f'Invalid {field_name} format'),
                            error_type="conditional_validation_error"
                        )
        
        return ValidationResult(valid=True, field_name=field_name)

    def validate_field(self, field_name: str, value: Any, 
                      full_record: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a single field value with dependency awareness."""
        # First do basic field validation
        result = self.validator.validate_field(field_name, value)
        if not result.valid:
            return result
            
        # Validate conditional rules
        if full_record:
            result = self._validate_field(field_name, value, full_record)
            if not result.valid:
                return result
            
            # Get field properties
            field_config = self._get_field_config(field_name)
            
            # Check if field belongs to any validation groups
            groups = field_config.get('validation', {}).get('groups', [])
            if groups:
                group_result = self._validate_field_groups(field_name, value, full_record, groups)
                if not group_result.valid:
                    return group_result
                    
            # Check direct dependencies
            if field_name in self.dependency_manager.dependencies:
                dep_result = self._validate_field_dependencies(field_name, value, full_record)
                if not dep_result.valid:
                    return dep_result
            
        return ValidationResult(valid=True, field_name=field_name)
    
    def _validate_field_groups(self, field_name: str, value: Any, 
                             record: Dict[str, Any], groups: List[str]) -> ValidationResult:
        """Validate a field according to its validation groups."""
        for group_name in groups:
            if not self.group_manager.is_group_enabled(group_name):
                continue
                
            # Get all rules from this group and its dependencies
            rules = self.group_manager.get_group_rules(group_name)
            
            for rule in rules:
                result = self._apply_validation_rule(field_name, value, record, rule)
                if not result.valid:
                    # Set error level based on group configuration
                    error_level = self.group_manager.get_group_error_level(group_name)
                    result.error_level = error_level
                    return result
                    
        return ValidationResult(valid=True, field_name=field_name)
    
    def _validate_field_dependencies(self, field_name: str, value: Any, 
                                   record: Dict[str, Any]) -> ValidationResult:
        """Validate a field's dependencies."""
        for dep in self.dependency_manager.get_dependencies(field_name):
            if dep.target_field not in record:
                continue
                
            target_value = record[dep.target_field]
            
            if dep.dependency_type == 'comparison' and dep.validation_rule:
                result = self._validate_comparison(
                    field_name, value,
                    dep.target_field, target_value,
                    dep.validation_rule['operator']
                )
                if not result.valid:
                    return result
                    
        return ValidationResult(valid=True, field_name=field_name)
    
    def _apply_validation_rule(self, field_name: str, value: Any, 
                             record: Dict[str, Any], rule: str) -> ValidationResult:
        """Apply a validation rule to a field value."""
        # Split rule into components (e.g., "compare:less_than:target_field")
        components = rule.split(':')
        if not components:
            return ValidationResult(valid=True, field_name=field_name)
            
        rule_type = components[0]
        
        if rule_type == 'compare':
            if len(components) >= 3:
                operator = components[1]
                target_field = components[2]
                
                if target_field in record:
                    return self._validate_comparison(
                        field_name, value,
                        target_field, record[target_field],
                        operator
                    )
                    
        elif rule_type == 'condition':
            if len(components) >= 4:
                condition_field = components[1]
                condition_value = components[2]
                condition_action = components[3]
                
                # Check if condition is met
                if condition_field in record and str(record[condition_field]) == condition_value:
                    if condition_action == 'require' and len(components) >= 5:
                        required_field = components[4]
                        # Check if required field is present and not empty
                        if required_field not in record or not record[required_field]:
                            return ValidationResult(
                                valid=False,
                                field_name=required_field,
                                error_message=f"Field {required_field} is required when {condition_field} is {condition_value}",
                                error_type="conditional_required_field"
                            )
                            
        return ValidationResult(valid=True, field_name=field_name)
    
    def _validate_comparison(self, field_name: str, value: Any,
                           target_field: str, target_value: Any,
                           operator: str) -> ValidationResult:
        """Validate a field comparison."""
        try:
            if field_name == target_field:
                # Skip self-comparisons
                return ValidationResult(valid=True, field_name=field_name)
                
            if operator == 'less_than' and not value < target_value:
                return ValidationResult(
                    valid=False,
                    field_name=field_name,
                    error_message=f"{field_name} must be less than {target_field}",
                    error_type="comparison_error"
                )
                
            elif operator == 'less_than_equal' and not value <= target_value:
                return ValidationResult(
                    valid=False,
                    field_name=field_name,
                    error_message=f"{field_name} must be less than or equal to {target_field}",
                    error_type="comparison_error"
                )
                
            elif operator == 'greater_than' and not value > target_value:
                return ValidationResult(
                    valid=False,
                    field_name=field_name,
                    error_message=f"{field_name} must be greater than {target_field}",
                    error_type="comparison_error"
                )
                
            elif operator == 'greater_than_equal' and not value >= target_value:
                return ValidationResult(
                    valid=False,
                    field_name=field_name,
                    error_message=f"{field_name} must be greater than or equal to {target_field}",
                    error_type="comparison_error"
                )
                
            elif operator == 'equal' and value != target_value:
                return ValidationResult(
                    valid=False,
                    field_name=field_name,
                    error_message=f"{field_name} must equal {target_field}",
                    error_type="comparison_error"
                )
                
            elif operator == 'not_equal' and value == target_value:
                return ValidationResult(
                    valid=False,
                    field_name=field_name,
                    error_message=f"{field_name} must not equal {target_field}",
                    error_type="comparison_error"
                )
                
            return ValidationResult(valid=True, field_name=field_name)
            
        except TypeError as e:
            logger.warning(f"Type error during comparison validation: {str(e)}")
            return ValidationResult(
                valid=False,
                field_name=field_name,
                error_message=f"Cannot compare {field_name} with {target_field}: {str(e)}",
                error_type="comparison_type_error"
            )
    
    def _get_field_config(self, field_name: str) -> Dict[str, Any]:
        """Get configuration for a field from field_properties."""
        # First check direct field properties
        if field_name in self.field_properties:
            return self.field_properties[field_name]
            
        # Check pattern-based field properties
        for field_type, type_config in self.field_properties.items():
            if not isinstance(type_config, dict):
                continue
                
            for subtype, subtype_config in type_config.items():
                if not isinstance(subtype_config, dict):
                    continue
                    
                fields = subtype_config.get('fields', [])
                if isinstance(fields, list) and field_name in fields:
                    return subtype_config
                    
        return {}
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get current validation statistics."""
        return self.validator.get_statistics()

    def log_validation_stats(self) -> None:
        """Log validation and cache statistics."""
        self.validator.log_statistics()

    def clear_cache(self) -> None:
        """Clear the validation cache."""
        self.validator.clear_cache()

    def get_validation_order(self) -> List[str]:
        """Get fields in dependency order for validation."""
        if not hasattr(self, 'dependency_manager') or not self.dependency_manager:
            # Ensure default fields are included
            return list(self.field_properties.keys())
            
        # Get order from dependency manager, ensuring all fields are included
        order = self.dependency_manager.get_validation_order()
        
        # Add any missing fields at the end
        for field in self.field_properties:
            if field not in order:
                order.append(field)
                
        return order