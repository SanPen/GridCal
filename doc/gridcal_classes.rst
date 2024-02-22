Models
=============

GridCal
----------------------------------------------------------------------

Area
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  ==========  ====  =========  =========  =====================  =======
      name     class_type  unit  mandatory  max_chars      descriptions       comment
    =========  ==========  ====  =========  =========  =====================  =======
    idtag      str               False                 Unique ID                     
    name       str               False                 Name of the branch.           
    code       str               False                 Secondary ID                  
    longitude  float       deg   False                 longitude of the bus.         
    latitude   float       deg   False                 latitude of the bus.          
    =========  ==========  ====  =========  =========  =====================  =======


Battery
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ========================  =================  ======  =========  =========  ==========================================================================  =======
              name               class_type       unit   mandatory  max_chars                                 descriptions                                 comment
    ========================  =================  ======  =========  =========  ==========================================================================  =======
    idtag                     str                        False                 Unique ID                                                                          
    name                      str                        False                 Name of the branch.                                                                
    code                      str                        False                 Secondary ID                                                                       
    bus                       Bus                        False                 Connection bus                                                                     
    cn                        Connectivity Node          False                 Connection connectivity node                                                       
    active                    bool                       False                 Is the load active?                                                                
    mttf                      float              h       False                 Mean time to failure                                                               
    mttr                      float              h       False                 Mean time to recovery                                                              
    capex                     float              e/MW    False                 Cost of investment. Used in expansion planning.                                    
    opex                      float              e/MWh   False                 Cost of operation. Used in expansion planning.                                     
    build_status              enum BuildStatus           False                 Branch build status. Used in expansion planning.                                   
    Cost                      float              e/MWh   False                 Cost of not served energy. Used in OPF.                                            
    control_bus               Bus                        False                 Control bus                                                                        
    control_cn                Connectivity Node          False                 Control connectivity node                                                          
    P                         float              MW      False                 Active power                                                                       
    Pmin                      float              MW      False                 Minimum active power. Used in OPF.                                                 
    Pmax                      float              MW      False                 Maximum active power. Used in OPF.                                                 
    is_controlled             bool                       False                 Is this generator voltage-controlled?                                              
    Pf                        float                      False                 Power factor (cos(fi)). This is used for non-controlled generators.                
    Vset                      float              p.u.    False                 Set voltage. This is used for controlled generators.                               
    Snom                      float              MVA     False                 Nomnial power.                                                                     
    Qmin                      float              MVAr    False                 Minimum reactive power.                                                            
    Qmax                      float              MVAr    False                 Maximum reactive power.                                                            
    use_reactive_power_curve  bool                       False                 Use the reactive power capability curve?                                           
    q_curve                   Generator Q curve  MVAr    False                 Capability curve data (double click on the generator to edit)                      
    R1                        float              p.u.    False                 Total positive sequence resistance.                                                
    X1                        float              p.u.    False                 Total positive sequence reactance.                                                 
    R0                        float              p.u.    False                 Total zero sequence resistance.                                                    
    X0                        float              p.u.    False                 Total zero sequence reactance.                                                     
    R2                        float              p.u.    False                 Total negative sequence resistance.                                                
    X2                        float              p.u.    False                 Total negative sequence reactance.                                                 
    Cost2                     float              e/MWh²  False                 Generation quadratic cost. Used in OPF.                                            
    Cost0                     float              e/h     False                 Generation constant cost. Used in OPF.                                             
    StartupCost               float              e/h     False                 Generation start-up cost. Used in OPF.                                             
    ShutdownCost              float              e/h     False                 Generation shut-down cost. Used in OPF.                                            
    MinTimeUp                 float              h       False                 Minimum time that the generator has to be on when started. Used in OPF.            
    MinTimeDown               float              h       False                 Minimum time that the generator has to be off when shut down. Used in OPF.         
    RampUp                    float              MW/h    False                 Maximum amount of generation increase per hour.                                    
    RampDown                  float              MW/h    False                 Maximum amount of generation decrease per hour.                                    
    enabled_dispatch          bool                       False                 Enabled for dispatch? Used in OPF.                                                 
    Enom                      float              MWh     False                 Nominal energy capacity.                                                           
    max_soc                   float              p.u.    False                 Minimum state of charge.                                                           
    min_soc                   float              p.u.    False                 Maximum state of charge.                                                           
    soc_0                     float              p.u.    False                 Initial state of charge.                                                           
    charge_efficiency         float              p.u.    False                 Charging efficiency.                                                               
    discharge_efficiency      float              p.u.    False                 Discharge efficiency.                                                              
    discharge_per_cycle       float              p.u.    False                                                                                                    
    ========================  =================  ======  =========  =========  ==========================================================================  =======


Branch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
           name            class_type      unit   mandatory  max_chars                                                                                                                descriptions                                                                                                                comment
    ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    idtag               str                       False                 Unique ID                                                                                                                                                                                                                                        
    name                str                       False                 Name of the branch.                                                                                                                                                                                                                              
    code                str                       False                 Secondary ID                                                                                                                                                                                                                                     
    bus_from            Bus                       False                 Name of the bus at the "from" side                                                                                                                                                                                                               
    bus_to              Bus                       False                 Name of the bus at the "to" side                                                                                                                                                                                                                 
    cn_from             Connectivity Node         False                 Name of the connectivity node at the "from" side                                                                                                                                                                                                 
    cn_to               Connectivity Node         False                 Name of the connectivity node at the "to" side                                                                                                                                                                                                   
    active              bool                      False                 Is active?                                                                                                                                                                                                                                       
    rate                float              MVA    False                 Thermal rating power                                                                                                                                                                                                                             
    contingency_factor  float              p.u.   False                 Rating multiplier for contingencies                                                                                                                                                                                                              
    monitor_loading     bool                      False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                                                                                                                                 
    mttf                float              h      False                 Mean time to failure                                                                                                                                                                                                                             
    mttr                float              h      False                 Mean time to repair                                                                                                                                                                                                                              
    Cost                float              e/MWh  False                 Cost of overloads. Used in OPF                                                                                                                                                                                                                   
    build_status        enum BuildStatus          False                 Branch build status. Used in expansion planning.                                                                                                                                                                                                 
    capex               float              e/MW   False                 Cost of investment. Used in expansion planning.                                                                                                                                                                                                  
    opex                float              e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                                                                                                                                   
    R                   float              p.u.   False                 Total positive sequence resistance.                                                                                                                                                                                                              
    X                   float              p.u.   False                 Total positive sequence reactance.                                                                                                                                                                                                               
    B                   float              p.u.   False                 Total positive sequence shunt susceptance.                                                                                                                                                                                                       
    G                   float              p.u.   False                 Total positive sequence shunt conductance.                                                                                                                                                                                                       
    tolerance           float              %      False                 Tolerance expected for the impedance values % is expected for transformers0% for lines.                                                                                                                                                          
    length              float              km     False                 Length of the line (not used for calculation)                                                                                                                                                                                                    
    temp_base           float              ºC     False                 Base temperature at which R was measured.                                                                                                                                                                                                        
    temp_oper           float              ºC     False                 Operation temperature to modify R.                                                                                                                                                                                                               
    alpha               float              1/ºC   False                 Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330         
    tap_module          float                     False                 Tap changer module, it a value close to 1.0                                                                                                                                                                                                      
    angle               float              rad    False                 Angle shift of the tap changer.                                                                                                                                                                                                                  
    template            enum BranchType           False                                                                                                                                                                                                                                                                  
    bus_to_regulated    bool                      False                 Is the regulation at the bus to?                                                                                                                                                                                                                 
    vset                float              p.u.   False                 set control voltage.                                                                                                                                                                                                                             
    r_fault             float              p.u.   False                 Fault resistance.                                                                                                                                                                                                                                
    x_fault             float              p.u.   False                 Fault reactance.                                                                                                                                                                                                                                 
    fault_pos           float              p.u.   False                 proportion of the fault location measured from the "from" bus.                                                                                                                                                                                   
    branch_type         enum BranchType    p.u.   False                 Fault resistance.                                                                                                                                                                                                                                
    ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======


