from __future__ import annotations

import copy
import math
from typing import Dict, Iterable, List, Set, Tuple

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    DgsDirectRootBuildResult,
    DgsSlotSignalDirection,
    ElmCompInstanceEntry,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import (
    DeviceType,
    ParamPowerFlowReferenceType,
    SynchronousMachineSpeedVariationMode,
    VarPowerFlowReferenceType,
)


def _float_tuple(values: Iterable[float]) -> Tuple[float, ...]:
    """Copy an iterable into an immutable tuple of floats.

    :param values: Numeric source values.
    :return: Immutable float tuple.
    """
    result_values: List[float] = list()
    source_value: float
    for source_value in values:
        result_values.append(float(source_value))
    else:
        pass
    return tuple(result_values)








def is_dgs_elmsym_direct_slot_contract(
        direct_result: DgsDirectRootBuildResult,
) -> bool:
    """Validate one synchronous-machine boundary from transient DGS entries.

    :param direct_result: Direct root and exact source-slot relations.
    :return: ``True`` for one complete resolved ElmSym equipment slot.
    """
    matching_count: int = 0
    direct_entry: ElmCompInstanceEntry
    required_outputs: Set[str] = set([
        "ID", "IQ", "IFDIEEE", "RPOWER", "SG", "VT", "VTD",
        "VTQ", "cosn", "speed",
    ])
    required_inputs: Set[str] = set(["pt", "ve"])

    for direct_entry in direct_result.direct_entries:
        if (
                direct_entry.element_reference_is_resolved
                and direct_entry.element_kind == "ElmSym"
                and required_outputs.issubset(set(
                    direct_entry.get_slot_signal_components(
                        direction=DgsSlotSignalDirection.Output,
                    )
                ))
                and required_inputs.issubset(set(
                    direct_entry.get_slot_signal_components(
                        direction=DgsSlotSignalDirection.Input,
                    )
                ))
        ):
            matching_count += 1
        else:
            pass
    else:
        pass
    return matching_count == 1


def _find_direct_declared_slot_output(
        direct_result: DgsDirectRootBuildResult,
        candidate_names: Iterable[str],
) -> Var | None:
    """Resolve one public cable from its exact transient slot relation.

    :param direct_result: Direct root with slot-to-child lookup.
    :param candidate_names: Public cable aliases in priority order.
    :return: Exact child output variable, or ``None`` when unresolved.
    """
    candidate_name: str
    direct_entry: ElmCompInstanceEntry
    outgoing_index: int
    outgoing_name: str
    child_block: Block | None
    child_output: Var

    for candidate_name in candidate_names:
        for direct_entry in direct_result.direct_entries:
            if direct_entry.slot_id is None:
                pass
            else:
                child_block = direct_result.child_block_by_slot_id.get(
                    direct_entry.slot_id,
                    None,
                )
                if child_block is None:
                    pass
                else:
                    for outgoing_index, outgoing_name in enumerate(
                            direct_entry.get_slot_signal_components(
                                direction=DgsSlotSignalDirection.Output,
                            )
                    ):
                        if outgoing_name == candidate_name:
                            for child_output in child_block.out_vars:
                                if child_output.name == outgoing_name:
                                    return child_output
                                else:
                                    pass
                            else:
                                pass
                            if outgoing_index < len(child_block.out_vars):
                                return child_block.out_vars[outgoing_index]
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
        else:
            pass
    else:
        pass
    return None


def _direct_declared_slot_output_is_unconnected(
        direct_result: DgsDirectRootBuildResult,
        candidate_names: Iterable[str],
) -> bool:
    """Detect one declared public output whose source element is empty.

    :param direct_result: Direct root with validated transient relations.
    :param candidate_names: Public cable aliases accepted by the equipment.
    :return: ``True`` only for an exact empty slot exposing one alias.
    """
    candidate_name_set: Set[str] = set(candidate_names)
    direct_entry: ElmCompInstanceEntry

    for direct_entry in direct_result.direct_entries:
        if (
                direct_entry.element_id is None
                and not candidate_name_set.isdisjoint(set(
                    direct_entry.get_slot_signal_components(
                        direction=DgsSlotSignalDirection.Output,
                    )
                ))
        ):
            return True
        else:
            pass
    else:
        pass
    return False


def _collect_direct_declared_controller_machine_inputs(
        direct_result: DgsDirectRootBuildResult,
) -> Set[str]:
    """Collect exact equipment signals consumed by instantiated controllers.

    :param direct_result: Direct root with transient slot and child relations.
    :return: Exact machine signal names proven to have controller consumers.
    """
    result: Set[str] = set()
    candidate_block: Block
    candidate_input: Var
    direct_entry: ElmCompInstanceEntry
    child_block: Block | None

    for candidate_block in direct_result.root_block.get_all_blocks():
        for candidate_input in candidate_block.in_vars:
            result.add(candidate_input.name)
        else:
            pass
    else:
        pass

    for direct_entry in direct_result.direct_entries:
        if (
                direct_entry.element_kind == "ElmSym"
                or direct_entry.accepts_element_kind(element_kind="ElmSym")
                or direct_entry.slot_id is None
                or len(direct_entry.get_slot_signal_components(
                    direction=DgsSlotSignalDirection.Input,
                )) != 1
        ):
            pass
        else:
            child_block = direct_result.child_block_by_slot_id.get(
                direct_entry.slot_id,
                None,
            )
            if child_block is not None and len(child_block.in_vars) > 0:
                result.add(direct_entry.get_slot_signal_components(
                    direction=DgsSlotSignalDirection.Input,
                )[0])
            else:
                pass
    else:
        pass
    return result


def _connect_direct_declared_slot_input(
        direct_result: DgsDirectRootBuildResult,
        signal_name: str,
        equipment_var: Var,
) -> int:
    """Replace one exact single-input child cable from transient slot data.

    :param direct_result: Direct root with transient slot and child relations.
    :param signal_name: Native equipment cable name.
    :param equipment_var: Canonical physical-equipment variable.
    :return: Number of distinct child inputs replaced.
    """
    result: int = 0
    replaced_uids: Set[int] = set()
    direct_entry: ElmCompInstanceEntry
    child_block: Block | None
    old_input: Var

    for direct_entry in direct_result.direct_entries:
        if (
                direct_entry.slot_id is None
                or len(direct_entry.get_slot_signal_components(
                    direction=DgsSlotSignalDirection.Input,
                )) != 1
                or direct_entry.get_slot_signal_components(
                    direction=DgsSlotSignalDirection.Input,
                )[0] != signal_name
        ):
            pass
        else:
            child_block = direct_result.child_block_by_slot_id.get(
                direct_entry.slot_id,
                None,
            )
            if child_block is None or len(child_block.in_vars) == 0:
                pass
            else:
                old_input = child_block.in_vars[0]
                if old_input.uid in replaced_uids:
                    pass
                else:
                    direct_result.root_block.update_model(old_input, equipment_var)
                    replaced_uids.add(old_input.uid)
                    result += 1
    else:
        pass
    return result


def _find_first_named_var_recursive(
        block: Block,
        candidate_names: Iterable[str],
) -> Var | None:
    """Find the first exact variable from an ordered alias set.

    :param block: Root block searched depth first.
    :param candidate_names: Native signal aliases in priority order.
    :return: Matching variable or ``None``.
    """
    candidate_name: str
    variable_group: Iterable[Var]
    variable: Var
    child_block: Block
    child_result: Var | None
    variable_groups: List[Iterable[Var]] = list([
        block.out_vars,
        block.algebraic_vars,
        block.state_vars,
        block.in_vars,
        list(block.event_dict.keys()),
    ])

    for candidate_name in candidate_names:
        for variable_group in variable_groups:
            for variable in variable_group:
                if variable.name == candidate_name:
                    return variable
                else:
                    pass
        for child_block in block.children:
            child_result = _find_first_named_var_recursive(
                block=child_block,
                candidate_names=list([candidate_name]),
            )
            if child_result is None:
                pass
            else:
                return child_result
    return None






def _connect_named_controller_inputs(
        block: Block,
        signal_name: str,
        equipment_var: Var,
) -> int:
    """Connect every exact controller input occurrence to equipment output.

    :param block: Imported controller root updated in place.
    :param signal_name: Exact PowerFactory cable component name.
    :param equipment_var: Canonical physical-machine variable.
    :return: Number of distinct consumer UIDs replaced.
    """
    matching_inputs: List[Var] = list()
    matching_uids: Set[int] = set()
    candidate_block: Block
    input_var: Var

    for candidate_block in block.get_all_blocks():
        for input_var in candidate_block.in_vars:
            if input_var.name == signal_name and input_var.uid not in matching_uids:
                matching_inputs.append(input_var)
                matching_uids.add(input_var.uid)
            else:
                pass
    for input_var in matching_inputs:
        block.update_model(input_var, equipment_var)
    return len(matching_inputs)






def install_unconnected_dgs_control_input_defaults(
        block: Block,
        equipment_signals: Dict[str, Var],
) -> None:
    """Retain zero baselines for genuinely unconnected PowerFactory inputs.

    A disconnected DSL input evaluates to zero in PowerFactory.  Direct-root
    construction exposes those inputs so meters and external events can bind
    them later.  Once the physical machine cables have been resolved, every
    remaining unbound root input must therefore remain an event-capable
    parameter with the native zero baseline.

    :param block: Imported controller root after machine cable substitution.
    :param equipment_signals: Canonical machine variables already connected.
    :return: None.
    """
    equipment_uids: Set[int] = set(
        equipment_var.uid for equipment_var in equipment_signals.values()
    )
    existing_event_uids: Set[int] = set()
    produced_uids: Set[int] = set()
    externally_mapped_uids: Set[int] = set()
    candidate_block: Block
    event_var: Var
    produced_var: Var
    mapped_var: Var | None
    input_var: Var

    for candidate_block in block.get_all_blocks():
        for event_var in candidate_block.event_dict.keys():
            existing_event_uids.add(event_var.uid)
        else:
            pass
        for produced_var in candidate_block.state_vars:
            produced_uids.add(produced_var.uid)
        else:
            pass
        for produced_var in candidate_block.algebraic_vars:
            produced_uids.add(produced_var.uid)
        else:
            pass
        for produced_var in candidate_block.out_vars:
            produced_uids.add(produced_var.uid)
        else:
            pass
        for mapped_var in candidate_block.external_mapping.values():
            if mapped_var is None:
                pass
            else:
                externally_mapped_uids.add(mapped_var.uid)
        else:
            pass
    for candidate_block in block.get_all_blocks():
        for input_var in candidate_block.in_vars:
            if (
                    input_var.uid in equipment_uids
                    or input_var.uid in existing_event_uids
                    or input_var.uid in produced_uids
                    or input_var.uid in externally_mapped_uids
            ):
                pass
            else:
                block.event_dict[input_var] = Const(0.0)
                existing_event_uids.add(input_var.uid)
        else:
            pass
    else:
        pass


