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

from GridCalEngine.IO.cim.cgmes.cgmes_utils import check_load_response_characteristic, check
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.IO.cim.cgmes.cgmes_poperty import CgmesProperty
from GridCalEngine.IO.base.base_circuit import BaseCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes.cgmes_data_parser import CgmesDataParser

from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.acdc_converter import ACDCConverter
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.acdc_converterdc_terminal import ACDCConverterDCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.cs_converter import CsConverter
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_base_terminal import DCBaseTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_breaker import DCBreaker
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_busbar import DCBusbar
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_chopper import DCChopper
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_conducting_equipment import DCConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_converter_unit import DCConverterUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_disconnector import DCDisconnector
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_equipment_container import DCEquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_ground import DCGround
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_line import DCLine
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_line_segment import DCLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_node import DCNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_series_device import DCSeriesDevice
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_shunt import DCShunt
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_switch import DCSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_terminal import DCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.per_lengthdc_line_parameter import PerLengthDCLineParameter
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.vs_capability_curve import VsCapabilityCurve
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.vs_converter import VsConverter
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.bus_name_marker import BusNameMarker
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.analog_control import AnalogControl
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.control import Control
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.limit import Limit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.limit_set import LimitSet
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.measurement import Measurement
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.measurement_value import MeasurementValue
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.quality61850 import Quality61850
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_scheduling_type import EnergySchedulingType
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_source import EnergySource
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.fossil_fuel import FossilFuel
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.hydro_generating_unit import HydroGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.hydro_power_plant import HydroPowerPlant
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.hydro_pump import HydroPump
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.nuclear_generating_unit import NuclearGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.solar_generating_unit import SolarGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.thermal_generating_unit import ThermalGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.wind_generating_unit import WindGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.acdc_terminal import ACDCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.basic_interval_schedule import BasicIntervalSchedule
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.bay import Bay
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node_container import ConnectivityNodeContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.curve import Curve
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.curve_data import CurveData
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.geographical_region import GeographicalRegion
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regular_interval_schedule import RegularIntervalSchedule
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.reporting_group import ReportingGroup
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sub_geographical_region import SubGeographicalRegion
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.substation import Substation
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.voltage_level import VoltageLevel
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.active_power_limit import ActivePowerLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.apparent_power_limit import ApparentPowerLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.current_limit import CurrentLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit import OperationalLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_set import OperationalLimitSet
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_type import OperationalLimitType
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.voltage_limit import VoltageLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ac_line_segment import ACLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.asynchronous_machine import AsynchronousMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.breaker import Breaker
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.busbar_section import BusbarSection
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conductor import Conductor
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connector import Connector
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.disconnector import Disconnector
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.earth_fault_compensator import EarthFaultCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_consumer import EnergyConsumer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.external_network_injection import ExternalNetworkInjection
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ground import Ground
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ground_disconnector import GroundDisconnector
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.grounding_impedance import GroundingImpedance
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.junction import Junction
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.line import Line
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.linear_shunt_compensator import LinearShuntCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_break_switch import LoadBreakSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.mutual_coupling import MutualCoupling
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.nonlinear_shunt_compensator import NonlinearShuntCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.nonlinear_shunt_compensator_point import \
    NonlinearShuntCompensatorPoint
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.petersen_coil import PetersenCoil
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer import PhaseTapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_asymmetrical import PhaseTapChangerAsymmetrical
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_linear import PhaseTapChangerLinear
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_non_linear import PhaseTapChangerNonLinear
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_symmetrical import PhaseTapChangerSymmetrical
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_table import PhaseTapChangerTable
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_table_point import PhaseTapChangerTablePoint
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_tabular import PhaseTapChangerTabular
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.protected_switch import ProtectedSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ratio_tap_changer import RatioTapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ratio_tap_changer_table import RatioTapChangerTable
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ratio_tap_changer_table_point import RatioTapChangerTablePoint
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.reactive_capability_curve import ReactiveCapabilityCurve
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_control import RegulatingControl
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.rotating_machine import RotatingMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.series_compensator import SeriesCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.shunt_compensator import ShuntCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.static_var_compensator import StaticVarCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.switch import Switch
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.synchronous_machine import SynchronousMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tap_changer import TapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tap_changer_control import TapChangerControl
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tap_changer_table_point import TapChangerTablePoint
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.transformer_end import TransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conform_load import ConformLoad
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conform_load_group import ConformLoadGroup
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_area import EnergyArea
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_area import LoadArea
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_group import LoadGroup
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_response_characteristic import LoadResponseCharacteristic
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.non_conform_load import NonConformLoad
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.non_conform_load_group import NonConformLoadGroup
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.season_day_type_schedule import SeasonDayTypeSchedule
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sub_load_area import SubLoadArea
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equivalent_branch import EquivalentBranch
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equivalent_equipment import EquivalentEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equivalent_injection import EquivalentInjection
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equivalent_network import EquivalentNetwork
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equivalent_shunt import EquivalentShunt
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.control_area import ControlArea
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.control_area_generating_unit import ControlAreaGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tie_flow import TieFlow
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_topological_island import DCTopologicalIsland
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_status import SvStatus
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_injection import SvInjection
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_power_flow import SvPowerFlow
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_shunt_compensator_sections import SvShuntCompensatorSections
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_tap_step import SvTapStep
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_voltage import SvVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_topological_node import DCTopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_island import TopologicalIsland
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.coordinate_system import CoordinateSystem
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.location import Location
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.position_point import PositionPoint

from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.full_model import FullModel


def find_attribute(referenced_object, obj, property_name, association_inverse_dict):
    for inverse, current in association_inverse_dict.items():
        c_class = str(current).split('.')[0]
        c_prop = str(current).split('.')[-1]
        if isinstance(obj, globals()[c_class]) and c_prop == property_name:
            i_class = str(inverse).split('.')[0]
            i_prop = str(inverse).split('.')[-1]
            if isinstance(referenced_object, globals()[i_class]) and i_prop in vars(referenced_object):
                return i_prop
            else:
                continue
        else:
            continue
    return None


