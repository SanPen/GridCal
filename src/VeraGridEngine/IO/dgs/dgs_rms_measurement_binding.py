# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import cmath
import math
import re
from typing import Dict, List, Set, Tuple

from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.series_reactance import SeriesReactance
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import (
    BlkDef,
    BlkSig,
    BlkSlot,
    DGSElement,
    ElmComp,
    ElmPhi,
    StaCubic,
    StaImea,
    StaPqmea,
    StaVmea,
)
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    ElmCompInstanceEntry,
    extract_elmcomp_direct_instances,
    get_blkslot_signal_interface,
    get_unambiguous_elmcomp_direct_instances,
    get_unique_elmcomp_slot_entries,
)
from VeraGridEngine.Templates.Rms.rms_meter_templates import (
    build_rms_current_meter_outputs_from_pq,
    build_rms_physical_signal_meter_block,
    build_rms_phase_locked_loop_block,
    build_rms_power_meter_outputs_from_pq,
    build_rms_voltage_meter_outputs_from_dc,
    build_rms_voltage_meter_outputs_from_polar,
)
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    RmsPhysicalMeasurementPoint,
    RmsPhysicalMeterKind,
    RmsTerminalSide,
    build_name_to_vars_lookup,
)
from VeraGridEngine.Utils.Symbolic.bus_rms_template import get_bus_rms_algebraic_vars
from VeraGridEngine.Utils.Symbolic.symbolic import (
    BinOp,
    Const,
    Expr,
    Func,
    Func2,
    UnOp,
    Var,
)
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import ConverterControlType, VarPowerFlowReferenceType


class DgsRmsMeasurementBindingReport:
    """Store the deterministic result of native DGS meter binding."""

    __slots__ = (
        "_bound_meter_count",
        "_bound_signal_count",
        "_skipped_meter_count",
        "_failed_meter_count",
    )

    def __init__(self) -> None:
        """Initialize all meter-binding counters to zero."""
        self._bound_meter_count: int = 0
        self._bound_signal_count: int = 0
        self._skipped_meter_count: int = 0
        self._failed_meter_count: int = 0

    def record_bound_meter(self, signal_count: int) -> None:
        """
        Record one meter whose exported signals were connected.

        :param signal_count: Number of connected scalar signals.
        :return: None.
        """
        self._bound_meter_count += 1
        self._bound_signal_count += int(signal_count)

    def record_skipped_meter(self) -> None:
        """Record one meter that does not belong to an active supported root."""
        self._skipped_meter_count += 1

    def record_failed_meter(self) -> None:
        """Record one handled meter-resolution failure."""
        self._failed_meter_count += 1

    def get_bound_meter_count(self) -> int:
        """Return the number of materialized native meters."""
        return self._bound_meter_count

    def get_bound_signal_count(self) -> int:
        """Return the number of connected scalar meter signals."""
        return self._bound_signal_count

    def get_skipped_meter_count(self) -> int:
        """Return the number of intentionally inactive meters."""
        return self._skipped_meter_count

    def get_failed_meter_count(self) -> int:
        """Return the number of handled meter failures."""
        return self._failed_meter_count


def _split_slot_signal_labels(signal_labels: List[str]) -> List[str]:
    """
    Expand PowerFactory vector labels into ordered scalar signal names.

    PowerFactory writes vector connections such as ``u1r;u1i`` in one BlkSig
    label. The symbolic runtime uses one scalar variable per component.

    :param signal_labels: Raw normalized BlkSig labels.
    :return: Ordered non-empty scalar signal names.
    """
    scalar_names: List[str] = list()
    signal_label: str
    component_name: str

    for signal_label in signal_labels:
        # Both separators are native PowerFactory list delimiters. Parenthesized
        # graphical duplicate suffixes were already removed by the DGS parser.
        for component_name in re.split(r"[;,]", signal_label):
            component_name = component_name.strip()
            if component_name == "":
                pass
            else:
                scalar_names.append(component_name)
    return scalar_names


def _get_veragrid_meter_output_names(
        alias_names: List[str],
) -> tuple[str, ...]:
    """Normalize imported aliases into concise VeraGrid-facing port names.

    The external alias remains the lookup key used to connect the controller.
    Only the visible meter output is normalized, which keeps source data out of
    the canonical block identity without losing traceability.

    :param alias_names: Ordered imported aliases selected by the controller.
    :return: Unique VeraGrid-facing output names in the same order.
    """
    output_names: List[str] = list()
    alias_name: str
    for alias_name in alias_names:
        source_marker_index: int = alias_name.lower().find("powerf")
        if source_marker_index >= 0:
            output_name: str = alias_name[:source_marker_index].rstrip("_ -")
        else:
            output_name = alias_name.strip()
        if output_name == "":
            output_name = "measurement"
        else:
            pass
        unique_output_name: str = output_name
        duplicate_index: int = 2
        while unique_output_name in output_names:
            unique_output_name = f"{output_name}_{duplicate_index}"
            duplicate_index += 1
        output_names.append(unique_output_name)
    return tuple(output_names)


def _get_veragrid_meter_name(
        meter_kind: RmsPhysicalMeterKind,
        source_fid: str,
) -> str:
    """Return one source-independent visible physical-meter name.

    :param meter_kind: Physical quantity family produced by the meter.
    :param source_fid: Stable source identity used only as a disambiguator.
    :return: VeraGrid-facing block name.
    """
    if meter_kind is RmsPhysicalMeterKind.PHASE_LOCKED_LOOP:
        quantity_name: str = "Phase"
    else:
        quantity_name = meter_kind.value.title()
    return f"{quantity_name} meter {source_fid}"


def _get_native_source_target_signal_names(
        dgs_circuit: DgsCircuit,
        source_slot_id: str,
) -> List[str]:
    """
    Resolve the consumer-side names fed by one native source slot.

    A BlkSig display label records the producer symbol (for example ``p``),
    while the consuming DSL port can use a different name (for example
    ``P_act``). Runtime binding must follow the exported endpoint indices, not
    assume that the two labels are equal.

    :param dgs_circuit: Parsed DGS signal graph.
    :param source_slot_id: Native source BlkSlot FID.
    :return: Ordered consumer-side scalar signal names.
    """
    slot_by_id: Dict[str, BlkSlot] = dict()
    slot: BlkSlot
    signal: BlkSig
    target_names: List[str] = list()

    for slot in dgs_circuit.blkslots:
        slot_by_id[slot.ID] = slot

    for signal in dgs_circuit.blksigs:
        producer_slot_id: str = str(signal.pnodfrom).strip()
        if producer_slot_id != source_slot_id:
            pass
        else:
            consumer_slot_id: str = str(signal.pnodto).strip()
            consumer_slot: BlkSlot | None = slot_by_id.get(
                consumer_slot_id,
                None,
            )
            consumer_port_index: int = int(signal.inodto)
            if (
                    consumer_slot is None
                    or consumer_port_index < 0
                    or consumer_port_index >= len(consumer_slot.inputs)
            ):
                pass
            else:
                consumer_components: List[str] = _split_slot_signal_labels(
                    signal_labels=list([
                        consumer_slot.inputs[consumer_port_index],
                    ]),
                )
                component_name: str
                for component_name in consumer_components:
                    if component_name in target_names:
                        pass
                    else:
                        target_names.append(component_name)
    return target_names


def _measurement_entry_sort_key(entry: ElmCompInstanceEntry) -> int:
    """
    Return the stable positional key of one composite measurement slot.

    :param entry: Direct ElmComp slot entry.
    :return: Exported pblk/pelm ordinal or ``-1`` when absent.
    """
    if entry.slot_index is None:
        result: int = -1
    else:
        result = entry.slot_index
    return result


def _build_implicit_meter_target_by_slot(
        dgs_circuit: DgsCircuit,
        root_element: ElmComp,
        entries: List[ElmCompInstanceEntry],
) -> Dict[str, str]:
    """
    Infer unwired native-meter targets from the declared frame interface order.

    Some PowerFactory equipment frames omit ``BlkSig`` rows because their slots
    are wired positionally. The controller slot still declares its complete
    input vector, while the root frame declares the external subset. The ordered
    remainder maps one-to-one to the ordered native measurement slots.

    :param dgs_circuit: Parsed DGS circuit.
    :param root_element: Owning ElmComp instance.
    :param entries: Ordered direct root slot instances.
    :return: Meter slot FID to consumer input name.
    """
    slot_by_id: Dict[str, BlkSlot] = dict()
    slot: BlkSlot
    for slot in dgs_circuit.blkslots:
        slot_by_id[slot.ID] = slot

    root_type_id: str = str(root_element.typ_id)
    root_input_names: set[str] = set()
    block_definition: BlkDef
    for block_definition in dgs_circuit.blkdefs:
        if str(block_definition.ID) == root_type_id:
            root_input_names.update(block_definition.inputs)
        else:
            pass

    controller_input_names: List[str] = list()
    entry: ElmCompInstanceEntry
    for entry in entries:
        if entry.slot_id is None or entry.element_kind not in ("ElmDsl", "ElmComp"):
            pass
        else:
            controller_slot: BlkSlot | None = slot_by_id.get(entry.slot_id, None)
            if controller_slot is None or len(controller_slot.inputs) == 0:
                pass
            else:
                if len(controller_input_names) == 0:
                    controller_input_names = _split_slot_signal_labels(
                        signal_labels=controller_slot.inputs,
                    )
                else:
                    # More than one controller consumer makes positional
                    # ownership ambiguous, so no implicit mapping is emitted.
                    controller_input_names = list()
                    break

    internal_controller_inputs: List[str] = list(
        input_name
        for input_name in controller_input_names
        if input_name not in root_input_names
    )
    measurement_entries: List[ElmCompInstanceEntry] = list(
        entry
        for entry in entries
        if entry.element_kind in ("StaVmea", "StaImea", "StaPqmea")
        and entry.slot_id is not None
    )
    measurement_entries.sort(key=_measurement_entry_sort_key)

    target_by_slot: Dict[str, str] = dict()
    mapping_index: int
    if len(internal_controller_inputs) == len(measurement_entries):
        for mapping_index in range(len(measurement_entries)):
            meter_slot_id: str | None = measurement_entries[mapping_index].slot_id
            if meter_slot_id is None:
                pass
            else:
                target_by_slot[meter_slot_id] = internal_controller_inputs[mapping_index]
    else:
        pass
    return target_by_slot


def _build_dgs_element_index(dgs_circuit: DgsCircuit) -> Dict[str, DGSElement]:
    """
    Build an exact FID lookup over every parsed DGS class.

    :param dgs_circuit: Parsed source DGS.
    :return: DGS element lookup keyed by FID.
    """
    element_by_id: Dict[str, DGSElement] = dict()
    element: DGSElement

    for element in dgs_circuit.get_all_elements_iter():
        if element.ID == "":
            pass
        else:
            element_by_id[element.ID] = element
    return element_by_id


def _build_dynamic_device_index(circuit: MultiCircuit) -> Dict[str, DynamicDevice]:
    """
    Index physical dynamic-capable devices by authoritative DGS idtag.

    :param circuit: Imported VeraGrid circuit.
    :return: Dynamic-device lookup keyed by exact source FID.
    """
    device_by_id: Dict[str, DynamicDevice] = dict()
    api_object: object

    for api_object in circuit.get_all_elements_iter():
        if isinstance(api_object, DynamicDevice):
            device_by_id[str(api_object.idtag)] = api_object
        else:
            pass
    return device_by_id


def _build_bus_index(circuit: MultiCircuit) -> Dict[str, Bus]:
    """
    Index VeraGrid buses by authoritative DGS terminal FID.

    :param circuit: Imported VeraGrid circuit.
    :return: Bus lookup keyed by exact source FID.
    """
    bus_by_id: Dict[str, Bus] = dict()
    bus: Bus

    for bus in circuit.buses:
        bus_by_id[str(bus.idtag)] = bus
    return bus_by_id


def _resolve_terminal_id(
        pointer_id: str,
        dgs_element_by_id: Dict[str, DGSElement],
) -> str | None:
    """
    Resolve an ElmTerm or StaCubic pointer to its terminal FID.

    :param pointer_id: DGS pointer exported by a native meter.
    :param dgs_element_by_id: Exact DGS element lookup.
    :return: Terminal FID or ``None`` when the pointer is unresolved.
    """
    pointed_element: DGSElement | None = dgs_element_by_id.get(pointer_id, None)

    if isinstance(pointed_element, StaCubic):
        terminal_id: str | None = pointed_element.fold_id
    else:
        if pointed_element is None:
            terminal_id = None
        else:
            # StaVmea may point directly to ElmTerm. The class is deliberately
            # not inferred from a display name; only its authoritative FID is used.
            terminal_id = pointed_element.ID
    return terminal_id


