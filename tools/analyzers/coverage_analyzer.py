"""Coverage analysis implementation."""

import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional

from ..common import BaseReport, DirectoryHelper

class CoverageAnalyzer(BaseReport):
    """Analyze test coverage from coverage.xml files."""
    
    def __init__(self, coverage_file: Optional[str] = None):
        # Get default coverage file path if none provided
        if not coverage_file:
            coverage_dir = DirectoryHelper.get_results_dir()
            coverage_file = str(coverage_dir / 'coverage.xml')
        super().__init__(Path(coverage_file).parent)
        self.coverage_file = coverage_file
        self.coverage_data = defaultdict(dict)
    
    def parse_coverage_xml(self):
        """Parse the coverage XML file and build a nested module structure"""
        tree = ET.parse(self.coverage_file)
        root = tree.getroot()
        
        for package in root.findall('.//package'):
            package_name = package.get('name')
            for class_ in package.findall('class'):
                class_name = class_.get('name')
                full_name = f"{package_name}.{class_name}"
                
                lines = class_.find('lines')
                total_lines = len(lines)
                covered_lines = sum(1 for line in lines if line.get('hits') != '0')
                
                self.coverage_data[full_name] = {
                    'total_lines': total_lines,
                    'covered_lines': covered_lines,
                    'coverage_percent': (covered_lines / total_lines) * 100 if total_lines > 0 else 0
                }
    
    def generate_report(self):
        """Generate coverage report"""
        self.parse_coverage_xml()
        
        total_lines = sum(data['total_lines'] for data in self.coverage_data.values())
        covered_lines = sum(data['covered_lines'] for data in self.coverage_data.values())
        
        report = {
            'total_files': len(self.coverage_data),
            'total_lines': total_lines,
            'covered_lines': covered_lines,
            'coverage_percent': (covered_lines / total_lines * 100) if total_lines else 0,
            'files': self.coverage_data
        }
        
        # Save directly to results directory
        self.save_report(report, 'coverage_report.json')
        return report