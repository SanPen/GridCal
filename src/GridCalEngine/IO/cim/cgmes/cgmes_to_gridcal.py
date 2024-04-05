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
import time

import numpy as np
from typing import Dict, List, Tuple
import GridCalEngine.IO.cim.cgmes.cgmes_enums as cgmes_enums
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as gcdev
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_export import CimExporter
from GridCalEngine.IO.cim.cgmes.cgmes_utils import (get_nominal_voltage,
                                                    get_pu_values_ac_line_segment,
                                                    get_values_shunt,
                                                    get_pu_values_power_transformer, get_pu_values_power_transformer3w,
                                                    get_windings,
                                                    get_regulating_control, get_pu_values_power_transformer_end,
                                                    get_slack_id)
from GridCalEngine.IO.cim.cgmes.gridcal_to_cgmes import gridcal_to_cgmes  # TODO move them here
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ac_line_segment import ACLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.switch import Switch
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.disconnector import Disconnector
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_break_switch import LoadBreakSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.breaker import Breaker
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.voltage_level import VoltageLevel
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.bay import Bay


def get_gcdev_voltage_dict(cgmes_model: CgmesCircuit,
                           logger: DataLogger) -> Dict[str, Tuple[float, float]]:
    """
    Builds up voltage dictionary.

    :param cgmes_model: The CGMES circuit model.
    :param logger: The data logger for error handling.
    :return: A dictionary mapping TopologicalNode UUIDs
        to voltage (v) and angle. Dict[str, Tuple[float, float]]
    """

    # build the voltages dictionary
    v_dict: Dict[str, Tuple[float, float]] = dict()

    for e in cgmes_model.SvVoltage_list:
        if not isinstance(e.TopologicalNode, str):
            v_dict[e.TopologicalNode.uuid] = (e.v, e.angle)
        else:
            logger.add_error(msg='Missing reference',
                             device=e.rdfid,
                             device_class=e.tpe,
                             device_property="TopologicalNode",
                             value=e.TopologicalNode,
                             expected_value='object')
    return v_dict


def get_gcdev_device_to_terminal_dict(cgmes_model: CgmesCircuit,
                                      logger: DataLogger) -> Dict[str, List[Terminal]]:
    """
    Dictionary relating the conducting equipment to the terminal object(s)
    """
    # dictionary relating the conducting equipment to the terminal object
    device_to_terminal_dict: Dict[str, List[Terminal]] = dict()

    for e in cgmes_model.Terminal_list:
        if isinstance(e.ConductingEquipment, ConductingEquipment):
            lst = device_to_terminal_dict.get(e.ConductingEquipment.uuid, None)
            if lst is None:
                device_to_terminal_dict[e.ConductingEquipment.uuid] = [e]
            else:
                lst.append(e)
        else:
            logger.add_error(msg='The object is not a ConductingEquipment',
                             device=e.rdfid,
                             device_class=e.tpe,
                             device_property="ConductingEquipment",
                             value=e.ConductingEquipment,
                             expected_value='object')
    return device_to_terminal_dict


def find_terms_connections(cgmes_terminal: Terminal,
                           calc_node_dict: Dict[str, gcdev.Bus],
                           cn_dict: Dict[str, gcdev.ConnectivityNode]):
    """

    :param cgmes_terminal:
    :param calc_node_dict:
    :param cn_dict:
    :return:
    """

    if cgmes_terminal is not None:
        # get the rosetta calculation node if exists
        if cgmes_terminal.TopologicalNode is not None:
            calc_node = calc_node_dict.get(cgmes_terminal.TopologicalNode.uuid, None)
        else:
            calc_node = None

        # get the gcdev connectivity node if exists
        if cgmes_terminal.ConnectivityNode is not None:
            cn = cn_dict.get(cgmes_terminal.ConnectivityNode.uuid, None)
        else:
            cn = None
    else:
        calc_node = None
        cn = None

    return calc_node, cn


