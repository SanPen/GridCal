from GridCal.Engine import *

Sbase = 100 # MVA


def complex_impedance(z, XR):
    """
    Returns the complex impedance from z (in %) and the X/R ratio.
    """
    z = float(abs(z))
    XR = float(abs(XR))
    real = (z**2/(1+XR**2))**0.5
    try:
        imag = (z**2/(1+1/XR**2))**0.5
    except ZeroDivisionError:
        imag = 0.0
    return complex(real, imag)


def test_xfo_static_tap_1():
    """
    Basic test with the main transformer's  HV tap (X_C3) set at +5% (1.05 pu),
    which lowers the LV by the same amount (-5%).
    """
    test_name = "test_xfo_static_tap_1"
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    POI = Bus(name="POI",
              vnom=100, #kV
              is_slack=True)
    grid.add_bus(POI)

    B_C3 = Bus(name="B_C3",
               vnom=10) #kV
    grid.add_bus(B_C3)

    B_MV_M32 = Bus(name="B_MV_M32",
                   vnom=10) #kV
    grid.add_bus(B_MV_M32)

    B_LV_M32 = Bus(name="B_LV_M32",
                   vnom=0.6) #kV
    grid.add_bus(B_LV_M32)

    # Create voltage controlled generators (or slack, a.k.a. swing)
    UT = Generator(name="Utility")
    UT.bus = POI
    grid.add_generator(POI, UT)

    # Create static generators (with fixed power factor)
    M32 = StaticGenerator(name="M32",
                          P=4.2, Q=0.0) # MVA (complex)
    M32.bus = B_LV_M32
    grid.add_static_generator(B_LV_M32, M32)

    # Create transformer types
    s = 5 # MVA
    z = 8 # %
    xr = 40
    SS = TransformerType(name="SS",
                         hv_nominal_voltage=100, # kV
                         lv_nominal_voltage=10, # kV
                         nominal_power=s,
                         copper_losses=complex_impedance(z, xr).real*s*1000/Sbase,
                         iron_losses=6.25, # kW
                         no_load_current=0.5, # %
                         short_circuit_voltage=z)
    grid.add_transformer_type(SS)

    s = 5 # MVA
    z = 6 # %
    xr = 20
    PM = TransformerType(name="PM",
                         hv_nominal_voltage=10, # kV
                         lv_nominal_voltage=0.6, # kV
                         nominal_power=s,
                         copper_losses=complex_impedance(z, xr).real*s*1000/Sbase,
                         iron_losses=6.25, # kW
                         no_load_current=0.5, # %
                         short_circuit_voltage=z)
    grid.add_transformer_type(PM)

    # Create branches
    X_C3 = Branch(bus_from=POI,
                  bus_to=B_C3,
                  name="X_C3",
                  branch_type=BranchType.Transformer,
                  template=SS,
                  tap=1.05)
    grid.add_branch(X_C3)

    C_M32 = Branch(bus_from=B_C3,
                   bus_to=B_MV_M32,
                   name="C_M32",
                   r=0.784,
                   x=0.174)
    grid.add_branch(C_M32)

    X_M32 = Branch(bus_from=B_MV_M32,
                   bus_to=B_LV_M32,
                   name="X_M32",
                   branch_type=BranchType.Transformer,
                   template=PM)
    grid.add_branch(X_M32)

    # Apply templates (device types)
    grid.apply_all_branch_types()

    print("Buses:")
    for i, b in enumerate(grid.buses):
        print(f" - bus[{i}]: {b}")
    print()

    options = PowerFlowOptions(SolverType.LM,
                               verbose=True,
                               initialize_with_existing_solution=True,
                               multi_core=True,
                               control_q=ReactivePowerControlMode.Direct,
                               tolerance=1e-6,
                               max_iter=99)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    approx_volt = [round(100*abs(v), 1) for v in power_flow.results.voltage]
    solution = [100.0, 94.7, 98.0, 98.1] # Expected solution from GridCal

    print()
    print(f"Test: {test_name}")
    print(f"Results:  {approx_volt}")
    print(f"Solution: {solution}")
    print()

    print("Generators:")
    for g in grid.get_generators():
        print(f" - Generator {g}: q_min={g.Qmin} MVAR, q_max={g.Qmax} MVAR")
    print()

    print("Branches:")
    for b in grid.branches:
        print(f" - {b}:")
        print(f"   R = {round(b.R, 4)} pu")
        print(f"   X = {round(b.X, 4)} pu")
        print(f"   X/R = {round(b.X/b.R, 1)}")
        print(f"   G = {round(b.G, 4)} pu")
        print(f"   B = {round(b.B, 4)} pu")
    print()

    print("Transformer types:")
    for t in grid.transformer_types:
        print(f" - {t}: Copper losses={int(t.Pcu)}kW, Iron losses={int(t.Pfe)}kW, SC voltage={t.Vsc}%")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={1000*round(power_flow.results.losses[i], 3)} kVA")
    print()

    equal = True
    for i in range(len(approx_volt)):
        if approx_volt[i] != solution[i]:
            equal = False

    assert equal


