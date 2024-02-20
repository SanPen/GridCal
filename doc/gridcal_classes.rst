Models
=============

Roseta
------------------------------------------------------------

Area
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  =========  ==========  ====  =========  =========  =====================  =======
    class    name     class_type  unit  mandatory  max_chars      descriptions       comment
    =====  =========  ==========  ====  =========  =========  =====================  =======
    Area   idtag      str               False                 Unique ID                     
    Area   name       str               False                 Name of the branch.           
    Area   code       str               False                 Secondary ID                  
    Area   longitude  float       deg   False                 longitude of the bus.         
    Area   latitude   float       deg   False                 latitude of the bus.          
    =====  =========  ==========  ====  =========  =========  =====================  =======


Battery
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =======  ========================  =================  ======  =========  =========  ==========================================================================  =======
     class             name               class_type       unit   mandatory  max_chars                                 descriptions                                 comment
    =======  ========================  =================  ======  =========  =========  ==========================================================================  =======
    Battery  idtag                     str                        False                 Unique ID                                                                          
    Battery  name                      str                        False                 Name of the branch.                                                                
    Battery  code                      str                        False                 Secondary ID                                                                       
    Battery  bus                       Bus                        False                 Connection bus                                                                     
    Battery  cn                        Connectivity Node          False                 Connection connectivity node                                                       
    Battery  active                    bool                       False                 Is the load active?                                                                
    Battery  mttf                      float              h       False                 Mean time to failure                                                               
    Battery  mttr                      float              h       False                 Mean time to recovery                                                              
    Battery  capex                     float              e/MW    False                 Cost of investment. Used in expansion planning.                                    
    Battery  opex                      float              e/MWh   False                 Cost of operation. Used in expansion planning.                                     
    Battery  build_status              enum BuildStatus           False                 Branch build status. Used in expansion planning.                                   
    Battery  Cost                      float              e/MWh   False                 Cost of not served energy. Used in OPF.                                            
    Battery  control_bus               Bus                        False                 Control bus                                                                        
    Battery  control_cn                Connectivity Node          False                 Control connectivity node                                                          
    Battery  P                         float              MW      False                 Active power                                                                       
    Battery  Pmin                      float              MW      False                 Minimum active power. Used in OPF.                                                 
    Battery  Pmax                      float              MW      False                 Maximum active power. Used in OPF.                                                 
    Battery  is_controlled             bool                       False                 Is this generator voltage-controlled?                                              
    Battery  Pf                        float                      False                 Power factor (cos(fi)). This is used for non-controlled generators.                
    Battery  Vset                      float              p.u.    False                 Set voltage. This is used for controlled generators.                               
    Battery  Snom                      float              MVA     False                 Nomnial power.                                                                     
    Battery  Qmin                      float              MVAr    False                 Minimum reactive power.                                                            
    Battery  Qmax                      float              MVAr    False                 Maximum reactive power.                                                            
    Battery  use_reactive_power_curve  bool                       False                 Use the reactive power capability curve?                                           
    Battery  q_curve                   Generator Q curve  MVAr    False                 Capability curve data (double click on the generator to edit)                      
    Battery  R1                        float              p.u.    False                 Total positive sequence resistance.                                                
    Battery  X1                        float              p.u.    False                 Total positive sequence reactance.                                                 
    Battery  R0                        float              p.u.    False                 Total zero sequence resistance.                                                    
    Battery  X0                        float              p.u.    False                 Total zero sequence reactance.                                                     
    Battery  R2                        float              p.u.    False                 Total negative sequence resistance.                                                
    Battery  X2                        float              p.u.    False                 Total negative sequence reactance.                                                 
    Battery  Cost2                     float              e/MWh²  False                 Generation quadratic cost. Used in OPF.                                            
    Battery  Cost0                     float              e/h     False                 Generation constant cost. Used in OPF.                                             
    Battery  StartupCost               float              e/h     False                 Generation start-up cost. Used in OPF.                                             
    Battery  ShutdownCost              float              e/h     False                 Generation shut-down cost. Used in OPF.                                            
    Battery  MinTimeUp                 float              h       False                 Minimum time that the generator has to be on when started. Used in OPF.            
    Battery  MinTimeDown               float              h       False                 Minimum time that the generator has to be off when shut down. Used in OPF.         
    Battery  RampUp                    float              MW/h    False                 Maximum amount of generation increase per hour.                                    
    Battery  RampDown                  float              MW/h    False                 Maximum amount of generation decrease per hour.                                    
    Battery  enabled_dispatch          bool                       False                 Enabled for dispatch? Used in OPF.                                                 
    Battery  Enom                      float              MWh     False                 Nominal energy capacity.                                                           
    Battery  max_soc                   float              p.u.    False                 Minimum state of charge.                                                           
    Battery  min_soc                   float              p.u.    False                 Maximum state of charge.                                                           
    Battery  soc_0                     float              p.u.    False                 Initial state of charge.                                                           
    Battery  charge_efficiency         float              p.u.    False                 Charging efficiency.                                                               
    Battery  discharge_efficiency      float              p.u.    False                 Discharge efficiency.                                                              
    Battery  discharge_per_cycle       float              p.u.    False                                                                                                    
    =======  ========================  =================  ======  =========  =========  ==========================================================================  =======


Branch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ======  ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    class          name            class_type      unit   mandatory  max_chars                                                                                                                descriptions                                                                                                                comment
    ======  ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    Branch  idtag               str                       False                 Unique ID                                                                                                                                                                                                                                        
    Branch  name                str                       False                 Name of the branch.                                                                                                                                                                                                                              
    Branch  code                str                       False                 Secondary ID                                                                                                                                                                                                                                     
    Branch  bus_from            Bus                       False                 Name of the bus at the "from" side                                                                                                                                                                                                               
    Branch  bus_to              Bus                       False                 Name of the bus at the "to" side                                                                                                                                                                                                                 
    Branch  cn_from             Connectivity Node         False                 Name of the connectivity node at the "from" side                                                                                                                                                                                                 
    Branch  cn_to               Connectivity Node         False                 Name of the connectivity node at the "to" side                                                                                                                                                                                                   
    Branch  active              bool                      False                 Is active?                                                                                                                                                                                                                                       
    Branch  rate                float              MVA    False                 Thermal rating power                                                                                                                                                                                                                             
    Branch  contingency_factor  float              p.u.   False                 Rating multiplier for contingencies                                                                                                                                                                                                              
    Branch  monitor_loading     bool                      False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                                                                                                                                 
    Branch  mttf                float              h      False                 Mean time to failure                                                                                                                                                                                                                             
    Branch  mttr                float              h      False                 Mean time to repair                                                                                                                                                                                                                              
    Branch  Cost                float              e/MWh  False                 Cost of overloads. Used in OPF                                                                                                                                                                                                                   
    Branch  build_status        enum BuildStatus          False                 Branch build status. Used in expansion planning.                                                                                                                                                                                                 
    Branch  capex               float              e/MW   False                 Cost of investment. Used in expansion planning.                                                                                                                                                                                                  
    Branch  opex                float              e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                                                                                                                                   
    Branch  R                   float              p.u.   False                 Total positive sequence resistance.                                                                                                                                                                                                              
    Branch  X                   float              p.u.   False                 Total positive sequence reactance.                                                                                                                                                                                                               
    Branch  B                   float              p.u.   False                 Total positive sequence shunt susceptance.                                                                                                                                                                                                       
    Branch  G                   float              p.u.   False                 Total positive sequence shunt conductance.                                                                                                                                                                                                       
    Branch  tolerance           float              %      False                 Tolerance expected for the impedance values % is expected for transformers0% for lines.                                                                                                                                                          
    Branch  length              float              km     False                 Length of the line (not used for calculation)                                                                                                                                                                                                    
    Branch  temp_base           float              ºC     False                 Base temperature at which R was measured.                                                                                                                                                                                                        
    Branch  temp_oper           float              ºC     False                 Operation temperature to modify R.                                                                                                                                                                                                               
    Branch  alpha               float              1/ºC   False                 Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330         
    Branch  tap_module          float                     False                 Tap changer module, it a value close to 1.0                                                                                                                                                                                                      
    Branch  angle               float              rad    False                 Angle shift of the tap changer.                                                                                                                                                                                                                  
    Branch  template            enum BranchType           False                                                                                                                                                                                                                                                                  
    Branch  bus_to_regulated    bool                      False                 Is the regulation at the bus to?                                                                                                                                                                                                                 
    Branch  vset                float              p.u.   False                 set control voltage.                                                                                                                                                                                                                             
    Branch  r_fault             float              p.u.   False                 Fault resistance.                                                                                                                                                                                                                                
    Branch  x_fault             float              p.u.   False                 Fault reactance.                                                                                                                                                                                                                                 
    Branch  fault_pos           float              p.u.   False                 proportion of the fault location measured from the "from" bus.                                                                                                                                                                                   
    Branch  branch_type         enum BranchType    p.u.   False                 Fault resistance.                                                                                                                                                                                                                                
    ======  ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======


