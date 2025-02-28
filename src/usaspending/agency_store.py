"""Agency data store implementation."""
from typing import Dict, Any, Optional, Set
import logging
from .entity_store import EntityStore

logger = logging.getLogger(__name__)

class AgencyEntityStore(EntityStore):
    """Manages agency data storage with hierarchical relationship tracking."""
    
    def __init__(self, base_path: str, entity_type: str, config: Dict[str, Any]) -> None:
        super().__init__(base_path, entity_type, config)
        self.subagencies: Dict[str, Set[str]] = {}
        self.offices: Dict[str, Set[str]] = {}
        self.role_mappings: Dict[str, Dict[str, Set[str]]] = {
            'awarding': {},
            'funding': {},
            'parent_award': {}
        }

    def add_entity(self, entity_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Add agency with hierarchical relationship tracking."""
        if not entity_data:
            return None
            
        # Add base entity
        agency_id = super().add_entity(entity_data)
        if not agency_id:
            return None
            
        # Track role assignments
        if isinstance(entity_data, dict):
            for level, level_data in entity_data.items():
                if isinstance(level_data, dict) and 'roles' in level_data:
                    for role in level_data['roles']:
                        if role in self.role_mappings:
                            if level not in self.role_mappings[role]:
                                self.role_mappings[role][level] = set()
                            self.role_mappings[role][level].add(agency_id)

        # Track hierarchical relationships
        if isinstance(agency_id, dict):
            for level, key in agency_id.items():
                if level == 'sub_agency' and key:
                    if 'agency' in agency_id:
                        parent_key = agency_id['agency']
                        if parent_key not in self.subagencies:
                            self.subagencies[parent_key] = set()
                        self.subagencies[parent_key].add(key)
                        self.add_relationship(parent_key, "HAS_SUBAGENCY", key)
                        self.add_relationship(key, "BELONGS_TO_AGENCY", parent_key)

                elif level == 'office' and key:
                    if 'sub_agency' in agency_id:
                        parent_key = agency_id['sub_agency']
                        if parent_key not in self.offices:
                            self.offices[parent_key] = set()
                        self.offices[parent_key].add(key)
                        self.add_relationship(parent_key, "HAS_OFFICE", key)
                        self.add_relationship(key, "BELONGS_TO_SUBAGENCY", parent_key)
                        
        return agency_id

    def get_agency_hierarchy(self, agency_id: str) -> Dict[str, Any]:
        """Get agency's hierarchical relationships and roles."""
        return {
            'subagencies': list(self.subagencies.get(agency_id, set())),
            'offices': list(self.offices.get(agency_id, set())),
            'roles': {
                role: {
                    level: list(agencies) 
                    for level, agencies in level_data.items() 
                    if agency_id in agencies
                }
                for role, level_data in self.role_mappings.items()
            }
        }

    def save(self) -> None:
        """Save agencies with hierarchical relationship data and role mappings."""
        try:
            logger.info(f"Agency: Starting save with {len(self.cache)} agencies")
            
            # Add hierarchy and role data to each agency
            for agency_id in self.cache:
                self.cache[agency_id]['hierarchy'] = self.get_agency_hierarchy(agency_id)
                logger.debug(f"Agency: Added hierarchy and role data for {agency_id}")
                
            super().save()
            logger.info(f"Agency: Successfully saved {self.stats.unique} agencies")
            
        except Exception as e:
            logger.error(f"Agency: Error saving agency store: {str(e)}")
            self._cleanup_temp_files()
            raise