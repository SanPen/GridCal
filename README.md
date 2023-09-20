# GridCal

GridCal is a top tier power systems planning and simulation software. 
As such it has all the static analysis studies that you can think of, plus 
linear and non-linear optimization functions. Some of these functions are 
well know, while others you may have never heard of as they are a 
product of cutting-edge research.

![](/home/santi/Documentos/Git/GitHub/GridCal/pics/GridCal.png)

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/75e794c9bcfd49bda1721b9ba8f6c790)](https://app.codacy.com/app/SanPen/GridCal?utm_source=github.com&utm_medium=referral&utm_content=SanPen/GridCal&utm_campaign=Badge_Grade_Dashboard)
[![Documentation Status](https://readthedocs.org/projects/gridcal/badge/?version=latest)](https://gridcal.readthedocs.io/en/latest/?badge=latest) [![Build Status](https://travis-ci.org/SanPen/GridCal.svg?branch=master)](https://travis-ci.org/SanPen/GridCal)
[![DOI](https://www.zenodo.org/badge/49583206.svg)](https://www.zenodo.org/badge/latestdoi/49583206)
[![Downloads](https://static.pepy.tech/personalized-badge/gridcal?period=total&units=abbreviation&left_color=grey&right_color=green&left_text=Downloads)](https://pepy.tech/project/gridcal)


GridCal started in 2015 as a project to be able to work with, out of frustration with 
the available options. This led to design a proper programming library and a 
nice graphical user interface for everyone. This no-nonsense approach has fostered numerous 
innovations; Some of them pushed by the need to use the software in commercial 
environments, and some ignited by curiosity and research.

If you are a professional looking for a free software to get the job done on time, 
look no further. If you are a researcher looking for a real-world, TSO-tested platform, 
you're in good hands. If you are a teacher willing to teach your students the ins-and-outs 
of commercial grade software, this is it. And if you are a student willing to learn 
about the algorithms of the books, but for real, we've got you covered.

Our commitment is with you: GridCal is a high quality product. It is free for ever. 
For all of us now and the generations to come.

## Installation

GridCal is a software made in the Python programming language. 
Therefore, it needs a python interpreter installed in your operative system. 
We recommend to install the latest version of [Python](www.python.org) and then, 
install GridCal with the following terminal command:

```
pip install GridCal
```

You may need to use `pip3` if you are under Linux or MacOS, both of which 
come with Python pre-installed already.

### Run th graphical user interface

Once you install GridCal in your local Python distribution, you can run the 
graphical user interface with the following terminal command:

```
python -c "from GridCal.ExecuteGridCal import run; run()"
```

### Install only the engine

Some of you may only need GridCal as a library for some other purpose 
like batch calculations, AI training or simple scripting. Whatever it may be, 
you can get the GridCal engine the following terminal command:

```
pip install GridCalEngine
```

Again, you may need to use `pip3` if you are under Linux or MacOS.

### Standalone setup

If you don't know what is this Python thing, we offer a windows installation:

[Windows setup](https://www.advancedgridinsights.com/gridcal)

This will install GridCal as a normal windows program and you need not to worry 
about any of the previous instructions. Still, if you need some guidance, the 
following video might be of assistance: [Setup tutorial (video)](https://youtu.be/SY66WgLGo54).


## Features

GridCal is packed with feautures:

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

All of these are industry tested algoriths, some of which surpass most comemercially available software.
The aim is to be a drop-in replacement for the expensive and less usable commercial
software, so that you can work, research and learn with it.

### Resources

In an effort to ease the simulation and construction of grids, 
We have included extra materials to work with. These are included in the standalone setups.

- [Load profiles](https://github.com/SanPen/GridCal/tree/master/Grids_and_profiles/equipment) for your projects
- [Grids](https://github.com/SanPen/GridCal/tree/master/Grids_and_profiles/grids) from IEEE and other open projects
- [Equipment catalogue](https://gridcal.readthedocs.io/en/latest/data_sheets.html) (Wires, Cables and Transformers) ready to use in GridCal


### Tutorials and examples

- [Tutorials](https://gridcal.readthedocs.io/en/latest/tutorials/tutorials_module.html)

- [Cloning the repository (video)](https://youtu.be/59W_rqimB6w)

- [Making a grid with profiles (video)](https://youtu.be/H2d_2bMsIS0)

- [GridCal PlayGround repository](https://github.com/yasirroni/GridCalPlayground) with some notebooks and examples.

- [tests](https://github.com/SanPen/GridCal/tree/master/src/tests) may serve as a valuable source of examples.

## API

Since day one, GridCal was meant to be used as a library as much as it was meant 
to be used from the user interface. Following, we include some usage examples, but 
feel free to check the [documentation](https://gridcal.readthedocs.io) out where you will find a complete
description of the theory, the models and the objects.

### Loading a grid

```python
import GridCalEngine.api as gce

# load a grid
my_grid = gce.open_file("my_file.gridcal")
```

GridCal supports a plethora of file formats:

- CIM 16 (.zip and .xml)
- CGMES 2.4.15 (.zip and .xml)
- PSS/e raw and rawx versions 29 to 35, including USA market excahnge RAW-30 specifics.
- Matpower .m files directly.
- DigSilent .DGS (not fully compatible)
- PowerWorld .EPC (not fully compatible, supports substation coordinates)

### Save a grid

```python
import GridCalEngine.api as gce

# create a grid
...

# save
gce.save_file(my_grid, "my_file.gridcal")
```

### Creating a Grid from the API objects

We are going to create a very simple 5-node grid from the excellent book 
*Power System Load Flow Analysis by Lynn Powell*.

```python
import GridCalEngine.api as gce

# declare a circuit object
grid = gce.MultiCircuit()

# Add the buses and the generators and loads attached
bus1 = gce.Bus('Bus 1', vnom=20)
# bus1.is_slack = True  # we may mark the bus a slack
grid.add_bus(bus1)

# add a generator to the bus 1
gen1 = gce.Generator('Slack Generator', vset=1.0)
grid.add_generator(bus1, gen1)

# add bus 2 with a load attached
bus2 = gce.Bus('Bus 2', vnom=20)
grid.add_bus(bus2)
grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

# add bus 3 with a load attached
bus3 = gce.Bus('Bus 3', vnom=20)
grid.add_bus(bus3)
grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

# add bus 4 with a load attached
bus4 = gce.Bus('Bus 4', vnom=20)
grid.add_bus(bus4)
grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

# add bus 5 with a load attached
bus5 = gce.Bus('Bus 5', vnom=20)
grid.add_bus(bus5)
grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

# add Lines connecting the buses
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

```python
import GridCalEngine.api as gce

results = gce.power_flow(grid)

print('\n\n', grid.name)
print('\t|V|:', abs(results.voltage))
print('\t|Sbranch|:', abs(results.Sf))
print('\t|loading|:', abs(results.loading) * 100)
print('\terr:', results.error)
print('\tConv:', results.converged)
```

Using the more complex library objects:

```python
import GridCalEngine.api as gce

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

```python

```

### Linear optimization

```python

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

All trademarks mentioned in the documentation or the source code belong to their respective owners.