Bus
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ===========  ==========  ======  =========  =========  ===============================================================================================  =======
    class     name      class_type   unit   mandatory  max_chars                                           descriptions                                            comment
    =====  ===========  ==========  ======  =========  =========  ===============================================================================================  =======
    Bus    idtag        str                 False                 Unique ID                                                                                               
    Bus    name         str                 False                 Name of the branch.                                                                                     
    Bus    code         str                 False                 Secondary ID                                                                                            
    Bus    active       bool                False                 Is the bus active? used to disable the bus.                                                             
    Bus    is_slack     bool                False                 Force the bus to be of slack type.                                                                      
    Bus    is_dc        bool                False                 Is this bus of DC type?.                                                                                
    Bus    is_internal  bool                False                 Is this bus part of a composite transformer, such as  a 3-winding transformer or a fluid node?.         
    Bus    Vnom         float       kV      False                 Nominal line voltage of the bus.                                                                        
    Bus    Vm0          float       p.u.    False                 Voltage module guess.                                                                                   
    Bus    Va0          float       rad.    False                 Voltage angle guess.                                                                                    
    Bus    Vmin         float       p.u.    False                 Lower range of allowed voltage module.                                                                  
    Bus    Vmax         float       p.u.    False                 Higher range of allowed voltage module.                                                                 
    Bus    Vm_cost      float       e/unit  False                 Cost of over and under voltages                                                                         
    Bus    angle_min    float       rad.    False                 Lower range of allowed voltage angle.                                                                   
    Bus    angle_max    float       rad.    False                 Higher range of allowed voltage angle.                                                                  
    Bus    angle_cost   float       e/unit  False                 Cost of over and under angles                                                                           
    Bus    r_fault      float       p.u.    False                 Resistance of the fault.This is used for short circuit studies.                                         
    Bus    x_fault      float       p.u.    False                 Reactance of the fault.This is used for short circuit studies.                                          
    Bus    x            float       px      False                 x position in pixels.                                                                                   
    Bus    y            float       px      False                 y position in pixels.                                                                                   
    Bus    h            float       px      False                 height of the bus in pixels.                                                                            
    Bus    w            float       px      False                 Width of the bus in pixels.                                                                             
    Bus    country      Country             False                 Country of the bus                                                                                      
    Bus    area         Area                False                 Area of the bus                                                                                         
    Bus    zone         Zone                False                 Zone of the bus                                                                                         
    Bus    substation   Substation          False                 Substation of the bus.                                                                                  
    Bus    longitude    float       deg     False                 longitude of the bus.                                                                                   
    Bus    latitude     float       deg     False                 latitude of the bus.                                                                                    
    =====  ===========  ==========  ======  =========  =========  ===============================================================================================  =======


BusBar
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ======  ==========  =================  ====  =========  =========  =====================================  =======
    class      name        class_type      unit  mandatory  max_chars              descriptions               comment
    ======  ==========  =================  ====  =========  =========  =====================================  =======
    BusBar  idtag       str                      False                 Unique ID                                     
    BusBar  name        str                      False                 Name of the branch.                           
    BusBar  code        str                      False                 Secondary ID                                  
    BusBar  substation  Substation               False                 Substation of this bus bar (optional)         
    BusBar  cn          Connectivity Node        False                 Internal connectvity node                     
    ======  ==========  =================  ====  =========  =========  =====================================  =======


Connectivity Node
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =================  ===========  ==========  ====  =========  =========  =====================================================  =======
          class           name      class_type  unit  mandatory  max_chars                      descriptions                       comment
    =================  ===========  ==========  ====  =========  =========  =====================================================  =======
    Connectivity Node  idtag        str               False                 Unique ID                                                     
    Connectivity Node  name         str               False                 Name of the branch.                                           
    Connectivity Node  code         str               False                 Secondary ID                                                  
    Connectivity Node  dc           bool              False                 is this a DC connectivity node?                               
    Connectivity Node  default_bus  Bus               False                 Default bus to use for topology processing (optional)         
    =================  ===========  ==========  ====  =========  =========  =====================================================  =======


Contingency
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ===========  ============  =================  ====  =========  =========  =================================================  =======
       class         name         class_type      unit  mandatory  max_chars                    descriptions                     comment
    ===========  ============  =================  ====  =========  =========  =================================================  =======
    Contingency  idtag         str                      False                 Unique ID                                                 
    Contingency  name          str                      False                 Name of the branch.                                       
    Contingency  code          str                      False                 Secondary ID                                              
    Contingency  device_idtag  str                      False                 Unique ID                                                 
    Contingency  prop          str                      False                 Name of the object property to change (active, %)         
    Contingency  value         float                    False                 Property value                                            
    Contingency  group         Contingency Group        False                 Contingency group                                         
    ===========  ============  =================  ====  =========  =========  =================================================  =======


Contingency Group
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =================  ========  ==========  ====  =========  =========  ==========================================  =======
          class          name    class_type  unit  mandatory  max_chars                 descriptions                 comment
    =================  ========  ==========  ====  =========  =========  ==========================================  =======
    Contingency Group  idtag     str               False                 Unique ID                                          
    Contingency Group  name      str               False                 Name of the branch.                                
    Contingency Group  code      str               False                 Secondary ID                                       
    Contingency Group  category  str               False                 Some tag to category the contingency group         
    =================  ========  ==========  ====  =========  =========  ==========================================  =======


Country
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =======  =========  ==========  ====  =========  =========  =====================  =======
     class     name     class_type  unit  mandatory  max_chars      descriptions       comment
    =======  =========  ==========  ====  =========  =========  =====================  =======
    Country  idtag      str               False                 Unique ID                     
    Country  name       str               False                 Name of the branch.           
    Country  code       str               False                 Secondary ID                  
    Country  longitude  float       deg   False                 longitude of the bus.         
    Country  latitude   float       deg   False                 latitude of the bus.          
    =======  =========  ==========  ====  =========  =========  =====================  =======


DC line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =======  ==================  =================  =====  =========  =========  ===========================================================================================================================  =======
     class          name            class_type      unit   mandatory  max_chars                                                         descriptions                                                          comment
    =======  ==================  =================  =====  =========  =========  ===========================================================================================================================  =======
    DC line  idtag               str                       False                 Unique ID                                                                                                                           
    DC line  name                str                       False                 Name of the branch.                                                                                                                 
    DC line  code                str                       False                 Secondary ID                                                                                                                        
    DC line  bus_from            Bus                       False                 Name of the bus at the "from" side                                                                                                  
    DC line  bus_to              Bus                       False                 Name of the bus at the "to" side                                                                                                    
    DC line  cn_from             Connectivity Node         False                 Name of the connectivity node at the "from" side                                                                                    
    DC line  cn_to               Connectivity Node         False                 Name of the connectivity node at the "to" side                                                                                      
    DC line  active              bool                      False                 Is active?                                                                                                                          
    DC line  rate                float              MVA    False                 Thermal rating power                                                                                                                
    DC line  contingency_factor  float              p.u.   False                 Rating multiplier for contingencies                                                                                                 
    DC line  monitor_loading     bool                      False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                    
    DC line  mttf                float              h      False                 Mean time to failure                                                                                                                
    DC line  mttr                float              h      False                 Mean time to repair                                                                                                                 
    DC line  Cost                float              e/MWh  False                 Cost of overloads. Used in OPF                                                                                                      
    DC line  build_status        enum BuildStatus          False                 Branch build status. Used in expansion planning.                                                                                    
    DC line  capex               float              e/MW   False                 Cost of investment. Used in expansion planning.                                                                                     
    DC line  opex                float              e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                      
    DC line  R                   float              p.u.   False                 Total positive sequence resistance.                                                                                                 
    DC line  length              float              km     False                 Length of the line (not used for calculation)                                                                                       
    DC line  r_fault             float              p.u.   False                 Resistance of the mid-line fault.Used in short circuit studies.                                                                     
    DC line  fault_pos           float              p.u.   False                 Per-unit positioning of the fault:0 would be at the "from" side,1 would be at the "to" side,therefore 0.5 is at the middle.         
    DC line  template            Sequence line             False                                                                                                                                                     
    =======  ==================  =================  =====  =========  =========  ===========================================================================================================================  =======


Emission
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ========  =====  ==========  ====  =========  =========  ===========================  =======
     class    name   class_type  unit  mandatory  max_chars         descriptions          comment
    ========  =====  ==========  ====  =========  =========  ===========================  =======
    Emission  idtag  str               False                 Unique ID                           
    Emission  name   str               False                 Name of the branch.                 
    Emission  code   str               False                 Secondary ID                        
    Emission  cost   float       e/t   False                 Cost of emissions (e / ton)         
    Emission  color  str               False                 Color to paint                      
    ========  =====  ==========  ====  =========  =========  ===========================  =======


