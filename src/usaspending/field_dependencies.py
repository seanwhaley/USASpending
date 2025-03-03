"""Field dependency management system."""
from typing import Dict, Any, Set, List, Union, Tuple, Optional
import logging
from collections import defaultdict
from copy import deepcopy

logger = logging.getLogger(__name__)

class FieldDependency:
    """Represents a dependency between fields."""
    
    def __init__(self, field_name: str, target_field: Union[str, Tuple[str, ...], None], dependency_type: str,
                 validation_rule: Optional[Dict[str, Any]] = None):
        """Initialize field dependency."""
        self.field_name = field_name
        self.target_field = target_field if isinstance(target_field, tuple) else target_field
        self.dependency_type = dependency_type
        self.validation_rule = validation_rule

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FieldDependency):
            return NotImplemented
        return (self.field_name == other.field_name and
                self.target_field == other.target_field and
                self.dependency_type == other.dependency_type)

    def __hash__(self) -> int:
        # Fix: Handle None target_field values
        if self.target_field is None:
            target = None
        elif isinstance(self.target_field, str):
            target = self.target_field
        else:
            target = tuple(sorted(self.target_field))
        return hash((self.field_name, target, self.dependency_type))

    def __repr__(self) -> str:
        return f"FieldDependency(field={self.field_name}, target={self.target_field}, type={self.dependency_type})"

