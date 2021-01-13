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
    - **name** (str, "Bus"): Name of the bus.
    - **vnom** (float, 10.0): Nominal voltage in kV.
    - **vmin** (float, 0.9): Minimum per unit voltage.
    - **vmax** (float, 1.1): Maximum per unit voltage.
    - **r_fault** (float, 0.0): Resistance of the fault in per unit (SC only).
    - **x_fault** (float, 0.0): Reactance of the fault in per unit (SC only).
    - **xpos** (int, 0): X position in pixels (GUI only).
    - **ypos** (int, 0): Y position in pixels (GUI only).
    - **height** (int, 0): Height of the graphic object (GUI only).
    - **width** (int, 0): Width of the graphic object (GUI only).
    - **active** (bool, True): Is the bus active?
    - **is_slack** (bool, False): Is this bus a slack bus?
    - **area** (str, "Default"): Name of the area.
    - **zone** (str, "Default"): Name of the zone.
    - **substation** (str, "Default"): Name of the substation.

**Note:** if the arguments of the object are not explicitly selected, then GridCal will set them to the default values (above).

3. Add Load
^^^^^^^^^^^
Adding a load named l2 to bus 2:

.. code-block:: python

    l2 = Load(name='Load',
          G=0, B=0,  # admittance of the ZIP model in MVA at the nominal voltage
          Ir=0, Ii=0,  # Current of the ZIP model in MVA at the nominal voltage
          P=40, Q=20,  # Power of the ZIP model in MVA
          active=True,  # Is active?
          mttf=0.0,  # Mean time to failure
          mttr=0.0  # Mean time to recovery
          )
    grid.add_load(bus2, l2)

Other arguments in the Load() object that can be added are:
    - **name** (str, "Load"): Name of the load.
    - **G** (float, 0.0): Conductance in equivalent MW.
    - **B** (float, 0.0): Susceptance in equivalent MVAr.
    - **Ir** (float, 0.0): Real current in equivalent MW.
    - **Ii** (float, 0.0): Imaginary current in equivalent MVAr.
    - **P** (float, 0.0): Active power in MW.
    - **Q** (float, 0.0): Reactive power in MVAr.
    - **G_prof** (DataFrame, None): Pandas DataFrame with the conductance profile in equivalent MW.
    - **B_prof** (DataFrame, None): Pandas DataFrame with the susceptance profile in equivalent MVAr
    - **Ir_prof** (DataFrame, None): Pandas DataFrame with the real current profile in equivalent MW.
    - **Ii_prof** (DataFrame, None): Pandas DataFrame with the imaginary current profile in equivalent MVAr.
    - **P_prof** (DataFrame, None): Pandas DataFrame with the active power profile in equivalent MW.
    - **Q_prof** (DataFrame, None): Pandas DataFrame with the reactive power profile in equivalent MVAr.
    - **active** (bool, True): Is the load active?
    - **mttf** (float, 0.0): Mean time to failure in hours.
    - **mttr** (float, 0.0): Mean time to recovery in hours.

**Note:** if the arguments of the object are not explicitly selected, then GridCal will set them to the default values (above).
**Note:** in GridCal, loads, generators, etc are stored within each bus.
**Note:** (+) to act as a load, (-) to act as a generator.
**Note:** this is a ZIP load model.

4. Add Generator
^^^^^^^^^^^^^^^^
Adding a generator named g1 to bus 1:

.. code-block:: python

    g1 = Generator(name='gen',
               active_power=0.0,  # Active power in MW, since this generator is used to set the slack , is 0
               voltage_module=1.0,  # Voltage set point to control
               Qmin=-9999,  # minimum reactive power in MVAr
               Qmax=9999,  # Maximum reactive power in MVAr
               Snom=9999,  # Nominal power in MVA
               power_prof=None,  # power profile
               vset_prof=None,  # voltage set point profile
               active=True  # Is active?
               )
    grid.add_generator(bus1, g1)