def find_references(elements_by_type: Dict[str, List[IdentifiedObject]],
                    all_objects_dict: Dict[str, IdentifiedObject],
                    all_objects_dict_boundary: Union[Dict[str, IdentifiedObject], None],
                    association_inverse_dict,
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
                if value is not None and isinstance(value, IdentifiedObject):
                    value = value.rdfid

                if value is not None:  # if the value is something...

                    if cim_prop.class_type in [str, float, int, bool]:
                        # set the referenced object in the property
                        try:
                            if isinstance(value, list):
                                setattr(element, property_name, value)
                            else:
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
                        if not isinstance(value, list):
                            referenced_object = all_objects_dict.get(value, None)

                            if referenced_object is None and all_objects_dict_boundary:
                                # search for the reference in the boundary set
                                referenced_object = all_objects_dict_boundary.get(value, None)

                                # add to the normal data if it wasn't added before
                                if referenced_object is not None and referenced_object.rdfid not in all_objects_dict:
                                    all_objects_dict[referenced_object.rdfid] = referenced_object
                                    added_from_the_boundary_set.append(referenced_object)

                            # if the reference was found in the data of the boundary set ...
                            if referenced_object is not None:
                                if mark_used:
                                    referenced_object.used = True

                                # set the referenced object in the property
                                setattr(element, property_name, referenced_object)

                                # register the inverse reference
                                referenced_object.add_reference(element,
                                                                find_attribute(referenced_object=referenced_object,
                                                                               obj=element,
                                                                               property_name=property_name,
                                                                               association_inverse_dict=association_inverse_dict))

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
                        else:
                            referenced_object_list = set()
                            for v in value:
                                if isinstance(v, IdentifiedObject):
                                    v = v.rdfid

                                referenced_object = all_objects_dict.get(v, None)

                                if referenced_object is None and all_objects_dict_boundary:
                                    # search for the reference in the boundary set
                                    referenced_object = all_objects_dict_boundary.get(v, None)

                                    # add to the normal data if it wasn't added before
                                    if referenced_object is not None and referenced_object.rdfid not in all_objects_dict:
                                        all_objects_dict[referenced_object.rdfid] = referenced_object
                                        added_from_the_boundary_set.append(referenced_object)

                                # if the reference was found in the data of the boundary set ...
                                if referenced_object is not None:
                                    if mark_used:
                                        referenced_object.used = True

                                    # set the referenced object in the property
                                    referenced_object_list.add(referenced_object)

                                    # register the inverse reference
                                    referenced_object.add_reference(element,
                                                                    find_attribute(referenced_object=referenced_object,
                                                                                   obj=element,
                                                                                   property_name=property_name,
                                                                                   association_inverse_dict=association_inverse_dict))

                                    # check that the type matches the expected type
                                    if cim_prop.class_type in [ConnectivityNodeContainer, IdentifiedObject]:
                                        # the container class is too generic...
                                        pass
                                    else:
                                        if not isinstance(referenced_object, cim_prop.class_type) and \
                                                cim_prop.class_type != EquipmentContainer:
                                            # if the class specification does not match but the
                                            # required type is also not a generic polymorphic object ...
                                            cls = str(cim_prop.class_type).split('.')[-1].replace("'", "").replace(">",
                                                                                                                   "")
                                            logger.add_error(msg='Object type different from expected',
                                                             device=element.rdfid,
                                                             device_class=class_name,
                                                             device_property=property_name,
                                                             value=referenced_object.tpe,
                                                             expected_value=cls)
                                else:

                                    # I want to know that it was not found
                                    element.missing_references[property_name] = v

                                    if hasattr(element, 'rdfid'):
                                        logger.add_error(msg='Reference not found',
                                                         device=element.rdfid,
                                                         device_class=class_name,
                                                         device_property=property_name,
                                                         value='Not found',
                                                         expected_value=v)
                                    else:
                                        logger.add_error(msg='Reference not found for (debugger error)',
                                                         device=element.rdfid,
                                                         device_class=class_name,
                                                         device_property=property_name,
                                                         value='Not found',
                                                         expected_value=v)
                            if len(referenced_object_list) > 1:
                                setattr(element, property_name, list(referenced_object_list))
                            elif len(referenced_object_list) == 1:
                                setattr(element, property_name, list(referenced_object_list)[0])

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
            # todo: is it Ok?
            if isinstance(element, LoadResponseCharacteristic):
                check_load_response_characteristic(load_response_characteristic=element, logger=logger)
            else:
                check(logger=logger)

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
                            association_inverse_dict,
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
                    association_inverse_dict=association_inverse_dict,
                    logger=logger,
                    mark_used=True)


