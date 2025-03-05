"""Validation group and dependency management."""
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import networkx as nx

from .logging_config import get_logger
from .exceptions import ConfigurationError

logger = get_logger(__name__)

@dataclass
class ValidationGroup:
    """Represents a validation group with rules and dependencies."""
    name: str
    rules: List[str]
    description: Optional[str] = None
    enabled: bool = True
    error_level: str = "error"
    dependencies: List[str] = field(default_factory=list)

@dataclass
class FieldDependency:
    """Represents a field dependency."""
    field: str
    type: str
    target_field: str
    validation_rule: Optional[Dict[str, Any]] = None

class ValidationManager:
    """Manages validation groups and field dependencies."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize validation manager."""
        self.validation_groups: Dict[str, ValidationGroup] = {}
        self.field_dependencies: Dict[str, List[FieldDependency]] = defaultdict(list)
        self.field_properties = config.get('field_properties', {})
        
        # Load validation groups
        for group_id, group_config in config.get('validation_groups', {}).items():
            self.validation_groups[group_id] = ValidationGroup(
                name=group_config['name'],
                rules=group_config['rules'],
                description=group_config.get('description'),
                enabled=group_config.get('enabled', True),
                error_level=group_config.get('error_level', 'error'),
                dependencies=group_config.get('dependencies', [])
            )
        
        # Load field dependencies
        for field_name, field_config in self.field_properties.items():
            validation = field_config.get('validation', {})
            for dep in validation.get('dependencies', []):
                self.field_dependencies[field_name].append(
                    FieldDependency(
                        field=field_name,
                        type=dep['type'],
                        target_field=dep['target_field'],
                        validation_rule=dep.get('validation_rule')
                    )
                )
        
        # Validate dependencies
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        """Validate group and field dependencies."""
        self._check_group_circular_deps()
        self._check_field_circular_deps()
        self._check_dependency_existence()

    def _check_group_circular_deps(self) -> None:
        """Check for circular dependencies between validation groups."""
        # Build dependency graph
        G = nx.DiGraph()
        for group_id, group in self.validation_groups.items():
            G.add_node(group_id)
            for dep in group.dependencies:
                G.add_edge(group_id, dep)
        
        try:
            # Find cycles
            cycles = list(nx.simple_cycles(G))
            if cycles:
                cycle_str = ' -> '.join(cycles[0] + [cycles[0][0]])
                raise ConfigurationError(
                    f"Circular dependency detected in validation groups: {cycle_str}"
                )
        except nx.NetworkXNoCycle:
            pass  # No cycles found

    def _check_field_circular_deps(self) -> None:
        """Check for circular dependencies between fields."""
        # Build dependency graph
        G = nx.DiGraph()
        for field, deps in self.field_dependencies.items():
            G.add_node(field)
            for dep in deps:
                G.add_edge(field, dep.target_field)
        
        try:
            # Find cycles
            cycles = list(nx.simple_cycles(G))
            if cycles:
                cycle_str = ' -> '.join(cycles[0] + [cycles[0][0]])
                raise ConfigurationError(
                    f"Circular dependency detected in field dependencies: {cycle_str}"
                )
        except nx.NetworkXNoCycle:
            pass  # No cycles found

    def _check_dependency_existence(self) -> None:
        """Check that all referenced dependencies exist."""
        # Check validation group dependencies
        all_groups = set(self.validation_groups.keys())
        for group in self.validation_groups.values():
            missing = [dep for dep in group.dependencies if dep not in all_groups]
            if missing:
                raise ConfigurationError(
                    f"Validation group '{group.name}' references non-existent "
                    f"groups: {', '.join(missing)}"
                )
        
        # Check field dependencies
        all_fields = set(self.field_properties.keys())
        for field, deps in self.field_dependencies.items():
            for dep in deps:
                if dep.target_field not in all_fields:
                    raise ConfigurationError(
                        f"Field '{field}' references non-existent "
                        f"field: {dep.target_field}"
                    )

    def get_validation_order(self) -> List[str]:
        """Get fields in dependency-aware validation order."""
        # Build dependency graph
        G = nx.DiGraph()
        for field, deps in self.field_dependencies.items():
            G.add_node(field)
            for dep in deps:
                G.add_edge(dep.target_field, field)  # Reverse edges for topological sort
        
        # Add independent fields
        for field in self.field_properties:
            if field not in G:
                G.add_node(field)
        
        try:
            # Topological sort gives validation order
            return list(nx.topological_sort(G))
        except nx.NetworkXUnfeasible:
            # This shouldn't happen since we check for cycles in initialization
            raise ConfigurationError("Unexpected circular dependency detected")

    def get_group_rules(self, group_id: str) -> List[str]:
        """Get validation rules for a group."""
        group = self.validation_groups.get(group_id)
        if not group:
            return []
        return group.rules if group.enabled else []

    def get_field_dependencies(self, field: str) -> List[FieldDependency]:
        """Get dependencies for a field."""
        return self.field_dependencies.get(field, [])