def find_connections(cgmes_elm: IdentifiedObject,
                     device_to_terminal_dict: Dict[str, List[Terminal]],
                     calc_node_dict: Dict[str, gcdev.Bus],
                     cn_dict: Dict[str, gcdev.ConnectivityNode],
                     logger: DataLogger):
    """

    :param cgmes_elm:
    :param device_to_terminal_dict:
    :param calc_node_dict:
    :param cn_dict:
    :param logger:
    :return:
    """
    # get the cgmes terminal of this device
    cgmes_terminals = device_to_terminal_dict.get(cgmes_elm.uuid, None)

    if cgmes_terminals is not None:
        calc_nodes = list()
        cns = list()
        for cgmes_terminal in cgmes_terminals:
            calc_node, cn = find_terms_connections(cgmes_terminal,
                                                   calc_node_dict,
                                                   cn_dict)
            calc_nodes.append(calc_node)
            cns.append(cn)
    else:
        calc_nodes = []
        cns = []
        logger.add_error("No terminal for the device",
                         device=cgmes_elm.rdfid,
                         device_class=cgmes_elm.tpe)

    return calc_nodes, cns


def find_object_by_idtag(object_list, target_idtag):  # TODO move to somewhere
    """
    Finds an object with the specified idtag
     in the given object_list from a Multi Circuit.

    Args:
        object_list (list[MyObject]): List of MyObject instances.
        target_idtag (str): The uuid to search for.

    Returns:
        MyObject or None: The found object or None if not found.
    """
    for obj in object_list:
        if obj.idtag == target_idtag:
            return obj
    return None


def get_gcdev_calculation_nodes(cgmes_model: CgmesCircuit,
                                gc_model: MultiCircuit,
                                v_dict: Dict[str, Tuple[float, float]],
                                logger: DataLogger) -> Dict[str, gcdev.Bus]:
    """
    Convert the TopologicalNodes to CalculationNodes
    :param cgmes_model: CgmesCircuit
    :param gc_model: gcdevCircuit
    :param v_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :return: dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus]
    """

    slack_id = get_slack_id(cgmes_model.SynchronousMachine_list)

    # dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
    calc_node_dict: Dict[str, gcdev.Bus] = dict()
    for cgmes_elm in cgmes_model.TopologicalNode_list:

        voltage = v_dict.get(cgmes_elm.uuid, None)
        nominal_voltage = get_nominal_voltage(topological_node=cgmes_elm,
                                              logger=logger)

        if voltage is not None and nominal_voltage is not None:
            vm = voltage[0] / nominal_voltage
            va = np.deg2rad(voltage[1])
        else:
            vm = 1.0
            va = 0.0

        is_slack = False
        if slack_id is not None:
            if slack_id == cgmes_elm.rdfid:
                is_slack = True

        # subs = find_object_by_idtag(
        #     object_list=gc_model.substations,
        #     target_idtag=cgmes_elm.Substation.uuid  # gcdev_elm.idtag
        # )

        volt_lev = find_object_by_idtag(
            object_list=gc_model.voltage_levels,
            target_idtag=cgmes_elm.ConnectivityNodeContainer.uuid
        )
        if volt_lev is None:
            print(f'No volt lev found for {cgmes_elm.name}')

        gcdev_elm = gcdev.Bus(name=cgmes_elm.name,
                              idtag=cgmes_elm.uuid,
                              code=cgmes_elm.description,
                              vnom=nominal_voltage,
                              vmin=0.9,
                              vmax=1.1,
                              active=True,
                              is_slack=is_slack,
                              is_dc=False,
                              # is_internal=False,
                              area=None,  # TODO get tp area
                              zone=None,  # TODO get tp zone
                              substation=None,  # TODO
                              voltage_level=volt_lev,  # TODO
                              country=None,  # TODO
                              # latitude=0.0,
                              # longitude=0.0,
                              Vm0=vm,
                              Va0=va)

        gc_model.add_bus(gcdev_elm)
        calc_node_dict[gcdev_elm.idtag] = gcdev_elm

    return calc_node_dict


def get_gcdev_connectivity_nodes(cgmes_model: CgmesCircuit,
                                 gcdev_model: MultiCircuit,
                                 calc_node_dict: Dict[str, gcdev.Bus],
                                 logger: DataLogger
                                 ) -> Dict[str, gcdev.ConnectivityNode]:
    """
    Convert the TopologicalNodes to CalculationNodes
    :param calc_node_dict: dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus]
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param logger: DataLogger
    :return: dictionary relating the ConnectivityNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus]
    """
    # dictionary relating the ConnectivityNode uuid to the gcdev ConnectivityNode
    cn_node_dict: Dict[str, gcdev.ConnectivityNode] = dict()
    for cgmes_elm in cgmes_model.ConnectivityNode_list:

        bus = calc_node_dict.get(cgmes_elm.TopologicalNode.uuid, None)
        if bus is None:
            logger.add_error(msg='No Bus found',
                             device=cgmes_elm,
                             device_class=cgmes_elm.tpe)

        gcdev_elm = gcdev.ConnectivityNode(
            idtag=cgmes_elm.uuid,
            code=cgmes_elm.description,
            name=cgmes_elm.name,
            dc=False,
            default_bus=bus
        )

        # gcdev_model.connectivity_nodes.append(gcdev_elm)
        cn_node_dict[gcdev_elm.idtag] = gcdev_elm

    return cn_node_dict