def test_xfo_static_tap_2():
    """
    Basic test with the main transformer's  HV tap (X_C3) set at -2.5%
    (0.975 pu), which raises the LV by the same amount (+2.5%).
    """
    test_name = "test_xfo_static_tap_2"
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    POI = Bus(name="POI",
              vnom=100, #kV
              is_slack=True)
    grid.add_bus(POI)

    B_C3 = Bus(name="B_C3",
               vnom=10) #kV
    grid.add_bus(B_C3)

    B_MV_M32 = Bus(name="B_MV_M32",
                   vnom=10) #kV
    grid.add_bus(B_MV_M32)

    B_LV_M32 = Bus(name="B_LV_M32",
                   vnom=0.6) #kV
    grid.add_bus(B_LV_M32)

    # Create voltage controlled generators (or slack, a.k.a. swing)
    UT = Generator(name="Utility")
    UT.bus = POI
    grid.add_generator(POI, UT)

    # Create static generators (with fixed power factor)
    M32 = StaticGenerator(name="M32",
                          P=4.2, Q=0.0) # MVA (complex)
    M32.bus = B_LV_M32
    grid.add_static_generator(B_LV_M32, M32)

    # Create transformer types
    s = 5 # MVA
    z = 8 # %
    xr = 40
    SS = TransformerType(name="SS",
                         hv_nominal_voltage=100, # kV
                         lv_nominal_voltage=10, # kV
                         nominal_power=s,
                         copper_losses=complex_impedance(z, xr).real*s*1000/Sbase,
                         iron_losses=6.25, # kW
                         no_load_current=0.5, # %
                         short_circuit_voltage=z)
    grid.add_transformer_type(SS)

    s = 5 # MVA
    z = 6 # %
    xr = 20
    PM = TransformerType(name="PM",
                         hv_nominal_voltage=10, # kV
                         lv_nominal_voltage=0.6, # kV
                         nominal_power=s,
                         copper_losses=complex_impedance(z, xr).real*s*1000/Sbase,
                         iron_losses=6.25, # kW
                         no_load_current=0.5, # %
                         short_circuit_voltage=z)
    grid.add_transformer_type(PM)

    # Create branches
    X_C3 = Branch(bus_from=POI,
                  bus_to=B_C3,
                  name="X_C3",
                  branch_type=BranchType.Transformer,
                  template=SS,
                  tap=0.975)
    grid.add_branch(X_C3)

    C_M32 = Branch(bus_from=B_C3,
                   bus_to=B_MV_M32,
                   name="C_M32",
                   r=0.784,
                   x=0.174)
    grid.add_branch(C_M32)

    X_M32 = Branch(bus_from=B_MV_M32,
                   bus_to=B_LV_M32,
                   name="X_M32",
                   branch_type=BranchType.Transformer,
                   template=PM)
    grid.add_branch(X_M32)

    # Apply templates (device types)
    grid.apply_all_branch_types()

    print("Buses:")
    for i, b in enumerate(grid.buses):
        print(f" - bus[{i}]: {b}")
    print()

    options = PowerFlowOptions(SolverType.LM,
                               verbose=True,
                               initialize_with_existing_solution=True,
                               multi_core=True,
                               control_q=ReactivePowerControlMode.Direct,
                               tolerance=1e-6,
                               max_iter=99)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    approx_volt = [round(100*abs(v), 1) for v in power_flow.results.voltage]
    solution = [100.0, 102.1, 105.2, 105.3] # Expected solution from GridCal

    print()
    print(f"Test: {test_name}")
    print(f"Results:  {approx_volt}")
    print(f"Solution: {solution}")
    print()

    print("Generators:")
    for g in grid.get_generators():
        print(f" - Generator {g}: q_min={g.Qmin} MVAR, q_max={g.Qmax} MVAR")
    print()

    print("Branches:")
    for b in grid.branches:
        print(f" - {b}:")
        print(f"   R = {round(b.R, 4)} pu")
        print(f"   X = {round(b.X, 4)} pu")
        print(f"   X/R = {round(b.X/b.R, 1)}")
        print(f"   G = {round(b.G, 4)} pu")
        print(f"   B = {round(b.B, 4)} pu")
    print()

    print("Transformer types:")
    for t in grid.transformer_types:
        print(f" - {t}: Copper losses={int(t.Pcu)}kW, Iron losses={int(t.Pfe)}kW, SC voltage={t.Vsc}%")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={1000*round(power_flow.results.losses[i], 3)} kVA")
    print()

    equal = True
    for i in range(len(approx_volt)):
        if approx_volt[i] != solution[i]:
            equal = False

    assert equal