class FieldDependencyManager:
    """Manages field dependencies and their validation ordering."""
    
    def __init__(self):
        """Initialize dependency manager."""
        self._dependencies: Dict[str, Set[FieldDependency]] = defaultdict(set)
        self._validation_order: Optional[List[str]] = None
    
    @property
    def dependencies(self) -> Dict[str, Set[FieldDependency]]:
        """Get all dependencies."""
        return self._dependencies

    def clear_dependencies(self) -> None:
        """Clear all dependencies."""
        self._dependencies.clear()
        self._validation_order = None
        
    def add_dependency(self, field_name: str, target_field: Union[str, Tuple[str, ...]], 
                      dependency_type: str, validation_rule: Optional[Dict[str, Any]] = None) -> None:
        """Add a field dependency."""
        dep = FieldDependency(field_name, target_field, dependency_type, validation_rule)
        self._dependencies[field_name].add(dep)
        self._validation_order = None
        
    def get_dependencies(self, field_name: str) -> List[FieldDependency]:
        """Get dependencies for a field."""
        return list(self._dependencies.get(field_name, set()))
        
    def remove_dependency(self, field_name: str, target_field: str, dependency_type: str) -> None:
        """Remove a specific dependency."""
        if field_name in self._dependencies:
            self._dependencies[field_name] = {
                dep for dep in self._dependencies[field_name]
                if not (dep.target_field == target_field and dep.dependency_type == dependency_type)
            }
            if not self._dependencies[field_name]:
                del self._dependencies[field_name]
            self._validation_order = None

    def get_dependency_graph(self) -> Dict[str, Set[Tuple[str, str]]]:
        """Get dependency graph representation."""
        graph = defaultdict(set)
        for field, deps in self._dependencies.items():
            for dep in deps:
                if isinstance(dep.target_field, str):
                    graph[field].add((dep.target_field, dep.dependency_type))
                else:
                    for t in dep.target_field:
                        graph[field].add((t, dep.dependency_type))
        return dict(graph)
            
    def has_circular_dependency(self, start_field: Optional[str] = None) -> bool:
        """Check for circular dependencies in the graph."""
        visited = set()
        path = set()
        
        def visit(field: str) -> bool:
            if field in path:
                cycle = list(path) + [field]
                start_idx = cycle.index(field)
                logger.error(f"Circular dependency detected: {' -> '.join(cycle[start_idx:])}")
                return True
            if field in visited:
                return False
                
            visited.add(field)
            path.add(field)
            
            for dep in self._dependencies.get(field, set()):
                target = dep.target_field
                if isinstance(target, tuple):
                    for t in target:
                        if visit(t):
                            return True
                else:
                    if visit(target):
                        return True
                        
            path.remove(field)
            return False

        if start_field:
            # For specific field check, return False if field doesn't exist
            if start_field not in self._dependencies:
                return False
            return visit(start_field)
            
        for field in self._dependencies:
            if visit(field):
                return True
        return False
        
    def get_validation_order(self) -> List[str]:
        """Get field validation order using topological sort."""
        if self._validation_order is not None:
            return self._validation_order
            
        # Check for circular dependencies first
        if self.has_circular_dependency():
            raise ValueError("Circular dependency detected")
            
        try:
            return self._compute_validation_order()
        except ValueError as e:
            logger.error(f"Error computing validation order: {str(e)}")
            return self._compute_fallback_order()
            
    def _compute_validation_order(self) -> List[str]:
        """Compute validation order using topological sort."""
        # Get all nodes (fields) in the graph
        all_nodes = set(self._dependencies.keys())
        for deps in self._dependencies.values():
            for dep in deps:
                if isinstance(dep.target_field, tuple):
                    all_nodes.update(dep.target_field)
                else:
                    all_nodes.add(dep.target_field)

        result = []
        in_degree = defaultdict(int)
        graph = defaultdict(set)
        
        # Build graph and calculate in-degrees
        for field, deps in self._dependencies.items():
            for dep in deps:
                target = dep.target_field
                if isinstance(target, tuple):
                    for t in target:
                        graph[t].add(field)
                        in_degree[field] += 1
                else:
                    graph[target].add(field)
                    in_degree[field] += 1
                    
        # Start with nodes that have no dependencies (including isolated nodes)
        queue = [node for node in all_nodes if in_degree[node] == 0]
        
        while queue:
            field = queue.pop(0)
            if field not in result:  # Avoid duplicates
                result.append(field)
            
            for dependent in graph[field]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check if all nodes are included
        if len(result) != len(all_nodes):
            raise ValueError("Circular dependency detected")
            
        self._validation_order = result
        return result
        
    def _compute_fallback_order(self) -> List[str]:
        """Compute a fallback validation order when topological sort fails."""
        logger.warning("Using fallback validation order due to circular dependencies")
        all_nodes = set()
        # Include all fields involved in dependencies
        for field, deps in self._dependencies.items():
            all_nodes.add(field)
            for dep in deps:
                if isinstance(dep.target_field, tuple):
                    all_nodes.update(dep.target_field)
                else:
                    all_nodes.add(dep.target_field)
        return sorted(list(all_nodes))
        
    def _process_field_properties(self, field_properties: Dict[str, Any]) -> None:
        """Process field properties to extract dependencies and transformations."""
        for field_name, props in field_properties.items():
            if not isinstance(props, dict):
                continue
                
            # Handle validation dependencies
            validation = props.get('validation', {})
            if 'dependencies' in validation:
                deps = validation['dependencies']
                if isinstance(deps, (list, tuple)):
                    for dep in deps:
                        if isinstance(dep, dict) and 'target_field' in dep:
                            self.add_dependency(
                                field_name=field_name,
                                target_field=dep['target_field'],
                                dependency_type=dep.get('type', 'required'),
                                validation_rule=dep.get('validation_rule')
                            )
                elif isinstance(deps, str):
                    self.add_dependency(field_name, deps, 'required')

            # Handle transformation dependencies
            transformation = props.get('transformation', {})
            
            # Handle single transformation
            if isinstance(transformation, dict):
                if 'source_field' in transformation:
                    self.add_dependency(
                        field_name=field_name,
                        target_field=transformation['source_field'],
                        dependency_type='transformation'
                    )
                # Handle operations list
                operations = transformation.get('operations', [])
                if isinstance(operations, list):
                    for op in operations:
                        if isinstance(op, dict) and 'source_field' in op:
                            self.add_dependency(
                                field_name=field_name,
                                target_field=op['source_field'],
                                dependency_type='transformation'
                            )

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'FieldDependencyManager':
        """Create dependency manager from configuration."""
        manager = cls()
        if not config:
            return manager
            
        if 'field_properties' in config:
            manager._process_field_properties(config['field_properties'])
            
        return manager