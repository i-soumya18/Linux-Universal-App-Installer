#!/usr/bin/env python3
"""
Linux Universal App Installer
A professional drag-and-drop application installer for Linux.
"""

import sys
import os
from setuptools import setup, find_packages

# Read the README file if it exists
readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
if os.path.exists(readme_path):
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_description = f.read()
else:
    long_description = __doc__

setup(
    name="linux-universal-app-installer",
    version="2.0.0",
    description="A professional drag-and-drop application installer for Linux",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Linux Universal App Installer Team",
    author_email="installer@example.com",
    url="https://github.com/linux-app-installer/linux-universal-app-installer",
    packages=find_packages(),
    py_modules=['main'],
    include_package_data=True,
    install_requires=[
        'PyQt5>=5.15.0',
    ],
    extras_require={
        'dev': [
            'pytest>=6.0.0',
            'pytest-qt>=3.3.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'linux-app-installer=main:main',
        ],
        'gui_scripts': [
            'linux-app-installer-gui=main:main',
        ],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: System :: Installation/Setup',
        'Topic :: Desktop Environment',
    ],
    keywords='linux installer appimage deb snap flatpak application installer',
    python_requires='>=3.8',
    zip_safe=False,
)