def test_xfo_static_tap_3():
    """
    Basic test with the main transformer's  HV tap (X_C3) set at -2.5%
    (0.975 pu), which raises the LV by the same amount (+2.5%).
    """
    test_name = "test_xfo_static_tap_3"
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    POI = Bus(name="POI",
              vnom=100,  # kV
              is_slack=True)
    grid.add_bus(POI)

    B_C3 = Bus(name="B_C3",
               vnom=10)  # kV
    grid.add_bus(B_C3)

    B_MV_M32 = Bus(name="B_MV_M32",
                   vnom=10)  # kV
    grid.add_bus(B_MV_M32)

    B_LV_M32 = Bus(name="B_LV_M32",
                   vnom=0.6)  # kV
    grid.add_bus(B_LV_M32)

    # Create voltage controlled generators (or slack, a.k.a. swing)
    UT = Generator(name="Utility")
    UT.bus = POI
    grid.add_generator(POI, UT)

    # Create static generators (with fixed power factor)
    M32 = StaticGenerator(name="M32",
                          P=4.2, Q=0.0) # MVA (complex)
    M32.bus = B_LV_M32
    grid.add_static_generator(B_LV_M32, M32)

    # Create transformer types
    s = 5  # MVA
    z = 8  # %
    xr = 40
    SS = TransformerType(name="SS",
                         hv_nominal_voltage=100,  # kV
                         lv_nominal_voltage=10,  # kV
                         nominal_power=s,
                         copper_losses=complex_impedance(z, xr).real*s*1000/Sbase,
                         iron_losses=6.25,  # kW
                         no_load_current=0.5,  # %
                         short_circuit_voltage=z)
    grid.add_transformer_type(SS)

    s = 5  # MVA
    z = 6  # %
    xr = 20
    PM = TransformerType(name="PM",
                         hv_nominal_voltage=10,  # kV
                         lv_nominal_voltage=0.6,  # kV
                         nominal_power=s,
                         copper_losses=complex_impedance(z, xr).real*s*1000/Sbase,
                         iron_losses=6.25,  # kW
                         no_load_current=0.5,  # %
                         short_circuit_voltage=z)
    grid.add_transformer_type(PM)

    # Create branches
    X_C3 = Branch(bus_from=POI,
                  bus_to=B_C3,
                  name="X_C3",
                  branch_type=BranchType.Transformer,
                  template=SS,
                  tap=0.975)
    # update to a more precise tap changer
    X_C3.apply_tap_changer(TapChanger(taps_up=20, taps_down=20, max_reg=1.1, min_reg=0.9))
    grid.add_branch(X_C3)

    C_M32 = Branch(bus_from=B_C3,
                   bus_to=B_MV_M32,
                   name="C_M32",
                   r=0.784,
                   x=0.174)
    grid.add_branch(C_M32)

    X_M32 = Branch(bus_from=B_MV_M32,
                   bus_to=B_LV_M32,
                   name="X_M32",
                   branch_type=BranchType.Transformer,
                   template=PM)
    grid.add_branch(X_M32)

    # Apply templates (device types)
    grid.apply_all_branch_types()

    print("Buses:")
    for i, b in enumerate(grid.buses):
        print(f" - bus[{i}]: {b}")
    print()

    grid.compile()
    options = PowerFlowOptions(SolverType.NR,
                               verbose=True,
                               initialize_with_existing_solution=True,
                               multi_core=True,
                               control_q=ReactivePowerControlMode.Direct,
                               tolerance=1e-6,
                               max_iter=15)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    print()
    print(f"Test: {test_name}")
    print()

    print("Generators:")
    for g in grid.get_generators():
        print(f" - Generator {g}: q_min={g.Qmin} MVAR, q_max={g.Qmax} MVAR")
    print()

    print("Branches:")
    for b in grid.branches:
        print(f" - {b}:")
        print(f"   R = {round(b.R, 4)} pu")
        print(f"   X = {round(b.X, 4)} pu")
        print(f"   X/R = {round(b.X/b.R, 1)}")
        print(f"   G = {round(b.G, 4)} pu")
        print(f"   B = {round(b.B, 4)} pu")
    print()

    print("Transformer types:")
    for t in grid.transformer_types:
        print(f" - {t}: Copper losses={int(t.Pcu)}kW, "
              f"Iron losses={int(t.Pfe)}kW, SC voltage={t.Vsc}%")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={1000*round(power_flow.results.losses[i], 3)} kVA")
    print()

    equal = False
    for i, branch in enumerate(grid.branches):
        if branch.name == "X_C3":
            equal = power_flow.results.tap_module[i] == branch.tap_module

    if not equal:
        grid.export_pf(f"{test_name}_results.xlsx", power_flow.results)
        grid.save_excel(f"{test_name}_grid.xlsx")

    assert equal
