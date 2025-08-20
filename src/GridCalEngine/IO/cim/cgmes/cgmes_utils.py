# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Dict
import numpy as np
import GridCalEngine.Devices as gcdev
from GridCalEngine.IO.cim.cgmes.base import rfid2uuid
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_typing import (CGMES_TERMINAL, CGMES_ACDC_TERMINAL,
                                                     CGMES_BASE_VOLTAGE, CGMES_ASSETS,
                                                     CGMES_TOPOLOGICAL_NODE, CGMES_CONNECTIVITY_NODE,
                                                     CGMES_POWER_TRANSFORMER, CGMES_POWER_TRANSFORMER_END,
                                                     CGMES_AC_LINE_SEGMENT, CGMES_SHUNT_COMPENSATOR,
                                                     CGMES_NON_LINEAR_SHUNT_COMPENSATOR,
                                                     CGMES_LINEAR_SHUNT_COMPENSATOR,
                                                     CGMES_EQUIVALENT_SHUNT)
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.IO.cim.cgmes.cgmes_enums import LimitTypeKind


def find_terminal_bus(cgmes_terminal: CGMES_TERMINAL,
                      bus_dict: Dict[str, gcdev.Bus],
                      TopologicalNode_tpe,
                      DCTopologicalNode_tpe) -> gcdev.Bus | None:
    """
    Find the bus associated to a terminal
    :param cgmes_terminal:
    :param bus_dict:
    :param TopologicalNode_tpe: TopologicalNode type
                                (might come from different cgmes versions, hence we need to pass the type)
    :param DCTopologicalNode_tpe: DCTopologicalNode type
                                  (might come from different cgmes versions, hence we need to pass the type)
    :return:
    """
    if cgmes_terminal is not None:
        if hasattr(cgmes_terminal, "TopologicalNode"):  # Try for AC terminal
            # get the rosetta calculation node if exists
            if isinstance(cgmes_terminal.TopologicalNode, TopologicalNode_tpe):
                return bus_dict.get(cgmes_terminal.TopologicalNode.uuid, None)
            else:
                return None

        elif hasattr(cgmes_terminal, "DCTopologicalNode"):  # get the rosetta calculation node if exists
            if isinstance(cgmes_terminal.DCTopologicalNode, DCTopologicalNode_tpe):
                return bus_dict.get(cgmes_terminal.DCTopologicalNode.uuid, None)
            else:
                return None
        else:
            return None
    else:
        return None


def find_object_by_idtag(object_list: List[ALL_DEV_TYPES], target_idtag: str) -> ALL_DEV_TYPES | None:
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


def get_slack_id(machines):
    """
    Retrieves the ID of a Topological Node from a list of SynchronousMachines.

    @param machines: List of SynchronousMachine objects.
    @return: ID of a Topological Node if found, None otherwise.
    """
    # Check if machines is a list
    if not isinstance(machines, list):
        raise TypeError("Expected 'machines' to be a list of SynchronousMachine objects.")

    for m in machines:
        # Check if the machine has a referencePriority attribute
        if hasattr(m, 'referencePriority') and m.referencePriority == 1:
            # Check if Terminals attribute exists
            if hasattr(m, 'Terminals'):
                terminals = m.Terminals

                # Check if terminals is a list or single object
                if isinstance(terminals, list) and len(terminals) > 0:
                    terminal = terminals[0]
                elif not isinstance(terminals, list):
                    terminal = terminals
                else:
                    continue  # Skip to the next machine if terminals is an empty list

                # Check if TopologicalNode exists and has rdfid
                if hasattr(terminal, 'TopologicalNode') and hasattr(
                        terminal.TopologicalNode, 'rdfid'):
                    return terminal.TopologicalNode.rdfid
                else:
                    print(
                        f"Warning: TopologicalNode or rdfid missing in machine {m}.")
            else:
                print(f"Warning: Terminals attribute missing in machine {m}.")

    # If no matching machine is found
    return None


