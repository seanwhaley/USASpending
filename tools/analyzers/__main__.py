"""Command-line interface for analyzer tools."""

import sys
import argparse

from . import (
    CoverageAnalyzer,
    TestQualityAnalyzer,
    TestGapAnalyzer,
    FunctionalCoverageAnalyzer
)

def main():
    """Run the requested analyzer tool."""
    parser = argparse.ArgumentParser(description="Run test analysis tools")
    parser.add_argument('analyzer', choices=[
        'CoverageAnalyzer',
        'TestQualityAnalyzer',
        'TestGapAnalyzer',
        'FunctionalCoverageAnalyzer'
    ], help='The analyzer to run')
    args = parser.parse_args()
    
    # Create and run the requested analyzer
    analyzer_class = globals()[args.analyzer]
    analyzer = analyzer_class()
    analyzer.generate_report()
    return 0

if __name__ == '__main__':
    sys.exit(main())