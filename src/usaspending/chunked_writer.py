"""Chunked data writer with optimized processing."""
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import os
import json
from pathlib import Path

from .field_selector import FieldSelector
from .logging_config import get_logger
from .types import ChunkInfo
from .utils import TypeConverter
from .validation import ValidationEngine
from .exceptions import ChunkingError

logger = get_logger(__name__)

class ChunkedWriter:
    """Manages writing records in chunks with optimized batching and error handling."""
    
    def __init__(self, base_path: str, config: Dict[str, Any], field_selector: Optional[FieldSelector] = None, chunk_size: Optional[int] = None) -> None:
        """Initialize chunked writer with configuration."""
        self.base_path = Path(base_path)
        self.config = config
        self.field_selector = field_selector
        
        # Initialize settings from config
        self._init_config()
        self._init_validation()
        self._init_fields()
        
        # Processing state
        self.current_chunk = 1
        self.buffer: List[Dict[str, Any]] = []
        self.total_records = 0
        self.chunks_info: List[ChunkInfo] = []
        
    def _init_config(self) -> None:
        """Initialize configuration settings."""
        proc_config = self.config.get('global', {}).get('processing', {})
        if not proc_config:
            raise ChunkingError("Missing global.processing configuration section")
            
        # Core settings
        self.chunk_size = self._get_chunk_size(proc_config)
        self.max_chunk_size_mb = proc_config.get('max_chunk_size_mb')
        self.batch_size = proc_config.get('batch_size', 1000)
        
        # File format settings
        file_formats = self.config.get('global', {}).get('file_formats', {})
        self.json_indent = file_formats.get('json', {}).get('indent', 2)
        self.json_ensure_ascii = file_formats.get('json', {}).get('ensure_ascii', False)
        self.encoding = file_formats.get('encoding', 'utf-8')
        
    def _get_chunk_size(self, proc_config: Dict[str, Any]) -> int:
        """Get chunk size from config or override."""
        chunk_size = proc_config.get('records_per_chunk')
        if not chunk_size:
            raise ChunkingError("records_per_chunk required in global.processing config")
        return chunk_size
        
    def _init_validation(self) -> None:
        """Initialize validation if enabled."""
        self.validator = None
        if self.config['global']['input'].get('validate_input', True):
            self.validator = ValidationEngine(self.config)
            logger.debug("Validation engine initialized for ChunkedWriter")
            
            result = self.validator.validate_chunk_config()
            if not result.valid:
                raise ChunkingError(f"Chunk configuration error: {result.message}")
                
    def _init_fields(self) -> None:
        """Initialize field tracking."""
        self.keep_fields = self._collect_essential_fields()
        self.excluded_fields = self._build_excluded_fields()
        
        if not self.keep_fields:
            raise ChunkingError("No essential fields (key_fields) found in entity configurations")
            
    def _collect_essential_fields(self) -> Set[str]:
        """Collect essential fields from configuration."""
        fields = set()
        
        for section_data in self.config.values():
            if not isinstance(section_data, dict):
                continue
                
            # Add key fields
            if 'key_fields' in section_data:
                fields.update(section_data['key_fields'])
            
            # Add mapped fields
            if 'field_mappings' in section_data:
                for mapped_field in section_data['field_mappings'].values():
                    if isinstance(mapped_field, str):
                        fields.add(mapped_field)
                    elif isinstance(mapped_field, list):
                        fields.update(mapped_field)
                        
        return fields
        
    def _build_excluded_fields(self) -> Set[str]:
        """Build set of fields to exclude from processed records."""
        excluded = set()
        
        for cfg in self.config.values():
            if not isinstance(cfg, dict):
                continue
                
            # Handle field mappings
            if 'field_mappings' in cfg:
                for source_field in cfg['field_mappings'].values():
                    if isinstance(source_field, str):
                        if source_field not in self.keep_fields:
                            excluded.add(source_field)
                    elif isinstance(source_field, list):
                        excluded.update(f for f in source_field if f not in self.keep_fields)
                        
            # Handle field patterns
            if 'field_patterns' in cfg:
                exceptions = self.config.get('global', {}).get('field_pattern_exceptions', [])
                excluded.update(pattern for pattern in cfg['field_patterns']
                              if pattern not in exceptions)
                              
            # Handle explicit exclusions
            if 'exclude_fields' in cfg:
                excluded.update(cfg['exclude_fields'])
                
        return excluded

    def add_record(self, record: Dict[str, Any]) -> None:
        """Add a record to the buffer, writing chunk if buffer is full."""
        self.buffer.append(self.clean_record_for_chunk(record))
        if len(self.buffer) >= self.chunk_size:
            self.write_records()
            
    def clean_record_for_chunk(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Clean record for chunking by removing excluded fields."""
        if self.validator:
            return self.validator.validate_clean_record(record, self.keep_fields, self.excluded_fields)
            
        # Fallback when validation is disabled
        return {
            key: value for key, value in record.items()
            if (key in self.keep_fields or
                not any(key.startswith(pattern) for pattern in self.excluded_fields) or
                key.endswith('_ref'))
        }

    def write_records(self) -> None:
        """Write buffered records to chunk file with atomic operations."""
        if not self.buffer:
            return
            
        chunk_file = self.base_path.with_suffix(f'.part{self.current_chunk}.json')
        temp_file = chunk_file.with_suffix('.tmp')
        backup_file = chunk_file.with_suffix('.bak')
        
        try:
            chunk_data = {
                "metadata": {
                    "chunk_number": self.current_chunk,
                    "record_count": len(self.buffer),
                    "generated_date": datetime.now().isoformat()
                },
                "records": self.buffer
            }
            
            # Ensure output directory exists
            self.base_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Backup existing chunk
            if chunk_file.exists():
                chunk_file.replace(backup_file)
            
            # Write atomically using temporary file
            temp_file.write_text(
                json.dumps(chunk_data, indent=self.json_indent, ensure_ascii=self.json_ensure_ascii),
                encoding=self.encoding
            )
            temp_file.replace(chunk_file)
            
            # Update tracking
            self.chunks_info.append(ChunkInfo(
                file=str(chunk_file),
                record_count=len(self.buffer),
                chunk_number=self.current_chunk
            ))
            
            self.total_records += len(self.buffer)
            self.current_chunk += 1
            self.buffer = []
            
            # Clean up backup
            if backup_file.exists():
                backup_file.unlink()
                
        except Exception as e:
            logger.error(f"Error writing chunk {self.current_chunk}: {str(e)}")
            # Restore from backup if available
            if backup_file.exists():
                backup_file.replace(chunk_file)
            raise ChunkingError(f"Failed to write chunk {self.current_chunk}: {str(e)}")

    def write_index(self) -> None:
        """Write index file with chunk metadata."""
        index_file = self.base_path.with_suffix('_index.json')
        temp_file = index_file.with_suffix('.tmp')
        
        try:
            index_data = {
                "metadata": {
                    "total_records": self.total_records,
                    "total_chunks": len(self.chunks_info),
                    "generated_date": datetime.now().isoformat()
                },
                "chunks": [
                    {
                        "file": os.path.basename(chunk.file),
                        "record_count": chunk.record_count,
                        "chunk_number": chunk.chunk_number
                    }
                    for chunk in self.chunks_info
                ]
            }
            
            # Write atomically
            temp_file.write_text(
                json.dumps(index_data, indent=self.json_indent, ensure_ascii=self.json_ensure_ascii),
                encoding=self.encoding
            )
            temp_file.replace(index_file)
            
        except Exception as e:
            logger.error(f"Error writing index file: {str(e)}")
            raise ChunkingError(f"Failed to write index file: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """Get chunking statistics."""
        return {
            "total_records": self.total_records,
            "total_chunks": len(self.chunks_info),
            "current_chunk": self.current_chunk,
            "buffer_size": len(self.buffer),
            "chunk_size": self.chunk_size
        }