def build_cgmes_limit_dicts(cgmes_model: CgmesCircuit,
                            device_type,
                            logger: DataLogger):
    """
    Builds Rating dictionary for given device type from OperationalLimitSets

    :param cgmes_model:
    :param device_type:
    :param logger:
    :return:
    """
    sqrt_3 = 1.73205080756888
    patl_dict = dict()
    tatl_900_dict = dict()
    tatl_60_dict = dict()

    for cl in cgmes_model.cgmes_assets.CurrentLimit_list:

        if cl.OperationalLimitSet is None:
            logger.add_error(msg='OperationalLimitSet missing.',
                             device=cl.rdfid,
                             device_class=cl.tpe,
                             device_property="OperationalLimitSet",
                             value="None")

        else:
            op_lim_set = cl.OperationalLimitSet
            op_lim_type = cl.OperationalLimitType

            volt: float | None = get_voltage_terminal(op_lim_set.Terminal, logger)

            if volt is not None:
                rate_mva = np.round(cl.value * volt * sqrt_3 / 1e3, 4)

                if isinstance(op_lim_set.Terminal.ConductingEquipment, device_type):
                    branch_id = op_lim_set.Terminal.ConductingEquipment.uuid

                    if op_lim_type.limitType == LimitTypeKind.patl:

                        act_lim = patl_dict.get(branch_id, None)
                        if act_lim is None:
                            patl_dict[branch_id] = rate_mva
                        elif rate_mva < act_lim:
                            patl_dict[branch_id] = rate_mva

                    elif op_lim_type.limitType == LimitTypeKind.tatl:

                        if op_lim_type.acceptableDuration == 900:

                            act_lim = tatl_900_dict.get(branch_id, None)
                            if act_lim is None:
                                tatl_900_dict[branch_id] = rate_mva
                            elif rate_mva < act_lim:
                                tatl_900_dict[branch_id] = rate_mva

                        elif op_lim_type.acceptableDuration == 60:

                            act_lim = tatl_60_dict.get(branch_id, None)
                            if act_lim is None:
                                tatl_60_dict[branch_id] = rate_mva
                            elif rate_mva < act_lim:
                                tatl_60_dict[branch_id] = rate_mva

                        else:
                            logger.add_warning(
                                msg="Not supported .acceptable duration for OperationalLimitType",
                                device=op_lim_type,
                                device_class=op_lim_type.tpe,
                                value=op_lim_type.acceptableDuration,
                                comment="Currently only 900 and 60 is imported for TATL limits",
                            )
                    else:
                        logger.add_warning(
                            msg="Not supported .limitType duration for OperationalLimitType",
                            device=op_lim_type,
                            device_class=op_lim_type.tpe,
                            value=op_lim_type.limitType,
                            comment="Currently only PATL and TATL (900, 60) type are imported",
                        )

                else:
                    logger.add_error(msg='ConductingEquipment is missing for terminal.',
                                     device=op_lim_set.Terminal.rdfid,
                                     device_class=op_lim_set.Terminal.tpe,
                                     device_property="ConductingEquipment",
                                     value=op_lim_set.Terminal)

    # later development
    for al in cgmes_model.cgmes_assets.ActivePowerLimit_list:
        logger.add_warning(msg='ActivePowerLimit is not supported yet.',
                           device=al,
                           device_class=al.tpe,
                           comment="Only CurrentLimit is imported!")

    for app_lim in cgmes_model.cgmes_assets.ApparentPowerLimit_list:
        logger.add_warning(msg='ApparentPowerLimit is not supported yet.',
                           device=app_lim,
                           device_class=app_lim.tpe,
                           comment="Only CurrentLimit is imported!")

    return patl_dict, tatl_900_dict, tatl_60_dict


# region PowerTransformer ----------------------------------------------------------------------------------------------


def get_pu_values_power_transformer(power_transformer: CGMES_POWER_TRANSFORMER, System_Sbase: float):
    """
    Get the transformer p.u. values
    :return: R, X, G, B, R0, X0, G0, B0
    """
    try:
        windings = list(power_transformer.PowerTransformerEnd)

        R, X, G, B = 0, 0, 0, 0
        R0, X0, G0, B0 = 0, 0, 0, 0
        if len(windings) == 2:
            for winding in windings:
                r, x, g, b, r0, x0, g0, b0 = get_pu_values_power_transformer_end(winding, System_Sbase)
                R += r
                X += x
                G += g
                B += b
                R0 += r0
                X0 += x0
                G0 += g0
                B0 += b0

    except KeyError:
        R, X, G, B = 0, 0, 0, 0
        R0, X0, G0, B0 = 0, 0, 0, 0

    return R, X, G, B, R0, X0, G0, B0