def get_gcdev_loads(cgmes_model: CgmesCircuit,
                    gcdev_model: MultiCircuit,
                    calc_node_dict: Dict[str, gcdev.Bus],
                    cn_dict: Dict[str, gcdev.ConnectivityNode],
                    device_to_terminal_dict: Dict[str, List[Terminal]],
                    logger: DataLogger) -> None:
    """
    Convert the CGMES loads to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    """
    # convert loads
    for device_list in [cgmes_model.EnergyConsumer_list,
                        cgmes_model.ConformLoad_list,
                        cgmes_model.NonConformLoad_list]:

        for cgmes_elm in device_list:
            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]
                cn = cns[0]

                p, q, i_i, i_r, g, b = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                if cgmes_elm.LoadResponse is not None:

                    if cgmes_elm.LoadResponse.exponentModel:
                        print(f'Exponent model True at {cgmes_elm.name}')
                        pass  # TODO convert exponent to ZIP
                    else:  # ZIP model
                        # TODO check all attributes
                        p = cgmes_elm.p * cgmes_elm.LoadResponse.pConstantPower
                        q = cgmes_elm.q * cgmes_elm.LoadResponse.qConstantPower
                        i_r = cgmes_elm.p * cgmes_elm.LoadResponse.pConstantCurrent
                        i_i = cgmes_elm.q * cgmes_elm.LoadResponse.qConstantCurrent

                        # g = cgmes_elm.p / cgmes_elm.LoadResponse.pConstantImpedance  # TODO ask Chavdar
                        g = cgmes_elm.p * cgmes_elm.LoadResponse.pConstantImpedance
                        b = cgmes_elm.q * cgmes_elm.LoadResponse.qConstantImpedance
                else:
                    p = cgmes_elm.p
                    q = cgmes_elm.q

                gcdev_elm = gcdev.Load(idtag=cgmes_elm.uuid,
                                       code=cgmes_elm.description,
                                       name=cgmes_elm.name,
                                       active=True,
                                       P=p,
                                       Q=q,
                                       Ir=i_r,
                                       Ii=i_i,
                                       G=g,
                                       B=b)
                gcdev_model.add_load(calc_node, gcdev_elm)

            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def get_gcdev_generators(cgmes_model: CgmesCircuit,
                         gcdev_model: MultiCircuit,
                         calc_node_dict: Dict[str, gcdev.Bus],
                         cn_dict: Dict[str, gcdev.ConnectivityNode],
                         device_to_terminal_dict: Dict[str, List[Terminal]],
                         logger: DataLogger) -> None:
    """
    Convert the CGMES generators to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: Logger object
    """
    # add generation technologies
    general_tech = gcdev.Technology(idtag='', code='', name='General')
    thermal_tech = gcdev.Technology(idtag='', code='', name='Thermal')
    hydro_tech = gcdev.Technology(idtag='', code='', name='Hydro')
    solar_tech = gcdev.Technology(idtag='', code='', name='Solar')
    wind_tech = gcdev.Technology(idtag='', code='', name='Wind')
    nuclear_tech = gcdev.Technology(idtag='', code='', name='Nuclear')

    gcdev_model.add_technology(general_tech)
    gcdev_model.add_technology(thermal_tech)
    gcdev_model.add_technology(hydro_tech)
    gcdev_model.add_technology(solar_tech)
    gcdev_model.add_technology(wind_tech)
    gcdev_model.add_technology(nuclear_tech)

    tech_dict = {
        "GeneratingUnit": general_tech,
        "ThermalGeneratingUnit": thermal_tech,
        "HydroGeneratingUnit": hydro_tech,
        "SolarGeneratingUnit": solar_tech,
        "WindGeneratingUnit": wind_tech,
        "NuclearGeneratingUnit": nuclear_tech,
    }

    # plants_dict: Dict[str, gcdev.aggregation.Plant] = dict()

    # convert generators
    for device_list in [cgmes_model.SynchronousMachine_list]:
        for cgmes_elm in device_list:
            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]
                cn = cns[0]

                if cgmes_elm.GeneratingUnit is not None:

                    v_set, is_controlled = get_regulating_control(cgmes_elm=cgmes_elm,
                                                                  cgmes_enums=cgmes_enums,
                                                                  logger=logger)

                    if cgmes_elm.p != 0.0:
                        pf = np.cos(np.arctan(cgmes_elm.q / cgmes_elm.p))
                    else:
                        pf = 0.8

                    technology = tech_dict.get(cgmes_elm.GeneratingUnit.tpe, None)

                    gcdev_elm = gcdev.Generator(idtag=cgmes_elm.uuid,
                                                code=cgmes_elm.description,
                                                name=cgmes_elm.name,
                                                active=True,
                                                technology=technology,
                                                Snom=cgmes_elm.ratedS,
                                                P=-cgmes_elm.p,
                                                Pmin=cgmes_elm.GeneratingUnit.minOperatingP,
                                                Pmax=cgmes_elm.GeneratingUnit.maxOperatingP,
                                                power_factor=pf,
                                                Qmax=cgmes_elm.maxQ,
                                                Qmin=cgmes_elm.minQ,
                                                vset=v_set,
                                                is_controlled=is_controlled)

                    gcdev_model.add_generator(calc_node, gcdev_elm)

                    if technology:
                        gen_tech = gcdev.GeneratorTechnology(name=gcdev_elm.name + "_" + technology.name,
                                                             generator=gcdev_elm,
                                                             technology=technology)
                        gcdev_model.add_generator_technology(gen_tech)
                        # gcdev_model.add_generator_fuel()
                else:
                    logger.add_error(msg='SynchronousMachine has no generating unit',
                                     device=cgmes_elm.rdfid,
                                     device_class=cgmes_elm.tpe,
                                     device_property="GeneratingUnit",
                                     value='None',
                                     expected_value='Something')
            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def get_gcdev_external_grids(cgmes_model: CgmesCircuit,
                             gcdev_model: MultiCircuit,
                             calc_node_dict: Dict[str, gcdev.Bus],
                             cn_dict: Dict[str, gcdev.ConnectivityNode],
                             device_to_terminal_dict: Dict[str, List[Terminal]],
                             logger: DataLogger) -> None:
    """
    Convert the CGMES loads to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    """
    # convert loads
    for device_list in [cgmes_model.EquivalentInjection_list]:
        # TODO ExternalNetworkInjection
        for cgmes_elm in device_list:
            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]
                cn = cns[0]

                gcdev_elm = gcdev.ExternalGrid(idtag=cgmes_elm.uuid,
                                               code=cgmes_elm.description,
                                               name=cgmes_elm.name,
                                               active=True,
                                               P=cgmes_elm.p,
                                               Q=cgmes_elm.q)

                gcdev_model.add_external_grid(calc_node, gcdev_elm)
            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def get_gcdev_ac_lines(cgmes_model: CgmesCircuit,
                       gcdev_model: MultiCircuit,
                       calc_node_dict: Dict[str, gcdev.Bus],
                       cn_dict: Dict[str, gcdev.ConnectivityNode],
                       device_to_terminal_dict: Dict[str, List[Terminal]],
                       logger: DataLogger,
                       Sbase: float) -> None:
    """
    Convert the CGMES ac lines to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :param Sbase: system base power in MVA
    :return: None
    """

    # build the ratings dictionary
    rates_dict = dict()
    for e in cgmes_model.CurrentLimit_list:
        if not isinstance(e.OperationalLimitSet, str):
            if isinstance(e.OperationalLimitSet, list):
                for ols in e.OperationalLimitSet:
                    if isinstance(ols.Terminal.ConductingEquipment, ACLineSegment):
                        branch_id = e.OperationalLimitSet.Terminal.ConductingEquipment.uuid
                        rates_dict[branch_id] = e.value
            else:
                if isinstance(e.OperationalLimitSet.Terminal.ConductingEquipment, ACLineSegment):
                    branch_id = e.OperationalLimitSet.Terminal.ConductingEquipment.uuid
                    rates_dict[branch_id] = e.value

    # convert ac lines
    for device_list in [cgmes_model.ACLineSegment_list]:
        for cgmes_elm in device_list:
            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 2:
                calc_node_f = calc_nodes[0]
                calc_node_t = calc_nodes[1]
                cn_f = cns[0]
                cn_t = cns[1]

                # get per unit vlaues
                r, x, g, b, r0, x0, g0, b0 = get_pu_values_ac_line_segment(ac_line_segment=cgmes_elm, logger=logger,
                                                                           Sbase=Sbase)

                current_rate = rates_dict.get(cgmes_elm.uuid, None)  # A
                if current_rate:
                    # rate in MVA = kA * kV * sqrt(3)
                    rate = np.round((current_rate / 1000.0) * cgmes_elm.BaseVoltage.nominalVoltage * 1.73205080756888,
                                    4)
                else:
                    rate = 1e-20

                gcdev_elm = gcdev.Line(idtag=cgmes_elm.uuid,
                                       code=cgmes_elm.description,
                                       name=cgmes_elm.name,
                                       active=True,
                                       # cn_from=cn_f,
                                       # cn_to=cn_t,
                                       bus_from=calc_node_f,
                                       bus_to=calc_node_t,
                                       r=r,
                                       x=x,
                                       b=b,
                                       r0=r0,
                                       x0=x0,
                                       b0=b0,
                                       rate=rate,
                                       length=cgmes_elm.length)
                gcdev_model.add_line(gcdev_elm, logger=logger)
            else:
                logger.add_error(msg='Not exactly two terminals',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=2)


