Linear time-series optimization considering hydro plants
==========================================================

Just as power systems can be optimized accounting for all their electrical assets, the same can be said about the hydropower infrastructure. As a result, the operator ends up with two grids of different nature: one where electrons flow, and one where a fluid is transported. The two grids can be coupled, and consequently, they have to be simultaneously optimized. GridCal now integrates models for the fluid grid (e.g. a hydroelectric system), and adapts the optimization code to take these new devices into consideration.

The present document outlines the main additions in this regard, including:

- The models of a fluid grid.
- The effects of such new devices on the optimization problem.
- A practical example to illustrate the concepts.

1. Fluid models
---------------
There are five different models that have been introduced with this update. These are:

- **Node**: a given point in the fluid network, which is supposed to have a certain fluid level, fluid devices connected to it (such as turbines, pumps or P2Xs) and branches (potentially both electrical and fluid paths).
- **Path**: a connection between two fluid nodes, with limits in the flow it can transport. 
- **Turbine**: a device that transforms the mechanical energy from the fluid to electrical energy. As such, it has a generator associated to it.
- **Pump** a device that works in the reverse direction of a turbine. It converts electrical to mechanical energy.
- **P2X** a device responsible for the appearance of fluid from the consumption of power. It symbolizes the generalization of the power-to-gas technology used in hydrogen production, for instance.

.. figure:: ./../../figures/opf/fluid_elements.png

    An overview of a fluid network with nodes linked through paths, a P2X, a pump, and a turbine.

Each fluid model has a list of defining attributes. The relationship between the attribute name and the associated description is provided below. 

Node 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ================  ========  ================================================
        name          class_type       unit                      descriptions                  
    =============  ================  ========  ================================================
    idtag          str                         Unique ID                                       
    name           str                         Name of the branch.                             
    code           str                         Secondary ID                                    
    min_level      float             hm3       Minimum amount of fluid at the node/reservoir   
    max_level      float             hm3       Maximum amount of fluid at the node/reservoir   
    initial_level  float             hm3       Initial level of the node/reservoir             
    bus            Bus                         Electrical bus.                                 
    build_status   enum BuildStatus            Branch build status. Used in expansion planning.
    spillage_cost  float             €/(m3/s)  Cost of nodal spillage                          
    inflow         float             m3/s      Flow of fluid coming from the rain              
    =============  ================  ========  ================================================


Path
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ========  ==========  ====  ===================
      name    class_type  unit     descriptions    
    ========  ==========  ====  ===================
    idtag     str               Unique ID          
    name      str               Name of the branch.
    code      str               Secondary ID       
    source    Fluid node        Source node        
    target    Fluid node        Target node        
    min_flow  float       m3/s  Minimum flow       
    max_flow  float       m3/s  Maximum flow       
    ========  ==========  ====  ===================


Turbine
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ================  ======  ================================================
        name          class_type      unit                     descriptions                  
    =============  ================  ======  ================================================
    idtag          str                       Unique ID                                       
    name           str                       Name of the branch.                             
    code           str                       Secondary ID                                    
    efficiency     float             MWh/m3  Power plant energy production per fluid unit    
    max_flow_rate  float             m3/s    maximum fluid flow                              
    plant          Fluid node                Connection reservoir/node                       
    generator      Generator                 Electrical machine                              
    build_status   enum BuildStatus          Branch build status. Used in expansion planning.
    =============  ================  ======  ================================================

Pump
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ================  ======  ================================================
        name          class_type      unit                     descriptions                  
    =============  ================  ======  ================================================
    idtag          str                       Unique ID                                       
    name           str                       Name of the branch.                             
    code           str                       Secondary ID                                    
    efficiency     float             MWh/m3  Power plant energy production per fluid unit    
    max_flow_rate  float             m3/s    maximum fluid flow                              
    plant          Fluid node                Connection reservoir/node                       
    generator      Generator                 Electrical machine                              
    build_status   enum BuildStatus          Branch build status. Used in expansion planning.
    =============  ================  ======  ================================================