Bus
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ===========  ==========  ======  =========  =========  ===============================================================================================  =======
       name      class_type   unit   mandatory  max_chars                                           descriptions                                            comment
    ===========  ==========  ======  =========  =========  ===============================================================================================  =======
    idtag        str                 False                 Unique ID                                                                                               
    name         str                 False                 Name of the branch.                                                                                     
    code         str                 False                 Secondary ID                                                                                            
    active       bool                False                 Is the bus active? used to disable the bus.                                                             
    is_slack     bool                False                 Force the bus to be of slack type.                                                                      
    is_dc        bool                False                 Is this bus of DC type?.                                                                                
    is_internal  bool                False                 Is this bus part of a composite transformer, such as  a 3-winding transformer or a fluid node?.         
    Vnom         float       kV      False                 Nominal line voltage of the bus.                                                                        
    Vm0          float       p.u.    False                 Voltage module guess.                                                                                   
    Va0          float       rad.    False                 Voltage angle guess.                                                                                    
    Vmin         float       p.u.    False                 Lower range of allowed voltage module.                                                                  
    Vmax         float       p.u.    False                 Higher range of allowed voltage module.                                                                 
    Vm_cost      float       e/unit  False                 Cost of over and under voltages                                                                         
    angle_min    float       rad.    False                 Lower range of allowed voltage angle.                                                                   
    angle_max    float       rad.    False                 Higher range of allowed voltage angle.                                                                  
    angle_cost   float       e/unit  False                 Cost of over and under angles                                                                           
    r_fault      float       p.u.    False                 Resistance of the fault.This is used for short circuit studies.                                         
    x_fault      float       p.u.    False                 Reactance of the fault.This is used for short circuit studies.                                          
    x            float       px      False                 x position in pixels.                                                                                   
    y            float       px      False                 y position in pixels.                                                                                   
    h            float       px      False                 height of the bus in pixels.                                                                            
    w            float       px      False                 Width of the bus in pixels.                                                                             
    country      Country             False                 Country of the bus                                                                                      
    area         Area                False                 Area of the bus                                                                                         
    zone         Zone                False                 Zone of the bus                                                                                         
    substation   Substation          False                 Substation of the bus.                                                                                  
    longitude    float       deg     False                 longitude of the bus.                                                                                   
    latitude     float       deg     False                 latitude of the bus.                                                                                    
    ===========  ==========  ======  =========  =========  ===============================================================================================  =======


BusBar
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==========  =================  ====  =========  =========  =====================================  =======
       name        class_type      unit  mandatory  max_chars              descriptions               comment
    ==========  =================  ====  =========  =========  =====================================  =======
    idtag       str                      False                 Unique ID                                     
    name        str                      False                 Name of the branch.                           
    code        str                      False                 Secondary ID                                  
    substation  Substation               False                 Substation of this bus bar (optional)         
    cn          Connectivity Node        False                 Internal connectvity node                     
    ==========  =================  ====  =========  =========  =====================================  =======


Connectivity Node
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ===========  ==========  ====  =========  =========  =====================================================  =======
       name      class_type  unit  mandatory  max_chars                      descriptions                       comment
    ===========  ==========  ====  =========  =========  =====================================================  =======
    idtag        str               False                 Unique ID                                                     
    name         str               False                 Name of the branch.                                           
    code         str               False                 Secondary ID                                                  
    dc           bool              False                 is this a DC connectivity node?                               
    default_bus  Bus               False                 Default bus to use for topology processing (optional)         
    ===========  ==========  ====  =========  =========  =====================================================  =======


Contingency
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ============  =================  ====  =========  =========  =================================================  =======
        name         class_type      unit  mandatory  max_chars                    descriptions                     comment
    ============  =================  ====  =========  =========  =================================================  =======
    idtag         str                      False                 Unique ID                                                 
    name          str                      False                 Name of the branch.                                       
    code          str                      False                 Secondary ID                                              
    device_idtag  str                      False                 Unique ID                                                 
    prop          str                      False                 Name of the object property to change (active, %)         
    value         float                    False                 Property value                                            
    group         Contingency Group        False                 Contingency group                                         
    ============  =================  ====  =========  =========  =================================================  =======


Contingency Group
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ========  ==========  ====  =========  =========  ==========================================  =======
      name    class_type  unit  mandatory  max_chars                 descriptions                 comment
    ========  ==========  ====  =========  =========  ==========================================  =======
    idtag     str               False                 Unique ID                                          
    name      str               False                 Name of the branch.                                
    code      str               False                 Secondary ID                                       
    category  str               False                 Some tag to category the contingency group         
    ========  ==========  ====  =========  =========  ==========================================  =======


Country
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  ==========  ====  =========  =========  =====================  =======
      name     class_type  unit  mandatory  max_chars      descriptions       comment
    =========  ==========  ====  =========  =========  =====================  =======
    idtag      str               False                 Unique ID                     
    name       str               False                 Name of the branch.           
    code       str               False                 Secondary ID                  
    longitude  float       deg   False                 longitude of the bus.         
    latitude   float       deg   False                 latitude of the bus.          
    =========  ==========  ====  =========  =========  =====================  =======


DC line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  =================  =====  =========  =========  ===========================================================================================================================  =======
           name            class_type      unit   mandatory  max_chars                                                         descriptions                                                          comment
    ==================  =================  =====  =========  =========  ===========================================================================================================================  =======
    idtag               str                       False                 Unique ID                                                                                                                           
    name                str                       False                 Name of the branch.                                                                                                                 
    code                str                       False                 Secondary ID                                                                                                                        
    bus_from            Bus                       False                 Name of the bus at the "from" side                                                                                                  
    bus_to              Bus                       False                 Name of the bus at the "to" side                                                                                                    
    cn_from             Connectivity Node         False                 Name of the connectivity node at the "from" side                                                                                    
    cn_to               Connectivity Node         False                 Name of the connectivity node at the "to" side                                                                                      
    active              bool                      False                 Is active?                                                                                                                          
    rate                float              MVA    False                 Thermal rating power                                                                                                                
    contingency_factor  float              p.u.   False                 Rating multiplier for contingencies                                                                                                 
    monitor_loading     bool                      False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                    
    mttf                float              h      False                 Mean time to failure                                                                                                                
    mttr                float              h      False                 Mean time to repair                                                                                                                 
    Cost                float              e/MWh  False                 Cost of overloads. Used in OPF                                                                                                      
    build_status        enum BuildStatus          False                 Branch build status. Used in expansion planning.                                                                                    
    capex               float              e/MW   False                 Cost of investment. Used in expansion planning.                                                                                     
    opex                float              e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                      
    R                   float              p.u.   False                 Total positive sequence resistance.                                                                                                 
    length              float              km     False                 Length of the line (not used for calculation)                                                                                       
    r_fault             float              p.u.   False                 Resistance of the mid-line fault.Used in short circuit studies.                                                                     
    fault_pos           float              p.u.   False                 Per-unit positioning of the fault:0 would be at the "from" side,1 would be at the "to" side,therefore 0.5 is at the middle.         
    template            Sequence line             False                                                                                                                                                     
    ==================  =================  =====  =========  =========  ===========================================================================================================================  =======


