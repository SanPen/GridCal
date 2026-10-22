# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import re
from enum import Enum
from typing import Dict, List

from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.winding import Winding
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagramNode
from VeraGridEngine.enumerations import (
    BlockType,
    ConverterControlType,
    EmtFaultPlacementSide,
    FaultType,
    JMartiDataSourceMode,
    ShuntConnectionType,
    TheveninSourceVoltageMode,
    VarPowerFlowReferenceType,
    WindingType,
)
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block, rehash_block_tree_var_keyed_dicts
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Templates.BasicBlockCatalog as basic_block_templates
import VeraGridEngine.Templates as tem
import VeraGridEngine.Templates.Emt as emt_templates
import VeraGridEngine.Templates.Rms as rms_templates
from VeraGridEngine.Templates.Rms.dc_line_rms_template_v2 import DcLineRmsTemplateV2
from VeraGridEngine.Templates.Rms.hvdc_vsc_gfl_rms_template_v2 import (
    HvdcVscGflRmsTemplate,
    VscActiveControlRmsTemplate,
    VscReactiveControlRmsTemplate,
)
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_options import JMartiFitOptions


class GenericBlockTemplateDefinition(TemplateDefinition):
    """GUI-only builder for the configurable generic symbolic block."""

    __slots__ = ()

    def __init__(self, var_factory: VarFactory) -> None:
        """Create the default one-input/one-output generic definition.

        :param var_factory: Editor variable factory.
        :return: None.
        """
        super().__init__(
            var_factory,
            list((TemplateProp("inputs", "", "Number of input ports.", int, 1), TemplateProp("outputs", "", "Number of output ports.", int, 1), TemplateProp("name", "", "Generated block name.", str, "generic"),)),
        )

    def eval(self) -> Block:
        """
        Build a generic block from the current structural values.

        :return: Generic block built from the current structural values.
        """
        inputs: int = int(self.get_value("inputs"))
        outputs: int = int(self.get_value("outputs"))
        name: str = str(self.get_value("name"))
        if inputs < 1 or outputs < 1:
            raise ValueError("Generic blocks require at least one input and one output")
        else:
            return create_generic_block(self.vf, inputs, outputs, name)


class RlcComboBlockTemplateDefinition(TemplateDefinition):
    """GUI-only definition for the combined EMT RLC shunt block."""

    __slots__ = ()

    def __init__(self, var_factory: VarFactory) -> None:
        """Create a complete grounded three-phase RLC default.

        :param var_factory: Editor variable factory.
        :return: None.
        """
        super().__init__(
            var_factory,
            list((TemplateProp("include_r", "", "Include the resistive branch.", bool, True), TemplateProp("include_l", "", "Include the inductive branch.", bool, True), TemplateProp("include_c", "", "Include the capacitive branch.", bool, True), TemplateProp("phA", "", "Include phase A.", bool, True), TemplateProp("phB", "", "Include phase B.", bool, True), TemplateProp("phC", "", "Include phase C.", bool, True), TemplateProp(
                    "connection_type",
                    "",
                    "Electrical shunt connection.",
                    ShuntConnectionType,
                    ShuntConnectionType.GroundedStar,
                ), TemplateProp("direct_r_value", "ohm", "Default resistance.", float, 1.0), TemplateProp("direct_l_value", "H", "Default inductance.", float, 1.0e-3), TemplateProp("direct_c_value", "F", "Default capacitance.", float, 1.0e-6), TemplateProp("name", "", "Generated block name.", str, "RLC_combo_emt"),)),
        )

    def eval(self) -> EmtModelTemplate:
        """Build the combined RLC template from current options.

        :return: Configured EMT RLC model template.
        """
        return emt_templates.get_shunt_rlc_combo_emt_template(
            vf=self.vf,
            include_r=bool(self.get_value("include_r")),
            include_l=bool(self.get_value("include_l")),
            include_c=bool(self.get_value("include_c")),
            phA=bool(self.get_value("phA")),
            phB=bool(self.get_value("phB")),
            phC=bool(self.get_value("phC")),
            connection_type=self.get_value("connection_type"),
            direct_r_value=float(self.get_value("direct_r_value")),
            direct_l_value=float(self.get_value("direct_l_value")),
            direct_c_value=float(self.get_value("direct_c_value")),
            name=str(self.get_value("name")),
        )


