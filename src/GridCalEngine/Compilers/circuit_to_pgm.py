# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

from warnings import warn
import numpy as np
from typing import Tuple, Dict
import json
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at

PGM_RECOMMENDED_VERSION = "0.0.1"
PGM_VERSION = ''
PGM_AVAILABLE = False
try:
    import power_grid_model as pgm
    from power_grid_model import CalculationMethod, CalculationType
    from power_grid_model.validation import (validate_input_data,
                                             assert_valid_input_data,
                                             assert_valid_batch_data,
                                             ValidationError,
                                             ValidationException)
    from power_grid_model.utils import export_json_data
    from power_grid_model.errors import PowerGridError

    PGM_AVAILABLE = True
except ImportError:
    pgm = None
    PGM_AVAILABLE = False

'''
hierarchy

base ──┬─────────────────────────────────────────────── node
       │
       ├── branch ──────────────────────────────────┬── line
       │                                            ├── link
       │                                            └── transformer
       │
       ├── appliance ──┬─────────────────────────────── source
       │               │
       │               ├─────────────────────────────── shunt
       │               │
       │               └── generic_load_gen ────────┬── sym_load
       │                                            ├── sym_gen
       │                                            ├── asym_load
       │                                            └── asym_gen
       │
       └── sensor ─────┬── generic_voltage_sensor ──┬── sym_voltage_sensor
                       │                            └── asym_voltage_sensor
                       │
                       └── generic_power_sensor ────┬── sym_power_sensor
                                                    └── asym_power_sensor

'''


def get_pgm_buses(circuit: MultiCircuit, idx0):
    """
    Convert the buses to LFE'sPGM buses
    :param circuit: GridCal circuit
    :param idx0: First object index
    :return: bus dictionary buses[uuid] -> int
    """
    bus_dict = dict()

    node = pgm.initialize_array('input', 'node', len(circuit.buses))
    idx = idx0
    for i, bus in enumerate(circuit.buses):
        # fill in data
        node['id'][i] = idx
        node['u_rated'][i] = bus.Vnom * 1000.0  # in V

        # create dictionary entry
        bus_dict[bus.idtag] = idx
        idx += 1

    return node, bus_dict, idx


def get_pgm_loads(circuit: MultiCircuit, bus_dict, idx0, n_time=None):
    """
    Generate load data
    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    :param n_time: Number of time steps
    :return struct of load values, load_profile
    """

    devices = circuit.get_loads()
    ndev = len(devices) * 3
    sym_load = pgm.initialize_array('input', 'sym_load', ndev)

    if n_time:
        P = np.zeros((n_time, ndev))
        Q = np.zeros((n_time, ndev))
    else:
        P = np.zeros((0, ndev))
        Q = np.zeros((0, ndev))

    idx = idx0
    for k, elm in enumerate(devices):
        k1 = 3 * k
        k2 = 3 * k + 1
        k3 = 3 * k + 2

        sym_load['id'][k1] = idx
        sym_load['node'][k1] = bus_dict[elm.bus.idtag]
        sym_load['status'][k1] = int(elm.active)
        sym_load['type'][k1] = pgm.LoadGenType.const_power
        sym_load['p_specified'][k1] = elm.P * 1e6
        sym_load['q_specified'][k1] = elm.Q * 1e6

        if n_time:
            P[:, k1] = elm.P_prof * 1e6
            Q[:, k1] = elm.Q_prof * 1e6

        idx += 1

        sym_load['id'][k2] = idx
        sym_load['node'][k2] = bus_dict[elm.bus.idtag]
        sym_load['status'][k2] = int(elm.active)
        sym_load['type'][k2] = pgm.LoadGenType.const_current
        sym_load['p_specified'][k2] = elm.Ir * 1e6
        sym_load['q_specified'][k2] = elm.Ii * 1e6

        if n_time:
            P[:, k2] = elm.Ir_prof * 1e6
            Q[:, k2] = elm.Ii_prof * 1e6

        idx += 1

        sym_load['id'][k3] = idx
        sym_load['node'][k3] = bus_dict[elm.bus.idtag]
        sym_load['status'][k3] = int(elm.active)
        sym_load['type'][k3] = pgm.LoadGenType.const_impedance
        sym_load['p_specified'][k3] = elm.G * 1e6
        sym_load['q_specified'][k3] = elm.B * 1e6

        if n_time:
            P[:, k3] = elm.G_prof * 1e6
            Q[:, k3] = elm.B_prof * 1e6

        idx += 1

    if n_time:
        load_profile = pgm.initialize_array("update", "sym_load", (n_time, len(devices) * 3))
        load_profile["id"] = sym_load['id']
        load_profile["p_specified"] = P
        load_profile["q_specified"] = Q

        return sym_load, idx, load_profile
    else:
        return sym_load, idx, None


