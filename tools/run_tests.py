#!/usr/bin/env python
"""Run pytest with coverage and generate test analysis reports."""

import sys
import os
import subprocess
import argparse
import shutil
from pathlib import Path
import pytest
import time
import psutil
from typing import Dict, List, Optional

# Import directly from the tools package
from tools import DirectoryHelper, ProjectPathHelper
from .reports import PerformanceReportGenerator

def run_tests(tests_path: str = None, 
              coverage: bool = True, 
              verbose: bool = False, 
              pattern: str = None) -> bool:
    """Run pytest with coverage.
    
    Args:
        tests_path: Optional path to test directory or file
        coverage: Whether to collect coverage data
        verbose: Enable verbose output
        pattern: Test name pattern to run specific tests
        
    Returns:
        bool: True if tests passed
    """
    print("Running tests with pytest...")
    
    # Ensure results directory structure exists 
    ProjectPathHelper.ensure_results_structure()
    
    # Default test path is the tests directory
    if not tests_path:
        tests_path = os.path.join(ProjectPathHelper.get_project_root(), 'tests')
    
    # Build pytest command
    cmd = ['pytest']
    
    # Add coverage if requested
    if coverage:
        cmd.extend([
            '--cov=src', 
            '--cov-report=term', 
            f'--cov-report=xml:{DirectoryHelper.get_results_dir()}/coverage.xml'
        ])
    
    # Add verbosity if requested
    if verbose:
        cmd.append('-v')
    
    # Add pattern if specified
    if pattern:
        cmd.append(f'-k {pattern}')
    
    # Add tests path
    cmd.append(tests_path)
    
    # Run pytest
    try:
        result = subprocess.run(' '.join(cmd), shell=True, check=False)
        success = result.returncode == 0
        
        if success:
            print("All tests passed successfully!")
        else:
            print(f"Tests failed with return code {result.returncode}")
            
        return success
    except Exception as e:
        print(f"Error running tests: {str(e)}")
        return False

class PerformanceTestRunner:
    """Run tests while collecting performance metrics."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / 'output' / 'performance'
        self.output_dir = output_dir
        self.metrics: Dict[str, List] = {}
        self.start_time = time.time()
        
    def record_metric(self, category: str, name: str, value: float) -> None:
        """Record a performance metric."""
        key = f"{category}.{name}"
        if key not in self.metrics:
            self.metrics[key] = []
        self.metrics[key].append((time.time() - self.start_time, value))
        
    def get_process_metrics(self) -> Dict[str, float]:
        """Get current process resource metrics."""
        process = psutil.Process()
        return {
            'cpu_percent': process.cpu_percent(),
            'memory_mb': process.memory_info().rss / 1024 / 1024
        }
        
    def run_performance_tests(self) -> None:
        """Run performance tests with metrics collection."""
        # Record initial resource state 
        initial_metrics = self.get_process_metrics()
        self.record_metric('resources', 'initial_cpu', initial_metrics['cpu_percent'])
        self.record_metric('resources', 'initial_memory', initial_metrics['memory_mb'])
        
        # Run performance tests
        pytest.main(['tests/test_performance.py', '-v'])
        
        # Record final resource state
        final_metrics = self.get_process_metrics()
        self.record_metric('resources', 'final_cpu', final_metrics['cpu_percent'])
        self.record_metric('resources', 'final_memory', final_metrics['memory_mb'])
        
        # Generate performance report
        report_generator = PerformanceReportGenerator(self.output_dir)
        report = report_generator.generate_report(self.metrics)
        
        print("\nPerformance test run completed.")
        print(f"Report generated at: {self.output_dir}/performance_report.json")
        print("\nSummary:")
        for category, metrics in report['summary'].items():
            print(f"\n{category.title()} Metrics:")
            for metric_name, stats in metrics.items():
                print(f"  {metric_name}:")
                print(f"    Min: {stats['min']:.2f}")
                print(f"    Max: {stats['max']:.2f}")
                print(f"    Avg: {stats['avg']:.2f}")

def main():
    """Run all tests with performance monitoring."""
    runner = PerformanceTestRunner()
    runner.run_performance_tests()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run tests with pytest and coverage")
    parser.add_argument('--path', help='Path to test directory or file')
    parser.add_argument('--no-coverage', action='store_true', help='Disable coverage collection')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--pattern', '-k', help='Test name pattern to run specific tests')
    args = parser.parse_args()
    
    success = run_tests(
        tests_path=args.path,
        coverage=not args.no_coverage,
        verbose=args.verbose,
        pattern=args.pattern
    )
    
    sys.exit(0 if success else 1)
    main()