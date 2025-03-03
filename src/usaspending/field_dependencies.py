"""Field dependency management and validation ordering."""
from typing import Dict, Set, List, Any, Optional, Tuple, FrozenSet, Union
from collections import defaultdict
from functools import lru_cache

from .logging_config import get_logger

logger = get_logger(__name__)


class FieldDependency:
    def __init__(self, field_name: str, target_field: Union[str, Tuple[str, ...]], dependency_type: str, 
                 validation_rule=None):
        """Initialize field dependency.
        
        Args:
            field_name: Name of the field that has the dependency
            target_field: Name of the field this depends on, or tuple of fields for multi-dependencies
            dependency_type: Type of dependency
            validation_rule: Optional validation rules
        """
        self.field_name = field_name
        
        # Handle target_field consistently, always storing as a tuple
        if isinstance(target_field, (tuple, list)):
            self.dependencies = tuple(target_field)  # Convert to tuple to ensure it's immutable
            self.target_field = self.dependencies[0] if self.dependencies else None
        else:
            self.target_field = target_field
            self.dependencies = (target_field,)
            
        self.dependency_type = dependency_type
        
        # Store validation_rule as a dictionary, not as a frozen set
        self.validation_rule = None if validation_rule is None else dict(validation_rule)
        
    def __eq__(self, other):
        if not isinstance(other, FieldDependency):
            return False
        return (self.field_name == other.field_name and 
                self.dependencies == other.dependencies and
                self.dependency_type == other.dependency_type)
                
    def __hash__(self):
        # Make hashable by using only immutable attributes
        # Don't include validation_rule in hash calculation since it might be a dict
        return hash((self.field_name, self.dependencies, self.dependency_type))