def get_pu_values_power_transformer3w(power_transformer: CGMES_POWER_TRANSFORMER, System_Sbase: float):
    """
    Get the transformer p.u. values
    :return: r12, r23, r31, x12, x23, x31
    """
    try:
        # windings = get_windings(power_transformer)
        windings = list(power_transformer.PowerTransformerEnd)

        r12, r23, r31, x12, x23, x31 = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        if len(windings) == 3:
            r1, x1, g1, b1, r0_1, x0_1, g0_1, b0_1 = get_pu_values_power_transformer_end(windings[0], System_Sbase)
            r2, x2, g2, b2, r0_2, x0_2, g0_2, b0_2 = get_pu_values_power_transformer_end(windings[1], System_Sbase)
            r3, x3, g3, b3, r0_3, x0_3, g0_3, b0_3 = get_pu_values_power_transformer_end(windings[2], System_Sbase)

            r12 = r1 + r2
            r31 = r3 + r1
            r23 = r2 + r3
            x12 = x1 + x2
            x31 = x3 + x1
            x23 = x2 + x3

    except KeyError:
        r12, r23, r31, x12, x23, x31 = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    return r12, r23, r31, x12, x23, x31


# endregion ------------------------------------------------------------------------------------------------------------

# region PowerTransformerEnd
def get_voltage_power_transformer_end(power_transformer_end: CGMES_POWER_TRANSFORMER_END):
    """

    :param power_transformer_end:
    :return:
    """
    if power_transformer_end.ratedU > 0:
        return power_transformer_end.ratedU
    else:
        if power_transformer_end.BaseVoltage is not None:
            return power_transformer_end.BaseVoltage.nominalVoltage
        else:
            return None


def get_pu_values_power_transformer_end(power_transformer_end: CGMES_POWER_TRANSFORMER_END,
                                        Sbase_system: float = 100.0):
    """
    Get the per-unit values of the equivalent PI model
    :return: R, X, G, B, R0, X0, G0, B0
    """
    if (power_transformer_end.ratedS and power_transformer_end.ratedU and power_transformer_end.ratedS > 0 and
            power_transformer_end.ratedU > 0):
        Zbase = (power_transformer_end.ratedU * power_transformer_end.ratedU) / power_transformer_end.ratedS
        Ybase = 1.0 / Zbase
        machine_to_sys = Sbase_system / power_transformer_end.ratedS
        # at this point r, x, g, b are the complete values for all the line length
        # R = power_transformer_end.r / Zbase
        # X = power_transformer_end.x / Zbase
        # G = power_transformer_end.g / Ybase
        # B = power_transformer_end.b / Ybase
        # R0 = power_transformer_end.r0 / Zbase
        # X0 = power_transformer_end.x0 / Zbase
        # G0 = power_transformer_end.g0 / Ybase
        # B0 = power_transformer_end.b0 / Ybase
        R = power_transformer_end.r / Zbase * machine_to_sys
        X = power_transformer_end.x / Zbase * machine_to_sys
        G = power_transformer_end.g / Ybase * machine_to_sys
        B = power_transformer_end.b / Ybase * machine_to_sys
        if hasattr(power_transformer_end, "r0"):
            R0 = power_transformer_end.r0 / Zbase * machine_to_sys if power_transformer_end.r0 is not None else 1e-20
            X0 = power_transformer_end.x0 / Zbase * machine_to_sys if power_transformer_end.x0 is not None else 1e-20
            G0 = power_transformer_end.g0 / Ybase * machine_to_sys if power_transformer_end.g0 is not None else 1e-20
            B0 = power_transformer_end.b0 / Ybase * machine_to_sys if power_transformer_end.b0 is not None else 1e-20
        else:
            R0 = 1e-20
            X0 = 1e-20
            G0 = 1e-20
            B0 = 1e-20
    else:
        R = 1e-20
        X = 1e-20
        G = 1e-20
        B = 1e-20
        R0 = 1e-20
        X0 = 1e-20
        G0 = 1e-20
        B0 = 1e-20

    return R, X, G, B, R0, X0, G0, B0


# endregion ------------------------------------------------------------------------------------------------------------

