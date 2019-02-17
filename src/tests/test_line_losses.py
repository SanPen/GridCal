from GridCal.Engine import *

Sbase = 100  # MVA


def test_line_losses_1():
    """
    Basic line losses test.
    """
    test_name = "test_line_losses_1"
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
    grid.add_branch(Branch(bus_from=Bus0, bus_to=Bus1, name="Cable1", r=0.01, x=0.05))

    # Run non-linear load flow
    options = PowerFlowOptions(verbose=True)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    # Check solution
    approx_losses = round(1000*power_flow.results.losses[0], 3)
    solution = complex(0.116, 0.58)  # Expected solution from GridCal
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
        print(f" - {grid.buses[i]}: voltage={round(power_flow.results.voltage[i], 3)} pu")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={round(power_flow.results.losses[i], 3)} MVA")
    print()

    print("Loadings (power):")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: loading={round(power_flow.results.Sbranch[i], 3)} MVA")
    print()

    print("Loadings (current):")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: loading={round(power_flow.results.Ibranch[i], 3)} pu")
    print()

    assert approx_losses == solution


def test_line_losses_2():
    """
    Basic line losses test, with the impedance split into 2 series branches.
    """
    test_name = "test_line_losses_2"
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    Bus0 = Bus(name="Bus0", vnom=25, is_slack=True)
    Bus1 = Bus(name="Bus1", vnom=25)
    Bus2 = Bus(name="Bus1", vnom=25)

    for b in Bus0, Bus1, Bus2:
        grid.add_bus(b)

    # Create load
    grid.add_load(Bus2, Load(name="Load0", P=1.0, Q=0.4))

    # Create slack bus
    grid.add_generator(Bus0, Generator(name="Utility"))

    # Create cable (r and x should be in pu)
    grid.add_branch(Branch(bus_from=Bus0, bus_to=Bus1, name="Cable0", r=0.005, x=0.025))
    grid.add_branch(Branch(bus_from=Bus1, bus_to=Bus2, name="Cable1", r=0.005, x=0.025))

    # Run non-linear load flow
    options = PowerFlowOptions(verbose=True)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    # Check solution
    approx_losses = round(1000*sum(power_flow.results.losses), 3)
    solution = complex(0.116, 0.58)  # Expected solution from GridCal
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
        print(f" - {grid.buses[i]}: voltage={round(power_flow.results.voltage[i], 3)} pu")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={round(power_flow.results.losses[i], 3)} MVA")
    print()

    print("Loadings (power):")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: loading={round(power_flow.results.Sbranch[i], 3)} MVA")
    print()

    print("Loadings (current):")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: loading={round(power_flow.results.Ibranch[i], 3)} pu")
    print()

    assert approx_losses == solution


def test_line_losses_3():
    """
    Basic line losses test, with the impedance split into 2 parallel branches.
    """
    test_name = "test_line_losses_3"
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    Bus0 = Bus(name="Bus0", vnom=25, is_slack=True)
    Bus1 = Bus(name="Bus1", vnom=25)

    for b in Bus0, Bus1:
        grid.add_bus(b)

    # Create load
    grid.add_load(Bus1, Load(name="Load0", P=1.0, Q=0.4))

    # Create slack bus
    grid.add_generator(Bus0, Generator(name="Utility"))

    # Create cable (r and x should be in pu)
    grid.add_branch(Branch(bus_from=Bus0, bus_to=Bus1, name="Cable0", r=0.02, x=0.1))
    grid.add_branch(Branch(bus_from=Bus0, bus_to=Bus1, name="Cable1", r=0.02, x=0.1))

    # Run non-linear load flow
    options = PowerFlowOptions(verbose=True)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    # Check solution
    approx_losses = round(1000*sum(power_flow.results.losses), 3)
    solution = complex(0.116, 0.58)  # Expected solution from GridCal
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
        print(f" - {grid.buses[i]}: voltage={round(power_flow.results.voltage[i], 3)} pu")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={round(power_flow.results.losses[i], 3)} MVA")
    print()

    print("Loadings (power):")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: loading={round(power_flow.results.Sbranch[i], 3)} MVA")
    print()

    print("Loadings (current):")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: loading={round(power_flow.results.Ibranch[i], 3)} pu")
    print()

    assert approx_losses == solution
