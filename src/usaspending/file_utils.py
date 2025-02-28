"""Platform-specific file operations module."""
import os
import logging
from typing import Any

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
            raise ValueError(f"File does not exist: {path}")
        if not os.path.isfile(path):
            raise ValueError(f"Path is not a file: {path}")
        if not os.access(path, os.R_OK):
            raise ValueError(f"File is not readable: {path}")
    elif mode == 'w':
        dir_path = os.path.dirname(path) or '.'
        if not os.path.exists(dir_path):
            raise ValueError(f"Directory does not exist: {dir_path}")
        if not os.access(dir_path, os.W_OK):
            raise ValueError(f"Directory is not writable: {dir_path}")
    else:
        raise ValueError(f"Invalid file mode: {mode}")
