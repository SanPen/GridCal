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

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *
import GridCal.Engine.IO.matpower.matpower_branch_definitions as matpower_branches
import GridCal.Engine.IO.matpower.matpower_bus_definitions as matpower_buses
import GridCal.Engine.IO.matpower.matpower_gen_definitions as matpower_gen


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


def parse_areas_data(circuit: MultiCircuit, data, logger: Logger):
    """
    Parse Matpower / FUBM Matpower area data into GridCal
    :param circuit: MultiCircuit instance
    :param data: data dictionary
    :return: area index -> object dictionary
    """
    area_idx_dict = dict()
    if 'areas' in data.keys():
        table = data['areas']

        if table.shape[0] > 0:
            # if there are areas declared, clean the default areas
            circuit.areas = list()

        for i in range(table.shape[0]):
            area_idx = int(table[i, 0])
            area_ref_bus_idx = table[i, 1]
            a = Area(name='Area ' + str(area_idx), code=str(area_idx))
            area_idx_dict[area_idx] = (a, area_ref_bus_idx)
            circuit.add_area(a)

            if i == 0:
                # set the default area
                circuit.default_area = circuit.areas[0]

    return area_idx_dict


def parse_buses_data(circuit: MultiCircuit, data, area_idx_dict, logger: Logger):
    """
    Parse Matpower / FUBM Matpower bus data into GridCal
    :param circuit: MultiCircuit instance
    :param data: data dictionary
    :param area_idx_dict: area index -> object dictionary
    :return: bus index -> object dictionary
    """

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
        names = ['bus ' + str(int(table[i, matpower_buses.BUS_I])) for i in range(n)]

    # Buses
    bus_idx_dict = dict()
    for i in range(n):
        # Create bus
        area_idx = int(table[i, matpower_buses.BUS_AREA])
        bus_idx = int(table[i, matpower_buses.BUS_I])
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
                  vnom=table[i, matpower_buses.BASE_KV],
                  vmax=table[i, matpower_buses.VMAX],
                  vmin=table[i, matpower_buses.VMIN],
                  area=area,
                  is_slack=is_slack)

        # store the given bus index in relation to its real index in the table for later
        bus_idx_dict[table[i, matpower_buses.BUS_I]] = i

        # determine if the bus is set as slack manually
        tpe = table[i, matpower_buses.BUS_TYPE]
        if tpe == matpower_buses.REF:
            bus.is_slack = True
        else:
            bus.is_slack = False

        # Add the load
        if table[i, matpower_buses.PD] != 0 or table[i, matpower_buses.QD] != 0:
            load = Load(P=table[i, matpower_buses.PD], Q=table[i, matpower_buses.QD])
            load.bus = bus
            bus.loads.append(load)

        # Add the shunt
        if table[i, matpower_buses.GS] != 0 or table[i, matpower_buses.BS] != 0:
            shunt = Shunt(G=table[i, matpower_buses.GS], B=table[i, matpower_buses.BS])
            shunt.bus = bus
            bus.shunts.append(shunt)

        # Add the bus to the circuit buses
        circuit.add_bus(bus)

    return bus_idx_dict


def parse_generators(circuit: MultiCircuit, data, bus_idx_dict, logger: Logger):
    """
    Parse Matpower / FUBM Matpower generator data into GridCal
    :param circuit: MultiCircuit instance
    :param data: data dictionary
    :param bus_idx_dict: bus index -> object dictionary
    :return:
    """

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
        bus_idx = bus_idx_dict[int(table[i, matpower_gen.GEN_BUS])]
        gen = Generator(name=names[i],
                        active_power=table[i, matpower_gen.PG],
                        voltage_module=table[i, matpower_gen.VG],
                        Qmax=table[i, matpower_gen.QMAX],
                        Qmin=table[i, matpower_gen.QMIN])

        # Add the generator to the bus
        gen.bus = circuit.buses[bus_idx]
        circuit.buses[bus_idx].controlled_generators.append(gen)


