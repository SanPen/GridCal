# SPDX-License-Identifier: MPL-2.0
"""PSS/E DYR bindings to existing native RMS templates.

Machine-base impedances/inertia are converted explicitly. Controllers are
assembled by reviewed ports, never attached as complete physical devices merely
because their catalogue name matches a DYR record.
"""
from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING
import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.IO.raw.raw_types import RawGeneratorLike
from VeraGridEngine.IO.raw.psse_file_type import PsseFileType
from VeraGridEngine.IO.raw.psse_conversion_report import PsseConversionStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord, UserModelType
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus, BusIdentifier, EquipmentKind
from VeraGridEngine.Templates.Rms.gencls_rms_template import (
    get_complete_gencls_rms_template, GenclsMechanicalInput, GenclsRmsParameters,
    configure_gencls_block,
)
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import (
    get_genrou_rms_template, get_tgov1_rms_template, get_exst1_rms_template,
    get_esst3a_rms_template, GenrouRmsParameters, Tgov1RmsParameters,
    configure_genrou_block, configure_tgov1_block, set_rms_model_parameter, GenrouSaturationMode,
    _anti_windup_state_derivative,
)
from VeraGridEngine.Templates.Rms.international_standards import (
    build_international_standard_template, _normalize_imported_variable_names,
)
from VeraGridEngine.Templates.Rms.international_standards.governors.ivogo import build_ivogo_template
from VeraGridEngine.Templates.Rms.international_standards.governors.degov1 import DieselGovernorParameters, EngineDroopFeedback, build_degov1_template
from VeraGridEngine.Templates.Rms.international_standards.governors.ggov1 import (
    TrackedGovernorParameters, GovernorDroopFeedback, FuelFlowCharacteristic, build_ggov1_template)
from VeraGridEngine.Templates.Rms.international_standards.governors.hygov2 import CascadedHydroGovernorParameters, build_hygov2_template
from VeraGridEngine.Templates.Rms.international_standards.governors.pidgov import HydroDroopFeedback, PidHydroGovernorParameters, build_pidgov_template
from VeraGridEngine.Templates.Rms.international_standards.governors.hygov import NonlinearHydroGovernorParameters, build_hygov_template
from VeraGridEngine.Templates.Rms.international_standards.governors.tgov1d import build_tgov1d_template
from VeraGridEngine.Templates.Rms.international_standards.governors.gast import GasGovernorParameters, build_gast_template
from VeraGridEngine.Templates.Rms.international_standards.governors.ieesgo import SteamGovernorParameters, build_ieesgo_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.ivost import build_ivost_template
from VeraGridEngine.Templates.Rms.rational_controller import RationalStageParameters
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.stab1 import build_stab1_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.stab2a import build_stab2a_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.stab3 import build_stab3_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.stab4 import build_stab4_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.stabni import build_stabni_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.ieeest import IeeestParameters, build_ieeest_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.iee2st import Iee2stParameters, build_iee2st_template
from VeraGridEngine.Templates.Rms.international_standards.voltage_compensators.comp import build_comp_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_limiters.mnlex1 import build_mnlex1_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_limiters.mnlex2 import build_mnlex2_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_limiters.mnlex3 import build_mnlex3_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.exst2 import CompoundExciterKind, build_exst2_template
from VeraGridEngine.Templates.Rms.international_standards.synchronous_machines.gentra import build_gentra_template
from VeraGridEngine.Templates.Rms.international_standards.synchronous_machines.gensae import build_gensae_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.scrx import build_scrx_template
from VeraGridEngine.Templates.Rms.international_standards.governors.ieeeg3 import (
    HydraulicGovernorParameters, build_ieeeg3_template)
from VeraGridEngine.Templates.Rms.ramp_tracking_stabilizer import RampStabilizerParameters, StabilizerInterface
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.pss2a import build_pss2a_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.pss2b import build_pss2b_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.pss2c import build_pss2c_template
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.pss3b import QuadraticDualStabilizerParameters, build_pss3b_template
from VeraGridEngine.Templates.Rms.international_standards.governors.ieeeg1 import (
    MultiStageSteamGovernorParameters, build_ieeeg1_template)
from VeraGridEngine.Templates.Rms.international_standards.governors.lcfb1 import (
    TurbineLoadControllerParameters, build_lcfb1_template)
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esac8b import build_esac8b_template
from VeraGridEngine.Templates.Rms.compound_excitation_supply import CompoundSupplyParameters
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.dc4c import build_dc4c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.dc4b import build_dc4b_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac1c import build_ac1c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac2c import build_ac2c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac5c import build_ac5c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.expic1 import PiCompoundFieldParameters, build_expic1_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.exni import BridgeExcitationSupply, build_exni_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ieet1b import RotatingRateFeedbackSignal, build_ieet1b_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st6c import CurrentLimitedFieldParameters, FieldRegulatorLimiterLocation, build_st6c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st5c import build_st5c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st5b import ParallelChannelExciterParameters, build_st5b_template
from VeraGridEngine.Templates.Rms.cascaded_brushless_circuit import CascadedBrushlessCircuit, CascadedLimiterLocation, CascadedPowerSupply
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac7c import build_ac7c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac7b import CascadedBrushlessParameters, build_ac7b_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac8c import build_ac8c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac8b import PidBrushlessExciterParameters, CompoundPidPowerCircuit, build_ac8b_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import FilteredCompoundPiParameters, CompoundExcitationSource, CompoundSupplementLocation, build_st4c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4b import CompoundPiExciterParameters, build_st4b_template
from VeraGridEngine.Templates.Rms.self_feedback_exciter import ExcitationBridgeDynamics, ExcitationLimiterLocation, SelfFeedbackExciterParameters, build_self_feedback_exciter
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esst1a import StaticMinimumExcitationLocation, StaticMaximumExcitationLocation, StaticStabilizerLocation, TerminalFedExciterParameters, build_esst1a_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.budczt import LimitedPiExciterParameters, build_budczt_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.bbsex1 import AuxiliaryVoltageLocation, FeedbackStaticExciterParameters, build_bbsex1_template
from VeraGridEngine.Templates.Rms.thevenin_exciter import CompoundCapabilityLocation, TheveninExciterParameters, build_thevenin_exciter
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, RotatingLimiterLocation, build_dc_exciter
from VeraGridEngine.Templates.Rms.electromechanical_exciter import (
    ElectromechanicalExciterKind, ElectromechanicalExciterParameters, build_electromechanical_exciter)
from VeraGridEngine.Templates.Rms.alternator_rectifier import (
    AlternatorRectifierKind, AlternatorRectifierParameters, RectifierLimiterLocation, build_alternator_rectifier,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import InternationalStandardModel, DeviceType, VarPowerFlowReferenceType
if TYPE_CHECKING:
    from VeraGridEngine.IO.raw.auxiliary_to_veragrid import PsseAuxiliaryConverter


class PsseDynamicRole(Enum):
    """Distinct physical and controller attachment roles."""
    MACHINE = 'machine'
    GOVERNOR = 'governor'
    TURBINE_LOAD_CONTROLLER = 'turbine_load_controller'
    EXCITER = 'exciter'
    STABILIZER = 'stabilizer'
    COMPENSATOR = 'compensator'
    UNDEREXCITATION = 'underexcitation'


class PsseStabilizerInput(Enum):
    """Documented integer selectors, owned exclusively by the source adapter."""

    BLOCKED = 0
    ROTOR_SPEED = 1
    BUS_FREQUENCY = 2
    ELECTRICAL_POWER = 3
    ACCELERATING_POWER = 4
    BUS_VOLTAGE = 5
    VOLTAGE_DERIVATIVE = 6


class PsseDynamicBinding:
    """Explicit source model, role and native parameter-name correspondence."""
    __slots__ = ('role', 'standard', 'parameters', 'dc_kind', 'electromechanical_kind')

    def __init__(self, role: PsseDynamicRole, standard: InternationalStandardModel | None,
                 parameters: tuple[tuple[str, str], ...] = (),
                 dc_kind: DcExciterKind | None = None,
                 electromechanical_kind: ElectromechanicalExciterKind | None = None) -> None:
        """Store a reviewed mapping, not a name-based inference.

        :param role: Physical/controller role.
        :param standard: Existing catalogue builder, or None for network-ready templates.
        :param parameters: Exact CON-name to symbolic-parameter pairs.
        :param dc_kind: Reviewed DC-exciter equation structure, when applicable.
        :param electromechanical_kind: Reviewed reset and rapid-forcing structure, when applicable.
        """
        self.role: PsseDynamicRole = role
        self.standard: InternationalStandardModel | None = standard
        self.parameters: tuple[tuple[str, str], ...] = parameters
        self.dc_kind: DcExciterKind | None = dc_kind
        self.electromechanical_kind: ElectromechanicalExciterKind | None = electromechanical_kind


def dynamic_record_name(record: DyrRecord) -> str:
    """Select reviewed source identity without renaming a user-model assignment.

    Generic user headers never resolve by arbitrary subroutine name alone.
    Only a release-owned schema with a matching complete calling contract may
    select a user-model binding. Original keyword, header and tokens stay intact.

    :param record: Source record retaining its parser-selected schema.
    :return: Reviewed source subroutine or original assignment keyword.
    """
    if (record.user_schema is not None and record.user_header is not None
            and record.model.upper() == 'USRMDL' and record.user_schema.matches(record.user_header)):
        return record.user_schema.layout.name
    else:
        return record.model.upper()


def dynamic_binding(model: str) -> PsseDynamicBinding | None:
    """Get the explicit standard-library binding.

    :param model: PSS/E model name.
    :return: Reviewed binding or None; no reflection or plugin execution.
    """
    ac1_parameters: tuple[tuple[str, str], ...] = (('TR','avr_tR'),('TB','avr_tB'),('TC','avr_tC'),('KA','avr_Ka'),('TA','avr_tA'),('VRMAX','avr_VrMaxPu'),('VRMIN','avr_VrMinPu'),('TE','avr_tE'),('KF','avr_Kf'),('TF','avr_tF'),('KC','avr_Kc'),('KD','avr_Kd'),('KE','avr_Ke'),('E1','avr_VExcLowPu'),('SE1','avr_VExcSatLowPu'),('E2','avr_VExcHighPu'),('SE2','avr_VExcSatHighPu'))
    amplifier_ac1_parameters: tuple[tuple[str, str], ...] = tuple(
        ('VAMAX' if source == 'VRMAX' else ('VAMIN' if source == 'VRMIN' else source), target)
        for source, target in ac1_parameters)
    gated_ac1_parameters: tuple[tuple[str, str], ...] = amplifier_ac1_parameters + (('VRMAX','BridgeVRMAX'),('VRMIN','BridgeVRMIN'))
    shaped_ac5_parameters: tuple[tuple[str,str],...] = tuple(('TF1' if source == 'TF' else source,target) for source,target in ac1_parameters if source not in ('TB','TC')) + (('TF2','avr_tB'),('TF3','avr_tC'),('VFEMAX','VFEMAX'),('VEMIN','VEMIN'))
    bindings: dict[str, PsseDynamicBinding] = dict(
        GENCLS=PsseDynamicBinding(PsseDynamicRole.MACHINE, None),
        GENROU=PsseDynamicBinding(PsseDynamicRole.MACHINE, None),
        GENROE=PsseDynamicBinding(PsseDynamicRole.MACHINE, InternationalStandardModel.GENROE),
        GENTRA=PsseDynamicBinding(PsseDynamicRole.MACHINE, InternationalStandardModel.GENTRA),
        GENSAL=PsseDynamicBinding(PsseDynamicRole.MACHINE, InternationalStandardModel.GENSAL),
        GENSAE=PsseDynamicBinding(PsseDynamicRole.MACHINE, InternationalStandardModel.GENSAE),
        GGOV1=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.GGOV1),
        GGOV1D=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.GGOV1D),
        GGOV1DU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.GGOV1D),
        DEGOV=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.DEGOV),
        DEGOV1D=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.DEGOV1D),
        DEGOV1DU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.DEGOV1D),
        DEGOV1=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.DEGOV1),
        IEEEG1=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEEEG1),
        IEEEG1D=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEEEG1D),
        IEEEG1SDU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEEEG1D),
        LCFB1=PsseDynamicBinding(PsseDynamicRole.TURBINE_LOAD_CONTROLLER, InternationalStandardModel.LCFB1),
        GASTD=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.GASTD),
        GASTDU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.GASTD),
        IEESGOD=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEESGOD),
        IEESGODU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEESGOD),
        PIDGOV=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.PIDGOV),
        PIDGOVD=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.PIDGOVD),
        PIDGOVDU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.PIDGOVD),
        HYGOV2=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.HYGOV2),
        HYGOV2D=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.HYGOV2D),
        HYGOV2DU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.HYGOV2D),
        HYGOVD=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.HYGOVD),
        HYGOVDU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.HYGOVD),
        TGOV1D=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.TGOV1D),
        TGOV1DU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.TGOV1D),
        TGOV1=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, None),
        IEEEG3=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEEEG3),
        IEEEG3D=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEEEG3D),
        IEEEG3DU=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEEEG3D),
        GAST=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.GAST),
        IEESGO=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEESGO),
        IEEEG2=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IEEEG2,
            (('K','gov_K'),('T1','gov_t1'),('T2','gov_t2'),('T3','gov_t3'),
             ('PMAX','gov_PMaxPu'),('PMIN','gov_PMinPu'),('T4','gov_t4'))),
        IVOGO=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.IVOGO),
        IVOST=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.IVOST),
        STAB1=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.STAB1),
        STAB2A=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.STAB2A),
        STAB3=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.STAB3),
        STAB4=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.STAB4),
        STABNI=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.STABNI),
        IEEEST=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.IEEEST),
        PSS2A=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.PSS2A),
        PSS3B=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.PSS3B),
        PSS2C=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.PSS2C),
        PSS2B=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.PSS2B),
        IEE2ST=PsseDynamicBinding(PsseDynamicRole.STABILIZER, InternationalStandardModel.IEE2ST),
        COMP=PsseDynamicBinding(PsseDynamicRole.COMPENSATOR, InternationalStandardModel.COMP),
        IEEEVC=PsseDynamicBinding(PsseDynamicRole.COMPENSATOR, InternationalStandardModel.IEEEVC_1981,
            (('RC','RcPu'),('XC','XcPu'))),
        REMCMP=PsseDynamicBinding(PsseDynamicRole.COMPENSATOR, InternationalStandardModel.REMCMP),
        MNLEX1=PsseDynamicBinding(PsseDynamicRole.UNDEREXCITATION, InternationalStandardModel.MNLEX1),
        MNLEX2=PsseDynamicBinding(PsseDynamicRole.UNDEREXCITATION, InternationalStandardModel.MNLEX2),
        MNLEX3=PsseDynamicBinding(PsseDynamicRole.UNDEREXCITATION, InternationalStandardModel.MNLEX3),
        HYGOV=PsseDynamicBinding(PsseDynamicRole.GOVERNOR, InternationalStandardModel.HYGOV,
            (('R','Rperm'),('r','Rtemp'),('Tr','Tr'),('Tf','Tf'),('Tg','Tg'),('VELM','Velm'),('GMAX','Gmax'),('GMIN','Gmin'),('Tw','Tw'),('At','At'),('Dturb','Dturb'),('qNL','Qnl'))),
        EXST1=PsseDynamicBinding(PsseDynamicRole.EXCITER, None),
        EXST2A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXST2A),
        ESST2A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESST2A),
        EXST2=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXST2),
        IEEET1=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEET1,dc_kind=DcExciterKind.TYPE1),
        EXPIC1=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXPIC1),
        EXNI=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXNI),
        IEET1B=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEET1B),
        IEET1A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEET1A,dc_kind=DcExciterKind.LIMITED_TYPE1),
        IEEET4=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEET4,
            electromechanical_kind=ElectromechanicalExciterKind.DEADBAND_RESET),
        IEEET5=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEET5,
            electromechanical_kind=ElectromechanicalExciterKind.INTEGRAL_RESET),
        DC4C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.DC4C),
        DC4B=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.DC4B),
        DC3A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.DC3A,
            electromechanical_kind=ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET),
        IEEEX4=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEEX4,
            electromechanical_kind=ElectromechanicalExciterKind.NORMALIZED_RESET),
        IEET5A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEET5A,
            electromechanical_kind=ElectromechanicalExciterKind.LAG_OR_INTEGRAL),
        IEEEX1=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEEX1,dc_kind=DcExciterKind.COMPENSATED_TYPE1),
        ESDC1A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESDC1A,dc_kind=DcExciterKind.DC1A),
        ESDC2A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESDC2A,dc_kind=DcExciterKind.DC2A),
        EXDC2=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXDC2,dc_kind=DcExciterKind.DC2),
        IEEET2=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEET2,dc_kind=DcExciterKind.TYPE2),
        IEEEX2=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEEX2,dc_kind=DcExciterKind.COMPENSATED_TYPE2),
        IEEX2A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEX2A,dc_kind=DcExciterKind.TYPE2A),
        BBSEX1=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.BBSEX1),
        BUDCZT=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.BUDCZT),
        ST6C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ST6C),
        ST5C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ST5C),
        ST5B=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ST5B),
        AC7C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.AC7C),
        AC7B=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.AC7B),
        AC8C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.AC8C),
        AC8B=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.AC8B),
        ST4C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ST4C),
        ESST4B=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ST4B),
        ST7B=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ST7B),
        ST7C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ST7C),
        ST1C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ST1C),
        ESST1A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESST1A),
        IEEET3=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEET3),
        IEEEX3=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.IEEEX3),
        DC1C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.DC1C,dc_kind=DcExciterKind.BOUNDED_FIXED_SUPPLY),
        DC2C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.DC2C,dc_kind=DcExciterKind.BOUNDED_TERMINAL_SUPPLY),
        ESAC8B=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESAC8B),
        ESAC5A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESAC5A,dc_kind=DcExciterKind.BRUSHLESS),
        EXAC4=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXAC4),
        AC4C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.AC4C),
        ESAC4A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESAC4A),
        ESST3A=PsseDynamicBinding(PsseDynamicRole.EXCITER, None),
        SEXS=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.SEXS,
            (('TB','Tb'),('K','K'),('TE','Te'),('EMIN','EMin'),('EMAX','EMax'))),
        SCRX=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.SCRX,
            (('TB','avr_tB'),('K','avr_K'),('TE','avr_tE'),('EMIN','avr_VrMinPu'),
             ('EMAX','avr_VrMaxPu'),('CSWITCH','avr_CSwitch'),('RC_RFD','avr_RcToRfd'))),
        EXBAS=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXBAS,
            ac1_parameters+(('KP','KP'),('KI','KI'),('TF1','TF1'),('TF2','TF2'))),
        EXAC1=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXAC1,
            ac1_parameters),
        EXAC1A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXAC1A,ac1_parameters),
        AC5C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.AC5C,shaped_ac5_parameters),
        AC1C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.AC1C,gated_ac1_parameters+(('VFEMAX','VFEMAX'),('VEMIN','VEMIN'))),
        AC2C=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.AC2C,gated_ac1_parameters+(('KB','KB'),('KH','KH'),('VFEMAX','VFEMAX'),('VEMIN','VEMIN'))),
        ESAC1A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESAC1A,gated_ac1_parameters),
        ESAC2A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESAC2A,
            gated_ac1_parameters+(('KB','KB'),('KH','KH'),('VFEMAX','VFEMAX'))),
        ESAC3A=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.ESAC3A,
            amplifier_ac1_parameters+(('KR','KR'),('KN','KN'),('EFDN','EFDN'),('VEMIN','VEMIN'),('VFEMAX','VFEMAX'))),
        EXAC2=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXAC2,
            gated_ac1_parameters+(('KB','KB'),('KL','KL'),('KH','KH'),('VLR','VLR'))),
        EXAC3=PsseDynamicBinding(PsseDynamicRole.EXCITER, InternationalStandardModel.EXAC3,
            amplifier_ac1_parameters+(('KLV','KLV'),('KR','KR'),('KN','KN'),('EFDN','EFDN'),('VLV','VLV'))),
    )
    return bindings.get(model.upper(), None)