# def get_pgm_static_generators(circuit: MultiCircuit, bus_dict, idx0):
#     """
#
#     :param circuit: GridCal circuit
#     :param bus_dict: dictionary of bus id to LFE'sPGM index
#     """
#     devices = circuit.get_static_generators()
#
#     stagen = pgm.initialize_array('input', 'sym_gen', len(devices))
#
#     idx = idx0
#     for k, elm in enumerate(devices):
#         stagen['id'][k] = idx
#         stagen['node'][k] = bus_dict[elm.bus.idtag]
#         stagen['status'][k] = int(elm.active)
#         stagen['type'][k] = pgm.LoadGenType.const_power
#         stagen['p_specified'][k] = elm.P * 1e6
#         stagen['q_specified'][k] = elm.Q * 1e6
#         idx += 1
#
#     return stagen, idx


def get_pgm_shunts(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    :returns shunts, last object index
    """
    devices = circuit.get_shunts()

    shunt = pgm.initialize_array('input', 'shunt', len(devices))

    idx = idx0
    for k, elm in enumerate(devices):
        Ybase = circuit.Sbase / (elm.bus.Vnom ** 2)

        shunt['id'][k] = idx
        shunt['node'][k] = bus_dict[elm.bus.idtag]
        shunt['status'][k] = int(elm.active)

        shunt['g1'][k] = elm.G * Ybase
        shunt['b1'][k] = elm.B * Ybase
        shunt['g0'][k] = elm.G0 * Ybase
        shunt['b0'][k] = elm.B0 * Ybase

        idx += 1

    return shunt, idx


def get_pgm_generators(circuit: MultiCircuit, bus_dict, idx0, n_time=None):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    :param n_time: Number of time steps, last_index, generation profile
    """
    gen_devices = circuit.get_generators()
    stagen_devices = circuit.get_static_generators()
    batt_devices = circuit.get_batteries()
    ndev = len(gen_devices) + len(stagen_devices) + len(batt_devices)

    sym_gen = pgm.initialize_array('input', 'sym_gen', ndev)

    if n_time:
        P = np.zeros((n_time, ndev))
        Q = np.zeros((n_time, ndev))

    idx = idx0

    for k1, elm in enumerate(gen_devices + batt_devices):
        sym_gen['id'][k1] = idx
        sym_gen['node'][k1] = bus_dict[elm.bus.idtag]
        sym_gen['status'][k1] = int(elm.active)
        sym_gen['type'][k1] = pgm.LoadGenType.const_power
        sym_gen['p_specified'][k1] = elm.P * 1e6
        sym_gen['q_specified'][k1] = 0

        if n_time:
            P[:, k1] = elm.P_prof * 1e6

        idx += 1

    k2 = len(gen_devices) + len(batt_devices)
    for k, elm in enumerate(stagen_devices):
        sym_gen['id'][k2] = idx
        sym_gen['node'][k2] = bus_dict[elm.bus.idtag]
        sym_gen['status'][k2] = int(elm.active)
        sym_gen['type'][k2] = pgm.LoadGenType.const_power
        sym_gen['p_specified'][k2] = elm.P * 1e6
        sym_gen['q_specified'][k2] = elm.Q * 1e6

        if n_time:
            P[:, k2] = elm.P_prof * 1e6
            Q[:, k2] = elm.Q_prof * 1e6

        idx += 1
        k2 += 1

    if n_time:
        load_profile = pgm.initialize_array("update", "sym_gen", (n_time, ndev))
        load_profile["id"] = sym_gen['id']
        load_profile["p_specified"] = P
        load_profile["q_specified"] = Q

        return sym_gen, idx, load_profile
    else:
        return sym_gen, idx, None


def get_pgm_source(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    """
    gen_devices = circuit.get_generators()
    sym_gen = pgm.initialize_array('input', 'source', 1)
    idx = idx0
    k = 0
    if len(gen_devices) > 0:
        # pick the one with the largest P
        Pmax = 0.0
        i_max = 0
        for i, gen in enumerate(gen_devices):
            if gen.P > Pmax:
                Pmax = gen.P
                i_max = i

        elm = gen_devices[i_max]
        sym_gen['id'][k] = idx
        sym_gen['node'][k] = bus_dict[elm.bus.idtag]
        sym_gen['status'][k] = int(elm.active)
        sym_gen['u_ref'][k] = elm.Vset  # p.u.
        # sym_gen['u_ref_angle'][k] = 0.0
    else:
        # there are no generators, look for the slack bus
        found = False
        for i, bus in enumerate(circuit.buses):
            if bus.is_slack:
                sym_gen['id'][k] = idx
                sym_gen['node'][k] = i
                sym_gen['status'][k] = 1
                sym_gen['u_ref'][k] = bus.Vm0  # p.u.
                found = True

        if not found:
            warn('The grid must have either a generator or a slack marked bus!')

    idx += 1

    return sym_gen, idx


# def get_pgm_battery_data(circuit: MultiCircuit, bus_dict):
#     """
#
#     :param circuit: GridCal circuit
#     :param bus_dict: dictionary of bus id to LFE'sPGM index
#     """
#     devices = circuit.get_batteries()
#     batt = pgm.initialize_array('input', 'sym_load', len(devices))
#     for k, elm in enumerate(devices):
#         pass
#     return batt


def get_pgm_line(circuit: MultiCircuit, bus_dict, idx0, logger: Logger):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    :param logger: Logger object
    """

    line = pgm.initialize_array('input', 'line', len(circuit.lines))
    omega = 6.283185307 * circuit.fBase  # angular frequency
    r3 = np.sqrt(3.0)  # square root of 3

    # Compile the lines
    idx = idx0
    for i, elm in enumerate(circuit.lines):
        Vf = elm.bus_from.Vnom
        Vt = elm.bus_to.Vnom

        if Vf != Vt:
            logger.add_error('Different line terminal voltages', elm.name, str(Vt), str(Vf))
            elm.bus_to.Vnom = Vf

        Zbase = Vf * Vf / circuit.Sbase

        line['id'][i] = idx
        line['from_node'][i] = bus_dict[elm.bus_from.idtag]
        line['to_node'][i] = bus_dict[elm.bus_to.idtag]
        line['from_status'][i] = int(elm.bus_from.active)
        line['to_status'][i] = int(elm.bus_to.active)
        line['r1'][i] = elm.R * Zbase  # Ohm
        line['x1'][i] = elm.X * Zbase  # Ohm
        line['c1'][i] = elm.B / (omega * Zbase)  # Farad
        line['tan1'][i] = 0.0  # this is the ratio G/B, which does not apply here because we do not have G

        line['r0'][i] = elm.R0 * Zbase  # Ohm
        line['x0'][i] = elm.X0 * Zbase  # Ohm
        line['c0'][i] = elm.B0 / (omega * Zbase)  # Farad
        line['tan0'][i] = 0.0  # this is the ratio G/B, which does not apply here because we do not have G

        line['i_n'][i] = 1e6 * elm.rate / r3 / (Vf * 1000)  # rating in A
        idx += 1

    return line, idx


def get_pgm_transformer_data(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    """
    xfo = pgm.initialize_array('input', 'transformer', len(circuit.transformers2w))

    omega = 6.283185307 * circuit.fBase
    r3 = np.sqrt(3.0)

    # Compile the lines
    idx = idx0
    for i, elm in enumerate(circuit.transformers2w):
        Zbase = elm.bus_from.Vnom ** 2 / circuit.Sbase

        xfo['id'][i] = idx
        xfo['from_node'][i] = bus_dict[elm.bus_from.idtag]
        xfo['to_node'][i] = bus_dict[elm.bus_to.idtag]
        xfo['from_status'][i] = int(elm.bus_from.active)
        xfo['to_status'][i] = int(elm.bus_to.active)

        xfo['u1'][i] = 1e3 * elm.bus_from.Vnom  # rated voltage at from-side (V)
        xfo['u2'][i] = 1e3 * elm.bus_to.Vnom  # rated voltage at to-side (V)
        xfo['sn'][i] = 1e6 * elm.rate  # volt-ampere (VA)
        xfo['uk'][i] = elm.X * (elm.rate / circuit.Sbase)  # relative short circuit voltage (p.u.)
        xfo['pk'][i] = 0  # short circuit (copper) loss (W)
        xfo['i0'][i] = 0  # relative no-load current (p.u.)
        xfo['p0'][i] = 0  # no-load (iron) loss (W)

        # clock number of phase shift.
        # Even number is not possible if one side is Y(N)
        # winding and the other side is not Y(N) winding.
        # Odd number is not possible, if both sides are Y(N)
        # winding or both sides are not Y(N) winding.
        phase_int = int(np.round(np.rad2deg(elm.tap_phase) / 30)) % 12
        xfo['clock'][i] = phase_int

        xfo['winding_from'][i] = pgm.WindingType.wye  # WindingType object

        if phase_int % 2 == 0:
            xfo['winding_to'][i] = pgm.WindingType.wye_n  # WindingType object
        else:
            xfo['winding_to'][i] = pgm.WindingType.delta  # WindingType object

        xfo['tap_side'][i] = pgm.BranchSide.to_side  # BranchSide object
        xfo['tap_pos'][i] = 0  # current position of tap changer
        xfo['tap_min'][i] = 0  # position of tap changer at minimum voltage
        xfo['tap_max'][i] = 0  # position of tap changer at maximum voltage
        xfo['tap_nom'][i] = 0  # nominal position of tap changer
        xfo['tap_size'][i] = 1e-20  # size of each tap of the tap changer (V), TODO: this should be 0 in future versions

        # xfo['uk_min'][i] = 0  # relative short circuit voltage at minimum tap
        # xfo['uk_max'][i] = 0  # relative short circuit voltage at maximum tap
        # xfo['pk_min'][i] = 0  # short circuit (copper) loss at minimum tap (W)
        # xfo['pk_max'][i] = 0  # short circuit (copper) loss at maximum tap (W)
        #
        # xfo['r_grounding_from'][i] = 0  # grounding resistance at from-side, if relevant (Ohm)
        # xfo['x_grounding_from'][i] = 0  # grounding reactance at from-side, if relevant (Ohm)
        # xfo['r_grounding_to'][i] = 0  # grounding resistance at to-side, if relevant (Ohm)
        # xfo['x_grounding_to'][i] = 0  # grounding reactance at to-side, if relevant (Ohm)
        idx += 1

    return xfo, idx


def get_pgm_vsc_data(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    """
    vsc = pgm.initialize_array('input', 'sym_load', len(circuit.vsc_devices))
    idx = idx0
    for i, elm in enumerate(circuit.vsc_devices):
        pass
    return vsc, idx


def get_pgm_dc_line_data(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    """
    dc_line = pgm.initialize_array('input', 'sym_load', len(circuit.dc_lines))
    # Compile the lines
    idx = idx0
    for i, elm in enumerate(circuit.dc_lines):
        pass
    return dc_line, idx


def get_pgm_hvdc_data(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to LFE'sPGM index
    :param idx0: First object index
    """
    hvdc = pgm.initialize_array('input', 'sym_load', len(circuit.hvdc_lines))
    idx = idx0
    for i, elm in enumerate(circuit.hvdc_lines):
        pass
    return hvdc, idx


def get_pgm_input_data(circuit: MultiCircuit, logger: Logger = Logger(), time_series=False):
    if time_series:
        n_time = circuit.get_time_number()
    else:
        n_time = None

    idx0 = 0
    node, bus_dict, idx0 = get_pgm_buses(circuit, idx0)

    sym_load, idx0, load_profile = get_pgm_loads(circuit, bus_dict, idx0, n_time)

    shunt, idx0 = get_pgm_shunts(circuit, bus_dict, idx0)
    sym_gen, idx0, gen_profile = get_pgm_generators(circuit, bus_dict, idx0, n_time)
    source, idx0 = get_pgm_source(circuit, bus_dict, idx0)
    line, idx0 = get_pgm_line(circuit, bus_dict, idx0, logger)
    transformer, idx0 = get_pgm_transformer_data(circuit, bus_dict, idx0)

    # vsc = get_pgm_vsc_data(circuit, bus_dict)
    # dc_line = get_pgm_dc_line_data(circuit, bus_dict)
    # hvdc = get_pgm_hvdc_data(circuit, bus_dict)

    # all
    input_data = {
        'node': node,
        'line': line,
        'transformer': transformer,
        'sym_load': sym_load,
        'sym_gen': sym_gen,
        'source': source,
        'shunt': shunt
    }

    if time_series:
        time_series_mutation = {"sym_load": load_profile,
                                "sym_gen": gen_profile}

    else:
        time_series_mutation = dict()

    return input_data, time_series_mutation


def to_pgm(circuit: MultiCircuit, logger: Logger = Logger(), time_series=False) -> Tuple["pgm.PowerGridModel", Dict]:
    """
    Convert GridCal circuit to LFE'sPGM model
    See https://github.com/alliander-opensource/power-grid-model/blob/main/docs/graph-data-model.md
    :param circuit: MultiCircuit
    :param logger: Logger instance
    :param time_series: use time series?
    :return: pgm.PowerGridModel instance
    """

    input_data, time_series_mutation = get_pgm_input_data(circuit=circuit, logger=logger, time_series=time_series)

    try:
        # this asserts the validity for batches if time_series_mutation is not empty, otherwise this
        # function is the same as assert_valid_input_data
        assert_valid_batch_data(input_data=input_data,
                                update_data=time_series_mutation,
                                calculation_type=CalculationType.power_flow)

        model_ok = True
    except ValidationException as e:
        print("assert_valid_input_data", e)
        model_ok = False

    if model_ok:
        model = pgm.PowerGridModel(input_data, system_frequency=circuit.fBase)
    else:
        model = None

    return model, time_series_mutation


def pgm_pf(circuit: MultiCircuit, opt: PowerFlowOptions, logger: Logger, symmetric=True, time_series=False):
    """
    LFE'sPGM power flow
    :param circuit: MultiCircuit instance
    :param opt: Power Flow Options
    :param logger: Logger object
    :param symmetric: Symmetric (3-phase balanced calculation? / asymmetric)
    :param time_series: Time_series?
    :return: LFE's PGM Power flow results object
    """
    model, time_series_mutation = to_pgm(circuit, logger=logger, time_series=time_series)

    calculation_method_dict = {SolverType.NR: CalculationMethod.newton_raphson,
                               SolverType.BFS: CalculationMethod.iterative_current,
                               SolverType.BFS_linear: CalculationMethod.linear_current,
                               SolverType.Constant_Impedance_linear: CalculationMethod.linear}

    calculation_method = calculation_method_dict.get(opt.solver_type, CalculationMethod.newton_raphson)

    if time_series:
        # 2D
        try:
            pf_res = model.calculate_power_flow(symmetric=symmetric,
                                                update_data=time_series_mutation,
                                                error_tolerance=opt.tolerance,
                                                max_iterations=opt.max_iter,
                                                threading=0,  # -1: one thread, 0: all threads, any other: custom
                                                continue_on_batch_error=True,
                                                calculation_method=calculation_method)

        except PowerGridError as e:
            logger.add_error('Power flow failed\n' + str(e))
            pf_res = None

        gc_res = translate_pgm_pf_results2d(circuit, pf_res)

    else:
        # 1D
        try:
            pf_res = model.calculate_power_flow(symmetric=symmetric,
                                                calculation_method=calculation_method)

        except PowerGridError as e:
            logger.add_error('Power flow failed\n' + str(e))
            pf_res = None

        gc_res = translate_pgm_results(circuit, pf_res)

    return gc_res


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


def save_pgm(filename: str, circuit: MultiCircuit, logger: Logger = Logger(), time_series=False):
    """
    Save to Power Grid Model format
    :param filename:
    :param circuit:
    :param logger:
    :param time_series:
    :return:
    """
    input_data, time_series_mutation = get_pgm_input_data(circuit=circuit, logger=logger, time_series=time_series)

    data = {'input_data': input_data,
            'mutation': time_series_mutation}

    data_str = json.dumps(data, indent=True, cls=NumpyEncoder)

    # Save json to a text file
    text_file = open(filename, "w")
    text_file.write(data_str)
    text_file.close()
    # export_json_data(Path(filename), input_data)


def translate_pgm_results(grid: MultiCircuit, pf_res) -> PowerFlowResults:
    """
    Translate the PGM results to SnapShot power flow results
    :param grid:
    :param pf_res:
    :return: PowerFlowResults
    """

    nc = compile_numerical_circuit_at(grid)

    results = PowerFlowResults(n=nc.nbus,
                               m=nc.nbr,
                               n_hvdc=nc.nhvdc,
                               bus_names=nc.bus_names,
                               branch_names=nc.branch_names,
                               hvdc_names=nc.hvdc_names,
                               bus_types=nc.bus_types)

    if pf_res is None:
        return results

    Vm = pf_res['node']['u_pu']
    Va = pf_res['node']['u_angle']  # np.zeros_like(Vm)  # TODO: what about this?
    Pf = pf_res['line']['p_from'] * 1e-6
    Pt = pf_res['line']['p_to'] * 1e-6
    Qf = pf_res['line']['q_from'] * 1e-6
    Qt = pf_res['line']['q_to'] * 1e-6

    if 'transformer' in pf_res:
        Pf = np.r_[Pf, pf_res['transformer']['p_from']] * 1e-6
        Pt = np.r_[Pt, pf_res['transformer']['p_to']] * 1e-6
        Qf = np.r_[Qf, pf_res['transformer']['q_from']] * 1e-6
        Qt = np.r_[Qt, pf_res['transformer']['q_to']] * 1e-6

    losses = (Pf + Pt) + 1j * (Qf + Qt)

    results.voltage = Vm * np.exp(1j * Va)
    # results.Sbus = res.S[0, :]
    results.Sf = Pf + 1j * Qf
    results.St = Pt + 1j * Qt
    results.loading = Pf / (nc.branch_rates + 1e-20)
    results.losses = losses
    # results.Vbranch = res.Vbranch[0, :]
    # results.If = res.If[0, :]
    # results.It = res.It[0, :]
    # results.Beq = res.Beq[0, :]
    # results.m = res.tap_modules[0, :]
    # results.theta = res.tap_angles[0, :]

    results.F = nc.F
    results.T = nc.T
    # results.hvdc_F = res.F_hvdc
    # results.hvdc_T = res.T_hvdc
    # results.hvdc_Pf = res.hvdc_Pf[0, :]
    # results.hvdc_Pt = res.hvdc_Pt[0, :]
    # results.hvdc_loading = res.hvdc_loading[0, :]
    # results.hvdc_losses = res.hvdc_losses[0, :]
    results.bus_area_indices = grid.get_bus_area_indices()
    results.area_names = [a.name for a in grid.areas]

    return results


def translate_pgm_pf_results2d(grid: MultiCircuit, pf_res) -> PowerFlowTimeSeriesResults:
    """
    Translate the time series power flow results
    :param grid:
    :param pf_res:
    :return: TimeSeriesResults
    """

    nc = compile_numerical_circuit_at(grid)

    results = PowerFlowTimeSeriesResults(n=nc.nbus,
                                         m=nc.nbr,
                                         n_hvdc=nc.nhvdc,
                                         bus_names=nc.bus_names,
                                         branch_names=nc.branch_names,
                                         hvdc_names=nc.hvdc_names,
                                         time_array=grid.time_profile,
                                         bus_types=nc.bus_types)

    if pf_res is None:
        return results

    P = pf_res['node']['p'] * 1e-6
    Q = pf_res['node']['q'] * 1e-6
    Vm = pf_res['node']['u_pu']
    Va = pf_res['node']['u_angle']
    Pf = pf_res['line']['p_from'] * 1e-6
    Pt = pf_res['line']['p_to'] * 1e-6
    Qf = pf_res['line']['q_from'] * 1e-6
    Qt = pf_res['line']['q_to'] * 1e-6

    if 'transformer' in pf_res:
        Pf = np.c_[Pf, pf_res['transformer']['p_from']] * 1e-6
        Pt = np.c_[Pt, pf_res['transformer']['p_to']] * 1e-6
        Qf = np.c_[Qf, pf_res['transformer']['q_from']] * 1e-6
        Qt = np.c_[Qt, pf_res['transformer']['q_to']] * 1e-6

    losses = (Pf + Pt) + 1j * (Qf + Qt)

    results.voltage = Vm * np.exp(1j * Va)
    results.Sbus = P + 1j * Q
    results.Sf = Pf + 1j * Qf
    results.St = Pt + 1j * Qt
    results.loading = Pf / (nc.branch_rates + 1e-20)
    results.losses = losses
    # results.Vbranch = res.Vbranch[0, :]
    # results.If = res.If[0, :]
    # results.It = res.It[0, :]
    # results.Beq = res.Beq[0, :]
    # results.m = res.tap_modules[0, :]
    # results.theta = res.tap_angles[0, :]

    results.F = nc.F
    results.T = nc.T
    # results.hvdc_F = res.F_hvdc
    # results.hvdc_T = res.T_hvdc
    # results.hvdc_Pf = res.hvdc_Pf[0, :]
    # results.hvdc_Pt = res.hvdc_Pt[0, :]
    # results.hvdc_loading = res.hvdc_loading[0, :]
    # results.hvdc_losses = res.hvdc_losses[0, :]
    results.bus_area_indices = grid.get_bus_area_indices()
    results.area_names = [a.name for a in grid.areas]

    return results
