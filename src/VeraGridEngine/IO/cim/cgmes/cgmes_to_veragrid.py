# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Tuple, Union
import numpy as np
import VeraGridEngine.IO.cim.cgmes.cgmes_enums as cgmes_enums
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import CGMESVersions, ConverterControlType
import VeraGridEngine.Devices as gcdev
import VeraGridEngine.IO.cim.cgmes.cgmes_assets.cgmes_2_4_15_assets as cgmes24
import VeraGridEngine.IO.cim.cgmes.cgmes_assets.cgmes_3_0_0_assets as cgmes30
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_typing import (CGMES_TERMINAL, CGMES_TOPOLOGICAL_NODE,
                                                      CGMES_CONNECTIVITY_NODE, CGMES_DC_TERMINAL, CGMES_ASSETS)

from VeraGridEngine.IO.cim.cgmes.cgmes_utils import (get_nominal_voltage,
                                                     get_nominal_voltage_for_cn,
                                                     get_pu_values_ac_line_segment,
                                                     get_values_shunt,
                                                     get_pu_values_power_transformer,
                                                     get_pu_values_power_transformer3w,
                                                     get_regulating_control_params,
                                                     get_pu_values_power_transformer_end,
                                                     get_slack_id,
                                                     find_object_by_idtag,
                                                     find_terminal_bus,
                                                     build_cgmes_limit_dicts,
                                                     get_voltage_shunt)

from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.enumerations import TapChangerTypes, TapPhaseControl, TapModuleControl


class Cn2BusBarLookup:
    """
    Class to properly match the ConnectivityNodes to the BusBars
    """

    def __init__(self, cgmes_model: CgmesCircuit):
        """

        :param cgmes_model:
        """
        self.cn_dict: Dict[str, gcdev.Bus] = dict()
        self.bus_dict: Dict[str, gcdev.Bus] = dict()

        # fill information from CGMES terminals
        self.bb_to_cn_dict: Dict[str, CGMES_CONNECTIVITY_NODE] = dict()
        self.bb_to_tn_dict: Dict[str, CGMES_TOPOLOGICAL_NODE] = dict()

        self.fill(cgmes_model=cgmes_model)

    def fill(self, cgmes_model: CgmesCircuit):
        """

        :param cgmes_model:
        :return:
        """
        bb_tpe = cgmes_model.cgmes_assets.class_dict.get("BusbarSection", None)

        if bb_tpe is not None:

            # find the terminal -> CN links
            for terminal in cgmes_model.cgmes_assets.Terminal_list:
                if isinstance(terminal.ConductingEquipment, bb_tpe):

                    if terminal.ConnectivityNode is not None:
                        self.bb_to_cn_dict[terminal.ConductingEquipment.uuid] = terminal.ConnectivityNode

                    if terminal.TopologicalNode is not None:
                        self.bb_to_tn_dict[terminal.ConductingEquipment.uuid] = terminal.TopologicalNode

    def add_cn(self, bus: gcdev.Bus):
        """

        :param bus:
        :return:
        """
        self.cn_dict[bus.idtag] = bus

    def add_bus(self, bus: gcdev.Bus):
        """

        :param bus:
        :return:
        """
        self.bus_dict[bus.idtag] = bus

    def get_busbar_cn(self, bb_id: str) -> Union[None, gcdev.Bus]:
        """
        Get the associated ConnectivityNode object
        :param bb_id: BusBarSection uuid
        :return: Bus or None
        """
        cgmes_cn = self.bb_to_cn_dict.get(bb_id, None)

        if cgmes_cn is not None:
            return self.cn_dict[cgmes_cn.uuid]
        else:
            return None

    def get_busbar_bus(self, bb_id: str) -> Union[None, gcdev.Bus]:
        """
        Get the associated Bus object
        :param bb_id: BusBarSection uuid
        :return: Bus or None
        """
        cgmes_tn = self.bb_to_tn_dict.get(bb_id, None)

        if cgmes_tn is not None:
            return self.bus_dict[cgmes_tn.uuid]
        else:
            return None


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

    for e in cgmes_model.cgmes_assets.SvVoltage_list:
        if e.TopologicalNode and not isinstance(e.TopologicalNode, str):
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
                                      logger: DataLogger) -> Dict[str, List[CGMES_TERMINAL]]:
    """
    Dictionary relating the conducting equipment to the terminal object(s)
    """
    # dictionary relating the conducting equipment to the terminal object
    device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]] = dict()

    if cgmes_model.cgmes_version == CGMESVersions.v2_4_15:
        con_eq_type = cgmes24.ConductingEquipment
    elif cgmes_model.cgmes_version == CGMESVersions.v3_0_0:
        con_eq_type = cgmes30.ConductingEquipment
    else:
        raise NotImplementedError()

    for term in cgmes_model.cgmes_assets.Terminal_list:
        if isinstance(term.ConductingEquipment, con_eq_type):
            lst = device_to_terminal_dict.get(term.ConductingEquipment.uuid, None)
            if lst is None:
                device_to_terminal_dict[term.ConductingEquipment.uuid] = [term]
            else:
                lst.append(term)
        else:
            logger.add_error(msg='The object is not a ConductingEquipment',
                             device=term.rdfid,
                             device_class=term.tpe,
                             device_property="ConductingEquipment",
                             value=term.ConductingEquipment,
                             expected_value='object')
    return device_to_terminal_dict


def get_gcdev_dc_device_to_terminal_dict(
        cgmes_model: CgmesCircuit,
        logger: DataLogger) -> tuple[
    dict[str, list[CGMES_DC_TERMINAL]], list[CGMES_TOPOLOGICAL_NODE], list[CGMES_DC_TERMINAL]]:
    """
    Dictionary relating the DC conducting equipment to the DC terminal object(s)
    :param cgmes_model:
    :param logger:
    :return:
    """

    dc_device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]] = dict()

    if cgmes_model.cgmes_version == CGMESVersions.v2_4_15:
        dc_ground_type = cgmes24.DCGround
        dc_terminal_type = cgmes24.DCTerminal

    elif cgmes_model.cgmes_version == CGMESVersions.v3_0_0:
        dc_ground_type = cgmes30.DCGround
        dc_terminal_type = cgmes30.DCTerminal
    else:
        raise NotImplementedError()

    for dc_term in cgmes_model.cgmes_assets.DCTerminal_list:

        if isinstance(dc_term.DCConductingEquipment, dc_ground_type):
            logger.add_info(msg='DCGround DCTerminals are not imported',
                            device=dc_term.rdfid,
                            device_class=dc_term.tpe,
                            device_property="DCGround",
                            value=dc_term.DCConductingEquipment,
                            comment="get_gcdev_dc_device_to_terminal_dict")
            continue
        else:  # DCTerminals for DCLineSegments
            if dc_term.DCConductingEquipment is not None:
                lst = dc_device_to_terminal_dict.get(dc_term.DCConductingEquipment.uuid, None)
                if lst is None:
                    dc_device_to_terminal_dict[dc_term.DCConductingEquipment.uuid] = [dc_term]
                else:
                    lst.append(dc_term)
            else:
                logger.add_error(msg='No DCConductingEquipment',
                                 device=dc_term.rdfid,
                                 device_class=dc_term.tpe,
                                 device_property="DCConductingEquipment")

    ground_tp_list = list()
    ground_node_list = list()

    # relating the converter terminals to DCTerminals to if DCNode is common
    for conv_dc_term in cgmes_model.cgmes_assets.ACDCConverterDCTerminal_list:

        dc_term_n = None  # DCTerminal inside the same DCNode
        dc_node = conv_dc_term.DCNode

        if dc_node is not None:
            dc_tp = conv_dc_term.DCTopologicalNode
            if isinstance(dc_node.DCTerminals[0], dc_terminal_type):
                dc_term_n = dc_node.DCTerminals[0]
            elif isinstance(dc_node.DCTerminals[1], dc_terminal_type):
                dc_term_n = dc_node.DCTerminals[1]
            else:
                logger.add_error(
                    msg='No DCTerminal in DCNode Terminals [0:1]',
                    device=conv_dc_term.rdfid,
                    device_class=conv_dc_term.tpe,
                    device_property="DCNode",
                    value=conv_dc_term.DCNode,
                    comment="get_gcdev_dc_device_to_terminal_dict"
                )

            if isinstance(dc_term_n.DCConductingEquipment, dc_ground_type):
                logger.add_info(msg='DCGround ACDC converter DC terminals are not imported',
                                device=conv_dc_term.rdfid,
                                device_class=conv_dc_term.tpe,
                                device_property="DCGround",
                                value=conv_dc_term.DCConductingEquipment,
                                comment="get_gcdev_dc_device_to_terminal_dict")
                ground_tp_list.append(dc_tp)
                ground_node_list.append(dc_node)
                continue
            else:  # DCTerminals for ACDCConverter DC side
                dc_cond_eq = conv_dc_term.DCConductingEquipment  # the VSC
                lst = dc_device_to_terminal_dict.get(dc_cond_eq.uuid, None)
                if lst is None:
                    dc_device_to_terminal_dict[dc_cond_eq.uuid] = [dc_term_n]
                else:
                    lst.append(dc_term_n)
        else:
            logger.add_error("DCNode is None",
                             device_class=conv_dc_term.tpe,
                             device=conv_dc_term.rdfid,
                             device_property="DCNode")

    return dc_device_to_terminal_dict, ground_tp_list, ground_node_list


def find_associated_buses(cgmes_elm: CGMES_ASSETS,
                          device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                          bus_dict: Dict[str, gcdev.Bus],
                          TopologicalNode_tpe,
                          DCTopologicalNode_tpe,
                          logger: DataLogger) -> List[gcdev.Bus]:
    """
    This function finds the buses connected to a device
    :param cgmes_elm: some CGMES element
    :param device_to_terminal_dict: dictionary that related the CGMES device to all the terminals it may have
    :param bus_dict: dictionary of VeraGrid buses
    :param TopologicalNode_tpe: TopologicalNode type
                                (might come from different cgmes versions, hence we need to pass the type)
    :param DCTopologicalNode_tpe: DCTopologicalNode type
                                  (might come from different cgmes versions, hence we need to pass the type)
    :param logger: DataLogger
    :return: list of associated buses
    """
    # get the cgmes terminal of this device
    cgmes_terminals = device_to_terminal_dict.get(cgmes_elm.uuid, None)

    if cgmes_terminals is not None:
        buses = list()
        for cgmes_terminal in cgmes_terminals:
            bus = find_terminal_bus(cgmes_terminal,
                                    bus_dict,
                                    TopologicalNode_tpe=TopologicalNode_tpe,
                                    DCTopologicalNode_tpe=DCTopologicalNode_tpe)
            if bus is not None:
                buses.append(bus)
    else:
        buses = []
        logger.add_error("No terminal for the device",
                         device=cgmes_elm.rdfid,
                         device_class=cgmes_elm.tpe)

    return buses


