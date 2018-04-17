"""
# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
"""
import pandas as pd
import numpy as np
from GridCal.Engine.CalculationEngine import *
import os


def find_between(s, first, last):
    """
    Find sting between two sub-strings
    Args:
        s: Main string
        first: first sub-string
        last: second sub-string
    Example find_between('[Hello]', '[', ']')  -> returns 'Hello'
    Returns:
        String between the first and second sub-strings, if any was found otherwise returns an empty string
    """
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""


def parse_matpower_file_old(filename, export=False):
    """
    Converts a MatPower file to GridCal basic dictionary
    @param filename:
    @return:
    """
    f = open(filename)
    lines = f.readlines()
    f.close()

    keyword = ''

    version = 0
    baseMVA = 0

    strings = dict()
    structures = dict()

    structures_names = ['bus', 'gen', 'branch', 'gencost', 'bus_name']

    bus = list()
    gen = list()
    branch = list()
    gencost = list()
    bus_name = list()

    for line in lines:

        if line[0] == '%':
            pass
        else:
            dotsplit = line.split('.')

            if len(dotsplit) == 2:
                equalsplit = dotsplit[1].strip().split('=')

    #            print("keyword = |", keyword, "|")
                if len(equalsplit) == 2:
                    data = equalsplit[1].replace(";", "").replace("'", "")
                    keyword = equalsplit[0].strip()
                    if keyword == 'version':
                        version = float(data)

                    elif keyword == 'baseMVA':
                        baseMVA = float(data)

            if keyword in structures_names:

                # clean the comments from line: find % and remove from there on

                try:
                    idx = line.index('%')
                    line = line[0:idx-1]
                except:
                    pass

                if keyword in strings.keys():
                    strings[keyword] += line
                else:
                    strings[keyword] = line
            else:
                pass

    # clean strings
    for key in strings.keys():
        string = strings[key]
        if string.find('[') > -1:
            strings[key] = find_between(string, '[', ']').replace('\n', '')
        elif string.find('{') > -1:
            strings[key] = find_between(string, '{', '}').replace('\n', '')

        structures[key] = strings[key].split(';')

    # split the rows
    for key in structures.keys():
        table = structures[key]
        table2 = list()

        for line in table:
            if len(line.strip()) > 0:

                lne = line.split('\t')[1:]

                # for the bus names...
                if len(lne) == 1:
                    lne = lne[0].split()[:-1]
                    if len(lne) == 2:
                        lne = lne[0][1:] + '_' + lne[1]
                    else:
                        lne = lne[0][1:]
                # remove the empty elements from lne
                for i in range(len(lne)-1, -1, -1):
                    if lne[i] == '':
                        lne.pop(i)
                table2.append(lne)

        structures[key] = table2

    bus = np.array(structures['bus'], dtype=np.float)
    branch = np.array(structures['branch'], dtype=np.float)
    gen = np.array(structures['gen'], dtype=np.float)

    if 'gencost' in structures.keys():
        gencost = np.array(structures['gencost'], dtype=np.float)

    # refactor indices: Pass to zero indexing
    bus_dict = dict()
    i = 0
    BIDX = 0
    for bus_i in bus[:, BIDX]:
        bus_dict[bus_i] = i
        bus[i, BIDX] = i
        i += 1

    # replace buses in Branch and gen
    BF = 0
    BT = 1
    rows, cols = np.shape(branch)
    for r in range(rows):
        branch[r, BF] = bus_dict[branch[r, BF]]
        branch[r, BT] = bus_dict[branch[r, BT]]

    rows, cols = np.shape(gen)
    for r in range(rows):
        gen[r, BIDX] = bus_dict[gen[r, BIDX]]

    # Save
    if export:
        gen_headers = ["bus",
                       "Pg",
                       "Qg",
                       "Qmax",
                       "Qmin",
                       "Vg",
                       "mBase",
                       "status",
                       "Pmax",
                       "Pmin",
                       "Pc1",
                       "Pc2",
                       "Qc1min",
                       "Qc1max",
                       "Qc2min",
                       "Qc2max",
                       "ramp_agc",
                       "ramp_10",
                       "ramp_30",
                       "ramp_q",
                       "apf",
                       "MU_PMAX",
                       "MU_PMIN",
                       "MU_QMAX",
                       "MU_QMIN"]

        bus_headers = ["bus_i",
                       "type",
                       "Pd",
                       "Qd",
                       "Gs",
                       "Bs",
                       "area",
                       "Vm",
                       "Va",
                       "baseKV",
                       "zone",
                       "Vmax",
                       "Vmin",
                       "LaM_P",
                       "LaM_Q",
                       "Mu_Vmax",
                       "Mu_Vmin",
                       "Bus_X",
                       "Bus_Y",
                       "Collapsed"]

        branch_headers = ["fbus",  # 0
                          "tbus",
                          "r",
                          "x",
                          "b",
                          "rateA",
                          "rateB",
                          "rateC",
                          "ratio",
                          "angle",  # 9
                          "status",
                          "angmin",
                          "angmax",
                          "Pf",
                          "Qf",
                          "Pt",
                          "Qt",
                          "Mu_Sf",
                          "Mu_St",
                          "Mu_AngMin",  # 19
                          "Mu_AngMax",
                          "Current",
                          "Loading",
                          "Losses",
                          "Original_index"]

        name, file_extension = os.path.splitext(filename)
        writer = pd.ExcelWriter(name+'.xls', engine='xlsxwriter')

        # write conf
        dta = np.zeros((2, 2), dtype=np.object)
        dta[0, 0] = "Property"
        dta[0, 1] = "Value"

        dta[1, 0] = "baseMVA"
        dta[1, 1] = baseMVA
        df = pd.DataFrame(data=dta)
        df.to_excel(writer, index=False, header=False, sheet_name='Conf')

        # write buses
        rows, cols = np.shape(bus)
        df = pd.DataFrame(data=bus, columns=bus_headers[0:cols])
        df.to_excel(writer, index=False, header=True, sheet_name='Bus')

        # write gen
        rows, cols = np.shape(gen)
        df = pd.DataFrame(data=gen, columns=gen_headers[0:cols])
        df.to_excel(writer, index=False, header=True, sheet_name='Gen')

        # write branch
        rows, cols = np.shape(branch)
        df = pd.DataFrame(data=branch, columns=branch_headers[0:cols])
        df.to_excel(writer, index=False, header=True, sheet_name='Branch')

        writer.save()

    structures['bus'] = bus
    structures['gen'] = gen
    structures['branch'] = branch
    structures['baseMVA'] = baseMVA
    structures['version'] = version

    return structures


