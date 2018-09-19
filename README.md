![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal_banner.png)

# What is this?

This software aims to be a complete platform for power systems research and simulation. [Watch the video](https://youtu.be/7BbO7KKWwEY) and 
 [check out the manual](https://github.com/SanPen/GridCal/blob/master/Documentation/GridCal/Manual_of_GridCal.pdf)

![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal.png)


# Standalone setup

You can install GridCal as a separated standalone program without having to bother about setting up python.

[GridCal for windows x64](https://mega.nz/#!Dl5m0b7T!brD9O0ejs2Ih6rOLVaCjQm3-JZttH-ksrp5xXrrX3BU)

[GridCal for linux x64](https://mega.nz/#!m4YUhICZ!c5bLncNwqCQG3H6p0ST4qnSP1GTii-44_di06RGSV-o)

Remember to update the program to the latest version once installed. You'll find an update script in the installation folder.

# Python package installation

GridCal is multiplatform and it will work in Linux, Windows and OSX.

The recommended way to install GridCal if you have a python distribution already is to open a console and type:

`pip install GridCal` (Windows)

`pip3 install GridCal` (Linux / OSX)

*You must have Python 3.5 or higher installed to work with the GUI

Check out the video on how to install [**Python and GridCal on Windows 10**.](https://youtu.be/yGxMq2JB1Zo)

### Manual package installation

Sometimes `pip` does not download the lattest version for some reason. In those cases, go to https://pypi.python.org/pypi/GridCal/ and download the lattest GridCal file: `GridCal-x.xx.tar.gz`.

From a console install the file manually:

Windows: `pip install GridCal-x.xx.tar.gz`

OSX/Linux: `pip3 install GridCal-x.xx.tar.gz`

### Installation from GitHub

To install the development version of `GridCal` that lives under `UnderDevelopment`, open a console and type:

    python3 -m pip install -e 'git+git://github.com/SanPen/GridCal.git#egg=GridCal&subdirectory=UnderDevelopment'

Installing `GridCal` from GitHub, `pip` can still freeze the version using a commit hash:

    python -m pip install -e 'git+git://github.com/SanPen/GridCal.git@5c4dcb96998ae882412b5fee977cf0cff7a40d3c#egg=GridCal&subdirectory=UnderDevelopment'

Here `5c4dcb96998ae882412b5fee977cf0cff7a40d3c` is the git version.

# Run with user interface

From a Python console:

```
from GridCal.ExecuteGridCal import run
run()
```

Or directly from the shell:

- (Windows, with python 3.5 or higher)

    `python -c "from GridCal.ExecuteGridCal import run; run()"`

- (Linux/OSX)

    `python3 -c "from GridCal.ExecuteGridCal import run; run()"`

The GUI should pop up.

# Using GridCal as a library

You can use the calculation engine directly or from other applications:

`from GridCal.grid.CalculationEngine import *`

Then you can create the grid objects and access the simulation objects as demonstrated in the test scripts in the test folder.

`GridCal/UnderDevelopment/GridCal/tests/`

I use the engine to get the admittance matrix, power injections, etc. and then do research without having to worry about getting those vectors and matrices right since they are well calculated in the engine.


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

Some of the features you'll find already are:

- Compatible with other formats:
  - Import
    - CIM (Common Information Model v16)
    - PSS/e RAW versions 30, 32 and 33.
    - Matpower (might not be fully compatible, notify me if not).
    - DigSilent .DGS (not be fully compatible: Only positive sequence and devices like loads, generators, etc.)
  - Export
    - Excel (normal GridCal format)
    - Custom JSON
    - CIM (Common Information Model v16)

- Power flow:
  - Robust Newton Raphson in power and current equations.
  - Newton Raphson Iwamoto (optimal acceleration).
  - Fast Decoupled Power Flow
  - Levenberg-Marquardt (Works very well with large ill-conditioned grids)
  - Holomorphic Embedding Power Flow (Unicorn under investigation...)
  - DC approximation.
  - Linear AC approximation.

- DC Optimal power flow
 
- Time series with profiles in all the objects physical magnitudes.

- Bifurcation point with predictor-corrector Newton-Raphson.

- Monte Carlo / Latin Hypercube stochastic power flow based on the input profiles.

- Blackout cascading in simulation and step by step mode.

- Three-phase short circuit.

- Includes the Z-I-P load model, this means that the power flows can handle both power and current.  

- The ability to handle island grids in all the simulation modes.

- Profile editor and importer from Excel and CSV.

- Grid elements analysis to discover data problems.

- Overhead line construction from wire scheme.

- Device templates (lines and transformers).

- Grid reduction based on branch type and filtering by impedance values

- Export the schematic in SVG and PNG formats.

Visit the [Wiki](https://github.com/SanPen/GridCal/wiki) to learn more and to get started.

Send feedback and requests to santiago.penate.vera@gmail.com.
