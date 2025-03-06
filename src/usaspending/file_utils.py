"""Platform-specific file operations module."""
from __future__ import annotations

import os
import csv
import json
import time
import glob
import fnmatch
import logging
import tempfile
import shutil
import gzip
import threading
from datetime import datetime
from pathlib import Path
from typing import (
    Any, Dict, List, Optional, Union, Callable, TextIO, BinaryIO, 
    Iterator, TypeVar, Protocol, runtime_checkable, Final
)
from typing_extensions import TypeAlias
from contextlib import contextmanager
from io import StringIO, BytesIO
from functools import wraps

# Type definitions for improved type safety
T = TypeVar('T')
PathLike: TypeAlias = Union[str, Path]
JsonData: TypeAlias = Dict[str, Any]
CsvRow: TypeAlias = Dict[str, str]
BatchType: TypeAlias = List[CsvRow]

# Constants
DEFAULT_ENCODING: Final[str] = 'utf-8'
DEFAULT_CHUNK_SIZE: Final[int] = 8192
DEFAULT_BATCH_SIZE: Final[int] = 1000
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_DELAY: Final[float] = 1.0
DEFAULT_BACKOFF_FACTOR: Final[float] = 2.0
DEFAULT_RETRY_EXCEPTIONS: Final[tuple] = (IOError, OSError)
LOCK_EX: Final[int] = 2  # Exclusive lock
LOCK_UN: Final[int] = 8  # Unlock 
LOCK_NB: Final[int] = 4  # Non-blocking

logger = logging.getLogger(__name__)

# Platform-specific imports and constants
_has_locking = False
try:
    if os.name == 'nt':
        import msvcrt
        _has_locking = True
    else:
        try:
            import fcntl
            _has_locking = True
        except ImportError:
            logger.warning("fcntl not available on this platform")
except ImportError:
    logger.warning("File locking modules not available on this platform")

@runtime_checkable
class FileLike(Protocol):
    """Protocol for file-like objects."""
    def read(self, size: int = -1) -> Union[str, bytes]: ...
    def write(self, data: Union[str, bytes]) -> int: ...
    def close(self) -> None: ...
    def fileno(self) -> int: ...
    @property
    def mode(self) -> str: ...
    @property
    def closed(self) -> bool: ...

class FileOperationError(Exception):
    """Base exception for file operation errors."""
    pass

class FileAccessError(FileOperationError):
    """Exception for file access errors."""
    pass

class FileNotFoundError(FileOperationError):
    """Exception for file not found errors."""
    pass

class FileFormatError(FileOperationError):
    """Exception for file format errors."""
    pass

class FileLockError(FileOperationError):
    """Exception for file locking errors."""
    pass

class RetryableError(FileOperationError):
    """Exception for errors that can be retried."""
    pass