def txt2mat(txt, line_splitter=';', col_splitter='\t', to_float=True):
    """

    Args:
        txt:
        line_splitter:
        col_splitter:

    Returns:

    """
    lines = txt.strip().split(line_splitter)
    del lines[-1]
    nrows = len(lines)

    arr = None

    for i, line in enumerate(lines):
        vec = line.strip().split(col_splitter)

        if arr is None:
            ncols = len(vec)
            if to_float:
                arr = np.zeros((nrows, ncols))
            else:
                arr = np.zeros((nrows, ncols), dtype=np.object)
        # print('VEC:', vec)
        for j, val in enumerate(vec):
            # print('[', val, ']')
            if to_float:
                arr[i, j] = float(val)
            else:
                arr[i, j] = val.strip().replace("'", "")

    return np.array(arr)


def interpret_data_v1(circuit, data):
    """
    Pass the loaded table-like data to the  structures
    @param data: Data dictionary
    @return:
    """

    circuit.clear()

    # time profile
    if 'master_time' in data.keys():
        master_time_array = data['master_time']
    else:
        master_time_array = None

    import GridCal.Engine.Importers.BusDefinitions as e
    # Buses
    table = data['bus']
    buses_dict = dict()
    n = len(table)

    # load profiles
    if 'Lprof' in data.keys():
        Sprof = data['Lprof'] + 1j * data['LprofQ']
        are_load_prfiles = True
        print('There are load profiles')
    else:
        are_load_prfiles = False

    if 'bus_names' in data.keys():
        names = data['bus_names']
    else:
        names = ['bus ' + str(i) for i in range(n)]

    # Buses
    bus_idx_dict = dict()
    for i in range(n):
        # Create bus
        bus = Bus(name=names[i],
                  vnom=table[i, e.BASE_KV],
                  vmax=table[i, e.VMAX],
                  vmin=table[i, e.VMIN])

        # store the given bus index in relation to its real index in the table for later
        bus_idx_dict[table[i, e.BUS_I]] = i

        # determine if the bus is set as slack manually
        tpe = table[i, e.BUS_TYPE]
        if tpe == e.REF:
            bus.is_slack = True
        else:
            bus.is_slack = False

        # Add the load
        if table[i, e.PD] != 0 or table[i, e.QD] != 0:
            load = Load(power=table[i, e.PD] + 1j * table[i, e.QD])
            load.bus = bus
            if are_load_prfiles:  # set the profile
                load.Sprof = pd.DataFrame(data=Sprof[:, i],
                                          index=master_time_array,
                                          columns=['Load@' + names[i]])
            bus.loads.append(load)

        # Add the shunt
        if table[i, e.GS] != 0 or table[i, e.BS] != 0:
            shunt = Shunt(admittance=table[i, e.GS] + 1j * table[i, e.BS])
            shunt.bus = bus
            bus.shunts.append(shunt)

        # Add the bus to the circuit buses
        circuit.add_bus(bus)

    import GridCal.Engine.Importers.GenDefinitions as e
    # Generators
    table = data['gen']
    n = len(table)
    # load profiles
    if 'Gprof' in data.keys():
        Gprof = data['Gprof']
        are_gen_prfiles = True
        print('There are gen profiles')
    else:
        are_gen_prfiles = False

    if 'gen_names' in data.keys():
        names = data['gen_names']
    else:
        names = ['gen ' + str(i) for i in range(n)]
    for i in range(len(table)):
        bus_idx = bus_idx_dict[int(table[i, e.GEN_BUS])]
        gen = ControlledGenerator(name=names[i],
                                  active_power=table[i, e.PG],
                                  voltage_module=table[i, e.VG],
                                  Qmax=table[i, e.QMAX],
                                  Qmin=table[i, e.QMIN])
        if are_gen_prfiles:
            gen.create_P_profile(index=master_time_array, arr=Gprof[:, i])
            # gen.Pprof = pd.DataFrame(data=Gprof[:, i],
            #                          index=master_time_array,
            #                          columns=['Gen@' + names[i]])

        # Add the generator to the bus
        gen.bus = circuit.buses[bus_idx]
        circuit.buses[bus_idx].controlled_generators.append(gen)

    import GridCal.Engine.Importers.BranchDefinitions as e
    # Branches
    table = data['branch']
    n = len(table)
    if 'branch_names' in data.keys():
        names = data['branch_names']
    else:
        names = ['branch ' + str(i) for i in range(n)]
    for i in range(len(table)):
        f = circuit.buses[bus_idx_dict[int(table[i, e.F_BUS])]]
        t = circuit.buses[bus_idx_dict[int(table[i, e.T_BUS])]]
        branch = Branch(bus_from=f,
                        bus_to=t,
                        name=names[i],
                        r=table[i, e.BR_R],
                        x=table[i, e.BR_X],
                        g=0,
                        b=table[i, e.BR_B],
                        rate=table[i, e.RATE_A],
                        tap=table[i, e.TAP],
                        shift_angle=table[i, e.SHIFT],
                        active=bool(table[i, e.BR_STATUS]))

        circuit.add_branch(branch)

    # add the profiles
    if master_time_array is not None:

        circuit.format_profiles(master_time_array)

        table = data['bus']
        for i in range(len(table)):
            if are_load_prfiles and len(circuit.buses[i].loads) > 0:  # set the profile
                circuit.buses[i].loads[0].Sprof = pd.DataFrame(data=Sprof[:, i],
                                                               index=master_time_array,
                                                               columns=['Load@' + names[i]])
        import GridCal.Engine.Importers.GenDefinitions as e
        table = data['gen']
        for i in range(len(table)):
            bus_idx = int(table[i, e.GEN_BUS]) - 1
            if are_gen_prfiles:
                circuit.buses[bus_idx].controlled_generators[0].Pprof = pd.DataFrame(data=Gprof[:, i],
                                                                                     index=master_time_array,
                                                                                     columns=['Gen@' + names[i]])
    print('Interpreted.')
    return circuit


def parse_matpower_file(filename, export=False):
    """

    Args:
        filename:
        export:

    Returns:

    """

    # open the file as text
    with open(filename, 'r') as myfile:
        text = myfile.read().replace('\n', '')

    # split the file into its case variables (the case variables always start with 'mpc.')
    chunks = text.split('mpc.')

    # declare circuit
    circuit = MultiCircuit()

    data = dict()

    # further process the loaded text
    for chunk in chunks:
        if chunk.startswith("baseMVA"):
            v = find_between(chunk, '=', ';')
            circuit.Sbase = float(v)

        elif chunk.startswith("bus"):
            if chunk.startswith("bus_name"):
                v = txt2mat(find_between(chunk, '{', '}'), line_splitter=';', to_float=False)
                v = np.ndarray.flatten(v)
                data['bus_names'] = v
            else:
                data['bus'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif chunk.startswith("gencost"):
            data['gen_cost'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif chunk.startswith("gen"):
            data['gen'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif chunk.startswith("branch"):
            data['branch'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

    circuit = interpret_data_v1(circuit, data)
    # print(data)

    return circuit

