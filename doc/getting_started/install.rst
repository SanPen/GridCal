.. _install:

Installation
============

GridCal is designed to work with Python 3.6 and onwards, hence retro-compatibility is
not guaranteed.

Standalone setup
----------------

You can install GridCal as a separated standalone program without having to bother
about setting up python.

`GridCal for windows x64 <https://sanpv.files.wordpress.com/2018/11/gridcalsetup.zip>`_

`GridCal for linux x64 <https://sanpv.files.wordpress.com/2018/11/gridcal-standalone-linux.zip>`_

Remember to update the program to the latest version once installed. You'll find an
update script in the installation folder.

Python Package Installation
---------------------------

**GridCal** is multiplatform and it will work in Linux, Windows and OSX.

The recommended way to install **GridCal** if you have a python distribution already
is to open a console and type:

- **Windows**: :code:`pip install GridCal`
- **OSX / Linux**: :code:`pip3 install GridCal`

*You must have Python 3.6 or higher installed to work with the GUI.*

Check out the video on how to install `Python and GridCal on Windows 10 <https://youtu.be/yGxMq2JB1Zo>`_.

**Manual package installation**

Sometimes :code:`pip` does not download the lattest version for some reason. In those
cases, follow `this link <https://pypi.python.org/pypi/GridCal>`_ and download the
latest **GridCal** file: `GridCal-x.xx.tar.gz`.

From a console install the file manually:

- **Windows**: :code:`pip install GridCal-x.xx.tar.gz`
- **OSX / Linux**: :code:`pip3 install GridCal-x.xx.tar.gz`

**Installation from GitHub**

To install the development version of **GridCal** that lives under **src**, open a
console and type:

.. code::

    python3 -m pip install -e 'git+git://github.com/SanPen/GridCal.git#egg=GridCal&subdirectory=src'

Installing **GridCal** from GitHub, **pip** can still freeze the version using a commit
hash:

.. code::

    python -m pip install -e 'git+git://github.com/SanPen/GridCal.git@5c4dcb96998ae882412b5fee977cf0cff7a40d3c#egg=GridCal&subdirectory=UnderDevelopment'

Here :code:`5c4dcb96998ae882412b5fee977cf0cff7a40d3c` is the **git** version.
