Gr  .. _script_cheat_sheet:

Script Cheat Sheet
==================

This page was created as a resource to be able to better use GridCal as a Python library. The page contains everything from importing the library, opening models, running simulations, visualizing results, etc.

Importing the Library
---------------------
Create a Python script, and add the library there are two options:


1. The Entire Engine
^^^^^^^^^^^^^^^^^^^^^
In this case we are going to import everything automatically (recommended).

.. code-block:: python

    from GridCal.Engine import *

This is the way we are going to import GridCal's objects in all the tutorials, except when we import
them from a specific location (see 2). We could also import everything into a namespace in order to
avoid collisions with similarly named objects:

.. code-block:: python

    import GridCal.Engine as gce

Then you would call `gce.Bus()` instead of simply `Bus()`, like this it would be clear
that you are referring to GridCal's Bus object and not to any other object type named `Bus`.

2. Specific Engine Features
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In this case we are going to import only: branches, buses, generators, loads, types, power flow options, power flow solver types,
power flow drivers, multicircuit and time series (it is not limited to the options below).

.. code-block:: python

    from GridCal.Engine.Devices.branch import Branch, BranchTemplate
    from GridCal.Engine.Devices.bus import Bus
    from GridCal.Engine.Devices.generator import Generator
    from GridCal.Engine.Devices.load import Load
    from GridCal.Engine.Devices.types import BranchType
    from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, SolverType
    from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
    from GridCal.Engine.Core.multi_circuit import MultiCircuit
    from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeries




Opening GridCal File
--------------------
Here is how you can open an **existing** GridCal file to your script so you can work with it:

1. Make sure FileOpen Module is imported
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Import the engine and the file handler module below:

.. code-block:: python

    from GridCal.Engine import *
    from GridCal.Engine.IO.file_handler import FileOpen


2. Define and open model
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    grid = FileOpen(**Models_path**).open()

You can open files with the following extensions:
    - .xls: GridCal's old native format: tables saved into an excel file.
    - .xlsx: GridCal's old native format: tables saved into an excel file.
    - .gridcal: GridCal's native format. It is a Zip file with CSV files inside.
    - .sqlite: GridCal tables into a SQLite format.
    - .dgs: Power Factory text file.
    - .m: MatPower and it's FUBM branch of MatPower files.
    - .dpx: INESC (Portugal) exchange file format.
    - .json: REE / GridCal Json file format.
    - .raw: PSSe text file parser for versions 29, 30, 32, 33.
    - .xml: CIM version 16 (as interpreted by Power Factory...)


Saving GridCal File
--------------------
Here is how you can save an GridCal model to your script so you can work with it:

1. Make sure FileSave Module is imported
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Import the engine and the file handler module below:

.. code-block:: python

    from GridCal.Engine import *
    from GridCal.Engine.IO.file_handler import FileSave

2. Save GridCal model
^^^^^^^^^^^^^^^^^^^^^
This assumes you have a GridCal file open, defined and unsaved in your code.

.. code-block:: python

    grid = FileSave(**Models_path**).save()

You can save files with the following extensions:
    - .xls
    - .xlsx
    - .gridcal
    - .sqlite
    - .json
    - .xml

The .json format is the most compatible since it is the easiest to parse and understand
from another software. The excel formats are more human-readable and easy to parse as well.

Creating a New GridCal Model
----------------------------
In order to created a new model you can use these commands (assuming you have imported the GridCal library already). This section will show you the commands and all the options each have.

1. Create a Model
^^^^^^^^^^^^^^^^^

.. code-block:: python

    grid = MultiCircuit()

2. Add Bus
^^^^^^^^^^
Adding a bus named bus1 to grid, and making it a slack bus:

.. code-block:: python

    bus1 = Bus('Bus 1', vnom=20)
    bus1.is_slack = True
    grid.add_bus(bus1)

Other arguments in the Bus() object that can be added are:
.. code-block:: python

    Bus(self, name="Bus", idtag=None, code='', vnom=10, vmin=0.9, vmax=1.1, r_fault=0.0, x_fault=0.0, xpos=0, ypos=0, height=0, width=0, active=True, is_slack=False, is_dc=False, area=None, zone=None, substation=None, country=None, longitude=0.0, latitude=0.0)