def get_gcdev_buses(cgmes_model: CgmesCircuit,
                    gc_model: MultiCircuit,
                    v_dict: Dict[str, Tuple[float, float]],
                    cn_look_up: Cn2BusBarLookup,
                    skip_dc_import: bool,
                    buses_to_skip: List,
                    default_nominal_voltage: float,
                    logger: DataLogger) -> Tuple[Dict[str, gcdev.Bus], bool]:
    """
    Convert the TopologicalNodes to Buses (CalculationNodes)

    :param cgmes_model: CgmesCircuit
    :param gc_model: gcdevCircuit
    :param v_dict: Dict[str, Terminal]
    :param cn_look_up: CnLookup
    :param logger: DataLogger
    :return: dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus], fatal error?
    """

    slack_id = get_slack_id(cgmes_model.cgmes_assets.SynchronousMachine_list)
    if slack_id is None:
        logger.add_error(msg="Couldn't find referencePriority 1 in the SynchronousMachines.",
                         device_class="SynchronousMachine",
                         device_property="referencePriority")

    # dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
    calc_node_dict: Dict[str, gcdev.Bus] = dict()

    tp_with_cn = set()
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")
    line_tpe = cgmes_model.cgmes_assets.class_dict.get("Line")

    # First convert every CN to a bus
    for cn_elm in cgmes_model.cgmes_assets.ConnectivityNode_list:

        voltage = v_dict.get(cn_elm.uuid, None)
        nominal_voltage = get_nominal_voltage_for_cn(cn=cn_elm, logger=logger)
        if nominal_voltage == 0:
            logger.add_error(msg='Nominal voltage is 0. :(',
                             device=cn_elm.rdfid,
                             device_class=cn_elm.tpe,
                             device_property="nominalVoltage")
        elif nominal_voltage is None:
            logger.add_error(msg='Nominal voltage is None. Maybe boundary was not attached for import :(',
                             device=cn_elm.rdfid,
                             device_class=cn_elm.tpe,
                             device_property="nominalVoltage")
            # raise Exception("Nominal voltage is missing for Bus (Maybe boundary was not attached for import) !")
            return calc_node_dict, True

        if voltage is not None and nominal_voltage is not None:
            if nominal_voltage != 0.0:
                vm = voltage[0] / nominal_voltage
                va = np.deg2rad(voltage[1])
            else:
                logger.add_error("Nominal voltage is exactly zero",
                                 device=cn_elm.rdfid,
                                 device_class=cn_elm.tpe,
                                 device_property="nominalVoltage")
                vm = 1.0
                va = 0.0
        else:
            vm = 1.0
            va = 0.0

        is_slack = False
        if slack_id == cn_elm.rdfid:
            is_slack = True

        gcdev_elm = gcdev.Bus(
            idtag=cn_elm.uuid,
            code=cn_elm.description,
            name=cn_elm.name,
            Vnom=nominal_voltage,
            is_slack=is_slack,
            Va0=va,
            Vm0=vm,
        )

        gc_model.add_bus(gcdev_elm)
        cn_look_up.add_cn(gcdev_elm)
        calc_node_dict[gcdev_elm.idtag] = gcdev_elm

        # Record the associated TopologicalNode
        if hasattr(cn_elm, "TopologicalNode"):
            if isinstance(cn_elm.TopologicalNode, (TopologicalNode_tpe, DCTopologicalNode_tpe)):
                tp_uid = cn_elm.TopologicalNode.uuid
                tp_with_cn.add(tp_uid)
                # we double-record such that the TP is considered later
                calc_node_dict[tp_uid] = gcdev_elm

    # A TopologicalNode is only converted if there is no ConnectivityNode associated
    for tp_node in cgmes_model.cgmes_assets.TopologicalNode_list:

        if not (tp_node.uuid in tp_with_cn):  # if this TP does not have an associated CN ...

            voltage = v_dict.get(tp_node.uuid, None)
            nominal_voltage = get_nominal_voltage(topological_node=tp_node, logger=logger)
            if nominal_voltage == 0:
                logger.add_error(msg='Nominal voltage is 0. :(',
                                 device=tp_node.rdfid,
                                 device_class=tp_node.tpe,
                                 device_property="nominalVoltage")
            elif nominal_voltage is None:
                logger.add_error(msg='Nominal voltage is None. Maybe boundary was not attached for import :(',
                                 device=tp_node.rdfid,
                                 device_class=tp_node.tpe,
                                 device_property="nominalVoltage")
                # raise Exception("Nominal voltage is missing for Bus (Maybe boundary was not attached for import) !")
                return calc_node_dict, True

            if voltage is not None and nominal_voltage is not None:
                if nominal_voltage != 0.0:
                    vm = voltage[0] / nominal_voltage
                    va = np.deg2rad(voltage[1])
                else:
                    logger.add_error("Nominal voltage is exactly zero",
                                     device=tp_node.rdfid,
                                     device_class=tp_node.tpe,
                                     device_property="nominalVoltage")
                    vm = 1.0
                    va = 0.0
            else:
                vm = 1.0
                va = 0.0

            is_slack = False
            if slack_id == tp_node.rdfid:
                is_slack = True

            volt_lev = None
            substation = None
            country = None
            area = None
            zone = None
            longitude = 0.0
            latitude = 0.0
            if tp_node.ConnectivityNodeContainer is not None:

                if isinstance(tp_node.ConnectivityNodeContainer, str):
                    volt_lev: gcdev.VoltageLevel | None = find_object_by_idtag(
                        object_list=gc_model.voltage_levels,
                        target_idtag=tp_node.ConnectivityNodeContainer
                    )
                else:
                    volt_lev: gcdev.VoltageLevel | None = find_object_by_idtag(
                        object_list=gc_model.voltage_levels,
                        target_idtag=tp_node.ConnectivityNodeContainer.uuid
                    )

                if volt_lev is None:
                    if not isinstance(tp_node.ConnectivityNodeContainer, line_tpe):
                        logger.add_warning(msg='No voltage level found for the bus',
                                           device=tp_node.rdfid,
                                           device_class=tp_node.tpe,
                                           device_property="ConnectivityNodeContainer")
                else:
                    if volt_lev.substation is not None:
                        substation: gcdev.Substation | None = find_object_by_idtag(
                            object_list=gc_model.substations,
                            target_idtag=volt_lev.substation.idtag
                        )
                    else:
                        substation = None

                    if substation is None:
                        logger.add_warning(msg='No substation found for bus.',
                                           device=volt_lev.rdfid,
                                           device_class=str(volt_lev),
                                           device_property="substation")
                        print(f'No substation found for BUS {tp_node.name}')
                    else:
                        if cgmes_model.cgmes_map_areas_like_raw:
                            area = substation.area
                            zone = substation.zone
                        else:
                            country = substation.country
                        longitude = substation.longitude
                        latitude = substation.latitude
            else:
                logger.add_warning(msg='Missing voltage level.',
                                   device=tp_node.rdfid,
                                   device_class=tp_node.tpe,
                                   device_property="ConnectivityNodeContainer")
                # else form here get SubRegion and Region for Country...

            gcdev_elm = gcdev.Bus(name=tp_node.name,
                                  idtag=tp_node.uuid,
                                  code=tp_node.description,
                                  Vnom=nominal_voltage,
                                  vmin=0.9,
                                  vmax=1.1,
                                  active=True,
                                  is_slack=is_slack,
                                  is_dc=False,
                                  # is_internal=False,
                                  area=area,
                                  zone=zone,
                                  substation=substation,
                                  voltage_level=volt_lev,
                                  country=country,
                                  latitude=latitude,
                                  longitude=longitude,
                                  Vm0=vm,
                                  Va0=va)

            gc_model.add_bus(gcdev_elm)
            cn_look_up.add_bus(bus=gcdev_elm)
            calc_node_dict[gcdev_elm.idtag] = gcdev_elm
        else:
            logger.add_info(
                "TopologicalNode skipped because a ConnectivityNode exists",
                device_class="TopologicalNode",
                device=tp_node.uuid)

    # We try to add the DC nodes
    for cn_elm in cgmes_model.cgmes_assets.DCTopologicalNode_list:

        if not (cn_elm.uuid in tp_with_cn):
            if cn_elm not in buses_to_skip:
                gcdev_elm = gcdev.Bus(
                    name=cn_elm.name,
                    idtag=cn_elm.uuid,
                    code=cn_elm.description,
                    Vnom=default_nominal_voltage,
                    active=True,
                    is_slack=False,
                    is_dc=True,
                    area=None,  # areas and zones are not created from cgmes models
                    zone=None,
                    # substation=substat,
                    # voltage_level=volt_lev,
                    # country=country,
                    # latitude=latitude,
                    # longitude=longitude,
                    # Vm0=vm,
                    # Va0=va
                )

                if not skip_dc_import:
                    gc_model.add_bus(gcdev_elm)

                calc_node_dict[gcdev_elm.idtag] = gcdev_elm

    return calc_node_dict, False


# def get_gcdev_dc_buses(cgmes_model: CgmesCircuit,
#                        gc_model: MultiCircuit,
#                        skip_dc_import: bool,
#                        buses_to_skip: List,
#                        logger: DataLogger,
#                        default_nominal_voltage=500.0) -> Dict[str, gcdev.Bus]:
#     """
#     Convert the DCTopologicalNodes to DC Buses (CalculationNodes)
#
#     :param cgmes_model: CgmesCircuit
#     :param gc_model: gcdevCircuit
#     :param buses_to_skip:
#     :param skip_dc_import: If simplified HVDC modelling applied,
#                            DC buses are not imported into MultiCircuit model,
#                            but they are added to dc_bus_dict.
#     :param buses_to_skip: DCGround buses
#     :param logger: DataLogger
#     :param default_nominal_voltage: default nominal voltage for DC nodes since CGMES does not have any...
#     :return:
#     """
#
#     # dictionary relating the DCTopologicalNode uuid to the gcdev Bus (CalculationNode)
#     dc_bus_dict: Dict[str, gcdev.Bus] = dict()
#
#     for cgmes_elm in cgmes_model.cgmes_assets.DCTopologicalNode_list:
#
#         if cgmes_elm not in buses_to_skip:
#             gcdev_elm = gcdev.Bus(
#                 name=cgmes_elm.name,
#                 idtag=cgmes_elm.uuid,
#                 code=cgmes_elm.description,
#                 Vnom=default_nominal_voltage,
#                 active=True,
#                 is_slack=False,
#                 is_dc=True,
#                 area=None,  # areas and zones are not created from cgmes models
#                 zone=None,
#                 # substation=substat,
#                 # voltage_level=volt_lev,
#                 # country=country,
#                 # latitude=latitude,
#                 # longitude=longitude,
#                 # Vm0=vm,
#                 # Va0=va
#             )
#
#             if not skip_dc_import:
#                 gc_model.add_bus(gcdev_elm)
#
#             dc_bus_dict[gcdev_elm.idtag] = gcdev_elm
#
#     return dc_bus_dict


def get_gcdev_dc_connectivity_nodes(cgmes_model: CgmesCircuit,
                                    gc_model: MultiCircuit,
                                    skip_dc_import: bool,
                                    dc_bus_dict: Dict[str, gcdev.Bus],
                                    logger: DataLogger) -> Dict[str, gcdev.Bus]:
    """
    Convert the DC Nodes to DC Connectivity nodes

    :param cgmes_model: CgmesCircuit
    :param gc_model: gcdevCircuit
    :param skip_dc_import: If simplified HVDC modelling applied,
                           DCNodes are not imported into MultiCircuit model,
                           but they are added to dc_cn_node_dict.
    :param dc_bus_dict:
    :param logger: DataLogger
    :return:
    """
    # dictionary relating the ConnectivityNode uuid to the gcdev ConnectivityNode (DC)
    dc_cn_node_dict: Dict[str, gcdev.Bus] = dict()
    used_buses = set()
    for cgmes_elm in cgmes_model.cgmes_assets.DCNode_list:

        bus = dc_bus_dict.get(cgmes_elm.DCTopologicalNode.uuid, None)

        if bus is None:
            logger.add_warning(msg='No DC Bus found for DC Node.',
                               device=cgmes_elm.rdfid,
                               device_class=cgmes_elm.tpe,
                               comment="Maybe it belongs to a DCGround, that is not imported.")

        else:
            if bus not in used_buses:
                used_buses.add(bus)
                dc_cn_node_dict[bus.idtag] = bus

    return dc_cn_node_dict