def get_gcdev_ac_transformers(cgmes_model: CgmesCircuit,
                              gcdev_model: MultiCircuit,
                              calc_node_dict: Dict[str, gcdev.Bus],
                              cn_dict: Dict[str, gcdev.ConnectivityNode],
                              device_to_terminal_dict: Dict[str, List[Terminal]],
                              logger: DataLogger,
                              Sbase: float) -> None:
    """
    Convert the CGMES ac lines to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :param Sbase: system base power in MVA
    :return: None
    """

    # convert ac lines
    for device_list in [cgmes_model.PowerTransformer_list]:

        for cgmes_elm in device_list:

            windings = [None, None, None]
            for pte in list(cgmes_elm.PowerTransformerEnd):
                if hasattr(pte, "endNumber"):
                    i = getattr(pte, "endNumber")
                    windings[i - 1] = pte
            windings = [x for x in windings if x is not None]
            # windings = get_windings(cgmes_elm)
            # windings: List[PowerTransformerEnd] = list(cgmes_elm.references_to_me['PowerTransformerEnd'])

            if len(windings) == 2:
                calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                                   device_to_terminal_dict=device_to_terminal_dict,
                                                   calc_node_dict=calc_node_dict,
                                                   cn_dict=cn_dict,
                                                   logger=logger)

                if len(calc_nodes) == 2:
                    calc_node_f = calc_nodes[0]
                    calc_node_t = calc_nodes[1]
                    cn_f = cns[0]
                    cn_t = cns[1]

                    # v1 = windings[0].BaseVoltage.nominalVoltage
                    # v2 = windings[1].BaseVoltage.nominalVoltage
                    HV = windings[0].ratedU
                    LV = windings[1].ratedU
                    # HV = max(v1, v2)
                    # LV = min(v1, v2)
                    # get per unit vlaues

                    r, x, g, b, r0, x0, g0, b0 = get_pu_values_power_transformer(cgmes_elm, Sbase)
                    rated_s = windings[0].ratedS

                    gcdev_elm = gcdev.Transformer2W(idtag=cgmes_elm.uuid,
                                                    code=cgmes_elm.description,
                                                    name=cgmes_elm.name,
                                                    active=True,
                                                    # cn_from=cn_f,
                                                    # cn_to=cn_t,
                                                    bus_from=calc_node_f,
                                                    bus_to=calc_node_t,
                                                    nominal_power=rated_s,
                                                    HV=HV,
                                                    LV=LV,
                                                    r=r,
                                                    x=x,
                                                    g=g,
                                                    b=b,
                                                    r0=r0,
                                                    x0=x0,
                                                    g0=g0,
                                                    b0=b0,
                                                    tap_module=1.0,
                                                    tap_phase=0.0,
                                                    # rate=get_rate(cgmes_elm))
                                                    rate=rated_s)

                    gcdev_model.add_transformer2w(gcdev_elm)
                else:
                    logger.add_error(msg='Not exactly two terminals',
                                     device=cgmes_elm.rdfid,
                                     device_class=cgmes_elm.tpe,
                                     device_property="number of associated terminals",
                                     value=len(calc_nodes),
                                     expected_value=2)

            elif len(windings) == 3:
                calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                                   device_to_terminal_dict=device_to_terminal_dict,
                                                   calc_node_dict=calc_node_dict,
                                                   cn_dict=cn_dict,
                                                   logger=logger)

                if len(calc_nodes) == 3:
                    calc_node_1 = calc_nodes[0]
                    calc_node_2 = calc_nodes[1]
                    calc_node_3 = calc_nodes[2]
                    cn_1 = cns[0]
                    cn_2 = cns[1]
                    cn_3 = cns[2]

                    # v1 = windings[0].BaseVoltage.nominalVoltage
                    # v2 = windings[1].BaseVoltage.nominalVoltage
                    # v3 = windings[2].BaseVoltage.nominalVoltage
                    v1 = windings[0].ratedU
                    v2 = windings[1].ratedU
                    v3 = windings[2].ratedU
                    # HV = max(v1, v2, v3)
                    # LV = min(v1, v2, v3)
                    # get per unit values

                    r12, r23, r31, x12, x23, x31 = get_pu_values_power_transformer3w(cgmes_elm, Sbase)

                    gcdev_elm = gcdev.Transformer3W(idtag=cgmes_elm.uuid,
                                                    code=cgmes_elm.description,
                                                    name=cgmes_elm.name,
                                                    active=True,
                                                    bus1=calc_node_1,
                                                    bus2=calc_node_2,
                                                    bus3=calc_node_3,
                                                    V1=v1,
                                                    V2=v2,
                                                    V3=v3,
                                                    r12=r12, r23=r23, r31=r31,
                                                    x12=x12, x23=x23, x31=x31,
                                                    rate12=windings[0].ratedS,
                                                    rate23=windings[1].ratedS,
                                                    rate31=windings[2].ratedS,
                                                    x=0.0, y=0.0
                                                    )
                    r, x, g, b, r0, x0, g0, b0 = get_pu_values_power_transformer_end(windings[0], Sbase)
                    gcdev_elm.winding1.R = r
                    gcdev_elm.winding1.X = x
                    gcdev_elm.winding1.G = g
                    gcdev_elm.winding1.B = b
                    gcdev_elm.winding1.R0 = r0
                    gcdev_elm.winding1.X0 = x0
                    gcdev_elm.winding1.G0 = g0
                    gcdev_elm.winding1.B0 = b0
                    gcdev_elm.winding1.rate = windings[0].ratedS

                    r, x, g, b, r0, x0, g0, b0 = get_pu_values_power_transformer_end(windings[1], Sbase)
                    gcdev_elm.winding2.R = r
                    gcdev_elm.winding2.X = x
                    gcdev_elm.winding2.G = g
                    gcdev_elm.winding2.B = b
                    gcdev_elm.winding2.R0 = r0
                    gcdev_elm.winding2.X0 = x0
                    gcdev_elm.winding2.G0 = g0
                    gcdev_elm.winding2.B0 = b0
                    gcdev_elm.winding2.rate = windings[1].ratedS

                    r, x, g, b, r0, x0, g0, b0 = get_pu_values_power_transformer_end(windings[2], Sbase)
                    gcdev_elm.winding3.R = r
                    gcdev_elm.winding3.X = x
                    gcdev_elm.winding3.G = g
                    gcdev_elm.winding3.B = b
                    gcdev_elm.winding3.R0 = r0
                    gcdev_elm.winding3.X0 = x0
                    gcdev_elm.winding3.G0 = g0
                    gcdev_elm.winding3.B0 = b0
                    gcdev_elm.winding3.rate = windings[2].ratedS

                    gcdev_model.add_transformer3w(gcdev_elm)


                else:
                    logger.add_error(msg='Not exactly three terminals',
                                     device=cgmes_elm.rdfid,
                                     device_class=cgmes_elm.tpe,
                                     device_property="number of associated terminals",
                                     value=len(calc_nodes),
                                     expected_value=2)

            else:
                logger.add_error(msg='Transformers with {} windings not supported yet'.format(len(windings)),
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="windings",
                                 value=len(windings),
                                 expected_value=2)


