from typing import List

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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.full_model import FullModel
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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_asymmetrical import \
    PhaseTapChangerAsymmetrical
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_linear import PhaseTapChangerLinear
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_non_linear import PhaseTapChangerNonLinear
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_symmetrical import \
    PhaseTapChangerSymmetrical
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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_shunt_compensator_sections import \
    SvShuntCompensatorSections
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_tap_step import SvTapStep
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_voltage import SvVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_topological_node import DCTopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_island import TopologicalIsland
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.coordinate_system import CoordinateSystem
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.location import Location
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.position_point import PositionPoint


class Cgmes_2_4_15_Assets:

    def __init__(self):
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
            ('EnergySource', 'EnergySchedulingType'): 'EnergySource',
            ('EnergySource', 'BaseVoltage'): 'ConductingEquipment',
            ('EnergySource', 'EquipmentContainer'): 'Equipments',
            ('RegulatingControl', 'Terminal'): 'RegulatingControl',
            ('ControlAreaGeneratingUnit', 'ControlArea'): 'ControlAreaGeneratingUnit',
            ('ControlAreaGeneratingUnit', 'GeneratingUnit'): 'ControlAreaGeneratingUnit',
            ('NuclearGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('Line', 'Region'): 'Lines',
            ('ApparentPowerLimit', 'OperationalLimitSet'): 'OperationalLimitValue',
            ('ApparentPowerLimit', 'OperationalLimitType'): 'OperationalLimit',
            ('ControlArea', 'EnergyArea'): 'ControlArea',
            ('RatioTapChangerTablePoint', 'RatioTapChangerTable'): 'RatioTapChangerTablePoint',
            ('SubGeographicalRegion', 'Region'): 'Regions',
            ('PowerTransformer', 'BaseVoltage'): 'ConductingEquipment',
            ('PowerTransformer', 'EquipmentContainer'): 'Equipments',
            ('Terminal', 'ConductingEquipment'): 'Terminals',
            ('Terminal', 'ConnectivityNode'): 'Terminals',
            ('Terminal', 'BusNameMarker'): 'Terminal',
            ('Terminal', 'TopologicalNode'): 'Terminal',
            ('EquivalentBranch', 'EquivalentNetwork'): 'EquivalentEquipments',
            ('EquivalentBranch', 'BaseVoltage'): 'ConductingEquipment',
            ('EquivalentBranch', 'EquipmentContainer'): 'Equipments',
            ('ConformLoadGroup', 'SubLoadArea'): 'LoadGroups',
            ('Disconnector', 'BaseVoltage'): 'ConductingEquipment',
            ('Disconnector', 'EquipmentContainer'): 'Equipments',
            ('BusNameMarker', 'ReportingGroup'): 'BusNameMarker',
            ('ThermalGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('DCConverterUnit', 'Substation'): 'DCConverterUnit',
            ('LoadBreakSwitch', 'BaseVoltage'): 'ConductingEquipment',
            ('LoadBreakSwitch', 'EquipmentContainer'): 'Equipments',
            ('FossilFuel', 'ThermalGeneratingUnit'): 'FossilFuels',
            ('PowerTransformerEnd', 'PowerTransformer'): 'PowerTransformerEnd',
            ('PowerTransformerEnd', 'BaseVoltage'): 'TransformerEnds',
            ('PowerTransformerEnd', 'Terminal'): 'TransformerEnd',
            ('TapChangerControl', 'Terminal'): 'RegulatingControl',
            ('RatioTapChanger', 'TransformerEnd'): 'RatioTapChanger',
            ('RatioTapChanger', 'RatioTapChangerTable'): 'RatioTapChanger',
            ('RatioTapChanger', 'TapChangerControl'): 'TapChanger',
            ('DCSeriesDevice', 'EquipmentContainer'): 'Equipments',
            ('DCShunt', 'EquipmentContainer'): 'Equipments',
            ('ConformLoad', 'LoadGroup'): 'EnergyConsumers',
            ('ConformLoad', 'LoadResponse'): 'EnergyConsumer',
            ('ConformLoad', 'BaseVoltage'): 'ConductingEquipment',
            ('ConformLoad', 'EquipmentContainer'): 'Equipments',
            ('DCLine', 'Region'): 'DCLines',
            ('BusbarSection', 'BaseVoltage'): 'ConductingEquipment',
            ('BusbarSection', 'EquipmentContainer'): 'Equipments',
            ('HydroGeneratingUnit', 'HydroPowerPlant'): 'HydroGeneratingUnits',
            ('HydroGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('SynchronousMachine', 'InitialReactiveCapabilityCurve'): 'InitiallyUsedBySynchronousMachines',
            ('SynchronousMachine', 'GeneratingUnit'): 'RotatingMachine',
            ('SynchronousMachine', 'RegulatingControl'): 'RegulatingCondEq',
            ('SynchronousMachine', 'BaseVoltage'): 'ConductingEquipment',
            ('SynchronousMachine', 'EquipmentContainer'): 'Equipments',
            ('OperationalLimitSet', 'Equipment'): 'OperationalLimitSet',
            ('OperationalLimitSet', 'Terminal'): 'OperationalLimitSet',
            ('VoltageLimit', 'OperationalLimitSet'): 'OperationalLimitValue',
            ('VoltageLimit', 'OperationalLimitType'): 'OperationalLimit',
            ('VsConverter', 'CapabilityCurve'): 'VsConverterDCSides',
            ('VsConverter', 'PccTerminal'): 'ConverterDCSides',
            ('VsConverter', 'BaseVoltage'): 'ConductingEquipment',
            ('VsConverter', 'EquipmentContainer'): 'Equipments',
            ('HydroPump', 'RotatingMachine'): 'HydroPump',
            ('HydroPump', 'HydroPowerPlant'): 'HydroPumps',
            ('HydroPump', 'EquipmentContainer'): 'Equipments',
            ('GroundingImpedance', 'BaseVoltage'): 'ConductingEquipment',
            ('GroundingImpedance', 'EquipmentContainer'): 'Equipments',
            ('Ground', 'BaseVoltage'): 'ConductingEquipment',
            ('Ground', 'EquipmentContainer'): 'Equipments',
            ('PetersenCoil', 'BaseVoltage'): 'ConductingEquipment',
            ('PetersenCoil', 'EquipmentContainer'): 'Equipments',
            ('AsynchronousMachine', 'GeneratingUnit'): 'RotatingMachine',
            ('AsynchronousMachine', 'RegulatingControl'): 'RegulatingCondEq',
            ('AsynchronousMachine', 'BaseVoltage'): 'ConductingEquipment',
            ('AsynchronousMachine', 'EquipmentContainer'): 'Equipments',
            ('DCDisconnector', 'EquipmentContainer'): 'Equipments',
            ('Breaker', 'BaseVoltage'): 'ConductingEquipment',
            ('Breaker', 'EquipmentContainer'): 'Equipments',
            ('WindGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('EnergyConsumer', 'LoadResponse'): 'EnergyConsumer',
            ('EnergyConsumer', 'BaseVoltage'): 'ConductingEquipment',
            ('EnergyConsumer', 'EquipmentContainer'): 'Equipments',
            ('PhaseTapChangerAsymmetrical', 'TransformerEnd'): 'PhaseTapChanger',
            ('PhaseTapChangerAsymmetrical', 'TapChangerControl'): 'TapChanger',
            ('LinearShuntCompensator', 'RegulatingControl'): 'RegulatingCondEq',
            ('LinearShuntCompensator', 'BaseVoltage'): 'ConductingEquipment',
            ('LinearShuntCompensator', 'EquipmentContainer'): 'Equipments',
            ('SeriesCompensator', 'BaseVoltage'): 'ConductingEquipment',
            ('SeriesCompensator', 'EquipmentContainer'): 'Equipments',
            ('VoltageLevel', 'Substation'): 'VoltageLevels',
            ('VoltageLevel', 'BaseVoltage'): 'VoltageLevel',
            ('SubLoadArea', 'LoadArea'): 'SubLoadAreas',
            ('ExternalNetworkInjection', 'RegulatingControl'): 'RegulatingCondEq',
            ('ExternalNetworkInjection', 'BaseVoltage'): 'ConductingEquipment',
            ('ExternalNetworkInjection', 'EquipmentContainer'): 'Equipments',
            ('GeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('GroundDisconnector', 'BaseVoltage'): 'ConductingEquipment',
            ('GroundDisconnector', 'EquipmentContainer'): 'Equipments',
            ('DCBusbar', 'EquipmentContainer'): 'Equipments',
            ('PhaseTapChangerSymmetrical', 'TransformerEnd'): 'PhaseTapChanger',
            ('PhaseTapChangerSymmetrical', 'TapChangerControl'): 'TapChanger',
            ('NonlinearShuntCompensator', 'RegulatingControl'): 'RegulatingCondEq',
            ('NonlinearShuntCompensator', 'BaseVoltage'): 'ConductingEquipment',
            ('NonlinearShuntCompensator', 'EquipmentContainer'): 'Equipments',
            ('Substation', 'Region'): 'Substations',
            ('ConnectivityNode', 'ConnectivityNodeContainer'): 'ConnectivityNodes',
            ('ConnectivityNode', 'TopologicalNode'): 'ConnectivityNodes',
            ('TieFlow', 'ControlArea'): 'TieFlow',
            ('TieFlow', 'Terminal'): 'TieFlow',
            ('DCGround', 'EquipmentContainer'): 'Equipments',
            ('DCLineSegment', 'PerLengthParameter'): 'DCLineSegments',
            ('DCLineSegment', 'EquipmentContainer'): 'Equipments',
            ('Switch', 'BaseVoltage'): 'ConductingEquipment',
            ('Switch', 'EquipmentContainer'): 'Equipments',
            ('DCTerminal', 'DCConductingEquipment'): 'DCTerminals',
            ('DCTerminal', 'DCNode'): 'DCTerminals',
            ('DCTerminal', 'BusNameMarker'): 'Terminal',
            ('DCTerminal', 'DCTopologicalNode'): 'DCTerminals',
            ('ACLineSegment', 'BaseVoltage'): 'ConductingEquipment',
            ('ACLineSegment', 'EquipmentContainer'): 'Equipments',
            ('StaticVarCompensator', 'RegulatingControl'): 'RegulatingCondEq',
            ('StaticVarCompensator', 'BaseVoltage'): 'ConductingEquipment',
            ('StaticVarCompensator', 'EquipmentContainer'): 'Equipments',
            ('ActivePowerLimit', 'OperationalLimitSet'): 'OperationalLimitValue',
            ('ActivePowerLimit', 'OperationalLimitType'): 'OperationalLimit',
            ('SolarGeneratingUnit', 'EquipmentContainer'): 'Equipments',
            ('DCNode', 'DCEquipmentContainer'): 'DCNodes',
            ('DCNode', 'DCTopologicalNode'): 'DCNodes',
            ('PhaseTapChangerLinear', 'TransformerEnd'): 'PhaseTapChanger',
            ('PhaseTapChangerLinear', 'TapChangerControl'): 'TapChanger',
            ('MutualCoupling', 'Second_Terminal'): 'HasSecondMutualCoupling',
            ('MutualCoupling', 'First_Terminal'): 'HasFirstMutualCoupling',
            ('CsConverter', 'PccTerminal'): 'ConverterDCSides',
            ('CsConverter', 'BaseVoltage'): 'ConductingEquipment',
            ('CsConverter', 'EquipmentContainer'): 'Equipments',
            ('DCSwitch', 'EquipmentContainer'): 'Equipments',
            ('DCBreaker', 'EquipmentContainer'): 'Equipments',
            ('NonlinearShuntCompensatorPoint', 'NonlinearShuntCompensator'): 'NonlinearShuntCompensatorPoints',
            ('Junction', 'BaseVoltage'): 'ConductingEquipment',
            ('Junction', 'EquipmentContainer'): 'Equipments',
            ('DCChopper', 'EquipmentContainer'): 'Equipments',
            ('PhaseTapChangerTablePoint', 'PhaseTapChangerTable'): 'PhaseTapChangerTablePoint',
            ('CurveData', 'Curve'): 'CurveDatas',
            ('NonConformLoadGroup', 'SubLoadArea'): 'LoadGroups',
            ('EquivalentShunt', 'EquivalentNetwork'): 'EquivalentEquipments',
            ('EquivalentShunt', 'BaseVoltage'): 'ConductingEquipment',
            ('EquivalentShunt', 'EquipmentContainer'): 'Equipments',
            ('CurrentLimit', 'OperationalLimitSet'): 'OperationalLimitValue',
            ('CurrentLimit', 'OperationalLimitType'): 'OperationalLimit',
            ('ACDCConverterDCTerminal', 'DCConductingEquipment'): 'DCTerminals',
            ('ACDCConverterDCTerminal', 'DCNode'): 'DCTerminals',
            ('ACDCConverterDCTerminal', 'BusNameMarker'): 'Terminal',
            ('ACDCConverterDCTerminal', 'DCTopologicalNode'): 'DCTerminals',
            ('Bay', 'VoltageLevel'): 'Bays',
            ('PhaseTapChangerTabular', 'PhaseTapChangerTable'): 'PhaseTapChangerTabular',
            ('PhaseTapChangerTabular', 'TransformerEnd'): 'PhaseTapChanger',
            ('PhaseTapChangerTabular', 'TapChangerControl'): 'TapChanger',
            ('EquivalentInjection', 'ReactiveCapabilityCurve'): 'EquivalentInjection',
            ('EquivalentInjection', 'EquivalentNetwork'): 'EquivalentEquipments',
            ('EquivalentInjection', 'BaseVoltage'): 'ConductingEquipment',
            ('EquivalentInjection', 'EquipmentContainer'): 'Equipments',
            ('NonConformLoad', 'LoadGroup'): 'EnergyConsumers',
            ('NonConformLoad', 'LoadResponse'): 'EnergyConsumer',
            ('NonConformLoad', 'BaseVoltage'): 'ConductingEquipment',
            ('NonConformLoad', 'EquipmentContainer'): 'Equipments',
            ('PositionPoint', 'Location'): 'PositionPoints',
            ('Location', 'PowerSystemResources'): 'Location',
            ('Location', 'CoordinateSystem'): 'Location',
            ('DCTopologicalIsland', 'DCTopologicalNodes'): 'DCTopologicalIsland',
            ('SvShuntCompensatorSections', 'ShuntCompensator'): 'SvShuntCompensatorSections',
            ('SvInjection', 'TopologicalNode'): 'SvInjection',
            ('SvTapStep', 'TapChanger'): 'SvTapStep',
            ('TopologicalIsland', 'AngleRefTopologicalNode'): 'AngleRefTopologicalIsland',
            ('TopologicalIsland', 'TopologicalNodes'): 'TopologicalIsland',
            ('SvStatus', 'ConductingEquipment'): 'SvStatus',
            ('SvVoltage', 'TopologicalNode'): 'SvVoltage',
            ('SvPowerFlow', 'Terminal'): 'SvPowerFlow',
            ('TopologicalNode', 'BaseVoltage'): 'TopologicalNode',
            ('TopologicalNode', 'ConnectivityNodeContainer'): 'TopologicalNode',
            ('TopologicalNode', 'ReportingGroup'): 'TopologicalNode',
            ('DCTopologicalNode', 'DCEquipmentContainer'): 'DCTopologicalNode',
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
