"""Gap analysis implementation."""

import os
from pathlib import Path
from typing import Dict, Optional

from ..common import BaseReport, DirectoryHelper

class TestGapAnalyzer(BaseReport):
    """Analyze gaps in test coverage."""
    
    def __init__(self, src_dir: str = 'src', test_dir: str = 'tests', output_dir: Optional[str] = None):
        if not output_dir:
            output_dir = str(DirectoryHelper.get_results_dir())
        super().__init__(output_dir)
        self.src_dir = src_dir
        self.test_dir = test_dir
        self.implementation_files = set()
        self.test_files = set()
    
    def gather_files(self):
        """Gather all implementation and test files"""
        for root, _, files in os.walk(self.src_dir):
            for file in files:
                if file.endswith('.py'):
                    self.implementation_files.add(os.path.relpath(os.path.join(root, file), self.src_dir))
        
        for root, _, files in os.walk(self.test_dir):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    self.test_files.add(os.path.relpath(os.path.join(root, file), self.test_dir))
    
    def analyze_gaps(self):
        """Find implementation files without corresponding tests"""
        gaps = []
        
        for impl_file in self.implementation_files:
            test_file = f"test_{impl_file}"
            if test_file not in self.test_files:
                gaps.append(impl_file)
        
        return gaps
    
    def generate_report(self):
        """Generate test gap report"""
        self.gather_files()
        gaps = self.analyze_gaps()
        
        report = {
            'total_implementation_files': len(self.implementation_files),
            'total_test_files': len(self.test_files),
            'gaps': gaps,
            'action_items': [{
                'file': gap,
                'priority': 'high',
                'recommendation': 'Create tests for this file'
            } for gap in gaps]
        }
        
        self.save_report(report, 'test_gap_report.json')
        return report