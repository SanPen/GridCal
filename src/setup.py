"""
A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
import os
# io.open is needed for projects that support Python 2.7
# It ensures open() defaults to text mode with universal newlines,
# and accepts an argument to specify the text encoding
# Python 3 only projects can skip this import
from io import open

from GridCal.__version__ import __GridCal_VERSION__

here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file
# if os.path.exists(os.path.join(here, 'README.md')):
#     with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
#         long_description = f.read()
#         print(long_description)
# else:
#     long_description = ''

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

# if os.path.exists(os.path.join(here, 'about.txt')):
#     with open(os.path.join(here, 'about.txt'), encoding='utf-8') as f:
#         description = f.read()
#         print(description)
# else:
#     description = ''
#     print('Unable to read the description file')
description = 'GridCal is a Power Systems simulation program intended for professional use and research'

base_path = os.path.join('GridCal')

packages = find_packages(exclude=['docs', 'research', 'research.*', 'tests', 'tests.*', 'Tutorials'])

package_data = {'GridCal': ['*.md',
                            '*.rst',
                            'LICENSE.txt',
                            'data/cables.csv',
                            'data/transformers.csv',
                            'data/wires.csv'],
                'GridCal.ThirdParty.pulp': ["AUTHORS", "LICENSE",
                                            "pulp.cfg.linux",
                                            "pulp.cfg.win",
                                            "pulp.cfg.osx",
                                            "LICENSE.CoinMP.txt",
                                            "AUTHORS.CoinMP.txt",
                                            "README.CoinMP.txt"],
                'GridCal.ThirdParty.pulp.solverdir.cbc.linux.32': ['*', '*.*'],
                'GridCal.ThirdParty.pulp.solverdir.cbc.linux.64': ['*', '*.*'],
                'GridCal.ThirdParty.pulp.solverdir.cbc.win.32': ['*', '*.*'],
                'GridCal.ThirdParty.pulp.solverdir.cbc.win.64': ['*', '*.*'],
                'GridCal.ThirdParty.pulp.solverdir.cbc.osx.64': ['*', '*.*'],
                }

dependencies = ['setuptools>=41.0.1',
                'wheel>=0.33.4',
                "PySide2>=5.15",  # 5.14 breaks the UI generation for development
                "numpy>=1.19.0",
                "scipy>=1.0.0",
                "networkx>=2.1",
                "pandas>=1.0",
                "ortools>=9.0.0",
                "xlwt>=1.3.0",
                "xlrd>=1.1.0",
                "matplotlib>=2.1.1",
                "qtconsole>=4.5.4",
                "pyDOE>=0.3.8",
                "pySOT>=0.2.1",
                "openpyxl>=2.4.9",
                "smopy>=0.0.6",  # to render tiles
                "chardet>=3.0.4",  # for the psse files character detection
                "scikit-learn>=0.18",
                "geopy>=1.16",
                "pytest>=3.8",
                "h5py>=2.9.0",
                "numba>=0.46",  # to compile routines natively
                "folium",  # to render web maps
                'pyproj',
                'pyarrow'
                ]

extras_require = {
        'gch5 files':  ["tables"]  # this is for h5 compatibility
    }
# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    # This is the name of your project. The first time you publish this
    # package, this name will be registered for you. It will determine how
    # users can install this project, e.g.:
    #
    # $ pip install sample_project
    #
    # And where it will live on PyPI: https://pypi.org/project/sampleproject/
    #
    # There are some restrictions on what makes a valid project name
    # specification here:
    # https://packaging.python.org/specifications/core-metadata/#name
    name='GridCal',  # Required

    # Versions should comply with PEP 440:
    # https://www.python.org/dev/peps/pep-0440/
    #
    # For a discussion on single-sourcing the version across setup.py and the
    # project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=__GridCal_VERSION__,  # Required

    license='LGPL',

    # This is a one-line description or tag-line of what your project does. This
    # corresponds to the "Summary" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#summary
    description=description,  # Optional

    # This is an optional longer description of your project that represents
    # the body of text which users will see when they visit PyPI.
    #
    # Often, this is the same as your README, so you can just read it in from
    # that file directly (as we have already done above)
    #
    # This field corresponds to the "Description" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#description-optional
    # long_description=long_description,  # Optional

    # Denotes that our long_description is in Markdown; valid values are
    # text/plain, text/x-rst, and text/markdown
    #
    # Optional if long_description is written in reStructuredText (rst) but
    # required for plain-text or Markdown; if unspecified, "applications should
    # attempt to render [the long_description] as text/x-rst; charset=UTF-8 and
    # fall back to text/plain if it is not valid rst" (see link below)
    #
    # This field corresponds to the "Description-Content-Type" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#description-content-type-optional
    long_description_content_type='text/markdown',  # Optional (see note above)

    # This should be a valid link to your project's main homepage.
    #
    # This field corresponds to the "Home-Page" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#home-page-optional
    url='https://github.com/SanPen/GridCal',  # Optional

    # This should be your name or the name of the organization which owns the
    # project.
    author='Santiago Peñate Vera et. Al.',  # Optional

    # This should be a valid email address corresponding to the author listed
    # above.
    author_email='santiago.penate.vera@gmail.com',  # Optional

    # Classifiers help users find your project by categorizing it.
    #
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable

        # Pick your license as you wish
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        # These classifiers are *not* checked by 'pip install'. See instead
        # 'python_requires' below.
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
         'Programming Language :: Python :: 3.9',
    ],

    # This field adds keywords for your project which will appear on the
    # project page. What does your project relate to?
    #
    # Note that this is a string of words separated by whitespace, not a list.
    keywords='power systems planning',  # Optional

    # You can just specify package directories manually here if your project is
    # simple. Or you can use find_packages().
    #
    # Alternatively, if you just want to distribute a single Python file, use
    # the `py_modules` argument instead as follows, which will expect a file
    # called `my_module.py` to exist:
    #
    #   py_modules=["my_module"],
    #
    packages=packages,  # Required
    include_package_data=True,

    # Specify which Python versions you support. In contrast to the
    # 'Programming Language' classifiers above, 'pip install' will check this
    # and refuse to install the project if the version does not match. If you
    # do not support Python 2, you can simplify this to '>=3.5' or similar, see
    # https://packaging.python.org/guides/distributing-packages-using-setuptools/#python-requires
    python_requires='>=3.6',

    # This field lists other packages that your project depends on to run.
    # Any package you put here will be installed by pip when your project is
    # installed, so they must be valid existing projects.
    #
    # For an analysis of "install_requires" vs pip's requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=dependencies,

    # List additional groups of dependencies here (e.g. development
    # dependencies). Users will be able to install these using the "extras"
    # syntax, for example:
    #
    #   $ pip install sampleproject[dev]
    #
    # Similar to `install_requires` above, these must be valid existing
    # projects.
    extras_require=extras_require,

    # If there are data files included in your packages that need to be
    # installed, specify them here.
    #
    # If using Python 2.6 or earlier, then these have to be included in
    # MANIFEST.in as well.
    package_data=package_data,

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files
    #
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    # data_files=[('my_data', ['data/data_file'])],  # Optional
    # data_files=package_data,

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # `pip` to create the appropriate form of executable for the target
    # platform.
    #
    # For example, the following would provide a command called `sample` which
    # executes the function `main` from this package when invoked:
    # entry_points={  # Optional
    #     'console_scripts': [
    #         'sample=sample:main',
    #     ],
    # },

    # List additional URLs that are relevant to your project as a dict.
    #
    # This field corresponds to the "Project-URL" metadata fields:
    # https://packaging.python.org/specifications/core-metadata/#project-url-multiple-use
    #
    # Examples listed include a pattern for specifying where the package tracks
    # issues, where the source is hosted, where to say thanks to the package
    # maintainers, and where to support the project financially. The key is
    # what's used to render the link text on PyPI.
    # project_urls={'GridCal':'https://github.com/SanPen/GridCal'},  # optional
)