# region ACLineSegment
def get_voltage_ac_line_segment(ac_line_segment: CGMES_AC_LINE_SEGMENT, logger: DataLogger) -> float | None:
    """

    :param ac_line_segment:
    :param logger:
    :return:
    """
    if ac_line_segment.BaseVoltage is None:  # or isinstance(ac_line_segment.BaseVoltage, str):
        if 'Terminal' in ac_line_segment.references_to_me.keys():
            tps = list(ac_line_segment.references_to_me['Terminal'])

            if len(tps) > 0:
                tp = tps[0]

                return get_voltage_terminal(tp, logger=logger)
            else:
                return None
        else:
            return None
    else:
        return ac_line_segment.BaseVoltage.nominalVoltage


def get_pu_values_ac_line_segment(ac_line_segment: CGMES_AC_LINE_SEGMENT, logger: DataLogger, Sbase: float = 100.0):
    """
    Get the per-unit values of the equivalent PI model

    :param ac_line_segment
    :param logger: DataLogger
    :param Sbase: Sbase in MVA
    :return: R, X, Gch, Bch
    """
    if ac_line_segment.BaseVoltage is not None:
        Vnom = get_voltage_ac_line_segment(ac_line_segment, logger=logger)

        if Vnom is not None:

            Zbase = (Vnom * Vnom) / Sbase
            Ybase = 1.0 / Zbase

            # at this point r, x, g, b are the complete values for all the line length
            R = ac_line_segment.r / Zbase
            X = ac_line_segment.x / Zbase
            G = ac_line_segment.gch / Ybase if ac_line_segment.gch is not None else 1e-20
            B = ac_line_segment.bch / Ybase if ac_line_segment.bch is not None else 1e-20
            if hasattr(ac_line_segment, "r0"):
                R0 = ac_line_segment.r0 / Zbase if ac_line_segment.r0 is not None else 1e-20
                X0 = ac_line_segment.x0 / Zbase if ac_line_segment.x0 is not None else 1e-20
                G0 = ac_line_segment.g0ch / Ybase if ac_line_segment.g0ch is not None else 1e-20
                B0 = ac_line_segment.b0ch / Ybase if ac_line_segment.b0ch is not None else 1e-20
            else:
                R0 = 1e-20
                X0 = 1e-20
                G0 = 1e-20
                B0 = 1e-20
        else:
            R = 1e-20
            X = 0.00001
            G = 1e-20
            B = 1e-20
            R0 = 1e-20
            X0 = 1e-20
            G0 = 1e-20
            B0 = 1e-20
    else:
        R = 1e-20
        X = 0.00001
        G = 1e-20
        B = 1e-20
        R0 = 1e-20
        X0 = 1e-20
        G0 = 1e-20
        B0 = 1e-20

    return R, X, G, B, R0, X0, G0, B0


def get_rate_ac_line_segment():
    return 1e-20


# endregion ------------------------------------------------------------------------------------------------------------

# region Shunt
def get_voltage_shunt(shunt: CGMES_NON_LINEAR_SHUNT_COMPENSATOR | CGMES_EQUIVALENT_SHUNT | CGMES_SHUNT_COMPENSATOR,
                      logger: DataLogger) -> float | None:
    """

    :param shunt:
    :param logger:
    :return:
    """
    if shunt.BaseVoltage is not None:
        return shunt.BaseVoltage.nominalVoltage
    elif shunt.nomU is not None:
        return shunt.nomU
    else:  # TODO look at EquipmentContainer/VoltageLevel/BaseVoltage
        if 'Terminal' in shunt.references_to_me.keys():
            tps = list(shunt.references_to_me['Terminal'])

            if len(tps) > 0:
                tp = tps[0]

                return get_voltage_terminal(tp, logger=logger)
            else:
                return None
        else:
            return None


