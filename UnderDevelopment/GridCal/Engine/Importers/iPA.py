import json

from GridCal.Engine.CalculationEngine import MultiCircuit, Bus, Branch, Load, ControlledGenerator, Battery, BranchType


def load_iPA(file_name):

    circuit = MultiCircuit()

    with open(file_name) as json_file:
        data = json.load(json_file)

    # elements dictionaries
    xfrm_dict = {entry['IdEnRed']: entry for entry in data['Transformadores']}

    # nodes_dict = {entry['id']: entry for entry in data['Nudos']}
    nodes_dict = dict()
    buses_dict = dict()
    for entry in data['Nudos']:
        nodes_dict[entry['id']] = entry
        bus = Bus(name=str(entry['id']))
        buses_dict[entry['id']] = bus
        if entry['id'] > 0:  # omit the node 0 because it is the "earth node"...
            circuit.add_bus(bus)

    gen_dict = {entry['IdEnRed']: entry for entry in data['Generadores']}

    load_dict = {entry['IdEnRed']: entry for entry in data['Consumos']}

    sw_dict = {entry['IdEnRed']: entry for entry in data['Interruptores']}

    # main grid
    vector_red = data['Red']

    '''
    {'id': 0, 
    'Tipo': 1, 
    'E': 0, 
    'EFase': 0, 
    'Tomas': 0, 
    'R1': 1e-05, 
    'X1': 1e-05, 
    'R0': 1e-05, 
    'X0': 1e-05, 
    'RN': 1e-05, 
    'XN': 1e-05, 
    'P': 0, 
    'Q': 0, 
    'Nudo1': 2410, 
    'Nudo2': 2403, 
    'Carga_Max': -1, 
    'ClassID': 1090, 
    'ClassMEMBER': 98076366, 
    'Conf': 'abc', 
    'LineaMT': '2030:98075347', 
    'Unom': 15.0}
    '''

    for entry in vector_red:

        # pick the general attributes
        identifier = entry['id']
        tpe = entry['Tipo']
        n1_id = entry['Nudo1']
        n2_id = entry['Nudo2']

        # get the Bus objects associated to the bus indices
        if n1_id in buses_dict.keys():
            bus1 = buses_dict[n1_id]
        if n2_id in buses_dict.keys():
            bus2 = buses_dict[n2_id]

        if tpe == 0:  # Fuente de  Tensión(elemento  Ptheta)

            # pick the bus that is not the earth bus...
            if n1_id == 0:
                bus = bus2
            else:
                bus = bus1

            bus.is_slack = True
            elm = ControlledGenerator(name='Slack')
            circuit.add_controlled_generator(bus, elm)

        elif tpe == 1:  # Elemento impedancia(lineas)

            V = entry['Unom']
            Zbase = V * V / circuit.Sbase

            if identifier in load_dict.keys():
                # load!!!
                print('Load found in lines: WTF?')
            else:
                # line!!!
                r = entry['R1'] / Zbase
                x = entry['X1'] / Zbase

                if r > 1e-5:
                    branch_type = BranchType.Line
                else:
                    # mark as "generic branch" the branches with very low resistance
                    branch_type = BranchType.Branch

                elm = Branch(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x, branch_type=branch_type)
                circuit.add_branch(elm)

        elif tpe == 2:  # Elemento PQ

            # pick the bus that is not the earth bus...
            if n1_id == 0:
                bus = bus2
            else:
                bus = bus1

            p = entry['P']  # power in MW
            q = entry['Q']
            elm = Load(name=str(identifier), power=complex(p, q) * 1e-3)
            circuit.add_load(bus, elm)

        elif tpe == 3:  # Elemento  PV
            pass

        elif tpe == 4:  # Reg  de  tensión

            V = entry['Unom']
            Zbase = V * V / circuit.Sbase

            r = entry['R1'] / Zbase
            x = entry['X1'] / Zbase
            elm = Branch(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x, branch_type=BranchType.Transformer)
            circuit.add_branch(elm)

        elif tpe == 5:  # Transformador

            V = entry['Unom']
            Zbase = V * V / circuit.Sbase

            r = entry['R1'] / Zbase
            x = entry['X1'] / Zbase
            elm = Branch(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x, branch_type=BranchType.Transformer)
            circuit.add_branch(elm)

    # return the circuit
    return circuit


if __name__ == '__main__':

    fname = 'Export_sensible_v15_modif.json'

    circuit = load_iPA(file_name=fname)

    circuit.save_excel(fname + '_assuming_kW.xlsx')

    pass
