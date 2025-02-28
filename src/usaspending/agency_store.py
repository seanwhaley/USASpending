"""Agency data store implementation."""
from typing import Dict, Any, Optional, Set, Tuple, cast
import logging
from collections import defaultdict
from .entity_store import EntityStore
from .types import AgencyResolutionStats

logger = logging.getLogger(__name__)

class AgencyEntityStore(EntityStore):
    """Manages agency data storage with hierarchical relationship tracking."""
    
    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        """Initialize agency store with specialized tracking."""
        super().__init__(base_path, entity_type, config)
        self.pending_parents: Dict[str, Dict[str, Any]] = {}  # Unresolved parent agencies
        self.parent_mappings: Dict[str, Dict[str, str]] = {}  # Resolved parent references
        self.role_assignments: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """Add agency with hierarchical relationship tracking."""
        if not entity_data:
            return None

        entity_keys: Dict[str, str] = {}
        try:
            # Process each hierarchical level
            for level, level_data in entity_data.items():
                if not isinstance(level_data, dict):
                    continue

                # Add entity at this level
                data = level_data.get('data', {})
                if not data or 'key' not in level_data:
                    logger.warning(f"Agency: Missing required data for {level} level")
                    continue

                key = level_data['key']
                entity_keys[level] = key
                super().add_entity({
                    'level': level,
                    'key': key,
                    **data
                })

                # Track roles if present
                if 'roles' in level_data:
                    for role in level_data['roles']:
                        self.role_assignments[role][level].add(key)

            # Process hierarchical relationships if we have multiple levels
            if len(entity_keys) > 1:
                # Define relationships between levels
                hierarchy_configs = [
                    {
                        'from_level': 'department',
                        'to_level': 'agency',
                        'type': 'HAS_SUBAGENCY',
                        'inverse_type': 'BELONGS_TO_AGENCY'
                    },
                    {
                        'from_level': 'agency',
                        'to_level': 'office',
                        'type': 'HAS_OFFICE',
                        'inverse_type': 'BELONGS_TO_SUBAGENCY'
                    }
                ]
                self.relationship_manager.process_hierarchical_relationships(
                    entity_data, entity_keys, hierarchy_configs)

            # Process any pending parents
            if entity_keys:
                self._check_pending_parents(entity_keys)

            return entity_keys

        except Exception as e:
            logger.error(f"Agency: Error adding hierarchical entity: {str(e)}")
            return None

    def resolve_parent_agency(self, agency_code: str, agency_name: str) -> Tuple[str, str]:
        """Resolve parent agency reference to actual agency."""
        if agency_code in self.parent_mappings:
            mapping = self.parent_mappings[agency_code]
            return mapping['level'], mapping['mapped_id']

        # Look for matching department
        for entity_id, entity in self.cache.cache.items():
            if (entity.get('level') == 'department' and 
                entity.get('code') == agency_code):
                self.parent_mappings[agency_code] = {
                    'level': 'department',
                    'mapped_id': entity_id
                }
                return 'department', entity_id

        # Track pending parent
        if agency_code not in self.pending_parents:
            self.pending_parents[agency_code] = {
                'name': agency_name,
                'data': {
                    'code': agency_code,
                    'name': agency_name,
                    'level': 'department'
                }
            }
        return 'pending', agency_code

    def _check_pending_parents(self, entity_keys: Dict[str, str]) -> None:
        """Check if any pending parents can be resolved."""
        if 'department' not in entity_keys:
            return

        dept_key = entity_keys['department']
        dept = self.cache.cache[dept_key]
        dept_code = dept.get('code')

        if dept_code in self.pending_parents:
            self.parent_mappings[dept_code] = {
                'level': 'department',
                'mapped_id': dept_key
            }
            del self.pending_parents[dept_code]

    def get_agency_hierarchy(self, agency_id: str) -> Dict[str, Any]:
        """Get agency's hierarchical relationships and roles."""
        agency = self.cache.cache.get(agency_id)
        if not agency:
            return {}

        hierarchy = {
            'level': agency.get('level', ''),
            'parent': None,
            'children': [],
            'roles': []
        }

        # Use relationship manager to get parent/child relationships
        level = hierarchy['level']
        if level == 'agency':
            parents = self.relationship_manager.get_related_entities(agency_id, "BELONGS_TO_AGENCY")
            if parents:
                hierarchy['parent'] = next(iter(parents))
            hierarchy['children'] = list(self.relationship_manager.get_related_entities(agency_id, "HAS_OFFICE"))
        elif level == 'office':
            parents = self.relationship_manager.get_related_entities(agency_id, "BELONGS_TO_SUBAGENCY")
            if parents:
                hierarchy['parent'] = next(iter(parents))
        elif level == 'department':
            hierarchy['children'] = list(self.relationship_manager.get_related_entities(agency_id, "HAS_SUBAGENCY"))

        # Add roles
        hierarchy['roles'] = [
            role for role, levels in self.role_assignments.items()
            if any(agency_id in agencies for agencies in levels.values())
        ]

        return hierarchy

    def finalize_parent_agencies(self) -> None:
        """Add any unresolved parent agencies as departments."""
        for agency_code, agency_data in self.pending_parents.items():
            dept_key = f"DEPT_{agency_code}"
            super().add_entity({
                'level': 'department',
                'key': dept_key,
                **agency_data['data']
            })
            self.parent_mappings[agency_code] = {
                'level': 'department',
                'mapped_id': dept_key
            }
        self.pending_parents.clear()

    def save(self) -> None:
        """Save agencies with hierarchy data and resolved references."""
        try:
            logger.info(f"Agency: Starting save with {len(self.cache.cache)} agencies")

            self.finalize_parent_agencies()

            # Add hierarchy and roles to agency data
            for agency_id, agency_data in self.cache.cache.items():
                agency_data['hierarchy'] = self.get_agency_hierarchy(agency_id)
                agency_data['roles'] = [
                    role for role, levels in self.role_assignments.items()
                    if any(agency_id in agencies for agencies in levels.values())
                ]

            super().save()
            logger.info(f"Agency: Successfully saved {self.cache.stats.unique} agencies")

        except Exception as e:
            logger.error(f"Agency: Error saving agency store: {str(e)}")
            raise