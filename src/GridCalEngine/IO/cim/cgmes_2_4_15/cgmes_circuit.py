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

import pandas as pd
from collections.abc import Callable
from typing import Dict, List, Union
from enum import Enum, EnumMeta

from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.line.ac_line_segment import ACLineSegment
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.breaker import Breaker
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.bus_bar_section import BusbarSection
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.connector import Connector
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.junction import Junction
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.bus_name_marker import BusNameMarker
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.conform_load import ConformLoad
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.connectivity_node_container import ConnectivityNodeContainer
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.control_area import ControlArea
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.current_limit import CurrentLimit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.energy_area import EnergyArea
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.cgm_region import CGMRegion
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.modelling_authority import ModelingAuthority
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.merging_agent import MergingAgent
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.energy_consumer import EnergyConsumer
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.equivalent_injection import EquivalentInjection
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.equivalent_network import EquivalentNetwork
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.full_model import FullModel
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.geographical_region import GeographicalRegion
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.hydro_generating_unit import HydroGeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.hydro_power_plant import HydroPowerPlant
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.hydro_pump import HydroPump
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.line.line import Line
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.shunt.linear_shunt_compensator import LinearShuntCompensator
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.load_breaker_switch import LoadBreakSwitch
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.load_group import LoadGroup
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.load_response_characteristic import \
    LoadResponseCharacteristic
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.non_conform_load import NonConformLoad
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.nuclear_generating_unit import \
    NuclearGeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.control_area_generating_unit import \
    ControlAreaGeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.operational_limit_set import OperationalLimitSet
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.operational_limit_type import OperationalLimitType
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.power_transformer import PowerTransformer
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.ratio_tap_changer import RatioTapChanger
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.ratio_tap_changer_table import RatioTapChangerTable
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.ratio_tap_changer_table_point import \
    RatioTapChangerTablePoint
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.reactive_capability_curve import \
    ReactiveCapabilityCurve
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.regulating_control import RegulatingControl
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.rotating_machine import RotatingMachine
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.shunt.static_var_compensator import StaticVarCompensator
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.sub_geographical_region import SubGeographicalRegion
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.switch import Switch
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.synchronous_machine import SynchronousMachine
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.tap_changer_control import TapChangerControl
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer import PhaseTapChanger
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_non_linear import \
    PhaseTapChangerNonLinear
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_symmetrical import \
    PhaseTapChangerSymmetrical
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_tabular import \
    PhaseTapChangerTabular
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_table import PhaseTapChangerTable
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_table_point import \
    PhaseTapChangerTablePoint
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.thermal_generating_unit import \
    ThermalGeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.tie_flow import TieFlow
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.voltage_level import VoltageLevel
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.voltage_limit import VoltageLimit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.substation import Substation
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.wind_generating_unit import WindGeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.solar_generating_unit import SolarGeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.fossil_fuel import FossilFuel
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.equivalent_branch import EquivalentBranch
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.conform_load_group import ConformLoadGroup
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.non_conform_load_group import NonConformLoadGroup
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.energy_scheduling_type import EnergySchedulingType
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.load_area import LoadArea
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.sub_load_area import SubLoadArea
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.results.topological_island import TopologicalIsland
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.results.sv_voltage import SvVoltage
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.results.sv_power_flow import SvPowerFlow
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.results.sv_shunt_compensator_sections import SvShuntCompensatorSections
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.results.sv_tap_step import SvTapStep
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.inputs.curve import Curve
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.inputs.curve_data import CurveData
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_poperty import CgmesProperty
from GridCalEngine.IO.base.base_circuit import BaseCircuit
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_data_parser import CgmesDataParser


