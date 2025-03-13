import pytest
from typing import Dict, Any, Optional
from functools import wraps
import logging
from src.usaspending.core.utils import (
    safe_operation,
    implements,
    singleton,
    lazy_property,
    LoggerMixin,
    retry_operation,
    timing_decorator
)
from src.usaspending.core.exceptions import ConfigurationError

# Test class for singleton pattern
@singleton
class TestSingleton:
    def __init__(self):
        self.value = 0
    
    def increment(self):
        self.value += 1
        return self.value

# Test interface for implements decorator
class ITestInterface:
    def required_method(self) -> str:
        raise NotImplementedError

@implements(ITestInterface)
class ValidImplementation:
    def required_method(self) -> str:
        return "implemented"

class TestLoggerMixin(LoggerMixin):
    pass

def test_safe_operation_decorator():
    # Test function with safe_operation
    @safe_operation
    def safe_func(value: Optional[str] = None) -> str:
        if value is None:
            raise ValueError("Value cannot be None")
        return value.upper()
    
    # Test successful operation
    assert safe_func("test") == "TEST"
    
    # Test operation with error
    with pytest.raises(ValueError):
        safe_func(None)
    
    # Test with custom error handling
    @safe_operation(error_value="default")
    def safe_func_with_default(value: Optional[str] = None) -> str:
        if value is None:
            raise ValueError("Value cannot be None")
        return value.upper()
    
    assert safe_func_with_default(None) == "default"

def test_singleton_pattern():
    # Get singleton instances
    instance1 = TestSingleton()
    instance2 = TestSingleton()
    
    # Test instance equality
    assert instance1 is instance2
    
    # Test state is shared
    instance1.increment()
    assert instance2.value == 1
    
    instance2.increment()
    assert instance1.value == 2

def test_implements_decorator():
    # Test valid implementation
    impl = ValidImplementation()
    assert impl.required_method() == "implemented"
    
    # Test invalid implementation
    with pytest.raises(TypeError):
        @implements(ITestInterface)
        class InvalidImplementation:
            pass  # Missing required_method

def test_lazy_property_decorator():
    class TestClass:
        def __init__(self):
            self.compute_count = 0
        
        @lazy_property
        def expensive_computation(self):
            self.compute_count += 1
            return "computed_value"
    
    obj = TestClass()
    
    # First access should compute
    assert obj.expensive_computation == "computed_value"
    assert obj.compute_count == 1
    
    # Second access should use cached value
    assert obj.expensive_computation == "computed_value"
    assert obj.compute_count == 1

def test_logger_mixin():
    logger = TestLoggerMixin()
    
    # Test logger initialization
    assert logger.logger is not None
    assert isinstance(logger.logger, logging.Logger)
    assert logger.logger.name == "TestLoggerMixin"

def test_retry_operation():
    mock_calls = 0
    
    @retry_operation(max_attempts=3, delay=0.1)
    def flaky_operation():
        nonlocal mock_calls
        mock_calls += 1
        if mock_calls < 3:
            raise RuntimeError("Temporary failure")
        return "success"
    
    # Test successful retry
    result = flaky_operation()
    assert result == "success"
    assert mock_calls == 3
    
    # Test operation that always fails
    mock_calls = 0
    @retry_operation(max_attempts=2, delay=0.1)
    def failing_operation():
        nonlocal mock_calls
        mock_calls += 1
        raise RuntimeError("Permanent failure")
    
    with pytest.raises(RuntimeError):
        failing_operation()
    assert mock_calls == 2

def test_timing_decorator():
    @timing_decorator
    def timed_operation():
        return "result"
    
    # Test timing capture
    result = timed_operation()
    assert result == "result"
    
    # Test timing info was logged (would need to capture logs to verify)

def test_safe_operation_with_cleanup():
    cleanup_called = False
    
    @safe_operation
    def operation_with_cleanup():
        try:
            raise ValueError("Test error")
        finally:
            nonlocal cleanup_called
            cleanup_called = True
    
    with pytest.raises(ValueError):
        operation_with_cleanup()
    
    assert cleanup_called

def test_lazy_property_inheritance():
    class BaseClass:
        @lazy_property
        def base_property(self):
            return "base"
    
    class DerivedClass(BaseClass):
        @lazy_property
        def derived_property(self):
            return self.base_property + "_derived"
    
    obj = DerivedClass()
    assert obj.derived_property == "base_derived"

def test_singleton_inheritance():
    @singleton
    class BaseSingleton:
        pass
    
    @singleton
    class DerivedSingleton(BaseSingleton):
        pass
    
    base1 = BaseSingleton()
    base2 = BaseSingleton()
    derived1 = DerivedSingleton()
    derived2 = DerivedSingleton()
    
    assert base1 is base2
    assert derived1 is derived2
    assert base1 is not derived1

def test_logger_mixin_inheritance():
    class BaseLogger(LoggerMixin):
        pass
    
    class DerivedLogger(BaseLogger):
        pass
    
    base = BaseLogger()
    derived = DerivedLogger()
    
    assert base.logger.name == "BaseLogger"
    assert derived.logger.name == "DerivedLogger"
    assert base.logger is not derived.logger
