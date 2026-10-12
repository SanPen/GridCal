# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Parse, validate, serialize, and apply procedural Python model code."""

from __future__ import annotations

import ast
import keyword
import re
from typing import Dict, List, Mapping, Sequence

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import ProceduralFieldType, ProceduralLogicType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import (
    CmpOp,
    Comparison,
    Const,
    Expr,
    Var,
    string_to_symbolic,
    symbolic_to_string,
)
from VeraGridEngine.Utils.procedural_logic import (
    AnalogFlipFlopLogic,
    ConditionalDiagnosticLogic,
    DelayedSwitchEventLogic,
    DelayedThresholdLatchLogic,
    FixedSampleLogic,
    FlipFlopLogic,
    GradientLimiterLogic,
    HardSaturationLogic,
    MovingAverageLogic,
    PickupDropoffLogic,
    ProceduralLogicBase,
    ResetOnRisingEdgeLogic,
    SampledValueLogic,
    StartupHandoverLogic,
    ThreePhaseCarrierPwmLogic,
    ThreePhaseCarrierSampledModulationLogic,
    TimeDelayLogic,
    ValveStateLogic,
)
from VeraGridEngine.Templates.ProceduralLogicCatalog import (
    ProceduralBlockTemplateDescriptor,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    get_dynamic_library_procedural_descriptors,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dae_code_linter import (
    normalize_algebraic_equality_syntax,
)


def comparison_operator_to_python(operator: CmpOp) -> str:
    """Return the Python token accepted by the safe symbolic parser.

    Engine comparison values are presentation symbols and may contain Unicode
    glyphs such as ``≥``. The runtime editor serializes executable Python-like
    source, so it must use parser tokens instead.

    :param operator: Engine comparison operator.
    :return: Python comparison token.
    """
    if operator == CmpOp.LE:
        result: str = "<="
    elif operator == CmpOp.GE:
        result = ">="
    elif operator == CmpOp.LT:
        result = "<"
    elif operator == CmpOp.GT:
        result = ">"
    elif operator == CmpOp.EQ:
        result = "=="
    else:
        raise ValueError(f"Unsupported comparison operator '{operator}'")
    return result


def get_symbol_replacement_sort_key(symbol_name: str) -> tuple[int, str]:
    """Return a key that replaces longer non-Python names first.

    :param symbol_name: Original engine symbol name.
    :return: Descending-length-compatible sort key.
    """
    return -len(symbol_name), symbol_name


def normalize_runtime_expression_source(source: str,
                                        namespace: Mapping[str, Expr]) -> tuple[str, Dict[str, Expr]]:
    """Replace non-Python engine names with temporary parser aliases.

    Catalogue globalization preserves human-readable block labels, which may
    include spaces, parentheses or a leading digit. Those names are valid in
    the symbolic engine but not as Python AST identifiers. Temporary aliases
    let the safe parser reconstruct the original ``Var`` identities without
    renaming the model.

    :param source: Serialized symbolic source using engine names.
    :param namespace: Canonical name-to-expression mapping.
    :return: Parser-safe source and augmented namespace.
    """
    normalized: str = source
    parser_namespace: Dict[str, Expr] = dict(namespace)
    replacement_names: List[str] = list()
    symbol_name: str
    for symbol_name in namespace.keys():
        parser_safe: bool = symbol_name.isidentifier() and not keyword.iskeyword(symbol_name)
        if not parser_safe and symbol_name in normalized:
            replacement_names.append(symbol_name)
        else:
            pass
    replacement_names.sort(key=get_symbol_replacement_sort_key)

    replacement_index: int = 0
    for symbol_name in replacement_names:
        alias: str = f"__runtime_symbol_{replacement_index}"
        while alias in parser_namespace:
            replacement_index += 1
            alias = f"__runtime_symbol_{replacement_index}"
        normalized = normalized.replace(symbol_name, alias)
        parser_namespace[alias] = namespace[symbol_name]
        replacement_index += 1
    return normalized, parser_namespace


class ProceduralFieldDraft:
    """One typed field parsed from or serialized to Python model code."""

    __slots__ = ("_key", "_label", "_tpe", "_value", "_description")

    def __init__(self,
                 key: str,
                 label: str,
                 tpe: ProceduralFieldType,
                 value: str,
                 description: str) -> None:
        """Store one detached procedural field.

        :param key: Stable constructor/serialization field name.
        :param label: User-facing field label.
        :param tpe: Semantic editor and validation kind.
        :param value: Detached textual value.
        :param description: Contextual field explanation.
        :return: None.
        """
        self._key: str = key
        self._label: str = label
        self._tpe: ProceduralFieldType = tpe
        self._value: str = value
        self._description: str = description

    def get_key(self) -> str:
        """
        :return: The stable field key.
        """
        return self._key

    def get_label(self) -> str:
        """
        :return: The user-facing field label.
        """
        return self._label

    def get_tpe(self) -> ProceduralFieldType:
        """
        :return: The semantic editor kind.
        """
        return self._tpe

    def get_value(self) -> str:
        """
        :return: The detached textual value.
        """
        return self._value

    def set_value(self, value: str) -> None:
        """
        Replace the detached textual value.

        :param value: Value supplied for ``value``.
        :return: None.
        """
        self._value = value.strip()

    def get_description(self) -> str:
        """
        :return: The field help text.
        """
        return self._description

class RuntimeModeDraft:
    """Detached retained runtime mode with an initial symbolic expression."""

    __slots__ = ("_owner", "_variable", "_name", "_initial_expression", "_removed")

    def __init__(self,
                 owner: Block,
                 variable: Var | None,
                 name: str,
                 initial_expression: str) -> None:
        """Capture one retained mode without changing its block.

        :param owner: Direct block owning ``mode_dict``.
        :param variable: Existing variable or ``None`` for a new draft.
        :param name: Symbol name.
        :param initial_expression: Python-like symbolic initialization source.
        :return: None.
        """
        self._owner: Block = owner
        self._variable: Var | None = variable
        self._name: str = name
        self._initial_expression: str = initial_expression
        self._removed: bool = False

    def get_owner(self) -> Block:
        """
        :return: The direct owner block.
        """
        return self._owner

    def get_variable(self) -> Var | None:
        """
        Return the existing mode variable or ``None`` for a new mode.

        :return: The existing mode variable or ``None`` for a new mode.
        """
        return self._variable

    def get_name(self) -> str:
        """
        Return the mode symbol name.

        :return: The mode symbol name.
        """
        return self._name

    def set_name(self, name: str) -> None:
        """
        Set the name of a new retained mode.

        :param name: Value supplied for ``name``.
        :return: None.
        """
        self._name = name.strip()

    def get_initial_expression(self) -> str:
        """
        Return the staged initial expression source.

        :return: The staged initial expression source.
        """
        return self._initial_expression

    def is_new(self) -> bool:
        """
        Return whether Apply must create a real variable.

        :return: Whether Apply must create a real variable.
        """
        return self._variable is None

    def is_removed(self) -> bool:
        """
        Return whether deletion is staged.

        :return: Whether deletion is staged.
        """
        return self._removed

    def set_removed(self, removed: bool) -> None:
        """
        Stage or undo deletion.

        :param removed: Value supplied for ``removed``.
        :return: None.
        """
        self._removed = removed

class ProceduralLogicDraft:
    """Typed representation parsed from one procedural Python call."""

    __slots__ = ("_owner", "_logic_tpe", "_name", "_fields", "_original")

    def __init__(self,
                 owner: Block,
                 logic_tpe: ProceduralLogicType,
                 name: str,
                 fields: Sequence[ProceduralFieldDraft],
                 original: ProceduralLogicBase | None) -> None:
        """Capture one procedural entry and its typed fields.

        :param owner: Direct block owning the ordered entry.
        :param logic_tpe: Canonical procedural type.
        :param name: User-facing entry name.
        :param fields: Typed editable fields.
        :param original: Original entry or ``None`` for a staged addition.
        :return: None.
        """
        self._owner: Block = owner
        self._logic_tpe: ProceduralLogicType = logic_tpe
        self._name: str = name
        self._fields: List[ProceduralFieldDraft] = list(fields)
        self._original: ProceduralLogicBase | None = original

    def get_owner(self) -> Block:
        """
        :return: The direct owner block.
        """
        return self._owner

    def get_logic_tpe(self) -> ProceduralLogicType:
        """
        :return: The canonical logic type.
        """
        return self._logic_tpe

    def get_name(self) -> str:
        """
        :return: The staged entry name.
        """
        return self._name

    def get_fields(self) -> List[ProceduralFieldDraft]:
        """
        :return: The ordered editable fields.
        """
        return list(self._fields)

    def get_field(self, key: str) -> ProceduralFieldDraft | None:
        """Return one parsed field by its stable serialization key.

        :param key: Requested field key.
        :return: Matching field or ``None`` when the call omitted it.
        """
        result: ProceduralFieldDraft | None = None
        field: ProceduralFieldDraft
        for field in self._fields:
            if field.get_key() == key and result is None:
                result = field
            else:
                pass
        return result

    def get_original(self) -> ProceduralLogicBase | None:
        """
        Return the original runtime entry.

        :return: The original runtime entry.
        """
        return self._original

class RuntimeLogicValidationResult:
    """Validation messages for a complete retained-mode/procedural draft."""

    __slots__ = ("_errors", "_warnings")

    def __init__(self) -> None:
        """
        Create an empty validation result.

        :return: None.
        """
        self._errors: List[str] = list()
        self._warnings: List[str] = list()

    def add_error(self, message: str) -> None:
        """
        Append one blocking error.

        :param message: Value supplied for ``message``.
        :return: None.
        """
        self._errors.append(message)

    def add_warning(self, message: str) -> None:
        """
        Append one non-blocking warning.

        :param message: Value supplied for ``message``.
        :return: None.
        """
        self._warnings.append(message)

    def get_errors(self) -> List[str]:
        """
        Return blocking errors.

        :return: Blocking errors.
        """
        return list(self._errors)

    def get_warnings(self) -> List[str]:
        """
        Return non-blocking warnings.

        :return: Non-blocking warnings.
        """
        return list(self._warnings)

    def is_valid(self) -> bool:
        """
        Return whether no blocking error was collected.

        :return: Whether no blocking error was collected.
        """
        return len(self._errors) == 0


def procedural_expression_to_text(expression: Expr | Comparison | float | int | bool) -> str:
    """Convert one procedural expression to editable Python-like source.

    :param expression: Existing procedural expression or scalar.
    :return: Readable source accepted by ``string_to_symbolic``.
    """
    if isinstance(expression, Comparison):
        left_text: str = symbolic_to_string(expression.lhs)
        if isinstance(expression.rhs, Expr):
            right_text: str = symbolic_to_string(expression.rhs)
        else:
            right_text = str(expression.rhs)
        operator_text: str = comparison_operator_to_python(expression.op)
        result: str = f"{left_text} {operator_text} {right_text}"
    elif isinstance(expression, Expr):
        result = symbolic_to_string(expression)
    else:
        result = str(float(expression))
    return result


def make_procedural_field(key: str,
                          label: str,
                          tpe: ProceduralFieldType,
                          value: str,
                          description: str) -> ProceduralFieldDraft:
    """Build one non-trivial typed procedural field.

    :param key: Stable field key.
    :param label: User-facing label.
    :param tpe: Editor type.
    :param value: Initial text.
    :param description: Field help.
    :return: Configured field draft.
    """
    field: ProceduralFieldDraft = ProceduralFieldDraft(key, label, tpe, value, description)
    return field


def get_procedural_fields(entry: ProceduralLogicBase) -> List[ProceduralFieldDraft]:
    """Build typed fields from any supported runtime entry.

    :param entry: Existing procedural logic object.
    :return: Ordered field drafts.
    """
    fields: List[ProceduralFieldDraft] = list()
    expression_tpe: ProceduralFieldType = ProceduralFieldType.EXPRESSION
    mode_tpe: ProceduralFieldType = ProceduralFieldType.MODE_REFERENCE
    variable_tpe: ProceduralFieldType = ProceduralFieldType.VARIABLE_REFERENCE
    runtime_tpe: ProceduralFieldType = ProceduralFieldType.RUNTIME_REFERENCE
    target_tpe: ProceduralFieldType = ProceduralFieldType.TARGET_REFERENCE

    if isinstance(entry, ConditionalDiagnosticLogic):
        fields.extend(list((
            make_procedural_field(
                "condition_expr",
                "Condition",
                expression_tpe,
                procedural_expression_to_text(entry.condition_expr),
                "Condition that activates the diagnostic.",
            ),
            make_procedural_field(
                "message",
                "Message",
                ProceduralFieldType.REQUIRED_TEXT,
                entry.message,
                "Exact diagnostic text retained by the model.",
            ),
            make_procedural_field(
                "initialization_only",
                "Initialization only",
                ProceduralFieldType.BOOLEAN,
                str(entry.initialization_only),
                "Whether the diagnostic is restricted to initialization.",
            ),
        )))
    elif isinstance(entry, DelayedSwitchEventLogic):
        fields.extend(list((
            make_procedural_field(
                "output_var_name", "Output mode", mode_tpe,
                entry.output_var_name, "Retained switch-position mode.",
            ),
            make_procedural_field(
                "guard_expr", "Guard", expression_tpe,
                procedural_expression_to_text(entry.guard_expr),
                "Expression enabling trigger detection.",
            ),
            make_procedural_field(
                "trigger_expr", "Trigger", expression_tpe,
                procedural_expression_to_text(entry.trigger_expr),
                "Expression whose rising edge schedules the event.",
            ),
            make_procedural_field(
                "delay_expr", "Delay", expression_tpe,
                procedural_expression_to_text(entry.delay_expr),
                "Non-negative delay evaluated when the trigger rises.",
            ),
            make_procedural_field(
                "target_device_idtag", "Target device identifier",
                ProceduralFieldType.REQUIRED_TEXT, entry.target_device_idtag,
                "Exact physical equipment identifier.",
            ),
            make_procedural_field(
                "target_switch_idtag", "Target switch identifier",
                ProceduralFieldType.REQUIRED_TEXT, entry.target_switch_idtag,
                "Exact switch identifier.",
            ),
            make_procedural_field(
                "target_terminal_index", "Target terminal",
                ProceduralFieldType.INTEGER, str(entry.target_terminal_index),
                "Physical equipment terminal containing the switch.",
            ),
            make_procedural_field(
                "initial_closed", "Initially closed",
                ProceduralFieldType.BOOLEAN, str(entry.initial_closed),
                "Initial switch position.",
            ),
            make_procedural_field(
                "command_closed", "Command closed",
                ProceduralFieldType.BOOLEAN, str(entry.command_closed),
                "Switch position applied when the event fires.",
            ),
        )))
    elif isinstance(entry, FixedSampleLogic):
        fields.append(make_procedural_field("output_var_name", "Output mode", mode_tpe,
                                            entry.output_var_name, "Boolean value retained after initialization."))
        fields.append(make_procedural_field("condition_expr", "Condition", expression_tpe,
                                            procedural_expression_to_text(entry.condition_expr),
                                            "Condition sampled once during initialization."))
    elif isinstance(entry, SampledValueLogic):
        fields.append(make_procedural_field("output_var_name", "Output mode", mode_tpe,
                                            entry.output_var_name, "Retained sampled value."))
        fields.append(make_procedural_field("source_expr", "Source expression", expression_tpe,
                                            procedural_expression_to_text(entry.source_expr),
                                            "Expression sampled at every accepted step."))
    elif isinstance(entry, HardSaturationLogic):
        fields.extend(list((make_procedural_field("output_var_name", "Output mode", mode_tpe, entry.output_var_name,
                                  "Retained saturated output."), make_procedural_field("u_expr", "Input expression", expression_tpe,
                                  procedural_expression_to_text(entry.u_expr), "Value to clamp."), make_procedural_field("u_min_expr", "Minimum", expression_tpe,
                                  procedural_expression_to_text(entry.u_min_expr), "Lower saturation bound."), make_procedural_field("u_max_expr", "Maximum", expression_tpe,
                                  procedural_expression_to_text(entry.u_max_expr), "Upper saturation bound."),)))
    elif isinstance(entry, TimeDelayLogic):
        fields.extend(list((make_procedural_field("output_var_name", "Output mode", mode_tpe, entry.output_var_name,
                                  "Retained delayed value."), make_procedural_field("source_expr", "Source expression", expression_tpe,
                                  procedural_expression_to_text(entry.source_expr), "Value stored in history."), make_procedural_field("delay_expr", "Delay", expression_tpe,
                                  procedural_expression_to_text(entry.delay_expr), "Non-negative delay in seconds."),)))
    elif isinstance(entry, MovingAverageLogic):
        fields.extend(list((make_procedural_field("output_var_name", "Output mode", mode_tpe, entry.output_var_name,
                                  "Retained averaged output."), make_procedural_field("source_expr", "Source expression", expression_tpe,
                                  procedural_expression_to_text(entry.source_expr), "Value stored in history."), make_procedural_field("delay_expr", "Delay", expression_tpe,
                                  procedural_expression_to_text(entry.delay_expr), "Delay before the averaging window."), make_procedural_field("window_expr", "Window", expression_tpe,
                                  procedural_expression_to_text(entry.window_expr), "Averaging-window duration."),)))
    elif isinstance(entry, GradientLimiterLogic):
        fields.extend(list((make_procedural_field("output_var_name", "Output mode", mode_tpe, entry.output_var_name,
                                  "Retained rate-limited output."), make_procedural_field("source_expr", "Source expression", expression_tpe,
                                  procedural_expression_to_text(entry.source_expr), "Requested value."), make_procedural_field("lower_rate_expr", "Lower rate", expression_tpe,
                                  procedural_expression_to_text(entry.lower_rate_expr), "Minimum slope."), make_procedural_field("upper_rate_expr", "Upper rate", expression_tpe,
                                  procedural_expression_to_text(entry.upper_rate_expr), "Maximum slope."),)))
    elif isinstance(entry, FlipFlopLogic):
        fields.extend(list((make_procedural_field("output_var_name", "Output mode", mode_tpe, entry.output_var_name,
                                  "Retained binary latch state."), make_procedural_field("set_expr", "Set condition", expression_tpe,
                                  procedural_expression_to_text(entry.set_expr), "Condition driving the latch high."), make_procedural_field("reset_expr", "Reset condition", expression_tpe,
                                  procedural_expression_to_text(entry.reset_expr), "Condition driving the latch low."),)))
    elif isinstance(entry, AnalogFlipFlopLogic):
        fields.extend(list((make_procedural_field("output_var_name", "Output mode", mode_tpe, entry.output_var_name,
                                  "Retained analog latch output."), make_procedural_field("input_expr", "Input expression", expression_tpe,
                                  procedural_expression_to_text(entry.input_expr), "Analog value captured on Set."), make_procedural_field("set_expr", "Set condition", expression_tpe,
                                  procedural_expression_to_text(entry.set_expr), "Capture condition."), make_procedural_field("reset_expr", "Reset condition", expression_tpe,
                                  procedural_expression_to_text(entry.reset_expr), "Release condition."),)))
    elif isinstance(entry, PickupDropoffLogic):
        fields.extend(list((make_procedural_field("output_var_name", "Output mode", mode_tpe, entry.output_var_name,
                                  "Retained relay state."), make_procedural_field("bool_expr", "Condition", expression_tpe,
                                  procedural_expression_to_text(entry.bool_expr), "Relay input condition."), make_procedural_field("pickup_delay_expr", "Pickup delay", expression_tpe,
                                  procedural_expression_to_text(entry.pickup_delay_expr), "Delay before activation."), make_procedural_field("drop_delay_expr", "Dropoff delay", expression_tpe,
                                  procedural_expression_to_text(entry.drop_delay_expr), "Delay before deactivation."),)))
    elif isinstance(entry, ResetOnRisingEdgeLogic):
        fields.extend(list((make_procedural_field("target_var_name", "Target", target_tpe, entry.target_var_name,
                                  "DAE variable or runtime parameter modified on the edge."), make_procedural_field("reset_expr", "Rising-edge condition", expression_tpe,
                                  procedural_expression_to_text(entry.reset_expr), "Edge detector input."), make_procedural_field("value_expr", "Reset value", expression_tpe,
                                  procedural_expression_to_text(entry.value_expr), "Value assigned on the rising edge."),)))
    elif isinstance(entry, DelayedThresholdLatchLogic):
        fields.extend(list((make_procedural_field("monitored_var_name", "Monitored variable", variable_tpe,
                                  entry.monitored_var_name, "DAE signal compared with the threshold."), make_procedural_field("mode_var_name", "Output mode", mode_tpe, entry.mode_var_name,
                                  "Retained trip mode."), make_procedural_field("threshold", "Threshold", ProceduralFieldType.FLOAT,
                                  str(entry.threshold), "Trip threshold."), make_procedural_field("delay", "Delay", ProceduralFieldType.FLOAT,
                                  str(entry.delay), "Non-negative trip delay."), make_procedural_field("reset_delay", "Reset delay", ProceduralFieldType.OPTIONAL_FLOAT,
                                  "" if entry.reset_delay is None else str(entry.reset_delay),
                                  "Optional non-negative automatic reset delay."),)))
    elif isinstance(entry, StartupHandoverLogic):
        fields.extend(list((make_procedural_field("mode_var_name", "Output mode", mode_tpe, entry.mode_var_name,
                                  "Retained startup/handover mode."), make_procedural_field("enable_time_var_name", "Enable-time parameter", runtime_tpe,
                                  entry.enable_time_var_name, "Runtime parameter containing the handover time."),)))
    elif isinstance(entry, ValveStateLogic):
        valve_fields: tuple[tuple[str, str, ProceduralFieldType, str, str], ...] = (
            ("mode_var_name", "Output mode", mode_tpe, entry.mode_var_name, "Retained conduction path."),
            ("valve_type_var_name", "Valve type", runtime_tpe, entry.valve_type_var_name, "Runtime valve type code."),
            ("gate_var_name", "Gate command", runtime_tpe, entry.gate_var_name, "Runtime gate command."),
            ("antiparallel_var_name", "Antiparallel enabled", runtime_tpe,
             entry.antiparallel_var_name, "Runtime reverse-path flag."),
            ("voltage_eps_var_name", "Voltage deadband", runtime_tpe,
             entry.voltage_eps_var_name, "Runtime voltage deadband."),
            ("current_eps_var_name", "Current deadband", runtime_tpe,
             entry.current_eps_var_name, "Runtime current deadband."),
            ("valve_voltage_var_name", "Valve voltage", variable_tpe,
             entry.valve_voltage_var_name, "Measured valve voltage."),
            ("valve_current_var_name", "Valve current", variable_tpe,
             entry.valve_current_var_name, "Measured valve current."),
        )
        valve_field: tuple[str, str, ProceduralFieldType, str, str]
        for valve_field in valve_fields:
            fields.append(make_procedural_field(valve_field[0], valve_field[1], valve_field[2],
                                                valve_field[3], valve_field[4]))
    elif isinstance(entry, ThreePhaseCarrierPwmLogic):
        pwm_fields: tuple[tuple[str, str, ProceduralFieldType, str], ...] = (
            ("mod_a_var_name", "Modulation A", variable_tpe, entry.mod_a_var_name),
            ("mod_b_var_name", "Modulation B", variable_tpe, entry.mod_b_var_name),
            ("mod_c_var_name", "Modulation C", variable_tpe, entry.mod_c_var_name),
            ("gate_a_mode_var_name", "Gate mode A", mode_tpe, entry.gate_a_mode_var_name),
            ("gate_b_mode_var_name", "Gate mode B", mode_tpe, entry.gate_b_mode_var_name),
            ("gate_c_mode_var_name", "Gate mode C", mode_tpe, entry.gate_c_mode_var_name),
            ("omega_sw_var_name", "Switching frequency", runtime_tpe, entry.omega_sw_var_name),
            ("carrier_phase_var_name", "Carrier phase", runtime_tpe, entry.carrier_phase_var_name),
        )
        pwm_field: tuple[str, str, ProceduralFieldType, str]
        for pwm_field in pwm_fields:
            fields.append(make_procedural_field(pwm_field[0], pwm_field[1], pwm_field[2],
                                                pwm_field[3], "Three-phase carrier PWM reference."))
    elif isinstance(entry, ThreePhaseCarrierSampledModulationLogic):
        sampled_fields: tuple[tuple[str, str, ProceduralFieldType, str], ...] = (
            ("mod_a_var_name", "Modulation A", variable_tpe, entry.mod_a_var_name),
            ("mod_b_var_name", "Modulation B", variable_tpe, entry.mod_b_var_name),
            ("mod_c_var_name", "Modulation C", variable_tpe, entry.mod_c_var_name),
            ("sample_a_mode_var_name", "Sample mode A", mode_tpe, entry.sample_a_mode_var_name),
            ("sample_b_mode_var_name", "Sample mode B", mode_tpe, entry.sample_b_mode_var_name),
            ("sample_c_mode_var_name", "Sample mode C", mode_tpe, entry.sample_c_mode_var_name),
            ("omega_sw_var_name", "Switching frequency", runtime_tpe, entry.omega_sw_var_name),
            ("carrier_phase_var_name", "Carrier phase", runtime_tpe, entry.carrier_phase_var_name),
        )
        sampled_field: tuple[str, str, ProceduralFieldType, str]
        for sampled_field in sampled_fields:
            fields.append(make_procedural_field(sampled_field[0], sampled_field[1], sampled_field[2],
                                                sampled_field[3], "Carrier-synchronized sampling reference."))
    else:
        raise ValueError(f"Unsupported procedural logic entry '{entry.__class__.__name__}'")
    return fields


def get_default_procedural_fields(logic_tpe: ProceduralLogicType) -> List[ProceduralFieldDraft]:
    """Return safe empty/default fields for a newly requested logic type.

    :param logic_tpe: Type selected by the user.
    :return: Typed default field list.
    """
    mode: ProceduralFieldType = ProceduralFieldType.MODE_REFERENCE
    expr: ProceduralFieldType = ProceduralFieldType.EXPRESSION
    variable: ProceduralFieldType = ProceduralFieldType.VARIABLE_REFERENCE
    runtime: ProceduralFieldType = ProceduralFieldType.RUNTIME_REFERENCE
    target: ProceduralFieldType = ProceduralFieldType.TARGET_REFERENCE
    fields: List[ProceduralFieldDraft] = list()
    if logic_tpe == ProceduralLogicType.ConditionalDiagnostic:
        fields = list((
            make_procedural_field(
                "condition_expr", "Condition", expr, "0.0",
                "Condition that activates the diagnostic.",
            ),
            make_procedural_field(
                "message", "Message", ProceduralFieldType.REQUIRED_TEXT, "",
                "Exact diagnostic text retained by the model.",
            ),
            make_procedural_field(
                "initialization_only", "Initialization only",
                ProceduralFieldType.BOOLEAN, "False",
                "Whether the diagnostic is restricted to initialization.",
            ),
        ))
    elif logic_tpe == ProceduralLogicType.DelayedSwitchEvent:
        fields = list((
            make_procedural_field(
                "output_var_name", "Output mode", mode, "",
                "Retained switch-position mode.",
            ),
            make_procedural_field(
                "guard_expr", "Guard", expr, "1.0",
                "Expression enabling trigger detection.",
            ),
            make_procedural_field(
                "trigger_expr", "Trigger", expr, "0.0",
                "Expression whose rising edge schedules the event.",
            ),
            make_procedural_field(
                "delay_expr", "Delay", expr, "0.0",
                "Non-negative delay evaluated when the trigger rises.",
            ),
            make_procedural_field(
                "target_device_idtag", "Target device identifier",
                ProceduralFieldType.REQUIRED_TEXT, "",
                "Exact physical equipment identifier.",
            ),
            make_procedural_field(
                "target_switch_idtag", "Target switch identifier",
                ProceduralFieldType.REQUIRED_TEXT, "",
                "Exact switch identifier.",
            ),
            make_procedural_field(
                "target_terminal_index", "Target terminal",
                ProceduralFieldType.INTEGER, "0",
                "Physical equipment terminal containing the switch.",
            ),
            make_procedural_field(
                "initial_closed", "Initially closed",
                ProceduralFieldType.BOOLEAN, "False",
                "Initial switch position.",
            ),
            make_procedural_field(
                "command_closed", "Command closed",
                ProceduralFieldType.BOOLEAN, "False",
                "Switch position applied when the event fires.",
            ),
        ))
    elif logic_tpe == ProceduralLogicType.FixedSample:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Retained boolean output."), make_procedural_field("condition_expr", "Condition", expr, "0.0", "Condition sampled once."),))
    elif logic_tpe == ProceduralLogicType.SampledValue:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Retained sampled output."), make_procedural_field("source_expr", "Source expression", expr, "0.0", "Expression sampled each step."),))
    elif logic_tpe == ProceduralLogicType.HardSaturation:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Retained saturated output."), make_procedural_field("u_expr", "Input expression", expr, "0.0", "Value to clamp."), make_procedural_field("u_min_expr", "Minimum", expr, "-1.0", "Lower bound."), make_procedural_field("u_max_expr", "Maximum", expr, "1.0", "Upper bound."),))
    elif logic_tpe == ProceduralLogicType.TimeDelay:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Retained delayed output."), make_procedural_field("source_expr", "Source expression", expr, "0.0", "History input."), make_procedural_field("delay_expr", "Delay", expr, "0.0", "Non-negative delay."),))
    elif logic_tpe == ProceduralLogicType.MovingAverage:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Retained average."), make_procedural_field("source_expr", "Source expression", expr, "0.0", "History input."), make_procedural_field("delay_expr", "Delay", expr, "0.0", "Delay before window."), make_procedural_field("window_expr", "Window", expr, "0.01", "Average window."),))
    elif logic_tpe == ProceduralLogicType.GradientLimiter:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Retained limited output."), make_procedural_field("source_expr", "Source expression", expr, "0.0", "Requested value."), make_procedural_field("lower_rate_expr", "Lower rate", expr, "-1.0", "Minimum slope."), make_procedural_field("upper_rate_expr", "Upper rate", expr, "1.0", "Maximum slope."),))
    elif logic_tpe == ProceduralLogicType.FlipFlop:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Binary latch output."), make_procedural_field("set_expr", "Set condition", expr, "0.0", "Set condition."), make_procedural_field("reset_expr", "Reset condition", expr, "0.0", "Reset condition."),))
    elif logic_tpe == ProceduralLogicType.AnalogFlipFlop:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Analog latch output."), make_procedural_field("input_expr", "Input expression", expr, "0.0", "Captured value."), make_procedural_field("set_expr", "Set condition", expr, "0.0", "Capture condition."), make_procedural_field("reset_expr", "Reset condition", expr, "0.0", "Release condition."),))
    elif logic_tpe == ProceduralLogicType.PickupDropoff:
        fields = list((make_procedural_field("output_var_name", "Output mode", mode, "", "Relay output."), make_procedural_field("bool_expr", "Condition", expr, "0.0", "Relay condition."), make_procedural_field("pickup_delay_expr", "Pickup delay", expr, "0.0", "Activation delay."), make_procedural_field("drop_delay_expr", "Dropoff delay", expr, "0.0", "Deactivation delay."),))
    elif logic_tpe == ProceduralLogicType.ResetOnRisingEdge:
        fields = list((make_procedural_field("target_var_name", "Target", target, "", "Mutable reset target."), make_procedural_field("reset_expr", "Rising-edge condition", expr, "0.0", "Edge input."), make_procedural_field("value_expr", "Reset value", expr, "0.0", "Assigned value."),))
    elif logic_tpe == ProceduralLogicType.DelayedThresholdLatch:
        fields = list((make_procedural_field("monitored_var_name", "Monitored variable", variable, "", "Compared DAE signal."), make_procedural_field("mode_var_name", "Output mode", mode, "", "Retained trip mode."), make_procedural_field("threshold", "Threshold", ProceduralFieldType.FLOAT, "0.0", "Trip threshold."), make_procedural_field("delay", "Delay", ProceduralFieldType.FLOAT, "0.0", "Trip delay."), make_procedural_field("reset_delay", "Reset delay", ProceduralFieldType.OPTIONAL_FLOAT, "",
                                  "Optional automatic reset delay."),))
    elif logic_tpe == ProceduralLogicType.StartupHandover:
        fields = list((make_procedural_field("mode_var_name", "Output mode", mode, "", "Handover mode."), make_procedural_field("enable_time_var_name", "Enable-time parameter", runtime, "", "Handover time."),))
    elif logic_tpe == ProceduralLogicType.ValveState:
        valve_defaults: tuple[tuple[str, str, ProceduralFieldType], ...] = (
            ("mode_var_name", "Output mode", mode),
            ("valve_type_var_name", "Valve type", runtime),
            ("gate_var_name", "Gate command", runtime),
            ("antiparallel_var_name", "Antiparallel enabled", runtime),
            ("voltage_eps_var_name", "Voltage deadband", runtime),
            ("current_eps_var_name", "Current deadband", runtime),
            ("valve_voltage_var_name", "Valve voltage", variable),
            ("valve_current_var_name", "Valve current", variable),
        )
        valve_default: tuple[str, str, ProceduralFieldType]
        for valve_default in valve_defaults:
            fields.append(make_procedural_field(valve_default[0], valve_default[1], valve_default[2], "",
                                                "Required valve-state reference."))
    elif logic_tpe in (
        ProceduralLogicType.ThreePhaseCarrierPwm,
        ProceduralLogicType.ThreePhaseCarrierSampledModulation,
    ):
        sampled: bool = logic_tpe == ProceduralLogicType.ThreePhaseCarrierSampledModulation
        phase_prefix: str = "sample" if sampled else "gate"
        phase_fields: tuple[tuple[str, str, ProceduralFieldType], ...] = (
            ("mod_a_var_name", "Modulation A", variable),
            ("mod_b_var_name", "Modulation B", variable),
            ("mod_c_var_name", "Modulation C", variable),
            (f"{phase_prefix}_a_mode_var_name", f"{phase_prefix.title()} mode A", mode),
            (f"{phase_prefix}_b_mode_var_name", f"{phase_prefix.title()} mode B", mode),
            (f"{phase_prefix}_c_mode_var_name", f"{phase_prefix.title()} mode C", mode),
            ("omega_sw_var_name", "Switching frequency", runtime),
            ("carrier_phase_var_name", "Carrier phase", runtime),
        )
        phase_field: tuple[str, str, ProceduralFieldType]
        for phase_field in phase_fields:
            fields.append(make_procedural_field(phase_field[0], phase_field[1], phase_field[2], "",
                                                "Required three-phase carrier reference."))
    else:
        raise ValueError(f"Unsupported procedural logic type '{logic_tpe.value}'")
    return fields


def get_procedural_code_field_pairs(
        logic_tpe: ProceduralLogicType,
) -> List[tuple[str, str]]:
    """Return readable code keywords paired with stable Engine field keys.

    The editor language deliberately exposes behavioral names such as
    ``condition`` and ``output`` while the persistent Engine classes retain
    their existing attribute names. Keeping the translation in one function
    prevents the serializer and parser from drifting independently.

    :param logic_tpe: Procedural entry type represented in Python code.
    :return: Ordered ``(code keyword, field key)`` pairs.
    """
    if logic_tpe == ProceduralLogicType.ConditionalDiagnostic:
        pairs: List[tuple[str, str]] = list((
            ("condition", "condition_expr"),
            ("message", "message"),
            ("initialization_only", "initialization_only"),
        ))
    elif logic_tpe == ProceduralLogicType.DelayedSwitchEvent:
        pairs = list((
            ("output", "output_var_name"),
            ("guard", "guard_expr"),
            ("trigger", "trigger_expr"),
            ("delay", "delay_expr"),
            ("target_device_id", "target_device_idtag"),
            ("target_switch_id", "target_switch_idtag"),
            ("target_terminal", "target_terminal_index"),
            ("initial_closed", "initial_closed"),
            ("command_closed", "command_closed"),
        ))
    elif logic_tpe == ProceduralLogicType.FixedSample:
        pairs = list((("output", "output_var_name"), ("condition", "condition_expr")))
    elif logic_tpe == ProceduralLogicType.SampledValue:
        pairs = list((("output", "output_var_name"), ("source", "source_expr")))
    elif logic_tpe == ProceduralLogicType.HardSaturation:
        pairs = list((
            ("output", "output_var_name"),
            ("input", "u_expr"),
            ("minimum", "u_min_expr"),
            ("maximum", "u_max_expr"),
        ))
    elif logic_tpe == ProceduralLogicType.TimeDelay:
        pairs = list((
            ("output", "output_var_name"),
            ("source", "source_expr"),
            ("delay", "delay_expr"),
        ))
    elif logic_tpe == ProceduralLogicType.MovingAverage:
        pairs = list((
            ("output", "output_var_name"),
            ("source", "source_expr"),
            ("delay", "delay_expr"),
            ("window", "window_expr"),
        ))
    elif logic_tpe == ProceduralLogicType.GradientLimiter:
        pairs = list((
            ("output", "output_var_name"),
            ("source", "source_expr"),
            ("lower_rate", "lower_rate_expr"),
            ("upper_rate", "upper_rate_expr"),
        ))
    elif logic_tpe == ProceduralLogicType.FlipFlop:
        pairs = list((
            ("output", "output_var_name"),
            ("set_condition", "set_expr"),
            ("reset_condition", "reset_expr"),
        ))
    elif logic_tpe == ProceduralLogicType.AnalogFlipFlop:
        pairs = list((
            ("output", "output_var_name"),
            ("input", "input_expr"),
            ("set_condition", "set_expr"),
            ("reset_condition", "reset_expr"),
        ))
    elif logic_tpe == ProceduralLogicType.PickupDropoff:
        pairs = list((
            ("output", "output_var_name"),
            ("condition", "bool_expr"),
            ("pickup_delay", "pickup_delay_expr"),
            ("dropoff_delay", "drop_delay_expr"),
        ))
    elif logic_tpe == ProceduralLogicType.ResetOnRisingEdge:
        pairs = list((
            ("target", "target_var_name"),
            ("condition", "reset_expr"),
            ("value", "value_expr"),
        ))
    elif logic_tpe == ProceduralLogicType.DelayedThresholdLatch:
        pairs = list((
            ("monitored", "monitored_var_name"),
            ("output", "mode_var_name"),
            ("threshold", "threshold"),
            ("delay", "delay"),
            ("reset_delay", "reset_delay"),
        ))
    elif logic_tpe == ProceduralLogicType.StartupHandover:
        pairs = list((
            ("output", "mode_var_name"),
            ("enable_time", "enable_time_var_name"),
        ))
    elif logic_tpe == ProceduralLogicType.ValveState:
        pairs = list((
            ("output", "mode_var_name"),
            ("valve_type", "valve_type_var_name"),
            ("gate", "gate_var_name"),
            ("antiparallel", "antiparallel_var_name"),
            ("voltage_epsilon", "voltage_eps_var_name"),
            ("current_epsilon", "current_eps_var_name"),
            ("valve_voltage", "valve_voltage_var_name"),
            ("valve_current", "valve_current_var_name"),
        ))
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierPwm:
        pairs = list((
            ("modulation_a", "mod_a_var_name"),
            ("modulation_b", "mod_b_var_name"),
            ("modulation_c", "mod_c_var_name"),
            ("gate_a", "gate_a_mode_var_name"),
            ("gate_b", "gate_b_mode_var_name"),
            ("gate_c", "gate_c_mode_var_name"),
            ("switching_frequency", "omega_sw_var_name"),
            ("carrier_phase", "carrier_phase_var_name"),
        ))
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierSampledModulation:
        pairs = list((
            ("modulation_a", "mod_a_var_name"),
            ("modulation_b", "mod_b_var_name"),
            ("modulation_c", "mod_c_var_name"),
            ("sample_a", "sample_a_mode_var_name"),
            ("sample_b", "sample_b_mode_var_name"),
            ("sample_c", "sample_c_mode_var_name"),
            ("switching_frequency", "omega_sw_var_name"),
            ("carrier_phase", "carrier_phase_var_name"),
        ))
    else:
        raise ValueError(f"Unsupported procedural logic type '{logic_tpe.value}'")
    return pairs


def get_procedural_logic_type_from_code_name(code_name: str) -> ProceduralLogicType:
    """Resolve one whitelisted procedural function name.

    :param code_name: Function identifier written in ``procedural_logic``.
    :return: Matching concrete procedural type.
    :raises ValueError: If the function is unknown or represents the abstract base type.
    """
    result: ProceduralLogicType | None = None
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        if descriptor.logic_tpe.value == code_name:
            result = descriptor.logic_tpe
        else:
            pass
    if result is None:
        raise ValueError(f"Unsupported procedural logic function '{code_name}'")
    else:
        return result


def get_procedural_field_by_key(
        fields: Sequence[ProceduralFieldDraft],
        field_key: str,
) -> ProceduralFieldDraft:
    """Return one required field from an ordered procedural specification.

    :param fields: Available typed fields.
    :param field_key: Stable field key to locate.
    :return: Matching field.
    :raises ValueError: If the specification and field mapping disagree.
    """
    result: ProceduralFieldDraft | None = None
    field: ProceduralFieldDraft
    for field in fields:
        if field.get_key() == field_key:
            result = field
        else:
            pass
    if result is None:
        raise ValueError(f"Unknown procedural field '{field_key}'")
    else:
        return result


def serialize_procedural_code_field(field: ProceduralFieldDraft) -> str:
    """Serialize one typed field as safe Python-like source.

    :param field: Field whose staged value is serialized.
    :return: Source accepted by the procedural parser.
    """
    field_tpe: ProceduralFieldType = field.get_tpe()
    value: str = field.get_value()
    if field_tpe == ProceduralFieldType.EXPRESSION:
        result: str = value
    elif field_tpe in (
            ProceduralFieldType.MODE_REFERENCE,
            ProceduralFieldType.VARIABLE_REFERENCE,
            ProceduralFieldType.RUNTIME_REFERENCE,
            ProceduralFieldType.TARGET_REFERENCE):
        # Most references are ordinary identifiers and remain concise. Legacy
        # catalogue models can retain descriptive Engine names containing
        # spaces or punctuation, which must be quoted to keep the generated
        # model source syntactically valid and lossless.
        if value.isidentifier() and not keyword.iskeyword(value):
            result = value
        else:
            result = repr(value)
    elif field_tpe in (
            ProceduralFieldType.FLOAT,
            ProceduralFieldType.INTEGER,
            ProceduralFieldType.BOOLEAN):
        result = value
    elif field_tpe == ProceduralFieldType.OPTIONAL_FLOAT:
        result = "None" if len(value) == 0 else value
    elif field_tpe in (ProceduralFieldType.TEXT, ProceduralFieldType.REQUIRED_TEXT):
        result = repr(value)
    else:
        raise ValueError(f"Unsupported procedural field type '{field_tpe.value}'")
    return result


def get_procedural_logic_summary(logic_tpe: ProceduralLogicType) -> str:
    """Return concise user-facing behavior help for one procedural type.

    :param logic_tpe: Concrete procedural type.
    :return: One-sentence behavioral summary.
    """
    if logic_tpe == ProceduralLogicType.ConditionalDiagnostic:
        result: str = "Preserve a conditional source-model diagnostic."
    elif logic_tpe == ProceduralLogicType.DelayedSwitchEvent:
        result = "Schedule one delayed switch command on a guarded rising edge."
    elif logic_tpe == ProceduralLogicType.FixedSample:
        result = "Sample a condition once during initialization and retain it."
    elif logic_tpe == ProceduralLogicType.SampledValue:
        result = "Sample an expression after each accepted solver step."
    elif logic_tpe == ProceduralLogicType.HardSaturation:
        result = "Clamp an expression between dynamic minimum and maximum bounds."
    elif logic_tpe == ProceduralLogicType.TimeDelay:
        result = "Return an accepted-step source value after a configurable delay."
    elif logic_tpe == ProceduralLogicType.MovingAverage:
        result = "Average accepted source history over a delayed time window."
    elif logic_tpe == ProceduralLogicType.GradientLimiter:
        result = "Limit the accepted-step rate of change of a source expression."
    elif logic_tpe == ProceduralLogicType.FlipFlop:
        result = "Retain a Boolean latch controlled by set and reset conditions."
    elif logic_tpe == ProceduralLogicType.AnalogFlipFlop:
        result = "Capture and retain an analog value under set and reset conditions."
    elif logic_tpe == ProceduralLogicType.PickupDropoff:
        result = "Apply independent pickup and dropoff delays to a relay condition."
    elif logic_tpe == ProceduralLogicType.ResetOnRisingEdge:
        result = "Assign a value to a mutable target when a condition rises."
    elif logic_tpe == ProceduralLogicType.DelayedThresholdLatch:
        result = "Latch a threshold crossing after a fixed delay."
    elif logic_tpe == ProceduralLogicType.StartupHandover:
        result = "Switch a retained startup mode at a configured enable time."
    elif logic_tpe == ProceduralLogicType.ValveState:
        result = "Update a retained valve conduction state from gate and electrical signals."
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierPwm:
        result = "Generate three retained PWM gate states from carrier comparisons."
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierSampledModulation:
        result = "Sample three modulation references at carrier boundaries."
    else:
        raise ValueError(f"Unsupported procedural logic type '{logic_tpe.value}'")
    return result


def get_procedural_logic_signature(logic_tpe: ProceduralLogicType) -> str:
    """Build the readable keyword-only signature shown by completion.

    :param logic_tpe: Concrete procedural type.
    :return: Function-like signature using the editor's public keywords.
    """
    argument_labels: List[str] = list()
    code_keyword: str
    _field_key: str
    for code_keyword, _field_key in get_procedural_code_field_pairs(logic_tpe):
        argument_labels.append(f"{code_keyword}=...")
    argument_labels.append("name=''")
    return f"{logic_tpe.value}({', '.join(argument_labels)})"


def get_procedural_logic_help(logic_tpe: ProceduralLogicType) -> str:
    """Build multiline signature and argument help for popup and hover use.

    :param logic_tpe: Concrete procedural type.
    :return: Plain-text documentation suitable for a Qt tooltip.
    """
    fields: List[ProceduralFieldDraft] = get_default_procedural_fields(logic_tpe)
    lines: List[str] = list((
        get_procedural_logic_signature(logic_tpe),
        "",
        get_procedural_logic_summary(logic_tpe),
        "",
        "Named arguments:",
    ))
    code_keyword: str
    field_key: str
    for code_keyword, field_key in get_procedural_code_field_pairs(logic_tpe):
        field: ProceduralFieldDraft = get_procedural_field_by_key(fields, field_key)
        lines.append(f"  {code_keyword}: {field.get_description()}")
    lines.append("  name: Optional descriptive label for validation and diagnostics.")
    lines.append("")
    lines.append(
        "List order is preserved; each type runs at its Engine-defined update phase."
    )
    return "\n".join(lines)


def get_procedural_logic_help_by_code_name(code_name: str) -> str | None:
    """Return tooltip help when a token is a concrete procedural function.

    :param code_name: Identifier under the editor cursor.
    :return: Complete help text or ``None`` for a non-procedural identifier.
    """
    result: str | None = None
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        if descriptor.logic_tpe.value == code_name:
            result = get_procedural_logic_help(descriptor.logic_tpe)
        else:
            pass
    return result


def get_procedural_code_field_type(
        logic_tpe: ProceduralLogicType,
        code_keyword: str,
) -> ProceduralFieldType | None:
    """Return the semantic field type represented by one public keyword.

    :param logic_tpe: Active procedural call type.
    :param code_keyword: Named argument currently being edited.
    :return: Field type or ``None`` for ``name`` and unknown arguments.
    """
    result: ProceduralFieldType | None = None
    fields: List[ProceduralFieldDraft] = get_default_procedural_fields(logic_tpe)
    mapped_keyword: str
    field_key: str
    for mapped_keyword, field_key in get_procedural_code_field_pairs(logic_tpe):
        if mapped_keyword == code_keyword:
            field: ProceduralFieldDraft = get_procedural_field_by_key(fields, field_key)
            result = field.get_tpe()
        else:
            pass
    return result


def get_procedural_template_field_source(
        field: ProceduralFieldDraft,
) -> tuple[str, str | None]:
    """Return readable starter source and its replaceable placeholder token.

    :param field: Typed default field represented by the template.
    :return: Source fragment and first-edit placeholder, when applicable.
    """
    field_tpe: ProceduralFieldType = field.get_tpe()
    if field_tpe in (
            ProceduralFieldType.MODE_REFERENCE,
            ProceduralFieldType.VARIABLE_REFERENCE,
            ProceduralFieldType.RUNTIME_REFERENCE,
            ProceduralFieldType.TARGET_REFERENCE,
    ):
        # A reference cannot be inferred safely from the available symbols.
        # ``None`` keeps the template valid Python without inventing a model
        # identity, and is selected immediately so completion can replace it.
        source: str = "None"
        placeholder = source
    elif field_tpe == ProceduralFieldType.REQUIRED_TEXT:
        if field.get_key() == "message":
            placeholder = "diagnostic message"
        elif field.get_key() == "target_device_idtag":
            placeholder = "device_id"
        elif field.get_key() == "target_switch_idtag":
            placeholder = "switch_id"
        else:
            placeholder = "required text"
        source = repr(placeholder)
    else:
        source = serialize_procedural_code_field(field)
        placeholder = None
    return source, placeholder


def build_procedural_logic_call_lines(
        logic_tpe: ProceduralLogicType,
) -> tuple[List[str], str | None]:
    """Build one complete reusable procedural-call template.

    Returned lines are relative to the call indentation: the first and closing
    lines have no leading spaces, while named arguments use four spaces. Both
    toolbar insertion and code completion add the surrounding list indentation.

    :param logic_tpe: Concrete type selected by the user.
    :return: Relative source lines and the first token that should be selected.
    """
    fields: List[ProceduralFieldDraft] = get_default_procedural_fields(logic_tpe)
    lines: List[str] = list((f"{logic_tpe.value}(",))
    first_placeholder: str | None = None
    code_keyword: str
    field_key: str
    for code_keyword, field_key in get_procedural_code_field_pairs(logic_tpe):
        field: ProceduralFieldDraft = get_procedural_field_by_key(fields, field_key)
        field_source: str
        placeholder: str | None
        field_source, placeholder = get_procedural_template_field_source(field)
        lines.append(f"    {code_keyword}={field_source},")
        if first_placeholder is None and placeholder is not None:
            first_placeholder = placeholder
        else:
            pass
    entry_name: str = logic_tpe.value.replace("_", " ")
    lines.append(f"    name={entry_name!r},")
    lines.append("),")
    return lines, first_placeholder


def build_runtime_logic_code(block: Block) -> List[str]:
    """Serialize retained modes and ordered procedural entries for one block.

    :param block: Direct owner represented by one Python-code buffer.
    :return: Readable source lines for the two runtime sections.
    """
    lines: List[str] = list((
        "retained_modes = {",
        "    # Map each retained mode to its symbolic initialization expression.",
        "    # Example: latched_value: 0.0,",
    ))
    mode_variable: Var
    initial_expression: Expr
    for mode_variable, initial_expression in block.mode_dict.items():
        lines.append(
            f"    {mode_variable.name}: {procedural_expression_to_text(initial_expression)},"
        )
    lines.append("}")
    lines.append("")
    lines.append("procedural_logic = [")
    lines.append("    # List order is preserved; each type runs at its Engine-defined update phase.")
    lines.append("    # Use Add procedural logic above to insert a complete editable call.")
    editable_types: set[ProceduralLogicType] = set()
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        editable_types.add(descriptor.logic_tpe)
    entry: ProceduralLogicBase
    for entry in block.procedural_logic:
        logic_tpe: ProceduralLogicType = entry.logic_tpe
        if logic_tpe in editable_types:
            fields: List[ProceduralFieldDraft] = get_procedural_fields(entry)
            lines.append(f"    {logic_tpe.value}(")
            code_keyword: str
            field_key: str
            for code_keyword, field_key in get_procedural_code_field_pairs(logic_tpe):
                field: ProceduralFieldDraft = get_procedural_field_by_key(fields, field_key)
                lines.append(
                    f"        {code_keyword}={serialize_procedural_code_field(field)},"
                )
            lines.append(f"        name={entry.name!r},")
            lines.append("    ),")
        else:
            # Provider-owned entries remain attached to the Block while this
            # source view exposes only catalogue entries that users can edit.
            lines.append(
                f"    # Internal {logic_tpe.value} entry is preserved outside editable source."
            )
    lines.append("]")
    return lines


def parse_model_code_module(code: str) -> tuple[str, ast.Module]:
    """Parse a complete model-code buffer after normalizing DAE equalities.

    :param code: Complete Python-like block source.
    :return: Normalized source and its AST module.
    :raises ValueError: If the source is not syntactically valid.
    """
    normalized_code: str = normalize_algebraic_equality_syntax(code)
    try:
        module: ast.Module = ast.parse(normalized_code, mode="exec")
    except SyntaxError as error:
        raise ValueError(str(error)) from error
    return normalized_code, module


def get_model_code_assignment(module: ast.Module, section_name: str) -> ast.Assign:
    """Return one unique top-level assignment from a model-code module.

    :param module: Parsed complete model-code module.
    :param section_name: Required assignment name.
    :return: Matching assignment.
    :raises ValueError: If the section is missing or duplicated.
    """
    result: ast.Assign | None = None
    statement: ast.stmt
    for statement in module.body:
        if (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == section_name
        ):
            if result is None:
                result = statement
            else:
                raise ValueError(f"Section '{section_name}' is assigned more than once")
        else:
            pass
    if result is None:
        raise ValueError(f"Missing required model section '{section_name}'")
    else:
        return result


def find_model_code_assignment(module: ast.Module, section_name: str) -> ast.Assign | None:
    """Find one optional unique top-level model assignment.

    :param module: Parsed complete model-code module.
    :param section_name: Optional assignment name.
    :return: Matching assignment or ``None`` when legacy source omits it.
    :raises ValueError: If the section is duplicated.
    """
    result: ast.Assign | None = None
    statement: ast.stmt
    for statement in module.body:
        matches: bool = (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == section_name
        )
        if matches and isinstance(statement, ast.Assign):
            if result is None:
                result = statement
            else:
                raise ValueError(f"Section '{section_name}' is assigned more than once")
        else:
            pass
    return result


def get_ast_source_segment(source: str, node: ast.AST) -> str:
    """Return the exact normalized source represented by one AST node.

    :param source: Normalized complete source.
    :param node: AST node whose text is requested.
    :return: Non-empty source segment.
    :raises ValueError: If Python cannot recover the node text.
    """
    segment: str | None = ast.get_source_segment(source, node)
    if segment is None or len(segment.strip()) == 0:
        raise ValueError("Unable to read procedural source expression")
    else:
        return segment.strip()


def find_existing_mode_by_name(owner: Block, mode_name: str) -> Var | None:
    """Find one retained mode owned directly by a block.

    :param owner: Direct block owner.
    :param mode_name: Mode name written in source.
    :return: Existing mode variable or ``None`` for a new declaration.
    """
    result: Var | None = None
    mode_variable: Var
    for mode_variable in owner.mode_dict:
        if mode_variable.name == mode_name:
            result = mode_variable
        else:
            pass
    return result


def parse_retained_mode_drafts(code: str, owner: Block) -> List[RuntimeModeDraft]:
    """Parse retained-mode declarations without evaluating initialization expressions.

    Existing identities are first matched by name. A single unmatched old and
    new declaration is treated as an in-place rename so its UID is retained.
    More than one simultaneous ambiguous replacement is rejected rather than
    silently exchanging identities.

    :param code: Complete source for ``owner``.
    :param owner: Direct owner of the parsed modes.
    :return: Ordered retained-mode drafts.
    """
    normalized_code: str
    module: ast.Module
    normalized_code, module = parse_model_code_module(code)
    assignment_optional: ast.Assign | None = find_model_code_assignment(
        module,
        "retained_modes",
    )
    if assignment_optional is None:
        legacy_drafts: List[RuntimeModeDraft] = list()
        legacy_variable: Var
        legacy_initial: Expr
        for legacy_variable, legacy_initial in owner.mode_dict.items():
            legacy_drafts.append(RuntimeModeDraft(
                owner=owner,
                variable=legacy_variable,
                name=legacy_variable.name,
                initial_expression=procedural_expression_to_text(legacy_initial),
            ))
        return legacy_drafts
    else:
        assignment: ast.Assign = assignment_optional
    if not isinstance(assignment.value, ast.Dict):
        raise ValueError("Section 'retained_modes' must be a dictionary")
    else:
        pass

    declared_names: List[str] = list()
    declared_initials: List[str] = list()
    entry_index: int
    for entry_index in range(len(assignment.value.keys)):
        key_node: ast.expr | None = assignment.value.keys[entry_index]
        value_node: ast.expr = assignment.value.values[entry_index]
        if not isinstance(key_node, ast.Name):
            raise ValueError("Keys in 'retained_modes' must be mode names")
        elif key_node.id in declared_names:
            raise ValueError(f"Retained mode '{key_node.id}' is declared more than once")
        else:
            declared_names.append(key_node.id)
            declared_initials.append(get_ast_source_segment(normalized_code, value_node))

    drafts: List[RuntimeModeDraft] = list()
    unmatched_declaration_indexes: List[int] = list()
    matched_existing_uids: set[int] = set()
    declaration_index: int
    for declaration_index in range(len(declared_names)):
        declared_name: str = declared_names[declaration_index]
        existing_variable: Var | None = find_existing_mode_by_name(owner, declared_name)
        if existing_variable is not None:
            matched_existing_uids.add(existing_variable.uid)
            drafts.append(RuntimeModeDraft(
                owner=owner,
                variable=existing_variable,
                name=declared_name,
                initial_expression=declared_initials[declaration_index],
            ))
        else:
            unmatched_declaration_indexes.append(declaration_index)

    unmatched_existing: List[Var] = list()
    existing_variable: Var
    for existing_variable in owner.mode_dict:
        if existing_variable.uid not in matched_existing_uids:
            unmatched_existing.append(existing_variable)
        else:
            pass

    if len(unmatched_declaration_indexes) == 1 and len(unmatched_existing) == 1:
        renamed_index: int = unmatched_declaration_indexes[0]
        drafts.append(RuntimeModeDraft(
            owner=owner,
            variable=unmatched_existing[0],
            name=declared_names[renamed_index],
            initial_expression=declared_initials[renamed_index],
        ))
    elif len(unmatched_declaration_indexes) > 0 and len(unmatched_existing) > 0:
        raise ValueError(
            f"Block '{owner.name}' has ambiguous retained-mode additions, deletions, or renames; "
            "apply one rename separately"
        )
    else:
        for declaration_index in unmatched_declaration_indexes:
            drafts.append(RuntimeModeDraft(
                owner=owner,
                variable=None,
                name=declared_names[declaration_index],
                initial_expression=declared_initials[declaration_index],
            ))

    # Restore the exact source order after matching existing identities.
    ordered_drafts: List[RuntimeModeDraft] = list()
    for declared_name in declared_names:
        matching_draft: RuntimeModeDraft | None = None
        draft: RuntimeModeDraft
        for draft in drafts:
            if draft.get_name() == declared_name:
                matching_draft = draft
            else:
                pass
        if matching_draft is None:
            raise ValueError(f"Unable to bind retained mode '{declared_name}'")
        else:
            ordered_drafts.append(matching_draft)
    return ordered_drafts


def parse_procedural_field_source(
        source: str,
        node: ast.expr,
        field: ProceduralFieldDraft,
) -> str:
    """Convert one whitelisted call argument into its typed draft text.

    :param source: Normalized complete model source.
    :param node: Keyword value AST node.
    :param field: Typed destination field.
    :return: Text consumed by the existing runtime validator.
    """
    field_tpe: ProceduralFieldType = field.get_tpe()
    if field_tpe in (
            ProceduralFieldType.MODE_REFERENCE,
            ProceduralFieldType.VARIABLE_REFERENCE,
            ProceduralFieldType.RUNTIME_REFERENCE,
            ProceduralFieldType.TARGET_REFERENCE,
    ):
        if isinstance(node, ast.Name):
            result: str = node.id
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            result = node.value
        else:
            raise ValueError(
                f"'{field.get_label()}' must be a symbol name or quoted Engine name"
            )
    elif field_tpe == ProceduralFieldType.EXPRESSION:
        result = get_ast_source_segment(source, node)
    elif field_tpe in (ProceduralFieldType.FLOAT, ProceduralFieldType.INTEGER):
        result = get_ast_source_segment(source, node)
    elif field_tpe == ProceduralFieldType.OPTIONAL_FLOAT:
        if isinstance(node, ast.Constant) and node.value is None:
            result = ""
        else:
            result = get_ast_source_segment(source, node)
    elif field_tpe in (ProceduralFieldType.TEXT, ProceduralFieldType.REQUIRED_TEXT):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            result = node.value
        else:
            raise ValueError(f"'{field.get_label()}' must be quoted text")
    elif field_tpe == ProceduralFieldType.BOOLEAN:
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            result = str(node.value)
        else:
            raise ValueError(f"'{field.get_label()}' must be True or False")
    else:
        raise ValueError(f"Unsupported procedural field type '{field_tpe.value}'")
    return result


def parse_procedural_logic_drafts(code: str, owner: Block) -> List[ProceduralLogicDraft]:
    """Parse one ordered, whitelisted ``procedural_logic`` list.

    :param code: Complete source for ``owner``.
    :param owner: Direct owner of the parsed entries.
    :return: Ordered typed entry drafts.
    """
    normalized_code: str
    module: ast.Module
    normalized_code, module = parse_model_code_module(code)
    assignment_optional: ast.Assign | None = find_model_code_assignment(
        module,
        "procedural_logic",
    )
    if assignment_optional is None:
        legacy_entries: List[ProceduralLogicDraft] = list()
        legacy_entry: ProceduralLogicBase
        for legacy_entry in owner.procedural_logic:
            legacy_entries.append(ProceduralLogicDraft(
                owner=owner,
                logic_tpe=legacy_entry.logic_tpe,
                name=legacy_entry.name,
                fields=get_procedural_fields(legacy_entry),
                original=legacy_entry,
            ))
        return legacy_entries
    else:
        assignment: ast.Assign = assignment_optional
    if not isinstance(assignment.value, ast.List):
        raise ValueError("Section 'procedural_logic' must be a list")
    else:
        pass

    result: List[ProceduralLogicDraft] = list()
    entry_index: int
    element: ast.expr
    for entry_index, element in enumerate(assignment.value.elts):
        if not isinstance(element, ast.Call) or not isinstance(element.func, ast.Name):
            raise ValueError("Entries in 'procedural_logic' must be named function calls")
        elif len(element.args) > 0:
            raise ValueError("Procedural logic calls accept keyword arguments only")
        else:
            logic_tpe: ProceduralLogicType = get_procedural_logic_type_from_code_name(
                element.func.id
            )

        fields: List[ProceduralFieldDraft] = get_default_procedural_fields(logic_tpe)
        code_pairs: List[tuple[str, str]] = get_procedural_code_field_pairs(logic_tpe)
        entry_name: str = ""
        provided_keywords: set[str] = set()
        keyword: ast.keyword
        for keyword in element.keywords:
            if keyword.arg is None:
                raise ValueError("Procedural logic does not accept unpacked keyword arguments")
            elif keyword.arg in provided_keywords:
                raise ValueError(
                    f"Argument '{keyword.arg}' is repeated in '{logic_tpe.value}'"
                )
            else:
                provided_keywords.add(keyword.arg)

            if keyword.arg == "name":
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    entry_name = keyword.value.value
                else:
                    raise ValueError("Procedural entry 'name' must be quoted text")
            else:
                matching_field_key: str | None = None
                code_keyword: str
                field_key: str
                for code_keyword, field_key in code_pairs:
                    if code_keyword == keyword.arg:
                        matching_field_key = field_key
                    else:
                        pass
                if matching_field_key is None:
                    raise ValueError(
                        f"Unknown argument '{keyword.arg}' for '{logic_tpe.value}'"
                    )
                else:
                    field: ProceduralFieldDraft = get_procedural_field_by_key(
                        fields,
                        matching_field_key,
                    )
                    field.set_value(parse_procedural_field_source(
                        normalized_code,
                        keyword.value,
                        field,
                    ))

        code_keyword: str
        field_key: str
        for code_keyword, field_key in code_pairs:
            if code_keyword not in provided_keywords:
                raise ValueError(
                    f"Missing argument '{code_keyword}' for '{logic_tpe.value}'"
                )
            else:
                pass

        original: ProceduralLogicBase | None = None
        if entry_index < len(owner.procedural_logic):
            candidate_original: object = owner.procedural_logic[entry_index]
            if (
                    isinstance(candidate_original, ProceduralLogicBase)
                    and candidate_original.logic_tpe == logic_tpe
            ):
                original = candidate_original
            else:
                pass
        else:
            pass
        result.append(ProceduralLogicDraft(
            owner=owner,
            logic_tpe=logic_tpe,
            name=entry_name,
            fields=fields,
            original=original,
        ))
    return result


def build_runtime_code_signature(code: str) -> str:
    """Return a formatting-independent signature of both runtime sections.

    :param code: Complete block model source.
    :return: AST signature used to avoid rebuilding unchanged runtime objects.
    """
    _normalized_code: str
    module: ast.Module
    _normalized_code, module = parse_model_code_module(code)
    mode_assignment: ast.Assign | None = find_model_code_assignment(module, "retained_modes")
    logic_assignment: ast.Assign | None = find_model_code_assignment(module, "procedural_logic")
    mode_signature: str = "<missing retained_modes>"
    logic_signature: str = "<missing procedural_logic>"
    if mode_assignment is not None:
        mode_signature = ast.dump(mode_assignment, include_attributes=False)
    else:
        pass
    if logic_assignment is not None:
        logic_signature = ast.dump(logic_assignment, include_attributes=False)
    else:
        pass
    return mode_signature + logic_signature


def get_procedural_expression_variables(entry: ProceduralLogicBase) -> List[Var]:
    """Return every symbolic variable read by one runtime-logic entry.

    Runtime expressions may legitimately reference simulation-owned symbols
    that are not exposed in the block's DAE collections. The properties
    dialogue needs those exact ``Var`` identities in its parser namespace so
    opening and reapplying an existing catalogue model is lossless.

    :param entry: Existing procedural-logic entry.
    :return: Variables referenced by its symbolic expression fields.
    """
    expressions: List[Expr | Comparison | float | int] = list()
    if isinstance(entry, ConditionalDiagnosticLogic):
        expressions.append(entry.condition_expr)
    elif isinstance(entry, DelayedSwitchEventLogic):
        expressions.extend(list((
            entry.guard_expr,
            entry.trigger_expr,
            entry.delay_expr,
        )))
    elif isinstance(entry, FixedSampleLogic):
        expressions.append(entry.condition_expr)
    elif isinstance(entry, SampledValueLogic):
        expressions.append(entry.source_expr)
    elif isinstance(entry, HardSaturationLogic):
        expressions.extend(list((entry.u_expr, entry.u_min_expr, entry.u_max_expr,)))
    elif isinstance(entry, TimeDelayLogic):
        expressions.extend(list((entry.source_expr, entry.delay_expr,)))
    elif isinstance(entry, MovingAverageLogic):
        expressions.extend(list((entry.source_expr, entry.delay_expr, entry.window_expr,)))
    elif isinstance(entry, GradientLimiterLogic):
        expressions.extend(list((entry.source_expr, entry.lower_rate_expr, entry.upper_rate_expr,)))
    elif isinstance(entry, FlipFlopLogic):
        expressions.extend(list((entry.set_expr, entry.reset_expr,)))
    elif isinstance(entry, AnalogFlipFlopLogic):
        expressions.extend(list((entry.input_expr, entry.set_expr, entry.reset_expr,)))
    elif isinstance(entry, PickupDropoffLogic):
        expressions.extend(list((entry.bool_expr, entry.pickup_delay_expr, entry.drop_delay_expr,)))
    elif isinstance(entry, ResetOnRisingEdgeLogic):
        expressions.extend(list((entry.reset_expr, entry.value_expr,)))
    else:
        # The remaining logic types store typed symbol names and numeric
        # settings instead of free symbolic expression objects.
        pass

    variables: List[Var] = list()
    known_uids: set[int] = set()
    expression: Expr | Comparison | float | int
    for expression in expressions:
        expression_vars: List[Var] = list()
        if isinstance(expression, Comparison):
            expression_vars = expression.to_expression().get_vars()
        elif isinstance(expression, Expr):
            expression_vars = expression.get_vars()
        else:
            # Numeric convenience values are accepted by the engine for
            # expression fields and introduce no symbolic dependency.
            pass
        variable: Var
        for variable in expression_vars:
            if variable.uid not in known_uids:
                variables.append(variable)
                known_uids.add(variable.uid)
            else:
                pass
    return variables


def parse_runtime_expression(source: str, namespace: Mapping[str, Expr]) -> Expr | Comparison:
    """Parse one safe procedural or mode expression.

    :param source: Python-like symbolic source.
    :param namespace: Allowed identities.
    :return: Parsed expression or comparison.
    :raises ValueError: If the expression is empty or invalid.
    """
    normalized: str = source.strip()
    if len(normalized) == 0:
        raise ValueError("Expression cannot be empty")
    else:
        parser_source: str
        parser_namespace: Dict[str, Expr]
        parser_source, parser_namespace = normalize_runtime_expression_source(normalized, namespace)
        try:
            parsed: Expr | Comparison = string_to_symbolic(parser_source, parser_namespace)
        except SyntaxError as error:
            raise ValueError(str(error)) from error
    return parsed


def get_required_field_value(draft: ProceduralLogicDraft, key: str) -> str:
    """Return one required field value.

    :param draft: Owning procedural entry.
    :param key: Stable field key.
    :return: Non-empty field value.
    :raises ValueError: If the field is missing or empty.
    """
    field: ProceduralFieldDraft | None = draft.get_field(key)
    if field is None or len(field.get_value()) == 0:
        raise ValueError(f"Missing procedural field '{key}'")
    else:
        return field.get_value()


def get_required_expression(draft: ProceduralLogicDraft,
                            key: str,
                            namespace: Mapping[str, Expr]) -> Expr | Comparison:
    """Parse one required procedural expression field.

    :param draft: Owning procedural entry.
    :param key: Stable expression field key.
    :param namespace: Allowed symbolic identities.
    :return: Parsed expression.
    """
    return parse_runtime_expression(get_required_field_value(draft, key), namespace)


def get_required_float(draft: ProceduralLogicDraft, key: str) -> float:
    """Parse one required finite float field.

    :param draft: Owning procedural entry.
    :param key: Stable numeric field key.
    :return: Finite numeric value.
    """
    value: float = float(get_required_field_value(draft, key))
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"Procedural field '{key}' must be finite")
    else:
        return value


