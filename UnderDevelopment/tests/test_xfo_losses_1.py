from GridCal.Engine.PowerFlowDriver import PowerFlowOptions, SolverType, ReactivePowerControlMode
from GridCal.Engine.PowerFlowDriver import PowerFlow
from GridCal.Engine.CalculationEngine import MultiCircuit
from GridCal.Engine.Devices import *
from GridCal.Engine.DeviceTypes import *

test_name = "test_xfo_losses_1"
Sbase = 100 # MVA

def get_complex(z, XR):
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

def test_xfo_losses_1():
    """
    Simple test to compare transformer losses with other software (ETAP 18.1
    and pandapower 1.6.0 in this case).
    """
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    POI = Bus(name="POI", vnom=100, is_slack=True)
    B_C3 = Bus(name="B_C3", vnom=10)
    B_MV_M32 = Bus(name="B_MV_M32", vnom=10)
    B_LV_M32 = Bus(name="B_LV_M32", vnom=0.6)

    for b in POI, B_C3, B_MV_M32, B_LV_M32:
        grid.add_bus(b)

    # Create voltage controlled generators (or slack, a.k.a. swing)
    grid.add_controlled_generator(POI, ControlledGenerator(name="Utility"))

    # Create static generators (with fixed power factor)
    grid.add_static_generator(B_LV_M32, StaticGenerator(name="M32", power=4.2+0.0j))

    # Create transformer types
    s = 5 # MVA
    z = 8 # %
    xr = 40
    SS = TransformerType(name="SS",
                         hv_nominal_voltage=100, # kV
                         lv_nominal_voltage=10, # kV
                         nominal_power=s,
                         copper_losses=get_complex(z, xr).real*s*1000/Sbase,
                         iron_losses=1e-20,
                         no_load_current=1e-20,
                         short_circuit_voltage=z)
    grid.add_transformer_type(SS)

    s = 5 # MVA
    z = 6 # %
    xr = 20
    PM = TransformerType(name="PM",
                         hv_nominal_voltage=10, # kV
                         lv_nominal_voltage=0.6, # kV
                         nominal_power=s,
                         copper_losses=get_complex(z, xr).real*s*1000/Sbase,
                         iron_losses=1e-20,
                         no_load_current=1e-20,
                         short_circuit_voltage=z)
    grid.add_transformer_type(PM)

    # Create branches
    X_C3 = Branch(bus_from=POI,
                  bus_to=B_C3,
                  name="X_C3",
                  branch_type=BranchType.Transformer,
                  template=SS)
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

    grid.compile()
    options = PowerFlowOptions(SolverType.LM,
                               verbose=True,
                               initialize_with_existing_solution=True,
                               multi_core=True,
                               control_q=ReactivePowerControlMode.Direct,
                               tolerance=1e-6,
                               max_iter=99)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    approx_losses = round(1000*sum(power_flow.results.losses), 2)
    solution = complex(147.34, 495.42) # Expected solution from GridCal

    #solution = complex(147.36, 495.40) # Solution on ETAP 18.1
    # X_C3 = 6.67 + j266.6 kVA
    # X_M32 = 9.99 + j199.8 kVA
    # C_M32 = 130.7 + j29 kVA

    #solution = complex(146.76, 495.59) # Solution on pandapower 1.6.0
    # X_C3 = 6.507 + j266.710 kVA
    # X_M32 = 9.528 + j199.865 kVA
    # C_M32 = 130.727 + j29.013 kVA

    print("\n=================================================================")
    print(f"Test: {test_name}")
    print("=================================================================\n")
    print(f"Results:  {approx_losses}")
    print(f"Solution: {solution}")
    print()

    print("Buses:")
    for i, b in enumerate(grid.buses):
        print(f" - bus[{i}]: {b}")
    print()

    print("Controlled generators:")
    for g in grid.get_controlled_generators():
        print(f" - Generator {g}: q_min={g.Qmin}pu, q_max={g.Qmax}pu")
    print()

    print("Branches:")
    for b in grid.branches:
        print(f" - {b}:")
        print(f"   R = {round(b.R, 4)} pu")
        print(f"   X = {round(b.X, 4)} pu")
        print(f"   X/R = {round(b.X/b.R, 1)}")
    print()

    print("Transformer types:")
    for t in grid.transformer_types:
        print(f" - {t}: Copper losses={int(t.Copper_losses)}kW, Iron losses={int(t.Iron_losses)}kW, SC voltage={t.Short_circuit_voltage}%")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={1000*round(power_flow.results.losses[i], 3)} kVA")
    print()

    assert approx_losses == solution
