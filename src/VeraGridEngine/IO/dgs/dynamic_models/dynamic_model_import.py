# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import copy
import hashlib
import json
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Set, Tuple

from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagramConnection
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagramNode
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_rms_measurement_binding import (
    _build_dgs_element_index,
    _build_exact_meter_targets,
    _build_implicit_meter_target_by_slot,
    _get_native_source_target_signal_names,
    _get_veragrid_meter_name,
    _remove_meter_target_fallback_ownership,
    _resolve_native_pll_element,
)
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    DgsDirectRootBuildResult,
    DgsGraphicalIndexes,
    DgsGraphicTreeResult,
    DgsRootBlockResult,
    DgsSlotSignalDirection,
    DgsStandaloneBlockCatalogEntry,
    DgsStandaloneBlockOccurrence,
    ElmCompInstanceEntry,
    ParsedDgsBlockDefinition,
    UnsupportedDgsExpression,
    build_dgs_graphical_indexes,
    build_dgs_standalone_block_catalog_from_circuit,
    build_direct_root_elmcomp_block,
    build_standalone_blkdef_block,
    build_standalone_blkdef_block_from_parsed_block,
    build_dgs_root_block_from_circuit,
    extract_elmcomp_direct_instances,
    extract_root_slot_graphical_tree_from_circuit,
    get_blkslot_signal_interface,
    get_unique_elmcomp_slot_entries,
    list_dgs_blkref_catalog_occurrences_from_circuit,
    parse_dgs_block_definitions_from_circuit,
)
from VeraGridEngine.IO.dgs.dgs_objects import BlkSlot
from VeraGridEngine.IO.dgs.dgs_objects import DGSElement
from VeraGridEngine.IO.dgs.dgs_objects import ElmComp
from VeraGridEngine.IO.dgs.dgs_objects import ElmPhi
from VeraGridEngine.IO.dgs.dgs_objects import ElmSvs
from VeraGridEngine.IO.dgs.dgs_objects import StaImea
from VeraGridEngine.IO.dgs.dgs_objects import StaPqmea
from VeraGridEngine.IO.dgs.dgs_objects import StaVmea
from VeraGridEngine.IO.dynamic_model_import_types import (
    DgsDynamicModelActivationReport,
    DynamicModelImportBundle,
    DynamicModelImportEntry,
    DynamicModelImportEntryAvailability,
    DynamicModelImportEntryResult,
    DynamicModelImportEntryStatus,
    DynamicModelImportReport,
    DynamicModelImportSelectionRequest,
    DynamicModelImportSource,
    DynamicModelImportSourceProvenance,
    DynamicModelLoadedUserTemplate,
    _emit_dynamic_model_import_progress,
)
from VeraGridEngine.IO.dgs.dynamic_models.dgs_dynamic_association import DgsDynamicAssociationRecord
from VeraGridEngine.IO.dgs.dynamic_models.dgs_dynamic_association import infer_dgs_dynamic_association_role
from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmvsc_runtime_adapter import (
    build_dgs_elmvscmono_rms_runtime_template,
    build_dgs_elmvsc_rms_runtime_template,
    configure_dgs_elmvscmono_runtime_template_for_device,
    configure_dgs_elmvsc_runtime_template_for_device,
    is_dgs_elmvscmono_slot_contract,
    is_dgs_elmvsc_slot_contract,
)
from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmsym_runtime_adapter import (
    build_dgs_elmsym_rms_runtime_template,
    configure_dgs_elmsym_runtime_template_for_device,
)
from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmgenstat_runtime_adapter import (
    build_dgs_elmgenstat_rms_runtime_template,
)
from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmsvs_runtime_adapter import (
    build_dgs_elmsvs_rms_runtime_template,
)
from VeraGridEngine.IO.file_system import get_create_veragrid_folder
from VeraGridEngine.IO.dynamic_model_import_utils import sanitize_dynamic_model_file_stem
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    RmsPhysicalMeterKind,
    find_connections,
)
from VeraGridEngine.Utils.Symbolic.rms_measurements_functions import (
    build_rms_pll_measurements,
    build_rms_pll_measurements_from,
    build_rms_pll_measurements_to,
    build_rms_voltage_meter_outputs_from_dc_from,
    build_rms_voltage_meter_outputs_from_dc_to,
    build_rms_voltage_meter_outputs_from_dc,
    build_rms_voltage_meter_outputs_from_polar_from,
    build_rms_voltage_meter_outputs_from_polar_to,
    build_rms_voltage_meter_outputs_from_polar,
    find_measurements_for_inputs_group,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicCodec
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (
    BlockType,
    ConverterControlType,
    DeviceType,
    DgsDynamicAssociationRole,
    DynamicSimulationMode,
    RmsTerminalSide,
    VarPowerFlowReferenceType,
)

class DgsDynamicParserContractError(RuntimeError):
    """Report that the dynamic DGS parser boundary is incomplete."""


class _DgsRuntimeAdapterKind(Enum):
    """Identify the typed runtime-adapter contract queried by the importer."""

    VSC_MONOPOLAR = auto()
    VSC_BIPOLAR = auto()
    SYNCHRONOUS_MACHINE_PENDING = auto()
    SYNCHRONOUS_MACHINE = auto()
    STATIC_GENERATOR = auto()
    STATIC_VAR_SYSTEM = auto()


class _DgsRmsMeasurementConnection:
    """Describe one exact native-meter connection to a controller input.

    :param alias_name: Native output alias routed by the DGS signal graph.
    :param target_var: Exact controller input receiving the measurement.
    """

    __slots__ = ("alias_name", "target_var")

    def __init__(self, alias_name: str, target_var: Var) -> None:
        """Store one resolved producer-to-consumer endpoint.

        :param alias_name: Native output alias routed by the DGS signal graph.
        :param target_var: Exact controller input receiving the measurement.
        :return: None.
        """
        self.alias_name: str = alias_name
        self.target_var: Var = target_var


class _DgsRmsMeasurementSpec:
    """Carry native DGS meter semantics into early block materialization.

    :param source_fid: Stable native meter identity.
    :param source_name: Human-readable native meter name.
    :param meter_kind: Physical measurement family.
    :param meter_element: Parsed native meter configuration, when exported.
    :param connections: Exact controller endpoints driven by the meter.
    :param use_stationary_reference: Whether an ElmPhi exports a fixed frame.
    """

    __slots__ = (
        "source_fid",
        "source_name",
        "meter_kind",
        "meter_element",
        "connections",
        "use_stationary_reference",
    )

    def __init__(
            self,
            source_fid: str,
            source_name: str,
            meter_kind: RmsPhysicalMeterKind,
            meter_element: DGSElement | None,
            connections: List[_DgsRmsMeasurementConnection],
            use_stationary_reference: bool,
    ) -> None:
        """Store immutable-shape native measurement construction data.

        :param source_fid: Stable native meter identity.
        :param source_name: Human-readable native meter name.
        :param meter_kind: Physical measurement family.
        :param meter_element: Parsed native meter configuration, when exported.
        :param connections: Exact controller endpoints driven by the meter.
        :param use_stationary_reference: Whether an ElmPhi exports a fixed frame.
        :return: None.
        """
        self.source_fid: str = source_fid
        self.source_name: str = source_name
        self.meter_kind: RmsPhysicalMeterKind = meter_kind
        self.meter_element: DGSElement | None = meter_element
        self.connections: List[_DgsRmsMeasurementConnection] = connections
        self.use_stationary_reference: bool = use_stationary_reference


class DgsDynamicTemplateConversionResult:
    """Own the minimal transient state required after template conversion.

    The final templates are already owned by ``MultiCircuit``. Child-block
    lookups point into those same canonical block trees and exist only until
    exact device assignment and native measurement binding have completed.

    :param templates_by_root_dgs_id: Final templates indexed by root FID.
    :param child_blocks_by_root_and_slot_id: Canonical child blocks indexed by
        root FID and source slot FID for exact post-conversion binding.
    """

    __slots__ = (
        "templates_by_root_dgs_id",
        "child_blocks_by_root_and_slot_id",
    )

    def __init__(self) -> None:
        """Initialize empty fixed-purpose conversion lookups.

        :return: None.
        """
        self.templates_by_root_dgs_id: Dict[
            str,
            RmsModelTemplate | EmtModelTemplate,
        ] = dict()
        self.child_blocks_by_root_and_slot_id: Dict[
            str,
            Dict[str, Block],
        ] = dict()


class _DgsElmCompRelationKind(Enum):
    """Classify one direct DGS relation before any block is executed."""

    __slots__ = ()

    DYNAMIC_CANDIDATE = auto()
    PHYSICAL_REFERENCE = auto()
    OPAQUE_REFERENCE = auto()
    INVALID = auto()


class _DgsElmCompRelationClassification:
    """Carry one typed DGS relation decision and its evidence.

    :param kind: Exact non-executable or dynamic relation kind.
    :param reason: Human-readable evidence behind the decision.
    """

    __slots__ = ("_kind", "_reason")

    def __init__(
            self,
            kind: _DgsElmCompRelationKind,
            reason: str,
    ) -> None:
        """Store one relation decision.

        :param kind: Exact non-executable or dynamic relation kind.
        :param reason: Human-readable evidence behind the decision.
        :return: None.
        """
        self._kind: _DgsElmCompRelationKind = kind
        self._reason: str = reason

    def get_kind(self) -> _DgsElmCompRelationKind:
        """Return the typed relation kind.

        :return: Exact classification kind.
        """
        return self._kind

    def get_reason(self) -> str:
        """Return the evidence behind the relation decision.

        :return: Human-readable classification evidence.
        """
        return self._reason


def _classify_dgs_elmcomp_relation(
        entry: ElmCompInstanceEntry,
        unique_slot_indices: Set[int],
) -> _DgsElmCompRelationClassification:
    """Classify one direct ``ElmComp`` relation without using display names.

    A unique resolved ``pblk`` establishes the source slot envelope. A complete
    resolved dynamic target may then be materialized. Resolved physical targets
    and intentionally empty physical or vendor slots remain visible metadata,
    while missing, unresolved or repeated slot references and unresolved
    supplied targets fail closed.

    :param entry: Exact direct relation extracted from the DGS document.
    :param unique_slot_indices: Ordinals whose ``pblk`` resolves uniquely.
    :return: Typed pre-execution relation classification.
    """
    physical_roles: Set[DgsDynamicAssociationRole] = set([
        DgsDynamicAssociationRole.PhysicalHost,
        DgsDynamicAssociationRole.Measurement,
        DgsDynamicAssociationRole.SwitchActuator,
        DgsDynamicAssociationRole.ValveActuator,
        DgsDynamicAssociationRole.PassiveActuator,
    ])

    if entry.slot_index is None or entry.slot_index not in unique_slot_indices:
        if entry.slot_id is None:
            invalid_reason: str = "missing pblk slot reference"
        else:
            if not entry.slot_reference_is_resolved:
                invalid_reason = "unresolved pblk slot reference"
            else:
                invalid_reason = "repeated pblk slot reference"
        return _DgsElmCompRelationClassification(
            kind=_DgsElmCompRelationKind.INVALID,
            reason=invalid_reason,
        )
    else:
        pass

    association_role: DgsDynamicAssociationRole = (
        infer_dgs_dynamic_association_role(
            slot_index=entry.slot_index,
            source_element_class=entry.element_kind,
            slot_filter=entry.slot_filter,
        )
    )

    if entry.element_id is None:
        if association_role in physical_roles:
            empty_kind: _DgsElmCompRelationKind = (
                _DgsElmCompRelationKind.PHYSICAL_REFERENCE
            )
            empty_reason: str = "physical slot has no exported pElm target"
        else:
            empty_kind = _DgsElmCompRelationKind.OPAQUE_REFERENCE
            empty_reason = "slot has no exported pElm target"
        return _DgsElmCompRelationClassification(
            kind=empty_kind,
            reason=empty_reason,
        )
    else:
        pass

    if not entry.element_reference_is_resolved:
        return _DgsElmCompRelationClassification(
            kind=_DgsElmCompRelationKind.INVALID,
            reason="unresolved supplied pElm target",
        )
    else:
        pass

    if entry.element_kind == "ElmDsl" or entry.element_kind == "ElmComp":
        if entry.type_id is None:
            return _DgsElmCompRelationClassification(
                kind=_DgsElmCompRelationKind.INVALID,
                reason="dynamic pElm target has no exported type reference",
            )
        else:
            return _DgsElmCompRelationClassification(
                kind=_DgsElmCompRelationKind.DYNAMIC_CANDIDATE,
                reason="complete dynamic pblk/pelm relation",
            )
    else:
        pass

    if entry.type_id is None:
        if association_role in physical_roles:
            resolved_kind: _DgsElmCompRelationKind = (
                _DgsElmCompRelationKind.PHYSICAL_REFERENCE
            )
            resolved_reason: str = "resolved physical pElm target"
        else:
            resolved_kind = _DgsElmCompRelationKind.OPAQUE_REFERENCE
            resolved_reason = "resolved non-dynamic pElm target"
        return _DgsElmCompRelationClassification(
            kind=resolved_kind,
            reason=resolved_reason,
        )
    else:
        return _DgsElmCompRelationClassification(
            kind=_DgsElmCompRelationKind.INVALID,
            reason="non-dynamic pElm target declares a dynamic type reference",
        )


def _select_root_frame_display_name(root_block: Block) -> str | None:
    """
    Select the composite frame name used to group one imported PWM root.

    :param root_block: Parsed imported root block.
    :return: Preferred frame display name, or ``None``.
    """
    candidate_names: List[str] = list()
    child_block: Block
    child_name: str

    for child_block in root_block.children:
        child_name = str(child_block.name)

        if child_name == "VSC_Frame":
            return child_name
        else:
            if child_name.startswith("VSC_Frame"):
                candidate_names.append(child_name)
            else:
                pass

    if len(candidate_names) == 0:
        return None
    else:
        candidate_names.sort(key=len)
        return candidate_names[0]


def _build_dgs_non_executable_slot_notes(
        circuit: DgsCircuit,
        root_name: str,
        entry: ElmCompInstanceEntry,
) -> str:
    """
    Build notes for a DGS slot that has no materialized block.

    :param circuit: Parsed DGS circuit.
    :param root_name: Root ElmComp display name.
    :param entry: Direct slot entry.
    :return: Human-readable notes text.
    """
    incoming_signals, outgoing_signals = get_blkslot_signal_interface(
        circuit=circuit,
        slot_id=entry.slot_id,
    )
    notes_parts: List[str] = [f"Root: {root_name}", "Non-executable slot"]
    slot_obj: BlkSlot | None = None
    candidate_slot: BlkSlot

    if entry.slot_id is None:
        pass
    else:
        # The raw BlkSlot carries the physical interface metadata even when no ElmDsl/BlkDef exists behind it.
        for candidate_slot in circuit.blkslots:
            if str(candidate_slot.ID) == str(entry.slot_id):
                slot_obj = candidate_slot
                break
            else:
                pass

    if slot_obj is None:
        pass
    else:
        # The filter and slot IO names make the imported topology readable for valves, switches and measurements.
        if str(slot_obj.filtmod).strip() != "":
            notes_parts.append(f"filter: {slot_obj.filtmod}")
        else:
            pass

        if len(slot_obj.outputs) > 0:
            notes_parts.append(f"slot outputs: {', '.join(slot_obj.outputs)}")
        else:
            pass

        if len(slot_obj.inputs) > 0:
            notes_parts.append(f"slot inputs: {', '.join(slot_obj.inputs)}")
        else:
            pass

    if len(outgoing_signals) > 0:
        notes_parts.append(f"outputs: {', '.join(outgoing_signals)}")
    else:
        pass

    if len(incoming_signals) > 0:
        notes_parts.append(f"inputs: {', '.join(incoming_signals)}")
    else:
        pass

    return " | ".join(notes_parts)


def _build_dgs_import_source_provenance(
        root_element: ElmComp,
        direct_entry: ElmCompInstanceEntry | None = None,
) -> DynamicModelImportSourceProvenance:
    """
    Build typed provenance for one root or direct ElmComp slot entry.

    :param root_element: Owning root ElmComp.
    :param direct_entry: Optional direct pBlk/pElm slot relation.
    :return: Typed root/slot/element source provenance.
    """
    if direct_entry is None:
        slot_dgs_id: str | None = None
        slot_name: str | None = None
        slot_index: int | None = None
        slot_element: str | None = None
        slot_filter: str | None = None
        source_element_dgs_id: str | None = None
        source_element_name: str | None = None
        source_element_class: str | None = None
    else:
        slot_dgs_id = direct_entry.slot_id
        slot_name = direct_entry.slot_name
        slot_index = direct_entry.slot_index
        slot_element = direct_entry.slot_element
        slot_filter = direct_entry.slot_filter
        source_element_dgs_id = direct_entry.element_id
        source_element_name = direct_entry.element_name
        source_element_class = direct_entry.element_kind

    source_provenance: DynamicModelImportSourceProvenance = (
        DynamicModelImportSourceProvenance(
            root_dgs_id=root_element.ID,
            root_name=root_element.loc_name,
            root_typ_id=root_element.typ_id,
            slot_dgs_id=slot_dgs_id,
            slot_name=slot_name,
            slot_index=slot_index,
            slot_element=slot_element,
            slot_filter=slot_filter,
            source_element_dgs_id=source_element_dgs_id,
            source_element_name=source_element_name,
            source_element_class=source_element_class,
        )
    )
    return source_provenance


def _build_dgs_root_elmcomp_entries_with_progress(
        dgs_path: str,
        progress_callback: Callable[[int, str], None] | None,
        progress_start: int,
        progress_end: int,
        dgs_circuit: DgsCircuit | None = None,
        parsed_dgs_blocks: Dict[str, ParsedDgsBlockDefinition] | None = None,
) -> Tuple[List[DynamicModelImportEntry], Logger]:
    """
    Build root ``ElmComp`` import entries while emitting progress updates.

    :param dgs_path: Source DGS path.
    :param progress_callback: Optional UI progress callback.
    :param progress_start: Inclusive start percentage for this phase.
    :param progress_end: Inclusive end percentage for this phase.
    :param dgs_circuit: Optional circuit already parsed for the massive import.
    :param parsed_dgs_blocks: Optional definitions parsed from ``dgs_circuit``.
    :return: Pair ``(entries, logger)``.
    """
    circuit: DgsCircuit
    entries: List[DynamicModelImportEntry] = list()
    logger: Logger = Logger()
    root_element: ElmComp
    root_result: DgsRootBlockResult | None
    root_block: Block | None
    root_entry: DynamicModelImportEntry
    root_direct_entries: List[ElmCompInstanceEntry]
    unique_slot_entries: List[ElmCompInstanceEntry]
    unique_slot_entry: ElmCompInstanceEntry
    unique_slot_indices: Set[int]
    direct_entry: ElmCompInstanceEntry
    relation_classification: _DgsElmCompRelationClassification
    relation_kind: _DgsElmCompRelationKind
    frame_display_name: str | None
    frame_entry_key: str | None
    slot_display_name: str
    non_executable_notes_text: str
    slot_notes_text: str
    slot_parent_key: str
    slot_identity: str
    slot_availability: DynamicModelImportEntryAvailability
    graph_tree: DgsGraphicTreeResult | None
    cached_slot_block: Block | None
    materialized_slot_block: Block | None
    parsed_slot_block: ParsedDgsBlockDefinition | None
    effective_type_id: str | None
    total_root_count: int
    total_slot_count: int = 0
    total_steps: int
    completed_steps: int = 0
    processed_root_count: int = 0
    processed_slot_count: int = 0
    progress_span: int = progress_end - progress_start
    current_progress_value: int
    root_source_provenance: DynamicModelImportSourceProvenance
    slot_source_provenance: DynamicModelImportSourceProvenance
    direct_child_block_by_slot_id: Dict[str, Block]
    direct_graphical_tree_by_slot_id: Dict[
        str,
        DgsGraphicTreeResult,
    ]
    reported_unresolved_graphical_contracts: Set[Tuple[str, ...]] = set()

    if dgs_circuit is None:
        circuit = DgsCircuit()
        circuit.parse_dgs(dgs_path)
    else:
        circuit = dgs_circuit
    total_root_count = len(circuit.elmcomps)

    for root_element in circuit.elmcomps:
        total_slot_count += len(extract_elmcomp_direct_instances(circuit, root_element))

    total_steps = total_root_count + total_slot_count
    if total_steps <= 0:
        _emit_dynamic_model_import_progress(progress_callback, progress_end, "DGS root catalogue ready")
        return entries, logger
    else:
        pass

    # Parsing BlkDef expressions is independent of the concrete ElmDsl
    # parameters. Share those parsed definitions across every root in a massive DGS
    # import, while each root below still materializes its own instances.
    shared_parsed_dgs_blocks: Dict[str, ParsedDgsBlockDefinition]
    if parsed_dgs_blocks is None:
        shared_parsed_dgs_blocks = parse_dgs_block_definitions_from_circuit(
            circuit=circuit
        )
    else:
        shared_parsed_dgs_blocks = parsed_dgs_blocks
    graphical_indexes: DgsGraphicalIndexes = (
        build_dgs_graphical_indexes(circuit=circuit)
    )

    for root_element in circuit.elmcomps:
        root_direct_entries = list(extract_elmcomp_direct_instances(circuit, root_element))
        unique_slot_entries = get_unique_elmcomp_slot_entries(
            entries=root_direct_entries,
        )
        unique_slot_indices = set()
        for unique_slot_entry in unique_slot_entries:
            if unique_slot_entry.slot_index is None:
                pass
            else:
                unique_slot_indices.add(unique_slot_entry.slot_index)
        root_entry_key: str = f"dgs-root|{root_element.ID}"
        root_source_provenance = _build_dgs_import_source_provenance(
            root_element=root_element
        )
        try:
            root_result = build_dgs_root_block_from_circuit(
                circuit=circuit,
                parsed_blocks=shared_parsed_dgs_blocks,
                root_name=root_element.loc_name,
                root_typ_id=root_element.typ_id,
                root_dgs_id=root_element.ID,
            )
        except Exception as exc:
            logger.add_warning(
                msg="DGS root ElmComp import skipped",
                value=f"{root_element.loc_name}: {exc}",
            )
            root_result = None
        else:
            pass

        processed_root_count += 1
        completed_steps += 1
        current_progress_value = progress_start + int(round(progress_span * float(completed_steps) / float(total_steps)))
        _emit_dynamic_model_import_progress(
            progress_callback,
            current_progress_value,
            f"Importing DGS roots: {processed_root_count}/{total_root_count}",
        )

        if root_result is None:
            # A failed root remains a catalogue node so the report does not
            # hide the source object or any of its exact pblk/pelm relations.
            entries.append(
                DynamicModelImportEntry(
                    unique_key=root_entry_key,
                    display_name=root_element.loc_name,
                    source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                    source_block=None,
                    notes_text="Root ElmComp could not be materialized",
                    source_provenance=root_source_provenance,
                )
            )

            for direct_entry in root_direct_entries:
                if direct_entry.slot_id is None:
                    slot_identity = f"index-{direct_entry.slot_index}"
                else:
                    slot_identity = str(direct_entry.slot_id)

                if direct_entry.slot_name is None:
                    slot_display_name = f"Slot {direct_entry.slot_index}"
                else:
                    slot_display_name = str(direct_entry.slot_name)

                slot_source_provenance = _build_dgs_import_source_provenance(
                    root_element=root_element,
                    direct_entry=direct_entry,
                )
                entries.append(
                    DynamicModelImportEntry(
                        unique_key=f"dgs-unavailable|{root_element.ID}|{slot_identity}|{direct_entry.element_id}",
                        display_name=slot_display_name,
                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                        source_block=None,
                        notes_text=(
                            f"Root: {root_element.loc_name} | "
                            "Slot unavailable because its root could not be materialized"
                        ),
                        parent_key=root_entry_key,
                        source_provenance=slot_source_provenance,
                    )
                )
                processed_slot_count += 1
                completed_steps += 1
                current_progress_value = progress_start + int(
                    round(progress_span * float(completed_steps) / float(total_steps))
                )
                _emit_dynamic_model_import_progress(
                    progress_callback,
                    current_progress_value,
                    f"Importing DGS slots: {processed_slot_count}/{total_slot_count}",
                )
        else:
            try:
                direct_root_build_result: DgsDirectRootBuildResult = (
                    build_direct_root_elmcomp_block(
                        circuit=circuit,
                        result=root_result,
                        graphical_indexes=graphical_indexes,
                    )
                )
                direct_root_block: Block = direct_root_build_result.root_block
                direct_child_block_by_slot_id = (
                    direct_root_build_result.child_block_by_slot_id
                )
                direct_graphical_tree_by_slot_id = (
                    direct_root_build_result.graphical_tree_by_slot_id
                )
                root_block = direct_root_block
                root_block.name = root_element.loc_name
            except Exception as exc:
                logger.add_warning(
                    msg="DGS root ElmComp materialization skipped",
                    value=f"{root_element.loc_name}: {exc}",
                )
                root_block = None
                direct_child_block_by_slot_id = dict()
                direct_graphical_tree_by_slot_id = dict()
                # Keep the independently parsed pblk/pelm relations so every
                # failed slot remains visible in the partial-import report.
                root_direct_entries = list(root_direct_entries)

            if root_block is None:
                frame_display_name = None
            else:
                frame_display_name = _select_root_frame_display_name(root_result.root_block)
            frame_entry_key = None

            if root_block is None:
                entries.append(
                    DynamicModelImportEntry(
                        unique_key=root_entry_key,
                        display_name=root_element.loc_name,
                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                        source_block=None,
                        notes_text="Root ElmComp block could not be materialized",
                        source_provenance=root_source_provenance,
                    )
                )
            else:
                root_entry = DynamicModelImportEntry(
                    unique_key=root_entry_key,
                    display_name=root_element.loc_name,
                    source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                    source_block=root_block,
                    notes_text="Root ElmComp block",
                    source_provenance=root_source_provenance,
                )
                entries.append(root_entry)

            if frame_display_name is None:
                pass
            else:
                frame_entry_key = f"dgs-frame|{root_element.ID}|{root_element.typ_id}"
                entries.append(
                    DynamicModelImportEntry(
                        unique_key=frame_entry_key,
                        display_name=frame_display_name,
                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                        source_block=None,
                        notes_text=f"Root: {root_element.loc_name} | Composite frame",
                        parent_key=root_entry_key,
                        source_provenance=root_source_provenance,
                        availability=DynamicModelImportEntryAvailability.MetadataOnly,
                    )
                )

            for direct_entry in root_direct_entries:
                relation_classification = _classify_dgs_elmcomp_relation(
                    entry=direct_entry,
                    unique_slot_indices=unique_slot_indices,
                )
                relation_kind = relation_classification.get_kind()
                slot_parent_key = (
                    root_entry_key
                    if frame_entry_key is None
                    else frame_entry_key
                )
                if direct_entry.slot_name is None:
                    slot_display_name = f"Slot {direct_entry.slot_index}"
                else:
                    slot_display_name = str(direct_entry.slot_name)
                if direct_entry.slot_id is None:
                    slot_identity = f"index-{direct_entry.slot_index}"
                else:
                    slot_identity = str(direct_entry.slot_id)
                slot_source_provenance = _build_dgs_import_source_provenance(
                    root_element=root_element,
                    direct_entry=direct_entry,
                )

                if relation_kind != _DgsElmCompRelationKind.DYNAMIC_CANDIDATE:
                    if relation_kind == _DgsElmCompRelationKind.INVALID:
                        slot_availability = (
                            DynamicModelImportEntryAvailability.Failed
                        )
                        slot_notes_text = (
                            f"Root: {root_element.loc_name} | Invalid relation: "
                            f"{relation_classification.get_reason()}"
                        )
                    else:
                        slot_availability = (
                            DynamicModelImportEntryAvailability.MetadataOnly
                        )
                        non_executable_notes_text = (
                            _build_dgs_non_executable_slot_notes(
                                circuit=circuit,
                                root_name=root_element.loc_name,
                                entry=direct_entry,
                            )
                        )
                        slot_notes_text = (
                            f"{non_executable_notes_text}"
                            f" | Relation: {relation_classification.get_reason()}"
                        )
                    entries.append(
                        DynamicModelImportEntry(
                            unique_key=f"dgs-metadata|{root_element.ID}|{slot_identity}|{direct_entry.element_id}",
                            display_name=slot_display_name,
                            source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                            source_block=None,
                            notes_text=slot_notes_text,
                            parent_key=slot_parent_key,
                            source_provenance=slot_source_provenance,
                            availability=slot_availability,
                        )
                    )
                    processed_slot_count += 1
                    completed_steps += 1
                    current_progress_value = progress_start + int(
                        round(progress_span * float(completed_steps) / float(total_steps))
                    )
                    _emit_dynamic_model_import_progress(
                        progress_callback,
                        current_progress_value,
                        f"Importing DGS slots: {processed_slot_count}/{total_slot_count}",
                    )
                else:
                    slot_template_name: str = (
                        f"{root_element.loc_name}::{slot_display_name}"
                    )
                    slot_block: Block | None
                    effective_type_id = direct_entry.type_id

                    if effective_type_id is None:
                        slot_availability = (
                            DynamicModelImportEntryAvailability.Failed
                        )
                        slot_notes_text = (
                            f"Root: {root_element.loc_name} | "
                            "Dynamic relation has no executable type reference"
                        )
                        entries.append(
                            DynamicModelImportEntry(
                                unique_key=(
                                    f"dgs-unavailable|{root_element.ID}|"
                                    f"{slot_identity}|{direct_entry.element_id}"
                                ),
                                display_name=slot_display_name,
                                source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                source_block=None,
                                notes_text=slot_notes_text,
                                parent_key=slot_parent_key,
                                source_provenance=slot_source_provenance,
                                availability=slot_availability,
                            )
                        )
                    else:
                        # Reuse the exact child materialized while building the
                        # composite root. This avoids parsing the same graphical
                        # controller twice during a massive DGS import.
                        if direct_entry.slot_id is None:
                            cached_slot_block = None
                            graph_tree = None
                        else:
                            slot_id: str = str(direct_entry.slot_id)
                            cached_slot_block = (
                                direct_child_block_by_slot_id.get(
                                    slot_id,
                                    None,
                                )
                            )
                            graph_tree = direct_graphical_tree_by_slot_id.get(
                                slot_id,
                                None,
                            )

                        if cached_slot_block is None:
                            if graph_tree is None:
                                try:
                                    graph_tree = extract_root_slot_graphical_tree_from_circuit(
                                        circuit=circuit,
                                        result=root_result,
                                        slot_name=slot_display_name,
                                        slot_dgs_id=direct_entry.slot_id,
                                        graphical_indexes=graphical_indexes,
                                    )
                                except Exception as exc:
                                    logger.add_warning(
                                        msg="DGS slot import skipped",
                                        value=f"{root_element.loc_name}/{slot_display_name}: {exc}",
                                    )
                                    graph_tree = None
                                else:
                                    pass
                            else:
                                pass

                            if graph_tree is None:
                                materialized_slot_block = None
                            else:
                                materialized_slot_block = graph_tree.view_block
                        else:
                            materialized_slot_block = cached_slot_block

                        if graph_tree is None:
                            unresolved_graphical_input_names: List[str] = list()
                        else:
                            unresolved_graphical_input_names = list(
                                graph_tree.parent_bindings.unresolved_input_names
                            )
                        unresolved_graphical_input_names.sort()
                        if len(unresolved_graphical_input_names) == 0:
                            pass
                        else:
                            unresolved_contract_parts: List[str] = list()
                            unresolved_contract_parts.append(effective_type_id)
                            unresolved_contract_parts.extend(
                                unresolved_graphical_input_names
                            )
                            unresolved_contract_key: Tuple[str, ...] = tuple(
                                unresolved_contract_parts
                            )
                            if unresolved_contract_key in reported_unresolved_graphical_contracts:
                                pass
                            else:
                                reported_unresolved_graphical_contracts.add(
                                    unresolved_contract_key
                                )
                                logger.add_warning(
                                    msg="DGS graphical operator topology incomplete",
                                    value=(
                                        f"{direct_entry.type_name}: live routed inputs "
                                        f"{unresolved_graphical_input_names} have no exported "
                                        "producer. Re-export with BlkDiv, BlkMul and BlkSwt "
                                        "monitors in DGS Export Definitions 7_2/Export DGS."
                                    ),
                                )

                        if materialized_slot_block is None:
                            parsed_slot_block = root_result.parsed_blocks.get(
                                effective_type_id,
                                None,
                            )
                            try:
                                if parsed_slot_block is None:
                                    slot_block = build_standalone_blkdef_block(
                                        dgs_path=dgs_path,
                                        typ_id=effective_type_id,
                                        block_name=slot_template_name,
                                    )
                                else:
                                    slot_block = build_standalone_blkdef_block_from_parsed_block(
                                        parsed_block=parsed_slot_block,
                                        block_name=slot_template_name,
                                    )
                            except Exception as exc:
                                logger.add_warning(
                                    msg="DGS slot block materialization skipped",
                                    value=f"{root_element.loc_name}/{slot_display_name}: {exc}",
                                )
                                slot_block = None

                            if slot_block is None:
                                entries.append(
                                    DynamicModelImportEntry(
                                        unique_key=(
                                            f"dgs-unavailable|{root_element.ID}|"
                                            f"{slot_identity}|{direct_entry.element_id}"
                                        ),
                                        display_name=slot_display_name,
                                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                        source_block=None,
                                        notes_text=(
                                            f"Root: {root_element.loc_name} | "
                                            f"Slot: {slot_display_name} | Block could not be materialized"
                                        ),
                                        parent_key=slot_parent_key,
                                        source_provenance=slot_source_provenance,
                                    )
                                )
                            else:
                                entries.append(
                                    DynamicModelImportEntry(
                                        unique_key=f"dgs-slot|{root_element.ID}|{slot_identity}|{direct_entry.element_id}",
                                        display_name=slot_display_name,
                                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                        source_block=slot_block,
                                        notes_text=f"Root: {root_element.loc_name} | Slot: {slot_display_name}",
                                        parent_key=slot_parent_key,
                                        source_provenance=slot_source_provenance,
                                    )
                                )
                        else:
                            try:
                                slot_block = materialized_slot_block
                                slot_block.name = slot_template_name
                            except Exception as exc:
                                logger.add_warning(
                                    msg="DGS graphical slot materialization skipped",
                                    value=f"{root_element.loc_name}/{slot_display_name}: {exc}",
                                )
                                slot_block = None

                            if slot_block is None:
                                entries.append(
                                    DynamicModelImportEntry(
                                        unique_key=(
                                            f"dgs-unavailable|{root_element.ID}|"
                                            f"{slot_identity}|{direct_entry.element_id}"
                                        ),
                                        display_name=slot_display_name,
                                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                        source_block=None,
                                        notes_text=(
                                            f"Root: {root_element.loc_name} | "
                                            f"Slot: {slot_display_name} | Graph could not be materialized"
                                        ),
                                        parent_key=slot_parent_key,
                                        source_provenance=slot_source_provenance,
                                    )
                                )
                            else:
                                entries.append(
                                    DynamicModelImportEntry(
                                        unique_key=f"dgs-slot|{root_element.ID}|{slot_identity}|{direct_entry.element_id}",
                                        display_name=slot_display_name,
                                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                        source_block=slot_block,
                                        notes_text=f"Root: {root_element.loc_name} | Slot: {slot_display_name}",
                                        parent_key=slot_parent_key,
                                        source_provenance=slot_source_provenance,
                                    )
                                )

                    processed_slot_count += 1
                    completed_steps += 1
                    current_progress_value = progress_start + int(round(progress_span * float(completed_steps) / float(total_steps)))
                    _emit_dynamic_model_import_progress(
                        progress_callback,
                        current_progress_value,
                        f"Importing DGS slots: {processed_slot_count}/{total_slot_count}",
                    )

    _emit_dynamic_model_import_progress(progress_callback, progress_end, "DGS root and slot catalogue ready")
    return entries, logger






def build_dgs_dynamic_model_import_bundle(
        dgs_path: str,
        progress_callback: Callable[[int, str], None] | None = None,
        dgs_circuit: DgsCircuit | None = None,
) -> Tuple[DynamicModelImportBundle, Logger]:
    """
    Parse one PowerFactory DGS file into domain-neutral block candidates.

    :param dgs_path: Source DGS path.
    :param progress_callback: Optional UI progress callback.
    :param dgs_circuit: Optional circuit already parsed by the static importer.
    :return: Pair ``(bundle, logger)``.
    """
    logger: Logger = Logger()
    shared_circuit: DgsCircuit
    shared_parsed_blocks: Dict[str, ParsedDgsBlockDefinition]
    catalog_entries: List[DgsStandaloneBlockCatalogEntry]
    bundle_entries: List[DynamicModelImportEntry] = list()
    root_entries: List[DynamicModelImportEntry]
    root_logger: Logger
    catalog_entry: DgsStandaloneBlockCatalogEntry

    # Static and dynamic import consume the same ASCII object graph. Reuse that
    # graph so a massive DGS is parsed once and every catalogue/root view is
    # guaranteed to observe the same source objects.
    if dgs_circuit is None:
        shared_circuit = DgsCircuit()
        shared_circuit.parse_dgs(dgs_path)
    else:
        shared_circuit = dgs_circuit
    shared_parsed_blocks = parse_dgs_block_definitions_from_circuit(
        circuit=shared_circuit
    )

    _emit_dynamic_model_import_progress(progress_callback, 0, "Scanning DGS dynamic model structure...")
    try:
        catalog_entries = build_dgs_standalone_block_catalog_from_circuit(
            circuit=shared_circuit,
            parsed_blocks=shared_parsed_blocks,
            isolated_only=False,
        )
    except Exception as exc:
        catalog_entries = list()
        logger.add_warning(
            msg="Standalone DGS dynamic-model catalogue skipped",
            value=str(exc),
        )
    _emit_dynamic_model_import_progress(progress_callback, 15, "Building standalone DGS block catalogue...")

    for catalog_entry in catalog_entries:
        source_block: Block | None = None
        notes_lines: List[str] = list()
        notes_text: str

        if catalog_entry.build_error is None:
            try:
                source_block = build_standalone_blkdef_block_from_parsed_block(
                    parsed_block=shared_parsed_blocks[catalog_entry.typ_id],
                    block_name=catalog_entry.blkdef_name,
                )
            except Exception as exc:
                notes_lines.append(f"Build error: {exc}")
                logger.add_warning(
                    msg="DGS dynamic block build error",
                    value=f"{catalog_entry.blkdef_name}: {exc}",
                )
        else:
            notes_lines.append(f"Build error: {catalog_entry.build_error}")
            logger.add_warning(msg="DGS dynamic block build error", value=catalog_entry.build_error)

        if len(catalog_entry.unsupported_lines) > 0:
            notes_lines.append(f"Unsupported statements: {len(catalog_entry.unsupported_lines)}")
        else:
            pass

        notes_lines.append(
            f"Occurrences: {catalog_entry.occurrence_count} | Isolated: {catalog_entry.isolated_occurrence_count} | Connected: {catalog_entry.connected_occurrence_count}"
        )
        notes_text = "\n".join(notes_lines)

        bundle_entries.append(
            DynamicModelImportEntry(
                unique_key=f"dgs|{catalog_entry.typ_id}|{catalog_entry.blkdef_name}",
                display_name=catalog_entry.blkdef_name,
                source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                source_block=source_block,
                notes_text=notes_text,
            )
        )

    if len(shared_circuit.elmcomps) == 0:
        root_entries = list()
        root_logger = Logger()
    else:
        try:
            root_entries, root_logger = _build_dgs_root_elmcomp_entries_with_progress(
                dgs_path=dgs_path,
                progress_callback=progress_callback,
                progress_start=15,
                progress_end=95,
                dgs_circuit=shared_circuit,
                parsed_dgs_blocks=shared_parsed_blocks,
            )
        except Exception as exc:
            root_entries = list()
            root_logger = Logger()
            logger.add_warning(
                msg="Root DGS dynamic-model catalogue skipped",
                value=str(exc),
            )
    if root_logger.has_logs():
        logger += root_logger
    else:
        pass

    bundle_entries.extend(root_entries)
    _emit_dynamic_model_import_progress(progress_callback, 100, "DGS dynamic model catalogue ready")

    bundle: DynamicModelImportBundle = DynamicModelImportBundle(
        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
        source_path=dgs_path,
        entries=bundle_entries,
    )
    return bundle, logger


def get_dynamic_model_import_supported_device_types() -> List[DeviceType]:
    """
    Return the supported host-device types exposed by the import dialog.

    Imported external templates do not reliably encode the final VeraGrid device
    type, so the user must choose one explicit compatible target from a curated
    list instead of the full internal ``DeviceType`` enumeration.

    :return: Supported host-device types.
    """
    return list([
        DeviceType.NoDevice,
        DeviceType.DynamicModelHostDevice,
        DeviceType.GeneratorDevice,
        DeviceType.StaticGeneratorDevice,
        DeviceType.BatteryDevice,
        DeviceType.LoadDevice,
        DeviceType.ShuntDevice,
        DeviceType.ControllableShuntDevice,
        DeviceType.CurrentInjectionDevice,
        DeviceType.ExternalGridDevice,
        DeviceType.LineDevice,
        DeviceType.Transformer2WDevice,
        DeviceType.VscDevice,
        DeviceType.HVDCLineDevice,
        DeviceType.DCLineDevice,
        DeviceType.SwitchDevice,
    ])


def guess_dynamic_model_import_default_device_tpe(entry: "DynamicModelImportEntry") -> DeviceType:
    """
    Return the conservative non-physical classification for an imported entry.

    DGS ``ElmComp.pelm`` values describe slot occupancy and do not prove that a
    composite root is the active RMS or EMT model of one physical device. Composite
    ``ElmComp`` entries use VeraGrid's non-physical dynamic-host catalogue tag;
    standalone DSL blocks keep ``NoDevice``.

    :param entry: Imported entry.
    :return: Default device type guess.
    """
    source_provenance: DynamicModelImportSourceProvenance | None = (
        entry.get_source_provenance()
    )
    is_root_composite: bool = (
        entry.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs
        and source_provenance is not None
        and source_provenance.get_slot_index() is None
        and entry.get_parent_key() is None
        and entry.get_source_block() is not None
    )
    is_nested_composite: bool = (
        source_provenance is not None and
        source_provenance.get_source_element_class() == "ElmComp"
    )

    if is_root_composite or is_nested_composite:
        device_tpe: DeviceType = DeviceType.DynamicModelHostDevice
    else:
        device_tpe = DeviceType.NoDevice

    return device_tpe


def get_dgs_dynamic_host_device_tpe(source_element_class: str | None) -> DeviceType | None:
    """
    Map one authoritative PowerFactory host class to a VeraGrid device type.

    Auxiliary composite references such as ``StaSwitch`` and ``ElmSind`` are
    intentionally absent. They provide controller inputs or switching actions,
    but they do not identify the physical device that owns the composite model.

    :param source_element_class: Referenced DGS ``pElm`` class.
    :return: Compatible VeraGrid device type or ``None`` for non-host classes.
    """
    result: DeviceType | None

    if source_element_class in {"ElmVsc", "ElmVscmono"}:
        result = DeviceType.VscDevice
    else:
        if source_element_class == "ElmSvs":
            result = DeviceType.ControllableShuntDevice
        else:
            if source_element_class == "ElmSym":
                result = DeviceType.GeneratorDevice
            else:
                if source_element_class == "ElmGenstat":
                    # A composite-controlled ElmGenstat is a dynamic current
                    # injection. The static importer materializes that contract
                    # as Generator (or its Battery subclass), not as a fixed-PQ
                    # StaticGenerator.
                    result = DeviceType.GeneratorDevice
                else:
                    if source_element_class in {"ElmLod", "ElmLodlv", "ElmLodmv"}:
                        result = DeviceType.LoadDevice
                    else:
                        if source_element_class == "ElmBat":
                            result = DeviceType.BatteryDevice
                        else:
                            if source_element_class == "ElmLne":
                                result = DeviceType.LineDevice
                            else:
                                if source_element_class == "ElmTr2":
                                    result = DeviceType.Transformer2WDevice
                                else:
                                    if source_element_class == "ElmXnet":
                                        # The normal DGS path materializes an
                                        # external grid as a dynamic Generator.
                                        result = DeviceType.GeneratorDevice
                                    else:
                                        result = None

    return result


def is_dgs_dynamic_block_runtime_assignable(
        block: Block,
        device_tpe: DeviceType,
        adapter_kind: _DgsRuntimeAdapterKind | None = None,
) -> bool:
    """
    Check that an imported root exposes a complete VeraGrid runtime contract.

    Exact DGS ownership does not imply that the symbolic root includes the
    built-in PowerFactory equipment equations. Promotion therefore requires the
    external power-flow outputs and bus-facing inputs consumed by VeraGrid's
    device compiler. Unsupported families remain catalogue-only until their
    typed adapters are implemented and validated.

    :param block: Imported domain-neutral symbolic block.
    :param device_tpe: Exact physical host type inferred from DGS.
    :param adapter_kind: Import-local adapter classification. ``None`` retains
        compatibility with catalogue callers that inspect legacy templates.
    :return: ``True`` only for a complete supported runtime interface.
    """
    mapping_refs: Set[VarPowerFlowReferenceType] = set(block.external_mapping)
    input_refs: Set[VarPowerFlowReferenceType] = set()
    input_var: Var
    for input_var in block.in_vars:
        if isinstance(input_var.ref, VarPowerFlowReferenceType):
            input_refs.add(input_var.ref)
        else:
            pass

    required_mapping_values: Tuple[VarPowerFlowReferenceType, ...]
    required_input_values: Tuple[VarPowerFlowReferenceType, ...]
    if device_tpe == DeviceType.VscDevice:
        required_mapping_values = (
            VarPowerFlowReferenceType.Pf,
            VarPowerFlowReferenceType.Pt,
            VarPowerFlowReferenceType.Qt,
        )
        is_monopolar_vsc: bool = (
            adapter_kind == _DgsRuntimeAdapterKind.VSC_MONOPOLAR
        )
        if is_monopolar_vsc:
            required_input_values = (
                VarPowerFlowReferenceType.Vf_dc,
                VarPowerFlowReferenceType.Vmt,
                VarPowerFlowReferenceType.Vat,
            )
        else:
            required_input_values = (
                VarPowerFlowReferenceType.Vf_dc,
                VarPowerFlowReferenceType.Vt_dc,
                VarPowerFlowReferenceType.Vmt,
                VarPowerFlowReferenceType.Vat,
            )
    else:
        if device_tpe == DeviceType.ControllableShuntDevice:
            required_mapping_values = (
                VarPowerFlowReferenceType.P,
                VarPowerFlowReferenceType.Q,
            )
            required_input_values = (
                VarPowerFlowReferenceType.Vm,
                VarPowerFlowReferenceType.Va,
            )
        else:
            if device_tpe == DeviceType.GeneratorDevice:
                required_mapping_values = (
                    VarPowerFlowReferenceType.P,
                    VarPowerFlowReferenceType.Q,
                )
                required_input_values = (
                    VarPowerFlowReferenceType.Vm,
                    VarPowerFlowReferenceType.Va,
                )
            else:
                required_mapping_values = tuple()
                required_input_values = tuple()

    required_mapping_refs: Set[VarPowerFlowReferenceType] = set(
        required_mapping_values
    )
    required_input_refs: Set[VarPowerFlowReferenceType] = set(
        required_input_values
    )

    if len(required_mapping_refs) == 0 or len(required_input_refs) == 0:
        result: bool = False
    else:
        result = (
            required_mapping_refs.issubset(mapping_refs)
            and required_input_refs.issubset(input_refs)
        )

    return result


def _get_dgs_runtime_adapter_kind(
        block: Block,
        device_tpe: DeviceType,
) -> _DgsRuntimeAdapterKind | None:
    """Classify one source block without attaching metadata to it.

    The classification exists only during the DGS conversion.  It replaces
    mutable undeclared metadata previously copied onto ``Block`` and is
    discarded after the final template has been configured and assigned.

    :param block: Directly materialized DGS root block.
    :param device_tpe: Exact physical host family resolved by FID.
    :return: Required runtime adapter, or ``None`` for a native contract.
    """
    if device_tpe == DeviceType.VscDevice:
        if is_dgs_elmvscmono_slot_contract(block):
            adapter_kind: _DgsRuntimeAdapterKind | None = (
                _DgsRuntimeAdapterKind.VSC_MONOPOLAR
            )
        else:
            if is_dgs_elmvsc_slot_contract(block):
                adapter_kind = _DgsRuntimeAdapterKind.VSC_BIPOLAR
            else:
                adapter_kind = None
    else:
        # Generator and static-var equipment require the exact transient DGS
        # relation classified by ``_get_dgs_direct_runtime_adapter_kind``.
        # A detached Block cannot prove the physical FID association.
        adapter_kind = None
    return adapter_kind


def _get_dgs_direct_runtime_adapter_kind(
        direct_result: DgsDirectRootBuildResult,
        host_identity: Tuple[str, DeviceType, str, str | None],
) -> _DgsRuntimeAdapterKind | None:
    """Classify one physical adapter from an exact typed DGS slot.

    The source equipment FID and class must match exactly one resolved direct
    relation. Signal names are then checked only inside that relation's declared
    input/output lists, including uniqueness and direction. Recursive names in
    unrelated controller children cannot establish an equipment contract.

    :param direct_result: Materialized root plus its validated transient slots.
    :param host_identity: Exact FID, device type, source class and source name.
    :return: Structurally proven direct adapter, or ``None``.
    """
    host_source_id: str = host_identity[0]
    host_device_tpe: DeviceType = host_identity[1]
    host_source_class: str = host_identity[2]
    matching_entries: List[ElmCompInstanceEntry] = list()
    direct_entry: ElmCompInstanceEntry
    for direct_entry in direct_result.direct_entries:
        if (
                direct_entry.element_reference_is_resolved
                and direct_entry.element_id == host_source_id
                and direct_entry.element_kind == host_source_class
        ):
            matching_entries.append(direct_entry)
        else:
            pass

    if len(matching_entries) != 1:
        adapter_kind: _DgsRuntimeAdapterKind | None = None
    else:
        equipment_entry: ElmCompInstanceEntry = matching_entries[0]
        host_matches_declared_equipment: bool = (
            equipment_entry.accepts_element_kind(
                element_kind=host_source_class,
            )
        )
        output_components: List[str] = equipment_entry.get_slot_signal_components(
            direction=DgsSlotSignalDirection.Output,
        )
        input_components: List[str] = equipment_entry.get_slot_signal_components(
            direction=DgsSlotSignalDirection.Input,
        )
        output_names: Set[str] = set(output_components)
        input_names: Set[str] = set(input_components)
        contract_is_unique_and_directional: bool = bool(
            len(output_names) == len(output_components)
            and len(input_names) == len(input_components)
            and output_names.isdisjoint(input_names)
            and host_matches_declared_equipment
        )
        if not contract_is_unique_and_directional:
            adapter_kind = None
        else:
            if host_source_class == "ElmVscmono":
                required_outputs: Set[str] = set(("id", "iq", "uDC"))
                required_inputs: Set[str] = set(("Pmd", "Pmq"))
                has_angle_inputs: bool = bool(
                    {"cosref", "sinref"}.issubset(input_names)
                    or {"cosphi", "sinphi"}.issubset(input_names)
                )
                if (
                        required_outputs.issubset(output_names)
                        and required_inputs.issubset(input_names)
                        and has_angle_inputs
                ):
                    adapter_kind = _DgsRuntimeAdapterKind.VSC_MONOPOLAR
                else:
                    adapter_kind = None
            else:
                if host_source_class == "ElmVsc":
                    required_inputs = set(("Pmr", "Pmi", "mdc"))
                    current_output_count: int = int("iDC" in output_names) + int(
                        "idc" in output_names
                    )
                    cell_voltage_output_count: int = int(
                        "yUcell" in output_names
                    ) + int("Ucap" in output_names)
                    if (
                            required_inputs.issubset(input_names)
                            and current_output_count == 1
                            and cell_voltage_output_count == 1
                    ):
                        adapter_kind = _DgsRuntimeAdapterKind.VSC_BIPOLAR
                    else:
                        adapter_kind = None
                else:
                    if (
                            host_source_class == "ElmSym"
                            and host_device_tpe == DeviceType.GeneratorDevice
                    ):
                        required_outputs = set([
                            "ID", "IQ", "IFDIEEE", "RPOWER", "SG", "VT",
                            "VTD", "VTQ", "cosn", "speed",
                        ])
                        required_inputs = set(["pt", "ve"])
                        if (
                                required_outputs.issubset(output_names)
                                and required_inputs.issubset(input_names)
                        ):
                            adapter_kind = (
                                _DgsRuntimeAdapterKind.SYNCHRONOUS_MACHINE_PENDING
                            )
                        else:
                            adapter_kind = None
                    else:
                        if (
                                host_source_class == "ElmGenstat"
                                and host_device_tpe == DeviceType.GeneratorDevice
                        ):
                            required_inputs = set(["id_ref", "iq_ref"])
                            if required_inputs.issubset(input_names):
                                adapter_kind = _DgsRuntimeAdapterKind.STATIC_GENERATOR
                            else:
                                adapter_kind = None
                        else:
                            if (
                                    host_source_class == "ElmSvs"
                                    and host_device_tpe
                                    == DeviceType.ControllableShuntDevice
                            ):
                                required_outputs = set([
                                    "ysvs", "qreact", "qcap", "qfixcap",
                                    "nxcap", "nfixcap",
                                ])
                                required_inputs = set(["bsvs"])
                                if (
                                        required_outputs.issubset(output_names)
                                        and required_inputs.issubset(input_names)
                                ):
                                    adapter_kind = (
                                        _DgsRuntimeAdapterKind.STATIC_VAR_SYSTEM
                                    )
                                else:
                                    adapter_kind = None
                            else:
                                adapter_kind = None
    return adapter_kind


def guess_dynamic_model_import_hierarchy_device_tpe(
        bundle: "DynamicModelImportBundle",
        entry: "DynamicModelImportEntry",
) -> DeviceType:
    """
    Infer one physical host type from an exact DGS composite hierarchy.

    A root becomes directly assignable only when all supported physical host
    relations reduce to one source FID and one compatible VeraGrid device type.
    Roots with several hosts remain generic catalogue objects because assigning
    a plant controller independently to every device would duplicate its states.

    :param bundle: Bundle containing the complete source hierarchy.
    :param entry: Entry whose owning hierarchy is being classified.
    :return: Physical device type or the conservative generic classification.
    """
    fallback_tpe: DeviceType = guess_dynamic_model_import_default_device_tpe(entry=entry)
    source_provenance: DynamicModelImportSourceProvenance | None = (
        entry.get_source_provenance()
    )
    is_root_composite: bool = (
        source_provenance is not None
        and source_provenance.get_slot_index() is None
        and entry.get_parent_key() is None
        and entry.get_source_block() is not None
    )
    host_identities: Set[Tuple[str, DeviceType]] = set()
    candidate_entry: DynamicModelImportEntry
    candidate_provenance: DynamicModelImportSourceProvenance | None
    candidate_class: str | None
    candidate_device_tpe: DeviceType | None
    candidate_element_id: str | None
    source_block: Block | None = entry.get_source_block()

    if (
            entry.get_source_tpe() != DynamicModelImportSource.PowerFactoryDgs
            or source_provenance is None
            or not is_root_composite
    ):
        result: DeviceType = fallback_tpe
    else:
        # FID and class are the only admissible join keys. Display names remain
        # provenance and never participate in host inference.
        for candidate_entry in bundle.get_entries():
            candidate_provenance = candidate_entry.get_source_provenance()
            if candidate_provenance is None:
                pass
            else:
                if (
                        candidate_provenance.get_root_dgs_id()
                        != source_provenance.get_root_dgs_id()
                ):
                    pass
                else:
                    candidate_class = (
                        candidate_provenance.get_source_element_class()
                    )
                    candidate_device_tpe = get_dgs_dynamic_host_device_tpe(
                        source_element_class=candidate_class,
                    )
                    candidate_element_id = (
                        candidate_provenance.get_source_element_dgs_id()
                    )
                    if candidate_device_tpe is None or candidate_element_id is None:
                        pass
                    else:
                        host_identities.add((candidate_element_id, candidate_device_tpe))

        if len(host_identities) == 1:
            host_identity: Tuple[str, DeviceType] = next(iter(host_identities))
            if source_block is None:
                result = fallback_tpe
            else:
                runtime_contract_ready: bool = is_dgs_dynamic_block_runtime_assignable(
                    block=source_block,
                    device_tpe=host_identity[1],
                    adapter_kind=_get_dgs_runtime_adapter_kind(
                        block=source_block,
                        device_tpe=host_identity[1],
                    ),
                )
                elmvsc_adapter_supported: bool = (
                    host_identity[1] == DeviceType.VscDevice
                    and (
                        is_dgs_elmvsc_slot_contract(source_block)
                        or is_dgs_elmvscmono_slot_contract(source_block)
                    )
                )
                if (
                        runtime_contract_ready
                        or elmvsc_adapter_supported
                ):
                    result = host_identity[1]
                else:
                    result = fallback_tpe
        else:
            result = fallback_tpe

    return result


def _apply_composite_child_interface_if_missing(block: Block) -> None:
    """
    Synthesize one composite interface from child ports when the root lacks one.

    :param block: Candidate composite root block.
    :return: None.
    """
    input_vars_by_uid: Dict[int, Var] = dict()
    output_vars_by_uid: Dict[int, Var] = dict()
    child_block: Block
    input_var: Var
    output_var: Var

    if len(block.children) == 0:
        return
    else:
        pass

    if len(block.in_vars) > 0 or len(block.out_vars) > 0:
        return
    else:
        pass

    # first we discard variables that are interconected between child blocks
    intern_connected_vars_list: List[Var] = list()
    for child_block1 in block.children:
        for child_block2 in block.children:
            pairs, power_flow_pairs = find_connections(child_block1, child_block2)
            for pair in pairs:
                for var in pair:
                    intern_connected_vars_list.append(var)
            for power_flow_pair in power_flow_pairs:
                for var in power_flow_pair:
                    intern_connected_vars_list.append(var)


    for child_block in block.children:
        # Preserve the child order so imported reusable-template ports stay stable.
        for input_var in child_block.in_vars:
            if input_var.uid in input_vars_by_uid or input_var in intern_connected_vars_list:
                pass
            else:
                input_vars_by_uid[input_var.uid] = input_var

        for output_var in child_block.out_vars:
            if output_var.uid in output_vars_by_uid or input_var in intern_connected_vars_list:
                pass
            else:
                output_vars_by_uid[output_var.uid] = output_var

    block.in_vars = list(input_vars_by_uid.values())
    block.out_vars = list(output_vars_by_uid.values())


def _get_internally_connected_input_object_ids(block: Block) -> Set[int]:
    """Return child-input object identities supplied by another child.

    The DGS materializer reuses the exact ``Var`` identity, UID or shared
    reference when it resolves a routed signal. Only inputs absent from this
    internal graph belong to the public power-flow interface.

    :param block: Composite block whose direct children form the signal graph.
    :return: Object identities of child inputs connected inside the composite.
    """
    connected_input_object_ids: Set[int] = set()
    source_block: Block
    target_block: Block
    signal_pairs: List[tuple[Var, Var]]
    power_flow_pairs: List[tuple[Var, Var]]
    signal_pair: tuple[Var, Var]

    # Inspect every directed child pair because DGS signal routing is ordered
    # from a producer output to a consumer input.
    for source_block in block.children:
        for target_block in block.children:
            if source_block is target_block:
                pass
            else:
                signal_pairs, power_flow_pairs = find_connections(
                    source_block,
                    target_block,
                )
                for signal_pair in signal_pairs:
                    connected_input_object_ids.add(id(signal_pair[1]))
                for signal_pair in power_flow_pairs:
                    connected_input_object_ids.add(id(signal_pair[1]))

    return connected_input_object_ids


def _resolve_dgs_external_input_reference(
        input_name: str,
        device_tpe: DeviceType,
) -> VarPowerFlowReferenceType | None:
    """Resolve one public DGS input into its power-flow reference.

    Names are interpreted only after topology has proved that the input has no
    internal producer. Branch-like VSC measurements use terminal-specific
    references so equal physical quantities at opposite terminals cannot be
    joined by the editor merely because their generic reference matches.

    :param input_name: Imported DGS signal name.
    :param device_tpe: Physical device family owning the composite model.
    :return: Matching power-flow reference, or ``None`` for a control signal.
    """
    normalized_name: str = input_name.strip().lower()
    reference: VarPowerFlowReferenceType | None

    if device_tpe == DeviceType.VscDevice:
        vsc_references: Dict[str, VarPowerFlowReferenceType] = dict((
            ("vdc", VarPowerFlowReferenceType.Vf_dc),
            ("vm", VarPowerFlowReferenceType.Vmt),
            ("va", VarPowerFlowReferenceType.Vat),
            ("u", VarPowerFlowReferenceType.Ut),
            ("ur", VarPowerFlowReferenceType.URt),
            ("ui", VarPowerFlowReferenceType.UIt),
            ("ur_a", VarPowerFlowReferenceType.URt_A),
            ("ur_b", VarPowerFlowReferenceType.URt_B),
            ("ur_c", VarPowerFlowReferenceType.URt_C),
            ("ui_a", VarPowerFlowReferenceType.UIt_A),
            ("ui_b", VarPowerFlowReferenceType.UIt_B),
            ("ui_c", VarPowerFlowReferenceType.UIt_C),
            ("p_act", VarPowerFlowReferenceType.Pt),
            ("q_act", VarPowerFlowReferenceType.Qt),
            ("cosphi", VarPowerFlowReferenceType.COSPHIt),
            ("sinphi", VarPowerFlowReferenceType.SINPHIt),
            ("cosref", VarPowerFlowReferenceType.COSPHIt),
            ("sinref", VarPowerFlowReferenceType.SINPHIt),
        ))
        reference = vsc_references.get(normalized_name, None)
    else:
        device_is_injection: bool = device_tpe in (
            DeviceType.GeneratorDevice,
            DeviceType.LoadDevice,
            DeviceType.BatteryDevice,
            DeviceType.ControllableShuntDevice,
        )
        if device_is_injection:
            injection_references: Dict[str, VarPowerFlowReferenceType] = dict((
                ("vm", VarPowerFlowReferenceType.Vm),
                ("va", VarPowerFlowReferenceType.Va),
                ("u", VarPowerFlowReferenceType.U),
                ("ur", VarPowerFlowReferenceType.UR),
                ("ui", VarPowerFlowReferenceType.UI),
                ("ur_a", VarPowerFlowReferenceType.UR_A),
                ("ur_b", VarPowerFlowReferenceType.UR_B),
                ("ur_c", VarPowerFlowReferenceType.UR_C),
                ("ui_a", VarPowerFlowReferenceType.UI_A),
                ("ui_b", VarPowerFlowReferenceType.UI_B),
                ("ui_c", VarPowerFlowReferenceType.UI_C),
                ("p_act", VarPowerFlowReferenceType.P),
                ("q_act", VarPowerFlowReferenceType.Q),
                ("cosphi", VarPowerFlowReferenceType.COSPHI),
                ("sinphi", VarPowerFlowReferenceType.SINPHI),
                ("cosref", VarPowerFlowReferenceType.COSPHI),
                ("sinref", VarPowerFlowReferenceType.SINPHI),
            ))
            reference = injection_references.get(normalized_name, None)
        else:
            reference = None

    return reference


def _assign_dgs_external_input_references(
        block: Block,
        device_tpe: DeviceType,
) -> None:
    """Type child inputs that remain exposed outside a DGS composite.

    :param block: Fully connected composite built from direct DGS children.
    :param device_tpe: Physical device family owning the composite model.
    :return: None.
    """
    connected_input_object_ids: Set[int] = (
        _get_internally_connected_input_object_ids(block=block)
    )
    child_block: Block
    input_var: Var
    resolved_reference: VarPowerFlowReferenceType | None

    # Preserve internal control signals unchanged. The editor must only create
    # physical measurement blocks for inputs that cross the root boundary.
    for child_block in block.children:
        for input_var in child_block.in_vars:
            if id(input_var) in connected_input_object_ids:
                pass
            else:
                resolved_reference = _resolve_dgs_external_input_reference(
                    input_name=input_var.name,
                    device_tpe=device_tpe,
                )
                if resolved_reference is None:
                    pass
                else:
                    input_var.ref = resolved_reference


def _collect_unconnected_dgs_child_inputs(
        block: Block,
) -> List[Tuple[Block, Var]]:
    """Collect direct-child inputs that have no producer inside a composite.

    :param block: Composite DGS root whose direct children are inspected.
    :return: Ordered owner-variable pairs for unconnected child inputs.
    """
    connected_input_object_ids: Set[int] = (
        _get_internally_connected_input_object_ids(block=block)
    )
    unconnected_inputs: List[Tuple[Block, Var]] = list()
    child_block: Block
    input_var: Var
    for child_block in block.children:
        for input_var in child_block.in_vars:
            if id(input_var) in connected_input_object_ids:
                pass
            else:
                unconnected_inputs.append((child_block, input_var))
    return unconnected_inputs


def _classify_rms_measurement_terminal(
        reference: VarPowerFlowReferenceType,
) -> RmsTerminalSide | None:
    """Classify one measurement reference by its physical terminal.

    :param reference: Typed power-flow or measurement reference.
    :return: From, to, bus, or ``None`` when the reference is not measurable.
    """
    from_references: Set[VarPowerFlowReferenceType] = set((
        VarPowerFlowReferenceType.Vmf,
        VarPowerFlowReferenceType.Vaf,
        VarPowerFlowReferenceType.Vf_dc,
        VarPowerFlowReferenceType.Pf,
        VarPowerFlowReferenceType.Qf,
        VarPowerFlowReferenceType.Uf,
        VarPowerFlowReferenceType.URf,
        VarPowerFlowReferenceType.UIf,
        VarPowerFlowReferenceType.URf_A,
        VarPowerFlowReferenceType.URf_B,
        VarPowerFlowReferenceType.URf_C,
        VarPowerFlowReferenceType.UIf_A,
        VarPowerFlowReferenceType.UIf_B,
        VarPowerFlowReferenceType.UIf_C,
        VarPowerFlowReferenceType.COSPHIf,
        VarPowerFlowReferenceType.SINPHIf,
        VarPowerFlowReferenceType.If_dc,
    ))
    to_references: Set[VarPowerFlowReferenceType] = set((
        VarPowerFlowReferenceType.Vmt,
        VarPowerFlowReferenceType.Vat,
        VarPowerFlowReferenceType.Vt_dc,
        VarPowerFlowReferenceType.Pt,
        VarPowerFlowReferenceType.Qt,
        VarPowerFlowReferenceType.Ut,
        VarPowerFlowReferenceType.URt,
        VarPowerFlowReferenceType.UIt,
        VarPowerFlowReferenceType.URt_A,
        VarPowerFlowReferenceType.URt_B,
        VarPowerFlowReferenceType.URt_C,
        VarPowerFlowReferenceType.UIt_A,
        VarPowerFlowReferenceType.UIt_B,
        VarPowerFlowReferenceType.UIt_C,
        VarPowerFlowReferenceType.COSPHIt,
        VarPowerFlowReferenceType.SINPHIt,
        VarPowerFlowReferenceType.It_dc,
    ))
    bus_references: Set[VarPowerFlowReferenceType] = set((
        VarPowerFlowReferenceType.Vm,
        VarPowerFlowReferenceType.Va,
        VarPowerFlowReferenceType.Vdc,
        VarPowerFlowReferenceType.P,
        VarPowerFlowReferenceType.Q,
        VarPowerFlowReferenceType.U,
        VarPowerFlowReferenceType.UR,
        VarPowerFlowReferenceType.UI,
        VarPowerFlowReferenceType.UR_A,
        VarPowerFlowReferenceType.UR_B,
        VarPowerFlowReferenceType.UR_C,
        VarPowerFlowReferenceType.UI_A,
        VarPowerFlowReferenceType.UI_B,
        VarPowerFlowReferenceType.UI_C,
        VarPowerFlowReferenceType.COSPHI,
        VarPowerFlowReferenceType.SINPHI,
        VarPowerFlowReferenceType.I_DC,
    ))
    if reference in from_references:
        terminal_side: RmsTerminalSide | None = RmsTerminalSide.FROM
    else:
        if reference in to_references:
            terminal_side = RmsTerminalSide.TO
        else:
            if reference in bus_references:
                terminal_side = RmsTerminalSide.BUS
            else:
                terminal_side = None
    return terminal_side


def _get_rms_terminal_physical_references(
        block_type: BlockType,
        terminal_side: RmsTerminalSide,
        is_dc_terminal: bool,
) -> List[VarPowerFlowReferenceType]:
    """Return the physical root inputs required by one RMS measurement.

    :param block_type: Measurement family selected for the imported signals.
    :param terminal_side: Physical terminal represented by the measurement.
    :param is_dc_terminal: Whether the selected physical terminal is DC.
    :return: Ordered physical references required to build the measurement.
    """
    if terminal_side is RmsTerminalSide.FROM:
        vm_reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.Vmf
        va_reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.Vaf
        vdc_reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.Vf_dc
        p_reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.Pf
        q_reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.Qf
    else:
        if terminal_side is RmsTerminalSide.TO:
            vm_reference = VarPowerFlowReferenceType.Vmt
            va_reference = VarPowerFlowReferenceType.Vat
            vdc_reference = VarPowerFlowReferenceType.Vt_dc
            p_reference = VarPowerFlowReferenceType.Pt
            q_reference = VarPowerFlowReferenceType.Qt
        else:
            vm_reference = VarPowerFlowReferenceType.Vm
            va_reference = VarPowerFlowReferenceType.Va
            vdc_reference = VarPowerFlowReferenceType.Vdc
            p_reference = VarPowerFlowReferenceType.P
            q_reference = VarPowerFlowReferenceType.Q

    # Each measurement receives the smallest physical contract from which its
    # requested derived signals can be calculated.
    if block_type == BlockType.MEASUREMENTS_VOLTAGE_FROM_POLAR:
        required_references: List[VarPowerFlowReferenceType] = list((
            vm_reference,
            va_reference,
        ))
    else:
        if block_type == BlockType.MEASUREMENTS_PLL:
            required_references = list((va_reference,))
        else:
            if block_type == BlockType.MEASUREMENTS_VOLTAGE_FROM_DC:
                required_references = list((vdc_reference,))
            else:
                if block_type == BlockType.MEASUREMENTS_CURRENT_FROM_PQ:
                    required_references = list((
                        vm_reference,
                        va_reference,
                        p_reference,
                        q_reference,
                    ))
                else:
                    if block_type == BlockType.MEASUREMENTS_VOLTAGE_ANGLE:
                        if is_dc_terminal:
                            required_references = list((vdc_reference,))
                        else:
                            required_references = list((
                                vm_reference,
                                va_reference,
                            ))
                    else:
                        if block_type == BlockType.MEASUREMENTS_P_Q:
                            if is_dc_terminal:
                                required_references = list((p_reference,))
                            else:
                                required_references = list((
                                    p_reference,
                                    q_reference,
                                ))
                        else:
                            required_references = list()
    return required_references


def _get_or_create_dgs_physical_input(
        block: Block,
        reference: VarPowerFlowReferenceType,
        physical_inputs_by_reference: Dict[VarPowerFlowReferenceType, Var],
        var_factory: VarFactory,
) -> Var:
    """Resolve one canonical physical input for an imported DGS template.

    :param block: Imported root that exposes the physical input.
    :param reference: Exact power-flow quantity required by a measurement.
    :param physical_inputs_by_reference: Canonical inputs already allocated.
    :param var_factory: Factory owning newly allocated template variables.
    :return: Canonical physical input for the requested reference.
    """
    physical_input: Var | None = physical_inputs_by_reference.get(reference, None)
    if physical_input is None:
        # The parser has no bus model yet. Create the same typed boundary
        # variable used by native templates so device assignment can connect it
        # to the real bus through ``connect_bus_variables_rms`` later.
        physical_input = var_factory.add_var(
            name=reference.name,
            reference=reference,
        )
        physical_inputs_by_reference[reference] = physical_input
        block.in_vars.append(physical_input)
    else:
        pass
    return physical_input


def _build_dgs_rms_measurement_block(
        block_type: BlockType,
        terminal_side: RmsTerminalSide,
        is_dc_terminal: bool,
        physical_inputs_by_reference: Dict[VarPowerFlowReferenceType, Var],
        var_factory: VarFactory,
) -> Block | None:
    """Build one required RMS measurement for an exact terminal.

    :param block_type: Measurement family selected from the reference catalog.
    :param terminal_side: Physical terminal represented by the block.
    :param is_dc_terminal: Whether the selected physical terminal is DC.
    :param physical_inputs_by_reference: Canonical physical template inputs.
    :param var_factory: Isolated factory owned by this imported template.
    :return: Constructed measurement block, or ``None`` without prerequisites.
    """
    measurement_block: Block | None = None
    variables: List[Var]
    vm: Var | None
    va: Var | None
    vdc: Var | None
    if terminal_side is RmsTerminalSide.FROM:
        vm = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Vmf, None)
        va = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Vaf, None)
        vdc = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Vf_dc, None)
    else:
        if terminal_side is RmsTerminalSide.TO:
            vm = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Vmt, None)
            va = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Vat, None)
            vdc = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Vt_dc, None)
        else:
            vm = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Vm, None)
            va = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Va, None)
            vdc = physical_inputs_by_reference.get(VarPowerFlowReferenceType.Vdc, None)

    if block_type == BlockType.MEASUREMENTS_VOLTAGE_FROM_POLAR:
        if vm is None or va is None:
            pass
        else:
            if terminal_side is RmsTerminalSide.FROM:
                measurement_block, variables = build_rms_voltage_meter_outputs_from_polar_from(
                    var_factory=var_factory,
                    vm=vm,
                    va=va,
                )
            else:
                if terminal_side is RmsTerminalSide.TO:
                    measurement_block, variables = build_rms_voltage_meter_outputs_from_polar_to(
                        var_factory=var_factory,
                        vm=vm,
                        va=va,
                    )
                else:
                    nominal_frequency: Const = var_factory.add_const(50.0)
                    measurement_block, variables = build_rms_voltage_meter_outputs_from_polar(
                        var_factory=var_factory,
                        vm=vm,
                        va=va,
                        measured_frequency_hz=nominal_frequency,
                        nominal_frequency_hz=nominal_frequency,
                    )
                    measurement_block.in_vars = list((vm, va))
                    measurement_block.out_vars = variables
    else:
        if block_type == BlockType.MEASUREMENTS_PLL:
            if va is None:
                pass
            else:
                if terminal_side is RmsTerminalSide.FROM:
                    measurement_block, variables = build_rms_pll_measurements_from(
                        va=va,
                        var_factory=var_factory,
                    )
                else:
                    if terminal_side is RmsTerminalSide.TO:
                        measurement_block, variables = build_rms_pll_measurements_to(
                            va=va,
                            var_factory=var_factory,
                        )
                    else:
                        measurement_block, variables = build_rms_pll_measurements(
                            va=va,
                            var_factory=var_factory,
                        )
        else:
            if block_type == BlockType.MEASUREMENTS_VOLTAGE_FROM_DC:
                if vdc is None:
                    pass
                else:
                    if terminal_side is RmsTerminalSide.FROM:
                        measurement_block, variables = build_rms_voltage_meter_outputs_from_dc_from(
                            var_factory=var_factory,
                            vdc=vdc,
                        )
                    else:
                        if terminal_side is RmsTerminalSide.TO:
                            measurement_block, variables = build_rms_voltage_meter_outputs_from_dc_to(
                                var_factory=var_factory,
                                vdc=vdc,
                            )
                        else:
                            nominal_frequency = var_factory.add_const(50.0)
                            measurement_block, variables = build_rms_voltage_meter_outputs_from_dc(
                                var_factory=var_factory,
                                vdc=vdc,
                                nominal_frequency_hz=nominal_frequency,
                            )
                            measurement_block.in_vars = list((vdc,))
                            measurement_block.out_vars = variables
            else:
                if block_type in (
                        BlockType.MEASUREMENTS_VOLTAGE_ANGLE,
                        BlockType.MEASUREMENTS_P_Q,
                ):
                    pass_through_vars: List[Var] = list()
                    required_references: List[VarPowerFlowReferenceType] = (
                        _get_rms_terminal_physical_references(
                            block_type=block_type,
                            terminal_side=terminal_side,
                            is_dc_terminal=is_dc_terminal,
                        )
                    )
                    required_reference: VarPowerFlowReferenceType
                    for required_reference in required_references:
                        input_var: Var | None = physical_inputs_by_reference.get(
                            required_reference,
                            None,
                        )
                        if block_type == BlockType.MEASUREMENTS_VOLTAGE_ANGLE:
                            include_var: bool = input_var in (vm, va, vdc)
                        else:
                            include_var = (
                                input_var is not None
                                and input_var.ref == required_reference
                            )
                        if (
                                include_var
                                and input_var is not None
                                and input_var not in pass_through_vars
                        ):
                            pass_through_vars.append(input_var)
                        else:
                            pass
                    if len(pass_through_vars) == 0:
                        pass
                    else:
                        measurement_block = Block(
                            in_vars=list(pass_through_vars),
                            out_vars=pass_through_vars,
                        )
                else:
                    pass

    if measurement_block is None:
        pass
    else:
        measurement_block.name = block_type.name + "_" + terminal_side.name
    return measurement_block


