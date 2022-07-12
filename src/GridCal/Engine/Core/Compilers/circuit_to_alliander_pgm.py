# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

import os.path

import numpy as np

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Devices.enumerations import ConverterControlType, TransformerControlType
from GridCal.Engine.Devices import *
from GridCal.Engine.basic_structures import Logger, SolverType, ReactivePowerControlMode, TapsControlMode
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


try:
    import power_grid_model as pgm
    from power_grid_model.validation import validate_input_data, assert_valid_input_data, ValidationError, ValidationException

    ALLIANDER_PGM_AVAILABLE = True
    print("Alliander's PGM available")

except ImportError:
    ALLIANDER_PGM_AVAILABLE = False
    print("Alliander's power grid model is not available, try pip install power-grid-model")

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
    Convert the buses to Alliander's PGM buses
    :param circuit: GridCal circuit
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


def get_pgm_loads(circuit: MultiCircuit, bus_dict, idx0):
    """
    Generate load data
    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    :return struct of load values
    """

    devices = circuit.get_loads()

    sym_load = pgm.initialize_array('input', 'sym_load', len(devices) * 3)

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
        idx += 1

        sym_load['id'][k2] = idx
        sym_load['node'][k2] = bus_dict[elm.bus.idtag]
        sym_load['status'][k2] = int(elm.active)
        sym_load['type'][k2] = pgm.LoadGenType.const_current
        sym_load['p_specified'][k2] = elm.Ir * 1e6
        sym_load['q_specified'][k2] = elm.Ii * 1e6
        idx += 1

        sym_load['id'][k3] = idx
        sym_load['node'][k3] = bus_dict[elm.bus.idtag]
        sym_load['status'][k3] = int(elm.active)
        sym_load['type'][k3] = pgm.LoadGenType.const_impedance
        sym_load['p_specified'][k3] = elm.G * 1e6
        sym_load['q_specified'][k3] = elm.B * 1e6
        idx += 1

    return sym_load, idx


# def get_pgm_static_generators(circuit: MultiCircuit, bus_dict, idx0):
#     """
#
#     :param circuit: GridCal circuit
#     :param bus_dict: dictionary of bus id to Alliander's PGM index
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
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    devices = circuit.get_shunts()

    shunt = pgm.initialize_array('input', 'shunt', len(devices))

    idx = idx0
    for k, elm in enumerate(devices):
        Ybase = circuit.Sbase / (elm.bus.Vnom**2)

        shunt['id'][k] = idx
        shunt['node'][k] = bus_dict[elm.bus.idtag]
        shunt['status'][k] = int(elm.active)

        shunt['g1'][k] = elm.G * Ybase
        shunt['b1'][k] = elm.B * Ybase
        idx += 1

    return shunt, idx


