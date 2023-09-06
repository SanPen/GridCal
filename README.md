# GridCal

![](/home/santi/Documentos/Git/GitHub/GridCal/pics/GridCal.png)

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/75e794c9bcfd49bda1721b9ba8f6c790)](https://app.codacy.com/app/SanPen/GridCal?utm_source=github.com&utm_medium=referral&utm_content=SanPen/GridCal&utm_campaign=Badge_Grade_Dashboard)
[![Documentation Status](https://readthedocs.org/projects/gridcal/badge/?version=latest)](https://gridcal.readthedocs.io/en/latest/?badge=latest) [![Build Status](https://travis-ci.org/SanPen/GridCal.svg?branch=master)](https://travis-ci.org/SanPen/GridCal)
[![DOI](https://www.zenodo.org/badge/49583206.svg)](https://www.zenodo.org/badge/latestdoi/49583206)
[![Downloads](https://static.pepy.tech/personalized-badge/gridcal?period=total&units=abbreviation&left_color=grey&right_color=green&left_text=Downloads)](https://pepy.tech/project/gridcal)

GridCal is a tier-1 power systems planning and simulation software. 
As such it has all the static analysis studies that you can think of, plus 
linear and non-linear optimization functions. Some of these functions you 
perfectly know and some others you may have never heard of as they are a 
product of cutting-edge research.

GridCal started in 2015 as a project to be able to work with, frustrated by 
the available options. This led to design proper programming library and a 
nice graphical user interface. This no-nonsense approach has fostered numerous 
innovations; Some of them pushed by the need to use the software for commercial 
work, and some ignited by research and curiosity.

If you are a professional looking for a free software to get work done in time, 
look no further. If you are a researcher looking for a real-world, TSO-tested platform, 
you're in good hands. If you are a teacher willing to teach your students the ins-and-outs 
of commercial grade software, this is it. And if you are a student willing to learn 
about the algorithms of the books, but for real, we've been there.

Our commitment is with you: GridCal is a high quality product. It is free for ever. 
For all of us now and for the generations to come.

## Installation

GridCal is a software made in the Python programming language. 
Therefore, you need a python interpreter installed in your operative system. 
We recommend to install the latest version of [Python](www.python.org) and then, 
install GridCal with the following terminal command:

```
pip install GridCal
```

You may need to use `pip3` if you are under Linux or macOS, both of which 
come with Python pre-installed already.

### Run th graphical user interface

Once you install GridCal in your local Python distribution, you can run the 
graphical user interface with the following terminal command:

```
python -c "from GridCal.ExecuteGridCal import run; run()"
```

### Standalone setup

If you don't know what is this Python thing, we offer a windows installation:

[Windows setup](https://www.advancedgridinsights.com/gridcal)

This will install GridCal as a normal windows program and you need not to worry 
about any of the previous instructions.


## Features

- Large collection of devices to model electricity grids.
- AC/DC multi-grid power flow
- AC/DC multi-grid linear optimal power flow
- AC linear analysis (PTDF & LODF)
- AC linear net transfer capacity calculation
- AC+HVDC optimal net transfer capacity calculation
- AC/DC Stochastic power flow
- AC Short circuit
- AC Continuation power flow
- Contingency analysis (Power flow and LODF variants)
- Sigma analysis (one-shot stability analysis)
- Investments analysis
- Bus-branch schematic
- Substation-line map diagram
- Time series and snapshot for most simulations
- Overhead tower designer
- Inputs analysis
- Model bug report and repair
- Import many formats (PSSe .raw/rawx, epc, dgs, matpower, pypsa, json, cim, cgmes)
- Export in many formats (gridcal .xlsx/.gridcal/.json, cgmes, psse .raw/.rawx)


## API

Since day one, GridCal was meant to be used as a library as much as it was meant 
to be used from the user interface. 

### Loading a grid

```
import GridCal.api as gca

my_grid = gca.open_file("my_file.gridcal")
```

GridCal supports a plethora of file formats:

- CIM 16 (.zip and .xml)
- CGMES 2.4.15 (.zip and .xml)
- PSS/e raw and rawx versions 29 to 35, including USA market excahnge RAW-30 specifics.
- Matpower .m files directly.
- DigSilent .DGS (not fully compatible)
- PowerWorld .EPC (not fully compatible, supports substation coordinates)

### Save a grid

```
import GridCal.api as gca

gca.save_file(my_grid, "my_file.gridcal")
```

### Creating a Grid from the API objects

We are going to create a very simple 5-node grid from the excellent book 
*Power System Load Flow Analysis by Lynn Powell*.

```
import GridCal.Engine as gce

# declare a circuit object
grid = gce.MultiCircuit()

# Add the buses and the generators and loads attached
bus1 = gce.Bus('Bus 1', vnom=20)
# bus1.is_slack = True
grid.add_bus(bus1)

gen1 = gce.Generator('Slack Generator', voltage_module=1.0)
grid.add_generator(bus1, gen1)

bus2 = gce.Bus('Bus 2', vnom=20)
grid.add_bus(bus2)
grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

bus3 = gce.Bus('Bus 3', vnom=20)
grid.add_bus(bus3)
grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

bus4 = gce.Bus('Bus 4', vnom=20)
grid.add_bus(bus4)
grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

bus5 = gce.Bus('Bus 5', vnom=20)
grid.add_bus(bus5)
grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

# add Branches (Lines in this case)
grid.add_line(gce.Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.02))
grid.add_line(gce.Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.02))
grid.add_line(gce.Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.02))
grid.add_line(gce.Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.02))
grid.add_line(gce.Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.02))
grid.add_line(gce.Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.03))
grid.add_line(gce.Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02))
```

### Power Flow

Using the simlified API:

```
import GridCal.Engine as gca

results = gca.power_flow(grid)

print('\n\n', grid.name)
print('\t|V|:', abs(results.voltage))
print('\t|Sbranch|:', abs(results.Sf))
print('\t|loading|:', abs(results.loading) * 100)
print('\terr:', results.error)
print('\tConv:', results.converged)
```

Using the more complex library objects:

```
import GridCal.Engine as gce

options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
power_flow = gce.PowerFlowDriver(grid, options)
power_flow.run()

print('\n\n', grid.name)
print('\t|V|:', abs(power_flow.results.voltage))
print('\t|Sbranch|:', abs(power_flow.results.Sf))
print('\t|loading|:', abs(power_flow.results.loading) * 100)
print('\terr:', power_flow.results.error)
print('\tConv:', power_flow.results.converged)
```

### Linear analysis

```

```

### Linear optimization

```

```

## Contact

- Join the [Discord GridCal channel](https://discord.com/invite/dzxctaNbvu) for a friendly chat, or quick question.
- Submit questions or comments to our [form](https://forms.gle/MpjJAntAwZiLwE6B6).
- Submit bugs or requests in the [Issues](https://github.com/SanPen/GridCal/issues) section.
- Simply email [santiago@gridcal.org](santiago@gridcal.org)

## License

GridCal is licensed under the [Lesser General Public License v3.0](https://www.gnu.org/licenses/lgpl-3.0.en.html) (LGPL)

In practical terms this means that:

- You can use GridCal for commercial work.
- You can sell commercial services based on GridCal.
- If you distrubute GridCal, you must distribute GridCal's source code as well. 
That is always achieved in practice with python code.
- GridCal license does not propagate to works that are not a derivative of GridCal. 
An example of a derivative work is if you write a module of the program, the the license 
of the modue must be LGPL too. An example of a non-derivative work is if you use 
GridCal's API for something else without modifying the API itself, for instance, 
using it as a library for another program.

Nonetheless, read the license carefully.

## Disclaimer

[GridCal](http://consultas2.oepm.es/ceo/jsp/busqueda/consultaExterna.xhtml?numExp=1u6ec16k3hn1v05or1c1ah4va8re2e5810b4vrc1inj2ae0vz4sigbkzywc1id2ifqazajcdjwuvubmnxfjdz0vasw9rqs3u4u7i) is a trademark registered in the Spanish patents and trademarks office.

All other trademarks mentioned belong to their respective owners.