def _collect_native_dgs_rms_measurement_specs(
        dgs_circuit: DgsCircuit,
        root_element: ElmComp,
        direct_result: DgsDirectRootBuildResult,
        host_device: DynamicDevice | None,
) -> List[_DgsRmsMeasurementSpec]:
    """Resolve native meter semantics and exact consumers before adaptation.

    :param dgs_circuit: Parsed source graph retaining native meter objects.
    :param root_element: Composite root whose direct slots are materialized.
    :param direct_result: Exact direct-slot lookup for the controller root.
    :param host_device: Physical host used to interpret implicit ElmPhi frames.
    :return: Ordered native measurement construction specifications.
    """
    element_by_id: Dict[str, DGSElement] = _build_dgs_element_index(
        dgs_circuit=dgs_circuit,
    )
    implicit_target_by_slot: Dict[str, str] = (
        _build_implicit_meter_target_by_slot(
            dgs_circuit=dgs_circuit,
            root_element=root_element,
            entries=direct_result.direct_entries,
        )
    )
    specs: List[_DgsRmsMeasurementSpec] = list()
    entry: ElmCompInstanceEntry

    # Follow exact direct-slot identities so equal signal names in independent
    # controller children never become an accidental shared measurement.
    for entry in direct_result.direct_entries:
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
                    meter_element = _resolve_native_pll_element(
                        root_element=root_element,
                        dgs_circuit=dgs_circuit,
                    )
                else:
                    meter_element = None
            else:
                meter_element = element_by_id.get(entry.element_id, None)

            meter_kind: RmsPhysicalMeterKind | None
            if isinstance(meter_element, StaVmea):
                meter_kind = RmsPhysicalMeterKind.VOLTAGE
            else:
                if isinstance(meter_element, StaImea):
                    meter_kind = RmsPhysicalMeterKind.CURRENT
                else:
                    if isinstance(meter_element, StaPqmea):
                        meter_kind = RmsPhysicalMeterKind.POWER
                    else:
                        if isinstance(meter_element, ElmPhi) or is_pll_slot:
                            meter_kind = RmsPhysicalMeterKind.PHASE_LOCKED_LOOP
                        else:
                            meter_kind = None

            if meter_kind is None:
                pass
            else:
                # Early materialization owns the native meter equations, so it
                # must retain every exact BlkSig consumer. The late-binding
                # helper deliberately excludes equipment-owned signals, which
                # would incorrectly discard complete meters before the runtime
                # adapter has removed their provisional fallback ownership.
                targets_by_alias: Dict[str, List[Var]] = (
                    _build_exact_meter_targets(
                        dgs_circuit=dgs_circuit,
                        source_slot_id=entry.slot_id,
                        child_block_by_slot_id=(
                            direct_result.child_block_by_slot_id
                        ),
                    )
                )
                target_names: List[str] = (
                    _get_native_source_target_signal_names(
                        dgs_circuit=dgs_circuit,
                        source_slot_id=entry.slot_id,
                    )
                )
                if len(target_names) == 0:
                    implicit_target_name: str | None = (
                        implicit_target_by_slot.get(entry.slot_id, None)
                    )
                    if implicit_target_name is None:
                        target_names = list(targets_by_alias.keys())
                    else:
                        target_names = list((implicit_target_name,))
                else:
                    pass

                connections: List[_DgsRmsMeasurementConnection] = list()
                target_name: str
                target_var: Var
                for target_name in target_names:
                    target_vars: List[Var] | None = targets_by_alias.get(
                        target_name,
                        None,
                    )
                    if target_vars is None:
                        pass
                    else:
                        for target_var in target_vars:
                            connections.append(_DgsRmsMeasurementConnection(
                                alias_name=target_name,
                                target_var=target_var,
                            ))

                if len(connections) == 0:
                    pass
                else:
                    use_stationary_reference: bool = False
                    if isinstance(meter_element, ElmPhi):
                        use_stationary_reference = (
                            meter_element.pbusbar is None
                            or str(meter_element.pbusbar).strip() == ""
                        )
                    else:
                        if is_pll_slot and isinstance(host_device, VSC):
                            use_stationary_reference = (
                                host_device.control1 is ConverterControlType.Pac
                            )
                        else:
                            pass
                    source_fid: str
                    if meter_element is None:
                        source_fid = entry.slot_id
                    else:
                        source_fid = str(meter_element.ID)
                    source_name: str = _get_veragrid_meter_name(
                        meter_kind=meter_kind,
                        source_fid=source_fid,
                    )
                    specs.append(_DgsRmsMeasurementSpec(
                        source_fid=source_fid,
                        source_name=source_name,
                        meter_kind=meter_kind,
                        meter_element=meter_element,
                        connections=connections,
                        use_stationary_reference=use_stationary_reference,
                    ))
    return specs