def build_dgs_elmsym_rms_runtime_template(
        control_template: RmsModelTemplate,
        clone_control_block: bool = True,
        direct_result: DgsDirectRootBuildResult | None = None,
) -> RmsModelTemplate | None:
    """Create a pending typed adapter for one native ``ElmSym`` composite.

    The controller can be deduplicated before a physical host is known. The
    synchronous-machine equations are materialized during exact FID activation,
    because rotor structure and validation depend on that host's ``TypSym``.

    :param control_template: Imported controller-only RMS root.
    :param clone_control_block: Clone reusable GUI input before adaptation.
    :param direct_result: Optional transient direct-root conversion context.
    :return: Pending Generator template or ``None`` for another slot contract.
    """
    control_block: Block
    if clone_control_block:
        control_block = copy.deepcopy(control_template.block)
    else:
        control_block = control_template.block
    direct_contract_is_valid: bool = False
    if direct_result is None:
        pass
    else:
        direct_contract_is_valid = is_dgs_elmsym_direct_slot_contract(
            direct_result=direct_result,
        )
    if direct_contract_is_valid:
        result: RmsModelTemplate = RmsModelTemplate(name=control_template.name)
        result.name = control_template.name
        result.tpe = DeviceType.GeneratorDevice
        result.block = control_block
        result.block.dynamic_model_contract.dgs_elmsym_runtime_adapter_pending = True
        return result
    else:
        return None


def _machine_parameter_contract_is_valid(device: Generator) -> bool:
    """Validate parameters required by the supported standard RMS machine.

    :param device: Exact DGS synchronous-machine host.
    :return: ``True`` when the DGS contains a finite physical parameter set.
    """
    strictly_positive_values: Tuple[float, ...] = (
        float(device.rms_acceleration_time_constant),
        float(device.Snom),
        float(device.rated_power_factor),
        float(device.Xd),
        float(device.Xq),
        float(device.Xd_prime),
        float(device.Xd_2prime),
        float(device.Xq_2prime),
        float(device.Td0_prime),
        float(device.Td0_2prime),
        float(device.Tq0_2prime),
    )
    nonnegative_values: Tuple[float, ...] = (
        float(device.Rs),
        float(device.Xl),
        float(device.Tq0_prime),
        float(device.rms_dpu),
        float(device.rms_dkd),
        float(device.rms_dpe),
        float(device.rms_rotor_coupling_reactance_d),
        float(device.rms_rotor_coupling_reactance_q),
        float(device.rms_td_prime_short_circuit),
        float(device.rms_tq_prime_short_circuit),
        float(device.rms_td_2prime_short_circuit),
        float(device.rms_tq_2prime_short_circuit),
    )
    value: float

    for value in strictly_positive_values:
        if math.isfinite(value) and value > 0.0:
            pass
        else:
            return False
    for value in nonnegative_values:
        if math.isfinite(value) and value >= 0.0:
            pass
        else:
            return False
    if float(device.Xd) >= float(device.Xd_prime) >= float(device.Xd_2prime):
        pass
    else:
        return False
    if float(device.Xq) >= float(device.Xq_2prime):
        pass
    else:
        return False
    if float(device.Tq0_prime) > 0.0:
        return float(device.Xq_prime) >= float(device.Xq_2prime)
    else:
        return True


class _PowerFactoryEquivalentCircuit:
    """Hold the exact rotor circuit derived from one ``TypSym`` record."""

    __slots__ = (
        "xad", "xaq", "xrld", "xrlq", "xfd", "x1d", "x1q", "x2q",
        "t_sigma_fd", "t_sigma_1d", "t_sigma_1q", "t_sigma_2q",
        "excitation_current_base", "excitation_voltage_base_ratio",
        "saturation_curve_type", "saturation_axis_mode",
        "saturation_smoothing_factor",
        "speed_variation_mode",
        "saturation_voltage_points", "saturation_excitation_points",
        "saturation_sg10", "saturation_sg12",
        "saturation_q_voltage_points", "saturation_q_excitation_points",
        "saturation_sg10q", "saturation_sg12q",
    )

    def __init__(
            self,
            xad: float,
            xaq: float,
            xrld: float,
            xrlq: float,
            xfd: float,
            x1d: float,
            x1q: float,
            x2q: float,
            t_sigma_fd: float,
            t_sigma_1d: float,
            t_sigma_1q: float,
            t_sigma_2q: float,
            excitation_current_base: float,
            excitation_voltage_base_ratio: float,
            saturation_curve_type: int,
            saturation_axis_mode: int,
            saturation_smoothing_factor: float,
            speed_variation_mode: SynchronousMachineSpeedVariationMode,
            saturation_voltage_points: Tuple[float, ...],
            saturation_excitation_points: Tuple[float, ...],
            saturation_sg10: float,
            saturation_sg12: float,
            saturation_q_voltage_points: Tuple[float, ...],
            saturation_q_excitation_points: Tuple[float, ...],
            saturation_sg10q: float,
            saturation_sg12q: float,
    ) -> None:
        """Create an immutable-size equivalent-circuit value object.

        :param xad: d-axis mutual reactance in p.u.
        :param xaq: q-axis mutual reactance in p.u.
        :param xrld: Field-to-damper coupling reactance in p.u.
        :param xrlq: q-axis damper coupling reactance in p.u.
        :param xfd: Field-winding leakage reactance in p.u.
        :param x1d: d-axis damper leakage reactance in p.u.
        :param x1q: First q-axis damper leakage reactance in p.u.
        :param x2q: Second q-axis damper leakage reactance in p.u.
        :param t_sigma_fd: Field-winding rotor time constant in seconds.
        :param t_sigma_1d: d-axis damper rotor time constant in seconds.
        :param t_sigma_1q: First q-axis damper time constant in seconds.
        :param t_sigma_2q: Second q-axis damper time constant in seconds.
        :param excitation_current_base: Reciprocal excitation-current base.
        :param excitation_voltage_base_ratio: Exciter voltage base ratio.
        :param saturation_curve_type: Native saturation-curve selector.
        :param saturation_axis_mode: Native saturation-axis selector.
        :param saturation_smoothing_factor: Native tabular smoothing factor.
        :param speed_variation_mode: Native speed treatment in stator-voltage equations.
        :param saturation_voltage_points: Main-flux curve coordinates.
        :param saturation_excitation_points: Excitation-current coordinates.
        :param saturation_sg10: Saturation coefficient at 1.0 p.u. flux.
        :param saturation_sg12: Saturation coefficient at 1.2 p.u. flux.
        :param saturation_q_voltage_points: q-axis curve coordinates.
        :param saturation_q_excitation_points: q-axis excitation coordinates.
        :param saturation_sg10q: q-axis saturation at 1.0 p.u. flux.
        :param saturation_sg12q: q-axis saturation at 1.2 p.u. flux.
        :return: None.
        """
        self.xad: float = float(xad)
        self.xaq: float = float(xaq)
        self.xrld: float = float(xrld)
        self.xrlq: float = float(xrlq)
        self.xfd: float = float(xfd)
        self.x1d: float = float(x1d)
        self.x1q: float = float(x1q)
        self.x2q: float = float(x2q)
        self.t_sigma_fd: float = float(t_sigma_fd)
        self.t_sigma_1d: float = float(t_sigma_1d)
        self.t_sigma_1q: float = float(t_sigma_1q)
        self.t_sigma_2q: float = float(t_sigma_2q)
        self.excitation_current_base: float = float(excitation_current_base)
        self.excitation_voltage_base_ratio: float = float(
            excitation_voltage_base_ratio
        )
        self.saturation_curve_type: int = int(saturation_curve_type)
        self.saturation_axis_mode: int = int(saturation_axis_mode)
        self.saturation_smoothing_factor: float = float(
            saturation_smoothing_factor
        )
        self.speed_variation_mode: SynchronousMachineSpeedVariationMode = (
            speed_variation_mode
        )
        self.saturation_voltage_points: Tuple[float, ...] = tuple(
            saturation_voltage_points
        )
        self.saturation_excitation_points: Tuple[float, ...] = tuple(
            saturation_excitation_points
        )
        self.saturation_sg10: float = float(saturation_sg10)
        self.saturation_sg12: float = float(saturation_sg12)
        self.saturation_q_voltage_points: Tuple[float, ...] = tuple(
            saturation_q_voltage_points
        )
        self.saturation_q_excitation_points: Tuple[float, ...] = tuple(
            saturation_q_excitation_points
        )
        self.saturation_sg10q: float = float(saturation_sg10q)
        self.saturation_sg12q: float = float(saturation_sg12q)


def _build_raised_cosine_smoothed_positive_part(
        displacement: Expr,
        half_width: float,
) -> Expr:
    """Build the native compact positive-part transition at one corner.

    Native ordinate-perturbation sweeps identify a raised-cosine derivative
    inside the smoothing interval.  Integrating that derivative produces a
    compact transition which is exactly zero below the interval and exactly
    linear above it.  Its scale depends only on the exported smoothing factor
    and adjacent DGS abscissae; no machine-specific coefficient is fitted.

    :param displacement: Runtime abscissa relative to the curve corner.
    :param half_width: Positive half-width of the compact transition.
    :return: Smoothed equivalent of ``max(displacement, 0)``.
    """
    half_width_expr: Const = Const(half_width)
    negative_half_width_expr: Const = Const(-half_width)
    clamped_displacement: Expr = sym.max(
        negative_half_width_expr,
        sym.min(displacement, half_width_expr),
    )
    positive_linear_tail: Expr = sym.max(
        displacement - half_width_expr,
        Const(0.0),
    )
    smoothed_positive_part: Expr = (
        positive_linear_tail
        + Const(0.5) * (clamped_displacement + half_width_expr)
        - Const(half_width / math.pi)
        * sym.cos(
            Const(math.pi / (2.0 * half_width)) * clamped_displacement
        )
    )
    return smoothed_positive_part


