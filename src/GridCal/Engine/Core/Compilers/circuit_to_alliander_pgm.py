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

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Devices.enumerations import ConverterControlType, TransformerControlType
from GridCal.Engine.Devices import *
from GridCal.Engine.basic_structures import Logger, SolverType, ReactivePowerControlMode, TapsControlMode
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions


try:
    import power_grid_model as pgm

    ALLIANDER_PGM_AVAILABLE = True
    print("Alliander's PGM available")

except ImportError:
    ALLIANDER_PGM_AVAILABLE = False
    print("Alliander's power grid model is not available, try pip install power-grid-model")


def get_pgm_buses(circuit: MultiCircuit):
    """
    Convert the buses to Alliander's PGM buses
    :param circuit: GridCal circuit
    :return: bus dictionary buses[uuid] -> int
    """
    bus_dict = dict()

    node = pgm.initialize_array('input', 'node', len(circuit.buses))

    for i, bus in enumerate(circuit.buses):

        # fill in data
        node['id'][i] = i
        node['u_rated'][i] = bus.Vnom

        # create dictionary entry
        bus_dict[bus.idtag] = i

    return node, bus_dict


def get_pgm_loads(circuit: MultiCircuit, bus_dict):
    """
    Generate load data
    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    :return struct of load values
    """

    devices = circuit.get_loads()

    sym_load = pgm.initialize_array('input', 'sym_load', len(devices))

    for k, elm in enumerate(devices):
        sym_load['id'][k] = k
        sym_load['node'][k] = bus_dict[elm.bus.idtag]
        sym_load['status'][k] = int(elm.active)
        sym_load['type'][k] = pgm.LoadGenType.const_power
        sym_load['p_specified'][k] = elm.P * 1e6
        sym_load['q_specified'][k] = elm.Q * 1e6

    return sym_load


def get_pgm_static_generators(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    devices = circuit.get_static_generators()

    stagen = pgm.initialize_array('input', 'sym_load', len(devices))

    for k, elm in enumerate(devices):

        pass

    stagen


def get_pgm_shunts(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    devices = circuit.get_shunts()

    shunt = pgm.initialize_array('input', 'sym_load', len(devices))

    for k, elm in enumerate(devices):

        pass

    return shunt


def get_pgm_generators(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    devices = circuit.get_generators()

    gen = pgm.initialize_array('input', 'sym_load', len(devices))

    for k, elm in enumerate(devices):

        pass

    return gen


def get_pgm_battery_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    devices = circuit.get_batteries()
    batt = pgm.initialize_array('input', 'sym_load', len(devices))
    for k, elm in enumerate(devices):
        pass
    return batt


def get_pgm_line(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """

    line = pgm.initialize_array('input', 'line', len(circuit.lines))

    # Compile the lines
    for i, elm in enumerate(circuit.lines):

        line['id'][i] = i
        line['from_node'][i] = bus_dict[elm.bus_from.idtag]
        line['to_node'][i] = bus_dict[elm.bus_from.idtag]
        line['from_status'][i] = int(elm.bus_from.active)
        line['to_status'][i] = int(elm.bus_to.active)
        line['r1'][i] = elm.R
        line['x1'][i] = elm.X
        line['c1'][i] = 1.0 / elm.B if elm.B != 0 else 0
        line['tan1'][i] = 0.0  # TODO: what is this?
        line['i_n'][i] = elm.rate  # TODO: Is this the rate? what units?

    return line


def get_pgm_transformer_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    xfo = pgm.initialize_array('input', 'sym_load', len(circuit.transformers2w))

    for i, elm in enumerate(circuit.transformers2w):
        pass

    return xfo


def get_pgm_vsc_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    vsc = pgm.initialize_array('input', 'sym_load', len(circuit.vsc_devices))
    for i, elm in enumerate(circuit.vsc_devices):
        pass
    return vsc


def get_pgm_dc_line_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    dc_line = pgm.initialize_array('input', 'sym_load', len(circuit.dc_lines))
    # Compile the lines
    for i, elm in enumerate(circuit.dc_lines):
        pass
    return dc_line


def get_pgm_hvdc_data(circuit: MultiCircuit,  bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to Alliander's PGM index
    """
    hvdc = pgm.initialize_array('input', 'sym_load', len(circuit.hvdc_lines))
    for i, elm in enumerate(circuit.hvdc_lines):
        pass
    return hvdc


def to_pgm(circuit: MultiCircuit) -> pgm.PowerGridModel:
    """
    Convert GridCal circuit to Alliander's PGM model
    See https://github.com/alliander-opensource/power-grid-model/blob/main/docs/graph-data-model.md
    :param circuit: MultiCircuit
    :return: pgm.PowerGridModel instance
    """

    node, bus_dict = get_pgm_buses(circuit)

    sym_load = get_pgm_loads(circuit, bus_dict)
    stagen = get_pgm_static_generators(circuit, bus_dict)
    shunt = get_pgm_shunts(circuit, bus_dict)
    source = get_pgm_generators(circuit, bus_dict)
    battery = get_pgm_battery_data(circuit, bus_dict)
    line = get_pgm_line(circuit, bus_dict)
    xfo = get_pgm_transformer_data(circuit, bus_dict)
    vsc = get_pgm_vsc_data(circuit, bus_dict)
    dc_line = get_pgm_dc_line_data(circuit, bus_dict)
    hvdc = get_pgm_hvdc_data(circuit, bus_dict)

    # all
    input_data = {
        'node': node,
        'line': line,
        'sym_load': sym_load,
        'source': source
    }

    model = pgm.PowerGridModel(input_data, system_frequency=circuit.fBase)

    return model


def alliander_pgm_pf(circuit: MultiCircuit, opt: PowerFlowOptions):
    """
    Alliander's PGM power flow
    :param circuit: MultiCircuit instance
    :param opt: Power Flow Options
    :return: Alliander's PGM Power flow results object
    """
    model = to_pgm(circuit)

    pf_res = model.calculate_power_flow()

    return pf_res