Other arguments in the Load() object that can be added are:
    - **name** (str, "gen"): Name of the generator.
    - **active_power** (float, 0.0): Active power in MW.
    - **power_factor** (float, 0.8): Power factor.
    - **voltage_module** (float, 1.0): Voltage setpoint in per unit.
    - **is_controlled** (bool, True): Is the generator voltage controlled?
    - **Qmin** (float, -9999): Minimum reactive power in MVAr.
    - **Qmax** (float, 9999): Maximum reactive power in MVAr.
    - **Snom** (float, 9999): Nominal apparent power in MVA.
    - **power_prof** (DataFrame, None): Pandas DataFrame with the active power profile in MW.
    - **power_factor_prof** (DataFrame, None): Pandas DataFrame with the power factor profile.
    - **vset_prof** (DataFrame, None): Pandas DataFrame with the voltage setpoint profile in per unit.
    - **active** (bool, True): Is the generator active?
    - **p_min** (float, 0.0): Minimum dispatchable power in MW.
    - **p_max** (float, 9999): Maximum dispatchable power in MW.
    - **op_cost** (float, 1.0): Operational cost in Eur (or other currency) per MW.
    - **Sbase** (float, 100): Nominal apparent power in MVA.
    - **enabled_dispatch** (bool, True): Is the generator enabled for OPF?
    - **mttf** (float, 0.0): Mean time to failure in hours.
    - **mttr** (float, 0.0): Mean time to recovery in hours.
    - **technology** (GeneratorTechnologyType): Instance of technology to use.
    - **q_points**: list of reactive capability curve points [(P1, Qmin1, Qmax1), (P2, Qmin2, Qmax2), ...].
    - **use_reactive_power_curve**: Use the reactive power curve? otherwise use the plain old limits.

**Note:** if the arguments of the object are not explicitly selected, then GridCal will set them to the default values (above).

4. Add Line
^^^^^^^^^^^
Adding a line from bus 1 to bus 2 named Line12:

.. code-block:: python

    Line12 = Line(bus_from=bus1,
             bus_to=bus2,
             name='Line 1-2',
             r=0.05,  # resistance of the pi model in per unit
             x=0.11,  # reactance of the pi model in per unit
             g=1e-20,  # conductance of the pi model in per unit
             b=0.02,  # susceptance of the pi model in per unit
             rate=50,  # Rate in MVA
             tap=1.0,  # Tap value (value close to 1)
             shift_angle=0,  # Tap angle in radians
             active=True,  # is the branch active?
             mttf=0,  # Mean time to failure
             mttr=0,  # Mean time to recovery
             branch_type=BranchType.Line,  # Branch type tag
             length=1,  # Length in km (to be used with templates)
             template=BranchTemplate()  # Branch template (The default one is void)
             )
    grid.add_line(Line12)


Other arguments in the Line() object that can be added are:
    - **bus_from** (:ref:`Bus`): "From" :ref:`bus<Bus>` object.
    - **bus_to** (:ref:`Bus`): "To" :ref:`bus<Bus>` object.
    - **name** (str, "Branch"): Name of the branch.
    - **r** (float, 1e-20): Branch resistance in per unit.
    - **x** (float, 1e-20): Branch reactance in per unit.
    - **g** (float, 1e-20): Branch shunt conductance in per unit.
    - **rate** (float, 1.0): Branch rate in MVA.
    - **tap** (float, 1.0): Branch tap module.
    - **shift_angle** (int, 0): Tap shift angle in radians.
    - **active** (bool, True): Is the branch active?
    - **tolerance** (float, 0): Tolerance specified for the branch impedance in %.
    - **mttf** (float, 0.0): Mean time to failure in hours.
    - **mttr** (float, 0.0): Mean time to recovery in hours.
    - **r_fault** (float, 0.0): Mid-line fault resistance in per unit (SC only).
    - **x_fault** (float, 0.0): Mid-line fault reactance in per unit (SC only).
    - **fault_pos** (float, 0.0): Mid-line fault position in per unit (0.0 = `bus_from`, 0.5 = middle, 1.0 = `bus_to`).
    - **branch_type** (BranchType, BranchType.Line): Device type enumeration (ex.: :class:`GridCal.Engine.Devices.transformer.TransformerType`).
    - **length** (float, 0.0): Length of the branch in km.
    - **vset** (float, 1.0): Voltage set-point of the voltage controlled bus in per unit.
    - **temp_base** (float, 20.0): Base temperature at which `r` is measured in °C.
    - **temp_oper** (float, 20.0): Operating temperature in °C.
    - **alpha** (float, 0.0033): Thermal constant of the material in °C.
    - **bus_to_regulated** (bool, False): Is the `bus_to` voltage regulated by this branch?
    - **template** (BranchTemplate, BranchTemplate()): Basic branch template.

