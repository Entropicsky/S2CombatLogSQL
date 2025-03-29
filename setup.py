from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="smite_parser",
    version="0.1.0",
    author="AI Agent",
    author_email="example@example.com",
    description="Parser for SMITE 2 combat logs to SQLite database",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/smite_parser",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "smite-parser=smite_parser.cli:main",
        ],
    },
) 