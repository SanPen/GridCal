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
from typing import Dict, List
import GridCal.Engine.IO.cim.cgmes_2_4_15.cim_enums as cgmes_enums
from GridCal.Engine.IO.cim.cgmes_2_4_15.devices.terminal import Terminal
from GridCal.Engine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCal.Engine.IO.cim.cgmes_2_4_15.cgmes_circuit import CgmesCircuit
from GridCal.Engine.Core.Devices.multi_circuit import MultiCircuit
import GridCal.Engine.Core.Devices as gcdev
from GridCal.Engine.basic_structures import Logger


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
                     logger: Logger):
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
                                v_dict: Dict[str, Terminal]) -> Dict[str, gcdev.Bus]:
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
        nominal_voltage = cgmes_elm.get_nominal_voltage()
        if voltage is not None:
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
                    logger: Logger) -> None:
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
                         logger: Logger) -> None:
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
                            control_terminal = cgmes_elm.RegulatingControl.Terminal
                            v_control_value = cgmes_elm.RegulatingControl.targetValue

                            if cgmes_elm.EquipmentContainer.tpe == 'VoltageLevel':
                                v_set = v_control_value / cgmes_elm.EquipmentContainer.BaseVoltage.nominalVoltage

                                # find the control node
                                calc_node, cn = find_terms_connections(cgmes_terminal=control_terminal,
                                                                       calc_node_dict=calc_node_dict,
                                                                       cn_dict=cn_dict)

                                # try and see if the plant was created already:
                                # plant = plants_dict.get(control_terminal.uuid, None)
                                #
                                # if plant is None:
                                #     # create a control plant object
                                #     plant = gcdev.aggregation.Plant(idtag='',
                                #                                     code='',
                                #                                     name=calc_node.name if calc_node is not None else "",
                                #                                     cn=cn,
                                #                                     calc_node=calc_node,
                                #                                     v_set=v_set)
                                #
                                #     gcdev_model.plants.append(plant)
                                #     plants_dict[control_terminal.uuid] = plant
                                # else:
                                #     # check
                                #     if plant.v_set != v_set:
                                #         logger.add_warning(msg='More than one voltage control set point',
                                #                            device=cgmes_elm.rdfid,
                                #                            device_class=cgmes_elm.tpe,
                                #                            device_property="EquipmentContainer",
                                #                            value=v_set,
                                #                            expected_value=plant.v_set)

                            else:
                                control_terminal = None
                                plant = None
                                logger.add_warning(msg='SynchronousMachine has no voltage control',
                                                   device=cgmes_elm.rdfid,
                                                   device_class=cgmes_elm.tpe,
                                                   device_property="EquipmentContainer",
                                                   value='None',
                                                   expected_value='BaseVoltage')

                        else:
                            control_terminal = None
                            plant = None
                            logger.add_warning(msg='SynchronousMachine has no voltage control',
                                               device=cgmes_elm.rdfid,
                                               device_class=cgmes_elm.tpe,
                                               device_property="EquipmentContainer",
                                               value='None',
                                               expected_value='BaseVoltage')
                    else:
                        control_terminal = None
                        plant = None
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
                                                active_power=cgmes_elm.p,
                                                p_min=cgmes_elm.GeneratingUnit.minOperatingP,
                                                p_max=cgmes_elm.GeneratingUnit.maxOperatingP,
                                                power_factor=pf,
                                                Qmax=cgmes_elm.maxQ,
                                                Qmin=cgmes_elm.minQ)

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


def get_gcdev_ac_lines(cgmes_model: CgmesCircuit,
                       gcdev_model: MultiCircuit,
                       calc_node_dict: Dict[str, gcdev.Bus],
                       cn_dict: Dict[str, gcdev.ConnectivityNode],
                       device_to_terminal_dict: Dict[str, List[Terminal]],
                       logger: Logger) -> None:
    """
    Convert the CGMES ac lines to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    :return:
    """
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

                gcdev_elm = gcdev.Line(idtag=cgmes_elm.uuid,
                                       code=cgmes_elm.description,
                                       name=cgmes_elm.name,
                                       active=True,
                                       # cn_from=cn_f,
                                       # cn_to=cn_t,
                                       bus_from=calc_node_f,
                                       bus_to=calc_node_t,
                                       r=0.0,
                                       x=0.0,
                                       b=0.0,
                                       r0=0.0,
                                       x0=0.0,
                                       b0=0.0,
                                       length=0.0)
                gcdev_model.add_line(gcdev_elm, logger=logger)
            else:
                logger.add_error(msg='Not exactly two terminals',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=2)