Emission
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==========  ====  =========  =========  ===========================  =======
    name   class_type  unit  mandatory  max_chars         descriptions          comment
    =====  ==========  ====  =========  =========  ===========================  =======
    idtag  str               False                 Unique ID                           
    name   str               False                 Name of the branch.                 
    code   str               False                 Secondary ID                        
    cost   float       e/t   False                 Cost of emissions (e / ton)         
    color  str               False                 Color to paint                      
    =====  ==========  ====  =========  =========  ===========================  =======


Fluid P2X
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ================  ======  =========  =========  ================================================  =======
        name          class_type      unit   mandatory  max_chars                    descriptions                    comment
    =============  ================  ======  =========  =========  ================================================  =======
    idtag          str                       False                 Unique ID                                                
    name           str                       False                 Name of the branch.                                      
    code           str                       False                 Secondary ID                                             
    efficiency     float             MWh/m3  False                 Power plant energy production per fluid unit             
    max_flow_rate  float             m3/s    False                 maximum fluid flow                                       
    plant          Fluid node                False                 Connection reservoir/node                                
    generator      Generator                 False                 Electrical machine                                       
    build_status   enum BuildStatus          False                 Branch build status. Used in expansion planning.         
    =============  ================  ======  =========  =========  ================================================  =======


Fluid Pump
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ================  ======  =========  =========  ================================================  =======
        name          class_type      unit   mandatory  max_chars                    descriptions                    comment
    =============  ================  ======  =========  =========  ================================================  =======
    idtag          str                       False                 Unique ID                                                
    name           str                       False                 Name of the branch.                                      
    code           str                       False                 Secondary ID                                             
    efficiency     float             MWh/m3  False                 Power plant energy production per fluid unit             
    max_flow_rate  float             m3/s    False                 maximum fluid flow                                       
    plant          Fluid node                False                 Connection reservoir/node                                
    generator      Generator                 False                 Electrical machine                                       
    build_status   enum BuildStatus          False                 Branch build status. Used in expansion planning.         
    =============  ================  ======  =========  =========  ================================================  =======


Fluid Turbine
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ================  ======  =========  =========  ================================================  =======
        name          class_type      unit   mandatory  max_chars                    descriptions                    comment
    =============  ================  ======  =========  =========  ================================================  =======
    idtag          str                       False                 Unique ID                                                
    name           str                       False                 Name of the branch.                                      
    code           str                       False                 Secondary ID                                             
    efficiency     float             MWh/m3  False                 Power plant energy production per fluid unit             
    max_flow_rate  float             m3/s    False                 maximum fluid flow                                       
    plant          Fluid node                False                 Connection reservoir/node                                
    generator      Generator                 False                 Electrical machine                                       
    build_status   enum BuildStatus          False                 Branch build status. Used in expansion planning.         
    =============  ================  ======  =========  =========  ================================================  =======


Fluid node
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  ================  ========  =========  =========  ================================================  =======
        name          class_type       unit    mandatory  max_chars                    descriptions                    comment
    =============  ================  ========  =========  =========  ================================================  =======
    idtag          str                         False                 Unique ID                                                
    name           str                         False                 Name of the branch.                                      
    code           str                         False                 Secondary ID                                             
    min_level      float             hm3       False                 Minimum amount of fluid at the node/reservoir            
    max_level      float             hm3       False                 Maximum amount of fluid at the node/reservoir            
    initial_level  float             hm3       False                 Initial level of the node/reservoir                      
    bus            Bus                         False                 Electrical bus.                                          
    build_status   enum BuildStatus            False                 Branch build status. Used in expansion planning.         
    spillage_cost  float             e/(m3/s)  False                 Cost of nodal spillage                                   
    inflow         float             m3/s      False                 Flow of fluid coming from the rain                       
    =============  ================  ========  =========  =========  ================================================  =======


Fluid path
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ========  ==========  ====  =========  =========  ===================  =======
      name    class_type  unit  mandatory  max_chars     descriptions      comment
    ========  ==========  ====  =========  =========  ===================  =======
    idtag     str               False                 Unique ID                   
    name      str               False                 Name of the branch.         
    code      str               False                 Secondary ID                
    source    Fluid node        False                 Source node                 
    target    Fluid node        False                 Target node                 
    min_flow  float       m3/s  False                 Minimum flow                
    max_flow  float       m3/s  False                 Maximum flow                
    ========  ==========  ====  =========  =========  ===================  =======


Fuel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==========  ====  =========  =========  ======================  =======
    name   class_type  unit  mandatory  max_chars       descriptions       comment
    =====  ==========  ====  =========  =========  ======================  =======
    idtag  str               False                 Unique ID                      
    name   str               False                 Name of the branch.            
    code   str               False                 Secondary ID                   
    cost   float       e/t   False                 Cost of fuel (e / ton)         
    color  str               False                 Color to paint                 
    =====  ==========  ====  =========  =========  ======================  =======


Generator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ========================  =================  ======  =========  =========  ==========================================================================  =======
              name               class_type       unit   mandatory  max_chars                                 descriptions                                 comment
    ========================  =================  ======  =========  =========  ==========================================================================  =======
    idtag                     str                        False                 Unique ID                                                                          
    name                      str                        False                 Name of the branch.                                                                
    code                      str                        False                 Secondary ID                                                                       
    bus                       Bus                        False                 Connection bus                                                                     
    cn                        Connectivity Node          False                 Connection connectivity node                                                       
    active                    bool                       False                 Is the load active?                                                                
    mttf                      float              h       False                 Mean time to failure                                                               
    mttr                      float              h       False                 Mean time to recovery                                                              
    capex                     float              e/MW    False                 Cost of investment. Used in expansion planning.                                    
    opex                      float              e/MWh   False                 Cost of operation. Used in expansion planning.                                     
    build_status              enum BuildStatus           False                 Branch build status. Used in expansion planning.                                   
    Cost                      float              e/MWh   False                 Cost of not served energy. Used in OPF.                                            
    control_bus               Bus                        False                 Control bus                                                                        
    control_cn                Connectivity Node          False                 Control connectivity node                                                          
    P                         float              MW      False                 Active power                                                                       
    Pmin                      float              MW      False                 Minimum active power. Used in OPF.                                                 
    Pmax                      float              MW      False                 Maximum active power. Used in OPF.                                                 
    is_controlled             bool                       False                 Is this generator voltage-controlled?                                              
    Pf                        float                      False                 Power factor (cos(fi)). This is used for non-controlled generators.                
    Vset                      float              p.u.    False                 Set voltage. This is used for controlled generators.                               
    Snom                      float              MVA     False                 Nomnial power.                                                                     
    Qmin                      float              MVAr    False                 Minimum reactive power.                                                            
    Qmax                      float              MVAr    False                 Maximum reactive power.                                                            
    use_reactive_power_curve  bool                       False                 Use the reactive power capability curve?                                           
    q_curve                   Generator Q curve  MVAr    False                 Capability curve data (double click on the generator to edit)                      
    R1                        float              p.u.    False                 Total positive sequence resistance.                                                
    X1                        float              p.u.    False                 Total positive sequence reactance.                                                 
    R0                        float              p.u.    False                 Total zero sequence resistance.                                                    
    X0                        float              p.u.    False                 Total zero sequence reactance.                                                     
    R2                        float              p.u.    False                 Total negative sequence resistance.                                                
    X2                        float              p.u.    False                 Total negative sequence reactance.                                                 
    Cost2                     float              e/MWh²  False                 Generation quadratic cost. Used in OPF.                                            
    Cost0                     float              e/h     False                 Generation constant cost. Used in OPF.                                             
    StartupCost               float              e/h     False                 Generation start-up cost. Used in OPF.                                             
    ShutdownCost              float              e/h     False                 Generation shut-down cost. Used in OPF.                                            
    MinTimeUp                 float              h       False                 Minimum time that the generator has to be on when started. Used in OPF.            
    MinTimeDown               float              h       False                 Minimum time that the generator has to be off when shut down. Used in OPF.         
    RampUp                    float              MW/h    False                 Maximum amount of generation increase per hour.                                    
    RampDown                  float              MW/h    False                 Maximum amount of generation decrease per hour.                                    
    enabled_dispatch          bool                       False                 Enabled for dispatch? Used in OPF.                                                 
    ========================  =================  ======  =========  =========  ==========================================================================  =======


