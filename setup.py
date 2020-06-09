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
        "bn_crypto @ git+https://github.com/TheAssassin/bluenebula-auth.git#egg=bn_crypto",
    ],
    extras_require={
        "coloredlogs": [
            "pytest",
            "coloredlogs",
        ],
        "tests": [
            "tox",
        ],
        "sentry": [
            "sentry_sdk",
        ]
    },
    entry_points={
        "console_scripts": [
            "masterserver = masterserver.cli:run",
        ],
    },
)