def find_references(elements_by_type: Dict[str, List[IdentifiedObject]],
                    all_objects_dict: Dict[str, IdentifiedObject],
                    all_objects_dict_boundary: Union[Dict[str, IdentifiedObject], None],
                    logger: DataLogger,
                    mark_used: bool) -> None:
    """
    Replaces the references in the "actual" properties of the objects
    :param elements_by_type: Dictionary of elements by type to fill in (same as all_objects_dict but by categories)
    :param all_objects_dict: dictionary of all model objects to add Parsed objects
    :param all_objects_dict_boundary: dictionary of all boundary set objects to
                                      add Parsed objects used to find references
    :param logger: DataLogger
    :param mark_used: mark objects as used?
    :return: Nothing, it is done in place
    """
    added_from_the_boundary_set = list()

    # find cross-references
    for class_name, elements in elements_by_type.items():
        for element in elements:  # for every element of the type
            if mark_used:
                element.used = True

            # check the declared properties
            for property_name, cim_prop in element.declared_properties.items():

                # try to get the property value, else, fill with None
                # at this point val is always the string that came in the XML
                value = getattr(element, property_name)

                if value is not None:  # if the value is something...

                    if cim_prop.class_type in [str, float, int, bool]:
                        # set the referenced object in the property
                        try:
                            setattr(element, property_name, cim_prop.class_type(value))
                        except ValueError:
                            logger.add_error(msg='Value error',
                                             device=element.rdfid,
                                             device_class=class_name,
                                             device_property=property_name,
                                             value=value,
                                             expected_value=str(cim_prop.class_type))

                    elif isinstance(cim_prop.class_type, Enum) or isinstance(cim_prop.class_type, EnumMeta):

                        if type(value) == str:
                            chunks = value.split('.')
                            value2 = chunks[-1]
                            try:
                                enum_val = cim_prop.class_type(value2)
                                setattr(element, property_name, enum_val)
                            except TypeError as e:
                                logger.add_error(msg='Could not convert Enum',
                                                 device=element.rdfid,
                                                 device_class=class_name,
                                                 device_property=property_name,
                                                 value=value2 + " (value)",
                                                 expected_value=str(cim_prop.class_type))

                    else:
                        # search for the reference, if not found -> return None
                        referenced_object = all_objects_dict.get(value, None)

                        if referenced_object is None and all_objects_dict_boundary:
                            # search for the reference in the boundary set
                            referenced_object = all_objects_dict_boundary.get(value, None)

                            # add to the normal data if it wasn't added before
                            if referenced_object.rdfid not in all_objects_dict:
                                all_objects_dict[referenced_object.rdfid] = referenced_object
                                added_from_the_boundary_set.append(referenced_object)

                        # if the reference was found in the data of the boundary set ...
                        if referenced_object is not None:
                            if mark_used:
                                referenced_object.used = True

                            # set the referenced object in the property
                            setattr(element, property_name, referenced_object)

                            # register the inverse reference
                            referenced_object.add_reference(element)

                            # check that the type matches the expected type
                            if cim_prop.class_type in [ConnectivityNodeContainer, IdentifiedObject]:
                                # the container class is too generic...
                                pass
                            else:
                                if not isinstance(referenced_object, cim_prop.class_type) and \
                                        cim_prop.class_type != EquipmentContainer:
                                    # if the class specification does not match but the
                                    # required type is also not a generic polymorphic object ...
                                    cls = str(cim_prop.class_type).split('.')[-1].replace("'", "").replace(">", "")
                                    logger.add_error(msg='Object type different from expected',
                                                     device=element.rdfid,
                                                     device_class=class_name,
                                                     device_property=property_name,
                                                     value=referenced_object.tpe,
                                                     expected_value=cls)
                        else:

                            # I want to know that it was not found
                            element.missing_references[property_name] = value

                            if hasattr(element, 'rdfid'):
                                logger.add_error(msg='Reference not found',
                                                 device=element.rdfid,
                                                 device_class=class_name,
                                                 device_property=property_name,
                                                 value='Not found',
                                                 expected_value=value)
                            else:
                                logger.add_error(msg='Reference not found for (debugger error)',
                                                 device=element.rdfid,
                                                 device_class=class_name,
                                                 device_property=property_name,
                                                 value='Not found',
                                                 expected_value=value)

                    if cim_prop.out_of_the_standard:
                        logger.add_warning(msg='Property supported but out of the standard',
                                           device=element.rdfid,
                                           device_class=class_name,
                                           device_property=property_name,
                                           value=value,
                                           expected_value="")

                else:
                    if cim_prop.mandatory:
                        logger.add_error(msg='Required property not provided',
                                         device=element.rdfid,
                                         device_class=class_name,
                                         device_property=property_name,
                                         value='not provided',
                                         expected_value=property_name)
                    else:
                        pass

            # check the object rules
            element.check(logger=logger)

    # modify the elements_by_type here adding the elements from the boundary set
    # all_elements_dict was modified in the previous loop
    for referenced_object in added_from_the_boundary_set:
        objects_list_ = elements_by_type.get(referenced_object.tpe, None)
        if objects_list_:
            objects_list_.append(referenced_object)
        else:
            elements_by_type[referenced_object.tpe] = [referenced_object]