def get_gcdev_dc_lines(cgmes_model: CgmesCircuit,
                       gcdev_model: MultiCircuit,
                       dc_bus_dict: Dict[str, gcdev.Bus],
                       device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                       logger: DataLogger) -> None:
    """
    Convert the CGMES DCLineSegment to gcdev DC Line

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param dc_bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :return: None
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # convert DC lines
    for cgmes_elm in cgmes_model.cgmes_assets.DCLineSegment_list:

        calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                           device_to_terminal_dict=device_to_terminal_dict,
                                           bus_dict=dc_bus_dict,
                                           TopologicalNode_tpe=TopologicalNode_tpe,
                                           DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                           logger=logger)

        if len(calc_nodes) == 2:
            bus_f = calc_nodes[0]
            bus_t = calc_nodes[1]

            if cgmes_elm.length is None:
                length = 1.0
                logger.add_error(msg='DCLineSegment length is missing.', device=cgmes_elm.rdfid,
                                 device_class=str(cgmes_elm.tpe))
            else:
                length = float(cgmes_elm.length)

            gcdev_elm = gcdev.DcLine(
                bus_from=bus_f,
                bus_to=bus_t,
                name=cgmes_elm.name,
                idtag=cgmes_elm.uuid,
                code=cgmes_elm.description,
                r=cgmes_elm.resistance,
                # rate=rate,
                active=True,
                # r_fault = 0.0,
                # fault_pos = 0.5,
                length=length,
                # temp_base = 20,
                # temp_oper = 20,
                # alpha = 0.00330,
                # template = None,
                # contingency_factor = 1.0,
            )

            gcdev_model.add_dc_line(gcdev_elm)
        else:
            logger.add_error(msg='Not exactly two terminals',
                             device=cgmes_elm.rdfid,
                             device_class=cgmes_elm.tpe,
                             device_property="number of associated terminals",
                             value=len(calc_nodes),
                             expected_value=2)

    return


def get_gcdev_vsc_converters(cgmes_model: CgmesCircuit,
                             gcdev_model: MultiCircuit,
                             dc_bus_dict: Dict[str, gcdev.Bus],
                             dc_device_to_terminal_dict: Dict[str, List[CGMES_DC_TERMINAL]],
                             bus_dict: Dict[str, gcdev.Bus],
                             device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                             logger: DataLogger) -> None:
    """
    Convert the CGMES VcConverter to gcdev VSConverter

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param dc_bus_dict:
    :param dc_device_to_terminal_dict:
    :param bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :return: None
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    for cgmes_elm in cgmes_model.cgmes_assets.VsConverter_list:

        bus_dc = find_associated_buses(cgmes_elm=cgmes_elm,
                                       device_to_terminal_dict=dc_device_to_terminal_dict,
                                       bus_dict=dc_bus_dict,
                                       TopologicalNode_tpe=TopologicalNode_tpe,
                                       DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                       logger=logger)

        bus_ac = find_associated_buses(cgmes_elm=cgmes_elm,
                                       device_to_terminal_dict=device_to_terminal_dict,
                                       bus_dict=bus_dict,
                                       TopologicalNode_tpe=TopologicalNode_tpe,
                                       DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                       logger=logger)

        if len(bus_dc) == 1 and len(bus_ac) == 1:

            gcdev_elm = gcdev.VSC(
                bus_from=bus_dc[0],
                bus_to=bus_ac[0],
                name=cgmes_elm.name,
                idtag=cgmes_elm.uuid,
                code=cgmes_elm.description,
                active=True,
                # alpha1 = 0.0001,
                # alpha2 = 0.015,
                # alpha3 = 0.2,
                control1=ConverterControlType.Pdc,
                control1_val=cgmes_elm.p,
                control2=ConverterControlType.Vm_dc,
                control2_val=1.0,
            )

            gcdev_model.add_vsc(gcdev_elm)

        else:
            logger.add_error(msg='VSC has to have one AC and one DC terminal',
                             device=cgmes_elm.rdfid,
                             device_class=cgmes_elm.tpe,
                             device_property="number of associated terminals",
                             value=len(bus_dc),
                             expected_value=1,
                             comment="Import VSC from CGMES")

    return


def get_gcdev_hvdc_from_dcline_and_vscs(
        cgmes_model: CgmesCircuit,
        gcdev_model: MultiCircuit,
        dc_bus_dict: Dict[str, gcdev.Bus],
        dc_device_to_terminal_dict: Dict[str, List[CGMES_DC_TERMINAL]],
        bus_dict: Dict[str, gcdev.Bus],
        device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
        logger: DataLogger) -> None:
    """
    Convert the CGMES VcConverter to gcdev simplified HVDC lines
    (if required attributes for converting from VSC to VSC not given)

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param dc_bus_dict:
    :param dc_device_to_terminal_dict:
    :param bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :return: None
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    for dc_line_sgm in cgmes_model.cgmes_assets.DCLineSegment_list:
        # or in more general it is DCLine_list

        dc_buses = find_associated_buses(cgmes_elm=dc_line_sgm,
                                         device_to_terminal_dict=dc_device_to_terminal_dict,
                                         bus_dict=dc_bus_dict,
                                         TopologicalNode_tpe=TopologicalNode_tpe,
                                         DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                         logger=logger)

        # get the cgmes terminal of this device
        dc_terminals = dc_device_to_terminal_dict.get(dc_line_sgm.uuid, None)

        # get the VSC-s connected to this dc_buses
        device_list = [device
                       for device, term in dc_device_to_terminal_dict.items()
                       if term[0] in dc_terminals]

        vsc_list = [vsc
                    for vsc in cgmes_model.cgmes_assets.VsConverter_list
                    if vsc.uuid in device_list]

        # ONLY one line + two converters structure can be simplified
        if len(vsc_list) != 2:
            logger.add_info(msg='Not exactly two VSCs for DCLine(Segment)! cannot be simplified',
                            device=dc_line_sgm.rdfid,
                            device_class=dc_line_sgm.tpe,
                            device_property="number of connected VSConverters",
                            value=len(vsc_list),
                            expected_value=2,
                            comment="get_gcdev_hvdc_from_dcline_and_vscs")

        else:
            # bus_from: AC side of VSC 1
            bus_from = find_associated_buses(cgmes_elm=vsc_list[0],
                                             device_to_terminal_dict=device_to_terminal_dict,
                                             bus_dict=bus_dict,
                                             TopologicalNode_tpe=TopologicalNode_tpe,
                                             DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                             logger=logger)

            # bus_to: AC side of VSC 2
            bus_to = find_associated_buses(cgmes_elm=vsc_list[1],
                                           device_to_terminal_dict=device_to_terminal_dict,
                                           bus_dict=bus_dict,
                                           TopologicalNode_tpe=TopologicalNode_tpe,
                                           DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                           logger=logger)

            rated_udc = getattr(vsc_list[0], 'ratedUdc', None)
            if rated_udc is None:
                rated_udc = 200.0

            gcdev_elm = gcdev.HvdcLine(
                bus_from=bus_from[0],
                bus_to=bus_to[0],
                name=dc_line_sgm.name,
                idtag=dc_line_sgm.uuid,
                code=dc_line_sgm.description,
                active=True,
                Pset=abs(vsc_list[0].p),  # power of the VS converter
                # rate=rate,
                # rate of DCLine? or ratedP of Converter?
                # no Limit for DC terminal in XML
                Vset_f=vsc_list[0].targetUpcc,  # if not found, 1.0 p.u.
                Vset_t=vsc_list[1].targetUpcc,
                r=dc_line_sgm.resistance,
                dc_link_voltage=rated_udc,
            )

            gcdev_model.add_hvdc(gcdev_elm)

    return


def get_gcdev_branch_groups(cgmes_model: CgmesCircuit,
                            gcdev_model: MultiCircuit) -> None:
    """
    Convert to gcdev BranchGroups from CGMES
        Line, DCLIne, DCConverterUnit

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    """
    # convert branch aggregations
    for cgmes_elm in cgmes_model.cgmes_assets.DCLine_list:
        gcdev_elm = gcdev.BranchGroup(
            name=cgmes_elm.name,
            idtag=cgmes_elm.uuid,
            code=cgmes_elm.description,
        )

        gcdev_model.add_branch_group(gcdev_elm)


# def get_gcdev_connectivity_nodes(cgmes_model: CgmesCircuit,
#                                  gcdev_model: MultiCircuit,
#                                  calc_node_dict: Dict[str, gcdev.Bus],
#                                  cn_look_up: Cn2BusBarLookup,
#                                  logger: DataLogger) -> Dict[str, gcdev.Bus]:
#     """
#     Convert the ConnectivityNodes to VeraGrid Buses
#
#     :param calc_node_dict: dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
#              Dict[str, gcdev.Bus]
#     :param cgmes_model: CgmesCircuit
#     :param gcdev_model: gcdevCircuit
#     :param cn_look_up: CnLookUp
#     :param logger: DataLogger
#     :return: dictionary relating the ConnectivityNode uuid to the gcdev CalculationNode
#              Dict[str, gcdev.Bus]
#     """
#     # dictionary relating the ConnectivityNode uuid to the gcdev ConnectivityNode
#     cn_node_dict: Dict[str, gcdev.Bus] = dict()
#     used_buses = set()
#     for cgmes_elm in cgmes_model.cgmes_assets.ConnectivityNode_list:
#         bus: gcdev.Bus = calc_node_dict.get(cgmes_elm.TopologicalNode.uuid, None)
#         # vnom, vl = 10, None
#         # if bus is None:
#         #     logger.add_error(msg='No Bus found',
#         #                      device=cgmes_elm.rdfid,
#         #                      device_class=cgmes_elm.tpe)
#         #     default_bus = None
#         # else:
#         #     if bus not in used_buses:
#         #         default_bus = bus
#         #         used_buses.add(bus)
#         #     else:
#         #         default_bus = bus
#         #         # for the new TP processor, a CN always has to have a TP(/Bus)
#         #     vnom = bus.Vnom
#         #     vl = bus.voltage_level
#
#         gcdev_elm = gcdev.Bus(
#             idtag=cgmes_elm.uuid,
#             code=cgmes_elm.description,
#             name=cgmes_elm.name,
#         )
#
#         gcdev_model.add_bus(gcdev_elm)
#         cn_look_up.add_cn(gcdev_elm)
#         cn_node_dict[gcdev_elm.idtag] = gcdev_elm
#
#     return cn_node_dict