P2X
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ================  ======  ================================================
        name          class_type      unit                     descriptions                  
    =============  ================  ======  ================================================
    idtag          str                       Unique ID                                       
    name           str                       Name of the branch.                             
    code           str                       Secondary ID                                    
    efficiency     float             MWh/m3  Power plant energy production per fluid unit    
    max_flow_rate  float             m3/s    maximum fluid flow                              
    plant          Fluid node                Connection reservoir/node                       
    generator      Generator                 Electrical machine                              
    build_status   enum BuildStatus          Branch build status. Used in expansion planning.
    =============  ================  ======  ================================================

It is worth noting that turbines, pumps and P2Xs are fluid devices coupled to an electrical machine. That is, a generator is automatically created when these devices are built. The following conditions have to be considered in the corresponding generators:

.. table::

    ============================= ============ ============ ============
        Fluid device type             Cost         Pmax         Pmin    
    ============================= ============ ============ ============
    Turbine                            >=0           >0          >=0
    Pump                               <=0           <=0         <0
    P2X                                <=0           <=0         <0
    ============================= ============ ============ ============




2. Optimization adaptation 
--------------------------
The fluid transport problem is contemplated similarly with respect to the electrical problem. Basically, the flow balance has to be maintained at each node. The formulation that follows revolves around this idea.

2.1 Objective function
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The general objective function remains nearly untouched, as the generators associated with turbines, pumps and P2Xs are already considered in the code fraction dedicated to generation units. There is only a single addition to be accounted for, and this is the spillage cost. Hence, the following term is added:

.. math::

    \quad f_obj += \sum_m^{nm} cost_spill[m] \sum_t^{nt} spill[t,m]

where :math:`f_obj` is the objective function, :math:`m` is the fluid node index, :math:`nm` the number of fluid nodes, :math:`t` the time index, :math:`nt` the length of the time series, and :math:`spill` the actual spillage.

2.2 Balance constraint
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The flow balance has to be maintained at each node :math:`m` for each point in time :math:`t`. In general terms, it is expressed as:

.. math::

    \quad level[t,m] = level[t-1,m] \\
                       + dt * inflow[m] \\
                       + dt * flow_in[t,m] \\
                       + dt * flow_{p2x}[t,m] \\
                       - dt * spill[t,m] \\
                       - dt * flow_out[t,m]

where :math:`dt` is the time step, :math:`inflow[m]` is known data of the entering fluid flow, :math:`flow_in[t,m]` is the sum of the input flows from the connected paths, :math:`flow_{p2x}[t,m]` is the input flow coming from the P2Xs, and :math:`flow_out[t,m]` is the sum of the output flows from the connected paths. In case the first time index is being simulated, :math:`level[t-1,m]` is simply replaced by :math:`initial_level[m]`, which is input information.

The level of any given node has to be connected somehow to the contribution of injection devices. Hence, to consider turbines:

.. math::

    flow_out[t,m] += \sum_{i \in m}^{ni} p[t,g] * flow_max[i] / (p_max[g] * turb_eff[i])

where :math:`i` is the turbine index, :math:`p[t,g]` is the generation power at time :math:`t` for generator index :math:`g`, :math:`flow_max` is the maximum turbine flow, :math:`p_max` the maximum generator power in per unit, and :math:`turb_eff` the turbine's efficiency.

Similarly, for pumps:

.. math::

    flow_in[t,m] -= \sum_{i \in m}^{ni} p[t,g] * flow_max[i] * pump_eff[i] / abs(p_min[g])

where :math:`i` is the pump index, :math:`p[t,g]` is the generation power at time :math:`t` for generator index :math:`g`, :math:`flow_max` is the maximum pump flow, :math:`p_min` the minimum generator power in per unit, and :math:`pump_eff` the pump's efficiency.

In the case of P2Xs, it follows the same expression as in pumps:

.. math::

    flow_{p2x}[t,m] += \sum_{i \in m}^{ni} p[t,g] * flow_max[i] * p2x_eff[i] / abs(p_min[g])




2.3 Output results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The results of interest for each device type are shown below.

Node 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============================  ================  ======  =================================================
    name                           class_type        unit    descriptions                                      
    =============================  ================  ======  =================================================
    fluid_node_current_level       float             hm3     Node level                                         
    fluid_node_flow_in             float             m3/s    Input flow from paths                                                                             
    fluid_node_flow_out            float             m3/s    Output flow from paths                                       
    fluid_node_p2x_flow            float             m3/s    Input flow from the P2Xs  
    fluid_node_spillage            float             m3/s    Lost flow                           
    =============================  ================  ======  =================================================


