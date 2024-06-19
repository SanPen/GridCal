import json
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as dev


def load_iPA(file_name) -> MultiCircuit:
    """
    Read the nuts' Indra file format
    :param file_name: json file name
    :return: MultiCircuit
    """

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
        bus = dev.Bus(name=str(entry['id']))
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
        bus1 = buses_dict.get(n1_id, None)
        bus2 = buses_dict.get(n2_id, None)

        if tpe == 0:  # Fuente de  Tensión(elemento  Ptheta)

            # pick the bus that is not the earth bus...
            if n1_id == 0:
                bus = bus2
            else:
                bus = bus1

            bus.is_slack = True
            elm = dev.Generator(name='Slack')
            circuit.add_generator(bus, elm)

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

                elm = dev.Line(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x)
                circuit.add_line(elm)

        elif tpe == 2:  # Elemento PQ

            # pick the bus that is not the earth bus...
            if n1_id == 0:
                bus = bus2
            else:
                bus = bus1

            p = entry['P']  # power in MW
            q = entry['Q']
            elm = dev.Load(name=str(identifier), P=p*1e-3, Q=q * 1e-3)
            circuit.add_load(bus, elm)

        elif tpe == 3:  # Elemento  PV
            pass

        elif tpe == 4:  # Reg  de  tensión

            V = entry['Unom']
            Zbase = V * V / circuit.Sbase

            r = entry['R1'] / Zbase
            x = entry['X1'] / Zbase
            elm = dev.Transformer2W(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x)
            circuit.add_transformer2w(elm)

        elif tpe == 5:  # Transformador

            V = entry['Unom']
            Zbase = V * V / circuit.Sbase

            r = entry['R1'] / Zbase
            x = entry['X1'] / Zbase
            elm = dev.Transformer2W(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x)
            circuit.add_transformer2w(elm)

    # return the circuit
    return circuit