def named_parameter(record: DyrRecord, name: str) -> float:
    """Read a required constant from the already validated source schema.

    :param record: Valid DYR record.
    :param name: Exact schema parameter name (case-sensitive, including HYGOV R/r).
    :return: Parsed constant.
    :raises ValueError: Schema/binding mismatch, handled at the record boundary.
    """
    for parameter in record.parameters:
        if parameter.name == name:
            return parameter.value
        else:
            pass
    raise ValueError('DYR binding parameter absent: ' + name)


def freeze_input(block: Block, port: Var, vf: VarFactory, initial: Expr | Const | None = None) -> None:
    """Hold an unconnected physical input at its power-flow initialized value.

    :param block: Owning block.
    :param port: Input to close algebraically.
    :param vf: Circuit symbol factory.
    :param initial: Optional explicit initialization expression.
    """
    hold: Var = vf.add_var(port.name + '_DYR_hold')
    block.event_dict[hold] = vf.add_const(value=None, name=hold.name)
    block.init_eqs[hold] = initial if initial is not None else block.init_eqs[port]
    if initial is not None:
        block.init_eqs[port] = initial
    else:
        pass
    block.algebraic_vars.append(port)
    block.algebraic_eqs.append(port - hold)


def bind_parameters(block: Block, record: DyrRecord, binding: PsseDynamicBinding,
                    vf: VarFactory, suffix: str) -> None:
    """Apply every declared source-to-template parameter mapping.

    :param block: Fresh native component block.
    :param record: Valid source record.
    :param binding: Reviewed exact parameter names.
    :param vf: Circuit factory.
    :param suffix: Builder's deterministic instance suffix.
    """
    for source_name, target_name in binding.parameters:
        set_rms_model_parameter(block, target_name + '_' + suffix, named_parameter(record, source_name), vf)


def build_gensal_network(vf: VarFactory, record: DyrRecord, name: str,
                         base_ratio: float, ra: float, frequency: float) -> RmsModelTemplate:
    """Connect the existing five-state GENSAL equations to native P/Q bus ports.

    No GENROU substitution is used. Initial states follow the GENSAL steady-state
    stator and damper equations; the original machine saturation stays intact.

    :param vf: Circuit variable factory.
    :param record: Valid GENSAL constants on machine base.
    :param name: Fresh instance label.
    :param base_ratio: Machine MVA divided by system MVA.
    :param ra: Armature resistance on machine base.
    :param frequency: Network frequency in Hz.
    :return: Network-ready RMS wrapper around the existing standard machine.
    """
    template: RmsModelTemplate = build_international_standard_template(InternationalStandardModel.GENSAL, vf, name)
    machine: Block = template.block
    values: dict[str, float] = dict(FNomHz=frequency, H=named_parameter(record,'H')*base_ratio,
        D=named_parameter(record,'D')*base_ratio, RaPu=ra/base_ratio,
        XdPu=named_parameter(record,'Xd')/base_ratio, XqPu=named_parameter(record,'Xq')/base_ratio,
        XpdPu=named_parameter(record,'Xd1')/base_ratio, XppdPu=named_parameter(record,'Xd2')/base_ratio,
        XppqPu=named_parameter(record,'Xd2')/base_ratio, XlPu=named_parameter(record,'Xl')/base_ratio,
        Tpd0=named_parameter(record,'Tdo1'), Tppd0=named_parameter(record,'Tdo2'),
        Tppq0=named_parameter(record,'Tqo2'), S10=named_parameter(record,'S10'), S12=named_parameter(record,'S12'))
    for label, value in values.items():
        set_rms_model_parameter(machine, label + '_' + name, value, vf)
    vm: Var = vf.add_var('Vm', reference=VarPowerFlowReferenceType.Vm)
    va: Var = vf.add_var('Va', reference=VarPowerFlowReferenceType.Va)
    pg: Var = vf.add_var('Pg', reference=VarPowerFlowReferenceType.P)
    qg: Var = vf.add_var('Qg', reference=VarPowerFlowReferenceType.Q)
    id_var, iq_var, efd, pm = machine.in_vars
    ud, uq, pe, omega = machine.out_vars
    delta, _, epq, psikd, psippq = machine.state_vars
    voltage: Expr = vm * sym.exp(sym.Const(1j) * va)
    current: Expr = sym.conj((pg + sym.Const(1j) * qg) / voltage)
    internal: Expr = voltage + (sym.Const(values['RaPu']) + sym.Const(1j * values['XqPu'])) * current
    machine.init_eqs[delta] = sym.imag(sym.log(internal / sym.abs(internal)))
    rotation: Expr = sym.exp(-sym.Const(1j) * (delta - sym.Const(math.pi/2)))
    vd_init: Expr = sym.real(voltage * rotation)
    vq_init: Expr = sym.imag(voltage * rotation)
    machine.init_eqs[id_var] = sym.real(current * rotation)
    machine.init_eqs[iq_var] = sym.imag(current * rotation)
    machine.init_eqs[epq] = vq_init + values['RaPu']*iq_var + values['XpdPu']*id_var
    machine.init_eqs[psikd] = epq - (values['XpdPu']-values['XlPu'])*id_var
    machine.init_eqs[psippq] = (values['XqPu']-values['XppqPu'])*iq_var
    # The source algebraic initialization already defines XadIfd and Te exactly.
    variables: dict[str, Var] = dict((var.name, var) for var in machine.algebraic_vars)
    xad: Var = variables['XadIfdPu_' + name]
    torque: Var = variables['TePu_' + name]
    machine.init_eqs[efd] = xad
    machine.init_eqs[pm] = torque
    bridge: Block = Block(name=name+'_network')
    bridge.algebraic_vars = [id_var, iq_var, pg, qg]
    bridge.algebraic_eqs = [ud-vm*sym.sin(delta-va), uq-vm*sym.cos(delta-va), pg-ud*id_var-uq*iq_var, qg-uq*id_var+ud*iq_var]
    bridge.init_eqs[id_var] = machine.init_eqs[id_var]
    bridge.init_eqs[iq_var] = machine.init_eqs[iq_var]
    # These boundary inputs are now owned by the network bridge.
    machine.in_vars = [efd, pm]
    machine.init_eqs.pop(id_var, None)
    machine.init_eqs.pop(iq_var, None)
    root: Block = Block(name=name)
    root.children = [machine, bridge]
    root.in_vars = [vm, va]
    root.out_vars = [pg, qg, omega, xad, torque, ud, uq, id_var, iq_var]
    root.external_mapping = dict([(VarPowerFlowReferenceType.Vm,vm),(VarPowerFlowReferenceType.Va,va),(VarPowerFlowReferenceType.P,pg),(VarPowerFlowReferenceType.Q,qg)])
    # Ports use the same order as the network-ready GENROU wrapper's child.
    root.in_vars = [vm, va, pm, efd]
    root.init_eqs[pm] = torque
    root.init_eqs[efd] = xad
    template.block = Block(name=name+'_wrapper')
    template.block.children = [root]
    template.block.in_vars = [vm,va]
    template.block.out_vars = [pg,qg]
    template.block.external_mapping = dict(root.external_mapping)
    template.tpe = DeviceType.GeneratorDevice
    return template