Generator Emission
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  ==========  =====  =========  =========  ==================================================  =======
      name     class_type  unit   mandatory  max_chars                     descriptions                     comment
    =========  ==========  =====  =========  =========  ==================================================  =======
    idtag      str                False                 Unique ID                                                  
    name       str                False                 Name of the branch.                                        
    code       str                False                 Secondary ID                                               
    generator  Generator          False                 Generator                                                  
    emission   Emission           False                 Emission                                                   
    rate       float       t/MWh  False                 Emissions rate of the gas in the generator (t/MWh)         
    =========  ==========  =====  =========  =========  ==================================================  =======


Generator Fuel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  ==========  =====  =========  =========  ======================================  =======
      name     class_type  unit   mandatory  max_chars               descriptions               comment
    =========  ==========  =====  =========  =========  ======================================  =======
    idtag      str                False                 Unique ID                                      
    name       str                False                 Name of the branch.                            
    code       str                False                 Secondary ID                                   
    generator  Generator          False                 Generator                                      
    fuel       Fuel               False                 Fuel                                           
    rate       float       t/MWh  False                 Fuel consumption rate in the generator         
    =========  ==========  =====  =========  =========  ======================================  =======


Generator Technology
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==========  ==========  ====  =========  =========  ===================================================  =======
       name     class_type  unit  mandatory  max_chars                     descriptions                      comment
    ==========  ==========  ====  =========  =========  ===================================================  =======
    idtag       str               False                 Unique ID                                                   
    name        str               False                 Name of the branch.                                         
    code        str               False                 Secondary ID                                                
    generator   Generator         False                 Generator object                                            
    technology  Technology        False                 Technology object                                           
    proportion  float       p.u.  False                 Share of the generator associated to the technology         
    ==========  ==========  ====  =========  =========  ===================================================  =======


HVDC Line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  ====================  ======  =========  =========  ===========================================================================================  =======
           name              class_type        unit   mandatory  max_chars                                         descriptions                                          comment
    ==================  ====================  ======  =========  =========  ===========================================================================================  =======
    idtag               str                           False                 Unique ID                                                                                           
    name                str                           False                 Name of the branch.                                                                                 
    code                str                           False                 Secondary ID                                                                                        
    bus_from            Bus                           False                 Name of the bus at the "from" side                                                                  
    bus_to              Bus                           False                 Name of the bus at the "to" side                                                                    
    cn_from             Connectivity Node             False                 Name of the connectivity node at the "from" side                                                    
    cn_to               Connectivity Node             False                 Name of the connectivity node at the "to" side                                                      
    active              bool                          False                 Is active?                                                                                          
    rate                float                 MVA     False                 Thermal rating power                                                                                
    contingency_factor  float                 p.u.    False                 Rating multiplier for contingencies                                                                 
    monitor_loading     bool                          False                 Monitor this device loading for OPF, NTC or contingency studies.                                    
    mttf                float                 h       False                 Mean time to failure                                                                                
    mttr                float                 h       False                 Mean time to repair                                                                                 
    Cost                float                 e/MWh   False                 Cost of overloads. Used in OPF                                                                      
    build_status        enum BuildStatus              False                 Branch build status. Used in expansion planning.                                                    
    capex               float                 e/MW    False                 Cost of investment. Used in expansion planning.                                                     
    opex                float                 e/MWh   False                 Cost of operation. Used in expansion planning.                                                      
    dispatchable        bool                          False                 Is the line power optimizable?                                                                      
    control_mode        enum HvdcControlType  -       False                 Control type.                                                                                       
    Pset                float                 MW      False                 Set power flow.                                                                                     
    r                   float                 Ohm     False                 line resistance.                                                                                    
    angle_droop         float                 MW/deg  False                 Power/angle rate control                                                                            
    n_lines             int                           False                 Number of parallel lines between the converter stations. The rating will be equally divided         
    Vset_f              float                 p.u.    False                 Set voltage at the from side                                                                        
    Vset_t              float                 p.u.    False                 Set voltage at the to side                                                                          
    min_firing_angle_f  float                 rad     False                 minimum firing angle at the "from" side.                                                            
    max_firing_angle_f  float                 rad     False                 maximum firing angle at the "from" side.                                                            
    min_firing_angle_t  float                 rad     False                 minimum firing angle at the "to" side.                                                              
    max_firing_angle_t  float                 rad     False                 maximum firing angle at the "to" side.                                                              
    length              float                 km      False                 Length of the branch (not used for calculation)                                                     
    ==================  ====================  ======  =========  =========  ===========================================================================================  =======


Investment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ============  =================  ====  =========  =========  ======================================================================  =======
        name         class_type      unit  mandatory  max_chars                               descriptions                               comment
    ============  =================  ====  =========  =========  ======================================================================  =======
    idtag         str                      False                 Unique ID                                                                      
    name          str                      False                 Name of the branch.                                                            
    code          str                      False                 Secondary ID                                                                   
    device_idtag  str                      False                 Unique ID                                                                      
    CAPEX         float              Me    False                 Capital expenditures. This is the initial investment.                          
    OPEX          float              Me    False                 Operation expenditures. Maintenance costs among other recurrent costs.         
    group         Investments Group        False                 Investment group                                                               
    comment       str                      False                 Comments                                                                       
    ============  =================  ====  =========  =========  ======================================================================  =======


Investments Group
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ========  ==========  ====  =========  =========  ==========================================  =======
      name    class_type  unit  mandatory  max_chars                 descriptions                 comment
    ========  ==========  ====  =========  =========  ==========================================  =======
    idtag     str               False                 Unique ID                                          
    name      str               False                 Name of the branch.                                
    code      str               False                 Secondary ID                                       
    category  str               False                 Some tag to category the contingency group         
    comment   str               False                 Some comment                                       
    ========  ==========  ====  =========  =========  ==========================================  =======