def _build_tabular_saturation_coefficient(
        flux_magnitude: Expr,
        voltage_points: Tuple[float, ...],
        excitation_points: Tuple[float, ...],
        smoothing_factor: float = 0.0,
) -> Expr:
    """Build the native tabular ``SG(u)`` curve as a continuous expression.

    PowerFactory serialises ``TypSym.satv`` as magnetising flux and
    ``TypSym.satse`` as the normalised saturation ordinate ``SG(u)``.  The
    native curve interpolates the physical saturation increment
    ``delta_psi = psi * SG(psi)`` and divides the result by the instantaneous
    flux afterwards.  Interpolating ``SG`` directly changes the in-segment
    law even when the native smoothing factor is zero.

    Linear continuation outside the table preserves the end-segment law from
    the DGS without a case-specific clamp.

    :param flux_magnitude: Runtime magnetising-flux magnitude in p.u.
    :param voltage_points: Strictly increasing curve abscissae.
    :param excitation_points: Aligned native ``SG(u)`` ordinates.
    :param smoothing_factor: Native smoothing interval in percent.
    :return: Runtime saturation coefficient ``csat``.
    """
    zero: Const = Const(0.0)
    point_count: int = min(len(voltage_points), len(excitation_points))
    valid_curve: bool = point_count >= 2
    point_index: int
    if valid_curve:
        for point_index in range(1, point_count):
            if voltage_points[point_index] > voltage_points[point_index - 1]:
                pass
            else:
                valid_curve = False
        else:
            pass
    else:
        pass
    if valid_curve:
        # Reconstruct the physical saturation increment stored implicitly by
        # every normalised DGS point.  PowerFactory interpolates this quantity,
        # which preserves the electromagnetic meaning of the saturation table.
        saturation_increment_points: List[float] = list(
            voltage_points[point_index] * excitation_points[point_index]
            for point_index in range(point_count)
        )
        first_slope: float = (
            saturation_increment_points[1] - saturation_increment_points[0]
        ) / (
            voltage_points[1] - voltage_points[0]
        )
        saturation_increment_curve: Expr = (
            Const(saturation_increment_points[0])
            + Const(first_slope)
            * (flux_magnitude - Const(voltage_points[0]))
        )
        previous_slope: float = first_slope
        bounded_smoothing_factor: float = min(
            100.0,
            max(0.0, float(smoothing_factor)),
        )
        for point_index in range(1, point_count - 1):
            next_slope: float = (
                saturation_increment_points[point_index + 1]
                - saturation_increment_points[point_index]
            ) / (
                voltage_points[point_index + 1]
                - voltage_points[point_index]
            )
            corner_displacement: Expr = (
                flux_magnitude - Const(voltage_points[point_index])
            )
            if bounded_smoothing_factor > 0.0:
                # Convert the exported percentage to the compact transition
                # half-width on the smaller adjacent segment.  The native
                # interval spans the requested percentage in total, half on
                # either side of the slope corner.
                left_interval: float = (
                    voltage_points[point_index]
                    - voltage_points[point_index - 1]
                )
                right_interval: float = (
                    voltage_points[point_index + 1]
                    - voltage_points[point_index]
                )
                smoothing_half_width: float = (
                    0.5
                    * bounded_smoothing_factor
                    / 100.0
                    * min(left_interval, right_interval)
                )
                rounded_positive_part: Expr = (
                    _build_raised_cosine_smoothed_positive_part(
                        displacement=corner_displacement,
                        half_width=smoothing_half_width,
                    )
                )
            else:
                rounded_positive_part = sym.max(corner_displacement, zero)
            saturation_increment_curve = (
                saturation_increment_curve
                + Const(next_slope - previous_slope)
                * rounded_positive_part
            )
            previous_slope = next_slope
        else:
            pass
        # Convert the interpolated physical increment back to the normalised
        # coefficient used by the machine equations.  The flux expression is
        # already regularised at construction, while the epsilon protects this
        # helper when it is exercised independently by importing tests.
        epsilon: Const = Const(1.0e-12)
        coefficient: Expr = sym.max(
            saturation_increment_curve / (flux_magnitude + epsilon),
            zero,
        )
    else:
        coefficient = zero
    return coefficient


def _build_analytic_saturation_coefficient(
        flux_magnitude: Expr,
        curve_type: int,
        sg10: float,
        sg12: float,
) -> Expr:
    """Build a quadratic or exponential two-point saturation law.

    :param flux_magnitude: Runtime magnetising-flux magnitude in p.u.
    :param curve_type: Native curve selector, zero quadratic and one exponential.
    :param sg10: Saturation value at 1.0 p.u. flux.
    :param sg12: Saturation value at 1.2 p.u. flux.
    :return: Runtime saturation coefficient ``csat``.
    """
    zero: Const = Const(0.0)
    epsilon: Const = Const(1.0e-12)
    valid_points: bool = bool(sg10 > 0.0 and sg12 > 0.0)
    if valid_points and curve_type == 1:
        exponent: float = math.log(1.2 * sg12 / sg10) / math.log(1.2)
        coefficient: Expr = (
            Const(sg10) * flux_magnitude ** Const(exponent)
        )
    else:
        if valid_points:
            saturation_ratio_root: float = math.sqrt(1.2 * sg12 / sg10)
            denominator: float = 1.0 - saturation_ratio_root
            if abs(denominator) > 1.0e-12:
                intercept: float = (1.2 - saturation_ratio_root) / denominator
                gain: float = sg10 / ((1.0 - intercept) ** 2)
                coefficient = (
                    Const(gain)
                    * sym.max(flux_magnitude - Const(intercept), zero) ** Const(2.0)
                    / (flux_magnitude + epsilon)
                )
            else:
                coefficient = zero
        else:
            coefficient = zero
    return coefficient


def _build_saturation_coefficient(
        flux_magnitude: Expr,
        curve_type: int,
        voltage_points: Tuple[float, ...],
        excitation_points: Tuple[float, ...],
        smoothing_factor: float,
        sg10: float,
        sg12: float,
) -> Expr:
    """Select the native main-flux saturation curve representation.

    :param flux_magnitude: Runtime magnetising-flux magnitude in p.u.
    :param curve_type: Native curve selector.
    :param voltage_points: Optional tabular abscissae.
    :param excitation_points: Optional tabular ordinates.
    :param smoothing_factor: Native tabular smoothing interval in percent.
    :param sg10: Saturation at 1.0 p.u. flux.
    :param sg12: Saturation at 1.2 p.u. flux.
    :return: Runtime saturation coefficient ``csat``.
    """
    if curve_type == 2:
        coefficient: Expr = _build_tabular_saturation_coefficient(
            flux_magnitude=flux_magnitude,
            voltage_points=voltage_points,
            excitation_points=excitation_points,
            smoothing_factor=smoothing_factor,
        )
    else:
        coefficient = _build_analytic_saturation_coefficient(
            flux_magnitude=flux_magnitude,
            curve_type=curve_type,
            sg10=sg10,
            sg12=sg12,
        )
    return coefficient


def _calculate_two_loop_equivalent_axis(
        synchronous_reactance: float,
        transient_reactance: float,
        subtransient_reactance: float,
        leakage_reactance: float,
        coupling_reactance: float,
        transient_short_circuit_time: float,
        subtransient_short_circuit_time: float,
) -> Tuple[float, float, float, float] | None:
    """Apply PowerFactory equations 49--53 to one two-loop rotor axis.

    :param synchronous_reactance: Axis synchronous reactance in p.u.
    :param transient_reactance: Axis transient reactance in p.u.
    :param subtransient_reactance: Axis subtransient reactance in p.u.
    :param leakage_reactance: Stator leakage reactance in p.u.
    :param coupling_reactance: Coupling reactance between rotor windings in p.u.
    :param transient_short_circuit_time: Short-circuit transient constant in seconds.
    :param subtransient_short_circuit_time: Short-circuit subtransient constant in seconds.
    :return: Slow/fast leakage reactances and time constants, or ``None``.
    """
    epsilon: float = 1.0e-12
    magnetizing_reactance: float = synchronous_reactance - leakage_reactance
    x1_help: float = magnetizing_reactance + coupling_reactance
    x2_help: float = (
        x1_help
        - magnetizing_reactance * magnetizing_reactance / synchronous_reactance
    )
    subtransient_ratio: float = (
        subtransient_reactance / synchronous_reactance
    )
    x3_denominator: float = 1.0 - subtransient_ratio
    if abs(x3_denominator) > epsilon:
        x3_help: float = (
            x2_help - x1_help * subtransient_ratio
        ) / x3_denominator
    else:
        return None
    time_1: float = (
        synchronous_reactance / transient_reactance
        * transient_short_circuit_time
        + (
            1.0
            - synchronous_reactance / transient_reactance
            + synchronous_reactance / subtransient_reactance
        ) * subtransient_short_circuit_time
    )
    time_2: float = (
        transient_short_circuit_time + subtransient_short_circuit_time
    )
    x12_difference: float = x1_help - x2_help
    x32_difference: float = x3_help - x2_help
    if abs(x12_difference) > epsilon and abs(x32_difference) > epsilon:
        quadratic_a: float = (
            x2_help * time_1 - x1_help * time_2
        ) / x12_difference
        quadratic_b: float = (
            x3_help / x32_difference
            * transient_short_circuit_time
            * subtransient_short_circuit_time
        )
        discriminant: float = quadratic_a * quadratic_a / 4.0 - quadratic_b
    else:
        return None
    if discriminant >= 0.0:
        discriminant_root: float = math.sqrt(discriminant)
        slow_time: float = -quadratic_a / 2.0 + discriminant_root
        fast_time: float = -quadratic_a / 2.0 - discriminant_root
    else:
        return None
    time_difference: float = time_1 - time_2
    if abs(time_difference) > epsilon and abs(x3_help) > epsilon:
        slow_denominator: float = (
            time_difference / x12_difference + fast_time / x3_help
        )
        fast_denominator: float = (
            time_difference / x12_difference + slow_time / x3_help
        )
    else:
        return None
    if abs(slow_denominator) > epsilon and abs(fast_denominator) > epsilon:
        slow_reactance: float = (
            slow_time - fast_time
        ) / slow_denominator
        fast_reactance: float = (
            fast_time - slow_time
        ) / fast_denominator
    else:
        return None
    candidate_values: Tuple[float, ...] = (
        slow_reactance, fast_reactance, slow_time, fast_time,
    )
    candidate_value: float
    for candidate_value in candidate_values:
        if math.isfinite(candidate_value) and candidate_value > 0.0:
            pass
        else:
            return None
    else:
        pass
    return slow_reactance, fast_reactance, slow_time, fast_time


