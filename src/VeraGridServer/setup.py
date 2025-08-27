# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
import os

from VeraGridServer.__version__ import __VeraGridServer_VERSION__

here = os.path.abspath(os.path.dirname(__file__))

long_description = """# VeraGrid

This software aims to be a complete platform for power systems research and simulation.

[Watch the video https](https://youtu.be/SY66WgLGo54)

[Check out the documentation](https://gridcal.readthedocs.io)


## Installation

pip install VeraGridServer

For more options (including a standalone setup one), follow the
[installation instructions]( https://gridcal.readthedocs.io/en/latest/getting_started/install.html)
from the project's [documentation](https://gridcal.readthedocs.io)
"""

description = 'VeraGrid is a Power Systems simulation program intended for professional use and research'

base_path = os.path.join('VeraGridServer')

pkgs_to_exclude = ['docs', 'research', 'tests', 'tutorials', 'VeraGridEngine']

packages = find_packages(exclude=pkgs_to_exclude)

# ... so we have to do the filtering ourselves
packages2 = list()
for package in packages:
    elms = package.split('.')
    excluded = False
    for exclude in pkgs_to_exclude:
        if exclude in elms:
            excluded = True

    if not excluded:
        packages2.append(package)

package_data = {'VeraGridServer': ['*.md',
                                  '*.rst',
                                  'LICENSE.txt',
                                  'setup.py',
                                  'data/VeraGrid_icon.ico'],
                }

dependencies = ['setuptools>=41.0.1',
                'wheel>=0.37.2',
                "fastapi",
                "uvicorn",
                "websockets",
                "cryptography",
                "VeraGridEngine==" + __VeraGridServer_VERSION__,  # the VeraGridEngine version must be exactly the same
                ]

extras_require = {
    'gch5 files': ["tables"]  # this is for h5 compatibility
}
# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='VeraGridServer',  # Required
    version=__VeraGridServer_VERSION__,  # Required
    license='MPL2',
    description=description,  # Optional
    long_description=long_description,  # Optional
    long_description_content_type='text/markdown',  # Optional (see note above)
    url='https://github.com/SanPen/VeraGrid',  # Optional
    author='Santiago Peñate Vera et. Al.',  # Optional
    author_email='spenate@eroots.tech',  # Optional
    classifiers=[
        'Programming Language :: Python :: 3.8',
    ],
    keywords='power systems planning',  # Optional
    packages=packages2,  # Required
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=dependencies,
    extras_require=extras_require,
    package_data=package_data,
    entry_points={
        'console_scripts': [
            'gridcalserver = VeraGridServer.run:start_server',
        ],
    },
)
