"""Common utilities and functions used across the test tools."""

import os
import json, time
import datetime
from pathlib import Path
from typing import Dict, Any, Union, Optional, List

def detect_environment() -> str:
    """
    Detect the current environment based on environment variables.
    
    Checks for the following:
    - CI/CD: CI, GITHUB_ACTIONS, GITLAB_CI, JENKINS_URL, TRAVIS, CIRCLECI
    - Production: PRODUCTION, ENV=production, ENVIRONMENT=production, DJANGO_ENV=production, NODE_ENV=production
    - Development: Default when no other environment is detected
    
    Returns:
        str: One of 'ci', 'production', or 'development'
    """
    # Check for CI/CD environments
    ci_vars = ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_URL', 'TRAVIS', 'CIRCLECI']
    if any(os.getenv(var) for var in ci_vars):
        return 'ci'
    
    # Check for production environment
    prod_indicators = [
        os.getenv('PRODUCTION'),
        os.getenv('ENV') == 'production',
        os.getenv('ENVIRONMENT') == 'production',
        os.getenv('DJANGO_ENV') == 'production',
        os.getenv('NODE_ENV') == 'production'
    ]
    if any(prod_indicators):
        return 'production'
    
    # Default to development
    return 'development'

class DirectoryHelper:
    """Helper class for directory operations."""
    
    @staticmethod
    def ensure_dir(path: Union[str, Path]) -> Path:
        """Ensure a directory exists and return its Path object."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_project_root() -> Path:
        """Get the project root directory."""
        return Path(__file__).parent.parent
    
    @staticmethod
    def get_results_dir() -> Path:
        """Get the centralized results directory path."""
        return DirectoryHelper.get_project_root() / "output" / "test_dashboard" / "results"

class FileHelper:
    """Helper class for file operations."""
    
    @staticmethod
    def save_json_report(data: Dict[str, Any], output_file: Union[str, Path], indent: int = 2) -> None:
        """Save data as a JSON file, ensuring the directory exists."""
        output_file = Path(output_file)
        DirectoryHelper.ensure_dir(output_file.parent)
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=indent, default=str)  # Added default=str for datetime serialization
    
    @staticmethod
    def load_json_file(file_path: Union[str, Path], default: Optional[Dict] = None) -> Dict:
        """Load a JSON file or return the default if the file doesn't exist."""
        file_path = Path(file_path)
        if not file_path.exists():
            return default if default is not None else {}
            
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return default if default is not None else {}

class BaseReport:
    """Base class for report generators with common functionality."""
    
    def __init__(self, output_dir: Optional[Union[str, Path]] = None):
        """Initialize report generator with optional output directory override."""
        self.output_dir = Path(output_dir) if output_dir else DirectoryHelper.get_results_dir()
        self.environment = detect_environment()
        self.timestamp = datetime.datetime.now().isoformat()
    
    def save_report(self, data: Dict[str, Any], filename: str) -> None:
        """Save report data to a JSON file in the output directory."""
        output_file = self.output_dir / filename
        FileHelper.save_json_report(data, output_file)

class JSONFileOperations:
    """Helper class for JSON file operations."""
    
    @staticmethod
    def add_common_report_data(report: Dict[str, Any]) -> Dict[str, Any]:
        """Add common metadata to a report dictionary."""
        report.update({
            'timestamp': datetime.datetime.now().isoformat(),
            'environment': detect_environment(),
            'generated_by': os.getenv('USERNAME') or os.getenv('USER') or 'unknown'
        })
        return report

class ProjectPathHelper:
    """Helper class for project path operations."""
    
    @staticmethod
    def get_project_root() -> Path:
        """Get the project root directory."""
        return DirectoryHelper.get_project_root()
    
    @staticmethod
    def get_results_dir() -> Path:
        """Get the centralized results directory path."""
        return DirectoryHelper.get_results_dir()
    
    @staticmethod
    def get_relative_path(path: Union[str, Path], base: Optional[Union[str, Path]] = None) -> str:
        """Get path relative to base (defaults to project root)."""
        path = Path(path)
        base = Path(base) if base else ProjectPathHelper.get_project_root()
        return str(path.relative_to(base))

    @staticmethod
    def ensure_results_structure() -> None:
        """Ensure the basic results directory structure exists."""
        # Create main results directory
        results_dir = DirectoryHelper.get_results_dir()
        DirectoryHelper.ensure_dir(results_dir)

class Timer:
    """Context manager for timing code execution."""

    def __init__(self, description: str = "Operation"):
        """Initialize timer with optional description."""
        self.description = description
        self.start_time: Optional[float] = None

    def __enter__(self) -> None:
        """Start timer."""
        self.start_time = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timer and print elapsed time."""
        elapsed_time = time.time() - self.start_time
        print(f"{self.description} took {elapsed_time:.4f} seconds")
