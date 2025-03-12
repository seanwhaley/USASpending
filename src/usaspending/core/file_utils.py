"""Core file system operations."""
from __future__ import annotations

import os
import json
import gzip
import csv
import shutil
import hashlib
import tempfile
from pathlib import Path
from typing import (
    Any, Dict, List, Optional, Union, Iterator, TextIO, BinaryIO, TypeVar, cast, 
    Generator, Generic, Callable, TypeAlias, Protocol, IO
)
from contextlib import contextmanager
from functools import wraps
import logging
from collections import OrderedDict

from .exceptions import FileOperationError
from .types import JsonData

# Type definitions
PathLike: TypeAlias = Union[str, Path]
T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')
F = TypeVar('F', bound=Callable[..., Any])

# Configure logging
logger = logging.getLogger(__name__)

class LRUCache(Generic[KT, VT]):
    """Least Recently Used (LRU) cache implementation."""
    
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._cache: OrderedDict[KT, VT] = OrderedDict()
        
    def get(self, key: KT) -> Optional[VT]:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]
        
    def put(self, key: KT, value: VT) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)
            
    def clear(self) -> None:
        self._cache.clear()

def retry_on_error(max_retries: int = 3, delay: float = 0.1) -> Callable[[F], F]:
    """Decorator to retry file operations on failure."""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(delay * (attempt + 1))
            raise FileOperationError(f"Operation failed after {max_retries} attempts: {str(last_error)}")
        return cast(F, wrapper)
    return decorator

