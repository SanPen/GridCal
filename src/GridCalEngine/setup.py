"""
A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
import os

from GridCalEngine.__version__ import __GridCalEngine_VERSION__

here = os.path.abspath(os.path.dirname(__file__))

long_description = '''# GridCal

This software aims to be a complete platform for power systems research and simulation.

[Watch the video https](https://youtu.be/SY66WgLGo54)

[Check out the documentation](https://gridcal.readthedocs.io)


## Installation

pip install GridCalEngine

For more options (including a standalone setup one), follow the
[installation instructions]( https://gridcal.readthedocs.io/en/latest/getting_started/install.html)
from the project's [documentation](https://gridcal.readthedocs.io)
'''

description = 'GridCal is a Power Systems simulation program intended for professional use and research'

pkgs_to_exclude = ['docs', 'research', 'tests', 'tutorials', 'GridCal']

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

package_data = {'GridCalEngine': ['LICENSE.txt', 'setup.py'], }

dependencies = ['setuptools>=41.0.1',
                'wheel>=0.37.2',
                "numpy>=1.19.0",
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
                "pytest>=3.8",
                "h5py>=2.9.0",
                "numba>=0.46",  # to compile routines natively
                'pyproj',
                'pyarrow',
                'ortools',
                "nptyping",
                "windpowerlib",
                "pvlib",
                "hyperopt",
                ]

extras_require = {
    'gch5 files': ["tables"]  # this is for h5 compatibility
}
# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='GridCalEngine',  # Required
    version=__GridCalEngine_VERSION__,  # Required
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
    package_dir={'': '.'},
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=dependencies,
    extras_require=extras_require,
    package_data=package_data,
)