def get_gcdev_loads(cgmes_model: CgmesCircuit,
                    gcdev_model: MultiCircuit,
                    bus_dict: Dict[str, gcdev.Bus],
                    device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                    logger: DataLogger) -> None:
    """
    Convert the CGMES loads to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # convert loads
    for device_list in [cgmes_model.cgmes_assets.EnergyConsumer_list,
                        cgmes_model.cgmes_assets.ConformLoad_list,
                        cgmes_model.cgmes_assets.NonConformLoad_list]:

        for cgmes_elm in device_list:
            calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               bus_dict=bus_dict,
                                               TopologicalNode_tpe=TopologicalNode_tpe,
                                               DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]

                p, q, i_i, i_r, g, b = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                if cgmes_elm.LoadResponse is not None:

                    if cgmes_elm.LoadResponse.exponentModel:
                        logger.add_error(
                            msg=f'Exponent model True',
                            device=cgmes_elm.rdfid,
                            device_class=cgmes_elm.tpe,
                            device_property="LoadResponse",
                            value=cgmes_elm.LoadResponse.exponentModel,
                            comment=f"get_gcdev_loads() {cgmes_elm.name}")
                        # TODO convert exponent to ZIP
                    else:  # ZIP model
                        # :param P: Active power in MW
                        p = cgmes_elm.p * cgmes_elm.LoadResponse.pConstantPower
                        # :param Q: Reactive power in MVAr
                        q = cgmes_elm.q * cgmes_elm.LoadResponse.qConstantPower
                        # :param Ir: Real current in equivalent MW
                        i_r = cgmes_elm.p * cgmes_elm.LoadResponse.pConstantCurrent
                        # :param Ii: Imaginary current in equivalent MVAr
                        i_i = cgmes_elm.q * cgmes_elm.LoadResponse.qConstantCurrent
                        # :param G: Conductance in equivalent MW
                        g = cgmes_elm.p * cgmes_elm.LoadResponse.pConstantImpedance
                        # :param B: Susceptance in equivalent MVAr
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

                if isinstance(cgmes_elm, cgmes_model.assets.ConformLoad):
                    gcdev_elm.scalable = True
                else:
                    gcdev_elm.scalable = False

                gcdev_model.add_load(bus=calc_node, api_obj=gcdev_elm)

            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def get_gcdev_generators(cgmes_model: CgmesCircuit,
                         gcdev_model: MultiCircuit,
                         bus_dict: Dict[str, gcdev.Bus],
                         device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                         logger: DataLogger) -> None:
    """
    Convert the CGMES generators to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: Logger object
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # add generation technologies
    general_tech = gcdev.Technology(idtag='', code='', name='General')
    thermal_tech = gcdev.Technology(idtag='', code='', name='Thermal')
    hydro_tech = gcdev.Technology(idtag='', code='', name='Hydro')
    solar_tech = gcdev.Technology(idtag='', code='', name='Solar')
    wind_tech_on = gcdev.Technology(idtag='', code='', name='Wind Onshore')
    wind_tech_off = gcdev.Technology(idtag='', code='', name='Wind Offshore')
    nuclear_tech = gcdev.Technology(idtag='', code='', name='Nuclear')

    gcdev_model.add_technology(general_tech)
    gcdev_model.add_technology(thermal_tech)
    gcdev_model.add_technology(hydro_tech)
    gcdev_model.add_technology(solar_tech)
    gcdev_model.add_technology(wind_tech_on)
    gcdev_model.add_technology(wind_tech_off)
    gcdev_model.add_technology(nuclear_tech)

    tech_dict = {
        "GeneratingUnit": general_tech,
        "ThermalGeneratingUnit": thermal_tech,
        "HydroGeneratingUnit": hydro_tech,
        "SolarGeneratingUnit": solar_tech,
        "WindGeneratingUnit": [wind_tech_on, wind_tech_off],
        "NuclearGeneratingUnit": nuclear_tech,
    }

    # plants_dict: Dict[str, gcdev.aggregation.Plant] = dict()

    # convert generators
    for device_list in [cgmes_model.cgmes_assets.SynchronousMachine_list]:
        for cgmes_elm in device_list:
            calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               bus_dict=bus_dict,
                                               TopologicalNode_tpe=TopologicalNode_tpe,
                                               DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]

                if cgmes_elm.GeneratingUnit is not None:

                    v_set, is_controlled, controlled_bus, controlled_cn = (
                        get_regulating_control_params(
                            cgmes_elm=cgmes_elm,
                            cgmes_enums=cgmes_enums,
                            bus_dict=bus_dict,
                            TopologicalNode_tpe=TopologicalNode_tpe,
                            DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                            logger=logger
                        ))

                    if cgmes_elm.p != 0.0:
                        pf = np.cos(np.arctan(cgmes_elm.q / cgmes_elm.p))
                    else:
                        pf = 1.0  # default is 0.8 in gc
                        logger.add_warning(msg='GeneratingUnit p is 0.',
                                           device=cgmes_elm.rdfid,
                                           device_class=cgmes_elm.tpe,
                                           device_property="p",
                                           value='0')

                    technology = tech_dict.get(cgmes_elm.GeneratingUnit.tpe, None)
                    if cgmes_elm.GeneratingUnit.tpe == "WindGeneratingUnit":
                        if cgmes_elm.GeneratingUnit.windGenUnitType == cgmes_enums.WindGenUnitKind.onshore:
                            technology = technology[0]
                        else:
                            technology = technology[1]

                    gcdev_elm = gcdev.Generator(idtag=cgmes_elm.uuid,
                                                code=cgmes_elm.description,
                                                name=cgmes_elm.name,
                                                active=True,
                                                Snom=cgmes_elm.ratedS,
                                                P=-cgmes_elm.p,
                                                Pmin=cgmes_elm.GeneratingUnit.minOperatingP,
                                                Pmax=cgmes_elm.GeneratingUnit.maxOperatingP,
                                                power_factor=pf,
                                                Qmax=cgmes_elm.maxQ if cgmes_elm.maxQ is not None else 9999.0,
                                                Qmin=cgmes_elm.minQ if cgmes_elm.minQ is not None else -9999.0,
                                                vset=v_set,
                                                is_controlled=is_controlled,
                                                # controlled_bus
                                                # TODO get controlled gc.bus
                                                )

                    gcdev_model.add_generator(bus=calc_node, api_obj=gcdev_elm)

                    if technology:
                        gcdev_elm.technologies.append(gcdev.Association(api_object=technology, value=1.0))
                else:
                    logger.add_error(msg='SynchronousMachine has no generating unit',
                                     device=cgmes_elm.rdfid,
                                     device_class=cgmes_elm.tpe,
                                     device_property="GeneratingUnit",
                                     value='None')
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
                             device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                             logger: DataLogger) -> None:
    """
    Convert the CGMES loads to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # convert loads
    for device_list in [cgmes_model.cgmes_assets.EquivalentInjection_list]:
        # TODO ExternalNetworkInjection
        for cgmes_elm in device_list:
            calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               bus_dict=calc_node_dict,
                                               TopologicalNode_tpe=TopologicalNode_tpe,
                                               DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]

                # TODO define ExternalGrid.mode
                gcdev_elm = gcdev.ExternalGrid(idtag=cgmes_elm.uuid,
                                               code=cgmes_elm.description,
                                               name=cgmes_elm.name,
                                               active=True,
                                               # mode=enum.PQ/PV/VD
                                               P=cgmes_elm.p,
                                               Q=cgmes_elm.q)

                gcdev_model.add_external_grid(bus=calc_node, api_obj=gcdev_elm)
            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def get_gcdev_ac_lines(cgmes_model: CgmesCircuit,
                       gcdev_model: MultiCircuit,
                       bus_dict: Dict[str, gcdev.Bus],
                       device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                       logger: DataLogger,
                       Sbase: float) -> None:
    """
    Convert the CGMES ac lines to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :param Sbase: system base power in MVA
    :return: None
    """

    # build the ratings dictionary
    (patl_dict, tatl_900_dict, tatl_60_dict) = build_cgmes_limit_dicts(
        cgmes_model=cgmes_model,
        device_type=cgmes_model.assets.ACLineSegment,
        logger=logger
    )
    # # build the ratings dictionary
    # rates_dict = dict()
    # acline_type = cgmes_model.get_class_type("ACLineSegment")
    # for e in cgmes_model.cgmes_assets.CurrentLimit_list:
    #     if e.OperationalLimitSet is None:
    #         logger.add_error(msg='OperationalLimitSet missing.',
    #                          device=e.rdfid,
    #                          device_class=e.tpe,
    #                          device_property="OperationalLimitSet",
    #                          value="None")
    #         continue
    #     if not isinstance(e.OperationalLimitSet, str):
    #         if isinstance(e.OperationalLimitSet, list):
    #             for ols in e.OperationalLimitSet:
    #                 if isinstance(ols.Terminal.ConductingEquipment, acline_type):
    #                     branch_id = ols.Terminal.ConductingEquipment.uuid
    #                     rates_dict[branch_id] = e.value
    #         else:
    #             if isinstance(e.OperationalLimitSet.Terminal.ConductingEquipment, acline_type):
    #                 branch_id = e.OperationalLimitSet.Terminal.ConductingEquipment.uuid
    #                 rates_dict[branch_id] = e.value

    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # convert ac lines
    for device_list in [cgmes_model.cgmes_assets.ACLineSegment_list]:
        for cgmes_elm in device_list:
            calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               bus_dict=bus_dict,
                                               TopologicalNode_tpe=TopologicalNode_tpe,
                                               DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                               logger=logger)

            if len(calc_nodes) == 2:
                calc_node_f = calc_nodes[0]
                calc_node_t = calc_nodes[1]

                # get per unit values
                r, x, g, b, r0, x0, g0, b0 = get_pu_values_ac_line_segment(ac_line_segment=cgmes_elm, logger=logger,
                                                                           Sbase=Sbase)

                normal_rate_mva = patl_dict.get(cgmes_elm.uuid, 9999.0)
                # min PATL rate in MW/MVA
                cont_rate_mva = tatl_900_dict.get(cgmes_elm.uuid, 9999.0)
                # min TATL900 rate in MW/MVA
                if cont_rate_mva != 9999.0:
                    cont_factor = cont_rate_mva / normal_rate_mva
                else:
                    cont_factor = 1.0
                prot_rate_mva = tatl_60_dict.get(cgmes_elm.uuid, 9999.0)
                # min TATL60 rate in MW/MVA
                if prot_rate_mva != 9999.0:
                    prot_factor = prot_rate_mva / normal_rate_mva
                else:
                    prot_factor = 1.4

                if cgmes_elm.length is None:
                    length = 1.0
                    logger.add_error(msg='Length missing.', device=cgmes_elm.rdfid, device_class=str(cgmes_elm.tpe))
                else:
                    length = float(cgmes_elm.length)

                gcdev_elm = gcdev.Line(
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    name=cgmes_elm.name,
                    active=True,
                    bus_from=calc_node_f,
                    bus_to=calc_node_t,
                    r=r,
                    x=x,
                    b=b,
                    r0=r0,
                    x0=x0,
                    b0=b0,
                    rate=normal_rate_mva,
                    contingency_factor=cont_factor,
                    protection_rating_factor=prot_factor,
                    length=length,
                )

                gcdev_model.add_line(gcdev_elm, logger=logger)
            else:
                logger.add_error(msg='Not exactly two terminals',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=2)


# def get_tap_changer_values(windings):
#     """
#     Get Tap Changer values from one of the given windings (that is not None).
#
#     :param windings: List of transformer windings.
#     :return:
#     """
#     tap_module: float = 1.0
#     total_positions, neutral_pos, normal, tap_step, dV = 0, 0, 0, 0, 0.0
#     tc_type = TapChangerTypes.NoRegulation
#
#     for winding in windings:
#         rtc = winding.RatioTapChanger
#         if rtc is not None:
#             total_positions = rtc.highStep - rtc.lowStep + 1    # lowStep generally negative
#             neutral_pos = rtc.neutralStep - rtc.lowStep
#             normal = rtc.normalStep - rtc.lowStep
#             dV = round(rtc.stepVoltageIncrement / 100, 6)
#             # tc._tap_position = neutral_position  # index with respect to the neutral position = Step from SSH
#             # set after initialisation
#             tap_step = rtc.step
#             tap_module = round(1 + (rtc.step - rtc.neutralStep) * dV, 6)
#
#             # Control from Control object
#             if (getattr(rtc, 'TapChangerControl', None) and
#                     rtc.TapChangerControl.mode == cgmes_enums.RegulatingControlModeKind.voltage):
#                 tc_type = TapChangerTypes.VoltageRegulation
#
#             # tculControlMode is not relevant
#             # if (hasattr(rtc, 'tculControlMode') and
#             #         rtc.tculControlMode == cgmes_enums.TransformerControlMode.volt):
#             #     tc_type = TapChangerTypes.VoltageRegulation
#
#         else:
#             continue
#     return tap_module, total_positions, neutral_pos, normal, dV, tc_type, tap_step

