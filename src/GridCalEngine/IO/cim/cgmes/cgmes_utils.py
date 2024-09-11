from typing import List, Tuple, Dict
import numpy as np
import GridCalEngine.Devices as gcdev
from GridCalEngine.IO.cim.cgmes.base import Base, rfid2uuid
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.data_logger import DataLogger


def find_terms_connections(cgmes_terminal: Base,
                           calc_node_dict: Dict[str, gcdev.Bus],
                           cn_dict: Dict[str, gcdev.ConnectivityNode]) -> Tuple[gcdev.Bus, gcdev.ConnectivityNode]:
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


def find_object_by_idtag(object_list, target_idtag):
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

    @param machines: List[SynchronousMachine]
    @return: ID of a Topological Node
    """
    for m in machines:
        if m.referencePriority == 1:
            if not isinstance(m.Terminals, list):
                return m.Terminals.TopologicalNode.rdfid
            else:
                return m.Terminals[0].TopologicalNode.rdfid
    return None


def build_rates_dict(cgmes_model, device_type, logger):
    """
    Builds Rating dictionary for given device type from OperationalLimitSets

    :param cgmes_model:
    :param device_type:
    :param logger:
    :return:
    """
    rates_dict = dict()
    for cl in cgmes_model.cgmes_assets.CurrentLimit_list:

        if cl.OperationalLimitSet is None:
            logger.add_error(msg='OperationalLimitSet missing.',
                             device=cl.rdfid,
                             device_class=cl.tpe,
                             device_property="OperationalLimitSet",
                             value="None")
            continue
        if not isinstance(cl.OperationalLimitSet, str):
            if isinstance(cl.OperationalLimitSet, list):
                for ols in cl.OperationalLimitSet:
                    volt = get_voltage_terminal(ols.Terminal, logger)
                    rate_mva = np.round(cl.value * volt / 1000, 4)
                    # TODO rate in MVA = kA * kV * sqrt(3), is sqrt(3) needed?
                    # TODO type check: put min PATL to the dict
                    if isinstance(ols.Terminal.ConductingEquipment,
                                  device_type):
                        branch_id = ols.Terminal.ConductingEquipment.uuid
                        act_lim = rates_dict.get(branch_id, None)
                        if act_lim is None:
                            rates_dict[branch_id] = rate_mva
                        elif cl.value < act_lim:
                            rates_dict[branch_id] = rate_mva
            else:
                if isinstance(cl.OperationalLimitSet.Terminal.ConductingEquipment,
                              device_type):
                    volt = get_voltage_terminal(cl.OperationalLimitSet.Terminal,
                                                logger)
                    rate_mva = np.round(cl.value * volt / 1000, 4)

                    branch_id = cl.OperationalLimitSet.Terminal.ConductingEquipment.uuid
                    act_lim = rates_dict.get(branch_id, None)
                    if act_lim is None:
                        rates_dict[branch_id] = rate_mva
                    elif cl.value < act_lim:
                        rates_dict[branch_id] = rate_mva

    # TODO ActivePowerLimit_list, ApparentPowerLimit_list
    # for al in [cgmes_model.cgmes_assets.ActivePowerLimit_list,
    #            cgmes_model.cgmes_assets.ApparentPowerLimit_list]:

    return rates_dict


# region PowerTransformer


def get_pu_values_power_transformer(power_transformer, System_Sbase):
    """
    Get the transformer p.u. values
    :return:
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


def get_pu_values_power_transformer3w(power_transformer, System_Sbase):
    """
    Get the transformer p.u. values
    :return:
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


# endregion

# region PowerTransformerEnd
def get_voltage_power_transformer_end(power_transformer_end):
    if power_transformer_end.ratedU > 0:
        return power_transformer_end.ratedU
    else:
        if power_transformer_end.BaseVoltage is not None:
            return power_transformer_end.BaseVoltage.nominalVoltage
        else:
            return None


def get_pu_values_power_transformer_end(power_transformer_end, Sbase_system=100):
    """
    Get the per-unit values of the equivalent PI model
    :return: R, X, Gch, Bch
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
            R0 = power_transformer_end.r0 / Zbase * machine_to_sys if power_transformer_end.r0 is not None else 0
            X0 = power_transformer_end.x0 / Zbase * machine_to_sys if power_transformer_end.x0 is not None else 0
            G0 = power_transformer_end.g0 / Ybase * machine_to_sys if power_transformer_end.g0 is not None else 0
            B0 = power_transformer_end.b0 / Ybase * machine_to_sys if power_transformer_end.b0 is not None else 0
        else:
            R0 = 0
            X0 = 0
            G0 = 0
            B0 = 0
    else:
        R = 0
        X = 0
        G = 0
        B = 0
        R0 = 0
        X0 = 0
        G0 = 0
        B0 = 0

    return R, X, G, B, R0, X0, G0, B0