def _get_native_dgs_measurement_physical_references(
        spec: _DgsRmsMeasurementSpec,
) -> List[VarPowerFlowReferenceType]:
    """Return physical inputs required by one early native measurement.

    :param spec: Resolved native measurement specification.
    :return: Ordered physical power-flow references.
    """
    terminal_side: RmsTerminalSide | None = None
    connection: _DgsRmsMeasurementConnection

    # Native meters may export non-terminal signals first, such as ``fe``
    # before ``u``. Inspect every exact endpoint until one identifies the
    # physical side instead of making the result depend on DGS row order.
    for connection in spec.connections:
        candidate_reference: object = connection.target_var.ref
        if isinstance(candidate_reference, VarPowerFlowReferenceType):
            candidate_terminal_side: RmsTerminalSide | None = (
                _classify_rms_measurement_terminal(
                reference=candidate_reference,
                )
            )
            if terminal_side is None and candidate_terminal_side is not None:
                terminal_side = candidate_terminal_side
            else:
                pass
        else:
            pass

    if terminal_side is None:
        references: List[VarPowerFlowReferenceType] = list()
    else:
        if spec.meter_kind is RmsPhysicalMeterKind.POWER:
            references = _get_rms_terminal_physical_references(
                block_type=BlockType.MEASUREMENTS_P_Q,
                terminal_side=terminal_side,
                is_dc_terminal=False,
            )
        else:
            if spec.meter_kind is RmsPhysicalMeterKind.VOLTAGE:
                references = _get_rms_terminal_physical_references(
                    block_type=BlockType.MEASUREMENTS_VOLTAGE_FROM_POLAR,
                    terminal_side=terminal_side,
                    is_dc_terminal=False,
                )
            else:
                if spec.meter_kind is RmsPhysicalMeterKind.PHASE_LOCKED_LOOP:
                    references = _get_rms_terminal_physical_references(
                        block_type=BlockType.MEASUREMENTS_PLL,
                        terminal_side=terminal_side,
                        is_dc_terminal=False,
                    )
                else:
                    references = list()

    # Some controller aliases use COSPHI/SINPHI references, whose terminal
    # classification identifies the side but not the voltage-angle prerequisite.
    if (
            spec.meter_kind is RmsPhysicalMeterKind.PHASE_LOCKED_LOOP
            and not spec.use_stationary_reference
            and terminal_side is not None
    ):
        if terminal_side is RmsTerminalSide.FROM:
            references = list((VarPowerFlowReferenceType.Vaf,))
        else:
            if terminal_side is RmsTerminalSide.TO:
                references = list((VarPowerFlowReferenceType.Vat,))
            else:
                references = list((VarPowerFlowReferenceType.Va,))
    else:
        pass
    return references


