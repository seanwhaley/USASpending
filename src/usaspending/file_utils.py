"""Platform-specific file operations module."""
from __future__ import annotations

import os
import json
import time
import glob
import logging
import fnmatch
import shutil
from pathlib import Path
from typing import (
    Any, Dict, List, Optional, Union, Callable, TextIO, BinaryIO, 
    Iterator, TypeVar, Final, cast
)
from typing_extensions import TypeAlias
from contextlib import contextmanager
from io import StringIO, BytesIO
from functools import wraps

# Define FileOperationError locally instead of importing it
class FileOperationError(Exception):
    """Exception raised for file operation errors."""

# Type definitions for improved type safety
T = TypeVar('T')
PathLike: TypeAlias = Union[str, Path]
JsonData: TypeAlias = Dict[str, Any]
CsvRow: TypeAlias = Dict[str, str]
BatchType: TypeAlias = List[CsvRow]

# Constants
DEFAULT_ENCODING: Final[str] = 'utf-8'
DEFAULT_CHUNK_SIZE: Final[int] = 8192
DEFAULT_MAX_RETRIES: Final[int] = 3

# Add logger
logger = logging.getLogger(__name__)

# Fix the return type annotation to properly handle any callable
def retry_on_exception(max_retries: int = DEFAULT_MAX_RETRIES, delay: float = 0.1) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying file operations on failure."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
            logger.error(f"Operation failed after {max_retries} attempts: {str(last_exception)}")
            raise FileOperationError(f"Operation failed after {max_retries} attempts: {str(last_exception)}")
        return wrapper
    return decorator

@contextmanager
def safe_open_file(
    path: PathLike,
    mode: str = 'r',
    encoding: Optional[str] = None,
    newline: Optional[str] = None,
    buffering: int = -1,
    **kwargs: Any
) -> Iterator[Union[TextIO, BinaryIO]]:
    """
    Safely open a file with proper error handling.
    
    Args:
        path: Path-like object representing file path
        mode: File open mode ('r', 'w', 'a', 'b', etc)
        encoding: File encoding (default: utf-8 for text mode)
        newline: How to handle newlines
        buffering: Buffering policy (-1 to use default buffering)
        **kwargs: Additional arguments passed to open()
        
    Raises:
        FileOperationError: If file operation fails
    """
    path_obj = Path(path).resolve()
    
    try:
        # Create parent directories if writing
        if 'w' in mode or 'a' in mode:
            path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Validate path before opening
        if 'r' in mode and not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path_obj}")
            
        kwargs['buffering'] = buffering
        if 'b' in mode:
            # Binary mode doesn't use encoding
            with open(path_obj, mode, **kwargs) as f:
                yield cast(BinaryIO, f)
        else:
            # Text mode with encoding
            encoding = encoding or DEFAULT_ENCODING
            with open(path_obj, mode, encoding=encoding, newline=newline, **kwargs) as f:
                yield cast(TextIO, f)
                
    except FileNotFoundError as e:
        logger.error(f"File not found: {path_obj}")
        raise FileOperationError(f"File not found: {path_obj}") from e
    except PermissionError as e:
        logger.error(f"Permission denied: {path_obj}")
        raise FileOperationError(f"Permission denied: {path_obj}") from e
    except OSError as e:
        logger.error(f"OS error while accessing {path_obj}: {e}")
        raise FileOperationError(f"OS error while accessing {path_obj}: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error accessing {path_obj}: {e}")
        raise FileOperationError(f"Unexpected error accessing {path_obj}: {e}") from e

@retry_on_exception()
def read_text_file(path: PathLike, encoding: str = DEFAULT_ENCODING, strip: bool = True) -> str:
    """Read text file with retries."""
    with safe_open_file(path, 'r', encoding=encoding) as f:
        content = f.read()
        if isinstance(content, bytes):
            content = content.decode(encoding)
        return content.strip() if strip else content

@retry_on_exception()
def write_text_file(path: PathLike, content: str, encoding: str = DEFAULT_ENCODING, 
                    make_dirs: bool = False, atomic: bool = True) -> None:
    """Write text file atomically with retries."""
    path_obj = Path(path)
    
    if make_dirs:
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
    if atomic:
        temp_path = path_obj.with_suffix(path_obj.suffix + '.tmp')
        try:
            with safe_open_file(temp_path, 'w', encoding=encoding) as f:
                cast(TextIO, f).write(content)  # Fix write method type mismatch
            atomic_replace(temp_path, path_obj)
        finally:
            safe_delete(temp_path)
    else:
        with safe_open_file(path_obj, 'w', encoding=encoding) as f:
            cast(TextIO, f).write(content)  # Fix write method type mismatch

