# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List

from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_converter import ACDCConverter
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_converterdc_terminal import ACDCConverterDCTerminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_terminal import ACDCTerminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ac_line_segment import ACLineSegment
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.active_power_limit import ActivePowerLimit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.apparent_power_limit import ApparentPowerLimit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.asynchronous_machine import AsynchronousMachine
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.auxiliary_equipment import AuxiliaryEquipment
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.base_voltage import BaseVoltage
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.basic_interval_schedule import BasicIntervalSchedule
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.battery_unit import BatteryUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.bay import Bay
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.boundary_point import BoundaryPoint
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.breaker import Breaker
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.busbar_section import BusbarSection
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.bus_name_marker import BusNameMarker
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.caes_plant import CAESPlant
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.clamp import Clamp
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.full_model import FullModel
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.cogeneration_plant import CogenerationPlant
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.combined_cycle_plant import CombinedCyclePlant
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conducting_equipment import ConductingEquipment
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conductor import Conductor
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conform_load import ConformLoad
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conform_load_group import ConformLoadGroup
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connectivity_node import ConnectivityNode
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connectivity_node_container import ConnectivityNodeContainer
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connector import Connector
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control_area import ControlArea
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control_area_generating_unit import ControlAreaGeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.cs_converter import CsConverter
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.current_limit import CurrentLimit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.current_transformer import CurrentTransformer
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.curve import Curve
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.curve_data import CurveData
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.cut import Cut
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_base_terminal import DCBaseTerminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_breaker import DCBreaker
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_busbar import DCBusbar
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_chopper import DCChopper
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_conducting_equipment import DCConductingEquipment
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_converter_unit import DCConverterUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_disconnector import DCDisconnector
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_equipment_container import DCEquipmentContainer
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_ground import DCGround
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_line import DCLine
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_line_segment import DCLineSegment
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_node import DCNode
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_series_device import DCSeriesDevice
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_shunt import DCShunt
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_switch import DCSwitch
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_terminal import DCTerminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.disconnector import Disconnector
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.disconnecting_circuit_breaker import DisconnectingCircuitBreaker
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.earth_fault_compensator import EarthFaultCompensator
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_area import EnergyArea
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_connection import EnergyConnection
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_consumer import EnergyConsumer
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_scheduling_type import EnergySchedulingType
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_source import EnergySource
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment import Equipment
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment_container import EquipmentContainer
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_branch import EquivalentBranch
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_equipment import EquivalentEquipment
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_injection import EquivalentInjection
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_network import EquivalentNetwork
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_shunt import EquivalentShunt
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.external_network_injection import ExternalNetworkInjection
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.fault_indicator import FaultIndicator
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.fossil_fuel import FossilFuel
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.fuse import Fuse
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.generating_unit import GeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.geographical_region import GeographicalRegion
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ground import Ground
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ground_disconnector import GroundDisconnector
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.grounding_impedance import GroundingImpedance
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_generating_unit import HydroGeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_power_plant import HydroPowerPlant
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_pump import HydroPump
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.jumper import Jumper
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.junction import Junction
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.line import Line
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.linear_shunt_compensator import LinearShuntCompensator
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_area import LoadArea
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_break_switch import LoadBreakSwitch
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_group import LoadGroup
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_response_characteristic import LoadResponseCharacteristic
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.non_conform_load import NonConformLoad
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.non_conform_load_group import NonConformLoadGroup
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.nonlinear_shunt_compensator import NonlinearShuntCompensator
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.nonlinear_shunt_compensator_point import \
    NonlinearShuntCompensatorPoint
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.nuclear_generating_unit import NuclearGeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit import OperationalLimit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit_set import OperationalLimitSet
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit_type import OperationalLimitType
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.petersen_coil import PetersenCoil
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer import PhaseTapChanger
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_asymmetrical import PhaseTapChangerAsymmetrical
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_linear import PhaseTapChangerLinear
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_non_linear import PhaseTapChangerNonLinear
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_symmetrical import PhaseTapChangerSymmetrical
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_table import PhaseTapChangerTable
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_table_point import PhaseTapChangerTablePoint
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_tabular import PhaseTapChangerTabular
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.photo_voltaic_unit import PhotoVoltaicUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.post_line_sensor import PostLineSensor
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.potential_transformer import PotentialTransformer
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_connection import PowerElectronicsConnection
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_unit import PowerElectronicsUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_wind_unit import PowerElectronicsWindUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_transformer import PowerTransformer
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_transformer_end import PowerTransformerEnd
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.protected_switch import ProtectedSwitch
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer import RatioTapChanger
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer_table import RatioTapChangerTable
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer_table_point import RatioTapChangerTablePoint
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.reactive_capability_curve import ReactiveCapabilityCurve
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_cond_eq import RegulatingCondEq
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_control import RegulatingControl
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regular_interval_schedule import RegularIntervalSchedule
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.reporting_group import ReportingGroup
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.rotating_machine import RotatingMachine
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sensor import Sensor
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.season_day_type_schedule import SeasonDayTypeSchedule
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.series_compensator import SeriesCompensator
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.shunt_compensator import ShuntCompensator
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.solar_generating_unit import SolarGeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.solar_power_plant import SolarPowerPlant
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.static_var_compensator import StaticVarCompensator
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sub_geographical_region import SubGeographicalRegion
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sub_load_area import SubLoadArea
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.substation import Substation
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.surge_arrester import SurgeArrester
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.switch import Switch
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.synchronous_machine import SynchronousMachine
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer import TapChanger
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer_control import TapChangerControl
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer_table_point import TapChangerTablePoint
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.terminal import Terminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.thermal_generating_unit import ThermalGeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tie_flow import TieFlow
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.transformer_end import TransformerEnd
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.voltage_level import VoltageLevel
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.voltage_limit import VoltageLimit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.vs_capability_curve import VsCapabilityCurve
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.vs_converter import VsConverter
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wave_trap import WaveTrap
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wind_generating_unit import WindGeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wind_power_plant import WindPowerPlant
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_topological_island import DCTopologicalIsland
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_topological_node import DCTopologicalNode
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_injection import SvInjection
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_power_flow import SvPowerFlow
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_shunt_compensator_sections import SvShuntCompensatorSections
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_status import SvStatus
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_switch import SvSwitch
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_tap_step import SvTapStep
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_voltage import SvVoltage
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.topological_island import TopologicalIsland
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.topological_node import TopologicalNode
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.service_location import ServiceLocation
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.work_location import WorkLocation
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.coordinate_system import CoordinateSystem
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.location import Location
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.position_point import PositionPoint

