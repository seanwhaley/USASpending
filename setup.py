"""Setup configuration for USASpending package."""
from setuptools import setup, find_packages

setup(
    name="usaspending",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "PyYAML>=6.0.1,<7.0.0",
        "python-dateutil==2.8.2",
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