class JMartiBlockTemplateDefinition(TemplateDefinition):
    """GUI builder exposing the complete former JMarti-dialog configuration."""

    __slots__ = ()

    def __init__(self, var_factory: VarFactory) -> None:
        """Create one ABC JMarti definition with complete fitting defaults.

        :param var_factory: Editor variable factory.
        :return: None.
        """
        options: JMartiFitOptions = JMartiFitOptions()
        properties: List[TemplateProp] = list((TemplateProp("phN", "", "Include neutral conductor N.", bool, False), TemplateProp("phA", "", "Include phase A.", bool, True), TemplateProp("phB", "", "Include phase B.", bool, True), TemplateProp("phC", "", "Include phase C.", bool, True), TemplateProp("data_source_mode", "", "Frequency-data source.", JMartiDataSourceMode,
                         JMartiDataSourceMode.AUTOMATIC_TEMPLATE), TemplateProp("nominal_frequency_hz", "Hz", "Nominal source frequency.", float, 50.0), TemplateProp("import_file_path", "", "NPZ frequency-sample file.", str, ""), TemplateProp("import_line_length_m", "m", "Fallback imported line length.", float, 0.0), TemplateProp("sweep_low_hz", "Hz", "Automatic sweep lower frequency.", float, 10.0), TemplateProp("sweep_high_hz", "Hz", "Automatic sweep upper frequency.", float, 10000.0), TemplateProp("sweep_sample_count", "", "Automatic sweep sample count.", int, 48), TemplateProp("reference_frequency_hz", "Hz", "Modal-basis reference frequency.", float,
                         float(options.reference_frequency_hz)), TemplateProp("use_frequency_exploration_window", "", "Restrict the fitting band.", bool,
                         bool(options.use_frequency_exploration_window)), TemplateProp("exploration_low_hz", "Hz", "Fitting-band lower frequency.", float,
                         float(options.exploration_low_hz)), TemplateProp("exploration_high_hz", "Hz", "Fitting-band upper frequency.", float,
                         float(options.exploration_high_hz)), TemplateProp("use_delay_fit_window", "", "Restrict the delay-fit band.", bool,
                         bool(options.use_delay_fit_window)), TemplateProp("delay_fit_low_hz", "Hz", "Delay-fit lower frequency.", float,
                         float(options.delay_fit_low_hz)), TemplateProp("delay_fit_high_hz", "Hz", "Delay-fit upper frequency.", float,
                         float(options.delay_fit_high_hz)), TemplateProp("decoupling_warning_tolerance", "", "Modal decoupling warning tolerance.", float,
                         float(options.decoupling_warning_tolerance)), TemplateProp("loewner_relative_tolerance", "", "Loewner order tolerance.", float,
                         float(options.loewner_relative_tolerance)), TemplateProp("maximum_model_order", "", "Maximum rational model order.", int,
                         int(options.maximum_model_order)), TemplateProp("forced_model_order", "", "Forced order; zero selects automatic order.", int,
                         int(options.forced_model_order)), TemplateProp("minimum_frequency_samples", "", "Minimum fitting samples.", int,
                         int(options.minimum_frequency_samples)), TemplateProp("vf_max_iterations", "", "Vector-fitting iteration limit.", int,
                         int(options.vf_max_iterations)), TemplateProp("vf_pole_shift_tolerance", "", "Vector-fitting pole-shift tolerance.", float,
                         float(options.vf_pole_shift_tolerance)), TemplateProp("vf_enforce_stable_poles", "", "Reflect unstable fitted poles.", bool,
                         bool(options.vf_enforce_stable_poles)), TemplateProp("vf_stability_real_part_floor", "", "Stable-pole real-part floor.", float,
                         float(options.vf_stability_real_part_floor)), TemplateProp("vf_include_constant_term", "", "Include the rational constant term.", bool,
                         bool(options.vf_include_constant_term)), TemplateProp("vf_include_proportional_term", "", "Include the proportional s term.", bool,
                         bool(options.vf_include_proportional_term)), TemplateProp("passivity_frequency_sample_count", "", "Passivity-check sample count.", int,
                         int(options.passivity_frequency_sample_count)), TemplateProp("passivity_minimum_real_yc_tolerance", "", "Allowed Re(Yc) negativity.", float,
                         float(options.passivity_minimum_real_yc_tolerance)), TemplateProp("passivity_maximum_hres_gain_tolerance", "", "Allowed |Hres| gain slack.", float,
                         float(options.passivity_maximum_hres_gain_tolerance)), TemplateProp("name", "", "Generated block name.", str, "J_Marti"),))
        TemplateDefinition.__init__(self, var_factory, properties)

    def eval(self) -> EmtModelTemplate:
        """Build the symbolic shell and retain the complete GUI configuration.

        :return: JMarti EMT template with serializable editor metadata.
        """
        template: EmtModelTemplate = emt_templates.get_jmarti_line_emt_template(
            vf=self.vf,
            phN=bool(self.get_value("phN")),
            phA=bool(self.get_value("phA")),
            phB=bool(self.get_value("phB")),
            phC=bool(self.get_value("phC")),
            name=str(self.get_value("name")),
        )
        configuration: Dict[str, object] = dict()
        prop: TemplateProp
        for prop in self.params:
            if prop.name != "name":
                if isinstance(prop.value, Enum):
                    configuration[prop.name] = prop.value.name
                else:
                    configuration[prop.name] = prop.value
            else:
                pass
        template.block.modal_template_kind = "jmarti_line_emt"
        template.block.modal_template_config = configuration
        return template


def get_blocktype2template_builder_dict() -> Dict[BlockType, type[TemplateDefinition]]:
    """
    Return the native block types constructed through template definitions. Only the ones that need more input info
    apart from VarFactory and name

    :return: Builder class lookup used by drop and properties workflows.
    """
    return dict(((BlockType.MIN, basic_block_templates.MinimumTemplate),
                 (BlockType.MAX, basic_block_templates.MaximumTemplate),
                 (BlockType.INTEGRATOR, basic_block_templates.IntegratorTemplate),
                 (BlockType.STARTUP_FREEZE_INTEGRATOR,
                  basic_block_templates.StartupFreezeIntegratorTemplate),
                 (BlockType.DERIVATIVE, basic_block_templates.DerivativeTemplate),
                 (BlockType.FAULT_EMT, emt_templates.FaultEmtTemplate),
                 (BlockType.EMT_THEVENIN, emt_templates.TheveninSourceEmtTemplate),
                 (BlockType.SWITCH_EMT, emt_templates.SwitchEmtTemplate),
                 (BlockType.GROUNDING_LINK_EMT, emt_templates.GroundingLinkEmtTemplate),
                 (BlockType.INDUCTION_MOTOR_EMT, emt_templates.InductionMotorEmtTemplate),
                 (BlockType.R_LOAD_EMT, emt_templates.ShuntRComboEmtTemplate),
                 (BlockType.L_LOAD_EMT, emt_templates.ShuntLComboEmtTemplate),
                 (BlockType.C_LOAD_EMT, emt_templates.ShuntCComboEmtTemplate),
                 (BlockType.VOLTAGE_SOURCE_EMT, emt_templates.VoltageSourceEmtTemplate),
                 (BlockType.CURRENT_SOURCE_EMT, emt_templates.CurrentSourceEmtTemplate),
                 (BlockType.CONTROLLED_VOLTAGE_SOURCE_EMT, emt_templates.ControlledVoltageSourceEmtTemplate),
                 (BlockType.CONTROLLED_CURRENT_SOURCE_EMT, emt_templates.ControlledCurrentSourceEmtTemplate),
                 (BlockType.ARBITRARY_WAVEFORM_VOLTAGE_SOURCE_EMT, emt_templates.ArbitraryWaveformVoltageSourceEmtTemplate),
                 (BlockType.ARBITRARY_WAVEFORM_CURRENT_SOURCE_EMT, emt_templates.ArbitraryWaveformCurrentSourceEmtTemplate),
                 (BlockType.NONLINEAR_RESISTOR_EMT, emt_templates.NonLinearResistorEmtTemplate),
                 (BlockType.STEP_VOLTAGE_SOURCE_EMT, emt_templates.StepVoltageSourceEmtTemplate),
                 (BlockType.STEP_CURRENT_SOURCE_EMT, emt_templates.StepCurrentSourceEmtTemplate),
                 (BlockType.RAMP_VOLTAGE_SOURCE_EMT, emt_templates.RampVoltageSourceEmtTemplate),
                 (BlockType.RAMP_CURRENT_SOURCE_EMT, emt_templates.RampCurrentSourceEmtTemplate),
                 (BlockType.DOUBLE_EXPONENTIAL_CURRENT_SOURCE_EMT, emt_templates.DoubleExponentialCurrentSourceEmtTemplate),
                 (BlockType.HEIDLER_CURRENT_SOURCE_EMT, emt_templates.HeidlerCurrentSourceEmtTemplate),
                 (BlockType.CIGRE_SURGE_CURRENT_SOURCE_EMT, emt_templates.CigreSurgeCurrentSourceEmtTemplate),
                 (BlockType.EXP_LOAD_EMT, emt_templates.ExponentialLoadEmtTemplate),
                 (BlockType.ZIP_LOAD_EMT, emt_templates.LoadZIPEmtTemplate),
                 (BlockType.TRAFO_EMT, emt_templates.TransformerEmtTemplate),
                 (BlockType.XFMR_TRANSFORMER, emt_templates.XfmrEmtTemplate),
                 (BlockType.EMT_PI_LINE, emt_templates.PiLineEmtTemplate),
                 (BlockType.EMT_BERGERON_LINE, emt_templates.BergeronLineEmtTemplate),
                 (BlockType.EMT_JMARTI_LINE, JMartiBlockTemplateDefinition),
                 (BlockType.INVERSE_LOOKUP_ARRAY, emt_templates.InverseLookupArrayLinearRuntimeTemplate),
                 (BlockType.LOOKUP_ARRAY_LINEAR, emt_templates.LookupArrayLinearRuntimeTemplate),
                 (BlockType.LOOKUP_ARRAY_LINEAR_VARIABLE, emt_templates.LookupArrayLinearVariableRuntimeTemplate),
                 (BlockType.LOOKUP_ARRAY_SPLINE, emt_templates.LookupArraySplineRuntimeTemplate),
                 (BlockType.LOOKUP_MATRIX_LINEAR, emt_templates.LookupMatrixLinearRuntimeTemplate),
                 (BlockType.LOOKUP_MATRIX_SPLINE, emt_templates.LookupMatrixSplineRuntimeTemplate),
                 (BlockType.GFL_VSC_HVDC_RMS, HvdcVscGflRmsTemplate),
                 (BlockType.VSC_ACTIVE_CONTROL_RMS, VscActiveControlRmsTemplate),
                 (BlockType.VSC_REACTIVE_CONTROL_RMS, VscReactiveControlRmsTemplate),
                 (BlockType.DC_LINE_RMS, DcLineRmsTemplateV2),))


