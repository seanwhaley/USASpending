"""Report generation and dashboard preparation tools."""

import os
import json
import shutil
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from .common import BaseReport, DirectoryHelper, FileHelper, ProjectPathHelper, JSONFileOperations
from .analyzers import CoverageAnalyzer, TestQualityAnalyzer, TestGapAnalyzer

class ValidationReportGenerator(BaseReport):
    """Generate validation reports based on test results and coverage data."""
    
    def __init__(self, output_dir: Optional[str] = None):
        if not output_dir:
            output_dir = str(DirectoryHelper.get_results_dir())
        super().__init__(output_dir)
        self.thresholds = {
            'min_coverage': 70.0,
            'critical_modules_coverage': 80.0,
            'min_quality_score': 60.0
        }
    
    def _check_coverage(self, coverage_data: Dict) -> Dict:
        """Validate coverage meets thresholds"""
        overall_coverage = coverage_data.get('coverage_percent', 0)
        return {
            'name': 'coverage_threshold',
            'passed': overall_coverage >= self.thresholds['min_coverage'],
            'message': (
                f"Code coverage ({overall_coverage:.1f}%) is "
                f"{'above' if overall_coverage >= self.thresholds['min_coverage'] else 'below'} "
                f"threshold of {self.thresholds['min_coverage']}%"
            )
        }
    
    def _check_quality(self, quality_data: Dict) -> Dict:
        """Validate test quality meets thresholds"""
        quality_score = quality_data.get('overall_quality_score', 0)
        return {
            'name': 'test_quality_threshold',
            'passed': quality_score >= self.thresholds['min_quality_score'],
            'message': (
                f"Test quality score ({quality_score:.1f}) is "
                f"{'above' if quality_score >= self.thresholds['min_quality_score'] else 'below'} "
                f"threshold of {self.thresholds['min_quality_score']}"
            )
        }
    
    def _check_gaps(self, gap_data: Dict) -> Dict:
        """Validate there are no critical test gaps"""
        gaps = gap_data.get('gaps', [])
        return {
            'name': 'no_test_gaps',
            'passed': len(gaps) == 0,
            'message': (
                "No test gaps found" if len(gaps) == 0
                else f"{len(gaps)} modules found without tests"
            )
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate validation report by checking all metrics"""
        # Load reports directly from the results directory
        coverage_data = FileHelper.load_json_file(
            DirectoryHelper.get_results_dir() / 'coverage_report.json', 
            {}
        )
        quality_data = FileHelper.load_json_file(
            DirectoryHelper.get_results_dir() / 'test_quality_report.json',
            {}
        )
        gap_data = FileHelper.load_json_file(
            DirectoryHelper.get_results_dir() / 'test_gap_report.json',
            {}
        )
        
        # Run checks
        checks = [
            self._check_coverage(coverage_data),
            self._check_quality(quality_data),
            self._check_gaps(gap_data)
        ]
        
        # Compile report
        report = {
            'validation_summary': {
                'passed': all(check['passed'] for check in checks),
                'total_checks': len(checks),
                'passed_checks': sum(1 for check in checks if check['passed']),
                'failed_checks': sum(1 for check in checks if not check['passed']),
                'validation_checks': checks
            }
        }
        
        JSONFileOperations.add_common_report_data(report)
        self.save_report(report, 'validation_report.json')
        return report


class DashboardGenerator(BaseReport):
    """Generate the test coverage dashboard."""
    
    def __init__(self, template_dir: str = 'static/tests_dashboard', output_dir: Optional[str] = None):
        if not output_dir:
            # Generate dashboard directly at output/test_dashboard
            output_dir = str(DirectoryHelper.get_project_root() / 'output' / 'test_dashboard')
        super().__init__(output_dir)
        self.template_dir = template_dir
        self.available_reports = self._check_available_reports()

    def _check_available_reports(self) -> Dict[str, bool]:
        """Check which report files exist in the results directory"""
        results_dir = DirectoryHelper.get_results_dir()
        return {
            'coverage': (results_dir / 'coverage_report.json').exists(),
            'quality': (results_dir / 'test_quality_report.json').exists(),
            'gaps': (results_dir / 'test_gap_report.json').exists(),
            'functional': (results_dir / 'functional_coverage_report.json').exists(),
            'validation': (results_dir / 'validation_report.json').exists(),
            'history': (results_dir / 'coverage_history.json').exists()
        }
    
    def _copy_static_files(self, static_dir: Path, output_dir: Path) -> None:
        """Copy static files to output directory."""
        # Copy css and js directories
        for item in ['css', 'js']:
            src_path = static_dir / item
            dest_path = output_dir / item
            
            if src_path.exists():
                # Handle directory removal with error handling
                if dest_path.exists():
                    try:
                        # Try to remove existing directory
                        shutil.rmtree(dest_path)
                    except (PermissionError, OSError) as e:
                        # If removal fails, try to update files individually
                        print(f"Warning: Could not remove existing {item} directory: {str(e)}")
                        print(f"Attempting to update files individually...")
                        try:
                            # Copy files individually instead
                            if not dest_path.exists():
                                os.makedirs(dest_path)
                            
                            for src_file in src_path.glob('**/*'):
                                if src_file.is_file():
                                    rel_path = src_file.relative_to(src_path)
                                    dest_file = dest_path / rel_path
                                    
                                    # Create parent directories if needed
                                    if not dest_file.parent.exists():
                                        os.makedirs(dest_file.parent)
                                        
                                    # Copy the file, overwriting if it exists
                                    shutil.copy2(src_file, dest_file)
                        except Exception as copy_error:
                            print(f"Warning: Could not update {item} files: {str(copy_error)}")
                else:
                    # If destination doesn't exist, create it fresh
                    try:
                        shutil.copytree(src_path, dest_path)
                    except Exception as e:
                        print(f"Warning: Could not copy {item} directory: {str(e)}")

        # Copy index.html directly
        src_index = static_dir / 'index.html'
        if src_index.exists():
            try:
                shutil.copy2(src_index, output_dir / 'index.html')
            except Exception as e:
                print(f"Warning: Could not copy index.html: {str(e)}")
    
    def _create_config(self, output_dir: Path) -> None:
        """Create dashboard configuration file."""
        # Use direct paths to results files in the root results directory
        data_paths = {}
        if self.available_reports['coverage']:
            data_paths['coverage'] = 'results/coverage_report.json'
        if self.available_reports['quality']:
            data_paths['quality'] = 'results/test_quality_report.json'
        if self.available_reports['gaps']:
            data_paths['gaps'] = 'results/test_gap_report.json'
        if self.available_reports['validation']:
            data_paths['validation'] = 'results/validation_report.json'
        if self.available_reports['functional']:
            data_paths['functional'] = 'results/functional_coverage_report.json'
        if self.available_reports['history']:
            data_paths['history'] = 'results/coverage_history.json'

        config = {
            'dataPaths': data_paths,
            'generatedAt': datetime.datetime.now().isoformat(),
            'environment': self.environment,
            'dashboardVersion': '1.0.0',
            'availableReports': self.available_reports
        }
        
        config_dir = output_dir / 'js'
        DirectoryHelper.ensure_dir(config_dir)
        
        with open(config_dir / 'config.js', 'w') as f:
            f.write('// This file is auto-generated - do not edit directly\n')
            f.write(f'const CONFIG = {json.dumps(config, indent=2)};\n')
    
    def _create_ai_summary(self, output_dir: Path) -> None:
        """Create AI-friendly summary of test issues."""
        results_dir = DirectoryHelper.get_results_dir()
        issues = []
        
        if self.available_reports['gaps']:
            gap_data = FileHelper.load_json_file(
                results_dir / 'test_gap_report.json', 
                {}
            )
            for gap in gap_data.get('gaps', []):
                issues.append({
                    'type': 'coverage_gap',
                    'module': gap,
                    'priority': 'high',
                    'recommendation': 'Create test coverage for this module'
                })
        
        if self.available_reports['validation']:
            validation_data = FileHelper.load_json_file(
                results_dir / 'validation_report.json',
                {}
            )
            for check in validation_data.get('validation_summary', {}).get('validation_checks', []):
                if not check.get('passed', True):
                    issues.append({
                        'type': 'validation_failure',
                        'message': check.get('message', ''),
                        'priority': 'high',
                        'recommendation': 'Fix validation failure'
                    })
        
        # Create summary
        summary = {
            'timestamp': datetime.datetime.now().isoformat(),
            'environment': self.environment,
            'total_issues': len(issues),
            'test_issues': issues,
            'report_availability': self.available_reports
        }
        
        # Save summary to results directory
        FileHelper.save_json_report(summary, DirectoryHelper.get_results_dir() / 'ai_test_summary.json')
    
    def generate_dashboard(self) -> None:
        """Generate the complete test dashboard."""
        # Ensure results structure exists
        ProjectPathHelper.ensure_results_structure()
        
        static_dir = ProjectPathHelper.get_project_root() / 'static' / 'tests_dashboard'
        
        # Check what reports are available
        print("\nReport availability:")
        for report, available in self.available_reports.items():
            print(f"  - {report}: {'Available' if available else 'Not available'}")
        
        # Ensure dashboard directory exists and is clean
        DirectoryHelper.ensure_dir(self.output_dir)
        
        # Copy static files
        self._copy_static_files(static_dir, self.output_dir)
        
        # Create config.js
        self._create_config(self.output_dir)
        
        # Create AI summary
        self._create_ai_summary(self.output_dir)
        
        print(f"\nDashboard generated successfully at {self.output_dir / 'index.html'}")
        if not all(self.available_reports.values()):
            print("\nNote: Some reports were not available. The dashboard will show partial data.")
            print("Run with fewer --skip options to generate a complete dashboard.")


class PerformanceReportGenerator(BaseReport):
    """Generate performance reports from test metrics."""
    
    def __init__(self, output_dir: Optional[str] = None):
        if not output_dir:
            output_dir = str(DirectoryHelper.get_results_dir())
        super().__init__(output_dir)
    
    def generate_report(self, metrics: Dict[str, List]) -> Dict[str, Any]:
        """Generate a performance report from collected metrics.
        
        Args:
            metrics: Dictionary of metric names to list of (timestamp, value) tuples
            
        Returns:
            Dict containing the performance report data
        """
        summary = {}
        
        # Calculate summary statistics for each metric
        for metric_key, values in metrics.items():
            category, name = metric_key.split('.')
            if category not in summary:
                summary[category] = {}
                
            metric_values = [v[1] for v in values]  # Extract just the values
            if metric_values:
                summary[category][name] = {
                    'min': min(metric_values),
                    'max': max(metric_values),
                    'avg': sum(metric_values) / len(metric_values)
                }
        
        # Compile report
        report = {
            'summary': summary,
            'metrics': metrics,
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        JSONFileOperations.add_common_report_data(report)
        self.save_report(report, 'performance_report.json')
        return report


def update_coverage_history(reports_dir: Optional[Path] = None) -> None:
    """Update the coverage history with current coverage data."""
    results_dir = DirectoryHelper.get_results_dir()
    
    # Load current coverage directly from results dir
    coverage_data = FileHelper.load_json_file(
        results_dir / 'coverage_report.json'
    )
    if not coverage_data:
        print("No coverage data found")
        return
    
    coverage_value = coverage_data.get('coverage_percent', 0)
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # Load or create history
    history_file = results_dir / 'coverage_history.json'
    history = FileHelper.load_json_file(history_file, {'dates': [], 'coverage': []})
    
    # Update history
    if not history['dates'] or history['dates'][-1] != current_date:
        history['dates'].append(current_date)
        history['coverage'].append(coverage_value)
        
        # Limit to last 30 entries
        if len(history['dates']) > 30:
            history['dates'] = history['dates'][-30:]
            history['coverage'] = history['coverage'][-30:]
            
        # Save updated history
        FileHelper.save_json_report(history, history_file)
        print(f"Coverage history updated. Latest coverage: {coverage_value:.2f}%")


if __name__ == "__main__":
    dashboard = DashboardGenerator()
    dashboard.generate_dashboard()