#
# def set_tap_changer_values(windings,
#                            gcdev_trafo: gcdev.Transformer2W) -> None:
#     """
#     Get Tap Changer values from one of the given windings (that is not None).
#
#     :param gcdev_trafo: VeraGrid transformer
#     :param windings: List of transformer windings.
#     :return:
#     """
#     total_positions, neutral_pos, normal, tap_step, dV = 0, 0, 0, 0, 0.0
#     tc_type = TapChangerTypes.NoRegulation
#
#     for winding in windings:
#         rtc = winding.RatioTapChanger
#         if rtc is not None:
#             # Control from Control object
#             if (getattr(rtc, 'TapChangerControl', None) and
#                     rtc.TapChangerControl.mode == cgmes_enums.RegulatingControlModeKind.voltage):
#                 tc_type = TapChangerTypes.VoltageRegulation
#
#             gcdev_trafo.tap_changer.init_from_cgmes(
#                 low=rtc.lowStep,
#                 high=rtc.highStep,
#                 normal=rtc.normalStep,
#                 neutral=rtc.neutralStep,
#                 stepVoltageIncrement=rtc.stepVoltageIncrement,
#                 step=rtc.step,
#                 asymmetry_angle=90,
#                 tc_type=tc_type)
#
#         ptc = winding.PhaseTapChanger
#         # if isinstance(ptc, cgmes_model.get_class_type("PhaseTapChangerSymmetrical")):
#         if ptc is not None:
#             # Control from Control object
#             if (getattr(ptc, 'TapChangerControl', None) and
#                     ptc.TapChangerControl.mode == cgmes_enums.RegulatingControlModeKind.voltage):
#                 tc_type = TapChangerTypes.VoltageRegulation
#
#             gcdev_trafo.tap_changer.init_from_cgmes(
#                 low=ptc.lowStep,
#                 high=ptc.highStep,
#                 normal=ptc.normalStep,
#                 neutral=ptc.neutralStep,
#                 stepVoltageIncrement=ptc.voltageStepIncrement,
#                 step=ptc.step,
#                 asymmetry_angle=90,
#                 tc_type=tc_type)
#
#     return


def get_gcdev_ac_transformers(cgmes_model: CgmesCircuit,
                              gcdev_model: MultiCircuit,
                              bus_dict: Dict[str, gcdev.Bus],
                              device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                              logger: DataLogger,
                              Sbase: float) -> None:
    """
    Convert the CGMES ac lines to gcdev
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :param Sbase: system base power in MVA
    :return: None
    """

    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # build the ratings dictionary
    trafo_type = cgmes_model.assets.PowerTransformer
    (patl_dict, tatl_900_dict, tatl_60_dict) = build_cgmes_limit_dicts(cgmes_model, trafo_type, logger)

    # convert transformers
    for device_list in [cgmes_model.cgmes_assets.PowerTransformer_list]:

        for cgmes_elm in device_list:

            windings = [None, None, None]
            for pte in list(cgmes_elm.PowerTransformerEnd):
                if hasattr(pte, "endNumber"):
                    i = getattr(pte, "endNumber")
                    if i is not None:
                        windings[i - 1] = pte
            windings = [x for x in windings if x is not None]

            normal_rate_mva = patl_dict.get(cgmes_elm.uuid, 9999.0)  # min PATL rate in MW/MVA
            cont_rate_mva = tatl_900_dict.get(cgmes_elm.uuid, 9999.0)  # min TATL900 rate in MW/MVA
            if cont_rate_mva != 9999.0:
                cont_factor = cont_rate_mva / normal_rate_mva
            else:
                cont_factor = 1.0
            prot_rate_mva = tatl_60_dict.get(cgmes_elm.uuid, 9999.0)  # min TATL60 rate in MW/MVA
            if prot_rate_mva != 9999.0:
                prot_factor = prot_rate_mva / normal_rate_mva
            else:
                prot_factor = 1.4

            calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               bus_dict=bus_dict,
                                               TopologicalNode_tpe=TopologicalNode_tpe,
                                               DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                               logger=logger)

            if len(windings) == 2:

                if len(calc_nodes) == 2:
                    calc_node_f = calc_nodes[0]
                    calc_node_t = calc_nodes[1]

                    HV = windings[0].ratedU
                    LV = windings[1].ratedU

                    # get per unit values
                    r, x, g, b, r0, x0, g0, b0 = get_pu_values_power_transformer(cgmes_elm, Sbase)
                    rated_s = windings[0].ratedS

                    gcdev_elm = gcdev.Transformer2W(
                        idtag=cgmes_elm.uuid,
                        code=cgmes_elm.description,
                        name=cgmes_elm.name,
                        active=True,
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
                        # tap_module=tap_m,
                        # # tap_phase=0.0,
                        # # tap_module_control_mode=,  # leave fixed
                        # # tap_angle_control_mode=,
                        # tc_total_positions=total_pos,
                        # tc_neutral_position=neutral_pos,
                        # tc_normal_position=normal_pos,
                        # tc_dV=dV,
                        # # tc_asymmetry_angle = 90,
                        # tc_type=tc_type,
                        rate=normal_rate_mva,
                        contingency_factor=cont_factor,
                        protection_rating_factor=prot_factor,
                    )

                    # # get Tap data from CGMES
                    # tap_m, total_pos, neutral_pos, normal_pos, dV, tc_type, tap_pos = get_tap_changer_values(windings)

                    # # TAP Changer INIT from CGMES
                    # set_tap_changer_values(windings=windings,
                    #                        gcdev_trafo=gcdev_elm)

                    gcdev_model.add_transformer2w(gcdev_elm)
                else:
                    logger.add_error(msg='Not exactly two terminals',
                                     device=cgmes_elm.rdfid,
                                     device_class=cgmes_elm.tpe,
                                     device_property="number of associated terminals",
                                     value=len(calc_nodes),
                                     expected_value="2")

            elif len(windings) == 3:

                if len(calc_nodes) == 3:

                    # sort the windings to match the nominal buses voltage...
                    # The problem is that the windings order might not be the same as the buses order
                    # hence, there might be large virtual taps
                    windings2 = [None, None, None]
                    for i in range(3):
                        v_bus = calc_nodes[i].Vnom
                        d_min = 1e20
                        j_min = -1
                        for j in range(3):
                            v_winding = windings[j].ratedU
                            d = abs(v_bus - v_winding)
                            if d < d_min:
                                d_min = d
                                j_min = j
                        windings2[i] = windings[j_min]

                        if i != j_min:
                            logger.add_error(
                                msg='The winding is not in the right order with respect to the transformer TopologicalNodes',
                                device=windings[j_min].uuid, device_class=windings[j_min].tpe
                            )

                    windings = windings2

                    # assign values
                    r12, r23, r31, x12, x23, x31 = get_pu_values_power_transformer3w(cgmes_elm, Sbase)

                    gcdev_elm = gcdev.Transformer3W(idtag=cgmes_elm.uuid,
                                                    code=cgmes_elm.description,
                                                    name=cgmes_elm.name,
                                                    active=True,
                                                    bus1=calc_nodes[0],
                                                    bus2=calc_nodes[1],
                                                    bus3=calc_nodes[2],
                                                    w1_idtag=windings[0].uuid,
                                                    w2_idtag=windings[1].uuid,
                                                    w3_idtag=windings[2].uuid,
                                                    V1=windings[0].ratedU,
                                                    V2=windings[1].ratedU,
                                                    V3=windings[2].ratedU,
                                                    # r12=r12, r23=r23, r31=r31,
                                                    # x12=x12, x23=x23, x31=x31,
                                                    rate12=windings[0].ratedS,
                                                    rate23=windings[1].ratedS,
                                                    rate31=windings[2].ratedS, )

                    r1, x1, g1, b1, r01, x01, g01, b01 = get_pu_values_power_transformer_end(windings[0], Sbase)
                    gcdev_elm.winding1.R = r1
                    gcdev_elm.winding1.X = x1
                    gcdev_elm.winding1.G = g1
                    gcdev_elm.winding1.B = b1
                    gcdev_elm.winding1.R0 = r01
                    gcdev_elm.winding1.X0 = x01
                    gcdev_elm.winding1.G0 = g01
                    gcdev_elm.winding1.B0 = b01
                    gcdev_elm.winding1.rate = float(windings[0].ratedS)

                    r2, x2, g2, b2, r02, x02, g02, b02 = get_pu_values_power_transformer_end(windings[1], Sbase)
                    gcdev_elm.winding2.R = r2
                    gcdev_elm.winding2.X = x2
                    gcdev_elm.winding2.G = g2
                    gcdev_elm.winding2.B = b2
                    gcdev_elm.winding2.R0 = r02
                    gcdev_elm.winding2.X0 = x02
                    gcdev_elm.winding2.G0 = g02
                    gcdev_elm.winding2.B0 = b02
                    gcdev_elm.winding2.rate = float(windings[1].ratedS)

                    r3, x3, g3, b3, r03, x03, g03, b03 = get_pu_values_power_transformer_end(windings[2], Sbase)
                    gcdev_elm.winding3.R = r3
                    gcdev_elm.winding3.X = x3
                    gcdev_elm.winding3.G = g3
                    gcdev_elm.winding3.B = b3
                    gcdev_elm.winding3.R0 = r03
                    gcdev_elm.winding3.X0 = x03
                    gcdev_elm.winding3.G0 = g03
                    gcdev_elm.winding3.B0 = b03
                    gcdev_elm.winding3.rate = float(windings[2].ratedS)

                    gcdev_elm.fill_from_star(r1=r1, r2=r2, r3=r3, x1=x1, x2=x2, x3=x3)

                    gcdev_model.add_transformer3w(gcdev_elm, add_middle_bus=True)

                else:
                    logger.add_error(msg='Not exactly three terminals',
                                     device=cgmes_elm.rdfid,
                                     device_class=cgmes_elm.tpe,
                                     device_property="number of associated terminals",
                                     value=len(calc_nodes),
                                     expected_value="3")

            else:
                logger.add_error(msg=f'Transformers with {len(windings)} windings not supported yet',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="windings",
                                 value=len(windings),
                                 expected_value="2 or 3")