CGMES3_ASSETS = (ACDCConverter |
                 ACDCConverterDCTerminal |
                 ACDCTerminal |
                 ACLineSegment |
                 ActivePowerLimit |
                 ApparentPowerLimit |
                 AsynchronousMachine |
                 AuxiliaryEquipment |
                 BaseVoltage |
                 BasicIntervalSchedule |
                 BatteryUnit |
                 Bay |
                 BoundaryPoint |
                 Breaker |
                 BusbarSection |
                 BusNameMarker |
                 CAESPlant |
                 Clamp |
                 FullModel |
                 CogenerationPlant |
                 CombinedCyclePlant |
                 ConductingEquipment |
                 Conductor |
                 ConformLoad |
                 ConformLoadGroup |
                 ConnectivityNode |
                 ConnectivityNodeContainer |
                 Connector |
                 ControlArea |
                 ControlAreaGeneratingUnit |
                 CsConverter |
                 CurrentLimit |
                 CurrentTransformer |
                 Curve |
                 CurveData |
                 Cut |
                 DCBaseTerminal |
                 DCBreaker |
                 DCBusbar |
                 DCChopper |
                 DCConductingEquipment |
                 DCConverterUnit |
                 DCDisconnector |
                 DCEquipmentContainer |
                 DCGround |
                 DCLine |
                 DCLineSegment |
                 DCNode |
                 DCSeriesDevice |
                 DCShunt |
                 DCSwitch |
                 DCTerminal |
                 Disconnector |
                 DisconnectingCircuitBreaker |
                 EarthFaultCompensator |
                 EnergyArea |
                 EnergyConnection |
                 EnergyConsumer |
                 EnergySchedulingType |
                 EnergySource |
                 Equipment |
                 EquipmentContainer |
                 EquivalentBranch |
                 EquivalentEquipment |
                 EquivalentInjection |
                 EquivalentNetwork |
                 EquivalentShunt |
                 ExternalNetworkInjection |
                 FaultIndicator |
                 FossilFuel |
                 Fuse |
                 GeneratingUnit |
                 GeographicalRegion |
                 Ground |
                 GroundDisconnector |
                 GroundingImpedance |
                 HydroGeneratingUnit |
                 HydroPowerPlant |
                 HydroPump |
                 IdentifiedObject |
                 Jumper |
                 Junction |
                 Line |
                 LinearShuntCompensator |
                 LoadArea |
                 LoadBreakSwitch |
                 LoadGroup |
                 LoadResponseCharacteristic |
                 NonConformLoad |
                 NonConformLoadGroup |
                 NonlinearShuntCompensator |
                 NonlinearShuntCompensatorPoint |
                 NuclearGeneratingUnit |
                 OperationalLimit |
                 OperationalLimitSet |
                 OperationalLimitType |
                 PetersenCoil |
                 PhaseTapChanger |
                 PhaseTapChangerAsymmetrical |
                 PhaseTapChangerLinear |
                 PhaseTapChangerNonLinear |
                 PhaseTapChangerSymmetrical |
                 PhaseTapChangerTable |
                 PhaseTapChangerTablePoint |
                 PhaseTapChangerTabular |
                 PhotoVoltaicUnit |
                 PostLineSensor |
                 PotentialTransformer |
                 PowerElectronicsConnection |
                 PowerElectronicsUnit |
                 PowerElectronicsWindUnit |
                 PowerSystemResource |
                 PowerTransformer |
                 PowerTransformerEnd |
                 ProtectedSwitch |
                 RatioTapChanger |
                 RatioTapChangerTable |
                 RatioTapChangerTablePoint |
                 ReactiveCapabilityCurve |
                 RegulatingCondEq |
                 RegulatingControl |
                 RegularIntervalSchedule |
                 ReportingGroup |
                 RotatingMachine |
                 Sensor |
                 SeasonDayTypeSchedule |
                 SeriesCompensator |
                 ShuntCompensator |
                 SolarGeneratingUnit |
                 SolarPowerPlant |
                 StaticVarCompensator |
                 SubGeographicalRegion |
                 SubLoadArea |
                 Substation |
                 SurgeArrester |
                 Switch |
                 SynchronousMachine |
                 TapChanger |
                 TapChangerControl |
                 TapChangerTablePoint |
                 Terminal |
                 ThermalGeneratingUnit |
                 TieFlow |
                 TransformerEnd |
                 VoltageLevel |
                 VoltageLimit |
                 VsCapabilityCurve |
                 VsConverter |
                 WaveTrap |
                 WindGeneratingUnit |
                 WindPowerPlant |
                 DCTopologicalIsland |
                 DCTopologicalNode |
                 SvInjection |
                 SvPowerFlow |
                 SvShuntCompensatorSections |
                 SvStatus |
                 SvSwitch |
                 SvTapStep |
                 SvVoltage |
                 TopologicalIsland |
                 TopologicalNode |
                 ServiceLocation |
                 WorkLocation |
                 CoordinateSystem |
                 Location |
                 PositionPoint
                 )