def parse_branches_data(circuit: MultiCircuit, data, bus_idx_dict, logger: Logger):
    """
    Parse Matpower / FUBM Matpower branch data into GridCal
    :param circuit: MultiCircuit instance
    :param data: data dictionary
    :param bus_idx_dict: bus index -> object dictionary
    :return: Nothing
    """

    # Branches
    table = data['branch']
    n = len(table)

    if table.shape[1] == 37:  # FUBM model
        logger.add_info('It is a FUBM model')

    if 'branch_names' in data.keys():
        names = data['branch_names']
    else:
        names = ['branch ' + str(i) for i in range(n)]
    for i in range(len(table)):
        f = circuit.buses[bus_idx_dict[int(table[i, matpower_branches.F_BUS])]]
        t = circuit.buses[bus_idx_dict[int(table[i, matpower_branches.T_BUS])]]

        if table.shape[1] == 37:  # FUBM model

            # converter type (I, II, III)
            matpower_converter_mode = table[i, matpower_branches.CONV_A]

            if matpower_converter_mode > 0:  # it is a converter

                # set the from bus as a DC bus
                # this is by design of the matpower FUBM model,
                # if it is a converter,
                # the DC bus is always the "from" bus
                f.is_dc = True

                # determine the converter control mode
                Pfset = table[i, matpower_branches.PF]
                Ptset = table[i, matpower_branches.PT]
                Vac_set = table[i, matpower_branches.VT_SET]
                Vdc_set = table[i, matpower_branches.VF_SET]
                Qfset = table[i, matpower_branches.QF]
                Qtset = table[i, matpower_branches.QT]
                m = table[i, matpower_branches.TAP] if table[i, matpower_branches.TAP] > 0 else 1.0

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

                rate = max(table[i, [matpower_branches.RATE_A, matpower_branches.RATE_B, matpower_branches.RATE_C]])

                branch = VSC(bus_from=f,
                             bus_to=t,
                             name='VSC' + str(len(circuit.vsc_devices) + 1),
                             active=bool(table[i, matpower_branches.BR_STATUS]),
                             r1=table[i, matpower_branches.BR_R],
                             x1=table[i, matpower_branches.BR_X],
                             m=m,
                             m_max=table[i, matpower_branches.MA_MAX],
                             m_min=table[i, matpower_branches.MA_MIN],
                             theta=table[i, matpower_branches.SHIFT],
                             theta_max=np.deg2rad(table[i, matpower_branches.ANGMAX]),
                             theta_min=np.deg2rad(table[i, matpower_branches.ANGMIN]),
                             G0=table[i, matpower_branches.GSW],
                             Beq=table[i, matpower_branches.BEQ],
                             Beq_max=table[i, matpower_branches.BEQ_MAX],
                             Beq_min=table[i, matpower_branches.BEQ_MIN],
                             rate=rate,
                             kdp=table[i, matpower_branches.KDP],
                             k=table[i, matpower_branches.K2],
                             control_mode=control_mode,
                             Pfset=Pfset,
                             Qfset=Qfset,
                             Vac_set=Vac_set if Vac_set > 0 else 1.0,
                             Vdc_set=Vdc_set if Vdc_set > 0 else 1.0,
                             alpha1=table[i, matpower_branches.ALPHA1],
                             alpha2=table[i, matpower_branches.ALPHA2],
                             alpha3=table[i, matpower_branches.ALPHA3])
                circuit.add_vsc(branch)

                logger.add_info('Branch as converter', 'Branch {}'.format(str(i+1)))

            else:

                if f.Vnom != t.Vnom or (table[i, matpower_branches.TAP] != 1.0 and table[i, matpower_branches.TAP] != 0) or table[i, matpower_branches.SHIFT] != 0.0:

                    branch = Transformer2W(bus_from=f,
                                           bus_to=t,
                                           name=names[i],
                                           r=table[i, matpower_branches.BR_R],
                                           x=table[i, matpower_branches.BR_X],
                                           g=0,
                                           b=table[i, matpower_branches.BR_B],
                                           rate=table[i, matpower_branches.RATE_A],
                                           tap=table[i, matpower_branches.TAP],
                                           shift_angle=table[i, matpower_branches.SHIFT],
                                           active=bool(table[i, matpower_branches.BR_STATUS]))
                    circuit.add_transformer2w(branch)
                    logger.add_info('Branch as 2w transformer', 'Branch {}'.format(str(i + 1)))

                else:
                    branch = Line(bus_from=f,
                                  bus_to=t,
                                  name=names[i],
                                  r=table[i, matpower_branches.BR_R],
                                  x=table[i, matpower_branches.BR_X],
                                  b=table[i, matpower_branches.BR_B],
                                  rate=table[i, matpower_branches.RATE_A],
                                  active=bool(table[i, matpower_branches.BR_STATUS]))
                    circuit.add_line(branch)
                    logger.add_info('Branch as line', 'Branch {}'.format(str(i + 1)))

        else:

            if f.Vnom != t.Vnom or (table[i, matpower_branches.TAP] != 1.0 and table[i, matpower_branches.TAP] != 0) or table[i, matpower_branches.SHIFT] != 0.0:

                branch = Transformer2W(bus_from=f,
                                       bus_to=t,
                                       name=names[i],
                                       r=table[i, matpower_branches.BR_R],
                                       x=table[i, matpower_branches.BR_X],
                                       g=0,
                                       b=table[i, matpower_branches.BR_B],
                                       rate=table[i, matpower_branches.RATE_A],
                                       tap=table[i, matpower_branches.TAP],
                                       shift_angle=table[i, matpower_branches.SHIFT],
                                       active=bool(table[i, matpower_branches.BR_STATUS]))
                circuit.add_transformer2w(branch)
                logger.add_info('Branch as 2w transformer', 'Branch {}'.format(str(i + 1)))

            else:
                branch = Line(bus_from=f,
                              bus_to=t,
                              name=names[i],
                              r=table[i, matpower_branches.BR_R],
                              x=table[i, matpower_branches.BR_X],
                              b=table[i, matpower_branches.BR_B],
                              rate=table[i, matpower_branches.RATE_A],
                              active=bool(table[i, matpower_branches.BR_STATUS]))
                circuit.add_line(branch)
                logger.add_info('Branch as line', 'Branch {}'.format(str(i + 1)))

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
            logger.add_info('Converted to DC line', line.name)


def interpret_data_v1(circuit: MultiCircuit, data, logger: Logger) -> MultiCircuit:
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
    area_idx_dict = parse_areas_data(circuit, data, logger)

    # parse buses
    bus_idx_dict = parse_buses_data(circuit, data, area_idx_dict, logger)

    # parse generators
    parse_generators(circuit, data, bus_idx_dict, logger)

    # parse branches
    parse_branches_data(circuit, data, bus_idx_dict, logger)

    # add the profiles
    if master_time_array is not None:
        circuit.format_profiles(master_time_array)

    return circuit


def parse_matpower_file(filename, export=False) -> [MultiCircuit, Logger]:
    """

    Args:
        filename:
        export:

    Returns:

    """

    logger = Logger()

    # open the file as text
    with open(filename, 'r') as myfile:
        text = myfile.read()

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

    if 'bus' in data.keys():
        circuit = interpret_data_v1(circuit, data, logger)
    else:
        logger.add_error('No bus data')

    return circuit, logger


if __name__ == '__main__':

    fname = '/home/santi/Descargas/matpower-fubm-master/data/fubm_caseHVDC_vt.m'
    grid = parse_matpower_file(fname)

    print()