Fluid P2X
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  =============  ================  ======  =========  =========  ================================================  =======
      class        name          class_type      unit   mandatory  max_chars                    descriptions                    comment
    =========  =============  ================  ======  =========  =========  ================================================  =======
    Fluid P2X  idtag          str                       False                 Unique ID                                                
    Fluid P2X  name           str                       False                 Name of the branch.                                      
    Fluid P2X  code           str                       False                 Secondary ID                                             
    Fluid P2X  efficiency     float             MWh/m3  False                 Power plant energy production per fluid unit             
    Fluid P2X  max_flow_rate  float             m3/s    False                 maximum fluid flow                                       
    Fluid P2X  plant          Fluid node                False                 Connection reservoir/node                                
    Fluid P2X  generator      Generator                 False                 Electrical machine                                       
    Fluid P2X  build_status   enum BuildStatus          False                 Branch build status. Used in expansion planning.         
    =========  =============  ================  ======  =========  =========  ================================================  =======


Fluid Pump
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==========  =============  ================  ======  =========  =========  ================================================  =======
      class         name          class_type      unit   mandatory  max_chars                    descriptions                    comment
    ==========  =============  ================  ======  =========  =========  ================================================  =======
    Fluid Pump  idtag          str                       False                 Unique ID                                                
    Fluid Pump  name           str                       False                 Name of the branch.                                      
    Fluid Pump  code           str                       False                 Secondary ID                                             
    Fluid Pump  efficiency     float             MWh/m3  False                 Power plant energy production per fluid unit             
    Fluid Pump  max_flow_rate  float             m3/s    False                 maximum fluid flow                                       
    Fluid Pump  plant          Fluid node                False                 Connection reservoir/node                                
    Fluid Pump  generator      Generator                 False                 Electrical machine                                       
    Fluid Pump  build_status   enum BuildStatus          False                 Branch build status. Used in expansion planning.         
    ==========  =============  ================  ======  =========  =========  ================================================  =======


Fluid Turbine
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  =============  ================  ======  =========  =========  ================================================  =======
        class          name          class_type      unit   mandatory  max_chars                    descriptions                    comment
    =============  =============  ================  ======  =========  =========  ================================================  =======
    Fluid Turbine  idtag          str                       False                 Unique ID                                                
    Fluid Turbine  name           str                       False                 Name of the branch.                                      
    Fluid Turbine  code           str                       False                 Secondary ID                                             
    Fluid Turbine  efficiency     float             MWh/m3  False                 Power plant energy production per fluid unit             
    Fluid Turbine  max_flow_rate  float             m3/s    False                 maximum fluid flow                                       
    Fluid Turbine  plant          Fluid node                False                 Connection reservoir/node                                
    Fluid Turbine  generator      Generator                 False                 Electrical machine                                       
    Fluid Turbine  build_status   enum BuildStatus          False                 Branch build status. Used in expansion planning.         
    =============  =============  ================  ======  =========  =========  ================================================  =======


Fluid node
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==========  =============  ================  ========  =========  =========  ================================================  =======
      class         name          class_type       unit    mandatory  max_chars                    descriptions                    comment
    ==========  =============  ================  ========  =========  =========  ================================================  =======
    Fluid node  idtag          str                         False                 Unique ID                                                
    Fluid node  name           str                         False                 Name of the branch.                                      
    Fluid node  code           str                         False                 Secondary ID                                             
    Fluid node  min_level      float             hm3       False                 Minimum amount of fluid at the node/reservoir            
    Fluid node  max_level      float             hm3       False                 Maximum amount of fluid at the node/reservoir            
    Fluid node  initial_level  float             hm3       False                 Initial level of the node/reservoir                      
    Fluid node  bus            Bus                         False                 Electrical bus.                                          
    Fluid node  build_status   enum BuildStatus            False                 Branch build status. Used in expansion planning.         
    Fluid node  spillage_cost  float             e/(m3/s)  False                 Cost of nodal spillage                                   
    Fluid node  inflow         float             m3/s      False                 Flow of fluid coming from the rain                       
    ==========  =============  ================  ========  =========  =========  ================================================  =======


Fluid path
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==========  ========  ==========  ====  =========  =========  ===================  =======
      class       name    class_type  unit  mandatory  max_chars     descriptions      comment
    ==========  ========  ==========  ====  =========  =========  ===================  =======
    Fluid path  idtag     str               False                 Unique ID                   
    Fluid path  name      str               False                 Name of the branch.         
    Fluid path  code      str               False                 Secondary ID                
    Fluid path  source    Fluid node        False                 Source node                 
    Fluid path  target    Fluid node        False                 Target node                 
    Fluid path  min_flow  float       m3/s  False                 Minimum flow                
    Fluid path  max_flow  float       m3/s  False                 Maximum flow                
    ==========  ========  ==========  ====  =========  =========  ===================  =======


Fuel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  =====  ==========  ====  =========  =========  ======================  =======
    class  name   class_type  unit  mandatory  max_chars       descriptions       comment
    =====  =====  ==========  ====  =========  =========  ======================  =======
    Fuel   idtag  str               False                 Unique ID                      
    Fuel   name   str               False                 Name of the branch.            
    Fuel   code   str               False                 Secondary ID                   
    Fuel   cost   float       e/t   False                 Cost of fuel (e / ton)         
    Fuel   color  str               False                 Color to paint                 
    =====  =====  ==========  ====  =========  =========  ======================  =======


Generator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  ========================  =================  ======  =========  =========  ==========================================================================  =======
      class              name               class_type       unit   mandatory  max_chars                                 descriptions                                 comment
    =========  ========================  =================  ======  =========  =========  ==========================================================================  =======
    Generator  idtag                     str                        False                 Unique ID                                                                          
    Generator  name                      str                        False                 Name of the branch.                                                                
    Generator  code                      str                        False                 Secondary ID                                                                       
    Generator  bus                       Bus                        False                 Connection bus                                                                     
    Generator  cn                        Connectivity Node          False                 Connection connectivity node                                                       
    Generator  active                    bool                       False                 Is the load active?                                                                
    Generator  mttf                      float              h       False                 Mean time to failure                                                               
    Generator  mttr                      float              h       False                 Mean time to recovery                                                              
    Generator  capex                     float              e/MW    False                 Cost of investment. Used in expansion planning.                                    
    Generator  opex                      float              e/MWh   False                 Cost of operation. Used in expansion planning.                                     
    Generator  build_status              enum BuildStatus           False                 Branch build status. Used in expansion planning.                                   
    Generator  Cost                      float              e/MWh   False                 Cost of not served energy. Used in OPF.                                            
    Generator  control_bus               Bus                        False                 Control bus                                                                        
    Generator  control_cn                Connectivity Node          False                 Control connectivity node                                                          
    Generator  P                         float              MW      False                 Active power                                                                       
    Generator  Pmin                      float              MW      False                 Minimum active power. Used in OPF.                                                 
    Generator  Pmax                      float              MW      False                 Maximum active power. Used in OPF.                                                 
    Generator  is_controlled             bool                       False                 Is this generator voltage-controlled?                                              
    Generator  Pf                        float                      False                 Power factor (cos(fi)). This is used for non-controlled generators.                
    Generator  Vset                      float              p.u.    False                 Set voltage. This is used for controlled generators.                               
    Generator  Snom                      float              MVA     False                 Nomnial power.                                                                     
    Generator  Qmin                      float              MVAr    False                 Minimum reactive power.                                                            
    Generator  Qmax                      float              MVAr    False                 Maximum reactive power.                                                            
    Generator  use_reactive_power_curve  bool                       False                 Use the reactive power capability curve?                                           
    Generator  q_curve                   Generator Q curve  MVAr    False                 Capability curve data (double click on the generator to edit)                      
    Generator  R1                        float              p.u.    False                 Total positive sequence resistance.                                                
    Generator  X1                        float              p.u.    False                 Total positive sequence reactance.                                                 
    Generator  R0                        float              p.u.    False                 Total zero sequence resistance.                                                    
    Generator  X0                        float              p.u.    False                 Total zero sequence reactance.                                                     
    Generator  R2                        float              p.u.    False                 Total negative sequence resistance.                                                
    Generator  X2                        float              p.u.    False                 Total negative sequence reactance.                                                 
    Generator  Cost2                     float              e/MWh²  False                 Generation quadratic cost. Used in OPF.                                            
    Generator  Cost0                     float              e/h     False                 Generation constant cost. Used in OPF.                                             
    Generator  StartupCost               float              e/h     False                 Generation start-up cost. Used in OPF.                                             
    Generator  ShutdownCost              float              e/h     False                 Generation shut-down cost. Used in OPF.                                            
    Generator  MinTimeUp                 float              h       False                 Minimum time that the generator has to be on when started. Used in OPF.            
    Generator  MinTimeDown               float              h       False                 Minimum time that the generator has to be off when shut down. Used in OPF.         
    Generator  RampUp                    float              MW/h    False                 Maximum amount of generation increase per hour.                                    
    Generator  RampDown                  float              MW/h    False                 Maximum amount of generation decrease per hour.                                    
    Generator  enabled_dispatch          bool                       False                 Enabled for dispatch? Used in OPF.                                                 
    =========  ========================  =================  ======  =========  =========  ==========================================================================  =======