3.
^^^^^^^^^^^^^^^^
Adding a bus named bus1 to grid, and making it a slack bus:

.. code-block:: python
    bus1 = Bus('Bus 1', vnom=20)
    bus1.is_slack = True
    grid.add_bus(bus1)

Other arguments in the Bus() object that can be added are:


View GridCal Model
------------------
Once you have opened a GridCal model (previous subsection), here is all you can do to 'grid' (MultiCircuit module):
    - *.get_bus_number()* - returns number of buses in circuit.
    - *.get_branch_lists()* - lists branch lists.
    - *.get_branch_number()* - returns number of branches (any type).
    - *.get_time_number()* - returns number of buses.
    - *.get_dimensions()* - returns 3 dimensions of the grid: 1) # of buses, 2) # of branches and 3) # of time steps.
    - *.clear()* - clear multicircuit and removes buses and branches.
    - *.get_buses()* - returns buses.
    - *.get_branches()* - returns branches.
    - *.get_loads()* - returns loads.
    - *.get_load_names()* - returns load names.
    - *.get_static_generators()* - returns static generators.
    - *.get_static_generators_names()* - returns static generators names.
    - *.get_shunts()* - returns shunts.
    - *.get_shunt_names()* - returns shunts names.
    - *.get_generators()* - returns generators.
    - *.get_battery_names()* - returns battery names.
    - *.get_battery_capacities()* - returns battery capacities.
    - *.get_elements_by_type(DeviceType)* - takes in device types as an arguments, returns all elements from that type.
    - *.get_node_elements_by_type2(DeviceType)* - takes in device types as an arguments, returns all elements from that type.
    - *.apply_lp_profiles()* - applies certain load profile results  as a device profiles.
    - *.copy()* - creats a complete copy of the multicircuit element.
    - *.get_catalogue_dict(Boolean branches_only)* - returns dictionary with catalogue types and a list of objects.
    - *.get_catalogue_dict_by_name(type_class=None)* - returns dictionary with catalogue types and a list of object names.
    - *.get_properties_dict()* - returns JSON dictionary of the multicircuit with: id, type, phases, name, Sbase, comments.
    - *.get_units_dict()*
    - *.assign_circuit()* - assign a circuit to this object.
    - *.build_graph()* -  returns a networkx DiGraph object of the grid.
    - *.create_profiles(steps, step_length, step_unit, time_base: datetime = datetime.now())* - set the default profiles in all the objects enabled to have profiles. Arguments: **steps** (int): Number of time steps,**step_length** (int): Time length (1, 2, 15, ...), **step_unit** (str): Unit of the time step ("h", "m" or "s"), **time_base** (datetime, datetime.now()): Date to start from.
    - *.format_profiles(index)* - format the pandas profiles in place using a time index.
    - *.ensure_profiles_exist()* - format the pandas profiles in place using a time index.
    - *.get_node_elements_by_type(element_type: DeviceType)* - returns set of elements and their parent nodes.
    - *.get_bus_dict()* - return dictionary of buses.
    - *.get_bus_index_dict()* - return dictionary of buses.
    - *.add_bus(obj: Bus)* - adds a bus object to grid.
    - *.delete_bus(obj: Bus)* - deletes a bus object to grid.
    - *.add_line(obj: Line)* - adds a line object to grid.
    - *.add_dc_line(obj: DcLine):* - adds a DC Line object to grid.
    - *.add_transformer2w(obj: Transformer2W)* - adds a transformer object to grid.
    - *.add_hvdc(obj: HvdcLine)* - adds a HVDC Line object to grid.
    - *.add_vsc(obj: VSC)* - adds a VSC Converter object to grid.
    - *.add_upfc(obj: UPFC)* - adds a UPFC Converter object to grid.
    - *.add_branch(obj)* - adds a branch object to grid.
    - *.delete_branch(obj: Branch)* - deletes a branch object to grid.
    - *.delete_line(obj: Line)* - deletes a line object to grid.
    - *.delete_dc_line(obj: DcLine)* - deletes a DC Line object to grid.
    - *.delete_transformer2w(obj: Transformer2W)* - deletes a transformer object to grid.
    - *.delete_hvdc_line(obj: HvdcLine)* - deletes a HVDC Line object to grid.
    - *.delete_vsc_converter(obj: VSC)* - deletes a VSC Converter object to grid.
    - *.delete_upfc_converter(obj: UPFC)* - deletes a UPFC Converter object to grid.
    - *.add_load(bus: Bus, api_obj=None)* - adds load object to a specific bus.
    - *.add_generator(bus: Bus, api_obj=None)* - adds generator object to a specific bus.
    - *.add_static_generator(bus: Bus, api_obj=None)* - adds static generator object to a specific bus.
    - *.add_battery(bus: Bus, api_obj=None)* - adds battery object to a specific bus.
    - *.add_shunt(bus: Bus, api_obj=None)* - adds shunt object to a specific bus.
    - *.add_wire(obj: Wire)* - adds wire to collection.
    - *.delete_wire(i, catalogue_to_check=None)* - delete wire from collection.
    - *.add_overhead_line( obj: Tower)* - adds overhead line (tower) template to the collection.
    - *.delete_overhead_line(i, catalogue_to_check=None)* - deletes overhead line (tower) template to the collection.
    - *.add_underground_line(obj: UndergroundLineType)* - adds underground line.
    - *.delete_underground_line(i, catalogue_to_check=None)* - deletes underground line.
    - *.add_sequence_line(obj: SequenceLineType)* - adds sequence line to collection.
    - *.delete_sequence_line(i, catalogue_to_check=None)* - deletes sequence line to collection.
    - *.add_transformer_type(obj: TransformerType)* - adds transformer template.
    - *.delete_transformer_type(i, catalogue_to_check)* - deletes transformer template.
    - *.apply_all_branch_types)* - apply all branch types.
    - *.add_substation(obj: Substation)* - adds substation.
    - *.delete_substation(i)* - deletes substation.
    - *.add_area(obj: Area)* - adds area.
    - *.delete_area(i)* - deletes area.
    - *.add_zone(obj: Zone)* - adds zone.
    - *.delete_zone(i)* - deletes zone.
    - *.add_country(obj: Country)* - adds country.
    - *.delete_country(i)* - deletes country.
    - *.plot_graph(ax=None)* - plot grid using matplotlib.
    - *.export_pf(file_name, power_flow_results)* - exports power flow results to excel file.
    - *.export_profiles(file_name)* - export profiles to file.
    - *.set_state(t)* - set profile sstate at the index to as a default value.
    - *.get_bus_branch_connectivity_matrix()* - get the branch-bus connectivity.
    - *.get_adjacent_matrix()* - get the bus adjacent matrix.
    - *.get_adjacent_buses(A: csc_matrix, bus_idx)* - return array of indices of the buses adjacent to the bus given by it's index.
    - *.try_to_fix_buses_location(buses_selection)* - try to fix the location of the null-location buses.
    - *.get_center_location()* - get the mean coordinates of the system (lat, lon).
    - *.get_boundaries(buses)* - get the graphic representation boundaries.
    - *.average_separation(branches)* - returns average separation of buses.
    - *.add_circuit(circuit: "MultiCircuit", angle)* -adss new circuit object to current circuit object.
    - *.snapshot_balance()* - creates a report DataFrame with the snapshot active power balance.
    - *.scale_power(factor)* - modify the loads and generators.
    - *.get_used_templates()* - returns list of used templates in the objects.
    - *.get_automatic_precision()* - get the precision that simulates correctly the power flow.
    - *.fill_xy_from_lat_lon(destructive=True, factor=0.01)* - fill the x and y value from the latitude and longitude values.

**Example:**

To get the number of buses in the grid and save it in the variable "buses":

.. code-block:: python

    buses = grid.get_bus_number()

**Example:**

To add a branch, that has  branch object as a parameter:

.. code-block:: python

   grid.add_branch(Branch(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02))

Running a Power Flow
--------------------

Running a Time Series Power Flow
--------------------------------

Visualize Results
-----------------



Further functions can be found the in the source code. In order to see how to create the distribution grid example using the library look here

