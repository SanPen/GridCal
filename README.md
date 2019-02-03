![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal_banner.png)

# What is this?

This software aims to be a complete platform for power systems research and simulation.
[Watch the video](https://youtu.be/7BbO7KKWwEY) and
[check out the documentation](https://gridcal.readthedocs.io)

![](https://github.com/SanPen/GridCal/blob/master/pics/GridCal.png)

# Installation

Follow the
[installation instructions](https://gridcal.readthedocs.io/en/latest/getting_started/install.html)
from the project's documentation.

# Execution

GridCal can be used in 2 ways:

1. With a GUI;
2. As a library.

Executing `python3 -c "from GridCal.ExecuteGridCal import run; run()"` in a console
should bring up the GUI under most platforms. For detailed instructions, follow the
[instructions](https://gridcal.readthedocs.io/en/latest/getting_started.html)
from the project's documentation.

# Examples

Examples are included in `Tutorials` folder of the GitHub repository. In addition, the
tests under `src/tests` may serve as valuable examples.

# Features overview

It is pure Python, it works for Windows, Linux and OSX.

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

Visit the [Wiki](https://github.com/SanPen/GridCal/wiki) and the
[check out the documentation](https://gridcal.readthedocs.io) to learn more and to
get started.

Send feedback and requests to santiago.penate.vera@gmail.com.