def convert_data_to_objects(data: Dict[str, Dict[str, Dict[str, str]]],
                            all_objects_dict: Dict[str, IdentifiedObject],
                            all_objects_dict_boundary: Union[Dict[str, IdentifiedObject], None],
                            elements_by_type: Dict[str, List[IdentifiedObject]],
                            class_dict: Dict[str, IdentifiedObject],
                            logger: DataLogger) -> None:
    """
    Convert CGMES data dictionaries to proper CGMES objects
    :param data: source data to convert
    :param all_objects_dict: dictionary of all model objects to add Parsed objects
    :param all_objects_dict_boundary: dictionary of all boundary set objects to
                                      add Parsed objects used to find references
    :param elements_by_type: Dictionary of elements by type to fill in (same as all_objects_dict but by categories)
    :param class_dict: CgmesCircuit or None
    :param logger:DataLogger
    :return: None
    """
    for class_name, objects_dict in data.items():

        objects_list = list()
        for rdfid, object_data in objects_dict.items():

            object_template = class_dict.get(class_name, None)

            if object_template is not None:

                parsed_object = object_template(rdfid=rdfid, tpe=class_name)
                parsed_object.parse_dict(data=object_data, logger=logger)

                found = all_objects_dict.get(parsed_object.rdfid, None)

                if found is None:
                    all_objects_dict[parsed_object.rdfid] = parsed_object
                else:
                    if "Sv" not in class_name:
                        logger.add_error("Duplicated RDFID", device=class_name, value=parsed_object.rdfid)

                objects_list.append(parsed_object)

            else:
                logger.add_error("Class not recognized", device_class=class_name)

        elements_by_type[class_name] = objects_list

    # replace refferences by actual objects
    find_references(elements_by_type=elements_by_type,
                    all_objects_dict=all_objects_dict,
                    all_objects_dict_boundary=all_objects_dict_boundary,
                    logger=logger,
                    mark_used=True)


