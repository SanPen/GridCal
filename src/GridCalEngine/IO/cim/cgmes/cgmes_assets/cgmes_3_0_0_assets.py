from typing import List

from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_converter import ACDCConverter
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_converterdc_terminal import ACDCConverterDCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_terminal import ACDCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ac_line_segment import ACLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.active_power_limit import ActivePowerLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.apparent_power_limit import ApparentPowerLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.asynchronous_machine import AsynchronousMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.auxiliary_equipment import AuxiliaryEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.basic_interval_schedule import BasicIntervalSchedule
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.battery_unit import BatteryUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.bay import Bay
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.boundary_point import BoundaryPoint
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.breaker import Breaker
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.busbar_section import BusbarSection
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.bus_name_marker import BusNameMarker
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.caes_plant import CAESPlant
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.clamp import Clamp
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.cogeneration_plant import CogenerationPlant
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.combined_cycle_plant import CombinedCyclePlant
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conductor import Conductor
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conform_load import ConformLoad
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conform_load_group import ConformLoadGroup
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connectivity_node_container import ConnectivityNodeContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connector import Connector
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control_area import ControlArea
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control_area_generating_unit import ControlAreaGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.cs_converter import CsConverter
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.current_limit import CurrentLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.current_transformer import CurrentTransformer
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.curve import Curve
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.curve_data import CurveData
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.cut import Cut
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_base_terminal import DCBaseTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_breaker import DCBreaker
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_busbar import DCBusbar
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_chopper import DCChopper
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_conducting_equipment import DCConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_converter_unit import DCConverterUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_disconnector import DCDisconnector
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_equipment_container import DCEquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_ground import DCGround
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_line import DCLine
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_line_segment import DCLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_node import DCNode
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_series_device import DCSeriesDevice
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_shunt import DCShunt
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_switch import DCSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_terminal import DCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.disconnector import Disconnector
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.disconnecting_circuit_breaker import DisconnectingCircuitBreaker
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.earth_fault_compensator import EarthFaultCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_area import EnergyArea
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_connection import EnergyConnection
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_consumer import EnergyConsumer
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_scheduling_type import EnergySchedulingType
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_source import EnergySource
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_branch import EquivalentBranch
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_equipment import EquivalentEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_injection import EquivalentInjection
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_network import EquivalentNetwork
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_shunt import EquivalentShunt
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.external_network_injection import ExternalNetworkInjection
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.fault_indicator import FaultIndicator
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.fossil_fuel import FossilFuel
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.fuse import Fuse
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.geographical_region import GeographicalRegion
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ground import Ground
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ground_disconnector import GroundDisconnector
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.grounding_impedance import GroundingImpedance
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_generating_unit import HydroGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_power_plant import HydroPowerPlant
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_pump import HydroPump
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.jumper import Jumper
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.junction import Junction
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.line import Line
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.linear_shunt_compensator import LinearShuntCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_area import LoadArea
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_break_switch import LoadBreakSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_group import LoadGroup
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_response_characteristic import LoadResponseCharacteristic
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.non_conform_load import NonConformLoad
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.non_conform_load_group import NonConformLoadGroup
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.nonlinear_shunt_compensator import NonlinearShuntCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.nonlinear_shunt_compensator_point import \
    NonlinearShuntCompensatorPoint
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.nuclear_generating_unit import NuclearGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit import OperationalLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit_set import OperationalLimitSet
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit_type import OperationalLimitType
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.petersen_coil import PetersenCoil
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer import PhaseTapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_asymmetrical import PhaseTapChangerAsymmetrical
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_linear import PhaseTapChangerLinear
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_non_linear import PhaseTapChangerNonLinear
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_symmetrical import PhaseTapChangerSymmetrical
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_table import PhaseTapChangerTable
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_table_point import PhaseTapChangerTablePoint
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_tabular import PhaseTapChangerTabular
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.photo_voltaic_unit import PhotoVoltaicUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.post_line_sensor import PostLineSensor
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.potential_transformer import PotentialTransformer
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_connection import PowerElectronicsConnection
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_unit import PowerElectronicsUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_wind_unit import PowerElectronicsWindUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_transformer import PowerTransformer
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.protected_switch import ProtectedSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer import RatioTapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer_table import RatioTapChangerTable
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer_table_point import RatioTapChangerTablePoint
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.reactive_capability_curve import ReactiveCapabilityCurve
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_control import RegulatingControl
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regular_interval_schedule import RegularIntervalSchedule
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.reporting_group import ReportingGroup
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.rotating_machine import RotatingMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sensor import Sensor
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.season_day_type_schedule import SeasonDayTypeSchedule
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.series_compensator import SeriesCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.shunt_compensator import ShuntCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.solar_generating_unit import SolarGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.solar_power_plant import SolarPowerPlant
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.static_var_compensator import StaticVarCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sub_geographical_region import SubGeographicalRegion
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sub_load_area import SubLoadArea
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.substation import Substation
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.surge_arrester import SurgeArrester
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.switch import Switch
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.synchronous_machine import SynchronousMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer import TapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer_control import TapChangerControl
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer_table_point import TapChangerTablePoint
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.thermal_generating_unit import ThermalGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tie_flow import TieFlow
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.transformer_end import TransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.voltage_level import VoltageLevel
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.voltage_limit import VoltageLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.vs_capability_curve import VsCapabilityCurve
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.vs_converter import VsConverter
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wave_trap import WaveTrap
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wind_generating_unit import WindGeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wind_power_plant import WindPowerPlant
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_topological_island import DCTopologicalIsland
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_topological_node import DCTopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_injection import SvInjection
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_power_flow import SvPowerFlow
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_shunt_compensator_sections import SvShuntCompensatorSections
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_status import SvStatus
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_switch import SvSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_tap_step import SvTapStep
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_voltage import SvVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.topological_island import TopologicalIsland
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.service_location import ServiceLocation
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.work_location import WorkLocation
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.coordinate_system import CoordinateSystem
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.location import Location
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.position_point import PositionPoint


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
        }

        self.association_inverse_dict = {
            'Terminal.ConverterDCSides': 'ACDCConverter.PccTerminal',
            'ACDCConverterDCTerminal.DCConductingEquipment': 'ACDCConverter.DCTerminals',
            'ACDCConverter.DCTerminals': 'ACDCConverterDCTerminal.DCConductingEquipment',
            'OperationalLimitSet.Terminal': 'ACDCTerminal.OperationalLimitSet',
            'BusNameMarker.Terminal': 'ACDCTerminal.BusNameMarker',
            'Clamp.ACLineSegment': 'ACLineSegment.Clamp',
            'Cut.ACLineSegment': 'ACLineSegment.Cut',
            'Terminal.AuxiliaryEquipment': 'AuxiliaryEquipment.Terminal',
            'ConductingEquipment.BaseVoltage': 'BaseVoltage.ConductingEquipment',
            'VoltageLevel.BaseVoltage': 'BaseVoltage.VoltageLevel',
            'TransformerEnd.BaseVoltage': 'BaseVoltage.TransformerEnds',
            'TopologicalNode.BaseVoltage': 'BaseVoltage.TopologicalNode',
            'VoltageLevel.Bays': 'Bay.VoltageLevel',
            'ConnectivityNode.BoundaryPoint': 'BoundaryPoint.ConnectivityNode',
            'ACDCTerminal.BusNameMarker': 'BusNameMarker.Terminal',
            'ReportingGroup.BusNameMarker': 'BusNameMarker.ReportingGroup',
            'ThermalGeneratingUnit.CAESPlant': 'CAESPlant.ThermalGeneratingUnit',
            'ACLineSegment.Clamp': 'Clamp.ACLineSegment',
            'ThermalGeneratingUnit.CogenerationPlant': 'CogenerationPlant.ThermalGeneratingUnits',
            'ThermalGeneratingUnit.CombinedCyclePlant': 'CombinedCyclePlant.ThermalGeneratingUnits',
            'BaseVoltage.ConductingEquipment': 'ConductingEquipment.BaseVoltage',
            'Terminal.ConductingEquipment': 'ConductingEquipment.Terminals',
            'SvStatus.ConductingEquipment': 'ConductingEquipment.SvStatus',
            'ConformLoadGroup.EnergyConsumers': 'ConformLoad.LoadGroup',
            'ConformLoad.LoadGroup': 'ConformLoadGroup.EnergyConsumers',
            'BoundaryPoint.ConnectivityNode': 'ConnectivityNode.BoundaryPoint',
            'Terminal.ConnectivityNode': 'ConnectivityNode.Terminals',
            'ConnectivityNodeContainer.ConnectivityNodes': 'ConnectivityNode.ConnectivityNodeContainer',
            'TopologicalNode.ConnectivityNodes': 'ConnectivityNode.TopologicalNode',
            'ConnectivityNode.ConnectivityNodeContainer': 'ConnectivityNodeContainer.ConnectivityNodes',
            'TopologicalNode.ConnectivityNodeContainer': 'ConnectivityNodeContainer.TopologicalNode',
            'TieFlow.ControlArea': 'ControlArea.TieFlow',
            'ControlAreaGeneratingUnit.ControlArea': 'ControlArea.ControlAreaGeneratingUnit',
            'EnergyArea.ControlArea': 'ControlArea.EnergyArea',
            'ControlArea.ControlAreaGeneratingUnit': 'ControlAreaGeneratingUnit.ControlArea',
            'GeneratingUnit.ControlAreaGeneratingUnit': 'ControlAreaGeneratingUnit.GeneratingUnit',
            'CurveData.Curve': 'Curve.CurveDatas',
            'Curve.CurveDatas': 'CurveData.Curve',
            'ACLineSegment.Cut': 'Cut.ACLineSegment',
            'DCNode.DCTerminals': 'DCBaseTerminal.DCNode',
            'DCTopologicalNode.DCTerminals': 'DCBaseTerminal.DCTopologicalNode',
            'DCTerminal.DCConductingEquipment': 'DCConductingEquipment.DCTerminals',
            'Substation.DCConverterUnit': 'DCConverterUnit.Substation',
            'DCNode.DCEquipmentContainer': 'DCEquipmentContainer.DCNodes',
            'DCTopologicalNode.DCEquipmentContainer': 'DCEquipmentContainer.DCTopologicalNode',
            'SubGeographicalRegion.DCLines': 'DCLine.Region',
            'DCBaseTerminal.DCNode': 'DCNode.DCTerminals',
            'DCEquipmentContainer.DCNodes': 'DCNode.DCEquipmentContainer',
            'DCTopologicalNode.DCNodes': 'DCNode.DCTopologicalNode',
            'DCConductingEquipment.DCTerminals': 'DCTerminal.DCConductingEquipment',
            'ControlArea.EnergyArea': 'EnergyArea.ControlArea',
            'LoadResponseCharacteristic.EnergyConsumer': 'EnergyConsumer.LoadResponse',
            'EnergySource.EnergySchedulingType': 'EnergySchedulingType.EnergySource',
            'EnergySchedulingType.EnergySource': 'EnergySource.EnergySchedulingType',
            'EquipmentContainer.Equipments': 'Equipment.EquipmentContainer',
            'OperationalLimitSet.Equipment': 'Equipment.OperationalLimitSet',
            'Equipment.EquipmentContainer': 'EquipmentContainer.Equipments',
            'EquivalentNetwork.EquivalentEquipments': 'EquivalentEquipment.EquivalentNetwork',
            'ReactiveCapabilityCurve.EquivalentInjection': 'EquivalentInjection.ReactiveCapabilityCurve',
            'EquivalentEquipment.EquivalentNetwork': 'EquivalentNetwork.EquivalentEquipments',
            'ThermalGeneratingUnit.FossilFuels': 'FossilFuel.ThermalGeneratingUnit',
            'ControlAreaGeneratingUnit.GeneratingUnit': 'GeneratingUnit.ControlAreaGeneratingUnit',
            'RotatingMachine.GeneratingUnit': 'GeneratingUnit.RotatingMachine',
            'SubGeographicalRegion.Region': 'GeographicalRegion.Regions',
            'HydroPowerPlant.HydroGeneratingUnits': 'HydroGeneratingUnit.HydroPowerPlant',
            'HydroGeneratingUnit.HydroPowerPlant': 'HydroPowerPlant.HydroGeneratingUnits',
            'HydroPump.HydroPowerPlant': 'HydroPowerPlant.HydroPumps',
            'HydroPowerPlant.HydroPumps': 'HydroPump.HydroPowerPlant',
            'RotatingMachine.HydroPump': 'HydroPump.RotatingMachine',
            'SubGeographicalRegion.Lines': 'Line.Region',
            'SubLoadArea.LoadArea': 'LoadArea.SubLoadAreas',
            'SubLoadArea.LoadGroups': 'LoadGroup.SubLoadArea',
            'EnergyConsumer.LoadResponse': 'LoadResponseCharacteristic.EnergyConsumer',
            'NonConformLoadGroup.EnergyConsumers': 'NonConformLoad.LoadGroup',
            'NonConformLoad.LoadGroup': 'NonConformLoadGroup.EnergyConsumers',
            'NonlinearShuntCompensatorPoint.NonlinearShuntCompensator': 'NonlinearShuntCompensator.NonlinearShuntCompensatorPoints',
            'NonlinearShuntCompensator.NonlinearShuntCompensatorPoints': 'NonlinearShuntCompensatorPoint.NonlinearShuntCompensator',
            'OperationalLimitSet.OperationalLimitValue': 'OperationalLimit.OperationalLimitSet',
            'OperationalLimitType.OperationalLimit': 'OperationalLimit.OperationalLimitType',
            'ACDCTerminal.OperationalLimitSet': 'OperationalLimitSet.Terminal',
            'Equipment.OperationalLimitSet': 'OperationalLimitSet.Equipment',
            'OperationalLimit.OperationalLimitSet': 'OperationalLimitSet.OperationalLimitValue',
            'OperationalLimit.OperationalLimitType': 'OperationalLimitType.OperationalLimit',
            'TransformerEnd.PhaseTapChanger': 'PhaseTapChanger.TransformerEnd',
            'PhaseTapChangerTablePoint.PhaseTapChangerTable': 'PhaseTapChangerTable.PhaseTapChangerTablePoint',
            'PhaseTapChangerTabular.PhaseTapChangerTable': 'PhaseTapChangerTable.PhaseTapChangerTabular',
            'PhaseTapChangerTable.PhaseTapChangerTablePoint': 'PhaseTapChangerTablePoint.PhaseTapChangerTable',
            'PhaseTapChangerTable.PhaseTapChangerTabular': 'PhaseTapChangerTabular.PhaseTapChangerTable',
            'PowerElectronicsUnit.PowerElectronicsConnection': 'PowerElectronicsConnection.PowerElectronicsUnit',
            'PowerElectronicsConnection.PowerElectronicsUnit': 'PowerElectronicsUnit.PowerElectronicsConnection',
            'Location.PowerSystemResources': 'PowerSystemResource.Location',
            'PowerTransformerEnd.PowerTransformer': 'PowerTransformer.PowerTransformerEnd',
            'PowerTransformer.PowerTransformerEnd': 'PowerTransformerEnd.PowerTransformer',
            'RatioTapChangerTable.RatioTapChanger': 'RatioTapChanger.RatioTapChangerTable',
            'TransformerEnd.RatioTapChanger': 'RatioTapChanger.TransformerEnd',
            'RatioTapChanger.RatioTapChangerTable': 'RatioTapChangerTable.RatioTapChanger',
            'RatioTapChangerTablePoint.RatioTapChangerTable': 'RatioTapChangerTable.RatioTapChangerTablePoint',
            'RatioTapChangerTable.RatioTapChangerTablePoint': 'RatioTapChangerTablePoint.RatioTapChangerTable',
            'EquivalentInjection.ReactiveCapabilityCurve': 'ReactiveCapabilityCurve.EquivalentInjection',
            'SynchronousMachine.InitialReactiveCapabilityCurve': 'ReactiveCapabilityCurve.InitiallyUsedBySynchronousMachines',
            'RegulatingCondEq.RegulatingControl': 'RegulatingControl.RegulatingCondEq',
            'Terminal.RegulatingControl': 'RegulatingControl.Terminal',
            'BusNameMarker.ReportingGroup': 'ReportingGroup.BusNameMarker',
            'TopologicalNode.ReportingGroup': 'ReportingGroup.TopologicalNode',
            'GeneratingUnit.RotatingMachine': 'RotatingMachine.GeneratingUnit',
            'HydroPump.RotatingMachine': 'RotatingMachine.HydroPump',
            'SvShuntCompensatorSections.ShuntCompensator': 'ShuntCompensator.SvShuntCompensatorSections',
            'SolarPowerPlant.SolarGeneratingUnits': 'SolarGeneratingUnit.SolarPowerPlant',
            'SolarGeneratingUnit.SolarPowerPlant': 'SolarPowerPlant.SolarGeneratingUnits',
            'DCLine.Region': 'SubGeographicalRegion.DCLines',
            'GeographicalRegion.Regions': 'SubGeographicalRegion.Region',
            'Line.Region': 'SubGeographicalRegion.Lines',
            'Substation.Region': 'SubGeographicalRegion.Substations',
            'LoadArea.SubLoadAreas': 'SubLoadArea.LoadArea',
            'LoadGroup.SubLoadArea': 'SubLoadArea.LoadGroups',
            'DCConverterUnit.Substation': 'Substation.DCConverterUnit',
            'SubGeographicalRegion.Substations': 'Substation.Region',
            'VoltageLevel.Substation': 'Substation.VoltageLevels',
            'SvSwitch.Switch': 'Switch.SvSwitch',
            'ReactiveCapabilityCurve.InitiallyUsedBySynchronousMachines': 'SynchronousMachine.InitialReactiveCapabilityCurve',
            'TapChangerControl.TapChanger': 'TapChanger.TapChangerControl',
            'SvTapStep.TapChanger': 'TapChanger.SvTapStep',
            'TapChanger.TapChangerControl': 'TapChangerControl.TapChanger',
            'ACDCConverter.PccTerminal': 'Terminal.ConverterDCSides',
            'AuxiliaryEquipment.Terminal': 'Terminal.AuxiliaryEquipment',
            'ConductingEquipment.Terminals': 'Terminal.ConductingEquipment',
            'ConnectivityNode.Terminals': 'Terminal.ConnectivityNode',
            'RegulatingControl.Terminal': 'Terminal.RegulatingControl',
            'TransformerEnd.Terminal': 'Terminal.TransformerEnd',
            'TieFlow.Terminal': 'Terminal.TieFlow',
            'SvPowerFlow.Terminal': 'Terminal.SvPowerFlow',
            'TopologicalNode.Terminal': 'Terminal.TopologicalNode',
            'CAESPlant.ThermalGeneratingUnit': 'ThermalGeneratingUnit.CAESPlant',
            'CogenerationPlant.ThermalGeneratingUnits': 'ThermalGeneratingUnit.CogenerationPlant',
            'CombinedCyclePlant.ThermalGeneratingUnits': 'ThermalGeneratingUnit.CombinedCyclePlant',
            'FossilFuel.ThermalGeneratingUnit': 'ThermalGeneratingUnit.FossilFuels',
            'ControlArea.TieFlow': 'TieFlow.ControlArea',
            'Terminal.TieFlow': 'TieFlow.Terminal',
            'BaseVoltage.TransformerEnds': 'TransformerEnd.BaseVoltage',
            'PhaseTapChanger.TransformerEnd': 'TransformerEnd.PhaseTapChanger',
            'RatioTapChanger.TransformerEnd': 'TransformerEnd.RatioTapChanger',
            'Terminal.TransformerEnd': 'TransformerEnd.Terminal',
            'BaseVoltage.VoltageLevel': 'VoltageLevel.BaseVoltage',
            'Bay.VoltageLevel': 'VoltageLevel.Bays',
            'Substation.VoltageLevels': 'VoltageLevel.Substation',
            'VsConverter.CapabilityCurve': 'VsCapabilityCurve.VsConverterDCSides',
            'VsCapabilityCurve.VsConverterDCSides': 'VsConverter.CapabilityCurve',
            'WindPowerPlant.WindGeneratingUnits': 'WindGeneratingUnit.WindPowerPlant',
            'WindGeneratingUnit.WindPowerPlant': 'WindPowerPlant.WindGeneratingUnits',
            'DCTopologicalNode.DCTopologicalIsland': 'DCTopologicalIsland.DCTopologicalNodes',
            'DCTopologicalIsland.DCTopologicalNodes': 'DCTopologicalNode.DCTopologicalIsland',
            'DCBaseTerminal.DCTopologicalNode': 'DCTopologicalNode.DCTerminals',
            'DCEquipmentContainer.DCTopologicalNode': 'DCTopologicalNode.DCEquipmentContainer',
            'DCNode.DCTopologicalNode': 'DCTopologicalNode.DCNodes',
            'TopologicalNode.SvInjection': 'SvInjection.TopologicalNode',
            'Terminal.SvPowerFlow': 'SvPowerFlow.Terminal',
            'ShuntCompensator.SvShuntCompensatorSections': 'SvShuntCompensatorSections.ShuntCompensator',
            'ConductingEquipment.SvStatus': 'SvStatus.ConductingEquipment',
            'Switch.SvSwitch': 'SvSwitch.Switch',
            'TapChanger.SvTapStep': 'SvTapStep.TapChanger',
            'TopologicalNode.SvVoltage': 'SvVoltage.TopologicalNode',
            'TopologicalNode.AngleRefTopologicalIsland': 'TopologicalIsland.AngleRefTopologicalNode',
            'TopologicalNode.TopologicalIsland': 'TopologicalIsland.TopologicalNodes',
            'SvInjection.TopologicalNode': 'TopologicalNode.SvInjection',
            'SvVoltage.TopologicalNode': 'TopologicalNode.SvVoltage',
            'TopologicalIsland.AngleRefTopologicalNode': 'TopologicalNode.AngleRefTopologicalIsland',
            'TopologicalIsland.TopologicalNodes': 'TopologicalNode.TopologicalIsland',
            'BaseVoltage.TopologicalNode': 'TopologicalNode.BaseVoltage',
            'ConnectivityNode.TopologicalNode': 'TopologicalNode.ConnectivityNodes',
            'ConnectivityNodeContainer.TopologicalNode': 'TopologicalNode.ConnectivityNodeContainer',
            'Terminal.TopologicalNode': 'TopologicalNode.Terminal',
            'ReportingGroup.TopologicalNode': 'TopologicalNode.ReportingGroup',
            'Location.CoordinateSystem': 'CoordinateSystem.Locations',
            'CoordinateSystem.Locations': 'Location.CoordinateSystem',
            'PowerSystemResource.Location': 'Location.PowerSystemResources',
            'PositionPoint.Location': 'Location.PositionPoints',
            'Location.PositionPoints': 'PositionPoint.Location',
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