def build_controller(record: DyrRecord, binding: PsseDynamicBinding, vf: VarFactory,
                     name: str, base_ratio: float) -> RmsModelTemplate:
    """Materialize a fresh existing controller with explicit parameter conversion.

    :param record: Valid controller constants.
    :param binding: Reviewed role and parameter map.
    :param vf: Circuit symbol factory.
    :param name: Unique component instance label.
    :param base_ratio: Machine MVA divided by system MVA.
    :return: Parameterized component, still awaiting physical signal connections.
    """
    template: RmsModelTemplate
    if record.model.upper() == 'TGOV1':
        template = get_tgov1_rms_template(vf, name)
        parameters: Tgov1RmsParameters = Tgov1RmsParameters(1.0, named_parameter(record,'R')/base_ratio,
            named_parameter(record,'VMAX')*base_ratio,named_parameter(record,'VMIN')*base_ratio,
            named_parameter(record,'T1'),named_parameter(record,'T2'),named_parameter(record,'T3'),named_parameter(record,'Dt')*base_ratio)
        configure_tgov1_block(template.block.children[0], parameters, vf)
    elif dynamic_record_name(record) in ('GGOV1','GGOV1D','GGOV1DU'):
        tracked: TrackedGovernorParameters = TrackedGovernorParameters(
            feedback=GovernorDroopFeedback(record.icons[0]), fuel_characteristic=FuelFlowCharacteristic(record.icons[1]),
            droop=named_parameter(record,'R'), power_time=named_parameter(record,'TPELEC'),
            error_limits=(named_parameter(record,'MINERR'), named_parameter(record,'MAXERR')),
            governor_gains=(named_parameter(record,'KPGOV'), named_parameter(record,'KIGOV'), named_parameter(record,'KDGOV')),
            derivative_time=named_parameter(record,'TDGOV'), valve_limits=(named_parameter(record,'VMIN'), named_parameter(record,'VMAX')),
            actuator_time=named_parameter(record,'TACT'), valve_rates=(named_parameter(record,'RCLOSE'), named_parameter(record,'ROPEN')),
            turbine_gain=named_parameter(record,'KTURB'), no_load_fuel=named_parameter(record,'WFNL'),
            turbine_times=(named_parameter(record,'TC'), named_parameter(record,'TB')),
            load_time=named_parameter(record,'TFLOAD'), load_gains=(named_parameter(record,'KPLOAD'), named_parameter(record,'KILOAD')),
            load_reference=named_parameter(record,'LDREF'), damping=named_parameter(record,'DM'),
            reset_gain=named_parameter(record,'KIMW'), deadband=named_parameter(record,'DB'),
            temperature_times=(named_parameter(record,'TSA'), named_parameter(record,'TSB')),
            speed_deadband=(named_parameter(record,'DBL'), named_parameter(record,'DBH')) if dynamic_record_name(record) in ('GGOV1D','GGOV1DU') else (0.,0.),
            load_rates=(named_parameter(record,'RDOWN'),named_parameter(record,'RUP')))
        template = build_ggov1_template(vf,name,tracked)
    elif dynamic_record_name(record) in ('DEGOV','DEGOV1','DEGOV1D','DEGOV1DU'):
        engine: DieselGovernorParameters = DieselGovernorParameters(
            t1=named_parameter(record,'T1'),t2=named_parameter(record,'T2'),t3=named_parameter(record,'T3'),
            gain=named_parameter(record,'K'),t4=named_parameter(record,'T4'),t5=named_parameter(record,'T5'),t6=named_parameter(record,'T6'),
            combustion_delay=named_parameter(record,'TD'),maximum=named_parameter(record,'TMAX'),minimum=named_parameter(record,'TMIN'),
            droop=named_parameter(record,'DROOP') if dynamic_record_name(record) != 'DEGOV' else 0.,
            power_time=named_parameter(record,'TE') if dynamic_record_name(record) != 'DEGOV' else 0.,
            feedback=EngineDroopFeedback(record.icons[0]) if dynamic_record_name(record) != 'DEGOV' else EngineDroopFeedback.THROTTLE,
            deadband_high=named_parameter(record,'DBH') if dynamic_record_name(record) in ('DEGOV1D','DEGOV1DU') else 0.,
            deadband_low=named_parameter(record,'DBL') if dynamic_record_name(record) in ('DEGOV1D','DEGOV1DU') else 0.)
        template = build_degov1_template(vf,name,engine)
    elif record.model.upper() == 'LCFB1':
        load_settings: TurbineLoadControllerParameters = TurbineLoadControllerParameters(
            frequency_bias=named_parameter(record,'FB') if record.icons[0] == 1 else 0.0,
            power_time=named_parameter(record,'TPELEC'),deadband=named_parameter(record,'DB'),
            error_limit=named_parameter(record,'EMAX'),proportional_gain=named_parameter(record,'KP'),
            integral_gain=named_parameter(record,'KI'),correction_limit=named_parameter(record,'LRMAX'))
        template = build_lcfb1_template(vf,name,load_settings)
    elif dynamic_record_name(record) in ('IEEEG1','IEEEG1D','IEEEG1SDU'):
        steam: MultiStageSteamGovernorParameters = MultiStageSteamGovernorParameters(
            gain=named_parameter(record,'K'),speed_lag=named_parameter(record,'T1'),speed_lead=named_parameter(record,'T2'),
            servo_time=named_parameter(record,'T3'),opening_rate=named_parameter(record,'UO'),closing_rate=named_parameter(record,'UC'),
            maximum=named_parameter(record,'PMAX'),minimum=named_parameter(record,'PMIN'),
            turbine_times=(named_parameter(record,'T4'),named_parameter(record,'T5'),named_parameter(record,'T6'),named_parameter(record,'T7')),
            fractions=tuple(named_parameter(record,'K'+str(index)) for index in range(1,9)),
            deadband_high=named_parameter(record,'DBH') if dynamic_record_name(record) in ('IEEEG1D','IEEEG1SDU') else 0.0,
            deadband_low=named_parameter(record,'DBL') if dynamic_record_name(record) in ('IEEEG1D','IEEEG1SDU') else 0.0)
        template = build_ieeeg1_template(vf,name,steam)
    elif dynamic_record_name(record) in ('IEEEG3','IEEEG3D','IEEEG3DU'):
        hydraulics: HydraulicGovernorParameters = HydraulicGovernorParameters(
            gate_time=named_parameter(record,'TG'), pilot_time=named_parameter(record,'TP'),
            opening_rate=named_parameter(record,'UO'), closing_rate=named_parameter(record,'UC'),
            gate_max=named_parameter(record,'PMAX'), gate_min=named_parameter(record,'PMIN'),
            permanent_droop=named_parameter(record,'SIGMA'), transient_droop=named_parameter(record,'DELTA'),
            reset_time=named_parameter(record,'TR'), water_time=named_parameter(record,'TW'),
            a11=named_parameter(record,'A11'), a13=named_parameter(record,'A13'),
            a21=named_parameter(record,'A21'), a23=named_parameter(record,'A23'),
            deadband_high=named_parameter(record,'DBH') if dynamic_record_name(record) in ('IEEEG3D','IEEEG3DU') else 0.0,
            deadband_low=named_parameter(record,'DBL') if dynamic_record_name(record) in ('IEEEG3D','IEEEG3DU') else 0.0)
        template = build_ieeeg3_template(vf,name,hydraulics)
    elif record.model.upper() in ('EXST1','ESST3A'):
        template = get_exst1_rms_template(vf,name) if record.model.upper() == 'EXST1' else get_esst3a_rms_template(vf,name)
        for parameter in record.parameters:
            value: float = parameter.value
            # Both the data sheet and native THETAP parameter use degrees.
            set_rms_model_parameter(template.block.children[0], parameter.name, value, vf)
        block: Block = template.block.children[0]
        if record.model.upper() == 'EXST1':
            configure_exst1_algebraic_lags(block,record)
        else:
            parameters_by_name: dict[str, Var] = dict((var.name,var) for var in block.event_dict)
            # Preserve PSS/E regulator and exciter limits absent from this
            # catalogue's zero-TA realization, using its existing anti-windup helper.
            block.algebraic_eqs[5] = sym.hard_sat(parameters_by_name['KA']*block.algebraic_vars[4],
                parameters_by_name['VRMIN'],parameters_by_name['VRMAX'])-block.algebraic_vars[5]
            block.state_eqs[2] = _anti_windup_state_derivative(block.state_vars[2],block.state_eqs[2],
                parameters_by_name['VMMIN'],parameters_by_name['VMMAX'])
            if named_parameter(record,'TR') == 0:
                state: Var = block.state_vars.pop(0)
                block.state_eqs.pop(0)
                if block.diff_vars:
                    block.diff_vars.pop(0)
                else:
                    pass
                block.algebraic_vars.append(state)
                block.algebraic_eqs.append(block.in_vars[1]-state)
            else:
                pass
    elif dynamic_record_name(record) in ('TGOV1D','TGOV1DU'):
        template = build_tgov1d_template(vf,name,Tgov1RmsParameters(1.,named_parameter(record,'R'),
            named_parameter(record,'VMAX'),named_parameter(record,'VMIN'),named_parameter(record,'T1'),
            named_parameter(record,'T2'),named_parameter(record,'T3'),named_parameter(record,'Dt')),
            named_parameter(record,'DBL'),named_parameter(record,'DBH'))
    elif dynamic_record_name(record) in ('HYGOV','HYGOVD','HYGOVDU'):
        hydro_parameters: NonlinearHydroGovernorParameters = NonlinearHydroGovernorParameters(
            permanent_droop=named_parameter(record,'R'),temporary_droop=named_parameter(record,'r'),
            reset_time=named_parameter(record,'Tr'),filter_time=named_parameter(record,'Tf'),gate_time=named_parameter(record,'Tg'),
            velocity=named_parameter(record,'VELM'),maximum=named_parameter(record,'GMAX'),minimum=named_parameter(record,'GMIN'),
            water_time=named_parameter(record,'Tw'),gain=named_parameter(record,'At'),damping=named_parameter(record,'Dturb'),
            no_load_flow=named_parameter(record,'qNL'),
            deadband_low=named_parameter(record,'DBL') if dynamic_record_name(record) != 'HYGOV' else 0.,
            deadband_high=named_parameter(record,'DBH') if dynamic_record_name(record) != 'HYGOV' else 0.)
        template = build_hygov_template(vf,name,hydro_parameters)
    elif dynamic_record_name(record) in ('GAST','GASTD','GASTDU'):
        template = build_gast_template(vf, name, GasGovernorParameters(
            r=named_parameter(record,'R'), t1=named_parameter(record,'T1'),
            t2=named_parameter(record,'T2'), t3=named_parameter(record,'T3'),
            ambient_limit=named_parameter(record,'AT'), temperature_gain=named_parameter(record,'KT'),
            valve_max=named_parameter(record,'VMAX'), valve_min=named_parameter(record,'VMIN'),
            damping=named_parameter(record,'Dturb'),
            deadband_low=named_parameter(record,'DBL') if dynamic_record_name(record) != 'GAST' else 0.,
            deadband_high=named_parameter(record,'DBH') if dynamic_record_name(record) != 'GAST' else 0.))
    elif dynamic_record_name(record) in ('IEESGO','IEESGOD','IEESGODU'):
        template = build_ieesgo_template(vf, name, SteamGovernorParameters(
            t1=named_parameter(record,'T1'), t2=named_parameter(record,'T2'),
            t3=named_parameter(record,'T3'), t4=named_parameter(record,'T4'),
            t5=named_parameter(record,'T5'), t6=named_parameter(record,'T6'),
            gain=named_parameter(record,'K1'), reheat_fraction=named_parameter(record,'K2'),
            low_pressure_fraction=named_parameter(record,'K3'), power_max=named_parameter(record,'PMAX'),
            power_min=named_parameter(record,'PMIN'),
            deadband_low=named_parameter(record,'DBL') if dynamic_record_name(record) != 'IEESGO' else 0.,
            deadband_high=named_parameter(record,'DBH') if dynamic_record_name(record) != 'IEESGO' else 0.))
    elif record.model.upper() in ('PSS2A','PSS2B','PSS2C'):
        limited: bool = record.model.upper() != 'PSS2A'
        ramp: RampStabilizerParameters = RampStabilizerParameters(
            washout_times=(named_parameter(record,'TW1'),named_parameter(record,'TW2'),
                           named_parameter(record,'TW3'),named_parameter(record,'TW4')),
            transducer_times=(named_parameter(record,'T6'),named_parameter(record,'T7')),
            ks1=named_parameter(record,'KS1'),ks2=named_parameter(record,'KS2'),ks3=named_parameter(record,'KS3'),
            t8=named_parameter(record,'T8'),t9=named_parameter(record,'T9'),
            ramp_m=record.icons[4],ramp_n=record.icons[5],
            phase_times=((named_parameter(record,'T1'),named_parameter(record,'T2')),
                         (named_parameter(record,'T3'),named_parameter(record,'T4')),
                         (named_parameter(record,'T10'),named_parameter(record,'T11')) if limited else (0.0,0.0)),
            upper=named_parameter(record,'VSTMAX'),lower=named_parameter(record,'VSTMIN'),
            input_limits=((named_parameter(record,'VS1MIN'),named_parameter(record,'VS1MAX')),
                          (named_parameter(record,'VS2MIN'),named_parameter(record,'VS2MAX'))) if limited else ((-10.0,10.0),(-10.0,10.0)),
            fourth_phase=(named_parameter(record,'T12'),named_parameter(record,'T13')) if record.model.upper() == 'PSS2C' else (0.,0.))
        template = build_pss2c_template(vf,name,ramp,StabilizerInterface.SELECTED_SIGNALS) if record.model.upper() == 'PSS2C' else (build_pss2b_template(vf,name,ramp,StabilizerInterface.SELECTED_SIGNALS) if limited else
                    build_pss2a_template(vf,name,ramp,StabilizerInterface.SELECTED_SIGNALS))
    elif record.model.upper() == 'PSS3B':
        template = build_pss3b_template(vf,name,QuadraticDualStabilizerParameters(
            gains=(named_parameter(record,'KS1'),named_parameter(record,'KS2')),
            transducer_times=(named_parameter(record,'T1'),named_parameter(record,'T2')),
            washout_times=(named_parameter(record,'TW1'),named_parameter(record,'TW2'),named_parameter(record,'TW3')),
            coefficients=(named_parameter(record,'A1'),named_parameter(record,'A2'),named_parameter(record,'A3'),named_parameter(record,'A4'),
                named_parameter(record,'A5'),named_parameter(record,'A6'),named_parameter(record,'A7'),named_parameter(record,'A8')),
            upper=named_parameter(record,'VSTMAX'),lower=named_parameter(record,'VSTMIN')))
    elif record.model.upper() == 'IEE2ST':
        template = build_iee2st_template(vf, name, Iee2stParameters(
            gains=(named_parameter(record,'K1'), named_parameter(record,'K2')),
            transducer_times=(named_parameter(record,'T1'), named_parameter(record,'T2')),
            reset_numerator=named_parameter(record,'T3'), reset_denominator=named_parameter(record,'T4'),
            phase_times=((named_parameter(record,'T5'), named_parameter(record,'T6')),
                (named_parameter(record,'T7'), named_parameter(record,'T8')),
                (named_parameter(record,'T9'), named_parameter(record,'T10'))),
            upper=named_parameter(record,'LSMAX'), lower=named_parameter(record,'LSMIN'),
            voltage_upper=named_parameter(record,'VCU'), voltage_lower=named_parameter(record,'VCL')))
    elif record.model.upper() == 'IEEEST':
        template = build_ieeest_template(vf, name, IeeestParameters(
            filter_coefficients=(named_parameter(record,'A1'), named_parameter(record,'A2'),
                named_parameter(record,'A3'), named_parameter(record,'A4'),
                named_parameter(record,'A5'), named_parameter(record,'A6')),
            lead1=named_parameter(record,'T1'), lag1=named_parameter(record,'T2'),
            lead2=named_parameter(record,'T3'), lag2=named_parameter(record,'T4'),
            reset_numerator=named_parameter(record,'T5'), reset_denominator=named_parameter(record,'T6'),
            gain=named_parameter(record,'KS'), upper=named_parameter(record,'LSMAX'),
            lower=named_parameter(record,'LSMIN'), voltage_upper=named_parameter(record,'VCU'),
            voltage_lower=named_parameter(record,'VCL')))
    elif record.model.upper() == 'STAB1':
        template = build_stab1_template(vf, name, gain_over_time=named_parameter(record,'KoverT'),
            washout_time=named_parameter(record,'T'), lead1_ratio=named_parameter(record,'T1overT3'),
            lag1_time=named_parameter(record,'T3'), lead2_ratio=named_parameter(record,'T2overT4'),
            lag2_time=named_parameter(record,'T4'), output_limit=named_parameter(record,'HLIM'))
    elif record.model.upper() == 'STAB2A':
        template = build_stab2a_template(vf, name, k2=named_parameter(record,'K2'), t2=named_parameter(record,'T2'),
            k3=named_parameter(record,'K3'), t3=named_parameter(record,'T3'), k4=named_parameter(record,'K4'),
            k5=named_parameter(record,'K5'), t5=named_parameter(record,'T5'), output_limit=named_parameter(record,'HLIM'))
    elif record.model.upper() == 'STAB3':
        template = build_stab3_template(vf, name, transducer_time=named_parameter(record,'Tt'),
            first_lag_time=named_parameter(record,'TX1'), reset_time=named_parameter(record,'TX2'),
            gain=named_parameter(record,'KX'), output_limit=named_parameter(record,'VLIM'))
    elif record.model.upper() == 'STAB4':
        template = build_stab4_template(vf, name, gain=named_parameter(record,'KX'),
            transducer_time=named_parameter(record,'TT'), first_lag_time=named_parameter(record,'TX1'),
            reset_time=named_parameter(record,'TX2'), lead1_time=named_parameter(record,'Ta'),
            lead2_time=named_parameter(record,'Tb'), second_lag_time=named_parameter(record,'Tc'),
            output_lag1_time=named_parameter(record,'Td'), output_lag2_time=named_parameter(record,'Te'),
            lower_limit=named_parameter(record,'L1'), upper_limit=named_parameter(record,'L2'))
    elif record.model.upper() == 'STABNI':
        template = build_stabni_template(vf,name,gain=named_parameter(record,'K'),lead_time=named_parameter(record,'T1'),
            transducer_time=named_parameter(record,'T2'),reset_time=named_parameter(record,'T0'),
            output_limit=named_parameter(record,'LIMIT'))
    elif record.model.upper() == 'MNLEX1':
        template = build_mnlex1_template(vf,name,feedback_gain=named_parameter(record,'KF2'),
            feedback_time=named_parameter(record,'TF2'),limiter_gain=named_parameter(record,'KM'),
            limiter_time=named_parameter(record,'TM'),maximum=named_parameter(record,'MELMAX'),
            slope=named_parameter(record,'K'))
    elif record.model.upper() == 'MNLEX2':
        template = build_mnlex2_template(vf,name,feedback_gain=named_parameter(record,'KF2'),
            feedback_time=named_parameter(record,'TF2'),limiter_gain=named_parameter(record,'KM'),
            limiter_time=named_parameter(record,'TM'),maximum=named_parameter(record,'MELMAX'),
            reactive_center=named_parameter(record,'Q0'),radius=named_parameter(record,'Radius'))
    elif record.model.upper() == 'MNLEX3':
        template = build_mnlex3_template(vf,name,feedback_gain=named_parameter(record,'KF2'),
            feedback_time=named_parameter(record,'TF2'),limiter_gain=named_parameter(record,'KM'),
            limiter_time=named_parameter(record,'TM'),maximum=named_parameter(record,'MELMAX'),
            reactive_intercept=named_parameter(record,'Q0'),slope=named_parameter(record,'B'))
    elif record.model.upper() == 'DC4C':
        if named_parameter(record,'KE') == 0:
            raise ValueError('Compound commutator automatic field-resistance calibration is unreviewed')
        else:
            pass
        template = build_dc4c_template(vf,name,DcExciterParameters(
            tr=named_parameter(record,'TR'),ka=named_parameter(record,'KA'),ta=named_parameter(record,'TA'),
            vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),
            ke=named_parameter(record,'KE'),te=named_parameter(record,'TE'),kf=named_parameter(record,'KF'),tf=named_parameter(record,'TF'),
            field_min=named_parameter(record,'VEMIN'),e1=named_parameter(record,'E1'),se1=named_parameter(record,'SE1'),
            e2=named_parameter(record,'E2'),se2=named_parameter(record,'SE2')),
            named_parameter(record,'KPR'),named_parameter(record,'KJR'),named_parameter(record,'KDR'),named_parameter(record,'TDR'),
            RotatingLimiterLocation(record.icons[1]),RotatingLimiterLocation(record.icons[0]),
            CompoundSupplyParameters(kp=named_parameter(record,'KP'),ki=named_parameter(record,'KI'),
                xl=named_parameter(record,'XL'),theta=named_parameter(record,'THETAP'),kc=named_parameter(record,'KC1'),
                vbmax=named_parameter(record,'VBMAX'),source=CompoundExcitationSource(record.icons[3])))
    elif record.model.upper() == 'DC4B':
        template = build_dc4b_template(vf,name,DcExciterParameters(
            tr=named_parameter(record,'TR'),ka=named_parameter(record,'KA'),ta=named_parameter(record,'TA'),
            vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),
            ke=named_parameter(record,'KE'),te=named_parameter(record,'TE'),kf=named_parameter(record,'KF'),tf=named_parameter(record,'TF'),
            field_min=named_parameter(record,'VEMIN'),e1=named_parameter(record,'E1'),se1=named_parameter(record,'SE1'),
            e2=named_parameter(record,'E2'),se2=named_parameter(record,'SE2')),
            named_parameter(record,'KP'),named_parameter(record,'KI'),named_parameter(record,'KD'),named_parameter(record,'TD'),
            RotatingLimiterLocation(record.icons[1]),RotatingLimiterLocation(record.icons[0]))
    elif record.model.upper() in ('EXAC4','ESAC4A','AC4C'):
        template = build_alternator_rectifier(vf,name,
            AlternatorRectifierKind.OUTPUT_CLIP if record.model.upper() == 'EXAC4' else (AlternatorRectifierKind.SELECTABLE_GATES if record.model.upper() == 'AC4C' else AlternatorRectifierKind.NONWINDUP_GATE),
            AlternatorRectifierParameters(tr=named_parameter(record,'TR'),
                vi_max=named_parameter(record,'VIMAX'), vi_min=named_parameter(record,'VIMIN'),
                tc=named_parameter(record,'TC'), tb=named_parameter(record,'TB'),
                ka=named_parameter(record,'KA'), ta=named_parameter(record,'TA'),
                vr_max=named_parameter(record,'VRMAX'), vr_min=named_parameter(record,'VRMIN'),
                kc=named_parameter(record,'KC')),
            RectifierLimiterLocation(record.icons[1]) if record.model.upper() == 'AC4C' else RectifierLimiterLocation.SUMMATION,
            RectifierLimiterLocation(record.icons[0]) if record.model.upper() == 'AC4C' else RectifierLimiterLocation.SUMMATION)
    elif binding.electromechanical_kind is not None:
        mechanism: ElectromechanicalExciterKind = binding.electromechanical_kind
        source_upper: float = named_parameter(record,'VRMAX')
        source_ke: float = named_parameter(record,'KE')
        mechanics: ElectromechanicalExciterParameters = ElectromechanicalExciterParameters(
            tr=named_parameter(record,'TR') if mechanism in (ElectromechanicalExciterKind.NORMALIZED_RESET,ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET) else 0.0,
            reset_time=named_parameter(record,'TRH'),
            reset_deadband=named_parameter(record,'KR') if mechanism == ElectromechanicalExciterKind.DEADBAND_RESET else 0.0,
            fast_band=named_parameter(record,'KV'), regulator_max=None if source_upper == 0 and mechanism != ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET else source_upper,
            regulator_min=named_parameter(record,'VRMIN'), field_gain=None if source_ke == 0 and mechanism != ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET else source_ke,
            field_time=named_parameter(record,'TE'), e1=named_parameter(record,'E1'), se1=named_parameter(record,'SE1'),
            e2=named_parameter(record,'E2'), se2=named_parameter(record,'SE2'),
            gain=named_parameter(record,'KA') if mechanism == ElectromechanicalExciterKind.LAG_OR_INTEGRAL else 1.0,
            field_min=named_parameter(record,'EFDMIN') if mechanism == ElectromechanicalExciterKind.LAG_OR_INTEGRAL else (named_parameter(record,'VEMIN') if mechanism == ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET else 0.0),
            field_max=named_parameter(record,'EFDMAX') if mechanism == ElectromechanicalExciterKind.LAG_OR_INTEGRAL else 5.0)
        template = build_electromechanical_exciter(vf,name,mechanism,mechanics)
    elif dynamic_record_name(record) in ('PIDGOV','PIDGOVD','PIDGOVDU'):
        pid_deadband: bool = dynamic_record_name(record) != 'PIDGOV'
        if len(record.icons) != 1:
            raise ValueError('Hydraulic PID feedback selection is missing')
        else:
            pass
        template = build_pidgov_template(vf,name,PidHydroGovernorParameters(
            droop=named_parameter(record,'RPERM'),detector_time=named_parameter(record,'TREG'),
            kp=named_parameter(record,'KP'),ki=named_parameter(record,'KI'),kd=named_parameter(record,'KD'),
            controller_time=named_parameter(record,'TA'),servo_time=named_parameter(record,'TB'),damping=named_parameter(record,'DTURB'),
            g0=named_parameter(record,'G0'),g1=named_parameter(record,'G1'),p1=named_parameter(record,'P1'),
            g2=named_parameter(record,'G2'),p2=named_parameter(record,'P2'),p3=named_parameter(record,'P3'),
            gate_max=named_parameter(record,'GMAX'),gate_min=named_parameter(record,'GMIN'),
            water_factor=named_parameter(record,'ATW'),water_time=named_parameter(record,'TW'),
            opening_rate=named_parameter(record,'VELMAX'),closing_rate=named_parameter(record,'VELMIN'),feedback=HydroDroopFeedback(record.icons[0]),
            deadband_low=named_parameter(record,'DBL') if pid_deadband else 0.,
            deadband_high=named_parameter(record,'DBH') if pid_deadband else 0.))
    elif dynamic_record_name(record) in ('HYGOV2','HYGOV2D','HYGOV2DU'):
        cascaded_deadband: bool = dynamic_record_name(record) != 'HYGOV2'
        template = build_hygov2_template(vf,name,CascadedHydroGovernorParameters(
            kp=named_parameter(record,'KP'),ki=named_parameter(record,'KI'),ka=named_parameter(record,'KA'),
            t1=named_parameter(record,'T1'),t2=named_parameter(record,'T2'),t3=named_parameter(record,'T3'),
            t4=named_parameter(record,'T4'),t5=named_parameter(record,'T5'),t6=named_parameter(record,'T6'),
            reset_time=named_parameter(record,'TR'),temporary_droop=named_parameter(record,'r'),
            permanent_droop=named_parameter(record,'R'),gate_velocity=named_parameter(record,'VGMAX'),
            gate_max=named_parameter(record,'GMAX'),gate_min=named_parameter(record,'GMIN'),power_gain=named_parameter(record,'PMAX'),
            deadband_low=named_parameter(record,'DBL') if cascaded_deadband else 0.,
            deadband_high=named_parameter(record,'DBH') if cascaded_deadband else 0.))
    elif record.model.upper() == 'BUDCZT':
        template = build_budczt_template(vf,name,LimitedPiExciterParameters(
            kp=named_parameter(record,'KP'),ka=named_parameter(record,'KA'),ke=named_parameter(record,'KE'),
            tr=named_parameter(record,'TR'),ti=named_parameter(record,'TI'),
            ta=named_parameter(record,'TA'),te=named_parameter(record,'TE'),
            regulator_max=named_parameter(record,'URMAX'),regulator_min=named_parameter(record,'URMIN'),
            field_max=named_parameter(record,'EFDMAX'),field_min=named_parameter(record,'EFDMIN')))
    elif record.model.upper() == 'EXPIC1':
        template = build_expic1_template(vf,name,PiCompoundFieldParameters(
            tr=named_parameter(record,'TR'),ka=named_parameter(record,'KA'),ta1=named_parameter(record,'TA1'),
            vr1=named_parameter(record,'VR1'),vr2=named_parameter(record,'VR2'),ta2=named_parameter(record,'TA2'),ta3=named_parameter(record,'TA3'),ta4=named_parameter(record,'TA4'),
            vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),kf=named_parameter(record,'KF'),tf1=named_parameter(record,'TF1'),tf2=named_parameter(record,'TF2'),
            efdmax=named_parameter(record,'EFDMAX'),efdmin=named_parameter(record,'EFDMIN'),ke=named_parameter(record,'KE'),te=named_parameter(record,'TE'),
            e1=named_parameter(record,'E1'),se1=named_parameter(record,'SE1'),e2=named_parameter(record,'E2'),se2=named_parameter(record,'SE2'),
            kp=named_parameter(record,'KP'),ki=named_parameter(record,'KI'),kc=named_parameter(record,'KC')))
    elif record.model.upper() == 'EXNI':
        if named_parameter(record,'R') != 0:
            raise ValueError('Controlled-bridge reverse-current logic requires separate review; only bidirectional R=0 is supported')
        else:
            pass
        template = build_exni_template(vf,name,tr=named_parameter(record,'TR'),ka=named_parameter(record,'KA'),ta=named_parameter(record,'TA'),
            vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),kf=named_parameter(record,'KF'),
            tf1=named_parameter(record,'TF1'),tf2=named_parameter(record,'TF2'),supply=BridgeExcitationSupply(named_parameter(record,'SWITCH')))
    elif record.model.upper() == 'IEET1B':
        if named_parameter(record,'KE') == 0 or named_parameter(record,'VRMAX') == 0:
            raise ValueError('Biased rotating exciter automatic coefficient/capability calibration has not been reviewed')
        else:
            pass
        template = build_ieet1b_template(vf,name,DcExciterParameters(
            tr=named_parameter(record,'TR'),ka=named_parameter(record,'KA'),ta=named_parameter(record,'TA1'),
            vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),ke=named_parameter(record,'KE'),te=named_parameter(record,'TE'),
            kf=named_parameter(record,'KF1'),tf=named_parameter(record,'TF1'),e1=named_parameter(record,'E1'),se1=named_parameter(record,'SE1'),
            e2=named_parameter(record,'E2'),se2=named_parameter(record,'SE2')),
            second_time=named_parameter(record,'TA2'),error_max=named_parameter(record,'VSMAX'),error_min=named_parameter(record,'VSMIN'),
            compensation=named_parameter(record,'Xe'),feedback_signal=RotatingRateFeedbackSignal(named_parameter(record,'Switch')))
    elif record.model.upper() == 'ST6C':
        template = build_st6c_template(vf,name,CurrentLimitedFieldParameters(
            tr=named_parameter(record,'TR'),kpa=named_parameter(record,'KPA'),kia=named_parameter(record,'KIA'),
            kda=named_parameter(record,'KDA'),tda=named_parameter(record,'TDA'),vamax=named_parameter(record,'VAMAX'),
            vamin=named_parameter(record,'VAMIN'),kff=named_parameter(record,'KFF'),km=named_parameter(record,'KM'),
            kci=named_parameter(record,'KCI'),klr=named_parameter(record,'KLR'),ilr=named_parameter(record,'ILR'),
            vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),kg=named_parameter(record,'KG'),
            tg=named_parameter(record,'TG'),vmmax=named_parameter(record,'VMMAX'),vmmin=named_parameter(record,'VMMIN'),
            ta=named_parameter(record,'TA'),supply=CompoundSupplyParameters(kp=named_parameter(record,'KP'),
                ki=named_parameter(record,'KI'),xl=named_parameter(record,'XL'),theta=named_parameter(record,'THETAP'),
                kc=named_parameter(record,'KC'),vbmax=named_parameter(record,'VBMAX'),source=CompoundExcitationSource(record.icons[3])),
            minimum_location=FieldRegulatorLimiterLocation(record.icons[1]),maximum_location=FieldRegulatorLimiterLocation(record.icons[0])))
    elif record.model.upper() in ('ST5B','ST5C'):
        parallel_parameters: ParallelChannelExciterParameters = ParallelChannelExciterParameters(
            tr=named_parameter(record,'TR'),
            tc1=named_parameter(record,'TC1'),
            tb1=named_parameter(record,'TB1'),
            tc2=named_parameter(record,'TC2'),
            tb2=named_parameter(record,'TB2'),
            kr=named_parameter(record,'KR'),
            vrmax=named_parameter(record,'VRMAX'),
            vrmin=named_parameter(record,'VRMIN'),
            t1=named_parameter(record,'T1'),
            kc=named_parameter(record,'KC'),
            tuc1=named_parameter(record,'TUC1'),
            tub1=named_parameter(record,'TUB1'),
            tuc2=named_parameter(record,'TUC2'),
            tub2=named_parameter(record,'TUB2'),
            toc1=named_parameter(record,'TOC1'),
            tob1=named_parameter(record,'TOB1'),
            toc2=named_parameter(record,'TOC2'),
            tob2=named_parameter(record,'TOB2'),
            minimum_location=ExcitationLimiterLocation(record.icons[1]) if record.model.upper() == 'ST5C' else ExcitationLimiterLocation.REFERENCE_GATE,
            maximum_location=ExcitationLimiterLocation(record.icons[0]) if record.model.upper() == 'ST5C' else ExcitationLimiterLocation.REFERENCE_GATE)
        template = build_st5c_template(vf,name,parallel_parameters) if record.model.upper() == 'ST5C' else build_st5b_template(vf,name,parallel_parameters)
    elif record.model.upper() in ('AC7B','AC7C'):
        cascaded_parameters: CascadedBrushlessParameters = CascadedBrushlessParameters(
            tr=named_parameter(record,'TR'),
            kpr=named_parameter(record,'KPR'),
            kir=named_parameter(record,'KIR'),
            kdr=named_parameter(record,'KDR'),
            tdr=named_parameter(record,'TDR'),
            vrmax=named_parameter(record,'VRMAX'),
            vrmin=named_parameter(record,'VRMIN'),
            kpa=named_parameter(record,'KPA'),
            kia=named_parameter(record,'KIA'),
            vamax=named_parameter(record,'VAMAX'),
            vamin=named_parameter(record,'VAMIN'),
            kp=named_parameter(record,'KP'),
            kl=named_parameter(record,'KL'),
            kf1=named_parameter(record,'KF1'),
            kf2=named_parameter(record,'KF2'),
            kf3=named_parameter(record,'KF3'),
            tf3=named_parameter(record,'TF3'),
            kc=named_parameter(record,'KC'),
            kd=named_parameter(record,'KD'),
            ke=named_parameter(record,'KE'),
            te=named_parameter(record,'TE'),
            vfemax=named_parameter(record,'VFEMAX'),
            vemin=named_parameter(record,'VEMIN'),
            e1=named_parameter(record,'E1'),
            se1=named_parameter(record,'SE1'),
            e2=named_parameter(record,'E2'),
            se2=named_parameter(record,'SE2'))
        if record.model.upper() == 'AC7C':
            if record.icons[5] == 1 and named_parameter(record,'KP') == 0:
                raise ValueError('Modern cascaded KP=0 potential-supply bypass requires separate source review')
            else:
                pass
            template = build_ac7c_template(vf,name,cascaded_parameters,CascadedBrushlessCircuit(
                ki=named_parameter(record,'KI'),xl=named_parameter(record,'XL'),theta=named_parameter(record,'THETAP'),
                kc1=named_parameter(record,'KC1'),vbmax=named_parameter(record,'VBMAX'),kr=named_parameter(record,'KR'),
                source=CompoundExcitationSource(record.icons[4]),power_supply=CascadedPowerSupply(record.icons[5]),
                minimum_location=CascadedLimiterLocation(record.icons[1]),maximum_location=CascadedLimiterLocation(record.icons[0]),
                supplement_location=CompoundSupplementLocation(record.icons[3])))
        else:
            template = build_ac7b_template(vf,name,cascaded_parameters)
    elif record.model.upper() in ('AC8B','AC8C'):
        pid_brushless_parameters: PidBrushlessExciterParameters = PidBrushlessExciterParameters(
            tr=named_parameter(record,'TR'),
            kpr=named_parameter(record,'KPR'),
            kir=named_parameter(record,'KIR'),
            kdr=named_parameter(record,'KDR'),
            tdr=named_parameter(record,'TDR'),
            vpidmax=named_parameter(record,'VPIDMAX'),
            vpidmin=named_parameter(record,'VPIDMIN'),
            ka=named_parameter(record,'KA'),
            ta=named_parameter(record,'TA'),
            vrmax=named_parameter(record,'VRMAX'),
            vrmin=named_parameter(record,'VRMIN'),
            kc=named_parameter(record,'KC'),
            kd=named_parameter(record,'KD'),
            ke=named_parameter(record,'KE'),
            te=named_parameter(record,'TE'),
            vfemax=named_parameter(record,'VFEMAX'),
            vemin=named_parameter(record,'VEMIN'),
            e1=named_parameter(record,'E1'),
            se1=named_parameter(record,'SE1'),
            e2=named_parameter(record,'E2'),
            se2=named_parameter(record,'SE2'))
        if record.model.upper() == 'AC8C':
            template = build_ac8c_template(vf,name,pid_brushless_parameters,CompoundPidPowerCircuit(
                kp=named_parameter(record,'KP'),ki=named_parameter(record,'KI'),xl=named_parameter(record,'XL'),
                theta=named_parameter(record,'THETAP'),kc1=named_parameter(record,'KC1'),vbmax=named_parameter(record,'VBMAX'),
                source=CompoundExcitationSource(record.icons[4]),minimum_location=ExcitationLimiterLocation(record.icons[1]),
                maximum_location=ExcitationLimiterLocation(record.icons[0]),supplement_location=CompoundSupplementLocation(record.icons[3])))
        else:
            template = build_ac8b_template(vf,name,pid_brushless_parameters)
    elif record.model.upper() == 'ST4C':
        template = build_st4c_template(vf,name,FilteredCompoundPiParameters(
            tr=named_parameter(record,'TR'),
            kpr=named_parameter(record,'KPR'),
            kir=named_parameter(record,'KIR'),
            vrmax=named_parameter(record,'VRMAX'),
            vrmin=named_parameter(record,'VRMIN'),
            kpm=named_parameter(record,'KPM'),
            kim=named_parameter(record,'KIM'),
            vmmax=named_parameter(record,'VMMAX'),
            vmmin=named_parameter(record,'VMMIN'),
            ta=named_parameter(record,'TA'),
            vamax=named_parameter(record,'VAMAX'),
            vamin=named_parameter(record,'VAMIN'),
            kg=named_parameter(record,'KG'),
            tg=named_parameter(record,'TG'),
            vgmax=named_parameter(record,'VGMAX'),
            kp=named_parameter(record,'KP'),
            ki=named_parameter(record,'KI'),
            xl=named_parameter(record,'XL'),
            thetap=named_parameter(record,'THETAP'),
            kc=named_parameter(record,'KC'),
            vbmax=named_parameter(record,'VBMAX'),
            minimum_location=ExcitationLimiterLocation(record.icons[2]),maximum_location=ExcitationLimiterLocation(record.icons[1]),
            supplement_location=CompoundSupplementLocation(record.icons[0]),source=CompoundExcitationSource(record.icons[4])))
    elif record.model.upper() == 'ESST4B':
        template = build_st4b_template(vf,name,CompoundPiExciterParameters(
            tr=named_parameter(record,'TR'),kpr=named_parameter(record,'KPR'),kir=named_parameter(record,'KIR'),
            vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),ta=named_parameter(record,'TA'),
            kpm=named_parameter(record,'KPM'),kim=named_parameter(record,'KIM'),vmmax=named_parameter(record,'VMMAX'),vmmin=named_parameter(record,'VMMIN'),
            kg=named_parameter(record,'KG'),kp=named_parameter(record,'KP'),ki=named_parameter(record,'KI'),vbmax=named_parameter(record,'VBMAX'),
            kc=named_parameter(record,'KC'),xl=named_parameter(record,'Xl'),thetap=named_parameter(record,'THETAP')))
    elif record.model.upper() in ('ST7B','ST7C'):
        if len(record.icons) != 2:
            raise ValueError('Self-feedback excitation requires explicit OEL/UEL selectors')
        else:
            pass
        template = build_self_feedback_exciter(vf,name,
            ExcitationBridgeDynamics.FIRING_LAG if record.model.upper() == 'ST7C' else ExcitationBridgeDynamics.INSTANTANEOUS,
            SelfFeedbackExciterParameters(tr=named_parameter(record,'TR'),tg=named_parameter(record,'TG'),tf=named_parameter(record,'TF'),
                vmax=named_parameter(record,'VMAX'),vmin=named_parameter(record,'VMIN'),kpa=named_parameter(record,'KPA'),
                vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),kh=named_parameter(record,'KH'),kl=named_parameter(record,'KL'),
                tc=named_parameter(record,'TC'),tb=named_parameter(record,'TB'),kia=named_parameter(record,'KIA'),tia=named_parameter(record,'TIA'),
                ta=named_parameter(record,'TA') if record.model.upper() == 'ST7C' else .02,
                minimum_location=ExcitationLimiterLocation(record.icons[1]),maximum_location=ExcitationLimiterLocation(record.icons[0])))
    elif record.model.upper() in ('ESST1A','ST1C'):
        if len(record.icons) != (3 if record.model.upper() == 'ST1C' else 2):
            raise ValueError('Terminal-fed static excitation requires UEL and stabilizer insertion flags')
        else:
            pass
        template = build_esst1a_template(vf,name,TerminalFedExciterParameters(
            tr=named_parameter(record,'TR'),vi_max=named_parameter(record,'VIMAX'),vi_min=named_parameter(record,'VIMIN'),
            tc=named_parameter(record,'TC'),tb=named_parameter(record,'TB'),tc1=named_parameter(record,'TC1'),tb1=named_parameter(record,'TB1'),
            ka=named_parameter(record,'KA'),ta=named_parameter(record,'TA'),va_max=named_parameter(record,'VAMAX'),va_min=named_parameter(record,'VAMIN'),
            vr_max=named_parameter(record,'VRMAX'),vr_min=named_parameter(record,'VRMIN'),kc=named_parameter(record,'KC'),
            kf=named_parameter(record,'KF'),tf=named_parameter(record,'TF'),klr=named_parameter(record,'KLR'),ilr=named_parameter(record,'ILR'),
            minimum_location=StaticMinimumExcitationLocation(record.icons[0]),stabilizer_location=StaticStabilizerLocation(record.icons[1])),
            StaticMaximumExcitationLocation(record.icons[2]) if record.model.upper() == 'ST1C' else None)
    elif record.model.upper() == 'BBSEX1':
        template = build_bbsex1_template(vf,name,FeedbackStaticExciterParameters(
            tr=named_parameter(record,'TF'),gain=named_parameter(record,'K'),
            t1=named_parameter(record,'T1'),t2=named_parameter(record,'T2'),
            t3=named_parameter(record,'T3'),t4=named_parameter(record,'T4'),
            regulator_max=named_parameter(record,'VRMAX'),regulator_min=named_parameter(record,'VRMIN'),
            field_max=named_parameter(record,'EFDMAX'),field_min=named_parameter(record,'EFDMIN'),
            auxiliary_location=AuxiliaryVoltageLocation.FIELD_OUTPUT if named_parameter(record,'Switch') == 0 else AuxiliaryVoltageLocation.VOLTAGE_ERROR))
    elif record.model.upper() == 'ESAC8B':
        if named_parameter(record,'KE') == 0 or named_parameter(record,'VRMAX') == 0:
            raise ValueError('ESAC8B automatic field/capability calibration has not been reviewed')
        else:
            pass
        template = build_esac8b_template(vf,name,DcExciterParameters(
            tr=named_parameter(record,'TR'),ka=named_parameter(record,'KA'),ta=named_parameter(record,'TA'),
            vrmax=named_parameter(record,'VRMAX'),vrmin=named_parameter(record,'VRMIN'),
            te=named_parameter(record,'TE'),ke=named_parameter(record,'KE'),
            e1=named_parameter(record,'E1'),se1=named_parameter(record,'SE1'),
            e2=named_parameter(record,'E2'),se2=named_parameter(record,'SE2')),
            named_parameter(record,'KP'),named_parameter(record,'KI'),
            named_parameter(record,'KD'),named_parameter(record,'TD'))
    elif binding.dc_kind is not None:
        kind: DcExciterKind = binding.dc_kind
        bounded_rotating: bool = kind in (DcExciterKind.BOUNDED_FIXED_SUPPLY,DcExciterKind.BOUNDED_TERMINAL_SUPPLY)
        field_coefficient: float = named_parameter(record,'KE')
        upper_capability: float = named_parameter(record,'VRMAX')
        p: DcExciterParameters = DcExciterParameters(tr=0.0 if kind == DcExciterKind.LIMITED_TYPE1 else named_parameter(record,'TR'),
            ka=named_parameter(record,'KA'),ta=named_parameter(record,'TA'),
            tb=0.0 if kind in (DcExciterKind.TYPE1,DcExciterKind.TYPE2,DcExciterKind.BRUSHLESS,DcExciterKind.LIMITED_TYPE1) else named_parameter(record,'TB'),
            tc=0.0 if kind in (DcExciterKind.TYPE1,DcExciterKind.TYPE2,DcExciterKind.BRUSHLESS,DcExciterKind.LIMITED_TYPE1) else named_parameter(record,'TC'),
            vrmax=None if upper_capability == 0 else upper_capability,vrmin=named_parameter(record,'VRMIN'),
            ke=None if field_coefficient == 0 else field_coefficient,te=named_parameter(record,'TE'),
            kf=named_parameter(record,'KF1' if record.model.upper() == 'IEEEX1' else 'KF'),
            tf=named_parameter(record,'TF' if kind in (DcExciterKind.TYPE1,DcExciterKind.LIMITED_TYPE1,DcExciterKind.BOUNDED_FIXED_SUPPLY,DcExciterKind.BOUNDED_TERMINAL_SUPPLY) else 'TF1'),
            e1=named_parameter(record,'E1'),se1=named_parameter(record,'SE1'),
            e2=named_parameter(record,'EFDMAX' if kind == DcExciterKind.LIMITED_TYPE1 else 'E2'),
            se2=named_parameter(record,'SEMAX' if kind == DcExciterKind.LIMITED_TYPE1 else 'SE2'),
            tf2=named_parameter(record,'TF2') if kind in (DcExciterKind.TYPE2,DcExciterKind.COMPENSATED_TYPE2,DcExciterKind.BRUSHLESS) else 1.0,
            tf3=named_parameter(record,'TF3') if kind == DcExciterKind.BRUSHLESS else 0.0,
            field_min=named_parameter(record,'VEMIN') if bounded_rotating else (named_parameter(record,'EFDMIN') if kind == DcExciterKind.LIMITED_TYPE1 else 0.0),
            field_max=named_parameter(record,'VEMAX') if bounded_rotating else 999.)
        template = build_dc_exciter(vf,name,kind,p,
            RotatingLimiterLocation(record.icons[1]) if bounded_rotating else RotatingLimiterLocation.SUMMATION,
            RotatingLimiterLocation(record.icons[0]) if bounded_rotating else RotatingLimiterLocation.SUMMATION)
    elif record.model.upper() in ('IEEET3','IEEEX3'):
        template = build_thevenin_exciter(vf,name,
            CompoundCapabilityLocation.TOTAL_FORCING if record.model.upper() == 'IEEET3' else CompoundCapabilityLocation.COMPOUND_SUPPLY,
            TheveninExciterParameters(tr=named_parameter(record,'TR'),ka=named_parameter(record,'KA'),ta=named_parameter(record,'TA'),
                regulator_max=named_parameter(record,'VRMAX'),regulator_min=named_parameter(record,'VRMIN'),
                te=named_parameter(record,'TE'),kf=named_parameter(record,'KF'),tf=named_parameter(record,'TF'),
                kp=named_parameter(record,'KP'),ki=named_parameter(record,'KI'),supply_max=named_parameter(record,'VBMAX'),ke=named_parameter(record,'KE')))
    elif record.model.upper() in ('EXST2','EXST2A','ESST2A'):
        template = build_exst2_template(vf,name,transducer_time=named_parameter(record,'TR'),
            regulator_gain=named_parameter(record,'KA'),regulator_time=named_parameter(record,'TA'),
            regulator_max=named_parameter(record,'VRMAX'),regulator_min=named_parameter(record,'VRMIN'),
            field_feedback=named_parameter(record,'KE'),exciter_time=named_parameter(record,'TE'),
            rate_gain=named_parameter(record,'KF'),rate_time=named_parameter(record,'TF'),
            potential_gain=named_parameter(record,'KP'),current_gain=named_parameter(record,'KI'),
            commutation_gain=named_parameter(record,'KC'),field_max=named_parameter(record,'EFDMAX'),
            initial_field_voltage=0.0,
            kind=CompoundExciterKind.ADDITIVE_BRIDGE if record.model.upper() == 'EXST2' else (
                CompoundExciterKind.GATED_MULTIPLICATIVE_BRIDGE if record.model.upper() == 'ESST2A' else CompoundExciterKind.MULTIPLICATIVE_BRIDGE))
    elif record.model.upper() in ('IVOST','IVOGO'):
        rational_stages: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] = (
            RationalStageParameters(gain=named_parameter(record,'K1'),numerator=named_parameter(record,'A1'),
                denominator=named_parameter(record,'A2'),lead=named_parameter(record,'T1'),lag=named_parameter(record,'T2'),
                maximum=named_parameter(record,'MAX1'),minimum=named_parameter(record,'MIN1')),
            RationalStageParameters(gain=named_parameter(record,'K3'),numerator=named_parameter(record,'A3'),
                denominator=named_parameter(record,'A4'),lead=named_parameter(record,'T3'),lag=named_parameter(record,'T4'),
                maximum=named_parameter(record,'MAX3'),minimum=named_parameter(record,'MIN3')),
            RationalStageParameters(gain=named_parameter(record,'K5'),numerator=named_parameter(record,'A5'),
                denominator=named_parameter(record,'A6'),lead=named_parameter(record,'T5'),lag=named_parameter(record,'T6'),
                maximum=named_parameter(record,'MAX5'),minimum=named_parameter(record,'MIN5')),
        )
        if record.model.upper() == 'IVOST':
            template = build_ivost_template(vf,name,rational_stages)
        else:
            template = build_ivogo_template(vf,name,rational_stages)
    elif record.model.upper() == 'COMP':
        template = build_comp_template(vf, name, reactance=named_parameter(record,'Xe'))
    elif binding.standard is not None:
        if record.model.upper() in ('AC1C','AC2C','AC5C'):
            existing_uids: set[int] = set(vf.get_vars_dict().keys())
            existing_uids.update(vf.get_diff_var_dict().keys())
            if record.model.upper() == 'AC1C':
                template = build_ac1c_template(vf,name,RotatingLimiterLocation(record.icons[1]),RotatingLimiterLocation(record.icons[0]))
            elif record.model.upper() == 'AC2C':
                template = build_ac2c_template(vf,name,RotatingLimiterLocation(record.icons[1]),RotatingLimiterLocation(record.icons[0]))
            else:
                template = build_ac5c_template(vf,name,RotatingLimiterLocation(record.icons[1]),RotatingLimiterLocation(record.icons[0]))
            _normalize_imported_variable_names(vf,existing_uids)
        elif record.model.upper() == 'SCRX':
            existing_uids: set[int] = set(vf.get_vars_dict().keys())
            existing_uids.update(vf.get_diff_var_dict().keys())
            template = build_scrx_template(vf,name,exciter_time=named_parameter(record,'TE'))
            _normalize_imported_variable_names(vf,existing_uids)
        else:
            template = build_international_standard_template(binding.standard, vf, name)
        bind_parameters(template.block,record,binding,vf,name)
        if record.model.upper() == 'SEXS':
            set_rms_model_parameter(template.block,'Ta_'+name,named_parameter(record,'TATB')*named_parameter(record,'TB'),vf)
        elif record.model.upper() == 'SCRX':
            set_rms_model_parameter(template.block,'avr_tA_'+name,named_parameter(record,'TATB')*named_parameter(record,'TB'),vf)
        else:
            pass
        if record.model.upper() in ('EXAC1','EXAC1A','ESAC1A','EXAC2','EXAC3','ESAC2A','ESAC3A','EXBAS','AC1C','AC2C','AC5C'):
            variables: dict[str, Var] = dict((var.name, var) for var in template.block.event_dict)
            lead_state: Var = next(var for var in template.block.state_vars if var.name == 'avr_leadLag_x_scaled_1_'+name)
            template.block.init_eqs[lead_state] = variables['avr_leadLag_a_end_'+name] * variables['avr_leadLag_x_start_1_'+name]
            if named_parameter(record,'SE1') == 0 and named_parameter(record,'SE2') == 0:
                # Remove the disabled curve structurally rather than evaluate
                # a gated zero multiplied by an undefined saturation fit.
                for coefficient in ('avr_Sq','avr_Bsq','avr_VExcThresholdPu'):
                    set_rms_model_parameter(template.block,coefficient+'_'+name,0.0,vf)
            else:
                pass
        else:
            pass
        if record.model.upper() == 'IEEEG2' and named_parameter(record,'T1') == 0:
            # A zero speed-filter lag is an exact measurement identity. The
            # following positive T3 compensator still makes the transfer proper.
            filter_name: str = 'gov_firstOrder_y_'+name
            filter_index: int = next(index for index,variable in enumerate(template.block.state_vars) if variable.name == filter_name)
            filter_state: Var = template.block.state_vars.pop(filter_index)
            template.block.state_eqs.pop(filter_index)
            template.block.diff_vars.pop(filter_index)
            template.block.algebraic_vars.append(filter_state)
            template.block.algebraic_eqs.append(filter_state-(template.block.in_vars[0]-template.block.in_vars[1]))
        else:
            pass
        # Generated catalogue components include stand-alone input declarations
        # and unused Modelica diagnostic/$START variables. Inputs are owned by
        # the host once wired; dead declarations must not make its DAE singular.
        used: set[int] = set()
        for equations in (template.block.state_eqs, template.block.algebraic_eqs):
            for equation in equations:
                used.update(var.uid for var in equation.get_vars())
        inputs: set[int] = set(var.uid for var in template.block.in_vars)
        retained: list[Var] = list()
        for variable in template.block.algebraic_vars:
            if variable.uid in inputs:
                pass
            elif variable.uid in used:
                retained.append(variable)
            else:
                template.block.init_eqs.pop(variable, None)
        template.block.algebraic_vars = retained
    else:
        raise ValueError('No reviewed native controller builder')
    return template