def _get_bus_voltage_expressions(bus: Bus) -> Tuple[Expr, Expr, Expr | None]:
    """
    Return voltage magnitude, angle and optional DC voltage expressions.

    :param bus: Exact measured VeraGrid bus.
    :return: Tuple ``(Vm, Va, Vdc_or_none)``.
    """
    dc_voltage: Var | None
    voltage_magnitude: Var
    voltage_angle: Var
    dc_voltage, voltage_magnitude, voltage_angle = get_bus_rms_algebraic_vars(
        bus_rms_model=bus.rms_model,
    )
    return voltage_magnitude, voltage_angle, dc_voltage


def _resolve_cubicle_source(
        cubicle_id: str,
        dgs_element_by_id: Dict[str, DGSElement],
        device_by_id: Dict[str, DynamicDevice],
        bus_by_id: Dict[str, Bus],
) -> Tuple[DynamicDevice | None, Bus | None, int | None]:
    """
    Resolve one measured cubicle to its physical device, bus and terminal side.

    :param cubicle_id: Exact measured StaCubic FID.
    :param dgs_element_by_id: Exact DGS element lookup.
    :param device_by_id: VeraGrid physical-device lookup.
    :param bus_by_id: VeraGrid bus lookup.
    :return: Tuple ``(device, bus, source_terminal_index)``.
    """
    pointed_element: DGSElement | None = dgs_element_by_id.get(cubicle_id, None)

    if isinstance(pointed_element, StaCubic):
        source_device: DynamicDevice | None = device_by_id.get(
            str(pointed_element.obj_id),
            None,
        )
        source_bus: Bus | None = bus_by_id.get(str(pointed_element.fold_id), None)
        source_terminal_index: int | None = int(pointed_element.obj_bus)
    else:
        source_device = None
        source_bus = None
        source_terminal_index = None
    return source_device, source_bus, source_terminal_index


def _get_physical_meter_terminal_side(
        source_device: DynamicDevice,
        source_terminal_index: int,
) -> RmsTerminalSide | None:
    """Map one DGS cubicle ordinal to the canonical physical terminal side.

    :param source_device: Exact measured VeraGrid device.
    :param source_terminal_index: DGS terminal ordinal selected by the cubicle.
    :return: Typed canonical terminal side, or ``None`` for an invalid ordinal.
    """
    if isinstance(source_device, VSC):
        # ElmVsc cubicle zero is the AC terminal represented by VeraGrid's
        # canonical ``to`` side.
        if source_terminal_index == 0:
            terminal_side: RmsTerminalSide | None = RmsTerminalSide.TO
        else:
            terminal_side = None
    else:
        if isinstance(source_device, BranchParent):
            if source_terminal_index == 0:
                terminal_side = RmsTerminalSide.FROM
            else:
                if source_terminal_index == 1:
                    terminal_side = RmsTerminalSide.TO
                else:
                    terminal_side = None
        else:
            if source_terminal_index == 0:
                terminal_side = RmsTerminalSide.BUS
            else:
                terminal_side = None
    return terminal_side


def _resolve_logical_actuator_current_source(
        circuit: MultiCircuit,
        root_dgs_id: str,
        measured_bus: Bus,
) -> Tuple[DynamicDevice | None, int | None]:
    """Resolve an omitted native valve to its retained series branch.

    PowerFactory can omit ``ElmValve`` rows while retaining a ``StaImea``
    cubicle that points to that valve. The valve and passive impedance are in
    series, so their current is identical. Exact root ownership plus the
    measured terminal must select one and only one retained branch; ambiguous
    topology produces no fallback.

    :param circuit: Imported circuit with prepared logical actuator topology.
    :param root_dgs_id: Exact owning ElmComp FID.
    :param measured_bus: Terminal resolved from the measurement cubicle.
    :return: Unique physical series branch and terminal index, or two ``None`` values.
    """
    candidates: List[Tuple[DynamicDevice, int]] = list()
    branch: object
    for branch in circuit.get_branches_iter(
        add_vsc=False,
        add_hvdc=False,
        add_switch=False,
    ):
        if isinstance(branch, (Line, SeriesReactance)):
            branch_root_raw: str | None = (
                branch.rms_model.dynamic_model_contract.dgs_logical_actuator_root_id
            )
            if branch_root_raw == root_dgs_id:
                if branch.bus_from is measured_bus:
                    candidates.append((branch, 0))
                else:
                    if branch.bus_to is measured_bus:
                        candidates.append((branch, 1))
                    else:
                        pass
            else:
                pass
        else:
            pass

    if len(candidates) == 1:
        result: Tuple[DynamicDevice | None, int | None] = candidates[0]
    else:
        result = (None, None)
    return result


def _get_device_pq_expressions(
        source_device: DynamicDevice,
        source_terminal_index: int,
) -> Tuple[Expr | None, Expr | None]:
    """
    Resolve P/Q expressions at one exact physical-device terminal.

    :param source_device: Measured physical VeraGrid device.
    :param source_terminal_index: DGS StaCubic terminal ordinal.
    :return: Pair ``(P, Q)`` with ``None`` for unavailable channels.
    """
    mapping: Dict[VarPowerFlowReferenceType, Var] = source_device.rms_model.external_mapping

    if isinstance(source_device, VSC):
        # ElmVsc cubicle zero is its AC terminal in the DGS topology, whereas
        # the VeraGrid adapter uses Pt/Qt for the same AC-side power.
        active_power: Expr | None = mapping.get(VarPowerFlowReferenceType.Pt, None)
        reactive_power: Expr | None = mapping.get(VarPowerFlowReferenceType.Qt, None)
    else:
        if source_terminal_index == 0:
            active_power = mapping.get(VarPowerFlowReferenceType.Pf, None)
            reactive_power = mapping.get(VarPowerFlowReferenceType.Qf, None)
        else:
            active_power = mapping.get(VarPowerFlowReferenceType.Pt, None)
            reactive_power = mapping.get(VarPowerFlowReferenceType.Qt, None)

        if active_power is None:
            active_power = mapping.get(VarPowerFlowReferenceType.P, None)
        else:
            pass
        if reactive_power is None:
            reactive_power = mapping.get(VarPowerFlowReferenceType.Q, None)
        else:
            pass
    return active_power, reactive_power


def _get_ideal_transformer_relay_pq_expressions(
        circuit: MultiCircuit,
        source_device: DynamicDevice,
        source_terminal_index: int,
        host_device: DynamicDevice,
) -> Tuple[Expr | None, Expr | None]:
    """Relay ideal-transformer terminal power from one unique adjacent VSC.

    Topology reduction merges the buses of a zero-impedance transformer, so a
    static power-flow result cannot retain that transformer's internal branch
    flow. When an equipment controller owns the only VSC on the opposite side,
    lossless terminal balance makes the VSC AC power the exact physical signal
    measured at the remote transformer terminal. The meter identity and
    terminal declaration remain attached to the transformer.

    :param circuit: Canonical circuit used to validate unique adjacency.
    :param source_device: Physical device selected by the native meter.
    :param source_terminal_index: Measured transformer terminal ordinal.
    :param host_device: Dynamic equipment root that consumes the meter signal.
    :return: Relayed active/reactive expressions, or two ``None`` values.
    """
    if (
            isinstance(source_device, Transformer2W)
            and isinstance(host_device, VSC)
            and source_device.rms_model.dynamic_model_contract.rms_ideal_transformer
            and source_terminal_index in (0, 1)
    ):
        pass
    else:
        return None, None

    host_ac_bus: Bus | None
    if host_device.bus_to is not None and not host_device.bus_to.is_dc:
        host_ac_bus = host_device.bus_to
    else:
        if host_device.bus_from is not None and not host_device.bus_from.is_dc:
            host_ac_bus = host_device.bus_from
        else:
            host_ac_bus = None

    if host_ac_bus is None:
        return None, None
    else:
        pass

    transformer_from_is_host: bool = source_device.bus_from is host_ac_bus
    transformer_to_is_host: bool = source_device.bus_to is host_ac_bus
    if transformer_from_is_host or transformer_to_is_host:
        pass
    else:
        return None, None

    # The relay is valid only for a two-device junction. Any additional active
    # branch or injection would contribute power that the VSC terminal alone
    # cannot represent.
    connected_devices_are_exact: bool = True
    connected_device_count: int = 0
    candidate_branch: object
    for candidate_branch in circuit.get_branches_iter(
            add_vsc=True,
            add_hvdc=True,
            add_switch=True,
    ):
        if isinstance(candidate_branch, BranchParent) and candidate_branch.active:
            candidate_is_connected: bool = (
                candidate_branch.bus_from is host_ac_bus
                or candidate_branch.bus_to is host_ac_bus
            )
            if candidate_is_connected:
                connected_device_count += 1
                if candidate_branch is source_device or candidate_branch is host_device:
                    pass
                else:
                    connected_devices_are_exact = False
            else:
                pass
        else:
            pass

    candidate_injection: object
    for candidate_injection in circuit.get_injection_devices_iter():
        if isinstance(candidate_injection, DynamicDevice) and candidate_injection.active:
            if candidate_injection.bus is host_ac_bus:
                connected_devices_are_exact = False
            else:
                pass
        else:
            pass

    if connected_devices_are_exact and connected_device_count == 2:
        pass
    else:
        return None, None

    host_mapping: Dict[VarPowerFlowReferenceType, Var] = (
        host_device.rms_model.external_mapping
    )
    host_active_power: Expr | None = host_mapping.get(
        VarPowerFlowReferenceType.Pt,
        None,
    )
    host_reactive_power: Expr | None = host_mapping.get(
        VarPowerFlowReferenceType.Qt,
        None,
    )
    if host_active_power is None or host_reactive_power is None:
        return None, None
    else:
        pass

    measured_terminal_is_host: bool = (
        (source_terminal_index == 0 and transformer_from_is_host)
        or (source_terminal_index == 1 and transformer_to_is_host)
    )
    if measured_terminal_is_host:
        return Const(-1.0) * host_active_power, Const(-1.0) * host_reactive_power
    else:
        return host_active_power, host_reactive_power


def _get_dc_branch_current_expression(
        source_device: DynamicDevice,
        source_terminal_index: int,
) -> Expr | None:
    """Return the signed DC current entering one measured branch terminal.

    RMS DC branches expose their series current through ``If_dc``. Some
    three-terminal devices also expose the explicit opposite-terminal
    ``It_dc`` channel. The retained from-current must be negated at the
    opposite terminal when no side-specific channel exists. Cable shunt
    current is added separately by the meter builder.

    :param source_device: Exact measured physical branch.
    :param source_terminal_index: Retained branch terminal ordinal.
    :return: Signed per-unit DC current, or ``None`` when unavailable.
    """
    mapping: Dict[VarPowerFlowReferenceType, Var] = (
        source_device.rms_model.external_mapping
    )
    from_current: Expr | None = mapping.get(
        VarPowerFlowReferenceType.If_dc,
        None,
    )
    to_current: Expr | None = mapping.get(
        VarPowerFlowReferenceType.It_dc,
        None,
    )

    if source_terminal_index == 0:
        current_expression: Expr | None = from_current
    else:
        if to_current is not None:
            current_expression = to_current
        else:
            if from_current is not None:
                current_expression = Const(-1.0) * from_current
            else:
                current_expression = None
    return current_expression


