from setuptools import setup, find_packages

setup(
    name="property_data_platform",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "packages": [
            "ingest=property_data_platform.ingest:main",
        ],
    },
    install_requires=[
        "setuptools",
        "requests",
        "beautifulsoup4",
        "yfinance",
        "pandas",
    ],
)
