"""Entity serialization and file operations."""
from typing import Dict, Any, List, Optional
from pathlib import Path
import os
import json
import logging
from datetime import datetime

from .file_utils import (
    write_json_file, read_json_file, ensure_directory, 
    backup_file, safe_delete, atomic_replace, FileOperationError
)

logger = logging.getLogger(__name__)

class EntitySerializer:
    """Handles entity serialization and file operations."""

    def __init__(self, base_path: str, entity_type: str, encoding: str = "utf-8"):
        """Initialize entity serializer.
        
        Args:
            base_path: Base path for entity storage
            entity_type: Type of entity being serialized
            encoding: Character encoding for files
        """
        self.base_path = base_path
        self.entity_type = entity_type
        self.encoding = encoding
        self.file_path = f"{base_path}_{entity_type}.json"
        self.temp_file_path = f"{self.file_path}.tmp"
        
    def get_base_metadata(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Get base metadata for entity output."""
        return {
            "entity_type": self.entity_type,
            "total_references": stats.get("total", 0),
            "unique_entities": stats.get("unique", 0),
            "relationship_counts": stats.get("relationships", {}),
            "skipped_entities": stats.get("skipped", {}),
            "natural_keys_used": stats.get("natural_keys_used", 0),
            "hash_keys_used": stats.get("hash_keys_used", 0),
            "generated_date": datetime.now().isoformat()
        }
        
    def estimate_json_size(self, cache: Dict[str, Dict[str, Any]], relationships: Dict[str, Any]) -> int:
        """Estimate JSON output size in bytes."""
        sample_size = min(100, len(cache))
        if sample_size == 0:
            return 0
            
        sample_keys = list(cache.keys())[:sample_size]
        sample_data = {k: cache[k] for k in sample_keys}
        
        # Create sample output
        sample_output = {
            "metadata": {"sample": True},
            "entities": sample_data,
            "relationships": {k: {sk: list(v[sk]) for sk in list(v.keys())[:10]} 
                            for k, v in relationships.items()}
        }
        
        # Get sample size and extrapolate
        sample_json = json.dumps(sample_output)
        avg_entity_size = len(sample_json) / sample_size
        
        return int(avg_entity_size * len(cache))
        
    def save(self, cache: Dict[str, Dict[str, Any]], relationships: Dict[str, Any], 
             stats: Dict[str, Any], indent: int = 2, max_file_size: int = 50 * 1024 * 1024) -> None:
        """Save entities with atomic file operations and batching."""
        try:
            logger.info(f"Starting save for {self.entity_type} store with {len(cache)} entities")
            
            # Create directory if needed
            output_dir = os.path.dirname(self.file_path)
            ensure_directory(output_dir)

            # Estimate size and determine save strategy
            estimated_size = self.estimate_json_size(cache, relationships)
            logger.info(f"Estimated output size: {estimated_size/(1024*1024):.2f}MB")
            
            base_metadata = self.get_base_metadata(stats)
            
            if len(cache) > 10000 or estimated_size > max_file_size:
                logger.info("Using partitioned save strategy")
                self._save_partitioned(cache, relationships, base_metadata, indent)
            else:
                logger.info("Using single file save strategy")
                self._save_single_file(cache, relationships, base_metadata, indent)

            logger.info(f"Successfully saved {base_metadata['unique_entities']} {self.entity_type} entities")

        except Exception as e:
            logger.error(f"Error saving entity store: {str(e)}", exc_info=True)
            self._cleanup_temp_files()
            raise
            
    def _save_single_file(self, cache: Dict[str, Dict[str, Any]], relationships: Dict[str, Any],
                         metadata: Dict[str, Any], indent: int) -> None:
        """Save all entities to a single file."""
        try:
            # Clean up any existing temp file first
            self._cleanup_temp_files()
            
            # Create backup if file exists
            if os.path.exists(self.file_path):
                backup_file(self.file_path)
            
            # Prepare output data
            output_data = {
                "metadata": metadata,
                "entities": cache,
                "relationships": {k: {sk: list(v[sk]) for sk in v.keys()} 
                                for k, v in relationships.items()}
            }
            
            # Write data atomically
            write_json_file(
                self.file_path, 
                output_data, 
                encoding=self.encoding, 
                indent=indent,
                ensure_ascii=False,
                atomic=True
            )
            
        except Exception as e:
            logger.error(f"Error saving single file: {str(e)}", exc_info=True)
            self._cleanup_temp_files()
            raise
            
    def _save_partitioned(self, cache: Dict[str, Dict[str, Any]], relationships: Dict[str, Any],
                         metadata: Dict[str, Any], indent: int) -> None:
        """Save large datasets in partitioned files with an index."""
        try:
            base_path = self.file_path.rsplit('.', 1)[0]
            logger.info(f"Starting partitioned save to {base_path}")
            
            # Calculate partition size for ~25MB partitions
            target_size = 25 * 1024 * 1024
            sample_size = min(1000, len(cache))
            sample_keys = list(cache.keys())[:sample_size]
            sample_data = {k: cache[k] for k in sample_keys}
            sample_json = json.dumps({"entities": sample_data})
            avg_entity_size = len(sample_json) / sample_size
            partition_size = max(100, min(10000, int(target_size / avg_entity_size)))
            
            logger.info(f"Calculated partition size: {partition_size} entities")
            
            # Create and save partitions
            entities = list(cache.items())
            partition_count = (len(entities) + partition_size - 1) // partition_size
            
            # Prepare index data
            index_data: Dict[str, Any] = {
                "metadata": metadata,
                "partitions": [],
                "relationships": {}
            }
            
            # Create temporary directory for atomic operations
            temp_dir = Path(base_path).parent / ".tmp"
            ensure_directory(str(temp_dir))
            
            created_files = []
            try:
                for i in range(0, len(entities), partition_size):
                    partition_entities = dict(entities[i:i + partition_size])
                    partition_file = f"{base_path}_part{i//partition_size}.json"
                    partition_metadata = self._save_partition(
                        partition_file, partition_entities, i//partition_size, indent)
                    index_data["partitions"].append(partition_metadata)
                    created_files.append(partition_file)
                
                # Add relationship information to index
                for rel_type, rel_map in relationships.items():
                    index_data["relationships"][rel_type] = {
                        e: list(r) for e, r in rel_map.items()
                    }
                
                # Save index file atomically
                index_file = f"{base_path}_index.json"
                temp_index_file = str(temp_dir / "index.json.tmp")
                logger.info(f"Writing index file to {index_file}")
                
                write_json_file(
                    index_file, 
                    index_data, 
                    encoding=self.encoding, 
                    indent=indent, 
                    ensure_ascii=False,
                    atomic=True
                )
                created_files.append(index_file)
                
                logger.info(f"Successfully saved {partition_count} partitions with index")
                
            except Exception as e:
                # Clean up any created files on error
                for file in created_files:
                    try:
                        safe_delete(file)
                    except Exception:
                        pass
                raise
                
            finally:
                # Clean up temp directory
                try:
                    if temp_dir.exists():
                        for file in temp_dir.iterdir():
                            safe_delete(str(file))
                        temp_dir.rmdir()
                except OSError as e:
                    logger.warning(f"Error cleaning up temp directory: {e}")
            
        except Exception as e:
            logger.error(f"Error in partitioned save: {str(e)}", exc_info=True)
            raise
            
    def _save_partition(self, partition_file: str, partition: Dict[str, Dict[str, Any]], 
                       partition_num: int, indent: int) -> Dict[str, Any]:
        """Save a single partition to file."""
        try:
            # Prepare partition metadata
            partition_metadata = {
                "partition_number": partition_num,
                "entity_count": len(partition),
                "file_path": partition_file
            }
            
            # Write partition to file
            write_json_file(
                partition_file,
                {
                    "metadata": partition_metadata,
                    "entities": partition
                },
                encoding=self.encoding,
                indent=indent,
                ensure_ascii=False,
                atomic=True
            )
            
            return partition_metadata
            
        except Exception as e:
            logger.error(f"Error saving partition {partition_num}: {str(e)}", exc_info=True)
            raise
            
    def _cleanup_temp_files(self) -> None:
        """Clean up any temporary files."""
        try:
            if os.path.exists(self.temp_file_path):
                safe_delete(self.temp_file_path)
        except Exception as e:
            logger.warning(f"Error cleaning up temp file: {str(e)}")

    def load(self) -> Optional[Dict[str, Any]]:
        """Load entity data from disk."""
        if not os.path.exists(self.file_path):
            return None
            
        try:
            return read_json_file(self.file_path, encoding=self.encoding)
        except FileOperationError as e:
            logger.error(f"Error loading entity data: {str(e)}")
            return None