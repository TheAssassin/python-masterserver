import os

from setuptools import setup, find_packages


setup(
    name="masterserver",
    version="0.0.1",
    packages=find_packages(),
    license="MIT",
    long_description=open(os.path.join(os.path.dirname(__file__), "README.md")).read(),
    install_requires=[
        "aiohttp",
    ],
    extras_require={
        "coloredlogs": [
            "pytest",
            "coloredlogs",
        ],
        "tests": [
            "tox",
        ],
    },
    entry_points={
        "console_scripts": [
            "masterserver = masterserver.cli:run",
        ],
    },
)