Line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
           name            class_type      unit   mandatory  max_chars                                                                                                                descriptions                                                                                                                comment
    ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    idtag               str                       False                 Unique ID                                                                                                                                                                                                                                        
    name                str                       False                 Name of the branch.                                                                                                                                                                                                                              
    code                str                       False                 Secondary ID                                                                                                                                                                                                                                     
    bus_from            Bus                       False                 Name of the bus at the "from" side                                                                                                                                                                                                               
    bus_to              Bus                       False                 Name of the bus at the "to" side                                                                                                                                                                                                                 
    cn_from             Connectivity Node         False                 Name of the connectivity node at the "from" side                                                                                                                                                                                                 
    cn_to               Connectivity Node         False                 Name of the connectivity node at the "to" side                                                                                                                                                                                                   
    active              bool                      False                 Is active?                                                                                                                                                                                                                                       
    rate                float              MVA    False                 Thermal rating power                                                                                                                                                                                                                             
    contingency_factor  float              p.u.   False                 Rating multiplier for contingencies                                                                                                                                                                                                              
    monitor_loading     bool                      False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                                                                                                                                 
    mttf                float              h      False                 Mean time to failure                                                                                                                                                                                                                             
    mttr                float              h      False                 Mean time to repair                                                                                                                                                                                                                              
    Cost                float              e/MWh  False                 Cost of overloads. Used in OPF                                                                                                                                                                                                                   
    build_status        enum BuildStatus          False                 Branch build status. Used in expansion planning.                                                                                                                                                                                                 
    capex               float              e/MW   False                 Cost of investment. Used in expansion planning.                                                                                                                                                                                                  
    opex                float              e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                                                                                                                                   
    R                   float              p.u.   False                 Total positive sequence resistance.                                                                                                                                                                                                              
    X                   float              p.u.   False                 Total positive sequence reactance.                                                                                                                                                                                                               
    B                   float              p.u.   False                 Total positive sequence shunt susceptance.                                                                                                                                                                                                       
    R0                  float              p.u.   False                 Total zero sequence resistance.                                                                                                                                                                                                                  
    X0                  float              p.u.   False                 Total zero sequence reactance.                                                                                                                                                                                                                   
    B0                  float              p.u.   False                 Total zero sequence shunt susceptance.                                                                                                                                                                                                           
    R2                  float              p.u.   False                 Total negative sequence resistance.                                                                                                                                                                                                              
    X2                  float              p.u.   False                 Total negative sequence reactance.                                                                                                                                                                                                               
    B2                  float              p.u.   False                 Total negative sequence shunt susceptance.                                                                                                                                                                                                       
    tolerance           float              %      False                 Tolerance expected for the impedance values % is expected for transformers0% for lines.                                                                                                                                                          
    length              float              km     False                 Length of the line (not used for calculation)                                                                                                                                                                                                    
    temp_base           float              ºC     False                 Base temperature at which R was measured.                                                                                                                                                                                                        
    temp_oper           float              ºC     False                 Operation temperature to modify R.                                                                                                                                                                                                               
    alpha               float              1/ºC   False                 Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330         
    r_fault             float              p.u.   False                 Resistance of the mid-line fault.Used in short circuit studies.                                                                                                                                                                                  
    x_fault             float              p.u.   False                 Reactance of the mid-line fault.Used in short circuit studies.                                                                                                                                                                                   
    fault_pos           float              p.u.   False                 Per-unit positioning of the fault:0 would be at the "from" side,1 would be at the "to" side,therefore 0.5 is at the middle.                                                                                                                      
    template            Sequence line             False                                                                                                                                                                                                                                                                  
    ==================  =================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======


Load
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ============  =================  =====  =========  =========  =======================================================  =======
        name         class_type      unit   mandatory  max_chars                       descriptions                        comment
    ============  =================  =====  =========  =========  =======================================================  =======
    idtag         str                       False                 Unique ID                                                       
    name          str                       False                 Name of the branch.                                             
    code          str                       False                 Secondary ID                                                    
    bus           Bus                       False                 Connection bus                                                  
    cn            Connectivity Node         False                 Connection connectivity node                                    
    active        bool                      False                 Is the load active?                                             
    mttf          float              h      False                 Mean time to failure                                            
    mttr          float              h      False                 Mean time to recovery                                           
    capex         float              e/MW   False                 Cost of investment. Used in expansion planning.                 
    opex          float              e/MWh  False                 Cost of operation. Used in expansion planning.                  
    build_status  enum BuildStatus          False                 Branch build status. Used in expansion planning.                
    Cost          float              e/MWh  False                 Cost of not served energy. Used in OPF.                         
    P             float              MW     False                 Active power                                                    
    Q             float              MVAr   False                 Reactive power                                                  
    Ir            float              MW     False                 Active power of the current component at V=1.0 p.u.             
    Ii            float              MVAr   False                 Reactive power of the current component at V=1.0 p.u.           
    G             float              MW     False                 Active power of the impedance component at V=1.0 p.u.           
    B             float              MVAr   False                 Reactive power of the impedance component at V=1.0 p.u.         
    ============  =================  =====  =========  =========  =======================================================  =======


Sequence line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==========  ======  =========  =========  ==========================================  =======
    name   class_type   unit   mandatory  max_chars                 descriptions                 comment
    =====  ==========  ======  =========  =========  ==========================================  =======
    idtag  str                 False                 Unique ID                                          
    name   str                 False                 Name of the branch.                                
    code   str                 False                 Secondary ID                                       
    Imax   float       kA      False                 Current rating of the line                         
    Vnom   float       kV      False                 Voltage rating of the line                         
    R      float       Ohm/km  False                 Positive-sequence resistance per km                
    X      float       Ohm/km  False                 Positive-sequence reactance per km                 
    B      float       uS/km   False                 Positive-sequence shunt susceptance per km         
    R0     float       Ohm/km  False                 Zero-sequence resistance per km                    
    X0     float       Ohm/km  False                 Zero-sequence reactance per km                     
    B0     float       uS/km   False                 Zero-sequence shunt susceptance per km             
    =====  ==========  ======  =========  =========  ==========================================  =======


Shunt
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =============  =================  =====  =========  =========  =====================================================================  =======
        name          class_type      unit   mandatory  max_chars                              descriptions                               comment
    =============  =================  =====  =========  =========  =====================================================================  =======
    idtag          str                       False                 Unique ID                                                                     
    name           str                       False                 Name of the branch.                                                           
    code           str                       False                 Secondary ID                                                                  
    bus            Bus                       False                 Connection bus                                                                
    cn             Connectivity Node         False                 Connection connectivity node                                                  
    active         bool                      False                 Is the load active?                                                           
    mttf           float              h      False                 Mean time to failure                                                          
    mttr           float              h      False                 Mean time to recovery                                                         
    capex          float              e/MW   False                 Cost of investment. Used in expansion planning.                               
    opex           float              e/MWh  False                 Cost of operation. Used in expansion planning.                                
    build_status   enum BuildStatus          False                 Branch build status. Used in expansion planning.                              
    Cost           float              e/MWh  False                 Cost of not served energy. Used in OPF.                                       
    G              float              MW     False                 Active power                                                                  
    B              float              MVAr   False                 Reactive power                                                                
    G0             float              MW     False                 Zero sequence active power of the impedance component at V=1.0 p.u.           
    B0             float              MVAr   False                 Zero sequence reactive power of the impedance component at V=1.0 p.u.         
    is_controlled  bool                      False                 Is the shunt controllable?                                                    
    Bmin           float              MVAr   False                 Reactive power min control value at V=1.0 p.u.                                
    Bmax           float              MVAr   False                 Reactive power max control value at V=1.0 p.u.                                
    Vset           float              p.u.   False                 Set voltage. This is used for controlled shunts.                              
    =============  =================  =====  =========  =========  =====================================================================  =======


Static Generator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ============  =================  =====  =========  =========  ================================================  =======
        name         class_type      unit   mandatory  max_chars                    descriptions                    comment
    ============  =================  =====  =========  =========  ================================================  =======
    idtag         str                       False                 Unique ID                                                
    name          str                       False                 Name of the branch.                                      
    code          str                       False                 Secondary ID                                             
    bus           Bus                       False                 Connection bus                                           
    cn            Connectivity Node         False                 Connection connectivity node                             
    active        bool                      False                 Is the load active?                                      
    mttf          float              h      False                 Mean time to failure                                     
    mttr          float              h      False                 Mean time to recovery                                    
    capex         float              e/MW   False                 Cost of investment. Used in expansion planning.          
    opex          float              e/MWh  False                 Cost of operation. Used in expansion planning.           
    build_status  enum BuildStatus          False                 Branch build status. Used in expansion planning.         
    Cost          float              e/MWh  False                 Cost of not served energy. Used in OPF.                  
    P             float              MW     False                 Active power                                             
    Q             float              MVAr   False                 Reactive power                                           
    ============  =================  =====  =========  =========  ================================================  =======