def get_optional_float(draft: ProceduralLogicDraft, key: str) -> float | None:
    """Parse one optional finite float field.

    :param draft: Owning procedural entry.
    :param key: Stable optional numeric field key.
    :return: Parsed number or ``None``.
    """
    field: ProceduralFieldDraft | None = draft.get_field(key)
    if field is None or len(field.get_value()) == 0:
        result: float | None = None
    else:
        result = get_required_float(draft, key)
    return result


def get_required_integer(draft: ProceduralLogicDraft, key: str) -> int:
    """Parse one required integer field without accepting Boolean values.

    :param draft: Typed procedural entry draft.
    :param key: Stable integer field key.
    :return: Parsed integer value.
    """
    source: str = get_required_field_value(draft, key)
    try:
        value: object = ast.literal_eval(source)
    except (SyntaxError, ValueError) as error:
        raise ValueError(f"Procedural field '{key}' must be an integer") from error
    if isinstance(value, int) and not isinstance(value, bool):
        result: int = value
    else:
        raise ValueError(f"Procedural field '{key}' must be an integer")
    return result


def get_required_boolean(draft: ProceduralLogicDraft, key: str) -> bool:
    """Parse one required Python Boolean literal.

    :param draft: Typed procedural entry draft.
    :param key: Stable Boolean field key.
    :return: Parsed Boolean value.
    """
    source: str = get_required_field_value(draft, key)
    if source == "True":
        result: bool = True
    elif source == "False":
        result = False
    else:
        raise ValueError(f"Procedural field '{key}' must be True or False")
    return result