@contextmanager
def atomic_write(file_path: PathLike, mode: str = 'w',
                encoding: Optional[str] = 'utf-8',
                **kwargs: Any) -> Generator[IO[Any], None, None]:
    """Write to file atomically using a temporary file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    tmp: Optional[IO[Any]] = None
    try:
        tmp_file = tempfile.NamedTemporaryFile(
            mode='w+b',
            dir=str(path.parent),
            prefix=f'.{path.name}.',
            suffix='.tmp',
            delete=False
        )
        
        if 'b' in mode:
            tmp = cast(BinaryIO, tmp_file)
        else:
            # Wrap in TextIOWrapper for text mode
            tmp = open(tmp_file.name, mode=mode, encoding=encoding, **kwargs)
        
        yield tmp
        
        # Ensure content is written
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        
        # Replace target file atomically
        if os.name == 'nt':  # Windows
            # Can't rename if target exists on Windows
            if path.exists():
                path.unlink()
        os.rename(tmp_file.name, path)
        
    except Exception as e:
        if tmp:
            tmp.close()
            try:
                os.unlink(tmp_file.name)
            except OSError:
                pass
        raise FileOperationError(f"Atomic write failed: {str(e)}") from e

@contextmanager
def atomic_operation(filepath: PathLike) -> Generator[Path, None, None]:
    """Perform atomic file operation using a temporary file."""
    temp_path = Path(tempfile.mktemp(dir=Path(filepath).parent))
    try:
        yield temp_path
        # Atomic replace
        temp_path.replace(filepath)
    except Exception:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise

@retry_on_error()
def read_json_file(file_path: PathLike, encoding: str = 'utf-8') -> JsonData:
    """Read JSON file with retry on error."""
    path = Path(file_path)
    if not path.exists():
        raise FileOperationError(f"File not found: {file_path}")
        
    try:
        if path.suffix == '.gz':
            with gzip.open(path, 'rt', encoding=encoding) as f:
                return cast(JsonData, json.load(f))
        else:
            with open(path, 'r', encoding=encoding) as f:
                return cast(JsonData, json.load(f))
    except Exception as e:
        raise FileOperationError(f"Failed to read JSON file: {str(e)}") from e

@retry_on_error()
def write_json_file(data: JsonData, file_path: PathLike,
                   compress: bool = False, indent: Optional[int] = 2,
                   encoding: str = 'utf-8') -> None:
    """Write JSON file atomically with optional compression."""
    path = Path(file_path)
    try:
        if compress:
            with atomic_write(path, 'wb') as f:
                content = json.dumps(data, indent=indent).encode(encoding)
                cast(BinaryIO, f).write(gzip.compress(content))
        else:
            with atomic_write(path, 'w', encoding=encoding) as f:
                json.dump(data, cast(TextIO, f), indent=indent)
    except Exception as e:
        raise FileOperationError(f"Failed to write JSON file: {str(e)}") from e

@retry_on_error()
def read_csv_file(file_path: PathLike, encoding: str = 'utf-8',
                  **csv_kwargs: Any) -> Iterator[Dict[str, str]]:
    """Read CSV file as dictionary records with retry."""
    path = Path(file_path)
    if not path.exists():
        raise FileOperationError(f"File not found: {file_path}")
        
    try:
        with open(path, 'r', encoding=encoding, newline='') as f:
            reader = csv.DictReader(f, **csv_kwargs)
            if reader.fieldnames is None:
                raise FileOperationError("CSV file has no headers")
            yield from reader
    except Exception as e:
        raise FileOperationError(f"Failed to read CSV file: {str(e)}") from e

@retry_on_error()
def write_csv_file(records: List[Dict[str, Any]], file_path: PathLike,
                  fieldnames: Optional[List[str]] = None,
                  encoding: str = 'utf-8', **csv_kwargs: Any) -> None:
    """Write CSV file atomically."""
    if not records:
        raise FileOperationError("No records to write")
        
    # Get fieldnames from first record if not provided
    if not fieldnames:
        fieldnames = list(records[0].keys())
    
    try:
        with atomic_write(file_path, 'w', encoding=encoding, newline='') as f:
            writer = csv.DictWriter(cast(TextIO, f), fieldnames=fieldnames, **csv_kwargs)
            writer.writeheader()
            writer.writerows(records)
    except Exception as e:
        raise FileOperationError(f"Failed to write CSV file: {str(e)}") from e

def ensure_directory(path: PathLike) -> None:
    """Ensure directory exists, creating it if necessary."""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise FileOperationError(f"Failed to create directory: {str(e)}") from e

def delete_directory(path: PathLike, ignore_errors: bool = False) -> None:
    """Delete directory and all contents."""
    try:
        shutil.rmtree(path, ignore_errors=ignore_errors)
    except Exception as e:
        raise FileOperationError(f"Failed to delete directory: {str(e)}") from e

def calculate_file_hash(file_path: PathLike, hash_type: str = 'sha256',
                       chunk_size: int = 8192) -> str:
    """Calculate file hash."""
    try:
        hasher = getattr(hashlib, hash_type)()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                hasher.update(chunk)
        return cast(str, hasher.hexdigest())
    except Exception as e:
        raise FileOperationError(f"Failed to calculate file hash: {str(e)}") from e

def get_file_size(file_path: PathLike) -> int:
    """Get file size in bytes."""
    try:
        return Path(file_path).stat().st_size
    except Exception as e:
        raise FileOperationError(f"Failed to get file size: {str(e)}") from e

@contextmanager
def temp_directory() -> Generator[Path, None, None]:
    """Create and clean up a temporary directory."""
    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
    finally:
        if temp_dir and temp_dir.exists():
            delete_directory(temp_dir, ignore_errors=True)

def list_files(directory: PathLike, pattern: str = '*',
               recursive: bool = False) -> Iterator[Path]:
    """List files in directory matching pattern."""
    try:
        path = Path(directory)
        if not path.exists():
            raise FileOperationError(f"Directory not found: {directory}")
            
        if recursive:
            yield from path.rglob(pattern)
        else:
            yield from path.glob(pattern)
    except Exception as e:
        raise FileOperationError(f"Failed to list files: {str(e)}") from e

def move_file(src: PathLike, dst: PathLike, overwrite: bool = False) -> None:
    """Move file with proper error handling."""
    try:
        src_path = Path(src)
        dst_path = Path(dst)
        
        if not src_path.exists():
            raise FileOperationError(f"Source file not found: {src}")
            
        if dst_path.exists() and not overwrite:
            raise FileOperationError(f"Destination file exists: {dst}")
            
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
    except Exception as e:
        raise FileOperationError(f"Failed to move file: {str(e)}") from e

def copy_file(src: PathLike, dst: PathLike, overwrite: bool = False) -> None:
    """Copy file with proper error handling."""
    try:
        src_path = Path(src)
        dst_path = Path(dst)
        
        if not src_path.exists():
            raise FileOperationError(f"Source file not found: {src}")
            
        if dst_path.exists() and not overwrite:
            raise FileOperationError(f"Destination file exists: {dst}")
            
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_path), str(dst_path))
    except Exception as e:
        raise FileOperationError(f"Failed to copy file: {str(e)}") from e

def safe_remove(path: PathLike) -> bool:
    """Safely remove a file or directory."""
    try:
        path_obj = Path(path)
        if path_obj.is_file():
            path_obj.unlink()
        elif path_obj.is_dir():
            shutil.rmtree(path_obj)
        return True
    except Exception:
        return False