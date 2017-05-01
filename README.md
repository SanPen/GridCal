![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal_banner.png)

# What is this?

This software aims to be a complete platform for power systems research and simulation. [Watch the video](https://youtu.be/7BbO7KKWwEY) and 
 [check out the manual](https://github.com/SanPen/GridCal/blob/master/Documentation/GridCal/Manual_of_GridCal.pdf)

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

`from GridCal.grid.CalculationEngine import *`

Then you can create the grid objects and access the simulation objects as demonstrated in the test scripts in the test folder.

`GridCal/UnderDevelopment/GridCal/tests/`

I use the engine to get the admittance matrix, power injections, etc. and then do research without having to worry abour getting those vectors and matrices right since they are well calculated in the engine.


Example:
```
from GridCal.grid.CalculationEngine import *

# Declare a multi-circuit object
grid = MultiCircuit()

# Load the IEEE30 bus grid in the circuit object
grid.load_file('IEEE30.xlsx')

# Compile the grid
grid.compile()

# Pick the circuit 0, if there are no islands all the grid elements are in this object.
# Each island holds its own calculation objects
circuit = grid.circuits[0]

# Print some useful computed vectors and matrices
print('\nYbus:\n', circuit.power_flow_input.Ybus.todense())
print('\nYseries:\n', circuit.power_flow_input.Yseries.todense())
print('\nYshunt:\n', circuit.power_flow_input.Yshunt)
print('\nSbus:\n', circuit.power_flow_input.Sbus)
print('\nIbus:\n', circuit.power_flow_input.Ibus)
print('\nVbus:\n', circuit.power_flow_input.Vbus)
print('\ntypes:\n', circuit.power_flow_input.types)
print('\npq:\n', circuit.power_flow_input.pq)
print('\npv:\n', circuit.power_flow_input.pv)
print('\nvd:\n', circuit.power_flow_input.ref)
```

The main logic is to store the grid elements information in objects, and then "compile the objects" to get efficient arrays that represent the grid for calculation.

The compilation detects the islands formed in the grid and treats each island as a different power system. Then the results are merged back into single multi-island vectors of results.
 
All the engine objects and calculations can be accessed through the embedded python console in the GUI.

# Features overview
It is pure Python, It works for Windows, Linux and OSX.

It is based on PyPower (MatPower for python) and it is compatible with Matpower files, and many more to come.

Some of the features you'll find already are:

- Power flow:
  - Newton Raphson Iwamoto (robust Newton Raphson).
  - Levenberg-Marquardt (Works very well with large grids)
  - Holomorphic Embedding Power flow (Under investigation...)
  - DC approximation.
  
- Includes the Z-I-P load model, this means that the power flows can handle both power and current.  

- The ability to handle island grids in all the simulation modes.

- Time series with profiles in all the objects physical magnitudes.

- Bifurcation point with predictor-corrector Newton-Raphson.

- Monte Carlo simulation based on the input profiles. (Stochastic power flow)

- Three-phase short circuit.

Visit the [Wiki](https://github.com/SanPen/GridCal/wiki) to learn more and get started.

Send feedback and requests to santiago.penate.vera@gmail.com.