Path 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============================  ================  ======  =================================================
    name                           class_type        unit    descriptions                                      
    =============================  ================  ======  =================================================
    fluid_path_flow                     float         m3/s   Flow circulating through the path                                            
    =============================  ================  ======  =================================================

Injection (turbine, pump, P2X)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============================  ================  ======  =================================================
    name                           class_type        unit    descriptions                                      
    =============================  ================  ======  =================================================
    fluid_injection_flow                    float      m3/s   Flow injected by the device                                            
    =============================  ================  ======  =================================================





3. Practical example
--------------------
This section covers a practical case to exemplify how to build a grid containing fluid type devices, run the time-series linear optimization, and explore the results. Everything will be shown through GridCal's scripting functionalities.


Model initialization 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    grid = gce.MultiCircuit(name='hydro_grid')

    # let's create a master profile
    date0 = dt.datetime(2023, 1, 1)
    time_array = pd.DatetimeIndex([date0 + dt.timedelta(hours=i) for i in range(10)])
    x = np.linspace(0, 10, len(time_array))
    df_0 = pd.DataFrame(data=x, index=time_array)  # complex values

    # set the grid master time profile
    grid.time_profile = df_0.index


Add fluid side
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    # Add some fluid nodes, with their electrical buses
    fb1 = gce.Bus(name='fb1')
    fb2 = gce.Bus(name='fb2')
    fb3 = gce.Bus(name='fb3')

    grid.add_bus(fb1)
    grid.add_bus(fb2)
    grid.add_bus(fb3)

    f1 = gce.FluidNode(name='fluid_node_1',
                       min_level=0.,
                       max_level=100.,
                       current_level=50.,
                       spillage_cost=10.,
                       inflow=0.,
                       bus=fb1)

    f2 = gce.FluidNode(name='fluid_node_2',
                       spillage_cost=10.,
                       bus=fb2)

    f3 = gce.FluidNode(name='fluid_node_3',
                       spillage_cost=10.,
                       bus=fb3)

    f4 = gce.FluidNode(name='fluid_node_4',
                       min_level=0,
                       max_level=100,
                       current_level=50,
                       spillage_cost=10.,
                       inflow=0.)

    grid.add_fluid_node(f1)
    grid.add_fluid_node(f2)
    grid.add_fluid_node(f3)
    grid.add_fluid_node(f4)

    # Add the paths
    p1 = gce.FluidPath(name='path_1',
                       source=f1,
                       target=f2,
                       min_flow=-50.,
                       max_flow=50.,)

    p2 = gce.FluidPath(name='path_2',
                       source=f2,
                       target=f3,
                       min_flow=-50.,
                       max_flow=50.,)

    p3 = gce.FluidPath(name='path_3',
                       source=f3,
                       target=f4,
                       min_flow=-50.,
                       max_flow=50.,)

    grid.add_fluid_path(p1)
    grid.add_fluid_path(p2)
    grid.add_fluid_path(p3)

    # Add electrical generators for each fluid machine
    g1 = gce.Generator(name='turb_1_gen',
                       Pmax=1000.0,
                       Pmin=0.0,
                       Cost=0.5)

    g2 = gce.Generator(name='pump_1_gen',
                       Pmax=0.0,
                       Pmin=-1000.0,
                       Cost=-0.5)

    g3 = gce.Generator(name='p2x_1_gen',
                       Pmax=0.0,
                       Pmin=-1000.0,
                       Cost=-0.5)

    grid.add_generator(fb3, g1)
    grid.add_generator(fb2, g2)
    grid.add_generator(fb1, g3)

    # Add a turbine
    turb1 = gce.FluidTurbine(name='turbine_1',
                             plant=f3,
                             generator=g1,
                             max_flow_rate=45.0,
                             efficiency=0.95)

    grid.add_fluid_turbine(f3, turb1)

    # Add a pump
    pump1 = gce.FluidPump(name='pump_1',
                          reservoir=f2,
                          generator=g2,
                          max_flow_rate=49.0,
                          efficiency=0.85)

    grid.add_fluid_pump(f2, pump1)

    # Add a p2x
    p2x1 = gce.FluidP2x(name='p2x_1',
                        plant=f1,
                        generator=g3,
                        max_flow_rate=49.0,
                        efficiency=0.9)

    grid.add_fluid_p2x(f1, p2x1)