def _calculate_powerfactory_equivalent_circuit(
        device: Generator,
) -> _PowerFactoryEquivalentCircuit | None:
    """Convert the stored DGS short-circuit contract to rotor parameters.

    The computation follows the public PowerFactory 2025 synchronous-machine
    technical reference exactly.  It is intentionally performed from the DGS
    values at RMS preparation time, so normal conversion never needs the
    licensed API and edits to the static machine remain effective.

    :param device: Generator that retained the source ``TypSym`` contract.
    :return: Exact equivalent circuit, or ``None`` for invalid source data.
    """
    direct_transient_short_time: float = float(
        device.rms_td_prime_short_circuit
    )
    if direct_transient_short_time > 0.0:
        pass
    else:
        direct_transient_short_time = (
            float(device.Td0_prime) * float(device.Xd_prime)
            / float(device.Xd)
        )
    direct_subtransient_short_time: float = float(
        device.rms_td_2prime_short_circuit
    )
    if direct_subtransient_short_time > 0.0:
        pass
    else:
        direct_subtransient_short_time = (
            float(device.Td0_2prime) * float(device.Xd_2prime)
            / float(device.Xd_prime)
        )
    round_rotor: bool = float(device.Tq0_prime) > 0.0
    quadrature_transient_short_time: float = float(
        device.rms_tq_prime_short_circuit
    )
    if quadrature_transient_short_time > 0.0 or not round_rotor:
        pass
    else:
        quadrature_transient_short_time = (
            float(device.Tq0_prime) * float(device.Xq_prime)
            / float(device.Xq)
        )
    quadrature_subtransient_short_time: float = float(
        device.rms_tq_2prime_short_circuit
    )
    if quadrature_subtransient_short_time > 0.0:
        pass
    else:
        if round_rotor:
            quadrature_subtransient_numerator: float = float(device.Xq_prime)
        else:
            quadrature_subtransient_numerator = float(device.Xq)
        quadrature_subtransient_short_time = (
            float(device.Tq0_2prime) * float(device.Xq_2prime)
            / quadrature_subtransient_numerator
        )

    d_axis: Tuple[float, float, float, float] | None = (
        _calculate_two_loop_equivalent_axis(
            synchronous_reactance=float(device.Xd),
            transient_reactance=float(device.Xd_prime),
            subtransient_reactance=float(device.Xd_2prime),
            leakage_reactance=float(device.Xl),
            coupling_reactance=float(device.rms_rotor_coupling_reactance_d),
            transient_short_circuit_time=direct_transient_short_time,
            subtransient_short_circuit_time=direct_subtransient_short_time,
        )
    )
    if d_axis is None:
        return None
    else:
        xfd: float = d_axis[0]
        x1d: float = d_axis[1]
        t_sigma_fd: float = d_axis[2]
        t_sigma_1d: float = d_axis[3]

    if round_rotor:
        q_axis: Tuple[float, float, float, float] | None = (
            _calculate_two_loop_equivalent_axis(
                synchronous_reactance=float(device.Xq),
                transient_reactance=float(device.Xq_prime),
                subtransient_reactance=float(device.Xq_2prime),
                leakage_reactance=float(device.Xl),
                coupling_reactance=float(
                    device.rms_rotor_coupling_reactance_q
                ),
                transient_short_circuit_time=quadrature_transient_short_time,
                subtransient_short_circuit_time=(
                    quadrature_subtransient_short_time
                ),
            )
        )
        if q_axis is None:
            return None
        else:
            x1q: float = q_axis[0]
            x2q: float = q_axis[1]
            t_sigma_1q: float = q_axis[2]
            t_sigma_2q: float = q_axis[3]
    else:
        q_axis_denominator: float = float(device.Xq) - float(device.Xq_2prime)
        if q_axis_denominator > 1.0e-12:
            x1q = (
                (float(device.Xq) - float(device.Xl))
                * (float(device.Xq_2prime) - float(device.Xl))
                / q_axis_denominator
            )
        else:
            return None
        rotor_rate: float = (
            float(device.Xq_2prime) / float(device.Xq)
            * (float(device.Xq) - float(device.Xl) + x1q)
            / quadrature_subtransient_short_time
        )
        if x1q > 0.0 and rotor_rate > 0.0 and math.isfinite(rotor_rate):
            t_sigma_1q = x1q / rotor_rate
            x2q = 0.0
            t_sigma_2q = 0.0
        else:
            return None

    equivalent: _PowerFactoryEquivalentCircuit = _PowerFactoryEquivalentCircuit(
        xad=float(device.Xd) - float(device.Xl),
        xaq=float(device.Xq) - float(device.Xl),
        xrld=float(device.rms_rotor_coupling_reactance_d),
        xrlq=float(device.rms_rotor_coupling_reactance_q),
        xfd=xfd,
        x1d=x1d,
        x1q=x1q,
        x2q=x2q,
        t_sigma_fd=t_sigma_fd,
        t_sigma_1d=t_sigma_1d,
        t_sigma_1q=t_sigma_1q,
        t_sigma_2q=t_sigma_2q,
        excitation_current_base=max(
            1.0e-12,
            float(device.rms_excitation_current_base),
        ),
        excitation_voltage_base_ratio=max(
            1.0e-12,
            float(device.rms_excitation_voltage_base_ratio),
        ),
        saturation_curve_type=int(device.rms_saturation_curve_type),
        saturation_axis_mode=int(device.rms_saturation_axis_mode),
        saturation_smoothing_factor=float(
            device.rms_saturation_smoothing_factor
        ),
        speed_variation_mode=device.rms_speed_variation_mode,
        saturation_voltage_points=_float_tuple(
            values=device.rms_saturation_voltage_points
        ),
        saturation_excitation_points=_float_tuple(
            values=device.rms_saturation_excitation_points
        ),
        saturation_sg10=float(device.rms_saturation_sg10),
        saturation_sg12=float(device.rms_saturation_sg12),
        saturation_q_voltage_points=_float_tuple(
            values=device.rms_saturation_q_voltage_points
        ),
        saturation_q_excitation_points=_float_tuple(
            values=device.rms_saturation_q_excitation_points
        ),
        saturation_sg10q=float(device.rms_saturation_sg10q),
        saturation_sg12q=float(device.rms_saturation_sg12q),
    )
    return equivalent


def _calculate_unsaturated_rated_field_voltage(device: Generator) -> float:
    """Calculate the native ``ve_rated`` signal from the rated machine point.

    PowerFactory's unsaturated ``ElmSym`` exposes the excitation voltage needed
    at rated terminal voltage, rated apparent power and rated power factor.  The
    DGS already carries the complete stator and reactance data, so this interface
    value is reproducible offline and must not default to one per unit.

    :param device: Synchronous generator with a validated physical contract.
    :return: Positive rated field voltage in the machine excitation coordinate.
    """
    rated_power_factor: float = abs(float(device.rated_power_factor))
    rated_reactive_power: float = math.sqrt(
        max(0.0, 1.0 - rated_power_factor * rated_power_factor)
    )
    stator_resistance: float = float(device.Rs)
    quadrature_reactance: float = float(device.Xq)
    direct_reactance: float = float(device.Xd)

    # At rated terminal voltage the internal q-axis phasor behind Xq fixes the
    # rotor reference.  Resolve it in rectangular coordinates to preserve the
    # correct quadrant without an avoidable inverse-trigonometric round trip.
    internal_voltage_real: float = (
        1.0
        + stator_resistance * rated_power_factor
        + quadrature_reactance * rated_reactive_power
    )
    internal_voltage_imaginary: float = (
        quadrature_reactance * rated_power_factor
        - stator_resistance * rated_reactive_power
    )
    internal_voltage_magnitude: float = math.hypot(
        internal_voltage_real,
        internal_voltage_imaginary,
    )
    if internal_voltage_magnitude > 1.0e-12:
        rotor_sine: float = (
            internal_voltage_imaginary / internal_voltage_magnitude
        )
        rotor_cosine: float = internal_voltage_real / internal_voltage_magnitude
        direct_current: float = (
            rated_power_factor * rotor_sine
            + rated_reactive_power * rotor_cosine
        )
        quadrature_current: float = (
            rated_power_factor * rotor_cosine
            - rated_reactive_power * rotor_sine
        )
        air_gap_base_field_voltage: float = (
            rotor_cosine
            + direct_reactance * direct_current
            + stator_resistance * quadrature_current
        )
        excitation_base_scale: float = (
            max(1.0e-12, float(device.rms_excitation_current_base))
            * max(
                1.0e-12,
                float(device.rms_excitation_voltage_base_ratio),
            )
        )
        rated_field_voltage: float = (
            air_gap_base_field_voltage / excitation_base_scale
        )
    else:
        rated_field_voltage = float("nan")

    if math.isfinite(rated_field_voltage) and rated_field_voltage > 1.0e-12:
        return rated_field_voltage
    else:
        return 1.0


def _calculate_machine_active_base_factor(device: Generator) -> float:
    """Return the non-singular active-power base used by machine dynamics.

    PowerFactory exports synchronous condensers with ``cosn`` close to zero so
    controllers can still recognize their nominal active-power capability.
    Rotor torque and electrical power remain expressed on the machine MVA base
    for that device class; dividing those equations by the near-zero marker
    would create a numerical singularity that is absent from the native model.

    :param device: Configured synchronous machine host.
    :return: Rated power factor for generators, or unity for a zero-P machine.
    """
    rated_power_factor: float = abs(float(device.rated_power_factor))
    if rated_power_factor > 1.0e-6:
        return rated_power_factor
    else:
        return 1.0