Generator Emission
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  =========  ==========  =====  =========  =========  ==================================================  =======
          class           name     class_type  unit   mandatory  max_chars                     descriptions                     comment
    ==================  =========  ==========  =====  =========  =========  ==================================================  =======
    Generator Emission  idtag      str                False                 Unique ID                                                  
    Generator Emission  name       str                False                 Name of the branch.                                        
    Generator Emission  code       str                False                 Secondary ID                                               
    Generator Emission  generator  Generator          False                 Generator                                                  
    Generator Emission  emission   Emission           False                 Emission                                                   
    Generator Emission  rate       float       t/MWh  False                 Emissions rate of the gas in the generator (t/MWh)         
    ==================  =========  ==========  =====  =========  =========  ==================================================  =======


Generator Fuel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==============  =========  ==========  =====  =========  =========  ======================================  =======
        class         name     class_type  unit   mandatory  max_chars               descriptions               comment
    ==============  =========  ==========  =====  =========  =========  ======================================  =======
    Generator Fuel  idtag      str                False                 Unique ID                                      
    Generator Fuel  name       str                False                 Name of the branch.                            
    Generator Fuel  code       str                False                 Secondary ID                                   
    Generator Fuel  generator  Generator          False                 Generator                                      
    Generator Fuel  fuel       Fuel               False                 Fuel                                           
    Generator Fuel  rate       float       t/MWh  False                 Fuel consumption rate in the generator         
    ==============  =========  ==========  =====  =========  =========  ======================================  =======


Generator Technology
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ====================  ==========  ==========  ====  =========  =========  ===================================================  =======
           class             name     class_type  unit  mandatory  max_chars                     descriptions                      comment
    ====================  ==========  ==========  ====  =========  =========  ===================================================  =======
    Generator Technology  idtag       str               False                 Unique ID                                                   
    Generator Technology  name        str               False                 Name of the branch.                                         
    Generator Technology  code        str               False                 Secondary ID                                                
    Generator Technology  generator   Generator         False                 Generator object                                            
    Generator Technology  technology  Technology        False                 Technology object                                           
    Generator Technology  proportion  float       p.u.  False                 Share of the generator associated to the technology         
    ====================  ==========  ==========  ====  =========  =========  ===================================================  =======


HVDC Line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  ==================  ====================  ======  =========  =========  ===========================================================================================  =======
      class           name              class_type        unit   mandatory  max_chars                                         descriptions                                          comment
    =========  ==================  ====================  ======  =========  =========  ===========================================================================================  =======
    HVDC Line  idtag               str                           False                 Unique ID                                                                                           
    HVDC Line  name                str                           False                 Name of the branch.                                                                                 
    HVDC Line  code                str                           False                 Secondary ID                                                                                        
    HVDC Line  bus_from            Bus                           False                 Name of the bus at the "from" side                                                                  
    HVDC Line  bus_to              Bus                           False                 Name of the bus at the "to" side                                                                    
    HVDC Line  cn_from             Connectivity Node             False                 Name of the connectivity node at the "from" side                                                    
    HVDC Line  cn_to               Connectivity Node             False                 Name of the connectivity node at the "to" side                                                      
    HVDC Line  active              bool                          False                 Is active?                                                                                          
    HVDC Line  rate                float                 MVA     False                 Thermal rating power                                                                                
    HVDC Line  contingency_factor  float                 p.u.    False                 Rating multiplier for contingencies                                                                 
    HVDC Line  monitor_loading     bool                          False                 Monitor this device loading for OPF, NTC or contingency studies.                                    
    HVDC Line  mttf                float                 h       False                 Mean time to failure                                                                                
    HVDC Line  mttr                float                 h       False                 Mean time to repair                                                                                 
    HVDC Line  Cost                float                 e/MWh   False                 Cost of overloads. Used in OPF                                                                      
    HVDC Line  build_status        enum BuildStatus              False                 Branch build status. Used in expansion planning.                                                    
    HVDC Line  capex               float                 e/MW    False                 Cost of investment. Used in expansion planning.                                                     
    HVDC Line  opex                float                 e/MWh   False                 Cost of operation. Used in expansion planning.                                                      
    HVDC Line  dispatchable        bool                          False                 Is the line power optimizable?                                                                      
    HVDC Line  control_mode        enum HvdcControlType  -       False                 Control type.                                                                                       
    HVDC Line  Pset                float                 MW      False                 Set power flow.                                                                                     
    HVDC Line  r                   float                 Ohm     False                 line resistance.                                                                                    
    HVDC Line  angle_droop         float                 MW/deg  False                 Power/angle rate control                                                                            
    HVDC Line  n_lines             int                           False                 Number of parallel lines between the converter stations. The rating will be equally divided         
    HVDC Line  Vset_f              float                 p.u.    False                 Set voltage at the from side                                                                        
    HVDC Line  Vset_t              float                 p.u.    False                 Set voltage at the to side                                                                          
    HVDC Line  min_firing_angle_f  float                 rad     False                 minimum firing angle at the "from" side.                                                            
    HVDC Line  max_firing_angle_f  float                 rad     False                 maximum firing angle at the "from" side.                                                            
    HVDC Line  min_firing_angle_t  float                 rad     False                 minimum firing angle at the "to" side.                                                              
    HVDC Line  max_firing_angle_t  float                 rad     False                 maximum firing angle at the "to" side.                                                              
    HVDC Line  length              float                 km      False                 Length of the branch (not used for calculation)                                                     
    =========  ==================  ====================  ======  =========  =========  ===========================================================================================  =======


Investment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==========  ============  =================  ====  =========  =========  ======================================================================  =======
      class         name         class_type      unit  mandatory  max_chars                               descriptions                               comment
    ==========  ============  =================  ====  =========  =========  ======================================================================  =======
    Investment  idtag         str                      False                 Unique ID                                                                      
    Investment  name          str                      False                 Name of the branch.                                                            
    Investment  code          str                      False                 Secondary ID                                                                   
    Investment  device_idtag  str                      False                 Unique ID                                                                      
    Investment  CAPEX         float              Me    False                 Capital expenditures. This is the initial investment.                          
    Investment  OPEX          float              Me    False                 Operation expenditures. Maintenance costs among other recurrent costs.         
    Investment  group         Investments Group        False                 Investment group                                                               
    Investment  comment       str                      False                 Comments                                                                       
    ==========  ============  =================  ====  =========  =========  ======================================================================  =======


Investments Group
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =================  ========  ==========  ====  =========  =========  ==========================================  =======
          class          name    class_type  unit  mandatory  max_chars                 descriptions                 comment
    =================  ========  ==========  ====  =========  =========  ==========================================  =======
    Investments Group  idtag     str               False                 Unique ID                                          
    Investments Group  name      str               False                 Name of the branch.                                
    Investments Group  code      str               False                 Secondary ID                                       
    Investments Group  category  str               False                 Some tag to category the contingency group         
    Investments Group  comment   str               False                 Some comment                                       
    =================  ========  ==========  ====  =========  =========  ==========================================  =======


