"""
GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
from typing import Dict, Tuple, List, Union
import numpy as np
import GridCalEngine.basic_structures as bs
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Core.Devices as dev
import GridCalEngine.IO.matpower.matpower_branch_definitions as matpower_branches
import GridCalEngine.IO.matpower.matpower_bus_definitions as matpower_buses
import GridCalEngine.IO.matpower.matpower_gen_definitions as matpower_gen


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


def parse_areas_data(circuit: MultiCircuit, data, logger: bs.Logger):
    """
    Parse Matpower / FUBM Matpower area data into GridCal
    :param circuit: MultiCircuit instance
    :param data: data dictionary
    :param logger: Logger
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
            a = dev.Area(name='Area ' + str(area_idx), code=str(area_idx))
            area_idx_dict[area_idx] = (a, area_ref_bus_idx)
            circuit.add_area(a)

            if i == 0:
                # set the default area
                circuit.default_area = circuit.areas[0]

    return area_idx_dict


def parse_buses_data(circuit: MultiCircuit, data, area_idx_dict, logger: bs.Logger):
    """
    Parse Matpower / FUBM Matpower bus data into GridCal
    :param circuit: MultiCircuit instance
    :param data: data dictionary
    :param area_idx_dict: area index -> object dictionary
    :param logger: Logger
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

        bus = dev.Bus(name=names[i],
                      code=code,
                      vnom=table[i, matpower_buses.BASE_KV],
                      vmax=table[i, matpower_buses.VMAX],
                      vmin=table[i, matpower_buses.VMIN],
                      area=area,
                      is_slack=is_slack,
                      Vm0=table[i, matpower_buses.VM],
                      Va0=table[i, matpower_buses.VA])

        # store the given bus index in relation to its real index in the table for later
        bus_idx_dict[table[i, matpower_buses.BUS_I]] = i

        # determine if the bus is set as slack manually
        bus.is_slack = table[i, matpower_buses.BUS_TYPE] == matpower_buses.REF

        # Add the load
        if table[i, matpower_buses.PD] != 0 or table[i, matpower_buses.QD] != 0:
            load = dev.Load(P=table[i, matpower_buses.PD], Q=table[i, matpower_buses.QD])
            load.bus = bus
            bus.loads.append(load)

        # Add the shunt
        if table[i, matpower_buses.GS] != 0 or table[i, matpower_buses.BS] != 0:
            shunt = dev.Shunt(G=table[i, matpower_buses.GS], B=table[i, matpower_buses.BS])
            shunt.bus = bus
            bus.shunts.append(shunt)

        # Add the bus to the circuit buses
        circuit.add_bus(bus)

    return bus_idx_dict


def parse_generators(circuit: MultiCircuit, data, bus_idx_dict, logger: bs.Logger):
    """
    Parse Matpower / FUBM Matpower generator data into GridCal
    :param circuit: MultiCircuit instance
    :param data: data dictionary
    :param bus_idx_dict: bus index -> object dictionary
    :param logger: Logger
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

    gen_dict = dict()
    for i in range(len(table)):
        bus_idx = bus_idx_dict[int(table[i, matpower_gen.GEN_BUS])]
        # TODO: Calculate pf based on reactive_power
        gen = dev.Generator(name=names[i],
                            P=table[i, matpower_gen.PG],
                            vset=table[i, matpower_gen.VG],
                            Qmax=table[i, matpower_gen.QMAX],
                            Qmin=table[i, matpower_gen.QMIN],
                            Pmin=table[i, matpower_gen.PMIN],
                            Pmax=table[i, matpower_gen.PMAX]
                            )

        gen_dict[i] = gen

        # Add the generator to the bus
        gen.bus = circuit.buses[bus_idx]
        circuit.buses[bus_idx].generators.append(gen)

    if 'gencost' in data:
        # parse the OPF data
        opf_table = data['gencost']

        for i in range(opf_table.shape[0]):
            curve_model = opf_table[i, 0]
            startup_cost = opf_table[i, 1]
            shutdown_cost = opf_table[i, 2]
            n_cost = opf_table[i, 3]
            points = opf_table[i, 4:]
            if curve_model == 2:
                if len(points) > 1:
                    gen_dict[i].Cost0 = points[0]
                    gen_dict[i].Cost = points[1]
                    gen_dict[i].Cost2 = points[2]
            elif curve_model == 1:
                # fit a quadratic curve
                x = points[0::1]
                y = points[0::2]
                coeff = np.polyfit(x, y, 2)
                gen_dict[i].Cost = coeff[1]
            else:
                logger.add_warning("Unsupported curve model", gen_dict[i].name, curve_model)

            # if gen_dict[i].Cost == 0.0:
            #     gen_dict[i].enabled_dispatch = False