Substation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  ==========  ====  =========  =========  =====================  =======
      name     class_type  unit  mandatory  max_chars      descriptions       comment
    =========  ==========  ====  =========  =========  =====================  =======
    idtag      str               False                 Unique ID                     
    name       str               False                 Name of the branch.           
    code       str               False                 Secondary ID                  
    longitude  float       deg   False                 longitude of the bus.         
    latitude   float       deg   False                 latitude of the bus.          
    =========  ==========  ====  =========  =========  =====================  =======


Technology
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==========  ====  =========  =========  ========================  =======
    name   class_type  unit  mandatory  max_chars        descriptions        comment
    =====  ==========  ====  =========  =========  ========================  =======
    idtag  str               False                 Unique ID                        
    name   str               False                 Name of the branch.              
    code   str               False                 Secondary ID                     
    name2  str               False                 Name 2 of the technology         
    name3  str               False                 Name 3 of the technology         
    name4  str               False                 Name 4 of the technology         
    color  str               False                 Color to paint                   
    =====  ==========  ====  =========  =========  ========================  =======


Tower
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =================  ==========  ======  =========  =========  ===================================  =======
          name         class_type   unit   mandatory  max_chars             descriptions              comment
    =================  ==========  ======  =========  =========  ===================================  =======
    idtag              str                 False                 Unique ID                                   
    name               str                 False                 Name of the branch.                         
    code               str                 False                 Secondary ID                                
    earth_resistivity  float       Ohm/m3  False                 Earth resistivity                           
    frequency          float       Hz      False                 Frequency                                   
    R1                 float       Ohm/km  False                 Positive sequence resistance                
    X1                 float       Ohm/km  False                 Positive sequence reactance                 
    Bsh1               float       uS/km   False                 Positive sequence shunt susceptance         
    R0                 float       Ohm/km  False                 Zero-sequence resistance                    
    X0                 float       Ohm/km  False                 Zero sequence reactance                     
    Bsh0               float       uS/km   False                 Zero sequence shunt susceptance             
    Imax               float       kA      False                 Current rating of the tower                 
    Vnom               float       kV      False                 Voltage rating of the line                  
    =================  ==========  ======  =========  =========  ===================================  =======


Transformer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
           name                 class_type           unit   mandatory  max_chars                                                                                                                descriptions                                                                                                                comment
    ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    idtag               str                                 False                 Unique ID                                                                                                                                                                                                                                        
    name                str                                 False                 Name of the branch.                                                                                                                                                                                                                              
    code                str                                 False                 Secondary ID                                                                                                                                                                                                                                     
    bus_from            Bus                                 False                 Name of the bus at the "from" side                                                                                                                                                                                                               
    bus_to              Bus                                 False                 Name of the bus at the "to" side                                                                                                                                                                                                                 
    cn_from             Connectivity Node                   False                 Name of the connectivity node at the "from" side                                                                                                                                                                                                 
    cn_to               Connectivity Node                   False                 Name of the connectivity node at the "to" side                                                                                                                                                                                                   
    active              bool                                False                 Is active?                                                                                                                                                                                                                                       
    rate                float                        MVA    False                 Thermal rating power                                                                                                                                                                                                                             
    contingency_factor  float                        p.u.   False                 Rating multiplier for contingencies                                                                                                                                                                                                              
    monitor_loading     bool                                False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                                                                                                                                 
    mttf                float                        h      False                 Mean time to failure                                                                                                                                                                                                                             
    mttr                float                        h      False                 Mean time to repair                                                                                                                                                                                                                              
    Cost                float                        e/MWh  False                 Cost of overloads. Used in OPF                                                                                                                                                                                                                   
    build_status        enum BuildStatus                    False                 Branch build status. Used in expansion planning.                                                                                                                                                                                                 
    capex               float                        e/MW   False                 Cost of investment. Used in expansion planning.                                                                                                                                                                                                  
    opex                float                        e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                                                                                                                                   
    HV                  float                        kV     False                 High voltage rating                                                                                                                                                                                                                              
    LV                  float                        kV     False                 Low voltage rating                                                                                                                                                                                                                               
    Sn                  float                        MVA    False                 Nominal power                                                                                                                                                                                                                                    
    Pcu                 float                        kW     False                 Copper losses (optional)                                                                                                                                                                                                                         
    Pfe                 float                        kW     False                 Iron losses (optional)                                                                                                                                                                                                                           
    I0                  float                        %      False                 No-load current (optional)                                                                                                                                                                                                                       
    Vsc                 float                        %      False                 Short-circuit voltage (optional)                                                                                                                                                                                                                 
    R                   float                        p.u.   False                 Total positive sequence resistance.                                                                                                                                                                                                              
    X                   float                        p.u.   False                 Total positive sequence reactance.                                                                                                                                                                                                               
    G                   float                        p.u.   False                 Total positive sequence shunt conductance.                                                                                                                                                                                                       
    B                   float                        p.u.   False                 Total positive sequence shunt susceptance.                                                                                                                                                                                                       
    R0                  float                        p.u.   False                 Total zero sequence resistance.                                                                                                                                                                                                                  
    X0                  float                        p.u.   False                 Total zero sequence reactance.                                                                                                                                                                                                                   
    G0                  float                        p.u.   False                 Total zero sequence shunt conductance.                                                                                                                                                                                                           
    B0                  float                        p.u.   False                 Total zero sequence shunt susceptance.                                                                                                                                                                                                           
    R2                  float                        p.u.   False                 Total negative sequence resistance.                                                                                                                                                                                                              
    X2                  float                        p.u.   False                 Total negative sequence reactance.                                                                                                                                                                                                               
    G2                  float                        p.u.   False                 Total negative sequence shunt conductance.                                                                                                                                                                                                       
    B2                  float                        p.u.   False                 Total negative sequence shunt susceptance.                                                                                                                                                                                                       
    conn                enum WindingsConnection             False                 Windings connection (from, to):G: grounded starS: ungrounded starD: delta                                                                                                                                                                        
    tolerance           float                        %      False                 Tolerance expected for the impedance values% is expected for transformers0% for lines.                                                                                                                                                           
    tap_module          float                               False                 Tap changer module, it a value close to 1.0                                                                                                                                                                                                      
    tap_module_max      float                               False                 Tap changer module max value                                                                                                                                                                                                                     
    tap_module_min      float                               False                 Tap changer module min value                                                                                                                                                                                                                     
    tap_phase           float                        rad    False                 Angle shift of the tap changer.                                                                                                                                                                                                                  
    tap_phase_max       float                        rad    False                 Max angle.                                                                                                                                                                                                                                       
    tap_phase_min       float                        rad    False                 Min angle.                                                                                                                                                                                                                                       
    control_mode        enum TransformerControlType         False                 Control type of the transformer                                                                                                                                                                                                                  
    vset                float                        p.u.   False                 Objective voltage at the "to" side of the bus when regulating the tap.                                                                                                                                                                           
    Pset                float                        p.u.   False                 Objective power at the "from" side of when regulating the angle.                                                                                                                                                                                 
    temp_base           float                        ºC     False                 Base temperature at which R was measured.                                                                                                                                                                                                        
    temp_oper           float                        ºC     False                 Operation temperature to modify R.                                                                                                                                                                                                               
    alpha               float                        1/ºC   False                 Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330         
    template            Transformer type                    False                                                                                                                                                                                                                                                                  
    ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======


Transformer type
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==========  ====  =========  =========  ========================================  =======
    name   class_type  unit  mandatory  max_chars                descriptions                comment
    =====  ==========  ====  =========  =========  ========================================  =======
    idtag  str               False                 Unique ID                                        
    name   str               False                 Name of the branch.                              
    code   str               False                 Secondary ID                                     
    HV     float       kV    False                 Nominal voltage al the high voltage side         
    LV     float       kV    False                 Nominal voltage al the low voltage side          
    Sn     float       MVA   False                 Nominal power                                    
    Pcu    float       kW    False                 Copper losses                                    
    Pfe    float       kW    False                 Iron losses                                      
    I0     float       %     False                 No-load current                                  
    Vsc    float       %     False                 Short-circuit voltage                            
    =====  ==========  ====  =========  =========  ========================================  =======


