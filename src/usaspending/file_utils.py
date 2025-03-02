"""Platform-specific file operations module."""
import os
import logging
import json
import csv
import time
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, TextIO, BinaryIO, Iterator
from contextlib import contextmanager
from io import StringIO, BytesIO
from functools import wraps

logger = logging.getLogger(__name__)

# Platform-specific imports and constants
_has_locking = False
LOCK_EX = 2  # Exclusive lock
LOCK_UN = 8  # Unlock 
LOCK_NB = 4  # Non-blocking

try:
    if os.name == 'nt':
        import msvcrt
        _has_locking = True
    else:
        try:
            import fcntl
            # Get constants or use defaults
            LOCK_EX = getattr(fcntl, 'LOCK_EX', 2)
            LOCK_UN = getattr(fcntl, 'LOCK_UN', 8)  
            LOCK_NB = getattr(fcntl, 'LOCK_NB', 4)
            _has_locking = True
        except ImportError:
            pass
except ImportError:
    logger.warning("File locking modules not available on this platform")

# Default retry settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_RETRY_EXCEPTIONS = (IOError, OSError)

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

class RetryableError(FileOperationError):
    """Exception for errors that can be retried."""
    pass

def retry_on_exception(max_retries: int = DEFAULT_MAX_RETRIES,
                       retry_delay: float = DEFAULT_RETRY_DELAY,
                       backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
                       retry_exceptions: tuple = DEFAULT_RETRY_EXCEPTIONS) -> Callable:
    """Decorator to retry functions on exception.
    
    Args:
        max_retries: Maximum number of retries
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Factor to increase delay by after each retry
        retry_exceptions: Tuple of exceptions to retry on
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            delay = retry_delay
            
            while attempt <= max_retries:
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {str(e)}")
                        raise RetryableError(f"Operation failed after {max_retries} retries: {str(e)}")
                        
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} failed for {func.__name__}: "
                        f"{str(e)}. Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
                    
        return wrapper
    return decorator

def validate_file_operation(file: Any, operation: str) -> None:
    """Validate file object before performing operations.
    
    Args:
        file: File object to validate
        operation: Operation being performed ('lock' or 'unlock')
        
    Raises:
        ValueError: If file object is invalid
    """
    if not hasattr(file, 'fileno'):
        raise ValueError("File object must have fileno() method")
    try:
        fd = file.fileno()
        if fd < 0:
            raise ValueError("Invalid file descriptor")
    except (AttributeError, IOError) as e:
        raise ValueError(f"Cannot get file descriptor: {str(e)}")
    
    if not file.mode.startswith(('r', 'w', 'a')):
        raise ValueError(f"Invalid file mode '{file.mode}' for {operation}")
        
    # Check if file is closed
    if file.closed:
        raise ValueError("Cannot perform operation on closed file")

def platform_lock_file(file: Any) -> None:
    """Lock a file using platform-specific mechanisms."""
    if not _has_locking:
        return
        
    try:
        validate_file_operation(file, 'lock')
        
        if os.name == 'nt':
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            if 'fcntl' in globals():
                fcntl.flock(file.fileno(), LOCK_EX | LOCK_NB)
                
    except ValueError as ve:
        logger.warning(f"File validation failed: {str(ve)}")
    except Exception as e:
        logger.warning(f"Failed to acquire file lock: {str(e)}")

def platform_unlock_file(file: Any) -> None:
    """Unlock a file using platform-specific mechanisms."""
    if not _has_locking:
        return
        
    try:
        validate_file_operation(file, 'unlock')
        
        if os.name == 'nt':
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            if 'fcntl' in globals():
                fcntl.flock(file.fileno(), LOCK_UN)
                
    except ValueError as ve:
        logger.warning(f"File validation failed: {str(ve)}")
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
            raise FileNotFoundError(f"File does not exist: {path}")
        if not os.path.isfile(path):
            raise ValueError(f"Path is not a file: {path}")
        if not os.access(path, os.R_OK):
            raise FileAccessError(f"File is not readable: {path}")
    elif mode == 'w':
        dir_path = os.path.dirname(path) or '.'
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Directory does not exist: {dir_path}")
        if not os.access(dir_path, os.W_OK):
            raise FileAccessError(f"Directory is not writable: {dir_path}")
    else:
        raise ValueError(f"Invalid file mode: {mode}")

@contextmanager
def safe_open_file(path: str, mode: str = 'r', encoding: Optional[str] = None, 
                  newline: Optional[str] = None, **kwargs) -> TextIO:
    """Safely open a file with validation and error handling.
    
    Args:
        path: Path to file
        mode: File mode ('r', 'w', 'a', etc.)
        encoding: File encoding
        newline: Newline character handling
        **kwargs: Additional arguments for open()
        
    Yields:
        File object
        
    Raises:
        FileOperationError: On file operation errors
    """
    file = None
    try:
        is_read = 'r' in mode and not ('+' in mode)
        validate_file_path(path, 'r' if is_read else 'w')
        file = open(path, mode, encoding=encoding, newline=newline, **kwargs)
        yield file
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Error opening file {path}: {str(e)}")
    except (IOError, OSError) as e:
        raise FileAccessError(f"Error accessing file {path}: {str(e)}")
    except Exception as e:
        raise FileOperationError(f"Error with file {path}: {str(e)}")
    finally:
        if file and not file.closed:
            try:
                file.close()
            except Exception as e:
                logger.warning(f"Error closing file {path}: {str(e)}")

@retry_on_exception()
def read_text_file(path: str, encoding: str = 'utf-8', strip: bool = True) -> str:
    """Read text file with retry logic.
    
    Args:
        path: Path to file
        encoding: File encoding
        strip: Whether to strip whitespace from content
        
    Returns:
        File content as string
        
    Raises:
        FileOperationError: On file operation errors
    """
    with safe_open_file(path, 'r', encoding=encoding) as f:
        content = f.read()
        return content.strip() if strip else content

@retry_on_exception()
def write_text_file(path: str, content: str, encoding: str = 'utf-8', 
                   make_dirs: bool = False, atomic: bool = True) -> None:
    """Write text file with retry logic and atomic operations.
    
    Args:
        path: Path to file
        content: Content to write
        encoding: File encoding
        make_dirs: Create parent directories if they don't exist
        atomic: Use atomic write operation
        
    Raises:
        FileOperationError: On file operation errors
    """
    if make_dirs:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    
    if atomic:
        temp_path = f"{path}.tmp"
        try:
            with safe_open_file(temp_path, 'w', encoding=encoding) as f:
                f.write(content)
            os.replace(temp_path, path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise FileOperationError(f"Error writing file {path}: {str(e)}")
    else:
        with safe_open_file(path, 'w', encoding=encoding) as f:
            f.write(content)

@retry_on_exception()
def read_json_file(path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
    """Read JSON file with retry logic.
    
    Args:
        path: Path to file
        encoding: File encoding
        
    Returns:
        Parsed JSON data
        
    Raises:
        FileOperationError: On file operation errors
        FileFormatError: On JSON parsing errors
    """
    try:
        with safe_open_file(path, 'r', encoding=encoding) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise FileFormatError(f"Invalid JSON in file {path}: {str(e)}")

@retry_on_exception()
def write_json_file(path: str, data: Dict[str, Any], encoding: str = 'utf-8',
                   indent: int = 2, ensure_ascii: bool = False, 
                   make_dirs: bool = False, atomic: bool = True) -> None:
    """Write JSON file with retry logic and atomic operations.
    
    Args:
        path: Path to file
        data: Data to write
        encoding: File encoding
        indent: JSON indentation
        ensure_ascii: Whether to ensure ASCII output
        make_dirs: Create parent directories if they don't exist
        atomic: Use atomic write operation
        
    Raises:
        FileOperationError: On file operation errors
    """
    try:
        json_content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
        write_text_file(path, json_content, encoding=encoding, 
                       make_dirs=make_dirs, atomic=atomic)
    except TypeError as e:
        raise FileFormatError(f"Error serializing JSON for file {path}: {str(e)}")

@retry_on_exception()
def read_csv_file(path: str, encoding: str = 'utf-8', delimiter: str = ',', 
                 quotechar: str = '"', has_header: bool = True) -> List[Dict[str, Any]]:
    """Read CSV file with retry logic.
    
    Args:
        path: Path to file
        encoding: File encoding
        delimiter: CSV delimiter
        quotechar: CSV quote character
        has_header: Whether file has header row
        
    Returns:
        List of dictionaries with CSV data
        
    Raises:
        FileOperationError: On file operation errors
        FileFormatError: On CSV parsing errors
    """
    try:
        with safe_open_file(path, 'r', encoding=encoding, newline='') as f:
            if has_header:
                reader = csv.DictReader(f, delimiter=delimiter, quotechar=quotechar)
                return list(reader)
            else:
                reader = csv.reader(f, delimiter=delimiter, quotechar=quotechar)
                data = list(reader)
                return [dict(zip([f"col{i}" for i in range(len(row))], row)) for row in data]
    except csv.Error as e:
        raise FileFormatError(f"CSV parsing error in file {path}: {str(e)}")

@retry_on_exception()
def write_csv_file(path: str, data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None,
                  encoding: str = 'utf-8', delimiter: str = ',', quotechar: str = '"',
                  make_dirs: bool = False, atomic: bool = True) -> None:
    """Write CSV file with retry logic and atomic operations.
    
    Args:
        path: Path to file
        data: List of dictionaries to write
        fieldnames: List of field names (column headers)
        encoding: File encoding
        delimiter: CSV delimiter
        quotechar: CSV quote character
        make_dirs: Create parent directories if they don't exist
        atomic: Use atomic write operation
        
    Raises:
        FileOperationError: On file operation errors
    """
    if not data:
        raise ValueError("No data provided for CSV writing")
        
    # Determine fieldnames if not provided
    if fieldnames is None:
        fieldnames = list(data[0].keys())
        
    if make_dirs:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    
    try:
        if atomic:
            temp_path = f"{path}.tmp"
            with safe_open_file(temp_path, 'w', encoding=encoding, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter, 
                                      quotechar=quotechar, quoting=csv.QUOTE_MINIMAL)
                writer.writeheader()
                writer.writerows(data)
            os.replace(temp_path, path)
        else:
            with safe_open_file(path, 'w', encoding=encoding, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter, 
                                      quotechar=quotechar, quoting=csv.QUOTE_MINIMAL)
                writer.writeheader()
                writer.writerows(data)
    except csv.Error as e:
        raise FileFormatError(f"CSV writing error for file {path}: {str(e)}")
    except Exception as e:
        if atomic and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        raise FileOperationError(f"Error writing CSV file {path}: {str(e)}")

@contextmanager
def csv_reader(path: str, encoding: str = 'utf-8', delimiter: str = ',', 
              quotechar: str = '"', batch_size: int = 1000) -> Iterator[Dict[str, Any]]:
    """Generator for reading CSV in batches with proper resource management.
    
    Args:
        path: Path to CSV file
        encoding: File encoding
        delimiter: CSV delimiter
        quotechar: CSV quote character
        batch_size: Number of rows to yield at once
        
    Yields:
        Batches of CSV rows as dictionaries
        
    Raises:
        FileOperationError: On file operation errors
    """
    try:
        with safe_open_file(path, 'r', encoding=encoding, newline='') as f:
            reader = csv.DictReader(f, delimiter=delimiter, quotechar=quotechar)
            batch = []
            for row in reader:
                batch.append(row)
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:  # Yield any remaining rows
                yield batch
    except csv.Error as e:
        raise FileFormatError(f"CSV parsing error in file {path}: {str(e)}")

@retry_on_exception()
def ensure_directory(path: str) -> None:
    """Ensure directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Raises:
        FileOperationError: On directory creation error
    """
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        raise FileOperationError(f"Failed to create directory {path}: {str(e)}")

@retry_on_exception()
def backup_file(source: str, suffix: str = '.bak', max_backups: int = 5) -> str:
    """Create backup of a file with versioning.
    
    Args:
        source: Source file path
        suffix: Backup file suffix
        max_backups: Maximum number of backup versions to keep
        
    Returns:
        Backup file path
        
    Raises:
        FileOperationError: On backup error
    """
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file does not exist: {source}")
        
    # Create backup with timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = f"{source}.{timestamp}{suffix}"
    
    try:
        shutil.copy2(source, backup_path)
        
        # Clean up old backups if needed
        dir_path = os.path.dirname(source) or '.'
        base_name = os.path.basename(source)
        backups = sorted([
            os.path.join(dir_path, f) for f in os.listdir(dir_path)
            if f.startswith(base_name + '.') and f.endswith(suffix)
        ])
        
        # Remove oldest backups if we have too many
        while len(backups) > max_backups:
            try:
                os.remove(backups[0])
                backups.pop(0)
            except Exception as e:
                logger.warning(f"Failed to remove old backup {backups[0]}: {str(e)}")
                break
                
        return backup_path
    except Exception as e:
        raise FileOperationError(f"Failed to create backup of {source}: {str(e)}")

@retry_on_exception()
def safe_delete(path: str) -> None:
    """Safely delete a file with retry logic.
    
    Args:
        path: Path to file
        
    Raises:
        FileOperationError: On deletion error
    """
    if not os.path.exists(path):
        return
        
    try:
        os.remove(path)
    except Exception as e:
        raise FileOperationError(f"Failed to delete file {path}: {str(e)}")

@retry_on_exception(max_retries=2)  # Fewer retries for atomic operations
def atomic_replace(source: str, target: str) -> None:
    """Atomically replace target file with source file.
    
    Args:
        source: Source file path
        target: Target file path
        
    Raises:
        FileOperationError: On replace error
    """
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file does not exist: {source}")
        
    try:
        # On Windows, we may need special handling if target exists
        if os.path.exists(target) and os.name == 'nt':
            temp_path = f"{target}.replacing"
            if os.path.exists(temp_path):
                os.remove(temp_path)
            os.rename(target, temp_path)
            os.rename(source, target)
            os.remove(temp_path)
        else:
            os.replace(source, target)
    except Exception as e:
        raise FileOperationError(f"Failed to replace {target} with {source}: {str(e)}")

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
        raise FileNotFoundError(f"File does not exist: {path}")
    return os.path.getsize(path)

def get_memory_efficient_reader(path: str, encoding: str = 'utf-8', 
                              batch_size: int = 1000, **kwargs) -> Iterator:
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
    """
    ext = os.path.splitext(path)[1].lower()
    
    if ext == '.csv':
        return csv_reader(
            path, 
            encoding=encoding, 
            batch_size=batch_size,
            delimiter=kwargs.get('delimiter', ','), 
            quotechar=kwargs.get('quotechar', '"')
        )
    elif ext == '.json':
        # For JSON files, we currently need to load the whole file
        # A more efficient JSON streaming parser could be implemented if needed
        data = read_json_file(path, encoding=encoding)
        if isinstance(data, list):
            for i in range(0, len(data), batch_size):
                yield data[i:i+batch_size]
        else:
            yield data
    else:
        raise ValueError(f"Unsupported file type: {ext}")