def configure_exst1_algebraic_lags(block: Block, record: DyrRecord) -> None:
    """Lower documented zero-time-constant EXST1 lags to exact algebraic equations.

    :param block: Fresh native EXST1 block, with reviewed original state/port order.
    :param record: Source constants; no epsilon replaces zero lags.
    """
    states: list[Var] = list()
    equations: list[Expr] = list()
    derivatives: list[Var] = list()
    gain: Var = next(var for var in block.event_dict if var.name == 'KA')
    for index, parameter in enumerate(('TR','TB','TA','TF')):
        state: Var = block.state_vars[index]
        if named_parameter(record,parameter) != 0:
            states.append(state)
            equations.append(block.state_eqs[index])
            if index < len(block.diff_vars):
                derivatives.append(block.diff_vars[index])
            else:
                pass
        else:
            block.algebraic_vars.append(state)
            if index == 0:
                block.algebraic_eqs.append(block.in_vars[1]-state)
            elif index == 1:
                block.algebraic_eqs.append(block.algebraic_vars[2]-state)
                block.algebraic_eqs[3] = block.algebraic_vars[3]-block.algebraic_vars[2]
            elif index == 2:
                block.algebraic_eqs.append(gain*block.algebraic_vars[3]-state)
            else:
                block.algebraic_eqs.append(block.state_vars[2]-state)
                block.algebraic_eqs[4] = block.algebraic_vars[4]
    block.state_vars = states
    block.state_eqs = equations
    block.diff_vars = derivatives