def get_values_shunt(shunt: CGMES_LINEAR_SHUNT_COMPENSATOR,
                     logger: DataLogger,
                     Sbase: float = 100.0):
    """
    Get the per-unit values of the Shunt (per Section)

    :param shunt: CGMES Linear shunt compensator
    :param logger: Datalogger
    :param Sbase: Sbase in MVA
    :return: G, B, G0, B0
    """
    Vnom = get_voltage_shunt(shunt, logger=logger)

    if Vnom is not None:

        # Zbase = (Vnom * Vnom) / Sbase
        # Ybase = 1.0 / Zbase

        # at this point g, b are the complete values for all the line length
        G = shunt.gPerSection * (Vnom * Vnom)
        B = shunt.bPerSection * (Vnom * Vnom)
        if hasattr(shunt, "g0PerSection"):
            G0 = shunt.g0PerSection * (Vnom * Vnom) if shunt.g0PerSection is not None else 0
            B0 = shunt.b0PerSection * (Vnom * Vnom) if shunt.b0PerSection is not None else 0
        else:
            G0 = 0.0
            B0 = 0.0
    else:
        G = 0.0
        B = 0.0
        G0 = 0.0
        B0 = 0.0

    return G, B, G0, B0


# endregion ------------------------------------------------------------------------------------------------------------

# region Terminal(acdc_terminal.ACDCTerminal)
def get_voltage_terminal(terminal: CGMES_TERMINAL | CGMES_ACDC_TERMINAL,
                         logger: DataLogger) -> float | None:
    """
    Get the voltage of this terminal
    :return: Voltage or None
    """
    if hasattr(terminal, "TopologicalNode"):
        if terminal.TopologicalNode is not None:
            return get_nominal_voltage(terminal.TopologicalNode, logger=logger)
        else:
            return None
    elif hasattr(terminal, "DCTopologicalNode"):
        logger.add_error("Cannot retrieve voltage from a DC terminal, this is a CGMES design error",
                         device_class=terminal.tpe,
                         device_property="DCTopologicalNode",
                         device=terminal.uuid)
        return None


# ----------------------------------------------------------------------------------------------------------------------
# TopologicalNode(IdentifiedObject):
# ----------------------------------------------------------------------------------------------------------------------

def get_nominal_voltage(topological_node: CGMES_TOPOLOGICAL_NODE, logger: DataLogger) -> float:
    """
    Try to get the nominal voltage of a TopologicalNode
    :return: hopefully the nominal voltage
    """
    if topological_node.BaseVoltage is not None:
        if not isinstance(topological_node.BaseVoltage, str):
            return float(topological_node.BaseVoltage.nominalVoltage)
        else:
            logger.add_error(msg='Missing reference',
                             device=topological_node.rdfid,
                             device_class=topological_node.tpe,
                             device_property="BaseVoltage",
                             value=topological_node.BaseVoltage,
                             expected_value='object')
            return 0.0
    else:
        logger.add_error(msg='Missing reference',
                         device=topological_node.rdfid,
                         device_class=topological_node.tpe,
                         device_property="BaseVoltage",
                         value=topological_node.BaseVoltage,
                         expected_value='object')
        return 0.0


def get_nominal_voltage_for_cn(cn: CGMES_CONNECTIVITY_NODE, logger: DataLogger) -> float:
    """
    Try to get the nominal voltage of a ConnectivityNode
    :return: hopefully the nominal voltage
    """
    if hasattr(cn, 'ConnectivityNodeContainer'):
        if hasattr(cn.ConnectivityNodeContainer, 'BaseVoltage'):
            if cn.ConnectivityNodeContainer.BaseVoltage is not None:
                if not isinstance(cn.ConnectivityNodeContainer.BaseVoltage, str):
                    return float(cn.ConnectivityNodeContainer.BaseVoltage.nominalVoltage)
                else:
                    logger.add_error(msg='Missing reference',
                                     device=cn.rdfid,
                                     device_class=cn.tpe,
                                     device_property="BaseVoltage",
                                     value=cn.ConnectivityNodeContainer.BaseVoltage,
                                     expected_value='object')
                    return 0.0
            else:
                logger.add_error(msg='Missing reference',
                                 device=cn.rdfid,
                                 device_class=cn.tpe,
                                 device_property="BaseVoltage",
                                 value=cn.ConnectivityNodeContainer,
                                 expected_value='object')
                return 0.0
        else:
            logger.add_error(msg='Missing reference',
                             device=cn.rdfid,
                             device_class=cn.tpe,
                             device_property="BaseVoltage",
                             value=cn.ConnectivityNodeContainer,
                             expected_value='object')
            return 0.0
    else:
        logger.add_error(msg='Missing reference',
                         device=cn.rdfid,
                         device_class=cn.tpe,
                         device_property="ConnectivityNodeContainer",
                         value=cn,
                         expected_value='object')
        return 0.0