def get_gcdev_shunts(cgmes_model: CgmesCircuit,
                     gcdev_model: MultiCircuit,
                     calc_node_dict: Dict[str, gcdev.Bus],
                     cn_dict: Dict[str, gcdev.ConnectivityNode],
                     device_to_terminal_dict: Dict[str, List[Terminal]],
                     logger: DataLogger,
                     Sbase: float) -> None:
    """
    Convert the CGMES shunts to gcdev

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    """
    # convert shunts
    for device_list in [cgmes_model.LinearShuntCompensator_list, cgmes_model.NonlinearShuntCompensator_list]:

        for cgmes_elm in device_list:

            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]
                cn = cns[0]

                # conversion
                G, B, G0, B0 = get_values_shunt(shunt=cgmes_elm,
                                                logger=logger,
                                                Sbase=Sbase)
                v_set, is_controlled = get_regulating_control(
                    cgmes_elm=cgmes_elm,
                    cgmes_enums=cgmes_enums,
                    logger=logger)

                gcdev_elm = gcdev.Shunt(
                    idtag=cgmes_elm.uuid,
                    name=cgmes_elm.name,
                    code=cgmes_elm.description,
                    G=G * cgmes_elm.sections,
                    B=B * cgmes_elm.sections,
                    G0=G0 * cgmes_elm.sections,
                    B0=B0 * cgmes_elm.sections,
                    # Bmax=B * cgmes_elm.maximumSections,
                    # Bmin=B,
                    active=True,  # TODO what is this?
                    # controlled=is_controlled,
                    # vset=v_set,
                    # bus=calc_node,  # ?
                    # cn=cn,  # ?
                )
                gcdev_model.add_shunt(calc_node, gcdev_elm)

            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def get_gcdev_switches(cgmes_model: CgmesCircuit,
                       gcdev_model: MultiCircuit,
                       calc_node_dict: Dict[str, gcdev.Bus],
                       cn_dict: Dict[str, gcdev.ConnectivityNode],
                       device_to_terminal_dict: Dict[str, List[Terminal]],
                       logger: DataLogger,
                       Sbase: float) -> None:
    """
    Convert the CGMES switching devices to gcdev

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :param Sbase: system base power in MVA
    :return: None
    """
    # Build the ratings dictionary
    rates_dict = {}
    for e in cgmes_model.CurrentLimit_list:
        if not isinstance(e.OperationalLimitSet, str):
            conducting_equipment = e.OperationalLimitSet.Terminal.ConductingEquipment
            if isinstance(conducting_equipment,
                          (Switch, Breaker, Disconnector, LoadBreakSwitch)):
                branch_id = conducting_equipment.uuid
                rates_dict[branch_id] = e.value

    # convert switch
    for device_list in [cgmes_model.Switch_list,
                        cgmes_model.Breaker_list,
                        cgmes_model.Disconnector_list,
                        cgmes_model.LoadBreakSwitch_list,
                        # cgmes_model.GroundDisconnector_list
                        ]:

        for cgmes_elm in device_list:
            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 2:
                calc_node_f = calc_nodes[0]
                calc_node_t = calc_nodes[1]
                cn_f = cns[0]
                cn_t = cns[1]

                operational_current_rate = rates_dict.get(cgmes_elm.uuid, None)  # A
                if operational_current_rate and cgmes_elm.BaseVoltage is not None:
                    # rate in MVA = A / 1000 * kV * sqrt(3)    CORRECTED!
                    op_rate = np.round((operational_current_rate / 1000.0) *
                                       cgmes_elm.BaseVoltage.nominalVoltage * 1.73205080756888,
                                       4)
                else:
                    op_rate = 9999  # Corrected

                if cgmes_elm.ratedCurrent is not None and cgmes_elm.ratedCurrent != 0.0:  # TODO
                    rated_current = np.round(
                        (cgmes_elm.ratedCurrent / 1000.0) * cgmes_elm.BaseVoltage.nominalVoltage * 1.73205080756888,
                        4)
                else:
                    rated_current = op_rate

                gcdev_elm = gcdev.Switch(
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    name=cgmes_elm.name,
                    active=True,
                    cn_from=cn_f,
                    cn_to=cn_t,
                    bus_from=calc_node_f,
                    bus_to=calc_node_t,
                    rate=op_rate,
                    rated_current=rated_current,
                    is_open=cgmes_elm.open,
                    retained=cgmes_elm.retained,
                    normal_open=cgmes_elm.normalOpen
                )

                gcdev_model.add_switch(gcdev_elm)
            else:
                logger.add_error(msg='Not exactly two terminals',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=2)


