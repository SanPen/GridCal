Installation
============

GridCal is designed to work with Python 3.6 and onwards, hence retro-compatibility is not guaranteed.

Windows
-------

Open a system console (go to the desktop menu and type cmd, the console should appear). Then type:

.. code::

    pip install GridCal

This assumes that your system-wide python is a Python 3 distribution, hence you must make sure of this. An easy way to check this, is to open a console, type `python` and if a Python 3 console opens within the terminal, then it is allright.

For windows systems I have disabled the installation of PyQt (the user interface technology) because it conflicts with the Qt version provided by Anaconda. This should not be the case, but it happens. Therefore, under windows, you must install Python through Anaconda.

Linux / OSX
-----------

On Unix systems the python 2 / 3 issue is non existent since the terminal commands for Python 2 and Python 3 are different. So, simply go to a system terminal and type:

.. code::

    pip3 install GridCal

This command will install all the dependencies flawlessly unlike under windows.
