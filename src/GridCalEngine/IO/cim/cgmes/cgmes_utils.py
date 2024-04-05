from typing import List, Tuple

from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ac_line_segment import ACLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.busbar_section import BusbarSection
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_consumer import EnergyConsumer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_response_characteristic import LoadResponseCharacteristic
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_control import RegulatingControl
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.switch import Switch
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.linear_shunt_compensator import LinearShuntCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.synchronous_machine import SynchronousMachine
from GridCalEngine.data_logger import DataLogger
import numpy as np


def get_slack_id(machines: List[SynchronousMachine]):
    for m in machines:
        if m.referencePriority == 1:
            if not isinstance(m.Terminals, list):
                return m.Terminals.TopologicalNode.rdfid
            else:
                return m.Terminals[0].TopologicalNode.rdfid
    return None


# region PowerTransformer
def get_windings_number(power_transformer: PowerTransformer):
    """
    Get the number of windings
    :return: # number of associated windings
    """
    # todo: No reference for this method
    try:
        return len(power_transformer.references_to_me['PowerTransformerEnd'])
    except KeyError:
        return 0


def get_windings(power_transformer: PowerTransformer) -> List["PowerTransformerEnd"]:
    """
    Get list of windings in order of .endNumber
    :return: list of winding objects
    """
    try:
        windings_init: List[PowerTransformerEnd] = list(power_transformer.references_to_me['PowerTransformerEnd'])

        # windings: List[PowerTransformerEnd] = list()
        # for winding in windings_init:
        #     if winding.endNumber == 1:
        #         windings.append(winding)
        # for winding in windings_init:
        #     if winding.endNumber == 2:
        #         windings.append(winding)
        # if len(windings_init) == 3:
        #     for winding in windings_init:
        #         if winding.endNumber == 3:
        #             windings.append(winding)

        return sorted(windings_init, key=lambda x: x.endNumber)
    except KeyError:
        return list()


def get_pu_values_power_transformer(power_transformer: PowerTransformer, System_Sbase):
    """
    Get the transformer p.u. values
    :return:
    """
    try:
        # windings = get_windings(power_transformer)
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


def get_pu_values_power_transformer3w(power_transformer: PowerTransformer, System_Sbase):
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


def get_voltages(power_transformer: PowerTransformer):
    """

    :return:
    """
    # todo: is it unnecessary? Referenced only in cimparser
    return [get_voltage_power_transformer_end(x) for x in
            get_windings(power_transformer)]  # TODO logger?


def get_rate(power_transformer: PowerTransformer):
    rating = 0
    for winding in get_windings(power_transformer):
        if winding.ratedS > rating:
            rating = winding.ratedS

    return rating


# endregion

# region PowerTransformerEnd
def get_voltage_power_transformer_end(power_transformer_end: PowerTransformerEnd):
    if power_transformer_end.ratedU > 0:
        return power_transformer_end.ratedU
    else:
        if power_transformer_end.BaseVoltage is not None:
            return power_transformer_end.BaseVoltage.nominalVoltage
        else:
            return None


def get_pu_values_power_transformer_end(power_transformer_end: PowerTransformerEnd, Sbase_system=100):
    """
    Get the per-unit values of the equivalent PI model
    :return: R, X, Gch, Bch
    """
    if power_transformer_end.ratedS > 0 and power_transformer_end.ratedU > 0:
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
        R0 = power_transformer_end.r0 / Zbase * machine_to_sys if power_transformer_end.r0 is not None else 0
        X0 = power_transformer_end.x0 / Zbase * machine_to_sys if power_transformer_end.x0 is not None else 0
        G0 = power_transformer_end.g0 / Ybase * machine_to_sys if power_transformer_end.g0 is not None else 0
        B0 = power_transformer_end.b0 / Ybase * machine_to_sys if power_transformer_end.b0 is not None else 0
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
def get_voltage_ac_line_segment(ac_line_segment: ACLineSegment, logger: DataLogger):
    if ac_line_segment.BaseVoltage is not None:
        return ac_line_segment.BaseVoltage.nominalVoltage
    else:
        if 'Terminal' in ac_line_segment.references_to_me.keys():
            tps = list(ac_line_segment.references_to_me['Terminal'])

            if len(tps) > 0:
                tp = tps[0]

                return get_voltage_terminal(tp, logger=logger)
            else:
                return None
        else:
            return None


