import os
import VeraGridEngine.api as gce
import VeraGridEngine.Devices as dev
import VeraGrid.templates as templs
import VeraGridEngine.Topology.topology as tp


def open_dummy_grid():
    # fname = os.path.join('C:/Users/J/Downloads/temp_tr1.gridcal')
    # fname = os.path.join('C:/Users/J/Downloads/temp_tr1_invested.gridcal')
    # fname = os.path.join('C:/Users/J/Downloads/temp_tr2.gridcal')
    fname = os.path.join('C:/Users/J/Downloads/vg1.gridcal')
    main_circuit = gce.open_file(fname)
    results = gce.power_flow(main_circuit)
    print(results.voltage)

    abc = main_circuit.get_branch_active_time_array()
    # tp.find_different_states(states_array=abc[main_circuit.time_indices])

    return main_circuit


def process_dummy_grid():
    fname = os.path.join('C:/Users/J/Downloads/temp_tr1.gridcal')
    main_circuit = gce.open_file(fname)
    results = gce.power_flow(main_circuit)
    print(results.voltage)

    my_tr = main_circuit.transformers2w[0]

    inv_group = dev.InvestmentsGroup(name='Ig0')
    investment1 = dev.Investment(name='Investment 1x', group=inv_group, device=my_tr)
    main_circuit.add_investment(investment1)
    main_circuit.add_investments_group(inv_group)
    gce.save_file(main_circuit, 'C:/Users/J/Downloads/temp_tr1_invested.gridcal')
    return None


def create_dummy_grid():
    grid = gce.MultiCircuit()

    bus1 = gce.Bus(name='Bus1', Vnom=20)
    bus2 = gce.Bus(name='Bus2', Vnom=20)
    grid.add_bus(bus1)
    grid.add_bus(bus2)
    tr1 = gce.Transformer2W(bus_from=bus1, bus_to=bus2)
    grid.add_transformer2w(tr1)

    grid.transformer_types = templs.get_transformer_catalogue()
    grid.underground_cable_types = templs.get_cables_catalogue()
    grid.circuit_wire_types = templs.get_wires_catalogue()
    grid.sequence_line_types = templs.get_sequence_lines_catalogue()

    return grid


if __name__ == "__main__":
    open_dummy_grid()
    # pp = process_dummy_grid()
    # gg = create_dummy_grid()