@retry_on_exception()
def read_json_file(path: PathLike, encoding: str = DEFAULT_ENCODING) -> JsonData:
    """Read JSON file with retries."""
    with safe_open_file(path, 'r', encoding=encoding) as f:
        result = json.load(cast(TextIO, f))  # Ensure proper TextIO casting
        return cast(JsonData, result)  # Cast result to JsonData

@retry_on_exception()
def write_json_file(path: PathLike, data: JsonData, encoding: str = DEFAULT_ENCODING,
                    indent: int = 2, ensure_ascii: bool = False, 
                    make_dirs: bool = False, atomic: bool = True) -> None:
    """Write JSON file atomically with retries."""
    path_obj = Path(path)
    
    if make_dirs:
        path_obj.parent.mkdir(parents=True, exist_ok=True)

    if atomic:
        temp_path = path_obj.with_suffix(path_obj.suffix + '.tmp')
        try:
            with safe_open_file(temp_path, 'w', encoding=encoding) as f_io:
                assert not isinstance(f_io, BinaryIO)
                json.dump(data, f_io, indent=indent, ensure_ascii=ensure_ascii)
            atomic_replace(temp_path, path_obj)
        finally:
            safe_delete(temp_path)
    else:
        with safe_open_file(path_obj, 'w', encoding=encoding) as f_io:
            assert not isinstance(f_io, BinaryIO)
            json.dump(data, f_io, indent=indent, ensure_ascii=ensure_ascii)

@retry_on_exception()
def get_files(directory: PathLike, pattern: str = "*", recursive: bool = False) -> List[str]:
    """Get list of files matching pattern."""
    directory_path = Path(directory).resolve()
    try:
        if recursive:
            return [str(p) for p in directory_path.rglob(pattern)]
        return [str(p) for p in directory_path.glob(pattern)]
    except Exception as e:
        logger.error(f"Failed to list files in {directory_path}: {str(e)}")
        raise FileOperationError(f"Failed to list files in {directory_path}: {str(e)}")

@retry_on_exception()
def ensure_directory(path: PathLike) -> None:
    """Ensure directory exists."""
    path_obj = Path(path)
    try:
        path_obj.mkdir(parents=True, exist_ok=True)
        if not path_obj.exists():
            raise FileOperationError(f"Failed to create directory: {path_obj}")
    except Exception as e:
        logger.error(f"Error ensuring directory {path_obj} exists: {str(e)}")
        raise FileOperationError(f"Error ensuring directory {path_obj} exists: {str(e)}")

@retry_on_exception()
def backup_file(source: PathLike, suffix: str = '.bak', max_backups: int = 5) -> str:
    """Create backup of file with rotation."""
    source_path = Path(source)
    if not source_path.exists():
        logger.error(f"Source file does not exist: {source_path}")
        raise FileOperationError(f"Source file does not exist: {source_path}")
        
    base = source_path.with_suffix(source_path.suffix + suffix)
    backup_path = base
    index = 1
    
    while backup_path.exists() and index < max_backups:
        backup_path = base.with_name(f"{base.stem}.{index}{base.suffix}")
        index += 1
        
    if backup_path.exists():
        backup_path.unlink()
        
    shutil.copy2(source_path, backup_path)
    return str(backup_path)

@retry_on_exception()
def safe_delete(path: PathLike) -> None:
    """Safely delete file if it exists."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception as e:
        raise FileOperationError(f"Failed to delete file {path}: {str(e)}")

@retry_on_exception(max_retries=2)
def atomic_replace(source: PathLike, target: PathLike) -> None:
    """Atomically replace target file with source file."""
    source_path = Path(source)
    target_path = Path(target)
    
    if not source_path.exists():
        logger.error(f"Source file does not exist: {source_path}")
        raise FileOperationError(f"Source file does not exist: {source_path}")
        
    try:
        if os.name == 'nt' and target_path.exists():
            target_path.unlink()
        os.rename(source_path, target_path)
    except Exception as e:
        logger.error(f"Failed to replace {target_path} with {source_path}: {str(e)}")
        raise FileOperationError(f"Failed to replace {target_path} with {source_path}: {str(e)}")

def read_in_chunks(file_obj: BinaryIO, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Iterator[bytes]:
    """Read file in chunks to handle large files efficiently."""
    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive")
    while True:
        try:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            yield chunk
        except Exception as e:
            logger.error(f"Error reading chunk: {str(e)}")
            raise FileOperationError(f"Error reading chunk: {str(e)}")

# Exports
__all__ = [
    'safe_open_file',
    'read_text_file',
    'write_text_file',
    'read_json_file', 
    'write_json_file',
    'get_files',
    'ensure_directory',
    'backup_file',
    'safe_delete',
    'atomic_replace',
    'read_in_chunks'
]