def get_transformer_tap_changers(cgmes_model: CgmesCircuit,
                                 gcdev_model: MultiCircuit,
                                 bus_dict: Dict[str, gcdev.Bus],
                                 logger: DataLogger) -> None:
    """
    Process Tap Changer Classes from CGMES and put them into VeraGrid transformers.

    :param cgmes_model: CgmesModel
    :param gcdev_model: MultiCircuit
    :param bus_dict: Dict[str, gcdev.Bus]
    :param logger:
    :return:
    """

    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    ratio_tc_class = cgmes_model.assets.RatioTapChanger
    phase_sy_class = cgmes_model.assets.PhaseTapChangerSymmetrical
    phase_as_class = cgmes_model.assets.PhaseTapChangerAsymmetrical

    # convert ac lines
    for device_list in [cgmes_model.cgmes_assets.RatioTapChanger_list,
                        cgmes_model.cgmes_assets.PhaseTapChangerSymmetrical_list,
                        cgmes_model.cgmes_assets.PhaseTapChangerAsymmetrical_list]:

        for tap_changer in device_list:

            # Transformer attributes
            tap_module_control_mode: TapModuleControl = TapModuleControl.fixed
            tap_phase_control_mode: TapPhaseControl = TapPhaseControl.fixed
            # TapChanger attributes
            asymmetry_angle = 90
            tc_type = TapChangerTypes.NoRegulation
            reg_bus = None
            reg_cn = None

            if isinstance(tap_changer, ratio_tc_class):
                # Control from Control object
                if getattr(tap_changer, 'TapChangerControl', None):
                    if (tap_changer.TapChangerControl.mode == cgmes_enums.RegulatingControlModeKind.voltage
                            and tap_changer.TapChangerControl.enabled):
                        tc_type = TapChangerTypes.VoltageRegulation
                        tap_module_control_mode = TapModuleControl.Vm

                        reg_bus = find_terminal_bus(
                            cgmes_terminal=tap_changer.TapChangerControl.Terminal,
                            bus_dict=bus_dict,
                            TopologicalNode_tpe=TopologicalNode_tpe,
                            DCTopologicalNode_tpe=DCTopologicalNode_tpe
                        )
                else:
                    logger.add_warning(msg="No TapChangerControl found for RatioTapChanger",
                                       device=tap_changer.rdfid,
                                       device_class=tap_changer.tpe,
                                       device_property="control for TapChanger",
                                       value=type(tap_changer))

            elif isinstance(tap_changer, phase_sy_class):
                tc_type = TapChangerTypes.Symmetrical

                if getattr(tap_changer, 'TapChangerControl', None):
                    if (tap_changer.TapChangerControl.mode == cgmes_enums.RegulatingControlModeKind.activePower
                            and tap_changer.TapChangerControl.enabled):
                        tap_phase_control_mode = TapPhaseControl.Pf  # from bus
                else:
                    logger.add_warning(msg="No TapChangerControl found for PhaseTapChangerSymmetrical",
                                       device=tap_changer.rdfid,
                                       device_class=tap_changer.tpe,
                                       device_property="control for TapChanger",
                                       value=type(tap_changer))

            elif isinstance(tap_changer, phase_as_class):
                tc_type = TapChangerTypes.Asymmetrical
                # windingConnectionAngle def in CGMES:
                # The phase angle between the in-phase winding and the out-of -phase winding
                # used for creating phase shift. The out-of-phase winding produces
                # what is known as the difference voltage.
                # Setting this angle to 90 degrees is not the same as a symmemtrical transformer.
                asymmetry_angle = tap_changer.windingConnectionAngle

                if getattr(tap_changer, 'TapChangerControl', None):
                    if (tap_changer.TapChangerControl.mode == cgmes_enums.RegulatingControlModeKind.activePower
                            and tap_changer.TapChangerControl.enabled):
                        tap_phase_control_mode = TapPhaseControl.Pf  # from bus
                else:
                    logger.add_warning(msg="No TapChangerControl found for PhaseTapChangerAsymmetrical",
                                       device=tap_changer.rdfid,
                                       device_class=tap_changer.tpe,
                                       device_property="control for TapChanger",
                                       value=type(tap_changer))

            else:
                logger.add_warning(msg="TapChanger Class not recognized.",
                                   device=tap_changer.rdfid,
                                   device_class=tap_changer.tpe,
                                   device_property="control for TapChanger",
                                   value=type(tap_changer))

            # attribute handling sVI
            if isinstance(tap_changer, cgmes_model.assets.PhaseTapChanger):
                tap_changer.stepVoltageIncrement = tap_changer.voltageStepIncrement

            if tap_changer.TransformerEnd is not None:
                trafo_id = tap_changer.TransformerEnd.PowerTransformer.uuid

                # Search in Transformer 2W
                gcdev_trafo = find_object_by_idtag(
                    object_list=gcdev_model.transformers2w,
                    target_idtag=trafo_id
                )

                if gcdev_trafo is None:
                    # Search in Transformer 3W
                    gcdev_trafo = find_object_by_idtag(
                        object_list=gcdev_model.transformers3w,
                        target_idtag=trafo_id
                    )

                if isinstance(gcdev_trafo, gcdev.Transformer2W):

                    gcdev_trafo.tap_module_control_mode = tap_module_control_mode
                    gcdev_trafo.tap_phase_control_mode = tap_phase_control_mode

                    # gcdev_trafo.regulation_bus = reg_bus
                    # gcdev_trafo.regulation_cn = reg_cn

                    gcdev_trafo.tap_changer.init_from_cgmes(
                        low=tap_changer.lowStep,
                        high=tap_changer.highStep,
                        normal=tap_changer.normalStep,
                        neutral=tap_changer.neutralStep,
                        stepVoltageIncrement=tap_changer.stepVoltageIncrement,
                        step=int(tap_changer.step),
                        asymmetry_angle=asymmetry_angle,
                        tc_type=tc_type
                    )

                    if gcdev_trafo.tap_changer.tc_type == TapChangerTypes.NoRegulation:
                        gcdev_trafo.tap_module = gcdev_trafo.tap_changer.get_tap_module()
                        # print(f"Tap module: {gcdev_trafo.tap_module} <--- before recalc")
                        # SET tap_module asif it was VoltageRegulation
                        gcdev_trafo.tap_changer.tc_type = TapChangerTypes.VoltageRegulation
                        gcdev_trafo.tap_changer.recalc()
                        gcdev_trafo.tap_module = gcdev_trafo.tap_changer.get_tap_module()
                        # print(f"Tap module: {gcdev_trafo.tap_module} <--- after recalc")
                        # Set it back to NoRegulation
                        gcdev_trafo.tap_changer.tc_type = TapChangerTypes.NoRegulation
                        # # SET tap_module from dV
                        # print(f"Tap module: {1 - gcdev_trafo.tap_changer.dV} <-- from dV")
                        # gcdev_trafo.tap_module = 1 - gcdev_trafo.tap_changer.dV
                        # gcdev_trafo.tap_phase = 0

                    elif gcdev_trafo.tap_changer.tc_type == TapChangerTypes.VoltageRegulation:
                        # SET tap_module from its own TapChanger object
                        gcdev_trafo.tap_module = gcdev_trafo.tap_changer.get_tap_module()
                        logger.add_info(msg="CGMES import: tap module calculated",
                                        device=gcdev_trafo.device_type,
                                        value=gcdev_trafo.tap_module)
                        # print("Tap module calculated:", gcdev_trafo.tap_module)

                    elif gcdev_trafo.tap_changer.tc_type == TapChangerTypes.Symmetrical:
                        gcdev_trafo.tap_phase = gcdev_trafo.tap_changer.get_tap_phase()
                        logger.add_info(msg="CGMES import: tap module calculated",
                                        device=gcdev_trafo.device_type,
                                        value=gcdev_trafo.tap_module)
                        # print("Tap phase calculated:", gcdev_trafo.tap_phase)

                    elif gcdev_trafo.tap_changer.tc_type == TapChangerTypes.Asymmetrical:
                        # SET tap_module from its own TapChanger object
                        gcdev_trafo.tap_module = gcdev_trafo.tap_changer.get_tap_module()
                        logger.add_info(msg="CGMES import: tap module calculated",
                                        device=gcdev_trafo.device_type,
                                        value=gcdev_trafo.tap_module)
                        # print("Tap module calculated:", gcdev_trafo.tap_module)
                        gcdev_trafo.tap_phase = gcdev_trafo.tap_changer.get_tap_phase()
                        logger.add_info(msg="CGMES import: tap module calculated",
                                        device=gcdev_trafo.device_type,
                                        value=gcdev_trafo.tap_module)
                        # print("Tap phase calculated:", gcdev_trafo.tap_phase)

                    else:
                        logger.add_error(msg="CGMES import: TapChanger has no Type",
                                         device=gcdev_trafo.device_type,
                                         value=gcdev_trafo.tap_changer.tc_type)

                elif isinstance(gcdev_trafo, gcdev.Transformer3W):
                    winding_id = tap_changer.TransformerEnd.uuid
                    # get the winding with the TapChanger
                    winding_w_tc = find_object_by_idtag(
                        object_list=[gcdev_trafo.winding1,
                                     gcdev_trafo.winding2,
                                     gcdev_trafo.winding3],
                        target_idtag=winding_id
                    )

                    if winding_w_tc is not None:
                        winding_w_tc.tap_changer.init_from_cgmes(
                            low=tap_changer.lowStep,
                            high=tap_changer.highStep,
                            normal=tap_changer.normalStep,
                            neutral=tap_changer.neutralStep,
                            stepVoltageIncrement=tap_changer.stepVoltageIncrement,
                            step=int(tap_changer.step),
                            # asymmetry_angle=90,
                            tc_type=tc_type
                        )

                        # SET tap_module and tap_phase from its own TapChanger object
                        winding_w_tc.tap_module = winding_w_tc.tap_changer.get_tap_module()
                        winding_w_tc.tap_phase = winding_w_tc.tap_changer.get_tap_phase()
                    else:
                        logger.add_error("Winding of the tap changer not found",
                                         device_class="TransformerEnd",
                                         device=winding_id)

                else:
                    logger.add_error(msg='Transformer not found for TapChanger',
                                     device=tap_changer.rdfid,
                                     device_class=tap_changer.tpe,
                                     device_property="transformer for powertransformerend",
                                     value=None,
                                     expected_value=trafo_id)

            else:
                logger.add_error("tap_changer.TransformerEnd is None",
                                 device_class=tap_changer.tpe,
                                 device=tap_changer.rdfid,
                                 device_property="TransformerEnd")