def parse_branches_data(circuit: MultiCircuit, data, bus_idx_dict, logger: bs.Logger):
    """
    Parse Matpower / FUBM Matpower branch data into GridCal
    :param circuit: MultiCircuit instance
    :param data: data dictionary
    :param bus_idx_dict: bus index -> object dictionary
    :param logger: Logger
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
                            control_mode = dev.ConverterControlType.type_I_2

                        elif Vac_set != 0.0:
                            control_mode = dev.ConverterControlType.type_I_3

                        else:
                            control_mode = dev.ConverterControlType.type_I_1

                    else:
                        control_mode = dev.ConverterControlType.type_0_free

                elif matpower_converter_mode == 2:

                    if Vac_set == 0.0:
                        control_mode = dev.ConverterControlType.type_II_4
                    else:
                        control_mode = dev.ConverterControlType.type_II_5

                elif matpower_converter_mode == 3:
                    control_mode = dev.ConverterControlType.type_III_6

                elif matpower_converter_mode == 4:
                    control_mode = dev.ConverterControlType.type_III_7

                else:
                    control_mode = dev.ConverterControlType.type_0_free

                rate = max(table[i, [matpower_branches.RATE_A, matpower_branches.RATE_B, matpower_branches.RATE_C]])

                branch = dev.VSC(bus_from=f,
                                 bus_to=t,
                                 name='VSC' + str(len(circuit.vsc_devices) + 1),
                                 active=bool(table[i, matpower_branches.BR_STATUS]),
                                 r=table[i, matpower_branches.BR_R],
                                 x=table[i, matpower_branches.BR_X],
                                 tap_module=m,
                                 tap_module_max=table[i, matpower_branches.MA_MAX],
                                 tap_module_min=table[i, matpower_branches.MA_MIN],
                                 tap_phase=table[i, matpower_branches.SHIFT],
                                 tap_phase_max=np.deg2rad(table[i, matpower_branches.ANGMAX]),
                                 tap_phase_min=np.deg2rad(table[i, matpower_branches.ANGMIN]),
                                 G0sw=table[i, matpower_branches.GSW],
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

                logger.add_info('Branch as converter', 'Branch {}'.format(str(i + 1)))

            else:

                if (f.Vnom != t.Vnom or
                        (table[i, matpower_branches.TAP] != 1.0 and
                         table[i, matpower_branches.TAP] != 0) or
                        table[i, matpower_branches.SHIFT] != 0.0):

                    branch = dev.Transformer2W(bus_from=f,
                                               bus_to=t,
                                               name=names[i],
                                               r=table[i, matpower_branches.BR_R],
                                               x=table[i, matpower_branches.BR_X],
                                               g=0,
                                               b=table[i, matpower_branches.BR_B],
                                               rate=table[i, matpower_branches.RATE_A],
                                               tap_module=table[i, matpower_branches.TAP],
                                               tap_phase=table[i, matpower_branches.SHIFT],
                                               active=bool(table[i, matpower_branches.BR_STATUS]))
                    circuit.add_transformer2w(branch)
                    logger.add_info('Branch as 2w transformer', 'Branch {}'.format(str(i + 1)))

                else:
                    branch = dev.Line(bus_from=f,
                                      bus_to=t,
                                      name=names[i],
                                      r=table[i, matpower_branches.BR_R],
                                      x=table[i, matpower_branches.BR_X],
                                      b=table[i, matpower_branches.BR_B],
                                      rate=table[i, matpower_branches.RATE_A],
                                      active=bool(table[i, matpower_branches.BR_STATUS]))
                    circuit.add_line(branch, logger=logger)
                    logger.add_info('Branch as line', 'Branch {}'.format(str(i + 1)))

        else:

            if f.Vnom != t.Vnom or \
                    (table[i, matpower_branches.TAP] != 1.0 and table[i, matpower_branches.TAP] != 0) or \
                    table[i, matpower_branches.SHIFT] != 0.0:

                branch = dev.Transformer2W(bus_from=f,
                                           bus_to=t,
                                           name=names[i],
                                           r=table[i, matpower_branches.BR_R],
                                           x=table[i, matpower_branches.BR_X],
                                           g=0,
                                           b=table[i, matpower_branches.BR_B],
                                           rate=table[i, matpower_branches.RATE_A],
                                           tap_module=table[i, matpower_branches.TAP],
                                           tap_phase=table[i, matpower_branches.SHIFT],
                                           active=bool(table[i, matpower_branches.BR_STATUS]))
                circuit.add_transformer2w(branch)
                logger.add_info('Branch as 2w transformer', 'Branch {}'.format(str(i + 1)))

            else:
                branch = dev.Line(bus_from=f,
                                  bus_to=t,
                                  name=names[i],
                                  r=table[i, matpower_branches.BR_R],
                                  x=table[i, matpower_branches.BR_X],
                                  b=table[i, matpower_branches.BR_B],
                                  rate=table[i, matpower_branches.RATE_A],
                                  active=bool(table[i, matpower_branches.BR_STATUS]))
                circuit.add_line(branch, logger=logger)
                logger.add_info('Branch as line', 'Branch {}'.format(str(i + 1)))

    # convert normal lines into DC-lines if needed
    for line in circuit.lines:

        if line.bus_to.is_dc and line.bus_from.is_dc:
            dc_line = dev.DcLine(bus_from=line.bus_from,
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


def interpret_data_v1(circuit: MultiCircuit, data, logger: bs.Logger) -> MultiCircuit:
    """
    Pass the loaded table-like data to the  structures
    :param circuit:
    :param data: Data dictionary
    :param logger: Logger
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

    # parse Branches
    parse_branches_data(circuit, data, bus_idx_dict, logger)

    # add the profiles
    if master_time_array is not None:
        circuit.format_profiles(master_time_array)

    return circuit


