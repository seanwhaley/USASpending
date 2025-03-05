"""System for managing field dependencies and validation order."""
from typing import Dict, Any, List, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import networkx as nx

from .interfaces import IDependencyManager, ISchemaAdapter
from .logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class Dependency:
    """Represents a field dependency."""
    field_name: str
    target_field: str
    dependency_type: str
    validation_rule: Dict[str, Any]
    error_level: str = "error"

class DependencyManager(IDependencyManager):
    """Manages field dependencies and validation order."""
    
    def __init__(self):
        """Initialize dependency manager."""
        self.dependencies: Dict[str, List[Dependency]] = defaultdict(list)
        self.validation_order: Optional[List[str]] = None
        self.validation_graph: Optional[nx.DiGraph] = None
        
    def add_dependency(self, field_name: str, target_field: str,
                      dependency_type: str, validation_rule: Dict[str, Any]) -> None:
        """Add field dependency."""
        dependency = Dependency(
            field_name=field_name,
            target_field=target_field,
            dependency_type=dependency_type,
            validation_rule=validation_rule
        )
        
        self.dependencies[field_name].append(dependency)
        # Invalidate cached order
        self.validation_order = None
        self.validation_graph = None
        
    def get_validation_order(self) -> List[str]:
        """Get ordered list of fields for validation."""
        if self.validation_order is None:
            self._compute_validation_order()
        return self.validation_order or []
        
    def validate_dependencies(self, record: Dict[str, Any],
                          adapters: Dict[str, ISchemaAdapter]) -> List[str]:
        """Validate field dependencies."""
        errors: List[str] = []
        
        # Ensure validation order is computed
        validation_order = self.get_validation_order()
        
        # Track validated fields and their values
        validated_fields: Dict[str, Any] = {}
        
        # Validate fields in order
        for field_name in validation_order:
            if field_name not in record:
                continue
                
            field_value = record[field_name]
            field_dependencies = self.dependencies.get(field_name, [])
            
            # Check dependencies
            for dep in field_dependencies:
                if not self._validate_dependency(
                    dep, field_value, validated_fields, adapters):
                    errors.append(
                        f"Field {field_name} failed dependency validation: "
                        f"depends on {dep.target_field} ({dep.dependency_type})"
                    )
                    if dep.error_level == "error":
                        return errors
                        
            # Store validated value
            validated_fields[field_name] = field_value
            
        return errors
        
    def _validate_dependency(self, dependency: Dependency,
                           field_value: Any,
                           validated_fields: Dict[str, Any],
                           adapters: Dict[str, ISchemaAdapter]) -> bool:
        """Validate a single dependency."""
        target_value = validated_fields.get(dependency.target_field)
        
        if target_value is None:
            # Target field not present or not yet validated
            return False
            
        if dependency.dependency_type == "required_if":
            # Field required if target matches condition
            condition_value = dependency.validation_rule.get("equals")
            if target_value == condition_value and field_value is None:
                return False
                
        elif dependency.dependency_type == "required_unless":
            # Field required unless target matches condition
            condition_value = dependency.validation_rule.get("equals")
            if target_value != condition_value and field_value is None:
                return False
                
        elif dependency.dependency_type == "equals":
            # Field must equal target
            if field_value != target_value:
                return False
                
        elif dependency.dependency_type == "not_equals":
            # Field must not equal target
            if field_value == target_value:
                return False
                
        elif dependency.dependency_type == "greater_than":
            # Field must be greater than target
            try:
                if not (isinstance(field_value, (int, float)) and
                       isinstance(target_value, (int, float)) and
                       field_value > target_value):
                    return False
            except (TypeError, ValueError):
                return False
                
        elif dependency.dependency_type == "less_than":
            # Field must be less than target
            try:
                if not (isinstance(field_value, (int, float)) and
                       isinstance(target_value, (int, float)) and
                       field_value < target_value):
                    return False
            except (TypeError, ValueError):
                return False
                
        elif dependency.dependency_type == "custom":
            # Custom validation rule
            adapter = adapters.get(dependency.target_field)
            if adapter:
                return adapter.validate(field_value, dependency.field_name)
                
        return True
        
    def _compute_validation_order(self) -> None:
        """Compute field validation order using topological sort."""
        # Build dependency graph
        graph = nx.DiGraph()
        
        # Add all fields as nodes
        fields: Set[str] = set()
        for field_name, deps in self.dependencies.items():
            fields.add(field_name)
            fields.update(d.target_field for d in deps)
            
        for field in fields:
            graph.add_node(field)
            
        # Add dependency edges
        for field_name, deps in self.dependencies.items():
            for dep in deps:
                # Edge from target to dependent field
                graph.add_edge(dep.target_field, field_name)
                
        try:
            # Compute order using topological sort
            order = list(nx.topological_sort(graph))
            
            # Store results
            self.validation_order = order
            self.validation_graph = graph
            
        except nx.NetworkXUnfeasible:
            logger.error("Circular dependencies detected in validation rules")
            # Use arbitrary order if cycle detected
            self.validation_order = sorted(fields)
            self.validation_graph = graph
            
    def get_field_dependencies(self, field_name: str) -> List[Dependency]:
        """Get dependencies for a field."""
        return self.dependencies.get(field_name, []).copy()
        
    def get_dependent_fields(self, field_name: str) -> List[str]:
        """Get fields that depend on the given field."""
        if self.validation_graph is None:
            self._compute_validation_order()
            
        if not self.validation_graph or field_name not in self.validation_graph:
            return []
            
        return [
            node for node in self.validation_graph.successors(field_name)
        ]
        
    def clear_dependencies(self) -> None:
        """Clear all dependencies."""
        self.dependencies.clear()
        self.validation_order = None
        self.validation_graph = None
        
    def get_dependency_groups(self) -> List[Set[str]]:
        """Get groups of mutually dependent fields."""
        if self.validation_graph is None:
            self._compute_validation_order()
            
        if not self.validation_graph:
            return []
            
        # Find strongly connected components
        return [set(group) for group in
                nx.strongly_connected_components(self.validation_graph)]
        
    def is_circular_dependency(self, field_name: str,
                             target_field: str) -> bool:
        """Check if adding dependency would create cycle."""
        if self.validation_graph is None:
            self._compute_validation_order()
            
        if not self.validation_graph:
            return False
            
        # Check if target already depends on field
        try:
            return nx.has_path(self.validation_graph,
                             field_name, target_field)
        except nx.NetworkXError:
            return False
            
    def analyze_dependencies(self) -> Dict[str, Any]:
        """Analyze dependency structure."""
        if self.validation_graph is None:
            self._compute_validation_order()
            
        if not self.validation_graph:
            return {}
            
        analysis = {
            "total_fields": len(self.validation_graph),
            "dependency_groups": len(self.get_dependency_groups()),
            "max_depth": 0,
            "fields_by_depth": defaultdict(list),
            "bottlenecks": []
        }
        
        # Compute depth for each field
        for field in self.validation_graph.nodes():
            depth = len(nx.ancestors(self.validation_graph, field))
            analysis["fields_by_depth"][depth].append(field)
            analysis["max_depth"] = max(analysis["max_depth"], depth)
            
        # Find bottleneck fields
        for field in self.validation_graph.nodes():
            successors = set(nx.descendants(self.validation_graph, field))
            predecessors = set(nx.ancestors(self.validation_graph, field))
            if len(successors) > 2 and len(predecessors) > 2:
                analysis["bottlenecks"].append({
                    "field": field,
                    "dependencies": len(predecessors),
                    "dependents": len(successors)
                })
                
        return analysis