def _build_dc_current_alias_expressions(
        meter: StaImea,
        signal_names: List[str],
        measured_bus: Bus,
        source_device: DynamicDevice,
        source_terminal_index: int,
        system_base_mva: float,
) -> Dict[str, Expr]:
    """Map a native DC current meter without introducing AC voltage inputs.

    PowerFactory ``StaImea`` mode 2 exposes the physical current in kA. The
    VeraGrid RMS DC network stores branch current in per unit on the circuit
    MVA base, whose corresponding kA base is ``Sbase / Vnom``. Mode 1 remains
    per unit. The imaginary component of a scalar DC current is identically
    zero.

    :param meter: Parsed native current meter carrying its unit mode.
    :param signal_names: Scalar outgoing BlkSig aliases.
    :param measured_bus: Exact measured DC terminal.
    :param source_device: Exact retained DC branch.
    :param source_terminal_index: Retained branch terminal ordinal.
    :param system_base_mva: VeraGrid circuit power base in MVA.
    :return: Alias-to-expression mapping, empty when current is unavailable.
    """
    dc_current: Expr | None = _get_dc_branch_current_expression(
        source_device=source_device,
        source_terminal_index=source_terminal_index,
    )
    if dc_current is None:
        return dict()
    else:
        pass

    # PowerFactory reports the current entering the measured cable cubicle.
    # For a lumped pi cable that is the series current plus the local C/2
    # charging current. Keep If_dc itself unchanged because nodal power balance
    # and line energy use the series branch current.
    terminal_current: Expr = dc_current
    if isinstance(source_device, Line):
        terminal_capacitance: float = 0.5 * max(
            0.0,
            float(source_device.dc_shunt_capacitance_pu_seconds),
        )
        voltage_derivative: Var | None = measured_bus.rms_model.external_mapping.get(
            VarPowerFlowReferenceType.d_Vdc,
            None,
        )
        if terminal_capacitance > 0.0 and voltage_derivative is not None:
            terminal_current = (
                terminal_current
                + Const(terminal_capacitance) * voltage_derivative
            )
        else:
            pass
    else:
        pass

    if (
            meter.i_mode == 2
            and system_base_mva > 0.0
            and measured_bus.Vnom > 0.0
    ):
        # MVA / kV is kA, so this converts the DC network per-unit current to
        # the physical unit declared by the PowerFactory DSL interface.
        current_scale: float = system_base_mva / float(measured_bus.Vnom)
    else:
        current_scale = 1.0

    scaled_current: Expr = Const(current_scale) * terminal_current
    alias_expressions: Dict[str, Expr] = dict()
    signal_name: str
    normalized_name: str
    for signal_name in signal_names:
        normalized_name = signal_name.lower()
        if "ii" in normalized_name or normalized_name.endswith("imag"):
            alias_expressions[signal_name] = Const(0.0)
        else:
            alias_expressions[signal_name] = scaled_current
    return alias_expressions


def _get_device_power_base_mva(source_device: DynamicDevice) -> float | None:
    """
    Return the explicit nominal MVA base of a measured physical device.

    :param source_device: Exact device referenced by the native meter cubicle.
    :return: Positive device power base or ``None`` when the class has no such base.
    """
    power_base_mva: float | None

    if isinstance(source_device, VSC):
        power_base_mva = float(source_device.rate)
    else:
        if isinstance(source_device, Transformer2W):
            power_base_mva = float(source_device.rate)
        else:
            if isinstance(source_device, Generator):
                power_base_mva = float(source_device.Snom)
            else:
                power_base_mva = None

    if power_base_mva is None or power_base_mva <= 0.0:
        return None
    else:
        return power_base_mva


def _build_voltage_alias_expressions(
        meter: StaVmea,
        signal_names: List[str],
        measured_bus: Bus,
) -> Dict[str, Expr]:
    """
    Map exported voltage-slot aliases to physical bus expressions.

    :param meter: Parsed native voltage meter.
    :param signal_names: Scalar outgoing BlkSig aliases.
    :param measured_bus: Exact measured VeraGrid bus.
    :return: Alias-to-expression mapping.
    """
    if meter.outserv != 0:
        return dict()
    else:
        pass

    voltage_magnitude: Expr
    voltage_angle: Expr
    dc_voltage: Expr | None
    voltage_magnitude, voltage_angle, dc_voltage = _get_bus_voltage_expressions(
        bus=measured_bus,
    )
    nominal_frequency_hz: Const = Const(
        meter.nominalFreq if meter.nominalFreq > 0.0 else 50.0
    )
    if dc_voltage is None:
        native_outputs: Dict[str, Expr] = build_rms_voltage_meter_outputs_from_polar(
            vm=voltage_magnitude,
            va=voltage_angle,
            measured_frequency_hz=nominal_frequency_hz,
            nominal_frequency_hz=nominal_frequency_hz,
        )
    else:
        native_outputs = build_rms_voltage_meter_outputs_from_dc(
            vdc=dc_voltage,
            nominal_frequency_hz=nominal_frequency_hz,
        )

    alias_expressions: Dict[str, Expr] = dict()
    signal_name: str
    normalized_name: str
    source_expression: Expr

    for signal_name in signal_names:
        normalized_name = signal_name.lower()
        if "u1r" in normalized_name or normalized_name == "ur":
            source_expression = native_outputs["ur"]
        else:
            if "u1i" in normalized_name or normalized_name == "ui":
                source_expression = native_outputs["ui"]
            else:
                if normalized_name.startswith("cosphi"):
                    source_expression = sym.cos(voltage_angle)
                else:
                    if normalized_name.startswith("sinphi"):
                        source_expression = sym.sin(voltage_angle)
                    else:
                        if "phi" in normalized_name:
                            source_expression = voltage_angle
                        else:
                            if normalized_name in ("fe", "fref"):
                                # PowerFactory StaVmea exports ``fe`` and
                                # ``fref`` as per-unit electrical/reference
                                # frequency. They are distinct from ``Fnom``
                                # and explicit ``*_Hz`` channels routed through
                                # the same native voltage-measurement slot.
                                source_expression = Const(1.0)
                            else:
                                if (
                                        normalized_name.startswith("f")
                                        or "_hz" in normalized_name
                                ):
                                    source_expression = nominal_frequency_hz
                                else:
                                    if dc_voltage is None:
                                        source_expression = native_outputs["u"]
                                    else:
                                        source_expression = dc_voltage
        alias_expressions[signal_name] = source_expression
    return alias_expressions


def _build_pll_alias_expressions(
        circuit: MultiCircuit,
        signal_names: List[str],
        measured_bus: Bus,
        meter: ElmPhi | None,
        meter_id: str,
        use_stationary_reference: bool,
) -> Tuple[Dict[str, Expr], Block | None]:
    """
    Materialize and expose one native stateful ``ElmPhi__pll`` measurement.

    Older DGS definitions omit the native equipment row even though the
    ``BlkSlot`` declares ``ElmPhi``. In that case the documented PowerFactory
    equipment defaults are used. Enriched DGS files override both gains from
    their own ``ElmPhi`` row, so normal execution remains DGS-only.

    :param circuit: Imported circuit owning the shared variable factory.
    :param signal_names: Scalar output symbols declared by the PLL slot.
    :param measured_bus: AC terminal of the associated physical converter.
    :param meter: Parsed native PLL row, or ``None`` for an implicit old export.
    :param meter_id: Stable DGS equipment or slot identifier.
    :param use_stationary_reference: Preserve the native unit-vector reference
        when the built-in PLL has no measured-bus connection.
    :return: Supported aliases and the optional stateful PLL block that owns
        their output variables.
    """
    voltage_magnitude: Expr
    voltage_angle: Expr
    dc_voltage: Expr | None
    voltage_magnitude, voltage_angle, dc_voltage = _get_bus_voltage_expressions(
        bus=measured_bus,
    )
    alias_expressions: Dict[str, Expr] = dict()
    measurement_block: Block | None = None
    if dc_voltage is None and use_stationary_reference:
        # A native ElmPhi without pbusbar is a stationary frame source. It is
        # not an algebraic bus-angle approximation and owns no dynamic state.
        signal_name: str
        normalized_name: str
        for signal_name in signal_names:
            normalized_name = signal_name.lower()
            if normalized_name.startswith("cosphi"):
                alias_expressions[signal_name] = Const(1.0)
            else:
                if normalized_name.startswith("sinphi"):
                    alias_expressions[signal_name] = Const(0.0)
                else:
                    is_hertz_frequency_alias: bool = (
                        signal_name == "Fmeas"
                        or "_hz" in normalized_name
                        or normalized_name.endswith("hz")
                    )
                    if is_hertz_frequency_alias:
                        alias_expressions[signal_name] = Const(float(circuit.fBase))
                    else:
                        if normalized_name == "fmeas":
                            alias_expressions[signal_name] = Const(1.0)
                        else:
                            pass
    else:
        pass

    if dc_voltage is None and not use_stationary_reference:
        # These are the native built-in defaults observed from the equipment
        # class itself. They are a class contract, not a project calibration.
        proportional_gain: float = 200.0196990966797
        integral_gain: float = 10004.1298828125
        if meter is None:
            pass
        else:
            if meter.Kp > 0.0:
                proportional_gain = float(meter.Kp)
            else:
                pass
            if meter.Ki > 0.0:
                integral_gain = float(meter.Ki)
            else:
                pass

        pll_block: Block
        native_outputs: Dict[str, Var]
        pll_block, native_outputs = build_rms_phase_locked_loop_block(
            vf=circuit.var_factory,
            va=voltage_angle,
            proportional_gain=proportional_gain,
            integral_gain=integral_gain,
            nominal_frequency_hz=float(circuit.fBase),
            name=_get_veragrid_meter_name(
                meter_kind=RmsPhysicalMeterKind.PHASE_LOCKED_LOOP,
                source_fid=meter_id,
            ),
        )
        measurement_block = pll_block

        signal_name: str
        normalized_name: str
        source_var: Var | None
        for signal_name in signal_names:
            normalized_name = signal_name.lower()
            is_hertz_frequency_alias: bool = (
                signal_name == "Fmeas"
                or "_hz" in normalized_name
                or normalized_name.endswith("hz")
            )
            if is_hertz_frequency_alias:
                source_var = native_outputs.get("Fmeas", None)
            else:
                if normalized_name == "fmeas":
                    source_var = native_outputs.get("fmeas", None)
                else:
                    if normalized_name == "fmeas_hz" or normalized_name == "fmeashz":
                        source_var = native_outputs.get("Fmeas", None)
                    else:
                        if normalized_name.startswith("cosphi"):
                            source_var = native_outputs.get("cosphi", None)
                        else:
                            if normalized_name.startswith("sinphi"):
                                source_var = native_outputs.get("sinphi", None)
                            else:
                                source_var = native_outputs.get(signal_name, None)
            if source_var is None:
                pass
            else:
                alias_expressions[signal_name] = source_var
    else:
        pass
    return alias_expressions, measurement_block


def _build_current_alias_expressions(
        meter: StaImea,
        signal_names: List[str],
        measured_bus: Bus,
        source_device: DynamicDevice,
        source_terminal_index: int,
        system_base_mva: float,
        host_model: Block | None = None,
) -> Dict[str, Expr]:
    """
    Map exported current-slot aliases to physical terminal expressions.

    :param meter: Parsed native current meter carrying its output-unit mode.
    :param signal_names: Scalar outgoing BlkSig aliases.
    :param measured_bus: Exact measured VeraGrid bus.
    :param source_device: Exact measured physical device.
    :param source_terminal_index: Measured DGS terminal ordinal.
    :param system_base_mva: VeraGrid circuit power base in MVA.
    :param host_model: Imported consumer model declaring any input-base conversion.
    :return: Alias-to-expression mapping.
    """
    if meter.outserv != 0:
        return dict()
    else:
        pass

    if measured_bus.is_dc:
        return _build_dc_current_alias_expressions(
            meter=meter,
            signal_names=signal_names,
            measured_bus=measured_bus,
            source_device=source_device,
            source_terminal_index=source_terminal_index,
            system_base_mva=system_base_mva,
        )
    else:
        pass

    voltage_magnitude: Expr
    voltage_angle: Expr
    dc_voltage: Expr | None
    voltage_magnitude, voltage_angle, dc_voltage = _get_bus_voltage_expressions(
        bus=measured_bus,
    )
    active_power: Expr | None
    reactive_power: Expr | None
    active_power, reactive_power = _get_device_pq_expressions(
        source_device=source_device,
        source_terminal_index=source_terminal_index,
    )
    if active_power is None:
        return dict()
    else:
        pass
    if reactive_power is None:
        reactive_power = Const(0.0)
    else:
        pass
    native_outputs: Dict[str, Expr] = build_rms_current_meter_outputs_from_pq(
        vm=voltage_magnitude,
        va=voltage_angle,
        p=active_power,
        q=reactive_power,
    )
    current_scale: float = 1.0
    device_power_base_mva: float | None = _get_device_power_base_mva(
        source_device=source_device,
    )
    if (
            meter.i_mode == 1
            and device_power_base_mva is not None
            and system_base_mva > 0.0
    ):
        # RMS network currents use the circuit MVA base. PowerFactory's
        # per-unit current meter uses the explicit nominal base of the device
        # referenced by its cubicle, so convert before feeding the DSL.
        current_scale = system_base_mva / device_power_base_mva
        if host_model is None:
            pass
        else:
            # Some OEM controllers receive the native meter on a declared
            # rated-voltage base and immediately convert it to their common
            # controller base. Reconstruct that input base from the exported
            # symbolic division itself. This keeps the DSL conversion intact
            # and avoids project- or signal-name-specific scale factors.
            current_scale *= _infer_current_meter_input_voltage_gain(
                host_model=host_model,
                signal_names=signal_names,
                measured_voltage_base_kv=float(measured_bus.Vnom),
            )
    else:
        pass
    if isinstance(source_device, VSC):
        # ElmVsc's native busac current points from the AC network into the
        # converter. VeraGrid's Pt/Qt terminal current uses the opposite branch
        # orientation, so the complete Cartesian current must be reversed.
        current_scale = -current_scale
    else:
        pass
    alias_expressions: Dict[str, Expr] = dict()
    signal_name: str
    normalized_name: str

    for signal_name in signal_names:
        normalized_name = signal_name.lower()
        if "i1r" in normalized_name or normalized_name == "ir":
            alias_expressions[signal_name] = Const(current_scale) * native_outputs["ir"]
        else:
            if "i1i" in normalized_name or normalized_name == "ii":
                alias_expressions[signal_name] = Const(current_scale) * native_outputs["ii"]
            else:
                alias_expressions[signal_name] = Const(current_scale) * native_outputs["i"]
    return alias_expressions