Transformer3W
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ========  ==========  ====  =========  =========  =============================  =======
      name    class_type  unit  mandatory  max_chars          descriptions           comment
    ========  ==========  ====  =========  =========  =============================  =======
    idtag     str               False                 Unique ID                             
    name      str               False                 Name of the branch.                   
    code      str               False                 Secondary ID                          
    bus0      Bus               False                 Middle point connection bus.          
    bus1      Bus               False                 Bus 1.                                
    bus2      Bus               False                 Bus 2.                                
    bus3      Bus               False                 Bus 3.                                
    active    bool              False                 Is active?                            
    winding1  Winding           False                 Winding 1.                            
    winding2  Winding           False                 Winding 2.                            
    winding3  Winding           False                 Winding 3.                            
    V1        float       kV    False                 Side 1 rating                         
    V2        float       kV    False                 Side 2 rating                         
    V3        float       kV    False                 Side 3 rating                         
    r12       float       p.u.  False                 Resistance measured from 1->2         
    r23       float       p.u.  False                 Resistance measured from 2->3         
    r31       float       p.u.  False                 Resistance measured from 3->1         
    x12       float       p.u.  False                 Reactance measured from 1->2          
    x23       float       p.u.  False                 Reactance measured from 2->3          
    x31       float       p.u.  False                 Reactance measured from 3->1          
    rate12    float       MVA   False                 Rating measured from 1->2             
    rate23    float       MVA   False                 Rating measured from 2->3             
    rate31    float       MVA   False                 Rating measured from 3->1             
    x         float       px    False                 x position                            
    y         float       px    False                 y position                            
    ========  ==========  ====  =========  =========  =============================  =======


UPFC
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  =================  =====  =========  =========  ================================================================  =======
           name            class_type      unit   mandatory  max_chars                            descriptions                            comment
    ==================  =================  =====  =========  =========  ================================================================  =======
    idtag               str                       False                 Unique ID                                                                
    name                str                       False                 Name of the branch.                                                      
    code                str                       False                 Secondary ID                                                             
    bus_from            Bus                       False                 Name of the bus at the "from" side                                       
    bus_to              Bus                       False                 Name of the bus at the "to" side                                         
    cn_from             Connectivity Node         False                 Name of the connectivity node at the "from" side                         
    cn_to               Connectivity Node         False                 Name of the connectivity node at the "to" side                           
    active              bool                      False                 Is active?                                                               
    rate                float              MVA    False                 Thermal rating power                                                     
    contingency_factor  float              p.u.   False                 Rating multiplier for contingencies                                      
    monitor_loading     bool                      False                 Monitor this device loading for OPF, NTC or contingency studies.         
    mttf                float              h      False                 Mean time to failure                                                     
    mttr                float              h      False                 Mean time to repair                                                      
    Cost                float              e/MWh  False                 Cost of overloads. Used in OPF                                           
    build_status        enum BuildStatus          False                 Branch build status. Used in expansion planning.                         
    capex               float              e/MW   False                 Cost of investment. Used in expansion planning.                          
    opex                float              e/MWh  False                 Cost of operation. Used in expansion planning.                           
    Rs                  float              p.u.   False                 Series positive sequence resistance.                                     
    Xs                  float              p.u.   False                 Series positive sequence reactance.                                      
    Rsh                 float              p.u.   False                 Shunt positive sequence resistance.                                      
    Xsh                 float              p.u.   False                 Shunt positive sequence resistance.                                      
    Rs0                 float              p.u.   False                 Series zero sequence resistance.                                         
    Xs0                 float              p.u.   False                 Series zero sequence reactance.                                          
    Rsh0                float              p.u.   False                 Shunt zero sequence resistance.                                          
    Xsh0                float              p.u.   False                 Shunt zero sequence resistance.                                          
    Rs2                 float              p.u.   False                 Series negative sequence resistance.                                     
    Xs2                 float              p.u.   False                 Series negative sequence reactance.                                      
    Rsh2                float              p.u.   False                 Shunt negative sequence resistance.                                      
    Xsh2                float              p.u.   False                 Shunt negative sequence resistance.                                      
    Vsh                 float              p.u.   False                 Shunt voltage set point.                                                 
    Pfset               float              MW     False                 Active power set point.                                                  
    Qfset               float              MVAr   False                 Active power set point.                                                  
    ==================  =================  =====  =========  =========  ================================================================  =======


Underground line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =====  ==========  ======  =========  =========  ==========================================  =======
    name   class_type   unit   mandatory  max_chars                 descriptions                 comment
    =====  ==========  ======  =========  =========  ==========================================  =======
    idtag  str                 False                 Unique ID                                          
    name   str                 False                 Name of the branch.                                
    code   str                 False                 Secondary ID                                       
    Imax   float       kA      False                 Current rating of the line                         
    Vnom   float       kV      False                 Voltage rating of the line                         
    R      float       Ohm/km  False                 Positive-sequence resistance per km                
    X      float       Ohm/km  False                 Positive-sequence reactance per km                 
    B      float       uS/km   False                 Positive-sequence shunt susceptance per km         
    R0     float       Ohm/km  False                 Zero-sequence resistance per km                    
    X0     float       Ohm/km  False                 Zero-sequence reactance per km                     
    B0     float       uS/km   False                 Zero-sequence shunt susceptance per km             
    =====  ==========  ======  =========  =========  ==========================================  =======


VSC
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  =========================  =========  =========  =========  ================================================================  =======
           name                class_type            unit     mandatory  max_chars                            descriptions                            comment
    ==================  =========================  =========  =========  =========  ================================================================  =======
    idtag               str                                   False                 Unique ID                                                                
    name                str                                   False                 Name of the branch.                                                      
    code                str                                   False                 Secondary ID                                                             
    bus_from            Bus                                   False                 Name of the bus at the "from" side                                       
    bus_to              Bus                                   False                 Name of the bus at the "to" side                                         
    cn_from             Connectivity Node                     False                 Name of the connectivity node at the "from" side                         
    cn_to               Connectivity Node                     False                 Name of the connectivity node at the "to" side                           
    active              bool                                  False                 Is active?                                                               
    rate                float                      MVA        False                 Thermal rating power                                                     
    contingency_factor  float                      p.u.       False                 Rating multiplier for contingencies                                      
    monitor_loading     bool                                  False                 Monitor this device loading for OPF, NTC or contingency studies.         
    mttf                float                      h          False                 Mean time to failure                                                     
    mttr                float                      h          False                 Mean time to repair                                                      
    Cost                float                      e/MWh      False                 Cost of overloads. Used in OPF                                           
    build_status        enum BuildStatus                      False                 Branch build status. Used in expansion planning.                         
    capex               float                      e/MW       False                 Cost of investment. Used in expansion planning.                          
    opex                float                      e/MWh      False                 Cost of operation. Used in expansion planning.                           
    R                   float                      p.u.       False                 Resistive positive sequence losses.                                      
    X                   float                      p.u.       False                 Magnetic positive sequence losses.                                       
    R0                  float                      p.u.       False                 Resistive zero sequence losses.                                          
    X0                  float                      p.u.       False                 Magnetic zero sequence losses.                                           
    R2                  float                      p.u.       False                 Resistive negative sequence losses.                                      
    X2                  float                      p.u.       False                 Magnetic negative sequence losses.                                       
    G0sw                float                      p.u.       False                 Inverter losses.                                                         
    Beq                 float                      p.u.       False                 Total shunt susceptance.                                                 
    Beq_max             float                      p.u.       False                 Max total shunt susceptance.                                             
    Beq_min             float                      p.u.       False                 Min total shunt susceptance.                                             
    tap_module          float                                 False                 Tap changer module, it a value close to 1.0                              
    tap_module_max      float                                 False                 Max tap changer module                                                   
    tap_module_min      float                                 False                 Min tap changer module                                                   
    tap_phase           float                      rad        False                 Converter firing angle.                                                  
    tap_phase_max       float                      rad        False                 Max converter firing angle.                                              
    tap_phase_min       float                      rad        False                 Min converter firing angle.                                              
    alpha1              float                                 False                 Converter losses curve parameter (IEC 62751-2 loss Correction).          
    alpha2              float                                 False                 Converter losses curve parameter (IEC 62751-2 loss Correction).          
    alpha3              float                                 False                 Converter losses curve parameter (IEC 62751-2 loss Correction).          
    k                   float                      p.u./p.u.  False                 Converter factor, typically 0.866.                                       
    control_mode        enum ConverterControlType             False                 Converter control mode                                                   
    kdp                 float                      p.u./p.u.  False                 Droop Power/Voltage slope.                                               
    Pdc_set             float                      MW         False                 DC power set point.                                                      
    Qac_set             float                      MVAr       False                 AC Reactive power set point.                                             
    Vac_set             float                      p.u.       False                 AC voltage set point.                                                    
    Vdc_set             float                      p.u.       False                 DC voltage set point.                                                    
    ==================  =========================  =========  =========  =========  ================================================================  =======


