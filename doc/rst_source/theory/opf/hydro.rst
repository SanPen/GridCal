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

.. figure:: ../../figures/opf/fluid_elements.png

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

    \quad f_obj += \sum_m^{nm} cost_spill[m] \sum_t^{nt} spill[t,m] \\

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
                       - dt * flow_out[t,m] \\

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

(scripting)

.. code-block:: python

    def hello_world():
        print("Hello, world!")