Line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    class         name            class_type      unit   mandatory  max_chars                                                                                                                descriptions                                                                                                                comment
    =====  ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    Line   idtag               str                       False                 Unique ID                                                                                                                                                                                                                                        
    Line   name                str                       False                 Name of the branch.                                                                                                                                                                                                                              
    Line   code                str                       False                 Secondary ID                                                                                                                                                                                                                                     
    Line   bus_from            Bus                       False                 Name of the bus at the "from" side                                                                                                                                                                                                               
    Line   bus_to              Bus                       False                 Name of the bus at the "to" side                                                                                                                                                                                                                 
    Line   cn_from             Connectivity Node         False                 Name of the connectivity node at the "from" side                                                                                                                                                                                                 
    Line   cn_to               Connectivity Node         False                 Name of the connectivity node at the "to" side                                                                                                                                                                                                   
    Line   active              bool                      False                 Is active?                                                                                                                                                                                                                                       
    Line   rate                float              MVA    False                 Thermal rating power                                                                                                                                                                                                                             
    Line   contingency_factor  float              p.u.   False                 Rating multiplier for contingencies                                                                                                                                                                                                              
    Line   monitor_loading     bool                      False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                                                                                                                                 
    Line   mttf                float              h      False                 Mean time to failure                                                                                                                                                                                                                             
    Line   mttr                float              h      False                 Mean time to repair                                                                                                                                                                                                                              
    Line   Cost                float              e/MWh  False                 Cost of overloads. Used in OPF                                                                                                                                                                                                                   
    Line   build_status        enum BuildStatus          False                 Branch build status. Used in expansion planning.                                                                                                                                                                                                 
    Line   capex               float              e/MW   False                 Cost of investment. Used in expansion planning.                                                                                                                                                                                                  
    Line   opex                float              e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                                                                                                                                   
    Line   R                   float              p.u.   False                 Total positive sequence resistance.                                                                                                                                                                                                              
    Line   X                   float              p.u.   False                 Total positive sequence reactance.                                                                                                                                                                                                               
    Line   B                   float              p.u.   False                 Total positive sequence shunt susceptance.                                                                                                                                                                                                       
    Line   R0                  float              p.u.   False                 Total zero sequence resistance.                                                                                                                                                                                                                  
    Line   X0                  float              p.u.   False                 Total zero sequence reactance.                                                                                                                                                                                                                   
    Line   B0                  float              p.u.   False                 Total zero sequence shunt susceptance.                                                                                                                                                                                                           
    Line   R2                  float              p.u.   False                 Total negative sequence resistance.                                                                                                                                                                                                              
    Line   X2                  float              p.u.   False                 Total negative sequence reactance.                                                                                                                                                                                                               
    Line   B2                  float              p.u.   False                 Total negative sequence shunt susceptance.                                                                                                                                                                                                       
    Line   tolerance           float              %      False                 Tolerance expected for the impedance values % is expected for transformers0% for lines.                                                                                                                                                          
    Line   length              float              km     False                 Length of the line (not used for calculation)                                                                                                                                                                                                    
    Line   temp_base           float              ºC     False                 Base temperature at which R was measured.                                                                                                                                                                                                        
    Line   temp_oper           float              ºC     False                 Operation temperature to modify R.                                                                                                                                                                                                               
    Line   alpha               float              1/ºC   False                 Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330         
    Line   r_fault             float              p.u.   False                 Resistance of the mid-line fault.Used in short circuit studies.                                                                                                                                                                                  
    Line   x_fault             float              p.u.   False                 Reactance of the mid-line fault.Used in short circuit studies.                                                                                                                                                                                   
    Line   fault_pos           float              p.u.   False                 Per-unit positioning of the fault:0 would be at the "from" side,1 would be at the "to" side,therefore 0.5 is at the middle.                                                                                                                      
    Line   template            Sequence line             False                                                                                                                                                                                                                                                                  
    =====  ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======


Load
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ============  =================  =====  =========  =========  =======================================================  =======
    class      name         class_type      unit   mandatory  max_chars                       descriptions                        comment
    =====  ============  =================  =====  =========  =========  =======================================================  =======
    Load   idtag         str                       False                 Unique ID                                                       
    Load   name          str                       False                 Name of the branch.                                             
    Load   code          str                       False                 Secondary ID                                                    
    Load   bus           Bus                       False                 Connection bus                                                  
    Load   cn            Connectivity Node         False                 Connection connectivity node                                    
    Load   active        bool                      False                 Is the load active?                                             
    Load   mttf          float              h      False                 Mean time to failure                                            
    Load   mttr          float              h      False                 Mean time to recovery                                           
    Load   capex         float              e/MW   False                 Cost of investment. Used in expansion planning.                 
    Load   opex          float              e/MWh  False                 Cost of operation. Used in expansion planning.                  
    Load   build_status  enum BuildStatus          False                 Branch build status. Used in expansion planning.                
    Load   Cost          float              e/MWh  False                 Cost of not served energy. Used in OPF.                         
    Load   P             float              MW     False                 Active power                                                    
    Load   Q             float              MVAr   False                 Reactive power                                                  
    Load   Ir            float              MW     False                 Active power of the current component at V=1.0 p.u.             
    Load   Ii            float              MVAr   False                 Reactive power of the current component at V=1.0 p.u.           
    Load   G             float              MW     False                 Active power of the impedance component at V=1.0 p.u.           
    Load   B             float              MVAr   False                 Reactive power of the impedance component at V=1.0 p.u.         
    =====  ============  =================  =====  =========  =========  =======================================================  =======


Sequence line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  =====  ==========  ======  =========  =========  ==========================================  =======
        class      name   class_type   unit   mandatory  max_chars                 descriptions                 comment
    =============  =====  ==========  ======  =========  =========  ==========================================  =======
    Sequence line  idtag  str                 False                 Unique ID                                          
    Sequence line  name   str                 False                 Name of the branch.                                
    Sequence line  code   str                 False                 Secondary ID                                       
    Sequence line  Imax   float       kA      False                 Current rating of the line                         
    Sequence line  Vnom   float       kV      False                 Voltage rating of the line                         
    Sequence line  R      float       Ohm/km  False                 Positive-sequence resistance per km                
    Sequence line  X      float       Ohm/km  False                 Positive-sequence reactance per km                 
    Sequence line  B      float       uS/km   False                 Positive-sequence shunt susceptance per km         
    Sequence line  R0     float       Ohm/km  False                 Zero-sequence resistance per km                    
    Sequence line  X0     float       Ohm/km  False                 Zero-sequence reactance per km                     
    Sequence line  B0     float       uS/km   False                 Zero-sequence shunt susceptance per km             
    =============  =====  ==========  ======  =========  =========  ==========================================  =======


Shunt
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  =============  =================  =====  =========  =========  =====================================================================  =======
    class      name          class_type      unit   mandatory  max_chars                              descriptions                               comment
    =====  =============  =================  =====  =========  =========  =====================================================================  =======
    Shunt  idtag          str                       False                 Unique ID                                                                     
    Shunt  name           str                       False                 Name of the branch.                                                           
    Shunt  code           str                       False                 Secondary ID                                                                  
    Shunt  bus            Bus                       False                 Connection bus                                                                
    Shunt  cn             Connectivity Node         False                 Connection connectivity node                                                  
    Shunt  active         bool                      False                 Is the load active?                                                           
    Shunt  mttf           float              h      False                 Mean time to failure                                                          
    Shunt  mttr           float              h      False                 Mean time to recovery                                                         
    Shunt  capex          float              e/MW   False                 Cost of investment. Used in expansion planning.                               
    Shunt  opex           float              e/MWh  False                 Cost of operation. Used in expansion planning.                                
    Shunt  build_status   enum BuildStatus          False                 Branch build status. Used in expansion planning.                              
    Shunt  Cost           float              e/MWh  False                 Cost of not served energy. Used in OPF.                                       
    Shunt  G              float              MW     False                 Active power                                                                  
    Shunt  B              float              MVAr   False                 Reactive power                                                                
    Shunt  G0             float              MW     False                 Zero sequence active power of the impedance component at V=1.0 p.u.           
    Shunt  B0             float              MVAr   False                 Zero sequence reactive power of the impedance component at V=1.0 p.u.         
    Shunt  is_controlled  bool                      False                 Is the shunt controllable?                                                    
    Shunt  Bmin           float              MVAr   False                 Reactive power min control value at V=1.0 p.u.                                
    Shunt  Bmax           float              MVAr   False                 Reactive power max control value at V=1.0 p.u.                                
    Shunt  Vset           float              p.u.   False                 Set voltage. This is used for controlled shunts.                              
    =====  =============  =================  =====  =========  =========  =====================================================================  =======


Static Generator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ================  ============  =================  =====  =========  =========  ================================================  =======
         class            name         class_type      unit   mandatory  max_chars                    descriptions                    comment
    ================  ============  =================  =====  =========  =========  ================================================  =======
    Static Generator  idtag         str                       False                 Unique ID                                                
    Static Generator  name          str                       False                 Name of the branch.                                      
    Static Generator  code          str                       False                 Secondary ID                                             
    Static Generator  bus           Bus                       False                 Connection bus                                           
    Static Generator  cn            Connectivity Node         False                 Connection connectivity node                             
    Static Generator  active        bool                      False                 Is the load active?                                      
    Static Generator  mttf          float              h      False                 Mean time to failure                                     
    Static Generator  mttr          float              h      False                 Mean time to recovery                                    
    Static Generator  capex         float              e/MW   False                 Cost of investment. Used in expansion planning.          
    Static Generator  opex          float              e/MWh  False                 Cost of operation. Used in expansion planning.           
    Static Generator  build_status  enum BuildStatus          False                 Branch build status. Used in expansion planning.         
    Static Generator  Cost          float              e/MWh  False                 Cost of not served energy. Used in OPF.                  
    Static Generator  P             float              MW     False                 Active power                                             
    Static Generator  Q             float              MVAr   False                 Reactive power                                           
    ================  ============  =================  =====  =========  =========  ================================================  =======