class CgmesCircuit(BaseCircuit):
    """
    CgmesCircuit
    """

    def __init__(self,
                 text_func: Union[Callable, None] = None,
                 progress_func: Union[Callable, None] = None,
                 logger=DataLogger()):
        """
        CIM circuit constructor
        """
        BaseCircuit.__init__(self)

        self.logger: DataLogger = logger

        self.text_func = text_func
        self.progress_func = progress_func

        self.class_dict = {'IdentifiedObject': IdentifiedObject,
                           'Terminal': Terminal,
                           'BaseVoltage': BaseVoltage,
                           'TopologicalNode': TopologicalNode,
                           'BusbarSection': BusbarSection,
                           'Connector': Connector,
                           'Junction': Junction,
                           'BusNameMarker': BusNameMarker,
                           'Substation': Substation,
                           'ConnectivityNode': ConnectivityNode,
                           'OperationalLimitSet': OperationalLimitSet,
                           'OperationalLimitType': OperationalLimitType,
                           'GeographicalRegion': GeographicalRegion,
                           'SubGeographicalRegion': SubGeographicalRegion,
                           'CGMRegion': CGMRegion,
                           'ModelingAuthority': ModelingAuthority,
                           'MergingAgent': MergingAgent,
                           'VoltageLevel': VoltageLevel,
                           'CurrentLimit': CurrentLimit,
                           'VoltageLimit': VoltageLimit,
                           'EquivalentInjection': EquivalentInjection,
                           'EquivalentNetwork': EquivalentNetwork,
                           'EquivalentBranch': EquivalentBranch,
                           'ControlArea': ControlArea,
                           'ControlAreaGeneratingUnit': ControlAreaGeneratingUnit,
                           'Breaker': Breaker,
                           'Switch': Switch,
                           "LoadBreakSwitch": LoadBreakSwitch,
                           'Line': Line,
                           'ACLineSegment': ACLineSegment,
                           'PowerTransformerEnd': PowerTransformerEnd,
                           'PowerTransformer': PowerTransformer,
                           'PhaseTapChanger': PhaseTapChanger,
                           'PhaseTapChangerNonLinear': PhaseTapChangerNonLinear,
                           'PhaseTapChangerSymmetrical': PhaseTapChangerSymmetrical,
                           'PhaseTapChangerTablePoint': PhaseTapChangerTablePoint,
                           'PhaseTapChangerTable': PhaseTapChangerTable,
                           'PhaseTapChangerTabular': PhaseTapChangerTabular,
                           'EnergyConsumer': EnergyConsumer,
                           'EnergyArea': EnergyArea,
                           'ConformLoad': ConformLoad,
                           'ConformLoadGroup': ConformLoadGroup,
                           'NonConformLoad': NonConformLoad,
                           'NonConformLoadGroup': NonConformLoadGroup,
                           'LoadResponseCharacteristic': LoadResponseCharacteristic,
                           'EnergySchedulingType': EnergySchedulingType,
                           'LoadGroup': LoadGroup,
                           'LoadArea': LoadArea,
                           'SubLoadArea': SubLoadArea,
                           'RegulatingControl': RegulatingControl,
                           'RatioTapChanger': RatioTapChanger,
                           'GeneratingUnit': GeneratingUnit,
                           'SynchronousMachine': SynchronousMachine,
                           'HydroPump': HydroPump,
                           'RotatingMachine': RotatingMachine,
                           # 'HydroGenerationUnit': HydroGeneratingUnit,  # todo: should this exist?
                           'HydroGeneratingUnit': HydroGeneratingUnit,
                           'HydroPowerPlant': HydroPowerPlant,
                           'LinearShuntCompensator': LinearShuntCompensator,
                           'NuclearGeneratingUnit': NuclearGeneratingUnit,
                           'RatioTapChangerTable': RatioTapChangerTable,
                           'RatioTapChangerTablePoint': RatioTapChangerTablePoint,
                           'ReactiveCapabilityCurve': ReactiveCapabilityCurve,
                           'StaticVarCompensator': StaticVarCompensator,
                           'TapChangerControl': TapChangerControl,
                           # 'ThermalGenerationUnit': ThermalGeneratingUnit,  # todo: should this exist?
                           'ThermalGeneratingUnit': ThermalGeneratingUnit,
                           # 'WindGenerationUnit': WindGeneratingUnit,  # todo: should this exist?
                           'WindGeneratingUnit': WindGeneratingUnit,
                           'SolarGeneratingUnit': SolarGeneratingUnit,
                           'FullModel': FullModel,
                           'TopologicalIsland': TopologicalIsland,
                           'TieFlow': TieFlow,
                           'FossilFuel': FossilFuel,
                           'Curve': Curve,
                           'CurveData': CurveData,
                           'SvPowerFlow': SvPowerFlow,
                           'SvVoltage': SvVoltage,
                           'SvShuntCompensatorSections': SvShuntCompensatorSections,
                           'SvTapStep': SvTapStep
                           }

        self.IdentifiedObject_list: List[IdentifiedObject] = list()
        self.Terminal_list: List[Terminal] = list()
        self.BaseVoltage_list: List[BaseVoltage] = list()
        self.TopologicalNode_list: List[TopologicalNode] = list()
        self.BusbarSection_list: List[BusbarSection] = list()
        self.Connector_list: List[Connector] = list()
        self.Junction_list: List[Junction] = list()
        self.BusNameMarker_list: List[BusNameMarker] = list()
        self.Substation_list: List[Substation] = list()
        self.ConnectivityNode_list: List[ConnectivityNode] = list()
        self.OperationalLimitSet_list: List[OperationalLimitSet] = list()
        self.OperationalLimitType_list: List[OperationalLimitType] = list()
        self.GeographicalRegion_list: List[GeographicalRegion] = list()
        self.SubGeographicalRegion_list: List[SubGeographicalRegion] = list()
        self.CGMRegion_list: List[CGMRegion] = list()
        self.ModelingAuthority_list: List[ModelingAuthority] = list()
        self.MergingAgent_list: List[MergingAgent] = list()
        self.VoltageLevel_list: List[VoltageLevel] = list()
        self.CurrentLimit_list: List[CurrentLimit] = list()
        self.VoltageLimit_list: List[VoltageLimit] = list()
        self.EquivalentInjection_list: List[EquivalentInjection] = list()
        self.EquivalentNetwork_list: List[EquivalentNetwork] = list()
        self.EquivalentBranch_list: List[EquivalentBranch] = list()
        self.ControlArea_list: List[ControlArea] = list()
        self.ControlAreaGeneratingUnit_list: List[ControlAreaGeneratingUnit] = list()
        self.Breaker_list: List[Breaker] = list()
        self.Switch_list: List[Switch] = list()
        self.LoadBreakSwitch_list: List[LoadBreakSwitch] = list()
        self.Line_list: List[Line] = list()
        self.ACLineSegment_list: List[ACLineSegment] = list()
        self.PowerTransformerEnd_list: List[PowerTransformerEnd] = list()
        self.PowerTransformer_list: List[PowerTransformer] = list()
        self.PhaseTapChanger_list: List[PhaseTapChanger] = list()
        self.PhaseTapChangerNonLinear_list: List[PhaseTapChangerNonLinear] = list()
        self.PhaseTapChangerSymmetrical_list: List[PhaseTapChangerSymmetrical] = list()
        self.PhaseTapChangerTablePoint_list: List[PhaseTapChangerTablePoint] = list()
        self.PhaseTapChangerTable_list: List[PhaseTapChangerTable] = list()
        self.PhaseTapChangerTabular_list: List[PhaseTapChangerTabular] = list()
        self.EnergyConsumer_list: List[EnergyConsumer] = list()
        self.EnergyArea_list: List[EnergyArea] = list()
        self.ConformLoad_list: List[ConformLoad] = list()
        self.ConformLoadGroup_list: List[ConformLoadGroup] = list()
        self.NonConformLoad_list: List[NonConformLoad] = list()
        self.NonConformLoadGroup_list: List[NonConformLoadGroup] = list()
        self.LoadResponseCharacteristic_list: List[LoadResponseCharacteristic] = list()
        self.EnergySchedulingType_list: List[EnergySchedulingType] = list()
        self.LoadGroup_list: List[LoadGroup] = list()
        self.LoadArea_list: List[LoadArea] = list()
        self.SubLoadArea_list: List[SubLoadArea] = list()
        self.RegulatingControl_list: List[RegulatingControl] = list()
        self.RatioTapChanger_list: List[RatioTapChanger] = list()
        self.GeneratingUnit_list: List[GeneratingUnit] = list()
        self.SynchronousMachine_list: List[SynchronousMachine] = list()
        self.HydroPump_list: List[HydroPump] = list()
        self.RotatingMachine_list: List[RotatingMachine] = list()
        self.HydroGeneratingUnit_list: List[HydroGeneratingUnit] = list()
        self.HydroPowerPlant_list: List[HydroPowerPlant] = list()
        self.LinearShuntCompensator_list: List[LinearShuntCompensator] = list()
        self.NuclearGeneratingUnit_list: List[NuclearGeneratingUnit] = list()
        self.RatioTapChangerTable_list: List[RatioTapChangerTable] = list()
        self.RatioTapChangerTablePoint_list: List[RatioTapChangerTablePoint] = list()
        self.ReactiveCapabilityCurve_list: List[ReactiveCapabilityCurve] = list()
        self.StaticVarCompensator_list: List[StaticVarCompensator] = list()
        self.TapChangerControl_list: List[TapChangerControl] = list()
        self.ThermalGeneratingUnit_list: List[ThermalGeneratingUnit] = list()
        self.WindGeneratingUnit_list: List[WindGeneratingUnit] = list()
        self.SolarGeneratingUnit_list: List[SolarGeneratingUnit] = list()
        self.FullModel_list: List[FullModel] = list()
        self.TopologicalIsland_list: List[TopologicalIsland] = list()
        self.TieFlow_list: List[TieFlow] = list()
        self.FossilFuel_list: List[FossilFuel] = list()
        self.Curve_list: List[Curve] = list()
        self.CurveData_list: List[CurveData] = list()
        self.SvPowerFlow_list: List[SvPowerFlow] = list()
        self.SvVoltage_list: List[SvVoltage] = list()
        self.SvShuntCompensatorSections_list: List[SvShuntCompensatorSections] = list()
        self.SvTapStep_list: List[SvTapStep] = list()

        # classes to read, theo others are ignored
        self.classes = [key for key, va in self.class_dict.items()]

        # dictionary with all objects, usefull to find repeated ID's
        self.all_objects_dict: Dict[str, IdentifiedObject] = dict()
        self.all_objects_dict_boundary: Dict[str, IdentifiedObject] = dict()

        # dictionary with elements by type
        self.elements_by_type: Dict[str, List[IdentifiedObject]] = dict()
        self.elements_by_type_boundary: Dict[str, List[IdentifiedObject]] = dict()

        # dictionary representation of the xml data
        self.data: Dict[str, Dict[str, Dict[str, str]]] = dict()
        self.boundary_set: Dict[str, Dict[str, Dict[str, str]]] = dict()

    def parse_files(self, files: List[str], delete_unused=True, detect_circular_references=False):
        """
        Parse CGMES files into this class
        :param files: list of CGMES files (.zip / .xml)
        :param delete_unused: Detele the unused boundary set?
        :param detect_circular_references: report the circular references
        """

        # read the CGMES data as dictionaries
        data_parser = CgmesDataParser(text_func=self.text_func,
                                      progress_func=self.progress_func,
                                      logger=self.logger)
        data_parser.load_files(files=files)

        # set the data
        self.set_data(data=data_parser.data,
                      boundary_set=data_parser.boudary_set)

        # convert the dictionaries to the internal class model for the boundary set
        # do not mark the boundary set objects as used
        convert_data_to_objects(data=self.boundary_set,
                                all_objects_dict=self.all_objects_dict_boundary,
                                all_objects_dict_boundary=None,
                                elements_by_type=self.elements_by_type_boundary,
                                class_dict=self.class_dict,
                                logger=self.logger)

        # convert the dictionaries to the internal class model,
        # this marks as used only the boundary set objects that are refferenced,
        # this allows to delete the excess of boundary set objects later
        convert_data_to_objects(data=self.data,
                                all_objects_dict=self.all_objects_dict,
                                all_objects_dict_boundary=self.all_objects_dict_boundary,
                                elements_by_type=self.elements_by_type,
                                class_dict=self.class_dict,
                                logger=self.logger)

        # Assign the data from all_objects_dict to the appropriate lists in the circuit
        self.assign_data_to_lists()

        if delete_unused:
            # delete the unused objects from the boundary set
            self.delete_unused()

        if detect_circular_references:
            # for reporting porpuses, detect the circular references in the model due to polymorphism
            self.detect_circular_references()

    def assign_data_to_lists(self) -> None:
        """
        Assign the data from all_objects_dict to the appropriate lists in the circuit
        :return: Nothing
        """
        for object_id, parsed_object in self.all_objects_dict.items():

            # add to its list
            list_name = parsed_object.tpe + '_list'
            if hasattr(self, list_name):
                getattr(self, list_name).append(parsed_object)
            else:
                print('Missing list:', list_name)

    def set_data(self, data: Dict[str, Dict[str, Dict[str, str]]], boundary_set: Dict[str, Dict[str, Dict[str, str]]]):
        """

        :param data:
        :param boundary_set:
        :return:
        """
        self.data = data
        self.boundary_set = boundary_set

    def meta_programmer(self):
        """
        This function is here to help in the class programming by inverse engineering
        :return:
        """
        for key, obj_list in self.class_dict.items():

            if not hasattr(self, key + '_list'):
                print('self.{0}_list: List[{0}] = list()'.format(key))

    def add(self, elm: IdentifiedObject):
        """
        Add generic object to the circuit
        :param elm: any CGMES object
        :return: True if successful, False otherwise
        """
        """
        self.elements = list()
        self.all_objects_dict: Dict[str, cimdev.IdentifiedObject] = dict()
        self.elements_by_type: Dict[str, List[cimdev.IdentifiedObject]] = dict()
        """

        # find if the element was added before
        collided = self.all_objects_dict.get(elm.rdfid, None)

        if collided is not None:
            self.logger.add_error("RDFID collision, element not added",
                                  device_class=elm.tpe,
                                  device=elm.rdfid,
                                  comment="Collided object {0}:{1} ({2})".format(collided.tpe,
                                                                                 collided.rdfid,
                                                                                 collided.shortName))
            return False

        self.all_objects_dict[elm.rdfid] = elm

        if elm.tpe in self.elements_by_type:
            self.elements_by_type[elm.tpe].append(elm)
        else:
            self.elements_by_type[elm.tpe] = [elm]

        # add to its list
        list_name = elm.tpe + '_list'
        if hasattr(self, list_name):
            getattr(self, list_name).append(elm)
        else:
            print('Missing list:', list_name)

        return True

    def get_properties(self) -> List[CgmesProperty]:
        """
        Get list of CIM properties
        :return:
        """
        data = list()
        for name, cls in self.class_dict.items():
            data.append(CgmesProperty(property_name=name, class_type=cls))
        return data

    def get_class_properties(self) -> List[CgmesProperty]:
        """

        :return:
        """
        return [p for p in self.get_properties() if p.class_type not in [str, bool, int, float]]

    def get_objects_list(self, elm_type):
        """

        :param elm_type:
        :return:
        """
        return self.elements_by_type.get(elm_type, [])

    def emit_text(self, val):
        """

        :param val:
        """
        if self.text_func is not None:
            self.text_func(val)

    def emit_progress(self, val):
        """

        :param val:
        """
        if self.progress_func is not None:
            self.progress_func(val)

    def clear(self):
        """
        Clear the circuit
        """
        self.all_objects_dict = dict()
        self.elements_by_type = dict()

    @staticmethod
    def check_type(xml, class_types, starters=['<cim:', '<md:'], enders=['</cim:', '</md:']):
        """
        Checks if we are starting an object of the predefined types
        :param xml: some text
        :param class_types: list of CIM types
        :param starters list of possible string to add prior to the class when opening an object
        :param enders list of possible string to add prior to a class when closing an object
        :return: start_recording, end_recording, the found type or None if no one was found
        """

        # for each type
        for tpe in class_types:

            for starter, ender in zip(starters, enders):
                # if the starter token is found: this is the beginning of an object
                if starter + tpe + ' rdf:ID' in xml:
                    return True, False, tpe

                # if the starter token is found: this is the beginning of an object (only in the topology definition)
                elif starter + tpe + ' rdf:about' in xml:
                    return True, False, tpe

                # if the ender token is found: this is the end of an object
                elif ender + tpe + '>' in xml:
                    return False, True, tpe

        # otherwise, this is neither the beginning nor the end of an object
        return False, False, ""

    def delete_unused(self) -> None:
        """
        Delete elements that have no refferences to them
        """
        elements_by_type = dict()
        all_objects_dict = dict()

        # delete elements without references
        for class_name, elements in self.elements_by_type.items():

            objects_list = list()

            for element in elements:  # for every element of the type

                if element.can_keep():
                    all_objects_dict[element.rdfid] = element
                    objects_list.append(element)
                else:
                    print('deleted', element)

            elements_by_type[class_name] = objects_list

        # replace
        self.elements_by_type = elements_by_type
        self.all_objects_dict = all_objects_dict

    def parse_xml_text(self, text_lines):
        """
        Fill the XML into the objects
        :param text_lines:
        :return:
        """

        xml_string = "".join(text_lines)

        import xml.etree.ElementTree as ET

        def find_id(child: ET.Element):
            """
            Try to find the ID of an element
            :param child: XML element
            :return: RDFID
            """
            obj_id = ''
            for attr, value in child.attrib.items():
                if 'about' in attr.lower() or 'resource' in attr.lower():
                    if ':' in value:
                        obj_id = value.split(':')[-1]
                    else:
                        obj_id = value
                elif 'id' in attr.lower():
                    obj_id = value

            return obj_id.replace('_', '').replace('#', '')

        def find_class_name(child: ET.Element):
            """
            Try to find the CIM class name
            :param child: XML element
            :return: class name
            """
            if '}' in child.tag:
                class_name = child.tag.split('}')[-1]
            else:
                class_name = child.tag

            if '.' in class_name:
                class_name = class_name.split('.')[-1]

            return class_name

        def parse_xml_to_dict(xml_element: ET.Element):
            """
            Parse element into dictionary
            :param xml_element: XML element
            :return: Dictionary representing the XML
            """
            result = dict()

            for child in xml_element:
                # key = child.tag

                obj_id = find_id(child)
                class_name = find_class_name(child)

                if len(child) > 0:
                    child_result = parse_xml_to_dict(child)

                    objects_list = result.get(class_name, None)

                    if objects_list is None:
                        result[class_name] = {obj_id: child_result}
                    else:
                        objects_list[obj_id] = child_result
                else:
                    if child.text is None:
                        result[class_name] = obj_id  # it is a resource id
                    else:
                        result[class_name] = child.text

            return result

        def merge(A: Dict[str, Dict[str, Dict[str, str]]],
                  B: Dict[str, Dict[str, Dict[str, str]]]):
            """
            Modify A using B
            :param A: CIM data dictionary to be modified in-place
            :param B: CIM data dictionary used to modify A
            """
            # for each category in B
            for class_name_b, class_obj_dict_b in B.items():

                class_obj_dict_a = A.get(class_name_b, None)

                if class_obj_dict_a is None:
                    # the category does not exist in A, just copy it from B
                    A[class_name_b] = class_obj_dict_b

                else:

                    # for every object in the category from B
                    for rdfid, obj_b in class_obj_dict_b.items():

                        obj_a = class_obj_dict_a.get(rdfid, None)

                        if obj_a is None:
                            # the object in B does not exist in A, copy it
                            class_obj_dict_a[rdfid] = obj_b
                        else:
                            # the object in B already has an entry in A, modify it

                            # for each property
                            for prop_name, value_b in obj_b.items():

                                value_a = obj_a.get(prop_name, None)

                                if value_a is None:
                                    # the property does not exist in A, add it
                                    obj_a[prop_name] = value_b
                                else:
                                    if value_b != value_a:
                                        # the value exists in A, and the value in B is not None, add it
                                        obj_a[prop_name] = value_b
                                        self.logger.add_warning("Overwriting value",
                                                                device=str(obj_a),
                                                                device_class=class_name_b,
                                                                device_property=prop_name,
                                                                value=value_b,
                                                                expected_value=value_a)
                                    else:
                                        # the assigning value from B is the same as the already stored in A
                                        pass

        root = ET.fromstring(xml_string)
        new_cim_data = parse_xml_to_dict(root)
        merge(self.data, new_cim_data)

    def get_data_frames_dictionary(self):
        """
        Get dictionary of DataFrames
        :return: dictionary of DataFrames
        """
        dfs = dict()
        for class_name, elements in self.elements_by_type.items():
            values = [element.get_dict() for element in elements]
            dfs[class_name] = pd.DataFrame(values)

        return dfs

    def to_excel(self, fname):
        """

        :param fname:
        :return:
        """
        if self.text_func is not None:
            self.text_func('Saving to excel')

        dfs = self.get_data_frames_dictionary()

        keys = list(dfs.keys())
        keys.sort()

        n = len(keys)
        writer = pd.ExcelWriter(fname)
        for i, class_name in enumerate(keys):

            if self.progress_func is not None:
                self.progress_func((i + 1) / n * 100.0)

            if self.text_func is not None:
                self.text_func('Saving {} to excel'.format(class_name))

            df = dfs[class_name]
            df.to_excel(writer, sheet_name=class_name, index=False)
        writer.save()

    def detect_circular_references(self):
        """
        Detect circular references
        """
        for rdfid, elm in self.all_objects_dict.items():
            visited = list()
            is_loop = elm.detect_circular_references(visited)

            if is_loop:
                self.logger.add_warning(msg="Linking loop",
                                        device=elm.rdfid,
                                        device_class=elm.tpe,
                                        value=len(visited))

    def get_circular_references(self) -> List[List[IdentifiedObject]]:
        """
        Detect circular references
        """
        res = list()
        for rdfid, elm in self.all_objects_dict.items():
            visited = list()
            is_loop = elm.detect_circular_references(visited)

            if is_loop:
                res.append([self.all_objects_dict[v] for v in visited])

        return res

    def get_base_voltages(self) -> List[BaseVoltage]:
        """

        :return:
        """
        return self.elements_by_type.get('BaseVoltage', [])

    def get_model_xml(self, profiles: List[cgmesProfile] = [cgmesProfile.EQ]) -> Dict[cgmesProfile, str]:
        """
        Get a dictionary of xml per CGMES profile
        :param profiles: list of profiles to acquire
        :returns Dictionary  Dict[cgmesProfile, str]
        """
        data = dict()
        for tpe, elm_list in self.elements_by_type.items():

            for elm in elm_list:

                elm_data = elm.get_xml(level=0, profiles=profiles)

                for profile, txt in elm_data.items():

                    if profile in data:
                        data[profile] += txt
                    else:
                        data[profile] = txt
        return data

    def get_boundary_voltages_dict(self) -> Dict[float, BaseVoltage]:
        """
        Get the BaseVoltage objects from the boundary set as
        a dictionary with the nominal voltage as key
        :return: Dict[float, BaseVoltage]
        """
        return {e.nominalVoltage: e for e in self.elements_by_type_boundary['BaseVoltage']}