def build_runtime_logic_entry(draft: ProceduralLogicDraft,
                              namespace: Mapping[str, Expr]) -> ProceduralLogicBase:
    """Construct one runtime entry from a fully validated draft.

    :param draft: Typed procedural draft.
    :param namespace: Authoritative symbolic identities.
    :return: Reconstructed runtime entry.
    """
    tpe: ProceduralLogicType = draft.get_logic_tpe()
    name: str = draft.get_name()
    if tpe == ProceduralLogicType.ConditionalDiagnostic:
        result: ProceduralLogicBase = ConditionalDiagnosticLogic(
            condition_expr=get_required_expression(draft, "condition_expr", namespace),
            message=get_required_field_value(draft, "message"),
            initialization_only=get_required_boolean(draft, "initialization_only"),
            name=name,
        )
    elif tpe == ProceduralLogicType.DelayedSwitchEvent:
        result = DelayedSwitchEventLogic(
            output_var_name=get_required_field_value(draft, "output_var_name"),
            guard_expr=get_required_expression(draft, "guard_expr", namespace),
            trigger_expr=get_required_expression(draft, "trigger_expr", namespace),
            delay_expr=get_required_expression(draft, "delay_expr", namespace),
            target_device_idtag=get_required_field_value(draft, "target_device_idtag"),
            target_switch_idtag=get_required_field_value(draft, "target_switch_idtag"),
            target_terminal_index=get_required_integer(draft, "target_terminal_index"),
            initial_closed=get_required_boolean(draft, "initial_closed"),
            command_closed=get_required_boolean(draft, "command_closed"),
            name=name,
        )
    elif tpe == ProceduralLogicType.FixedSample:
        result = FixedSampleLogic(
            get_required_field_value(draft, "output_var_name"),
            get_required_expression(draft, "condition_expr", namespace), name)
    elif tpe == ProceduralLogicType.SampledValue:
        sampled_output_name: str = get_required_field_value(draft, "output_var_name")
        sampled_output: Expr | None = namespace.get(sampled_output_name, None)
        sampled_output_uid: int | None = sampled_output.uid if isinstance(sampled_output, Var) else None
        result = SampledValueLogic(
            sampled_output_name,
            get_required_expression(draft, "source_expr", namespace),
            name,
            sampled_output_uid,
        )
    elif tpe == ProceduralLogicType.HardSaturation:
        result = HardSaturationLogic(get_required_field_value(draft, "output_var_name"),
                                     get_required_expression(draft, "u_expr", namespace),
                                     get_required_expression(draft, "u_min_expr", namespace),
                                     get_required_expression(draft, "u_max_expr", namespace), name)
    elif tpe == ProceduralLogicType.TimeDelay:
        result = TimeDelayLogic(get_required_field_value(draft, "output_var_name"),
                                get_required_expression(draft, "source_expr", namespace),
                                get_required_expression(draft, "delay_expr", namespace), name)
    elif tpe == ProceduralLogicType.MovingAverage:
        result = MovingAverageLogic(get_required_field_value(draft, "output_var_name"),
                                    get_required_expression(draft, "source_expr", namespace),
                                    get_required_expression(draft, "delay_expr", namespace),
                                    get_required_expression(draft, "window_expr", namespace), name)
    elif tpe == ProceduralLogicType.GradientLimiter:
        result = GradientLimiterLogic(get_required_field_value(draft, "output_var_name"),
                                      get_required_expression(draft, "source_expr", namespace),
                                      get_required_expression(draft, "lower_rate_expr", namespace),
                                      get_required_expression(draft, "upper_rate_expr", namespace), name)
    elif tpe == ProceduralLogicType.FlipFlop:
        result = FlipFlopLogic(get_required_field_value(draft, "output_var_name"),
                               get_required_expression(draft, "set_expr", namespace),
                               get_required_expression(draft, "reset_expr", namespace), name)
    elif tpe == ProceduralLogicType.AnalogFlipFlop:
        result = AnalogFlipFlopLogic(get_required_field_value(draft, "output_var_name"),
                                     get_required_expression(draft, "input_expr", namespace),
                                     get_required_expression(draft, "set_expr", namespace),
                                     get_required_expression(draft, "reset_expr", namespace), name)
    elif tpe == ProceduralLogicType.PickupDropoff:
        relay_output_name: str = get_required_field_value(draft, "output_var_name")
        relay_output: Expr | None = namespace.get(relay_output_name, None)
        relay_output_uid: int | None = relay_output.uid if isinstance(relay_output, Var) else None
        result = PickupDropoffLogic(
            relay_output_name,
            get_required_expression(draft, "bool_expr", namespace),
            get_required_expression(draft, "pickup_delay_expr", namespace),
            get_required_expression(draft, "drop_delay_expr", namespace),
            name,
            relay_output_uid,
        )
    elif tpe == ProceduralLogicType.ResetOnRisingEdge:
        result = ResetOnRisingEdgeLogic(get_required_field_value(draft, "target_var_name"),
                                        get_required_expression(draft, "reset_expr", namespace),
                                        get_required_expression(draft, "value_expr", namespace), name)
    elif tpe == ProceduralLogicType.DelayedThresholdLatch:
        result = DelayedThresholdLatchLogic(
            get_required_field_value(draft, "monitored_var_name"),
            get_required_field_value(draft, "mode_var_name"),
            get_required_float(draft, "threshold"),
            get_required_float(draft, "delay"),
            get_optional_float(draft, "reset_delay"), name)
    elif tpe == ProceduralLogicType.StartupHandover:
        result = StartupHandoverLogic(get_required_field_value(draft, "mode_var_name"),
                                      get_required_field_value(draft, "enable_time_var_name"), name)
    elif tpe == ProceduralLogicType.ValveState:
        result = ValveStateLogic(
            get_required_field_value(draft, "mode_var_name"),
            get_required_field_value(draft, "valve_type_var_name"),
            get_required_field_value(draft, "gate_var_name"),
            get_required_field_value(draft, "antiparallel_var_name"),
            get_required_field_value(draft, "voltage_eps_var_name"),
            get_required_field_value(draft, "current_eps_var_name"),
            get_required_field_value(draft, "valve_voltage_var_name"),
            get_required_field_value(draft, "valve_current_var_name"), name)
    elif tpe == ProceduralLogicType.ThreePhaseCarrierPwm:
        result = ThreePhaseCarrierPwmLogic(
            get_required_field_value(draft, "mod_a_var_name"),
            get_required_field_value(draft, "mod_b_var_name"),
            get_required_field_value(draft, "mod_c_var_name"),
            get_required_field_value(draft, "gate_a_mode_var_name"),
            get_required_field_value(draft, "gate_b_mode_var_name"),
            get_required_field_value(draft, "gate_c_mode_var_name"),
            get_required_field_value(draft, "omega_sw_var_name"),
            get_required_field_value(draft, "carrier_phase_var_name"), name)
    elif tpe == ProceduralLogicType.ThreePhaseCarrierSampledModulation:
        result = ThreePhaseCarrierSampledModulationLogic(
            get_required_field_value(draft, "mod_a_var_name"),
            get_required_field_value(draft, "mod_b_var_name"),
            get_required_field_value(draft, "mod_c_var_name"),
            get_required_field_value(draft, "sample_a_mode_var_name"),
            get_required_field_value(draft, "sample_b_mode_var_name"),
            get_required_field_value(draft, "sample_c_mode_var_name"),
            get_required_field_value(draft, "omega_sw_var_name"),
            get_required_field_value(draft, "carrier_phase_var_name"), name)
    else:
        raise ValueError(f"Unsupported procedural logic type '{tpe.value}'")
    return result