class CgmesCircuit(BaseCircuit):
    """
    CgmesCircuit
    """

    def __init__(self,
                 cgmes_version: str = "",
                 text_func: Union[Callable, None] = None,
                 progress_func: Union[Callable, None] = None,
                 logger=DataLogger()):
        """
        CIM circuit constructor
        """
        BaseCircuit.__init__(self)

        self.cgmes_version = cgmes_version
        self.logger: DataLogger = logger

        self.text_func = text_func
        self.progress_func = progress_func

        self.class_dict = {
            'ACDCConverter': ACDCConverter,
            'ACDCConverterDCTerminal': ACDCConverterDCTerminal,
            'CsConverter': CsConverter,
            'DCBaseTerminal': DCBaseTerminal,
            'DCBreaker': DCBreaker,
            'DCBusbar': DCBusbar,
            'DCChopper': DCChopper,
            'DCConductingEquipment': DCConductingEquipment,
            'DCConverterUnit': DCConverterUnit,
            'DCDisconnector': DCDisconnector,
            'DCEquipmentContainer': DCEquipmentContainer,
            'DCGround': DCGround,
            'DCLine': DCLine,
            'DCLineSegment': DCLineSegment,
            'DCNode': DCNode,
            'DCSeriesDevice': DCSeriesDevice,
            'DCShunt': DCShunt,
            'DCSwitch': DCSwitch,
            'DCTerminal': DCTerminal,
            'PerLengthDCLineParameter': PerLengthDCLineParameter,
            'VsCapabilityCurve': VsCapabilityCurve,
            'VsConverter': VsConverter,
            'BusNameMarker': BusNameMarker,
            'AnalogControl': AnalogControl,
            'Control': Control,
            'Limit': Limit,
            'LimitSet': LimitSet,
            'Measurement': Measurement,
            'MeasurementValue': MeasurementValue,
            'Quality61850': Quality61850,
            'EnergySchedulingType': EnergySchedulingType,
            'EnergySource': EnergySource,
            'FossilFuel': FossilFuel,
            'GeneratingUnit': GeneratingUnit,
            'HydroGeneratingUnit': HydroGeneratingUnit,
            'HydroPowerPlant': HydroPowerPlant,
            'HydroPump': HydroPump,
            'NuclearGeneratingUnit': NuclearGeneratingUnit,
            'SolarGeneratingUnit': SolarGeneratingUnit,
            'ThermalGeneratingUnit': ThermalGeneratingUnit,
            'WindGeneratingUnit': WindGeneratingUnit,
            'ACDCTerminal': ACDCTerminal,
            'BaseVoltage': BaseVoltage,
            'BasicIntervalSchedule': BasicIntervalSchedule,
            'Bay': Bay,
            'ConductingEquipment': ConductingEquipment,
            'ConnectivityNode': ConnectivityNode,
            'ConnectivityNodeContainer': ConnectivityNodeContainer,
            'Curve': Curve,
            'CurveData': CurveData,
            'Equipment': Equipment,
            'EquipmentContainer': EquipmentContainer,
            'GeographicalRegion': GeographicalRegion,
            'IdentifiedObject': IdentifiedObject,
            'PowerSystemResource': PowerSystemResource,
            'RegularIntervalSchedule': RegularIntervalSchedule,
            'ReportingGroup': ReportingGroup,
            'SubGeographicalRegion': SubGeographicalRegion,
            'Substation': Substation,
            'Terminal': Terminal,
            'VoltageLevel': VoltageLevel,
            'ActivePowerLimit': ActivePowerLimit,
            'ApparentPowerLimit': ApparentPowerLimit,
            'CurrentLimit': CurrentLimit,
            'OperationalLimit': OperationalLimit,
            'OperationalLimitSet': OperationalLimitSet,
            'OperationalLimitType': OperationalLimitType,
            'VoltageLimit': VoltageLimit,
            'ACLineSegment': ACLineSegment,
            'AsynchronousMachine': AsynchronousMachine,
            'Breaker': Breaker,
            'BusbarSection': BusbarSection,
            'Conductor': Conductor,
            'Connector': Connector,
            'Disconnector': Disconnector,
            'EarthFaultCompensator': EarthFaultCompensator,
            'EnergyConsumer': EnergyConsumer,
            'ExternalNetworkInjection': ExternalNetworkInjection,
            'Ground': Ground,
            'GroundDisconnector': GroundDisconnector,
            'GroundingImpedance': GroundingImpedance,
            'Junction': Junction,
            'Line': Line,
            'LinearShuntCompensator': LinearShuntCompensator,
            'LoadBreakSwitch': LoadBreakSwitch,
            'MutualCoupling': MutualCoupling,
            'NonlinearShuntCompensator': NonlinearShuntCompensator,
            'NonlinearShuntCompensatorPoint': NonlinearShuntCompensatorPoint,
            'PetersenCoil': PetersenCoil,
            'PhaseTapChanger': PhaseTapChanger,
            'PhaseTapChangerAsymmetrical': PhaseTapChangerAsymmetrical,
            'PhaseTapChangerLinear': PhaseTapChangerLinear,
            'PhaseTapChangerNonLinear': PhaseTapChangerNonLinear,
            'PhaseTapChangerSymmetrical': PhaseTapChangerSymmetrical,
            'PhaseTapChangerTable': PhaseTapChangerTable,
            'PhaseTapChangerTablePoint': PhaseTapChangerTablePoint,
            'PhaseTapChangerTabular': PhaseTapChangerTabular,
            'PowerTransformer': PowerTransformer,
            'PowerTransformerEnd': PowerTransformerEnd,
            'ProtectedSwitch': ProtectedSwitch,
            'RatioTapChanger': RatioTapChanger,
            'RatioTapChangerTable': RatioTapChangerTable,
            'RatioTapChangerTablePoint': RatioTapChangerTablePoint,
            'ReactiveCapabilityCurve': ReactiveCapabilityCurve,
            'RegulatingCondEq': RegulatingCondEq,
            'RegulatingControl': RegulatingControl,
            'RotatingMachine': RotatingMachine,
            'SeriesCompensator': SeriesCompensator,
            'ShuntCompensator': ShuntCompensator,
            'StaticVarCompensator': StaticVarCompensator,
            'Switch': Switch,
            'SynchronousMachine': SynchronousMachine,
            'TapChanger': TapChanger,
            'TapChangerControl': TapChangerControl,
            'TapChangerTablePoint': TapChangerTablePoint,
            'TransformerEnd': TransformerEnd,
            'ConformLoad': ConformLoad,
            'ConformLoadGroup': ConformLoadGroup,
            'EnergyArea': EnergyArea,
            'LoadArea': LoadArea,
            'LoadGroup': LoadGroup,
            'LoadResponseCharacteristic': LoadResponseCharacteristic,
            'NonConformLoad': NonConformLoad,
            'NonConformLoadGroup': NonConformLoadGroup,
            'SeasonDayTypeSchedule': SeasonDayTypeSchedule,
            'SubLoadArea': SubLoadArea,
            'EquivalentBranch': EquivalentBranch,
            'EquivalentEquipment': EquivalentEquipment,
            'EquivalentInjection': EquivalentInjection,
            'EquivalentNetwork': EquivalentNetwork,
            'EquivalentShunt': EquivalentShunt,
            'ControlArea': ControlArea,
            'ControlAreaGeneratingUnit': ControlAreaGeneratingUnit,
            'TieFlow': TieFlow,
            'DCTopologicalIsland': DCTopologicalIsland,
            'SvStatus': SvStatus,
            'SvInjection': SvInjection,
            'SvPowerFlow': SvPowerFlow,
            'SvShuntCompensatorSections': SvShuntCompensatorSections,
            'SvTapStep': SvTapStep,
            'SvVoltage': SvVoltage,
            'DCTopologicalNode': DCTopologicalNode,
            'TopologicalNode': TopologicalNode,
            'TopologicalIsland': TopologicalIsland,
            'CoordinateSystem': CoordinateSystem,
            'Location': Location,
            'PositionPoint': PositionPoint,
            'FullModel': FullModel,
        }

        self.association_inverse_dict = {
            'ACDCConverterDCTerminal.DCConductingEquipment': 'ACDCConverter.DCTerminals',
            'Terminal.ConverterDCSides': 'ACDCConverter.PccTerminal',
            'ACDCConverter.DCTerminals': 'ACDCConverterDCTerminal.DCConductingEquipment',
            'DCNode.DCTerminals': 'DCBaseTerminal.DCNode',
            'DCTopologicalNode.DCTerminals': 'DCBaseTerminal.DCTopologicalNode',
            'DCTerminal.DCConductingEquipment': 'DCConductingEquipment.DCTerminals',
            'Substation.DCConverterUnit': 'DCConverterUnit.Substation',
            'DCNode.DCEquipmentContainer': 'DCEquipmentContainer.DCNodes',
            'DCTopologicalNode.DCEquipmentContainer': 'DCEquipmentContainer.DCTopologicalNode',
            'SubGeographicalRegion.DCLines': 'DCLine.Region',
            'PerLengthDCLineParameter.DCLineSegments': 'DCLineSegment.PerLengthParameter',
            'DCBaseTerminal.DCNode': 'DCNode.DCTerminals',
            'DCEquipmentContainer.DCNodes': 'DCNode.DCEquipmentContainer',
            'DCTopologicalNode.DCNodes': 'DCNode.DCTopologicalNode',
            'DCConductingEquipment.DCTerminals': 'DCTerminal.DCConductingEquipment',
            'DCLineSegment.PerLengthParameter': 'PerLengthDCLineParameter.DCLineSegments',
            'VsConverter.CapabilityCurve': 'VsCapabilityCurve.VsConverterDCSides',
            'VsCapabilityCurve.VsConverterDCSides': 'VsConverter.CapabilityCurve',
            'ReportingGroup.BusNameMarker': 'BusNameMarker.ReportingGroup',
            'ACDCTerminal.BusNameMarker': 'BusNameMarker.Terminal',
            'PowerSystemResource.Controls': 'Control.PowerSystemResource',
            'ACDCTerminal.Measurements': 'Measurement.Terminal',
            'PowerSystemResource.Measurements': 'Measurement.PowerSystemResource',
            'EnergySource.EnergySchedulingType': 'EnergySchedulingType.EnergySource',
            'EnergySchedulingType.EnergySource': 'EnergySource.EnergySchedulingType',
            'ThermalGeneratingUnit.FossilFuels': 'FossilFuel.ThermalGeneratingUnit',
            'ControlAreaGeneratingUnit.GeneratingUnit': 'GeneratingUnit.ControlAreaGeneratingUnit',
            'RotatingMachine.GeneratingUnit': 'GeneratingUnit.RotatingMachine',
            'HydroPowerPlant.HydroGeneratingUnits': 'HydroGeneratingUnit.HydroPowerPlant',
            'HydroGeneratingUnit.HydroPowerPlant': 'HydroPowerPlant.HydroGeneratingUnits',
            'HydroPump.HydroPowerPlant': 'HydroPowerPlant.HydroPumps',
            'HydroPowerPlant.HydroPumps': 'HydroPump.HydroPowerPlant',
            'RotatingMachine.HydroPump': 'HydroPump.RotatingMachine',
            'FossilFuel.ThermalGeneratingUnit': 'ThermalGeneratingUnit.FossilFuels',
            'BusNameMarker.Terminal': 'ACDCTerminal.BusNameMarker',
            'Measurement.Terminal': 'ACDCTerminal.Measurements',
            'OperationalLimitSet.Terminal': 'ACDCTerminal.OperationalLimitSet',
            'ConductingEquipment.BaseVoltage': 'BaseVoltage.ConductingEquipment',
            'VoltageLevel.BaseVoltage': 'BaseVoltage.VoltageLevel',
            'TransformerEnd.BaseVoltage': 'BaseVoltage.TransformerEnds',
            'TopologicalNode.BaseVoltage': 'BaseVoltage.TopologicalNode',
            'VoltageLevel.Bays': 'Bay.VoltageLevel',
            'BaseVoltage.ConductingEquipment': 'ConductingEquipment.BaseVoltage',
            'Terminal.ConductingEquipment': 'ConductingEquipment.Terminals',
            'SvStatus.ConductingEquipment': 'ConductingEquipment.SvStatus',
            'Terminal.ConnectivityNode': 'ConnectivityNode.Terminals',
            'ConnectivityNodeContainer.ConnectivityNodes': 'ConnectivityNode.ConnectivityNodeContainer',
            'TopologicalNode.ConnectivityNodes': 'ConnectivityNode.TopologicalNode',
            'ConnectivityNode.ConnectivityNodeContainer': 'ConnectivityNodeContainer.ConnectivityNodes',
            'TopologicalNode.ConnectivityNodeContainer': 'ConnectivityNodeContainer.TopologicalNode',
            'CurveData.Curve': 'Curve.CurveDatas',
            'Curve.CurveDatas': 'CurveData.Curve',
            'EquipmentContainer.Equipments': 'Equipment.EquipmentContainer',
            'OperationalLimitSet.Equipment': 'Equipment.OperationalLimitSet',
            'Equipment.EquipmentContainer': 'EquipmentContainer.Equipments',
            'SubGeographicalRegion.Region': 'GeographicalRegion.Regions',
            'Control.PowerSystemResource': 'PowerSystemResource.Controls',
            'Measurement.PowerSystemResource': 'PowerSystemResource.Measurements',
            'Location.PowerSystemResources': 'PowerSystemResource.Location',
            'BusNameMarker.ReportingGroup': 'ReportingGroup.BusNameMarker',
            'TopologicalNode.ReportingGroup': 'ReportingGroup.TopologicalNode',
            'DCLine.Region': 'SubGeographicalRegion.DCLines',
            'GeographicalRegion.Regions': 'SubGeographicalRegion.Region',
            'Line.Region': 'SubGeographicalRegion.Lines',
            'Substation.Region': 'SubGeographicalRegion.Substations',
            'DCConverterUnit.Substation': 'Substation.DCConverterUnit',
            'SubGeographicalRegion.Substations': 'Substation.Region',
            'VoltageLevel.Substation': 'Substation.VoltageLevels',
            'ACDCConverter.PccTerminal': 'Terminal.ConverterDCSides',
            'ConductingEquipment.Terminals': 'Terminal.ConductingEquipment',
            'ConnectivityNode.Terminals': 'Terminal.ConnectivityNode',
            'MutualCoupling.First_Terminal': 'Terminal.HasFirstMutualCoupling',
            'MutualCoupling.Second_Terminal': 'Terminal.HasSecondMutualCoupling',
            'RegulatingControl.Terminal': 'Terminal.RegulatingControl',
            'TieFlow.Terminal': 'Terminal.TieFlow',
            'TransformerEnd.Terminal': 'Terminal.TransformerEnd',
            'SvPowerFlow.Terminal': 'Terminal.SvPowerFlow',
            'TopologicalNode.Terminal': 'Terminal.TopologicalNode',
            'BaseVoltage.VoltageLevel': 'VoltageLevel.BaseVoltage',
            'Bay.VoltageLevel': 'VoltageLevel.Bays',
            'Substation.VoltageLevels': 'VoltageLevel.Substation',
            'OperationalLimitSet.OperationalLimitValue': 'OperationalLimit.OperationalLimitSet',
            'OperationalLimitType.OperationalLimit': 'OperationalLimit.OperationalLimitType',
            'ACDCTerminal.OperationalLimitSet': 'OperationalLimitSet.Terminal',
            'Equipment.OperationalLimitSet': 'OperationalLimitSet.Equipment',
            'OperationalLimit.OperationalLimitSet': 'OperationalLimitSet.OperationalLimitValue',
            'OperationalLimit.OperationalLimitType': 'OperationalLimitType.OperationalLimit',
            'LoadResponseCharacteristic.EnergyConsumer': 'EnergyConsumer.LoadResponse',
            'SubGeographicalRegion.Lines': 'Line.Region',
            'Terminal.HasFirstMutualCoupling': 'MutualCoupling.First_Terminal',
            'Terminal.HasSecondMutualCoupling': 'MutualCoupling.Second_Terminal',
            'NonlinearShuntCompensatorPoint.NonlinearShuntCompensator': 'NonlinearShuntCompensator.NonlinearShuntCompensatorPoints',
            'NonlinearShuntCompensator.NonlinearShuntCompensatorPoints': 'NonlinearShuntCompensatorPoint.NonlinearShuntCompensator',
            'TransformerEnd.PhaseTapChanger': 'PhaseTapChanger.TransformerEnd',
            'PhaseTapChangerTablePoint.PhaseTapChangerTable': 'PhaseTapChangerTable.PhaseTapChangerTablePoint',
            'PhaseTapChangerTabular.PhaseTapChangerTable': 'PhaseTapChangerTable.PhaseTapChangerTabular',
            'PhaseTapChangerTable.PhaseTapChangerTablePoint': 'PhaseTapChangerTablePoint.PhaseTapChangerTable',
            'PhaseTapChangerTable.PhaseTapChangerTabular': 'PhaseTapChangerTabular.PhaseTapChangerTable',
            'PowerTransformerEnd.PowerTransformer': 'PowerTransformer.PowerTransformerEnd',
            'PowerTransformer.PowerTransformerEnd': 'PowerTransformerEnd.PowerTransformer',
            'RatioTapChangerTable.RatioTapChanger': 'RatioTapChanger.RatioTapChangerTable',
            'TransformerEnd.RatioTapChanger': 'RatioTapChanger.TransformerEnd',
            'RatioTapChanger.RatioTapChangerTable': 'RatioTapChangerTable.RatioTapChanger',
            'RatioTapChangerTablePoint.RatioTapChangerTable': 'RatioTapChangerTable.RatioTapChangerTablePoint',
            'RatioTapChangerTable.RatioTapChangerTablePoint': 'RatioTapChangerTablePoint.RatioTapChangerTable',
            'EquivalentInjection.ReactiveCapabilityCurve': 'ReactiveCapabilityCurve.EquivalentInjection',
            'SynchronousMachine.InitialReactiveCapabilityCurve': 'ReactiveCapabilityCurve.InitiallyUsedBySynchronousMachines',
            'RegulatingControl.RegulatingCondEq': 'RegulatingCondEq.RegulatingControl',
            'Terminal.RegulatingControl': 'RegulatingControl.Terminal',
            'RegulatingCondEq.RegulatingControl': 'RegulatingControl.RegulatingCondEq',
            'GeneratingUnit.RotatingMachine': 'RotatingMachine.GeneratingUnit',
            'HydroPump.RotatingMachine': 'RotatingMachine.HydroPump',
            'SvShuntCompensatorSections.ShuntCompensator': 'ShuntCompensator.SvShuntCompensatorSections',
            'ReactiveCapabilityCurve.InitiallyUsedBySynchronousMachines': 'SynchronousMachine.InitialReactiveCapabilityCurve',
            'TapChangerControl.TapChanger': 'TapChanger.TapChangerControl',
            'SvTapStep.TapChanger': 'TapChanger.SvTapStep',
            'TapChanger.TapChangerControl': 'TapChangerControl.TapChanger',
            'BaseVoltage.TransformerEnds': 'TransformerEnd.BaseVoltage',
            'Terminal.TransformerEnd': 'TransformerEnd.Terminal',
            'PhaseTapChanger.TransformerEnd': 'TransformerEnd.PhaseTapChanger',
            'RatioTapChanger.TransformerEnd': 'TransformerEnd.RatioTapChanger',
            'ConformLoadGroup.EnergyConsumers': 'ConformLoad.LoadGroup',
            'ConformLoad.LoadGroup': 'ConformLoadGroup.EnergyConsumers',
            'ControlArea.EnergyArea': 'EnergyArea.ControlArea',
            'SubLoadArea.LoadArea': 'LoadArea.SubLoadAreas',
            'SubLoadArea.LoadGroups': 'LoadGroup.SubLoadArea',
            'EnergyConsumer.LoadResponse': 'LoadResponseCharacteristic.EnergyConsumer',
            'NonConformLoadGroup.EnergyConsumers': 'NonConformLoad.LoadGroup',
            'NonConformLoad.LoadGroup': 'NonConformLoadGroup.EnergyConsumers',
            'LoadArea.SubLoadAreas': 'SubLoadArea.LoadArea',
            'LoadGroup.SubLoadArea': 'SubLoadArea.LoadGroups',
            'EquivalentNetwork.EquivalentEquipments': 'EquivalentEquipment.EquivalentNetwork',
            'ReactiveCapabilityCurve.EquivalentInjection': 'EquivalentInjection.ReactiveCapabilityCurve',
            'EquivalentEquipment.EquivalentNetwork': 'EquivalentNetwork.EquivalentEquipments',
            'EnergyArea.ControlArea': 'ControlArea.EnergyArea',
            'TieFlow.ControlArea': 'ControlArea.TieFlow',
            'ControlAreaGeneratingUnit.ControlArea': 'ControlArea.ControlAreaGeneratingUnit',
            'GeneratingUnit.ControlAreaGeneratingUnit': 'ControlAreaGeneratingUnit.GeneratingUnit',
            'ControlArea.ControlAreaGeneratingUnit': 'ControlAreaGeneratingUnit.ControlArea',
            'Terminal.TieFlow': 'TieFlow.Terminal',
            'ControlArea.TieFlow': 'TieFlow.ControlArea',
            'DCTopologicalNode.DCTopologicalIsland': 'DCTopologicalIsland.DCTopologicalNodes',
            'ConductingEquipment.SvStatus': 'SvStatus.ConductingEquipment',
            'TopologicalNode.SvInjection': 'SvInjection.TopologicalNode',
            'Terminal.SvPowerFlow': 'SvPowerFlow.Terminal',
            'ShuntCompensator.SvShuntCompensatorSections': 'SvShuntCompensatorSections.ShuntCompensator',
            'TapChanger.SvTapStep': 'SvTapStep.TapChanger',
            'TopologicalNode.SvVoltage': 'SvVoltage.TopologicalNode',
            'DCTopologicalIsland.DCTopologicalNodes': 'DCTopologicalNode.DCTopologicalIsland',
            'DCBaseTerminal.DCTopologicalNode': 'DCTopologicalNode.DCTerminals',
            'DCEquipmentContainer.DCTopologicalNode': 'DCTopologicalNode.DCEquipmentContainer',
            'DCNode.DCTopologicalNode': 'DCTopologicalNode.DCNodes',
            'SvInjection.TopologicalNode': 'TopologicalNode.SvInjection',
            'SvVoltage.TopologicalNode': 'TopologicalNode.SvVoltage',
            'TopologicalIsland.AngleRefTopologicalNode': 'TopologicalNode.AngleRefTopologicalIsland',
            'TopologicalIsland.TopologicalNodes': 'TopologicalNode.TopologicalIsland',
            'BaseVoltage.TopologicalNode': 'TopologicalNode.BaseVoltage',
            'ConnectivityNode.TopologicalNode': 'TopologicalNode.ConnectivityNodes',
            'ConnectivityNodeContainer.TopologicalNode': 'TopologicalNode.ConnectivityNodeContainer',
            'ReportingGroup.TopologicalNode': 'TopologicalNode.ReportingGroup',
            'Terminal.TopologicalNode': 'TopologicalNode.Terminal',
            'TopologicalNode.AngleRefTopologicalIsland': 'TopologicalIsland.AngleRefTopologicalNode',
            'TopologicalNode.TopologicalIsland': 'TopologicalIsland.TopologicalNodes',
            'Location.CoordinateSystem': 'CoordinateSystem.Location',
            'CoordinateSystem.Location': 'Location.CoordinateSystem',
            'PowerSystemResource.Location': 'Location.PowerSystemResources',
            'PositionPoint.Location': 'Location.PositionPoints',
            'Location.PositionPoints': 'PositionPoint.Location',
        }

        self.ACDCConverter_list: List[ACDCConverter] = list()
        self.ACDCConverterDCTerminal_list: List[ACDCConverterDCTerminal] = list()
        self.CsConverter_list: List[CsConverter] = list()
        self.DCBaseTerminal_list: List[DCBaseTerminal] = list()
        self.DCBreaker_list: List[DCBreaker] = list()
        self.DCBusbar_list: List[DCBusbar] = list()
        self.DCChopper_list: List[DCChopper] = list()
        self.DCConductingEquipment_list: List[DCConductingEquipment] = list()
        self.DCConverterUnit_list: List[DCConverterUnit] = list()
        self.DCDisconnector_list: List[DCDisconnector] = list()
        self.DCEquipmentContainer_list: List[DCEquipmentContainer] = list()
        self.DCGround_list: List[DCGround] = list()
        self.DCLine_list: List[DCLine] = list()
        self.DCLineSegment_list: List[DCLineSegment] = list()
        self.DCNode_list: List[DCNode] = list()
        self.DCSeriesDevice_list: List[DCSeriesDevice] = list()
        self.DCShunt_list: List[DCShunt] = list()
        self.DCSwitch_list: List[DCSwitch] = list()
        self.DCTerminal_list: List[DCTerminal] = list()
        self.PerLengthDCLineParameter_list: List[PerLengthDCLineParameter] = list()
        self.VsCapabilityCurve_list: List[VsCapabilityCurve] = list()
        self.VsConverter_list: List[VsConverter] = list()
        self.BusNameMarker_list: List[BusNameMarker] = list()
        self.AnalogControl_list: List[AnalogControl] = list()
        self.Control_list: List[Control] = list()
        self.Limit_list: List[Limit] = list()
        self.LimitSet_list: List[LimitSet] = list()
        self.Measurement_list: List[Measurement] = list()
        self.MeasurementValue_list: List[MeasurementValue] = list()
        self.Quality61850_list: List[Quality61850] = list()
        self.EnergySchedulingType_list: List[EnergySchedulingType] = list()
        self.EnergySource_list: List[EnergySource] = list()
        self.FossilFuel_list: List[FossilFuel] = list()
        self.GeneratingUnit_list: List[GeneratingUnit] = list()
        self.HydroGeneratingUnit_list: List[HydroGeneratingUnit] = list()
        self.HydroPowerPlant_list: List[HydroPowerPlant] = list()
        self.HydroPump_list: List[HydroPump] = list()
        self.NuclearGeneratingUnit_list: List[NuclearGeneratingUnit] = list()
        self.SolarGeneratingUnit_list: List[SolarGeneratingUnit] = list()
        self.ThermalGeneratingUnit_list: List[ThermalGeneratingUnit] = list()
        self.WindGeneratingUnit_list: List[WindGeneratingUnit] = list()
        self.ACDCTerminal_list: List[ACDCTerminal] = list()
        self.BaseVoltage_list: List[BaseVoltage] = list()
        self.BasicIntervalSchedule_list: List[BasicIntervalSchedule] = list()
        self.Bay_list: List[Bay] = list()
        self.ConductingEquipment_list: List[ConductingEquipment] = list()
        self.ConnectivityNode_list: List[ConnectivityNode] = list()
        self.ConnectivityNodeContainer_list: List[ConnectivityNodeContainer] = list()
        self.Curve_list: List[Curve] = list()
        self.CurveData_list: List[CurveData] = list()
        self.Equipment_list: List[Equipment] = list()
        self.EquipmentContainer_list: List[EquipmentContainer] = list()
        self.GeographicalRegion_list: List[GeographicalRegion] = list()
        self.IdentifiedObject_list: List[IdentifiedObject] = list()
        self.PowerSystemResource_list: List[PowerSystemResource] = list()
        self.RegularIntervalSchedule_list: List[RegularIntervalSchedule] = list()
        self.ReportingGroup_list: List[ReportingGroup] = list()
        self.SubGeographicalRegion_list: List[SubGeographicalRegion] = list()
        self.Substation_list: List[Substation] = list()
        self.Terminal_list: List[Terminal] = list()
        self.VoltageLevel_list: List[VoltageLevel] = list()
        self.ActivePowerLimit_list: List[ActivePowerLimit] = list()
        self.ApparentPowerLimit_list: List[ApparentPowerLimit] = list()
        self.CurrentLimit_list: List[CurrentLimit] = list()
        self.OperationalLimit_list: List[OperationalLimit] = list()
        self.OperationalLimitSet_list: List[OperationalLimitSet] = list()
        self.OperationalLimitType_list: List[OperationalLimitType] = list()
        self.VoltageLimit_list: List[VoltageLimit] = list()
        self.ACLineSegment_list: List[ACLineSegment] = list()
        self.AsynchronousMachine_list: List[AsynchronousMachine] = list()
        self.Breaker_list: List[Breaker] = list()
        self.BusbarSection_list: List[BusbarSection] = list()
        self.Conductor_list: List[Conductor] = list()
        self.Connector_list: List[Connector] = list()
        self.Disconnector_list: List[Disconnector] = list()
        self.EarthFaultCompensator_list: List[EarthFaultCompensator] = list()
        self.EnergyConsumer_list: List[EnergyConsumer] = list()
        self.ExternalNetworkInjection_list: List[ExternalNetworkInjection] = list()
        self.Ground_list: List[Ground] = list()
        self.GroundDisconnector_list: List[GroundDisconnector] = list()
        self.GroundingImpedance_list: List[GroundingImpedance] = list()
        self.Junction_list: List[Junction] = list()
        self.Line_list: List[Line] = list()
        self.LinearShuntCompensator_list: List[LinearShuntCompensator] = list()
        self.LoadBreakSwitch_list: List[LoadBreakSwitch] = list()
        self.MutualCoupling_list: List[MutualCoupling] = list()
        self.NonlinearShuntCompensator_list: List[NonlinearShuntCompensator] = list()
        self.NonlinearShuntCompensatorPoint_list: List[NonlinearShuntCompensatorPoint] = list()
        self.PetersenCoil_list: List[PetersenCoil] = list()
        self.PhaseTapChanger_list: List[PhaseTapChanger] = list()
        self.PhaseTapChangerAsymmetrical_list: List[PhaseTapChangerAsymmetrical] = list()
        self.PhaseTapChangerLinear_list: List[PhaseTapChangerLinear] = list()
        self.PhaseTapChangerNonLinear_list: List[PhaseTapChangerNonLinear] = list()
        self.PhaseTapChangerSymmetrical_list: List[PhaseTapChangerSymmetrical] = list()
        self.PhaseTapChangerTable_list: List[PhaseTapChangerTable] = list()
        self.PhaseTapChangerTablePoint_list: List[PhaseTapChangerTablePoint] = list()
        self.PhaseTapChangerTabular_list: List[PhaseTapChangerTabular] = list()
        self.PowerTransformer_list: List[PowerTransformer] = list()
        self.PowerTransformerEnd_list: List[PowerTransformerEnd] = list()
        self.ProtectedSwitch_list: List[ProtectedSwitch] = list()
        self.RatioTapChanger_list: List[RatioTapChanger] = list()
        self.RatioTapChangerTable_list: List[RatioTapChangerTable] = list()
        self.RatioTapChangerTablePoint_list: List[RatioTapChangerTablePoint] = list()
        self.ReactiveCapabilityCurve_list: List[ReactiveCapabilityCurve] = list()
        self.RegulatingCondEq_list: List[RegulatingCondEq] = list()
        self.RegulatingControl_list: List[RegulatingControl] = list()
        self.RotatingMachine_list: List[RotatingMachine] = list()
        self.SeriesCompensator_list: List[SeriesCompensator] = list()
        self.ShuntCompensator_list: List[ShuntCompensator] = list()
        self.StaticVarCompensator_list: List[StaticVarCompensator] = list()
        self.Switch_list: List[Switch] = list()
        self.SynchronousMachine_list: List[SynchronousMachine] = list()
        self.TapChanger_list: List[TapChanger] = list()
        self.TapChangerControl_list: List[TapChangerControl] = list()
        self.TapChangerTablePoint_list: List[TapChangerTablePoint] = list()
        self.TransformerEnd_list: List[TransformerEnd] = list()
        self.ConformLoad_list: List[ConformLoad] = list()
        self.ConformLoadGroup_list: List[ConformLoadGroup] = list()
        self.EnergyArea_list: List[EnergyArea] = list()
        self.LoadArea_list: List[LoadArea] = list()
        self.LoadGroup_list: List[LoadGroup] = list()
        self.LoadResponseCharacteristic_list: List[LoadResponseCharacteristic] = list()
        self.NonConformLoad_list: List[NonConformLoad] = list()
        self.NonConformLoadGroup_list: List[NonConformLoadGroup] = list()
        self.SeasonDayTypeSchedule_list: List[SeasonDayTypeSchedule] = list()
        self.SubLoadArea_list: List[SubLoadArea] = list()
        self.EquivalentBranch_list: List[EquivalentBranch] = list()
        self.EquivalentEquipment_list: List[EquivalentEquipment] = list()
        self.EquivalentInjection_list: List[EquivalentInjection] = list()
        self.EquivalentNetwork_list: List[EquivalentNetwork] = list()
        self.EquivalentShunt_list: List[EquivalentShunt] = list()
        self.ControlArea_list: List[ControlArea] = list()
        self.ControlAreaGeneratingUnit_list: List[ControlAreaGeneratingUnit] = list()
        self.TieFlow_list: List[TieFlow] = list()
        self.DCTopologicalIsland_list: List[DCTopologicalIsland] = list()
        self.SvStatus_list: List[SvStatus] = list()
        self.SvInjection_list: List[SvInjection] = list()
        self.SvPowerFlow_list: List[SvPowerFlow] = list()
        self.SvShuntCompensatorSections_list: List[SvShuntCompensatorSections] = list()
        self.SvTapStep_list: List[SvTapStep] = list()
        self.SvVoltage_list: List[SvVoltage] = list()
        self.DCTopologicalNode_list: List[DCTopologicalNode] = list()
        self.TopologicalNode_list: List[TopologicalNode] = list()
        self.TopologicalIsland_list: List[TopologicalIsland] = list()
        self.CoordinateSystem_list: List[CoordinateSystem] = list()
        self.Location_list: List[Location] = list()
        self.PositionPoint_list: List[PositionPoint] = list()
        self.FullModel_list: List[FullModel] = list()

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

    def parse_files(self, data_parser: CgmesDataParser, delete_unused=True, detect_circular_references=False):
        """
        Parse CGMES files into this class
        :param delete_unused: Detele the unused boundary set?
        :param data_parser: getting the read files
        :param detect_circular_references: report the circular references
        """

        # read the CGMES data as dictionaries
        # data_parser = CgmesDataParser(text_func=self.text_func,
        #                               progress_func=self.progress_func,
        #                               logger=self.logger)
        # data_parser.load_files(files=files)

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
                                association_inverse_dict=self.association_inverse_dict,
                                logger=self.logger)

        # convert the dictionaries to the internal class model,
        # this marks as used only the boundary set objects that are referenced,
        # this allows to delete the excess of boundary set objects later
        convert_data_to_objects(data=self.data,
                                all_objects_dict=self.all_objects_dict,
                                all_objects_dict_boundary=self.all_objects_dict_boundary,
                                elements_by_type=self.elements_by_type,
                                class_dict=self.class_dict,
                                association_inverse_dict=self.association_inverse_dict,
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
            df.to_excel(writer, sheet_name=class_name, index=True)
        writer._save()

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
