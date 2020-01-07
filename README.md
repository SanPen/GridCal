[![Codacy Badge](https://api.codacy.com/project/badge/Grade/75e794c9bcfd49bda1721b9ba8f6c790)](https://app.codacy.com/app/SanPen/GridCal?utm_source=github.com&utm_medium=referral&utm_content=SanPen/GridCal&utm_campaign=Badge_Grade_Dashboard)
[![Documentation Status](https://readthedocs.org/projects/gridcal/badge/?version=latest)](https://gridcal.readthedocs.io/en/latest/?badge=latest) [![Build Status](https://travis-ci.org/SanPen/GridCal.svg?branch=master)](https://travis-ci.org/SanPen/GridCal)
[![DOI](https://www.zenodo.org/badge/49583206.svg)](https://www.zenodo.org/badge/latestdoi/49583206)

# What is this?

![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal_banner.png)

This software aims to be a complete platform for power systems research and simulation.
[Watch the video](https://youtu.be/SY66WgLGo54) and
[check out the documentation](https://gridcal.readthedocs.io)

![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal.png)

# Installation

Try: `pip install GridCal`

For more options (including a standalone setup one), follow the
[installation instructions](https://gridcal.readthedocs.io/en/latest/getting_started/install.html)
from the project's [documentation](https://gridcal.readthedocs.io).


# Execution

GridCal can be used in 2 ways:

1. With a GUI;
2. As a library.

Executing `python3 -c "from GridCal.ExecuteGridCal import run; run()"` in a console
should bring up the GUI under most platforms. For detailed instructions, follow the
[instructions](https://gridcal.readthedocs.io/en/latest/getting_started.html)
from the project's documentation.

# Tutorials

- Cloning the repository: https://youtu.be/59W_rqimB6w

- Standalone GridCal setup: https://youtu.be/SY66WgLGo54

- Making a grid with profiles: https://youtu.be/H2d_2bMsIS0

# Batteries included

In an effort to ease the simulation and construction of grids, We have included extra materials to work with.
 
[Here](https://github.com/SanPen/GridCal/tree/master/Grids_and_profiles) you can find:
- Load profiles for your projects
- Standard IEEE grids as well as grids from open projects
- [Equipment catalogue](https://gridcal.readthedocs.io/en/latest/data_sheets.html) (Wires, Cables and Transformers) ready to use in GridCal

# Examples

Examples are included in [Tutorials](https://gridcal.readthedocs.io/en/latest/tutorials/tutorials_module.html) section. In addition, the
tests under [src/tests](https://github.com/SanPen/GridCal/tree/master/src/tests) may serve as valuable examples.

# Testing GridCal

    python3 -m venv venv
    venv/bin/python -m pip install --upgrade -r requirements_venv.txt
    venv/bin/python -m tox

# Features overview

It is pure Python, it works for Windows, Linux and OSX.

Some of the features you'll find already are:

- Compatible with other formats:
  - **Import** (Drag & Drop)
    - CIM (Common Information Model v16)
    - PSS/e RAW versions 29, 30, 32, 33 and 34.
    - Matpower (might not be fully compatible, notify me if not).
    - DigSilent .DGS (not be fully compatible: Only positive sequence and devices like loads, generators, etc.)
    
  - **Export**
    - Zip file `.gridcal` with CSV inside (fastest, normal GridCal format) 
    - Sqlite
    - Excel
    - Custom JSON
    - CIM (Common Information Model v16)

- **Power flow**:
  - Robust Newton Raphson in power and current equations.
  - Newton Raphson Iwamoto (optimal acceleration).
  - Fast Decoupled Power Flow
  - Levenberg-Marquardt (Works very well with large ill-conditioned grids)
  - Holomorphic Embedding Power Flow (Unicorn under investigation...)
  - DC approximation.
  - Linear AC approximation.
  
- **Optimal power flow (OPF)** and generation dispatch:
  - Linear (DC) with losses.
  - Linear (Ac) with losses.
  - Loss-less simple generation dispatch.  
  - All the modes can be split the runs in hours, days, weeks or months!

- **Time series** with profiles in all the objects physical magnitudes.

- **PTDF** approximated branch flow time series for super fast estimation of the flows.

- Bifurcation point with predictor-corrector Newton-Raphson.

- **Monte Carlo / Latin Hypercube** stochastic power flow based on the input profiles.

- **Blackout cascading** in simulation and step by step mode.

- Three-phase **short circuit**.

- Includes the Z-I-P load model, this means that the power flows can handle both power and current.

- The ability to handle island grids in all the simulation modes.

- **Profile editor** and importer from Excel and CSV.

- **Grid elements' analysis** to discover data problems.

- **Overhead line construction** from wire scheme.

- Device **templates** (lines and transformers).

- **Grid reduction** based on branch type and filtering by impedance values

- **Export** the schematic in SVG and PNG formats.

[Check out the documentation](https://gridcal.readthedocs.io) to learn more and to get started.


# Contact

Send feedback and requests to [santiago.penate.vera@gmail.com](santiago.penate.vera@gmail.com).