def get_gcdev_substations(cgmes_model: CgmesCircuit,
                          gcdev_model: MultiCircuit) -> None:
    """
    Convert the CGMES substations to gcdev substations

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    """
    # convert substations
    for device_list in [cgmes_model.Substation_list]:

        for cgmes_elm in device_list:
            gcdev_elm = gcdev.Substation(
                name=cgmes_elm.name,
                idtag=cgmes_elm.uuid,
                code=cgmes_elm.description,
                # latitude=0.0,     # later from GL profile/Location class
                # longitude=0.0
            )

            gcdev_model.add_substation(gcdev_elm)


def get_gcdev_voltage_levels(cgmes_model: CgmesCircuit,
                             gcdev_model: MultiCircuit,
                             logger: DataLogger) -> None:
    """
    Convert the CGMES voltage levels to gcdev voltage levels

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param logger:
    """
    for cgmes_elm in cgmes_model.VoltageLevel_list:

        gcdev_elm = gcdev.VoltageLevel(
            idtag=cgmes_elm.uuid,
            name=cgmes_elm.name,
            Vnom=cgmes_elm.BaseVoltage.nominalVoltage
        )

        subs = find_object_by_idtag(
            object_list=gcdev_model.substations,
            target_idtag=cgmes_elm.Substation.uuid  # gcdev_elm.idtag
        )
        if subs:
            gcdev_elm.substation = subs

        gcdev_model.add_voltage_level(gcdev_elm)


