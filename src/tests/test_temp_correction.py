# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from pytest import approx

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices import *
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions, PowerFlowDriver

Sbase = 100  # MVA


def test_cable_temp():
    B_C3 = Bus(name="B_C3",
               Vnom=10)  # kV

    B_MV_M32 = Bus(name="B_MV_M32",
                   Vnom=10)  # kV

    cable = Branch(bus_from=B_C3,
                   bus_to=B_MV_M32,
                   name="C_M32",
                   r=0.784,
                   x=0.174,
                   temp_base=20,  # °C
                   temp_oper=90,  # °C
                   alpha=0.00323)  # Copper

    assert approx(cable.R_corrected) == 0.961262


def test_same_temp():
    B_C3 = Bus(name="B_C3",
               Vnom=10)  # kV

    B_MV_M32 = Bus(name="B_MV_M32",
                   Vnom=10)  # kV

    cable = Line(bus_from=B_C3,
                 bus_to=B_MV_M32,
                 name="C_M32",
                 r=0.784,
                 x=0.174,
                 temp_base=20,  # °C
                 temp_oper=20,  # °C
                 alpha=0.00323)  # Copper

    assert cable.R_corrected == 0.784


def test_corr_line_losses():
    test_name = "test_corr_line_losses"

    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = Logger()

    # Create buses
    Bus0 = Bus(name="Bus0", Vnom=10, is_slack=True)
    Bus1 = Bus(name="Bus1", Vnom=10)

    grid.add_bus(Bus0)
    grid.add_bus(Bus1)

    # Create load
    grid.add_load(Bus1, Load(name="Load0", P=1.0, Q=0.4))

    # Create slack bus
    grid.add_generator(Bus0, Generator(name="Utility"))

    # Create cable
    cable = Line(bus_from=Bus0,
                 bus_to=Bus1,
                 name="Cable0",
                 r=0.784,
                 x=0.174,
                 temp_base=20,  # °C
                 temp_oper=90,  # °C
                 alpha=0.00323)  # Copper

    grid.add_line(cable)

    options = PowerFlowOptions(verbose=True,
                               apply_temperature_correction=True)

    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    # Check solution
    approx_losses = round(power_flow.results.losses[0], 3)
    solution = complex(0.011, 0.002)  # Expected solution from VeraGrid
                                      # Tested on ETAP 16.1.0

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

    print("Branches:")
    for b in grid.lines:
        print(f" - {b}:")
        print(f"   R = {round(b.R, 4)} pu")
        print(f"   X = {round(b.X, 4)} pu")
        print(f"   X/R = {round(b.X/b.R, 2)}")
    print()

    print("Voltages:")
    for i in range(len(grid.buses)):
        print(f" - {grid.buses[i]}: voltage={round(power_flow.results.voltage[i], 3)} pu")
    print()

    print("Losses:")
    for i in range(len(grid.lines)):
        print(f" - {grid.lines[i]}: losses={round(power_flow.results.losses[i], 3)} MVA")
    print()

    print("Loadings (power):")
    for i in range(len(grid.lines)):
        print(f" - {grid.lines[i]}: loading={round(power_flow.results.Sf[i], 3)} MVA")
    print()

    print("Loadings (current):")
    for i in range(len(grid.lines)):
        print(f" - {grid.lines[i]}: loading={round(power_flow.results.If[i], 3)} pu")
    print()

    assert approx_losses == solution