# def parse_bus_bars(cim: CgmesCircuit, circuit: MultiCircuit, logger: Logger):
#     """
#
#     :param cim:
#     :param circuit:
#     :param logger:
#     :return:
#     """
#
#     busbar_dict = dict()
#
#     if 'BusbarSection' in cim.elements_by_type.keys():
#         for elm in cim.elements_by_type['BusbarSection']:
#             obj = gcdev.Bus(name=str(elm.name),
#                             idtag=elm.uuid)
#
#             circuit.add_bus(obj)
#
#             busbar_dict[elm] = obj
#     else:
#         logger.add_error("No BusbarSections: There is no chance to reduce the grid")
#
#     return busbar_dict
#
#
# def parse_ac_line_segment(cim: CgmesCircuit, circuit: MultiCircuit, busbar_dict, logger: Logger):
#     """
#
#     :param cim:
#     :param circuit:
#     :param busbar_dict:
#     :return:
#     """
#
#     if 'ACLineSegment' in cim.elements_by_type.keys():
#         for elm in cim.elements_by_type['ACLineSegment']:
#
#             b1, b2 = elm.get_buses()
#
#             B1, B2 = try_buses(b1, b2, busbar_dict)
#
#             if B1 is not None and B2 is not None:
#                 R, X, G, B = elm.get_pu_values()
#                 rate = elm.get_rate()
#
#                 # create AcLineSegment (Line)
#                 line = gcdev.Line(idtag=elm.uuid,
#                                   bus_from=B1,
#                                   bus_to=B2,
#                                   name=str(elm.name),
#                                   r=R,
#                                   x=X,
#                                   b=B,
#                                   rate=rate,
#                                   active=True,
#                                   mttf=0,
#                                   mttr=0)
#
#                 circuit.add_line(line)
#             else:
#                 logger.add_error('Bus not found', elm.rdfid)
#
#
# def parse_power_transformer(cim: CgmesCircuit, circuit: MultiCircuit, busbar_dict, logger: Logger):
#     """
#
#     :param cim:
#     :param circuit:
#     :param busbar_dict:
#     :return:
#     """
#     if 'PowerTransformer' in cim.elements_by_type.keys():
#         for elm in cim.elements_by_type['PowerTransformer']:
#             b1, b2 = elm.get_buses()
#             B1, B2 = try_buses(b1, b2, busbar_dict)
#
#             if B1 is not None and B2 is not None:
#                 R, X, G, B = elm.get_pu_values()
#                 rate = elm.get_rate()
#
#                 voltages = elm.get_voltages()
#                 voltages.sort()
#
#                 if len(voltages) == 2:
#                     lv, hv = voltages
#                 else:
#                     lv = 1
#                     hv = 1
#                     logger.add_error('Could not parse transformer nominal voltages', elm.name)
#
#                 line = gcdev.Transformer2W(idtag=cimdev.rfid2uuid(elm.rdfid),
#                                            bus_from=B1,
#                                            bus_to=B2,
#                                            name=str(elm.name),
#                                            r=R,
#                                            x=X,
#                                            g=G,
#                                            b=B,
#                                            rate=rate,
#                                            tap=1.0,
#                                            shift_angle=0,
#                                            active=True,
#                                            HV=hv,
#                                            LV=lv)
#
#                 circuit.add_branch(line)
#             else:
#                 logger.add_error('Bus not found', elm.rdfid)
#
#
# def parse_switches(cim: CgmesCircuit, circuit: MultiCircuit, busbar_dict, logger: Logger):
#     """
#
#     :param cim:
#     :param circuit:
#     :param busbar_dict:
#     :return:
#     """
#     EPS = 1e-20
#     cim_switches = ['Switch', 'Disconnector', 'Breaker', 'LoadBreakSwitch']
#     if any_in_dict(cim.elements_by_type, cim_switches):
#         for elm in get_elements(cim.elements_by_type, cim_switches):
#             b1, b2 = elm.get_buses()
#             B1, B2 = try_buses(b1, b2, busbar_dict)
#
#             if B1 is not None and B2 is not None:
#                 state = True
#                 line = gcdev.Switch(idtag=elm.uuid,
#                                     bus_from=B1,
#                                     bus_to=B2,
#                                     name=str(elm.name),
#                                     r=EPS,
#                                     x=EPS,
#                                     rate=EPS,
#                                     active=state)
#
#                 circuit.add_switch(line)
#             else:
#                 logger.add_error('Bus not found', elm.rdfid)
#
#
# def parse_loads(cim: CgmesCircuit, circuit: MultiCircuit, busbar_dict, logger: Logger):
#     """
#
#     :param cim:
#     :param circuit:
#     :param busbar_dict:
#     :return:
#     """
#     cim_loads = ['ConformLoad', 'EnergyConsumer', 'NonConformLoad']
#     if any_in_dict(cim.elements_by_type, cim_loads):
#         for elm in get_elements(cim.elements_by_type, cim_loads):
#
#             b1 = elm.get_bus()
#             B1 = try_bus(b1, busbar_dict)
#
#             if B1 is not None:
#
#                 p, q = elm.get_pq()
#
#                 load = gcdev.Load(idtag=elm.uuid,
#                                   name=str(elm.name),
#                                   G=0,
#                                   B=0,
#                                   Ir=0,
#                                   Ii=0,
#                                   P=p if p is not None else 0,
#                                   Q=q if q is not None else 0)
#                 circuit.add_load(B1, load)
#             else:
#                 logger.add_error('Bus not found', elm.rdfid)
#
#
# def parse_shunts(cim: CgmesCircuit, circuit: MultiCircuit, busbar_dict, logger: Logger):
#     """
#
#     :param cim:
#     :param circuit:
#     :param busbar_dict:
#     :return:
#     """
#     if 'ShuntCompensator' in cim.elements_by_type.keys():
#         for elm in cim.elements_by_type['ShuntCompensator']:
#             b1 = elm.get_bus()
#             B1 = try_bus(b1, busbar_dict)
#
#             if B1 is not None:
#                 g = 0
#                 b = 0
#                 sh = gcdev.Shunt(idtag=elm.uuid,
#                                  name=str(elm.name),
#                                  G=g,
#                                  B=b)
#                 circuit.add_shunt(B1, sh)
#             else:
#                 logger.add_error('Bus not found', elm.rdfid)
#
#
# def parse_generators(cim: CgmesCircuit, circuit: MultiCircuit, busbar_dict, logger: Logger):
#     """
#
#     :param cim:
#     :param circuit:
#     :param busbar_dict:
#     :return:
#     """
#     if 'SynchronousMachine' in cim.elements_by_type.keys():
#         for elm in cim.elements_by_type['SynchronousMachine']:
#             b1 = elm.get_bus()
#             B1 = try_bus(b1, busbar_dict)
#
#             if B1 is not None:
#
#                 gen = gcdev.Generator(idtag=elm.uuid,
#                                       name=str(elm.name),
#                                       active_power=-elm.p,
#                                       # CGMES defines the generator P as negative to indicate a positive injection
#                                       voltage_module=1.0)
#                 circuit.add_generator(B1, gen)
#
#             else:
#                 logger.add_error('Bus not found', elm.rdfid)


