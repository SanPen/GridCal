# GridCal
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
import numpy as np
from typing import Dict, List, Tuple
import GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums as cgmes_enums
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.line.ac_line_segment import ACLineSegment
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Core.Devices as gcdev
from GridCalEngine.data_logger import DataLogger


def find_terms_connections(cgmes_terminal,
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


def get_gcdev_calculation_nodes(cgmes_model: CgmesCircuit,
                                gc_model: MultiCircuit,
                                v_dict: Dict[str, Tuple[float, float]],
                                logger: DataLogger) -> Dict[str, gcdev.Bus]:
    """
    Convert the TopologicalNodes to CalculationNodes
    :param cgmes_model: CgmesCircuit
    :param gc_model: gcdevCircuit
    :param v_dict: Dict[str, Terminal]
    :return: dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus]
    """
    # dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
    calc_node_dict: Dict[str, gcdev.Bus] = dict()
    for cgmes_elm in cgmes_model.TopologicalNode_list:

        voltage = v_dict.get(cgmes_elm.uuid, None)
        nominal_voltage = cgmes_elm.get_nominal_voltage(logger=logger)
        if voltage is not None and nominal_voltage is not None:
            vm = voltage[0] / nominal_voltage
            va = np.deg2rad(voltage[1])
        else:
            vm = 1.0
            va = 0.0

        gcdev_elm = gcdev.Bus(idtag=cgmes_elm.uuid,
                              code=cgmes_elm.description,
                              name=cgmes_elm.name,
                              active=True,
                              vnom=nominal_voltage,
                              is_dc=False,
                              is_slack=False,
                              vmin=0.9,
                              vmax=1.1,
                              latitude=0.0,
                              longitude=0.0,
                              area=None,
                              zone=None,
                              Vm0=vm,
                              Va0=va)

        gc_model.add_bus(gcdev_elm)
        calc_node_dict[gcdev_elm.idtag] = gcdev_elm

    return calc_node_dict


def get_gcdev_connectivity_nodes(cgmes_model: CgmesCircuit,
                                 gcdev_model: MultiCircuit) \
        -> Dict[str, gcdev.ConnectivityNode]:
    """
    Convert the TopologicalNodes to CalculationNodes
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :return: dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus]
    """
    # dictionary relating the ConnectivityNode uuid to the gcdev ConnectivityNode
    cn_node_dict: Dict[str, gcdev.ConnectivityNode] = dict()
    for cgmes_elm in cgmes_model.ConnectivityNode_list:
        gcdev_elm = gcdev.ConnectivityNode(idtag=cgmes_elm.uuid,
                                           code=cgmes_elm.description,
                                           name=cgmes_elm.name,
                                           dc=False,
                                           bus_bar=None)

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
    for device_list in [cgmes_model.ConformLoad_list, cgmes_model.NonConformLoad_list]:
        for cgmes_elm in device_list:
            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]
                cn = cns[0]

                gcdev_elm = gcdev.Load(idtag=cgmes_elm.uuid,
                                       code=cgmes_elm.description,
                                       name=cgmes_elm.name,
                                       active=True,
                                       P=cgmes_elm.p,
                                       Q=cgmes_elm.q,
                                       Ir=0.0,
                                       Ii=0.0,
                                       G=0.0,
                                       B=0.0)
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

                    if cgmes_elm.RegulatingControl is not None:
                        if cgmes_elm.RegulatingControl.mode == cgmes_enums.RegulatingControlModeKind.voltage:

                            if cgmes_elm.EquipmentContainer.tpe == 'VoltageLevel':
                                v_control_value = cgmes_elm.RegulatingControl.targetValue  # kV
                                v_set = v_control_value / cgmes_elm.EquipmentContainer.BaseVoltage.nominalVoltage
                                is_controlled = True

                                # find the control node
                                control_terminal = cgmes_elm.RegulatingControl.Terminal
                                control_node, cn = find_terms_connections(cgmes_terminal=control_terminal,
                                                                          calc_node_dict=calc_node_dict,
                                                                          cn_dict=cn_dict)

                                print(end='')

                            else:
                                control_node = None
                                v_set = 1.0
                                is_controlled = False
                                logger.add_warning(msg='SynchronousMachine has no voltage control',
                                                   device=cgmes_elm.rdfid,
                                                   device_class=cgmes_elm.tpe,
                                                   device_property="EquipmentContainer",
                                                   value='None',
                                                   expected_value='BaseVoltage')

                        else:
                            control_node = None
                            v_set = 1.0
                            is_controlled = False
                            logger.add_warning(msg='SynchronousMachine has no voltage control',
                                               device=cgmes_elm.rdfid,
                                               device_class=cgmes_elm.tpe,
                                               device_property="EquipmentContainer",
                                               value='None',
                                               expected_value='BaseVoltage')
                    else:
                        control_node = None
                        v_set = 1.0
                        is_controlled = False
                        logger.add_warning(msg='SynchronousMachine has no voltage control',
                                           device=cgmes_elm.rdfid,
                                           device_class=cgmes_elm.tpe,
                                           device_property="EquipmentContainer",
                                           value='None',
                                           expected_value='BaseVoltage')

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
                r, x, g, b, r0, x0, g0, b0 = cgmes_elm.get_pu_values(logger, Sbase)

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

            windings: List[PowerTransformerEnd] = list(cgmes_elm.references_to_me['PowerTransformerEnd'])

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

                    v1 = windings[0].BaseVoltage.nominalVoltage
                    v2 = windings[1].BaseVoltage.nominalVoltage
                    HV = max(v1, v2)
                    LV = min(v1, v2)
                    # get per unit vlaues

                    r, x, g, b, r0, x0, g0, b0 = cgmes_elm.get_pu_values(Sbase)

                    gcdev_elm = gcdev.Transformer2W(idtag=cgmes_elm.uuid,
                                                    code=cgmes_elm.description,
                                                    name=cgmes_elm.name,
                                                    active=True,
                                                    # cn_from=cn_f,
                                                    # cn_to=cn_t,
                                                    bus_from=calc_node_f,
                                                    bus_to=calc_node_t,
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
                                                    rate=cgmes_elm.get_rate())

                    gcdev_model.add_transformer2w(gcdev_elm)
                else:
                    logger.add_error(msg='Not exactly two terminals',
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


def cgmes_to_gridcal(cgmes_model: CgmesCircuit, logger: DataLogger) -> MultiCircuit:
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

    # build the voltages dictionary
    v_dict = dict()
    for e in cgmes_model.SvVoltage_list:
        if not isinstance(e.TopologicalNode, str):
            v_dict[e.TopologicalNode.uuid] = (e.v, e.angle)
        else:
            logger.add_error(msg='Missing refference',
                             device=e.rdfid,
                             device_class=e.tpe,
                             device_property="TopologicalNode",
                             value=e.TopologicalNode,
                             expected_value='object')

    # dictionary relating the conducting equipement to the terminal object
    device_to_terminal_dict: Dict[str, List[Terminal]] = dict()
    for e in cgmes_model.Terminal_list:
        lst = device_to_terminal_dict.get(e.ConductingEquipment.uuid, None)
        if lst is None:
            device_to_terminal_dict[e.ConductingEquipment.uuid] = [e]
        else:
            lst.append(e)

    calc_node_dict = get_gcdev_calculation_nodes(cgmes_model, gc_model, v_dict, logger)
    cn_dict = get_gcdev_connectivity_nodes(cgmes_model, gc_model)
    get_gcdev_loads(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)
    get_gcdev_external_grids(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)
    get_gcdev_generators(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)

    get_gcdev_ac_lines(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger, Sbase)
    get_gcdev_ac_transformers(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger, Sbase)

    return gc_model
