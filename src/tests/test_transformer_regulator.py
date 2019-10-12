from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices.branch import Branch, TapChanger
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.generator import Generator
from GridCal.Engine.Devices.static_generator import StaticGenerator
from GridCal.Engine.Devices.transformer import TransformerType
from GridCal.Engine.Devices.types import BranchType
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import \
    PowerFlowOptions, ReactivePowerControlMode, SolverType, TapsControlMode
from GridCal.Engine.Simulations.PowerFlow import PowerFlowDriver

Sbase = 100  # MVA


def complex_impedance(z, XR):
    """
    Returns the complex impedance from z and the X/R ratio.
    """
    z = float(abs(z))
    XR = float(abs(XR))
    real = (z**2/(1+XR**2))**0.5
    try:
        imag = (z**2/(1+1/XR**2))**0.5
    except ZeroDivisionError:
        imag = 0.0
    return complex(real, imag)


def test_gridcal_regulator():
    """
    GridCal test for the new implementation of transformer voltage regulators.
    """
    test_name = "test_gridcal_regulator"
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = Logger()

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
                          P=4.2, Q=0.0)  # MVA (complex)
    M32.bus = B_LV_M32
    grid.add_static_generator(B_LV_M32, M32)

    # Create transformer types
    s = 100  # MVA
    z = 8  # %
    xr = 40
    SS = TransformerType(name="SS",
                         hv_nominal_voltage=100,  # kV
                         lv_nominal_voltage=10,  # kV
                         nominal_power=s,  # MVA
                         copper_losses=complex_impedance(z, xr).real*s*1000/Sbase,  # kW
                         iron_losses=125,  # kW
                         no_load_current=0.5,  # %
                         short_circuit_voltage=z)  # %
    grid.add_transformer_type(SS)

    s = 5  # MVA
    z = 6  # %
    xr = 20
    PM = TransformerType(name="PM",
                         hv_nominal_voltage=10,  # kV
                         lv_nominal_voltage=0.6,  # kV
                         nominal_power=s,  # MVA
                         copper_losses=complex_impedance(z, xr).real*s*1000/Sbase,  # kW
                         iron_losses=6.25,  # kW
                         no_load_current=0.5,  # %
                         short_circuit_voltage=z)  # %
    grid.add_transformer_type(PM)

    # Create branches
    X_C3 = Branch(bus_from=POI,
                  bus_to=B_C3,
                  name="X_C3",
                  branch_type=BranchType.Transformer,
                  template=SS,
                  bus_to_regulated=True,
                  vset=1.05)
    X_C3.tap_changer = TapChanger(taps_up=16, taps_down=16, max_reg=1.1, min_reg=0.9)
    X_C3.tap_changer.set_tap(X_C3.tap_module)
    grid.add_branch(X_C3)

    C_M32 = Branch(bus_from=B_C3,
                   bus_to=B_MV_M32,
                   name="C_M32",
                   r=7.84,
                   x=1.74)
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
                               control_taps=TapsControlMode.Direct,
                               tolerance=1e-6,
                               max_iter=99)

    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    approx_volt = [round(100*abs(v), 1) for v in power_flow.results.voltage]
    solution = [100.0, 105.2, 130.0, 130.1] # Expected solution from GridCal

    print()
    print(f"Test: {test_name}")
    print(f"Results:  {approx_volt}")
    print(f"Solution: {solution}")
    print()

    print("Generators:")
    for g in grid.get_generators():
        print(f" - Generator {g}: q_min={g.Qmin}pu, q_max={g.Qmax}pu")
    print()

    print("Branches:")
    for b in grid.branches:
        print(f" - {b}: R={round(b.R, 4)}pu, X={round(b.X, 4)}pu, X/R={round(b.X/b.R, 1)}, vset={b.vset}")
    print()

    print("Transformer types:")
    for t in grid.transformer_types:
        print(f" - {t}: Copper losses={int(t.Pcu)}kW, Iron losses={int(t.Pfe)}kW, SC voltage={t.Vsc}%")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={round(power_flow.results.losses[i], 3)} MVA")
    print()

    print(f"Voltage settings: {grid.numerical_circuit.vset}")

    equal = True
    for i in range(len(approx_volt)):
        if approx_volt[i] != solution[i]:
            equal = False

    assert equal