def create_default_template_builder(var_factory: VarFactory,
                                    block_type: BlockType,
                                    item_name: str,
                                    api_object: ALL_DEV_TYPES | None = None) -> TemplateDefinition | None:
    """Create one template builder with a complete deterministic default setup.

    Existing template definitions already own almost every default. Only the
    few builders whose contract intentionally requires a GUI choice are filled
    here. This gives drag-and-drop a valid result without opening the legacy
    creation dialogue.

    :param var_factory: Live editor variable factory.
    :param block_type: Native library block type.
    :param item_name: Generated diagram item name.
    :param api_object: Optional transformer-like device supplying winding data.
    :return: Configured builder or ``None`` for non-builder block types.
    """
    builder_classes: Dict[BlockType, type[TemplateDefinition]] = get_blocktype2template_builder_dict()
    builder_class: type[TemplateDefinition] | None = builder_classes.get(block_type, None)
    if builder_class is None:
        return None
    else:
        builder: TemplateDefinition = builder_class(var_factory)

    _unused_item_name: str = item_name

    # Every phase-selective library block opens with the same predictable
    # three-wire AC topology. Neutral stays disabled because it must be an
    # explicit modelling choice, while A, B and C are all enabled by default.
    default_phase_values: tuple[tuple[str, bool], ...] = (
        ("phN", False),
        ("phA", True),
        ("phB", True),
        ("phC", True),
    )
    phase_property_name: str
    phase_default_value: bool
    for phase_property_name, phase_default_value in default_phase_values:
        phase_property: TemplateProp | None = builder.params_dict.get(phase_property_name, None)
        if phase_property is not None:
            phase_property.value = phase_default_value
        else:
            pass

    if block_type == BlockType.FAULT_EMT:
        fault_type_property: TemplateProp | None = builder.params_dict.get("fault_type", None)
        placement_property: TemplateProp | None = builder.params_dict.get("placement_side", None)
        if fault_type_property is not None:
            # The fault topology must agree with the common ABC phase mask.
            # LLL is the three-wire choice; grounded LLLG would introduce a
            # ground path that the default phase policy intentionally avoids.
            fault_type_property.value = FaultType.LLL
        else:
            pass
        if placement_property is not None:
            placement_property.value = EmtFaultPlacementSide.FromSide
        else:
            pass
    elif block_type == BlockType.GROUNDING_LINK_EMT:
        include_r_property: TemplateProp | None = builder.params_dict.get("include_r", None)
        resistance_property: TemplateProp | None = builder.params_dict.get("direct_r_value", None)
        if include_r_property is not None:
            include_r_property.value = True
        else:
            pass
        if resistance_property is not None:
            resistance_property.value = 1.0
        else:
            pass
    elif block_type == BlockType.TRAFO_EMT or block_type == BlockType.XFMR_TRANSFORMER:
        connection_from: WindingType | None
        connection_to: WindingType | None
        if isinstance(api_object, (Transformer2W, Winding)):
            connection_from, connection_to = _get_transformer_connection_types(api_object)
        else:
            connection_from, connection_to = None, None
        if connection_from is None:
            connection_from = WindingType.GroundedStar
        else:
            pass
        if connection_to is None:
            connection_to = WindingType.GroundedStar
        else:
            pass
        connection_from_property: TemplateProp | None = builder.params_dict.get("conn_f", None)
        connection_to_property: TemplateProp | None = builder.params_dict.get("conn_t", None)
        if connection_from_property is not None:
            connection_from_property.value = connection_from
        else:
            pass
        if connection_to_property is not None:
            connection_to_property.value = connection_to
        else:
            pass
    elif block_type == BlockType.INVERSE_LOOKUP_ARRAY:
        points_property: TemplateProp | None = builder.params_dict.get("points", None)
        if points_property is not None:
            points_property.value = ((0.0, 0.0), (1.0, 1.0), (2.0, 2.0))
        else:
            pass
    else:
        pass

    return builder


def create_structural_template_builder(var_factory: VarFactory,
                                       block_type: BlockType,
                                       item_name: str,
                                       api_object: ALL_DEV_TYPES | None = None) -> TemplateDefinition | None:
    """Create any native structural builder used by the properties modal.

    :param var_factory: Factory receiving variables if the builder evaluates.
    :param block_type: Native block type.
    :param item_name: Existing or generated block name.
    :param api_object: Optional device used for transformer defaults.
    :return: Configured builder or ``None`` when reconstruction is unsupported.
    """
    if block_type == BlockType.GENERIC:
        builder: TemplateDefinition | None = GenericBlockTemplateDefinition(var_factory)
    elif block_type == BlockType.RLC_COMBO_EMT:
        builder = RlcComboBlockTemplateDefinition(var_factory)
    elif block_type == BlockType.SUM:
        builder = basic_block_templates.AdderTemplate(vf=var_factory)
    elif block_type == BlockType.PRODUCT:
        builder = basic_block_templates.ProductTemplate(vf=var_factory)
    else:
        builder = create_default_template_builder(
            var_factory=var_factory,
            block_type=block_type,
            item_name=item_name,
            api_object=api_object,
        )
    return builder


