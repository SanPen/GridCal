# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, List

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import _get_phase_count_name
from VeraGridEngine.Utils.Symbolic.block import Expr, Var
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType


def _get_active_nabc_labels(phN: bool, phA: bool, phB: bool, phC: bool) -> List[str]:
    """
    Return the enabled NABC labels in deterministic order.

    :param phN: Whether neutral is active.
    :param phA: Whether phase A is active.
    :param phB: Whether phase B is active.
    :param phC: Whether phase C is active.
    :return: Ordered active label list.
    :raises ValueError: If no terminal is enabled.
    """
    active_labels: List[str] = list()

    if phN:
        active_labels.append("N")
    else:
        pass

    if phA:
        active_labels.append("A")
    else:
        pass

    if phB:
        active_labels.append("B")
    else:
        pass

    if phC:
        active_labels.append("C")
    else:
        pass

    if active_labels:
        return active_labels
    else:
        raise ValueError("At least one source terminal must be enabled for an EMT source template")


def _get_voltage_reference(phase_label: str) -> VarPowerFlowReferenceType:
    """
    Return the EMT voltage reference enum for one NABC label.

    :param phase_label: One of ``N``, ``A``, ``B`` or ``C``.
    :return: Matching voltage reference enum.
    """
    if phase_label == "N":
        return VarPowerFlowReferenceType.v_N
    elif phase_label == "A":
        return VarPowerFlowReferenceType.v_A
    elif phase_label == "B":
        return VarPowerFlowReferenceType.v_B
    elif phase_label == "C":
        return VarPowerFlowReferenceType.v_C
    else:
        raise ValueError(f"Unsupported source phase label '{phase_label}'")


def _get_current_reference(phase_label: str) -> VarPowerFlowReferenceType:
    """
    Return the EMT injected-current reference enum for one NABC label.

    :param phase_label: One of ``N``, ``A``, ``B`` or ``C``.
    :return: Matching current reference enum.
    """
    if phase_label == "N":
        return VarPowerFlowReferenceType.i_N
    elif phase_label == "A":
        return VarPowerFlowReferenceType.i_A
    elif phase_label == "B":
        return VarPowerFlowReferenceType.i_B
    elif phase_label == "C":
        return VarPowerFlowReferenceType.i_C
    else:
        raise ValueError(f"Unsupported source phase label '{phase_label}'")


def _build_external_mapping(voltage_vars: Dict[str, Var], current_vars: Dict[str, Var]) -> Dict[VarPowerFlowReferenceType, Var | None]:
    """
    Build one full EMT external mapping with inactive entries set to ``None``.

    :param voltage_vars: Active bus-voltage inputs by label.
    :param current_vars: Active injected-current outputs by label.
    :return: External mapping dictionary.
    """
    return dict({
        VarPowerFlowReferenceType.v_N: voltage_vars.get("N", None),
        VarPowerFlowReferenceType.v_A: voltage_vars.get("A", None),
        VarPowerFlowReferenceType.v_B: voltage_vars.get("B", None),
        VarPowerFlowReferenceType.v_C: voltage_vars.get("C", None),
        VarPowerFlowReferenceType.i_N: current_vars.get("N", None),
        VarPowerFlowReferenceType.i_A: current_vars.get("A", None),
        VarPowerFlowReferenceType.i_B: current_vars.get("B", None),
        VarPowerFlowReferenceType.i_C: current_vars.get("C", None),
    })


def _build_source_template_name(base_name: str,
                                phN: bool,
                                phA: bool,
                                phB: bool,
                                phC: bool,
                                requested_name: str | None) -> str:
    """
    Resolve one source template name with a phase-count suffix.

    :param base_name: Base symbolic name.
    :param phN: Whether neutral is active.
    :param phA: Whether phase A is active.
    :param phB: Whether phase B is active.
    :param phC: Whether phase C is active.
    :param requested_name: Optional caller-provided name.
    :return: Resolved template name.
    """
    phase_count: int = int(phN) + int(phA) + int(phB) + int(phC)
    return _get_phase_count_name(base_name=base_name, phase_count=phase_count, requested_name=requested_name)