def _build_native_dgs_measurement_expression(
        spec: _DgsRmsMeasurementSpec,
        alias_name: str,
        physical_inputs_by_reference: Dict[VarPowerFlowReferenceType, Var],
        circuit: MultiCircuit,
) -> Expr | None:
    """Build one native meter output expression from physical placeholders.

    :param spec: Resolved native measurement specification.
    :param alias_name: Exact producer alias connected to a controller input.
    :param physical_inputs_by_reference: Canonical early physical inputs.
    :param circuit: Circuit supplying system power and frequency bases.
    :return: Native output expression, or ``None`` when unsupported.
    """
    normalized_name: str = alias_name.strip().lower()
    expression: Expr | None = None
    references: List[VarPowerFlowReferenceType] = (
        _get_native_dgs_measurement_physical_references(spec=spec)
    )

    if spec.meter_kind is RmsPhysicalMeterKind.POWER:
        power_meter: StaPqmea | None
        if isinstance(spec.meter_element, StaPqmea):
            power_meter = spec.meter_element
        else:
            power_meter = None
        if power_meter is None or power_meter.outserv != 0:
            pass
        else:
            orientation: float = 1.0 if power_meter.i_orient == 0 else -1.0
            if power_meter.Snom > 0.0 and circuit.Sbase > 0.0:
                power_scale: float = float(circuit.Sbase) / float(power_meter.Snom)
            else:
                power_scale = 1.0
            if normalized_name.startswith("q") and len(references) > 1:
                physical_power: Var | None = physical_inputs_by_reference.get(
                    references[1],
                    None,
                )
            else:
                if len(references) > 0:
                    physical_power = physical_inputs_by_reference.get(
                        references[0],
                        None,
                    )
                else:
                    physical_power = None
            if physical_power is None:
                pass
            else:
                expression = Const(orientation * power_scale) * physical_power
    else:
        if spec.meter_kind is RmsPhysicalMeterKind.VOLTAGE:
            if len(references) < 2:
                pass
            else:
                voltage_magnitude: Var | None = physical_inputs_by_reference.get(
                    references[0],
                    None,
                )
                voltage_angle: Var | None = physical_inputs_by_reference.get(
                    references[1],
                    None,
                )
                if voltage_magnitude is None or voltage_angle is None:
                    pass
                else:
                    if "u1r" in normalized_name or normalized_name == "ur":
                        expression = voltage_magnitude * sym.cos(voltage_angle)
                    else:
                        if "u1i" in normalized_name or normalized_name == "ui":
                            expression = voltage_magnitude * sym.sin(voltage_angle)
                        else:
                            if normalized_name.startswith("cosphi"):
                                expression = sym.cos(voltage_angle)
                            else:
                                if normalized_name.startswith("sinphi"):
                                    expression = sym.sin(voltage_angle)
                                else:
                                    if "phi" in normalized_name:
                                        expression = voltage_angle
                                    else:
                                        if normalized_name in ("fe", "fref"):
                                            expression = Const(1.0)
                                        else:
                                            if (
                                                    normalized_name.startswith("f")
                                                    or "_hz" in normalized_name
                                            ):
                                                expression = Const(float(circuit.fBase))
                                            else:
                                                expression = voltage_magnitude
        else:
            if spec.meter_kind is RmsPhysicalMeterKind.PHASE_LOCKED_LOOP:
                if spec.use_stationary_reference:
                    if normalized_name.startswith("cosphi"):
                        expression = Const(1.0)
                    else:
                        if normalized_name.startswith("sinphi"):
                            expression = Const(0.0)
                        else:
                            if normalized_name == "fmeas":
                                expression = Const(1.0)
                            else:
                                if "hz" in normalized_name:
                                    expression = Const(float(circuit.fBase))
                                else:
                                    pass
                else:
                    if len(references) == 0:
                        voltage_angle = None
                    else:
                        voltage_angle = physical_inputs_by_reference.get(
                            references[0],
                            None,
                        )
                    if voltage_angle is None:
                        pass
                    else:
                        if normalized_name.startswith("cosphi"):
                            expression = sym.cos(voltage_angle)
                        else:
                            if normalized_name.startswith("sinphi"):
                                expression = sym.sin(voltage_angle)
                            else:
                                pass
            else:
                pass
    return expression


def _materialize_native_dgs_rms_measurements(
        block: Block,
        circuit: MultiCircuit,
        native_specs: List[_DgsRmsMeasurementSpec],
        physical_inputs_by_reference: Dict[VarPowerFlowReferenceType, Var],
        var_factory: VarFactory,
) -> Set[int]:
    """Create native early measurements and connect exact controller inputs.

    :param block: Imported controller root receiving measurement children.
    :param circuit: Circuit supplying native measurement bases.
    :param native_specs: Exact native meter construction specifications.
    :param physical_inputs_by_reference: Shared physical placeholder lookup.
    :param var_factory: Factory owning early measurement variables.
    :return: Object identities of controller inputs replaced successfully.
    """
    replaced_input_object_ids: Set[int] = set()
    spec: _DgsRmsMeasurementSpec
    for spec in native_specs:
        required_references: List[VarPowerFlowReferenceType] = (
            _get_native_dgs_measurement_physical_references(spec=spec)
        )
        required_reference: VarPowerFlowReferenceType
        for required_reference in required_references:
            _get_or_create_dgs_physical_input(
                block=block,
                reference=required_reference,
                physical_inputs_by_reference=physical_inputs_by_reference,
                var_factory=var_factory,
            )

        measurement_block: Block = Block(name=spec.source_name)
        measurement_block.in_vars = list(
            physical_inputs_by_reference[reference]
            for reference in required_references
        )
        connected_count: int = 0
        output_by_alias: Dict[str, Var] = dict()
        connection: _DgsRmsMeasurementConnection
        for connection in spec.connections:
            output_var: Var | None = output_by_alias.get(
                connection.alias_name,
                None,
            )
            if output_var is None:
                source_expression: Expr | None = (
                    _build_native_dgs_measurement_expression(
                        spec=spec,
                        alias_name=connection.alias_name,
                        physical_inputs_by_reference=physical_inputs_by_reference,
                        circuit=circuit,
                    )
                )
                if source_expression is None:
                    pass
                else:
                    # The exact DGS consumer variable becomes the measurement
                    # output. Reusing it prevents a same-name second UID from
                    # appearing when the template is wrapped or duplicated.
                    output_var = connection.target_var
                    _remove_meter_target_fallback_ownership(
                        host_model=block,
                        target_var=output_var,
                    )
                    measurement_block.algebraic_vars.append(output_var)
                    measurement_block.out_vars.append(output_var)
                    measurement_block.algebraic_eqs.append(
                        output_var - source_expression
                    )
                    output_by_alias[connection.alias_name] = output_var
                    replaced_input_object_ids.add(id(connection.target_var))
                    connected_count += 1
            else:
                # One native output can feed several exact endpoints. Remove
                # every additional receiver fallback before atomically joining
                # its complete block interface to the canonical output UID.
                _remove_meter_target_fallback_ownership(
                    host_model=block,
                    target_var=connection.target_var,
                )
                block.update_model(
                    old=connection.target_var,
                    new=output_var,
                )
                replaced_input_object_ids.add(id(connection.target_var))
                connected_count += 1

        if connected_count == 0:
            pass
        else:
            block.children.append(measurement_block)
    return replaced_input_object_ids