def _collect_dgs_divisions(expression: Expr,
                           divisions: List[Func2]) -> None:
    """
    Collect every native ``dgs_divide`` node below one expression.

    :param expression: Symbolic expression to inspect.
    :param divisions: Output list updated in traversal order.
    :return: None.
    """
    if isinstance(expression, BinOp):
        _collect_dgs_divisions(expression=expression.left, divisions=divisions)
        _collect_dgs_divisions(expression=expression.right, divisions=divisions)
    else:
        if isinstance(expression, UnOp):
            _collect_dgs_divisions(
                expression=expression.operand,
                divisions=divisions,
            )
        else:
            if isinstance(expression, Func):
                _collect_dgs_divisions(expression=expression.arg, divisions=divisions)
            else:
                if isinstance(expression, Func2):
                    if expression.name == "dgs_divide":
                        divisions.append(expression)
                    else:
                        pass
                    _collect_dgs_divisions(
                        expression=expression.arg1,
                        divisions=divisions,
                    )
                    _collect_dgs_divisions(
                        expression=expression.arg2,
                        divisions=divisions,
                    )
                else:
                    pass


def _build_constant_parameter_value_lookup(host_model: Block) -> Dict[int, float]:
    """
    Build the constant parameter values declared by one imported model tree.

    :param host_model: Imported root block.
    :return: Constant values keyed by symbolic variable UID.
    """
    values_by_uid: Dict[int, float] = dict()
    block: Block
    parameter_var: Var
    parameter_value: object

    for block in host_model.get_all_blocks():
        # Event parameters preserve the concrete ElmDsl instance values.
        for parameter_var, parameter_value in block.event_dict.items():
            if isinstance(parameter_value, Const) and parameter_value.value is not None:
                values_by_uid[parameter_var.uid] = float(parameter_value.value)
            else:
                pass

        # Immutable parameters may also participate in a generated base ratio.
        for parameter_var, parameter_value in block.parameters.items():
            if isinstance(parameter_value, Const) and parameter_value.value is not None:
                values_by_uid[parameter_var.uid] = float(parameter_value.value)
            else:
                pass

    return values_by_uid


def _get_declared_values(expression: Expr,
                         values_by_uid: Dict[int, float]) -> List[float]:
    """
    Return constant parameter values referenced by one expression.

    :param expression: Symbolic expression whose dependencies are inspected.
    :param values_by_uid: Known constant parameter values.
    :return: Constant values referenced by the expression.
    """
    declared_values: List[float] = list()
    expression_vars: List[Var] = expression.get_vars()
    expression_var: Var

    for expression_var in expression_vars:
        declared_value: float | None = values_by_uid.get(expression_var.uid, None)
        if declared_value is None:
            pass
        else:
            declared_values.append(declared_value)
    return declared_values


def _infer_current_meter_input_voltage_gain(
        host_model: Block,
        signal_names: List[str],
        measured_voltage_base_kv: float,
) -> float:
    """
    Infer a native current-meter input voltage-base conversion from its consumer.

    A PowerFactory controller may declare ``Un / Ur`` in the first equation
    consuming a per-unit current meter. The meter itself is then expressed on
    ``Ur`` while the VeraGrid network current uses the measured bus base ``Un``.
    This routine identifies that exported ratio structurally and returns
    ``Ur / Un``. Missing or conflicting declarations safely retain unity.

    :param host_model: Imported model consuming the native meter aliases.
    :param signal_names: Exact scalar aliases produced by the meter slot.
    :param measured_voltage_base_kv: VeraGrid bus nominal voltage in kV.
    :return: Unique inferred input-base gain, or one when absent or ambiguous.
    """
    if measured_voltage_base_kv <= 0.0:
        return 1.0
    else:
        pass

    vars_by_name: Dict[str, List[Var]] = build_name_to_vars_lookup(
        block=host_model,
    )
    target_uids: Set[int] = set()
    signal_name: str
    target_var: Var
    for signal_name in signal_names:
        for target_var in vars_by_name.get(signal_name, list()):
            target_uids.add(target_var.uid)

    if len(target_uids) == 0:
        return 1.0
    else:
        pass

    values_by_uid: Dict[int, float] = _build_constant_parameter_value_lookup(
        host_model=host_model,
    )
    candidate_gains: List[float] = list()
    block: Block
    equation: Expr
    equation_uids: Set[int]
    divisions: List[Func2]
    division: Func2

    for block in host_model.get_all_blocks():
        for equation in block.algebraic_eqs:
            equation_uids = set(variable.uid for variable in equation.get_vars())
            if len(target_uids.intersection(equation_uids)) == 0:
                pass
            else:
                divisions = list()
                _collect_dgs_divisions(
                    expression=equation,
                    divisions=divisions,
                )
                for division in divisions:
                    numerator_values: List[float] = _get_declared_values(
                        expression=division.arg1,
                        values_by_uid=values_by_uid,
                    )
                    denominator_values: List[float] = _get_declared_values(
                        expression=division.arg2,
                        values_by_uid=values_by_uid,
                    )
                    numerator_matches_bus: bool = any(
                        abs(value - measured_voltage_base_kv)
                        <= 1.0e-9 * max(1.0, measured_voltage_base_kv)
                        for value in numerator_values
                    )
                    denominator_value: float
                    if numerator_matches_bus:
                        for denominator_value in denominator_values:
                            candidate_gain: float = (
                                denominator_value / measured_voltage_base_kv
                            )
                            is_plausible_voltage_ratio: bool = (
                                candidate_gain >= 0.5
                                and candidate_gain <= 2.0
                                and abs(candidate_gain - 1.0) > 1.0e-9
                            )
                            if is_plausible_voltage_ratio:
                                candidate_gains.append(candidate_gain)
                            else:
                                pass
                    else:
                        pass

    unique_gains: List[float] = list()
    candidate_gain = 1.0
    for candidate_gain in candidate_gains:
        gain_already_present: bool = any(
            abs(candidate_gain - existing_gain) <= 1.0e-9
            for existing_gain in unique_gains
        )
        if gain_already_present:
            pass
        else:
            unique_gains.append(candidate_gain)

    if len(unique_gains) == 1:
        return unique_gains[0]
    else:
        return 1.0


def _build_power_alias_expressions(
        meter: StaPqmea,
        signal_names: List[str],
        source_device: DynamicDevice,
        source_terminal_index: int,
        system_base_mva: float,
        circuit: MultiCircuit,
        host_device: DynamicDevice,
) -> Dict[str, Expr]:
    """
    Map exported P/Q-slot aliases to physical terminal power expressions.

    :param meter: Parsed native P/Q meter.
    :param signal_names: Scalar outgoing BlkSig aliases.
    :param source_device: Exact measured physical device.
    :param source_terminal_index: Measured DGS terminal ordinal.
    :param system_base_mva: VeraGrid circuit power base in MVA.
    :param circuit: Canonical circuit used for exact topology validation.
    :param host_device: Dynamic equipment root consuming the measurement.
    :return: Alias-to-expression mapping.
    """
    if meter.outserv != 0:
        return dict()
    else:
        pass

    active_power: Expr | None
    reactive_power: Expr | None
    active_power, reactive_power = _get_ideal_transformer_relay_pq_expressions(
        circuit=circuit,
        source_device=source_device,
        source_terminal_index=source_terminal_index,
        host_device=host_device,
    )
    if active_power is None or reactive_power is None:
        active_power, reactive_power = _get_device_pq_expressions(
            source_device=source_device,
            source_terminal_index=source_terminal_index,
        )
    else:
        pass
    if active_power is None or reactive_power is None:
        return dict()
    else:
        pass
    orientation: float
    if meter.i_orient == 0:
        orientation = 1.0
    else:
        # PowerFactory exports the reversed StaPqmea orientation as ``1`` in
        # current DGS 7.2 files. Older/hand-authored DGS fixtures can encode
        # the same selected state as ``-1``; zero is the only native state
        # that retains the physical terminal sign.
        orientation = -1.0
    power_scale: float
    if meter.Snom > 0.0 and system_base_mva > 0.0:
        # The meter exports p.u. on its own Snom while the RMS network stores
        # terminal power on MultiCircuit.Sbase.
        power_scale = system_base_mva / float(meter.Snom)
    else:
        power_scale = 1.0
    native_outputs: Dict[str, Expr] = build_rms_power_meter_outputs_from_pq(
        p=Const(orientation * power_scale) * active_power,
        q=Const(orientation * power_scale) * reactive_power,
    )
    alias_expressions: Dict[str, Expr] = dict()
    signal_name: str

    for signal_name in signal_names:
        if signal_name.lower().startswith("q"):
            alias_expressions[signal_name] = native_outputs["q"]
        else:
            alias_expressions[signal_name] = native_outputs["p"]
    return alias_expressions