def copy_template_builder_values(source: TemplateDefinition,
                                 target: TemplateDefinition) -> None:
    """Copy typed builder inputs by name into an independent preflight builder.

    :param source: Modal draft builder.
    :param target: Fresh builder using an isolated VarFactory.
    :return: None.
    """
    source_property: TemplateProp
    for source_property in source.params:
        target_property: TemplateProp | None = target.params_dict.get(source_property.name, None)
        if target_property is not None:
            target_property.value = source_property.value
        else:
            pass


def _get_fault_type_from_block_structure(block: Block) -> FaultType | None:
    """Infer one persisted fault topology from its distinctive algebraic variables.

    The symbolic variable names are part of the saved model, unlike arbitrary
    Python attributes. They therefore provide a backwards-compatible recovery
    path for files saved before explicit modal metadata existed.

    :param block: Existing EMT fault block.
    :return: Inferred fault topology, or ``None`` for an unknown structure.
    """
    algebraic_names: set[str] = set(variable.name for variable in block.algebraic_vars)
    active_phase_count: int = 0
    phase_name: str
    for phase_name in ("A", "B", "C"):
        if block_has_phase_port(block=block, phase_name=phase_name):
            active_phase_count += 1
        else:
            pass

    has_ground_branch_current: bool = False
    has_common_node_current: bool = False
    has_phase_pair_current: bool = False
    algebraic_name: str
    for algebraic_name in algebraic_names:
        if re.search(r"^i_fault_[ABC]G(?:_|$)", algebraic_name) is not None:
            has_ground_branch_current = True
        elif re.search(r"^i_fault_[ABC]N(?:_|$)", algebraic_name) is not None:
            has_common_node_current = True
        elif re.search(r"^i_fault_[ABC][ABC](?:_|$)", algebraic_name) is not None:
            has_phase_pair_current = True
        else:
            pass

    if has_ground_branch_current and active_phase_count == 1:
        return FaultType.LG
    elif has_ground_branch_current and active_phase_count == 3:
        return FaultType.LLLG
    elif has_common_node_current and active_phase_count == 2:
        return FaultType.LLG
    elif has_common_node_current and active_phase_count == 3:
        return FaultType.LLL
    elif has_phase_pair_current and active_phase_count == 2:
        return FaultType.LL
    else:
        return None


def _get_fault_placement_from_block_structure(block: Block) -> EmtFaultPlacementSide | None:
    """Recover the semantic branch side encoded in persisted phase-node names.

    :param block: Existing EMT fault block.
    :return: Recovered placement side, or ``None`` when no marker remains.
    """
    child_block: Block
    for child_block in block.children:
        if child_block.name.startswith("From Phase "):
            return EmtFaultPlacementSide.FromSide
        elif child_block.name.startswith("To Phase "):
            return EmtFaultPlacementSide.ToSide
        else:
            pass
    return None


def _get_fault_constant(block: Block,
                        variable_name: str,
                        is_mode: bool) -> float | None:
    """Read one numeric fault constant from a persisted symbolic assignment.

    :param block: Existing EMT fault block.
    :param variable_name: Exact symbolic parameter name.
    :param is_mode: Whether to inspect the mode dictionary instead of events.
    :return: Numeric value, or ``None`` when the assignment is absent or invalid.
    """
    assignments: Dict[Var, Expr]
    if is_mode:
        assignments = block.mode_dict
    else:
        assignments = block.event_dict

    variable: Var
    expression: Expr
    for variable, expression in assignments.items():
        if variable.name == variable_name and isinstance(expression, Const):
            if isinstance(expression.value, (int, float)) and not isinstance(expression.value, bool):
                return float(expression.value)
            else:
                return None
        else:
            pass
    return None


def _recover_fault_builder_values(builder: TemplateDefinition, block: Block) -> None:
    """Recover every fault setting represented by the saved symbolic structure.

    :param builder: Fault template builder receiving persisted values.
    :param block: Existing EMT fault block.
    :return: None.
    """
    inferred_fault_type: FaultType | None = _get_fault_type_from_block_structure(block=block)
    fault_type_property: TemplateProp | None = builder.params_dict.get("fault_type", None)
    if fault_type_property is not None and inferred_fault_type is not None:
        fault_type_property.value = inferred_fault_type
    else:
        pass

    inferred_placement: EmtFaultPlacementSide | None = _get_fault_placement_from_block_structure(block=block)
    placement_property: TemplateProp | None = builder.params_dict.get("placement_side", None)
    if placement_property is not None and inferred_placement is not None:
        placement_property.value = inferred_placement
    else:
        pass

    # Procedural logic remains present even after connecting ``fault_cmd``
    # substitutes that input with a differently named upstream variable.
    signal_controlled: bool = len(block.procedural_logic) > 0
    input_variable: Var
    for input_variable in block.in_vars:
        if input_variable.name == "fault_cmd":
            signal_controlled = True
        else:
            pass
    signal_property: TemplateProp | None = builder.params_dict.get("signal_controlled", None)
    if signal_property is not None:
        signal_property.value = signal_controlled
    else:
        pass

    initial_closed_value: float | None = _get_fault_constant(
        block=block,
        variable_name="fault_closed_mode",
        is_mode=True,
    )
    initial_closed_property: TemplateProp | None = builder.params_dict.get("initial_closed", None)
    if initial_closed_property is not None and initial_closed_value is not None:
        initial_closed_property.value = initial_closed_value >= 0.5
    else:
        pass

    event_property_names: tuple[tuple[str, str], ...] = (
        ("fault_resistance", "fault_r"),
        ("ground_resistance", "fault_rg"),
        ("open_conductance", "fault_open_g"),
        ("fault_time_constant", "fault_tau"),
        ("command_threshold", "fault_cmd_threshold"),
    )
    property_name: str
    event_variable_name: str
    for property_name, event_variable_name in event_property_names:
        property_value: float | None = _get_fault_constant(
            block=block,
            variable_name=event_variable_name,
            is_mode=False,
        )
        target_property: TemplateProp | None = builder.params_dict.get(property_name, None)
        if target_property is not None and property_value is not None:
            target_property.value = property_value
        else:
            pass


