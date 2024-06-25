# This file is part of GridCal.g
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
"""
A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
import os

from GridCal.__version__ import __GridCal_VERSION__


here = os.path.abspath(os.path.dirname(__file__))

long_description = '''# GridCal

This software aims to be a complete platform for power systems research and simulation.

[Watch the video https](https://youtu.be/SY66WgLGo54)

[Check out the documentation](https://gridcal.readthedocs.io)


## Installation

pip install GridCal

For more options (including a standalone setup one), follow the
[installation instructions]( https://gridcal.readthedocs.io/en/latest/getting_started/install.html)
from the project's [documentation](https://gridcal.readthedocs.io)
'''

description = 'GridCal is a Power Systems simulation program intended for professional use and research'

base_path = os.path.join('GridCal')

pkgs_to_exclude = ['docs', 'research', 'tests', 'tutorials', 'GridCalEngine']

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


package_data = {'GridCal': ['*.md',
                            '*.rst',
                            'LICENSE.txt',
                            'setup.py',
                            'data/cables.csv',
                            'data/transformers.csv',
                            'data/wires.csv',
                            'data/sequence_lines.csv'],
                }

dependencies = ['setuptools>=41.0.1',
                'wheel>=0.37.2',
                "PySide6<=6.6.3.1",  # 5.14 breaks the UI generation for development, 6.7.0 breaks all
                "numpy>=1.19.0,<2.0.0",
                "scipy>=1.0.0",
                "networkx>=2.1",
                "pandas>=1.0",
                "ortools>=9.8.0",
                "xlwt>=1.3.0",
                "xlrd>=1.1.0",
                "matplotlib>=2.1.1",
                "qtconsole>=4.5.4",
                "openpyxl>=2.4.9",
                "chardet>=3.0.4",  # for the psse files character detection
                "scikit-learn>=0.18",
                "geopy>=1.16",
                "pytest>=7.2",
                "h5py>=2.9.0",
                "numba>=0.46",  # to compile routines natively
                'pyproj',
                'pyarrow',
                'ortools',
                "darkdetect",
                "pyqtdarktheme",
                "nptyping",
                "windpowerlib",
                "pvlib",
                "hyperopt",
                "rdflib",
                "websockets",
                "opencv-python",
                "packaging",
                "GridCalEngine==" + __GridCal_VERSION__,  # the GridCalEngine version must be exactly the same
                ]

extras_require = {
        'gch5 files':  ["tables"]  # this is for h5 compatibility
    }
# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='GridCal',  # Required
    version=__GridCal_VERSION__,  # Required
    license='LGPL',
    description=description,  # Optional
    long_description=long_description,  # Optional
    long_description_content_type='text/markdown',  # Optional (see note above)
    url='https://github.com/SanPen/GridCal',  # Optional
    author='Santiago Peñate Vera et. Al.',  # Optional
    author_email='santiago@gridcal.org',  # Optional
    classifiers=[
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
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
            'gridcal = GridCal.ExecuteGridCal:runGridCal',
            'GridCal = GridCal.ExecuteGridCal:runGridCal',
        ],
    },
)