# endregion

# region ACLineSegment
def get_voltage_ac_line_segment(ac_line_segment, logger: DataLogger):
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


def get_pu_values_ac_line_segment(ac_line_segment, logger: DataLogger, Sbase: float = 100.0):
    """
    Get the per-unit values of the equivalent PI model

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
            G = ac_line_segment.gch / Ybase if ac_line_segment.gch is not None else 0
            B = ac_line_segment.bch / Ybase if ac_line_segment.bch is not None else 0
            if hasattr(ac_line_segment, "r0"):
                R0 = ac_line_segment.r0 / Zbase if ac_line_segment.r0 is not None else 0
                X0 = ac_line_segment.x0 / Zbase if ac_line_segment.x0 is not None else 0
                G0 = ac_line_segment.g0ch / Ybase if ac_line_segment.g0ch is not None else 0
                B0 = ac_line_segment.b0ch / Ybase if ac_line_segment.b0ch is not None else 0
            else:
                R0 = 0
                X0 = 0
                G0 = 0
                B0 = 0
        else:
            R = 0
            X = 0
            G = 0
            B = 0
            R0 = 0
            X0 = 0
            G0 = 0
            B0 = 0
    else:
        R = 0
        X = 0
        G = 0
        B = 0
        R0 = 0
        X0 = 0
        G0 = 0
        B0 = 0

    return R, X, G, B, R0, X0, G0, B0


def get_rate_ac_line_segment():
    return 1e-20


# endregion

# region Shunt
def get_voltage_shunt(shunt, logger: DataLogger):
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


def get_values_shunt(shunt,
                     logger: DataLogger,
                     Sbase: float = 100.0):
    """
    Get the per-unit values of the Shunt (per Section)

    :param shunt: CGMES Linear shunt compensator
    :param logger: Datalogger
    :param Sbase: Sbase in MVA
    :return: G, B, G0, B0
    """
    if shunt.BaseVoltage is not None:
        Vnom = get_voltage_shunt(shunt, logger=logger)

        if Vnom is not None:

            # Zbase = (Vnom * Vnom) / Sbase
            # Ybase = 1.0 / Zbase

            # at this point g, b are the complete values for all the line length
            G = shunt.gPerSection * (Vnom * Vnom) if shunt.gPerSection is not None else 0
            B = shunt.bPerSection * (Vnom * Vnom) if shunt.bPerSection is not None else 0
            G0 = shunt.g0PerSection * (Vnom * Vnom) if shunt.g0PerSection is not None else 0
            B0 = shunt.b0PerSection * (Vnom * Vnom) if shunt.b0PerSection is not None else 0

        else:
            G = 0
            B = 0
            G0 = 0
            B0 = 0

    else:
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
                G0 = 0
                B0 = 0
        else:
            G = 0
            B = 0
            G0 = 0
            B0 = 0

    return G, B, G0, B0


# endregion

# region Terminal(acdc_terminal.ACDCTerminal)
def get_voltage_terminal(terminal, logger: DataLogger):
    """
    Get the voltage of this terminal
    :return: Voltage or None
    """
    if terminal.TopologicalNode is not None:
        return get_nominal_voltage(terminal.TopologicalNode, logger=logger)
    else:
        return None


# endregion


# region TopologicalNode(IdentifiedObject):
def get_nominal_voltage(topological_node, logger) -> float:
    """

    :return:
    """
    if topological_node.BaseVoltage is not None:
        if not isinstance(topological_node.BaseVoltage, str):
            return float(topological_node.BaseVoltage.nominalVoltage)
        else:
            logger.add_error(msg='Missing refference',
                             device=topological_node.rdfid,
                             device_class=topological_node.tpe,
                             device_property="BaseVoltage",
                             value=topological_node.BaseVoltage,
                             expected_value='object')
    else:
        logger.add_error(msg='Missing refference',
                         device=topological_node.rdfid,
                         device_class=topological_node.tpe,
                         device_property="BaseVoltage",
                         value=topological_node.BaseVoltage,
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

# region BaseVoltage(IdentifiedObject)
def base_voltage_to_str(base_voltage):
    return base_voltage.tpe + ':' + base_voltage.rdfid + ':' + str(base_voltage.nominalVoltage) + ' kV'


# endregion

def get_regulating_control(cgmes_elm,
                           cgmes_enums,
                           calc_node_dict,
                           cn_dict,
                           logger: DataLogger):
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
                control_node, cn = find_terms_connections(cgmes_terminal=control_terminal,
                                                          calc_node_dict=calc_node_dict,
                                                          cn_dict=cn_dict)

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


# region export UTILS

# class ReferenceManager:
#     # use it after an element object added
#     def __init__(self):
#         self.data = dict()
#
#     def add(self, cgmes_obj: Base):
#
#         tpe_dict = self.data.get(cgmes_obj.tpe, None)
#         if tpe_dict is None:
#             self.data[cgmes_obj.tpe] = {cgmes_obj.rdfid: cgmes_obj}
#         else:
#             tpe_dict[cgmes_obj.rdfid] = cgmes_obj


def find_object_by_uuid(cgmes_model: CgmesCircuit, object_list, target_uuid):
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


def find_tn_by_name(cgmes_model: CgmesCircuit, target_name):
    """
    Finds the topological node with the specified name
     from a CGMES Circuit.

    @param cgmes_model:
    @param target_name:
    @return:
    """
    boundary_obj_dict = cgmes_model.elements_by_type_boundary.get("TopologicalNode")
    if boundary_obj_dict is not None:
        for obj in boundary_obj_dict:
            if obj.name == target_name:
                return obj
    for obj in cgmes_model.cgmes_assets.TopologicalNode_list:
        if obj.name == target_name:
            return obj
    return None


def find_object_by_vnom(cgmes_model: CgmesCircuit, object_list: List[Base], target_vnom):
    boundary_obj_list = cgmes_model.elements_by_type_boundary.get("BaseVoltage")
    if boundary_obj_list is not None:
        for obj in boundary_obj_list:
            if obj.nominalVoltage == target_vnom:
                return obj
    for obj in object_list:
        if obj.nominalVoltage == target_vnom:
            return obj
    return None


def find_object_by_attribute(object_list: List, target_attr_name, target_value):
    if hasattr(object_list[0], target_attr_name):
        for obj in object_list:
            obj_attr = getattr(obj, target_attr_name)
            if obj_attr == target_value:
                return obj
    return None


def get_ohm_values_power_transformer(r, x, g, b, r0, x0, g0, b0, nominal_power, rated_voltage):
    """
    Get the transformer ohm values
    :return:
    """
    try:
        Sbase_system = 100
        Zbase = (rated_voltage * rated_voltage) / nominal_power
        Ybase = 1.0 / Zbase
        R, X, G, B = 0, 0, 0, 0
        R0, X0, G0, B0 = 0, 0, 0, 0
        machine_to_sys = Sbase_system / nominal_power
        R = r * Zbase / machine_to_sys
        X = x * Zbase / machine_to_sys
        G = g * Ybase / machine_to_sys
        B = b * Ybase / machine_to_sys
        R0 = r0 * Zbase / machine_to_sys if r0 is not None else 0
        X0 = x0 * Zbase / machine_to_sys if x0 is not None else 0
        G0 = g0 * Ybase / machine_to_sys if g0 is not None else 0
        B0 = b0 * Ybase / machine_to_sys if b0 is not None else 0

    except KeyError:
        R, X, G, B = 0, 0, 0, 0
        R0, X0, G0, B0 = 0, 0, 0, 0

    return R, X, G, B, R0, X0, G0, B0

# endregion
