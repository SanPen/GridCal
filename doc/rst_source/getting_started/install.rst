Installation
==============

GridCal is designed to work with Python 3.6 and onwards, hence retro-compatibility is
not guaranteed.

Standalone setup
----------------

You can install GridCal as a separated standalone program without having to bother
about setting up python.

`GridCal for windows x64 <https://drive.google.com/open?id=1F_zr8gZ6HXp7wGLcnOxzSVJqXP-XZ4T9>`_

`GridCal for linux x64 <https://drive.google.com/open?id=1atPCEKxapp7UsI_dFahr3XGwoaH96Tg5>`_

Remember to update the program to the latest version once installed. You'll find an
update script in the installation folder.

**note**: On Linux, if you get a, `ImportError: libffi.so.6` error, it means that the
libffi library version 6 is not present (happens for newer ubuntu distributions)
The you may install it with the following commands:

.. code:: text

    wget http://mirrors.kernel.org/ubuntu/pool/main/libf/libffi/libffi6_3.2.1-8_amd64.deb

    sudo apt install ./libffi6_3.2.1-8_amd64.deb


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

PySide2 vs. PyQt5
------------------

Now GridCal has been completely ported to PySide2.
The reason for this is because PySide2 has been endorsed by Qt as the main python
wrapper for the Qt Library and therefore it is expected to have the best support.

However there are plenty of other libraries that depend of PyQt5 which is an alternative wrapper for the Qt
framework (and used to be the best one though)

After some test, I can tell you that if GridCal does not work and you installed Python via the
Anaconda distribution, go to your anaconda main folder and remove the file `qt.conf`. No other real solution out
is there really.

Issues with PySide6 in ubuntu
-------------------------------------

Under Ubuntu 22.04, you may encounter the following issue:

```
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
```

```
sudo apt-get install '^libxcb.*-dev' libx11-xcb-dev libglu1-mesa-dev libxrender-dev libxi-dev libxkbcommon-dev libxkbcommon-x11-dev
```

Installing python and GridCal from scratch
--------------------------------------------------

Since Python 3.7, the packages `jupyter`, `qtconsole` and dome others related to the notebooks
have completely screwed up the compatibility of old versions. Therefore, in order to replicate
a viable python distribution where GridCal works, we need to install a certain subset of
packages. I have compiled the following `pip` command that achieves this:

.. code::

    python -m pip install alabaster==0.7.12 astroid==2.2.5 atomicwrites==1.3.0 attrs==19.1.0 Babel==2.6.0 backcall==0.1.0 branca==0.3.1 certifi==2019.3.9 chardet==3.0.4 cvxopt==1.2.3  cycler==0.10.0 Cython==0.29.13 decorator==4.4.0 dill==0.2.9 docutils==0.14 et-xmlfile==1.0.1 folium==0.10.0 geographiclib==1.49 geopy==1.19.0 GridCal>=3.6.7 h5py==2.9.0 idna==2.8 imagesize==1.1.0 intel-openmp==2019.0 ipykernel==5.1.1 ipython==7.5.0 ipython-genutils==0.2.0 isort==4.3.21 jdcal==1.4.1 jedi==0.13.3 Jinja2==2.10.1 joblib==0.13.2 jupyter-client==5.2.4 jupyter-core==4.4.0 kiwisolver==1.1.0 lazy-object-proxy==1.4.1 llvmlite==0.31.0 MarkupSafe==1.1.1 matplotlib==3.1.1 mccabe==0.6.1 mkl==2019.0 more-itertools==7.1.0 networkx==2.3 nose==1.3.7 numba==0.47.0 numpy==1.16.3 openpyxl==2.6.2 packaging==19.0 pandas==0.24.2 parso==0.4.0 pexpect==4.7.0 pickleshare==0.7.5 Pillow==6.0.0 pluggy==0.11.0 POAP==0.1.26 prompt-toolkit==2.0.9 ptyprocess==0.6.0 PuLP==1.6.10 py==1.8.0 pyamg==4.0.0 pybind11==2.3.0 pyDOE==0.3.8 pyDOE2==1.2.0 Pygments==2.4.1 pyparsing==2.4.0 PySide2==5.13.0 pySOT==0.2.2 pytest==4.5.0 python-dateutil==2.8.0 pytz==2019.1 pyzmq==18.0.1 qtconsole==4.5.0 requests==2.22.0 scikit-learn==0.21.2 scipy==1.3.0 shiboken2==5.13.0 six==1.12.0 smopy==0.0.6 snowballstemmer==1.9.0 Sphinx==2.1.2 sphinxcontrib-applehelp==1.0.1 sphinxcontrib-devhelp==1.0.1 sphinxcontrib-htmlhelp==1.0.2 sphinxcontrib-jsmath==1.0.1 sphinxcontrib-qthelp==1.0.2 sphinxcontrib-serializinghtml==1.1.3 SQLAlchemy==1.3.7 tabulate==0.8.3 tornado==6.0.2 traitlets==4.3.2 typed-ast==1.4.0 urllib3==1.25.3 wcwidth==0.1.7 wrapt==1.11.2 xlrd==1.2.0 xlwt==1.3.0

These packages replicate GridCal's development environment in python 3.7.x and are guaranteed to work.


Make Miniconda work under Windows
--------------------------------------------------

The use of Anaconda is completely discouraged since we were unable to make GridCal
work there due to the Qt issues on the platform.
As of version 4.0.0 of GridCal we have tested the following procedure to make Miniconda work:

- Install Python 3.9 Miniconda3 x64: https://docs.conda.io/en/latest/miniconda.html
    - Should also work for other 3.x versions of python for 64 bits.
    - Uncheck the advanced options during the installation unless you need them.

- Copy the following files from `[miniconda folder]\Library\bin` to `[miniconda folder]\Library\DLLs`
    - libcrypto-1_1-x64.dll
    - libcrypto-1_1-x64.pdb
    - libssl-1_1-x64.dll
    - libssl-1_1-x64.pdb

- Install GridCal: `python.exe -m pip install GridCal`

- Copy the following files from `[miniconda folder]\Library\bin` to `[miniconda folder]\Library\DLLs`
    - sqlite3.dll

- Test: `python.exe -c "from GridCal.ExecuteGridCal import run; run()"`


Configure MIP solvers
------------------------------

.. code::

    CPLEX_HOME="/opt/ibm/ILOG/CPLEX_Enterprise_Server1210/CPLEX_Studio/cplex"
    CPO_HOME="/opt/ibm/ILOG/CPLEX_Enterprise_Server1210/CPLEX_Studio/cpoptimizer"
    PATH="${PATH}:${CPLEX_HOME}/bin/x86-64_linux:${CPO_HOME}/bin/x86-64_linux"
    export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${CPLEX_HOME}/bin/x86-64_linux:${CPO_HOME}/bin/x86-64_linux"

.. code::

    GUROBI_HOME="/opt/gurobi1000"
    PATH="${PATH}:${GUROBI_HOME}/bin"
    LD_LIBRARY_PATH="${GUROBI_HOME}/lib"