def _add_required_dgs_rms_measurements(
        block: Block,
        host_device: DynamicDevice,
        circuit: MultiCircuit,
        native_specs: List[_DgsRmsMeasurementSpec],
) -> None:
    """Materialize and connect measurements required by one imported model.

    :param block: Imported DGS composite root.
    :param host_device: Exact static device that owns the final RMS template.
    :param circuit: Circuit providing the system power and frequency bases.
    :param native_specs: Exact native meters resolved from the DGS graph.
    :return: None.
    """
    measurement_var_factory: VarFactory = VarFactory()
    physical_inputs_by_reference: Dict[VarPowerFlowReferenceType, Var] = dict()
    replaced_input_object_ids: Set[int] = (
        _materialize_native_dgs_rms_measurements(
            block=block,
            circuit=circuit,
            native_specs=native_specs,
            physical_inputs_by_reference=physical_inputs_by_reference,
            var_factory=measurement_var_factory,
        )
    )
    unconnected_inputs: List[Tuple[Block, Var]] = (
        _collect_unconnected_dgs_child_inputs(block=block)
    )
    physical_input_object_ids: Set[int] = set(
        id(physical_input)
        for physical_input in physical_inputs_by_reference.values()
    )
    unconnected_inputs = list(
        input_entry
        for input_entry in unconnected_inputs
        if id(input_entry[1]) not in physical_input_object_ids
    )
    inputs_by_terminal: Dict[RmsTerminalSide, List[Tuple[Block, Var]]] = dict((
        (RmsTerminalSide.FROM, list()),
        (RmsTerminalSide.TO, list()),
        (RmsTerminalSide.BUS, list()),
    ))
    owner_block: Block
    input_var: Var
    for owner_block, input_var in unconnected_inputs:
        if isinstance(input_var.ref, VarPowerFlowReferenceType):
            terminal_side: RmsTerminalSide | None = (
                _classify_rms_measurement_terminal(reference=input_var.ref)
            )
            if terminal_side is None:
                pass
            else:
                inputs_by_terminal[terminal_side].append((owner_block, input_var))
        else:
            pass

    terminal_side: RmsTerminalSide
    terminal_inputs: List[Tuple[Block, Var]]
    for terminal_side, terminal_inputs in inputs_by_terminal.items():
        if len(terminal_inputs) == 0:
            pass
        else:
            if isinstance(host_device, BranchParent):
                if terminal_side is RmsTerminalSide.FROM:
                    terminal_bus = host_device.bus_from
                else:
                    if terminal_side is RmsTerminalSide.TO:
                        terminal_bus = host_device.bus_to
                    else:
                        terminal_bus = None
            else:
                if isinstance(host_device, InjectionParent):
                    if terminal_side is RmsTerminalSide.BUS:
                        terminal_bus = host_device.bus
                    else:
                        terminal_bus = None
                else:
                    terminal_bus = None

            if terminal_bus is None:
                pass
            else:
                terminal_vars: List[Var] = list(
                    input_entry[1] for input_entry in terminal_inputs
                )
                measurement_types: List[BlockType] = (
                    find_measurements_for_inputs_group(
                        bus=terminal_bus,
                        inputs=terminal_vars,
                    )
                )
                measurement_type: BlockType
                for measurement_type in measurement_types:
                    # Allocate every prerequisite before invoking the builder.
                    # A single canonical input is reused across all measurements
                    # that observe the same physical terminal quantity.
                    required_references: List[VarPowerFlowReferenceType] = (
                        _get_rms_terminal_physical_references(
                            block_type=measurement_type,
                            terminal_side=terminal_side,
                            is_dc_terminal=terminal_bus.is_dc,
                        )
                    )
                    required_reference: VarPowerFlowReferenceType
                    for required_reference in required_references:
                        _get_or_create_dgs_physical_input(
                            block=block,
                            reference=required_reference,
                            physical_inputs_by_reference=physical_inputs_by_reference,
                            var_factory=measurement_var_factory,
                        )
                    measurement_block: Block | None = _build_dgs_rms_measurement_block(
                        block_type=measurement_type,
                        terminal_side=terminal_side,
                        is_dc_terminal=terminal_bus.is_dc,
                        physical_inputs_by_reference=physical_inputs_by_reference,
                        var_factory=measurement_var_factory,
                    )
                    if measurement_block is None:
                        pass
                    else:
                        measurement_output: Var
                        for measurement_output in measurement_block.out_vars:
                            for owner_block, input_var in terminal_inputs:
                                if (
                                        input_var.ref == measurement_output.ref
                                        and input_var is not measurement_output
                                ):
                                    owner_block.update_model(
                                        old=input_var,
                                        new=measurement_output,
                                    )
                                    replaced_input_object_ids.add(id(input_var))
                                else:
                                    pass
                        block.children.append(measurement_block)

    if len(replaced_input_object_ids) == 0:
        pass
    else:
        block.in_vars = list(
            root_input
            for root_input in block.in_vars
            if id(root_input) not in replaced_input_object_ids
        )


def _clone_import_block(block: Block) -> Block:
    """
    Clone one imported symbolic block for one selected target template.

    :param block: Imported symbolic block.
    :return: Deep-copied block.
    """
    cloned_block: Block = copy.deepcopy(block)
    _apply_composite_child_interface_if_missing(cloned_block)
    return cloned_block


def _build_selected_template_from_import_entry(
        entry: DynamicModelImportEntry,
        selection_request: DynamicModelImportSelectionRequest,
        clone_source_block: bool = True,
) -> RmsModelTemplate | EmtModelTemplate | None:
    """
    Materialize one selected reusable template using the user import choices.

    :param entry: Imported entry.
    :param selection_request: Explicit user import request.
    :param clone_source_block: Clone the source block for reusable GUI bundles.
    :return: Materialized RMS or EMT reusable template, or ``None``.
    """
    source_block: Block | None = entry.get_source_block()
    cloned_block: Block
    template_name: str = entry.get_display_name()
    template_comment: str = f"{entry.get_source_tpe().value} dynamic model: {template_name}"
    emt_template: EmtModelTemplate
    rms_template: RmsModelTemplate

    if source_block is None:
        return None
    else:
        pass

    if clone_source_block:
        cloned_block = _clone_import_block(source_block)
    else:
        # A normal massive DGS open owns an ephemeral bundle. Transfer its
        # symbolic block into the circuit wrapper instead of retaining a second
        # deep copy of every OEM model at peak memory.
        cloned_block = source_block
        _apply_composite_child_interface_if_missing(cloned_block)
    if selection_request.get_target_domain() == DynamicSimulationMode.EMT:
        emt_template = EmtModelTemplate(name=template_name)
        emt_template.tpe = selection_request.get_device_tpe()
        emt_template.block = cloned_block
        emt_template.name = template_name
        emt_template.comment = template_comment
        return emt_template
    else:
        if selection_request.get_target_domain() == DynamicSimulationMode.RMS:
            rms_template = RmsModelTemplate(name=template_name)
            rms_template.tpe = selection_request.get_device_tpe()
            rms_template.block = cloned_block
            rms_template.name = template_name
            rms_template.comment = template_comment
            if (
                    entry.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs
                    and selection_request.get_device_tpe() == DeviceType.VscDevice
                    and (
                        is_dgs_elmvsc_slot_contract(cloned_block)
                        or is_dgs_elmvscmono_slot_contract(cloned_block)
                    )
            ):
                if is_dgs_elmvscmono_slot_contract(cloned_block):
                    adapted_template: RmsModelTemplate | None = (
                        build_dgs_elmvscmono_rms_runtime_template(
                            control_template=rms_template,
                            clone_control_block=clone_source_block,
                        )
                    )
                else:
                    adapted_template = (
                        build_dgs_elmvsc_rms_runtime_template(
                            control_template=rms_template,
                            clone_control_block=clone_source_block,
                        )
                    )
                if adapted_template is None:
                    return rms_template
                else:
                    return adapted_template
            else:
                # Detached catalogue blocks do not carry the transient FID
                # relation required by equipment adapters. Keep them generic
                # and fail closed until a direct DGS conversion supplies it.
                return rms_template
        else:
            return None


def _build_dgs_direct_runtime_template(
        source_block: Block,
        circuit: MultiCircuit,
        template_name: str,
        target_domain: DynamicSimulationMode,
        device_tpe: DeviceType,
        adapter_kind: _DgsRuntimeAdapterKind | None,
        direct_result: DgsDirectRootBuildResult | None,
        source_svs: ElmSvs | None,
        host_device: DynamicDevice | None,
        native_measurement_specs: List[_DgsRmsMeasurementSpec],
) -> RmsModelTemplate | EmtModelTemplate:
    """Wrap one directly materialized DGS block in its final template.

    The caller transfers ownership of ``source_block``.  No catalogue entry,
    serialization payload or duplicate symbolic graph is created between the
    parser and the final ``MultiCircuit`` template.

    :param source_block: Direct root block owned by this conversion.
    :param circuit: Destination circuit supplying system measurement bases.
    :param template_name: Final reusable-template display name.
    :param target_domain: Explicit RMS or EMT destination.
    :param device_tpe: Exact physical host family or generic dynamic host.
    :param adapter_kind: Import-local runtime adapter classification.
    :param direct_result: Transient direct-root conversion context, if present.
    :param source_svs: Exact transient ElmSvs source, when adapting an SVC.
    :param host_device: Exact static host used to resolve measurement terminals.
    :param native_measurement_specs: Native meters resolved from the DGS graph.
    :return: Final RMS or EMT template ready for circuit registration.
    """
    # Type only child inputs whose DGS signal has no internal producer. The
    # synthesized root interface then exposes the same typed Var objects.
    _assign_dgs_external_input_references(
        block=source_block,
        device_tpe=device_tpe,
    )

    # Native PowerFactory meters are not executable ElmDsl children. Replace
    # their missing signals with explicit VeraGrid measurements before the root
    # interface is finalized for the editor and runtime adapter.
    if (
            target_domain == DynamicSimulationMode.RMS
            and host_device is not None
    ):
        _add_required_dgs_rms_measurements(
            block=source_block,
            host_device=host_device,
            circuit=circuit,
            native_specs=native_measurement_specs,
        )
    else:
        pass

    # Complete only the public composite ports already owned by the child graph.
    _apply_composite_child_interface_if_missing(block=source_block)
    source_block.name = template_name
    template_comment: str = (
        f"PowerFactory DGS dynamic model: {template_name}"
    )

    if target_domain == DynamicSimulationMode.EMT:
        emt_template: EmtModelTemplate = EmtModelTemplate(name=template_name)
        emt_template.tpe = device_tpe
        emt_template.block = source_block
        emt_template.name = template_name
        emt_template.comment = template_comment
        result: RmsModelTemplate | EmtModelTemplate = emt_template
    else:
        rms_template: RmsModelTemplate = RmsModelTemplate(name=template_name)
        rms_template.tpe = device_tpe
        rms_template.block = source_block
        rms_template.name = template_name
        rms_template.comment = template_comment
        adapted_template: RmsModelTemplate | None

        # Runtime wrappers consume the same block directly; cloning here would
        # create the forbidden second semantic model during a massive import.
        if adapter_kind == _DgsRuntimeAdapterKind.VSC_MONOPOLAR:
            adapted_template = build_dgs_elmvscmono_rms_runtime_template(
                control_template=rms_template,
                clone_control_block=False,
            )
        else:
            if adapter_kind == _DgsRuntimeAdapterKind.VSC_BIPOLAR:
                adapted_template = build_dgs_elmvsc_rms_runtime_template(
                    control_template=rms_template,
                    clone_control_block=False,
                )
            else:
                if (
                        adapter_kind
                        == _DgsRuntimeAdapterKind.SYNCHRONOUS_MACHINE_PENDING
                ):
                    adapted_template = build_dgs_elmsym_rms_runtime_template(
                        control_template=rms_template,
                        clone_control_block=False,
                        direct_result=direct_result,
                    )
                else:
                    if adapter_kind == _DgsRuntimeAdapterKind.STATIC_GENERATOR:
                        adapted_template = (
                            build_dgs_elmgenstat_rms_runtime_template(
                                control_template=rms_template,
                                clone_control_block=False,
                                direct_result=direct_result,
                            )
                        )
                    else:
                        if (
                                adapter_kind
                                == _DgsRuntimeAdapterKind.STATIC_VAR_SYSTEM
                        ):
                            adapted_template = (
                                build_dgs_elmsvs_rms_runtime_template(
                                    control_template=rms_template,
                                    clone_control_block=False,
                                    direct_result=direct_result,
                                    source_svs=source_svs,
                                )
                            )
                        else:
                            adapted_template = rms_template

        if adapted_template is None:
            # Preserve the declarative root for inspection, but never expose an
            # incomplete physical adapter as assignable equipment.
            rms_template.tpe = DeviceType.DynamicModelHostDevice
            result = rms_template
        else:
            result = adapted_template
    return result


def build_dynamic_import_template_fingerprint(
        template_obj: RmsModelTemplate | EmtModelTemplate,
) -> str | None:
    """
    Build a deterministic structural fingerprint for one reusable template.

    :param template_obj: Materialized reusable template.
    :return: SHA-256 fingerprint, or ``None`` when canonicalization fails.
    """
    fingerprint_block: Block = copy.copy(template_obj.block)
    fingerprint_block.name = "__veragrid_dynamic_template_root__"
    if isinstance(template_obj, RmsModelTemplate):
        target_domain: DynamicSimulationMode = DynamicSimulationMode.RMS
    else:
        target_domain = DynamicSimulationMode.EMT

    try:
        payload_text: str = _build_user_dynamic_template_payload_text(
            block=fingerprint_block,
            template_name="__veragrid_dynamic_template__",
            target_domain=target_domain,
            device_tpe=template_obj.tpe,
        )
    except (KeyError, TypeError, ValueError):
        return None
    else:
        return hashlib.sha256(payload_text.encode("utf-8")).hexdigest()


def _build_source_qualified_dynamic_import_template_name(
        entry: DynamicModelImportEntry,
        existing_names: Set[str],
) -> str:
    """
    Build a readable unique name for a non-equivalent name collision.

    :param entry: Imported entry whose display name already exists.
    :param existing_names: Names already present in the target domain.
    :return: Unique human-readable template name.
    """
    base_name: str = entry.get_display_name()
    key_parts: List[str] = entry.get_unique_key().split("|")
    source_provenance: DynamicModelImportSourceProvenance | None = (
        entry.get_source_provenance()
    )
    source_label: str = "imported variant"
    candidate_name: str
    suffix_index: int = 2

    if source_provenance is None:
        if len(key_parts) >= 3 and key_parts[0] == "dgs-slot":
            source_label = "child slot"
        else:
            if len(key_parts) >= 2 and key_parts[0].startswith("dgs-"):
                source_label = "DGS variant"
            else:
                pass
    else:
        # Stable FIDs belong in metadata; collision names remain readable by
        # presenting the exported root/slot labels to humans.
        if source_provenance.get_root_name().casefold() == base_name.casefold():
            if source_provenance.get_slot_name() is None:
                source_label = "root variant"
            else:
                source_label = source_provenance.get_slot_name()
        else:
            source_label = source_provenance.get_root_name()

    candidate_name = f"{base_name} [{source_label}]"
    while candidate_name in existing_names:
        candidate_name = f"{base_name} [{source_label} {suffix_index}]"
        suffix_index += 1

    return candidate_name


def _append_dynamic_model_import_entry_result(
        report: DynamicModelImportReport | None,
        entry: DynamicModelImportEntry,
        selection_request: DynamicModelImportSelectionRequest,
        final_name: str | None,
        status: DynamicModelImportEntryStatus,
        message: str,
) -> DynamicModelImportEntryResult | None:
    """
    Append one structured result when the caller requested reporting.

    :param report: Optional aggregate report.
    :param entry: Processed source catalogue entry.
    :param selection_request: Explicit target-domain selection.
    :param final_name: Final circuit template name, when available.
    :param status: Explicit processing status.
    :param message: Human-readable outcome diagnostic.
    :return: Appended result or ``None`` when reporting is disabled.
    """
    if report is None:
        entry_result: DynamicModelImportEntryResult | None = None
    else:
        entry_result = DynamicModelImportEntryResult(
            unique_key=entry.get_unique_key(),
            requested_name=entry.get_display_name(),
            final_name=final_name,
            domain=selection_request.get_target_domain(),
            status=status,
            source_provenance=entry.get_source_provenance(),
            message=message,
        )
        report.add_entry_result(entry_result=entry_result)

    return entry_result


def build_dgs_dynamic_association_records(
        report: DynamicModelImportReport,
) -> List[DgsDynamicAssociationRecord]:
    """
    Build the source association records from one DGS import.

    The records preserve the DGS composite hierarchy and final catalogue
    identity without activating a runtime dynamic model during file import.

    :param report: Completed massive-import report.
    :return: Ordered source association records.
    """
    records: List[DgsDynamicAssociationRecord] = list()
    root_template_name_by_dgs_id: Dict[str, str] = dict()
    entry_result: DynamicModelImportEntryResult
    source_provenance: DynamicModelImportSourceProvenance | None
    final_template_name: str | None

    # Resolve the reusable composite template once per exact ElmComp FID.  The
    # root result and its physical pElm slot results are deliberately separate
    # catalogue entries, so this first pass provides the safe join key between
    # them without relying on display names.
    for entry_result in report.get_entry_results():
        source_provenance = entry_result.get_source_provenance()
        final_template_name = entry_result.get_final_name()
        is_root_result: bool = (
            source_provenance is not None
            and source_provenance.get_slot_index() is None
            and final_template_name is not None
        )
        if (
                is_root_result
                and source_provenance is not None
                and final_template_name is not None
        ):
            root_template_name_by_dgs_id[
                source_provenance.get_root_dgs_id()
            ] = final_template_name
        else:
            pass

    for entry_result in report.get_entry_results():
        source_provenance = entry_result.get_source_provenance()
        if source_provenance is None:
            pass
        else:
            final_template_name = entry_result.get_final_name()
            source_element_class: str | None = (
                source_provenance.get_source_element_class()
            )
            is_physical_root_slot: bool = (
                source_provenance.get_slot_index() is not None
                and source_element_class is not None
                and source_element_class not in {"ElmDsl", "ElmComp"}
            )
            if final_template_name is None and is_physical_root_slot:
                # A physical pElm is a source reference, not a reusable template.
                # Carry the owning root-template identity onto its association
                # record so consumers can answer which composite controls the
                # exact equipment FID while keeping activation as a distinct,
                # explicitly validated runtime step.
                final_template_name = root_template_name_by_dgs_id.get(
                    source_provenance.get_root_dgs_id(),
                    None,
                )
            else:
                pass
            records.append(
                DgsDynamicAssociationRecord(
                    unique_key=entry_result.get_unique_key(),
                    root_dgs_id=source_provenance.get_root_dgs_id(),
                    root_name=source_provenance.get_root_name(),
                    root_typ_id=source_provenance.get_root_typ_id(),
                    slot_dgs_id=source_provenance.get_slot_dgs_id(),
                    slot_name=source_provenance.get_slot_name(),
                    slot_index=source_provenance.get_slot_index(),
                    slot_element=source_provenance.get_slot_element(),
                    slot_filter=source_provenance.get_slot_filter(),
                    source_element_dgs_id=(
                        source_provenance.get_source_element_dgs_id()
                    ),
                    source_element_name=source_provenance.get_source_element_name(),
                    source_element_class=(
                        source_provenance.get_source_element_class()
                    ),
                    final_template_name=final_template_name,
                    role=infer_dgs_dynamic_association_role(
                        slot_index=source_provenance.get_slot_index(),
                        source_element_class=(
                            source_provenance.get_source_element_class()
                        ),
                        slot_filter=source_provenance.get_slot_filter(),
                    ),
                    target_domain=entry_result.get_domain(),
                    status=entry_result.get_status(),
                )
            )

    return records