def cgmes_to_gridcal(cgmes_model: CgmesCircuit, logger: Logger) -> MultiCircuit:
    """
    convert CGMES model to gcdev
    :param cgmes_model: CgmesCircuit
    :param logger: Logger object
    :return: MultiCircuit
    """
    gc_model = MultiCircuit()

    # busbar_dict = parse_bus_bars(cgmes_model, circuit, logger)
    # parse_ac_line_segment(cgmes_model, circuit, busbar_dict, logger)
    # parse_power_transformer(cgmes_model, circuit, busbar_dict, logger)
    # parse_switches(cgmes_model, circuit, busbar_dict, logger)
    # parse_loads(cgmes_model, circuit, busbar_dict, logger)
    # parse_shunts(cgmes_model, circuit, busbar_dict, logger)
    # parse_generators(cgmes_model, circuit, busbar_dict, logger)

    # build the voltages dictionary
    v_dict = {e.TopologicalNode.uuid: (e.v, e.angle) for e in cgmes_model.SvVoltage_list}

    # dictionary relating the conducting equipement to the terminal object
    device_to_terminal_dict: Dict[str, List[Terminal]] = dict()
    for e in cgmes_model.Terminal_list:
        lst = device_to_terminal_dict.get(e.ConductingEquipment.uuid, None)
        if lst is None:
            device_to_terminal_dict[e.ConductingEquipment.uuid] = [e]
        else:
            lst.append(e)

    calc_node_dict = get_gcdev_calculation_nodes(cgmes_model, gc_model, v_dict)
    cn_dict = get_gcdev_connectivity_nodes(cgmes_model, gc_model)
    get_gcdev_loads(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)
    get_gcdev_generators(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)

    get_gcdev_ac_lines(cgmes_model, gc_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)

    return gc_model
