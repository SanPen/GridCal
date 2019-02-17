from GridCal.Engine import *

Sbase = 100  # MVA


def test_tolerance_lf_higher():
    test_name = "test_tolerance_lf_higher"
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    Bus0 = Bus(name="Bus0", vnom=25, is_slack=True)
    Bus1 = Bus(name="Bus1", vnom=25)

    grid.add_bus(Bus0)
    grid.add_bus(Bus1)

    # Create load
    grid.add_load(Bus1, Load(name="Load0", P=1.0, Q=0.4))

    # Create slack bus
    grid.add_generator(Bus0, Generator(name="Utility"))

    # Create cable (r and x should be in pu)
    grid.add_branch(Branch(bus_from=Bus0,
                           bus_to=Bus1,
                           name="Cable1",
                           r=0.01,
                           x=0.05,
                           tolerance=10))

    # Run non-linear power flow
    options = PowerFlowOptions(verbose=True,
                               branch_impedance_tolerance_mode=BranchImpedanceMode.Upper)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    # Check solution
    approx_losses = round(1000 * power_flow.results.losses[0], 3)
    solution = complex(0.128, 0.58)  # Expected solution from GridCal
    # Tested on ETAP 16.1.0 and pandapower

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
    for b in grid.branches:
        print(f" - {b}:")
        print(f"   R = {round(b.R, 4)} pu")
        print(f"   X = {round(b.X, 4)} pu")
        print(f"   X/R = {round(b.X/b.R, 2)}")
    print()

    print("Voltages:")
    for i in range(len(grid.buses)):
        print(
            f" - {grid.buses[i]}: voltage={round(power_flow.results.voltage[i], 3)} pu"
        )
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(
            f" - {grid.branches[i]}: losses={round(power_flow.results.losses[i], 3)} MVA"
        )
    print()

    print("Loadings (power):")
    for i in range(len(grid.branches)):
        print(
            f" - {grid.branches[i]}: loading={round(power_flow.results.Sbranch[i], 3)} MVA"
        )
    print()

    print("Loadings (current):")
    for i in range(len(grid.branches)):
        print(
            f" - {grid.branches[i]}: loading={round(power_flow.results.Ibranch[i], 3)} pu"
        )
    print()

    assert approx_losses == solution


def test_tolerance_lf_lower():
    test_name = "test_tolerance_lf_lower"
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    Bus0 = Bus(name="Bus0", vnom=25, is_slack=True)
    Bus1 = Bus(name="Bus1", vnom=25)

    grid.add_bus(Bus0)
    grid.add_bus(Bus1)

    # Create load
    grid.add_load(Bus1, Load(name="Load0", P=1.0, Q=0.4))

    # Create slack bus
    grid.add_generator(Bus0, Generator(name="Utility"))

    # Create cable (r and x should be in pu)
    grid.add_branch(Branch(bus_from=Bus0,
                           bus_to=Bus1,
                           name="Cable1",
                           r=0.01,
                           x=0.05,
                           tolerance=10))

    # Run non-linear power flow
    options = PowerFlowOptions(verbose=True,
                               branch_impedance_tolerance_mode=BranchImpedanceMode.Lower)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    # Check solution
    approx_losses = round(1000 * power_flow.results.losses[0], 3)
    solution = complex(0.104, 0.58)  # Expected solution from GridCal
    # Tested on ETAP 16.1.0 and pandapower

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
    for b in grid.branches:
        print(f" - {b}:")
        print(f"   R = {round(b.R, 4)} pu")
        print(f"   X = {round(b.X, 4)} pu")
        print(f"   X/R = {round(b.X/b.R, 2)}")
    print()

    print("Voltages:")
    for i in range(len(grid.buses)):
        print(
            f" - {grid.buses[i]}: voltage={round(power_flow.results.voltage[i], 3)} pu"
        )
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(
            f" - {grid.branches[i]}: losses={round(power_flow.results.losses[i], 3)} MVA"
        )
    print()

    print("Loadings (power):")
    for i in range(len(grid.branches)):
        print(
            f" - {grid.branches[i]}: loading={round(power_flow.results.Sbranch[i], 3)} MVA"
        )
    print()

    print("Loadings (current):")
    for i in range(len(grid.branches)):
        print(
            f" - {grid.branches[i]}: loading={round(power_flow.results.Ibranch[i], 3)} pu"
        )
    print()

    assert approx_losses == solution