def get_pu_values_ac_line_segment(ac_line_segment: ACLineSegment, logger: DataLogger, Sbase: float = 100.0):
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
            R0 = ac_line_segment.r0 / Zbase if ac_line_segment.r0 is not None else 0
            X0 = ac_line_segment.x0 / Zbase if ac_line_segment.x0 is not None else 0
            G0 = ac_line_segment.g0ch / Ybase if ac_line_segment.g0ch is not None else 0
            B0 = ac_line_segment.b0ch / Ybase if ac_line_segment.b0ch is not None else 0
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
def get_voltage_shunt(shunt: LinearShuntCompensator, logger: DataLogger):
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


def get_values_shunt(shunt: LinearShuntCompensator, logger: DataLogger, Sbase: float = 100.0):
    """
    Get the per-unit values of the Shunt (per Section)

    :param Sbase: Sbase in MVA
    :return: G, B
    """
    if shunt.BaseVoltage is not None:
        Vnom = get_voltage_shunt(shunt, logger=logger)

        if Vnom is not None:

            # Zbase = (Vnom * Vnom) / Sbase
            # Ybase = 1.0 / Zbase

            # at this point g, b are the complete values for all the line length
            G = shunt.gPerSection * (Vnom * Vnom)
            B = shunt.bPerSection * (Vnom * Vnom)
            G0 = shunt.g0PerSection * (Vnom * Vnom)
            B0 = shunt.b0PerSection * (Vnom * Vnom)

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
            G0 = shunt.g0PerSection * (Vnom * Vnom) if shunt.g0PerSection is not None else 0
            B0 = shunt.b0PerSection * (Vnom * Vnom) if shunt.b0PerSection is not None else 0

        else:
            G = 0
            B = 0
            G0 = 0
            B0 = 0

    return G, B, G0, B0


# endregion

# region Terminal(acdc_terminal.ACDCTerminal)
def get_voltage_terminal(terminal: Terminal, logger: DataLogger):
    """
    Get the voltage of this terminal
    :return: Voltage or None
    """
    if terminal.TopologicalNode is not None:
        return get_nominal_voltage(terminal.TopologicalNode, logger=logger)
    else:
        return None


# endregion

# region BusbarSection(IdentifiedObject)
def get_topological_nodes_bus_bar(busbar_section: BusbarSection):
    """
    Get the associated TopologicalNode instances
    :return: list of TopologicalNode instances
    """
    # todo: referenced only from cim16
    try:
        terms = busbar_section.references_to_me['Terminal']
        return [TopologicalNode for term in terms]
    except KeyError:
        return list()


def get_topological_node_bus_bar(busbar_section: BusbarSection):
    """
    Get the first TopologicalNode found
    :return: first TopologicalNode found
    """
    # todo: referenced only from cim16
    try:
        terms = busbar_section.references_to_me['Terminal']
        for term in terms:
            return TopologicalNode
    except KeyError:
        return list()


# endregion

# region Dipole (IdentifiedObject)
def get_topological_nodes_dipole(identified_object: IdentifiedObject) -> Tuple["TopologicalNode", "TopologicalNode"]:
    """
    Get the TopologyNodes of this branch
    :return: (TopologyNodes, TopologyNodes) or (None, None)
    """
    # todo
    try:
        terminals = list(identified_object.references_to_me['Terminal'])

        if len(terminals) == 2:
            n1 = terminals[0].TopologicalNode
            n2 = terminals[1].TopologicalNode
            return n1, n2
        else:
            return None, None

    except KeyError:
        return None, None


def get_buses_dipole(identified_object: IdentifiedObject) -> Tuple["BusbarSection", "BusbarSection"]:
    """
    Get the associated bus
    :return: (BusbarSection, BusbarSection) or (None, None)
    """
    # todo: not referenced
    t1, t2 = get_topological_nodes_dipole(identified_object)
    b1 = get_bus_topological_node(t1) if t1 is not None else None
    b2 = get_bus_topological_node(t1) if t2 is not None else None
    return b1, b2