def _refer_vsc_pq_controls_through_measured_transformer(
        circuit: MultiCircuit,
        host_device: DynamicDevice | None,
        source_device: DynamicDevice,
        source_terminal_index: int,
) -> bool:
    """Refer a configured remote P/Q pair to the VSC electrical terminal.

    A finite-impedance step-up transformer can be the declared P/Q measurement
    point of a native VSC composite. VeraGrid's static VSC formulation owns its
    controls at the converter terminal, so the configured remote target must be
    transported through the canonical transformer two-port at the imported
    voltage snapshot. This keeps the configured setpoint authoritative while
    accounting for the transformer's reactive consumption.

    :param circuit: Canonical circuit that owns the system power base.
    :param host_device: Dynamic root consuming the native power measurement.
    :param source_device: Physical device selected by the measured cubicle.
    :param source_terminal_index: Measured transformer terminal ordinal.
    :return: ``True`` when both VSC controls were referred successfully.
    """
    if (
            isinstance(host_device, VSC)
            and isinstance(source_device, Transformer2W)
            and not source_device.rms_model.dynamic_model_contract.rms_ideal_transformer
            and circuit.Sbase > 0.0
    ):
        pass
    else:
        return False

    control1: ConverterControlType = host_device.control1
    control2: ConverterControlType = host_device.control2
    if control1 is ConverterControlType.Pac and control2 is ConverterControlType.Qac:
        configured_remote_power: complex = complex(
            -float(host_device.control1_val),
            -float(host_device.control2_val),
        )
    elif control1 is ConverterControlType.Qac and control2 is ConverterControlType.Pac:
        configured_remote_power = complex(
            -float(host_device.control2_val),
            -float(host_device.control1_val),
        )
    else:
        return False

    host_ac_bus: Bus | None
    if host_device.bus_to is not None and not host_device.bus_to.is_dc:
        host_ac_bus = host_device.bus_to
    else:
        if host_device.bus_from is not None and not host_device.bus_from.is_dc:
            host_ac_bus = host_device.bus_from
        else:
            host_ac_bus = None

    measured_bus: Bus | None
    opposite_bus: Bus | None
    measured_is_from: bool
    if source_terminal_index == 0 and source_device.bus_to is host_ac_bus:
        measured_bus = source_device.bus_from
        opposite_bus = source_device.bus_to
        measured_is_from = True
    elif source_terminal_index == 1 and source_device.bus_from is host_ac_bus:
        measured_bus = source_device.bus_to
        opposite_bus = source_device.bus_from
        measured_is_from = False
    else:
        return False

    if measured_bus is None or opposite_bus is None:
        return False
    else:
        pass

    measured_voltage: complex = complex(
        float(measured_bus.Vm0)
        * cmath.exp(1.0j * float(measured_bus.Va0))
    )
    series_impedance: complex = complex(
        float(source_device.R),
        float(source_device.X),
    )
    if (
            abs(measured_voltage) > 1.0e-12
            and abs(series_impedance) > 1.0e-12
            and math.isfinite(measured_voltage.real)
            and math.isfinite(measured_voltage.imag)
    ):
        pass
    else:
        return False

    virtual_tap_from: float
    virtual_tap_to: float
    virtual_tap_from, virtual_tap_to = source_device.get_virtual_taps()
    tap_module: float = float(source_device.tap_module)
    tap_phase: float = float(source_device.tap_phase)
    series_admittance: complex = 1.0 / series_impedance
    half_shunt_admittance: complex = complex(
        float(source_device.G),
        float(source_device.B),
    ) / 2.0
    y_from_from: complex = (
        (series_admittance + half_shunt_admittance)
        / (tap_module * tap_module * virtual_tap_from * virtual_tap_from)
    )
    y_from_to: complex = (
        -series_admittance
        / (
            tap_module
            * cmath.exp(-1.0j * tap_phase)
            * virtual_tap_from
            * virtual_tap_to
        )
    )
    y_to_from: complex = (
        -series_admittance
        / (
            tap_module
            * cmath.exp(1.0j * tap_phase)
            * virtual_tap_to
            * virtual_tap_from
        )
    )
    y_to_to: complex = (
        (series_admittance + half_shunt_admittance)
        / (virtual_tap_to * virtual_tap_to)
    )
    measured_power_pu: complex = configured_remote_power / float(circuit.Sbase)
    measured_current: complex = (measured_power_pu / measured_voltage).conjugate()

    # Solve the two-port relation from the configured measured-terminal power,
    # then use the opposite terminal flow as the converter's local target.
    if measured_is_from and abs(y_from_to) > 1.0e-12:
        opposite_voltage: complex = (
            measured_current - y_from_from * measured_voltage
        ) / y_from_to
        opposite_current: complex = (
            y_to_from * measured_voltage + y_to_to * opposite_voltage
        )
    elif not measured_is_from and abs(y_to_from) > 1.0e-12:
        opposite_voltage = (
            measured_current - y_to_to * measured_voltage
        ) / y_to_from
        opposite_current = (
            y_from_from * opposite_voltage + y_from_to * measured_voltage
        )
    else:
        return False

    local_vsc_power: complex = (
        -opposite_voltage * opposite_current.conjugate() * float(circuit.Sbase)
    )
    local_target_is_finite: bool = bool(
        math.isfinite(local_vsc_power.real)
        and math.isfinite(local_vsc_power.imag)
    )
    if local_target_is_finite:
        if control1 is ConverterControlType.Pac:
            host_device.control1_val = float(local_vsc_power.real)
            host_device.control2_val = float(local_vsc_power.imag)
        else:
            host_device.control1_val = float(local_vsc_power.imag)
            host_device.control2_val = float(local_vsc_power.real)
        return True
    else:
        return False


def _resolve_virtual_pll_voltage_source(
        pll_entry: ElmCompInstanceEntry,
        entries: List[ElmCompInstanceEntry],
        dgs_circuit: DgsCircuit,
        dgs_element_by_id: Dict[str, DGSElement],
        bus_by_id: Dict[str, Bus],
) -> Tuple[StaVmea | None, Bus | None]:
    """
    Resolve an uninstantiated ElmPhi/ElmPll slot to its upstream voltage meter.

    PowerFactory may leave the PLL ``pElm`` position empty because the slot is
    a built-in signal processor. Its source remains authoritative in BlkSig:
    a voltage-meter slot feeds the PLL input node.

    :param pll_entry: Empty physical slot filtered as ElmPhi or ElmPll.
    :param entries: Direct composite entries indexed by their BlkSlot FIDs.
    :param dgs_circuit: Parsed source DGS containing the BlkSig graph.
    :param dgs_element_by_id: Exact DGS element lookup.
    :param bus_by_id: Imported bus lookup keyed by source terminal FID.
    :return: Upstream voltage meter and measured bus, or two ``None`` values.
    """
    entry_by_slot_id: Dict[str, ElmCompInstanceEntry] = dict()
    candidate_entry: ElmCompInstanceEntry
    for candidate_entry in entries:
        if candidate_entry.slot_id is None:
            pass
        else:
            entry_by_slot_id[candidate_entry.slot_id] = candidate_entry

    if pll_entry.slot_id is None:
        return None, None
    else:
        pass

    source_meter: StaVmea | None = None
    source_bus: Bus | None = None
    signal: BlkSig
    for signal in dgs_circuit.blksigs:
        if str(signal.pnodto).strip() == pll_entry.slot_id:
            source_slot_id: str = str(signal.pnodfrom).strip()
            source_entry: ElmCompInstanceEntry | None = entry_by_slot_id.get(
                source_slot_id,
                None,
            )
            if source_entry is None or source_entry.element_id is None:
                pass
            else:
                source_element: DGSElement | None = dgs_element_by_id.get(
                    source_entry.element_id,
                    None,
                )
                if isinstance(source_element, StaVmea):
                    terminal_id: str | None = _resolve_terminal_id(
                        pointer_id=source_element.pbusbar,
                        dgs_element_by_id=dgs_element_by_id,
                    )
                    if terminal_id is None:
                        pass
                    else:
                        candidate_bus: Bus | None = bus_by_id.get(
                            terminal_id,
                            None,
                        )
                        if candidate_bus is None:
                            pass
                        else:
                            source_meter = source_element
                            source_bus = candidate_bus
                else:
                    pass
        else:
            pass
    return source_meter, source_bus


def _resolve_native_pll_element(
        root_element: ElmComp,
        dgs_circuit: DgsCircuit,
) -> ElmPhi | None:
    """
    Resolve an enriched native PLL row owned by one composite root.

    PowerFactory keeps the built-in measurement outside ``ElmComp.pElm`` in
    some export versions. Its authoritative ``fold_id`` still identifies the
    owning composite, which is sufficient without relying on display names.

    :param root_element: Composite model whose PLL slot is being bound.
    :param dgs_circuit: Parsed DGS containing optional ``ElmPhi`` rows.
    :return: Unique owned PLL row or ``None`` when unavailable or ambiguous.
    """
    matching_elements: List[ElmPhi] = list()
    meter: ElmPhi
    root_id: str = str(root_element.ID).strip()

    for meter in dgs_circuit.elmphis:
        if str(meter.fold_id).strip() == root_id:
            matching_elements.append(meter)
        else:
            pass

    if len(matching_elements) == 1:
        return matching_elements[0]
    else:
        return None


def _remove_meter_target_fallback_ownership(
        host_model: Block,
        target_var: Var,
) -> None:
    """Remove imported receiver ownership superseded by a native meter.

    Graphical DGS inputs are exposed as algebraic variables on their root so
    an unconnected input can retain its imported startup value. Once an exact
    native meter is connected, that meter owns the only solved equation and
    the receiver remains an input alias rather than a second algebraic owner.

    :param host_model: Activated imported controller root.
    :param target_var: Exact receiver input connected to the native meter.
    :return: None.
    """
    target_block: Block
    target_event_var: Var
    target_initial_var: Var

    # Remove runtime and startup fallbacks from whichever imported child
    # declared them. The native meter owns both phases after connection.
    for target_block in host_model.get_all_blocks():
        target_event_vars: List[Var] = list(target_block.event_dict.keys())
        for target_event_var in target_event_vars:
            if target_event_var is target_var:
                target_block.event_dict.pop(target_event_var, None)
            else:
                pass
        target_initial_vars: List[Var] = list(target_block.init_eqs.keys())
        for target_initial_var in target_initial_vars:
            if target_initial_var is target_var:
                target_block.init_eqs.pop(target_initial_var, None)
            else:
                pass

    # Imported wrapper levels may re-expose the same unconnected graphical
    # input as an algebraic unknown without an equation. The physical meter now
    # supplies that equation, so the exact receiver object must no longer be
    # registered as a solved variable at any wrapper level.
    target_index: int
    candidate_index: int
    candidate_var: Var
    mapped_var: Var | None
    for target_block in host_model.get_all_blocks():
        target_index = len(target_block.algebraic_vars)
        for candidate_index, candidate_var in enumerate(target_block.algebraic_vars):
            if candidate_var is target_var:
                target_index = candidate_index
            else:
                pass
        if target_index < len(target_block.algebraic_vars):
            target_block.algebraic_vars.pop(target_index)
        else:
            pass
        mapped_var = target_block.var_mapping.get(target_var.name, None)
        if mapped_var is target_var:
            target_block.var_mapping.pop(target_var.name, None)
        else:
            pass


def _promote_meter_dependent_startup_inputs(
        host_model: Block,
        meter_output_var: Var,
) -> None:
    """Retain meter-derived startup-only inputs as event parameters.

    A PowerFactory ``inc()`` assignment may initialize an otherwise unowned
    controller input from a physical meter. Such an input is held after startup
    and therefore belongs to the event-parameter store, not the solved DAE.

    :param host_model: Activated imported controller root.
    :param meter_output_var: Connected physical meter output.
    :return: None.
    """
    candidate_block: Block
    initial_var: Var
    initial_expr: Expr
    expression_var: Var
    input_var: Var

    for candidate_block in host_model.get_all_blocks():
        initial_items: List[Tuple[Var, Expr]] = list(
            candidate_block.init_eqs.items()
        )
        for initial_var, initial_expr in initial_items:
            is_input: bool = False
            for input_var in candidate_block.in_vars:
                if input_var is initial_var:
                    is_input = True
                else:
                    pass
            depends_on_meter: bool = False
            for expression_var in initial_expr.get_vars():
                if expression_var.uid == meter_output_var.uid:
                    depends_on_meter = True
                else:
                    pass
            if is_input and depends_on_meter:
                candidate_block.init_eqs.pop(initial_var, None)
                candidate_block.event_dict[initial_var] = initial_expr
            else:
                pass