Substation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==========  =========  ==========  ====  =========  =========  =====================  =======
      class       name     class_type  unit  mandatory  max_chars      descriptions       comment
    ==========  =========  ==========  ====  =========  =========  =====================  =======
    Substation  idtag      str               False                 Unique ID                     
    Substation  name       str               False                 Name of the branch.           
    Substation  code       str               False                 Secondary ID                  
    Substation  longitude  float       deg   False                 longitude of the bus.         
    Substation  latitude   float       deg   False                 latitude of the bus.          
    ==========  =========  ==========  ====  =========  =========  =====================  =======


Technology
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==========  =====  ==========  ====  =========  =========  ========================  =======
      class     name   class_type  unit  mandatory  max_chars        descriptions        comment
    ==========  =====  ==========  ====  =========  =========  ========================  =======
    Technology  idtag  str               False                 Unique ID                        
    Technology  name   str               False                 Name of the branch.              
    Technology  code   str               False                 Secondary ID                     
    Technology  name2  str               False                 Name 2 of the technology         
    Technology  name3  str               False                 Name 3 of the technology         
    Technology  name4  str               False                 Name 4 of the technology         
    Technology  color  str               False                 Color to paint                   
    ==========  =====  ==========  ====  =========  =========  ========================  =======


Tower
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  =================  ==========  ======  =========  =========  ===================================  =======
    class        name         class_type   unit   mandatory  max_chars             descriptions              comment
    =====  =================  ==========  ======  =========  =========  ===================================  =======
    Tower  idtag              str                 False                 Unique ID                                   
    Tower  name               str                 False                 Name of the branch.                         
    Tower  code               str                 False                 Secondary ID                                
    Tower  earth_resistivity  float       Ohm/m3  False                 Earth resistivity                           
    Tower  frequency          float       Hz      False                 Frequency                                   
    Tower  R1                 float       Ohm/km  False                 Positive sequence resistance                
    Tower  X1                 float       Ohm/km  False                 Positive sequence reactance                 
    Tower  Bsh1               float       uS/km   False                 Positive sequence shunt susceptance         
    Tower  R0                 float       Ohm/km  False                 Zero-sequence resistance                    
    Tower  X0                 float       Ohm/km  False                 Zero sequence reactance                     
    Tower  Bsh0               float       uS/km   False                 Zero sequence shunt susceptance             
    Tower  Imax               float       kA      False                 Current rating of the tower                 
    Tower  Vnom               float       kV      False                 Voltage rating of the line                  
    =====  =================  ==========  ======  =========  =========  ===================================  =======


Transformer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ===========  ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
       class            name                 class_type           unit   mandatory  max_chars                                                                                                                descriptions                                                                                                                comment
    ===========  ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    Transformer  idtag               str                                 False                 Unique ID                                                                                                                                                                                                                                        
    Transformer  name                str                                 False                 Name of the branch.                                                                                                                                                                                                                              
    Transformer  code                str                                 False                 Secondary ID                                                                                                                                                                                                                                     
    Transformer  bus_from            Bus                                 False                 Name of the bus at the "from" side                                                                                                                                                                                                               
    Transformer  bus_to              Bus                                 False                 Name of the bus at the "to" side                                                                                                                                                                                                                 
    Transformer  cn_from             Connectivity Node                   False                 Name of the connectivity node at the "from" side                                                                                                                                                                                                 
    Transformer  cn_to               Connectivity Node                   False                 Name of the connectivity node at the "to" side                                                                                                                                                                                                   
    Transformer  active              bool                                False                 Is active?                                                                                                                                                                                                                                       
    Transformer  rate                float                        MVA    False                 Thermal rating power                                                                                                                                                                                                                             
    Transformer  contingency_factor  float                        p.u.   False                 Rating multiplier for contingencies                                                                                                                                                                                                              
    Transformer  monitor_loading     bool                                False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                                                                                                                                 
    Transformer  mttf                float                        h      False                 Mean time to failure                                                                                                                                                                                                                             
    Transformer  mttr                float                        h      False                 Mean time to repair                                                                                                                                                                                                                              
    Transformer  Cost                float                        e/MWh  False                 Cost of overloads. Used in OPF                                                                                                                                                                                                                   
    Transformer  build_status        enum BuildStatus                    False                 Branch build status. Used in expansion planning.                                                                                                                                                                                                 
    Transformer  capex               float                        e/MW   False                 Cost of investment. Used in expansion planning.                                                                                                                                                                                                  
    Transformer  opex                float                        e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                                                                                                                                   
    Transformer  HV                  float                        kV     False                 High voltage rating                                                                                                                                                                                                                              
    Transformer  LV                  float                        kV     False                 Low voltage rating                                                                                                                                                                                                                               
    Transformer  Sn                  float                        MVA    False                 Nominal power                                                                                                                                                                                                                                    
    Transformer  Pcu                 float                        kW     False                 Copper losses (optional)                                                                                                                                                                                                                         
    Transformer  Pfe                 float                        kW     False                 Iron losses (optional)                                                                                                                                                                                                                           
    Transformer  I0                  float                        %      False                 No-load current (optional)                                                                                                                                                                                                                       
    Transformer  Vsc                 float                        %      False                 Short-circuit voltage (optional)                                                                                                                                                                                                                 
    Transformer  R                   float                        p.u.   False                 Total positive sequence resistance.                                                                                                                                                                                                              
    Transformer  X                   float                        p.u.   False                 Total positive sequence reactance.                                                                                                                                                                                                               
    Transformer  G                   float                        p.u.   False                 Total positive sequence shunt conductance.                                                                                                                                                                                                       
    Transformer  B                   float                        p.u.   False                 Total positive sequence shunt susceptance.                                                                                                                                                                                                       
    Transformer  R0                  float                        p.u.   False                 Total zero sequence resistance.                                                                                                                                                                                                                  
    Transformer  X0                  float                        p.u.   False                 Total zero sequence reactance.                                                                                                                                                                                                                   
    Transformer  G0                  float                        p.u.   False                 Total zero sequence shunt conductance.                                                                                                                                                                                                           
    Transformer  B0                  float                        p.u.   False                 Total zero sequence shunt susceptance.                                                                                                                                                                                                           
    Transformer  R2                  float                        p.u.   False                 Total negative sequence resistance.                                                                                                                                                                                                              
    Transformer  X2                  float                        p.u.   False                 Total negative sequence reactance.                                                                                                                                                                                                               
    Transformer  G2                  float                        p.u.   False                 Total negative sequence shunt conductance.                                                                                                                                                                                                       
    Transformer  B2                  float                        p.u.   False                 Total negative sequence shunt susceptance.                                                                                                                                                                                                       
    Transformer  conn                enum WindingsConnection             False                 Windings connection (from, to):G: grounded starS: ungrounded starD: delta                                                                                                                                                                        
    Transformer  tolerance           float                        %      False                 Tolerance expected for the impedance values% is expected for transformers0% for lines.                                                                                                                                                           
    Transformer  tap_module          float                               False                 Tap changer module, it a value close to 1.0                                                                                                                                                                                                      
    Transformer  tap_module_max      float                               False                 Tap changer module max value                                                                                                                                                                                                                     
    Transformer  tap_module_min      float                               False                 Tap changer module min value                                                                                                                                                                                                                     
    Transformer  tap_phase           float                        rad    False                 Angle shift of the tap changer.                                                                                                                                                                                                                  
    Transformer  tap_phase_max       float                        rad    False                 Max angle.                                                                                                                                                                                                                                       
    Transformer  tap_phase_min       float                        rad    False                 Min angle.                                                                                                                                                                                                                                       
    Transformer  control_mode        enum TransformerControlType         False                 Control type of the transformer                                                                                                                                                                                                                  
    Transformer  vset                float                        p.u.   False                 Objective voltage at the "to" side of the bus when regulating the tap.                                                                                                                                                                           
    Transformer  Pset                float                        p.u.   False                 Objective power at the "from" side of when regulating the angle.                                                                                                                                                                                 
    Transformer  temp_base           float                        ºC     False                 Base temperature at which R was measured.                                                                                                                                                                                                        
    Transformer  temp_oper           float                        ºC     False                 Operation temperature to modify R.                                                                                                                                                                                                               
    Transformer  alpha               float                        1/ºC   False                 Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330         
    Transformer  template            Transformer type                    False                                                                                                                                                                                                                                                                  
    ===========  ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======