def read_matpower_file(filename: str) -> [MultiCircuit, bs.Logger]:
    """

    :param filename:
    :return:
    """

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
            data['gencost'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif key == "gen":
            data['gen'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

        elif key == "branch":
            data['branch'] = txt2mat(find_between(chunk, '[', ']'), line_splitter=';')

    return data


def parse_matpower_file(filename, export=False) -> [MultiCircuit, bs.Logger]:
    """

    Args:
        filename:
        export:

    Returns:

    """

    # declare circuit
    circuit = MultiCircuit()

    logger = bs.Logger()

    data = read_matpower_file(filename)

    if 'bus' in data.keys():
        circuit = interpret_data_v1(circuit, data, logger)
    else:
        logger.add_error('No bus data')

    return circuit, logger


def arr_to_dict(hdr, arr):
    """
    Match header-data pair into a dictionary
    :param hdr: array of header data
    :param arr: array of values
    :return:
    """
    assert len(hdr) == len(arr)
    return {h: a for h, a in zip(hdr, arr)}


def get_matpower_case_data(filename, force_linear_cost=False) -> Dict:
    """
    PArse matpower .m file and get the case data structure
    :param filename: Name of the file
    :param force_linear_cost: Force linear cost when costs are found?
    :return: Matpower case data dictionary
    """
    logger = bs.Logger()

    data = read_matpower_file(filename)

    bus_data = list()
    bus_arr = data['bus']
    headers = matpower_buses.bus_headers[:bus_arr.shape[1]]
    for i in range(bus_arr.shape[0]):
        bus_data.append(arr_to_dict(hdr=headers, arr=bus_arr[i, :]))

    gen_data = list()
    gen_arr = data['gen']
    headers = matpower_gen.gen_headers[: gen_arr.shape[1]]
    for i in range(gen_arr.shape[0]):
        gen_data.append(arr_to_dict(hdr=headers, arr=gen_arr[i, :]))

    gen_cost_data = list()
    gen_cost_arr = data['gencost']
    for i in range(gen_cost_arr.shape[0]):
        costtype = gen_cost_arr[i, 0]
        startup = gen_cost_arr[i, 1]
        shutdown = gen_cost_arr[i, 2]
        n = int(gen_cost_arr[i, 3])
        costvector = gen_cost_arr[i, 3:3 + n]

        if force_linear_cost:
            if len(costvector) == 3:
                costvector[2] = 0.0

        gen_cost_data.append({'costtype': costtype,
                              'startup': startup,
                              'shutdown': shutdown,
                              'n': n,
                              'costvector': costvector})

    branch_data = list()
    bus_arr = data['branch']
    headers = matpower_branches.branch_headers[: bus_arr.shape[1]]
    for i in range(bus_arr.shape[0]):
        branch_data.append(arr_to_dict(hdr=headers, arr=bus_arr[i, :]))

    return {'baseMVA': 100.0,
            'bus': bus_data,
            'branch': branch_data,
            'gen': gen_data,
            'gencost': gen_cost_data}


def get_buses(circuit: MultiCircuit) -> Tuple[List[Dict[str, float]], Dict[dev.Bus, int]]:
    """
    Get matpower buses structure
    :param circuit: MultiCircuit
    :return: list of buses structure, buses dictionary {Bus: bus int}
    """
    data = list()

    bus_dict = dict()

    for i, elm in enumerate(circuit.buses):

        Pd = 0.0
        Qd = 0.0
        Gs = 0.0
        Bs = 0.0

        for child in (elm.loads + elm.static_generators + elm.external_grids):
            Pd += child.P
            Qd += child.Q

        for child in elm.shunts:
            Gs += child.G
            Bs += child.B

        data.append({
            'bus_i': i + 1,  # matlab starts at 1
            'type': elm.determine_bus_type().value,
            'Pd': Pd,
            'Qd': Qd,
            'Gs': Gs,
            'Bs': Bs,
            'area': 0,
            'Vm': elm.Vm0,
            'Va': elm.Va0,
            'baseKV': elm.Vnom,
            'zone': 0,
            'Vmax': elm.Vmax,
            'Vmin': elm.Vmin
        })

        bus_dict[circuit.buses[i]] = i + 1

    return data, bus_dict


def get_generation(circuit: MultiCircuit, bus_dict: Dict[dev.Bus, int]) -> Tuple[List[Dict[str, float]],
                                                                                 List[Dict[str, float]]]:
    """
    Get generation and generation cost data
    :param circuit:
    :param bus_dict:
    :return:
    """
    data = list()
    cost_data = list()
    elm_list = circuit.get_generators() + circuit.get_batteries()

    for k, elm in enumerate(elm_list):
        i = bus_dict[elm.bus]  # already accounts for the +1 of Matlab

        data.append({'bus': i,
                     'Pg': elm.P,
                     'Qg': 0,
                     'Qmax': elm.Qmax,
                     'Qmin': elm.Qmin,
                     'Vg': elm.Vset,
                     'mBase': elm.Snom,
                     'status': int(elm.active),
                     'Pmax': elm.Pmax,
                     'Pmin': elm.Pmin,
                     'Pc1': 0,
                     'Pc2': 0,
                     'Qc1min': 0,
                     'Qc1max': 0,
                     'Qc2min': 0,
                     'Qc2max': 0,
                     'ramp_agc': 0,
                     'ramp_10': 0,
                     'ramp_30': 0,
                     'ramp_q': 0,
                     'apf': 0,
                     })

        cost_data.append({
            'costtype': 2,
            'startup': elm.StartupCost,
            'shutdown': elm.ShutdownCost,
            'n': 3,
            'costvector': [elm.Cost2, elm.Cost, elm.Cost0]
        })

    return data, cost_data


def get_branches(circuit: MultiCircuit, bus_dict: Dict[dev.Bus, int]) -> List[Dict[str, float]]:
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    data = list()

    elm_list = circuit.get_branches_wo_hvdc()

    for k, elm in enumerate(elm_list):
        f = bus_dict[elm.bus_from]  # already accounts for the +1 of Matlab
        t = bus_dict[elm.bus_to]  # already accounts for the +1 of Matlab

        angle = 0.0
        ratio = 1.0
        angmin = -360.0  # deg
        angmax = 360.0  # deg
        if isinstance(elm, dev.Transformer2W):
            angle = elm.tap_phase * 57.2958  # deg
            ratio = elm.tap_module
            angmin = elm.tap_phase_min * 57.2958  # deg
            angmax = elm.tap_phase_max * 57.2958  # deg

        data.append({'fbus': f,
                     'tbus': t,
                     'r': elm.R,
                     'x': elm.X,
                     'b': elm.B,
                     'rateA': elm.rate,
                     'rateB': elm.rate * elm.contingency_factor,
                     'rateC': 0,
                     'ratio': ratio,
                     'angle': angle,
                     'status': int(elm.active),
                     'angmin': angmin,
                     'angmax': angmax,
                     })

    return data


def to_matpower(circuit: MultiCircuit, logger: bs.Logger = bs.Logger()) -> Dict[str, Union[float, List[Dict[str, float]]]]:
    """

    :param circuit:
    :param logger:
    :return:
    """
    case = dict()
    case['baseMVA'] = circuit.Sbase
    case['bus'], bus_dict = get_buses(circuit=circuit)
    case['gen'], case['gencost'] = get_generation(circuit=circuit, bus_dict=bus_dict)
    case['branch'] = get_branches(circuit=circuit, bus_dict=bus_dict)

    return case
