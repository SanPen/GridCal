# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Substation import Bus
from GridCalEngine.Devices.Injections.generator import Generator
from GridCalEngine.Devices.Injections.static_generator import StaticGenerator
from GridCalEngine.Devices.Branches.transformer import TransformerType, Transformer2W
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver


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


def test_basic():
    """
    Basic GridCal test, also useful for a basic tutorial. In this case the
    magnetizing branch of the transformers is neglected by inputting 1e-20
    excitation current and iron core losses.
    The results are identical to ETAP's, which always uses this assumption in
    balanced load flow calculations.
    """
    test_name = "test_basic"
    grid = MultiCircuit(name=test_name)
    S_base = 100  # MVA
    grid.Sbase = S_base
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
                          P=4.2,  # MW
                          Q=0.0j)  # MVAr
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
                         copper_losses=complex_impedance(z, xr).real * s * 1000 / S_base,
                         iron_losses=1e-20,
                         no_load_current=1e-20,
                         short_circuit_voltage=z)
    grid.add_transformer_type(SS)

    s = 5  # MVA
    z = 6  # %
    xr = 20
    PM = TransformerType(name="PM",
                         hv_nominal_voltage=10,  # kV
                         lv_nominal_voltage=0.6,  # kV
                         nominal_power=s,
                         copper_losses=complex_impedance(z, xr).real * s * 1000 / S_base,
                         iron_losses=1e-20,
                         no_load_current=1e-20,
                         short_circuit_voltage=z)
    grid.add_transformer_type(PM)

    # Create Branches
    X_C3 = Transformer2W(bus_from=POI,
                         bus_to=B_C3,
                         name="X_C3",
                         template=SS)
    grid.add_transformer2w(X_C3)

    C_M32 = Transformer2W(bus_from=B_C3,
                          bus_to=B_MV_M32,
                          name="C_M32",
                          r=0.784,
                          x=0.174)
    grid.add_transformer2w(C_M32)

    X_M32 = Transformer2W(bus_from=B_MV_M32,
                          bus_to=B_LV_M32,
                          name="X_M32",
                          template=PM)
    grid.add_transformer2w(X_M32)

    # Apply templates (device types)
    grid.apply_all_branch_types()

    print("Buses:")
    for i, b in enumerate(grid.buses):
        print(f" - bus[{i}]: {b}")
    print()

    options = PowerFlowOptions(SolverType.NR,
                               verbose=True,
                               initialize_with_existing_solution=True,
                               multi_core=True,
                               control_q=ReactivePowerControlMode.Direct,
                               tolerance=1e-6,
                               max_iter=99)

    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    approx_volt = [round(100 * abs(v), 1) for v in power_flow.results.voltage]
    solution = [100.0, 99.6, 102.7, 102.9]  # Expected solution from GridCal and ETAP 16.1.0, for reference

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
    branches = grid.get_branches()
    for b in branches:
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
    for i in range(len(branches)):
        print(f" - {branches[i]}: losses={1000*round(power_flow.results.losses[i], 3)} kVA")
    print()

    equal = True
    for i in range(len(approx_volt)):
        if approx_volt[i] != solution[i]:
            equal = False

    assert equal


def test_gridcal_basic_pi():
    """
    Basic GridCal test, also useful for a basic tutorial. In this case the
    magnetizing branch of the transformers is considered.
    """
    Sbase = 100  # MVA
    test_name = "test_basic_pi"
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
                          P=4.2,  # MW
                          Q=0.0j)  # MVAR
    M32.bus = B_LV_M32
    grid.add_static_generator(B_LV_M32, M32)

    # Create transformer types
    s = 5 # MVA
    z = 8 # %
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

    s = 5 # MVA
    z = 6 # %
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

    # Create Branches
    X_C3 = Transformer2W(bus_from=POI,
                         bus_to=B_C3,
                         name="X_C3",
                         template=SS)
    grid.add_transformer2w(X_C3)

    C_M32 = Transformer2W(bus_from=B_C3,
                          bus_to=B_MV_M32,
                          name="C_M32",
                          r=0.784,
                          x=0.174)
    grid.add_transformer2w(C_M32)

    X_M32 = Transformer2W(bus_from=B_MV_M32,
                          bus_to=B_LV_M32,
                          name="X_M32",
                          template=PM)
    grid.add_transformer2w(X_M32)

    # Apply templates (device types)
    grid.apply_all_branch_types()

    print("Buses:")
    for i, b in enumerate(grid.buses):
        print(f" - bus[{i}]: {b}")
    print()

    options = PowerFlowOptions(SolverType.NR,
                               verbose=True,
                               initialize_with_existing_solution=True,
                               multi_core=True,
                               control_q=ReactivePowerControlMode.Direct,
                               tolerance=1e-6,
                               max_iter=99)

    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    approx_volt = [round(100*abs(v), 1) for v in power_flow.results.voltage]
    solution = [100.0, 99.5, 102.7, 102.8]  # Expected solution from GridCal
    etap_sol = [100.0, 99.6, 102.7, 102.9]  # ETAP 16.1.0, for reference (ignores magnetizing branch)

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
    branches = grid.get_branches()
    for b in branches:
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
    for i in range(len(branches)):
        print(f" - {branches[i]}: losses={1000*round(power_flow.results.losses[i], 3)} kVA")
    print()

    equal = True
    for i in range(len(approx_volt)):
        if approx_volt[i] != solution[i]:
            equal = False

    assert equal


if __name__ == '__main__':

    test_basic()

    test_gridcal_basic_pi()