def retry_on_exception(
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    retry_exceptions: tuple = DEFAULT_RETRY_EXCEPTIONS
) -> Callable:
    """Decorator to retry functions on exception.
    
    Args:
        max_retries: Maximum number of retries
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Factor to increase delay by after each retry
        retry_exceptions: Tuple of exceptions to retry on
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            delay = retry_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                            f"Retrying in {delay} seconds..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    
            if last_exception:
                raise RetryableError(
                    f"Operation failed after {max_retries} attempts: {str(last_exception)}"
                ) from last_exception
            raise RetryableError(f"Operation failed after {max_retries} attempts")
                    
        return wrapper
    return decorator

def validate_file_operation(file: FileLike, operation: str) -> None:
    """Validate file object before performing operations.
    
    Args:
        file: File object to validate
        operation: Operation being performed ('lock' or 'unlock')
        
    Raises:
        ValueError: If file object is invalid
    """
    if not isinstance(file, FileLike):
        raise ValueError("File object must implement FileLike protocol")
    
    try:
        fd = file.fileno()
        if fd < 0:
            raise ValueError("Invalid file descriptor")
    except (AttributeError, IOError) as e:
        raise ValueError(f"Cannot get file descriptor: {str(e)}")
    
    if not file.mode.startswith(('r', 'w', 'a')):
        raise ValueError(f"Invalid file mode '{file.mode}' for {operation}")
        
    if file.closed:
        raise ValueError("Cannot perform operation on closed file")

def platform_lock_file(file: FileLike) -> None:
    """Lock a file using platform-specific mechanisms.
    
    Args:
        file: File object to lock
        
    Raises:
        FileLockError: If locking fails
    """
    if not _has_locking:
        return
        
    try:
        validate_file_operation(file, 'lock')
        fd = file.fileno()
        
        if os.name == 'nt':
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except (IOError, OSError) as e:
                raise FileLockError(f"Failed to lock file: {str(e)}") from e
        else:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError) as e:
                raise FileLockError(f"Failed to lock file: {str(e)}") from e
                
    except ValueError as ve:
        logger.warning(f"File validation failed: {str(ve)}")
        raise FileLockError(str(ve)) from ve
    except Exception as e:
        logger.warning(f"Failed to acquire file lock: {str(e)}")
        raise FileLockError(str(e)) from e

def platform_unlock_file(file: FileLike) -> None:
    """Unlock a file using platform-specific mechanisms.
    
    Args:
        file: File object to unlock
    """
    if not _has_locking:
        return
        
    try:
        validate_file_operation(file, 'unlock')
        fd = file.fileno()
        
        if os.name == 'nt':
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except (IOError, OSError) as e:
                logger.warning(f"Failed to unlock file: {str(e)}")
        else:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except (IOError, OSError) as e:
                logger.warning(f"Failed to unlock file: {str(e)}")
                
    except ValueError as ve:
        logger.warning(f"File validation failed during unlock: {str(ve)}")
    except Exception as e:
        logger.warning(f"Failed to release file lock: {str(e)}")

def validate_file_path(path: str, mode: str = 'r') -> None:
    """Validate file path before operations.
    
    Args:
        path: File path to validate
        mode: File open mode ('r' for read, 'w' for write')
        
    Raises:
        ValueError: If path is invalid or inaccessible
    """
    if not path:
        raise ValueError("File path cannot be empty")
        
    if mode == 'r':
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        if not os.path.isfile(path):
            raise ValueError(f"Path is not a file: {path}")
        if not os.access(path, os.R_OK):
            raise FileAccessError(f"File not readable: {path}")
    elif mode == 'w':
        dir_path = os.path.dirname(path) or '.'
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        if not os.access(dir_path, os.W_OK):
            raise FileAccessError(f"Directory not writable: {dir_path}")
    else:
        raise ValueError(f"Invalid file mode: {mode}")

@contextmanager
def safe_open_file(path: str, mode: str = 'r', encoding: Optional[str] = None, 
                   newline: Optional[str] = None, **kwargs) -> Iterator[TextIO]:
    """Safely open a file with proper validation and error handling.
    
    Args:
        path: Path to file
        mode: File open mode
        encoding: File encoding
        newline: Newline handling
        **kwargs: Additional open() arguments
        
    Yields:
        File object
        
    Raises:
        FileOperationError: On file operation errors
    """
    validate_file_path(path, mode[0])
    
    try:
        with open(path, mode, encoding=encoding, newline=newline, **kwargs) as f:
            if 'w' in mode:
                platform_lock_file(f)
            yield f
    except IOError as e:
        raise FileOperationError(f"Failed to {mode} file {path}: {str(e)}")
    finally:
        if 'w' in mode:
            platform_unlock_file(f)

@retry_on_exception()
def read_text_file(path: str, encoding: str = 'utf-8', strip: bool = True) -> str:
    """Read text file with retries.
    
    Args:
        path: Path to file
        encoding: File encoding
        strip: Whether to strip whitespace
        
    Returns:
        File contents as string
        
    Raises:
        FileOperationError: On file operation errors
    """
    with safe_open_file(path, 'r', encoding=encoding) as f:
        content = f.read()
        return content.strip() if strip else content

@retry_on_exception()
def write_text_file(path: str, content: str, encoding: str = 'utf-8', 
                    make_dirs: bool = False, atomic: bool = True) -> None:
    """Write text file with retries.
    
    Args:
        path: Path to file
        content: Content to write
        encoding: File encoding
        make_dirs: Create parent directories if needed
        atomic: Use atomic write
        
    Raises:
        FileOperationError: On file operation errors
    """
    if make_dirs:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
    if atomic:
        temp_path = path + '.tmp'
        try:
            with safe_open_file(temp_path, 'w', encoding=encoding) as f:
                f.write(content)
            atomic_replace(temp_path, path)
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    else:
        with safe_open_file(path, 'w', encoding=encoding) as f:
            f.write(content)

@retry_on_exception()
def read_json_file(path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
    """Read JSON file with retries.
    
    Args:
        path: Path to file
        encoding: File encoding
        
    Returns:
        Parsed JSON data
        
    Raises:
        FileOperationError: On file operation errors
        FileFormatError: On JSON parse errors
    """
    try:
        with safe_open_file(path, 'r', encoding=encoding) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise FileFormatError(f"Invalid JSON in {path}: {str(e)}")

@retry_on_exception()
def write_json_file(path: str, data: Dict[str, Any], encoding: str = 'utf-8',
                    indent: int = 2, ensure_ascii: bool = False, 
                    make_dirs: bool = False, atomic: bool = True) -> None:
    """Write JSON file with retries.
    
    Args:
        path: Path to file
        data: Data to write
        encoding: File encoding
        indent: JSON indentation
        ensure_ascii: Escape non-ASCII characters
        make_dirs: Create parent directories if needed
        atomic: Use atomic write
        
    Raises:
        FileOperationError: On file operation errors
    """
    if make_dirs:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
    content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    
    if atomic:
        temp_path = path + '.tmp'
        try:
            with safe_open_file(temp_path, 'w', encoding=encoding) as f:
                f.write(content)
            atomic_replace(temp_path, path)
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    else:
        with safe_open_file(path, 'w', encoding=encoding) as f:
            f.write(content)

@retry_on_exception()
def read_csv_file(path: str, encoding: str = 'utf-8', delimiter: str = ',', 
                  quotechar: str = '"', has_header: bool = True) -> List[Dict[str, Any]]:
    """Read CSV file with retries.
    
    Args:
        path: Path to file
        encoding: File encoding
        delimiter: CSV delimiter
        quotechar: CSV quote character
        has_header: Whether file has header row
        
    Returns:
        List of row dictionaries
        
    Raises:
        FileOperationError: On file operation errors
        FileFormatError: On CSV parse errors
    """
    try:
        with safe_open_file(path, 'r', encoding=encoding, newline='') as f:
            reader = csv.DictReader(f, delimiter=delimiter, quotechar=quotechar) if has_header else \
                    csv.reader(f, delimiter=delimiter, quotechar=quotechar)
            return [row for row in reader]
    except csv.Error as e:
        raise FileFormatError(f"Invalid CSV in {path}: {str(e)}")

@retry_on_exception()
def write_csv_file(path: str, data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None,
                   encoding: str = 'utf-8', delimiter: str = ',', quotechar: str = '"',
                   make_dirs: bool = False, atomic: bool = True) -> None:
    """Write CSV file with retries.
    
    Args:
        path: Path to file
        data: List of row dictionaries
        fieldnames: List of field names
        encoding: File encoding
        delimiter: CSV delimiter
        quotechar: CSV quote character
        make_dirs: Create parent directories if needed
        atomic: Use atomic write
        
    Raises:
        FileOperationError: On file operation errors
    """
    if make_dirs:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
    if not fieldnames and data:
        fieldnames = list(data[0].keys())
        
    if atomic:
        temp_path = path + '.tmp'
        try:
            with safe_open_file(temp_path, 'w', encoding=encoding, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter, 
                                      quotechar=quotechar)
                writer.writeheader()
                writer.writerows(data)
            atomic_replace(temp_path, path)
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    else:
        with safe_open_file(path, 'w', encoding=encoding, newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter,
                                  quotechar=quotechar)
            writer.writeheader()
            writer.writerows(data)

@contextmanager
def csv_reader(path: str, encoding: str = DEFAULT_ENCODING, delimiter: str = ',', 
               quotechar: str = '"', batch_size: int = DEFAULT_BATCH_SIZE) -> Iterator[BatchType]:
    """Read CSV file in batches with proper context management.
    
    Args:
        path: Path to file
        encoding: File encoding
        delimiter: CSV delimiter
        quotechar: CSV quote character
        batch_size: Number of rows to yield at once
        
    Yields:
        Batches of row dictionaries
        
    Raises:
        FileOperationError: On file operation errors
        FileFormatError: On CSV parse errors
    """
    file_obj = None
    try:
        file_obj = open(path, 'r', encoding=encoding, newline='')
        reader = csv.DictReader(file_obj, delimiter=delimiter, quotechar=quotechar)
        batch = []
        yield batch  # Initial yield for context manager protocol
        
        try:
            for row in reader:
                batch.append(row)
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:  # Don't forget remaining items
                yield batch
        except csv.Error as e:
            raise FileFormatError(f"CSV parse error in {path}: {str(e)}")
        except Exception as e:
            raise FileOperationError(f"Error reading CSV file {path}: {str(e)}")
            
    except Exception as e:
        if isinstance(e, (FileFormatError, FileOperationError)):
            raise
        raise FileOperationError(f"Error setting up CSV reader for {path}: {str(e)}")
    finally:
        if file_obj:
            file_obj.close()

@contextmanager
def get_memory_efficient_reader(path: str, encoding: str = DEFAULT_ENCODING, 
                              batch_size: int = DEFAULT_BATCH_SIZE, **kwargs) -> Iterator[Union[BatchType, JsonData]]:
    """Get memory-efficient reader based on file type.
    
    Args:
        path: Path to file
        encoding: File encoding
        batch_size: Number of items to yield at once
        **kwargs: Additional arguments for specific readers
        
    Returns:
        Generator yielding batches of data
        
    Raises:
        FileOperationError: On file operation errors
        ValueError: If file type is not supported
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
        
    ext = os.path.splitext(path)[1].lower()
    
    try:
        if ext == '.csv':
            file_obj = None
            try:
                file_obj = open(path, 'r', encoding=encoding, newline='')
                reader = csv.DictReader(file_obj, **kwargs)
                
                def csv_batch_generator():
                    batch = []
                    for row in reader:
                        batch.append(row)
                        if len(batch) >= batch_size:
                            yield batch
                            batch = []
                    if batch:
                        yield batch
                    
                yield csv_batch_generator()
                
            except Exception as e:
                if isinstance(e, csv.Error):
                    raise FileFormatError(f"CSV parse error in {path}: {str(e)}")
                raise FileOperationError(f"Error reading CSV file {path}: {str(e)}")
            finally:
                if file_obj:
                    file_obj.close()
                    
        elif ext == '.json':
            with safe_open_file(path, 'r', encoding=encoding) as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise FileFormatError(f"JSON file {path} must contain a list of objects")
                
                def json_batch_generator():
                    batch = []
                    for item in data:
                        batch.append(item)
                        if len(batch) >= batch_size:
                            yield batch
                            batch = []
                    if batch:
                        yield batch
                        
                yield json_batch_generator()
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    except Exception as e:
        logger.error(f"Error reading file {path}: {str(e)}")
        raise

def get_file_size(path: str) -> int:
    """Get file size in bytes.
    
    Args:
        path: Path to file
        
    Returns:
        File size in bytes
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    return os.path.getsize(path)

@retry_on_exception()
def get_files(directory: str, pattern: str = '*', recursive: bool = False) -> List[str]:
    """Get list of files matching pattern.
    
    Args:
        directory: Directory to search
        pattern: Glob pattern to match
        recursive: Whether to search recursively
        
    Returns:
        List of matching file paths
        
    Raises:
        FileOperationError: On file operation errors
    """
    try:
        if recursive:
            matches = []
            for root, _, files in os.walk(directory):
                for filename in files:
                    if fnmatch.fnmatch(filename, pattern):
                        matches.append(os.path.join(root, filename))
            return matches
        else:
            return glob.glob(os.path.join(directory, pattern))
    except OSError as e:
        raise FileOperationError(f"Failed to list files in {directory}: {str(e)}")

@retry_on_exception()
def ensure_directory(path: str) -> None:
    """Ensure directory exists.
    
    Args:
        path: Directory path
        
    Raises:
        FileOperationError: On file operation errors
    """
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise FileOperationError(f"Failed to create directory {path}: {str(e)}")

@retry_on_exception()
def backup_file(source: str, suffix: str = '.bak', max_backups: int = 5) -> str:
    """Create backup of file.
    
    Args:
        source: Source file path
        suffix: Backup file suffix
        max_backups: Maximum number of backups to keep
        
    Returns:
        Backup file path
        
    Raises:
        FileOperationError: On file operation errors
    """
    # Ensure source exists
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")
        
    # Find next available backup name
    backup_base = source + suffix
    backup_path = backup_base
    counter = 1
    
    while os.path.exists(backup_path) and counter < max_backups:
        backup_path = f"{backup_base}.{counter}"
        counter += 1
        
    # Remove oldest backup if at limit
    if counter == max_backups and os.path.exists(backup_path):
        os.unlink(backup_path)
        
    # Copy source to backup
    try:
        shutil.copy2(source, backup_path)
        return backup_path
    except OSError as e:
        raise FileOperationError(f"Failed to create backup of {source}: {str(e)}")

@retry_on_exception()
def safe_delete(path: str) -> None:
    """Safely delete file.
    
    Args:
        path: File path
        
    Raises:
        FileOperationError: On file operation errors
    """
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError as e:
        raise FileOperationError(f"Failed to delete {path}: {str(e)}")

@retry_on_exception(max_retries=2)  # Fewer retries for atomic operations
def atomic_replace(source: str, target: str) -> None:
    """Atomically replace target with source.
    
    Args:
        source: Source file path
        target: Target file path
        
    Raises:
        FileOperationError: On file operation errors
    """
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")
        
    # Create backup of target if it exists
    if os.path.exists(target):
        try:
            backup_path = backup_file(target)
        except FileOperationError:
            backup_path = None
            
    try:
        # Perform atomic replace
        if os.name == 'nt':
            # Windows - use rename + replace
            if os.path.exists(target):
                os.replace(source, target)
            else:
                os.rename(source, target)
        else:
            # Unix - use rename (atomic on Unix)
            os.rename(source, target)
            
        # Remove backup on success
        if backup_path:
            safe_delete(backup_path)
            
    except OSError as e:
        # Restore from backup on failure
        if backup_path and os.path.exists(backup_path):
            try:
                os.rename(backup_path, target)
            except OSError:
                pass  # Can't restore backup
        raise FileOperationError(f"Failed to replace {target} with {source}: {str(e)}")