# endregion


# region LoadResponseCharacteristic(IdentifiedObject)
# def check_load_response_characteristic(load_response_characteristic, logger: DataLogger):
#     """
#     Check OCL rules
#     :param load_response_characteristic:
#     :param logger:
#     :return:
#     """
#     err_counter = 0
#     if load_response_characteristic.exponentModel:
#         if load_response_characteristic.pVoltageExponent not in load_response_characteristic.parsed_properties.keys():
#             err_counter += 1
#             logger.add_error(msg="OCL rule violation: pVoltageExponent not specified",
#                              device=load_response_characteristic.rdfid,
#                              device_class="LoadResponseCharacteristic",
#                              expected_value="Existence of pVoltageExponent")
#
#         if load_response_characteristic.qVoltageExponent not in load_response_characteristic.parsed_properties.keys():
#             err_counter += 1
#             logger.add_error(msg="OCL rule violation: qVoltageExponent not specified",
#                              device=load_response_characteristic.rdfid,
#                              device_class="LoadResponseCharacteristic",
#                              expected_value="Existence of qVoltageExponent")
#     else:
#         if load_response_characteristic.pConstantCurrent not in load_response_characteristic.parsed_properties.keys():
#             err_counter += 1
#             logger.add_error(msg="OCL rule violation: pConstantCurrent not specified",
#                              device=load_response_characteristic.rdfid,
#                              device_class="LoadResponseCharacteristic",
#                              expected_value="Existence of pConstantCurrent")
#
#         if load_response_characteristic.pConstantPower not in load_response_characteristic.parsed_properties.keys():
#             err_counter += 1
#             logger.add_error(msg="OCL rule violation: pConstantPower not specified",
#                              device=load_response_characteristic.rdfid,
#                              device_class="LoadResponseCharacteristic",
#                              expected_value="Existence of pConstantPower")
#
#         if load_response_characteristic.pConstantImpedance not in load_response_characteristic.parsed_properties.keys():
#             err_counter += 1
#             logger.add_error(msg="OCL rule violation: pConstantImpedance not specified",
#                              device=load_response_characteristic.rdfid,
#                              device_class="LoadResponseCharacteristic",
#                              expected_value="Existence of pConstantImpedance")
#
#         if load_response_characteristic.qConstantCurrent not in load_response_characteristic.parsed_properties.keys():
#             err_counter += 1
#             logger.add_error(msg="OCL rule violation: qConstantCurrent not specified",
#                              device=load_response_characteristic.rdfid,
#                              device_class="LoadResponseCharacteristic",
#                              expected_value="Existence of qConstantCurrent")
#
#         if load_response_characteristic.qConstantPower not in load_response_characteristic.parsed_properties.keys():
#             err_counter += 1
#             logger.add_error(msg="OCL rule violation: qConstantPower not specified",
#                              device=load_response_characteristic.rdfid,
#                              device_class="LoadResponseCharacteristic",
#                              expected_value="Existence of qConstantPower")
#
#         if load_response_characteristic.qConstantImpedance not in load_response_characteristic.parsed_properties.keys():
#             err_counter += 1
#             logger.add_error(msg="OCL rule violation: qConstantImpedance not specified",
#                              device=load_response_characteristic.rdfid,
#                              device_class="LoadResponseCharacteristic",
#                              expected_value="Existence of qConstantImpedance")
#
#         # p_factor = 0
#         # p_factor += load_response_characteristic.pConstantImpedance if load_response_characteristic.pConstantImpedance != ''
#         # p_factor = load_response_characteristic.pConstantImpedance + load_response_characteristic.pConstantCurrent + load_response_characteristic.pConstantPower
#         # q_factor = load_response_characteristic.qConstantImpedance + load_response_characteristic.qConstantCurrent + load_response_characteristic.qConstantPower
#         # if not np.isclose(p_factor, 1):
#         #     err_counter += 1
#         #     logger.add_error(msg="pConstantImpedance + pConstantCurrent + pConstantPower different from 1",
#         #                      device=load_response_characteristic.rdfid,
#         #                      device_class="LoadResponseCharacteristic",
#         #                      expected_value="1.0")
#         #
#         # if not np.isclose(q_factor, 1):
#         #     err_counter += 1
#         #     logger.add_error(msg="qConstantImpedance + qConstantCurrent + qConstantPower different from 1",
#         #                      device=load_response_characteristic.rdfid,
#         #                      device_class="LoadResponseCharacteristic",
#         #                      expected_value="1.0")
#
#     return err_counter == 0