**Note:** if the arguments of the object are not explicitly selected, then GridCal will set them to the default values (above).
**Note:** branch is a legacy model, try to use line or transformer instead.

4. Add Transformer
^^^^^^^^^^^^^^^^^^
Adding a transformer named Transformer1:

.. code-block:: python

    Transformer1 = (hv_nominal_voltage=0,
                    lv_nominal_voltage=0,
                    nominal_power=0.001,
                    copper_losses=0,
                    iron_losses=0,
                    no_load_current=0,
                    short_circuit_voltage=0,
                    gr_hv1=0.5, gx_hv1=0.5,
                    name='TransformerType',
                    tpe=BranchType.Transformer,
                    idtag=None)
    grid.add_transformer2w(Transformer1)


Other arguments in the Transformer2w() object that can be added are:

    - **hv_nominal_voltage** (float, 0.0): Primary side nominal voltage in kV (tied to the Branch's `bus_from`).
    - **lv_nominal_voltage** (float, 0.0): Secondary side nominal voltage in kV (tied to the Branch's `bus_to`).
    - **nominal_power** (float, 0.0): Transformer nominal apparent power in MVA.
    - **copper_losses** (float, 0.0): Copper losses in kW (also known as short circuit power).
    - **iron_losses** (float, 0.0): Iron losses in kW (also known as no-load power).
    - **no_load_current** (float, 0.0): No load current in %.
    - **short_circuit_voltage** (float, 0.0): Short circuit voltage in %.
    - **gr_hv1** (float, 0.5): Resistive contribution to the primary side in per unit (at the Branch's `bus_from`).
    - **gx_hv1** (float, 0.5): Reactive contribution to the primary side in per unit (at the Branch's `bus_from`).
    - **name** (str, "TransformerType"): Name of the type.
    - **tpe** (BranchType, BranchType.Transformer): Device type enumeration.

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
Once a grid has been loaded/created Power Flow analysis can be run like this:

.. code-block:: python

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,  # Base method to use
                              verbose=False,  # Verbose option where available
                              tolerance=1e-6,  # power error in p.u.
                              max_iter=25,  # maximum iteration number
                              control_q=True  # if to control the reactive power
                              )
    pf = PowerFlowDriver(grid, pf_options)
    pf.run()


Some of the Arguments/Options that can be added to the Power Flow method are:

    - **solver_type** (:ref:`SolverType<solver_type>`, SolverType.NR) -  Solver type.
    - **retry_with_other_methods** (bool, True) - Use a battery of methods to tackle the problem if the main solver fails.
    - **verbose** (bool, False) - Print additional details in the logger.
    - **initialize_with_existing_solution** (bool, True) -  *To be detailed*.
    - **tolerance** (float, 1e-6): Solution tolerance for the power flow numerical methods.
    - **max_iter** (int, 25): Maximum number of iterations for the power flow numerical method.
    - **max_outer_loop_iter** (int, 100): Maximum number of iterations for the controls outer loop.
    - **control_q** (:ref:`ReactivePowerControlMode<q_control>`, ReactivePowerControlMode.NoControl): Control mode for the PV nodes reactive power limits.
    -  **control_taps** (:ref:`TapsControlMode<taps_control>`, TapsControlMode.NoControl): Control mode for the transformer taps equipped with a voltage regulator (as part of the outer loop).
    - **multi_core** (bool, False): Use multi-core processing? applicable for time series.
    - **dispatch_storage** (bool, False): Dispatch storage?
    - **control_p** (bool, False): Control active power (optimization dispatch).
    - **apply_temperature_correction** (bool, False): Apply the temperature correction to the resistance of the branches?
    - **branch_impedance_tolerance_mode** (BranchImpedanceMode, BranchImpedanceMode.Specified): Type of modification of the branches impedance.
    - **q_steepness_factor** (float, 30): Steepness factor :math:`k` for the :ref:`ReactivePowerControlMode<q_control>` iterative control.
    - **distributed_slack** (bool, False): Applies the redistribution of the slack power proportionally among the controlled generators.
    - **ignore_single_node_islands** (bool, False): If True the islands of 1 node are ignored.
    - **backtracking_parameter** (float, 1e-4): parameter used to correct the "bad" iterations, typically 0.5.



Running a Time Series Power Flow
--------------------------------
Once a grid has been loaded/created Time Series Power Flow analysis can be run like this:

.. code-block:: python

    ts = TimeSeries(grid=grid,
                options=pf_options,
                opf_time_series_results=None,
                start_=0,
                end_=None)
    ts.run()

Some of the Arguments/Options that can be added to the Power Flow method are:
    - **grid: MultiCircuit**: grid object to which the analysis will be run.
    - **options: PowerFlowOptions**: power flow options that will be selected.
    - **opf_time_series_results=None**:
    - **start_=0**: start time.
    - **end_=None**: end time.
    - **use_clustering=False**: clustering selection.
    - **cluster_number=10**: clustering number.


Results
-------
Once the analysis have been run. There are different options to export and/or display results. You will have to manually pick the results you want to display and how. However, this gives great flexibility.


First, import Pandas and NumPy libraries:

.. code-block:: python

    import numpy as np
    import pandas as pd

Assuming you have done a Power Flow study and the result is stored in 'pf'. Then you can export:

1. To Excel
^^^^^^^^^^^

.. code-block:: python

    Results = pd.ExcelWriter('Results.xlsx')
    # Create Headers
    headers = ['Vm (p.u.)', 'Va (Deg)', 'Vre', 'Vim']
    # Choose variables to display
    Vm = np.abs(pf.results.voltage)
    Va = np.angle(pf.results.voltage, deg=True)
    Vre = pf.results.voltage.real
    Vim = pf.results.voltage.imag
    data = np.c_[Vm, Va, Vre, Vim]
    # Create Data Frame
    v_df = pd.DataFrame(data=data, columns=headers, index=grid.bus_names)
    # Export Results
    v_df.to_excel(Results, sheet_name='V')


2. To CSV
^^^^^^^^^

.. code-block:: python

    Results = pd.CSVWriter('Results.csv')
    # Create Headers
    headers = ['Vm (p.u.)', 'Va (Deg)', 'Vre', 'Vim']
    # Choose variables to display
    Vm = np.abs(pf.results.voltage)
    Va = np.angle(pf.results.voltage, deg=True)
    Vre = pf.results.voltage.real
    Vim = pf.results.voltage.imag
    data = np.c_[Vm, Va, Vre, Vim]
    # Create Data Frame
    v_df = pd.DataFrame(data=data, columns=headers, index=grid.bus_names)
    # Export Results
    v_df.to_csv(Results, sheet_name='V')


Further functions can be found the in the source code. In order to see a complete distribution grid example using the library look here_.

.. _here: https://gridcal.readthedocs.io/en/latest/tutorials/five_node_grid.html

