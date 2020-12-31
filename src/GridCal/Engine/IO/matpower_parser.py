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
import os

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *


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
    lines = txt.strip().split('\n')
    # del lines[-1]

    # preprocess lines (remove the comments)
    lines2 = list()
    for i, line in enumerate(lines):
        if line.lstrip()[0] == '%':
            print('skipping', line)
        else:
            lines2.append(line)

    # convert the lines to data
    nrows = len(lines2)
    arr = None
    for i, line in enumerate(lines2):

        if ';' in line:
            line2 = line.split(';')[0]
        else:
            line2 = line

        vec = line2.strip().split()

        # declare the container array based on the first line
        if arr is None:
            ncols = len(vec)
            if to_float:
                arr = np.zeros((nrows, ncols))
            else:
                arr = np.zeros((nrows, ncols), dtype=np.object)

        # fill-in the data
        for j, val in enumerate(vec):
            if to_float:
                arr[i, j] = float(val)
            else:
                arr[i, j] = val.strip().replace("'", "")

    return np.array(arr)


def interpret_data_v1(circuit: MultiCircuit, data) -> MultiCircuit:
    """
    Pass the loaded table-like data to the  structures
    :param circuit:
    :param data: Data dictionary
    :return:
    """

    circuit.clear()

    # time profile
    if 'master_time' in data.keys():
        master_time_array = data['master_time']
    else:
        master_time_array = None

    # areas
    area_idx_dict = dict()
    if 'areas' in data.keys():
        table = data['areas']

        if table.shape[0] > 0:
            # if there are areas declared, clean the default areas
            circuit.areas = list()

        for i in range(table.shape[0]):
            area_idx = int(table[i, 0])
            area_ref_bus_idx = table[i, 1]
            a = Area(name='Area ' + str(area_idx),
                     code=str(area_idx))
            area_idx_dict[area_idx] = (a, area_ref_bus_idx)
            circuit.add_area(a)

            if i == 0:
                # set the default area
                circuit.default_area = circuit.areas[0]

    import GridCal.Engine.IO.matpower_bus_definitions as e
    # Buses
    table = data['bus']

    n = table.shape[0]

    # load profiles
    if 'Lprof' in data.keys():
        Pprof = data['Lprof']
        Qprof = data['LprofQ']
        are_load_prfiles = True
        print('There are load profiles')
    else:
        are_load_prfiles = False

    if 'bus_names' in data.keys():
        names = data['bus_names']
    else:
        names = ['bus ' + str(int(table[i, e.BUS_I])) for i in range(n)]

    # Buses
    bus_idx_dict = dict()
    for i in range(n):
        # Create bus
        area_idx = int(table[i, e.BUS_AREA])
        bus_idx = int(table[i, e.BUS_I])
        is_slack = False

        if area_idx in area_idx_dict.keys():
            area, ref_idx = area_idx_dict[area_idx]
            if ref_idx == bus_idx:
                is_slack = True
        else:
            area = circuit.default_area

        code = str(bus_idx)

        bus = Bus(name=names[i],
                  code=code,
                  vnom=table[i, e.BASE_KV],
                  vmax=table[i, e.VMAX],
                  vmin=table[i, e.VMIN],
                  area=area,
                  is_slack=is_slack)

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
            load = Load(P=table[i, e.PD], Q=table[i, e.QD])
            load.bus = bus
            bus.loads.append(load)

        # Add the shunt
        if table[i, e.GS] != 0 or table[i, e.BS] != 0:
            shunt = Shunt(G=table[i, e.GS], B=table[i, e.BS])
            shunt.bus = bus
            bus.shunts.append(shunt)

        # Add the bus to the circuit buses
        circuit.add_bus(bus)

    import GridCal.Engine.IO.matpower_gen_definitions as e
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
        gen = Generator(name=names[i],
                        active_power=table[i, e.PG],
                        voltage_module=table[i, e.VG],
                        Qmax=table[i, e.QMAX],
                        Qmin=table[i, e.QMIN])

        # Add the generator to the bus
        gen.bus = circuit.buses[bus_idx]
        circuit.buses[bus_idx].controlled_generators.append(gen)

    import GridCal.Engine.IO.matpower_branch_definitions as e
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

        if table.shape[1] == 37:  # FUBM model

            # converter type (I, II, III)
            matpower_converter_mode = table[i, e.CONV_A]

            if matpower_converter_mode > 0:  # it is a converter

                # set the from bus as a DC bus
                # this is by design of the matpower FUBM model,
                # if it is a converter,
                # the DC bus is always the "from" bus
                f.is_dc = True

                # determine the converter control mode
                Pfset = table[i, e.PF]
                Ptset = table[i, e.PT]
                Vac_set = table[i, e.VT_SET]
                Vdc_set = table[i, e.VF_SET]
                Qfset = table[i, e.QF]
                Qtset = table[i, e.QT]
                m = table[i, e.TAP] if table[i, e.TAP] > 0 else 1.0

                if matpower_converter_mode == 1:

                    if Pfset != 0.0:

                        if Qtset != 0.0:
                            control_mode = ConverterControlType.type_I_2

                        elif Vac_set != 0.0:
                            control_mode = ConverterControlType.type_I_3

                        else:
                            control_mode = ConverterControlType.type_I_1

                    else:
                        control_mode = ConverterControlType.type_0_free

                elif matpower_converter_mode == 2:

                    if Vac_set == 0.0:
                        control_mode = ConverterControlType.type_II_4
                    else:
                        control_mode = ConverterControlType.type_II_5

                elif matpower_converter_mode == 3:
                    control_mode = ConverterControlType.type_III_6

                elif matpower_converter_mode == 4:
                    control_mode = ConverterControlType.type_III_7

                else:
                    control_mode = ConverterControlType.type_0_free

                branch = VSC(bus_from=f,
                             bus_to=t,
                             name='VSC' + str(len(circuit.vsc_devices) + 1),
                             active=bool(table[i, e.BR_STATUS]),
                             r1=table[i, e.BR_R],
                             x1=table[i, e.BR_X],
                             m=m,
                             m_max=table[i, e.MA_MAX],
                             m_min=table[i, e.MA_MIN],
                             theta=table[i, e.SHIFT],
                             theta_max=np.deg2rad(table[i, e.ANGMAX]),
                             theta_min=np.deg2rad(table[i, e.ANGMIN]),
                             G0=table[i, e.GSW],
                             Beq=table[i, e.BEQ],
                             Beq_max=table[i, e.BEQ_MAX],
                             Beq_min=table[i, e.BEQ_MIN],
                             rate=max(table[i, [e.RATE_A, e.RATE_B, e.RATE_C]]),
                             kdp=table[i, e.KDP],
                             k=table[i, e.K2],
                             control_mode=control_mode,
                             Pfset=Pfset,
                             Qfset=Qfset,
                             Vac_set=Vac_set if Vac_set > 0 else 1.0,
                             Vdc_set=Vdc_set if Vdc_set > 0 else 1.0,
                             alpha1=table[i, e.ALPHA1],
                             alpha2=table[i, e.ALPHA2],
                             alpha3=table[i, e.ALPHA3])
                circuit.add_vsc(branch)

            else:

                if f.Vnom != t.Vnom or (table[i, e.TAP] != 1.0 and table[i, e.TAP] != 0) or table[i, e.SHIFT] != 0.0:

                    branch = Transformer2W(bus_from=f,
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
                    circuit.add_transformer2w(branch)

                else:
                    branch = Line(bus_from=f,
                                  bus_to=t,
                                  name=names[i],
                                  r=table[i, e.BR_R],
                                  x=table[i, e.BR_X],
                                  b=table[i, e.BR_B],
                                  rate=table[i, e.RATE_A],
                                  active=bool(table[i, e.BR_STATUS]))
                    circuit.add_line(branch)

        else:

            if f.Vnom != t.Vnom or (table[i, e.TAP] != 1.0 and table[i, e.TAP] != 0) or table[i, e.SHIFT] != 0.0:

                branch = Transformer2W(bus_from=f,
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
                circuit.add_transformer2w(branch)

            else:
                branch = Line(bus_from=f,
                              bus_to=t,
                              name=names[i],
                              r=table[i, e.BR_R],
                              x=table[i, e.BR_X],
                              b=table[i, e.BR_B],
                              rate=table[i, e.RATE_A],
                              active=bool(table[i, e.BR_STATUS]))
                circuit.add_line(branch)

    # convert normal lines into DC-lines if needed
    for line in circuit.lines:

        if line.bus_to.is_dc and line.bus_from.is_dc:
            dc_line = DcLine(bus_from=line.bus_from,
                             bus_to=line.bus_to,
                             name=line.name,
                             active=line.active,
                             rate=line.rate,
                             r=line.R,
                             active_prof=line.active_prof,
                             rate_prof=line.rate_prof)

            # add device to the circuit
            circuit.add_dc_line(dc_line)

            # delete the line from the circuit
            circuit.delete_line(line)

    # add the profiles
    if master_time_array is not None:
        circuit.format_profiles(master_time_array)

    return circuit


def parse_matpower_file(filename, export=False) -> MultiCircuit:
    """

    Args:
        filename:
        export:

    Returns:

    """

    # open the file as text
    with open(filename, 'r') as myfile:
        text = myfile.read() #.replace('\n', '')

    # split the file into its case variables (the case variables always start with 'mpc.')
    chunks = text.split('mpc.')

    # declare circuit
    circuit = MultiCircuit()

    data = dict()

    # further process the loaded text
    for chunk in chunks:

        vals = chunk.split('=')
        key = vals[0].strip()

        if key == "baseMVA":
            v = find_between(chunk, '=', ';')
            circuit.Sbase = float(v)

        elif key == "bus":
            if chunk.startswith("bus_name"):
                v = txt2mat(find_between(chunk, '{', '}'), line_splitter=';', to_float=False)
                v = np.ndarray.flatten(v)
                data['bus_names'] = v
            else:
                data['bus'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif key == "areas":
            data['areas'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif key == "gencost":
            data['gen_cost'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif key == "gen":
            data['gen'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif key == "branch":
            data['branch'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

    circuit = interpret_data_v1(circuit, data)

    return circuit


if __name__ == '__main__':

    fname = '/home/santi/Descargas/matpower-fubm-master/data/fubm_caseHVDC_vt.m'
    grid = parse_matpower_file(fname)

    print()