def add_dynamic_import_selection_requests_to_circuit(
        circuit: MultiCircuit,
        bundle: DynamicModelImportBundle,
        selection_requests: Sequence[DynamicModelImportSelectionRequest],
        logger: Logger,
        progress_callback: Callable[[int, str], None] | None = None,
        user_root_folder: str | None = None,
        rename_conflicting_templates: bool = False,
        persist_to_user_catalog: bool = False,
        report: DynamicModelImportReport | None = None,
        template_fingerprint_by_object_id: Dict[int, str | None] | None = None,
        clone_source_blocks: bool = True,
) -> int:
    """
    Add the selected imported dynamic models to the circuit using explicit metadata.

    :param circuit: Target circuit.
    :param bundle: Imported dynamic-model bundle.
    :param selection_requests: Explicit selected import requests.
    :param logger: Logger receiving duplicate or importability diagnostics.
    :param progress_callback: Optional UI progress callback.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param rename_conflicting_templates: Rename non-equivalent name collisions instead of dropping them.
    :param persist_to_user_catalog: Legacy request retained for API compatibility;
        executable catalogue persistence is refused.
    :param report: Optional structured outcome report populated entry by entry.
    :param template_fingerprint_by_object_id: Optional identity cache shared
        with deferred DGS persistence.
    :param clone_source_blocks: Clone bundle blocks before installation. Disable
        only when the caller owns and consumes one ephemeral massive bundle.
    :return: Number of templates added to the circuit.
    """
    request_by_entry_key: Dict[str, DynamicModelImportSelectionRequest] = dict()
    existing_rms_names: Set[str] = set()
    existing_emt_names: Set[str] = set()
    existing_rms_templates_by_fingerprint: Dict[str, RmsModelTemplate] = dict()
    existing_emt_templates_by_fingerprint: Dict[str, EmtModelTemplate] = dict()
    processed_entry_keys: Set[str] = set()
    entry: DynamicModelImportEntry
    selection_request: DynamicModelImportSelectionRequest
    template_obj: RmsModelTemplate | EmtModelTemplate | None
    total_selected_count: int
    processed_selected_count: int = 0
    template_deduplicated: bool
    template_renamed: bool
    outcome_message: str
    fingerprint_cache: Dict[int, str | None]

    if persist_to_user_catalog:
        logger.add_warning(
            msg="Executable dynamic-model catalogue persistence refused",
            value=(
                user_root_folder
                if user_root_folder is not None
                else "The declarative template remains registered in MultiCircuit"
            ),
        )
    else:
        pass

    if template_fingerprint_by_object_id is None:
        fingerprint_cache = dict()
    else:
        fingerprint_cache = template_fingerprint_by_object_id

    for selection_request in selection_requests:
        entry_key: str = selection_request.get_entry_key()
        if entry_key in request_by_entry_key:
            logger.add_info(
                msg="Duplicate dynamic model selection ignored",
                value=entry_key,
            )
        else:
            request_by_entry_key[entry_key] = selection_request

    total_selected_count = len(request_by_entry_key)

    for template in circuit.rms_models:
        existing_rms_names.add(template.name)
        template_fingerprint: str | None = build_dynamic_import_template_fingerprint(template)
        fingerprint_cache[id(template)] = template_fingerprint
        if template_fingerprint is not None:
            existing_rms_templates_by_fingerprint[template_fingerprint] = template
        else:
            pass

    for template in circuit.emt_models:
        existing_emt_names.add(template.name)
        template_fingerprint = build_dynamic_import_template_fingerprint(template)
        fingerprint_cache[id(template)] = template_fingerprint
        if template_fingerprint is not None:
            existing_emt_templates_by_fingerprint[template_fingerprint] = template
        else:
            pass

    added_count: int = 0

    for entry in bundle.get_entries():
        entry.set_installed_template(None)
        selection_request = request_by_entry_key.get(entry.get_unique_key(), None)

        if selection_request is None or entry.get_unique_key() in processed_entry_keys:
            if selection_request is None:
                pass
            else:
                logger.add_info(
                    msg="Duplicate dynamic model catalogue entry ignored",
                    value=entry.get_unique_key(),
                )
                _append_dynamic_model_import_entry_result(
                    report=report,
                    entry=entry,
                    selection_request=selection_request,
                    final_name=None,
                    status=DynamicModelImportEntryStatus.Skipped,
                    message="Duplicate catalogue entry key ignored",
                )
        else:
            processed_entry_keys.add(entry.get_unique_key())

            processed_selected_count += 1
            if total_selected_count == 0:
                pass
            else:
                _emit_dynamic_model_import_progress(
                    progress_callback,
                    int(round(60.0 * float(processed_selected_count - 1) / float(total_selected_count))),
                    f"Adding selected dynamic models: {processed_selected_count}/{total_selected_count}",
                )

            outcome_message = ""
            try:
                template_obj = _build_selected_template_from_import_entry(
                    entry=entry,
                    selection_request=selection_request,
                    clone_source_block=clone_source_blocks,
                )
            except Exception as exc:
                template_obj = None
                outcome_message = str(exc)
                logger.add_warning(
                    msg="Dynamic model entry skipped after a materialization error",
                    value=f"{entry.get_display_name()}: {exc}",
                )

            if template_obj is None:
                logger.add_warning(msg="Dynamic model entry skipped because it is not importable", value=entry.get_display_name())
                if len(outcome_message) == 0:
                    outcome_message = "Source entry is not importable"
                else:
                    pass
                _append_dynamic_model_import_entry_result(
                    report=report,
                    entry=entry,
                    selection_request=selection_request,
                    final_name=None,
                    status=DynamicModelImportEntryStatus.Failed,
                    message=outcome_message,
                )
            else:
                template_added: bool = False
                template_deduplicated = False
                template_renamed = False
                outcome_message = "Template name already exists"
                template_fingerprint: str | None = build_dynamic_import_template_fingerprint(template_obj)
                fingerprint_cache[id(template_obj)] = template_fingerprint
                if isinstance(template_obj, RmsModelTemplate):
                    equivalent_rms_template: RmsModelTemplate | None = None
                    if template_fingerprint is None:
                        pass
                    else:
                        equivalent_rms_template = existing_rms_templates_by_fingerprint.get(
                            template_fingerprint,
                            None,
                        )

                    if rename_conflicting_templates and equivalent_rms_template is not None:
                        logger.add_info(
                            msg="Equivalent dynamic model entry deduplicated",
                            value=f"{template_obj.name} -> {equivalent_rms_template.name}",
                        )
                        entry.set_installed_template(equivalent_rms_template)
                        template_deduplicated = True
                        outcome_message = "Equivalent template reused by structural fingerprint"
                    else:
                        if template_obj.name in existing_rms_names:
                            if rename_conflicting_templates:
                                original_name: str = template_obj.name
                                template_obj.name = _build_source_qualified_dynamic_import_template_name(
                                    entry=entry,
                                    existing_names=existing_rms_names,
                                )
                                template_obj.block.name = template_obj.name
                                logger.add_info(
                                    msg="Dynamic model name collision renamed",
                                    value=f"{original_name} -> {template_obj.name}",
                                )
                                circuit.add_rms_model(template_obj)
                                existing_rms_names.add(template_obj.name)
                                template_added = True
                                template_renamed = True
                                outcome_message = f"Name collision renamed to {template_obj.name}"
                            else:
                                logger.add_warning(msg="Dynamic model entry skipped because the template name already exists", value=template_obj.name)
                        else:
                            circuit.add_rms_model(template_obj)
                            existing_rms_names.add(template_obj.name)
                            template_added = True
                            outcome_message = "Template added"

                    if template_added and template_fingerprint is not None:
                        existing_rms_templates_by_fingerprint[template_fingerprint] = template_obj
                    else:
                        pass
                else:
                    if isinstance(template_obj, EmtModelTemplate):
                        equivalent_emt_template: EmtModelTemplate | None = None
                        if template_fingerprint is None:
                            pass
                        else:
                            equivalent_emt_template = existing_emt_templates_by_fingerprint.get(
                                template_fingerprint,
                                None,
                            )

                        if rename_conflicting_templates and equivalent_emt_template is not None:
                            logger.add_info(
                                msg="Equivalent dynamic model entry deduplicated",
                                value=f"{template_obj.name} -> {equivalent_emt_template.name}",
                            )
                            entry.set_installed_template(equivalent_emt_template)
                            template_deduplicated = True
                            outcome_message = "Equivalent template reused by structural fingerprint"
                        else:
                            if template_obj.name in existing_emt_names:
                                if rename_conflicting_templates:
                                    original_name = template_obj.name
                                    template_obj.name = _build_source_qualified_dynamic_import_template_name(
                                        entry=entry,
                                        existing_names=existing_emt_names,
                                    )
                                    template_obj.block.name = template_obj.name
                                    logger.add_info(
                                        msg="Dynamic model name collision renamed",
                                        value=f"{original_name} -> {template_obj.name}",
                                    )
                                    circuit.add_emt_model(template_obj)
                                    existing_emt_names.add(template_obj.name)
                                    template_added = True
                                    template_renamed = True
                                    outcome_message = f"Name collision renamed to {template_obj.name}"
                                else:
                                    logger.add_warning(msg="Dynamic model entry skipped because the template name already exists", value=template_obj.name)
                            else:
                                circuit.add_emt_model(template_obj)
                                existing_emt_names.add(template_obj.name)
                                template_added = True
                                outcome_message = "Template added"

                        if template_added and template_fingerprint is not None:
                            existing_emt_templates_by_fingerprint[template_fingerprint] = template_obj
                        else:
                            pass
                    else:
                        outcome_message = "Materialized object has an unsupported template type"

                if template_added:
                    entry.set_installed_template(template_obj)
                    added_count += 1
                    if template_renamed:
                        entry_status: DynamicModelImportEntryStatus = DynamicModelImportEntryStatus.Renamed
                    else:
                        entry_status = DynamicModelImportEntryStatus.Added
                    _append_dynamic_model_import_entry_result(
                        report=report,
                        entry=entry,
                        selection_request=selection_request,
                        final_name=template_obj.name,
                        status=entry_status,
                        message=outcome_message,
                    )
                else:
                    if template_deduplicated:
                        deduplicated_template: RmsModelTemplate | EmtModelTemplate | None = (
                            entry.get_installed_template()
                        )
                        if deduplicated_template is None:
                            final_name: str | None = template_obj.name
                        else:
                            final_name = deduplicated_template.name
                        _append_dynamic_model_import_entry_result(
                            report=report,
                            entry=entry,
                            selection_request=selection_request,
                            final_name=final_name,
                            status=DynamicModelImportEntryStatus.Deduplicated,
                            message=outcome_message,
                        )
                    else:
                        _append_dynamic_model_import_entry_result(
                            report=report,
                            entry=entry,
                            selection_request=selection_request,
                            final_name=None,
                            status=DynamicModelImportEntryStatus.Skipped,
                            message=outcome_message,
                        )

            if total_selected_count == 0:
                pass
            else:
                _emit_dynamic_model_import_progress(
                    progress_callback,
                    int(round(60.0 * float(processed_selected_count) / float(total_selected_count))),
                    f"Adding selected dynamic models: {processed_selected_count}/{total_selected_count}",
                )

    _emit_dynamic_model_import_progress(progress_callback, 100, "Selected dynamic models imported")

    return added_count


def _find_exact_dgs_dynamic_host_devices(
        circuit: MultiCircuit,
        source_element_dgs_id: str,
        device_tpe: DeviceType,
        source_element_class: str | None,
) -> List[DynamicDevice]:
    """
    Find dynamic-capable devices by exact imported DGS FID and device type.

    Parallel-device suffixes are not expanded here. One PowerFactory composite
    does not define whether its states should be duplicated across VeraGrid
    parallel expansions, so such cases must remain unresolved and inspectable.

    :param circuit: Imported VeraGrid circuit.
    :param source_element_dgs_id: Authoritative source equipment FID.
    :param device_tpe: Expected VeraGrid host type.
    :param source_element_class: Authoritative PowerFactory equipment class.
    :return: Exact compatible dynamic devices.
    """
    matches: List[DynamicDevice] = list()
    candidate_obj: object
    candidate_device_types: List[DeviceType] = list([device_tpe])

    # Batteries inherit the Generator RMS contract but live in a separate
    # circuit collection. PowerFactory exports both wind/HVDC sources and
    # storage through ElmGenstat, so exact FID resolution must inspect both
    # compatible VeraGrid collections without relying on display categories.
    if (
            source_element_class == "ElmGenstat"
            and DeviceType.BatteryDevice not in candidate_device_types
    ):
        candidate_device_types.append(DeviceType.BatteryDevice)
    else:
        pass

    candidate_device_type: DeviceType
    for candidate_device_type in candidate_device_types:
        for candidate_obj in circuit.get_elements_by_type(
                device_type=candidate_device_type,
        ):
            if isinstance(candidate_obj, DynamicDevice):
                if candidate_obj.idtag == source_element_dgs_id:
                    matches.append(candidate_obj)
                else:
                    pass
            else:
                pass
        else:
            pass
    else:
        pass

    return matches


def _assign_dgs_dynamic_template_to_host(
        host_device: DynamicDevice,
        template_obj: RmsModelTemplate | EmtModelTemplate,
        activation_report: DgsDynamicModelActivationReport,
) -> None:
    """
    Assign one exact imported template without overwriting another controller.

    :param host_device: Exact physical host resolved by DGS FID.
    :param template_obj: Unique imported template.
    :param activation_report: Mutable structured outcome report.
    :return: None.
    """
    if isinstance(template_obj, RmsModelTemplate):
        current_template: RmsModelTemplate | EmtModelTemplate | None = host_device.rms_template
    else:
        current_template = host_device.emt_template

    if isinstance(template_obj, RmsModelTemplate):
        if current_template is template_obj:
            activation_report.record_already_active()
        else:
            if current_template is None:
                try:
                    host_device.rms_template = template_obj
                except (TypeError, ValueError, KeyError):
                    activation_report.record_failed()
                else:
                    activation_report.record_physical_activated()
            else:
                activation_report.record_conflict()
    else:
        if current_template is template_obj:
            activation_report.record_already_active()
        else:
            if current_template is None:
                try:
                    host_device.emt_template = template_obj
                except (TypeError, ValueError, KeyError):
                    activation_report.record_failed()
                else:
                    activation_report.record_physical_activated()
            else:
                activation_report.record_conflict()


def _resolve_dgs_direct_root_host_identity(
        dgs_circuit: DgsCircuit,
        root_element: ElmComp,
        logger: Logger,
) -> Tuple[str, DeviceType, str, str | None] | None:
    """Resolve at most one physical host directly from root ``pElm`` FIDs.

    :param dgs_circuit: Parsed declarative DGS object graph.
    :param root_element: Root composite whose host is being resolved.
    :param logger: Diagnostic sink for ambiguous source relations.
    :return: FID, VeraGrid type, source class and source name, or ``None``.
    """
    identities: Dict[
        Tuple[str, DeviceType],
        Tuple[str, str | None],
    ] = dict()
    direct_entries: List[ElmCompInstanceEntry] = (
        get_unique_elmcomp_slot_entries(
            entries=extract_elmcomp_direct_instances(
                circuit=dgs_circuit,
                root_element=root_element,
            )
        )
    )
    direct_entry: ElmCompInstanceEntry

    # Only one resolved unique slot may establish each physical FID identity.
    for direct_entry in direct_entries:
        source_element_id: str | None = direct_entry.element_id
        source_element_class: str | None = direct_entry.element_kind
        host_device_tpe: DeviceType | None = get_dgs_dynamic_host_device_tpe(
            source_element_class=source_element_class,
        )
        if (
                source_element_id is None
                or source_element_class is None
                or not direct_entry.element_reference_is_resolved
                or host_device_tpe is None
        ):
            pass
        else:
            host_key: Tuple[str, DeviceType] = (
                source_element_id,
                host_device_tpe,
            )
            if host_key in identities:
                pass
            else:
                identities[host_key] = (
                    source_element_class,
                    direct_entry.element_name,
                )

    if len(identities) == 1:
        exact_host_key: Tuple[str, DeviceType] = next(iter(identities))
        exact_host_source: Tuple[str, str | None] = identities[exact_host_key]
        result: Tuple[str, DeviceType, str, str | None] | None = (
            exact_host_key[0],
            exact_host_key[1],
            exact_host_source[0],
            exact_host_source[1],
        )
    else:
        if len(identities) > 1:
            logger.add_warning(
                msg=(
                    "DGS dynamic root retained without activation because "
                    "it has several physical hosts"
                ),
                value=root_element.loc_name,
            )
        else:
            pass
        result = None
    return result


def _register_dgs_direct_template(
        circuit: MultiCircuit,
        template_obj: RmsModelTemplate | EmtModelTemplate,
        root_dgs_id: str,
        existing_names: Set[str],
        logger: Logger,
) -> bool:
    """Register one direct DGS template with a deterministic FID collision name.

    :param circuit: Destination circuit.
    :param template_obj: Final template owning the parsed block.
    :param root_dgs_id: Exact source root FID used only for collision resolution.
    :param existing_names: Mutable names already registered in the destination domain.
    :param logger: Diagnostic sink for irreconcilable collisions.
    :return: ``True`` when the template was registered.
    """
    requested_name: str = str(template_obj.name).strip()
    if requested_name == "":
        requested_name = f"DGS dynamic root {root_dgs_id}"
    else:
        pass

    if requested_name in existing_names:
        final_name: str = f"{requested_name} [DGS {root_dgs_id}]"
    else:
        final_name = requested_name

    if final_name in existing_names:
        logger.add_warning(
            msg="DGS dynamic root skipped because its FID-qualified name already exists",
            value=final_name,
        )
        registered: bool = False
    else:
        template_obj.name = final_name
        template_obj.block.name = final_name
        if isinstance(template_obj, RmsModelTemplate):
            circuit.add_rms_model(template_obj)
        else:
            circuit.add_emt_model(template_obj)
        existing_names.add(final_name)
        registered = True
    return registered


def _activate_dgs_direct_template(
        circuit: MultiCircuit,
        template_obj: RmsModelTemplate | EmtModelTemplate,
        host_identity: Tuple[str, DeviceType, str, str | None],
        adapter_kind: _DgsRuntimeAdapterKind | None,
        logger: Logger,
) -> bool:
    """Configure and assign one template to the exact imported device FID.

    :param circuit: Circuit containing static devices and the final template.
    :param template_obj: Registered direct template.
    :param host_identity: Exact FID, VeraGrid type, source class and source name.
    :param adapter_kind: Import-local runtime adapter classification.
    :param logger: Diagnostic sink for fail-closed activation outcomes.
    :return: ``True`` when the exact host owns this template after the call.
    """
    source_element_id: str = host_identity[0]
    host_device_tpe: DeviceType = host_identity[1]
    source_element_class: str = host_identity[2]
    source_element_name: str | None = host_identity[3]
    host_devices: List[DynamicDevice] = _find_exact_dgs_dynamic_host_devices(
        circuit=circuit,
        source_element_dgs_id=source_element_id,
        device_tpe=host_device_tpe,
        source_element_class=source_element_class,
    )
    if len(host_devices) == 1:
        host_device: DynamicDevice | None = host_devices[0]
    else:
        host_device = None

    adapter_configuration_ready: bool = True
    if (
            isinstance(template_obj, RmsModelTemplate)
            and isinstance(host_device, VSC)
            and adapter_kind == _DgsRuntimeAdapterKind.VSC_MONOPOLAR
    ):
        adapter_configuration_ready = (
            configure_dgs_elmvscmono_runtime_template_for_device(
                template=template_obj,
                device=host_device,
                system_base_mva=float(circuit.Sbase),
            )
        )
    else:
        if (
                isinstance(template_obj, RmsModelTemplate)
                and isinstance(host_device, VSC)
                and adapter_kind == _DgsRuntimeAdapterKind.VSC_BIPOLAR
        ):
            adapter_configuration_ready = (
                configure_dgs_elmvsc_runtime_template_for_device(
                    template=template_obj,
                    device=host_device,
                    system_base_mva=float(circuit.Sbase),
                )
            )
        else:
            if (
                    isinstance(template_obj, RmsModelTemplate)
                    and isinstance(host_device, Generator)
                    and adapter_kind
                    == _DgsRuntimeAdapterKind.SYNCHRONOUS_MACHINE_PENDING
            ):
                adapter_configuration_ready = (
                    configure_dgs_elmsym_runtime_template_for_device(
                        template=template_obj,
                        device=host_device,
                        system_base_mva=float(circuit.Sbase),
                    )
                )
            else:
                pass

    runtime_adapter_kind: _DgsRuntimeAdapterKind | None = adapter_kind
    if (
            runtime_adapter_kind is None
            and source_element_class == "ElmVscmono"
    ):
        # A native monopolar block may already expose the complete equipment
        # boundary and therefore need no wrapper, but its voltage contract is
        # still monopolar during the final fail-closed assignment check.
        runtime_adapter_kind = _DgsRuntimeAdapterKind.VSC_MONOPOLAR
    else:
        pass

    runtime_contract_ready: bool = (
        host_device is not None
        and template_obj.tpe == host_device_tpe
        and adapter_configuration_ready
        and is_dgs_dynamic_block_runtime_assignable(
            block=template_obj.block,
            device_tpe=host_device_tpe,
            adapter_kind=runtime_adapter_kind,
        )
    )
    if not runtime_contract_ready or host_device is None:
        # An incomplete physical wrapper remains inspectable, but it must not
        # appear in the assignable device-template catalogue.
        template_obj.tpe = DeviceType.DynamicModelHostDevice
        logger.add_warning(
            msg=(
                "DGS dynamic host retained without activation because exact "
                "resolution or its runtime adapter contract is incomplete"
            ),
            device=source_element_name,
            device_class=source_element_class,
            value=source_element_id,
        )
        activated: bool = False
    else:
        if isinstance(template_obj, RmsModelTemplate):
            current_template: RmsModelTemplate | EmtModelTemplate | None = (
                host_device.rms_template
            )
        else:
            current_template = host_device.emt_template

        if current_template is template_obj:
            activated = True
        else:
            if current_template is not None:
                logger.add_warning(
                    msg="DGS dynamic host already owns a different template",
                    device=source_element_name,
                    device_class=source_element_class,
                    value=source_element_id,
                )
                activated = False
            else:
                try:
                    if isinstance(template_obj, RmsModelTemplate):
                        host_device.rms_template = template_obj
                    else:
                        host_device.emt_template = template_obj
                except (TypeError, ValueError, KeyError) as error:
                    logger.add_warning(
                        msg="DGS dynamic template assignment failed",
                        device=source_element_name,
                        device_class=source_element_class,
                        value=str(error),
                    )
                    activated = False
                else:
                    activated = True
    return activated


def _get_unique_dgs_dynamic_roots_by_id(
        dgs_circuit: DgsCircuit,
        logger: Logger,
        emit_diagnostics: bool,
) -> Dict[str, ElmComp]:
    """Select only roots with one non-empty normalized DGS FID.

    The first occurrence of a duplicated FID is deliberately excluded together
    with every later occurrence.  Keeping the first would let the assignment
    stage reuse one final template for several source roots.

    :param dgs_circuit: Parsed DGS circuit containing composite roots.
    :param logger: Import diagnostic sink.
    :param emit_diagnostics: Whether this validation pass records source errors.
    :return: Unique roots keyed by their normalized non-empty FID.
    """
    root_count_by_id: Dict[str, int] = dict()
    first_root_by_id: Dict[str, ElmComp] = dict()
    root_element: ElmComp
    for root_element in dgs_circuit.elmcomps:
        root_id: str = str(root_element.ID).strip()
        if root_id == "":
            if emit_diagnostics:
                logger.add_warning(
                    msg="DGS dynamic root skipped because its FID is empty",
                    device=root_element.loc_name,
                    device_class="ElmComp",
                )
            else:
                pass
        else:
            current_count: int | None = root_count_by_id.get(root_id, None)
            if current_count is None:
                root_count_by_id[root_id] = 1
                first_root_by_id[root_id] = root_element
            else:
                root_count_by_id[root_id] = current_count + 1

    unique_root_by_id: Dict[str, ElmComp] = dict()
    root_id: str
    for root_id, root_element in first_root_by_id.items():
        root_count: int | None = root_count_by_id.get(root_id, None)
        if root_count == 1:
            unique_root_by_id[root_id] = root_element
        else:
            if emit_diagnostics:
                logger.add_warning(
                    msg="DGS dynamic roots skipped because their FID is duplicated",
                    device=root_element.loc_name,
                    device_class="ElmComp",
                    value=root_id,
                )
            else:
                pass
    return unique_root_by_id