# endregion

# ----------------------------------------------------------------------------------------------------------------------
# region BaseVoltage(IdentifiedObject)
# ----------------------------------------------------------------------------------------------------------------------

def base_voltage_to_str(base_voltage: CGMES_BASE_VOLTAGE) -> str:
    """

    :param base_voltage:
    :return:
    """
    return base_voltage.tpe + ':' + base_voltage.rdfid + ':' + str(base_voltage.nominalVoltage) + ' kV'


# endregion

# ----------------------------------------------------------------------------------------------------------------------

def get_regulating_control_params(cgmes_elm,
                                  cgmes_enums,
                                  bus_dict,
                                  TopologicalNode_tpe,
                                  DCTopologicalNode_tpe,
                                  logger: DataLogger):
    """

    :param cgmes_elm:
    :param cgmes_enums:
    :param bus_dict:
    :param TopologicalNode_tpe:
    :param DCTopologicalNode_tpe:
    :param logger:
    :return:
    """

    control_bus = None
    if cgmes_elm.RegulatingControl is not None:

        if cgmes_elm.RegulatingControl.enabled:
            if cgmes_elm.controlEnabled:
                is_controlled = True
            else:
                is_controlled = False
        else:
            is_controlled = False

        control_node = None

        # TapModuleControl
        # fixed = 'Fixed'
        # Vm = 'Vm'
        # Qf = 'Qf'
        # Qt = 'Qt'
        #
        #
        # TapAngleControl,
        # fixed = 'Fixed'
        # Pf = 'Pf'
        # Pt = 'Pt'
        # belongs to PhaseTap, fixed if

        if cgmes_elm.RegulatingControl.mode == cgmes_enums.RegulatingControlModeKind.voltage:

            v_control_value = cgmes_elm.RegulatingControl.targetValue  # kV

            # cgmes_elm.EquipmentContainer.BaseVoltage.nominalVoltage
            controlled_terminal = cgmes_elm.RegulatingControl.Terminal
            # control_node = # TODO get gc.cn from terminal

            base_voltage = 0  # default
            if controlled_terminal.TopologicalNode:
                base_voltage = controlled_terminal.TopologicalNode.BaseVoltage.nominalVoltage
            else:
                if controlled_terminal.ConnectivityNode:
                    tn = controlled_terminal.ConnectivityNode.TopologicalNode
                    base_voltage = tn.BaseVoltage.nominalVoltage

            if base_voltage != 0:
                v_set = v_control_value / base_voltage
            else:
                v_set = 1.0

            if cgmes_elm.EquipmentContainer.tpe == 'VoltageLevel':
                # find the control node
                control_terminal = cgmes_elm.RegulatingControl.Terminal
                control_bus = find_terminal_bus(
                    cgmes_terminal=control_terminal,
                    bus_dict=bus_dict,
                    TopologicalNode_tpe=TopologicalNode_tpe,
                    DCTopologicalNode_tpe=DCTopologicalNode_tpe
                )
                control_node = None
            else:
                control_node = None
                v_set = 1.0
                is_controlled = False
                logger.add_warning(msg='RegulatingCondEq has no voltage control',
                                   device=cgmes_elm.rdfid,
                                   device_class=cgmes_elm.tpe,
                                   device_property="EquipmentContainer",
                                   value='None',
                                   expected_value='BaseVoltage')

        else:
            control_node = None
            v_set = 1.0
            is_controlled = False
            logger.add_warning(msg='RegulatingCondEq has control, but not voltage',
                               device=cgmes_elm.rdfid,
                               device_class=cgmes_elm.tpe,
                               device_property="EquipmentContainer",
                               value='None',
                               expected_value='BaseVoltage')
    else:
        control_node = None
        v_set = 1.0
        is_controlled = False
        logger.add_warning(msg='RegulatingCondEq has no control',
                           device=cgmes_elm.rdfid,
                           device_class=cgmes_elm.tpe,
                           device_property="EquipmentContainer",
                           value='None',
                           expected_value='BaseVoltage')

    return v_set, is_controlled, control_bus, control_node