def _build_dgs_elmsym_runtime_block(
        control_block: Block,
        round_rotor: bool,
        equivalent_circuit: _PowerFactoryEquivalentCircuit,
        direct_result: DgsDirectRootBuildResult,
) -> Block | None:
    """Combine one imported controller with the standard RMS machine shell.

    :param control_block: Exact imported AVR/governor/PSS hierarchy.
    :param round_rotor: Include the q-axis transient winding when ``True``.
    :param equivalent_circuit: Exact rotor circuit derived from ``TypSym``.
    :param direct_result: Optional transient direct-root conversion context.
    :return: Complete assignable block or ``None`` for an incomplete cable set.
    """
    # Direct DGS composites declare public controller cables on each BlkSlot.
    # Resolve those structural ports first because a graphical child can retain
    # a different internal output name after private-wire normalization.
    turbine_power: Var | None = _find_direct_declared_slot_output(
        direct_result=direct_result,
        candidate_names=("pt", "PT"),
    )
    excitation_voltage: Var | None = _find_direct_declared_slot_output(
        direct_result=direct_result,
        candidate_names=("ve", "EFD", "efd", "Vf"),
    )
    if turbine_power is None:
        turbine_slot_is_unconnected: bool = (
            _direct_declared_slot_output_is_unconnected(
                direct_result=direct_result,
                candidate_names=("pt", "PT"),
            )
        )
        if turbine_slot_is_unconnected:
            # An optional governor slot without an element produces the exact
            # disconnected PowerFactory cable value throughout the run.
            turbine_power = Var(name="pt")
            control_block.event_dict[turbine_power] = Const(0.0)
        else:
            turbine_power = _find_first_named_var_recursive(
                block=control_block,
                candidate_names=("pt", "PT"),
            )
    else:
        pass
    if excitation_voltage is None:
        excitation_slot_is_unconnected: bool = (
            _direct_declared_slot_output_is_unconnected(
                direct_result=direct_result,
                candidate_names=("ve", "EFD", "efd", "Vf"),
            )
        )
        if excitation_slot_is_unconnected:
            # Empty optional excitation slots obey the same native zero-cable
            # rule as every other disconnected DSL controller output.
            excitation_voltage = Var(name="ve")
            control_block.event_dict[excitation_voltage] = Const(0.0)
        else:
            excitation_voltage = _find_first_named_var_recursive(
                block=control_block,
                candidate_names=("ve", "EFD", "efd", "Vf"),
            )
    else:
        pass
    if turbine_power is None or excitation_voltage is None:
        return None
    else:
        pt: Var = turbine_power
        ve: Var = excitation_voltage

    # Network-facing variables use the ordinary Generator RMS contract.
    terminal_voltage: Var = Var(
        name="Vm",
        reference=VarPowerFlowReferenceType.Vm,
    )
    terminal_angle: Var = Var(
        name="Va",
        reference=VarPowerFlowReferenceType.Va,
    )
    active_power_system: Var = Var(
        name="Pg",
        reference=VarPowerFlowReferenceType.P,
    )
    reactive_power_system: Var = Var(
        name="Qg",
        reference=VarPowerFlowReferenceType.Q,
    )

    # PowerFactory's standard model integrates physical rotor flux linkages.
    # Retaining those same states is essential during faults: an equivalent
    # transient-emf model has the same steady state but a different trajectory.
    rotor_angle: Var = Var(name="phi")
    speed: Var = Var(name="speed")
    field_flux: Var = Var(name="psifd")
    direct_damper_flux: Var = Var(name="psi1d")
    first_quadrature_damper_flux: Var = Var(name="psi1q")
    # The second q-axis damper loop exists only in the round-rotor topology.
    # A salient machine must not expose a dummy state constrained to zero.
    if round_rotor:
        second_quadrature_damper_flux: Var = Var(name="psi2q")
    else:
        pass

    # Algebraic outputs define both the network injection and native frame IO.
    active_power_machine: Var = Var(name="P_machine")
    reactive_power_machine: Var = Var(name="Q_machine")
    direct_voltage: Var = Var(name="VTD")
    quadrature_voltage: Var = Var(name="VTQ")
    direct_current: Var = Var(name="ID")
    quadrature_current: Var = Var(name="IQ")
    electrical_torque: Var = Var(name="Te")
    excitation_current: Var = Var(name="IFDIEEE")
    electrical_power_active_base: Var = Var(name="RPOWER")
    reciprocal_field_current: Var = Var(name="ifd")
    direct_damper_current: Var = Var(name="i1d")
    first_quadrature_damper_current: Var = Var(name="i1q")
    if round_rotor:
        second_quadrature_damper_current: Var = Var(name="i2q")
    else:
        pass
    direct_subtransient_flux: Var = Var(name="psi_d_2prime")
    quadrature_subtransient_flux: Var = Var(name="psi_q_2prime")
    direct_stator_flux: Var = Var(name="psi_d")
    quadrature_stator_flux: Var = Var(name="psi_q")
    main_flux_saturation_coefficient: Var = Var(name="csat")
    direct_saturation_factor: Var = Var(name="satd")
    quadrature_saturation_factor: Var = Var(name="satq")
    saturated_direct_mutual_reactance: Var = Var(name="xad_sat")
    saturated_quadrature_mutual_reactance: Var = Var(name="xaq_sat")
    saturated_direct_subtransient_reactance: Var = Var(name="Xd_2prime_sat")
    saturated_quadrature_subtransient_reactance: Var = Var(name="Xq_2prime_sat")

    # Static DGS machine parameters remain editable and are assigned through
    # Generator GCProp dynamic references during RMS compilation.
    nominal_frequency: Var = Var(name="fn")
    angular_frequency: Var = Var(name="omega_base")
    acceleration_time: Var = Var(name="M")
    stator_resistance: Var = Var(name="Rs")
    xd: Var = Var(name="Xd")
    xq: Var = Var(name="Xq")
    xd_transient: Var = Var(name="Xd_prime")
    xq_transient: Var = Var(name="Xq_prime")
    xd_subtransient: Var = Var(name="Xd_2prime")
    xq_subtransient: Var = Var(name="Xq_2prime")
    leakage_reactance: Var = Var(name="Xl")
    td_transient: Var = Var(name="Td0_prime")
    tq_transient: Var = Var(name="Tq0_prime")
    td_subtransient: Var = Var(name="Td0_2prime")
    tq_subtransient: Var = Var(name="Tq0_2prime")
    damping_friction: Var = Var(name="dpu")
    damping_torque: Var = Var(name="dkd")
    damping_power: Var = Var(name="dpe")
    system_power_base: Var = Var(name="Sbase")
    machine_power_base: Var = Var(name="SG")
    rated_power_factor: Var = Var(name="cosn")
    machine_active_base_factor: Var = Var(name="machine_active_base_factor")
    excitation_gain: Var = Var(name="Gm")
    rated_field_voltage: Var = Var(name="VFDrated")
    direct_mutual_reactance: Var = Var(name="xadu")
    quadrature_mutual_reactance: Var = Var(name="xaqu")
    direct_rotor_coupling_reactance: Var = Var(name="xrld")
    quadrature_rotor_coupling_reactance: Var = Var(name="xrlq")
    field_leakage_reactance: Var = Var(name="xfd")
    direct_damper_leakage_reactance: Var = Var(name="x1d")
    first_quadrature_damper_leakage_reactance: Var = Var(name="x1q")
    field_rotor_time: Var = Var(name="T_sigma_fd")
    direct_damper_rotor_time: Var = Var(name="T_sigma_1d")
    first_quadrature_damper_rotor_time: Var = Var(name="T_sigma_1q")
    if round_rotor:
        second_quadrature_damper_leakage_reactance: Var = Var(name="x2q")
        second_quadrature_damper_rotor_time: Var = Var(name="T_sigma_2q")
    else:
        pass
    field_coupling_factor: Var = Var(name="kfd")
    direct_damper_coupling_factor: Var = Var(name="k1d")
    first_quadrature_coupling_factor: Var = Var(name="k1q")
    direct_rotor_determinant: Var = Var(name="xdet_d")
    if round_rotor:
        second_quadrature_coupling_factor: Var = Var(name="k2q")
        quadrature_rotor_determinant: Var = Var(name="xdet_q")
    else:
        pass

    equipment_signals: Dict[str, Var] = dict()
    equipment_signals["speed"] = speed
    equipment_signals["VT"] = terminal_voltage
    equipment_signals["VTD"] = direct_voltage
    equipment_signals["VTQ"] = quadrature_voltage
    equipment_signals["ID"] = direct_current
    equipment_signals["IQ"] = quadrature_current
    equipment_signals["IFDIEEE"] = excitation_current
    equipment_signals["RPOWER"] = electrical_power_active_base
    equipment_signals["SG"] = machine_power_base
    # PowerFactory graphical base-change blocks expose the synchronous-machine
    # rated apparent power as ``SN`` even though the native ElmSym output cable
    # is named ``SG``. Both labels represent the same physical MVA quantity, so
    # connect both aliases before unbound inputs receive their zero baseline.
    equipment_signals["SN"] = machine_power_base
    equipment_signals["cosn"] = rated_power_factor
    equipment_signals["TD0S"] = td_transient
    equipment_signals["Gm"] = excitation_gain
    equipment_signals["VFDrated"] = rated_field_voltage
    declared_machine_inputs: Set[str] = (
        _collect_direct_declared_controller_machine_inputs(
            direct_result=direct_result,
        )
    )
    required_connection_names: Set[str] = (
        declared_machine_inputs & set(equipment_signals.keys())
    )
    signal_name: str
    equipment_var: Var
    connection_count: int
    for signal_name, equipment_var in equipment_signals.items():
        connection_count = _connect_named_controller_inputs(
            block=control_block,
            signal_name=signal_name,
            equipment_var=equipment_var,
        )
        if connection_count == 0 and signal_name in required_connection_names:
            connection_count = _connect_direct_declared_slot_input(
                direct_result=direct_result,
                signal_name=signal_name,
                equipment_var=equipment_var,
            )
        else:
            pass
        if signal_name in required_connection_names and connection_count == 0:
            return None
        else:
            pass

    # Preserve PowerFactory's defined zero value for every external controller
    # input that remains unconnected after the exact machine wiring pass.
    install_unconnected_dgs_control_input_defaults(
        block=control_block,
        equipment_signals=equipment_signals,
    )

    epsilon: Const = Const(1.0e-12)
    excitation_current_base_expr: Const = Const(
        equivalent_circuit.excitation_current_base
    )
    excitation_voltage_base_ratio_expr: Const = Const(
        equivalent_circuit.excitation_voltage_base_ratio
    )
    initial_stator_speed: Expr = (
        angular_frequency
        / (Const(2.0 * math.pi) * nominal_frequency)
    )
    if (
            equivalent_circuit.speed_variation_mode
            is SynchronousMachineSpeedVariationMode.Considered
    ):
        subtransient_flux_speed: Expr = speed
        subtransient_current_speed: Expr = speed
    elif (
            equivalent_circuit.speed_variation_mode
            is SynchronousMachineSpeedVariationMode.PartiallyNeglected
    ):
        # Native partial mode retains instantaneous speed on the subtransient
        # flux terms while freezing only the x'' current terms at initial speed.
        subtransient_flux_speed = speed
        subtransient_current_speed = initial_stator_speed
    else:
        # Native neglected mode freezes both stator-voltage contributions at
        # initial synchronous speed, derived from exported frequency symbols.
        subtransient_flux_speed = initial_stator_speed
        subtransient_current_speed = initial_stator_speed
    # PowerFactory applies ``i_speedVar`` to the stator-voltage equations but
    # evaluates the RMS main-flux dependency curve in its nominal-frequency
    # coordinate.  Native trajectory inversion across a dynamic AVR stimulus
    # confirms that this coordinate remains the initialized synchronous speed
    # even when instantaneous speed is retained in the voltage equations.
    saturation_speed: Expr = initial_stator_speed
    # The curve then uses the instantaneous voltage and current operating point
    # together with the complete TypSym table retained in the DGS.
    direct_magnetising_flux: Expr = (
        (
            quadrature_voltage
            + stator_resistance * quadrature_current
        ) / (saturation_speed + epsilon)
        + leakage_reactance * direct_current
    )
    quadrature_magnetising_flux: Expr = (
        -(
            direct_voltage + stator_resistance * direct_current
        ) / (saturation_speed + epsilon)
        + leakage_reactance * quadrature_current
    )
    magnetising_flux_magnitude: Expr = sym.sqrt(
        direct_magnetising_flux * direct_magnetising_flux
        + quadrature_magnetising_flux * quadrature_magnetising_flux
        + epsilon
    )
    direct_flux_magnitude: Expr = sym.sqrt(
        direct_magnetising_flux * direct_magnetising_flux + epsilon
    )
    quadrature_flux_magnitude: Expr = sym.sqrt(
        quadrature_magnetising_flux * quadrature_magnetising_flux + epsilon
    )
    common_saturation_coefficient_expr: Expr = _build_saturation_coefficient(
        flux_magnitude=magnetising_flux_magnitude,
        curve_type=equivalent_circuit.saturation_curve_type,
        voltage_points=equivalent_circuit.saturation_voltage_points,
        excitation_points=equivalent_circuit.saturation_excitation_points,
        smoothing_factor=equivalent_circuit.saturation_smoothing_factor,
        sg10=equivalent_circuit.saturation_sg10,
        sg12=equivalent_circuit.saturation_sg12,
    )
    direct_component_saturation_coefficient: Expr = (
        _build_saturation_coefficient(
            flux_magnitude=direct_flux_magnitude,
            curve_type=equivalent_circuit.saturation_curve_type,
            voltage_points=equivalent_circuit.saturation_voltage_points,
            excitation_points=equivalent_circuit.saturation_excitation_points,
            smoothing_factor=equivalent_circuit.saturation_smoothing_factor,
            sg10=equivalent_circuit.saturation_sg10,
            sg12=equivalent_circuit.saturation_sg12,
        )
    )
    quadrature_component_saturation_coefficient: Expr = (
        _build_saturation_coefficient(
            flux_magnitude=quadrature_flux_magnitude,
            curve_type=equivalent_circuit.saturation_curve_type,
            voltage_points=equivalent_circuit.saturation_q_voltage_points,
            excitation_points=equivalent_circuit.saturation_q_excitation_points,
            smoothing_factor=equivalent_circuit.saturation_smoothing_factor,
            sg10=equivalent_circuit.saturation_sg10q,
            sg12=equivalent_circuit.saturation_sg12q,
        )
    )
    saturation_axis_mode: int = equivalent_circuit.saturation_axis_mode
    if saturation_axis_mode == 4:
        direct_saturation_coefficient_expr: Expr = common_saturation_coefficient_expr
        quadrature_saturation_coefficient_expr: Expr = common_saturation_coefficient_expr
    elif saturation_axis_mode == 1:
        direct_saturation_coefficient_expr = common_saturation_coefficient_expr
        quadrature_saturation_coefficient_expr = Const(0.0)
    elif saturation_axis_mode == 2:
        direct_saturation_coefficient_expr = direct_component_saturation_coefficient
        quadrature_saturation_coefficient_expr = quadrature_component_saturation_coefficient
    elif saturation_axis_mode == 3:
        direct_saturation_coefficient_expr = direct_component_saturation_coefficient
        quadrature_saturation_coefficient_expr = Const(0.0)
    else:
        # Native mode zero uses one magnitude curve and scales q-axis
        # saturation by the unsaturated mutual-reactance ratio (equation 129).
        direct_saturation_coefficient_expr = common_saturation_coefficient_expr
        quadrature_saturation_coefficient_expr = (
            quadrature_mutual_reactance
            / (direct_mutual_reactance + epsilon)
            * common_saturation_coefficient_expr
        )
    mechanical_torque: Expr = (
        pt / (speed + epsilon)
        - damping_friction * speed
    )
    damping_torque_expr: Expr = damping_torque * (speed - Const(1.0))
    damping_power_expr: Expr = (
        damping_power
        * (speed - Const(1.0))
        / (speed + epsilon)
    )
    state_vars: List[Var] = list([
        rotor_angle,
        speed,
        field_flux,
        direct_damper_flux,
        first_quadrature_damper_flux,
    ])
    state_eqs: List[Expr] = list([
        angular_frequency * (speed - Const(1.0)),
        (
            mechanical_torque
            - electrical_torque
            - damping_torque_expr
            - damping_power_expr
        ) / acceleration_time,
        (
            field_leakage_reactance / field_rotor_time
            * (
                ve
                * excitation_current_base_expr
                * excitation_voltage_base_ratio_expr
                / direct_mutual_reactance
                - reciprocal_field_current
            )
        ),
        -direct_damper_leakage_reactance
        / direct_damper_rotor_time
        * direct_damper_current,
        -first_quadrature_damper_leakage_reactance
        / first_quadrature_damper_rotor_time
        * first_quadrature_damper_current,
    ])
    if round_rotor:
        state_vars.append(second_quadrature_damper_flux)
        state_eqs.append(
            -second_quadrature_damper_leakage_reactance
            / second_quadrature_damper_rotor_time
            * second_quadrature_damper_current
        )
    else:
        pass

    field_loop_reactance: Expr = (
        saturated_direct_mutual_reactance
        + direct_rotor_coupling_reactance
        + field_leakage_reactance
    )
    direct_damper_loop_reactance: Expr = (
        saturated_direct_mutual_reactance
        + direct_rotor_coupling_reactance
        + direct_damper_leakage_reactance
    )
    first_quadrature_loop_reactance: Expr = (
        saturated_quadrature_mutual_reactance
        + quadrature_rotor_coupling_reactance
        + first_quadrature_damper_leakage_reactance
    )
    if round_rotor:
        second_quadrature_loop_reactance: Expr = (
            saturated_quadrature_mutual_reactance
            + quadrature_rotor_coupling_reactance
            + second_quadrature_damper_leakage_reactance
        )
    else:
        pass

    algebraic_eqs: List[Expr] = list([
        main_flux_saturation_coefficient
        - common_saturation_coefficient_expr,
        direct_saturation_factor - (
            Const(1.0) / (Const(1.0) + direct_saturation_coefficient_expr)
        ),
        quadrature_saturation_factor - (
            Const(1.0) / (Const(1.0) + quadrature_saturation_coefficient_expr)
        ),
        saturated_direct_mutual_reactance - (
            direct_saturation_factor * direct_mutual_reactance
        ),
        saturated_quadrature_mutual_reactance - (
            quadrature_saturation_factor * quadrature_mutual_reactance
        ),
        direct_rotor_determinant - (
            (
                saturated_direct_mutual_reactance
                + direct_rotor_coupling_reactance
            ) * (
                direct_damper_leakage_reactance
                + field_leakage_reactance
            )
            + field_leakage_reactance
            * direct_damper_leakage_reactance
        ),
        field_coupling_factor - (
            saturated_direct_mutual_reactance
            * direct_damper_leakage_reactance
            / direct_rotor_determinant
        ),
        direct_damper_coupling_factor - (
            saturated_direct_mutual_reactance
            * field_leakage_reactance
            / direct_rotor_determinant
        ),
        saturated_direct_subtransient_reactance - (
            saturated_direct_mutual_reactance
            + leakage_reactance
            - (field_coupling_factor + direct_damper_coupling_factor)
            * saturated_direct_mutual_reactance
        ),
        direct_voltage - (-terminal_voltage * sym.sin(terminal_angle - rotor_angle)),
        quadrature_voltage - terminal_voltage * sym.cos(terminal_angle - rotor_angle),
        active_power_machine - (
            direct_voltage * direct_current
            + quadrature_voltage * quadrature_current
        ),
        reactive_power_machine - (
            quadrature_voltage * direct_current
            - direct_voltage * quadrature_current
        ),
        direct_voltage - (
            -subtransient_flux_speed * quadrature_subtransient_flux
            + subtransient_current_speed
            * saturated_quadrature_subtransient_reactance
            * quadrature_current
            - stator_resistance * direct_current
        ),
        quadrature_voltage - (
            subtransient_flux_speed * direct_subtransient_flux
            - subtransient_current_speed
            * saturated_direct_subtransient_reactance
            * direct_current
            - stator_resistance * quadrature_current
        ),
        active_power_system - (
            active_power_machine * machine_power_base / system_power_base
        ),
        reactive_power_system - (
            reactive_power_machine * machine_power_base / system_power_base
        ),
        electrical_torque - (
            (
                quadrature_current * direct_stator_flux
                - direct_current * quadrature_stator_flux
            ) / machine_active_base_factor
        ),
        excitation_current - (
            direct_mutual_reactance
            * reciprocal_field_current
            / excitation_current_base_expr
        ),
        electrical_power_active_base - (
            active_power_machine / machine_active_base_factor
        ),
        reciprocal_field_current - (
            field_coupling_factor * direct_current
            + (
                direct_damper_loop_reactance * field_flux
                - (
                    saturated_direct_mutual_reactance
                    + direct_rotor_coupling_reactance
                ) * direct_damper_flux
            ) / direct_rotor_determinant
        ),
        direct_damper_current - (
            direct_damper_coupling_factor * direct_current
            + (
                field_loop_reactance * direct_damper_flux
                - (
                    saturated_direct_mutual_reactance
                    + direct_rotor_coupling_reactance
                ) * field_flux
            ) / direct_rotor_determinant
        ),
        direct_subtransient_flux - (
            field_coupling_factor * field_flux
            + direct_damper_coupling_factor * direct_damper_flux
        ),
        direct_stator_flux - (
            direct_subtransient_flux
            - saturated_direct_subtransient_reactance * direct_current
        ),
        quadrature_stator_flux - (
            quadrature_subtransient_flux
            - saturated_quadrature_subtransient_reactance * quadrature_current
        ),
    ])
    if round_rotor:
        algebraic_eqs.append(
            quadrature_rotor_determinant - (
                (
                    saturated_quadrature_mutual_reactance
                    + quadrature_rotor_coupling_reactance
                ) * (
                    second_quadrature_damper_leakage_reactance
                    + first_quadrature_damper_leakage_reactance
                )
                + second_quadrature_damper_leakage_reactance
                * first_quadrature_damper_leakage_reactance
            )
        )
        algebraic_eqs.append(
            first_quadrature_coupling_factor - (
                saturated_quadrature_mutual_reactance
                * second_quadrature_damper_leakage_reactance
                / quadrature_rotor_determinant
            )
        )
        algebraic_eqs.append(
            second_quadrature_coupling_factor - (
                saturated_quadrature_mutual_reactance
                * first_quadrature_damper_leakage_reactance
                / quadrature_rotor_determinant
            )
        )
        algebraic_eqs.append(
            saturated_quadrature_subtransient_reactance - (
                saturated_quadrature_mutual_reactance
                + leakage_reactance
                - (
                    first_quadrature_coupling_factor
                    + second_quadrature_coupling_factor
                ) * saturated_quadrature_mutual_reactance
            )
        )
        algebraic_eqs.append(
            first_quadrature_damper_current - (
                first_quadrature_coupling_factor * quadrature_current
                + (
                    second_quadrature_loop_reactance
                    * first_quadrature_damper_flux
                    - (
                        saturated_quadrature_mutual_reactance
                        + quadrature_rotor_coupling_reactance
                    ) * second_quadrature_damper_flux
                ) / quadrature_rotor_determinant
            )
        )
        algebraic_eqs.append(
            second_quadrature_damper_current - (
                second_quadrature_coupling_factor * quadrature_current
                + (
                    first_quadrature_loop_reactance
                    * second_quadrature_damper_flux
                    - (
                        saturated_quadrature_mutual_reactance
                        + quadrature_rotor_coupling_reactance
                    ) * first_quadrature_damper_flux
                ) / quadrature_rotor_determinant
            )
        )
        algebraic_eqs.append(
            quadrature_subtransient_flux - (
                first_quadrature_coupling_factor
                * first_quadrature_damper_flux
                + second_quadrature_coupling_factor
                * second_quadrature_damper_flux
            )
        )
    else:
        algebraic_eqs.append(
            first_quadrature_coupling_factor - (
                saturated_quadrature_mutual_reactance
                / first_quadrature_loop_reactance
            )
        )
        algebraic_eqs.append(
            saturated_quadrature_subtransient_reactance - (
                saturated_quadrature_mutual_reactance
                + leakage_reactance
                - first_quadrature_coupling_factor
                * saturated_quadrature_mutual_reactance
            )
        )
        algebraic_eqs.append(
            first_quadrature_damper_current - (
                first_quadrature_coupling_factor * quadrature_current
                + first_quadrature_damper_flux
                / first_quadrature_loop_reactance
            )
        )
        algebraic_eqs.append(
            quadrature_subtransient_flux - (
                first_quadrature_coupling_factor
                * first_quadrature_damper_flux
            )
        )
    algebraic_vars: List[Var] = list([
        active_power_system,
        reactive_power_system,
        active_power_machine,
        reactive_power_machine,
        direct_voltage,
        quadrature_voltage,
        direct_current,
        quadrature_current,
        electrical_torque,
        excitation_current,
        electrical_power_active_base,
        reciprocal_field_current,
        direct_damper_current,
        first_quadrature_damper_current,
        direct_subtransient_flux,
        quadrature_subtransient_flux,
        direct_stator_flux,
        quadrature_stator_flux,
        main_flux_saturation_coefficient,
        direct_saturation_factor,
        quadrature_saturation_factor,
        saturated_direct_mutual_reactance,
        saturated_quadrature_mutual_reactance,
        saturated_direct_subtransient_reactance,
        saturated_quadrature_subtransient_reactance,
        field_coupling_factor,
        direct_damper_coupling_factor,
        first_quadrature_coupling_factor,
        direct_rotor_determinant,
    ])
    if round_rotor:
        algebraic_vars.append(second_quadrature_coupling_factor)
        algebraic_vars.append(quadrature_rotor_determinant)
        algebraic_vars.append(second_quadrature_damper_current)
    else:
        pass

    machine_active_power_initial: Expr = (
        active_power_system * system_power_base / machine_power_base
    )
    machine_reactive_power_initial: Expr = (
        reactive_power_system * system_power_base / machine_power_base
    )
    complex_power_initial: Expr = (
        machine_active_power_initial
        + Const(1j) * machine_reactive_power_initial
    )
    terminal_phasor_initial: Expr = (
        terminal_voltage * sym.exp(Const(1j) * terminal_angle)
    )
    stator_current_initial: Expr = sym.conj(complex_power_initial) / (
        sym.conj(terminal_phasor_initial) + epsilon
    )
    internal_voltage_imaginary: Expr = (
        terminal_voltage * sym.sin(terminal_angle)
        + sym.imag(stator_current_initial) * stator_resistance
        + sym.real(stator_current_initial)
        * (leakage_reactance + saturated_quadrature_mutual_reactance)
    )
    internal_voltage_real: Expr = (
        terminal_voltage * sym.cos(terminal_angle)
        + sym.real(stator_current_initial) * stator_resistance
        - sym.imag(stator_current_initial)
        * (leakage_reactance + saturated_quadrature_mutual_reactance)
    )
    initial_eqs: Dict[Var, Expr] = dict()
    # Derive initial per-unit rotor speed from the physical frequency base.
    # This anchors every RMS island without a fitted state value or a dummy
    # constant variable; both frequency quantities remain DGS-bound symbols.
    initial_eqs[speed] = (
        angular_frequency
        / (Const(2.0 * math.pi) * nominal_frequency)
    )
    # The network phase of an island can legitimately lie in any quadrant.
    # ``atan(y/x)`` loses that quadrant and can invert Eq/EFD by pi even when
    # the static terminal solution is exact, so retain the full phasor angle.
    initial_eqs[rotor_angle] = sym.atan2(
        internal_voltage_imaginary,
        internal_voltage_real,
    )
    initial_eqs[direct_voltage] = (
        -terminal_voltage * sym.sin(terminal_angle - rotor_angle)
    )
    initial_eqs[quadrature_voltage] = (
        terminal_voltage * sym.cos(terminal_angle - rotor_angle)
    )
    initial_eqs[active_power_machine] = machine_active_power_initial
    initial_eqs[reactive_power_machine] = machine_reactive_power_initial
    initial_eqs[direct_current] = (
        active_power_machine * direct_voltage
        + reactive_power_machine * quadrature_voltage
    ) / (
        direct_voltage * direct_voltage
        + quadrature_voltage * quadrature_voltage
        + epsilon
    )
    initial_eqs[quadrature_current] = (
        active_power_machine * quadrature_voltage
        - reactive_power_machine * direct_voltage
    ) / (
        direct_voltage * direct_voltage
        + quadrature_voltage * quadrature_voltage
        + epsilon
    )
    initial_eqs[main_flux_saturation_coefficient] = (
        common_saturation_coefficient_expr
    )
    initial_eqs[direct_saturation_factor] = (
        Const(1.0) / (Const(1.0) + direct_saturation_coefficient_expr)
    )
    initial_eqs[quadrature_saturation_factor] = (
        Const(1.0) / (Const(1.0) + quadrature_saturation_coefficient_expr)
    )
    initial_eqs[saturated_direct_mutual_reactance] = (
        direct_saturation_factor * direct_mutual_reactance
    )
    initial_eqs[saturated_quadrature_mutual_reactance] = (
        quadrature_saturation_factor * quadrature_mutual_reactance
    )
    initial_eqs[direct_rotor_determinant] = (
        (
            saturated_direct_mutual_reactance
            + direct_rotor_coupling_reactance
        ) * (
            direct_damper_leakage_reactance + field_leakage_reactance
        )
        + field_leakage_reactance * direct_damper_leakage_reactance
    )
    initial_eqs[field_coupling_factor] = (
        saturated_direct_mutual_reactance
        * direct_damper_leakage_reactance
        / direct_rotor_determinant
    )
    initial_eqs[direct_damper_coupling_factor] = (
        saturated_direct_mutual_reactance
        * field_leakage_reactance
        / direct_rotor_determinant
    )
    initial_eqs[saturated_direct_subtransient_reactance] = (
        saturated_direct_mutual_reactance
        + leakage_reactance
        - (field_coupling_factor + direct_damper_coupling_factor)
        * saturated_direct_mutual_reactance
    )
    if round_rotor:
        initial_eqs[quadrature_rotor_determinant] = (
            (
                saturated_quadrature_mutual_reactance
                + quadrature_rotor_coupling_reactance
            ) * (
                second_quadrature_damper_leakage_reactance
                + first_quadrature_damper_leakage_reactance
            )
            + second_quadrature_damper_leakage_reactance
            * first_quadrature_damper_leakage_reactance
        )
        initial_eqs[first_quadrature_coupling_factor] = (
            saturated_quadrature_mutual_reactance
            * second_quadrature_damper_leakage_reactance
            / quadrature_rotor_determinant
        )
        initial_eqs[second_quadrature_coupling_factor] = (
            saturated_quadrature_mutual_reactance
            * first_quadrature_damper_leakage_reactance
            / quadrature_rotor_determinant
        )
    else:
        initial_eqs[first_quadrature_coupling_factor] = (
            saturated_quadrature_mutual_reactance
            / first_quadrature_loop_reactance
        )
    if round_rotor:
        initial_eqs[saturated_quadrature_subtransient_reactance] = (
            saturated_quadrature_mutual_reactance
            + leakage_reactance
            - (
                first_quadrature_coupling_factor
                + second_quadrature_coupling_factor
            ) * saturated_quadrature_mutual_reactance
        )
    else:
        initial_eqs[saturated_quadrature_subtransient_reactance] = (
            saturated_quadrature_mutual_reactance
            + leakage_reactance
            - first_quadrature_coupling_factor
            * saturated_quadrature_mutual_reactance
        )
    initial_eqs[direct_subtransient_flux] = (
        (
            quadrature_voltage
            + stator_resistance * quadrature_current
        ) / (initial_stator_speed + epsilon)
        + saturated_direct_subtransient_reactance * direct_current
    )
    initial_eqs[quadrature_subtransient_flux] = (
        -(
            direct_voltage
            + stator_resistance * direct_current
        ) / (initial_stator_speed + epsilon)
        + saturated_quadrature_subtransient_reactance * quadrature_current
    )
    initial_eqs[direct_stator_flux] = (
        direct_subtransient_flux
        - saturated_direct_subtransient_reactance * direct_current
    )
    initial_eqs[quadrature_stator_flux] = (
        quadrature_subtransient_flux
        - saturated_quadrature_subtransient_reactance * quadrature_current
    )
    initial_eqs[reciprocal_field_current] = (
        direct_stator_flux
        + (leakage_reactance + saturated_direct_mutual_reactance)
        * direct_current
    ) / saturated_direct_mutual_reactance
    initial_eqs[field_flux] = (
        -saturated_direct_mutual_reactance * direct_current
        + field_loop_reactance * reciprocal_field_current
    )
    initial_eqs[direct_damper_flux] = (
        -saturated_direct_mutual_reactance * direct_current
        + (
            saturated_direct_mutual_reactance
            + direct_rotor_coupling_reactance
        ) * reciprocal_field_current
    )
    initial_eqs[first_quadrature_damper_flux] = (
        -saturated_quadrature_mutual_reactance * quadrature_current
    )
    if round_rotor:
        initial_eqs[second_quadrature_damper_flux] = (
            -saturated_quadrature_mutual_reactance * quadrature_current
        )
    else:
        pass
    # Damper currents are consequences of the solved flux linkages.  Reusing
    # the physical rotor-circuit equations keeps initialization symbolic and
    # lets their zero steady-state value emerge without a numeric seed.
    initial_eqs[direct_damper_current] = (
        direct_damper_coupling_factor * direct_current
        + (
            field_loop_reactance * direct_damper_flux
            - (
                saturated_direct_mutual_reactance
                + direct_rotor_coupling_reactance
            ) * field_flux
        ) / direct_rotor_determinant
    )
    if round_rotor:
        initial_eqs[first_quadrature_damper_current] = (
            first_quadrature_coupling_factor * quadrature_current
            + (
                second_quadrature_loop_reactance
                * first_quadrature_damper_flux
                - (
                    saturated_quadrature_mutual_reactance
                    + quadrature_rotor_coupling_reactance
                ) * second_quadrature_damper_flux
            ) / quadrature_rotor_determinant
        )
        initial_eqs[second_quadrature_damper_current] = (
            second_quadrature_coupling_factor * quadrature_current
            + (
                first_quadrature_loop_reactance
                * second_quadrature_damper_flux
                - (
                    saturated_quadrature_mutual_reactance
                    + quadrature_rotor_coupling_reactance
                ) * first_quadrature_damper_flux
            ) / quadrature_rotor_determinant
        )
    else:
        initial_eqs[first_quadrature_damper_current] = (
            first_quadrature_coupling_factor * quadrature_current
            + first_quadrature_damper_flux
            / first_quadrature_loop_reactance
        )
    initial_eqs[electrical_torque] = (
        (
            quadrature_current * direct_stator_flux
            - direct_current * quadrature_stator_flux
        ) / machine_active_base_factor
    )
    initial_eqs[excitation_current] = (
        direct_mutual_reactance
        * reciprocal_field_current
        / excitation_current_base_expr
    )
    initial_eqs[electrical_power_active_base] = (
        active_power_machine / machine_active_base_factor
    )
    # PowerFactory initializes controller outputs from the solved machine
    # operating point before evaluating the first state derivative.  The DGS
    # controller can contain a local fallback for these shared cables, but the
    # physical ElmSym shell owns their unique equilibrium values.
    initial_eqs[ve] = (
        excitation_current / excitation_voltage_base_ratio_expr
    )
    initial_eqs[pt] = (
        (speed + epsilon)
        * (
            electrical_torque
            + damping_friction * speed
            + damping_torque_expr
            + damping_power_expr
        )
    )

    # The coupling reactances remain source properties on the host Generator.
    # Their numeric values are frozen only for this compiled template instance.
    direct_coupling_value: float = equivalent_circuit.xrld
    quadrature_coupling_value: float = equivalent_circuit.xrlq

    parameters: Dict[Var, Expr] = dict()
    parameters[nominal_frequency] = Const(50.0)
    parameters[angular_frequency] = Const(2.0 * math.pi * 50.0)
    parameters[acceleration_time] = Const(1.0)
    parameters[stator_resistance] = Const(0.0)
    parameters[xd] = Const(1.0)
    parameters[xq] = Const(1.0)
    parameters[xd_transient] = Const(0.3)
    parameters[xq_transient] = Const(0.3)
    parameters[xd_subtransient] = Const(0.2)
    parameters[xq_subtransient] = Const(0.2)
    parameters[leakage_reactance] = Const(0.1)
    parameters[td_transient] = Const(1.0)
    parameters[tq_transient] = Const(1.0)
    parameters[td_subtransient] = Const(0.1)
    parameters[tq_subtransient] = Const(0.1)
    parameters[damping_friction] = Const(0.0)
    parameters[damping_torque] = Const(0.0)
    parameters[damping_power] = Const(0.0)
    parameters[system_power_base] = Const(100.0)
    parameters[machine_power_base] = Const(100.0)
    parameters[rated_power_factor] = Const(1.0)
    parameters[machine_active_base_factor] = Const(1.0)
    # Air-gap-line excitation base is mathematically unity. Non-default base
    # modes require explicit exported metadata and are rejected by later model
    # extensions rather than inferred from a project name.
    parameters[excitation_gain] = Const(1.0)
    parameters[rated_field_voltage] = Const(1.0)
    parameters[direct_mutual_reactance] = Const(equivalent_circuit.xad)
    parameters[quadrature_mutual_reactance] = Const(equivalent_circuit.xaq)
    parameters[direct_rotor_coupling_reactance] = Const(direct_coupling_value)
    parameters[quadrature_rotor_coupling_reactance] = Const(
        quadrature_coupling_value
    )
    parameters[field_leakage_reactance] = Const(equivalent_circuit.xfd)
    parameters[direct_damper_leakage_reactance] = Const(
        equivalent_circuit.x1d
    )
    parameters[first_quadrature_damper_leakage_reactance] = Const(
        equivalent_circuit.x1q
    )
    parameters[field_rotor_time] = Const(equivalent_circuit.t_sigma_fd)
    parameters[direct_damper_rotor_time] = Const(
        equivalent_circuit.t_sigma_1d
    )
    parameters[first_quadrature_damper_rotor_time] = Const(
        equivalent_circuit.t_sigma_1q
    )
    if round_rotor:
        parameters[second_quadrature_damper_leakage_reactance] = Const(
            equivalent_circuit.x2q
        )
        parameters[second_quadrature_damper_rotor_time] = Const(
            equivalent_circuit.t_sigma_2q
        )
    else:
        pass
    api_mapping: Dict[ParamPowerFlowReferenceType, Var] = dict()
    api_mapping[ParamPowerFlowReferenceType.freq] = nominal_frequency
    api_mapping[ParamPowerFlowReferenceType.omega_base] = angular_frequency
    api_mapping[ParamPowerFlowReferenceType.M] = acceleration_time
    api_mapping[ParamPowerFlowReferenceType.Rs] = stator_resistance
    api_mapping[ParamPowerFlowReferenceType.Xd] = xd
    api_mapping[ParamPowerFlowReferenceType.Xq] = xq
    api_mapping[ParamPowerFlowReferenceType.Xd_prime] = xd_transient
    api_mapping[ParamPowerFlowReferenceType.Xq_prime] = xq_transient
    api_mapping[ParamPowerFlowReferenceType.Xd_2prime] = xd_subtransient
    api_mapping[ParamPowerFlowReferenceType.Xq_2prime] = xq_subtransient
    api_mapping[ParamPowerFlowReferenceType.Xl] = leakage_reactance
    api_mapping[ParamPowerFlowReferenceType.Td0_prime] = td_transient
    api_mapping[ParamPowerFlowReferenceType.Tq0_prime] = tq_transient
    api_mapping[ParamPowerFlowReferenceType.Td0_2prime] = td_subtransient
    api_mapping[ParamPowerFlowReferenceType.Tq0_2prime] = tq_subtransient
    api_mapping[ParamPowerFlowReferenceType.generator_rms_dpu] = damping_friction
    api_mapping[ParamPowerFlowReferenceType.generator_rms_dkd] = damping_torque
    api_mapping[ParamPowerFlowReferenceType.generator_rms_dpe] = damping_power
    api_mapping[ParamPowerFlowReferenceType.Sbase] = system_power_base
    api_mapping[ParamPowerFlowReferenceType.generator_snom_mva] = machine_power_base
    api_mapping[
        ParamPowerFlowReferenceType.generator_rated_power_factor
    ] = rated_power_factor

    wrapper_block: Block = Block(
        name="DGS synchronous machine and controls",
        children=list([control_block]),
        in_vars=list([terminal_voltage, terminal_angle]),
        out_vars=list([
            active_power_system,
            reactive_power_system,
            speed,
            excitation_current,
            electrical_power_active_base,
        ]),
        state_vars=state_vars,
        state_eqs=state_eqs,
        algebraic_vars=algebraic_vars,
        algebraic_eqs=algebraic_eqs,
        init_eqs=initial_eqs,
        post_init_seed_eqs=dict(initial_eqs),
        parameters=parameters,
        external_mapping=dict([
            (VarPowerFlowReferenceType.P, active_power_system),
            (VarPowerFlowReferenceType.Q, reactive_power_system),
            (VarPowerFlowReferenceType.Vm, terminal_voltage),
            (VarPowerFlowReferenceType.Va, terminal_angle),
        ]),
        api_obj_mapping=api_mapping,
    )
    wrapper_block.dynamic_model_contract.dgs_elmsym_runtime_adapter = True
    wrapper_block.dynamic_model_contract.dgs_elmsym_runtime_adapter_pending = False
    wrapper_block.dynamic_model_contract.dgs_elmsym_round_rotor = round_rotor
    # Retain exact variable identities so the circuit-level preparation pass
    # can replace the nominal-frequency frame with PowerFactory's exported
    # reference-machine frame after every physical ElmSym has been assigned.
    wrapper_block.dynamic_model_contract.dgs_elmsym_rotor_angle_var_uid = rotor_angle.uid
    wrapper_block.dynamic_model_contract.dgs_elmsym_speed_var_uid = speed.uid
    wrapper_block.dynamic_model_contract.dgs_elmsym_angular_frequency_var_uid = (
        angular_frequency.uid
    )
    wrapper_block.dynamic_model_contract.dgs_elmsym_rated_field_voltage_var_uid = (
        rated_field_voltage.uid
    )
    wrapper_block.dynamic_model_contract.dgs_elmsym_excitation_gain_var_uid = (
        excitation_gain.uid
    )
    wrapper_block.dynamic_model_contract.dgs_elmsym_active_base_factor_var_uid = (
        machine_active_base_factor.uid
    )
    explicit_initialization_uids: Set[int] = set()
    initial_var: Var
    for initial_var in initial_eqs.keys():
        explicit_initialization_uids.add(initial_var.uid)
    else:
        pass
    wrapper_block.dynamic_model_contract.dgs_explicit_initialization_uids = (
        explicit_initialization_uids
    )
    return wrapper_block