def convert_and_add_dgs_dynamic_templates_to_circuit(
        dgs_circuit: DgsCircuit,
        circuit: MultiCircuit,
        target_domain: DynamicSimulationMode | None,
        logger: Logger,
) -> DgsDynamicTemplateConversionResult:
    """Convert DGS roots directly into registered final templates.

    The automatic file-open path owns one transient DGS parse graph.  Each
    successful root follows ``Block -> Template -> MultiCircuit``.  The return
    value is the only cross-stage state: one minimal lookup from the exact root
    FID to the final template already owned by ``MultiCircuit``.

    :param dgs_circuit: Declarative DGS graph already used by static import.
    :param circuit: Destination circuit containing the static devices.
    :param target_domain: Explicit RMS or EMT destination; ``None`` is rejected.
    :param logger: Import diagnostics.
    :return: Final-template associations plus transient canonical slot lookups.
    """
    conversion_result: DgsDynamicTemplateConversionResult = (
        DgsDynamicTemplateConversionResult()
    )
    templates_by_root_dgs_id: Dict[
        str,
        RmsModelTemplate | EmtModelTemplate,
    ] = conversion_result.templates_by_root_dgs_id
    if target_domain not in {
        DynamicSimulationMode.RMS,
        DynamicSimulationMode.EMT,
    }:
        logger.add_error(
            msg="DGS dynamic model import requires RMS or EMT mode",
            value=target_domain,
        )
        return conversion_result
    else:
        pass

    # Reject empty and duplicated root identities before building the shared
    # graphical index. Ambiguous roots must not prevent independent valid roots
    # from reaching their own direct FID conversion.
    unique_root_by_id: Dict[str, ElmComp] = _get_unique_dgs_dynamic_roots_by_id(
        dgs_circuit=dgs_circuit,
        logger=logger,
        emit_diagnostics=True,
    )
    excluded_root_ids: Set[str] = set()
    candidate_root: ElmComp
    for candidate_root in dgs_circuit.elmcomps:
        if (
                candidate_root.ID != ""
                and candidate_root.ID not in unique_root_by_id
        ):
            excluded_root_ids.add(candidate_root.ID)
        else:
            pass

    try:
        parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = (
            parse_dgs_block_definitions_from_circuit(
                circuit=dgs_circuit,
                simulation_domain=target_domain,
            )
        )
        graphical_indexes: DgsGraphicalIndexes = build_dgs_graphical_indexes(
            circuit=dgs_circuit,
            excluded_element_ids=excluded_root_ids,
        )
    except (DgsDynamicParserContractError, KeyError, TypeError, ValueError) as error:
        logger.add_error(
            msg="DGS dynamic model import is unavailable",
            value=str(error),
        )
        return conversion_result

    if target_domain == DynamicSimulationMode.RMS:
        existing_names: Set[str] = set(
            template.name for template in circuit.rms_models
        )
    else:
        existing_names = set(
            template.name for template in circuit.emt_models
        )

    materialized_count: int = 0
    failed_count: int = 0
    root_id: str
    root_element: ElmComp
    for root_id, root_element in unique_root_by_id.items():
        host_identity: Tuple[str, DeviceType, str, str | None] | None = (
            _resolve_dgs_direct_root_host_identity(
                dgs_circuit=dgs_circuit,
                root_element=root_element,
                logger=logger,
            )
        )
        source_block: Block | None
        direct_result: DgsDirectRootBuildResult | None = None
        try:
            root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
                circuit=dgs_circuit,
                parsed_blocks=parsed_blocks,
                root_name=root_element.loc_name,
                root_typ_id=root_element.typ_id,
                root_dgs_id=root_id,
            )
            direct_result = build_direct_root_elmcomp_block(
                    circuit=dgs_circuit,
                    result=root_result,
                    graphical_indexes=graphical_indexes,
            )
            source_block = direct_result.root_block
        except (
                DgsDynamicParserContractError,
                KeyError,
                TypeError,
                UnsupportedDgsExpression,
                ValueError,
        ) as error:
            logger.add_warning(
                msg="DGS dynamic root could not be materialized",
                device=root_element.loc_name,
                device_class="ElmComp",
                value=str(error),
            )
            failed_count += 1
            source_block = None

        if source_block is None or direct_result is None:
            pass
        else:
            source_svs: ElmSvs | None = None
            host_device_for_measurements: DynamicDevice | None = None
            if host_identity is None:
                resolved_device_tpe: DeviceType = (
                    DeviceType.DynamicModelHostDevice
                )
                adapter_kind: _DgsRuntimeAdapterKind | None = None
            else:
                host_device_tpe: DeviceType = host_identity[1]
                adapter_kind = _get_dgs_direct_runtime_adapter_kind(
                    direct_result=direct_result,
                    host_identity=host_identity,
                )
                native_runtime_ready: bool = (
                    is_dgs_dynamic_block_runtime_assignable(
                        block=source_block,
                        device_tpe=host_device_tpe,
                        adapter_kind=adapter_kind,
                    )
                )
                adapter_supported: bool = (
                    target_domain == DynamicSimulationMode.RMS
                    and adapter_kind is not None
                )
                typed_vsc_contract_ready: bool = bool(
                    host_device_tpe != DeviceType.VscDevice
                    or adapter_kind is not None
                )
                if (
                        typed_vsc_contract_ready
                        and (native_runtime_ready or adapter_supported)
                ):
                    resolved_device_tpe = host_device_tpe
                else:
                    resolved_device_tpe = DeviceType.DynamicModelHostDevice
                    logger.add_warning(
                        msg=(
                            "DGS dynamic root retained as a generic template "
                            "because its physical runtime contract is unsupported"
                        ),
                        device=root_element.loc_name,
                        device_class="ElmComp",
                        value=root_id,
                    )

                if host_identity[2] == "ElmSvs":
                    candidate_source_svs: ElmSvs
                    source_svs_is_ambiguous: bool = False
                    for candidate_source_svs in dgs_circuit.elmsvss:
                        if candidate_source_svs.ID == host_identity[0]:
                            if source_svs is None:
                                source_svs = candidate_source_svs
                            else:
                                source_svs = None
                                source_svs_is_ambiguous = True
                        else:
                            pass
                    else:
                        pass
                    if source_svs_is_ambiguous:
                        source_svs = None
                    else:
                        pass
                else:
                    pass

                exact_host_devices_for_measurements: List[DynamicDevice] = (
                    _find_exact_dgs_dynamic_host_devices(
                        circuit=circuit,
                        source_element_dgs_id=host_identity[0],
                        device_tpe=host_identity[1],
                        source_element_class=host_identity[2],
                    )
                )
                if len(exact_host_devices_for_measurements) == 1:
                    host_device_for_measurements = (
                        exact_host_devices_for_measurements[0]
                    )
                else:
                    pass

            native_measurement_specs: List[_DgsRmsMeasurementSpec] = (
                _collect_native_dgs_rms_measurement_specs(
                    dgs_circuit=dgs_circuit,
                    root_element=root_element,
                    direct_result=direct_result,
                    host_device=host_device_for_measurements,
                )
            )
            template_obj: RmsModelTemplate | EmtModelTemplate = (
                _build_dgs_direct_runtime_template(
                    source_block=source_block,
                    circuit=circuit,
                    template_name=root_element.loc_name,
                    target_domain=target_domain,
                    device_tpe=resolved_device_tpe,
                    adapter_kind=adapter_kind,
                    direct_result=direct_result,
                    source_svs=source_svs,
                    host_device=host_device_for_measurements,
                    native_measurement_specs=native_measurement_specs,
                )
            )
            if (
                    adapter_kind
                    == _DgsRuntimeAdapterKind.SYNCHRONOUS_MACHINE_PENDING
                    and isinstance(template_obj, RmsModelTemplate)
                    and host_identity is not None
            ):
                exact_host_devices: List[DynamicDevice] = (
                    _find_exact_dgs_dynamic_host_devices(
                        circuit=circuit,
                        source_element_dgs_id=host_identity[0],
                        device_tpe=host_identity[1],
                        source_element_class=host_identity[2],
                    )
                )
                exact_host_device: DynamicDevice | None = None
                if len(exact_host_devices) == 1:
                    exact_host_device = exact_host_devices[0]
                else:
                    pass
                if isinstance(exact_host_device, Generator):
                    elmsym_configuration_ready: bool = (
                        configure_dgs_elmsym_runtime_template_for_device(
                            template=template_obj,
                            device=exact_host_device,
                            system_base_mva=float(circuit.Sbase),
                            direct_result=direct_result,
                        )
                    )
                else:
                    elmsym_configuration_ready = False
                if elmsym_configuration_ready:
                    pass
                else:
                    template_obj.tpe = DeviceType.DynamicModelHostDevice
                    logger.add_warning(
                        msg=(
                            "DGS ElmSym template retained as generic because "
                            "exact runtime configuration failed"
                        ),
                        device=root_element.loc_name,
                        device_class="ElmComp",
                        value=root_id,
                    )
            else:
                pass
            registered: bool = _register_dgs_direct_template(
                circuit=circuit,
                template_obj=template_obj,
                root_dgs_id=root_id,
                existing_names=existing_names,
                logger=logger,
            )
            if registered:
                templates_by_root_dgs_id[root_id] = template_obj
                conversion_result.child_blocks_by_root_and_slot_id[root_id] = (
                    dict(direct_result.child_block_by_slot_id)
                )
                materialized_count += 1
            else:
                failed_count += 1

    # Isolated BlkRef occurrences are valid reusable DGS definitions even when
    # the file has no ElmComp root or physical host. Materialize one final
    # catalogue template per exact BlkDef without creating Bundle/Entry state.
    standalone_occurrences: List[DgsStandaloneBlockOccurrence] = (
        list_dgs_blkref_catalog_occurrences_from_circuit(circuit=dgs_circuit)
    )
    standalone_id_count: Dict[str, int] = dict()
    standalone_occurrence: DgsStandaloneBlockOccurrence
    for standalone_occurrence in standalone_occurrences:
        standalone_id: str = str(standalone_occurrence.blkref_id).strip()
        current_count: int | None = standalone_id_count.get(standalone_id, None)
        if current_count is None:
            standalone_id_count[standalone_id] = 1
        else:
            standalone_id_count[standalone_id] = current_count + 1

    elmcomp_ids: Set[str] = set()
    source_root: ElmComp
    for source_root in dgs_circuit.elmcomps:
        elmcomp_ids.add(str(source_root.ID).strip())
    materialized_standalone_type_ids: Set[str] = set()
    for standalone_occurrence in standalone_occurrences:
        standalone_id = str(standalone_occurrence.blkref_id).strip()
        standalone_id_occurrences: int | None = standalone_id_count.get(
            standalone_id,
            None,
        )
        standalone_is_eligible: bool = bool(
            not standalone_occurrence.connected
            and standalone_id != ""
            and standalone_id_occurrences == 1
            and standalone_id not in elmcomp_ids
            and standalone_occurrence.typ_id
            not in materialized_standalone_type_ids
        )
        if not standalone_is_eligible:
            pass
        else:
            parsed_standalone: ParsedDgsBlockDefinition | None = (
                parsed_blocks.get(standalone_occurrence.typ_id, None)
            )
            if parsed_standalone is None:
                logger.add_warning(
                    msg="Isolated DGS BlkRef skipped because its BlkDef is missing",
                    device=standalone_occurrence.sample_display_name,
                    device_class="BlkRef",
                    value=standalone_id,
                )
                failed_count += 1
            else:
                try:
                    standalone_block: Block = (
                        build_standalone_blkdef_block_from_parsed_block(
                            parsed_block=parsed_standalone,
                            block_name=parsed_standalone.blkdef.loc_name,
                        )
                    )
                    standalone_template: RmsModelTemplate | EmtModelTemplate = (
                        _build_dgs_direct_runtime_template(
                            source_block=standalone_block,
                            circuit=circuit,
                            template_name=parsed_standalone.blkdef.loc_name,
                            target_domain=target_domain,
                            device_tpe=DeviceType.DynamicModelHostDevice,
                            adapter_kind=None,
                            direct_result=None,
                            source_svs=None,
                            host_device=None,
                            native_measurement_specs=list(),
                        )
                    )
                    standalone_registered: bool = _register_dgs_direct_template(
                        circuit=circuit,
                        template_obj=standalone_template,
                        root_dgs_id=standalone_id,
                        existing_names=existing_names,
                        logger=logger,
                    )
                except (
                        KeyError,
                        TypeError,
                        UnsupportedDgsExpression,
                        ValueError,
                ) as error:
                    logger.add_warning(
                        msg="Isolated DGS BlkRef could not be materialized",
                        device=standalone_occurrence.sample_display_name,
                        device_class="BlkRef",
                        value=str(error),
                    )
                    failed_count += 1
                else:
                    materialized_standalone_type_ids.add(
                        standalone_occurrence.typ_id
                    )
                    if standalone_registered:
                        materialized_count += 1
                    else:
                        failed_count += 1

    logger.add_info(
        msg="DGS dynamic template conversion completed",
        value=(
            f"templates={materialized_count}, "
            f"failed={failed_count}"
        ),
    )
    return conversion_result


def apply_dgs_dynamic_templates_to_devices(
        dgs_circuit: DgsCircuit,
        circuit: MultiCircuit,
        templates_by_root_dgs_id: Dict[
            str,
            RmsModelTemplate | EmtModelTemplate,
        ],
        logger: Logger,
) -> None:
    """Apply registered DGS templates to exact static devices by root FID.

    This second stage does not reconstruct source entries or duplicate blocks.
    It resolves the physical host again from the transient DGS graph, retrieves
    the already registered final template from the minimal FID lookup, configures
    each structurally proven adapter and assigns the template fail closed.

    :param dgs_circuit: Declarative DGS graph used for exact host resolution.
    :param circuit: Destination circuit owning devices and registered templates.
    :param templates_by_root_dgs_id: Final templates indexed by exact root FID.
    :param logger: Import diagnostics.
    :return: None.
    """
    activated_count: int = 0
    failed_count: int = 0
    unique_root_by_id: Dict[str, ElmComp] = _get_unique_dgs_dynamic_roots_by_id(
        dgs_circuit=dgs_circuit,
        logger=logger,
        emit_diagnostics=False,
    )
    root_id: str
    root_element: ElmComp
    for root_id, root_element in unique_root_by_id.items():
        template_obj: RmsModelTemplate | EmtModelTemplate | None = (
            templates_by_root_dgs_id.get(root_id, None)
        )
        if template_obj is None:
            pass
        else:
            host_identity: Tuple[
                str,
                DeviceType,
                str,
                str | None,
            ] | None = _resolve_dgs_direct_root_host_identity(
                dgs_circuit=dgs_circuit,
                root_element=root_element,
                logger=logger,
            )
            if host_identity is None:
                pass
            else:
                if (
                        template_obj.tpe == DeviceType.VscDevice
                        and host_identity[1] == DeviceType.VscDevice
                        and host_identity[2] == "ElmVscmono"
                ):
                    adapter_kind: _DgsRuntimeAdapterKind | None = (
                        _DgsRuntimeAdapterKind.VSC_MONOPOLAR
                    )
                else:
                    if (
                            template_obj.tpe == DeviceType.VscDevice
                            and host_identity[1] == DeviceType.VscDevice
                            and host_identity[2] == "ElmVsc"
                    ):
                        adapter_kind = _DgsRuntimeAdapterKind.VSC_BIPOLAR
                    else:
                        adapter_kind = None
                if _activate_dgs_direct_template(
                        circuit=circuit,
                        template_obj=template_obj,
                        host_identity=host_identity,
                        adapter_kind=adapter_kind,
                        logger=logger,
                ):
                    activated_count += 1
                else:
                    failed_count += 1

    logger.add_info(
        msg="DGS dynamic device assignment completed",
        value=f"activated={activated_count}, failed={failed_count}",
    )


def activate_unambiguous_dgs_dynamic_models_in_circuit(
        circuit: MultiCircuit,
        records: Sequence[DgsDynamicAssociationRecord],
        template_by_root_dgs_id: Dict[str, RmsModelTemplate | EmtModelTemplate],
        logger: Logger,
) -> DgsDynamicModelActivationReport:
    """
    Activate unambiguous DGS composite models on their exact physical hosts.

    A root is activated only when its supported host relations collapse to one
    ``(FID, device type)`` identity, that identity resolves to exactly one
    imported device and the final template name resolves uniquely. Auxiliary
    pElm references remain provenance and multi-host plant controllers remain
    explicit catalogue objects for a later user-directed composition workflow.

    :param circuit: Destination circuit with static devices and templates.
    :param records: Exact root-slot-pElm source associations.
    :param template_by_root_dgs_id: Installed VeraGrid template indexed by the
        exact source ElmComp FID that produced it.
    :param logger: Diagnostic sink for handled unresolved roots.
    :return: Structured activation report.
    """
    activation_report: DgsDynamicModelActivationReport = DgsDynamicModelActivationReport()
    records_by_root_id: Dict[str, List[DgsDynamicAssociationRecord]] = dict()
    record: DgsDynamicAssociationRecord
    root_records: List[DgsDynamicAssociationRecord]
    existing_root_records: List[DgsDynamicAssociationRecord] | None
    host_record_by_identity: Dict[Tuple[str, DeviceType], DgsDynamicAssociationRecord]
    source_element_id: str | None
    host_device_tpe: DeviceType | None
    host_identity: Tuple[str, DeviceType]
    host_record: DgsDynamicAssociationRecord
    template_name: str | None
    host_devices: List[DynamicDevice]
    template_obj: RmsModelTemplate | EmtModelTemplate | None

    # Group once by exact root FID so the ambiguity decision is linear in the
    # number of source associations even for large PowerFactory catalogues.
    for record in records:
        existing_root_records = records_by_root_id.get(record.get_root_dgs_id(), None)
        if existing_root_records is None:
            root_records = list()
            root_records.append(record)
            records_by_root_id[record.get_root_dgs_id()] = root_records
        else:
            existing_root_records.append(record)

    for root_records in records_by_root_id.values():
        host_record_by_identity = dict()
        for record in root_records:
            source_element_id = record.get_source_element_dgs_id()
            host_device_tpe = get_dgs_dynamic_host_device_tpe(
                source_element_class=record.get_source_element_class(),
            )
            template_name = record.get_final_template_name()
            if source_element_id is None or host_device_tpe is None or template_name is None:
                pass
            else:
                host_identity = source_element_id, host_device_tpe
                if host_identity in host_record_by_identity:
                    pass
                else:
                    host_record_by_identity[host_identity] = record

        if len(host_record_by_identity) == 0:
            # Roots without one exact physical host remain local catalogue
            # metadata. They are not promoted to global circuit devices.
            pass
        else:
            if len(host_record_by_identity) > 1:
                activation_report.record_ambiguous()
                logger.add_warning(
                    msg="DGS dynamic root retained without activation because it has several physical hosts",
                    value=root_records[0].get_root_name(),
                )
            else:
                host_identity = next(iter(host_record_by_identity))
                host_record = host_record_by_identity[host_identity]
                template_name = host_record.get_final_template_name()
                if template_name is None:
                    activation_report.record_unresolved()
                else:
                    host_devices = _find_exact_dgs_dynamic_host_devices(
                        circuit=circuit,
                        source_element_dgs_id=host_identity[0],
                        device_tpe=host_identity[1],
                        source_element_class=(
                            host_record.get_source_element_class()
                        ),
                    )
                    template_obj = template_by_root_dgs_id.get(
                        host_record.get_root_dgs_id(),
                        None,
                    )
                    if (
                            host_record.get_target_domain() == DynamicSimulationMode.RMS
                            and not isinstance(template_obj, RmsModelTemplate)
                    ):
                        template_obj = None
                    else:
                        if (
                                host_record.get_target_domain() == DynamicSimulationMode.EMT
                                and not isinstance(template_obj, EmtModelTemplate)
                        ):
                            template_obj = None
                        else:
                            pass
                    source_element_class: str = (
                        host_record.get_source_element_class()
                    )
                    if source_element_class == "ElmVscmono":
                        template_adapter_kind: _DgsRuntimeAdapterKind | None = (
                            _DgsRuntimeAdapterKind.VSC_MONOPOLAR
                        )
                    else:
                        if source_element_class == "ElmVsc":
                            template_adapter_kind = (
                                _DgsRuntimeAdapterKind.VSC_BIPOLAR
                            )
                        else:
                            if source_element_class == "ElmSym":
                                template_adapter_kind = (
                                    _DgsRuntimeAdapterKind.SYNCHRONOUS_MACHINE_PENDING
                                )
                            else:
                                template_adapter_kind = None
                    host_device: DynamicDevice | None
                    if len(host_devices) == 1:
                        host_device = host_devices[0]
                    else:
                        host_device = None
                    adapter_configuration_ready: bool = True
                    if (
                            isinstance(template_obj, RmsModelTemplate)
                            and isinstance(host_device, VSC)
                            and template_adapter_kind
                            == _DgsRuntimeAdapterKind.VSC_MONOPOLAR
                    ):
                        # Monopolar bridges use the grounded return represented
                        # by their one exported DC terminal and native base.
                        adapter_configuration_ready = (
                            configure_dgs_elmvscmono_runtime_template_for_device(
                                template=template_obj,
                                device=host_device,
                                system_base_mva=float(circuit.Sbase),
                            )
                        )
                    else:
                        if (
                                isinstance(template_obj, RmsModelTemplate)
                                and isinstance(host_device, VSC)
                                and template_adapter_kind
                                == _DgsRuntimeAdapterKind.VSC_BIPOLAR
                        ):
                            # Bipolar bridges use both exported pole bases.
                            adapter_configuration_ready = (
                                configure_dgs_elmvsc_runtime_template_for_device(
                                    template=template_obj,
                                    device=host_device,
                                    system_base_mva=float(circuit.Sbase),
                                )
                            )
                        else:
                            if (
                                    isinstance(template_obj, RmsModelTemplate)
                                    and isinstance(host_device, Generator)
                                    and template_adapter_kind
                                    == _DgsRuntimeAdapterKind.SYNCHRONOUS_MACHINE_PENDING
                            ):
                                # The exact TypSym selects salient or round
                                # rotor structure and supplies every physical
                                # parameter before the runtime contract check.
                                adapter_configuration_ready = (
                                    configure_dgs_elmsym_runtime_template_for_device(
                                        template=template_obj,
                                        device=host_device,
                                        system_base_mva=float(circuit.Sbase),
                                    )
                                )
                            else:
                                pass
                    runtime_contract_ready: bool = (
                        template_obj is not None
                        and template_obj.tpe == host_identity[1]
                        and adapter_configuration_ready
                        and is_dgs_dynamic_block_runtime_assignable(
                            block=template_obj.block,
                            device_tpe=host_identity[1],
                            adapter_kind=template_adapter_kind,
                        )
                    )
                    if len(host_devices) != 1 or not runtime_contract_ready:
                        activation_report.record_unresolved()
                        logger.add_warning(
                            msg=(
                                "DGS dynamic host retained without activation because exact "
                                "resolution or its runtime adapter contract is incomplete"
                            ),
                            device=host_record.get_source_element_name(),
                            device_class=host_record.get_source_element_class(),
                            value=host_identity[0],
                        )
                    else:
                        if template_obj is None:
                            # The explicit runtime-contract condition above makes
                            # this branch unreachable, while the local guard keeps
                            # the type state evident for static analysis.
                            activation_report.record_unresolved()
                            pass
                        else:
                            _assign_dgs_dynamic_template_to_host(
                                host_device=host_devices[0],
                                template_obj=template_obj,
                                activation_report=activation_report,
                            )

    return activation_report


