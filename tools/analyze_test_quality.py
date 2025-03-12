#!/usr/bin/env python
"""Run test quality analysis using the TestQualityAnalyzer."""

import sys
from pathlib import Path
import argparse

# Import from the tools package directly
from tools import TestQualityAnalyzer, DirectoryHelper, ProjectPathHelper

def analyze_test_quality(output_path: str = None) -> bool:
    """Run test quality analysis.
    
    Args:
        output_path: Optional override for output file path
        
    Returns:
        bool: True if analysis completed successfully
    """
    print("Analyzing test quality...")
    
    # Ensure results directory structure exists 
    ProjectPathHelper.ensure_results_structure()
    
    # Set up output path - default to results directory
    if output_path:
        output_file = Path(output_path)
        output_dir = output_file.parent
    else:
        output_dir = DirectoryHelper.get_results_dir()
        output_file = output_dir / 'test_quality_report.json'
    
    # Run analysis
    analyzer = TestQualityAnalyzer(output_dir=output_dir)
    report = analyzer.generate_report()
    
    # Print summary
    print(f"Overall test quality score: {report['overall_quality_score']:.1f}/100")
    print(f"{len(report['low_quality_tests'])} test files need quality improvements")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run test quality analysis")
    parser.add_argument('--output', help='Output file path override')
    args = parser.parse_args()
    
    success = analyze_test_quality(args.output)
    sys.exit(0 if success else 1)