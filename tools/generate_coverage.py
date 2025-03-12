#!/usr/bin/env python
"""Generate coverage reports from coverage.xml files."""

import sys
import argparse
from pathlib import Path

# Import directly from the tools package
from tools import CoverageAnalyzer, DirectoryHelper, ProjectPathHelper

def generate_coverage(coverage_file: str = None) -> bool:
    """Generate coverage reports from coverage.xml.
    
    Args:
        coverage_file: Optional override for coverage.xml file path
        
    Returns:
        bool: True if coverage report was generated successfully
    """
    print("Generating coverage report...")
    
    # Ensure results directory structure exists 
    ProjectPathHelper.ensure_results_structure()
    
    # Set up coverage file path
    if not coverage_file:
        coverage_dir = DirectoryHelper.get_results_dir()
        coverage_file = str(coverage_dir / 'coverage.xml')
    
    # Check if coverage file exists
    if not Path(coverage_file).exists():
        print(f"Error: Coverage file not found at {coverage_file}")
        return False
    
    # Generate report
    analyzer = CoverageAnalyzer(coverage_file=coverage_file)
    report = analyzer.generate_report()
    
    # Print summary
    coverage_percent = report.get('coverage_percent', 0)
    print(f"Total coverage: {coverage_percent:.1f}%")
    print(f"Files analyzed: {report.get('total_files', 0)}")
    print(f"Total lines: {report.get('total_lines', 0)}")
    print(f"Covered lines: {report.get('covered_lines', 0)}")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate coverage reports from coverage.xml")
    parser.add_argument('--coverage-file', help='Coverage XML file path')
    args = parser.parse_args()
    
    success = generate_coverage(args.coverage_file)
    sys.exit(0 if success else 1)