Transformer type
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ================  =====  ==========  ====  =========  =========  ========================================  =======
         class        name   class_type  unit  mandatory  max_chars                descriptions                comment
    ================  =====  ==========  ====  =========  =========  ========================================  =======
    Transformer type  idtag  str               False                 Unique ID                                        
    Transformer type  name   str               False                 Name of the branch.                              
    Transformer type  code   str               False                 Secondary ID                                     
    Transformer type  HV     float       kV    False                 Nominal voltage al the high voltage side         
    Transformer type  LV     float       kV    False                 Nominal voltage al the low voltage side          
    Transformer type  Sn     float       MVA   False                 Nominal power                                    
    Transformer type  Pcu    float       kW    False                 Copper losses                                    
    Transformer type  Pfe    float       kW    False                 Iron losses                                      
    Transformer type  I0     float       %     False                 No-load current                                  
    Transformer type  Vsc    float       %     False                 Short-circuit voltage                            
    ================  =====  ==========  ====  =========  =========  ========================================  =======


Transformer3W
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ========  ==========  ====  =========  =========  =============================  =======
        class        name    class_type  unit  mandatory  max_chars          descriptions           comment
    =============  ========  ==========  ====  =========  =========  =============================  =======
    Transformer3W  idtag     str               False                 Unique ID                             
    Transformer3W  name      str               False                 Name of the branch.                   
    Transformer3W  code      str               False                 Secondary ID                          
    Transformer3W  bus0      Bus               False                 Middle point connection bus.          
    Transformer3W  bus1      Bus               False                 Bus 1.                                
    Transformer3W  bus2      Bus               False                 Bus 2.                                
    Transformer3W  bus3      Bus               False                 Bus 3.                                
    Transformer3W  active    bool              False                 Is active?                            
    Transformer3W  winding1  Winding           False                 Winding 1.                            
    Transformer3W  winding2  Winding           False                 Winding 2.                            
    Transformer3W  winding3  Winding           False                 Winding 3.                            
    Transformer3W  V1        float       kV    False                 Side 1 rating                         
    Transformer3W  V2        float       kV    False                 Side 2 rating                         
    Transformer3W  V3        float       kV    False                 Side 3 rating                         
    Transformer3W  r12       float       p.u.  False                 Resistance measured from 1->2         
    Transformer3W  r23       float       p.u.  False                 Resistance measured from 2->3         
    Transformer3W  r31       float       p.u.  False                 Resistance measured from 3->1         
    Transformer3W  x12       float       p.u.  False                 Reactance measured from 1->2          
    Transformer3W  x23       float       p.u.  False                 Reactance measured from 2->3          
    Transformer3W  x31       float       p.u.  False                 Reactance measured from 3->1          
    Transformer3W  rate12    float       MVA   False                 Rating measured from 1->2             
    Transformer3W  rate23    float       MVA   False                 Rating measured from 2->3             
    Transformer3W  rate31    float       MVA   False                 Rating measured from 3->1             
    Transformer3W  x         float       px    False                 x position                            
    Transformer3W  y         float       px    False                 y position                            
    =============  ========  ==========  ====  =========  =========  =============================  =======


UPFC
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==================  =================  =====  =========  =========  ================================================================  =======
    class         name            class_type      unit   mandatory  max_chars                            descriptions                            comment
    =====  ==================  =================  =====  =========  =========  ================================================================  =======
    UPFC   idtag               str                       False                 Unique ID                                                                
    UPFC   name                str                       False                 Name of the branch.                                                      
    UPFC   code                str                       False                 Secondary ID                                                             
    UPFC   bus_from            Bus                       False                 Name of the bus at the "from" side                                       
    UPFC   bus_to              Bus                       False                 Name of the bus at the "to" side                                         
    UPFC   cn_from             Connectivity Node         False                 Name of the connectivity node at the "from" side                         
    UPFC   cn_to               Connectivity Node         False                 Name of the connectivity node at the "to" side                           
    UPFC   active              bool                      False                 Is active?                                                               
    UPFC   rate                float              MVA    False                 Thermal rating power                                                     
    UPFC   contingency_factor  float              p.u.   False                 Rating multiplier for contingencies                                      
    UPFC   monitor_loading     bool                      False                 Monitor this device loading for OPF, NTC or contingency studies.         
    UPFC   mttf                float              h      False                 Mean time to failure                                                     
    UPFC   mttr                float              h      False                 Mean time to repair                                                      
    UPFC   Cost                float              e/MWh  False                 Cost of overloads. Used in OPF                                           
    UPFC   build_status        enum BuildStatus          False                 Branch build status. Used in expansion planning.                         
    UPFC   capex               float              e/MW   False                 Cost of investment. Used in expansion planning.                          
    UPFC   opex                float              e/MWh  False                 Cost of operation. Used in expansion planning.                           
    UPFC   Rs                  float              p.u.   False                 Series positive sequence resistance.                                     
    UPFC   Xs                  float              p.u.   False                 Series positive sequence reactance.                                      
    UPFC   Rsh                 float              p.u.   False                 Shunt positive sequence resistance.                                      
    UPFC   Xsh                 float              p.u.   False                 Shunt positive sequence resistance.                                      
    UPFC   Rs0                 float              p.u.   False                 Series zero sequence resistance.                                         
    UPFC   Xs0                 float              p.u.   False                 Series zero sequence reactance.                                          
    UPFC   Rsh0                float              p.u.   False                 Shunt zero sequence resistance.                                          
    UPFC   Xsh0                float              p.u.   False                 Shunt zero sequence resistance.                                          
    UPFC   Rs2                 float              p.u.   False                 Series negative sequence resistance.                                     
    UPFC   Xs2                 float              p.u.   False                 Series negative sequence reactance.                                      
    UPFC   Rsh2                float              p.u.   False                 Shunt negative sequence resistance.                                      
    UPFC   Xsh2                float              p.u.   False                 Shunt negative sequence resistance.                                      
    UPFC   Vsh                 float              p.u.   False                 Shunt voltage set point.                                                 
    UPFC   Pfset               float              MW     False                 Active power set point.                                                  
    UPFC   Qfset               float              MVAr   False                 Active power set point.                                                  
    =====  ==================  =================  =====  =========  =========  ================================================================  =======


Underground line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ================  =====  ==========  ======  =========  =========  ==========================================  =======
         class        name   class_type   unit   mandatory  max_chars                 descriptions                 comment
    ================  =====  ==========  ======  =========  =========  ==========================================  =======
    Underground line  idtag  str                 False                 Unique ID                                          
    Underground line  name   str                 False                 Name of the branch.                                
    Underground line  code   str                 False                 Secondary ID                                       
    Underground line  Imax   float       kA      False                 Current rating of the line                         
    Underground line  Vnom   float       kV      False                 Voltage rating of the line                         
    Underground line  R      float       Ohm/km  False                 Positive-sequence resistance per km                
    Underground line  X      float       Ohm/km  False                 Positive-sequence reactance per km                 
    Underground line  B      float       uS/km   False                 Positive-sequence shunt susceptance per km         
    Underground line  R0     float       Ohm/km  False                 Zero-sequence resistance per km                    
    Underground line  X0     float       Ohm/km  False                 Zero-sequence reactance per km                     
    Underground line  B0     float       uS/km   False                 Zero-sequence shunt susceptance per km             
    ================  =====  ==========  ======  =========  =========  ==========================================  =======