def get_gcdev_busbars(cgmes_model: CgmesCircuit,
                      gcdev_model: MultiCircuit,
                      calc_node_dict: Dict[str, gcdev.Bus],
                      cn_dict: Dict[str, gcdev.ConnectivityNode],
                      device_to_terminal_dict: Dict[str, List[Terminal]],
                      logger: DataLogger
                      ) -> None:
    """
    Convert the CGMES busbars to gcdev busbars

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    """
    # convert busbars
    for device_list in [cgmes_model.BusbarSection_list]:

        for cgmes_elm in device_list:

            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]
                cn = cns[0]

                container = cgmes_elm.EquipmentContainer
                if isinstance(container, VoltageLevel):
                    substation = container.Substation
                elif isinstance(container, Bay):
                    substation = container.VoltageLevel.Substation
                else:
                    substation = None

                gcdev_elm = gcdev.BusBar(
                    name=cgmes_elm.name,
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    # substation=substation,  #TODO fix it with VoltageLevel
                    cn=cn
                )
                gcdev_model.add_bus_bar(gcdev_elm)

            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def cgmes_to_gridcal(cgmes_model: CgmesCircuit,
                     logger: DataLogger) -> MultiCircuit:
    """
    convert CGMES model to gcdev
    :param cgmes_model: CgmesCircuit
    :param logger: Logger object
    :return: MultiCircuit
    """
    gc_model = MultiCircuit()  # roseta
    Sbase = gc_model.Sbase

    # busbar_dict = parse_bus_bars(cgmes_model, circuit, logger)
    # parse_ac_line_segment(cgmes_model, circuit, busbar_dict, logger)
    # parse_power_transformer(cgmes_model, circuit, busbar_dict, logger)
    # parse_switches(cgmes_model, circuit, busbar_dict, logger)
    # parse_loads(cgmes_model, circuit, busbar_dict, logger)
    # parse_shunts(cgmes_model, circuit, busbar_dict, logger)
    # parse_generators(cgmes_model, circuit, busbar_dict, logger)

    get_gcdev_substations(cgmes_model, gc_model)
    get_gcdev_voltage_levels(cgmes_model, gc_model, logger)

    sv_volt_dict = get_gcdev_voltage_dict(cgmes_model, logger)
    device_to_terminal_dict = get_gcdev_device_to_terminal_dict(cgmes_model, logger)

    calc_node_dict = get_gcdev_calculation_nodes(cgmes_model, gc_model, sv_volt_dict, logger)
    cn_dict = get_gcdev_connectivity_nodes(cgmes_model, gc_model, calc_node_dict, logger)
    get_gcdev_busbars(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)

    get_gcdev_loads(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)
    get_gcdev_external_grids(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)
    get_gcdev_generators(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)

    get_gcdev_ac_lines(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger, Sbase)
    get_gcdev_ac_transformers(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger, Sbase)

    get_gcdev_shunts(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger, Sbase)
    get_gcdev_switches(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger, Sbase)

    print('debug')

    # Gridcal to cgmes
    cgmes_model_export = gridcal_to_cgmes(gc_model, logger)

    # Export with ET
    start = time.time()
    serializer = CimExporter(cgmes_model)
    serializer.export()
    end = time.time()
    print("ET export time: ", end - start, "sec")

    return gc_model