def initialize_template_builder_from_block(builder: TemplateDefinition,
                                           block: Block,
                                           block_type: BlockType) -> None:
    """Recover verified structural builder settings from a generated block.

    :param builder: Default builder that will receive recovered values.
    :param block: Existing generated block.
    :param block_type: Native type defining the extraction contract.
    :return: None.
    """
    name_property: TemplateProp | None = builder.params_dict.get("name", None)
    if name_property is not None:
        name_property.value = block.name
    else:
        pass

    phase_name: str
    for phase_name in ("N", "A", "B", "C"):
        phase_property: TemplateProp | None = builder.params_dict.get(f"ph{phase_name}", None)
        if phase_property is not None:
            phase_property.value = block_has_phase_port(block, phase_name)
        else:
            pass

    if block_type in (
        BlockType.EMT_JMARTI_LINE,
        BlockType.GFL_VSC_HVDC_RMS,
        BlockType.INTEGRATOR,
        BlockType.STARTUP_FREEZE_INTEGRATOR,
        BlockType.DERIVATIVE,
    ):
        stored_configuration: object = block.modal_template_config
        if isinstance(stored_configuration, dict):
            configuration_name: str
            configuration_value: object
            for configuration_name, configuration_value in stored_configuration.items():
                configuration_property: TemplateProp | None = builder.params_dict.get(configuration_name, None)
                if configuration_property is not None:
                    current_value: object = configuration_property.value
                    if isinstance(current_value, Enum) and isinstance(configuration_value, str):
                        enum_value: Enum | None = current_value.__class__.__members__.get(configuration_value, None)
                        if enum_value is not None:
                            configuration_property.value = enum_value
                        else:
                            pass
                    else:
                        configuration_property.value = configuration_value
                else:
                    pass
        else:
            pass
    else:
        pass

    if block_type == BlockType.EMT_THEVENIN:
        # The canonical immutable marker survives save/load and instance copies.
        # Legacy Blocks without a marker retain the balanced builder default.
        mode_property: TemplateProp | None = builder.params_dict.get("source_voltage_mode", None)
        source_block: Block
        for source_block in block.get_all_blocks():
            mode_variable: Var
            mode_expression: Expr
            for mode_variable, mode_expression in source_block.parameters.items():
                if (mode_property is not None and mode_variable.name == "source_voltage_mode"
                        and isinstance(mode_expression, Const)):
                    if mode_expression.value == 0.0:
                        mode_property.value = TheveninSourceVoltageMode.Balanced
                    elif mode_expression.value == 1.0:
                        mode_property.value = TheveninSourceVoltageMode.Phase
                    else:
                        raise ValueError("Invalid Thevenin source voltage mode marker")
                else:
                    pass
    else:
        pass

    if block_type == BlockType.FAULT_EMT:
        # The persisted symbolic equations and diagram are authoritative, so
        # recovery behaves identically before and after save/close/reopen.
        _recover_fault_builder_values(builder=builder, block=block)
    else:
        pass

    if block_type == BlockType.MIN or block_type == BlockType.MAX:
        input_count_property: TemplateProp | None = builder.params_dict.get("input_count", None)
        if input_count_property is not None:
            input_count_property.value = len(block.in_vars)
        else:
            pass
    else:
        pass

    if block_type == BlockType.LOOKUP_ARRAY_LINEAR_VARIABLE:
        # The dynamic lookup exposes one coordinate, N x-breakpoints and N
        # y-samples. Recover N from that stable port layout.
        lookup_input_count: int = len(block.in_vars)
        point_count_property: TemplateProp | None = builder.params_dict.get("point_count", None)
        has_valid_dynamic_layout: bool = (
            lookup_input_count >= 5
            and (lookup_input_count - 1) % 2 == 0
        )
        if point_count_property is not None and has_valid_dynamic_layout:
            point_count_property.value = (lookup_input_count - 1) // 2
        else:
            pass
    else:
        pass

    if block_type in (BlockType.LOOKUP_ARRAY_LINEAR, BlockType.LOOKUP_ARRAY_LINEAR_VARIABLE):
        # Linear lookup blocks retain the clipping choice as a mode parameter,
        # which survives serialization and remains independent of block names.
        clip_property: TemplateProp | None = builder.params_dict.get("clip", None)
        mode_variable: Var
        mode_expression: Expr
        for mode_variable, mode_expression in block.mode_dict.items():
            if (
                clip_property is not None
                and mode_variable.name.startswith("lookup_clip_")
                and isinstance(mode_expression, Const)
                and isinstance(mode_expression.value, (int, float))
                and not isinstance(mode_expression.value, bool)
            ):
                clip_property.value = float(mode_expression.value) >= 0.5
            else:
                pass
    else:
        pass

    if block_type in (
        BlockType.GFL_VSC_HVDC_RMS,
        BlockType.VSC_ACTIVE_CONTROL_RMS,
        BlockType.VSC_REACTIVE_CONTROL_RMS,
    ):
        # Current files persist the template settings, but older files do not.
        # Recover controller modes from the generated child names on every open:
        # the symbolic structure is authoritative if metadata is missing or stale.
        child_names: set[str] = set()
        candidate_block: Block
        for candidate_block in block.get_all_blocks():
            child_names.add(candidate_block.name)
            # Standalone controllers can be renamed by the user. Their
            # integral-state names still retain the structural mode after
            # serialization or equation decomposition.
            state_variable: Var
            for state_variable in candidate_block.state_vars:
                if state_variable.name.startswith("xi_"):
                    child_names.add(state_variable.name[3:])
                else:
                    pass

        control1_property: TemplateProp | None = builder.params_dict.get("control1", None)
        if control1_property is None:
            pass
        elif "Pdc_ctrl" in child_names:
            control1_property.value = ConverterControlType.Pdc
        elif "Pac_ctrl" in child_names:
            control1_property.value = ConverterControlType.Pac
        elif "Vdc_ctrl" in child_names:
            control1_property.value = ConverterControlType.Vm_dc
        else:
            pass

        control2_property: TemplateProp | None = builder.params_dict.get("control2", None)
        if control2_property is None:
            pass
        elif "Vac_ctrl" in child_names:
            control2_property.value = ConverterControlType.Vm_ac
        elif "Qac_ctrl" in child_names:
            control2_property.value = ConverterControlType.Qac
        else:
            pass

        # Cdc is a regular numeric parameter. Recovering it here prevents a
        # structural controller edit from replacing a saved custom value with
        # the builder default before the parameter table is reapplied.
        cdc_property: TemplateProp | None = builder.params_dict.get("cdc", None)
        for candidate_block in block.get_all_blocks():
            event_variable: Var
            event_expression: Expr
            for event_variable, event_expression in candidate_block.event_dict.items():
                if cdc_property is not None and event_variable.name == "Cdc" and isinstance(event_expression, Const):
                    if isinstance(event_expression.value, (int, float)):
                        cdc_property.value = float(event_expression.value)
                    else:
                        pass
                else:
                    pass
    else:
        pass

    if block_type in (
        BlockType.INVERSE_LOOKUP_ARRAY,
        BlockType.LOOKUP_ARRAY_LINEAR,
        BlockType.LOOKUP_ARRAY_SPLINE,
    ):
        points_property: TemplateProp | None = builder.params_dict.get("points", None)
        extracted_points: tuple[tuple[float, float], ...] | None = extract_lookup_array_points(block)
        if points_property is not None and extracted_points is not None:
            points_property.value = extracted_points
        else:
            pass
    elif block_type == BlockType.LOOKUP_MATRIX_LINEAR or block_type == BlockType.LOOKUP_MATRIX_SPLINE:
        matrix_property: TemplateProp | None = builder.params_dict.get("x_y_z_values", None)
        extracted_matrix: tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[float, ...], ...]] | None = (
            extract_lookup_matrix_values(block)
        )
        if matrix_property is not None and extracted_matrix is not None:
            matrix_property.value = extracted_matrix
        else:
            pass
    else:
        pass


