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

1. **Node**: a given point in the fluid network, which is supposed to have a certain fluid level, fluid devices connected to it (such as turbines, pumps or P2Xs) and branches (potentially both electrical and fluid paths).
2. **Path**: a connection between two fluid nodes, with limits in the flow it can transport. 
3. **Turbine**: a device that transforms the mechanical energy from the fluid to electrical energy. As such, it has a generator associated to it.
4. **Pump** a device that works in the reverse direction of a turbine. It converts electrical to mechanical energy.
5. **P2X** a device responsible for the appearance of fluid from the consumption of power. It symbolizes the generalization of the power-to-gas technology used in hydrogen production, for instance.

.. figure:: ../../figures/opf/fluid_elements.png

    An overview of a fluid network with nodes linked through paths, a P2X, a pump, and a turbine.

Each fluid model has a list of defining attributes. The relationship between the attribute name and the associated description is provided below. 

1. Node 
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


2. Path
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


3. Turbine
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

4. Pump
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


5. P2X
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

3. Practical example
--------------------

(scripting)

.. code-block:: python

    def hello_world():
        print("Hello, world!")