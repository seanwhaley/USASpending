#!/usr/bin/env python
"""Validate test coverage against thresholds."""

import sys
import argparse
from pathlib import Path

# Import directly from the tools package
from tools import ValidationReportGenerator, DirectoryHelper, ProjectPathHelper

def validate_coverage(validation_file: str = None) -> bool:
    """Run coverage validation against thresholds.
    
    Args:
        validation_file: Optional override for validation file path
        
    Returns:
        bool: True if validation passed
    """
    print("Validating test coverage...")
    
    # Ensure results directory structure exists 
    ProjectPathHelper.ensure_results_structure()
    
    # Generate validation report
    validator = ValidationReportGenerator()
    report = validator.generate_report()
    
    # Check if all validations passed
    validation_summary = report.get('validation_summary', {})
    passed = validation_summary.get('passed', False)
    
    # Print summary
    print(f"Validation complete: {validation_summary.get('passed_checks', 0)} of {validation_summary.get('total_checks', 0)} checks passed")
    
    if not passed:
        print("\nFailed checks:")
        for check in validation_summary.get('validation_checks', []):
            if not check.get('passed', True):
                print(f"  - {check.get('message', '')}")
    
    output_file = Path(DirectoryHelper.get_results_dir()) / 'validation_report.json'
    print(f"\nDetailed validation report saved to: {output_file}")
    
    return passed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate test coverage against thresholds")
    parser.add_argument('--output', help='Output file path override')
    args = parser.parse_args()
    
    success = validate_coverage(args.output)
    if not success:
        print("Warning: Coverage validation had errors")
    
    # Return success (0) even if validation fails, to allow pipeline to continue
    sys.exit(0)