def block_has_phase_port(block: Block, phase_name: str) -> bool:
    """Return whether one root input/output exposes the requested EMT phase.

    :param block: Generated block whose root ports are inspected.
    :param phase_name: One of ``N``, ``A``, ``B`` or ``C``.
    :return: Whether the phase is present.
    """
    result: bool = False
    variable_groups: tuple[List[Var], List[Var]] = (block.in_vars, block.out_vars)
    variable_group: List[Var]
    variable: Var
    for variable_group in variable_groups:
        for variable in variable_group:
            reference_text: str = "" if variable.ref is None else str(variable.ref.value)
            candidate_texts: tuple[str, str] = (variable.name, reference_text)
            candidate_text: str
            for candidate_text in candidate_texts:
                if re.search(rf"(?:^|_){phase_name}(?:$|_)", candidate_text) is not None:
                    result = True
                else:
                    pass
    return result


def extract_lookup_array_points(block: Block) -> tuple[tuple[float, float], ...] | None:
    """Recover persisted lookup-array points from event parameters.

    :param block: Lookup block storing ``arr_xN`` and ``arr_yN`` constants.
    :return: Ordered points or ``None`` when the structure is not recoverable.
    """
    x_values: Dict[int, float] = dict()
    y_values: Dict[int, float] = dict()
    variable: Var
    expression: object
    for variable, expression in block.event_dict.items():
        if isinstance(expression, Const) and isinstance(expression.value, (int, float)):
            x_match: re.Match[str] | None = re.search(r"arr_x(\d+)_", variable.name)
            y_match: re.Match[str] | None = re.search(r"arr_y(\d+)_", variable.name)
            if x_match is not None:
                x_values[int(x_match.group(1))] = float(expression.value)
            elif y_match is not None:
                y_values[int(y_match.group(1))] = float(expression.value)
            else:
                pass
        else:
            pass
    common_indexes: List[int] = sorted(set(x_values.keys()).intersection(y_values.keys()))
    if len(common_indexes) >= 2:
        return tuple((x_values[index], y_values[index]) for index in common_indexes)
    else:
        return None


def extract_lookup_matrix_values(
        block: Block,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[float, ...], ...]] | None:
    """Recover persisted lookup-matrix axes and surface from event parameters.

    :param block: Lookup block storing ``arr_xN``, ``arr_yN`` and ``arr_zN_M``.
    :return: ``(x, y, z)`` tuple or ``None`` when incomplete.
    """
    x_values: Dict[int, float] = dict()
    y_values: Dict[int, float] = dict()
    z_values: Dict[tuple[int, int], float] = dict()
    variable: Var
    expression: object
    for variable, expression in block.event_dict.items():
        if isinstance(expression, Const) and isinstance(expression.value, (int, float)):
            x_match: re.Match[str] | None = re.search(r"arr_x(\d+)_", variable.name)
            y_match: re.Match[str] | None = re.search(r"arr_y(\d+)_", variable.name)
            z_match: re.Match[str] | None = re.search(r"arr_z(\d+)_(\d+)_", variable.name)
            if x_match is not None:
                x_values[int(x_match.group(1))] = float(expression.value)
            elif y_match is not None:
                y_values[int(y_match.group(1))] = float(expression.value)
            elif z_match is not None:
                z_values[(int(z_match.group(1)), int(z_match.group(2)))] = float(expression.value)
            else:
                pass
        else:
            pass

    x_indexes: List[int] = sorted(x_values.keys())
    y_indexes: List[int] = sorted(y_values.keys())
    complete: bool = len(x_indexes) >= 2 and len(y_indexes) >= 2
    y_index: int
    x_index: int
    for y_index in y_indexes:
        for x_index in x_indexes:
            if (y_index, x_index) not in z_values:
                complete = False
            else:
                pass
    if complete:
        z_rows: tuple[tuple[float, ...], ...] = tuple(
            tuple(z_values[(y_index, x_index)] for x_index in x_indexes)
            for y_index in y_indexes
        )
        return (
            tuple(x_values[index] for index in x_indexes),
            tuple(y_values[index] for index in y_indexes),
            z_rows,
        )
    else:
        return None


def _get_transformer_connection_types(api_object: Transformer2W | Winding | None) -> tuple[
    WindingType | None, WindingType | None]:
    """
    Return the explicit from/to winding connections for transformer-like objects.

    :param api_object: Transformer-like API object.
    :return: Pair ``(conn_f, conn_t)`` or ``(None, None)`` when unavailable.
    """
    if api_object is None:
        return None, None
    else:
        return api_object.conn_f, api_object.conn_t