class RuntimeLogicDraftCollection:
    """Transactional collection of recursive modes and ordered logic entries."""

    __slots__ = ("_root", "_modes", "_entries")

    def __init__(self, root: Block) -> None:
        """Capture recursive runtime logic without mutating the source tree.

        :param root: Dialogue root block.
        :return: None.
        """
        self._root: Block = root
        self._modes: List[RuntimeModeDraft] = list()
        self._entries: List[ProceduralLogicDraft] = list()
        editable_types: set[ProceduralLogicType] = set()
        descriptor: ProceduralBlockTemplateDescriptor
        for descriptor in get_dynamic_library_procedural_descriptors():
            editable_types.add(descriptor.logic_tpe)
        owner: Block
        for owner in root.get_all_blocks():
            mode_variable: Var
            initial_expression: Expr
            for mode_variable, initial_expression in owner.mode_dict.items():
                self._modes.append(RuntimeModeDraft(
                    owner,
                    mode_variable,
                    mode_variable.name,
                    procedural_expression_to_text(initial_expression),
                ))
            entry: ProceduralLogicBase
            for entry in owner.procedural_logic:
                if entry.logic_tpe in editable_types:
                    self._entries.append(ProceduralLogicDraft(
                        owner,
                        entry.logic_tpe,
                        entry.name,
                        get_procedural_fields(entry),
                        entry,
                    ))
                else:
                    # Provider-owned entries stay on the Block and never become
                    # drafts in the catalogue-backed source editor.
                    pass

    def replace_code_drafts(
            self,
            modes: Sequence[RuntimeModeDraft],
            entries: Sequence[ProceduralLogicDraft],
    ) -> None:
        """Replace the detached collection with drafts parsed from Python code.

        :param modes: Complete retained-mode declarations from every owner.
        :param entries: Complete ordered procedural entries from every owner.
        :return: None.
        """
        self._modes = list(modes)
        self._entries = list(entries)

    def get_modes(self) -> List[RuntimeModeDraft]:
        """
        :return: Active and removed mode drafts.
        """
        return list(self._modes)

    def get_active_modes(self) -> List[RuntimeModeDraft]:
        """
        :return: Retained modes not staged for deletion.
        """
        result: List[RuntimeModeDraft] = list()
        mode: RuntimeModeDraft
        for mode in self._modes:
            if not mode.is_removed():
                result.append(mode)
            else:
                pass
        return result

    def get_entries(self) -> List[ProceduralLogicDraft]:
        """
        :return: Ordered procedural entry drafts.
        """
        return list(self._entries)

    def has_new_modes(self) -> bool:
        """
        :return: Whether Apply must create at least one retained mode.
        """
        result: bool = False
        mode: RuntimeModeDraft
        for mode in self._modes:
            if mode.is_new() and not mode.is_removed():
                result = True
            else:
                pass
        return result

    def add_mode(self, owner: Block, name: str, initial_expression: str) -> RuntimeModeDraft:
        """Stage one new retained mode.

        :param owner: Direct owner block.
        :param name: New symbol name.
        :param initial_expression: Initial source.
        :return: Added mode draft.
        """
        mode: RuntimeModeDraft = RuntimeModeDraft(owner, None, name, initial_expression)
        self._modes.append(mode)
        return mode

    def get_mode_writer_names(self, mode_name: str) -> List[str]:
        """Return ordered logic entry names writing one retained mode.

        :param mode_name: Mode symbol name.
        :return: Writer entry names.
        """
        writers: List[str] = list()
        entry: ProceduralLogicDraft
        field: ProceduralFieldDraft
        for entry in self._entries:
            for field in entry.get_fields():
                if field.get_tpe() == ProceduralFieldType.MODE_REFERENCE and field.get_value() == mode_name:
                    writers.append(entry.get_name())
                else:
                    pass
        return writers

    def remove_mode(self, row: int) -> tuple[bool, str]:
        """Stage one retained-mode declaration for deletion.

        Python model code is the authoritative editor. References are left in
        place so the user can update them in any order; Validate and Apply reject
        unknown references before the Engine is mutated.

        :param row: Mode row.
        :return: Success flag and an empty message.
        """
        if not 0 <= row < len(self._modes):
            return False, "Select one retained mode."
        else:
            mode: RuntimeModeDraft = self._modes[row]
            mode.set_removed(True)
            return True, ""

    def build_validation_namespace(self, base_namespace: Mapping[str, Expr]) -> Dict[str, Expr]:
        """Add staged retained modes and exclude removed ones.

        :param base_namespace: Current complete block namespace.
        :return: Namespace used by DAE and procedural validation.
        """
        namespace: Dict[str, Expr] = dict(base_namespace)
        mode: RuntimeModeDraft
        for mode in self._modes:
            existing_variable: Var | None = mode.get_variable()
            if existing_variable is not None and existing_variable.name != mode.get_name():
                namespace.pop(existing_variable.name, None)
            else:
                pass
            if mode.is_removed():
                namespace.pop(mode.get_name(), None)
            elif mode.is_new():
                namespace[mode.get_name()] = Var(mode.get_name())
            elif existing_variable is not None:
                namespace[mode.get_name()] = existing_variable
            else:
                pass
        return namespace

    def validate(self, base_namespace: Mapping[str, Expr]) -> RuntimeLogicValidationResult:
        """Validate modes, references, expressions, writers, and ordering.

        :param base_namespace: Complete symbolic namespace before staged modes.
        :return: Validation result with errors and warnings.
        """
        result: RuntimeLogicValidationResult = RuntimeLogicValidationResult()
        namespace: Dict[str, Expr] = self.build_validation_namespace(base_namespace)
        mode_names: set[str] = set()
        mode: RuntimeModeDraft
        for mode in self._modes:
            if not mode.is_removed():
                invalid_name: bool = (
                    len(mode.get_name()) == 0
                    or not mode.get_name().isidentifier()
                    or keyword.iskeyword(mode.get_name())
                )
                if invalid_name:
                    message: str = f"Mode '{mode.get_name()}' needs a valid Python symbol name."
                    result.add_error(message)
                elif mode.get_name() in mode_names:
                    message = f"Retained mode '{mode.get_name()}' is declared more than once."
                    result.add_error(message)
                elif mode.get_name() in base_namespace:
                    conflicting_symbol: Expr = base_namespace[mode.get_name()]
                    existing_mode_variable: Var | None = mode.get_variable()
                    if existing_mode_variable is not None and conflicting_symbol is existing_mode_variable:
                        mode_names.add(mode.get_name())
                    else:
                        message = (
                            f"Retained mode '{mode.get_name()}' conflicts with an existing DAE or parameter symbol."
                        )
                        result.add_error(message)
                else:
                    mode_names.add(mode.get_name())
                try:
                    initial_expression: Expr | Comparison = parse_runtime_expression(
                        mode.get_initial_expression(), namespace)
                    if isinstance(initial_expression, Comparison):
                        raise ValueError("initialization must be a numeric expression, not a comparison")
                    else:
                        pass
                except (KeyError, TypeError, ValueError) as error:
                    message = f"Mode '{mode.get_name()}' initialization: {error}"
                    result.add_error(message)
            else:
                pass

        entry_names: set[tuple[int, str]] = set()
        writer_rows: Dict[str, int] = dict()
        entry_index: int
        entry: ProceduralLogicDraft
        for entry_index, entry in enumerate(self._entries):
            entry_key: tuple[int, str] = (entry.get_owner().uid, entry.get_name())
            if len(entry.get_name()) == 0:
                if entry.get_original() is None:
                    message = f"Procedural entry #{entry_index + 1} needs a name."
                    result.add_error(message)
                else:
                    result.add_warning(
                        f"Existing procedural entry #{entry_index + 1} has no display name."
                    )
            elif entry_key in entry_names:
                message = f"Procedural entry name '{entry.get_name()}' is duplicated in '{entry.get_owner().name}'."
                if entry.get_original() is None:
                    result.add_error(message)
                else:
                    # Entry names are labels rather than runtime lookup keys.
                    # Preserve valid legacy catalogue blocks while preventing
                    # newly authored ambiguity.
                    result.add_warning(message)
            else:
                entry_names.add(entry_key)

            field: ProceduralFieldDraft
            for field in entry.get_fields():
                field_tpe: ProceduralFieldType = field.get_tpe()
                field_value: str = field.get_value()
                try:
                    if field_tpe == ProceduralFieldType.EXPRESSION:
                        parsed_expression: Expr | Comparison = parse_runtime_expression(field_value, namespace)
                        _unused_expression: Expr | Comparison = parsed_expression
                    elif field_tpe == ProceduralFieldType.FLOAT:
                        parsed_float: float = float(field_value)
                        if parsed_float != parsed_float or parsed_float in (float("inf"), float("-inf")):
                            raise ValueError("number must be finite")
                        else:
                            pass
                    elif field_tpe == ProceduralFieldType.OPTIONAL_FLOAT:
                        if len(field_value) > 0:
                            optional_float: float = float(field_value)
                            if optional_float != optional_float or optional_float in (float("inf"), float("-inf")):
                                raise ValueError("number must be finite")
                            else:
                                pass
                        else:
                            pass
                    elif field_tpe == ProceduralFieldType.REQUIRED_TEXT:
                        if len(field_value) == 0:
                            raise ValueError("text cannot be empty")
                        else:
                            pass
                    elif field_tpe == ProceduralFieldType.TEXT:
                        pass
                    elif field_tpe == ProceduralFieldType.INTEGER:
                        try:
                            integer_value: object = ast.literal_eval(field_value)
                        except (SyntaxError, ValueError) as error:
                            raise ValueError("value must be an integer") from error
                        if isinstance(integer_value, int) and not isinstance(integer_value, bool):
                            pass
                        else:
                            raise ValueError("value must be an integer")
                    elif field_tpe == ProceduralFieldType.BOOLEAN:
                        if field_value in ("True", "False"):
                            pass
                        else:
                            raise ValueError("value must be True or False")
                    elif field_tpe == ProceduralFieldType.MODE_REFERENCE:
                        if field_value not in mode_names:
                            raise ValueError(f"'{field_value}' is not a retained mode")
                        elif field_value in writer_rows:
                            raise ValueError(
                                f"mode '{field_value}' is already written by entry #{writer_rows[field_value] + 1}"
                            )
                        else:
                            writer_rows[field_value] = entry_index
                    elif field_tpe in (
                        ProceduralFieldType.VARIABLE_REFERENCE,
                        ProceduralFieldType.RUNTIME_REFERENCE,
                        ProceduralFieldType.TARGET_REFERENCE,
                    ):
                        if field_value not in namespace:
                            raise ValueError(f"unknown symbol '{field_value}'")
                        else:
                            pass
                    else:
                        pass
                except (KeyError, TypeError, ValueError) as error:
                    message = f"{entry.get_name()} / {field.get_label()}: {error}"
                    result.add_error(message)

        for mode in self.get_active_modes():
            writers = self.get_mode_writer_names(mode.get_name())
            if len(writers) == 0:
                result.add_warning(
                    f"Mode '{mode.get_name()}' has no procedural writer and is treated as retained/external."
                )
            else:
                pass
        self._validate_order_dependencies(result, writer_rows)
        return result

    def _validate_order_dependencies(self,
                                     result: RuntimeLogicValidationResult,
                                     writer_rows: Mapping[str, int]) -> None:
        """Warn when an expression reads a mode written later in the list.

        :param result: Validation result receiving warnings.
        :param writer_rows: Mode writer row lookup.
        :return: None.
        """
        entry_index: int
        entry: ProceduralLogicDraft
        for entry_index, entry in enumerate(self._entries):
            field: ProceduralFieldDraft
            for field in entry.get_fields():
                if field.get_tpe() == ProceduralFieldType.EXPRESSION:
                    mode_name: str
                    for mode_name, writer_index in writer_rows.items():
                        pattern: re.Pattern[str] = re.compile(rf"\b{re.escape(mode_name)}\b")
                        if writer_index > entry_index and pattern.search(field.get_value()) is not None:
                            result.add_warning(
                                f"'{entry.get_name()}' reads mode '{mode_name}' before its writer runs."
                            )
                        else:
                            pass
                else:
                    pass

    def apply_to_blocks(self, var_factory: VarFactory, base_namespace: Mapping[str, Expr]) -> Dict[str, Expr]:
        """Apply validated modes and logic entries to their direct owners.

        :param var_factory: Authoritative variable factory.
        :param base_namespace: Namespace after other symbol edits.
        :return: Namespace containing authoritative new mode variables.
        """
        validation: RuntimeLogicValidationResult = self.validate(base_namespace)
        if not validation.is_valid():
            raise ValueError(validation.get_errors()[0])
        else:
            namespace: Dict[str, Expr] = dict(base_namespace)

        mode: RuntimeModeDraft
        for mode in self._modes:
            variable: Var | None = mode.get_variable()
            previous_name: str | None = variable.name if variable is not None else None
            if mode.is_removed():
                if variable is not None:
                    mode.get_owner().mode_dict.pop(variable, None)
                    namespace.pop(variable.name, None)
                else:
                    pass
            else:
                if variable is None:
                    variable = var_factory.add_var(mode.get_name())
                elif variable.name != mode.get_name():
                    variable.set_name(mode.get_name())
                else:
                    pass
                if previous_name is not None and previous_name != mode.get_name():
                    # The validation namespace deliberately removed the old
                    # spelling. Mirror that behavior in the authoritative
                    # post-Apply namespace so stale source cannot keep using a
                    # renamed mode through a second dictionary key.
                    namespace.pop(previous_name, None)
                else:
                    pass
                namespace[mode.get_name()] = variable

        owner: Block
        for owner in self._root.get_all_blocks():
            owner_modes: Dict[Var, Expr | Const] = dict()
            for mode in self._modes:
                if mode.get_owner() is owner and not mode.is_removed():
                    mode_variable: Expr | None = namespace.get(mode.get_name(), None)
                    if isinstance(mode_variable, Var):
                        parsed_initial: Expr | Comparison = parse_runtime_expression(
                            mode.get_initial_expression(), namespace)
                        if isinstance(parsed_initial, Expr):
                            owner_modes[mode_variable] = parsed_initial
                        else:
                            raise ValueError(
                                f"Mode '{mode.get_name()}' initialization cannot be a comparison."
                            )
                    else:
                        raise ValueError(f"Mode '{mode.get_name()}' has no authoritative variable.")
                else:
                    pass
            owner.mode_dict = owner_modes

            owner_entries: List[ProceduralLogicBase] = list()
            entry: ProceduralLogicDraft
            for entry in self._entries:
                if entry.get_owner() is owner:
                    owner_entries.append(build_runtime_logic_entry(entry, namespace))
                else:
                    pass
            owner.procedural_logic = owner_entries
        return namespace


def build_runtime_logic_drafts_from_code(
        root: Block,
        owner_code: Sequence[tuple[Block, str]],
) -> RuntimeLogicDraftCollection:
    """Build one recursive runtime draft collection from model-code buffers.

    Mode declarations are collected for every owner before procedural entries
    are validated by the caller. This keeps the code-owner combo consistent
    with the Engine's recursive block hierarchy and execution order.

    :param root: Root block shown by Block Properties.
    :param owner_code: Ordered direct owners and their complete source buffers.
    :return: Detached recursive runtime draft collection.
    """
    modes: List[RuntimeModeDraft] = list()
    entries: List[ProceduralLogicDraft] = list()
    owner: Block
    code: str
    for owner, code in owner_code:
        modes.extend(parse_retained_mode_drafts(code, owner))
    for owner, code in owner_code:
        entries.extend(parse_procedural_logic_drafts(code, owner))

    collection: RuntimeLogicDraftCollection = RuntimeLogicDraftCollection(root)
    collection.replace_code_drafts(modes=modes, entries=entries)
    return collection