def add_all_dynamic_import_bundle_to_circuit_with_report(
        circuit: MultiCircuit,
        bundle: DynamicModelImportBundle,
        logger: Logger,
        target_domain: DynamicSimulationMode,
        progress_callback: Callable[[int, str], None] | None = None,
        user_root_folder: str | None = None,
        persist_to_user_catalog: bool = False,
        consume_bundle_templates: bool = False,
) -> DynamicModelImportReport:
    """
    Add every importable bundle entry to a circuit for non-interactive DGS loading.

    Structurally equivalent entries are deduplicated across names within the same
    target domain and device classification.  Same-name entries with a different
    symbolic structure receive a deterministic source-qualified name so
    the bulk path never discards a valid variant merely because another root
    exposed the same slot label.

    :param circuit: Target circuit.
    :param bundle: Parsed dynamic-model bundle.
    :param logger: Logger receiving partial-failure and deduplication diagnostics.
    :param target_domain: Explicit RMS or EMT destination for every selected entry.
    :param progress_callback: Optional UI progress callback.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param persist_to_user_catalog: Deprecated compatibility request; executable persistence is refused.
    :param consume_bundle_templates: Transfer source blocks from an ephemeral
        bundle to avoid a second massive symbolic graph in memory.
    :return: Structured massive-import report.
    """
    selection_requests: List[DynamicModelImportSelectionRequest] = list()
    selected_entry_keys: Set[str] = set()
    entry: DynamicModelImportEntry
    importable_count: int = 0
    selection_request: DynamicModelImportSelectionRequest
    entry_availability: DynamicModelImportEntryAvailability
    unavailable_status: DynamicModelImportEntryStatus
    unavailable_message: str
    source_is_dgs: bool = (
        bundle.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs
    )
    effective_persist_to_user_catalog: bool = (
        persist_to_user_catalog and not source_is_dgs
    )
    template_fingerprint_by_object_id: Dict[int, str | None] = dict()

    # Imported DGS models remain declarative data owned by the circuit. They
    # must never be converted into executable Python for user-catalog storage.
    if persist_to_user_catalog and source_is_dgs:
        logger.add_warning(
            msg="DGS dynamic model Python persistence refused",
            value="The imported Block and template remain in the circuit",
        )
    else:
        pass

    for entry in bundle.get_entries():
        if entry.is_importable():
            importable_count += 1
        else:
            pass

    report: DynamicModelImportReport = DynamicModelImportReport(
        discovered_count=len(bundle.get_entries()),
        importable_count=importable_count,
    )

    for entry in bundle.get_entries():
        if not entry.is_importable():
            entry_availability = entry.get_availability()
            if entry_availability == DynamicModelImportEntryAvailability.MetadataOnly:
                unavailable_status = DynamicModelImportEntryStatus.Skipped
                unavailable_message = (
                    "Source hierarchy and association metadata retained without "
                    "a reusable template"
                )
            else:
                unavailable_status = DynamicModelImportEntryStatus.Failed
                unavailable_message = "Source entry could not be materialized"
            selection_request = DynamicModelImportSelectionRequest(
                entry_key=entry.get_unique_key(),
                target_domain=target_domain,
                device_tpe=guess_dynamic_model_import_hierarchy_device_tpe(bundle=bundle, entry=entry),
            )
            _append_dynamic_model_import_entry_result(
                report=report,
                entry=entry,
                selection_request=selection_request,
                final_name=None,
                status=unavailable_status,
                message=unavailable_message,
            )
        else:
            entry_key: str = entry.get_unique_key()
            if entry_key in selected_entry_keys:
                logger.add_info(
                    msg="Duplicate dynamic model catalogue entry ignored",
                    value=entry_key,
                )
            else:
                selected_entry_keys.add(entry_key)
                selection_requests.append(
                    DynamicModelImportSelectionRequest(
                        entry_key=entry_key,
                        target_domain=target_domain,
                        device_tpe=guess_dynamic_model_import_hierarchy_device_tpe(bundle=bundle, entry=entry),
                    )
                )

    add_dynamic_import_selection_requests_to_circuit(
        circuit=circuit,
        bundle=bundle,
        selection_requests=selection_requests,
        logger=logger,
        progress_callback=progress_callback,
        user_root_folder=user_root_folder,
        rename_conflicting_templates=True,
        persist_to_user_catalog=effective_persist_to_user_catalog,
        report=report,
        template_fingerprint_by_object_id=template_fingerprint_by_object_id,
        clone_source_blocks=not consume_bundle_templates,
    )

    # DGS source relations remain separate metadata.  Building one record per
    # report result preserves aliases after many-to-one template deduplication
    # without assigning any template to an electrical device.
    if bundle.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs:
        template_by_root_dgs_id: Dict[
            str,
            RmsModelTemplate | EmtModelTemplate,
        ] = dict()
        ambiguous_template_root_ids: Set[str] = set()

        # The source-to-destination association exists only while this import is
        # active. It replaces the former second lookup by a mutable display name
        # after the templates had already been registered in the circuit.
        for entry in bundle.get_entries():
            source_provenance: DynamicModelImportSourceProvenance | None = (
                entry.get_source_provenance()
            )
            installed_template: RmsModelTemplate | EmtModelTemplate | None = (
                entry.get_installed_template()
            )
            if (
                    source_provenance is None
                    or source_provenance.get_slot_index() is not None
                    or installed_template is None
            ):
                pass
            else:
                root_dgs_id: str = source_provenance.get_root_dgs_id()
                existing_template: RmsModelTemplate | EmtModelTemplate | None = (
                    template_by_root_dgs_id.get(root_dgs_id, None)
                )
                if root_dgs_id in ambiguous_template_root_ids:
                    pass
                else:
                    if existing_template is None:
                        template_by_root_dgs_id[root_dgs_id] = installed_template
                    else:
                        if existing_template is installed_template:
                            pass
                        else:
                            # More than one destination for one source root is not
                            # assignable. Remove the partial mapping so activation
                            # remains fail-closed and report the contradiction.
                            del template_by_root_dgs_id[root_dgs_id]
                            ambiguous_template_root_ids.add(root_dgs_id)
                            logger.add_warning(
                                msg=(
                                    "DGS dynamic root retained without activation because "
                                    "it produced several VeraGrid templates"
                                ),
                                value=root_dgs_id,
                            )

        association_records: List[DgsDynamicAssociationRecord] = build_dgs_dynamic_association_records(
            report=report,
        )

        # Exact single-host composites can now follow the same end state as a
        # manual GUI template assignment. Ambiguous plant controllers and
        # unsupported equipment remain safely available in the catalogue.
        activation_report: DgsDynamicModelActivationReport = (
            activate_unambiguous_dgs_dynamic_models_in_circuit(
                circuit=circuit,
                records=association_records,
                template_by_root_dgs_id=template_by_root_dgs_id,
                logger=logger,
            )
        )
        report.set_activation_report(activation_report=activation_report)
        logger.add_info(
            msg="DGS dynamic device models activated by exact source identity",
            value=activation_report.get_activated_count(),
        )

    else:
        pass

    return report


def add_all_dynamic_import_bundle_to_circuit(
        circuit: MultiCircuit,
        bundle: DynamicModelImportBundle,
        logger: Logger,
        target_domain: DynamicSimulationMode,
        progress_callback: Callable[[int, str], None] | None = None,
        user_root_folder: str | None = None,
        persist_to_user_catalog: bool = False,
) -> int:
    """
    Add every importable entry and return the backward-compatible added count.

    :param circuit: Target circuit.
    :param bundle: Parsed dynamic-model bundle.
    :param logger: Logger receiving partial-failure and deduplication diagnostics.
    :param target_domain: Explicit RMS or EMT destination for every selected entry.
    :param progress_callback: Optional UI progress callback.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param persist_to_user_catalog: Deprecated compatibility request; executable persistence is refused.
    :return: Number of added templates, including collision-safe renamed variants.
    """
    report: DynamicModelImportReport = add_all_dynamic_import_bundle_to_circuit_with_report(
        circuit=circuit,
        bundle=bundle,
        logger=logger,
        target_domain=target_domain,
        progress_callback=progress_callback,
        user_root_folder=user_root_folder,
        persist_to_user_catalog=persist_to_user_catalog,
    )
    return report.get_added_count()


def add_dynamic_import_bundle_to_circuit(
        circuit: MultiCircuit,
        bundle: DynamicModelImportBundle,
        selected_keys: Sequence[str],
        target_domain: DynamicSimulationMode,
        device_tpe: DeviceType,
        logger: Logger,
) -> int:
    """
    Add the selected imported dynamic models to the circuit.

    The caller selects the simulation domain and compatible device family before
    any RMS or EMT template is materialized.

    :param circuit: Target circuit.
    :param bundle: Imported dynamic-model bundle.
    :param selected_keys: Selected entry keys.
    :param target_domain: Explicit RMS or EMT destination.
    :param device_tpe: Compatible VeraGrid device family.
    :param logger: Logger receiving duplicate or importability diagnostics.
    :return: Number of templates added to the circuit.
    """
    selection_requests: List[DynamicModelImportSelectionRequest] = list()
    entry_key: str

    for entry_key in selected_keys:
        selection_requests.append(
            DynamicModelImportSelectionRequest(
                entry_key=entry_key,
                target_domain=target_domain,
                device_tpe=device_tpe,
            )
        )

    return add_dynamic_import_selection_requests_to_circuit(
        circuit=circuit,
        bundle=bundle,
        selection_requests=selection_requests,
        logger=logger,
    )


def load_user_dynamic_model_templates_into_circuit(
        circuit: MultiCircuit,
        logger: Logger | None = None,
        user_root_folder: str | None = None,
) -> int:
    """
    Load persisted user dynamic templates from the VeraGrid user folder.

    The loader only targets the importer-managed ``user_templates`` folder so the
    GUI can restore previously imported EMT templates across sessions without
    coupling that behavior to generic ``MultiCircuit`` construction.

    :param circuit: Target circuit receiving the persisted templates.
    :param logger: Optional logger receiving load diagnostics.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Number of templates added to the circuit.
    """
    effective_logger: Logger = Logger() if logger is None else logger
    existing_rms_names: Set[str] = set()
    existing_emt_names: Set[str] = set()
    loaded_template: DynamicModelLoadedUserTemplate
    template_obj: RmsModelTemplate | EmtModelTemplate
    added_count: int = 0

    # The catalogue must stay idempotent inside one circuit even if the same user
    # template file is scanned more than once across GUI actions.
    for template in circuit.rms_models:
        existing_rms_names.add(template.name)

    for template in circuit.emt_models:
        existing_emt_names.add(template.name)

    # Reuse the shared data-only scanner so the GUI catalogue and the importer
    # materialize exactly the same declarative template payloads.
    for loaded_template in load_user_dynamic_model_templates(
            logger=effective_logger,
            user_root_folder=user_root_folder,
    ):
        template_obj = loaded_template.get_template_obj()

        if isinstance(template_obj, RmsModelTemplate):
            if template_obj.name in existing_rms_names:
                effective_logger.add_debug(
                    "Skipped persisted user RMS model because the template name already exists",
                    template_obj.name,
                )
            else:
                circuit.add_rms_model(template_obj)
                existing_rms_names.add(template_obj.name)
                added_count += 1
        else:
            if isinstance(template_obj, EmtModelTemplate):
                if template_obj.name in existing_emt_names:
                    effective_logger.add_debug(
                        "Skipped persisted user EMT model because the template name already exists",
                        template_obj.name,
                    )
                else:
                    circuit.add_emt_model(template_obj)
                    existing_emt_names.add(template_obj.name)
                    added_count += 1
            else:
                pass

    return added_count


def load_user_dynamic_model_templates(
        logger: Logger | None = None,
        user_root_folder: str | None = None,
) -> List[DynamicModelLoadedUserTemplate]:
    """
    Materialize all persisted user dynamic templates from the VeraGrid user folder.

    :param logger: Optional logger receiving load diagnostics.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Materialized persisted user templates.
    """
    effective_logger: Logger = Logger() if logger is None else logger
    templates: List[DynamicModelLoadedUserTemplate] = list()
    seen_template_signatures: Set[tuple[DynamicSimulationMode, str]] = set()
    folder_path: Path
    payload_path: Path
    template: DynamicModelLoadedUserTemplate | None

    for folder_path in _iter_user_dynamic_models_folder_paths(user_root_folder=user_root_folder):
        # Declarative payloads are the only persisted representation accepted at
        # this boundary, so imported data can never become executable source.
        for payload_path in sorted(folder_path.glob("*.payload.json")):
            template = _load_user_dynamic_template_from_payload_path(
                payload_path=payload_path,
                logger=effective_logger,
            )

            if template is None:
                pass
            else:
                _append_loaded_user_dynamic_template_once(
                    template=template,
                    seen_template_signatures=seen_template_signatures,
                    templates=templates,
                )

    return templates


def _load_user_dynamic_template_from_payload_path(
        payload_path: Path,
        logger: Logger,
) -> DynamicModelLoadedUserTemplate | None:
    """Materialize one validated declarative user-template payload.

    :param payload_path: Exact JSON payload path.
    :param logger: Diagnostic sink for rejected payloads.
    :return: Typed loaded-template descriptor, or ``None`` when invalid.
    """
    try:
        loaded_payload: Tuple[
            Block,
            str,
            DynamicSimulationMode,
            DeviceType,
        ] | None = load_user_dynamic_template_json_payload(
            json_path=str(payload_path),
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.add_warning(
            msg="Declarative user dynamic-model payload rejected",
            value=f"{payload_path}: {error}",
        )
        loaded_payload = None

    if loaded_payload is None:
        result: DynamicModelLoadedUserTemplate | None = None
    else:
        block: Block = loaded_payload[0]
        template_name: str = loaded_payload[1]
        target_domain: DynamicSimulationMode = loaded_payload[2]
        device_tpe: DeviceType = loaded_payload[3]
        template_obj: RmsModelTemplate | EmtModelTemplate
        if target_domain == DynamicSimulationMode.RMS:
            template_obj = RmsModelTemplate(name=template_name)
        else:
            template_obj = EmtModelTemplate(name=template_name)
        template_obj.tpe = device_tpe
        template_obj.block = block
        result = DynamicModelLoadedUserTemplate(
            payload_path=payload_path,
            domain=target_domain,
            device_tpe=device_tpe,
            template_obj=template_obj,
        )
    return result


def _append_loaded_user_dynamic_template_once(
        template: DynamicModelLoadedUserTemplate,
        seen_template_signatures: Set[tuple[DynamicSimulationMode, str]],
        templates: List[DynamicModelLoadedUserTemplate],
) -> None:
    """
    Append one loaded template unless its domain and name were already restored.

    :param template: Loaded user-template descriptor.
    :param seen_template_signatures: Mutable set of already accepted signatures.
    :param templates: Mutable ordered output collection.
    :return: None.
    """
    template_signature: tuple[DynamicSimulationMode, str] = (
        template.get_domain(),
        template.get_template_obj().name,
    )

    # Domain-separated folders are scanned before the legacy folder, so keeping
    # the first signature deterministically preserves the modern catalogue.
    if template_signature in seen_template_signatures:
        pass
    else:
        seen_template_signatures.add(template_signature)
        templates.append(template)


def _get_user_dynamic_models_root_folder_path(create: bool = True,
                                              user_root_folder: str | None = None) -> Path:
    """
    Return the VeraGrid user root folder used to persist imported dynamic models.

    :param create: Create the folder when it does not exist?
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Persistent user dynamic-model root folder path.
    """
    root_folder_path: Path
    folder_path: Path

    if user_root_folder is None:
        root_folder_path = Path(get_create_veragrid_folder())
    else:
        root_folder_path = Path(user_root_folder)

    folder_path = root_folder_path / "user_defined_models"

    if create:
        folder_path.mkdir(parents=True, exist_ok=True)
    else:
        pass

    return folder_path


def _get_legacy_user_dynamic_models_folder_path(create: bool = False,
                                                user_root_folder: str | None = None) -> Path:
    """
    Return the legacy flat folder used by older VeraGrid builds.

    :param create: Create the folder when it does not exist?
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Legacy persisted user dynamic-model folder path.
    """
    root_folder_path: Path
    folder_path: Path

    if user_root_folder is None:
        root_folder_path = Path(get_create_veragrid_folder())
    else:
        root_folder_path = Path(user_root_folder)

    folder_path = root_folder_path / "user_templates"

    if create:
        folder_path.mkdir(parents=True, exist_ok=True)
    else:
        pass

    return folder_path


def _get_user_dynamic_models_domain_folder_path(
        target_domain: DynamicSimulationMode,
        create: bool = True,
        user_root_folder: str | None = None,
) -> Path:
    """
    Return the domain-specific VeraGrid user folder used to persist one template.

    :param target_domain: Selected persisted template domain.
    :param create: Create the folder when it does not exist?
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Persistent domain-specific user dynamic-model folder path.
    """
    folder_name: str

    if target_domain == DynamicSimulationMode.RMS:
        folder_name = "rms"
    else:
        if target_domain == DynamicSimulationMode.EMT:
            folder_name = "emt"
        else:
            raise ValueError(f"Unsupported user dynamic-model domain {target_domain}")

    folder_path: Path = _get_user_dynamic_models_root_folder_path(
        create=create,
        user_root_folder=user_root_folder,
    ) / folder_name

    if create:
        folder_path.mkdir(parents=True, exist_ok=True)
    else:
        pass

    return folder_path


def _iter_user_dynamic_models_folder_paths(user_root_folder: str | None = None) -> List[Path]:
    """
    Return the existing persisted user-template folders to scan.

    The loader prefers the new domain-separated layout while still scanning the
    legacy flat folder so existing user templates keep loading without migration.

    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Existing persisted user-template folders in deterministic order.
    """
    folder_paths: List[Path] = list()
    rms_folder_path: Path = _get_user_dynamic_models_domain_folder_path(
        DynamicSimulationMode.RMS,
        create=False,
        user_root_folder=user_root_folder,
    )
    emt_folder_path: Path = _get_user_dynamic_models_domain_folder_path(
        DynamicSimulationMode.EMT,
        create=False,
        user_root_folder=user_root_folder,
    )
    legacy_folder_path: Path = _get_legacy_user_dynamic_models_folder_path(
        create=False,
        user_root_folder=user_root_folder,
    )

    if rms_folder_path.exists():
        folder_paths.append(rms_folder_path)
    else:
        pass

    if emt_folder_path.exists():
        folder_paths.append(emt_folder_path)
    else:
        pass

    if legacy_folder_path.exists():
        folder_paths.append(legacy_folder_path)
    else:
        pass

    return folder_paths


def _sanitize_file_stem(text: str) -> str:
    """
    Convert one display name into a filesystem-safe stem.

    :param text: Source text.
    :return: Filesystem-safe stem.
    """
    return sanitize_dynamic_model_file_stem(text=text)


def build_user_dynamic_template_payload_output_path(
        template_name: str,
        target_domain: DynamicSimulationMode,
        catalog_root_folder: str | None = None,
) -> Path:
    """
    Build the preferred unsuffixed sidecar path for one persisted user template.

    :param template_name: Human-facing template name.
    :param target_domain: Selected RMS or EMT user folder.
    :param catalog_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Preferred JSON payload path before collision resolution.
    """
    output_folder: Path = _get_user_dynamic_models_domain_folder_path(
        target_domain=target_domain,
        create=True,
        user_root_folder=catalog_root_folder,
    )
    safe_stem: str = _sanitize_file_stem(template_name)

    if len(safe_stem) == 0:
        safe_stem = "user_dynamic_model"
    else:
        pass

    return output_folder / f"{safe_stem}.payload.json"


def _iter_child_blocks_recursive(block: Block) -> List[Block]:
    """
    Return every descendant child block in depth-first order.

    :param block: Root block.
    :return: Recursive child block list.
    """
    child_blocks: List[Block] = list()
    child_block: Block

    for child_block in block.children:
        child_blocks.append(child_block)
        child_blocks.extend(_iter_child_blocks_recursive(child_block))

    return child_blocks


def build_user_dynamic_template_persistable_block(block: Block) -> Block:
    """
    Build the reusable block stored in the declarative user-template payload.

    Device-bound editors expose lateral `INPUT_CONN` and `OUTPUT_CONN` blocks only
    as one visual wrapper around the reusable template interface. Persisting those
    GUI-only children into the catalogue would duplicate the lateral interface when
    the template gets opened again. The persisted declarative payload therefore
    keeps the root symbolic ports but removes the wrapper connection blocks and
    their diagram branches.

    :param block: Editor working block.
    :return: Persistable reusable block without GUI-only lateral wrappers.
    """
    export_block: Block = copy.deepcopy(block)
    interface_block_uids: Set[int] = set()
    filtered_children: List[Block] = list()
    child_block: Block
    node_uid: int
    node_data: BlockDiagramNode
    connection_uid: int
    connection_data: BlockDiagramConnection
    filtered_node_data: Dict[int, BlockDiagramNode] = dict()
    filtered_connection_data: Dict[int, BlockDiagramConnection] = dict()

    for node_uid, node_data in export_block.diagram.node_data.items():
        if node_data.tpe == BlockType.INPUT_CONN.name or node_data.tpe == BlockType.OUTPUT_CONN.name:
            interface_block_uids.add(int(node_data.device_uid))
        else:
            filtered_node_data[node_uid] = node_data

    for child_block in export_block.children:
        if child_block.uid in interface_block_uids:
            pass
        else:
            filtered_children.append(child_block)

    for connection_uid, connection_data in export_block.diagram.con_data.items():
        if connection_data.from_uid in interface_block_uids or connection_data.to_uid in interface_block_uids:
            pass
        else:
            filtered_connection_data[connection_uid] = connection_data

    export_block.children = filtered_children
    export_block.diagram.node_data = filtered_node_data
    export_block.diagram.con_data = filtered_connection_data
    _apply_composite_child_interface_if_missing(export_block)
    return export_block




def _build_user_dynamic_template_payload_text(
        block: Block,
        template_name: str,
        target_domain: DynamicSimulationMode,
        device_tpe: DeviceType,
        template_fingerprint: str | None = None,
) -> str:
    """
    Build the complete JSON validation snapshot before filesystem mutation.

    :param block: Persistable symbolic block.
    :param template_name: Final catalogue template name.
    :param target_domain: Selected RMS or EMT domain.
    :param device_tpe: Selected supported device type.
    :param template_fingerprint: Optional precomputed structural identity.
    :return: Deterministic JSON sidecar text.
    """
    payload: Dict[str, object] = dict()

    payload["template_name"] = template_name
    payload["target_domain"] = target_domain.value
    payload["device_tpe"] = device_tpe.name
    if template_fingerprint is None:
        pass
    else:
        payload["template_fingerprint"] = template_fingerprint
    payload["block_data"] = block.to_dict()
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=True,
        sort_keys=True,
    ) + "\n"


def export_user_dynamic_template_json_from_block(
        block: Block,
        output_path: str,
        template_name: str,
        target_domain: DynamicSimulationMode,
        device_tpe: DeviceType,
        progress_callback: Callable[[int, str], None] | None = None,
) -> Path:
    """
    Export one editor block to one standalone JSON payload.

    :param block: Exported symbolic block.
    :param output_path: Destination JSON file path.
    :param template_name: Default runtime template name.
    :param target_domain: Selected RMS or EMT catalogue domain.
    :param device_tpe: Selected supported device type.
    :param progress_callback: Optional UI progress callback.
    :return: Written JSON file path.
    """
    export_block: Block = copy.deepcopy(block)
    destination_path: Path = Path(output_path)
    payload_text: str

    _emit_dynamic_model_import_progress(progress_callback, 0, "Preparing JSON snapshot export...")
    _apply_composite_child_interface_if_missing(export_block)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    _emit_dynamic_model_import_progress(progress_callback, 25, "Serializing block snapshot...")
    payload_text = _build_user_dynamic_template_payload_text(
        block=export_block,
        template_name=template_name,
        target_domain=target_domain,
        device_tpe=device_tpe,
    )
    _emit_dynamic_model_import_progress(progress_callback, 75, "Writing JSON snapshot...")
    destination_path.write_text(payload_text, encoding="utf-8")
    _emit_dynamic_model_import_progress(progress_callback, 100, "JSON snapshot saved")
    return destination_path


def load_user_dynamic_template_json_payload(
        json_path: str,
        progress_callback: Callable[[int, str], None] | None = None,
) -> Tuple[Block, str, DynamicSimulationMode, DeviceType] | None:
    """
    Load one intermediate JSON snapshot exported from the dynamic block editor.

    :param json_path: Source JSON snapshot path.
    :param progress_callback: Optional UI progress callback.
    :return: Tuple ``(block, template_name, target_domain, device_tpe)`` or ``None`` when the payload is invalid.
    """
    _emit_dynamic_model_import_progress(progress_callback, 0, "Reading JSON snapshot...")
    payload_text: str = Path(json_path).read_text(encoding="utf-8")
    _emit_dynamic_model_import_progress(progress_callback, 20, "Parsing JSON snapshot...")
    payload_obj: object = json.loads(payload_text)
    template_name: str
    target_domain: DynamicSimulationMode
    device_tpe: DeviceType
    block: Block

    if isinstance(payload_obj, dict):
        block_data_obj: object | None = payload_obj.get("block_data", None)
        template_name_obj: object | None = payload_obj.get(
            "template_name",
            None,
        )
        target_domain_obj: object | None = payload_obj.get(
            "target_domain",
            None,
        )
        device_tpe_obj: object | None = payload_obj.get("device_tpe", None)
    else:
        return None

    if isinstance(block_data_obj, dict):
        _emit_dynamic_model_import_progress(progress_callback, 55, "Rebuilding symbolic block from JSON...")
        block = Block.parse(
            data=block_data_obj,
            procedural_logic_codec=ProceduralLogicCodec(),
        )
    else:
        return None

    if isinstance(template_name_obj, str):
        template_name = template_name_obj.strip()
    else:
        template_name = ""

    if len(template_name) == 0:
        template_name = block.name.strip()
    else:
        pass

    if len(template_name) == 0:
        template_name = Path(json_path).stem
    else:
        pass

    if target_domain_obj == DynamicSimulationMode.RMS.value:
        target_domain = DynamicSimulationMode.RMS
    else:
        if target_domain_obj == DynamicSimulationMode.EMT.value:
            target_domain = DynamicSimulationMode.EMT
        else:
            return None

    if isinstance(device_tpe_obj, str):
        if device_tpe_obj in DeviceType.__members__:
            device_tpe = DeviceType[device_tpe_obj]
        else:
            return None
    else:
        return None

    _emit_dynamic_model_import_progress(
        progress_callback,
        100,
        "JSON snapshot loaded",
    )
    return block, template_name, target_domain, device_tpe
