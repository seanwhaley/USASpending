"""Field dependency management and validation ordering."""
from typing import Dict, Set, List, Any, Optional, Tuple, FrozenSet
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from .logging_config import get_logger

logger = get_logger(__name__)


class FieldDependency:
    def __init__(self, field_name: str, target_field: str, dependency_type: str, 
                 validation_rule=None):
        self.field_name = field_name
        self.target_field = target_field
        self.dependency_type = dependency_type
        
        # Store validation_rule as a dictionary, not a frozenset
        self.validation_rule = validation_rule if validation_rule is None else dict(validation_rule)
        
    def __eq__(self, other):
        if not isinstance(other, FieldDependency):
            return False
        return (self.field_name == other.field_name and 
                self.target_field == other.target_field and
                self.dependency_type == other.dependency_type)
                
    def __hash__(self):
        # Make hashable by using only immutable attributes
        return hash((self.field_name, self.target_field, self.dependency_type))


class FieldDependencyManager:
    """Manages field dependencies and validation ordering."""

    def __init__(self):
        """Initialize field dependency manager."""
        self.dependencies: Dict[str, Set[FieldDependency]] = defaultdict(set)
        self.reverse_deps: Dict[str, Set[str]] = defaultdict(set)
        self.validation_order: List[str] = []
        
    def add_dependency(self, source: str, target: str, dep_type: str, 
                      validation: Optional[Dict[str, Any]] = None) -> None:
        """Add a field dependency.
        
        Args:
            source: The field that depends on the target
            target: The field that the source depends on
            dep_type: Type of dependency (comparison, derived, etc.)
            validation: Optional validation rule for the dependency
        """
        dep = FieldDependency(source, target, dep_type, validation)
        self.dependencies[source].add(dep)
        self.reverse_deps[target].add(source)
        self._invalidate_order()
        
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
            logger.warning(f"Circular dependency detected involving field: {field}")
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
        if not self.validation_order:
            self._compute_validation_order()
        return self.validation_order
        
    def _compute_validation_order(self) -> None:
        """Compute field validation order using topological sort."""
        visited: Set[str] = set()
        temp_mark: Set[str] = set()
        order: List[str] = []
        
        def visit(field: str) -> None:
            """Recursive function for topological sort."""
            if field in temp_mark:
                cycle_path = " -> ".join(list(temp_mark) + [field])
                logger.error(f"Circular dependency detected: {cycle_path}")
                raise ValueError(f"Circular dependency detected involving field: {field}")
                
            if field in visited:
                return
                
            temp_mark.add(field)
            
            # Visit target fields first (dependencies)
            for dep in self.dependencies[field]:
                visit(dep.target_field)
                
            temp_mark.remove(field)
            visited.add(field)
            order.append(field)
        
        # Start with fields that have dependencies
        all_fields = set(self.dependencies.keys()) | set(self.reverse_deps.keys())
        for field in all_fields:
            if field not in visited:
                visit(field)
                
        self.validation_order = order
        
    def _invalidate_order(self) -> None:
        """Invalidate cached validation order."""
        self.validation_order = []
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
        if 'field_dependencies' not in config:
            return
            
        field_deps = config['field_dependencies']
        for field_name, deps in field_deps.items():
            for dep in deps:
                if 'target_field' in dep and 'type' in dep:
                    self.add_dependency(
                        field_name,
                        dep['target_field'],
                        dep['type'],
                        dep.get('validation_rule')
                    )
        
        # Also check field_properties for dependencies
        if 'field_properties' in config:
            self._process_field_properties(config['field_properties'])
                    
    def _process_field_properties(self, field_properties: Dict[str, Any]) -> None:
        """Process field properties section for dependencies.
        
        Args:
            field_properties: Field properties configuration section
        """
        for field_name, props in field_properties.items():
            if not isinstance(props, dict):
                continue
                
            # Process validation dependencies
            validation = props.get('validation', {})
            if validation:
                dependencies = validation.get('dependencies', [])
                for dep in dependencies:
                    if 'target_field' in dep and 'type' in dep:
                        self.add_dependency(
                            field_name,
                            dep['target_field'],
                            dep['type'],
                            dep.get('validation_rule')
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
                    source_field = op.get('source_field')
                    if source_field:
                        self.add_dependency(field_name, source_field, 'derived')
                    elif op.get('type') == 'derive_fiscal_year' and 'source_field' in op:
                        self.add_dependency(field_name, op['source_field'], 'derived')
                    elif op.get('type') == 'derive_date_components' and 'source_field' in op:
                        self.add_dependency(field_name, op['source_field'], 'derived')