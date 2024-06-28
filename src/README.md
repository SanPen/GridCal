
# GridCal

This software aims to be a complete platform for power systems research and simulation.

[Watch the video https](https://youtu.be/SY66WgLGo54)

[Check out the documentation](https://gridcal.readthedocs.io)


## Installation

pip install GridCal

For more options (including a standalone setup one), follow the
[installation instructions]( https://gridcal.readthedocs.io/en/latest/getting_started/install.html)
from the project's [documentation](https://gridcal.readthedocs.io)

## Running an AC-OPF 

In order to run an AC Optimal Power Flow for a given grid using a Python script, the following piece of code shows a quick example 
for its execution:

```python
    import os
    import GridCalEngine.api as gce

    """
    IEEE14 example with AC-OPF
    """
    cwd = os.getcwd()
    fname = os.path.join('data', 'grids', 'IEEE 14.gridcal')
    grid = gce.FileOpen(fname).open()

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, 
                                              ips_tolerance=1e-8,
                                              ips_iterations=50, 
                                              verbose=1, 
                                              acopf_mode=gce.AcOpfMode.ACOPFstd)

    # AC-OPF
    res = gce.acopf(grid=grid,
                    pf_options=pf_options,
                    opf_options=opf_options,
                    plot_error=True,
                    pf_init=True)

    print('')


