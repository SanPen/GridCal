# utf8
"""
This module contains the core functionality of the CIM to Matpower import tool.

.. note::This module is based partially on the started but never finished open source project Cim2BusBranch https://www.versioneye.com/Python/Cim2BusBranch/0.1

.. seealso::  :py:mod:`Topology_NodeBreaker` and :py:mod:`CIM2Matpower`

:Date: 2016-05-10
:Authors: Konstantin Gerasimov
:e-mail: kkgerasimov@gmail.com
:Credits: This function is created for KU-Leuven as part of the GARPUR project http://www.garpur-project.eu
"""


import math
from datetime import datetime
from itertools import count
from sys import stdout

from PyCIM import RDFXMLReader

import Topology_NodeBreaker
import Topology_BusBranch
from PreProcess_CIM_files import fix_RTE_cim_files
from PostProcess_mpc import create_mpc


import logging
logger = logging.getLogger(__name__)


def cim_to_mpc(cimfiles, boundary_profiles=[], log_filename=''):
    """
    The main function transforming the CIM XML files into Matpower case structure (mpc) in BusBranch topology,
    together with an additional structure for the NodeBreaker topology data which cannot be fit in the mpc.

    .. warning:: The *cimfiles* and *boundary_profiles* must not contain Unidoce characters! Otherwise the `PyCIM` module fails!
    :param cimfiles: the filenames of the CIM files to be imported (preferably with full path)
    :type cimfiles: list of strings
    .. warning:: The *cimfiles* usually come in three files: _EQ, _TP and _SV. If so,
                 they need to be provided in the specified order!
    :param boundary_profiles: (optional) the filenames of the boundary files to be imported (preferably with full path)
    :type boundary_profiles: list of strings
    .. warning:: The *boundary_profiles* usually come in two files: _EQ and _TP. If so, they need to be provided in the specified order!
    :param log_filename: (optional) the filename in which a log should be saved (preferably with full path)
    :type log_filename: string
    :return mpc: Matpower case, together with information about the NodeBreaker topology
    :type mpc: dictionary
    .. warning:: In order to be used in Matlab, it still needs to be transformed from Python dictionaries and array to Matlab structure and matrices.

    .. seealso::  :py:mod:`Topology_NodeBreaker`
    """

    # Initialize logging
    logging.getLogger('').setLevel(logging.INFO)
    if type(log_filename) == str and log_filename != '':
        file_logger_handler = logging.FileHandler(filename=log_filename, mode='w')
        # file_logger_handler.setLevel(logging.DEBUG)
        file_logger_formatter = logging.Formatter('%(levelname)s : %(name)s : %(message)s')
        file_logger_handler.setFormatter(file_logger_formatter)
        logging.getLogger('').addHandler(file_logger_handler)  # attaches the file_handler to the root logger
    else:
        file_logger_handler = None
        pass
    console_logger_handler = logging.StreamHandler(stdout)
    # console_logger_handler.setLevel(logging.DEBUG)
    stdout_logger_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_logger_handler.setFormatter(stdout_logger_formatter)
    logging.getLogger('').addHandler(console_logger_handler)  # attaches the file_handler to the root logger
    logger.info('CIM to Matpower import STARTED at %s \n' % str(datetime.now()))

    # Check the RTE CIM files for compliance with PyCIM package class definitions
    fix_RTE_cim_files(cimfiles)

    try:
        # NB: The ENTSO-E boundary files have to be listed first (before the CIM of the actual network)
        # in order to be imported correctly !!!
        # NB: The CIM files have to be loaded in the following order: EQ, TP and then SV,
        # in order for the RDFXMLReader to work correctly !!!
        importer = CIM2Matpower(boundary_profiles + cimfiles)
        bus_branch_model, node_breaker_topology = importer.import_cim()
        mpc = create_mpc(bus_branch_model, node_breaker_topology)
    except:
        logger.error('Some error occured during the CIM import.\n'
                     'Are you sure you are importing CIMv14 ENTSO-E profile '
                     'and that you are providing all the CIM files (_EQ, _TP, _SV) '
                     'and boundary files (_EQ, _TP). All the files must end with the '
                     'corresponding suffix and must not contain Unicode characters! \n')
        logging.getLogger('').removeHandler(console_logger_handler)
        if file_logger_handler is not None:
            logging.getLogger('').removeHandler(file_logger_handler)
        logging.shutdown()
        raise

    logger.info('CIM to Matpower import ENDED at {0}} \n'.format(str(datetime.now())))

    # close the logging files after the function is finished
    logging.getLogger('').removeHandler(console_logger_handler)
    if file_logger_handler is not None:
        logging.getLogger('').removeHandler(file_logger_handler)
    logging.shutdown()

    return mpc