class Cgmes_3_0_0_Assets:
    def __init__(self):
        self.class_dict = {
            'ACDCConverter': ACDCConverter,
            'ACDCConverterDCTerminal': ACDCConverterDCTerminal,
            'ACDCTerminal': ACDCTerminal,
            'ACLineSegment': ACLineSegment,
            'ActivePowerLimit': ActivePowerLimit,
            'ApparentPowerLimit': ApparentPowerLimit,
            'AsynchronousMachine': AsynchronousMachine,
            'AuxiliaryEquipment': AuxiliaryEquipment,
            'BaseVoltage': BaseVoltage,
            'BasicIntervalSchedule': BasicIntervalSchedule,
            'BatteryUnit': BatteryUnit,
            'Bay': Bay,
            'BoundaryPoint': BoundaryPoint,
            'Breaker': Breaker,
            'BusbarSection': BusbarSection,
            'BusNameMarker': BusNameMarker,
            'CAESPlant': CAESPlant,
            'Clamp': Clamp,
            'CogenerationPlant': CogenerationPlant,
            'CombinedCyclePlant': CombinedCyclePlant,
            'ConductingEquipment': ConductingEquipment,
            'Conductor': Conductor,
            'ConformLoad': ConformLoad,
            'ConformLoadGroup': ConformLoadGroup,
            'ConnectivityNode': ConnectivityNode,
            'ConnectivityNodeContainer': ConnectivityNodeContainer,
            'Connector': Connector,
            'ControlArea': ControlArea,
            'ControlAreaGeneratingUnit': ControlAreaGeneratingUnit,
            'CsConverter': CsConverter,
            'CurrentLimit': CurrentLimit,
            'CurrentTransformer': CurrentTransformer,
            'Curve': Curve,
            'CurveData': CurveData,
            'Cut': Cut,
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
            'Disconnector': Disconnector,
            'DisconnectingCircuitBreaker': DisconnectingCircuitBreaker,
            'EarthFaultCompensator': EarthFaultCompensator,
            'EnergyArea': EnergyArea,
            'EnergyConnection': EnergyConnection,
            'EnergyConsumer': EnergyConsumer,
            'EnergySchedulingType': EnergySchedulingType,
            'EnergySource': EnergySource,
            'Equipment': Equipment,
            'EquipmentContainer': EquipmentContainer,
            'EquivalentBranch': EquivalentBranch,
            'EquivalentEquipment': EquivalentEquipment,
            'EquivalentInjection': EquivalentInjection,
            'EquivalentNetwork': EquivalentNetwork,
            'EquivalentShunt': EquivalentShunt,
            'ExternalNetworkInjection': ExternalNetworkInjection,
            'FaultIndicator': FaultIndicator,
            'FossilFuel': FossilFuel,
            'Fuse': Fuse,
            'GeneratingUnit': GeneratingUnit,
            'GeographicalRegion': GeographicalRegion,
            'Ground': Ground,
            'GroundDisconnector': GroundDisconnector,
            'GroundingImpedance': GroundingImpedance,
            'HydroGeneratingUnit': HydroGeneratingUnit,
            'HydroPowerPlant': HydroPowerPlant,
            'HydroPump': HydroPump,
            'IdentifiedObject': IdentifiedObject,
            'Jumper': Jumper,
            'Junction': Junction,
            'Line': Line,
            'LinearShuntCompensator': LinearShuntCompensator,
            'LoadArea': LoadArea,
            'LoadBreakSwitch': LoadBreakSwitch,
            'LoadGroup': LoadGroup,
            'LoadResponseCharacteristic': LoadResponseCharacteristic,
            'NonConformLoad': NonConformLoad,
            'NonConformLoadGroup': NonConformLoadGroup,
            'NonlinearShuntCompensator': NonlinearShuntCompensator,
            'NonlinearShuntCompensatorPoint': NonlinearShuntCompensatorPoint,
            'NuclearGeneratingUnit': NuclearGeneratingUnit,
            'OperationalLimit': OperationalLimit,
            'OperationalLimitSet': OperationalLimitSet,
            'OperationalLimitType': OperationalLimitType,
            'PetersenCoil': PetersenCoil,
            'PhaseTapChanger': PhaseTapChanger,
            'PhaseTapChangerAsymmetrical': PhaseTapChangerAsymmetrical,
            'PhaseTapChangerLinear': PhaseTapChangerLinear,
            'PhaseTapChangerNonLinear': PhaseTapChangerNonLinear,
            'PhaseTapChangerSymmetrical': PhaseTapChangerSymmetrical,
            'PhaseTapChangerTable': PhaseTapChangerTable,
            'PhaseTapChangerTablePoint': PhaseTapChangerTablePoint,
            'PhaseTapChangerTabular': PhaseTapChangerTabular,
            'PhotoVoltaicUnit': PhotoVoltaicUnit,
            'PostLineSensor': PostLineSensor,
            'PotentialTransformer': PotentialTransformer,
            'PowerElectronicsConnection': PowerElectronicsConnection,
            'PowerElectronicsUnit': PowerElectronicsUnit,
            'PowerElectronicsWindUnit': PowerElectronicsWindUnit,
            'PowerSystemResource': PowerSystemResource,
            'PowerTransformer': PowerTransformer,
            'PowerTransformerEnd': PowerTransformerEnd,
            'ProtectedSwitch': ProtectedSwitch,
            'RatioTapChanger': RatioTapChanger,
            'RatioTapChangerTable': RatioTapChangerTable,
            'RatioTapChangerTablePoint': RatioTapChangerTablePoint,
            'ReactiveCapabilityCurve': ReactiveCapabilityCurve,
            'RegulatingCondEq': RegulatingCondEq,
            'RegulatingControl': RegulatingControl,
            'RegularIntervalSchedule': RegularIntervalSchedule,
            'ReportingGroup': ReportingGroup,
            'RotatingMachine': RotatingMachine,
            'Sensor': Sensor,
            'SeasonDayTypeSchedule': SeasonDayTypeSchedule,
            'SeriesCompensator': SeriesCompensator,
            'ShuntCompensator': ShuntCompensator,
            'SolarGeneratingUnit': SolarGeneratingUnit,
            'SolarPowerPlant': SolarPowerPlant,
            'StaticVarCompensator': StaticVarCompensator,
            'SubGeographicalRegion': SubGeographicalRegion,
            'SubLoadArea': SubLoadArea,
            'Substation': Substation,
            'SurgeArrester': SurgeArrester,
            'Switch': Switch,
            'SynchronousMachine': SynchronousMachine,
            'TapChanger': TapChanger,
            'TapChangerControl': TapChangerControl,
            'TapChangerTablePoint': TapChangerTablePoint,
            'Terminal': Terminal,
            'ThermalGeneratingUnit': ThermalGeneratingUnit,
            'TieFlow': TieFlow,
            'TransformerEnd': TransformerEnd,
            'VoltageLevel': VoltageLevel,
            'VoltageLimit': VoltageLimit,
            'VsCapabilityCurve': VsCapabilityCurve,
            'VsConverter': VsConverter,
            'WaveTrap': WaveTrap,
            'WindGeneratingUnit': WindGeneratingUnit,
            'WindPowerPlant': WindPowerPlant,
            'DCTopologicalIsland': DCTopologicalIsland,
            'DCTopologicalNode': DCTopologicalNode,
            'SvInjection': SvInjection,
            'SvPowerFlow': SvPowerFlow,
            'SvShuntCompensatorSections': SvShuntCompensatorSections,
            'SvStatus': SvStatus,
            'SvSwitch': SvSwitch,
            'SvTapStep': SvTapStep,
            'SvVoltage': SvVoltage,
            'TopologicalIsland': TopologicalIsland,
            'TopologicalNode': TopologicalNode,
            'ServiceLocation': ServiceLocation,
            'WorkLocation': WorkLocation,
            'CoordinateSystem': CoordinateSystem,
            'Location': Location,
            'PositionPoint': PositionPoint,
            'FullModel': FullModel,
        }

        self.association_inverse_dict = {
            ('FaultIndicator', 'Terminal'): 'AuxiliaryEquipment',
            ('FaultIndicator', 'EquipmentContainer'): 'Equipments',
            ('BusbarSection', 'BaseVoltage'): 'ConductingEquipment',
            ('BusbarSection', 'EquipmentContainer'): 'Equipments',
            ('DCBusbar', 'EquipmentContainer'): 'Equipments',
            ('VsConverter', 'CapabilityCurve'): 'VsConverterDCSides',
            ('VsConverter', 'PccTerminal'): 'ConverterDCSides',
            ('VsConverter', 'BaseVoltage'): 'ConductingEquipment',
            ('VsConverter', 'EquipmentContainer'): 'Equipments',
            ('RatioTapChanger', 'TransformerEnd'): 'RatioTapChanger',
            ('RatioTapChanger', 'RatioTapChangerTable'): 'RatioTapChanger',
            ('RatioTapChanger', 'TapChangerControl'): 'TapChanger',
            ('DCTerminal', 'DCConductingEquipment'): 'DCTerminals',
            ('DCTerminal', 'DCNode'): 'DCTerminals',
            ('DCTerminal', 'BusNameMarker'): 'Terminal',
            ('DCTerminal', 'DCTopologicalNode'): 'DCTerminals',
            ('StaticVarCompensator', 'RegulatingControl'): 'RegulatingCondEq',
            ('StaticVarCompensator', 'BaseVoltage'): 'ConductingEquipment',
            ('StaticVarCompensator', 'EquipmentContainer'): 'Equipments',
            ('CsConverter', 'PccTerminal'): 'ConverterDCSides',
            ('CsConverter', 'BaseVoltage'): 'ConductingEquipment',
            ('CsConverter', 'EquipmentContainer'): 'Equipments',
            ('Line', 'Region'): 'Lines',
            ('DisconnectingCircuitBreaker', 'BaseVoltage'): 'ConductingEquipment',
            ('DisconnectingCircuitBreaker', 'EquipmentContainer'): 'Equipments',
            ('DCSeriesDevice', 'EquipmentContainer'): 'Equipments',
            ('Breaker', 'BaseVoltage'): 'ConductingEquipment',
            ('Breaker', 'EquipmentContainer'): 'Equipments',
            ('Disconnector', 'BaseVoltage'): 'ConductingEquipment',
            ('Disconnector', 'EquipmentContainer'): 'Equipments',
            ('OperationalLimitSet', 'Terminal'): 'OperationalLimitSet',
            ('OperationalLimitSet', 'Equipment'): 'OperationalLimitSet',
            ('TapChangerControl', 'Terminal'): 'RegulatingControl',
            ('ApparentPowerLimit', 'OperationalLimitSet'): 'OperationalLimitValue',
            ('ApparentPowerLimit', 'OperationalLimitType'): 'OperationalLimit',
            ('ActivePowerLimit', 'OperationalLimitSet'): 'OperationalLimitValue',
            ('ActivePowerLimit', 'OperationalLimitType'): 'OperationalLimit',
            ('HydroPump', 'RotatingMachine'): 'HydroPump',
            ('HydroPump', 'HydroPowerPlant'): 'HydroPumps',
            ('HydroPump', 'EquipmentContainer'): 'Equipments',
            ('SubLoadArea', 'LoadArea'): 'SubLoadAreas',
            ('SolarGeneratingUnit', 'SolarPowerPlant'): 'SolarGeneratingUnits',
            ('SolarGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('CurrentTransformer', 'Terminal'): 'AuxiliaryEquipment',
            ('CurrentTransformer', 'EquipmentContainer'): 'Equipments',
            ('EquivalentShunt', 'EquivalentNetwork'): 'EquivalentEquipments',
            ('EquivalentShunt', 'BaseVoltage'): 'ConductingEquipment',
            ('EquivalentShunt', 'EquipmentContainer'): 'Equipments',
            ('SeriesCompensator', 'BaseVoltage'): 'ConductingEquipment',
            ('SeriesCompensator', 'EquipmentContainer'): 'Equipments',
            ('DCShunt', 'EquipmentContainer'): 'Equipments',
            ('CurrentLimit', 'OperationalLimitSet'): 'OperationalLimitValue',
            ('CurrentLimit', 'OperationalLimitType'): 'OperationalLimit',
            ('Terminal', 'ConductingEquipment'): 'Terminals',
            ('Terminal', 'ConnectivityNode'): 'Terminals',
            ('Terminal', 'BusNameMarker'): 'Terminal',
            ('Terminal', 'TopologicalNode'): 'Terminal',
            ('AsynchronousMachine', 'GeneratingUnit'): 'RotatingMachine',
            ('AsynchronousMachine', 'RegulatingControl'): 'RegulatingCondEq',
            ('AsynchronousMachine', 'BaseVoltage'): 'ConductingEquipment',
            ('AsynchronousMachine', 'EquipmentContainer'): 'Equipments',
            ('ExternalNetworkInjection', 'RegulatingControl'): 'RegulatingCondEq',
            ('ExternalNetworkInjection', 'BaseVoltage'): 'ConductingEquipment',
            ('ExternalNetworkInjection', 'EquipmentContainer'): 'Equipments',
            ('SynchronousMachine', 'InitialReactiveCapabilityCurve'): 'InitiallyUsedBySynchronousMachines',
            ('SynchronousMachine', 'GeneratingUnit'): 'RotatingMachine',
            ('SynchronousMachine', 'RegulatingControl'): 'RegulatingCondEq',
            ('SynchronousMachine', 'BaseVoltage'): 'ConductingEquipment',
            ('SynchronousMachine', 'EquipmentContainer'): 'Equipments',
            ('PhaseTapChangerAsymmetrical', 'TransformerEnd'): 'PhaseTapChanger',
            ('PhaseTapChangerAsymmetrical', 'TapChangerControl'): 'TapChanger',
            ('BoundaryPoint', 'ConnectivityNode'): 'BoundaryPoint',
            ('ConformLoadGroup', 'SubLoadArea'): 'LoadGroups',
            ('ControlAreaGeneratingUnit', 'ControlArea'): 'ControlAreaGeneratingUnit',
            ('ControlAreaGeneratingUnit', 'GeneratingUnit'): 'ControlAreaGeneratingUnit',
            ('DCBreaker', 'EquipmentContainer'): 'Equipments',
            ('ThermalGeneratingUnit', 'CombinedCyclePlant'): 'ThermalGeneratingUnits',
            ('ThermalGeneratingUnit', 'CogenerationPlant'): 'ThermalGeneratingUnits',
            ('ThermalGeneratingUnit', 'CAESPlant'): 'ThermalGeneratingUnit',
            ('ThermalGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('Bay', 'VoltageLevel'): 'Bays',
            ('PhaseTapChangerLinear', 'TransformerEnd'): 'PhaseTapChanger',
            ('PhaseTapChangerLinear', 'TapChangerControl'): 'TapChanger',
            ('DCSwitch', 'EquipmentContainer'): 'Equipments',
            ('SubGeographicalRegion', 'Region'): 'Regions',
            ('CurveData', 'Curve'): 'CurveDatas',
            ('EquivalentBranch', 'EquivalentNetwork'): 'EquivalentEquipments',
            ('EquivalentBranch', 'BaseVoltage'): 'ConductingEquipment',
            ('EquivalentBranch', 'EquipmentContainer'): 'Equipments',
            ('DCChopper', 'EquipmentContainer'): 'Equipments',
            ('Ground', 'BaseVoltage'): 'ConductingEquipment',
            ('Ground', 'EquipmentContainer'): 'Equipments',
            ('GroundDisconnector', 'BaseVoltage'): 'ConductingEquipment',
            ('GroundDisconnector', 'EquipmentContainer'): 'Equipments',
            ('Clamp', 'ACLineSegment'): 'Clamp',
            ('Clamp', 'BaseVoltage'): 'ConductingEquipment',
            ('Clamp', 'EquipmentContainer'): 'Equipments',
            ('DCLine', 'Region'): 'DCLines',
            ('Substation', 'Region'): 'Substations',
            ('RegulatingControl', 'Terminal'): 'RegulatingControl',
            ('NonlinearShuntCompensator', 'RegulatingControl'): 'RegulatingCondEq',
            ('NonlinearShuntCompensator', 'BaseVoltage'): 'ConductingEquipment',
            ('NonlinearShuntCompensator', 'EquipmentContainer'): 'Equipments',
            ('PetersenCoil', 'BaseVoltage'): 'ConductingEquipment',
            ('PetersenCoil', 'EquipmentContainer'): 'Equipments',
            ('Fuse', 'BaseVoltage'): 'ConductingEquipment',
            ('Fuse', 'EquipmentContainer'): 'Equipments',
            ('Cut', 'ACLineSegment'): 'Cut',
            ('Cut', 'BaseVoltage'): 'ConductingEquipment',
            ('Cut', 'EquipmentContainer'): 'Equipments',
            ('Jumper', 'BaseVoltage'): 'ConductingEquipment',
            ('Jumper', 'EquipmentContainer'): 'Equipments',
            ('PowerTransformerEnd', 'PowerTransformer'): 'PowerTransformerEnd',
            ('PowerTransformerEnd', 'Terminal'): 'TransformerEnd',
            ('PowerTransformerEnd', 'BaseVoltage'): 'TransformerEnds',
            ('LoadBreakSwitch', 'BaseVoltage'): 'ConductingEquipment',
            ('LoadBreakSwitch', 'EquipmentContainer'): 'Equipments',
            ('DCLineSegment', 'EquipmentContainer'): 'Equipments',
            ('PhaseTapChangerSymmetrical', 'TransformerEnd'): 'PhaseTapChanger',
            ('PhaseTapChangerSymmetrical', 'TapChangerControl'): 'TapChanger',
            ('ConformLoad', 'LoadGroup'): 'EnergyConsumers',
            ('ConformLoad', 'LoadResponse'): 'EnergyConsumer',
            ('ConformLoad', 'BaseVoltage'): 'ConductingEquipment',
            ('ConformLoad', 'EquipmentContainer'): 'Equipments',
            ('ConnectivityNode', 'ConnectivityNodeContainer'): 'ConnectivityNodes',
            ('ConnectivityNode', 'TopologicalNode'): 'ConnectivityNodes',
            ('WindGeneratingUnit', 'WindPowerPlant'): 'WindGeneratingUnits',
            ('WindGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('ControlArea', 'EnergyArea'): 'ControlArea',
            ('VoltageLimit', 'OperationalLimitSet'): 'OperationalLimitValue',
            ('VoltageLimit', 'OperationalLimitType'): 'OperationalLimit',
            ('PowerElectronicsWindUnit', 'EquipmentContainer'): 'Equipments',
            ('PhotoVoltaicUnit', 'EquipmentContainer'): 'Equipments',
            ('DCGround', 'EquipmentContainer'): 'Equipments',
            ('ACDCConverterDCTerminal', 'DCConductingEquipment'): 'DCTerminals',
            ('ACDCConverterDCTerminal', 'DCNode'): 'DCTerminals',
            ('ACDCConverterDCTerminal', 'BusNameMarker'): 'Terminal',
            ('ACDCConverterDCTerminal', 'DCTopologicalNode'): 'DCTerminals',
            ('VoltageLevel', 'BaseVoltage'): 'VoltageLevel',
            ('VoltageLevel', 'Substation'): 'VoltageLevels',
            ('ACLineSegment', 'BaseVoltage'): 'ConductingEquipment',
            ('ACLineSegment', 'EquipmentContainer'): 'Equipments',
            ('NuclearGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('BatteryUnit', 'EquipmentContainer'): 'Equipments',
            ('EnergyConsumer', 'LoadResponse'): 'EnergyConsumer',
            ('EnergyConsumer', 'BaseVoltage'): 'ConductingEquipment',
            ('EnergyConsumer', 'EquipmentContainer'): 'Equipments',
            ('SurgeArrester', 'Terminal'): 'AuxiliaryEquipment',
            ('SurgeArrester', 'EquipmentContainer'): 'Equipments',
            ('DCNode', 'DCEquipmentContainer'): 'DCNodes',
            ('DCNode', 'DCTopologicalNode'): 'DCNodes',
            ('NonlinearShuntCompensatorPoint', 'NonlinearShuntCompensator'): 'NonlinearShuntCompensatorPoints',
            ('DCDisconnector', 'EquipmentContainer'): 'Equipments',
            ('Junction', 'BaseVoltage'): 'ConductingEquipment',
            ('Junction', 'EquipmentContainer'): 'Equipments',
            ('Switch', 'BaseVoltage'): 'ConductingEquipment',
            ('Switch', 'EquipmentContainer'): 'Equipments',
            ('NonConformLoad', 'LoadGroup'): 'EnergyConsumers',
            ('NonConformLoad', 'LoadResponse'): 'EnergyConsumer',
            ('NonConformLoad', 'BaseVoltage'): 'ConductingEquipment',
            ('NonConformLoad', 'EquipmentContainer'): 'Equipments',
            ('WaveTrap', 'Terminal'): 'AuxiliaryEquipment',
            ('WaveTrap', 'EquipmentContainer'): 'Equipments',
            ('FossilFuel', 'ThermalGeneratingUnit'): 'FossilFuels',
            ('BusNameMarker', 'ReportingGroup'): 'BusNameMarker',
            ('GroundingImpedance', 'BaseVoltage'): 'ConductingEquipment',
            ('GroundingImpedance', 'EquipmentContainer'): 'Equipments',
            ('TieFlow', 'Terminal'): 'TieFlow',
            ('TieFlow', 'ControlArea'): 'TieFlow',
            ('HydroGeneratingUnit', 'HydroPowerPlant'): 'HydroGeneratingUnits',
            ('HydroGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('LinearShuntCompensator', 'RegulatingControl'): 'RegulatingCondEq',
            ('LinearShuntCompensator', 'BaseVoltage'): 'ConductingEquipment',
            ('LinearShuntCompensator', 'EquipmentContainer'): 'Equipments',
            ('DCConverterUnit', 'Substation'): 'DCConverterUnit',
            ('EquivalentInjection', 'ReactiveCapabilityCurve'): 'EquivalentInjection',
            ('EquivalentInjection', 'EquivalentNetwork'): 'EquivalentEquipments',
            ('EquivalentInjection', 'BaseVoltage'): 'ConductingEquipment',
            ('EquivalentInjection', 'EquipmentContainer'): 'Equipments',
            ('RatioTapChangerTablePoint', 'RatioTapChangerTable'): 'RatioTapChangerTablePoint',
            ('EnergySource', 'EnergySchedulingType'): 'EnergySource',
            ('EnergySource', 'BaseVoltage'): 'ConductingEquipment',
            ('EnergySource', 'EquipmentContainer'): 'Equipments',
            ('NonConformLoadGroup', 'SubLoadArea'): 'LoadGroups',
            ('PostLineSensor', 'Terminal'): 'AuxiliaryEquipment',
            ('PostLineSensor', 'EquipmentContainer'): 'Equipments',
            ('PhaseTapChangerTablePoint', 'PhaseTapChangerTable'): 'PhaseTapChangerTablePoint',
            ('PotentialTransformer', 'Terminal'): 'AuxiliaryEquipment',
            ('PotentialTransformer', 'EquipmentContainer'): 'Equipments',
            ('PhaseTapChangerTabular', 'PhaseTapChangerTable'): 'PhaseTapChangerTabular',
            ('PhaseTapChangerTabular', 'TransformerEnd'): 'PhaseTapChanger',
            ('PhaseTapChangerTabular', 'TapChangerControl'): 'TapChanger',
            ('GeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('PowerTransformer', 'BaseVoltage'): 'ConductingEquipment',
            ('PowerTransformer', 'EquipmentContainer'): 'Equipments',
            ('PowerElectronicsConnection', 'PowerElectronicsUnit'): 'PowerElectronicsConnection',
            ('PowerElectronicsConnection', 'RegulatingControl'): 'RegulatingCondEq',
            ('PowerElectronicsConnection', 'BaseVoltage'): 'ConductingEquipment',
            ('PowerElectronicsConnection', 'EquipmentContainer'): 'Equipments',
            ('ServiceLocation', 'PowerSystemResources'): 'Location',
            ('ServiceLocation', 'CoordinateSystem'): 'Locations',
            ('Location', 'PowerSystemResources'): 'Location',
            ('Location', 'CoordinateSystem'): 'Locations',
            ('PositionPoint', 'Location'): 'PositionPoints',
            ('MutualCoupling', 'First_Terminal'): 'HasFirstMutualCoupling',
            ('MutualCoupling', 'Second_Terminal'): 'HasSecondMutualCoupling',
            ('TopologicalIsland', 'AngleRefTopologicalNode'): 'AngleRefTopologicalIsland',
            ('TopologicalIsland', 'TopologicalNodes'): 'TopologicalIsland',
            ('SvPowerFlow', 'Terminal'): 'SvPowerFlow',
            ('SvTapStep', 'TapChanger'): 'SvTapStep',
            ('SvSwitch', 'Switch'): 'SvSwitch',
            ('SvShuntCompensatorSections', 'ShuntCompensator'): 'SvShuntCompensatorSections',
            ('SvInjection', 'TopologicalNode'): 'SvInjection',
            ('DCTopologicalIsland', 'DCTopologicalNodes'): 'DCTopologicalIsland',
            ('SvVoltage', 'TopologicalNode'): 'SvVoltage',
            ('SvStatus', 'ConductingEquipment'): 'SvStatus',
            ('DCTopologicalNode', 'DCEquipmentContainer'): 'DCTopologicalNode',
            ('TopologicalNode', 'ReportingGroup'): 'TopologicalNode',
            ('TopologicalNode', 'BaseVoltage'): 'TopologicalNode',
            ('TopologicalNode', 'ConnectivityNodeContainer'): 'TopologicalNode',
        }

        self.ACDCConverter_list: List[ACDCConverter] = list()
        self.ACDCConverterDCTerminal_list: List[ACDCConverterDCTerminal] = list()
        self.ACDCTerminal_list: List[ACDCTerminal] = list()
        self.ACLineSegment_list: List[ACLineSegment] = list()
        self.ActivePowerLimit_list: List[ActivePowerLimit] = list()
        self.ApparentPowerLimit_list: List[ApparentPowerLimit] = list()
        self.AsynchronousMachine_list: List[AsynchronousMachine] = list()
        self.AuxiliaryEquipment_list: List[AuxiliaryEquipment] = list()
        self.BaseVoltage_list: List[BaseVoltage] = list()
        self.BasicIntervalSchedule_list: List[BasicIntervalSchedule] = list()
        self.BatteryUnit_list: List[BatteryUnit] = list()
        self.Bay_list: List[Bay] = list()
        self.BoundaryPoint_list: List[BoundaryPoint] = list()
        self.Breaker_list: List[Breaker] = list()
        self.BusbarSection_list: List[BusbarSection] = list()
        self.BusNameMarker_list: List[BusNameMarker] = list()
        self.CAESPlant_list: List[CAESPlant] = list()
        self.Clamp_list: List[Clamp] = list()
        self.CogenerationPlant_list: List[CogenerationPlant] = list()
        self.CombinedCyclePlant_list: List[CombinedCyclePlant] = list()
        self.ConductingEquipment_list: List[ConductingEquipment] = list()
        self.Conductor_list: List[Conductor] = list()
        self.ConformLoad_list: List[ConformLoad] = list()
        self.ConformLoadGroup_list: List[ConformLoadGroup] = list()
        self.ConnectivityNode_list: List[ConnectivityNode] = list()
        self.ConnectivityNodeContainer_list: List[ConnectivityNodeContainer] = list()
        self.Connector_list: List[Connector] = list()
        self.ControlArea_list: List[ControlArea] = list()
        self.ControlAreaGeneratingUnit_list: List[ControlAreaGeneratingUnit] = list()
        self.CsConverter_list: List[CsConverter] = list()
        self.CurrentLimit_list: List[CurrentLimit] = list()
        self.CurrentTransformer_list: List[CurrentTransformer] = list()
        self.Curve_list: List[Curve] = list()
        self.CurveData_list: List[CurveData] = list()
        self.Cut_list: List[Cut] = list()
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
        self.Disconnector_list: List[Disconnector] = list()
        self.DisconnectingCircuitBreaker_list: List[DisconnectingCircuitBreaker] = list()
        self.EarthFaultCompensator_list: List[EarthFaultCompensator] = list()
        self.EnergyArea_list: List[EnergyArea] = list()
        self.EnergyConnection_list: List[EnergyConnection] = list()
        self.EnergyConsumer_list: List[EnergyConsumer] = list()
        self.EnergySchedulingType_list: List[EnergySchedulingType] = list()
        self.EnergySource_list: List[EnergySource] = list()
        self.Equipment_list: List[Equipment] = list()
        self.EquipmentContainer_list: List[EquipmentContainer] = list()
        self.EquivalentBranch_list: List[EquivalentBranch] = list()
        self.EquivalentEquipment_list: List[EquivalentEquipment] = list()
        self.EquivalentInjection_list: List[EquivalentInjection] = list()
        self.EquivalentNetwork_list: List[EquivalentNetwork] = list()
        self.EquivalentShunt_list: List[EquivalentShunt] = list()
        self.ExternalNetworkInjection_list: List[ExternalNetworkInjection] = list()
        self.FaultIndicator_list: List[FaultIndicator] = list()
        self.FossilFuel_list: List[FossilFuel] = list()
        self.Fuse_list: List[Fuse] = list()
        self.GeneratingUnit_list: List[GeneratingUnit] = list()
        self.GeographicalRegion_list: List[GeographicalRegion] = list()
        self.Ground_list: List[Ground] = list()
        self.GroundDisconnector_list: List[GroundDisconnector] = list()
        self.GroundingImpedance_list: List[GroundingImpedance] = list()
        self.HydroGeneratingUnit_list: List[HydroGeneratingUnit] = list()
        self.HydroPowerPlant_list: List[HydroPowerPlant] = list()
        self.HydroPump_list: List[HydroPump] = list()
        self.IdentifiedObject_list: List[IdentifiedObject] = list()
        self.Jumper_list: List[Jumper] = list()
        self.Junction_list: List[Junction] = list()
        self.Line_list: List[Line] = list()
        self.LinearShuntCompensator_list: List[LinearShuntCompensator] = list()
        self.LoadArea_list: List[LoadArea] = list()
        self.LoadBreakSwitch_list: List[LoadBreakSwitch] = list()
        self.LoadGroup_list: List[LoadGroup] = list()
        self.LoadResponseCharacteristic_list: List[LoadResponseCharacteristic] = list()
        self.NonConformLoad_list: List[NonConformLoad] = list()
        self.NonConformLoadGroup_list: List[NonConformLoadGroup] = list()
        self.NonlinearShuntCompensator_list: List[NonlinearShuntCompensator] = list()
        self.NonlinearShuntCompensatorPoint_list: List[NonlinearShuntCompensatorPoint] = list()
        self.NuclearGeneratingUnit_list: List[NuclearGeneratingUnit] = list()
        self.OperationalLimit_list: List[OperationalLimit] = list()
        self.OperationalLimitSet_list: List[OperationalLimitSet] = list()
        self.OperationalLimitType_list: List[OperationalLimitType] = list()
        self.PetersenCoil_list: List[PetersenCoil] = list()
        self.PhaseTapChanger_list: List[PhaseTapChanger] = list()
        self.PhaseTapChangerAsymmetrical_list: List[PhaseTapChangerAsymmetrical] = list()
        self.PhaseTapChangerLinear_list: List[PhaseTapChangerLinear] = list()
        self.PhaseTapChangerNonLinear_list: List[PhaseTapChangerNonLinear] = list()
        self.PhaseTapChangerSymmetrical_list: List[PhaseTapChangerSymmetrical] = list()
        self.PhaseTapChangerTable_list: List[PhaseTapChangerTable] = list()
        self.PhaseTapChangerTablePoint_list: List[PhaseTapChangerTablePoint] = list()
        self.PhaseTapChangerTabular_list: List[PhaseTapChangerTabular] = list()
        self.PhotoVoltaicUnit_list: List[PhotoVoltaicUnit] = list()
        self.PostLineSensor_list: List[PostLineSensor] = list()
        self.PotentialTransformer_list: List[PotentialTransformer] = list()
        self.PowerElectronicsConnection_list: List[PowerElectronicsConnection] = list()
        self.PowerElectronicsUnit_list: List[PowerElectronicsUnit] = list()
        self.PowerElectronicsWindUnit_list: List[PowerElectronicsWindUnit] = list()
        self.PowerSystemResource_list: List[PowerSystemResource] = list()
        self.PowerTransformer_list: List[PowerTransformer] = list()
        self.PowerTransformerEnd_list: List[PowerTransformerEnd] = list()
        self.ProtectedSwitch_list: List[ProtectedSwitch] = list()
        self.RatioTapChanger_list: List[RatioTapChanger] = list()
        self.RatioTapChangerTable_list: List[RatioTapChangerTable] = list()
        self.RatioTapChangerTablePoint_list: List[RatioTapChangerTablePoint] = list()
        self.ReactiveCapabilityCurve_list: List[ReactiveCapabilityCurve] = list()
        self.RegulatingCondEq_list: List[RegulatingCondEq] = list()
        self.RegulatingControl_list: List[RegulatingControl] = list()
        self.RegularIntervalSchedule_list: List[RegularIntervalSchedule] = list()
        self.ReportingGroup_list: List[ReportingGroup] = list()
        self.RotatingMachine_list: List[RotatingMachine] = list()
        self.Sensor_list: List[Sensor] = list()
        self.SeasonDayTypeSchedule_list: List[SeasonDayTypeSchedule] = list()
        self.SeriesCompensator_list: List[SeriesCompensator] = list()
        self.ShuntCompensator_list: List[ShuntCompensator] = list()
        self.SolarGeneratingUnit_list: List[SolarGeneratingUnit] = list()
        self.SolarPowerPlant_list: List[SolarPowerPlant] = list()
        self.StaticVarCompensator_list: List[StaticVarCompensator] = list()
        self.SubGeographicalRegion_list: List[SubGeographicalRegion] = list()
        self.SubLoadArea_list: List[SubLoadArea] = list()
        self.Substation_list: List[Substation] = list()
        self.SurgeArrester_list: List[SurgeArrester] = list()
        self.Switch_list: List[Switch] = list()
        self.SynchronousMachine_list: List[SynchronousMachine] = list()
        self.TapChanger_list: List[TapChanger] = list()
        self.TapChangerControl_list: List[TapChangerControl] = list()
        self.TapChangerTablePoint_list: List[TapChangerTablePoint] = list()
        self.Terminal_list: List[Terminal] = list()
        self.ThermalGeneratingUnit_list: List[ThermalGeneratingUnit] = list()
        self.TieFlow_list: List[TieFlow] = list()
        self.TransformerEnd_list: List[TransformerEnd] = list()
        self.VoltageLevel_list: List[VoltageLevel] = list()
        self.VoltageLimit_list: List[VoltageLimit] = list()
        self.VsCapabilityCurve_list: List[VsCapabilityCurve] = list()
        self.VsConverter_list: List[VsConverter] = list()
        self.WaveTrap_list: List[WaveTrap] = list()
        self.WindGeneratingUnit_list: List[WindGeneratingUnit] = list()
        self.WindPowerPlant_list: List[WindPowerPlant] = list()
        self.DCTopologicalIsland_list: List[DCTopologicalIsland] = list()
        self.DCTopologicalNode_list: List[DCTopologicalNode] = list()
        self.SvInjection_list: List[SvInjection] = list()
        self.SvPowerFlow_list: List[SvPowerFlow] = list()
        self.SvShuntCompensatorSections_list: List[SvShuntCompensatorSections] = list()
        self.SvStatus_list: List[SvStatus] = list()
        self.SvSwitch_list: List[SvSwitch] = list()
        self.SvTapStep_list: List[SvTapStep] = list()
        self.SvVoltage_list: List[SvVoltage] = list()
        self.TopologicalIsland_list: List[TopologicalIsland] = list()
        self.TopologicalNode_list: List[TopologicalNode] = list()
        self.ServiceLocation_list: List[ServiceLocation] = list()
        self.WorkLocation_list: List[WorkLocation] = list()
        self.CoordinateSystem_list: List[CoordinateSystem] = list()
        self.Location_list: List[Location] = list()
        self.PositionPoint_list: List[PositionPoint] = list()
        self.FullModel_list: List[FullModel] = list()