def get_gcdev_shunts(cgmes_model: CgmesCircuit,
                     gcdev_model: MultiCircuit,
                     calc_node_dict: Dict[str, gcdev.Bus],
                     device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                     logger: DataLogger) -> None:
    """
    Convert the CGMES equivalent shunts to gcdev shunts,
    simple shunts without control

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: GcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # convert shunts
    for device_list in [cgmes_model.cgmes_assets.EquivalentShunt_list]:

        for cgmes_elm in device_list:

            calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               bus_dict=calc_node_dict,
                                               TopologicalNode_tpe=TopologicalNode_tpe,
                                               DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]

                Vnom = get_voltage_shunt(shunt=cgmes_elm, logger=logger)

                G = cgmes_elm.g * (Vnom * Vnom)
                B = cgmes_elm.b * (Vnom * Vnom)

                gcdev_elm = gcdev.Shunt(
                    idtag=cgmes_elm.uuid,
                    name=cgmes_elm.name,
                    code=cgmes_elm.description,
                    G=round(G, 4),
                    B=round(B, 4),
                    active=True,
                )
                gcdev_model.add_shunt(bus=calc_node, api_obj=gcdev_elm)

            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def get_gcdev_controllable_shunts(
        cgmes_model: CgmesCircuit,
        gcdev_model: MultiCircuit,
        bus_dict: Dict[str, gcdev.Bus],
        device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
        logger: DataLogger,
        Sbase: float) -> None:
    """
    Convert the CGMES linear and non-linear shunt compensators
    to gcdev Controllable shunts.

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param Sbase: base power (100 MVA)
    :param logger:
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # LINEAR
    for cgmes_elm in cgmes_model.cgmes_assets.LinearShuntCompensator_list:

        calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                           device_to_terminal_dict=device_to_terminal_dict,
                                           bus_dict=bus_dict,
                                           TopologicalNode_tpe=TopologicalNode_tpe,
                                           DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                           logger=logger)

        if len(calc_nodes) == 1:
            calc_node = calc_nodes[0]

            # conversion
            g, b, g0, b0 = get_values_shunt(shunt=cgmes_elm,
                                            logger=logger,
                                            Sbase=Sbase)

            v_set, is_controlled, controlled_bus, controlled_cn = (
                get_regulating_control_params(
                    cgmes_elm=cgmes_elm,
                    cgmes_enums=cgmes_enums,
                    bus_dict=bus_dict,
                    TopologicalNode_tpe=TopologicalNode_tpe,
                    DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                    logger=logger
                ))

            gcdev_elm = gcdev.ControllableShunt(
                idtag=cgmes_elm.uuid,
                name=cgmes_elm.name,
                code=cgmes_elm.description,
                active=True,
                is_nonlinear=False,  # it is Linear!
                number_of_steps=cgmes_elm.maximumSections,
                g_per_step=g,
                b_per_step=b,
                G0=g0,
                B0=b0,
                vset=v_set,
                is_controlled=is_controlled,
                control_bus=controlled_bus,
            )
            # B, G is calculated when step is set: only if .sections >= 1
            gcdev_elm.step = cgmes_elm.sections - 1

            gcdev_model.add_controllable_shunt(bus=calc_node, api_obj=gcdev_elm)

        else:
            logger.add_error(msg='Not exactly one terminal',
                             device=cgmes_elm.rdfid,
                             device_class=cgmes_elm.tpe,
                             device_property="number of associated terminals",
                             value=len(calc_nodes),
                             expected_value=1)

    # NON - LINEAR
    for cgmes_elm in cgmes_model.cgmes_assets.NonlinearShuntCompensator_list:

        calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                           device_to_terminal_dict=device_to_terminal_dict,
                                           bus_dict=bus_dict,
                                           TopologicalNode_tpe=TopologicalNode_tpe,
                                           DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                           logger=logger)

        if len(calc_nodes) == 1:
            calc_node = calc_nodes[0]

            # # conversion
            # G, B, G0, B0 = get_values_shunt(shunt=cgmes_elm,
            #                                 logger=logger,
            #                                 Sbase=Sbase)

            v_set, is_controlled, controlled_bus, controlled_cn = (
                get_regulating_control_params(
                    cgmes_elm=cgmes_elm,
                    cgmes_enums=cgmes_enums,
                    bus_dict=bus_dict,
                    TopologicalNode_tpe=TopologicalNode_tpe,
                    DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                    logger=logger
                ))

            gcdev_elm = gcdev.ControllableShunt(
                idtag=cgmes_elm.uuid,
                name=cgmes_elm.name,
                code=cgmes_elm.description,
                active=True,
                is_nonlinear=True,  # it is NonLinear!
                number_of_steps=cgmes_elm.maximumSections,
                step=cgmes_elm.sections,
                # g_per_step=G,
                # b_per_step=B,
                # G=G,
                # B=B,
                vset=v_set,
                is_controlled=is_controlled,
                control_bus=controlled_bus,
            )

            point_list = []
            for nl_sc_p in cgmes_model.cgmes_assets.NonlinearShuntCompensatorPoint_list:
                if nl_sc_p.NonlinearShuntCompensator == cgmes_elm:
                    point_list.append(nl_sc_p)
            point_list.sort(key=lambda obj: obj.sectionNumber)

            Vnom = get_voltage_shunt(shunt=cgmes_elm, logger=logger)

            b_list = [point.b * (Vnom * Vnom) for point in point_list]
            n_list = [1] * len(b_list)

            gcdev_elm.set_blocks(n_list, b_list)

            # gcdev_elm.B = b_list[0]     # how to consider Binit?
            # gcdev_elm.G

            # B, G is calculated when step is set: only if .sections >= 1
            gcdev_elm.step = cgmes_elm.sections - 1
            gcdev_elm.B = 50  # np.sum(gcdev_elm.b_steps[:gcdev_elm.step])

            gcdev_model.add_controllable_shunt(bus=calc_node, api_obj=gcdev_elm)

        else:
            logger.add_error(msg='Not exactly one terminal',
                             device=cgmes_elm.rdfid,
                             device_class=cgmes_elm.tpe,
                             device_property="number of associated terminals",
                             value=len(calc_nodes),
                             expected_value=1)


def get_gcdev_switches(cgmes_model: CgmesCircuit,
                       gcdev_model: MultiCircuit,
                       bus_dict: Dict[str, gcdev.Bus],
                       device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                       logger: DataLogger) -> None:
    """
    Convert the CGMES switching devices to gcdev

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param bus_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    :return: None
    """
    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # Build the ratings dictionary
    rates_dict = {}

    sw_type = cgmes_model.assets.Switch
    br_type = cgmes_model.assets.Breaker
    ds_type = cgmes_model.assets.Disconnector
    lbs_type = cgmes_model.assets.LoadBreakSwitch
    for e in cgmes_model.cgmes_assets.CurrentLimit_list:

        if e.OperationalLimitSet is not None:

            if not isinstance(e.OperationalLimitSet, str):

                if hasattr(e.OperationalLimitSet.Terminal, "ConductingEquipment"):
                    conducting_equipment = e.OperationalLimitSet.Terminal.ConductingEquipment
                    if isinstance(conducting_equipment, (sw_type, br_type, ds_type, lbs_type)):
                        branch_id = conducting_equipment.uuid
                        rates_dict[branch_id] = e.value
                else:
                    logger.add_error("No ConductingEquipment",
                                     device_class=e.OperationalLimitSet.Terminal.tpe,
                                     device_property="ConductingEquipment",
                                     device=e.OperationalLimitSet.Terminal.rdfid, )
            else:
                logger.add_error("OperationalLimitSet reference not found",
                                 device_class=e.tpe,
                                 device_property="OperationalLimitSet",
                                 device=e.OperationalLimitSet, )
        else:
            logger.add_error("No OperationalLimitSet",
                             device_class=e.tpe,
                             device_property="OperationalLimitSet",
                             device=e.rdfid, )

    # convert switch
    for device_list in [cgmes_model.cgmes_assets.Switch_list,
                        cgmes_model.cgmes_assets.Breaker_list,
                        cgmes_model.cgmes_assets.Disconnector_list,
                        cgmes_model.cgmes_assets.LoadBreakSwitch_list,
                        # cgmes_model.GroundDisconnector_list
                        ]:

        for cgmes_elm in device_list:
            calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               bus_dict=bus_dict,
                                               TopologicalNode_tpe=TopologicalNode_tpe,
                                               DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                               logger=logger)

            if len(calc_nodes) == 2:
                calc_node_f = calc_nodes[0]
                calc_node_t = calc_nodes[1]

                operational_current_rate = rates_dict.get(cgmes_elm.uuid, None)  # A
                if operational_current_rate and cgmes_elm.BaseVoltage is not None:
                    # rate in MVA = A / 1000 * kV * sqrt(3)    CORRECTED!
                    op_rate = np.round((operational_current_rate / 1000.0) *
                                       cgmes_elm.BaseVoltage.nominalVoltage * 1.73205080756888,
                                       4)
                else:
                    op_rate = 9999  # Corrected

                if (cgmes_elm.ratedCurrent is not None
                        and cgmes_elm.ratedCurrent != 0.0
                        and cgmes_elm.BaseVoltage is not None):
                    rated_current = np.round(
                        (cgmes_elm.ratedCurrent / 1000.0) * cgmes_elm.BaseVoltage.nominalVoltage * 1.73205080756888,
                        4)
                else:
                    rated_current = op_rate

                active = True
                if cgmes_elm.open:
                    active = False

                gcdev_elm = gcdev.Switch(
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    name=cgmes_elm.name,
                    active=active,
                    bus_from=calc_node_f,
                    bus_to=calc_node_t,
                    rate=op_rate,
                    rated_current=rated_current,
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
                          gcdev_model: MultiCircuit,
                          logger: DataLogger) -> None:
    """
    Convert the CGMES substations to gcdev substations

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    """
    # convert substations
    for device_list in [cgmes_model.cgmes_assets.Substation_list]:

        for cgmes_elm in device_list:

            community, area, zone = None, None, None
            if cgmes_model.cgmes_map_areas_like_raw:
                zone = find_object_by_idtag(
                    object_list=gcdev_model.zones,
                    target_idtag=cgmes_elm.Region.uuid
                )
                area = find_object_by_idtag(
                    object_list=gcdev_model.areas,
                    target_idtag=cgmes_elm.Region.Region.uuid
                )
            else:
                community = find_object_by_idtag(
                    object_list=gcdev_model.communities,
                    target_idtag=cgmes_elm.Region.uuid
                )

            if cgmes_elm.Location:
                try:
                    longitude = float(cgmes_elm.Location.PositionPoints.xPosition)
                    latitude = float(cgmes_elm.Location.PositionPoints.yPosition)
                except ValueError:
                    longitude = 0.0
                    latitude = 0.0
                    logger.add_error(msg="Cannot extract longitude or latitude value.")
            else:
                latitude = 0.0
                longitude = 0.0

            gcdev_elm = gcdev.Substation(
                name=cgmes_elm.name,
                idtag=cgmes_elm.uuid,
                code=cgmes_elm.description,
                latitude=latitude,  # later from GL profile/Location class
                longitude=longitude
            )

            if community is not None:
                gcdev_elm.community = community
            if area is not None:
                gcdev_elm.area = area
            if zone is not None:
                gcdev_elm.zone = zone

            gcdev_model.add_substation(gcdev_elm)


def get_gcdev_voltage_levels(cgmes_model: CgmesCircuit,
                             gcdev_model: MultiCircuit,
                             logger: DataLogger) -> Dict[str, gcdev.VoltageLevel]:
    """
    Convert the CGMES voltage levels to gcdev voltage levels

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param logger:
    """
    # dictionary relating the VoltageLevel idtag to the gcdev VoltageLevel
    volt_lev_dict: Dict[str, gcdev.VoltageLevel] = dict()

    for cgmes_elm in cgmes_model.cgmes_assets.VoltageLevel_list:

        if not isinstance(cgmes_elm.BaseVoltage, str):  # if it is a string it was not substituted...

            gcdev_elm = gcdev.VoltageLevel(
                idtag=cgmes_elm.uuid,
                name=cgmes_elm.name,
                Vnom=cgmes_elm.BaseVoltage.nominalVoltage
            )

            if cgmes_elm.Substation is not None:
                subs = find_object_by_idtag(
                    object_list=gcdev_model.substations,
                    target_idtag=cgmes_elm.Substation.uuid  # gcdev_elm.idtag
                )

                if subs:
                    gcdev_elm.substation = subs

            gcdev_model.add_voltage_level(gcdev_elm)
            volt_lev_dict[gcdev_elm.idtag] = gcdev_elm

        else:
            logger.add_error(msg='Base voltage not found for VoltageLevel',
                             device=str(cgmes_elm.BaseVoltage),
                             comment="get_gcdev_voltage_levels")

    return volt_lev_dict