def freeze_named_parameter(block: Block, name: str, initial: Expr | Const, vf: VarFactory) -> None:
    """Initialize a native service parameter from the host's power-flow state.

    :param block: Controller block.
    :param name: Exact native parameter name.
    :param initial: Initialization expression.
    :param vf: Circuit symbol factory.
    :raises ValueError: Missing or ambiguous parameter mapping.
    """
    matches: list[Var] = [var for var in block.event_dict if var.name == name]
    if len(matches) != 1:
        raise ValueError('Native service parameter not unique: ' + name)
    else:
        parameter: Var = matches[0]
        block.event_dict[parameter] = vf.add_const(value=None, name=name)
        block.init_eqs[parameter] = initial


def connect_scaled(root: Block, target: Var, source: Var, factor: float, vf: VarFactory) -> None:
    """Connect a controller port with an explicit machine/system base conversion.

    :param root: Owning composite block for a required scaling equation.
    :param target: Consuming port.
    :param source: Producing signal.
    :param factor: Target units divided by source units.
    :param vf: Shared symbol factory.
    """
    if factor == 1.0:
        vf.add_connection(target, source)
    else:
        root.algebraic_vars.append(target)
        root.algebraic_eqs.append(target - source * sym.Const(factor))
        root.init_eqs[target] = source * sym.Const(factor)


def bind_supplementary_voltage(root: Block, block: Block, port: Var, vf: VarFactory,
                                stabilizer: Block | None, underexcitation: Block | None) -> None:
    """Connect additive voltage controls to an exciter's common summation port.

    :param root: Assembly owning a required signal-summing equation.
    :param block: Exciter owning the open input port.
    :param port: Common supplementary voltage input.
    :param vf: Shared circuit variable factory.
    :param stabilizer: Optional supplementary damping controller.
    :param underexcitation: Optional additive minimum-excitation controller.
    """
    if stabilizer is None and underexcitation is None:
        freeze_input(block,port,vf,sym.Const(0.0))
    else:
        signal: Expr = sym.Const(0.0)
        if stabilizer is not None:
            signal = signal+stabilizer.out_vars[0]
        else:
            pass
        if underexcitation is not None:
            signal = signal+underexcitation.out_vars[0]
        else:
            pass
        root.algebraic_vars.append(port)
        root.algebraic_eqs.append(port-signal)
        root.init_eqs[port] = signal