def _connect_meter_aliases(
        host_model: Block,
        targets_by_name: Dict[str, List[Var]],
        alias_expressions: Dict[str, Expr],
        meter_name: str,
        meter_source_fid: str,
        meter_target_fid: str,
        meter_terminal_side: RmsTerminalSide,
        meter_kind: RmsPhysicalMeterKind,
        var_factory: VarFactory,
        prepared_meter_block: Block | None,
) -> int:
    """
    Finalize one native meter block and connect it to controller inputs.

    Early import may already own the controller output variables. Finalize
    that unique FID/UID-matched block instead of creating a second owner.

    :param host_model: Activated imported controller model.
    :param targets_by_name: Stable pre-connection control interfaces by name.
    :param alias_expressions: Exported signal aliases and physical expressions.
    :param meter_name: Stable user-facing native measurement identity.
    :param meter_source_fid: Exact native meter or built-in slot FID.
    :param meter_target_fid: Exact measured bus or physical-device FID.
    :param meter_terminal_side: Canonical physical terminal selected by the meter.
    :param meter_kind: Typed physical quantity family.
    :param var_factory: Shared circuit variable factory that owns connections.
    :param prepared_meter_block: Optional stateful meter whose output variables
        already occur in ``alias_expressions``.
    :return: Number of aliases connected to existing control variables.
    """
    connected_expressions: Dict[str, Expr] = dict()
    connected_alias_names: List[str] = list()
    connected_count: int = 0
    alias_name: str
    source_expression: Expr
    target_vars: List[Var] | None
    output_by_alias_name: Dict[str, Var] = dict()
    meter_block: Block

    # Build the complete supported interface before mutating the final model.
    # A source with no exact controller endpoint must not leave an orphan node
    # in the dynamic editor or an unused equation in the runtime graph.
    for alias_name, source_expression in alias_expressions.items():
        target_vars = targets_by_name.get(alias_name, None)
        if target_vars is None or len(target_vars) == 0:
            pass
        else:
            connected_expressions[alias_name] = source_expression

    if len(connected_expressions) == 0:
        return 0
    else:
        pass

    # Early measurements keep controller ports alive during activation. Their
    # canonical name alone is insufficient: every selected alias must resolve
    # to exactly one of that block's actual output UIDs before any mutation.
    early_meter_blocks: List[Block] = list(
        candidate for candidate in host_model.get_all_blocks()
        if candidate.name == meter_name
    )
    early_meter_block: Block | None = None
    early_parent: Block | None = None
    early_child_index: int = -1
    early_outputs: Dict[str, Var] = dict()
    if len(early_meter_blocks) == 0:
        pass
    else:
        if len(early_meter_blocks) != 1:
            return 0
        else:
            early_meter_block = early_meter_blocks[0]
        for alias_name in connected_expressions.keys():
            target_vars = targets_by_name.get(alias_name, None)
            target_uids: Set[int] = set(
                target.uid for target in target_vars
            ) if target_vars is not None else set()
            matching_outputs: List[Var] = list(
                output for output in early_meter_block.out_vars
                if output.uid in target_uids
            )
            if len(matching_outputs) != 1:
                return 0
            else:
                early_outputs[alias_name] = matching_outputs[0]
        if set(output.uid for output in early_outputs.values()) != set(
                output.uid for output in early_meter_block.out_vars
        ):
            return 0
        else:
            pass
        candidate_parent: Block
        candidate_child: Block
        candidate_index: int
        for candidate_parent in host_model.get_all_blocks():
            for candidate_index, candidate_child in enumerate(candidate_parent.children):
                if candidate_child is early_meter_block:
                    if early_parent is None:
                        early_parent = candidate_parent
                        early_child_index = candidate_index
                    else:
                        return 0
                else:
                    pass
        if early_parent is None:
            return 0
        else:
            pass

    if prepared_meter_block is None and early_meter_block is not None:
        # Keep the exact consumer Var objects, replacing only early host-side
        # placeholders with the established physical FID/side expressions.
        meter_block = early_meter_block
        output_by_alias_name = early_outputs
        meter_block.in_vars = list()
        meter_block.algebraic_vars = list(early_outputs.values())
        meter_block.out_vars = list(early_outputs.values())
        meter_block.algebraic_eqs = list(
            early_outputs[alias_name] - source_expression
            for alias_name, source_expression in connected_expressions.items()
        )
        meter_block.init_eqs = dict(
            (early_outputs[alias_name], source_expression)
            for alias_name, source_expression in connected_expressions.items()
        )
    elif prepared_meter_block is None:
        meter_block, output_by_alias_name = build_rms_physical_signal_meter_block(
            vf=var_factory,
            signal_expressions=connected_expressions,
            output_signal_names=_get_veragrid_meter_output_names(
                alias_names=list(connected_expressions.keys()),
            ),
            name=meter_name,
            source_fid=meter_source_fid,
            target_fid=meter_target_fid,
            terminal_side=meter_terminal_side,
            meter_kind=meter_kind,
        )
    else:
        meter_block = prepared_meter_block
        prepared_outputs_complete: bool = True
        for alias_name, source_expression in connected_expressions.items():
            if isinstance(source_expression, Var):
                output_by_alias_name[alias_name] = source_expression
            else:
                prepared_outputs_complete = False
        if prepared_outputs_complete:
            if early_meter_block is None:
                pass
            else:
                # Alias spellings may share one prepared native output. A
                # single solved UID cannot retain two different early owners;
                # reject the entire mapping before changing any equations.
                retained_uid_by_prepared_uid: Dict[int, int] = dict()
                for alias_name in connected_expressions.keys():
                    prepared_output: Var = output_by_alias_name[alias_name]
                    retained_uid: int = early_outputs[alias_name].uid
                    previous_uid: int | None = retained_uid_by_prepared_uid.get(
                        prepared_output.uid, None,
                    )
                    if previous_uid is None or previous_uid == retained_uid:
                        retained_uid_by_prepared_uid[prepared_output.uid] = retained_uid
                    else:
                        return 0
                # Stateful PLL equations and startup belong to the prepared
                # native block. Rebind its outputs before replacing the early
                # child; preserve the existing editor identity and position.
                for alias_name, source_expression in connected_expressions.items():
                    output_var: Var = output_by_alias_name[alias_name]
                    retained_output: Var = early_outputs[alias_name]
                    meter_block.update_model(old=output_var, new=retained_output)
                    output_by_alias_name[alias_name] = retained_output
                meter_block.uid = early_meter_block.uid
        else:
            return 0

    selected_output_names: List[str] = list()
    selected_output_uids: List[int] = list()
    selected_alias_name: str
    for selected_alias_name in connected_expressions.keys():
        selected_output_var: Var | None = output_by_alias_name.get(
            selected_alias_name,
            None,
        )
        if selected_output_var is None:
            return 0
        else:
            selected_output_names.append(selected_output_var.name)
            selected_output_uids.append(selected_output_var.uid)

    # Persist only the outputs that have exact controller endpoints. The block
    # owns their equations; this metadata exposes physical identity and signal
    # selection to local logic and global readout without duplicating variables.
    meter_block.dynamic_model_contract.rms_physical_measurement_point = (
        RmsPhysicalMeasurementPoint(
            source_fid=meter_source_fid,
            target_fid=meter_target_fid,
            terminal_side=meter_terminal_side,
            meter_kind=meter_kind,
            output_signal_names=tuple(selected_output_names),
            output_var_uids=tuple(selected_output_uids),
        )
    )

    # The child is part of the one canonical RMS graph. The editor will expose
    # it as a separate node and infer each cable from the propagated Var UID.
    if early_meter_block is None:
        host_model.add(meter_block)
    else:
        if early_parent is not None:
            early_parent.children[early_child_index] = meter_block
        else:
            return 0
    target_var: Var
    for alias_name, source_expression in connected_expressions.items():
        target_vars = targets_by_name.get(alias_name, None)
        if target_vars is None:
            pass
        else:
            output_var = output_by_alias_name.get(alias_name, None)
            # Early outputs reuse controller Vars, which need not yet carry
            # a cable reference. Reuse the factory's declared reference owner
            # so editor connections expose the same identity as runtime UIDs.
            if output_var is not None and output_var.shared_ref is None:
                var_factory.add_shared_ref_to_var(
                    v=output_var,
                    shared_reference=f"{meter_name}:{alias_name}",
                )
            else:
                pass
            for target_var in target_vars:
                if output_var is None:
                    pass
                else:
                    if target_var.uid == output_var.uid:
                        # The early output already owns this exact consumer
                        # UID. Removing fallback ownership here would delete
                        # the newly finalized meter's solved variable.
                        _promote_meter_dependent_startup_inputs(
                            host_model=host_model,
                            meter_output_var=output_var,
                        )
                        target_var.shared_ref = output_var.shared_ref
                        connected_count += 1
                    else:
                        _remove_meter_target_fallback_ownership(
                            host_model=host_model,
                            target_var=target_var,
                        )
                    # One physical meter output may feed several exact slot
                    # endpoints. The shared reference draws the editor cable;
                    # VarFactory propagates the same edge into runtime UIDs.
                    if target_var.uid == output_var.uid or output_var.shared_ref is None:
                        pass
                    else:
                        target_var.shared_ref = output_var.shared_ref
                        var_factory.save_var_in_vars_references_dict(
                            var=target_var,
                            reference=output_var.shared_ref.name,
                        )
                        var_factory.add_connections(
                            vars_to_subs=list([target_var]),
                            incoming_vars=list([output_var]),
                        )
                        _promote_meter_dependent_startup_inputs(
                            host_model=host_model,
                            meter_output_var=output_var,
                        )
                        connected_count += 1
            if alias_name in connected_alias_names:
                pass
            else:
                connected_alias_names.append(alias_name)

    if connected_count > 0:
        # Native meter outputs are algebraic signal sources whose physical
        # dependencies may change during every nonlinear boundary refresh.
        # Keep this declaration separate from controller startup ordering so
        # the solver can refresh measurements after updating retained DGS
        # branches without replaying unrelated controller shells.
        runtime_measurement_sync_names: List[str] = list(
            host_model.dynamic_model_contract.runtime_measurement_shell_sync_names
        )
        alias_name: str
        for alias_name in connected_alias_names:
            if alias_name in runtime_measurement_sync_names:
                pass
            else:
                runtime_measurement_sync_names.append(alias_name)
        host_model.dynamic_model_contract.runtime_measurement_shell_sync_names = (
            runtime_measurement_sync_names
        )
    else:
        pass
    return connected_count


def _retain_disabled_meter_targets(
        host_model: Block,
        targets_by_name: Dict[str, List[Var]],
        signal_names: List[str],
) -> int:
    """
    Retain receiver fallbacks for one out-of-service native meter.

    PowerFactory does not create a solved measurement equation for a disabled
    meter. A receiving ``inc0()`` value remains authoritative; an input without
    such a fallback is a held zero signal. Representing both cases as runtime
    parameters keeps disabled inputs out of the Newton Jacobian.

    :param host_model: Activated imported controller model.
    :param targets_by_name: Stable control interfaces grouped by signal name.
    :param signal_names: Output signal names exported by the meter slot.
    :return: Number of receiver targets retained or initialized.
    """
    connected_count: int = 0
    signal_name: str
    target_vars: List[Var] | None
    target_var: Var
    target_block: Block
    existing_event_var: Var
    fallback_found: bool

    for signal_name in signal_names:
        target_vars = targets_by_name.get(signal_name, None)
        if target_vars is None:
            pass
        else:
            for target_var in target_vars:
                fallback_found = False
                for target_block in host_model.get_all_blocks():
                    for existing_event_var in target_block.event_dict.keys():
                        if existing_event_var.uid == target_var.uid:
                            fallback_found = True
                        else:
                            pass

                if fallback_found:
                    # Preserve the exact exported inc0 expression already held
                    # by the receiving controller input.
                    pass
                else:
                    # A disabled source without receiver fallback is a held
                    # zero boundary input, not an unconstrained DAE variable.
                    host_model.event_dict[target_var] = Const(0.0)
                connected_count += 1

    return connected_count




def _get_equipment_owned_signal_names(host_model: Block) -> Set[str]:
    """Return signal aliases whose units are owned by a physical wrapper.

    Imported graphical meters are built after dynamic device activation. A
    runtime adapter can therefore declare the boundary aliases it already
    supplies, allowing the generic binder to retain the meter in the catalogue
    without creating a second equation for the same controller receiver.

    :param host_model: Activated physical or logical RMS root.
    :return: Exact non-empty wrapper-owned signal names.
    """
    equipment_owned_names: Set[str] = set()
    raw_name: str

    for raw_name in host_model.dynamic_model_contract.dgs_equipment_owned_signal_names:
        if raw_name != "":
            equipment_owned_names.add(raw_name)
        else:
            pass
    else:
        pass
    return equipment_owned_names


def _find_block_child_path(
        root_block: Block,
        target_block: Block,
) -> Tuple[int, ...] | None:
    """Find one child's structural index path inside a canonical block tree.

    :param root_block: Canonical template root to traverse.
    :param target_block: Canonical descendant selected by an exact DGS slot FID.
    :return: Child-index path, an empty path for the root, or ``None``.
    """
    if root_block is target_block:
        return tuple()
    else:
        pass

    child_index: int
    child_block: Block
    for child_index, child_block in enumerate(root_block.children):
        child_path: Tuple[int, ...] | None = _find_block_child_path(
            root_block=child_block,
            target_block=target_block,
        )
        if child_path is None:
            pass
        else:
            return (child_index,) + child_path
    return None


def _resolve_block_child_path(
        root_block: Block,
        child_path: Tuple[int, ...],
) -> Block | None:
    """Resolve a canonical child path in one duplicated runtime block tree.

    :param root_block: Activated device or logical-controller block root.
    :param child_path: Structural child indices derived from its template.
    :return: Homologous runtime block, or ``None`` if structures diverged.
    """
    current_block: Block = root_block
    child_index: int
    for child_index in child_path:
        if child_index >= 0 and child_index < len(current_block.children):
            current_block = current_block.children[child_index]
        else:
            return None
    return current_block


def _translate_slot_blocks_to_runtime(
        template_root: Block,
        runtime_root: Block,
        template_block_by_slot_id: Dict[str, Block],
) -> Dict[str, Block]:
    """Translate exact template-slot ownership into one runtime block tree.

    :param template_root: Registered final template block.
    :param runtime_root: Activated device model or the same logical root.
    :param template_block_by_slot_id: Exact FID lookup into ``template_root``.
    :return: Exact FID lookup into ``runtime_root``.
    """
    runtime_block_by_slot_id: Dict[str, Block] = dict()
    slot_id: str
    template_block: Block
    for slot_id, template_block in template_block_by_slot_id.items():
        child_path: Tuple[int, ...] | None = _find_block_child_path(
            root_block=template_root,
            target_block=template_block,
        )
        if child_path is None:
            pass
        else:
            runtime_block: Block | None = _resolve_block_child_path(
                root_block=runtime_root,
                child_path=child_path,
            )
            if runtime_block is None:
                pass
            else:
                runtime_block_by_slot_id[slot_id] = runtime_block
    return runtime_block_by_slot_id


