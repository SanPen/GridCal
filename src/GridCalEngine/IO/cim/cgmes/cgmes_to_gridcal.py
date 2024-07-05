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
import numpy as np
from typing import Dict, List, Tuple, Union
import GridCalEngine.IO.cim.cgmes.cgmes_enums as cgmes_enums
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as gcdev
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_utils import (get_nominal_voltage,
                                                    get_pu_values_ac_line_segment,
                                                    get_values_shunt,
                                                    get_pu_values_power_transformer,
                                                    get_pu_values_power_transformer3w,
                                                    get_regulating_control,
                                                    get_pu_values_power_transformer_end,
                                                    get_slack_id,
                                                    find_object_by_idtag,
                                                    find_terms_connections)
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.IO.cim.cgmes.base import Base


class CnLookup:
    """
    Class to properly match the ConnectivityNodes to the BusBars
    """

    def __init__(self, cgmes_model: CgmesCircuit):
        self.cn_dict: Dict[str, gcdev.ConnectivityNode] = dict()
        self.bus_dict: Dict[str, gcdev.Bus] = dict()

        # fill information from CGMES terminals
        self.bb_to_cn_dict: Dict[str, Base] = dict()
        self.bb_to_tn_dict: Dict[str, Base] = dict()

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

    def add_cn(self, cn: gcdev.ConnectivityNode):
        """

        :param cn:
        :return:
        """
        self.cn_dict[cn.idtag] = cn

    def add_bus(self, bus: gcdev.Bus):
        """

        :param bus:
        :return:
        """
        self.bus_dict[bus.idtag] = bus

    def get_busbar_cn(self, bb_id: str) -> Union[None, gcdev.ConnectivityNode]:
        """
        Get the associated ConnectivityNode object
        :param bb_id: BusBarSection uuid
        :return: ConnectivityNode or None
        """
        cgmes_cn = self.bb_to_cn_dict.get(bb_id, None)

        if cgmes_cn is not None:
            return self.cn_dict[cgmes_cn.uuid]
        else:
            return None

    def get_busbar_bus(self, bb_id: str) -> Union[None, gcdev.Bus]:
        """
        Get the associated ConnectivityNode object
        :param bb_id: BusBarSection uuid
        :return: ConnectivityNode or None
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
                                      logger: DataLogger) -> Dict[str, List[Base]]:
    """
    Dictionary relating the conducting equipment to the terminal object(s)
    """
    # dictionary relating the conducting equipment to the terminal object
    device_to_terminal_dict: Dict[str, List[Base]] = dict()

    con_eq_type = cgmes_model.get_class_type("ConductingEquipment")
    if con_eq_type is None:
        raise NotImplementedError("Class type missing from assets!")

    for e in cgmes_model.cgmes_assets.Terminal_list:
        if isinstance(e.ConductingEquipment, con_eq_type):
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


def find_connections(cgmes_elm: Base,
                     device_to_terminal_dict: Dict[str, List[Base]],
                     calc_node_dict: Dict[str, gcdev.Bus],
                     cn_dict: Dict[str, gcdev.ConnectivityNode],
                     logger: DataLogger) -> Tuple[List[gcdev.Bus], List[gcdev.ConnectivityNode]]:
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
                                cn_look_up: CnLookup,
                                logger: DataLogger) -> Dict[str, gcdev.Bus]:
    """
    Convert the TopologicalNodes to CalculationNodes
    :param cgmes_model: CgmesCircuit
    :param gc_model: gcdevCircuit
    :param v_dict: Dict[str, Terminal]
    :param cn_look_up: CnLookup
    :param logger: DataLogger
    :return: dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus]
    """

    slack_id = get_slack_id(cgmes_model.cgmes_assets.SynchronousMachine_list)
    if slack_id is None:
        logger.add_error(msg="Couldn't find referencePriority 1 in the SynchronousMachines.",
                         device_class="SynchronousMachine",
                         device_property="referencePriority")  # TODO error check

    # dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
    calc_node_dict: Dict[str, gcdev.Bus] = dict()
    for cgmes_elm in cgmes_model.cgmes_assets.TopologicalNode_list:

        voltage = v_dict.get(cgmes_elm.uuid, None)
        nominal_voltage = get_nominal_voltage(topological_node=cgmes_elm,
                                              logger=logger)
        if nominal_voltage == 0:
            logger.add_error(msg='Nominal voltage is 0. :(',
                             device=cgmes_elm.rdfid,
                             device_class=cgmes_elm.tpe,
                             device_property="nominalVoltage")

        if voltage is not None and nominal_voltage is not None:
            vm = voltage[0] / nominal_voltage
            va = np.deg2rad(voltage[1])
        else:
            vm = 1.0
            va = 0.0

        is_slack = False
        if slack_id == cgmes_elm.rdfid:
            is_slack = True

        volt_lev, substat, country = None, None, None
        longitude, latitude = 0.0, 0.0
        if cgmes_elm.ConnectivityNodeContainer:
            volt_lev = find_object_by_idtag(
                object_list=gc_model.voltage_levels,
                target_idtag=cgmes_elm.ConnectivityNodeContainer.uuid
            )
            if volt_lev is None:
                line_tpe = cgmes_model.cgmes_assets.class_dict.get("Line")
                if not isinstance(cgmes_elm.ConnectivityNodeContainer, line_tpe):
                    logger.add_warning(msg='No voltage level found for the bus',
                                       device=cgmes_elm.rdfid,
                                       device_class=cgmes_elm.tpe,
                                       device_property="ConnectivityNodeContainer")
            else:
                substat = find_object_by_idtag(
                    object_list=gc_model.substations,
                    target_idtag=volt_lev.substation.idtag
                )
                if substat is None:
                    logger.add_warning(msg='No substation found for bus.',
                                       device=volt_lev.rdfid,
                                       device_class=volt_lev.tpe,
                                       device_property="substation")
                    print(f'No substation found for BUS {cgmes_elm.name}')
                else:
                    country = substat.country
                    longitude = substat.longitude
                    latitude = substat.latitude
        else:
            logger.add_warning(msg='Missing voltage level.',
                               device=cgmes_elm.rdfid,
                               device_class=cgmes_elm.tpe,
                               device_property="ConnectivityNodeContainer")
            # else form here get SubRegion and Region for Country..
        gcdev_elm = gcdev.Bus(name=cgmes_elm.name,
                              idtag=cgmes_elm.uuid,
                              code=cgmes_elm.description,
                              Vnom=nominal_voltage,
                              vmin=0.9,
                              vmax=1.1,
                              active=True,
                              is_slack=is_slack,
                              is_dc=False,
                              # is_internal=False,
                              area=None,  # areas and zones are not created from cgmes models
                              zone=None,
                              substation=substat,
                              voltage_level=volt_lev,
                              country=country,
                              latitude=latitude,
                              longitude=longitude,
                              Vm0=vm,
                              Va0=va)

        gc_model.add_bus(gcdev_elm)
        cn_look_up.add_bus(bus=gcdev_elm)
        calc_node_dict[gcdev_elm.idtag] = gcdev_elm

    return calc_node_dict


def get_gcdev_connectivity_nodes(cgmes_model: CgmesCircuit,
                                 gcdev_model: MultiCircuit,
                                 calc_node_dict: Dict[str, gcdev.Bus],
                                 cn_look_up: CnLookup,
                                 logger: DataLogger) -> Dict[str, gcdev.ConnectivityNode]:
    """
    Convert the TopologicalNodes to CalculationNodes
    :param calc_node_dict: dictionary relating the TopologicalNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus]
    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param cn_look_up: CnLookUp
    :param logger: DataLogger
    :return: dictionary relating the ConnectivityNode uuid to the gcdev CalculationNode
             Dict[str, gcdev.Bus]
    """
    # dictionary relating the ConnectivityNode uuid to the gcdev ConnectivityNode
    cn_node_dict: Dict[str, gcdev.ConnectivityNode] = dict()
    used_buses = set()
    for cgmes_elm in cgmes_model.cgmes_assets.ConnectivityNode_list:

        bus = calc_node_dict.get(cgmes_elm.TopologicalNode.uuid, None)
        vnom, vl = 10, None
        if bus is None:
            logger.add_error(msg='No Bus found',
                             device=cgmes_elm.rdfid,
                             device_class=cgmes_elm.tpe)
            default_bus = None
        else:
            if bus not in used_buses:
                default_bus = bus
                used_buses.add(bus)
            else:
                default_bus = None
            vnom = bus.Vnom
            vl = bus.voltage_level

        gcdev_elm = gcdev.ConnectivityNode(
            idtag=cgmes_elm.uuid,
            code=cgmes_elm.description,
            name=cgmes_elm.name,
            dc=False,
            default_bus=default_bus,  # this is only set by the BusBar's
            Vnom=vnom,
            voltage_level=vl
        )

        gcdev_model.connectivity_nodes.append(gcdev_elm)
        cn_look_up.add_cn(gcdev_elm)
        cn_node_dict[gcdev_elm.idtag] = gcdev_elm

    return cn_node_dict


def get_gcdev_loads(cgmes_model: CgmesCircuit,
                    gcdev_model: MultiCircuit,
                    calc_node_dict: Dict[str, gcdev.Bus],
                    cn_dict: Dict[str, gcdev.ConnectivityNode],
                    device_to_terminal_dict: Dict[str, List[Base]],
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
    for device_list in [cgmes_model.cgmes_assets.EnergyConsumer_list,
                        cgmes_model.cgmes_assets.ConformLoad_list,
                        cgmes_model.cgmes_assets.NonConformLoad_list]:

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

                gcdev_model.add_load(bus=calc_node, api_obj=gcdev_elm, cn=cn)

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
                         device_to_terminal_dict: Dict[str, List[Base]],
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
            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 1:
                calc_node = calc_nodes[0]
                cn = cns[0]

                if cgmes_elm.GeneratingUnit is not None:

                    v_set, is_controlled, controlled_bus, controlled_cn = (
                        get_regulating_control(
                            cgmes_elm=cgmes_elm,
                            cgmes_enums=cgmes_enums,
                            calc_node_dict=calc_node_dict,
                            cn_dict=cn_dict,
                            logger=logger
                        ))

                    if cgmes_elm.p != 0.0:
                        pf = np.cos(np.arctan(cgmes_elm.q / cgmes_elm.p))
                    else:
                        pf = 0.8
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
                                                Qmax=cgmes_elm.maxQ,
                                                Qmin=cgmes_elm.minQ,
                                                vset=v_set,
                                                is_controlled=is_controlled,
                                                # controlled_bus
                                                # TODO get controlled gc.bus
                                                )

                    gcdev_model.add_generator(bus=calc_node, api_obj=gcdev_elm, cn=cn)

                    if technology:
                        gcdev_elm.technologies.append(gcdev.Association(api_object=technology, value=1.0))
                        # gcdev_model.add_generator_fuel()
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
                             cn_dict: Dict[str, gcdev.ConnectivityNode],
                             device_to_terminal_dict: Dict[str, List[Base]],
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
    for device_list in [cgmes_model.cgmes_assets.EquivalentInjection_list]:
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

                gcdev_model.add_external_grid(bus=calc_node, api_obj=gcdev_elm, cn=cn)
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
                       device_to_terminal_dict: Dict[str, List[Base]],
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
    acline_type = cgmes_model.get_class_type("ACLineSegment")
    for e in cgmes_model.cgmes_assets.CurrentLimit_list:
        if e.OperationalLimitSet is None:
            logger.add_error(msg='OperationalLimitSet missing.',
                             device=e.rdfid,
                             device_class=e.tpe,
                             device_property="OperationalLimitSet",
                             value="None")
            continue
        if not isinstance(e.OperationalLimitSet, str):
            if isinstance(e.OperationalLimitSet, list):
                for ols in e.OperationalLimitSet:
                    if isinstance(ols.Terminal.ConductingEquipment, acline_type):
                        branch_id = ols.Terminal.ConductingEquipment.uuid
                        rates_dict[branch_id] = e.value
            else:
                if isinstance(e.OperationalLimitSet.Terminal.ConductingEquipment, acline_type):
                    branch_id = e.OperationalLimitSet.Terminal.ConductingEquipment.uuid
                    rates_dict[branch_id] = e.value

    # convert ac lines
    for device_list in [cgmes_model.cgmes_assets.ACLineSegment_list]:
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
                                       cn_from=cn_f,
                                       cn_to=cn_t,
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
                              device_to_terminal_dict: Dict[str, List[Base]],
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
    for device_list in [cgmes_model.cgmes_assets.PowerTransformer_list]:

        for cgmes_elm in device_list:

            windings = [None, None, None]
            for pte in list(cgmes_elm.PowerTransformerEnd):
                if hasattr(pte, "endNumber"):
                    i = getattr(pte, "endNumber")
                    if i is not None:
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
                                                    cn_from=cn_f,
                                                    cn_to=cn_t,
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
                                                    # control_mode,  # legacy
                                                    # tap_module_control_mode=,
                                                    # tap_angle_control_mode=,
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
                                                    # bus0=,
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
                                                    x=0.0,
                                                    y=0.0)

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
                    gcdev_elm.winding1.cn_from = cn_1
                    gcdev_elm.winding1.cn_to = cn_2

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
                    gcdev_elm.winding2.cn_from = cn_2
                    gcdev_elm.winding2.cn_to = cn_3

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
                    gcdev_elm.winding3.cn_from = cn_3
                    gcdev_elm.winding3.cn_to = cn_1

                    # gcdev_model.add_transformer3w(gcdev_elm, add_middle_bus=False)  # TODO: Why not adding the middle bus?
                    gcdev_model.add_transformer3w(gcdev_elm, add_middle_bus=True)

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
                     device_to_terminal_dict: Dict[str, List[Base]],
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
    :param Sbase:
    """
    # convert shunts
    for device_list in [cgmes_model.cgmes_assets.LinearShuntCompensator_list]:

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
                    active=True,
                )
                gcdev_model.add_shunt(bus=calc_node, api_obj=gcdev_elm, cn=cn)

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
        calc_node_dict: Dict[str, gcdev.Bus],
        cn_dict: Dict[str, gcdev.ConnectivityNode],
        device_to_terminal_dict: Dict[str, List[Base]],
        logger: DataLogger,
        Sbase: float) -> None:
    """
    Convert the CGMES non-linear shunt compensators to gcdev Controllable shunts.

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param logger:
    """
    # comes later
    for device_list in [cgmes_model.cgmes_assets.NonlinearShuntCompensator_list]:
        # ...
        # v_set, is_controlled = get_regulating_control(
        #     cgmes_elm=cgmes_elm,
        #     cgmes_enums=cgmes_enums,
        #     logger=logger)
        pass