def attach_controller(template: RmsModelTemplate, machine: Block, controller: RmsModelTemplate,
                      record: DyrRecord, vf: VarFactory, base_ratio: float, system_base: float,
                      stabilizer: Block | None = None, compensator: Block | None = None,
                      underexcitation: Block | None = None, load_controller: Block | None = None) -> None:
    """Wire a reviewed governor/exciter to one complete generator model.

    :param template: Composite generator template.
    :param machine: Network-facing machine block with reviewed port order.
    :param controller: Parameterized native component.
    :param record: Source controller record.
    :param vf: Circuit symbol factory.
    :param base_ratio: Machine MVA divided by system MVA.
    :param system_base: Network power base in MVA for an explicitly rated turbine.
    :param stabilizer: Optional already-connected supplementary-voltage controller.
    :param compensator: Optional already-connected voltage measurement component.
    :param underexcitation: Optional already-connected additive minimum-excitation limiter.
    :param load_controller: Optional reviewed outer load controller, consumed by its compatible governor.
    """
    block: Block = controller.block.children[0] if controller.block.children else controller.block
    model: str = dynamic_record_name(record)
    binding: PsseDynamicBinding | None = dynamic_binding(model)
    dc_kind: DcExciterKind | None = None if binding is None else binding.dc_kind
    electromechanical_kind: ElectromechanicalExciterKind | None = None if binding is None else binding.electromechanical_kind
    sensed_voltage: Var = machine.in_vars[0] if compensator is None else compensator.out_vars[0]
    stabilizer_bias: Expr = Const(0.0) if stabilizer is None else stabilizer.out_vars[0]
    # Connections replace port references; capture the machine's operating-point
    # expression before the field port is rebound to the controller output.
    field_initial: Expr | Const | None = machine.init_eqs.get(machine.in_vars[3], None) if len(machine.in_vars) > 3 else None
    controller_reference_initial: Expr | Const | None = block.init_eqs.get(block.in_vars[1],None) if model in ('EXST2','EXST2A','ESST2A','IEEET3','IEEEX3','EXAC4','ESAC4A','AC4C','ESAC8B','BBSEX1','BUDCZT','ESST1A','ST1C','ST7B','ST7C','ST5B','ST5C','ST6C','AC7B','AC7C','AC8B','AC8C','ST4C','ESST4B','IEET1B','EXNI','EXPIC1','DC4B','DC4C') or dc_kind is not None or electromechanical_kind is not None else None
    pid_reference_initial: Expr | Const | None = block.init_eqs.get(block.in_vars[1],None) if model in ('PIDGOV','PIDGOVD','PIDGOVDU') else None
    fuel_reference_initial: Expr | Const | None = block.init_eqs.get(block.in_vars[2],None) if model in ('GGOV1','GGOV1D','GGOV1DU') else None
    rational_reference: Expr | Const | None = block.init_eqs.get(block.in_vars[1],None) if model == 'IVOGO' else None
    engine_reference: Expr | Const | None = block.init_eqs.get(block.in_vars[2],None) if model in ('DEGOV','DEGOV1','DEGOV1D','DEGOV1DU') else None
    # OpenIPSL components carry stand-alone input guesses. They must not
    # overwrite the producing machine/bus initializer after port rebinding.
    for input_port in block.in_vars:
        block.init_eqs.pop(input_port, None)
    if binding is not None and binding.role == PsseDynamicRole.EXCITER and field_initial is not None:
        block.init_eqs[block.out_vars[0]] = field_initial
    else:
        pass
    if model == 'TGOV1':
        vf.add_connection(machine.in_vars[2], block.out_vars[0])
        vf.add_connection(block.in_vars[0], machine.out_vars[2])
        torque: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        vf.add_connection(block.in_vars[1], torque)
    elif model in ('GGOV1','GGOV1D','GGOV1DU'):
        fuel_rating: float = named_parameter(record,'TRATE')
        fuel_ratio: float = fuel_rating/system_base if fuel_rating > 0 else base_ratio
        fuel_initial: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        if fuel_reference_initial is None:
            raise ValueError('Fuel-governor speed/load reference initialization is missing')
        else:
            pass
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,block.in_vars[1],machine.out_vars[0],1/fuel_ratio,vf)
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[0],fuel_ratio,vf)
        freeze_named_parameter(block,'InitialMechanicalPowerPu_'+controller.name,fuel_initial/Const(fuel_ratio),vf)
        freeze_input(block,block.in_vars[2],vf,fuel_reference_initial)
        freeze_input(block,block.in_vars[3],vf,machine.out_vars[0]/Const(fuel_ratio))
    elif model == 'IVOGO':
        if rational_reference is None:
            raise ValueError('Rational governor operating-point reference is missing')
        else:
            pass
        rational_torque0: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[1],base_ratio,vf)
        freeze_named_parameter(block,'InitialMechanicalPowerPu_'+controller.name,rational_torque0*machine.out_vars[2]/Const(base_ratio),vf)
        freeze_input(block,block.in_vars[1],vf,rational_reference)
    elif model in ('DEGOV','DEGOV1','DEGOV1D','DEGOV1DU'):
        engine_rating: float = named_parameter(record,'TRATE') if model in ('DEGOV1D','DEGOV1DU') else 0.
        engine_ratio: float = engine_rating/system_base if engine_rating > 0 else base_ratio
        engine_initial: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        if engine_reference is None:
            raise ValueError('Engine governor reference initialization is missing')
        else:
            pass
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,block.in_vars[1],machine.out_vars[0],1/engine_ratio,vf)
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[1],engine_ratio,vf)
        freeze_named_parameter(block,'InitialMechanicalTorquePu_'+controller.name,engine_initial/Const(engine_ratio),vf)
        freeze_named_parameter(block,'InitialElectricalPowerPu_'+controller.name,machine.out_vars[0]/Const(engine_ratio),vf)
        freeze_input(block,block.in_vars[2],vf,engine_reference)
    elif model in ('IEEEG1','IEEEG1D','IEEEG1SDU'):
        steam_rating: float = named_parameter(record,'TRATE') if model in ('IEEEG1D','IEEEG1SDU') else 0.0
        steam_ratio: float = steam_rating/system_base if steam_rating > 0 else base_ratio
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[2],steam_ratio,vf)
        steam_initial: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        freeze_input(block,block.in_vars[1],vf,Const(1.0))
        if load_controller is None:
            freeze_input(block,block.in_vars[2],vf,steam_initial/Const(steam_ratio))
        else:
            fraction_sum: float = sum(named_parameter(record,'K'+str(index)) for index in range(1,9))
            freeze_input(load_controller,load_controller.in_vars[2],vf,steam_initial/Const(steam_ratio*fraction_sum))
            connect_scaled(template.block,block.in_vars[2],load_controller.out_vars[0],fraction_sum,vf)
    elif model in ('IEEEG3','IEEEG3D','IEEEG3DU'):
        turbine_rating: float = named_parameter(record,'TRATE') if model in ('IEEEG3D','IEEEG3DU') else 0.0
        turbine_ratio: float = turbine_rating/system_base if turbine_rating > 0 else base_ratio
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[0],turbine_ratio,vf)
        initial_power: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        freeze_input(block,block.in_vars[1],vf,initial_power/Const(turbine_ratio))
    elif model == 'IEEEG2':
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[0],base_ratio,vf)
        torque: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        initial: Expr = torque/sym.Const(base_ratio)
        freeze_input(block,block.in_vars[1],vf,sym.Const(1.0))
        freeze_input(block,block.in_vars[2],vf,initial)
        freeze_named_parameter(block,'gov_Pm0Pu_'+controller.name,initial,vf)
    elif model in ('GAST','GASTD','GASTDU','IEESGO','IEESGOD','IEESGODU','TGOV1D','TGOV1DU'):
        family_ratio: float = base_ratio if model in ('GAST','IEESGO') else (named_parameter(record,'TRATE')/system_base if named_parameter(record,'TRATE') > 0 else base_ratio)
        vf.add_connection(block.in_vars[0], machine.out_vars[2])
        connect_scaled(template.block, machine.in_vars[2], block.out_vars[0], family_ratio, vf)
        torque: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        freeze_input(block, block.in_vars[1], vf, torque / sym.Const(family_ratio))
    elif model in ('PIDGOV','PIDGOVD','PIDGOVDU'):
        pid_ratio: float = base_ratio if model == 'PIDGOV' else (named_parameter(record,'TRATE')/system_base if named_parameter(record,'TRATE') > 0 else base_ratio)
        if pid_reference_initial is None:
            raise ValueError('Hydraulic PID reference initialization is missing')
        else:
            pass
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,block.in_vars[2],machine.out_vars[0],1./pid_ratio,vf)
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[0],pid_ratio,vf)
        pid_torque: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        freeze_named_parameter(block,'Pm0Pu_'+controller.name,pid_torque/Const(pid_ratio),vf)
        freeze_named_parameter(block,'Pe0Pu_'+controller.name,machine.out_vars[0]/Const(pid_ratio),vf)
        freeze_input(block,block.in_vars[1],vf,pid_reference_initial)
    elif model in ('HYGOV2','HYGOV2D','HYGOV2DU'):
        cascade_ratio: float = base_ratio if model == 'HYGOV2' else (named_parameter(record,'TRATE')/system_base if named_parameter(record,'TRATE') > 0 else base_ratio)
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[0],cascade_ratio,vf)
        cascade_torque: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        initial_cascade_power: Expr = cascade_torque/Const(cascade_ratio)
        freeze_named_parameter(block,'Pm0Pu_'+controller.name,initial_cascade_power,vf)
        freeze_input(block,block.in_vars[1],vf,Const(named_parameter(record,'R')/named_parameter(record,'PMAX'))*initial_cascade_power)
    elif model in ('HYGOV','HYGOVD','HYGOVDU'):
        hydro_ratio: float = base_ratio if model == 'HYGOV' else (named_parameter(record,'TRATE')/system_base if named_parameter(record,'TRATE') > 0 else base_ratio)
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
        connect_scaled(template.block,machine.in_vars[2],block.out_vars[0],hydro_ratio,vf)
        hydro_torque: Var = machine.out_vars[3] if len(machine.out_vars) == 4 else machine.out_vars[4]
        hydro_gate: Expr = hydro_torque/Const(hydro_ratio*named_parameter(record,'At'))+Const(named_parameter(record,'qNL'))
        freeze_input(block,block.in_vars[1],vf,Const(named_parameter(record,'R'))*hydro_gate)
    elif model in ('EXST1','ESST3A'):
        vf.add_connection(machine.in_vars[3], block.out_vars[0])
        vf.add_connection(block.in_vars[0], machine.out_vars[3])
        vf.add_connection(block.in_vars[1], sensed_voltage)
        if model == 'ESST3A':
            vf.add_connection(block.in_vars[2], machine.out_vars[5])
            vf.add_connection(block.in_vars[3], machine.out_vars[6])
            connect_scaled(template.block, block.in_vars[4], machine.out_vars[7], 1.0/base_ratio, vf)
            connect_scaled(template.block, block.in_vars[5], machine.out_vars[8], 1.0/base_ratio, vf)
            pss: Var = block.in_vars[6]
        else:
            pss = block.in_vars[2]
        bind_supplementary_voltage(template.block,block,pss,vf,stabilizer,underexcitation)
        if underexcitation is not None or stabilizer is not None:
            # Template normalization may already have moved an initialized
            # reference parameter from init_eqs into event_dict.
            for registry in (block.init_eqs,block.event_dict):
                for variable in tuple(registry):
                    if variable.name in ('vref0','vref'):
                        registry[variable] = registry[variable]-stabilizer_bias
                        if underexcitation is not None:
                            registry[variable] = registry[variable]-underexcitation.out_vars[0]
                        else:
                            pass
                    else:
                        pass
        else:
            pass
    elif model in ('EXAC4','ESAC4A','AC4C'):
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Alternator-fed rectifier field/reference initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[4],machine.out_vars[3])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        if stabilizer is None:
            freeze_input(block,block.in_vars[2],vf,Const(0.0))
        else:
            vf.add_connection(block.in_vars[2],stabilizer.out_vars[0])
        gated: bool = model == 'ESAC4A' or (model == 'AC4C' and record.icons[1] == 2)
        if model == 'AC4C':
            if record.icons[0] == 2:
                vf.add_connection(block.in_vars[5],block.out_vars[2])
            else:
                freeze_input(block,block.in_vars[5],vf,Const(0.0))
        else:
            pass
        if underexcitation is not None:
            vf.add_connection(block.in_vars[3],underexcitation.out_vars[0])
        elif gated:
            vf.add_connection(block.in_vars[3],block.out_vars[1])
        else:
            freeze_input(block,block.in_vars[3],vf,Const(0.0))
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial-stabilizer_bias
            if gated or underexcitation is None else controller_reference_initial-stabilizer_bias-underexcitation.out_vars[0])
    elif model == 'EXNI':
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Bidirectional bridge operating-point initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[4],machine.in_vars[0])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'Vt0Pu_'+controller.name,machine.in_vars[0],vf)
        freeze_named_parameter(block,'Aux0Pu_'+controller.name,stabilizer_bias if underexcitation is None else stabilizer_bias+underexcitation.out_vars[0],vf)
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if underexcitation is None:
            freeze_input(block,block.in_vars[3],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[3],underexcitation.out_vars[0])
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model == 'IEET1B':
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Biased rotating exciter operating-point initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[4],machine.in_vars[0])
        magnitude: Expr = sym.sqrt(machine.out_vars[7]**2+machine.out_vars[8]**2)/Const(base_ratio)
        template.block.algebraic_vars.append(block.in_vars[5])
        template.block.algebraic_eqs.append(block.in_vars[5]-magnitude)
        template.block.init_eqs[block.in_vars[5]] = magnitude
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'Imag0Pu_'+controller.name,magnitude,vf)
        freeze_named_parameter(block,'Aux0Pu_'+controller.name,stabilizer_bias if underexcitation is None else stabilizer_bias+underexcitation.out_vars[0],vf)
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if underexcitation is None:
            freeze_input(block,block.in_vars[3],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[3],underexcitation.out_vars[0])
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model in ('ST5B','ST5C'):
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Parallel-channel field/reference initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[3],machine.out_vars[3])
        vf.add_connection(block.in_vars[4],machine.in_vars[0])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Ifd0Pu_'+controller.name,machine.out_vars[3],vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'Vt0Pu_'+controller.name,machine.in_vars[0],vf)
        freeze_named_parameter(block,'Vs0Pu_'+controller.name,stabilizer_bias,vf)
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if model == 'ST5C' and record.icons[1] == 1:
            freeze_named_parameter(block,'Uel0Pu_'+controller.name,Const(0.) if underexcitation is None else underexcitation.out_vars[0],vf)
            if underexcitation is None:
                freeze_input(block,block.in_vars[5],vf,Const(0.))
            else:
                vf.add_connection(block.in_vars[5],underexcitation.out_vars[0])
        else:
            vf.add_connection(block.in_vars[5],block.out_vars[1] if underexcitation is None else underexcitation.out_vars[0])
        if model == 'ST5C' and record.icons[0] == 1:
            freeze_named_parameter(block,'Oel0Pu_'+controller.name,Const(0.),vf)
            freeze_input(block,block.in_vars[6],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[6],block.out_vars[2])
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model == 'AC7B':
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Cascaded brushless field/reference initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[3],machine.out_vars[3])
        vf.add_connection(block.in_vars[4],machine.in_vars[0])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Ifd0Pu_'+controller.name,machine.out_vars[3],vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'Vt0Pu_'+controller.name,machine.in_vars[0],vf)
        freeze_named_parameter(block,'Aux0Pu_'+controller.name,stabilizer_bias if underexcitation is None else stabilizer_bias+underexcitation.out_vars[0],vf)
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if underexcitation is None:
            freeze_input(block,block.in_vars[5],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[5],underexcitation.out_vars[0])
        freeze_input(block,block.in_vars[6],vf,Const(0.))
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model == 'AC8B':
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('PID brushless field/reference initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[3],machine.out_vars[3])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Ifd0Pu_'+controller.name,machine.out_vars[3],vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'Aux0Pu_'+controller.name,stabilizer_bias if underexcitation is None else stabilizer_bias+underexcitation.out_vars[0],vf)
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if underexcitation is None:
            freeze_input(block,block.in_vars[4],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[4],underexcitation.out_vars[0])
        freeze_input(block,block.in_vars[5],vf,Const(0.))
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model in ('ESST4B','EXPIC1','ST4C','AC8C','ST6C','AC7C'):
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Compound PI exciter operating-point initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[7],machine.out_vars[3])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'Vs0Pu_'+controller.name,stabilizer_bias,vf)
        freeze_named_parameter(block,'Uel0Pu_'+controller.name,Const(0.) if underexcitation is None else underexcitation.out_vars[0],vf)
        phasors: tuple[Expr,...] = terminal_phasor_signals(machine,base_ratio)
        for port,expression in zip(block.in_vars[3:7],phasors):
            template.block.algebraic_vars.append(port)
            template.block.algebraic_eqs.append(port-expression)
            template.block.init_eqs[port] = expression
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        minimum_flag: int = record.icons[1] if model in ('AC8C','ST6C','AC7C') else record.icons[2] if model == 'ST4C' else 1
        if underexcitation is None and model in ('ST4C','AC8C','ST6C','AC7C') and minimum_flag in ((2,4) if model == 'ST6C' else (2,3)):
            vf.add_connection(block.in_vars[8],block.out_vars[1 if minimum_flag == 2 else 3])
        elif underexcitation is None:
            freeze_input(block,block.in_vars[8],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[8],underexcitation.out_vars[0])
        if model in ('ST4C','AC8C','ST6C','AC7C'):
            if model in ('AC8C','ST6C','AC7C'):
                freeze_named_parameter(block,'Ifd0Pu_'+controller.name,machine.out_vars[3],vf)
            else:
                pass
            maximum_flag: int = record.icons[0] if model in ('AC8C','ST6C','AC7C') else record.icons[1]
            freeze_named_parameter(block,'Oel0Pu_'+controller.name,Const(0.),vf)
            if maximum_flag in ((1,3) if model == 'ST6C' else (1,)):
                freeze_input(block,block.in_vars[9],vf,Const(0.))
            else:
                vf.add_connection(block.in_vars[9],block.out_vars[2 if maximum_flag == 2 else 5 if model == 'AC7C' and maximum_flag == 4 else 4])
        elif model == 'ESST4B':
            vf.add_connection(block.in_vars[9],block.out_vars[1])
        else:
            pass
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model in ('ST7B','ST7C'):
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Self-feedback exciter operating-point initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[4],machine.in_vars[0])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'Vs0Pu_'+controller.name,stabilizer_bias,vf)
        freeze_named_parameter(block,'Uel0Pu_'+controller.name,Const(0.) if underexcitation is None else underexcitation.out_vars[0],vf)
        freeze_named_parameter(block,'Oel0Pu_'+controller.name,Const(0.),vf)
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if underexcitation is not None:
            vf.add_connection(block.in_vars[3],underexcitation.out_vars[0])
        elif record.icons[1] == 1:
            freeze_input(block,block.in_vars[3],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[3],block.out_vars[2 if record.icons[1] == 2 else 4])
        if record.icons[0] == 1:
            freeze_input(block,block.in_vars[5],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[5],block.out_vars[1 if record.icons[0] == 2 else 3])
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model in ('ESST1A','ST1C'):
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Terminal-fed static exciter initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[4],machine.in_vars[0])
        vf.add_connection(block.in_vars[5],machine.out_vars[3])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'Ifd0Pu_'+controller.name,machine.out_vars[3],vf)
        freeze_named_parameter(block,'Vs0Pu_'+controller.name,stabilizer_bias,vf)
        freeze_named_parameter(block,'Uel0Pu_'+controller.name,Const(0.) if underexcitation is None else underexcitation.out_vars[0],vf)
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if underexcitation is not None:
            vf.add_connection(block.in_vars[3],underexcitation.out_vars[0])
        elif record.icons[0] == 1:
            freeze_input(block,block.in_vars[3],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[3],block.out_vars[1 if record.icons[0] == 2 else 2])
        if model == 'ST1C':
            freeze_named_parameter(block,'Oel0Pu_'+controller.name,Const(0.),vf)
            if record.icons[2] == 1:
                freeze_input(block,block.in_vars[6],vf,Const(0.))
            else:
                vf.add_connection(block.in_vars[6],block.out_vars[4 if record.icons[2] == 2 else 3])
        else:
            vf.add_connection(block.in_vars[6],block.out_vars[3])
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model == 'BBSEX1':
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Static feedback exciter operating-point initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[4],machine.in_vars[0])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if underexcitation is None:
            freeze_input(block,block.in_vars[3],vf,Const(0.))
        else:
            vf.add_connection(block.in_vars[3],underexcitation.out_vars[0])
        auxiliary_initial: Expr = stabilizer_bias if underexcitation is None else stabilizer_bias+underexcitation.out_vars[0]
        freeze_named_parameter(block,'Aux0Pu_'+controller.name,auxiliary_initial,vf)
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial)
    elif model == 'DC4C':
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Compound commutator field/reference initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        compound_phasors: tuple[Expr,...] = terminal_phasor_signals(machine,base_ratio)
        for port,expression in zip(block.in_vars[3:7],compound_phasors):
            template.block.algebraic_vars.append(port)
            template.block.algebraic_eqs.append(port-expression)
            template.block.init_eqs[port] = expression
        bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
        if underexcitation is not None:
            vf.add_connection(block.in_vars[7],underexcitation.out_vars[0])
        elif record.icons[1] == 2:
            vf.add_connection(block.in_vars[7],block.out_vars[1])
        else:
            freeze_input(block,block.in_vars[7],vf,Const(0.))
        if record.icons[0] == 2:
            vf.add_connection(block.in_vars[8],block.out_vars[2])
        else:
            freeze_input(block,block.in_vars[8],vf,Const(0.))
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial-stabilizer_bias-
            (underexcitation.out_vars[0] if underexcitation is not None and record.icons[1] == 1 else Const(0.)))
    elif dc_kind is not None or electromechanical_kind is not None or model in ('ESAC8B','BUDCZT','DC4B'):
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Rotating exciter operating-point initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[4],machine.in_vars[0])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        if stabilizer is None:
            freeze_input(block,block.in_vars[2],vf,sym.Const(0.0))
        else:
            vf.add_connection(block.in_vars[2],stabilizer.out_vars[0])
        if model == 'DC4B':
            freeze_named_parameter(block,'Vt0Pu_'+controller.name,machine.in_vars[0],vf)
        else:
            pass
        bounded_rotating_host: bool = model == 'DC4B' or dc_kind in (DcExciterKind.BOUNDED_FIXED_SUPPLY,DcExciterKind.BOUNDED_TERMINAL_SUPPLY)
        gated: bool = dc_kind in (DcExciterKind.DC1A,DcExciterKind.DC2A) or (bounded_rotating_host and record.icons[1] == 2)
        if underexcitation is not None:
            vf.add_connection(block.in_vars[3],underexcitation.out_vars[0])
        elif gated:
            # max(demand,demand) bypasses an absent limiter at every time step.
            vf.add_connection(block.in_vars[3],block.out_vars[1])
        else:
            freeze_input(block,block.in_vars[3],vf,sym.Const(0.0))
        if bounded_rotating_host:
            if record.icons[0] == 2:
                vf.add_connection(block.in_vars[5],block.out_vars[2])
            else:
                freeze_input(block,block.in_vars[5],vf,Const(0.))
        else:
            pass
        freeze_input(block,block.in_vars[1],vf,controller_reference_initial-stabilizer_bias
            if gated or underexcitation is None else controller_reference_initial-stabilizer_bias-underexcitation.out_vars[0])
    elif model in ('EXST2','EXST2A','ESST2A','IEEET3','IEEEX3'):
        if field_initial is None or controller_reference_initial is None:
            raise ValueError('Static exciter field/reference initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],sensed_voltage)
        vf.add_connection(block.in_vars[7],machine.out_vars[3])
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        expressions: tuple[Expr,...] = terminal_phasor_signals(machine,base_ratio)
        for port,expression in zip(block.in_vars[3:7],expressions):
            template.block.algebraic_vars.append(port)
            template.block.algebraic_eqs.append(port-expression)
            template.block.init_eqs[port] = expression
        if model == 'ESST2A':
            bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,None)
            if underexcitation is None:
                vf.add_connection(block.in_vars[8],block.out_vars[1])
            else:
                vf.add_connection(block.in_vars[8],underexcitation.out_vars[0])
            freeze_input(block,block.in_vars[1],vf,controller_reference_initial-stabilizer_bias)
        else:
            bind_supplementary_voltage(template.block,block,block.in_vars[2],vf,stabilizer,underexcitation)
            freeze_input(block,block.in_vars[1],vf,controller_reference_initial-stabilizer_bias if underexcitation is None
                else controller_reference_initial-stabilizer_bias-underexcitation.out_vars[0])
    elif model == 'SCRX':
        if field_initial is None:
            raise ValueError('Static-exciter field initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],machine.out_vars[3])
        vf.add_connection(block.in_vars[4],sensed_voltage)
        vf.add_connection(block.in_vars[6],machine.in_vars[0])
        freeze_input(block,block.in_vars[1],vf,sym.Const(0.0))
        if stabilizer is None:
            freeze_input(block,block.in_vars[2],vf,sym.Const(0.0))
        else:
            vf.add_connection(block.in_vars[2],stabilizer.out_vars[0])
        if underexcitation is None:
            freeze_input(block,block.in_vars[5],vf,sym.Const(0.0))
        else:
            vf.add_connection(block.in_vars[5],underexcitation.out_vars[0])
        freeze_named_parameter(block,'avr_Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'avr_UStator0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'avr_Ut0Pu_'+controller.name,machine.in_vars[0],vf)
        freeze_named_parameter(block,'avr_IRotor0Pu_'+controller.name,machine.out_vars[3],vf)
        reference: Var = next(var for var in block.event_dict if var.name == 'avr_URef0Pu_'+controller.name)
        freeze_input(block,block.in_vars[3],vf,block.event_dict[reference]-stabilizer_bias if underexcitation is None
            else block.event_dict[reference]-stabilizer_bias-underexcitation.out_vars[0])
    elif model == 'SEXS':
        if field_initial is None:
            raise ValueError('Machine field initialization is missing')
        else:
            pass
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[1],sensed_voltage)
        bind_supplementary_voltage(template.block,block,block.in_vars[0],vf,stabilizer,underexcitation)
        freeze_named_parameter(block,'Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'Us0Pu_'+controller.name,sensed_voltage,vf)
        reference_initial: Expr = block.event_dict[next(var for var in block.event_dict if var.name == 'UsRef0Pu_'+controller.name)]
        freeze_input(block,block.in_vars[2],vf,reference_initial-stabilizer_bias if underexcitation is None
            else reference_initial-stabilizer_bias-underexcitation.out_vars[0])
    elif model in ('EXAC1','EXAC1A','ESAC1A','EXAC2','EXAC3','ESAC2A','ESAC3A','EXBAS','AC1C','AC2C','AC5C'):
        if field_initial is None:
            raise ValueError('Machine field initialization is missing')
        else:
            pass
        set_rms_model_parameter(block,'avr_ULow_'+controller.name,math.sqrt(3.0)/4.0,vf)
        vf.add_connection(machine.in_vars[3],block.out_vars[0])
        vf.add_connection(block.in_vars[0],machine.out_vars[3])
        vf.add_connection(block.in_vars[3],sensed_voltage)
        if model in ('ESAC1A','ESAC2A') or model in ('AC1C','AC2C','AC5C') and record.icons[0] == 2:
            vf.add_connection(block.in_vars[1],block.out_vars[2])
        else:
            freeze_input(block,block.in_vars[1],vf,sym.Const(0.0))
        if stabilizer is None:
            freeze_input(block,block.in_vars[2],vf,sym.Const(0.0))
        else:
            vf.add_connection(block.in_vars[2],stabilizer.out_vars[0])
        if underexcitation is None:
            if model in ('ESAC1A','ESAC2A','ESAC3A') or model in ('AC1C','AC2C','AC5C') and record.icons[1] == 2:
                vf.add_connection(block.in_vars[5],block.out_vars[1])
            else:
                freeze_input(block,block.in_vars[5],vf,sym.Const(0.0))
        else:
            vf.add_connection(block.in_vars[5],underexcitation.out_vars[0])
        freeze_named_parameter(block,'avr_Efd0Pu_'+controller.name,field_initial,vf)
        freeze_named_parameter(block,'avr_Us0Pu_'+controller.name,sensed_voltage,vf)
        freeze_named_parameter(block,'avr_Ir0Pu_'+controller.name,machine.out_vars[3],vf)
        # The template derives its reference from Efd0/Ir0 and saturation data.
        reference: Var = next(var for var in block.event_dict if var.name == 'avr_UsRef0Pu_'+controller.name)
        freeze_input(block,block.in_vars[4],vf,block.event_dict[reference]-stabilizer_bias if underexcitation is None or model in ('ESAC1A','ESAC2A','ESAC3A') or model in ('AC1C','AC2C','AC5C') and record.icons[1] == 2
            else block.event_dict[reference]-stabilizer_bias-underexcitation.out_vars[0])
    else:
        raise ValueError('No reviewed native signal connection for '+model)
    template.block.children.append(block)


def terminal_phasor_signals(machine: Block, base_ratio: float) -> tuple[Expr,...]:
    """Expose terminal voltage and machine-base current without dividing by voltage.

    :param machine: Machine with rotor-frame stator-current outputs.
    :param base_ratio: Machine MVA divided by system MVA.
    :return: Rectangular voltage/current signals in Vr,Vi,Ir,Ii order.
    """
    rotor: Block = machine.children[0] if machine.children else machine
    angle: Var = rotor.state_vars[0]
    voltage: Var = machine.in_vars[0]
    terminal_angle: Var = machine.in_vars[1]
    current_d: Var = machine.out_vars[7]
    current_q: Var = machine.out_vars[8]
    return (voltage*sym.cos(terminal_angle),voltage*sym.sin(terminal_angle),
        (current_d*sym.sin(angle)+current_q*sym.cos(angle))/sym.Const(base_ratio),
        (-current_d*sym.cos(angle)+current_q*sym.sin(angle))/sym.Const(base_ratio))


def attach_compensator(context: PsseAuxiliaryConverter, template: RmsModelTemplate,
                        machine: Block, controller: RmsModelTemplate, record: DyrRecord,
                        base_ratio: float) -> Block:
    """Connect local phasor or remote voltage sensing without changing the network.

    :param context: Native bus lookup and source conversion diagnostics.
    :param template: Complete host machine assembly.
    :param machine: Network-facing generator block with P/Q output ports.
    :param controller: Fresh native voltage-measurement component.
    :param record: Checked source voltage-compensation assignment.
    :param base_ratio: Machine MVA divided by system MVA.
    :return: Connected component whose output feeds the exciter measurement.
    :raises ValueError: Missing or invalid remote bus reference.
    """
    block: Block = controller.block
    vf: VarFactory = context.grid.var_factory
    for port in block.in_vars:
        block.init_eqs.pop(port,None)
    if record.model.upper() == 'REMCMP':
        remote_number: float = named_parameter(record,'JBUS')
        if remote_number <= 0 or not remote_number.is_integer():
            raise ValueError('Remote sensing requires a positive integer bus number')
        else:
            remote_bus: Bus | None = context.buses.get(int(remote_number),None)
            if remote_bus is None or remote_bus.is_dc:
                raise ValueError('Remote sensing requires an existing native AC bus')
            else:
                if remote_bus.rms_model.empty():
                    initialize_bus_rms(remote_bus,vf)
                else:
                    pass
                remote_voltage: Var | None = remote_bus.rms_model.external_mapping.get(VarPowerFlowReferenceType.Vm,None)
                if remote_voltage is None:
                    raise ValueError('Remote sensing bus has no polar RMS voltage mapping')
                else:
                    vf.add_network_connection(block.in_vars[0],remote_voltage)
    else:
        expressions: tuple[Expr,...] = terminal_phasor_signals(machine,base_ratio)
        for port,expression in zip(block.in_vars,expressions):
            template.block.algebraic_vars.append(port)
            template.block.algebraic_eqs.append(port-expression)
            template.block.init_eqs[port] = expression
    template.block.children.append(block)
    return block


def attach_underexcitation(template: RmsModelTemplate, machine: Block, controller: RmsModelTemplate,
                            record: DyrRecord, base_ratio: float) -> Block:
    """Connect capability and field signals to a native minimum-excitation controller.

    :param template: Complete host machine assembly.
    :param machine: Network-facing machine with rotor-frame current outputs.
    :param controller: Fresh native minimum-excitation controller.
    :param record: Source assignment selecting the capability characteristic.
    :param base_ratio: Machine MVA divided by system MVA.
    :return: Connected limiter whose output feeds the exciter summation.
    """
    block: Block = controller.block
    for port in block.in_vars:
        block.init_eqs.pop(port,None)
    if record.model.upper() == 'MNLEX2':
        signals: tuple[Expr,...] = (machine.out_vars[0]/sym.Const(base_ratio),
            machine.out_vars[1]/sym.Const(base_ratio),machine.in_vars[0])
    else:
        rotor: Block = machine.children[0] if machine.children else machine
        angle: Expr = rotor.state_vars[0]-machine.in_vars[1]
        # Rotate live stator currents, rather than divide P/Q by a possibly
        # collapsed voltage during a fault. Both currents use machine MVA base.
        active: Expr = (machine.out_vars[7]*sym.sin(angle)+machine.out_vars[8]*sym.cos(angle))/sym.Const(base_ratio)
        reactive: Expr = (machine.out_vars[7]*sym.cos(angle)-machine.out_vars[8]*sym.sin(angle))/sym.Const(base_ratio)
        signals = (active,machine.out_vars[3],machine.in_vars[3]) if record.model.upper() == 'MNLEX1' else (active,reactive,machine.in_vars[3])
    for port,signal in zip(block.in_vars,signals):
        template.block.algebraic_vars.append(port)
        template.block.algebraic_eqs.append(port-signal)
        template.block.init_eqs[port] = signal
    template.block.children.append(block)
    return block


def stabilizer_measurement(context: PsseAuxiliaryConverter, machine: Block,
                             selection: PsseStabilizerInput, remote: int | str,
                             base_ratio: float) -> Expr:
    """Resolve one reviewed stabilizer measurement without changing its physical base.

    :param context: Native bus lookup and shared symbol factory.
    :param machine: Network-facing host machine.
    :param selection: Explicit source input selector.
    :param remote: Zero for the terminal or a positive remote bus number.
    :param base_ratio: Machine MVA divided by system MVA.
    :return: Live measurement expression or explicit remote network variable.
    :raises ValueError: Unsupported measurement or missing native AC bus mapping.
    """
    if selection == PsseStabilizerInput.BLOCKED:
        return Const(0.0)
    elif selection == PsseStabilizerInput.ROTOR_SPEED:
        return machine.out_vars[2]-Const(1.0)
    elif selection == PsseStabilizerInput.ELECTRICAL_POWER:
        return machine.out_vars[0]/Const(base_ratio)
    elif selection == PsseStabilizerInput.BUS_VOLTAGE and remote == 0:
        return machine.in_vars[0]
    elif selection == PsseStabilizerInput.BUS_VOLTAGE and isinstance(remote, int):
        remote_bus: Bus | None = context.buses.get(remote, None)
        if remote_bus is None or remote_bus.is_dc:
            raise ValueError('Stabilizer remote voltage requires an existing native AC bus')
        else:
            if remote_bus.rms_model.empty():
                initialize_bus_rms(remote_bus, context.grid.var_factory)
            else:
                pass
            remote_voltage: Var | None = remote_bus.rms_model.external_mapping.get(VarPowerFlowReferenceType.Vm, None)
            if remote_voltage is None:
                raise ValueError('Stabilizer remote bus has no polar RMS voltage mapping')
            else:
                return remote_voltage
    else:
        raise ValueError('Stabilizer input measurement has no reviewed native realization')


def attach_stabilizer(context: PsseAuxiliaryConverter, template: RmsModelTemplate, machine: Block, controller: RmsModelTemplate,
                       record: DyrRecord, vf: VarFactory, base_ratio: float,
                       compensator: Block | None = None) -> Block:
    """Connect a supplementary-voltage controller to live machine measurements.

    :param context: Native bus lookup for explicitly selected remote voltage sensing.
    :param template: Complete host generator assembly.
    :param machine: Network-facing synchronous machine block.
    :param controller: Fresh native stabilizer instance.
    :param record: Source record determining the measured signal.
    :param vf: Shared circuit symbol factory.
    :param base_ratio: Machine MVA divided by system MVA.
    :param compensator: Reviewed compensated-voltage measurement used by supervision.
    :return: Connected block consumed by the exciter attachment.
    """
    block: Block = controller.block
    for port in block.in_vars:
        block.init_eqs.pop(port,None)
    if record.model.upper() in ('IEEEST', 'IEE2ST', 'PSS2A', 'PSS2B', 'PSS2C', 'PSS3B'):
        for index in range(1 if record.model.upper() == 'IEEEST' else 2):
            selection: PsseStabilizerInput = PsseStabilizerInput(record.icons[2*index])
            remote: int | str = record.icons[2*index+1]
            signal: Expr = stabilizer_measurement(context, machine, selection, remote, base_ratio)
            if remote != 0 and isinstance(signal, Var):
                vf.add_network_connection(block.in_vars[index], signal)
            else:
                template.block.algebraic_vars.append(block.in_vars[index])
                template.block.algebraic_eqs.append(block.in_vars[index]-signal)
                template.block.init_eqs[block.in_vars[index]] = signal
        # The application guide defines VCT as compensated voltage, independently
        # of where the stabilizer's selected input signal is measured.
        if record.model.upper() in ('IEEEST','IEE2ST'):
            voltage_port: Var = block.in_vars[-1]
            supervisory_voltage: Var = machine.in_vars[0] if compensator is None else compensator.out_vars[0]
            template.block.algebraic_vars.append(voltage_port)
            template.block.algebraic_eqs.append(voltage_port-supervisory_voltage)
            template.block.init_eqs[voltage_port] = supervisory_voltage
        else:
            pass
    elif record.model.upper() == 'IVOST':
        # The source diagram consumes PELEC directly, without a machine-base conversion.
        vf.add_connection(block.in_vars[0],machine.out_vars[0])
        freeze_named_parameter(block,'InitialElectricalPowerPu_'+controller.name,machine.out_vars[0],vf)
    elif record.model.upper() == 'STAB1':
        vf.add_connection(block.in_vars[0],machine.out_vars[2])
    else:
        connect_scaled(template.block,block.in_vars[0],machine.out_vars[0],1.0/base_ratio,vf)
        if len(block.in_vars) == 2:
            freeze_input(block,block.in_vars[1],vf,machine.out_vars[0]/sym.Const(base_ratio))
        else:
            pass
    template.block.children.append(block)
    return block


def validate_dynamic_parameters(record: DyrRecord) -> None:
    """Reject physical domains or template structural variants that cannot run exactly.

    :param record: Parsed numeric source record.
    :raises ValueError: Unsupported domain/structural variant.
    """
    model: str = dynamic_record_name(record)
    binding: PsseDynamicBinding | None = dynamic_binding(model)
    positive: tuple[str, ...] = ()
    if model in ('IEEEST', 'IEE2ST', 'PSS2A', 'PSS2B', 'PSS2C', 'PSS3B'):
        expected_icons: int = 2 if model == 'IEEEST' else (4 if model in ('IEE2ST','PSS3B') else 6)
        if len(record.icons) != expected_icons:
            raise ValueError('Stabilizer has an incorrect integer signal-selection header')
        else:
            pass
        for index in range(0, 2 if model == 'IEEEST' else 4, 2):
            selection: PsseStabilizerInput = PsseStabilizerInput(record.icons[index])
            if selection == PsseStabilizerInput.BLOCKED and model != 'IEE2ST':
                raise ValueError('Only the dual-input stabilizer documents a disabled input selector')
            elif selection not in (PsseStabilizerInput.BLOCKED, PsseStabilizerInput.ROTOR_SPEED, PsseStabilizerInput.ELECTRICAL_POWER,
                                 PsseStabilizerInput.BUS_VOLTAGE):
                raise ValueError('Stabilizer frequency, accelerating-power and voltage-derivative measurements remain unreviewed')
            elif record.icons[index+1] != 0 and selection != PsseStabilizerInput.BUS_VOLTAGE:
                raise ValueError('Remote bus is not allowed for this stabilizer input')
            else:
                pass
    elif model in ('IVOST','IVOGO'):
        for stage_index in (1,3,5):
            if named_parameter(record,'A'+str(stage_index+1)) == 0 and named_parameter(record,'A'+str(stage_index)) == 0:
                raise ValueError('Source zero-origin rational-stage cancellation requires a reviewed initialization convention')
            elif named_parameter(record,'A'+str(stage_index+1)) == 0 and named_parameter(record,'K'+str(stage_index)) == 0:
                raise ValueError('Source zero-gain free-integral initialization requires separate review')
            elif stage_index != 5 and named_parameter(record,'A'+str(stage_index+1)) == 0 and named_parameter(record,'T'+str(stage_index)) > 0:
                raise ValueError('Source bounded PI degeneration requires a reviewed anti-windup convention')
            else:
                pass
    elif model == 'DC4C':
        positive = ('KPR','KA','TA','TE','VBMAX')
        if len(record.icons) != 4 or any(flag not in (1,2) for flag in record.icons):
            raise ValueError('Compound commutator selectors must each be one or two')
        else:
            pass
    elif model in ('AC4C','DC4B'):
        if len(record.icons) != 2 or any(flag not in (1,2) for flag in record.icons):
            raise ValueError('Exciter OEL/UEL selectors must each be one or two')
        else:
            pass
    elif model == 'GENCLS':
        if named_parameter(record,'H') < 0:
            raise ValueError('Classical machine inertia cannot be negative')
        else:
            pass
    elif model in ('GENROU','GENROE'):
        positive = ('H','Tdo1','Tdo2','Tqo1','Tqo2','Xd','Xq','Xd1','Xq1','Xd2')
    elif model in ('GENSAL','GENSAE'):
        positive = ('H','Tdo1','Tdo2','Tqo2','Xd','Xq','Xd1','Xd2')
    elif model == 'GENTRA':
        positive = ('H','Tdo1','Xd','Xq','Xd1')
        if named_parameter(record,'AF') <= 0:
            raise ValueError('Source network-iteration acceleration factor must be positive')
        else:
            pass
    elif model in ('GGOV1','GGOV1D','GGOV1DU'):
        if len(record.icons) != 2 or record.icons[0] not in (-2,-1,0,1) or record.icons[1] not in (0,1):
            raise ValueError('Unreviewed fuel-governor droop or fuel-characteristic selector')
        elif named_parameter(record,'TENG') != 0 or named_parameter(record,'KA') != 0:
            raise ValueError('Fuel transport delay and time-step acceleration limiting need dedicated native realizations')
        elif min(named_parameter(record,'KPLOAD'),named_parameter(record,'KILOAD'),named_parameter(record,'TFLOAD')) <= 0:
            raise ValueError('Reviewed fuel-load limiting requires positive P/I gains and measurement time')
        elif named_parameter(record,'TRATE') < 0 or named_parameter(record,'ASET') < 0 or named_parameter(record,'TA') < 0:
            raise ValueError('Fuel-governor rating and disabled acceleration settings must be nonnegative')
        elif named_parameter(record,'RUP') <= 0 or named_parameter(record,'RDOWN') >= 0:
            raise ValueError('Source load-limit slew bounds must straddle zero even when the limiter is inactive')
        else:
            pass
    elif model in ('DEGOV','DEGOV1','DEGOV1D','DEGOV1DU'):
        positive = ('T1','T2','K','T5','T6','TD')
        if model != 'DEGOV' and (len(record.icons) != 1 or record.icons[0] not in (0,1)):
            raise ValueError('Engine governor droop control must select throttle or electrical power')
        elif min(named_parameter(record,'T3'),named_parameter(record,'T4')) < 0 or named_parameter(record,'TMAX') <= named_parameter(record,'TMIN'):
            raise ValueError('Engine governor requires nonnegative numerator times and ordered throttle limits')
        elif model in ('DEGOV1D','DEGOV1DU') and (named_parameter(record,'TRATE') < 0 or named_parameter(record,'DBH') < 0 or named_parameter(record,'DBL') > 0):
            raise ValueError('Engine governor rating/deadband signs are invalid')
        elif model != 'DEGOV' and min(named_parameter(record,'DROOP'),named_parameter(record,'TE')) < 0:
            raise ValueError('Engine governor droop and power measurement time must be nonnegative')
        else:
            pass
    elif model == 'LCFB1':
        if len(record.icons) != 2 or record.icons[0] not in (0,1) or record.icons[1] != 1:
            raise ValueError('Reviewed outer load control requires power control enabled and a binary frequency-bias flag')
        else:
            pass
    elif model in ('IEEEG1','IEEEG1D','IEEEG1SDU'):
        single_shaft_header: bool = record.icons == () if model == 'IEEEG1SDU' else len(record.icons) == 2 and record.icons[0] == 0
        if not single_shaft_header or any(named_parameter(record,'K'+str(index)) != 0 for index in (2,4,6,8)):
            raise ValueError('Cross-compound steam governor targets and second-shaft fractions require a reviewed multi-machine assembly')
        elif model in ('IEEEG1D','IEEEG1SDU') and named_parameter(record,'TRATE') < 0:
            raise ValueError('Steam turbine rating must be nonnegative; zero selects machine MBASE')
        else:
            pass
    elif model in ('IEEEG3D','IEEEG3DU'):
        if named_parameter(record,'TRATE') < 0:
            raise ValueError('Hydraulic turbine rating must be nonnegative; zero selects the machine base')
        else:
            pass
    elif model in ('TGOV1','TGOV1D','TGOV1DU'):
        positive = ('R','T1','T3')
    elif model in ('HYGOV','HYGOVD','HYGOVDU'):
        positive = ('R','r','Tr','Tf','Tg','Tw','At')
    elif model == 'IEEEG2':
        positive = ('T3','T4')
        if named_parameter(record,'T1') < 0 or named_parameter(record,'T2') < 0 or named_parameter(record,'K') < 0:
            raise ValueError('Hydro governor gain/filter times must be nonnegative')
        elif named_parameter(record,'PMAX') <= named_parameter(record,'PMIN'):
            raise ValueError('Hydro governor upper power limit must exceed lower limit')
        else:
            pass
    elif model == 'SEXS':
        positive = ('TB','K','TE')
    elif model == 'SCRX':
        positive = ('TB','K')
        if named_parameter(record,'TATB') < 0 or named_parameter(record,'RC_RFD') < 0 or named_parameter(record,'TE') < 0:
            raise ValueError('Static-exciter lead ratio and crowbar resistance must be nonnegative')
        elif named_parameter(record,'CSWITCH') not in (0,1):
            raise ValueError('Static-exciter source switch must be 0 or 1')
        elif named_parameter(record,'EMAX') <= named_parameter(record,'EMIN'):
            raise ValueError('Static-exciter maximum must exceed minimum')
        else:
            pass
    elif model == 'EXST1':
        positive = ('KA',)
        if any(named_parameter(record,name) < 0 for name in ('TR','TB','TA','TF')):
            raise ValueError('EXST1 time constants cannot be negative')
        elif named_parameter(record,'TB') == 0 and named_parameter(record,'TC') != 0:
            raise ValueError('Zero-TB EXST1 needs TC=0 for an exact algebraic lead-lag')
        elif named_parameter(record,'TF') == 0 and named_parameter(record,'KF') != 0:
            raise ValueError('Zero-TF EXST1 needs KF=0 for disabled rate feedback')
        else:
            pass
    elif model == 'ST6C':
        positive = ('KPA','TG','VBMAX')
        if len(record.icons) != 4 or any(flag not in (1,2,3,4) for flag in record.icons[:3]) or record.icons[3] not in (1,2):
            raise ValueError('Current-limited field excitation selectors are invalid')
        else:
            pass
    elif model in ('ST5B','ST5C'):
        positive = ('KR',)
        if model == 'ST5C' and (len(record.icons) != 2 or any(flag not in (1,2) for flag in record.icons)):
            raise ValueError('Selectable parallel excitation requires OEL/UEL selectors one or two')
        else:
            pass
    elif model in ('AC7B','AC7C'):
        positive = ('KE','TE','VFEMAX')
        if model == 'AC7C' and (len(record.icons) != 6 or record.icons[0] not in (1,2,3,4) or any(flag not in (1,2,3) for flag in record.icons[1:3]) or any(flag not in (1,2) for flag in record.icons[3:])):
            raise ValueError('Modern cascaded excitation source/signal selections are invalid')
        else:
            pass
    elif model in ('AC8B','AC8C'):
        positive = ('KA','KE','TE','VFEMAX')
        if model == 'AC8C' and (len(record.icons) != 5 or any(flag not in (1,2,3) for flag in record.icons[:3]) or any(flag not in (1,2) for flag in record.icons[3:])):
            raise ValueError('Compound PID excitation signal/source selectors are invalid')
        else:
            pass
    elif model == 'ST4C':
        positive = ('KPR','TG','VBMAX')
        if len(record.icons) != 5 or record.icons[0] not in (1,2) or any(flag not in (1,2,3) for flag in record.icons[1:4]) or record.icons[4] not in (1,2):
            raise ValueError('Filtered compound excitation signal/source selections are invalid')
        else:
            pass
    elif model == 'ESST3A':
        positive = ('TB','TM','KA')
        if named_parameter(record,'TA') != 0:
            raise ValueError('Native ESST3A template implements the TA=0 structural variant only')
        elif named_parameter(record,'TR') < 0:
            raise ValueError('ESST3A transducer time constant cannot be negative')
        else:
            pass
    elif model in ('EXAC1','EXAC1A','ESAC1A','EXAC2','EXAC3','ESAC2A','ESAC3A','EXBAS','AC1C','AC2C','AC5C'):
        positive = ('TR','TF2','KA','TA','TE','TF1') if model == 'AC5C' else ('TR','TB','KA','TA','TE','TF')
        if model in ('AC1C','AC2C','AC5C') and (len(record.icons) != 2 or any(flag not in (1,2) for flag in record.icons) or named_parameter(record,'VEMIN') != 0 or min(named_parameter(record,'KC'),named_parameter(record,'KD')) <= 0):
            raise ValueError('Reviewed brushless source requires OEL/UEL flags one or two, VEMIN=0 and positive KC/KD')
        else:
            pass
        if model == 'AC5C' and named_parameter(record,'TF3') < 0:
            raise ValueError('Brushless feedback-shaper lead time must be nonnegative')
        else:
            pass
        upper_name: str = 'VAMAX' if model in ('EXAC3','ESAC3A') else 'VRMAX'
        lower_name: str = 'VAMIN' if model in ('EXAC3','ESAC3A') else 'VRMIN'
        if named_parameter(record,upper_name) <= named_parameter(record,lower_name):
            raise ValueError('Exciter upper limit must exceed lower limit')
        elif model in ('ESAC1A','EXAC2','ESAC2A','AC1C','AC2C') and named_parameter(record,'VAMAX') <= named_parameter(record,'VAMIN'):
            raise ValueError('Exciter amplifier upper limit must exceed lower limit')
        elif min(named_parameter(record,'E1'),named_parameter(record,'SE1'),
                 named_parameter(record,'E2'),named_parameter(record,'SE2')) < 0:
            raise ValueError('Exciter saturation samples must be nonnegative')
        elif (named_parameter(record,'SE1') != 0 or named_parameter(record,'SE2') != 0) and (
                named_parameter(record,'E2') <= named_parameter(record,'E1') or
                named_parameter(record,'E2')*named_parameter(record,'SE2') <= named_parameter(record,'E1')*named_parameter(record,'SE1')):
            raise ValueError('Enabled saturation requires increasing voltage and excess-field samples')
        else:
            pass
        if model == 'EXBAS' and (min(named_parameter(record,'KI'),named_parameter(record,'TF2'),named_parameter(record,'KE')) <= 0 or
                min(named_parameter(record,'KP'),named_parameter(record,'TF1'),named_parameter(record,'KF'),named_parameter(record,'VRMIN')) < 0):
            raise ValueError('Reviewed PI brushless excitation requires positive integral/feedback-lag/resistance and nonnegative proportional/feedback/forcing settings')
        else:
            pass
        if model in ('ESAC2A','ESAC3A','AC1C','AC2C','AC5C') and (min(named_parameter(record,'KE'),named_parameter(record,'VFEMAX')) <= 0 or
                min(named_parameter(record,'KD'),named_parameter(record,'KC'),named_parameter(record,'KF')) < 0):
            raise ValueError('Reviewed field-current stops require positive resistance/current ceiling and nonnegative loading/feedback')
        elif model in ('ESAC2A','AC2C') and (named_parameter(record,'KB') <= 0 or named_parameter(record,'KH') < 0):
            raise ValueError('High-response excitation requires positive inner gain and nonnegative direct feedback')
        elif model == 'ESAC3A' and (min(named_parameter(record,'KR'),named_parameter(record,'EFDN')) <= 0 or
                min(named_parameter(record,'KN'),named_parameter(record,'VEMIN')) < 0):
            raise ValueError('Self-excited excitation requires positive supply gain/knee and nonnegative lower voltage/feedback')
        else:
            pass
        if model == 'EXAC2' and (min(named_parameter(record,'KB'),named_parameter(record,'KL'),
                                    named_parameter(record,'VLR')) <= 0 or named_parameter(record,'KH') < 0):
            raise ValueError('High-response excitation requires positive inner/limiter gain and reference, and nonnegative direct feedback')
        else:
            pass
        if model == 'EXAC3' and (min(named_parameter(record,'KR'),named_parameter(record,'EFDN')) <= 0 or
                min(named_parameter(record,'KLV'),named_parameter(record,'KN'),named_parameter(record,'VLV'),named_parameter(record,'KF')) < 0):
            raise ValueError('Self-excited excitation requires positive supply gain/knee and nonnegative feedback/limiter settings')
        else:
            pass
    elif model in ('EXST2','EXST2A','ESST2A','IEEET3','IEEEX3'):
        if named_parameter(record,'KI') == 0 and named_parameter(record,'KP') != 0:
            raise ValueError('Automatic compound current-source gain calibration has not been reviewed')
        else:
            pass
    elif model == 'IEEET4':
        if named_parameter(record,'KR') <= 0 or named_parameter(record,'KV') <= named_parameter(record,'KR'):
            raise ValueError('Reviewed relay reset requires 0 < KR < KV; zero-deadband substitutions are not inferred')
        else:
            pass
    elif binding is not None and binding.dc_kind is not None:
        if binding.dc_kind in (DcExciterKind.BOUNDED_FIXED_SUPPLY,DcExciterKind.BOUNDED_TERMINAL_SUPPLY):
            if len(record.icons) != 2 or any(selection not in (1,2) for selection in record.icons):
                raise ValueError('Bounded rotating excitation requires explicit OEL/UEL flags one or two')
            elif named_parameter(record,'KE') == 0 or named_parameter(record,'VRMAX') <= 0:
                raise ValueError('Bounded rotating exciter automatic coefficient/capability calibration has not been reviewed')
            else:
                pass
        else:
            pass
        reserved_switch: float = next((parameter.value for parameter in record.parameters if parameter.name == 'Switch'),0.0)
        if reserved_switch != 0:
            raise ValueError('Only the documented zero reserved DC-exciter switch is reviewed')
        else:
            pass
    else:
        pass
    if model == 'PSS2C':
        if named_parameter(record,'PSSON') >= 0:
            raise ValueError('Power-dependent stabilizer output hysteresis requires a reviewed discrete controller; PSSON must be negative')
        else:
            pass
    else:
        pass
    if model in ('TGOV1D','TGOV1DU','GASTD','GASTDU','IEESGOD','IEESGODU','HYGOVD','HYGOVDU','HYGOV2D','HYGOV2DU','PIDGOVD','PIDGOVDU'):
        if named_parameter(record,'TRATE') < 0:
            raise ValueError('Turbine rating must be nonnegative; zero selects machine MVA')
        else:
            pass
    else:
        pass
    if model in ('GENROU','GENROE','GENSAL','GENSAE'):
        if named_parameter(record,'Xd1') == named_parameter(record,'Xl'):
            raise ValueError('Transient and leakage reactances must differ')
        elif model in ('GENROU','GENROE') and named_parameter(record,'Xq1') == named_parameter(record,'Xl'):
            raise ValueError('Quadrature transient and leakage reactances must differ')
        elif named_parameter(record,'S10') < 0 or named_parameter(record,'S12') < 0 or (named_parameter(record,'S10') > 0 and named_parameter(record,'S12') <= named_parameter(record,'S10')):
            raise ValueError('Machine saturation points must be nonnegative and increasing')
        elif model in ('GENROE','GENSAE') and (named_parameter(record,'S10') == 0) != (named_parameter(record,'S12') == 0):
            raise ValueError('Power-law saturation needs two positive samples or two zeros')
        else:
            pass
    else:
        pass
    for name in positive:
        if named_parameter(record,name) <= 0:
            raise ValueError('Native '+model+' requires positive '+name+'; algebraic/zero-inertia variants are not substituted')
        else:
            pass


def convert_dynamics(context: PsseAuxiliaryConverter) -> None:
    """Build one connected native RMS model per exact PSS/E machine identity.

    A bad or unsupported controller blocks activation of its machine assembly.
    No partially connected model is installed as if it were ready to simulate.

    :param context: Shared native identity lookups, diagnostics and conversion ledger.
    """
    assignments: dict[tuple[int,str], list[tuple[str,DyrRecord]]] = dict()
    unresolved_buses: set[int] = set()
    unresolved_machines: set[tuple[int,str]] = set()
    rejected_sources: set[str] = set()
    for document in context.source.dyr_files:
        for record in document.records:
            number: int | None = context.bus_number(record.bus)
            binding: PsseDynamicBinding | None = dynamic_binding(dynamic_record_name(record))
            # An unreviewed two-shaft governor must not leave its other named
            # machine running as if that mechanical coupling did not exist.
            if record.model.upper() in ('IEEEG1','IEEEG1D') and record.status == RecordStatus.VALID and len(record.icons) == 2 and isinstance(record.icons[0],int) and record.icons[0] > 0:
                unresolved_machines.add((record.icons[0],str(record.icons[1]).strip()))
                if number is not None:
                    unresolved_machines.add((number,(record.equipment_id or '1').strip()))
                else:
                    pass
            elif (record.user_header is not None and record.user_header.model_type == UserModelType.CROSS_COMPOUND_GOVERNOR
                  and len(record.remote_buses) == 1 and len(record.user_header.references) == 2):
                secondary_number: int | None = context.bus_number(record.remote_buses[0])
                if secondary_number is not None:
                    unresolved_machines.add((secondary_number,str(record.user_header.references[1]).strip()))
                else:
                    pass
                if number is not None:
                    unresolved_machines.add((number,(record.equipment_id or '1').strip()))
                else:
                    pass
            else:
                pass
            if record.status != RecordStatus.VALID or number is None or binding is None:
                context.record(document.source,record.line_number,PsseFileType.DYR,
                    PsseConversionStatus.INVALID if record.status == RecordStatus.INVALID else PsseConversionStatus.UNSUPPORTED,
                    (), 'DYR record has no complete reviewed native model binding: '+record.model)
                if record.target_kind == EquipmentKind.MACHINE and number is not None and record.equipment_id is not None:
                    unresolved_machines.add((number,record.equipment_id.strip()))
                elif isinstance(record.identifier,int):
                    unresolved_buses.add(record.identifier)
                else:
                    pass
            else:
                key: tuple[int,str] = (number,(record.equipment_id or '1').strip())
                assignments.setdefault(key,list()).append((document.source,record))
        for tokens in document.rejected:
            context.record(document.source,0,PsseFileType.DYR,PsseConversionStatus.INVALID,(), 'Malformed DYR record retained in source document')
            if tokens:
                try:
                    rejected_bus: int | None = context.bus_number(BusIdentifier(None,tokens[0].text)) if tokens[0].quoted else int(tokens[0].text)
                except ValueError:
                    rejected_bus = None
                if rejected_bus is not None:
                    unresolved_buses.add(rejected_bus)
                else:
                    rejected_sources.add(document.source)
            else:
                rejected_sources.add(document.source)
    for key, records in assignments.items():
        generator: Generator | None = context.generators.get(key,None)
        raw: RawGeneratorLike | None = context.raw_generators.get(key,None)
        roles: dict[PsseDynamicRole,list[tuple[str,DyrRecord]]] = dict()
        for source, record in records:
            binding = dynamic_binding(dynamic_record_name(record))
            if binding is not None:
                roles.setdefault(binding.role,list()).append((source,record))
            else:
                pass
        machines: list[tuple[str,DyrRecord]] = roles.get(PsseDynamicRole.MACHINE,list())
        complete: bool = generator is not None and raw is not None and raw.MBASE > 0 and not raw.XT and context.grid.Sbase > 0 and len(machines) == 1 and key[0] not in unresolved_buses and key not in unresolved_machines and all(len(items)==1 for items in roles.values()) and all(source not in rejected_sources for source, _ in records)
        if not complete:
            for source, record in records:
                context.record(source,record.line_number,PsseFileType.DYR,PsseConversionStatus.UNRESOLVED,(), 'DYR assembly has missing/ambiguous host, competing models, unsupported neighboring records, or invalid MBASE')
        else:
            source, record = machines[0]
            vf: VarFactory = context.grid.var_factory
            ratio: float = raw.MBASE/context.grid.Sbase
            name: str = 'PSSE_'+str(key[0])+'_'+key[1]+'_'+record.model.upper()
            assignment_attempted: bool = False
            original_runtime: Block = generator.rms_model
            try:
                for _, candidate in records:
                    validate_dynamic_parameters(candidate)
                model: str = dynamic_record_name(record)
                template: RmsModelTemplate
                if model == 'GENCLS':
                    governor_records: list[tuple[str,DyrRecord]] = roles.get(PsseDynamicRole.GOVERNOR,list())
                    tgov: bool = bool(governor_records) and governor_records[0][1].model.upper() == 'TGOV1'
                    if governor_records and not tgov:
                        raise ValueError('GENCLS currently supports only the TGOV1 governor assembly')
                    else:
                        pass
                    template = get_complete_gencls_rms_template(vf, GenclsMechanicalInput.TGOV1 if tgov else GenclsMechanicalInput.CONSTANT, name)
                    configure_gencls_block(template.block.children[0], GenclsRmsParameters(context.grid.fBase,
                        named_parameter(record,'D')*ratio,2*named_parameter(record,'H')*ratio,
                        raw.ZR/ratio,raw.ZX/ratio),vf)
                elif model in ('GENROU','GENROE'):
                    saturation: GenrouSaturationMode
                    if named_parameter(record,'S10') == 0 and named_parameter(record,'S12') == 0:
                        saturation = GenrouSaturationMode.DISABLED
                    elif model == 'GENROE':
                        saturation = GenrouSaturationMode.POWER_LAW
                    else:
                        saturation = GenrouSaturationMode.QUADRATIC
                    template = get_genrou_rms_template(vf,name,saturation)
                    configure_genrou_block(template.block.children[0],GenrouRmsParameters(context.grid.fBase,
                        named_parameter(record,'D')*ratio,2*named_parameter(record,'H')*ratio,raw.ZR/ratio,
                        named_parameter(record,'Xl')/ratio,named_parameter(record,'Xd1')/ratio,
                        named_parameter(record,'S10'),named_parameter(record,'S12'),named_parameter(record,'Xd')/ratio,
                        named_parameter(record,'Xq')/ratio,named_parameter(record,'Xd2')/ratio,named_parameter(record,'Xq1')/ratio,
                        named_parameter(record,'Xd2')/ratio,named_parameter(record,'Tdo1'),named_parameter(record,'Tdo2'),
                        named_parameter(record,'Tqo1'),named_parameter(record,'Tqo2')),vf)
                elif model == 'GENSAE':
                    template = build_gensae_template(vf,name,frequency=context.grid.fBase,
                        damping=named_parameter(record,'D')*ratio, inertia=2*named_parameter(record,'H')*ratio,
                        resistance=raw.ZR/ratio, leakage=named_parameter(record,'Xl')/ratio,
                        xd_transient=named_parameter(record,'Xd1')/ratio,
                        saturation1=named_parameter(record,'S10'), saturation12=named_parameter(record,'S12'),
                        xd=named_parameter(record,'Xd')/ratio, xq=named_parameter(record,'Xq')/ratio,
                        x_subtransient=named_parameter(record,'Xd2')/ratio,
                        td_transient=named_parameter(record,'Tdo1'), td_subtransient=named_parameter(record,'Tdo2'),
                        tq_subtransient=named_parameter(record,'Tqo2'))
                elif model == 'GENTRA':
                    # AF relaxes the source network iteration; the native coupled DAE
                    # has no corresponding physical parameter to alter.
                    template = build_gentra_template(vf,name,context.grid.fBase,
                        named_parameter(record,'H')*ratio,named_parameter(record,'D')*ratio,
                        raw.ZR/ratio,named_parameter(record,'Xd')/ratio,
                        named_parameter(record,'Xq')/ratio,named_parameter(record,'Xd1')/ratio,
                        named_parameter(record,'Tdo1'),named_parameter(record,'S10'),named_parameter(record,'S12'))
                else:
                    template = build_gensal_network(vf,record,name,ratio,raw.ZR,context.grid.fBase)
                machine: Block = template.block.children[0]
                compensator_records: list[tuple[str,DyrRecord]] = roles.get(PsseDynamicRole.COMPENSATOR,list())
                compensator_block: Block | None = None
                if compensator_records:
                    if model == 'GENCLS' or not roles.get(PsseDynamicRole.EXCITER,list()):
                        raise ValueError('Voltage compensation requires a machine with an explicit exciter')
                    else:
                        compensator_record: DyrRecord = compensator_records[0][1]
                        compensator_binding: PsseDynamicBinding | None = dynamic_binding(compensator_record.model)
                        if compensator_binding is not None:
                            compensator_template: RmsModelTemplate = build_controller(compensator_record,compensator_binding,vf,
                                name+'_'+compensator_record.model.upper(),ratio)
                            compensator_block = attach_compensator(context,template,machine,compensator_template,compensator_record,ratio)
                        else:
                            raise ValueError('Voltage compensator binding disappeared')
                else:
                    pass
                stabilizer_records: list[tuple[str,DyrRecord]] = roles.get(PsseDynamicRole.STABILIZER,list())
                stabilizer_block: Block | None = None
                if stabilizer_records:
                    if model == 'GENCLS' or not roles.get(PsseDynamicRole.EXCITER,list()):
                        raise ValueError('Supplementary voltage control requires a machine with an explicit exciter')
                    else:
                        stabilizer_record: DyrRecord = stabilizer_records[0][1]
                        stabilizer_binding: PsseDynamicBinding | None = dynamic_binding(stabilizer_record.model)
                        if stabilizer_binding is not None:
                            stabilizer_template: RmsModelTemplate = build_controller(stabilizer_record,stabilizer_binding,vf,
                                name+'_'+stabilizer_record.model.upper(),ratio)
                            stabilizer_block = attach_stabilizer(context,template,machine,stabilizer_template,stabilizer_record,vf,ratio,compensator_block)
                        else:
                            raise ValueError('Stabilizer binding disappeared')
                else:
                    pass
                underexcitation_records: list[tuple[str,DyrRecord]] = roles.get(PsseDynamicRole.UNDEREXCITATION,list())
                underexcitation_block: Block | None = None
                if underexcitation_records:
                    if model == 'GENCLS' or not roles.get(PsseDynamicRole.EXCITER,list()):
                        raise ValueError('Minimum-excitation limiting requires a machine with an explicit exciter')
                    else:
                        underexcitation_record: DyrRecord = underexcitation_records[0][1]
                        underexcitation_binding: PsseDynamicBinding | None = dynamic_binding(underexcitation_record.model)
                        if underexcitation_binding is not None:
                            underexcitation_template: RmsModelTemplate = build_controller(underexcitation_record,underexcitation_binding,vf,
                                name+'_'+underexcitation_record.model.upper(),ratio)
                            underexcitation_block = attach_underexcitation(template,machine,underexcitation_template,underexcitation_record,ratio)
                        else:
                            raise ValueError('Minimum-excitation binding disappeared')
                else:
                    pass
                # GENCLS's optional governor was precomposed; configure it exactly once.
                load_records: list[tuple[str,DyrRecord]] = roles.get(PsseDynamicRole.TURBINE_LOAD_CONTROLLER,list())
                load_block: Block | None = None
                if load_records:
                    governed: list[tuple[str,DyrRecord]] = roles.get(PsseDynamicRole.GOVERNOR,list())
                    if model == 'GENCLS' or len(governed) != 1 or governed[0][1].model.upper() != 'IEEEG1':
                        raise ValueError('Reviewed outer load control currently requires a field-dynamic machine and a single-shaft IEEEG1 governor')
                    else:
                        load_record: DyrRecord = load_records[0][1]
                        load_binding: PsseDynamicBinding | None = dynamic_binding(load_record.model)
                        if load_binding is None:
                            raise ValueError('Turbine load-controller binding disappeared')
                        else:
                            load_template: RmsModelTemplate = build_controller(load_record,load_binding,vf,name+'_LCFB1',ratio)
                            load_block = load_template.block
                            for port in load_block.in_vars:
                                load_block.init_eqs.pop(port,None)
                            vf.add_connection(load_block.in_vars[0],machine.out_vars[2])
                            connect_scaled(template.block,load_block.in_vars[1],machine.out_vars[0],1.0/ratio,vf)
                            freeze_input(load_block,load_block.in_vars[3],vf,machine.out_vars[0]/Const(ratio))
                            template.block.children.append(load_block)
                else:
                    pass
                for role in (PsseDynamicRole.GOVERNOR,PsseDynamicRole.EXCITER):
                    controllers: list[tuple[str,DyrRecord]] = roles.get(role,list())
                    if controllers:
                        controller_record: DyrRecord = controllers[0][1]
                        binding = dynamic_binding(dynamic_record_name(controller_record))
                        if model == 'GENCLS' and role == PsseDynamicRole.EXCITER:
                            raise ValueError('GENCLS has a constant internal emf and cannot host an exciter')
                        else:
                            pass
                        if model == 'GENCLS' and controller_record.model.upper() == 'TGOV1':
                            governor: Block = template.block.children[1]
                            configure_tgov1_block(governor,Tgov1RmsParameters(1.0,named_parameter(controller_record,'R')/ratio,
                                named_parameter(controller_record,'VMAX')*ratio,named_parameter(controller_record,'VMIN')*ratio,
                                named_parameter(controller_record,'T1'),named_parameter(controller_record,'T2'),named_parameter(controller_record,'T3'),named_parameter(controller_record,'Dt')*ratio),vf)
                        elif binding is not None:
                            controller: RmsModelTemplate = build_controller(controller_record,binding,vf,name+'_'+dynamic_record_name(controller_record),ratio)
                            attach_controller(template,machine,controller,controller_record,vf,ratio,context.grid.Sbase,stabilizer_block,compensator_block,underexcitation_block,load_block)
                        else:
                            raise ValueError('Controller binding disappeared')
                    elif model != 'GENCLS':
                        port: Var = machine.in_vars[2] if role == PsseDynamicRole.GOVERNOR else machine.in_vars[3]
                        freeze_input(machine,port,vf)
                    else:
                        pass
                # No implicit replacement of a pre-existing user/native dynamic model.
                if generator.rms_template is not None or generator.rms_fmu_template is not None:
                    raise ValueError('Generator already has an RMS model assignment')
                else:
                    pass
                assignment_attempted = True
                generator.rms_template = template
                context.grid.add_rms_model(template)
                for source, applied in records:
                    context.record(source,applied.line_number,PsseFileType.DYR,PsseConversionStatus.CONVERTED,
                        (generator,template),'Applied '+applied.model+' through a parameterized native RMS assembly')
            except (ValueError,KeyError,IndexError) as error:
                if assignment_attempted:
                    generator.rms_template = None
                    generator.rms_model = original_runtime
                else:
                    pass
                for source, failed in records:
                    context.record(source,failed.line_number,PsseFileType.DYR,PsseConversionStatus.UNSUPPORTED,
                        (generator,),'DYR assembly not activated: '+str(error))