def _build_exact_meter_targets(
        dgs_circuit: DgsCircuit,
        source_slot_id: str,
        child_block_by_slot_id: Dict[str, Block],
) -> Dict[str, List[Var]]:
    """
    Resolve native-meter consumers from exact ``BlkSig`` graph endpoints.

    Equal signal labels are local to their ``BlkSlot`` and do not imply cable
    identity. The source and consumer slot FIDs plus ``inodto`` select the
    authoritative consumer port, matching the graph connection used while the
    DGS composite is built.

    :param dgs_circuit: Parsed DGS signal graph.
    :param source_slot_id: Native meter producer-slot FID.
    :param child_block_by_slot_id: Transient lookup into the canonical block
        tree created during direct DGS conversion.
    :return: Consumer port names mapped to their exact runtime variables.
    """
    slot_by_id: Dict[str, BlkSlot] = dict()
    slot: BlkSlot
    for slot in dgs_circuit.blkslots:
        slot_by_id[slot.ID] = slot

    exact_targets: Dict[str, List[Var]] = dict()
    signal: BlkSig
    for signal in dgs_circuit.blksigs:
        producer_slot_id: str = str(signal.pnodfrom).strip()
        if producer_slot_id != source_slot_id:
            pass
        else:
            consumer_slot_id: str = str(signal.pnodto).strip()
            consumer_block: Block | None = child_block_by_slot_id.get(
                consumer_slot_id,
                None,
            )
            consumer_slot: BlkSlot | None = slot_by_id.get(
                consumer_slot_id,
                None,
            )
            consumer_port_index: int = int(signal.inodto)
            port_ready: bool = (
                consumer_block is not None
                and consumer_slot is not None
                and consumer_port_index >= 0
                and consumer_port_index < len(consumer_slot.inputs)
            )
            if port_ready:
                consumer_components: List[str] = _split_slot_signal_labels(
                    signal_labels=list([
                        consumer_slot.inputs[consumer_port_index],
                    ]),
                )
                input_var_by_name: Dict[str, Var] = dict()
                input_var: Var
                for input_var in consumer_block.in_vars:
                    if input_var.name in input_var_by_name:
                        pass
                    else:
                        input_var_by_name[input_var.name] = input_var

                component_name: str
                for component_name in consumer_components:
                    target_var: Var | None = input_var_by_name.get(
                        component_name,
                        None,
                    )
                    if target_var is None:
                        pass
                    else:
                        exact_targets[component_name] = list([target_var])
            else:
                pass
    return exact_targets


def _build_meter_targets(
        host_model: Block,
        dgs_circuit: DgsCircuit,
        source_slot_id: str,
        child_block_by_slot_id: Dict[str, Block],
) -> Dict[str, List[Var]]:
    """
    Build exact native-meter targets from the source signal graph.

    :param host_model: Activated imported controller model.
    :param dgs_circuit: Parsed DGS signal graph.
    :param source_slot_id: Native meter producer-slot FID.
    :param child_block_by_slot_id: Transient exact slot-to-canonical-block map.
    :return: Signal-to-runtime-variable lookup.
    """
    targets: Dict[str, List[Var]] = _build_exact_meter_targets(
        dgs_circuit=dgs_circuit,
        source_slot_id=source_slot_id,
        child_block_by_slot_id=child_block_by_slot_id,
    )
    equipment_owned_names: Set[str] = _get_equipment_owned_signal_names(
        host_model=host_model,
    )
    for signal_name in equipment_owned_names:
        if signal_name in targets:
            targets.pop(signal_name, None)
        else:
            pass
    return targets