def get_gcdev_switches(cgmes_model: CgmesCircuit,
                       gcdev_model: MultiCircuit,
                       calc_node_dict: Dict[str, gcdev.Bus],
                       cn_dict: Dict[str, gcdev.ConnectivityNode],
                       device_to_terminal_dict: Dict[str, List[Base]],
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

    sw_type = cgmes_model.get_class_type("Switch")
    br_type = cgmes_model.get_class_type("Breaker")
    ds_type = cgmes_model.get_class_type("Disconnector")
    lbs_type = cgmes_model.get_class_type("LoadBreakSwitch")
    for e in cgmes_model.cgmes_assets.CurrentLimit_list:
        if not isinstance(e.OperationalLimitSet, str):
            conducting_equipment = e.OperationalLimitSet.Terminal.ConductingEquipment
            if isinstance(conducting_equipment,
                          (sw_type, br_type, ds_type, lbs_type)):
                branch_id = conducting_equipment.uuid
                rates_dict[branch_id] = e.value

    # convert switch
    for device_list in [cgmes_model.cgmes_assets.Switch_list,
                        cgmes_model.cgmes_assets.Breaker_list,
                        cgmes_model.cgmes_assets.Disconnector_list,
                        cgmes_model.cgmes_assets.LoadBreakSwitch_list,
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

                if (cgmes_elm.ratedCurrent is not None
                        and cgmes_elm.ratedCurrent != 0.0
                        and cgmes_elm.BaseVoltage is not None):  # TODO
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
                    cn_from=cn_f,
                    cn_to=cn_t,
                    bus_from=calc_node_f,
                    bus_to=calc_node_t,
                    rate=op_rate,
                    rated_current=rated_current,
                    # is_open=cgmes_elm.open,   # not used
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
    for device_list in [cgmes_model.cgmes_assets.Substation_list]:

        for cgmes_elm in device_list:

            region = find_object_by_idtag(
                object_list=gcdev_model.communities,
                target_idtag=cgmes_elm.Region.uuid
            )

            if cgmes_elm.Location:
                longitude = cgmes_elm.Location.PositionPoints.xPosition
                latitude = cgmes_elm.Location.PositionPoints.yPosition
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

            if region is not None:
                gcdev_elm.community = region
            else:
                print(f'No Community found for substation {gcdev_elm.name}')

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
        volt_lev_dict[gcdev_elm.idtag] = gcdev_elm

    return volt_lev_dict


def get_gcdev_busbars(cgmes_model: CgmesCircuit,
                      gcdev_model: MultiCircuit,
                      calc_node_dict: Dict[str, gcdev.Bus],
                      cn_dict: Dict[str, gcdev.ConnectivityNode],
                      device_to_terminal_dict: Dict[str, List[Base]],
                      cn_look_up: CnLookup,
                      logger: DataLogger) -> None:
    """
    Convert the CGMES busbars to gcdev busbars

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    :param calc_node_dict: Dict[str, gcdev.Bus]
    :param cn_dict: Dict[str, gcdev.ConnectivityNode]
    :param device_to_terminal_dict: Dict[str, Terminal]
    :param cn_look_up: CnLookUp
    :param logger: DataLogger
    """
    # convert busbars
    for device_list in [cgmes_model.cgmes_assets.BusbarSection_list]:

        for cgmes_elm in device_list:

            calc_nodes, cns = find_connections(cgmes_elm=cgmes_elm,
                                               device_to_terminal_dict=device_to_terminal_dict,
                                               calc_node_dict=calc_node_dict,
                                               cn_dict=cn_dict,
                                               logger=logger)

            if len(calc_nodes) == 1 or len(cns) == 1:
                # calc_node = calc_nodes[0]
                cn = cns[0]

                vl_type = cgmes_model.get_class_type("VoltageLevel")
                bay_type = cgmes_model.get_class_type("Bay")
                container = cgmes_elm.EquipmentContainer
                if isinstance(container, vl_type):
                    vl = container
                    substation = container.Substation
                elif isinstance(container, bay_type):
                    vl = None
                    substation = container.VoltageLevel.Substation
                else:
                    vl = None
                    substation = None

                cn = cn_look_up.get_busbar_cn(bb_id=cgmes_elm.uuid)
                bus = cn_look_up.get_busbar_bus(bb_id=cgmes_elm.uuid)

                if bus and cn:
                    cn.default_bus = bus

                gcdev_elm = gcdev.BusBar(
                    name=cgmes_elm.name,
                    idtag=cgmes_elm.uuid,
                    code=cgmes_elm.description,
                    voltage_level=vl,
                    cn=cn  # we make it explicitly None because this will be correted afterwards
                )
                gcdev_model.add_bus_bar(gcdev_elm, add_cn=cn is None)

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
    Convert the CGMES GeoGrapicalRegions to gcdev Country

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    """
    for device_list in [cgmes_model.cgmes_assets.GeographicalRegion_list]:

        for cgmes_elm in device_list:
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
    Convert the CGMES SubGeograpicalRegions to gcdev Community

    :param cgmes_model: CgmesCircuit
    :param gcdev_model: gcdevCircuit
    """
    for device_list in [cgmes_model.cgmes_assets.SubGeographicalRegion_list]:

        for cgmes_elm in device_list:
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


def cgmes_to_gridcal(cgmes_model: CgmesCircuit,
                     logger: DataLogger) -> MultiCircuit:
    """
    convert CGMES model to gcdev
    :param cgmes_model: CgmesCircuit
    :param logger: Logger object
    :return: MultiCircuit
    """
    gc_model = MultiCircuit()  # roseta
    gc_model.comments = 'Converted from a CGMES file'
    Sbase = gc_model.Sbase
    cgmes_model.emit_progress(70)
    cgmes_model.emit_text("Converting CGMES to Gridcal")
    # busbar_dict = parse_bus_bars(cgmes_model, circuit, logger)
    # parse_ac_line_segment(cgmes_model, circuit, busbar_dict, logger)
    # parse_power_transformer(cgmes_model, circuit, busbar_dict, logger)
    # parse_switches(cgmes_model, circuit, busbar_dict, logger)
    # parse_loads(cgmes_model, circuit, busbar_dict, logger)
    # parse_shunts(cgmes_model, circuit, busbar_dict, logger)
    # parse_generators(cgmes_model, circuit, busbar_dict, logger)

    get_gcdev_countries(cgmes_model, gc_model)

    # TODO: Assign the community in the buses
    get_gcdev_community(cgmes_model, gc_model)

    get_gcdev_substations(cgmes_model, gc_model)

    vl_dict = get_gcdev_voltage_levels(cgmes_model, gc_model, logger)

    cn_look_up = CnLookup(cgmes_model)

    sv_volt_dict = get_gcdev_voltage_dict(cgmes_model=cgmes_model,
                                          logger=logger)

    device_to_terminal_dict = get_gcdev_device_to_terminal_dict(cgmes_model=cgmes_model,
                                                                logger=logger)

    calc_node_dict = get_gcdev_calculation_nodes(cgmes_model=cgmes_model,
                                                 gc_model=gc_model,
                                                 v_dict=sv_volt_dict,
                                                 cn_look_up=cn_look_up,
                                                 logger=logger)

    cn_dict = get_gcdev_connectivity_nodes(cgmes_model=cgmes_model,
                                           gcdev_model=gc_model,
                                           calc_node_dict=calc_node_dict,
                                           cn_look_up=cn_look_up,
                                           logger=logger)
    cgmes_model.emit_progress(78)
    get_gcdev_busbars(cgmes_model=cgmes_model,
                      gcdev_model=gc_model,
                      calc_node_dict=calc_node_dict,
                      cn_dict=cn_dict,
                      device_to_terminal_dict=device_to_terminal_dict,
                      cn_look_up=cn_look_up,
                      logger=logger)

    get_gcdev_loads(cgmes_model=cgmes_model,
                    gcdev_model=gc_model,
                    calc_node_dict=calc_node_dict,
                    cn_dict=cn_dict,
                    device_to_terminal_dict=device_to_terminal_dict,
                    logger=logger)

    get_gcdev_external_grids(cgmes_model=cgmes_model,
                             gcdev_model=gc_model,
                             calc_node_dict=calc_node_dict,
                             cn_dict=cn_dict,
                             device_to_terminal_dict=device_to_terminal_dict,
                             logger=logger)

    get_gcdev_generators(cgmes_model=cgmes_model,
                         gcdev_model=gc_model,
                         calc_node_dict=calc_node_dict,
                         cn_dict=cn_dict,
                         device_to_terminal_dict=device_to_terminal_dict,
                         logger=logger)

    cgmes_model.emit_progress(86)

    get_gcdev_ac_lines(cgmes_model=cgmes_model,
                       gcdev_model=gc_model,
                       calc_node_dict=calc_node_dict,
                       cn_dict=cn_dict,
                       device_to_terminal_dict=device_to_terminal_dict,
                       logger=logger,
                       Sbase=Sbase)

    get_gcdev_ac_transformers(cgmes_model=cgmes_model,
                              gcdev_model=gc_model,
                              calc_node_dict=calc_node_dict,
                              cn_dict=cn_dict,
                              device_to_terminal_dict=device_to_terminal_dict,
                              logger=logger,
                              Sbase=Sbase)

    get_gcdev_shunts(cgmes_model=cgmes_model,
                     gcdev_model=gc_model,
                     calc_node_dict=calc_node_dict,
                     cn_dict=cn_dict,
                     device_to_terminal_dict=device_to_terminal_dict,
                     logger=logger,
                     Sbase=Sbase)

    # get_gcdev_controllable_shunts()  TODO controllable shunts
    get_gcdev_switches(cgmes_model=cgmes_model,
                       gcdev_model=gc_model,
                       calc_node_dict=calc_node_dict,
                       cn_dict=cn_dict,
                       device_to_terminal_dict=device_to_terminal_dict,
                       logger=logger,
                       Sbase=Sbase)

    print('debug')
    cgmes_model.emit_progress(100)
    cgmes_model.emit_text("Cgmes import done!")

    # Gridcal to cgmes
    # cgmes_model_export = CgmesCircuit(
    #     cgmes_version=cgmes_model.options.cgmes_version.__str__(),
    #     text_func=cgmes_model.text_func,
    #     progress_func=cgmes_model.progress_func, logger=logger)
    # cgmes_model_export = gridcal_to_cgmes(gc_model, cgmes_model_export, None, logger)

    # Export test for the imported data
    # start = time.time()
    # serializer = CimExporter(cgmes_model_export)
    # serializer.export_test()
    # end = time.time()
    # print("ET export time: ", end - start, "sec")

    # Export data converted from gridcal

    # Run topology progcessing
    # tp_info = gc_model.process_topology_at()

    return gc_model