class CIM2Matpower(object):
    """
    The *CIM2Matpower* transforms a CIM topology in *cim_file* into a
    bus/branch topology.

    *cim_file* is the path to an XML/RDF encoded CIM topology.

    """
    # Create a topological node (bus) for each one-terminal primary equipment
    _primary_one_t = [
        'TransformerWinding',
        'EnergySource',
        'EnergyConsumer',
        'Connector',  # BusbarSection, Junction
        'RegulatingCondEq'  # ShuntCompensator, StaticVarCompensator, FrequencyConverter, SynchronousMachine
    ]

    # Create a branch for each two-terminal primary equipment
    _primary_two_t = [
        'Conductor',  # DC-/ACLineSegment
        'SeriesCompensator',
        'PowerTransformer'
    ]

    # One-terminal secondary equipment can safely be ignored
    _secondary_one_t = [
        'Ground',
    ]

    # Search two-terminal for neighboring connectivity nodes for amalgamation
    _secondary_two_t = [
        'RectifierInverter',
        'Switch',  # Jumper, Fuse, Disconnector, GroundDisconnector, Breaker, LoadBreakSwitch
    ]

    ####################################################################################################################
    def __init__(self, cim_files):
        if type(cim_files) == str:
            cim_files = [cim_files]
        self.cim_files = cim_files

        xmlns = RDFXMLReader.xmlns(cim_files[0])
        self._package_map = RDFXMLReader.get_cim_ns(xmlns)[1]

        self._prim_onet = self._get_equipment_cls(CIM2Matpower._primary_one_t)
        self._prim_twot = self._get_equipment_cls(CIM2Matpower._primary_two_t)
        self._sec_onet = self._get_equipment_cls(CIM2Matpower._secondary_one_t)
        self._sec_twot = self._get_equipment_cls(CIM2Matpower._secondary_two_t)

        # reinitilize the automatically created ids
        Topology_BusBranch.Bus.id_generator = count(1)
        Topology_NodeBreaker.Node.id_generator = count(1)
        Topology_NodeBreaker.Area.id_generator = count(1)
        Topology_NodeBreaker.Zone.id_generator = count(1)
        Topology_NodeBreaker.Branch.id_generator = count(1)
        Topology_NodeBreaker.Generator.id_generator = count(1)

    ####################################################################################################################
    def import_cim(self):
        """
        Actually parses the CIM file and transforms its contents.
        A :class:`Topology_BusBranch.Case` object is returned.

        """
        cim_objects = {}

        for cim_file in self.cim_files:
            cim_objects = RDFXMLReader.cimread(cim_file, start_dict=cim_objects)

        base_power, tnodes = self._iterate_prim_eq(cim_objects)
        return self._create_bb_topology(base_power, tnodes), self.node_breaker_data

    ####################################################################################################################
    def _create_bb_topology(self, BasePower_MVA, tnodes):
        """
        Creates the :class:`Topology_BusBranch.Case`
        """
        buses, generators, p_transformers, ac_lines = self._create_buses_and_gens(tnodes)
        branches = self._create_branches(ac_lines, p_transformers, BasePower_MVA, buses)

        # replace tnode dict by list of buses
        for i, gen in enumerate(generators):
            generators[i].bus = buses[gen.bus]

        for i, branch in enumerate(branches):
            branches[i].from_bus = buses[branch.from_bus]
            branches[i].to_bus = buses[branch.to_bus]

        buses = list(set(buses.values()))

        return Topology_BusBranch.Case(BasePower_MVA, buses, generators, branches)

    ####################################################################################################################
    def _find_tnode(self, terminal):
        """

        :param terminal:
        :return:
        """
        try:
            tnode = terminal.ConnectivityNode.TopologicalNode
        except AttributeError:  # if no ConnectivityNode, try the TopologicalNode directly
            tnode = terminal.TopologicalNode
        return tnode

    ####################################################################################################################
    def _get_acline_mva_lim(self, acline):
        """

        :param acline:
        :return:
        """
        limit_class = 'CurrentLimit'
        limits_mva = [0, 0, 0]
        num_matpower_limits = 3

        try:
            limits_from_mva = []
            for lim in acline.Terminals[0].OperationalLimitSet[0].OperationalLimitValue:
                if lim.__class__.__name__ == limit_class:
                    limits_from_mva.append(lim.value * acline.Terminals[0].TopologicalNode.SvVoltage.v * math.sqrt(3) / 1e3)
            if limits_from_mva:
                limits_from_mva.sort()
                if len(limits_from_mva) < num_matpower_limits:
                    limits_from_mva.extend([0] * (num_matpower_limits - len(limits_from_mva)))
            if not limits_from_mva:
                limits_from_mva = [0, 0, 0]
        except:
            limits_from_mva = [0, 0, 0]

        try:
            limits_to_mva = []
            for lim in acline.Terminals[1].OperationalLimitSet[0].OperationalLimitValue:
                if lim.__class__.__name__ == limit_class:
                    limits_to_mva.append(lim.value * acline.Terminals[1].TopologicalNode.SvVoltage.v * math.sqrt(3) / 1e3)
            if limits_to_mva:
                limits_to_mva.sort()
                if len(limits_to_mva) < num_matpower_limits:
                    limits_to_mva.extend([0] * (num_matpower_limits - len(limits_to_mva)))
            if not limits_to_mva:
                limits_to_mva = [0, 0, 0]
        except:
            limits_to_mva = [0, 0, 0]

        for i in range(num_matpower_limits):
            if limits_from_mva[i] < limits_to_mva[i]:
                limits_mva[i] = limits_from_mva[i]
            else:
                limits_mva[i] = limits_to_mva[i]

        return limits_mva

    ####################################################################################################################
    def _create_branches(self, lines, p_transformers, BasePower_MVA, buses):
        """
        Creates list of :class:`Topology_BusBranch.Branch` -es

        Create list of :class:`Topology_NodeBreaker.Branch`, :class:`Topology_NodeBreaker.PhaseTapChanger`
                   and :class:`Topology_NodeBreaker.RatioTapChanger` -s

        """
        logger.info('START creating branches')

        branches = []
        for line in lines:
            status_connected = True
            for term in line.Terminals:
                if not term.connected:
                    status_connected = False

            from_bus = self._find_tnode(line.Terminals[0])
            to_bus = self._find_tnode(line.Terminals[1])

            if not from_bus:
                logging_message = 'Line %s: terminal _T0 is None and because of that the line is not imported!' % line.UUID
                logger.warn(logging_message)
            if from_bus not in buses:
                tisland_name = line.Terminals[0].TopologicalNode.TopologicalIsland.UUID
                if status_connected:
                    # ToDo: Maybe this should raise an error!
                    logging_message = 'Line %s (switched ON): the line is switched ON but terminal _T1 ' \
                                      'belongs to another island (%s) and because of that the ' \
                                      'line is not imported!' % (line.UUID, tisland_name)
                    logger.error(logging_message)
                else:
                    logger.warn('Line %s (switched off): terminal %s is connected to another island (%s) '
                                'and because of that the line is not imported!' % (line.UUID, line.Terminals[0].UUID,
                                                                                   tisland_name))
                continue

            if not to_bus:
                logging_message = 'Line %s: terminal _T1 is None and because of that the ' \
                                  'line is not imported!' % line.UUID
                logger.warn(logging_message)
            if to_bus not in buses:
                tisland_name = line.Terminals[1].TopologicalNode.TopologicalIsland.UUID
                if status_connected:
                    # ToDo: Maybe this should be an error!
                    logging_message = 'Line %s (switched ON): the line is switched ON but ' \
                                      'terminal _T1 belongs to another island (%s) and because of ' \
                                      'that the line is not imported!' %(line.UUID, tisland_name)
                    logger.error(logging_message)
                else:
                    logging_message = 'Line %s (switched off): terminal %s is connected to ' \
                                      'another island (%s) and because of that the line is ' \
                                      'not imported!' % (line.UUID, line.Terminals[1].UUID, tisland_name)
                    logger.warn(logging_message)
                continue

            if buses[from_bus].base_kv == buses[to_bus].base_kv:
                BaseVoltage_kV = buses[from_bus].base_kv
            else:
                logging_message = 'Line %s: base voltages different at the line terminals!' % line.UUID
                logger.critical(logging_message)
                raise ValueError(logging_message)

            # Ref. values for p.u. conversion
            z_base = BaseVoltage_kV ** 2 / BasePower_MVA  # Ohm
            y_base = 1.0 / z_base  # Ohm^-1

            limits_mva = self._get_acline_mva_lim(line)

            branches.append(Topology_BusBranch.Branch(
                                                        from_bus, to_bus,
                                                        name=line.UUID,
                                                        r=(line.r / z_base),
                                                        x=(line.x / z_base),
                                                        b=(line.bch / y_base),
                                                        rate_a=limits_mva[0],
                                                        rate_b=limits_mva[1],
                                                        rate_c=limits_mva[2],
                                                        online=status_connected
                                                    ))
            self.node_breaker_data.branches.append(
                Topology_NodeBreaker.Branch(node_from_id=self.cim_nodes[from_bus].id,
                                            node_to_id=self.cim_nodes[to_bus].id,
                                            id_cim=line.UUID,
                                            name=line.name,
                                            status_from=line.Terminals[0].connected,
                                            status_to=line.Terminals[1].connected))

        for pt in p_transformers:
            status_connected = True
            if hasattr(pt, 'TransformerWindings'):
                for tw in pt.TransformerWindings:
                    if not tw.Terminals[0].connected:
                        status_connected = False
                # CIMv14
                if len(pt.TransformerWindings) == 2:
                    # two-winding transformer
                    if pt.TransformerWindings[0].windingType == 'primary':
                        index_primary = 0
                        index_secondary = 1
                    else:
                        index_primary = 1
                        index_secondary = 0

                    to_bus_primary = self._find_tnode(pt.TransformerWindings[index_primary].Terminals[0])

                    if not to_bus_primary:
                        logging_message = 'Transformer %s: the TNode of terminal of primary winding ' \
                                          'is None and because of that the transformer is not imported!' % pt.UUID
                        logger.warn(logging_message)
                    if to_bus_primary not in buses:
                        tisland_name = pt.TransformerWindings[index_primary].Terminals[
                            0].TopologicalNode.TopologicalIsland.UUID
                        if status_connected:
                            logging_message = 'Transformer %s (switched ON): the transformer is switched ' \
                                              'ON but terminal %s belongs to another island (%s) and because ' \
                                              'of that the line is not imported!' % (pt.UUID,
                                                                                     pt.TransformerWindings[index_primary].Terminals[0].UUID, tisland_name)
                            logger.error(logging_message)
                            # NOTE: Maybe we should raise an error for this case
                        else:
                            logging_message = 'Transformer %s (switched off): terminal %s ' \
                                              'is connected to another island (%s) and because ' \
                                              'of that the transformer is not imported!' % (pt.UUID, pt.TransformerWindings[index_primary].Terminals[0].UUID, tisland_name)
                            logger.warn(logging_message)
                        continue

                    from_bus_secondary = self._find_tnode(pt.TransformerWindings[index_secondary].Terminals[0])
                    if not from_bus_secondary:
                        logging_message = 'Transformer %s: the TNode of terminal of secondary ' \
                                          'winding is None and because of that the transformer is ' \
                                          'not imported!' % pt.UUID
                        logger.warn(logging_message)
                    if from_bus_secondary not in buses:
                        tisland_name = pt.TransformerWindings[index_secondary].Terminals[
                            0].TopologicalNode.TopologicalIsland.UUID
                        if status_connected:
                            logging_message = 'Transformer %s (switched ON): the transformer is ' \
                                              'switched ON but terminal %s belongs to another island ' \
                                              '(%s) and because of that the line is not imported!' %(pt.UUID,pt.TransformerWindings[index_secondary].Terminals[0].UUID, tisland_name)
                            logger.error(logging_message)
                            # NOTE: Maybe we should raise an error for this case
                        else:
                            logging_message = 'Transformer %s (switched off): terminal %s is ' \
                                              'connected to another island (%s) and because of ' \
                                              'that the transformer is not imported!' % (pt.UUID, pt.TransformerWindings[index_secondary].Terminals[0].UUID, tisland_name)
                            logger.warn(logging_message)
                        continue

                    pt_ratio = (pt.TransformerWindings[index_secondary].ratedU / buses[from_bus_secondary].base_kv) / (
                        pt.TransformerWindings[index_primary].ratedU / buses[to_bus_primary].base_kv)

                    z_base_primary = buses[to_bus_primary].base_kv ** 2 / BasePower_MVA  # Ohm
                    z_base_secondary = buses[from_bus_secondary].base_kv ** 2 / BasePower_MVA  # Ohm
                    if pt.TransformerWindings[index_secondary].r or pt.TransformerWindings[index_secondary].x or \
                            pt.TransformerWindings[index_secondary].b:
                        logging_message = 'The two-windings transformer %s has impedance ' \
                                          'and/or admittance on its secondary winding!' % pt.UUID
                        logger.warn(logging_message)

                    pt_r_pu = pt.TransformerWindings[index_primary].r / z_base_primary
                    pt_x_pu = pt.TransformerWindings[index_primary].x / z_base_primary
                    pt_b_pu = -pt.TransformerWindings[
                        index_primary].b * z_base_primary  # KKG: ToDo: Shouldn't b be with minus?

                    # PHASE tap changers
                    ptc_ratio = 1
                    ptc_angle_deg = 0
                    ptc_x_pu = 0
                    ptc = pt.TransformerWindings[index_primary].PhaseTapChanger or pt.TransformerWindings[
                        index_secondary].PhaseTapChanger
                    if pt.TransformerWindings[index_primary].PhaseTapChanger and pt.TransformerWindings[
                        index_secondary].PhaseTapChanger:
                        logging_message = 'The two-windings transformer %s has PhaseTapChanger ' \
                                          'on its primary winding!' % pt.UUID
                        logger.warn(logging_message)
                    if ptc:
                        # The implementation of the PhaseTapChanger is based on the CIM1Impowerter.txt from the iTesla project
                        neutral_step = ptc.neutralStep
                        current_step = ptc.SvTapStep.continuousPosition
                        du0 = ptc.neutralU / ptc.TransformerWinding.ratedU
                        if math.fabs(du0) > 0.5:
                            du0 = 0
                        if ptc.voltageStepIncrementOutOfPhase and ptc.voltageStepIncrementOutOfPhase != 0:
                            # the original Java code is:
                            # du = (config.isInvertVoltageStepIncrementOutOfPhase() ? -1 : 1) * ptc.getVoltageStepIncrementOutOfPhase() / ptc.getTransformerWinding().getRatedU();
                            du = -1 * ptc.voltageStepIncrementOutOfPhase / ptc.TransformerWinding.ratedU
                        elif ptc.stepVoltageIncrement and ptc.stepVoltageIncrement != 0:
                            du = ptc.stepVoltageIncrement / 100
                        else:
                            logging_message = 'PhaseTapChanger %s of power transformer %s does not ' \
                                              'have a valid value for voltageStepIncrementOutOfPhase or ' \
                                              'stepVoltageIncrement attribute, so by default ' \
                                              'it is set to 1!' % (ptc.UUID, pt.UUID)
                            logger.warn(logging_message)
                            du = 1 / 100

                        if ptc.windingConnectionAngle:
                            theta_rad = math.radians(ptc.windingConnectionAngle)
                        else:
                            logging_message = 'PhaseTapChanger %s of power transformer %s ' \
                                              'does not have windingConnectionAngle attribute, ' \
                                              'so by default it is set to 1!' % (ptc.UUID, pt.UUID)
                            logger.warn(logging_message)
                            theta_rad = math.pi / 2

                        if ptc.xStepMin < 0 or ptc.xStepMax <= 0 or ptc.xStepMin > ptc.xStepMax:
                            xStepRangeIsInconsistent = True
                            logging_message = 'xStepMin and xStepMax of PhaseTapChanger %s of ' \
                                              'PowerTransformer %s are inconsistents!' % (ptc.UUID, pt.UUID)
                            logger.warn(logging_message)
                        else:
                            xStepRangeIsInconsistent = False

                        step_num_list = []
                        x_pu_list = []
                        angle_shift_deg_list = []
                        voltage_ratio_list = []

                        if ptc.phaseTapChangerType == 'symmetrical':
                            if ptc.stepPhaseShiftIncrement and ptc.stepPhaseShiftIncrement != 0:
                                for step in range(ptc.lowStep, ptc.highStep+1):
                                    step_num_list.append(step)
                                    n = step - neutral_step
                                    voltage_ratio_list.append(1)
                                    angle_shift_rad=-1 * n * math.radians(ptc.stepPhaseShiftIncrement)
                                    angle_shift_deg_list.append(math.degrees(angle_shift_rad))
                                    # the original Java code is:
                                    # float alpha = n * (float) Math.toRadians((config.isInvertVoltageStepIncrementOutOfPhase() ? -1 : 1) * ptc.stepPhaseShiftIncrement);
                            else:
                                for step in range(ptc.lowStep, ptc.highStep+1):
                                    step_num_list.append(step)
                                    n = step - neutral_step
                                    voltage_ratio_list.append(1)
                                    dy = (n * du / 2 - du0) * math.sin(theta_rad)
                                    angle_shift_rad=2 * math.asin(dy)
                                    angle_shift_deg_list.append(math.degrees(angle_shift_rad))
                        elif ptc.phaseTapChangerType == 'asymmetrical':
                            for step in range(ptc.lowStep, ptc.highStep+1):
                                step_num_list.append(step)
                                n = step - neutral_step
                                dx = (n * du - du0) * math.cos(theta_rad)
                                dy = (n * du - du0) * math.sin(theta_rad)
                                angle_shift_rad = math.atan2(dy, 1 + dx)
                                angle_shift_deg_list.append(math.degrees(angle_shift_rad))
                                voltage_ratio_list.append(1 / math.hypot(dy, 1 + dx))
                        else:
                            logger.critical('Unknown phaseTapChangerType!')
                            raise Exception('Unknown phaseTapChangerType!' + str(ptc.phaseTapChangerType))

                        angle_max_rad = math.radians(max(angle_shift_deg_list))
                        for angle_deg in angle_shift_deg_list:
                            angle_rad = math.radians(angle_deg)
                            if xStepRangeIsInconsistent or angle_max_rad == 0:
                                x_ohms = pt.TransformerWindings[index_primary].x
                            else:
                                if ptc.phaseTapChangerType == 'symmetrical':
                                    x_ohms = ptc.xStepMin + (ptc.xStepMax - ptc.xStepMin) * math.pow(math.sin(angle_rad / 2) / math.sin(angle_max_rad / 2), 2)
                                elif ptc.phaseTapChangerType == 'asymmetrical':
                                    numer = math.sin(theta_rad) - math.tan(angle_max_rad) * math.cos(theta_rad)
                                    denom = math.sin(theta_rad) - math.tan(angle_rad) * math.cos(theta_rad)
                                    x_ohms = ptc.xStepMin + (ptc.xStepMax - ptc.xStepMin) * math.pow(math.tan(angle_rad) / math.tan(angle_max_rad) * numer / denom, 2)
                            x_pu_list.append(x_ohms / z_base_secondary)

                        current_step_index = step_num_list.index(current_step)
                        ptc_x_pu = x_pu_list[current_step_index]
                        ptc_ratio = voltage_ratio_list[current_step_index]
                        ptc_angle_deg = angle_shift_deg_list[current_step_index]

                    # Ratio tap changer
                    rtc = None
                    rtc_ratio = 1
                    if pt.TransformerWindings[index_secondary].RatioTapChanger:
                        rtc = pt.TransformerWindings[index_secondary].RatioTapChanger
                        if rtc:
                            rtc_ratio = 1 + (rtc.SvTapStep.continuousPosition - rtc.neutralStep) * (
                                rtc.stepVoltageIncrement / 100)
                    if pt.TransformerWindings[index_primary].RatioTapChanger:
                        if pt.TransformerWindings[index_secondary].RatioTapChanger:
                            logging_message = 'The two-windings transformer %s has ' \
                                              'RatioTapChnager on both windings!' % pt.UUID
                            logger.warn(logging_message)
                        else:
                            rtc = pt.TransformerWindings[index_secondary].RatioTapChanger
                            if rtc:
                                rtc_ratio = 1 / (1 + (rtc.SvTapStep.continuousPosition - rtc.neutralStep) * (rtc.stepVoltageIncrement / 100))

                    # Limits
                    rate_a_mva = pt.TransformerWindings[index_primary].ratedS
                    rate_b_mva = pt.TransformerWindings[index_primary].shortTermS
                    rate_c_mva = pt.TransformerWindings[index_primary].emergencyS
                    if pt.TransformerWindings[index_primary].Terminals[0].OperationalLimitSet:
                        limits_list = []
                        for lim in pt.TransformerWindings[index_primary].Terminals[0].OperationalLimitSet[
                                0].OperationalLimitValue:
                            if lim.__class__.__name__ == 'CurrentLimit':
                                limits_list.append(lim)
                        # limits_list = pt.TransformerWindings[index_primary].Terminals[0].OperationalLimitSet[
                        #     0].OperationalLimitValue
                        limits_tnode = self._find_tnode(pt.TransformerWindings[index_primary].Terminals[0])
                    elif pt.TransformerWindings[index_secondary].Terminals[0].OperationalLimitSet:
                        limits_list = []
                        for lim in pt.TransformerWindings[index_secondary].Terminals[0].OperationalLimitSet[
                                0].OperationalLimitValue:
                            if lim.__class__.__name__ == 'CurrentLimit':
                                limits_list.append(lim)
                        # limits_list = pt.TransformerWindings[index_secondary].Terminals[0].OperationalLimitSet[
                        #     0].OperationalLimitValue
                        limits_tnode = self._find_tnode(pt.TransformerWindings[index_secondary].Terminals[0])
                    else:
                        limits_list = None
                    if limits_list:
                        if len(limits_list) > 0:
                            rate_a_mva = limits_list[0].value * limits_tnode.SvVoltage.v * math.sqrt(3) / 1e3  # buses[to_bus_primary].base_kv * math.sqrt(3) / 1e3
                        if len(limits_list) > 1:
                            rate_b_mva = limits_list[1].value * limits_tnode.SvVoltage.v * math.sqrt(3) / 1e3
                        if len(limits_list) > 2:
                            rate_c_mva = limits_list[2].value * limits_tnode.SvVoltage.v * math.sqrt(3) / 1e3

                elif len(pt.TransformerWindings) == 3:
                    logging_message = 'Three-winding transformer (%s) is NOT implemented yet!' % pt.UUID
                    logger.critical(logging_message)
                    raise NameError(logging_message)
                else:
                    logging_message = 'Transformer (%s) has wrong number (%d) of windings' %(pt.UUID, len(pt.TransformerWindings))
                    logger.critical(logging_message)
                    raise NameError(logging_message)
            else:
                logging_message = 'Transformer  %s  in CIM v15 and above is NOT implemented yet!' % pt.UUID
                logger.critical(logging_message)
                raise NameError(logging_message)

            if ptc_x_pu != 0:
                # This represents RTE CIM export logic for transformers!!!!
                # They always export the PhaseTapChanger as a separate transformer!!! However the CIMv14 standard suggests a more general situatuion is possible.
                pt_x_pu = ptc_x_pu

            branches.append(Topology_BusBranch.Branch(
                from_bus_secondary, to_bus_primary,
                name=pt.UUID,
                r=pt_r_pu,  #*((rtc_ratio/pt_ratio)**2), # ToDo: correct the resistence accounting for the non-nominal tap setting - it makes a small change but is part of the ENTSO-E PhaseShifter modelling guideline for CIMv16
                x=pt_x_pu,  #*((rtc_ratio/pt_ratio)**2),  # + ptc_x_pu,  # ToDo: correct the transformer winding reactance accounting for the non-nominal tap setting - it makes a small change but is part of the ENTSO-E PhaseShifter modelling guideline for CIMv16. However this is not the case for the RTE CIM export logic (because they treat the PhaseShifter as a separate transformer always).
                b=pt_b_pu,
                ratio=pt_ratio * rtc_ratio * ptc_ratio, # NB: This should be the correct way to calculate the exact ratio. However, in theory, the different export tools might have impleneted in a different way...
                angle=ptc_angle_deg,
                rate_a=rate_a_mva,
                rate_b=rate_b_mva,
                rate_c=rate_c_mva,
                online=status_connected,
            ))
            self.node_breaker_data.branches.append(
                Topology_NodeBreaker.Branch(node_from_id=self.cim_nodes[from_bus_secondary].id,
                                            node_to_id=self.cim_nodes[to_bus_primary].id,
                                            id_cim=pt.UUID,
                                            name=pt.name,
                                            status_from=pt.TransformerWindings[index_secondary].Terminals[0].connected,
                                            status_to=pt.TransformerWindings[index_primary].Terminals[0].connected))
            if ptc:  # PhaseTapChanger
                self.node_breaker_data.phasetapchangers.append(
                    Topology_NodeBreaker.PhaseTapChanger(branch_id=self.node_breaker_data.branches[-1].id,
                                                         id_cim=ptc.UUID,
                                                         step_num_list=step_num_list,
                                                         x_pu_list=x_pu_list,
                                                         angle_shift_deg_list=angle_shift_deg_list,
                                                         continuous_position=ptc.SvTapStep.continuousPosition))
            if rtc:  # RatioTapChanger
                if rtc.RegulatingControl:
                    self.node_breaker_data.ratiotapchangers.append(
                        Topology_NodeBreaker.RatioTapChanger(branch_id=self.node_breaker_data.branches[-1].id,
                                                             id_cim=rtc.UUID,
                                                             lowStep=rtc.lowStep,
                                                             highStep=rtc.highStep,
                                                             neutralU_kV=rtc.neutralU,
                                                             stepVoltageIncrement_kV=rtc.stepVoltageIncrement,
                                                             continuousPosition=rtc.SvTapStep.continuousPosition,
                                                             hasRegulatingControl=True,
                                                             RC_discrete=rtc.RegulatingControl.discrete,
                                                             RC_mode=rtc.RegulatingControl.mode,
                                                             RC_targetRange_kV=rtc.RegulatingControl.targetRange,
                                                             RC_targetValue_kV=rtc.RegulatingControl.targetValue))
                else:
                    self.node_breaker_data.ratiotapchangers.append(
                        Topology_NodeBreaker.RatioTapChanger(branch_id=self.node_breaker_data.branches[-1].id,
                                                             id_cim=rtc.UUID,
                                                             lowStep=rtc.lowStep,
                                                             highStep=rtc.highStep,
                                                             neutralU_kV=rtc.neutralU,
                                                             stepVoltageIncrement_kV=rtc.stepVoltageIncrement,
                                                             continuousPosition=rtc.SvTapStep.continuousPosition,
                                                             hasRegulatingControl=False))
        logging_message = 'Created totally %d branches' % len(branches)
        logger.info(logging_message)
        logger.info('END creating branches\n')
        return branches

    ####################################################################################################################
    def _create_buses_and_gens(self, tnodes):
        """
        Creates dictionary of :class:`Topology_BusBranch.Bus` -es and list of :class:`Topology_BusBranch.Generator` -s

        Create lists of ``PowerTransformer`` -s and ``ACLineSegment`` -s CIM objects

        Create lists of :class:`Topology_NodeBreaker.Node`, :class:`Topology_NodeBreaker.Substation`, :class:`Topology_NodeBreaker.Generator`, :class:`Topology_NodeBreaker.Load` and :class:`Topology_NodeBreaker.Shunt` -s

        """
        logger.info('START creating buses')
        buses = {}
        self.cim_nodes = {}  # To be used to find the node id in the self.node_breaker_data additional data structure
        cim_substations = {}
        generators = []
        power_transformers = set()
        ac_lines = set()

        # First create dictionary for the buses
        for voltage_level, tnodes_set in self.voltage_levels.items():  # for each VoltageLevel
            for tnode in tnodes_set:
                self.cim_nodes[tnode] = Topology_NodeBreaker.Node(id_cim=tnode.UUID,
                                                                  name=tnode.name,
                                                                  desc=tnode.description)
            if voltage_level.Substation in cim_substations:
                cim_substations[voltage_level.Substation].node_id_list.extend([self.cim_nodes[key].id for key in tnodes_set])
            else:
                cim_substations[voltage_level.Substation] = Topology_NodeBreaker.Substation(id_cim=voltage_level.Substation.UUID,
                                                                           name=voltage_level.Substation.name,
                                                                           node_id_list=[self.cim_nodes[key].id for key in tnodes_set])

        for voltage_level, tnodes_set in self.voltage_levels.items():  # for each VoltageLevel
            # import switches
            tnodes_bus_sets_list = []  # list of sets of tnodes at the same bus
            for equip in voltage_level.Equipments:
                if isinstance(equip, self._get_cls('Switch')):
                    term_from = equip.Terminals[0]
                    term_to = equip.Terminals[1]
                    tnode_from = self._find_tnode(term_from)
                    tnode_to = self._find_tnode(term_to)

                    add_switch_flag = True
                    if bool(tnode_from.TopologicalIsland is not self.biggest_tnode_island) ^ bool(tnode_to.TopologicalIsland is not self.biggest_tnode_island):
                        add_switch_flag = False
                        logging_message = 'Switch "%s" is switched ON and is connected between two ' \
                                          'different TopologicalIslands (%s and %s) and thus will not ' \
                                          'be imported !!!' % (equip.UUID,
                                                               tnode_from.TopologicalIsland.UUID,
                                                               tnode_to.TopologicalIsland.UUID)
                        logger.error(logging_message)
                        # raise AssertionError(logging_message)
                    elif tnode_from.TopologicalIsland is not self.biggest_tnode_island and tnode_to.TopologicalIsland is not self.biggest_tnode_island:
                        add_switch_flag = False

                    if term_from.connected and term_to.connected:
                        switch_status = True
                        if (tnode_from.SvVoltage.v, tnode_from.SvVoltage.angle) != (tnode_to.SvVoltage.v, tnode_to.SvVoltage.angle):
                            add_switch_flag = False
                            logging_message = 'Switch "%s" is switched ON but has different voltage at its terminals!!!'
                            logger.critical(logging_message)
                            raise AssertionError(logging_message)
                    else:
                        switch_status = False

                    if add_switch_flag:
                        self.node_breaker_data.switches.append(Topology_NodeBreaker.Switch(node_from_id=self.cim_nodes[tnode_from].id,
                                                                                           node_to_id=self.cim_nodes[tnode_to].id,
                                                                                           id_cim=equip.UUID,
                                                                                           name=equip.name,
                                                                                           status=switch_status))

                    if switch_status:
                        from_tnodes_bus_set = None
                        for idx, tnodes_bus_set in enumerate(tnodes_bus_sets_list):
                            if tnode_from in tnodes_bus_set:
                                from_tnodes_bus_set = tnodes_bus_set
                                from_idx = idx
                                break
                        to_tnodes_bus_set = None
                        for idx, tnodes_bus_set in enumerate(tnodes_bus_sets_list):
                            if tnode_to in tnodes_bus_set:
                                to_tnodes_bus_set = tnodes_bus_set
                                to_idx = idx
                                break

                        if from_tnodes_bus_set is not None and to_tnodes_bus_set is not None:
                            if from_idx != to_idx:
                                # merge tnode sets in one bus
                                tnodes_bus_sets_list[from_idx] |= tnodes_bus_sets_list[to_idx]
                                tnodes_bus_sets_list.pop(to_idx)
                        elif from_tnodes_bus_set is not None and to_tnodes_bus_set is None:
                            # add to the tnode to the set of tnodes for the corresponding bus
                            from_tnodes_bus_set.add(tnode_to)
                        elif from_tnodes_bus_set is None and to_tnodes_bus_set is not None:
                            # add to the tnode to the set of tnodes for the corresponding bus
                            to_tnodes_bus_set.add(tnode_from)
                        elif from_tnodes_bus_set is None and to_tnodes_bus_set is None:
                            tnodes_bus_sets_list.append({tnode_to, tnode_from})

            # create buses for the tnodes connected by switches
            processed_tnodes = set()
            for tnodes_bus_set in tnodes_bus_sets_list:
                new_set = set()
                for tnode in tnodes_bus_set:
                    if tnode.TopologicalIsland == self.biggest_tnode_island:
                        new_set.add(tnode)
                if new_set:
                    new_bus = Topology_BusBranch.Bus()
                    for tnode in new_set:
                        buses[tnode] = new_bus
                        self.cim_nodes[tnode].bus_id = new_bus.id
                        processed_tnodes.add(tnode)
                    # fill in some Bus data based on the last imported TNode in the Bus
                    new_bus.base_kv = self._get_base_voltage(tnode)
                    new_bus.vm = tnode.SvVoltage.v / self._get_base_voltage(tnode)
                    new_bus.va = tnode.SvVoltage.angle
                    new_bus.area = self.cim_areas[tnode.ControlArea].id
                    new_bus.zone = self.cim_zones[voltage_level.Substation.Region].id

            # create buses for the rest of the tnodes in the VoltageLevel
            for tnode in tnodes_set:
                if tnode not in processed_tnodes:
                    new_bus = Topology_BusBranch.Bus(
                        base_kv=self._get_base_voltage(tnode),
                        vm=tnode.SvVoltage.v / self._get_base_voltage(tnode),
                        va=tnode.SvVoltage.angle,
                        area=self.cim_areas[tnode.ControlArea].id,
                        zone=self.cim_zones[voltage_level.Substation.Region].id
                    )
                    buses[tnode] = new_bus
                    self.cim_nodes[tnode].bus_id = new_bus.id

        self.node_breaker_data.nodes = self.cim_nodes.values()
        self.node_breaker_data.substations = cim_substations.values()

        # find the swing bus
        voltage_levels_keys = self.voltage_levels.keys()
        swingbus_tnode = voltage_levels_keys[0].TopologicalNode[0].TopologicalIsland.AngleRef_TopologicalNode
        del voltage_levels_keys

        if not swingbus_tnode:
            logger.warn('No swing bus is given in the network!\n')

        for tnode, bus in buses.iteritems():  # for each TopologicalNode within the bus
            bus_pv = None

            # As of Matpower documentation
            bus_pd = 0.0  # real power demand (MW)
            bus_qd = 0.0  # reactive power demand (MVAr)
            bus_gs = 0.0  # shunt conductance (MW demanded at V = 1.0 p.u.)
            bus_bs = 0.0  # shunt susceptance (MVAr injected at V = 1.0 p.u.)

            try:
                prim_equip = tnodes[tnode]  # tnodes is actually the tnode_equip from _iterate_prim_eq()
            except KeyError:
                # skips the nodes with zero voltage
                continue

            base_voltage = self._get_base_voltage(tnode)

            vmax = 2
            vmin = 0

            for equip in prim_equip:
                status = equip.Terminals[0].connected  # This is only for the 1 terminal elements. The status of the 2 terminal elements is checked when they are transformed to branches
                if status:
                    try:
                        v_limits = []
                        for lim in equip.Terminals[0].OperationalLimitSet[0].OperationalLimitValue:
                            if lim.__class__.__name__ == 'VoltageLimit':
                                v_limits.append(lim.value / base_voltage)
                        if v_limits:
                            if max(v_limits) < vmax:
                                vmax = max(v_limits)
                            if min(v_limits) > vmin:
                                vmin = min(v_limits)
                    except:
                        pass

                equip_cls = equip.__class__.__name__

                ######################################
                #### 1 terminal elements
                if equip_cls == 'SynchronousMachine':
                    gen_name = equip.UUID
                    try:
                        # CIM16
                        pg = equip.p
                        qg = equip.q
                    except AttributeError:
                        pg = -equip.Terminals[0].SvPowerFlow.p
                        qg = -equip.Terminals[0].SvPowerFlow.q

                    try:
                        pg_max = equip.GeneratingUnit.maxOperatingP
                        pg_min = equip.GeneratingUnit.minOperatingP
                        gen_type = equip.GeneratingUnit.__class__.__name__.replace('GeneratingUnit', '')  # Some generator belong to the generic GeneratingUnit class, so their type will result in empty string
                    except AttributeError:
                        pg_max = 0
                        pg_min = 0
                        gen_type = ''

                    if equip.InitialReactiveCapabilityCurve:
                        try:
                            pc1 = equip.InitialReactiveCapabilityCurve.CurveDatas[0].xvalue
                            pc2 = equip.InitialReactiveCapabilityCurve.CurveDatas[1].xvalue
                            qc1_min = equip.InitialReactiveCapabilityCurve.CurveDatas[0].y1value
                            qc2_min = equip.InitialReactiveCapabilityCurve.CurveDatas[1].y1value
                            qc1_max = equip.InitialReactiveCapabilityCurve.CurveDatas[0].y2value
                            qc2_max = equip.InitialReactiveCapabilityCurve.CurveDatas[1].y2value
                        except AttributeError:
                            pc1, pc2, qc1_min, qc2_min, qc1_max, qc2_max = 0, 0, 0, 0, 0, 0
                    else:
                        pc1, pc2, qc1_min, qc2_min, qc1_max, qc2_max = 0, 0, 0, 0, 0, 0

                    if equip.minQ:
                        Qmin_MVAr = equip.minQ
                    else:
                        if equip.InitialReactiveCapabilityCurve:
                            Qmin_MVAr = equip.InitialReactiveCapabilityCurve.CurveDatas[0].y1value
                            # ToDo: Does this needs to be recalculated? As far as I understand
                            #  it is given for a specific P
                        else:
                            Qmin_MVAr = 0

                    if equip.maxQ:
                        Qmax_MVAr = equip.maxQ
                    else:
                        if equip.InitialReactiveCapabilityCurve:
                            Qmax_MVAr = equip.InitialReactiveCapabilityCurve.CurveDatas[0].y2value
                            # ToDo: Does this needs to be recalculated? As far as I understand
                            #  it is given for a specific P
                        else:
                            Qmax_MVAr = 0

                    vg_pu = tnode.SvVoltage.v / base_voltage

                    generators.append(Topology_BusBranch.Generator(
                        # bus is not created yet, fix later
                        bus=tnode, pg=pg, qg=qg, pg_min=pg_min, pg_max=pg_max,
                        qg_min=Qmin_MVAr, qg_max=Qmax_MVAr, vg=vg_pu, name=gen_name, online=status,
                        pc1=pc1, pc2=pc2, qc1_min=qc1_min, qc1_max=qc1_max, qc2_min=qc2_min, qc2_max=qc2_max
                    ))
                    try:
                        fuel_type = equip.GeneratingUnit.FossilFuels[0].fossilFuelType
                    except AttributeError:
                        fuel_type = ''

                    self.node_breaker_data.generators.append(Topology_NodeBreaker.Generator(node_id=self.cim_nodes[tnode].id,
                                                             id_cim=equip.UUID,
                                                             name=equip.GeneratingUnit.name or equip.name,
                                                             type=gen_type,
                                                             mode=equip.operatingMode,
                                                             fuel_type=fuel_type))
                    if equip.operatingMode == 'generator':
                        # ToDo: This logic for defining the type of bus might not be the best...
                        #  Instead maybe look at VoltageControl?
                        bus_pv = Topology_BusBranch.bus_type.PV

                ######################################
                elif equip_cls == 'EnergyConsumer':
                    if status:
                        try:
                            bus_pd += equip.p
                            bus_qd += equip.q
                        except AttributeError:
                            try:
                                bus_pd += equip.Terminals[0].SvPowerFlow.p
                                bus_qd += equip.Terminals[0].SvPowerFlow.q
                            except AttributeError:
                                logger.error('Load %s was not imported correctly!', equip.UUID)

                    self.node_breaker_data.loads.append(
                        Topology_NodeBreaker.Load(node_id=self.cim_nodes[tnode].id, id_cim=equip.UUID, name=equip.name,
                                                  p_mw=equip.Terminals[0].SvPowerFlow.p,
                                                  q_mvar=equip.Terminals[0].SvPowerFlow.q, status=status))
                ######################################
                elif equip_cls == 'ShuntCompensator':
                    shunt_sections = equip.SvShuntCompensatorSections.continuousSections
                    if status:
                        bus_bs += shunt_sections * equip.bPerSection * base_voltage ** 2
                        bus_gs += shunt_sections * equip.gPerSection * base_voltage ** 2

                    self.node_breaker_data.shunts.append(
                        Topology_NodeBreaker.Shunt(node_id=self.cim_nodes[tnode].id,
                                                   id_cim=equip.UUID,
                                                   name=equip.name,
                                                   status=status,
                                                   gPerSection_MVAr=equip.gPerSection * base_voltage ** 2,
                                                   bPerSection_MVAr=equip.bPerSection * base_voltage ** 2,
                                                   maximumSections=equip.maximumSections,
                                                   numActiveSections=equip.SvShuntCompensatorSections.continuousSections
                                                   ))

                ######################################
                #### 2 terminal elements
                elif equip_cls == 'TransformerWinding':
                    if equip.PowerTransformer:
                        power_transformers.add(equip.PowerTransformer)
                elif equip_cls == 'PowerTransformer':
                    power_transformers.add(equip)
                ######################################
                elif equip_cls == 'ACLineSegment':
                    ac_lines.add(equip)
                ######################################
                elif equip_cls == 'SeriesCompensator':
                    logging_message = 'SeriesCompensator  %s  is NOT implemented yet and thus is NOT imported!' % equip.UUID
                    logger.error(logging_message)
                ######################################
                elif equip_cls == 'StaticVarCompensator':
                    logging_message = 'StaticVarCompensator  %s  is NOT implemented yet and thus is NOT imported!' % equip.UUID
                    logger.error(logging_message)
                ######################################
                elif equip_cls == 'DCLineSegment':
                    logging_message = 'DCLineSegment  %s  is NOT implemented yet and thus is NOT imported!' % equip.UUID
                    logger.error(logging_message)
                ######################################
                elif equip_cls == 'RectifierInverter':
                    logging_message = 'RectifierInverter  %s  is NOT implemented yet and thus is NOT imported!' % equip.UUID
                    logger.error(logging_message)

            if tnode is swingbus_tnode:
                bus_swing = Topology_BusBranch.bus_type.REF
            else:
                bus_swing = None
            if bus.vm == 0:
                bus_isolated = Topology_BusBranch.bus_type.ISOLATED
                if bus.vm != 0:
                    logging_message = 'TNode  %s  has zero voltage with angle %f degrees !' %(tnode.UUID, bus.va)
                    logger.warn(logging_message)
            else:
                if bus.vm < 0.9 or bus.vm > 1.1:
                    logging_message = 'TNode  %s  has voltage %f !' %(tnode.UUID, bus.vm)
                    logger.warn(logging_message)
                bus_isolated = None
            tnode_bus_type = (bus_isolated or bus_swing or bus_pv or Topology_BusBranch.bus_type.PQ)

            if vmax < 1.9:  # 1.2:
                bus.vm_max = vmax
            if vmin > 0.1:  # 0.8
                bus.vm_min = vmin
            if bus.btype < tnode_bus_type:
                bus.btype = tnode_bus_type
            bus.pd += bus_pd
            bus.qd += bus_qd
            bus.bs += bus_bs
            bus.gs += bus_gs
            # if bus.cim_classes is not None:
            #     bus.cim_classes.append(cim_classes)
            #     bus.cim_classes.sort()
            # else:
            #     bus.cim_classes = cim_classes
            # if bus.pos is not None:
            #     bus.pos.union(position_points)
            # else:
            #     bus.pos = position_points

        logging_message = 'Created totally %d buses' % len(set(buses.values()))
        logger.info(logging_message)
        logger.info('END creating buses\n')
        return buses, generators, power_transformers, ac_lines

    ####################################################################################################################
    def _get_position_points(self, equipment):
        """
        Returns the set of position points (:class:`Topology_BusBranch.Point`) for
        *equipment*.

        """
        loc = equipment.Location
        if not loc:
            return set()

        pos = set([Topology_BusBranch.Point(float(p.xPosition), float(p.yPosition))
                   for p in loc.PositionPoints])

        return pos

    ####################################################################################################################
    def _get_base_voltage(self, tnode):
        """
        Tries to get a base voltage from *tnode* (TopologicalNode) to from its connectivity nodes.

        Raises a :class:`ValueError` if no base voltage can be found or if the base voltages of the connectivity nodes
        differ from each other.
        """

        if tnode.BaseVoltage:
            return tnode.BaseVoltage.nominalVoltage

        if (hasattr(tnode.ConnectivityNodeContainer, 'BaseVoltage') and
                tnode.ConnectivityNodeContainer.BaseVoltage):
            return tnode.ConnectivityNodeContainer.BaseVoltage.nominalVoltage

        base_voltage = None
        for cn in tnode.ConnectivityNodes:
            if not cn.ConnectivityNodeContainer or not hasattr(
                    cn.ConnectivityNodeContainer, 'BaseVoltage'):
                continue

            bv = cn.ConnectivityNodeContainer.BaseVoltage.nominalVoltage
            if not bv:
                continue

            if not base_voltage:
                base_voltage = bv
            elif bv != base_voltage:
                raise ValueError('Base voltage %s of %s deffers from %s' %
                                 (bv, cn.mRID, base_voltage))

        if base_voltage:
            return base_voltage

        return base_voltage

    ####################################################################################################################
    def _iterate_prim_eq(self, cim_objects):
        """
        Iterates over all *cim_objects* and creates ``TopologicalNode`-s (if they were not present).
        Find the self.biggest_tnode_island and imports ``TopologicalNode`-s only from it.
        Create a list of the control Areas and the load Zones.
        """

        self.node_breaker_data = Topology_NodeBreaker.Topology_NodeBreaker(CIM_filenames=self.cim_files)  # will store all data from the CIM files which cannot be directly mapped to the Matpower structure
        self.cim_areas = {}
        self.cim_zones = {}
        processed = set()  # Contain all processed connectivity nodes
        tnode_equipment = {}  # Top. nodes and adjacent equipment
        lines = set()  # Contains all lines
        base_power = None

        BasePower = self._get_cls('BasePower')
        TopologicalNode = self._get_cls('TopologicalNode')
        tnode_islands = {}

        # First iteration over all CIM objects - in order to create the TopologicalNodes (if not present)
        for mrid, obj in cim_objects.items():
            if isinstance(obj, self._prim_onet) or isinstance(obj, self._prim_twot):
                if hasattr(obj, 'Terminals'):
                    for term in obj.Terminals:
                        cnode = term.ConnectivityNode
                        if cnode:
                            if cnode in processed:
                                tnode = cnode.TopologicalNode
                            else:
                                tnode = TopologicalNode()
                                self._process_cnode(tnode, term, processed)

                            # Append obj to the tnodes equipment
                            tnode_equipment.setdefault(tnode, []).append(obj)
                            if tnode.TopologicalIsland not in tnode_islands:
                                tnode_islands[tnode.TopologicalIsland] = len(tnode.TopologicalIsland.TopologicalNodes)
                        else:
                            tnode = term.TopologicalNode
                            tnode_equipment.setdefault(tnode, []).append(obj)
                            if tnode.TopologicalIsland not in tnode_islands:
                                tnode_islands[tnode.TopologicalIsland] = len(tnode.TopologicalIsland.TopologicalNodes)
            elif isinstance(obj, BasePower):
                assert not base_power, 'There should be only one BasePower instance.'
                base_power = float(obj.basePower)
            elif isinstance(obj, self._get_cls('ControlArea')):
                self.cim_areas[obj] = Topology_NodeBreaker.Area(id_cim=obj.UUID,
                                                                name=obj.name,
                                                                netInterchange=obj.netInterchange,
                                                                pTolerance=obj.pTolerance)
            elif isinstance(obj, self._get_cls('SubGeographicalRegion')):
                self.cim_zones[obj] = Topology_NodeBreaker.Zone(id_cim=obj.UUID,
                                                                name=obj.name)

        self.node_breaker_data.areas = self.cim_areas.values()
        self.node_breaker_data.zones = self.cim_zones.values()

        # find biggest_tnode_island
        max_num_tnodes = max(tnode_islands.values())
        for tnode_island in tnode_islands:
            if tnode_islands[tnode_island] == max_num_tnodes:
                self.biggest_tnode_island = tnode_island
        logging_message = 'The biggest topological island is %s. Only elements in it will be imported!!!\n' % self.biggest_tnode_island.UUID
        logger.info(logging_message)

        if base_power is None:
            base_power = 100.0  # default basepower

        # Second iteration over all CIM objects - in order to import objects only from the biggest TopologicalIsland
        self.voltage_levels = {}
        for mrid, obj in cim_objects.items():
            if isinstance(obj, self._get_cls('Terminal')):
                try:
                    tnode = obj.ConnectivityNode.TopologicalNode
                except AttributeError:
                    try:
                        tnode = obj.TopologicalNode
                    except AttributeError:
                        print(
                            'Skipped %s of class %s .' % (obj.UUID, obj.__class__.__name__))  # this was just for testing
                        continue
                if tnode.ConnectivityNodeContainer:
                    if tnode.TopologicalIsland == self.biggest_tnode_island:
                        self.voltage_levels.setdefault(tnode.ConnectivityNodeContainer, set()).add(tnode)
                else:
                    print('TNode %s does not have ConnectivityNodeContainer.' % (tnode.name or tnode.UUID))

        return base_power, tnode_equipment

    ####################################################################################################################
    def _process_cnode(self, tnode, src_terminal, processed):
        """
        Recursively processes the connectivity node connected to *src_terminal*
        and adds it to terminals.

        You need to pass the terminal and not the connectivity node, because we need the terminal to keep track where
        we are coming from and to not to visit the same terminal again.
        """

        cnode = src_terminal.ConnectivityNode
        if cnode in processed:
            return

        tnode.addConnectivityNodes(cnode)
        processed.add(cnode)

        for terminal in cnode.Terminals:
            if terminal is src_terminal:
                continue

            ce = terminal.ConductingEquipment

            # Recursivly process other nodes if the terminal connects to a
            # rectifier inverter or a closed switch.
            if (isinstance(ce, self._get_cls('RectifierInverter')) or
                    (isinstance(ce, self._get_cls('Switch')) and
                         (not ce.normalOpen or ce.retain))):
                assert len(ce.Terminals) == 2

                other_term = ce.Terminals[1] if terminal is ce.Terminals[0] \
                    else ce.Terminals[0]

                self._process_cnode(tnode, other_term, processed)

    ####################################################################################################################
    def _get_equipment_cls(self, names):
        """Returns a touple containing the class objects for *names*."""
        classes = []
        for name in names:
            # Not all classes in each version of CIM
            try:
                classes.append(self._get_cls(name))
            except KeyError:
                pass
        return tuple(classes)

    ####################################################################################################################
    def _get_cls(self, name):
        """Imports and returns the class object for *name*."""
        module = __import__(self._package_map[name], globals(), locals(),
                            [name])

        return getattr(module, name)