def get_gcdev_busbars(cgmes_model: CgmesCircuit,
                      gcdev_model: MultiCircuit,
                      calc_node_dict: Dict[str, gcdev.Bus],
                      device_to_terminal_dict: Dict[str, List[CGMES_TERMINAL]],
                      logger: DataLogger) -> None:
    """
    Convert the CGMES busbars to gcdev busbars

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger: DataLogger
    """
    vl_dict = {elm.idtag: elm for elm in gcdev_model.voltage_levels}

    TopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("TopologicalNode")
    DCTopologicalNode_tpe = cgmes_model.cgmes_assets.class_dict.get("DCTopologicalNode")

    # convert busbars
    for device_list in [cgmes_model.cgmes_assets.BusbarSection_list]:

        for cgmes_elm in device_list:

            calc_nodes = find_associated_buses(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               bus_dict=calc_node_dict,
                                               TopologicalNode_tpe=TopologicalNode_tpe,
                                               DCTopologicalNode_tpe=DCTopologicalNode_tpe,
                                               logger=logger)

            if len(calc_nodes) == 1:

                container = cgmes_elm.EquipmentContainer

                if isinstance(container, cgmes_model.assets.VoltageLevel):
                    vl_cgmes = container
                    vl_gc = vl_dict.get(vl_cgmes.uuid, None)
                else:
                    vl_gc = None

                gcdev_elm = gcdev.BusBar(
                    name=cgmes_elm.name,
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    voltage_level=vl_gc,
                )
                gcdev_model.add_bus_bar(gcdev_elm)

            else:
                logger.add_error(msg='Not exactly one terminal',
                                 device=cgmes_elm.rdfid,
                                 device_class=cgmes_elm.tpe,
                                 device_property="number of associated terminals",
                                 value=len(calc_nodes),
                                 expected_value=1)


def get_gcdev_countries(cgmes_model: CgmesCircuit,
                        gcdev_model: MultiCircuit) -> None:
    """
    Convert the CGMES GeoGraphicalRegions to gcdev Country

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    """
    for device_list in [cgmes_model.cgmes_assets.GeographicalRegion_list]:

        for cgmes_elm in device_list:
            if cgmes_model.cgmes_map_areas_like_raw:
                gcdev_elm = gcdev.Area(
                    name=cgmes_elm.name,
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    # latitude=0.0,     # later from GL profile/Location class
                    # longitude=0.0
                )

                gcdev_model.add_area(gcdev_elm)

            else:
                gcdev_elm = gcdev.Country(
                    name=cgmes_elm.name,
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    # latitude=0.0,     # later from GL profile/Location class
                    # longitude=0.0
                )

                gcdev_model.add_country(gcdev_elm)


def get_gcdev_community(cgmes_model: CgmesCircuit,
                        gcdev_model: MultiCircuit) -> None:
    """
    Convert the CGMES SubGeographicalRegions to gcdev Community

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    """
    for device_list in [cgmes_model.cgmes_assets.SubGeographicalRegion_list]:

        for cgmes_elm in device_list:
            if cgmes_model.cgmes_map_areas_like_raw:
                gcdev_elm = gcdev.Zone(
                    name=cgmes_elm.name,
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    # latitude=0.0,     # later from GL profile/Location class
                    # longitude=0.0
                )

                a = find_object_by_idtag(
                    object_list=gcdev_model.areas,
                    target_idtag=cgmes_elm.Region.uuid
                )

                if a is not None:
                    gcdev_elm.area = a

                gcdev_model.add_zone(gcdev_elm)

            else:
                gcdev_elm = gcdev.Community(
                    name=cgmes_elm.name,
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    # latitude=0.0,     # later from GL profile/Location class
                    # longitude=0.0
                )

                c = find_object_by_idtag(
                    object_list=gcdev_model.countries,
                    target_idtag=cgmes_elm.Region.uuid
                )

                if c is not None:
                    gcdev_elm.country = c

                gcdev_model.add_community(gcdev_elm)


def get_header_mas(cgmes_model: CgmesCircuit,
                   gcdev_model: MultiCircuit,
                   logger: DataLogger) -> None:
    """

    :param cgmes_model:
    :param gcdev_model:
    :param logger:
    :return:
    """
    mas_set = set()
    for full_model in cgmes_model.cgmes_assets.FullModel_list:
        if full_model.modelingAuthoritySet is None:
            logger.add_warning(msg="Missing MAS in header!",
                               device=full_model.rdfid,
                               device_property="modelingAuthoritySet")
            continue
        if isinstance(full_model.modelingAuthoritySet, list):
            for mas in full_model.modelingAuthoritySet:
                mas_set.add(mas)
        else:
            mas_set.add(full_model.modelingAuthoritySet)
    for mas in mas_set:
        gcdev_elm = gcdev.ModellingAuthority(name=mas)
        gcdev_model.add_modelling_authority(gcdev_elm)


def cgmes_to_veragrid(cgmes_model: CgmesCircuit,
                      map_dc_to_hvdc_line: bool,
                      logger: DataLogger) -> MultiCircuit:
    """
    Convert CGMES model to gcdev

    :param cgmes_model: CgmesCircuit
    :param map_dc_to_hvdc_line: Converters and DC lines from CGMES are converted
                                to the simplified HvdcLine objects in VeraGrid
    :param logger: Logger object
    :return: MultiCircuit
    """
    gc_model = MultiCircuit()  # roseta
    gc_model.comments = 'Converted from a CGMES file'
    Sbase = gc_model.Sbase
    cgmes_model.emit_progress(70)
    cgmes_model.emit_text("Converting CGMES to VeraGrid")

    get_header_mas(cgmes_model, gc_model, logger)

    get_gcdev_countries(cgmes_model, gc_model)

    get_gcdev_community(cgmes_model, gc_model)

    get_gcdev_substations(cgmes_model, gc_model, logger)

    vl_dict = get_gcdev_voltage_levels(cgmes_model=cgmes_model,
                                       gcdev_model=gc_model,
                                       logger=logger)

    cn_look_up = Cn2BusBarLookup(cgmes_model)

    sv_volt_dict = get_gcdev_voltage_dict(cgmes_model=cgmes_model,
                                          logger=logger)

    device_to_terminal_dict = get_gcdev_device_to_terminal_dict(cgmes_model=cgmes_model,
                                                                logger=logger)

    dc_device_to_terminal_dict, ground_buses, ground_nodes = get_gcdev_dc_device_to_terminal_dict(
        cgmes_model=cgmes_model,
        logger=logger
    )

    # NOTE: In VeraGrid there are only buses (as it should be)
    # hence, the ConnectivityNodes and TopologicalNodes are
    # converted to buses giving priority to the ConnectivityNodes
    bus_dict, fatal_error = get_gcdev_buses(cgmes_model=cgmes_model,
                                            gc_model=gc_model,
                                            v_dict=sv_volt_dict,
                                            cn_look_up=cn_look_up,
                                            skip_dc_import=map_dc_to_hvdc_line,
                                            buses_to_skip=ground_buses,
                                            default_nominal_voltage=500.0,
                                            logger=logger)

    if fatal_error:
        return gc_model

    # cn_dict = get_gcdev_connectivity_nodes(cgmes_model=cgmes_model,
    #                                        gcdev_model=gc_model,
    #                                        calc_node_dict=bus_dict,
    #                                        cn_look_up=cn_look_up,
    #                                        logger=logger)

    cgmes_model.emit_progress(78)
    get_gcdev_busbars(cgmes_model=cgmes_model,
                      gcdev_model=gc_model,
                      calc_node_dict=bus_dict,
                      device_to_terminal_dict=device_to_terminal_dict,
                      logger=logger)

    get_gcdev_loads(cgmes_model=cgmes_model,
                    gcdev_model=gc_model,
                    bus_dict=bus_dict,
                    device_to_terminal_dict=device_to_terminal_dict,
                    logger=logger)

    get_gcdev_external_grids(cgmes_model=cgmes_model,
                             gcdev_model=gc_model,
                             calc_node_dict=bus_dict,
                             device_to_terminal_dict=device_to_terminal_dict,
                             logger=logger)

    get_gcdev_generators(cgmes_model=cgmes_model,
                         gcdev_model=gc_model,
                         bus_dict=bus_dict,
                         device_to_terminal_dict=device_to_terminal_dict,
                         logger=logger)

    cgmes_model.emit_progress(86)

    get_gcdev_ac_lines(cgmes_model=cgmes_model,
                       gcdev_model=gc_model,
                       bus_dict=bus_dict,
                       device_to_terminal_dict=device_to_terminal_dict,
                       logger=logger,
                       Sbase=Sbase)

    get_gcdev_ac_transformers(cgmes_model=cgmes_model,
                              gcdev_model=gc_model,
                              bus_dict=bus_dict,
                              device_to_terminal_dict=device_to_terminal_dict,
                              logger=logger,
                              Sbase=Sbase)

    get_transformer_tap_changers(cgmes_model=cgmes_model,
                                 gcdev_model=gc_model,
                                 bus_dict=bus_dict,
                                 logger=logger)

    get_gcdev_shunts(cgmes_model=cgmes_model,
                     gcdev_model=gc_model,
                     calc_node_dict=bus_dict,
                     device_to_terminal_dict=device_to_terminal_dict,
                     logger=logger)

    get_gcdev_controllable_shunts(
        cgmes_model=cgmes_model,
        gcdev_model=gc_model,
        bus_dict=bus_dict,
        device_to_terminal_dict=device_to_terminal_dict,
        logger=logger,
        Sbase=Sbase
    )
    get_gcdev_switches(cgmes_model=cgmes_model,
                       gcdev_model=gc_model,
                       bus_dict=bus_dict,
                       device_to_terminal_dict=device_to_terminal_dict,
                       logger=logger, )

    cgmes_model.emit_progress(91)
    cgmes_model.emit_text("Converting CGMES to VeraGrid - HVDC")

    # DC elements  ---------------------------------------------------------

    dc_device_to_terminal_dict, ground_buses, ground_nodes = get_gcdev_dc_device_to_terminal_dict(
        cgmes_model=cgmes_model,
        logger=logger
    )

    # dc_bus_dict = get_gcdev_dc_buses(
    #     cgmes_model=cgmes_model,
    #     gc_model=gc_model,
    #     skip_dc_import=map_dc_to_hvdc_line,
    #     buses_to_skip=ground_buses,
    #     logger=logger
    # )

    dc_cn_dict = get_gcdev_dc_connectivity_nodes(
        cgmes_model=cgmes_model,
        gc_model=gc_model,
        skip_dc_import=map_dc_to_hvdc_line,
        dc_bus_dict=bus_dict,
        logger=logger
    )

    if map_dc_to_hvdc_line:

        logger.add_info(
            msg="Simplified HVDC modelling",
            comment="DC buses are not imported!")

        get_gcdev_hvdc_from_dcline_and_vscs(
            cgmes_model=cgmes_model,
            gcdev_model=gc_model,
            dc_bus_dict=bus_dict,
            dc_device_to_terminal_dict=dc_device_to_terminal_dict,
            bus_dict=bus_dict,
            device_to_terminal_dict=device_to_terminal_dict,
            logger=logger,
        )

    else:

        logger.add_info(
            msg="Detailed HVDC modelling with VsConverters and DC Lines",
            comment="DC buses are imported!")

        get_gcdev_dc_lines(
            cgmes_model=cgmes_model,
            gcdev_model=gc_model,
            dc_bus_dict=bus_dict,
            device_to_terminal_dict=dc_device_to_terminal_dict,
            logger=logger,
        )

        get_gcdev_vsc_converters(
            cgmes_model=cgmes_model,
            gcdev_model=gc_model,
            dc_bus_dict=bus_dict,
            dc_device_to_terminal_dict=dc_device_to_terminal_dict,
            bus_dict=bus_dict,
            device_to_terminal_dict=device_to_terminal_dict,
            logger=logger,
        )

    cgmes_model.emit_progress(100)
    cgmes_model.emit_text("Cgmes import done!")

    return gc_model