def get_nodes_dipole(identified_object: IdentifiedObject) -> Tuple["TopologicalNode", "TopologicalNode"]:
    """
    Get the TopologyNodes of this branch
    :return: two TopologyNodes or nothing
    """
    # todo: not referenced
    try:
        terminals = list(identified_object.references_to_me['Terminal'])

        if len(terminals) == 2:
            n1 = terminals[0].TopologicalNode
            n2 = terminals[1].TopologicalNode
            return n1, n2
        else:
            return None, None

    except KeyError:
        return None, None


# endregion

# region MonoPole(ConductingEquipment)
def get_topological_node_monopole(conducting_equipment: ConductingEquipment):
    """
    Get the TopologyNodes of this branch
    :return: two TopologyNodes or nothing
    """
    try:
        terminals = list(conducting_equipment.references_to_me['Terminal'])

        if len(terminals) == 1:
            n1 = terminals[0].TopologicalNode
            return n1
        else:
            return None

    except KeyError:
        return None


def get_bus_monopole(conducting_equipment: ConductingEquipment):
    """
    Get the associated bus
    :return:
    """
    tp = get_topological_node_monopole(conducting_equipment)
    if tp is None:
        return None
    else:
        return get_bus_topological_node(tp)  # todo: is it ok?


def get_dict(conducting_equipment: ConductingEquipment):
    """
    Get dictionary with the data
    :return: Dictionary
    """
    tp = get_topological_node_monopole(conducting_equipment)
    bus = get_bus_topological_node(tp) if tp is not None else None  # todo: is it ok?

    d = conducting_equipment.get_dict()  # todo: check it
    d['TopologicalNode'] = '' if tp is None else tp.uuid
    d['BusbarSection'] = '' if bus is None else bus.uuid
    return d


# endregion

# region ConformLoad, NonConformLoad(EnergyConsumer)
def get_pq(energy_consumer: EnergyConsumer):
    # todo: referenced only from cim16
    return energy_consumer.p, energy_consumer.q


# endregion

# region TopologicalNode(IdentifiedObject):
def get_nominal_voltage(topological_node: TopologicalNode, logger) -> float:
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
        return 0.0


def get_bus_topological_node(topological_node: TopologicalNode):
    """
    Get an associated BusBar, if any
    :return: BusbarSection or None is not fond
    """
    try:
        terms = topological_node.references_to_me['Terminal']
        for term in terms:
            if isinstance(ConductingEquipment, BusbarSection):  # TODO check the old code
                return ConductingEquipment

    except KeyError:
        return None


# endregion

# region Switch(DiPole, ConductingEquipment):
def get_nodes(switch: Switch):
    """
    Get the TopologyNodes of this branch
    :return: two TopologyNodes or nothing
    """
    # todo: not referenced
    try:
        terminals = list(switch.references_to_me['Terminal'])

        if len(terminals) == 2:
            n1 = TopologicalNode
            n2 = TopologicalNode
            return n1, n2
        else:
            return None, None

    except KeyError:
        return None, None


# endregion

def check(logger: DataLogger):
    """
    Check specific OCL rules
    :param logger: Logger instance
    :return: true is ok false otherwise
    """
    return True