def create_block_of_type(var_factory: VarFactory,
                         block_type: BlockType,
                         item_name: str = "",
                         api_object: ALL_DEV_TYPES | None = None) -> Block | None:
    """
    Create a Block appropriate for block_type.

    :param var_factory: Factory that owns symbolic variables.
    :param block_type: Dynamic block catalogue type.
    :param item_name: Requested visible item name.
    :param api_object: Static network device associated with the model.
    :return: Block instance appropriate for ``block_type``, or ``None`` when creation is cancelled.
    """
    # CONST (single output)
    if block_type == BlockType.CONST:
        blk = basic_block_templates.constant(var_factory, item_name)
        blk.name = item_name
        return blk

    # Generic blocks use the same deterministic default interface as the
    # dedicated library-drop path so direct factory callers remain consistent.
    elif block_type == BlockType.GENERIC:
        return create_generic_block(
            var_factory=var_factory,
            inputs=1,
            outputs=1,
            name=item_name,
        )

    # GAIN (single input -> single output)
    elif block_type == BlockType.GAIN:
        blk = basic_block_templates.gain(var_factory, item_name)
        blk.name = item_name
        return blk
    #
    # # SUM / ADDER (2 inputs)
    # elif block_type == BlockType.SUM:
    #     blk = adder(var_factory = var_factory,
    #                 name=item_name)
    #     blk.name = item_name
    #     return blk

    # # PRODUCT (2 inputs)
    # elif block_type == BlockType.PRODUCT:
    #     blk = product(var_factory, item_name)
    #     blk.name = item_name
    #     return blk

    # ABSOLUT (single input -> single output)
    elif block_type == BlockType.ABS:
        blk = basic_block_templates.absolut(var_factory, item_name)
        blk.name = item_name
        return blk

    # ---------- RMS BLOCKS ----------

    # GENRAW (simple model)
    elif block_type == BlockType.GENRAW:
        blk = tem.get_genrow_rms_template(var_factory).block
        blk.name = item_name
        return blk

    # GENQEC (generator with saturation)
    elif block_type == BlockType.GENQEC:
        blk = tem.get_genqec_rms(var_factory, item_name).block
        blk.name = item_name
        return blk

    # GOVERNOR (governor with control)
    elif block_type == BlockType.GOV_RMS:
        blk = tem.get_governor_rms(var_factory, item_name).block
        blk.name = item_name
        return blk

    # STABILIZER (stabilizer)
    elif block_type == BlockType.STAB_RMS:
        blk = tem.get_stabilizer_rms(var_factory, item_name).block
        blk.name = item_name
        return blk

    # EXCITER (exciter)
    elif block_type == BlockType.EXCITER_RMS:
        blk = tem.get_exciter_rms(var_factory, item_name).block
        blk.name = item_name
        return blk

    # LINE (line)
    elif block_type == BlockType.LINE_RMS:
        blk = tem.get_line_rms_template(var_factory).block
        blk.name = item_name
        return blk

    # LOAD (line)
    elif block_type == BlockType.LOAD_RMS:
        blk = tem.get_load_rms_template(var_factory).block
        blk.name = item_name
        return blk

    # GRID FORMING CONVERTER
    elif block_type == BlockType.GFL_VSC_RMS:
        blk = tem.build_vsc_rms(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.PLL_TRANSFORM_RMS:
        blk = tem.get_pll_transform_rms(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.PI_CURRENT_CONTROLLER:
        blk = tem.get_pi_current_controller(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.PI_POWER_CONTROLLER:
        blk = tem.get_pi_power_controller(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.GFL_CONVERTER_RMS:
        blk = tem.get_gfl_converter_rms(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.VSC_PLL_RMS:
        return rms_templates.build_vsc_pll_rms(var_factory, name=item_name)

    elif block_type == BlockType.VSC_ELECTRICAL_RMS:
        return rms_templates.build_vsc_electrical_rms(var_factory, name=item_name)

    elif block_type == BlockType.VSC_CURRENT_LIMITER_RMS:
        return rms_templates.build_vsc_current_limiter_rms(var_factory, name=item_name)

    elif block_type in (BlockType.VSC_VD_HAT_RMS, BlockType.VSC_VQ_HAT_RMS):
        # Keep native identifiers and symbolic names stable, but show the
        # controller's purpose instead of the historical enum on a new drop.
        controller_label: str
        if block_type == BlockType.VSC_VD_HAT_RMS:
            blk = rms_templates.build_vsc_vd_hat_rms(var_factory, name=item_name)
            controller_label = "d-axis current PI controller"
        else:
            blk = rms_templates.build_vsc_vq_hat_rms(var_factory, name=item_name)
            controller_label = "q-axis current PI controller"
        generated_prefix: str = f"{block_type.name}_"
        instance_number: str = item_name.removeprefix(generated_prefix)
        if item_name.startswith(generated_prefix) and instance_number.isdecimal():
            blk.name = f"{controller_label}_{instance_number}"
        else:
            # Explicit caller/user names must not be overwritten.
            pass
        return blk

    elif block_type == BlockType.VSC_DC_LINK_RMS:
        return rms_templates.build_vsc_dc_link_rms(var_factory, name=item_name)

    elif block_type == BlockType.VOLTAGE_SOURCE_RMS:
        blk = rms_templates.VoltageSourceBuild(var_factory, name=item_name).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.TRANSFORMER_2W_RMS:
        blk = rms_templates.get_transformer2w_rms(vf=var_factory).block
        blk.name = item_name
        return blk


    # DC PV source averaged
    # elif block_type == BlockType.DC_PV_SOURCE_RMS:
    #     blk = tem.DCPVSourceAveraged(var_factory).block
    #     blk.name = item_name
    #     return blk

    # ---------- EMT BLOCKS ----------
    # EMT type GENERATOR
    elif block_type == BlockType.EMT_GENERATOR:
        blk = tem.get_simple_generator_emt_template(var_factory).block
        blk.name = item_name
        return blk

    # Thevenin equivalent generator
    elif block_type == BlockType.EMT_THEVENIN:
        blk = tem.get_generator_thevenin_rl_emt_template_with_ref(var_factory).block
        blk.name = item_name
        return blk

    # GOVERNOR (governor with control)
    elif block_type == BlockType.GOV_EMT:
        blk = tem.get_governor_emt(var_factory, item_name).block
        blk.name = item_name
        return blk

    # STABILIZER (stabilizer)
    elif block_type == BlockType.STAB_EMT:
        blk = tem.get_stabilizer_emt(var_factory, item_name).block
        blk.name = item_name
        return blk

    # EXCITER (exciter)
    elif block_type == BlockType.EXCITER_EMT:
        blk = tem.get_exciter_emt(var_factory, item_name).block
        blk.name = item_name
        return blk

    # DC LOAD
    elif block_type == BlockType.DC_LOAD_EMT:
        blk = tem.get_dc_load_emt_template(var_factory).block
        blk.name = item_name
        return blk

    # Three-phase RLC shunt. The library exposes this combined block directly,
    # so it needs a deterministic construction path rather than falling through
    # to the unsupported-block error raised for genuinely unknown types.
    elif block_type == BlockType.RLC_COMBO_EMT:
        blk = emt_templates.get_shunt_rlc_combo_emt_template(
            vf=var_factory,
            include_r=True,
            include_l=True,
            include_c=True,
            phA=True,
            phB=True,
            phC=True,
            connection_type=ShuntConnectionType.GroundedStar,
            direct_r_value=1.0,
            direct_l_value=1.0e-3,
            direct_c_value=1.0e-6,
            name=item_name,
        ).block
        blk.name = item_name
        return blk

    # #
    # elif block_type == BlockType.INDUCTION_MOTOR_EMT:
    #     blk = tem.get_induction_motor_emt_template(vf=var_factory, name=item_name).block
    #     blk.name = item_name
    #     return blk

    elif block_type == BlockType.GROUND_EMT:
        blk = tem.get_ground_emt_template(var_factory, item_name).block
        blk.name = item_name
        return blk

    # The two PV library entries represent the shipped Level-1 and Level-2
    # averaged-value models. Keeping both routes here makes every draggable
    # library payload materializable without a legacy creation dialogue.
    elif block_type == BlockType.PV_EMT:
        blk = tem.get_pv_avm_grid_following_emt_template(var_factory, item_name).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.PV_POWER_PLANT_EMT:
        blk = tem.get_pv_avm_boost_grid_following_emt_template(var_factory, item_name).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.BATTERY_EMT:
        blk = tem.get_battery_avm_emt_template(var_factory, item_name).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.BESS_EMT:
        blk = tem.get_bess_avm_grid_following_emt_template(var_factory, item_name).block
        blk.name = item_name
        return blk

    # DC LINE
    elif block_type == BlockType.EMT_DC_LINE:
        blk = tem.get_dc_line_with_power_input_emt_template(var_factory).block
        blk.name = item_name
        return blk

    # COMPLETE PSEUDO EMT VSC
    elif block_type == BlockType.COMPLETE_PSEUDO_VSC_EMT:
        blk = tem.get_full_pseudo_emt_converter(var_factory).block
        blk.name = item_name
        return blk


    elif block_type == BlockType.DC_VOLTAGE_SOURCE_EMT:
        blk = tem.get_dc_voltage_source_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.DC_CURRENT_SOURCE_EMT:
        blk = tem.get_dc_current_source_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.CONTROLLED_DC_VOLTAGE_SOURCE_EMT:
        blk = tem.get_controlled_dc_voltage_source_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.CONTROLLED_DC_CURRENT_SOURCE_EMT:
        blk = tem.get_controlled_dc_current_source_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.BALANCED_3PH_VOLTAGE_SOURCE_EMT:
        blk = tem.get_balanced_3ph_voltage_source_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.BALANCED_3PH_CURRENT_SOURCE_EMT:
        blk = tem.get_balanced_3ph_current_source_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.CONTROLLED_BALANCED_3PH_VOLTAGE_SOURCE_EMT:
        blk = tem.get_controlled_balanced_3ph_voltage_source_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.CONTROLLED_BALANCED_3PH_CURRENT_SOURCE_EMT:
        blk = tem.get_controlled_balanced_3ph_current_source_emt_template(var_factory).block
        blk.name = item_name
        return blk

    else:
        raise ValueError(f"Unknown block type: {block_type}")


def create_generic_block(var_factory: VarFactory,
                         inputs: int,
                         outputs: int,
                         name: str = "generic"
                         ) -> Block:
    """

    :param var_factory:
    :param inputs:
    :param outputs:
    :param name:
    :return:
    """
    blk = basic_block_templates.generic(var_factory, inputs, outputs)
    blk.name = name
    return blk


def synchronize_vsc_library_initialization(
        root: Block,
        block_types: dict[int, BlockType] | None = None,
) -> list[Var]:
    """Bind the VSC inner-PI initial conditions for a Library assembly.

    The two inner-PI output initializations follow the actual symbolic
    connections, including intermediate ELK operation blocks, rather than
    labels. Physical Pt/Qt are power-flow-initialized algebraic variables and
    must not receive duplicate initialization equations.

    :param root: Complete editor working tree with its physical root interface.
    :param block_types: Optional in-memory component types; persisted diagrams
        supply the types when reopening a saved model.
    :return: Target variables whose initialization cannot yet be connected.
    """
    blocks: list[Block] = root.get_all_blocks()
    types_by_uid: dict[int, BlockType] = dict() if block_types is None else dict(block_types)
    candidate: Block
    diagram_node: BlockDiagramNode
    for candidate in blocks:
        for diagram_node in candidate.diagram.node_data.values():
            if diagram_node.tpe in BlockType.__members__:
                types_by_uid[diagram_node.device_uid] = BlockType[diagram_node.tpe]
            else:
                pass

    targets: dict[int, Var] = dict()
    for candidate in blocks:
        block_type: BlockType | None = types_by_uid.get(candidate.uid, None)
        if block_type in (BlockType.VSC_VD_HAT_RMS, BlockType.VSC_VQ_HAT_RMS) and len(candidate.out_vars) == 1:
            targets[candidate.out_vars[0].uid] = candidate.out_vars[0]
        else:
            pass
    if len(targets) == 0:
        return list()
    else:
        pass

    # Rebuild generated initial conditions on every save, so reconnecting a
    # port cannot retain an initialization dependency on its former neighbour.
    rehash_block_tree_var_keyed_dicts(root)
    assignments: dict[Var, Expr] = dict()
    owners: dict[int, Block] = dict()
    equations: list[Expr] = list()
    known: set[int] = set()
    variable: Var
    for candidate in blocks:
        for variable in list(candidate.init_eqs):
            if variable.uid in targets:
                del candidate.init_eqs[variable]
            else:
                pass
        assignments.update(candidate.init_eqs)
        assignments.update(candidate.event_dict)
        known.update(variable.uid for variable in candidate.parameters)
        equations.extend(candidate.algebraic_eqs)
        for variable in candidate.algebraic_vars:
            owners[variable.uid] = candidate

    # These are physical network seeds, not inferred connections. In
    # particular, Pt/Qt now belong directly to the electrical component.
    root_port_group: list[Var]
    for root_port_group in (root.in_vars, root.out_vars):
        known.update(variable.uid for variable in root_port_group)
    reference: VarPowerFlowReferenceType
    for reference in (
        VarPowerFlowReferenceType.Vdc, VarPowerFlowReferenceType.Vmt,
        VarPowerFlowReferenceType.Vat, VarPowerFlowReferenceType.Pf,
        VarPowerFlowReferenceType.Pt, VarPowerFlowReferenceType.Qt,
    ):
        mapped_variable: Var | None = root.external_mapping.get(reference, None)
        if mapped_variable is not None:
            known.add(mapped_variable.uid)
        else:
            pass

    # Resolve only affine algebraic identities with one unknown and a nonzero
    # constant coefficient. States are never solved or forced to equilibrium.
    # Existing init_eqs remain authoritative; their dependencies must actually
    # be resolvable before they are used to derive a downstream initialization.
    inferred: dict[Var, Expr] = dict()
    progress: bool = True
    expression: Expr
    while progress:
        progress = False
        for variable, expression in assignments.items():
            if variable.uid not in known and all(dependency.uid in known for dependency in expression.get_vars()):
                known.add(variable.uid)
                progress = True
            else:
                pass
        for expression in equations:
            unknowns: dict[int, Var] = dict(
                (dependency.uid, dependency) for dependency in expression.get_vars() if dependency.uid not in known
            )
            if len(unknowns) == 1:
                variable = next(iter(unknowns.values()))
                if variable.uid in owners and variable not in assignments:
                    coefficient: Expr = expression.diff(variable).simplify()
                    if isinstance(coefficient, Const) and coefficient.value is not None and coefficient.value != 0.0:
                        remainder: Expr = expression.subs(dict(((variable, Const(0.0)),))).simplify()
                        inferred_expression: Expr = (-remainder / coefficient).subs(inferred).simplify()
                        if all(dependency.uid in known for dependency in inferred_expression.get_vars()):
                            inferred[variable] = inferred_expression
                            known.add(variable.uid)
                            progress = True
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
            else:
                pass

    # Intermediate graphical operations are substituted, not added as new
    # initialization owners. Only the two inner-PI outputs are saved.
    unresolved: list[Var] = list()
    for variable in targets.values():
        initial_expression: Expr | None = inferred.get(variable, None)
        owner: Block | None = owners.get(variable.uid, None)
        if initial_expression is not None and owner is not None:
            owner.init_eqs[variable] = initial_expression
        else:
            unresolved.append(variable)
    return unresolved