def _resolve_phase_value(phase_values: Dict[str, float] | None,
                         phase_label: str,
                         default_value: float) -> float:
    """
    Return one optional per-phase scalar value.

    :param phase_values: Optional per-phase dictionary.
    :param phase_label: Requested phase label.
    :param default_value: Fallback value.
    :return: Scalar phase value.
    """
    if isinstance(phase_values, dict) and phase_label in phase_values:
        return float(phase_values[phase_label])
    else:
        return float(default_value)


def _build_sinusoidal_wave_expression(amplitude_expr: Expr,
                                      theta_var: Var,
                                      phase_deg_var: Var,
                                      offset_var: Var) -> Expr:
    """
    Build one sinusoidal wave expression based on the global EMT time.

    :param amplitude_expr: Wave amplitude expression.
    :param theta_var: Internal electrical angle state in rad.
    :param phase_deg_var: Phase offset in degrees.
    :param offset_var: DC offset.
    :return: Sinusoidal expression.
    """
    phase_rad_expr: Expr = (sym.Const(3.141592653589793) / sym.Const(180.0)) * phase_deg_var
    return offset_var + amplitude_expr * sym.sin(theta_var + phase_rad_expr)


class CurrentSourceEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phN", units="", descr="Whether neutral is active.", tpe=bool, value=False),
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="amplitude_values", units="", descr="Optional sinusoidal amplitudes by phase label.", tpe=dict, value=None),
                TemplateProp(name="frequency_hz", units="Hz", descr="Common sinusoidal frequency.", tpe=float, value=50.0),
                TemplateProp(name="phase_angle_deg", units="", descr="Optional phase offsets in degrees by phase label.", tpe=dict, value=None),
                TemplateProp(name="offset_values", units="", descr="Optional DC offsets by phase label.", tpe=dict, value=None),
                TemplateProp(name="name", units="", descr="Symbolic block name.", tpe=str, value="current_source_emt"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        phN: bool = self.get_value("phN")
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        amplitude_values: Dict[str, float] | None = self.get_value("amplitude_values")
        frequency_hz: float = self.get_value("frequency_hz")
        phase_angle_deg: Dict[str, float] | None = self.get_value("phase_angle_deg")
        offset_values: Dict[str, float] | None = self.get_value("offset_values")
        name: str | None = self.get_value("name")

        return get_current_source_emt_template(
            self.vf, phN, phA, phB, phC, amplitude_values, frequency_hz,
            phase_angle_deg, offset_values, name,
        )


def get_current_source_emt_template(vf: VarFactory,
                                    phN: bool = False,
                                    phA: bool = True,
                                    phB: bool = True,
                                    phC: bool = True,
                                    amplitude_values: Dict[str, float] | None = None,
                                    frequency_hz: float = 50.0,
                                    phase_angle_deg: Dict[str, float] | None = None,
                                    offset_values: Dict[str, float] | None = None,
                                    name: str | None = "current_source_emt") -> EmtModelTemplate:
    """
    Build one phase-selective sinusoidal EMT current source.

    Positive currents inject into the connected bus according to the existing EMT
    source convention used by generator-like blocks.

    :param vf: EMT variable factory.
    :param phN: Whether neutral is active.
    :param phA: Whether phase A is active.
    :param phB: Whether phase B is active.
    :param phC: Whether phase C is active.
    :param amplitude_values: Optional sinusoidal amplitudes by phase label.
    :param frequency_hz: Common sinusoidal frequency in Hz.
    :param phase_angle_deg: Optional phase offsets in degrees by phase label.
    :param offset_values: Optional DC offsets by phase label.
    :param name: Optional symbolic block name.
    :return: Configured EMT template.
    """
    active_labels: List[str] = _get_active_nabc_labels(phN=phN, phA=phA, phB=phB, phC=phC)
    resolved_name: str = _build_source_template_name("current_source_emt", phN, phA, phB, phC, name)
    template: EmtModelTemplate = EmtModelTemplate()
    template.tpe = DeviceType.GeneratorDevice
    template.name = resolved_name
    template.block.name = resolved_name

    frequency_var: Var = vf.add_var(name=f"f_src")
    template.block.event_dict[frequency_var] = vf.add_const(float(frequency_hz))
    theta_var: Var = vf.add_var(name=f"theta_src")
    d_theta_var: Var = vf.add_diff_var(name=f"d_theta_src", base_var=theta_var)

    voltage_vars: Dict[str, Var] = dict()
    current_vars: Dict[str, Var] = dict()
    in_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    out_vars: List[Var] = list()
    phase_label: str

    for phase_label in active_labels:
        voltage_var: Var = vf.add_var(name=f"v_{phase_label}", reference=_get_voltage_reference(phase_label))
        current_var: Var = vf.add_var(name=f"i_{phase_label}", reference=_get_current_reference(phase_label))
        amplitude_var: Var = vf.add_var(name=f"I_amp_{phase_label}")
        phase_deg_var: Var = vf.add_var(name=f"phi_deg_{phase_label}")
        offset_var: Var = vf.add_var(name=f"I_offset_{phase_label}")
        template.block.event_dict[amplitude_var] = vf.add_const(_resolve_phase_value(amplitude_values, phase_label, 0.0))
        template.block.event_dict[phase_deg_var] = vf.add_const(_resolve_phase_value(phase_angle_deg, phase_label, 0.0))
        template.block.event_dict[offset_var] = vf.add_const(_resolve_phase_value(offset_values, phase_label, 0.0))
        voltage_vars[phase_label] = voltage_var
        current_vars[phase_label] = current_var
        in_vars.append(voltage_var)
        algebraic_vars.append(current_var)
        # Seed the full waveform so phase offsets satisfy the same law at startup.
        source_current_expr: Expr = _build_sinusoidal_wave_expression(amplitude_var, theta_var, phase_deg_var, offset_var)
        algebraic_eqs.append(current_var - source_current_expr)
        out_vars.append(current_var)
        template.block.init_eqs[current_var] = source_current_expr

    template.block.in_vars = in_vars
    template.block.state_vars = [theta_var]
    template.block.diff_vars = [d_theta_var]
    template.block.state_eqs = [sym.Const(2.0) * sym.Const(3.141592653589793) * frequency_var]
    template.block.algebraic_vars = algebraic_vars
    template.block.algebraic_eqs = algebraic_eqs
    template.block.out_vars = out_vars
    template.block.external_mapping = _build_external_mapping(voltage_vars, current_vars)
    template.block.init_eqs[theta_var] = sym.Const(0.0)
    return template


class ControlledCurrentSourceEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phN", units="", descr="Whether neutral is active.", tpe=bool, value=False),
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="frequency_hz", units="Hz", descr="Common sinusoidal frequency.", tpe=float, value=50.0),
                TemplateProp(name="phase_angle_deg", units="", descr="Optional phase offsets in degrees by phase label.", tpe=dict, value=None),
                TemplateProp(name="offset_values", units="", descr="Optional DC offsets by phase label.", tpe=dict, value=None),
                TemplateProp(name="name", units="", descr="Symbolic block name.", tpe=str, value="controlled_current_source_emt"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        phN: bool = self.get_value("phN")
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        frequency_hz: float = self.get_value("frequency_hz")
        phase_angle_deg: Dict[str, float] | None = self.get_value("phase_angle_deg")
        offset_values: Dict[str, float] | None = self.get_value("offset_values")
        name: str | None = self.get_value("name")

        return get_controlled_current_source_emt_template(
            self.vf, phN, phA, phB, phC, frequency_hz,
            phase_angle_deg, offset_values, name,
        )


def get_controlled_current_source_emt_template(vf: VarFactory,
                                               phN: bool = False,
                                               phA: bool = True,
                                               phB: bool = True,
                                               phC: bool = True,
                                               frequency_hz: float = 50.0,
                                               phase_angle_deg: Dict[str, float] | None = None,
                                               offset_values: Dict[str, float] | None = None,
                                               name: str | None = "controlled_current_source_emt") -> EmtModelTemplate:
    """
    Build one phase-selective controlled sinusoidal EMT current source.

    The command inputs represent the per-phase sinusoidal amplitudes.

    :param vf: EMT variable factory.
    :param phN: Whether neutral is active.
    :param phA: Whether phase A is active.
    :param phB: Whether phase B is active.
    :param phC: Whether phase C is active.
    :param frequency_hz: Common sinusoidal frequency in Hz.
    :param phase_angle_deg: Optional phase offsets in degrees by phase label.
    :param offset_values: Optional DC offsets by phase label.
    :param name: Optional symbolic block name.
    :return: Configured EMT template.
    """
    active_labels: List[str] = _get_active_nabc_labels(phN=phN, phA=phA, phB=phB, phC=phC)
    resolved_name: str = _build_source_template_name("controlled_current_source_emt", phN, phA, phB, phC, name)
    template: EmtModelTemplate = EmtModelTemplate()
    template.tpe = DeviceType.GeneratorDevice
    template.name = resolved_name
    template.block.name = resolved_name

    frequency_var: Var = vf.add_var(name=f"f_src")
    template.block.event_dict[frequency_var] = vf.add_const(float(frequency_hz))
    theta_var: Var = vf.add_var(name=f"theta_src")
    d_theta_var: Var = vf.add_diff_var(name=f"d_theta_src", base_var=theta_var)

    voltage_vars: Dict[str, Var] = dict()
    current_vars: Dict[str, Var] = dict()
    in_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    out_vars: List[Var] = list()
    phase_label: str

    for phase_label in active_labels:
        voltage_var: Var = vf.add_var(name=f"v_{phase_label}", reference=_get_voltage_reference(phase_label))
        current_var: Var = vf.add_var(name=f"i_{phase_label}", reference=_get_current_reference(phase_label))
        amplitude_command_var: Var = vf.add_var(name=f"i_amp_cmd_{phase_label}")
        phase_deg_var: Var = vf.add_var(name=f"phi_deg_{phase_label}")
        offset_var: Var = vf.add_var(name=f"I_offset_{phase_label}")
        template.block.event_dict[phase_deg_var] = vf.add_const(_resolve_phase_value(phase_angle_deg, phase_label, 0.0))
        template.block.event_dict[offset_var] = vf.add_const(_resolve_phase_value(offset_values, phase_label, 0.0))
        voltage_vars[phase_label] = voltage_var
        current_vars[phase_label] = current_var
        in_vars.append(voltage_var)
        in_vars.append(amplitude_command_var)
        algebraic_vars.append(current_var)
        # The initial current must include the external amplitude command and phase offset.
        source_current_expr: Expr = _build_sinusoidal_wave_expression(amplitude_command_var, theta_var, phase_deg_var, offset_var)
        algebraic_eqs.append(current_var - source_current_expr)
        out_vars.append(current_var)
        template.block.init_eqs[current_var] = source_current_expr

    template.block.in_vars = in_vars
    template.block.state_vars = [theta_var]
    template.block.diff_vars = [d_theta_var]
    template.block.state_eqs = [sym.Const(2.0) * sym.Const(3.141592653589793) * frequency_var]
    template.block.algebraic_vars = algebraic_vars
    template.block.algebraic_eqs = algebraic_eqs
    template.block.out_vars = out_vars
    template.block.external_mapping = _build_external_mapping(voltage_vars, current_vars)
    template.block.init_eqs[theta_var] = sym.Const(0.0)
    return template


class VoltageSourceEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phN", units="", descr="Whether neutral is active.", tpe=bool, value=False),
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="amplitude_values", units="", descr="Optional sinusoidal amplitudes by phase label.", tpe=dict, value=None),
                TemplateProp(name="frequency_hz", units="Hz", descr="Common sinusoidal frequency.", tpe=float, value=50.0),
                TemplateProp(name="phase_angle_deg", units="", descr="Optional phase offsets in degrees by phase label.", tpe=dict, value=None),
                TemplateProp(name="offset_values", units="", descr="Optional DC offsets by phase label.", tpe=dict, value=None),
                TemplateProp(name="source_conductance_value", units="S", descr="Common Norton conductance.", tpe=float, value=0.0),
                TemplateProp(name="name", units="", descr="Symbolic block name.", tpe=str, value="voltage_source_emt"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        phN: bool = self.get_value("phN")
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        amplitude_values: Dict[str, float] | None = self.get_value("amplitude_values")
        frequency_hz: float = self.get_value("frequency_hz")
        phase_angle_deg: Dict[str, float] | None = self.get_value("phase_angle_deg")
        offset_values: Dict[str, float] | None = self.get_value("offset_values")
        source_conductance_value: float = self.get_value("source_conductance_value")
        name: str | None = self.get_value("name")

        return get_voltage_source_emt_template(
            self.vf, phN, phA, phB, phC, amplitude_values, frequency_hz,
            phase_angle_deg, offset_values, source_conductance_value, name,
        )


def get_voltage_source_emt_template(vf: VarFactory,
                                    phN: bool = False,
                                    phA: bool = True,
                                    phB: bool = True,
                                    phC: bool = True,
                                    amplitude_values: Dict[str, float] | None = None,
                                    frequency_hz: float = 50.0,
                                    phase_angle_deg: Dict[str, float] | None = None,
                                    offset_values: Dict[str, float] | None = None,
                                    source_conductance_value: float = 0.0,
                                    name: str | None = "voltage_source_emt") -> EmtModelTemplate:
    """
    Build one phase-selective sinusoidal EMT voltage source using one Norton-like injection.

    The block injects ``i = g * (v_src - v_bus)`` where ``v_src`` is one
    internally generated sinusoidal waveform.

    :param vf: EMT variable factory.
    :param phN: Whether neutral is active.
    :param phA: Whether phase A is active.
    :param phB: Whether phase B is active.
    :param phC: Whether phase C is active.
    :param amplitude_values: Optional sinusoidal amplitudes by phase label.
    :param frequency_hz: Common sinusoidal frequency in Hz.
    :param phase_angle_deg: Optional phase offsets in degrees by phase label.
    :param offset_values: Optional DC offsets by phase label.
    :param source_conductance_value: Common Norton conductance.
    :param name: Optional symbolic block name.
    :return: Configured EMT template.
    """
    active_labels: List[str] = _get_active_nabc_labels(phN=phN, phA=phA, phB=phB, phC=phC)
    resolved_name: str = _build_source_template_name("voltage_source_emt", phN, phA, phB, phC, name)
    template: EmtModelTemplate = EmtModelTemplate()
    template.tpe = DeviceType.GeneratorDevice
    template.name = resolved_name
    template.block.name = resolved_name

    frequency_var: Var = vf.add_var(name=f"f_src")
    source_conductance_var: Var = vf.add_var(name=f"g_src")
    template.block.event_dict[frequency_var] = vf.add_const(float(frequency_hz))
    template.block.event_dict[source_conductance_var] = vf.add_const(float(source_conductance_value))
    theta_var: Var = vf.add_var(name=f"theta_src")
    d_theta_var: Var = vf.add_diff_var(name=f"d_theta_src", base_var=theta_var)

    voltage_vars: Dict[str, Var] = dict()
    current_vars: Dict[str, Var] = dict()
    in_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    out_vars: List[Var] = list()
    phase_label: str

    for phase_label in active_labels:
        voltage_var: Var = vf.add_var(name=f"v_{phase_label}", reference=_get_voltage_reference(phase_label))
        current_var: Var = vf.add_var(name=f"i_{phase_label}", reference=_get_current_reference(phase_label))
        amplitude_var: Var = vf.add_var(name=f"V_amp_{phase_label}")
        phase_deg_var: Var = vf.add_var(name=f"phi_deg_{phase_label}")
        offset_var: Var = vf.add_var(name=f"V_offset_{phase_label}")
        template.block.event_dict[amplitude_var] = vf.add_const(_resolve_phase_value(amplitude_values, phase_label, 0.0))
        template.block.event_dict[phase_deg_var] = vf.add_const(_resolve_phase_value(phase_angle_deg, phase_label, 0.0))
        template.block.event_dict[offset_var] = vf.add_const(_resolve_phase_value(offset_values, phase_label, 0.0))
        voltage_vars[phase_label] = voltage_var
        current_vars[phase_label] = current_var
        in_vars.append(voltage_var)
        algebraic_vars.append(current_var)
        # Reuse the Norton law for the seed, including source phase and bus voltage.
        source_current_expr: Expr = source_conductance_var * (
            _build_sinusoidal_wave_expression(amplitude_var, theta_var, phase_deg_var, offset_var) - voltage_var)
        algebraic_eqs.append(current_var - source_current_expr)
        out_vars.append(current_var)
        template.block.init_eqs[current_var] = source_current_expr

    template.block.in_vars = in_vars
    template.block.state_vars = [theta_var]
    template.block.diff_vars = [d_theta_var]
    template.block.state_eqs = [sym.Const(2.0) * sym.Const(3.141592653589793) * frequency_var]
    template.block.algebraic_vars = algebraic_vars
    template.block.algebraic_eqs = algebraic_eqs
    template.block.out_vars = out_vars
    template.block.external_mapping = _build_external_mapping(voltage_vars, current_vars)
    template.block.init_eqs[theta_var] = sym.Const(0.0)
    return template


class ControlledVoltageSourceEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phN", units="", descr="Whether neutral is active.", tpe=bool, value=False),
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="frequency_hz", units="Hz", descr="Common sinusoidal frequency.", tpe=float, value=50.0),
                TemplateProp(name="phase_angle_deg", units="", descr="Optional phase offsets in degrees by phase label.", tpe=dict, value=None),
                TemplateProp(name="offset_values", units="", descr="Optional DC offsets by phase label.", tpe=dict, value=None),
                TemplateProp(name="source_conductance_value", units="S", descr="Common Norton conductance.", tpe=float, value=0.0),
                TemplateProp(name="name", units="", descr="Symbolic block name.", tpe=str, value="controlled_voltage_source_emt"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        phN: bool = self.get_value("phN")
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        frequency_hz: float = self.get_value("frequency_hz")
        phase_angle_deg: Dict[str, float] | None = self.get_value("phase_angle_deg")
        offset_values: Dict[str, float] | None = self.get_value("offset_values")
        source_conductance_value: float = self.get_value("source_conductance_value")
        name: str | None = self.get_value("name")

        return get_controlled_voltage_source_emt_template(
            self.vf, phN, phA, phB, phC, frequency_hz,
            phase_angle_deg, offset_values, source_conductance_value, name,
        )


def get_controlled_voltage_source_emt_template(vf: VarFactory,
                                               phN: bool = False,
                                               phA: bool = True,
                                               phB: bool = True,
                                               phC: bool = True,
                                               frequency_hz: float = 50.0,
                                               phase_angle_deg: Dict[str, float] | None = None,
                                               offset_values: Dict[str, float] | None = None,
                                               source_conductance_value: float = 0.0,
                                               name: str | None = "controlled_voltage_source_emt") -> EmtModelTemplate:
    """
    Build one phase-selective controlled sinusoidal EMT voltage source.

    The command inputs represent the per-phase sinusoidal amplitudes. The bus sees
    the same Norton-like equivalent ``i = g * (v_src - v_bus)``.

    :param vf: EMT variable factory.
    :param phN: Whether neutral is active.
    :param phA: Whether phase A is active.
    :param phB: Whether phase B is active.
    :param phC: Whether phase C is active.
    :param frequency_hz: Common sinusoidal frequency in Hz.
    :param phase_angle_deg: Optional phase offsets in degrees by phase label.
    :param offset_values: Optional DC offsets by phase label.
    :param source_conductance_value: Common Norton conductance.
    :param name: Optional symbolic block name.
    :return: Configured EMT template.
    """
    active_labels: List[str] = _get_active_nabc_labels(phN=phN, phA=phA, phB=phB, phC=phC)
    resolved_name: str = _build_source_template_name("controlled_voltage_source_emt", phN, phA, phB, phC, name)
    template: EmtModelTemplate = EmtModelTemplate()
    template.tpe = DeviceType.GeneratorDevice
    template.name = resolved_name
    template.block.name = resolved_name

    frequency_var: Var = vf.add_var(name=f"f_src")
    source_conductance_var: Var = vf.add_var(name=f"g_src")
    template.block.event_dict[frequency_var] = vf.add_const(float(frequency_hz))
    template.block.event_dict[source_conductance_var] = vf.add_const(float(source_conductance_value))
    theta_var: Var = vf.add_var(name=f"theta_src")
    d_theta_var: Var = vf.add_diff_var(name=f"d_theta_src", base_var=theta_var)

    voltage_vars: Dict[str, Var] = dict()
    current_vars: Dict[str, Var] = dict()
    in_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    out_vars: List[Var] = list()
    phase_label: str

    for phase_label in active_labels:
        voltage_var: Var = vf.add_var(name=f"v_{phase_label}", reference=_get_voltage_reference(phase_label))
        current_var: Var = vf.add_var(name=f"i_{phase_label}", reference=_get_current_reference(phase_label))
        amplitude_command_var: Var = vf.add_var(name=f"v_amp_cmd_{phase_label}")
        phase_deg_var: Var = vf.add_var(name=f"phi_deg_{phase_label}")
        offset_var: Var = vf.add_var(name=f"V_offset_{phase_label}")
        template.block.event_dict[phase_deg_var] = vf.add_const(_resolve_phase_value(phase_angle_deg, phase_label, 0.0))
        template.block.event_dict[offset_var] = vf.add_const(_resolve_phase_value(offset_values, phase_label, 0.0))
        voltage_vars[phase_label] = voltage_var
        current_vars[phase_label] = current_var
        in_vars.append(voltage_var)
        in_vars.append(amplitude_command_var)
        algebraic_vars.append(current_var)
        # Use the commanded Norton current at startup as well as during simulation.
        source_current_expr: Expr = source_conductance_var * (
            _build_sinusoidal_wave_expression(amplitude_command_var, theta_var, phase_deg_var, offset_var) - voltage_var)
        algebraic_eqs.append(current_var - source_current_expr)
        out_vars.append(current_var)
        template.block.init_eqs[current_var] = source_current_expr

    template.block.in_vars = in_vars
    template.block.state_vars = [theta_var]
    template.block.diff_vars = [d_theta_var]
    template.block.state_eqs = [sym.Const(2.0) * sym.Const(3.141592653589793) * frequency_var]
    template.block.algebraic_vars = algebraic_vars
    template.block.algebraic_eqs = algebraic_eqs
    template.block.out_vars = out_vars
    template.block.external_mapping = _build_external_mapping(voltage_vars, current_vars)
    template.block.init_eqs[theta_var] = sym.Const(0.0)
    return template
