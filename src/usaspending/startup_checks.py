"""Startup validation system for checking initialization requirements."""
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
import os
import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .interfaces import (
    IEntityFactory, IEntityStore, IValidationService,
    IEntityMapper, IDataProcessor, ITransformerFactory
)
from .logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class StartupCheck:
    """Configuration for a startup validation check."""
    name: str
    check_function: Callable[[], bool]
    error_message: str
    severity: str = "error"  # error, warning, info
    dependencies: List[str] = None
    timeout: float = 5.0  # seconds

class StartupValidator:
    """Validates system configuration at startup."""
    
    def __init__(self):
        """Initialize validator."""
        self.checks: Dict[str, StartupCheck] = {}
        self.results: Dict[str, bool] = {}
        self.messages: List[str] = []
        
    def add_check(self, check: StartupCheck) -> None:
        """Add a validation check."""
        self.checks[check.name] = check
        
    def run_checks(self, parallel: bool = True) -> bool:
        """Run all validation checks."""
        self.results.clear()
        self.messages.clear()
        
        if parallel:
            return self._run_parallel_checks()
        return self._run_sequential_checks()
        
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

class SystemValidator:
    """Validates core system components and configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with system configuration."""
        self.config = config
        self.validator = StartupValidator()
        self._add_standard_checks()
        
    def _add_standard_checks(self) -> None:
        """Add standard system validation checks."""
        # Configuration checks
        self.validator.add_check(StartupCheck(
            name="config_paths",
            check_function=self._check_paths,
            error_message="Required paths are missing or inaccessible",
            severity="error"
        ))
        
        self.validator.add_check(StartupCheck(
            name="config_permissions",
            check_function=self._check_permissions,
            error_message="Insufficient permissions for required paths",
            severity="error",
            dependencies=["config_paths"]
        ))
        
        # Component checks
        self.validator.add_check(StartupCheck(
            name="entity_factory",
            check_function=self._check_entity_factory,
            error_message="Entity factory initialization failed",
            severity="error"
        ))
        
        self.validator.add_check(StartupCheck(
            name="entity_store",
            check_function=self._check_entity_store,
            error_message="Entity store initialization failed",
            severity="error",
            dependencies=["entity_factory"]
        ))
        
        self.validator.add_check(StartupCheck(
            name="validation_service",
            check_function=self._check_validation_service,
            error_message="Validation service initialization failed",
            severity="error"
        ))
        
        # Optional component checks
        self.validator.add_check(StartupCheck(
            name="transformer_factory",
            check_function=self._check_transformer_factory,
            error_message="Transformer factory initialization failed",
            severity="warning"
        ))
        
    def _check_paths(self) -> bool:
        """Check required paths exist and are accessible."""
        required_paths = self.config.get('paths', {})
        for path_name, path in required_paths.items():
            if not os.path.exists(path):
                logger.error(f"Required path missing: {path_name} = {path}")
                return False
        return True
        
    def _check_permissions(self) -> bool:
        """Check permissions on required paths."""
        required_paths = self.config.get('paths', {})
        for path_name, path in required_paths.items():
            if not os.access(path, os.R_OK | os.W_OK):
                logger.error(f"Insufficient permissions: {path_name} = {path}")
                return False
        return True
        
    def _check_entity_factory(self) -> bool:
        """Check entity factory configuration."""
        factory_config = self.config.get('entity_factory', {})
        factory_class = factory_config.get('class')
        if not factory_class:
            return False
            
        try:
            module_path, class_name = factory_class.rsplit('.', 1)
            module = importlib.import_module(module_path)
            factory_cls = getattr(module, class_name)
            return issubclass(factory_cls, IEntityFactory)
        except Exception:
            return False
            
    def _check_entity_store(self) -> bool:
        """Check entity store configuration."""
        store_config = self.config.get('entity_store', {})
        store_class = store_config.get('class')
        if not store_class:
            return False
            
        try:
            module_path, class_name = store_class.rsplit('.', 1)
            module = importlib.import_module(module_path)
            store_cls = getattr(module, class_name)
            return issubclass(store_cls, IEntityStore)
        except Exception:
            return False
            
    def _check_validation_service(self) -> bool:
        """Check validation service configuration."""
        validation_config = self.config.get('validation_service', {})
        service_class = validation_config.get('class')
        if not service_class:
            return False
            
        try:
            module_path, class_name = service_class.rsplit('.', 1)
            module = importlib.import_module(module_path)
            service_cls = getattr(module, class_name)
            return issubclass(service_cls, IValidationService)
        except Exception:
            return False
            
    def _check_transformer_factory(self) -> bool:
        """Check transformer factory configuration."""
        transform_config = self.config.get('transformer_factory', {})
        factory_class = transform_config.get('class')
        if not factory_class:
            return True  # Optional component
            
        try:
            module_path, class_name = factory_class.rsplit('.', 1)
            module = importlib.import_module(module_path)
            factory_cls = getattr(module, class_name)
            return issubclass(factory_cls, ITransformerFactory)
        except Exception:
            return False
            
    def validate(self) -> bool:
        """Run all system validation checks."""
        return self.validator.run_checks()
        
    def get_messages(self) -> List[str]:
        """Get validation messages."""
        return self.validator.get_messages()
        
    def get_results(self) -> Dict[str, bool]:
        """Get validation results."""
        return self.validator.get_results()