Add remaining electrical side
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    # Add the electrical grid part
    b1 = gce.Bus(name='b1',
                 vnom=10,
                 is_slack=True)

    b2 = gce.Bus(name='b2',
                 vnom=10)

    grid.add_bus(b1)
    grid.add_bus(b2)

    g0 = gce.Generator(name='slack_gen',
                       Pmax=1000.0,
                       Pmin=0.0,
                       Cost=0.8)

    grid.add_generator(b1, g0)

    l1 = gce.Load(name='l1',
                  P=11,
                  Q=0)

    grid.add_load(b2, l1)

    line1 = gce.Line(name='line1',
                     bus_from=b1,
                     bus_to=b2,
                     rate=5,
                     x=0.05)

    line2 = gce.Line(name='line2',
                     bus_from=b1,
                     bus_to=fb1,
                     rate=10,
                     x=0.05)

    line3 = gce.Line(name='line3',
                     bus_from=b1,
                     bus_to=fb2,
                     rate=10,
                     x=0.05)

    line4 = gce.Line(name='line4',
                     bus_from=fb3,
                     bus_to=b2,
                     rate=15,
                     x=0.05)

    grid.add_line(line1)
    grid.add_line(line2)
    grid.add_line(line3)
    grid.add_line(line4)

The resulting system is the one shown below.

.. figure:: ./../../figures/opf/case6_fluid.png

Run optimization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    # Run the simulation
    opf_driver = gce.OptimalPowerFlowTimeSeriesDriver(grid=grid)

    print('Solving...')
    opf_driver.run()

    print("Status:", opf_driver.results.converged)
    print('Angles\n', np.angle(opf_driver.results.voltage))
    print('Branch loading\n', opf_driver.results.loading)
    print('Gen power\n', opf_driver.results.generator_power)


Results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Generation power, in MW**

+----------------------+-----------+-------------+--------------+------------+
| time                 | p2x_1_gen | pump_1_gen  | turb_1_gen   | slack_gen  |
+======================+===========+=============+==============+============+
| 2023-01-01 00:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 01:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 02:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 03:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 04:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 05:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 06:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 07:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 08:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+
| 2023-01-01 09:00:00  | 0.0       | -6.8237821  | 6.0          | 11.823782  |
+----------------------+-----------+-------------+--------------+------------+

**Fluid node level, in m3**

+----------------------+--------------+--------------+--------------+--------------+
| time                 | fluid_node_1 | fluid_node_2 | fluid_node_3 | fluid_node_4 |
+======================+==============+==============+==============+==============+
| 2023-01-01 00:00:00  | 49.998977    | 0.0          | 0.0          | 50.001023    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 01:00:00  | 49.997954    | 0.0          | 0.0          | 50.002046    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 02:00:00  | 49.996931    | 0.0          | 0.0          | 50.003069    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 03:00:00  | 49.995907    | 0.0          | 0.0          | 50.004093    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 04:00:00  | 49.994884    | 0.0          | 0.0          | 50.005116    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 05:00:00  | 49.993861    | 0.0          | 0.0          | 50.006139    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 06:00:00  | 49.992838    | 0.0          | 0.0          | 50.007162    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 07:00:00  | 49.991815    | 0.0          | 0.0          | 50.008185    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 08:00:00  | 49.990792    | 0.0          | 0.0          | 50.009208    |
+----------------------+--------------+--------------+--------------+--------------+
| 2023-01-01 09:00:00  | 49.989768    | 0.0          | 0.0          | 50.010232    |
+----------------------+--------------+--------------+--------------+--------------+

**Path flow, in m3/s**

+----------------------+----------+----------+----------+
| time                 | path_1   | path_2   | path_3   |
+======================+==========+==========+==========+
| 2023-01-01 00:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 01:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 02:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 03:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 04:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 05:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 06:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 07:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 08:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
| 2023-01-01 09:00:00  | 0.284211 | 0.284211 | 0.284211 |
+----------------------+----------+----------+----------+
