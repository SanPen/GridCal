from distutils.core import setup
import sys
import os
import platform
from GridCal.grid.CalculationEngine import __GridCal_VERSION__

def make_linux_desktop_file(version_, comment):
    """
    Makes the linux desktop entry
    Args:
        version_: program version
        comment: entry comment

    Returns:

    """

    '''
    [Desktop Entry]
    Version=1.0
    Terminal=false
    Type=Application
    Name=GridCal
    Exec=/path/to/executable
    Icon=/path/to/icon
    Categories=Graphics;2DGraphics;Development;
    Comment=Tooltip comment appears when you hover on menu icon.
    '''

    str = '[Desktop Entry]' + '\n'
    str += 'Version=' + version_ + '\n'
    str += 'Terminal=false' + '\n'
    str += 'Type=Application' + '\n'
    str += 'Name=GridCal' + '\n'
    str += 'Exec=/path/to/executable' + '\n'
    str += 'Icon=/path/to/icon' + '\n'
    str += 'Categories=Science;' + '\n'
    str += 'MimeType=text/x-python' + '\n'
    str += 'Comment=' + comment

    # save the file
    fname = "GridCal.desktop"
    text_file = open(fname, "w")
    text_file.write(str)
    text_file.close()

    return fname

name = "GridCal"
version = str(__GridCal_VERSION__)
description = "Research Oriented electrical simulation software."

# Python 3.5 or later needed
if sys.version_info < (3, 5, 0, 'final', 0):
    raise (SystemExit, 'Python 3.5 or later is required!')

# Build a list of all project modules
packages = []
for dirname, dirnames, filenames in os.walk(name):
        if '__init__.py' in filenames:
            packages.append(dirname.replace('/', '.'))

package_dir = {name: name}

# Data_files (e.g. doc) needs (directory, files-in-this-directory) tuples
data_files = []
for dirname, dirnames, filenames in os.walk('doc'):
        fileslist = []
        for filename in filenames:
            fullname = os.path.join(dirname, filename)
            fileslist.append(fullname)
        data_files.append(('share/' + name + '/' + dirname, fileslist))

if platform.system() == 'Windows':
    # list the packages (On windows anaconda is assumed)
    required_packages = ["numpy",
                          "scipy",
                          "networkx",
                          "pandas",
                          "xlwt",
                          "xlrd",
                          # "PyQt5",
                          "matplotlib",
                          "qtconsole",
                          "pysot",
                          "openpyxl"
                          ]
else:
    # make the desktop entry
    make_linux_desktop_file(version_=version, comment=description)

    # list the packages
    required_packages = ["numpy",
                         "scipy",
                         "networkx",
                         "pandas",
                         "xlwt",
                         "xlrd",
                         "PyQt5",
                         "matplotlib",
                         "qtconsole",
                         "pysot",
                         "openpyxl"
                         ]

setup(
    # Application name:
    name=name,

    # Version number (initial):
    version=version,

    # Application author details:
    author="Santiago Peñate Vera",
    author_email="santiago.penate.vera@gmail.com",

    # Packages
    packages=packages,

    data_files=data_files,

    # Include additional files into the package
    include_package_data=True,

    # Details
    url="http://pypi.python.org/pypi/GridCal/",

    # License file
    license="LICENSE.txt",

    # description
    description=description,

    # long_description=open("README.txt").read(),

    # Dependent packages (distributions)
    install_requires=required_packages,
    setup_requires=required_packages,
)
