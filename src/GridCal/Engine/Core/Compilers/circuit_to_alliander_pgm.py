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
from GridCal.Engine.IO.file_system import get_create_gridcal_folder


try:
    import power_grid_model as pgm

    ALLIANDER_PGM_AVAILABLE = True
    print("Alliander's PGM available")

except ImportError:
    ALLIANDER_PGM_AVAILABLE = False
    print("Alliander's power grid model is not available")


def get_pgm_buses(circuit: MultiCircuit):
    """
    Convert the buses to bentayga buses
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
    :param bus_dict: dictionary of bus id to bentayga bus object
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
    :param bus_dict: dictionary of bus id to bentayga bus object
    """
    devices = circuit.get_static_generators()
    for k, elm in enumerate(devices):

        pass


def get_pgm_shunts(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to bentayga bus object
    """
    devices = circuit.get_shunts()
    for k, elm in enumerate(devices):

        pass


def get_pgm_generators(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to bentayga bus object
    """
    devices = circuit.get_generators()

    for k, elm in enumerate(devices):

        pass


def get_battery_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to bentayga bus object
    """
    devices = circuit.get_batteries()

    for k, elm in enumerate(devices):
        pass


def add_pgm_line(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to bentayga bus object
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


def get_transformer_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to bentayga bus object
    """
    for i, elm in enumerate(circuit.transformers2w):
        pass


def get_vsc_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to bentayga bus object
    """
    for i, elm in enumerate(circuit.vsc_devices):
        pass


def get_dc_line_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to bentayga bus object
    """
    # Compile the lines
    for i, elm in enumerate(circuit.dc_lines):
        pass


def get_hvdc_data(circuit: MultiCircuit,  bus_dict):
    """

    :param circuit: GridCal circuit
    :param bus_dict: dictionary of bus id to bentayga bus object
    """

    for i, elm in enumerate(circuit.hvdc_lines):
        pass


def to_pgm(circuit: MultiCircuit) -> pgm.PowerGridModel:
    """
    Convert GridCal circuit to Alliander's PGM model
    :param circuit: MultiCircuit
    :return: btg.Circuit instance
    """

    node, bus_dict = get_pgm_buses(circuit)

    sym_load = get_pgm_loads(circuit, bus_dict)
    stagen = get_pgm_static_generators(circuit, bus_dict)
    shunt = get_pgm_shunts(circuit, bus_dict)
    source = get_pgm_generators(circuit, bus_dict)
    battery = get_battery_data(circuit, bus_dict)
    line = add_pgm_line(circuit, bus_dict)
    xfo = get_transformer_data(circuit, bus_dict)
    vsc = get_vsc_data(circuit, bus_dict)
    dc_line = get_dc_line_data(circuit, bus_dict)
    hvdc = get_hvdc_data(circuit, bus_dict)

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
    Bentayga power flow
    :param circuit: MultiCircuit instance
    :param opt: Power Flow Options
    :return: Bentayga Power flow results object
    """
    model = to_pgm(circuit)

    pf_res = model.calculate_power_flow()

    return pf_res

