![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal_banner.png)

# What is this?

This software aims to be a complete platform for power systems research and simulation. [Watch the video](https://youtu.be/7BbO7KKWwEY)

![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal.png)

![](https://github.com/SanPen/GridCal/blob/master/pics/results_vstability.png)

# Installation

Open a console and type:

`pip install GridCal` (windows)

`pip3 install GridCal` (Linux / OSX)

*You must have Python 3.5 or higher installed to work with the GUI

# Run with user interface

From a Python console:

`from GridCal.ExecuteGridCal import run`

`run()`

Or directly from the shell:


`python -c "from GridCal.ExecuteGridCal import run; run()"`(Windows, with python 3.5 or higher)

`python3 -c "from GridCal.ExecuteGridCal import run; run()"` (Linux/OSX)

The GUI should pop up.

# Using GridCal as a library

You can use the calculation engine directly or from other applications:

`from GridCal.grid.CircuitOO import *`

Then you can create the grid objects and access the simulation objects as demonstrated in the test scripts in the test folder.

`GridCal/UnderDevelopment/GridCal/tests/`

#Features overview
It is pure Python, It works for Windows, Linux and OSX.

It is based on PyPower (MatPower for python) and it is compatible with Matpower files, and many more to come.

Some of the features you'll find already are:

- Power flow:
  - Newton Raphson Iwamoto (robust Newton Raphson).
  - Holomorphic Embedding Power flow.
  - DC approximation.
  
- Includes the Z-I-P load model, this means that the power flows can handle both power and current.  

- The ability to handle island grids in all the simulation modes.

- Time series with profiles in all the objects physical magnitudes.

- Bifurcation point with predictor-corrector Newton-Raphson.

- Monte Carlo simulation based on the input profiles. (Stochastic power flow)

Visit the [Wiki](https://github.com/SanPen/GridCal/wiki) to learn more and get started.

Send feedback and requests to santiago.penate.vera@gmail.com.