def bind_dgs_rms_measurements(
        circuit: MultiCircuit,
        dgs_circuit: DgsCircuit,
        templates_by_root_dgs_id: Dict[
            str,
            RmsModelTemplate | EmtModelTemplate,
        ],
        child_blocks_by_root_and_slot_id: Dict[str, Dict[str, Block]],
        logger: Logger,
) -> DgsRmsMeasurementBindingReport:
    """
    Bind native PowerFactory measurements to activated VeraGrid RMS controls.

    Only exact FIDs participate. Roots without one unique active physical host,
    unresolved pointers and unsupported measurement channels remain visible in
    the association catalogue but are not guessed or constant-filled.

    :param circuit: Imported VeraGrid circuit with prepared electrical RMS shells.
    :param dgs_circuit: Parsed source DGS containing measurement topology.
    :param templates_by_root_dgs_id: Minimal stage-one association from each
        unique source root FID to its registered final template.
    :param child_blocks_by_root_and_slot_id: Transient exact slot lookups into
        the same canonical blocks owned by the registered templates.
    :param logger: Diagnostic sink for handled partial failures.
    :return: Structured native-meter binding report.
    """
    report: DgsRmsMeasurementBindingReport = DgsRmsMeasurementBindingReport()
    dgs_element_by_id: Dict[str, DGSElement] = _build_dgs_element_index(
        dgs_circuit=dgs_circuit,
    )
    device_by_id: Dict[str, DynamicDevice] = _build_dynamic_device_index(
        circuit=circuit,
    )
    bus_by_id: Dict[str, Bus] = _build_bus_index(circuit=circuit)
    root_count_by_id: Dict[str, int] = dict()
    first_root_by_id: Dict[str, ElmComp] = dict()
    root_element: ElmComp
    for root_element in dgs_circuit.elmcomps:
        root_id: str = str(root_element.ID).strip()
        if len(root_id) == 0:
            pass
        else:
            previous_count: int | None = root_count_by_id.get(root_id, None)
            if previous_count is None:
                root_count_by_id[root_id] = 1
                first_root_by_id[root_id] = root_element
            else:
                root_count_by_id[root_id] = previous_count + 1

    eligible_template_by_root_id: Dict[str, RmsModelTemplate] = dict()
    eligible_root_by_id: Dict[str, ElmComp] = dict()
    root_id: str
    for root_id, root_element in first_root_by_id.items():
        root_count: int | None = root_count_by_id.get(root_id, None)
        registered_template: RmsModelTemplate | EmtModelTemplate | None = (
            templates_by_root_dgs_id.get(root_id, None)
        )
        if root_count == 1 and isinstance(registered_template, RmsModelTemplate):
            eligible_root_by_id[root_id] = root_element
            eligible_template_by_root_id[root_id] = registered_template
        else:
            pass

    # Logical controllers have no single static host. Their exact prepared
    # ElmSind shells establish the physical ownership envelope instead.
    prepared_actuator_ids_by_root: Dict[str, Set[str]] = dict()
    physical_branch: object
    for physical_branch in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=False,
    ):
        if isinstance(physical_branch, (Line, SeriesReactance)):
            actuator_root_id: str | None = (
                physical_branch.rms_model.dynamic_model_contract.dgs_logical_actuator_root_id
            )
            if actuator_root_id is None:
                pass
            else:
                prepared_ids: Set[str] | None = (
                    prepared_actuator_ids_by_root.get(actuator_root_id, None)
                )
                if prepared_ids is None:
                    prepared_ids = set()
                    prepared_actuator_ids_by_root[actuator_root_id] = prepared_ids
                else:
                    pass
                prepared_ids.add(str(physical_branch.idtag))
        else:
            pass

    for root_id, root_element in eligible_root_by_id.items():
        raw_entries: List[ElmCompInstanceEntry] = extract_elmcomp_direct_instances(
            circuit=dgs_circuit,
            root_element=root_element,
        )
        entries: List[ElmCompInstanceEntry] = get_unique_elmcomp_slot_entries(
            entries=raw_entries,
        )
        unambiguous_entries: List[ElmCompInstanceEntry] = (
            get_unambiguous_elmcomp_direct_instances(entries=raw_entries)
        )
        host_devices: List[DynamicDevice] = list()
        entry: ElmCompInstanceEntry
        implicit_meter_target_by_slot: Dict[str, str] = (
            _build_implicit_meter_target_by_slot(
                dgs_circuit=dgs_circuit,
                root_element=root_element,
                entries=entries,
            )
        )

        # A composite is executable on one physical object only when its exact
        # pElm relations resolve to one already activated runtime host.
        for entry in unambiguous_entries:
            is_supported_host_class: bool = entry.element_kind in (
                "ElmVsc",
                "ElmVscmono",
                "ElmSvs",
                "ElmSym",
                "ElmGenstat",
                "ElmLne",
                "ElmTr2",
                "ElmXnet",
            )
            if entry.element_id is None or not is_supported_host_class:
                pass
            else:
                candidate_host: DynamicDevice | None = device_by_id.get(
                    entry.element_id,
                    None,
                )
                expected_template: RmsModelTemplate = (
                    eligible_template_by_root_id[root_id]
                )
                if (
                        candidate_host is None
                        or candidate_host.rms_template is not expected_template
                ):
                    pass
                else:
                    if candidate_host in host_devices:
                        pass
                    else:
                        host_devices.append(candidate_host)

        logical_actuator_source_ids: Set[str] = set()
        for entry in unambiguous_entries:
            if entry.element_kind == "ElmSind" and entry.element_id is not None:
                logical_actuator_source_ids.add(entry.element_id)
            else:
                pass
        prepared_actuator_source_ids: Set[str] | None = (
            prepared_actuator_ids_by_root.get(root_id, None)
        )
        logical_actuator_is_complete: bool = (
            len(logical_actuator_source_ids) > 0
            and prepared_actuator_source_ids == logical_actuator_source_ids
        )

        host_device: DynamicDevice | None
        host_model: Block | None
        if len(host_devices) == 1:
            host_device = host_devices[0]
            host_model = host_device.rms_model
        else:
            if len(host_devices) == 0 and logical_actuator_is_complete:
                host_device = None
                host_model = eligible_template_by_root_id[root_id].block
            else:
                host_device = None
                host_model = None

        if host_model is not None:
            template_child_block_by_slot_id: Dict[str, Block] = (
                child_blocks_by_root_and_slot_id.get(root_id, dict())
            )
            child_block_by_slot_id: Dict[str, Block] = (
                _translate_slot_blocks_to_runtime(
                    template_root=eligible_template_by_root_id[root_id].block,
                    runtime_root=host_model,
                    template_block_by_slot_id=template_child_block_by_slot_id,
                )
            )
            for entry in entries:
                if entry.slot_id is None:
                    pass
                else:
                    is_pll_slot: bool = (
                        entry.slot_filter is not None
                        and (
                            "ElmPhi" in entry.slot_filter
                            or "ElmPll" in entry.slot_filter
                        )
                    )
                    meter_element: DGSElement | None
                    if entry.element_id is None:
                        if is_pll_slot:
                            # Enriched definitions export the built-in object as
                            # a child row even when the composite pElm remains
                            # empty. Resolve that exact ownership first.
                            meter_element = _resolve_native_pll_element(
                                root_element=root_element,
                                dgs_circuit=dgs_circuit,
                            )
                        else:
                            meter_element = None
                    else:
                        meter_element = dgs_element_by_id.get(
                            entry.element_id,
                            None,
                        )
                    incoming_names: List[str]
                    outgoing_names: List[str]
                    incoming_names, outgoing_names = get_blkslot_signal_interface(
                        circuit=dgs_circuit,
                        slot_id=entry.slot_id,
                    )
                    signal_names: List[str] = _split_slot_signal_labels(
                        signal_labels=outgoing_names,
                    )
                    if isinstance(
                            meter_element,
                            (StaVmea, StaImea, StaPqmea, ElmPhi),
                    ):
                        target_signal_names: List[str] = (
                            _get_native_source_target_signal_names(
                                dgs_circuit=dgs_circuit,
                                source_slot_id=entry.slot_id,
                            )
                        )
                        if len(target_signal_names) > 0:
                            signal_names = target_signal_names
                        else:
                            implicit_target_name: str | None = (
                                implicit_meter_target_by_slot.get(
                                    entry.slot_id,
                                    None,
                                )
                            )
                            if implicit_target_name is None:
                                pass
                            else:
                                signal_names = list([implicit_target_name])
                    else:
                        pass
                    alias_expressions: Dict[str, Expr] = dict()
                    prepared_meter_block: Block | None = None
                    meter_target_fid: str | None = None
                    meter_terminal_side: RmsTerminalSide | None = None
                    physical_meter_kind: RmsPhysicalMeterKind | None = None

                    if isinstance(meter_element, StaVmea):
                        terminal_id: str | None = _resolve_terminal_id(
                            pointer_id=meter_element.pbusbar,
                            dgs_element_by_id=dgs_element_by_id,
                        )
                        measured_bus: Bus | None
                        if terminal_id is None:
                            measured_bus = None
                        else:
                            measured_bus = bus_by_id.get(terminal_id, None)
                        if measured_bus is None:
                            pass
                        else:
                            meter_target_fid = str(measured_bus.idtag)
                            meter_terminal_side = RmsTerminalSide.BUS
                            physical_meter_kind = RmsPhysicalMeterKind.VOLTAGE
                            alias_expressions = _build_voltage_alias_expressions(
                                meter=meter_element,
                                signal_names=signal_names,
                                measured_bus=measured_bus,
                            )
                    else:
                        if isinstance(meter_element, StaImea):
                            source_device: DynamicDevice | None
                            source_bus: Bus | None
                            source_terminal_index: int | None
                            source_device, source_bus, source_terminal_index = (
                                _resolve_cubicle_source(
                                    cubicle_id=meter_element.pcubic,
                                    dgs_element_by_id=dgs_element_by_id,
                                    device_by_id=device_by_id,
                                    bus_by_id=bus_by_id,
                                )
                            )
                            if source_device is None and source_bus is not None:
                                logical_source_device: DynamicDevice | None
                                logical_source_terminal_index: int | None
                                (
                                    logical_source_device,
                                    logical_source_terminal_index,
                                ) = _resolve_logical_actuator_current_source(
                                    circuit=circuit,
                                    root_dgs_id=str(root_element.ID),
                                    measured_bus=source_bus,
                                )
                                if (
                                    logical_source_device is not None
                                    and logical_source_terminal_index is not None
                                ):
                                    source_device = logical_source_device
                                    source_terminal_index = logical_source_terminal_index
                                else:
                                    pass
                            else:
                                pass
                            if (
                                    source_device is None
                                    or source_bus is None
                                    or source_terminal_index is None
                            ):
                                pass
                            else:
                                meter_terminal_side = (
                                    _get_physical_meter_terminal_side(
                                        source_device=source_device,
                                        source_terminal_index=source_terminal_index,
                                    )
                                )
                                if meter_terminal_side is None:
                                    pass
                                else:
                                    meter_target_fid = str(source_device.idtag)
                                    physical_meter_kind = RmsPhysicalMeterKind.CURRENT
                                    alias_expressions = _build_current_alias_expressions(
                                        meter=meter_element,
                                        signal_names=signal_names,
                                        measured_bus=source_bus,
                                        source_device=source_device,
                                        source_terminal_index=source_terminal_index,
                                        system_base_mva=float(circuit.Sbase),
                                        host_model=host_model,
                                    )
                        else:
                            if isinstance(meter_element, StaPqmea):
                                power_device: DynamicDevice | None
                                power_bus: Bus | None
                                power_terminal_index: int | None
                                power_device, power_bus, power_terminal_index = (
                                    _resolve_cubicle_source(
                                        cubicle_id=meter_element.pcubic,
                                        dgs_element_by_id=dgs_element_by_id,
                                        device_by_id=device_by_id,
                                        bus_by_id=bus_by_id,
                                    )
                                )
                                if power_device is None or power_terminal_index is None:
                                    pass
                                else:
                                    meter_terminal_side = (
                                        _get_physical_meter_terminal_side(
                                            source_device=power_device,
                                            source_terminal_index=power_terminal_index,
                                        )
                                    )
                                    if meter_terminal_side is None:
                                        pass
                                    else:
                                        _refer_vsc_pq_controls_through_measured_transformer(
                                            circuit=circuit,
                                            host_device=host_device,
                                            source_device=power_device,
                                            source_terminal_index=power_terminal_index,
                                        )
                                        meter_target_fid = str(power_device.idtag)
                                        physical_meter_kind = RmsPhysicalMeterKind.POWER
                                        alias_expressions = _build_power_alias_expressions(
                                            meter=meter_element,
                                            signal_names=signal_names,
                                            source_device=power_device,
                                            source_terminal_index=power_terminal_index,
                                            system_base_mva=float(circuit.Sbase),
                                            circuit=circuit,
                                            host_device=host_device,
                                        )
                            else:
                                if is_pll_slot:
                                    pll_source_meter: StaVmea | None
                                    pll_source_bus: Bus | None
                                    native_pll_terminal_id: str | None = None
                                    if (
                                        isinstance(meter_element, ElmPhi)
                                        and meter_element.pbusbar is not None
                                        and str(meter_element.pbusbar).strip() != ""
                                    ):
                                        native_pll_terminal_id = _resolve_terminal_id(
                                            pointer_id=meter_element.pbusbar,
                                            dgs_element_by_id=dgs_element_by_id,
                                        )
                                    else:
                                        pass
                                    if native_pll_terminal_id is None:
                                        pll_source_meter, pll_source_bus = (
                                            _resolve_virtual_pll_voltage_source(
                                                pll_entry=entry,
                                                entries=entries,
                                                dgs_circuit=dgs_circuit,
                                                dgs_element_by_id=dgs_element_by_id,
                                                bus_by_id=bus_by_id,
                                            )
                                        )
                                    else:
                                        pll_source_meter = None
                                        pll_source_bus = bus_by_id.get(
                                            native_pll_terminal_id,
                                            None,
                                        )
                                    if pll_source_bus is None:
                                        # An empty native ElmPhi slot has no
                                        # graphical input. Its equipment
                                        # semantics measure the associated
                                        # converter AC terminal directly.
                                        if isinstance(host_device, VSC):
                                            if (
                                                host_device.bus_to is not None
                                                and not host_device.bus_to.is_dc
                                            ):
                                                pll_source_bus = host_device.bus_to
                                            else:
                                                if (
                                                    host_device.bus_from is not None
                                                    and not host_device.bus_from.is_dc
                                                ):
                                                    pll_source_bus = host_device.bus_from
                                                else:
                                                    pass
                                        else:
                                            pass
                                    else:
                                        pass
                                    if pll_source_bus is None:
                                        pass
                                    else:
                                        meter_target_fid = str(pll_source_bus.idtag)
                                        meter_terminal_side = RmsTerminalSide.BUS
                                        physical_meter_kind = (
                                            RmsPhysicalMeterKind.PHASE_LOCKED_LOOP
                                        )
                                        # ElmPhi is a stateful equipment model,
                                        # irrespective of whether its measured
                                        # bus was declared on its own row or by
                                        # the upstream voltage-measurement graph.
                                        native_pll: ElmPhi | None
                                        if isinstance(meter_element, ElmPhi):
                                            native_pll = meter_element
                                        else:
                                            native_pll = None
                                        use_stationary_reference: bool
                                        if native_pll is None:
                                            # Legacy DGS omits the hidden
                                            # ElmPhi row. Pac is the exported
                                            # structural marker for the native
                                            # unconnected stationary dq frame.
                                            use_stationary_reference = (
                                                pll_source_meter is None
                                                and isinstance(host_device, VSC)
                                                and host_device.control1
                                                is ConverterControlType.Pac
                                            )
                                        else:
                                            use_stationary_reference = (
                                                native_pll.pbusbar is None
                                                or str(native_pll.pbusbar).strip() == ""
                                            )
                                        (
                                            alias_expressions,
                                            prepared_meter_block,
                                        ) = _build_pll_alias_expressions(
                                                circuit=circuit,
                                                signal_names=signal_names,
                                                measured_bus=pll_source_bus,
                                                meter=native_pll,
                                                meter_id=(
                                                    native_pll.ID
                                                    if native_pll is not None
                                                    else entry.slot_id
                                                ),
                                                use_stationary_reference=(
                                                    use_stationary_reference
                                                ),
                                        )
                                else:
                                    pass

                    if (
                        isinstance(
                            meter_element,
                            (StaVmea, StaImea, StaPqmea, ElmPhi),
                        )
                        or is_pll_slot
                    ):
                        meter_is_out_of_service: bool = (
                            isinstance(
                                meter_element,
                                (StaVmea, StaImea, StaPqmea, ElmPhi),
                            )
                            and meter_element.outserv != 0
                        )
                        if meter_is_out_of_service:
                            # A disabled meter contributes no solved physical
                            # equation. Preserve receiver inc0 values and create
                            # held zero parameters only where no fallback exists.
                            host_targets_by_name: Dict[str, List[Var]] = (
                                _build_meter_targets(
                                    host_model=host_model,
                                    dgs_circuit=dgs_circuit,
                                    source_slot_id=entry.slot_id,
                                    child_block_by_slot_id=child_block_by_slot_id,
                                )
                            )
                            connected_count: int = _retain_disabled_meter_targets(
                                host_model=host_model,
                                targets_by_name=host_targets_by_name,
                                signal_names=signal_names,
                            )
                            report.record_skipped_meter()
                            if connected_count > 0:
                                pass
                            else:
                                report.record_failed_meter()
                                logger.add_warning(
                                    msg="DGS disabled RMS meter has no matching control signal",
                                    device=entry.element_name,
                                    value=signal_names,
                                )
                        else:
                            # Live meters become solved physical equations and
                            # supersede any receiver-side fallback.
                            if (
                                    len(alias_expressions) == 0
                                    or meter_target_fid is None
                                    or meter_terminal_side is None
                                    or physical_meter_kind is None
                            ):
                                report.record_failed_meter()
                                logger.add_warning(
                                    msg="DGS native RMS meter could not be resolved",
                                    device=entry.element_name,
                                    value=entry.element_id,
                                )
                            else:
                                host_targets_by_name = _build_meter_targets(
                                    host_model=host_model,
                                    dgs_circuit=dgs_circuit,
                                    source_slot_id=entry.slot_id,
                                    child_block_by_slot_id=child_block_by_slot_id,
                                )
                                if (
                                        isinstance(
                                            meter_element,
                                            (StaVmea, StaImea, StaPqmea, ElmPhi),
                                        )
                                        and str(meter_element.ID).strip() != ""
                                ):
                                    meter_source_id: str = str(meter_element.ID)
                                else:
                                    if entry.element_id is not None:
                                        meter_source_id = entry.element_id
                                    else:
                                        meter_source_id = entry.slot_id
                                connected_count = _connect_meter_aliases(
                                    host_model=host_model,
                                    targets_by_name=host_targets_by_name,
                                    alias_expressions=alias_expressions,
                                    meter_name=_get_veragrid_meter_name(
                                        meter_kind=physical_meter_kind,
                                        source_fid=meter_source_id,
                                    ),
                                    meter_source_fid=meter_source_id,
                                    meter_target_fid=meter_target_fid,
                                    meter_terminal_side=meter_terminal_side,
                                    meter_kind=physical_meter_kind,
                                    var_factory=circuit.var_factory,
                                    prepared_meter_block=prepared_meter_block,
                                )
                                if connected_count > 0:
                                    report.record_bound_meter(
                                        signal_count=connected_count,
                                    )
                                else:
                                    report.record_failed_meter()
                                    logger.add_warning(
                                        msg="DGS native RMS meter has no matching control signal",
                                        device=entry.element_name,
                                        value=signal_names,
                                    )
                    else:
                        pass
        else:
            for entry in entries:
                if entry.element_kind in (
                        "StaVmea",
                        "StaImea",
                        "StaPqmea",
                        "ElmPhi",
                ):
                    unresolved_meter: DGSElement | None = (
                        dgs_element_by_id.get(entry.element_id, None)
                        if entry.element_id is not None
                        else None
                    )
                    unresolved_meter_is_out_of_service: bool = (
                        isinstance(
                            unresolved_meter,
                            (StaVmea, StaImea, StaPqmea, ElmPhi),
                        )
                        and unresolved_meter.outserv != 0
                    )
                    if (
                            int(root_element.outserv) != 0
                            or unresolved_meter_is_out_of_service
                    ):
                        report.record_skipped_meter()
                    else:
                        report.record_failed_meter()
                        logger.add_warning(
                            msg="DGS native RMS meter has no unique active host",
                            device=entry.element_name,
                            value=entry.element_id,
                            expected_value=root_id,
                        )
                else:
                    pass

    return report