class FieldDependencyManager:
    """Manages field dependencies and validation ordering."""

    def __init__(self):
        """Initialize field dependency manager."""
        self.dependencies: Dict[str, Set[FieldDependency]] = defaultdict(set)
        self.reverse_deps: Dict[str, Set[str]] = defaultdict(set)
        self._validation_order: List[str] = []
        
    def add_dependency(self, source_field: str, target_field: str, dependency_type: str,
                      validation_rule: Optional[Dict[str, Any]] = None,
                      allow_self_reference: bool = False) -> None:
        """
        Add a dependency between two fields.
        
        Args:
            source_field: The dependent field (that relies on the target)
            target_field: The field that the source depends on
            dependency_type: Type of dependency (e.g., 'calculation', 'validation')
            validation_rule: Optional validation rules for this dependency
            allow_self_reference: If True, allows a field to depend on itself
        """
        # Skip adding self-references unless explicitly allowed
        if source_field == target_field and not allow_self_reference:
            logger.debug(f"Skipping self-reference dependency for field: {source_field}")
            return
        
        # Check for bidirectional dependencies (like start_date<->end_date)
        # For date validation, it's common to have bidirectional constraints
        # We'll tag these as bidirectional and handle them specially
        is_bidirectional = False
        if target_field in self.dependencies and any(
            dep.target_field == source_field for dep in self.dependencies[target_field]
        ):
            is_bidirectional = True
            # For validation dependencies like date comparisons, mark as bidirectional
            # instead of creating circular dependencies
            if dependency_type in ['comparison', 'validation']:
                logger.info(f"Bidirectional relationship detected between {source_field} and {target_field}")
                # Add metadata to validation rule to indicate bidirectional relationship
                if validation_rule is None:
                    validation_rule = {}
                validation_rule['bidirectional'] = True
            
        # Create dependency object
        dependency = FieldDependency(
            field_name=source_field,
            target_field=target_field,
            dependency_type=dependency_type,
            validation_rule=validation_rule
        )
        
        # Add to dependencies collection
        if source_field not in self.dependencies:
            self.dependencies[source_field] = set()
        self.dependencies[source_field].add(dependency)
        
        # Add to reverse dependency mapping
        if target_field not in self.reverse_deps:
            self.reverse_deps[target_field] = set()
        self.reverse_deps[target_field].add(source_field)
        
        # Reset cached validation order
        self._validation_order = []
        self.has_circular_dependency.cache_clear()
        
    def get_dependencies(self, field: str) -> Set[FieldDependency]:
        """Get all dependencies for a field."""
        return self.dependencies[field]
        
    def get_dependent_fields(self, field: str) -> Set[str]:
        """Get fields that depend on this field."""
        return self.reverse_deps[field]
        
    @lru_cache(maxsize=1024)
    def has_circular_dependency(self, field: str, visited: Optional[FrozenSet[str]] = None) -> bool:
        """Check for circular dependencies.
        
        Args:
            field: The field to check
            visited: Set of fields already visited in the current path
            
        Returns:
            True if a circular dependency is detected, False otherwise
        """
        if visited is None:
            visited = frozenset()
        
        if field in visited:
            cycle_path = " -> ".join(list(visited) + [field])
            logger.warning(f"Circular dependency detected: {cycle_path}")
            return True
            
        new_visited = visited | {field}
        
        # Check if any target fields create a cycle
        return any(
            self.has_circular_dependency(dep.target_field, new_visited)
            for dep in self.dependencies[field]
        )
        
    def get_validation_order(self) -> List[str]:
        """Get ordered list of fields for validation.
        
        Returns:
            List of field names in dependency order (fields with no dependencies first)
        """
        if not self._validation_order:
            try:
                self._compute_validation_order()
            except ValueError as e:
                logger.error(f"Error computing validation order: {str(e)}")
                # Fall back to a simple order that ignores circular dependencies
                self._compute_fallback_order()
        return self._validation_order

    def _compute_validation_order(self) -> None:
        """Compute field validation order using topological sort."""
        visited: Set[str] = set()
        temp_mark: Set[str] = set()
        order: List[str] = []

        def visit(field: str) -> None:
            """Recursive function for topological sort."""
            if field in temp_mark:
                # Check if this is a bidirectional dependency before raising error
                cycle_fields = list(temp_mark) + [field]
                is_bidirectional = False

                for i in range(len(cycle_fields) - 1):
                    current = cycle_fields[i]
                    next_field = cycle_fields[i + 1]

                    # Check if there's a bidirectional relationship
                    if current in self.dependencies and next_field in self.dependencies:
                        current_deps = self.dependencies[current]
                        next_deps = self.dependencies[next_field]

                        # Look for matching bidirectional dependencies
                        current_to_next = next(
                            (dep for dep in current_deps 
                             if dep.target_field == next_field 
                             and dep.validation_rule 
                             and dep.validation_rule.get('bidirectional')), 
                            None
                        )
                        next_to_current = next(
                            (dep for dep in next_deps 
                             if dep.target_field == current 
                             and dep.validation_rule 
                             and dep.validation_rule.get('bidirectional')), 
                            None
                        )

                        if current_to_next and next_to_current:
                            is_bidirectional = True
                            break

                if not is_bidirectional:
                    cycle_path = " -> ".join(cycle_fields)
                    logger.error(f"Circular dependency detected: {cycle_path}")
                    raise ValueError(f"Circular dependency detected involving field: {field}")
                else:
                    logger.debug(f"Bidirectional relationship detected in dependency chain, continuing")
                    return

            if field in visited:
                return

            temp_mark.add(field)

            # Visit target fields first (dependencies)
            for dep in self.dependencies[field]:
                # Skip visiting target if it's a bidirectional relationship
                if not (dep.validation_rule and dep.validation_rule.get('bidirectional')):
                    visit(dep.target_field)

            temp_mark.remove(field)
            visited.add(field)
            order.append(field)

        # Start with fields that have dependencies
        all_fields = set(self.dependencies.keys()) | set(self.reverse_deps.keys())

        # Process non-bidirectional fields first
        bidirectional_fields = set()
        for field in all_fields:
            if field not in visited:
                # Check if field has any bidirectional dependencies
                has_bidirectional = False
                if field in self.dependencies:
                    has_bidirectional = any(
                        dep.validation_rule and dep.validation_rule.get('bidirectional')
                        for dep in self.dependencies[field]
                    )
                if has_bidirectional:
                    bidirectional_fields.add(field)
                else:
                    visit(field)

        # Then process bidirectional fields
        for field in bidirectional_fields:
            if field not in visited:
                visit(field)

        self._validation_order = order
        
    def _compute_fallback_order(self) -> None:
        """Compute a simple validation order that ignores circular dependencies.
        This is used as a fallback when topological sort fails due to cycles.
        """
        # Start with fields that have no outgoing dependencies
        all_fields = set(self.dependencies.keys()) | set(self.reverse_deps.keys())
        dependency_count = {field: len(self.dependencies[field]) for field in all_fields}
        
        # Sort by dependency count (fewest dependencies first)
        self._validation_order = sorted(all_fields, key=lambda f: dependency_count[f])
        logger.warning(f"Using fallback validation order due to circular dependencies: {self._validation_order}")
        
    def _invalidate_order(self) -> None:
        """Invalidate cached validation order."""
        self._validation_order = []
        self.has_circular_dependency.cache_clear()
        
    def get_dependency_graph(self) -> Dict[str, List[Tuple[str, str]]]:
        """Get a dictionary representation of the dependency graph.
        
        Returns:
            Dictionary with field names as keys and lists of (target_field, dependency_type) as values
        """
        graph = defaultdict(list)
        for source, deps in self.dependencies.items():
            for dep in deps:
                graph[source].append((dep.target_field, dep.dependency_type))
        return dict(graph)
    
    def from_config(self, config: Dict[str, Any]) -> None:
        """Initialize dependencies from configuration.
        
        Args:
            config: Configuration dictionary with field_dependencies section
        """
        # Process direct field dependencies
        if 'field_dependencies' in config:
            field_deps = config['field_dependencies']
            if isinstance(field_deps, dict):
                for field_name, deps in field_deps.items():
                    if isinstance(deps, list):
                        for dep in deps:
                            if isinstance(dep, dict) and 'target_field' in dep and 'type' in dep:
                                self.add_dependency(
                                    field_name,
                                    dep['target_field'],
                                    dep['type'],
                                    dep.get('validation_rule')
                                )
        
        # Process field properties for additional dependencies
        if 'field_properties' in config:
            self._process_field_properties(config['field_properties'])
        
        # Process validation groups
        if 'validation_groups' in config:
            for group_name, group_config in config['validation_groups'].items():
                if isinstance(group_config, dict):
                    # Handle group dependencies
                    if 'rules' in group_config:
                        for rule in group_config['rules']:
                            # Parse comparison rules (format: compare:operator:target_field)
                            if isinstance(rule, str):
                                components = rule.split(':')
                                if len(components) >= 3 and components[0] == 'compare':
                                    operator = components[1]
                                    target_field = components[2]
                                    # Find fields that belong to this group
                                    if 'field_properties' in config:
                                        for field_name, props in config['field_properties'].items():
                                            if isinstance(props, dict):
                                                validation = props.get('validation', {})
                                                if group_name in validation.get('groups', []):
                                                    self.add_dependency(
                                                        field_name,
                                                        target_field,
                                                        'comparison',
                                                        {'operator': operator, 'bidirectional': True}
                                                    )
                    
    def _process_field_properties(self, field_properties: Dict[str, Any]) -> None:
        """Process field properties section for dependencies."""
        for field_name, props in field_properties.items():
            if not isinstance(props, dict):
                continue
                
            # Process validation dependencies
            validation = props.get('validation', {})
            if validation:
                # Handle explicit dependencies
                dependencies = validation.get('dependencies', [])
                if isinstance(dependencies, list):
                    for dep in dependencies:
                        if isinstance(dep, dict) and 'target_field' in dep and 'type' in dep:
                            self.add_dependency(
                                field_name,
                                dep['target_field'],
                                dep['type'],
                                dep.get('validation_rule')
                            )
                
                # Handle validation groups
                groups = validation.get('groups', [])
                if isinstance(groups, list):
                    for group in groups:
                        self.add_dependency(
                            field_name,
                            f"group:{group}",  # Special prefix for group dependencies
                            'group_validation',
                            {'group': group}
                        )
                    
            # Process transformation dependencies
            transform = props.get('transformation', {})
            if transform:
                # Handle both direct transformation type and operations list
                if 'type' in transform:
                    source_field = transform.get('source_field')
                    if source_field:
                        self.add_dependency(field_name, source_field, 'derived')
                
                operations = transform.get('operations', [])
                for op in operations:
                    if isinstance(op, dict):
                        source_field = op.get('source_field')
                        if source_field:
                            self.add_dependency(field_name, source_field, 'derived')
                        elif op.get('type') == 'derive_fiscal_year' and 'source_field' in op:
                            self.add_dependency(field_name, op['source_field'], 'derived')
                        elif op.get('type') == 'derive_date_components' and 'source_field' in op:
                            self.add_dependency(field_name, op['source_field'], 'derived')

    def remove_dependency(self, source_field: str, target_field: str, dependency_type: str) -> None:
        """
        Remove a dependency between two fields.
        
        Args:
            source_field: The dependent field (that relies on the target)
            target_field: The field that the source depends on
            dependency_type: Type of dependency (e.g., 'calculation', 'validation')
        """
        # Find and remove the dependency from the source field's dependencies
        if source_field in self.dependencies:
            to_remove = None
            for dep in self.dependencies[source_field]:
                if dep.target_field == target_field and dep.dependency_type == dependency_type:
                    to_remove = dep
                    break
                    
            if to_remove:
                self.dependencies[source_field].remove(to_remove)
                
                # Also update the reverse dependency mapping
                if target_field in self.reverse_deps and source_field in self.reverse_deps[target_field]:
                    self.reverse_deps[target_field].remove(source_field)
                    
                    # Clean up empty sets
                    if not self.reverse_deps[target_field]:
                        del self.reverse_deps[target_field]
                
                # Clean up empty sets
                if not self.dependencies[source_field]:
                    del self.dependencies[source_field]
                    
        # Reset cached validation order and dependency cache
        self._validation_order = []  
        self.has_circular_dependency.cache_clear()

    def clear_dependencies(self) -> None:
        """Clear all dependencies and cached data."""
        self.dependencies.clear()
        self.reverse_deps.clear()
        self._validation_order.clear()
        self.has_circular_dependency.cache_clear()