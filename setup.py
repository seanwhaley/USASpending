"""Setup configuration for USASpending package."""
from setuptools import setup, find_packages

setup(
    name="usaspending",
    version="0.1.0",
    packages=find_packages(include=['usaspending*', 'tools*']),
    package_dir={
        "usaspending": "src/usaspending",
        "tools": "tools"
    },
    install_requires=[
        "PyYAML>=6.0.1,<7.0.0",
        "python-dateutil>=2.9.0.post0",  # Updated to latest version
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "mypy>=1.8.0",
            "types-PyYAML>=6.0.12.12",
        ]
    },
    python_requires=">=3.9",
)