VSC
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==================  =========================  =========  =========  =========  ================================================================  =======
    class         name                class_type            unit     mandatory  max_chars                            descriptions                            comment
    =====  ==================  =========================  =========  =========  =========  ================================================================  =======
    VSC    idtag               str                                   False                 Unique ID                                                                
    VSC    name                str                                   False                 Name of the branch.                                                      
    VSC    code                str                                   False                 Secondary ID                                                             
    VSC    bus_from            Bus                                   False                 Name of the bus at the "from" side                                       
    VSC    bus_to              Bus                                   False                 Name of the bus at the "to" side                                         
    VSC    cn_from             Connectivity Node                     False                 Name of the connectivity node at the "from" side                         
    VSC    cn_to               Connectivity Node                     False                 Name of the connectivity node at the "to" side                           
    VSC    active              bool                                  False                 Is active?                                                               
    VSC    rate                float                      MVA        False                 Thermal rating power                                                     
    VSC    contingency_factor  float                      p.u.       False                 Rating multiplier for contingencies                                      
    VSC    monitor_loading     bool                                  False                 Monitor this device loading for OPF, NTC or contingency studies.         
    VSC    mttf                float                      h          False                 Mean time to failure                                                     
    VSC    mttr                float                      h          False                 Mean time to repair                                                      
    VSC    Cost                float                      e/MWh      False                 Cost of overloads. Used in OPF                                           
    VSC    build_status        enum BuildStatus                      False                 Branch build status. Used in expansion planning.                         
    VSC    capex               float                      e/MW       False                 Cost of investment. Used in expansion planning.                          
    VSC    opex                float                      e/MWh      False                 Cost of operation. Used in expansion planning.                           
    VSC    R                   float                      p.u.       False                 Resistive positive sequence losses.                                      
    VSC    X                   float                      p.u.       False                 Magnetic positive sequence losses.                                       
    VSC    R0                  float                      p.u.       False                 Resistive zero sequence losses.                                          
    VSC    X0                  float                      p.u.       False                 Magnetic zero sequence losses.                                           
    VSC    R2                  float                      p.u.       False                 Resistive negative sequence losses.                                      
    VSC    X2                  float                      p.u.       False                 Magnetic negative sequence losses.                                       
    VSC    G0sw                float                      p.u.       False                 Inverter losses.                                                         
    VSC    Beq                 float                      p.u.       False                 Total shunt susceptance.                                                 
    VSC    Beq_max             float                      p.u.       False                 Max total shunt susceptance.                                             
    VSC    Beq_min             float                      p.u.       False                 Min total shunt susceptance.                                             
    VSC    tap_module          float                                 False                 Tap changer module, it a value close to 1.0                              
    VSC    tap_module_max      float                                 False                 Max tap changer module                                                   
    VSC    tap_module_min      float                                 False                 Min tap changer module                                                   
    VSC    tap_phase           float                      rad        False                 Converter firing angle.                                                  
    VSC    tap_phase_max       float                      rad        False                 Max converter firing angle.                                              
    VSC    tap_phase_min       float                      rad        False                 Min converter firing angle.                                              
    VSC    alpha1              float                                 False                 Converter losses curve parameter (IEC 62751-2 loss Correction).          
    VSC    alpha2              float                                 False                 Converter losses curve parameter (IEC 62751-2 loss Correction).          
    VSC    alpha3              float                                 False                 Converter losses curve parameter (IEC 62751-2 loss Correction).          
    VSC    k                   float                      p.u./p.u.  False                 Converter factor, typically 0.866.                                       
    VSC    control_mode        enum ConverterControlType             False                 Converter control mode                                                   
    VSC    kdp                 float                      p.u./p.u.  False                 Droop Power/Voltage slope.                                               
    VSC    Pdc_set             float                      MW         False                 DC power set point.                                                      
    VSC    Qac_set             float                      MVAr       False                 AC Reactive power set point.                                             
    VSC    Vac_set             float                      p.u.       False                 AC voltage set point.                                                    
    VSC    Vdc_set             float                      p.u.       False                 DC voltage set point.                                                    
    =====  ==================  =========================  =========  =========  =========  ================================================================  =======


Winding
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =======  ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
     class          name                 class_type           unit   mandatory  max_chars                                                                                                                descriptions                                                                                                                comment
    =======  ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    Winding  idtag               str                                 False                 Unique ID                                                                                                                                                                                                                                        
    Winding  name                str                                 False                 Name of the branch.                                                                                                                                                                                                                              
    Winding  code                str                                 False                 Secondary ID                                                                                                                                                                                                                                     
    Winding  bus_from            Bus                                 False                 Name of the bus at the "from" side                                                                                                                                                                                                               
    Winding  bus_to              Bus                                 False                 Name of the bus at the "to" side                                                                                                                                                                                                                 
    Winding  cn_from             Connectivity Node                   False                 Name of the connectivity node at the "from" side                                                                                                                                                                                                 
    Winding  cn_to               Connectivity Node                   False                 Name of the connectivity node at the "to" side                                                                                                                                                                                                   
    Winding  active              bool                                False                 Is active?                                                                                                                                                                                                                                       
    Winding  rate                float                        MVA    False                 Thermal rating power                                                                                                                                                                                                                             
    Winding  contingency_factor  float                        p.u.   False                 Rating multiplier for contingencies                                                                                                                                                                                                              
    Winding  monitor_loading     bool                                False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                                                                                                                                 
    Winding  mttf                float                        h      False                 Mean time to failure                                                                                                                                                                                                                             
    Winding  mttr                float                        h      False                 Mean time to repair                                                                                                                                                                                                                              
    Winding  Cost                float                        e/MWh  False                 Cost of overloads. Used in OPF                                                                                                                                                                                                                   
    Winding  build_status        enum BuildStatus                    False                 Branch build status. Used in expansion planning.                                                                                                                                                                                                 
    Winding  capex               float                        e/MW   False                 Cost of investment. Used in expansion planning.                                                                                                                                                                                                  
    Winding  opex                float                        e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                                                                                                                                   
    Winding  HV                  float                        kV     False                 High voltage rating                                                                                                                                                                                                                              
    Winding  LV                  float                        kV     False                 Low voltage rating                                                                                                                                                                                                                               
    Winding  R                   float                        p.u.   False                 Total positive sequence resistance.                                                                                                                                                                                                              
    Winding  X                   float                        p.u.   False                 Total positive sequence reactance.                                                                                                                                                                                                               
    Winding  G                   float                        p.u.   False                 Total positive sequence shunt conductance.                                                                                                                                                                                                       
    Winding  B                   float                        p.u.   False                 Total positive sequence shunt susceptance.                                                                                                                                                                                                       
    Winding  R0                  float                        p.u.   False                 Total zero sequence resistance.                                                                                                                                                                                                                  
    Winding  X0                  float                        p.u.   False                 Total zero sequence reactance.                                                                                                                                                                                                                   
    Winding  G0                  float                        p.u.   False                 Total zero sequence shunt conductance.                                                                                                                                                                                                           
    Winding  B0                  float                        p.u.   False                 Total zero sequence shunt susceptance.                                                                                                                                                                                                           
    Winding  R2                  float                        p.u.   False                 Total negative sequence resistance.                                                                                                                                                                                                              
    Winding  X2                  float                        p.u.   False                 Total negative sequence reactance.                                                                                                                                                                                                               
    Winding  G2                  float                        p.u.   False                 Total negative sequence shunt conductance.                                                                                                                                                                                                       
    Winding  B2                  float                        p.u.   False                 Total negative sequence shunt susceptance.                                                                                                                                                                                                       
    Winding  conn                enum WindingsConnection             False                 Windings connection (from, to):G: grounded starS: ungrounded starD: delta                                                                                                                                                                        
    Winding  tolerance           float                        %      False                 Tolerance expected for the impedance values.                                                                                                                                                                                                     
    Winding  tap_module          float                               False                 Tap changer module, it a value close to 1.0                                                                                                                                                                                                      
    Winding  tap_module_max      float                               False                 Tap changer module max value                                                                                                                                                                                                                     
    Winding  tap_module_min      float                               False                 Tap changer module min value                                                                                                                                                                                                                     
    Winding  tap_phase           float                        rad    False                 Angle shift of the tap changer.                                                                                                                                                                                                                  
    Winding  tap_phase_max       float                        rad    False                 Max angle.                                                                                                                                                                                                                                       
    Winding  tap_phase_min       float                        rad    False                 Min angle.                                                                                                                                                                                                                                       
    Winding  control_mode        enum TransformerControlType         False                 Control type of the transformer                                                                                                                                                                                                                  
    Winding  vset                float                        p.u.   False                 Objective voltage at the "to" side of the bus when regulating the tap.                                                                                                                                                                           
    Winding  Pset                float                        p.u.   False                 Objective power at the "from" side of when regulating the angle.                                                                                                                                                                                 
    Winding  temp_base           float                        ºC     False                 Base temperature at which R was measured.                                                                                                                                                                                                        
    Winding  temp_oper           float                        ºC     False                 Operation temperature to modify R.                                                                                                                                                                                                               
    Winding  alpha               float                        1/ºC   False                 Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330         
    Winding  template            Transformer type                    False                                                                                                                                                                                                                                                                  
    =======  ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======


Wire
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ===========  ==========  ======  =========  =========  ======================================  =======
    class     name      class_type   unit   mandatory  max_chars               descriptions               comment
    =====  ===========  ==========  ======  =========  =========  ======================================  =======
    Wire   idtag        str                 False                 Unique ID                                      
    Wire   name         str                 False                 Name of the branch.                            
    Wire   code         str                 False                 Secondary ID                                   
    Wire   r            float       Ohm/km  False                 resistance of the conductor                    
    Wire   x            float       Ohm/km  False                 reactance of the conductor                     
    Wire   gmr          float       m       False                 Geometric Mean Radius of the conductor         
    Wire   max_current  float       kA      False                 Maximum current of the conductor               
    =====  ===========  ==========  ======  =========  =========  ======================================  =======


Zone
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  =========  ==========  ====  =========  =========  =====================  =======
    class    name     class_type  unit  mandatory  max_chars      descriptions       comment
    =====  =========  ==========  ====  =========  =========  =====================  =======
    Zone   idtag      str               False                 Unique ID                     
    Zone   name       str               False                 Name of the branch.           
    Zone   code       str               False                 Secondary ID                  
    Zone   longitude  float       deg   False                 longitude of the bus.         
    Zone   latitude   float       deg   False                 latitude of the bus.          
    =====  =========  ==========  ====  =========  =========  =====================  =======


