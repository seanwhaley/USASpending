"""System startup validation."""
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .logging_config import get_logger
from .config_validation import ConfigValidator
from .exceptions import ConfigurationError

logger = get_logger(__name__)

@dataclass
class StartupCheck:
    """Configuration for a startup validation check."""
    name: str
    check_function: Callable[[], bool]
    error_message: str
    severity: str = "error"
    dependencies: List[str] = None
    timeout: float = 5.0  # seconds

class StartupValidator:
    """Validates system configuration at startup."""
    
    def __init__(self, config_validator: ConfigValidator):
        """Initialize with configuration validator."""
        self.config_validator = config_validator
        self.checks: Dict[str, StartupCheck] = {}
        self.results: Dict[str, bool] = {}
        self.messages: List[str] = []
        
    def add_check(self, check: StartupCheck) -> None:
        """Add a validation check."""
        self.checks[check.name] = check
        
    def run_checks(self, parallel: bool = True) -> bool:
        """Run all validation checks."""
        # First validate configuration
        errors = self.config_validator.validate_config(self.config_validator.config)
        if errors:
            for error in errors:
                self.messages.append(f"{error.severity.upper()}: {error.path}: {error.message}")
            return False
        
        # Then run component checks
        self.results.clear()
        self.messages = []  # Keep config validation messages
        
        if parallel:
            return self._run_parallel_checks()
        return self._run_sequential_checks()
        
    def _run_parallel_checks(self) -> bool:
        """Run checks in parallel where possible."""
        all_passed = True
        
        # Group checks by dependencies
        independent_checks = []
        dependent_checks = []
        
        for check in self.checks.values():
            if not check.dependencies:
                independent_checks.append(check)
            else:
                dependent_checks.append(check)
                
        # Run independent checks in parallel
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._run_single_check, check): check
                for check in independent_checks
            }
            
            for future in as_completed(futures):
                check = futures[future]
                try:
                    passed = future.result()
                    self.results[check.name] = passed
                    all_passed = all_passed and (
                        passed or check.severity != "error"
                    )
                except Exception as e:
                    logger.error(f"Check {check.name} failed with error: {e}")
                    self.results[check.name] = False
                    all_passed = False
                    
        # Run dependent checks sequentially
        for check in dependent_checks:
            # Verify dependencies passed
            dependencies_passed = all(
                self.results.get(dep, False)
                for dep in (check.dependencies or [])
            )
            
            if dependencies_passed:
                passed = self._run_single_check(check)
                self.results[check.name] = passed
                all_passed = all_passed and (
                    passed or check.severity != "error"
                )
            else:
                self.results[check.name] = False
                self.messages.append(
                    f"Skipped {check.name} due to failed dependencies"
                )
                if check.severity == "error":
                    all_passed = False
                    
        return all_passed
        
    def _run_sequential_checks(self) -> bool:
        """Run checks sequentially."""
        all_passed = True
        
        for name, check in self.checks.items():
            passed = self._run_single_check(check)
            self.results[name] = passed
            all_passed = all_passed and (
                passed or check.severity != "error"
            )
            
        return all_passed
        
    def _run_single_check(self, check: StartupCheck) -> bool:
        """Run a single validation check."""
        try:
            start_time = time.time()
            result = check.check_function()
            elapsed_time = time.time() - start_time
            
            if elapsed_time > check.timeout:
                logger.warning(
                    f"Check {check.name} exceeded timeout "
                    f"({elapsed_time:.2f}s > {check.timeout:.2f}s)"
                )
                
            if not result:
                self.messages.append(
                    f"{check.severity.upper()}: {check.error_message}"
                )
                
            return result
            
        except Exception as e:
            logger.error(f"Check {check.name} failed with error: {e}")
            self.messages.append(
                f"ERROR: {check.name} check failed - {str(e)}"
            )
            return False
            
    def get_messages(self) -> List[str]:
        """Get validation messages."""
        return self.messages.copy()
        
    def get_results(self) -> Dict[str, bool]:
        """Get validation results."""
        return dict(self.results)

def perform_startup_checks(config_validator: Optional[ConfigValidator] = None,
                         parallel: bool = True) -> bool:
    """Perform system startup validation checks.
    
    Args:
        config_validator: Optional config validator instance
        parallel: Whether to run checks in parallel when possible
        
    Returns:
        True if all checks pass, False otherwise
    """
    if not config_validator:
        from .config import ConfigManager
        config = ConfigManager()
        config_validator = ConfigValidator(config)
        
    validator = StartupValidator(config_validator)
    
    # Add standard checks
    validator.add_check(StartupCheck(
        name="config_validation",
        check_function=lambda: len(config_validator.validate_config()) == 0,
        error_message="Configuration validation failed"
    ))
    
    validator.add_check(StartupCheck(
        name="logging_setup",
        check_function=lambda: logger is not None,
        error_message="Logging system not properly initialized"
    ))
    
    # Run checks
    success = validator.run_checks(parallel=parallel)
    
    # Log results
    if not success:
        for msg in validator.get_messages():
            logger.error(msg)
    
    return success