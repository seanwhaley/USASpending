"""Command-line interface for test analysis tools."""

import sys
import argparse
from pathlib import Path

from . import (
    analyze_test_quality,
    generate_coverage,
    validate_coverage,
    run_tests,
    TestQualityAnalyzer,
    TestGapAnalyzer,
    FunctionalCoverageAnalyzer,
    DashboardGenerator
)

def main():
    """Run the requested tool."""
    parser = argparse.ArgumentParser(description="Test analysis tools")
    parser.add_argument('tool', choices=[
        'analyze_test_quality',
        'generate_coverage',
        'validate_coverage',
        'run_tests',
        'gap_analysis',
        'functional_analysis',
        'generate_dashboard'
    ], help='The tool to run')
    parser.add_argument('--output', help='Optional output file override')
    args = parser.parse_args()
    
    try:
        if args.tool == 'analyze_test_quality':
            analyze_test_quality(args.output)
        elif args.tool == 'generate_coverage':
            generate_coverage(args.output)
        elif args.tool == 'validate_coverage':
            validate_coverage(args.output)
        elif args.tool == 'run_tests':
            run_tests()
        elif args.tool == 'gap_analysis':
            analyzer = TestGapAnalyzer()
            analyzer.generate_report()
        elif args.tool == 'functional_analysis':
            analyzer = FunctionalCoverageAnalyzer()
            analyzer.generate_report()
        elif args.tool == 'generate_dashboard':
            dashboard = DashboardGenerator()
            dashboard.generate_dashboard()
        return 0
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())