def configure_dgs_elmsym_runtime_template_for_device(
        template: RmsModelTemplate,
        device: Generator,
        system_base_mva: float,
        direct_result: DgsDirectRootBuildResult | None = None,
) -> bool:
    """Materialize one exact synchronous-machine/controller runtime template.

    :param template: Pending or already configured DGS template.
    :param device: Exact Generator host selected through the DGS FID.
    :param system_base_mva: VeraGrid system base used for validation.
    :param direct_result: Optional transient direct-root conversion context.
    :return: ``True`` only for a complete, physically valid adapter.
    """
    already_configured: bool = (
        template.block.dynamic_model_contract.dgs_elmsym_runtime_adapter
    )
    pending: bool = (
        template.block.dynamic_model_contract.dgs_elmsym_runtime_adapter_pending
    )
    if already_configured:
        return True
    else:
        pass
    if (
            not pending
            or direct_result is None
            or not math.isfinite(system_base_mva)
            or system_base_mva <= 0.0
            or not _machine_parameter_contract_is_valid(device=device)
    ):
        return False
    else:
        pass

    equivalent_circuit: _PowerFactoryEquivalentCircuit | None = (
        _calculate_powerfactory_equivalent_circuit(device=device)
    )
    if equivalent_circuit is None:
        return False
    else:
        pass
    round_rotor: bool = float(device.Tq0_prime) > 0.0
    if direct_result is None:
        control_block: Block = copy.deepcopy(template.block)
    else:
        if direct_result.root_block is template.block:
            control_block = template.block
        else:
            return False
    configured_block: Block | None = _build_dgs_elmsym_runtime_block(
        control_block=control_block,
        round_rotor=round_rotor,
        equivalent_circuit=equivalent_circuit,
        direct_result=direct_result,
    )
    if configured_block is None:
        return False
    else:
        rated_field_voltage_uid_raw: int | None = (
            configured_block.dynamic_model_contract.dgs_elmsym_rated_field_voltage_var_uid
        )
        if float(device.rms_rated_field_voltage) > 1.0e-12:
            rated_field_voltage_value: float = float(
                device.rms_rated_field_voltage
            )
        else:
            rated_field_voltage_value = (
                _calculate_unsaturated_rated_field_voltage(device=device)
            )
        excitation_gain_uid_raw: int | None = (
            configured_block.dynamic_model_contract.dgs_elmsym_excitation_gain_var_uid
        )
        if float(device.rms_excitation_gain) > 1.0e-12:
            excitation_gain_value: float = float(device.rms_excitation_gain)
        else:
            # Older DGS files do not carry the calculated ElmSym boundary.
            # Unity retains their historical air-gap-base behavior explicitly.
            excitation_gain_value = 1.0
        active_base_factor_uid_raw: int | None = (
            configured_block.dynamic_model_contract.dgs_elmsym_active_base_factor_var_uid
        )
        active_base_factor_value: float = (
            _calculate_machine_active_base_factor(device=device)
        )
        parameter_var: Var
        rated_field_voltage_assigned: bool = False
        excitation_gain_assigned: bool = False
        active_base_factor_assigned: bool = False
        for parameter_var in configured_block.parameters.keys():
            if parameter_var.uid == rated_field_voltage_uid_raw:
                # TypSym.satur=0 uses the exact unsaturated rated-point value.
                # This scales AVR state limits in the same excitation
                # coordinate as the machine EFD equation.
                configured_block.parameters[parameter_var] = Const(
                    rated_field_voltage_value
                )
                rated_field_voltage_assigned = True
            elif parameter_var.uid == excitation_gain_uid_raw:
                # Gm rescales the exciter integrator state while leaving its
                # physical EFD output unchanged.  It must therefore come from
                # the machine boundary, not from a controller-specific fit.
                configured_block.parameters[parameter_var] = Const(
                    excitation_gain_value
                )
                excitation_gain_assigned = True
            elif parameter_var.uid == active_base_factor_uid_raw:
                # Keep raw ``cosn`` on the exported controller cable while
                # selecting the physical MVA torque base for a condenser.
                configured_block.parameters[parameter_var] = Const(
                    active_base_factor_value
                )
                active_base_factor_assigned = True
            else:
                pass
        else:
            pass
        if (
                rated_field_voltage_assigned
                and excitation_gain_assigned
                and active_base_factor_assigned
        ):
            pass
        else:
            return False
        template.block = configured_block
        return True