def get_pgm_generators(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    gen_devices = circuit.get_generators()
    stagen_devices = circuit.get_static_generators()
    batt_devices = circuit.get_batteries()

    sym_gen = pgm.initialize_array('input', 'sym_gen',
                                   len(gen_devices) + len(stagen_devices) + len(batt_devices))

    idx = idx0

    for k, elm in enumerate(gen_devices + batt_devices):
        sym_gen['id'][k] = idx
        sym_gen['node'][k] = bus_dict[elm.bus.idtag]
        sym_gen['status'][k] = int(elm.active)
        sym_gen['type'][k] = pgm.LoadGenType.const_power
        sym_gen['p_specified'][k] = elm.P * 1e6
        sym_gen['q_specified'][k] = 0
        idx += 1

    k2 = len(gen_devices) + len(batt_devices)
    for k, elm in enumerate(stagen_devices):
        sym_gen['id'][k2] = idx
        sym_gen['node'][k2] = bus_dict[elm.bus.idtag]
        sym_gen['status'][k2] = int(elm.active)
        sym_gen['type'][k2] = pgm.LoadGenType.const_power
        sym_gen['p_specified'][k2] = elm.P * 1e6
        sym_gen['q_specified'][k2] = elm.Q * 1e6
        idx += 1
        k2 += 1

    return sym_gen, idx


def get_pgm_source(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    gen_devices = circuit.get_generators()

    sym_gen = pgm.initialize_array('input', 'source', 1)

    # TODO: pick the one with the largest P
    elm = gen_devices[0]

    idx = idx0
    k = 0
    sym_gen['id'][k] = idx
    sym_gen['node'][k] = bus_dict[elm.bus.idtag]
    sym_gen['status'][k] = int(elm.active)
    sym_gen['u_ref'][k] = elm.Vset
    # sym_gen['u_ref_angle'][k] = 0.0
    idx += 1

    return sym_gen, idx


# def get_pgm_battery_data(circuit: MultiCircuit, bus_dict):
#     """
#
#     :param circuit: GridCal circuit
#     :param bus_dict: dictionary of bus id to Alliander's PGM index
#     """
#     devices = circuit.get_batteries()
#     batt = pgm.initialize_array('input', 'sym_load', len(devices))
#     for k, elm in enumerate(devices):
#         pass
#     return batt


def get_pgm_line(circuit: MultiCircuit, bus_dict, idx0, logger: Logger):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
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
        line['i_n'][i] = 1e6 * elm.rate / r3 / (Vf * 1000)  # rating in A
        idx += 1

    return line, idx


def get_pgm_transformer_data(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
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
        phase_int = int(np.round(np.rad2deg(elm.angle) / 30)) % 12
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
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    vsc = pgm.initialize_array('input', 'sym_load', len(circuit.vsc_devices))
    idx = idx0
    for i, elm in enumerate(circuit.vsc_devices):
        pass
    return vsc, idx


def get_pgm_dc_line_data(circuit: MultiCircuit, bus_dict, idx0):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
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
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    hvdc = pgm.initialize_array('input', 'sym_load', len(circuit.hvdc_lines))
    idx = idx0
    for i, elm in enumerate(circuit.hvdc_lines):
        pass
    return hvdc, idx


def to_pgm(circuit: MultiCircuit, logger: Logger = Logger()) -> "pgm.PowerGridModel":
    """
    Convert GridCal circuit to Alliander's PGM model
    See https://github.com/alliander-opensource/power-grid-model/blob/main/docs/graph-data-model.md
    :param circuit: MultiCircuit
    :return: pgm.PowerGridModel instance
    """
    idx0 = 0
    node, bus_dict, idx0 = get_pgm_buses(circuit, idx0)

    sym_load, idx0 = get_pgm_loads(circuit, bus_dict, idx0)

    shunt, idx0 = get_pgm_shunts(circuit, bus_dict, idx0)
    sym_gen, idx0 = get_pgm_generators(circuit, bus_dict, idx0)
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

    try:
        assert_valid_input_data(input_data=input_data)
        model_ok = True
    except ValidationException as e:
        print(e)
        model_ok = False

    if model_ok:
        model = pgm.PowerGridModel(input_data, system_frequency=circuit.fBase)
    else:
        model = None

    return model


def alliander_pgm_pf(circuit: MultiCircuit, opt: PowerFlowOptions, logger: Logger):
    """
    Alliander's PGM power flow
    :param circuit: MultiCircuit instance
    :param opt: Power Flow Options
    :param logger: Logger object
    :return: Alliander's PGM Power flow results object
    """
    model = to_pgm(circuit, logger=logger)

    try:
        pf_res = model.calculate_power_flow()

    except RuntimeError as e:
        logger.add_error('Power flow failed\n' + str(e))
        pf_res = None

    gc_res = translate_pgm_results(circuit, pf_res)

    return gc_res


def translate_pgm_results(grid: MultiCircuit, pf_res) -> PowerFlowResults:
    from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit

    nc = compile_snapshot_circuit(grid)

    results = PowerFlowResults(n=nc.nbus,
                               m=nc.nbr,
                               n_tr=nc.ntr,
                               n_hvdc=nc.nhvdc,
                               bus_names=nc.bus_names,
                               branch_names=nc.branch_names,
                               transformer_names=nc.transformer_data.tr_names,
                               hvdc_names=nc.hvdc_names,
                               bus_types=nc.bus_types)

    if pf_res is None:
        return results

    Vm = pf_res['node']['u_pu']
    Va = np.zeros_like(Vm)
    Pf = pf_res['line']['p_from'] * 1e-6
    Pt = pf_res['line']['p_to'] * 1e-6
    Qf = pf_res['line']['q_from'] * 1e-6
    Qt = pf_res['line']['q_to'] * 1e-6

    if 'transformer' in pf_res:
        Pf = np.r_[Pf, pf_res['transformer']['p_from']] * 1e-6
        Pt = np.r_[Pt, pf_res['transformer']['p_to']] * 1e-6
        Qf = np.r_[Pf, pf_res['transformer']['q_from']] * 1e-6
        Qt = np.r_[Pt, pf_res['transformer']['q_to']] * 1e-6

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


if __name__ == "__main__":
    import GridCal.Engine as gce
    # fname = './../../../../../Grids_and_profiles/grids/IEEE 14.xlsx'
    fname = './../../../../../Grids_and_profiles/grids/IEEE 30 Bus.gridcal'
    circ = gce.FileOpen(fname).open()

    pf_opt = PowerFlowOptions()
    lgr = Logger()
    pgm_ = alliander_pgm_pf(circ, pf_opt, lgr)
    print()
