"""Enhanced validation module for USASpending data."""
from typing import Dict, Any, List, Optional, TYPE_CHECKING, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from decimal import Decimal
from datetime import date, datetime
import re  # Added missing import for regex pattern matching
import collections

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
        self.validators = {}  # Initialize validators dictionary
        
        # Initialize field dependencies from config
        self._init_field_dependencies()
        
    def _init_field_dependencies(self) -> None:
        """Initialize field dependencies from configuration."""
        # Clear existing dependencies
        self.dependency_manager.clear_dependencies()
        
        # Load dependencies from field properties
        for field_name, config in self.field_properties.items():
            if not isinstance(config, dict):
                continue
                
            validation = config.get('validation', {})
            
            # Add explicit dependencies
            dependencies = validation.get('dependencies', [])
            for dep in dependencies:
                if isinstance(dep, dict) and 'target_field' in dep:
                    self.dependency_manager.add_dependency(
                        field_name,
                        dep['target_field'],
                        dep.get('type', 'validation'),
                        dep.get('validation_rule', {})
                    )

            # Add group-based dependencies
            groups = validation.get('groups', [])
            for group_name in groups:
                if group_name in self.group_manager.groups:
                    group = self.group_manager.groups[group_name]
                    for rule in group.rules:
                        if ':' in rule:
                            components = rule.split(':')
                            if len(components) >= 3 and components[0] == 'compare':
                                target_field = components[2]
                                # Add bidirectional dependency for comparisons
                                self.dependency_manager.add_dependency(
                                    field_name,
                                    target_field,
                                    'comparison',
                                    {'operator': components[1], 'bidirectional': True}
                                )
                                self.dependency_manager.add_dependency(
                                    target_field,
                                    field_name,
                                    'comparison',
                                    {'operator': components[1], 'bidirectional': True}
                                )
                        
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
    
    def update_field_dependencies(self):
        """Update field dependencies after configuration changes."""
        self._init_field_dependencies()
    
    def validate_record(self, record: Dict[str, Any]) -> List[ValidationResult]:
        """Validate a record, handling circular dependencies."""
        # Update dependencies first in case config changed
        self.update_field_dependencies()
        
        # Track validation results
        results = []
        
        # Get fields to validate
        fields_to_validate = list(record.keys())
        
        # Initialize tracking of validation attempts
        processed_fields = set()
        field_defer_counts = {}
        max_deferrals = len(fields_to_validate) + 1  # Allow N+1 deferrals before assuming a cycle
        
        # Process fields in dependency order if possible
        validation_order = self.get_validation_order()
        
        # Reorder fields to validate based on dependencies
        ordered_fields = []
        for field in validation_order:
            if field in fields_to_validate:
                ordered_fields.append(field)
        
        # Add any remaining fields not in the validation order
        for field in fields_to_validate:
            if field not in ordered_fields:
                ordered_fields.append(field)
        
        # Use a queue for processing fields
        fields_queue = collections.deque(ordered_fields)
        
        while fields_queue:
            field_name = fields_queue.popleft()
            
            # Skip already processed fields
            if field_name in processed_fields:
                continue
                
            # Get unvalidated dependencies
            unvalidated_dependencies = self._get_unvalidated_dependencies(field_name, record)
            
            if unvalidated_dependencies:
                # Track how many times this field has been deferred
                field_defer_counts[field_name] = field_defer_counts.get(field_name, 0) + 1
                
                # If we've deferred this field too many times, we're in a cycle
                if field_defer_counts[field_name] > max_deferrals:
                    # Force validation despite circular dependency
                    result = self._validate_field(field_name, record.get(field_name), record)
                    if not result.valid:
                        results.append(result)
                    processed_fields.add(field_name)
                else:
                    # Move dependencies to front of queue
                    for dep in reversed(unvalidated_dependencies):
                        if dep in fields_queue:
                            fields_queue.remove(dep)
                        fields_queue.appendleft(dep)
                    
                    # Move current field to end
                    fields_queue.append(field_name)
            else:
                # No dependencies or all are validated, proceed with validation
                result = self._validate_field(field_name, record.get(field_name), record)
                if not result.valid:
                    results.append(result)
                processed_fields.add(field_name)
                
        return results

    def _force_validate_in_cycle(self, field_name, record, circular_dependencies):
        """Break circular dependency by validating the field with current values."""
        # Log the circular dependency
        logger.warning(
            f"Circular dependency detected for field '{field_name}' with dependencies: {circular_dependencies}. "
            f"Forcing validation with current values."
        )

    def _validate_field(self, field_name: str, value: Any, full_record: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a single field including any conditional rules."""
        field_config = self._get_field_config(field_name)
        validation = field_config.get('validation', {})
        
        # First do basic field validation
        result = self.validator.validate_field(field_name, value)
        if not result.valid:
            return result
        
        # Check if there are conditional rules
        conditional_rules = validation.get('conditional_rules', {})
        if conditional_rules and full_record:
            payment_type = full_record.get('payment_type')
            payment_code = full_record.get('payment_code')
            
            if payment_type and payment_code and payment_type in conditional_rules:
                rule_config = conditional_rules[payment_type]
                pattern = rule_config.get('pattern')
                
                if pattern and not re.match(pattern, str(payment_code)):
                    return ValidationResult(
                        valid=False,
                        field_name='payment_code',
                        error_message=rule_config.get('error_message', f'Invalid payment code format for {payment_type}'),
                        error_type="conditional_validation_error"
                    )
        
        # Validate groups
        groups = validation.get('groups', [])
        if groups and full_record:
            for group_name in groups:
                if self.group_manager.is_group_enabled(group_name):
                    group_result = self._validate_field_groups(field_name, value, full_record, [group_name])
                    if not group_result.valid:
                        return group_result
        
        # Validate field dependencies
        if hasattr(self.dependency_manager, "get_dependencies"):
            deps = self.dependency_manager.get_dependencies(field_name)
            if deps and full_record:
                for dep in deps:
                    target_field = dep
                    # Handle different return types
                    if hasattr(dep, "target_field"):
                        target_field = dep.target_field
                        
                    if target_field in full_record:
                        dep_result = self._validate_field_dependencies(field_name, value, full_record)
                        if not dep_result.valid:
                            return dep_result
        
        return ValidationResult(valid=True, field_name=field_name)

    def validate_field(self, field_name: str, value: Any, 
                      full_record: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a single field value with dependency awareness."""
        return self._validate_field(field_name, value, full_record)
    
    def _validate_field_groups(self, field_name: str, value: Any, 
                             record: Dict[str, Any], groups: List[str]) -> ValidationResult:
        """Validate a field according to its validation groups."""
        all_dependencies = set()
        
        for group_name in groups:
            if not self.group_manager.is_group_enabled(group_name):
                continue
                
            # Get all rules from this group and its dependencies
            rules = self.group_manager.get_group_rules(group_name)
            
            for rule in rules:
                # Track dependencies before validation
                components = rule.split(':')
                if len(components) >= 3 and components[0] == 'compare':
                    target_field = components[2]
                    all_dependencies.add(target_field)
                
                result = self._apply_validation_rule(field_name, value, record, rule)
                if not result.valid:
                    # Set error level based on group configuration
                    error_level = self.group_manager.get_group_error_level(group_name)
                    result.error_level = error_level
                    return result
        
        # Add all discovered dependencies to the dependency manager
        for dep_field in all_dependencies:
            if dep_field != field_name:  # Avoid self-dependencies
                self.dependency_manager.add_dependency(
                    field_name,
                    dep_field,
                    'group_validation',
                    {'bidirectional': True}
                )
                    
        return ValidationResult(valid=True, field_name=field_name)
    
    def _validate_field_dependencies(self, field_name: str, value: Any, 
                                   record: Dict[str, Any]) -> ValidationResult:
        """Validate a field's dependencies."""
        deps = []
        
        # Handle different implementations of get_dependencies
        if hasattr(self.dependency_manager, "get_dependencies"):
            deps = self.dependency_manager.get_dependencies(field_name)
        
        for dep in deps:
            target_field = dep
            validation_rule = {}
            dependency_type = ""
            
            # Handle different return types
            if hasattr(dep, "target_field"):
                target_field = dep.target_field
                validation_rule = getattr(dep, "validation_rule", {})
                dependency_type = getattr(dep, "dependency_type", "")
            
            if target_field not in record:
                continue
                
            target_value = record[target_field]
            
            if dependency_type == 'comparison' and validation_rule and 'operator' in validation_rule:
                result = self._validate_comparison(
                    field_name, value,
                    target_field, target_value,
                    validation_rule['operator']
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

            # Ensure types are compatible for comparison
            if type(value) != type(target_value):
                raise TypeError(f"Cannot compare {field_name} with {target_field}: incompatible types {type(value)} and {type(target_value)}")

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
            
        # Check type-specific field properties
        for field_type, type_config in self.field_properties.items():
            if not isinstance(type_config, dict):
                continue
                
            # Check numeric fields
            if field_type == 'numeric':
                for subtype in ('money', 'integer', 'decimal'):
                    if subtype in type_config:
                        subtype_config = type_config[subtype]
                        if field_name in subtype_config.get('fields', []):
                            return subtype_config
                            
            # Check string fields
            elif field_type == 'string':
                for subtype in ('agency_code', 'uei', 'naics', 'psc', 'zip_code', 'phone', 'state_code', 'country_code'):
                    if subtype in type_config:
                        subtype_config = type_config[subtype]
                        if field_name in subtype_config.get('fields', []):
                            return subtype_config
                            
            # Check date fields
            elif field_type == 'date':
                for subtype in ('standard', 'not_future'):
                    if subtype in type_config:
                        subtype_config = type_config[subtype]
                        if field_name in subtype_config.get('fields', []):
                            return subtype_config
                            
            # Check boolean fields
            elif field_type == 'boolean':
                if 'standard' in type_config:
                    subtype_config = type_config['standard']
                    if field_name in subtype_config.get('fields', []):
                        return subtype_config
                        
            # Check enum fields
            elif field_type == 'enum':
                for subtype in ('contract_type', 'idv_type', 'action_type', 'contract_pricing', 'yes_no_extended'):
                    if subtype in type_config:
                        subtype_config = type_config[subtype]
                        if field_name in subtype_config.get('fields', []):
                            return subtype_config
                            
            # Check derived fields
            elif field_type == 'derived':
                if 'fiscal_year' in type_config:
                    subtype_config = type_config['fiscal_year']
                    if field_name in subtype_config.get('fields', []):
                        return subtype_config
                        
            # Check pattern-based fields for any other type
            else:
                for subtype, subtype_config in type_config.items():
                    if not isinstance(subtype_config, dict):
                        continue
                        
                    fields = subtype_config.get('fields', [])
                    if isinstance(fields, list):
                        # Check exact match
                        if field_name in fields:
                            return subtype_config
                            
                        # Check pattern match
                        for pattern in fields:
                            if '*' in pattern:
                                pattern_regex = pattern.replace('*', '.*')
                                if re.match(pattern_regex, field_name):
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
        all_fields = set()
        
        # Add fields from field properties
        all_fields.update(self.field_properties.keys())
        
        # Add fields from validation groups
        for group in self.group_manager.groups.values():
            for rule in group.rules:
                components = rule.split(':')
                if len(components) >= 3:
                    all_fields.add(components[2])  # Add target field
        
        # Get ordered list from dependency manager
        if hasattr(self.dependency_manager, 'get_validation_order'):
            order = self.dependency_manager.get_validation_order()
            
            # Add any remaining fields that aren't in the dependency order
            for field in all_fields:
                if field not in order:
                    order.append(field)
            return order
            
        # If dependency manager doesn't have proper method, return all fields
        return list(all_fields)

    def _get_unvalidated_dependencies(self, field_name: str, record: Dict[str, Any]) -> List[str]:
        """Get list of unvalidated dependencies for a field.
        
        Args:
            field_name: The field to check dependencies for
            record: The record being validated
            
        Returns:
            List of field names that need validation
        """
        unvalidated = []
        deps = []
        
        if hasattr(self.dependency_manager, "get_dependencies"):
            deps = self.dependency_manager.get_dependencies(field_name)
            
        for dep in deps:
            target_field = dep
            # Handle different return types
            if hasattr(dep, "target_field"):
                target_field = dep.target_field
            elif isinstance(dep, dict) and 'target' in dep:
                target_field = dep['target']
                
            # Skip if validator doesn't exist
            if target_field not in self.validators:
                continue
                
            try:
                # Check if field is validated
                validator = self.validators[target_field]
                if not validator.is_validated(record):
                    unvalidated.append(target_field)
            except Exception as e:
                # Skip dependencies that raise exceptions during validation check
                logger.warning(f"Error checking validation status for {target_field}: {str(e)}")
                continue
                
        return unvalidated