Winding
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
           name                 class_type           unit   mandatory  max_chars                                                                                                                descriptions                                                                                                                comment
    ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======
    idtag               str                                 False                 Unique ID                                                                                                                                                                                                                                        
    name                str                                 False                 Name of the branch.                                                                                                                                                                                                                              
    code                str                                 False                 Secondary ID                                                                                                                                                                                                                                     
    bus_from            Bus                                 False                 Name of the bus at the "from" side                                                                                                                                                                                                               
    bus_to              Bus                                 False                 Name of the bus at the "to" side                                                                                                                                                                                                                 
    cn_from             Connectivity Node                   False                 Name of the connectivity node at the "from" side                                                                                                                                                                                                 
    cn_to               Connectivity Node                   False                 Name of the connectivity node at the "to" side                                                                                                                                                                                                   
    active              bool                                False                 Is active?                                                                                                                                                                                                                                       
    rate                float                        MVA    False                 Thermal rating power                                                                                                                                                                                                                             
    contingency_factor  float                        p.u.   False                 Rating multiplier for contingencies                                                                                                                                                                                                              
    monitor_loading     bool                                False                 Monitor this device loading for OPF, NTC or contingency studies.                                                                                                                                                                                 
    mttf                float                        h      False                 Mean time to failure                                                                                                                                                                                                                             
    mttr                float                        h      False                 Mean time to repair                                                                                                                                                                                                                              
    Cost                float                        e/MWh  False                 Cost of overloads. Used in OPF                                                                                                                                                                                                                   
    build_status        enum BuildStatus                    False                 Branch build status. Used in expansion planning.                                                                                                                                                                                                 
    capex               float                        e/MW   False                 Cost of investment. Used in expansion planning.                                                                                                                                                                                                  
    opex                float                        e/MWh  False                 Cost of operation. Used in expansion planning.                                                                                                                                                                                                   
    HV                  float                        kV     False                 High voltage rating                                                                                                                                                                                                                              
    LV                  float                        kV     False                 Low voltage rating                                                                                                                                                                                                                               
    R                   float                        p.u.   False                 Total positive sequence resistance.                                                                                                                                                                                                              
    X                   float                        p.u.   False                 Total positive sequence reactance.                                                                                                                                                                                                               
    G                   float                        p.u.   False                 Total positive sequence shunt conductance.                                                                                                                                                                                                       
    B                   float                        p.u.   False                 Total positive sequence shunt susceptance.                                                                                                                                                                                                       
    R0                  float                        p.u.   False                 Total zero sequence resistance.                                                                                                                                                                                                                  
    X0                  float                        p.u.   False                 Total zero sequence reactance.                                                                                                                                                                                                                   
    G0                  float                        p.u.   False                 Total zero sequence shunt conductance.                                                                                                                                                                                                           
    B0                  float                        p.u.   False                 Total zero sequence shunt susceptance.                                                                                                                                                                                                           
    R2                  float                        p.u.   False                 Total negative sequence resistance.                                                                                                                                                                                                              
    X2                  float                        p.u.   False                 Total negative sequence reactance.                                                                                                                                                                                                               
    G2                  float                        p.u.   False                 Total negative sequence shunt conductance.                                                                                                                                                                                                       
    B2                  float                        p.u.   False                 Total negative sequence shunt susceptance.                                                                                                                                                                                                       
    conn                enum WindingsConnection             False                 Windings connection (from, to):G: grounded starS: ungrounded starD: delta                                                                                                                                                                        
    tolerance           float                        %      False                 Tolerance expected for the impedance values.                                                                                                                                                                                                     
    tap_module          float                               False                 Tap changer module, it a value close to 1.0                                                                                                                                                                                                      
    tap_module_max      float                               False                 Tap changer module max value                                                                                                                                                                                                                     
    tap_module_min      float                               False                 Tap changer module min value                                                                                                                                                                                                                     
    tap_phase           float                        rad    False                 Angle shift of the tap changer.                                                                                                                                                                                                                  
    tap_phase_max       float                        rad    False                 Max angle.                                                                                                                                                                                                                                       
    tap_phase_min       float                        rad    False                 Min angle.                                                                                                                                                                                                                                       
    control_mode        enum TransformerControlType         False                 Control type of the transformer                                                                                                                                                                                                                  
    vset                float                        p.u.   False                 Objective voltage at the "to" side of the bus when regulating the tap.                                                                                                                                                                           
    Pset                float                        p.u.   False                 Objective power at the "from" side of when regulating the angle.                                                                                                                                                                                 
    temp_base           float                        ºC     False                 Base temperature at which R was measured.                                                                                                                                                                                                        
    temp_oper           float                        ºC     False                 Operation temperature to modify R.                                                                                                                                                                                                               
    alpha               float                        1/ºC   False                 Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330         
    template            Transformer type                    False                                                                                                                                                                                                                                                                  
    ==================  ===========================  =====  =========  =========  ========================================================================================================================================================================================================================================  =======


Wire
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    ===========  ==========  ======  =========  =========  ======================================  =======
       name      class_type   unit   mandatory  max_chars               descriptions               comment
    ===========  ==========  ======  =========  =========  ======================================  =======
    idtag        str                 False                 Unique ID                                      
    name         str                 False                 Name of the branch.                            
    code         str                 False                 Secondary ID                                   
    r            float       Ohm/km  False                 resistance of the conductor                    
    x            float       Ohm/km  False                 reactance of the conductor                     
    gmr          float       m       False                 Geometric Mean Radius of the conductor         
    max_current  float       kA      False                 Maximum current of the conductor               
    ===========  ==========  ======  =========  =========  ======================================  =======


Zone
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::

    =========  ==========  ====  =========  =========  =====================  =======
      name     class_type  unit  mandatory  max_chars      descriptions       comment
    =========  ==========  ====  =========  =========  =====================  =======
    idtag      str               False                 Unique ID                     
    name       str               False                 Name of the branch.           
    code       str               False                 Secondary ID                  
    longitude  float       deg   False                 longitude of the bus.         
    latitude   float       deg   False                 latitude of the bus.          
    =========  ==========  ====  =========  =========  =====================  =======