# region LoadResponseCharacteristic(IdentifiedObject)
def check_load_response_characteristic(load_response_characteristic: LoadResponseCharacteristic, logger: DataLogger):
    """
    Check OCL rules
    :param load_response_characteristic:
    :param logger:
    :return:
    """
    err_counter = 0
    if load_response_characteristic.exponentModel:
        if load_response_characteristic.pVoltageExponent not in load_response_characteristic.parsed_properties.keys():
            err_counter += 1
            logger.add_error(msg="OCL rule violation: pVoltageExponent not specified",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="Existence of pVoltageExponent")

        if load_response_characteristic.qVoltageExponent not in load_response_characteristic.parsed_properties.keys():
            err_counter += 1
            logger.add_error(msg="OCL rule violation: qVoltageExponent not specified",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="Existence of qVoltageExponent")
    else:
        if load_response_characteristic.pConstantCurrent not in load_response_characteristic.parsed_properties.keys():
            err_counter += 1
            logger.add_error(msg="OCL rule violation: pConstantCurrent not specified",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="Existence of pConstantCurrent")

        if load_response_characteristic.pConstantPower not in load_response_characteristic.parsed_properties.keys():
            err_counter += 1
            logger.add_error(msg="OCL rule violation: pConstantPower not specified",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="Existence of pConstantPower")

        if load_response_characteristic.pConstantImpedance not in load_response_characteristic.parsed_properties.keys():
            err_counter += 1
            logger.add_error(msg="OCL rule violation: pConstantImpedance not specified",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="Existence of pConstantImpedance")

        if load_response_characteristic.qConstantCurrent not in load_response_characteristic.parsed_properties.keys():
            err_counter += 1
            logger.add_error(msg="OCL rule violation: qConstantCurrent not specified",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="Existence of qConstantCurrent")

        if load_response_characteristic.qConstantPower not in load_response_characteristic.parsed_properties.keys():
            err_counter += 1
            logger.add_error(msg="OCL rule violation: qConstantPower not specified",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="Existence of qConstantPower")

        if load_response_characteristic.qConstantImpedance not in load_response_characteristic.parsed_properties.keys():
            err_counter += 1
            logger.add_error(msg="OCL rule violation: qConstantImpedance not specified",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="Existence of qConstantImpedance")

        p_factor = load_response_characteristic.pConstantImpedance + load_response_characteristic.pConstantCurrent + load_response_characteristic.pConstantPower
        q_factor = load_response_characteristic.qConstantImpedance + load_response_characteristic.qConstantCurrent + load_response_characteristic.qConstantPower
        if not np.isclose(p_factor, 1):
            err_counter += 1
            logger.add_error(msg="pConstantImpedance + pConstantCurrent + pConstantPower different from 1",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="1.0")

        if not np.isclose(q_factor, 1):
            err_counter += 1
            logger.add_error(msg="qConstantImpedance + qConstantCurrent + qConstantPower different from 1",
                             device=load_response_characteristic.rdfid,
                             device_class="LoadResponseCharacteristic",
                             expected_value="1.0")

    return err_counter == 0


# endregion

# region BaseVoltage(IdentifiedObject)
def base_voltage_to_str(base_voltage: BaseVoltage):
    return base_voltage.tpe + ':' + base_voltage.rdfid + ':' + str(base_voltage.nominalVoltage) + ' kV'


# endregion

def get_regulating_control(cgmes_elm: RegulatingCondEq,
                           cgmes_enums,
                           logger: DataLogger):

    if cgmes_elm.RegulatingControl is not None:

        if cgmes_elm.RegulatingControl.enabled:
            if cgmes_elm.controlEnabled:
                is_controlled = True
            else:
                is_controlled = False
        else:
            is_controlled = False

        if cgmes_elm.RegulatingControl.mode == cgmes_enums.RegulatingControlModeKind.voltage:

            v_control_value = cgmes_elm.RegulatingControl.targetValue  # kV

            # cgmes_elm.EquipmentContainer.BaseVoltage.nominalVoltage
            controlled_terminal = cgmes_elm.RegulatingControl.Terminal
            base_voltage = controlled_terminal.TopologicalNode.BaseVoltage.nominalVoltage
            v_set = v_control_value / base_voltage

            # if cgmes_elm.EquipmentContainer.tpe == 'VoltageLevel':
            #
            #     # is_controlled = True
            #
            #     # find the control node
            #     # control_terminal = cgmes_elm.RegulatingControl.Terminal
            #     # control_node, cn = find_terms_connections(cgmes_terminal=control_terminal,
            #     #                                           calc_node_dict=calc_node_dict,
            #     #                                           cn_dict=cn_dict)
            #
            # else:
            #     control_node = None
            #     v_set = 1.0
            #     is_controlled = False
            #     logger.add_warning(msg='RegulatingCondEq has no voltage control',
            #                        device=cgmes_elm.rdfid,
            #                        device_class=cgmes_elm.tpe,
            #                        device_property="EquipmentContainer",
            #                        value='None',
            #                        expected_value='BaseVoltage')

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

    return v_set, is_controlled
