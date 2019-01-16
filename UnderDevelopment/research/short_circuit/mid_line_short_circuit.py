from GridCal.Engine.All import *


def split_branch(branch: Branch, fault_position, r_fault, x_fault):
    """
    Slpit a branch by a given distance
    :param branch: Branch of a circuit
    :param fault_position: per unit distance measured from the "from" bus
    :param r_fault: Fault resistance in p.u.
    :param x_fault: Fault reactance in p.u.
    :return: the two new branches and the mid short circuited bus
    """

    r = branch.R
    x = branch.X
    g = branch.G
    b = branch.B

    # deactivate the current branch
    branch.active = False

    # each of the branches will have "half" of the impedances and "half" of the shunts
    # Bus_from------------Middle_bus------------Bus_To
    #       |------x--------|   (x: distance measured in per unit (0~1)

    middle_bus = Bus()

    # set the bus fault impedance
    middle_bus.Zf = complex(r_fault, x_fault)

    br1 = Branch(bus_from=branch.bus_from,
                 bus_to=middle_bus,
                 r=r * fault_position,
                 x=x * fault_position,
                 g=g * fault_position,
                 b=b * fault_position)

    br2 = Branch(bus_from=middle_bus,
                 bus_to=branch.bus_to,
                 r=r * (1 - fault_position),
                 x=x * (1 - fault_position),
                 g=g * (1 - fault_position),
                 b=b * (1 - fault_position))

    return br1, br2, middle_bus


if __name__ == '__main__':
    main_circuit = MultiCircuit()

    fname = 'IEEE_30.xlsx'
    print('Reading...')
    main_circuit.load_file(fname)
    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)

    # modify the grid by inserting a mid-line short circuit bus
    br1, br2, middle_bus = split_branch(branch=main_circuit.branches[10], fault_position=0.2, r_fault=0, x_fault=0.15)

    main_circuit.add_branch(br1)
    main_circuit.add_branch(br2)
    main_circuit.add_bus(middle_bus)
    sc_bus_index = len(main_circuit.buses) - 1

    ####################################################################################################################
    # PowerFlow
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlow(main_circuit, options)
    power_flow.run()

    print('\n\n', main_circuit.name, ' number of buses:', len(main_circuit.buses))
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sbranch|:', abs(power_flow.results.Sbranch))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())

    ####################################################################################################################
    # Short circuit
    ####################################################################################################################
    print('\n\n')
    print('Short Circuit')
    sc_options = ShortCircuitOptions(bus_index=[sc_bus_index])
    sc = ShortCircuit(main_circuit, sc_options, power_flow.results)
    sc.run()

    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(main_circuit.short_circuit_results.voltage))
    print('\t|Sbranch|:', abs(main_circuit.short_circuit_results.Sbranch))
    print('\t|loading|:', abs(main_circuit.short_circuit_results.loading) * 100)