# ----------------------------------------------------------------------------------------------------------------------
# region export UTILS
# ----------------------------------------------------------------------------------------------------------------------

def find_object_by_uuid(cgmes_model: CgmesCircuit, object_list: List[CGMES_ASSETS], target_uuid: str):
    """
    Finds an object with the specified uuid
     in the given object_list from a CGMES Circuit.

    Args:
        cgmes_model:
        object_list (list[MyObject]): List of MyObject instances.
        target_uuid (str): The uuid to search for.

    Returns:
        MyObject or None: The found object or None if not found.
    """
    boundary_obj_dict = cgmes_model.all_objects_dict_boundary
    if boundary_obj_dict is not None:
        for k, obj in boundary_obj_dict.items():
            if rfid2uuid(k) == target_uuid:
                return obj

    for obj in object_list:
        if obj.uuid == target_uuid:
            return obj
    return None


def find_object_by_cond_eq_uuid(object_list, cond_eq_target_uuid):
    """
    Finds a conducting equipment object with the specified uuid
    in the given object_list from a CGMES Circuit.

    Args:
        object_list (list[MyObject]): List of MyObject instances.
        cond_eq_target_uuid (str): The uuid to search for.

    Returns:
        MyObject or None: The found object or None if not found.
    """

    for obj in object_list:
        if obj.ConductingEquipment.uuid == cond_eq_target_uuid:
            return obj
    return None


def find_object_by_vnom(cgmes_model: CgmesCircuit, object_list: List[CGMES_BASE_VOLTAGE],
                        target_vnom: float) -> CGMES_BASE_VOLTAGE | None:
    """
    Find object in the base voltages
    :param cgmes_model: CgmesCircuit
    :param object_list: List of BaseVoltage
    :param target_vnom: Some voltage to look for
    :return: BaseVoltage | None
    """
    boundary_obj_list: List[CGMES_BASE_VOLTAGE] = cgmes_model.elements_by_type_boundary.get("BaseVoltage", None)

    # first, search in the boundary set
    if boundary_obj_list is not None:
        for obj in boundary_obj_list:
            if obj.nominalVoltage == target_vnom:
                return obj

    # if not found, search in the provided objects list
    for obj in object_list:
        if obj.nominalVoltage == target_vnom:
            return obj

    return None


def find_object_by_attribute(object_list: List, target_attr_name: str, target_value: str | float | int):
    """

    :param object_list:
    :param target_attr_name:
    :param target_value:
    :return:
    """
    if hasattr(object_list[0], target_attr_name):
        for obj in object_list:
            obj_attr = getattr(obj, target_attr_name)
            if obj_attr == target_value:
                return obj
    return None


def get_ohm_values_power_transformer(r: float, x: float, g: float, b: float,
                                     r0: float, x0: float, g0: float, b0: float,
                                     nominal_power: float, rated_voltage: float, Sbase: float):
    """
    Get the transformer ohm values
    :param r:
    :param x:
    :param g:
    :param b:
    :param r0:
    :param x0:
    :param g0:
    :param b0:
    :param nominal_power:
    :param rated_voltage:
    :param Sbase:
    :return:
    """

    if nominal_power > 0:
        Zbase = (rated_voltage * rated_voltage) / nominal_power
        Ybase = 1.0 / Zbase
        machine_to_sys = Sbase / nominal_power

        R = r * Zbase / machine_to_sys
        X = x * Zbase / machine_to_sys
        G = g * Ybase / machine_to_sys
        B = b * Ybase / machine_to_sys
        R0 = r0 * Zbase / machine_to_sys if r0 is not None else 0
        X0 = x0 * Zbase / machine_to_sys if x0 is not None else 0
        G0 = g0 * Ybase / machine_to_sys if g0 is not None else 0
        B0 = b0 * Ybase / machine_to_sys if b0 is not None else 0

    else:
        R, X, G, B = 0, 0, 0, 0
        R0, X0, G0, B0 = 0, 0, 0, 0

    return R, X, G, B, R0, X0, G0, B0

# endregion
