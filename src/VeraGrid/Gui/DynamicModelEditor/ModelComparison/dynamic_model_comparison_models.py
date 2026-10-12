# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Typed data and Qt models used by the dynamic-model comparator."""

from __future__ import annotations

import ast
import re
from typing import Dict, List

from PySide6 import QtCore, QtGui

from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import iter_dynamic_editor_entries
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block, compare_n_blocks_structurally
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, NUMBER, Var
from VeraGridEngine.enumerations import (
    DeviceType,
    DynamicSimulationMode,
    ParamPowerFlowReferenceType,
)


def _device_type_sort_key(device_type: DeviceType) -> str:
    """Return a stable human-facing device-type ordering key.

    :param device_type: Device type to order.
    :return: Case-insensitive device-type label.
    """
    sort_key: str = str(device_type.value).casefold()
    return sort_key


def _record_name_sort_key(record: "ComparisonDeviceRecord") -> str:
    """Return a stable ordering key for one comparison device.

    :param record: Device record to order.
    :return: Case-insensitive device name.
    """
    sort_key: str = record.device.name.casefold()
    return sort_key


def build_device_type_prefix(device_type: DeviceType) -> str:
    """Build the deterministic prefix used by generated model-family names.

    :param device_type: Device type represented by the model family.
    :return: Lowercase underscore-separated prefix.
    """
    normalized_name: str = re.sub(r"[^A-Za-z0-9]+", "_", str(device_type.value)).strip("_").lower()
    if normalized_name.endswith("_device"):
        normalized_name = normalized_name.removesuffix("_device")
    else:
        pass
    if normalized_name == "":
        return "device"
    else:
        return normalized_name


def get_saved_model(device: DynamicDevice, mode: DynamicSimulationMode) -> Block:
    """Return the authoritative saved RMS or EMT model for one device.

    :param device: Dynamic network device.
    :param mode: Simulation family to read.
    :return: Persistent root block stored on the device.
    """
    if mode == DynamicSimulationMode.RMS:
        return device.rms_model
    else:
        return device.emt_model


def get_native_template(
        device: DynamicDevice,
        mode: DynamicSimulationMode,
) -> RmsModelTemplate | EmtModelTemplate | None:
    """Return the native template assigned to one device and simulation mode.

    :param device: Dynamic network device.
    :param mode: Simulation family to inspect.
    :return: Assigned native template, or ``None`` for structural grouping.
    """
    if mode == DynamicSimulationMode.RMS:
        return device.rms_template
    else:
        return device.emt_template


class ComparisonDeviceRecord:
    """Pair one circuit device with its authoritative saved model."""

    __slots__ = ("entry", "device", "block", "template")

    def __init__(
            self,
            entry: DynamicEditorEntry,
            device: DynamicDevice,
            block: Block,
            template: RmsModelTemplate | EmtModelTemplate | None,
    ) -> None:
        """Initialize one saved-model record.

        :param entry: Workspace entry for the device.
        :param device: Concrete network device.
        :param block: Persistent RMS or EMT root block.
        :param template: Assigned native template, when present.
        :return: None.
        """
        self.entry: DynamicEditorEntry = entry
        self.device: DynamicDevice = device
        self.block: Block = block
        self.template: RmsModelTemplate | EmtModelTemplate | None = template


class TemplateRecordBucket:
    """Collect records that point to exactly the same native template."""

    __slots__ = ("template", "records")

    def __init__(
            self,
            template: RmsModelTemplate | EmtModelTemplate,
    ) -> None:
        """Initialize an empty identity-based template bucket.

        :param template: Shared native template object.
        :return: None.
        """
        self.template: RmsModelTemplate | EmtModelTemplate = template
        self.records: List[ComparisonDeviceRecord] = list()


class DynamicModelComparisonGroup:
    """Represent one template-backed or structurally equivalent model family."""

    __slots__ = (
        "device_type",
        "records",
        "template",
        "variable_alignment",
        "generated_name",
        "_saved_name",
        "_pending_name",
        "_name_changed",
    )

    def __init__(
            self,
            device_type: DeviceType,
            records: List[ComparisonDeviceRecord],
            template: RmsModelTemplate | EmtModelTemplate | None,
            variable_alignment: Dict[int, List[int]],
            generated_name: str,
    ) -> None:
        """Initialize one selectable comparison group.

        :param device_type: Common network-device type.
        :param records: Devices belonging to the family.
        :param template: Shared native template, or ``None`` for structural groups.
        :param variable_alignment: Canonical reference UID to member UID mapping.
        :param generated_name: Deterministic fallback family name.
        :return: None.
        """
        self.device_type: DeviceType = device_type
        self.records: List[ComparisonDeviceRecord] = records
        self.template: RmsModelTemplate | EmtModelTemplate | None = template
        self.variable_alignment: Dict[int, List[int]] = variable_alignment
        self.generated_name: str = generated_name
        self._saved_name: str = self._resolve_persisted_name()
        self._pending_name: str = self._saved_name
        self._name_changed: bool = False

    def _resolve_persisted_name(self) -> str:
        """Resolve one common saved family label for the structural group.

        :return: Common non-empty label or the generated fallback.
        """
        if self.template is not None:
            return self.template.name
        else:
            pass

        common_name: str | None = None
        record: ComparisonDeviceRecord
        for record in self.records:
            candidate_name: str = record.block.model_family_name.strip()
            if candidate_name == "":
                return self.generated_name
            elif common_name is None:
                common_name = candidate_name
            elif common_name != candidate_name:
                return self.generated_name
            else:
                pass
        if common_name is None:
            return self.generated_name
        else:
            return common_name

    def is_name_editable(self) -> bool:
        """Return whether this structural group can receive a custom family name.

        :return: ``True`` only for non-template structural groups.
        """
        return self.template is None

    def get_display_name(self) -> str:
        """Return the currently staged family label.

        :return: Tree label shown to the user.
        """
        return self._pending_name

    def set_pending_name(self, name: str) -> None:
        """Stage one validated structural family label.

        :param name: Non-empty label entered in the tree.
        :return: None.
        """
        self._pending_name = name
        self._name_changed = name != self._saved_name

    def has_name_changes(self) -> bool:
        """Return whether the group name differs from its saved state.

        :return: Staged-name state.
        """
        return self._name_changed

    def apply_name(self) -> None:
        """Persist the staged family label on every complete saved root model.

        :return: None.
        """
        if self.template is None and self._name_changed:
            record: ComparisonDeviceRecord
            for record in self.records:
                record.block.model_family_name = self._pending_name
            self._saved_name = self._pending_name
            self._name_changed = False
        else:
            pass

    def mapped_variable_uid(self, reference_uid: int, member_index: int) -> int | None:
        """Map a representative variable UID to one equivalent member model.

        :param reference_uid: Variable UID in the representative saved block.
        :param member_index: Group record index.
        :return: Equivalent UID or ``None`` when alignment has no entry.
        """
        if member_index == 0:
            return reference_uid
        else:
            equivalent_uids: List[int] | None = self.variable_alignment.get(reference_uid, None)
        equivalent_index: int = member_index - 1
        if equivalent_uids is not None and equivalent_index < len(equivalent_uids):
            return equivalent_uids[equivalent_index]
        else:
            return None


def collect_comparison_records(
        circuit: MultiCircuit,
        mode: DynamicSimulationMode,
) -> Dict[DeviceType, List[ComparisonDeviceRecord]]:
    """Collect saved non-empty models by concrete network-device type.

    Detached working copies owned by open editors are deliberately inaccessible
    here. The comparator therefore changes only after the editor commits into
    ``device.rms_model`` or ``device.emt_model``.

    :param circuit: Circuit whose saved dynamic models are inspected.
    :param mode: RMS or EMT family.
    :return: Saved-model records grouped by device type.
    """
    result: Dict[DeviceType, List[ComparisonDeviceRecord]] = dict()
    entry: DynamicEditorEntry
    for entry in iter_dynamic_editor_entries(circuit=circuit):
        if mode not in entry.available_modes or not isinstance(entry.api_object, DynamicDevice):
            pass
        else:
            device: DynamicDevice = entry.api_object
            block: Block = get_saved_model(device=device, mode=mode)
            if block.empty():
                pass
            else:
                record: ComparisonDeviceRecord = ComparisonDeviceRecord(
                    entry=entry,
                    device=device,
                    block=block,
                    template=get_native_template(device=device, mode=mode),
                )
                records: List[ComparisonDeviceRecord] | None = result.get(device.device_type, None)
                if records is None:
                    records = list()
                    result[device.device_type] = records
                else:
                    pass
                records.append(record)
    return result


def _partition_template_records(
        records: List[ComparisonDeviceRecord],
) -> tuple[List[TemplateRecordBucket], List[ComparisonDeviceRecord]]:
    """Separate native-template identities from structural candidates.

    :param records: Saved models belonging to one device type.
    :return: Identity-based template buckets and non-template records.
    """
    template_buckets: List[TemplateRecordBucket] = list()
    structural_records: List[ComparisonDeviceRecord] = list()
    record: ComparisonDeviceRecord
    for record in records:
        if record.template is None:
            structural_records.append(record)
        else:
            matching_bucket: TemplateRecordBucket | None = None
            bucket: TemplateRecordBucket
            for bucket in template_buckets:
                if bucket.template is record.template:
                    matching_bucket = bucket
                else:
                    pass
            if matching_bucket is None:
                matching_bucket = TemplateRecordBucket(template=record.template)
                template_buckets.append(matching_bucket)
            else:
                pass
            matching_bucket.records.append(record)
    return template_buckets, structural_records


def build_model_comparison_groups(
        circuit: MultiCircuit,
        mode: DynamicSimulationMode,
) -> List[DynamicModelComparisonGroup]:
    """Build template and canonical structural model families.

    Template-backed devices are grouped by exact template identity. Remaining
    devices are passed directly to the Vectorized RMS structural comparator;
    no GUI hash or alternative equivalence algorithm is introduced.

    :param circuit: Circuit whose models are classified.
    :param mode: RMS or EMT family.
    :return: Ordered comparison groups.
    """
    records_by_type: Dict[DeviceType, List[ComparisonDeviceRecord]] = collect_comparison_records(
        circuit=circuit,
        mode=mode,
    )
    result: List[DynamicModelComparisonGroup] = list()
    ordered_device_types: List[DeviceType] = list(records_by_type.keys())
    ordered_device_types.sort(key=_device_type_sort_key)
    device_type: DeviceType
    for device_type in ordered_device_types:
        records: List[ComparisonDeviceRecord] = records_by_type[device_type]
        records.sort(key=_record_name_sort_key)
        template_buckets: List[TemplateRecordBucket]
        structural_records: List[ComparisonDeviceRecord]
        template_buckets, structural_records = _partition_template_records(records=records)

        # Native-template identity is authoritative and bypasses structural
        # comparison exactly as requested by the model-family contract.
        template_bucket: TemplateRecordBucket
        for template_bucket in template_buckets:
            template_bucket.records.sort(key=_record_name_sort_key)
            result.append(
                DynamicModelComparisonGroup(
                    device_type=device_type,
                    records=template_bucket.records,
                    template=template_bucket.template,
                    variable_alignment=dict(),
                    generated_name=template_bucket.template.name,
                )
            )

        if len(structural_records) == 0:
            pass
        else:
            blocks: List[Block] = list(record.block for record in structural_records)
            model_classes: Dict[int, List[int]]
            variable_alignment: Dict[int, List[int]]
            model_classes, variable_alignment = compare_n_blocks_structurally(blocks=blocks)
            records_by_uid: Dict[int, ComparisonDeviceRecord] = dict()
            record: ComparisonDeviceRecord
            for record in structural_records:
                records_by_uid[record.block.uid] = record

            generated_index: int = 1
            representative_uid: int
            equivalent_uids: List[int]
            for representative_uid, equivalent_uids in model_classes.items():
                group_records: List[ComparisonDeviceRecord] = list()
                representative_record: ComparisonDeviceRecord | None = records_by_uid.get(
                    representative_uid,
                    None,
                )
                if representative_record is None:
                    pass
                else:
                    group_records.append(representative_record)
                    equivalent_uid: int
                    for equivalent_uid in equivalent_uids:
                        equivalent_record: ComparisonDeviceRecord | None = records_by_uid.get(equivalent_uid, None)
                        if equivalent_record is not None:
                            group_records.append(equivalent_record)
                        else:
                            pass
                    generated_name: str = (
                        f"{build_device_type_prefix(device_type=device_type)}_type_{generated_index}"
                    )
                    result.append(
                        DynamicModelComparisonGroup(
                            device_type=device_type,
                            records=group_records,
                            template=None,
                            variable_alignment=variable_alignment,
                            generated_name=generated_name,
                        )
                    )
                    generated_index += 1
    return result


class ComparisonParameterDescriptor:
    """Identify one parameter column in the representative complete block tree."""

    __slots__ = (
        "owner_path",
        "owner_name",
        "variable",
        "is_event_parameter",
        "static_reference",
        "ordinal",
        "header",
    )

    def __init__(
            self,
            owner_path: tuple[int, ...],
            owner_name: str,
            variable: Var,
            is_event_parameter: bool,
            static_reference: ParamPowerFlowReferenceType | None,
            ordinal: int,
            header: str,
    ) -> None:
        """Initialize one representative parameter descriptor.

        :param owner_path: Child-index path from the complete root block.
        :param owner_name: Human-readable owning block name.
        :param variable: Representative parameter variable.
        :param is_event_parameter: Whether the value belongs to ``event_dict``.
        :param static_reference: Device-property reference for a static parameter.
        :param ordinal: Position within the owning parameter mapping.
        :param header: Unique table-column label.
        :return: None.
        """
        self.owner_path: tuple[int, ...] = owner_path
        self.owner_name: str = owner_name
        self.variable: Var = variable
        self.is_event_parameter: bool = is_event_parameter
        self.static_reference: ParamPowerFlowReferenceType | None = static_reference
        self.ordinal: int = ordinal
        self.header: str = header


def _collect_block_paths(
        block: Block,
        parent_path: tuple[int, ...],
        result: List[tuple[tuple[int, ...], Block]],
) -> None:
    """Append one complete block subtree with deterministic child-index paths.

    :param block: Current block node.
    :param parent_path: Path assigned to the current node.
    :param result: Preallocated traversal result being extended.
    :return: None.
    """
    result.append((parent_path, block))
    child_index: int
    child: Block
    for child_index, child in enumerate(block.children):
        _collect_block_paths(
            block=child,
            parent_path=parent_path + (child_index,),
            result=result,
        )


def get_parameter_static_reference(
        block: Block,
        variable: Var,
) -> ParamPowerFlowReferenceType | None:
    """Return the device-property key mapped to one static parameter.

    :param block: Direct block that may own the static mapping.
    :param variable: Symbolic parameter whose mapping is requested.
    :return: Mapped device-property key, or ``None`` when the template mapping is missing.
    """
    result: ParamPowerFlowReferenceType | None = None
    static_reference: ParamPowerFlowReferenceType
    mapped_variable: Var | None
    for static_reference, mapped_variable in block.api_obj_mapping.items():
        if mapped_variable is variable and result is None:
            result = static_reference
        else:
            pass
    return result


def collect_parameter_descriptors(block: Block) -> List[ComparisonParameterDescriptor]:
    """Collect declared static parameters, static mappings and event parameters.

    :param block: Representative persistent root block.
    :return: Ordered parameter-column descriptors.
    """
    block_paths: List[tuple[tuple[int, ...], Block]] = list()
    _collect_block_paths(block=block, parent_path=tuple(), result=block_paths)
    descriptors: List[ComparisonParameterDescriptor] = list()
    used_headers: set[str] = set()
    owner_path: tuple[int, ...]
    owner: Block
    for owner_path, owner in block_paths:
        # Immutable columns retain every declared parameter. The device mapping
        # is optional because a concrete local literal is also a valid source.
        static_reference: ParamPowerFlowReferenceType
        static_parameter: Var | None
        static_ordinal: int
        declared_static_parameter: Var
        for static_ordinal, declared_static_parameter in enumerate(owner.parameters.keys()):
            declared_static_reference: ParamPowerFlowReferenceType | None = get_parameter_static_reference(
                block=owner,
                variable=declared_static_parameter,
            )
            header: str = _build_parameter_header(
                owner=owner,
                owner_path=owner_path,
                variable=declared_static_parameter,
                used_headers=used_headers,
            )
            descriptors.append(
                ComparisonParameterDescriptor(
                    owner_path=owner_path,
                    owner_name=owner.name,
                    variable=declared_static_parameter,
                    is_event_parameter=False,
                    static_reference=declared_static_reference,
                    ordinal=static_ordinal,
                    header=header,
                )
            )

        # Composite roots may expose a child-owned static variable only through
        # api_obj_mapping. Add those mapping-only symbols after declared ones.
        mapping_ordinal: int
        for mapping_ordinal, (static_reference, static_parameter) in enumerate(owner.api_obj_mapping.items()):
            if (isinstance(static_parameter, Var)
                    and static_parameter not in owner.parameters
                    and static_parameter not in owner.event_dict):
                static_ordinal = len(owner.parameters) + mapping_ordinal
                mapped_header: str = _build_parameter_header(
                    owner=owner,
                    owner_path=owner_path,
                    variable=static_parameter,
                    used_headers=used_headers,
                )
                descriptors.append(
                    ComparisonParameterDescriptor(
                        owner_path=owner_path,
                        owner_name=owner.name,
                        variable=static_parameter,
                        is_event_parameter=False,
                        static_reference=static_reference,
                        ordinal=static_ordinal,
                        header=mapped_header,
                    )
                )
            else:
                pass
        # Event parameters remain model-owned expressions. Their optional API
        # mapping is part of the same initialization contract as for constants.
        event_parameter: Var
        event_ordinal: int
        for event_ordinal, event_parameter in enumerate(owner.event_dict.keys()):
            event_header: str = _build_parameter_header(
                owner=owner,
                owner_path=owner_path,
                variable=event_parameter,
                used_headers=used_headers,
            )
            descriptors.append(
                ComparisonParameterDescriptor(
                    owner_path=owner_path,
                    owner_name=owner.name,
                    variable=event_parameter,
                    is_event_parameter=True,
                    static_reference=get_parameter_static_reference(
                        block=owner,
                        variable=event_parameter,
                    ),
                    ordinal=event_ordinal,
                    header=event_header,
                )
            )
    return descriptors


def _build_parameter_header(
        owner: Block,
        owner_path: tuple[int, ...],
        variable: Var,
        used_headers: set[str],
) -> str:
    """Build a readable unique table header for one recursive parameter.

    :param owner: Block that owns the parameter.
    :param owner_path: Child-index path of the owner.
    :param variable: Parameter variable.
    :param used_headers: Headers already allocated in the same table.
    :return: Unique display label.
    """
    if len(owner_path) == 0:
        candidate: str = variable.name
    else:
        owner_label: str = owner.name if owner.name != "" else "block"
        candidate = f"{owner_label} / {variable.name}"
    if candidate not in used_headers:
        result: str = candidate
    else:
        path_label: str = ".".join(str(index + 1) for index in owner_path)
        result = f"{candidate} [{path_label}]"
        duplicate_index: int = 2
        while result in used_headers:
            result = f"{candidate} [{path_label}.{duplicate_index}]"
            duplicate_index += 1
    used_headers.add(result)
    return result


def get_block_at_path(root: Block, path: tuple[int, ...]) -> Block | None:
    """Resolve one deterministic child-index path in a complete block tree.

    :param root: Complete saved root block.
    :param path: Child-index path to follow.
    :return: Resolved block or ``None`` when structures differ.
    """
    current: Block = root
    path_index: int
    for path_index in path:
        if path_index < len(current.children):
            current = current.children[path_index]
        else:
            return None
    return current


class ComparisonParameterBinding:
    """Bind one comparison cell to its authoritative saved-model source."""

    __slots__ = ("owner", "variable", "expression", "static_reference")

    def __init__(
            self,
            owner: Block,
            variable: Var,
            expression: Expr | None,
            static_reference: ParamPowerFlowReferenceType | None,
    ) -> None:
        """Initialize one resolved parameter source.

        :param owner: Block that owns the authoritative mapping.
        :param variable: Symbolic parameter referenced by the mapping.
        :param expression: Local parameter expression, or ``None`` for a mapping-only legacy target.
        :param static_reference: Optional static device-property initialization source.
        :return: None.
        """
        self.owner: Block = owner
        self.variable: Var = variable
        self.expression: Expr | None = expression
        self.static_reference: ParamPowerFlowReferenceType | None = static_reference


def find_parameter_owner_by_uid(
        root: Block,
        variable_uid: int,
        descriptor: ComparisonParameterDescriptor,
) -> ComparisonParameterBinding | None:
    """Find one parameter and its owning mapping by aligned variable UID.

    :param root: Complete saved root block.
    :param variable_uid: Target variable UID.
    :param descriptor: Representative parameter source to resolve.
    :return: Resolved authoritative parameter binding, or ``None``.
    """
    owner: Block
    for owner in root.get_all_blocks():
        if descriptor.is_event_parameter:
            variable: Var
            expression: Expr
            for variable, expression in owner.event_dict.items():
                if variable.uid == variable_uid:
                    return ComparisonParameterBinding(
                        owner=owner,
                        variable=variable,
                        expression=expression,
                        static_reference=get_parameter_static_reference(
                            block=owner,
                            variable=variable,
                        ),
                    )
                else:
                    pass
        else:
            # Resolve the member variable first, then read that member's own
            # api_obj_mapping so mapping differences remain visible in the table.
            declared_static_variable: Var
            for declared_static_variable in owner.parameters.keys():
                if declared_static_variable.uid == variable_uid:
                    member_static_reference: ParamPowerFlowReferenceType | None = get_parameter_static_reference(
                        block=owner,
                        variable=declared_static_variable,
                    )
                    return ComparisonParameterBinding(
                        owner=owner,
                        variable=declared_static_variable,
                        expression=owner.parameters[declared_static_variable],
                        static_reference=member_static_reference,
                    )
                else:
                    pass
            static_reference: ParamPowerFlowReferenceType
            static_variable: Var | None
            for static_reference, static_variable in owner.api_obj_mapping.items():
                if isinstance(static_variable, Var) and static_variable.uid == variable_uid:
                    return ComparisonParameterBinding(
                        owner=owner,
                        variable=static_variable,
                        expression=None,
                        static_reference=static_reference,
                    )
                else:
                    pass
    return None


def find_parameter_owner_by_descriptor(
        root: Block,
        descriptor: ComparisonParameterDescriptor,
) -> ComparisonParameterBinding | None:
    """Resolve a parameter by the unchanged template/tree position fallback.

    :param root: Complete member root block.
    :param descriptor: Representative parameter descriptor.
    :return: Resolved authoritative parameter binding, or ``None``.
    """
    owner: Block | None = get_block_at_path(root=root, path=descriptor.owner_path)
    if owner is None:
        return None
    else:
        pass
    if descriptor.is_event_parameter:
        variables: List[Var] = list(owner.event_dict.keys())
        if descriptor.ordinal < len(variables):
            variable: Var = variables[descriptor.ordinal]
            expression: Expr = owner.event_dict[variable]
        else:
            return None
        if variable.name == descriptor.variable.name:
            return ComparisonParameterBinding(
                owner=owner,
                variable=variable,
                expression=expression,
                static_reference=get_parameter_static_reference(
                    block=owner,
                    variable=variable,
                ),
            )
        else:
            matching_variable: Var
            for matching_variable in variables:
                if matching_variable.name == descriptor.variable.name:
                    return ComparisonParameterBinding(
                        owner=owner,
                        variable=matching_variable,
                        expression=owner.event_dict[matching_variable],
                        static_reference=get_parameter_static_reference(
                            block=owner,
                            variable=matching_variable,
                        ),
                    )
                else:
                    pass
    else:
        # Prefer the declared-parameter order used by the representative. If
        # ordering changed, the symbolic name provides the stable fallback.
        static_variables: List[Var] = list(owner.parameters.keys())
        resolved_static_variable: Var | None = None
        if descriptor.ordinal < len(static_variables):
            ordinal_static_variable: Var = static_variables[descriptor.ordinal]
            if ordinal_static_variable.name == descriptor.variable.name:
                resolved_static_variable = ordinal_static_variable
            else:
                pass
        else:
            pass
        if resolved_static_variable is None:
            matching_static_variable: Var
            for matching_static_variable in static_variables:
                if matching_static_variable.name == descriptor.variable.name:
                    resolved_static_variable = matching_static_variable
                else:
                    pass
        else:
            pass

        # Mapping-only variables are not present in Block.parameters. Search the
        # semantic mapping itself when the declared-parameter lookup has no hit.
        resolved_static_reference: ParamPowerFlowReferenceType | None = None
        if resolved_static_variable is None:
            mapped_static_reference: ParamPowerFlowReferenceType
            mapped_static_variable: Var | None
            for mapped_static_reference, mapped_static_variable in owner.api_obj_mapping.items():
                if (
                        isinstance(mapped_static_variable, Var)
                        and mapped_static_variable.name == descriptor.variable.name
                        and resolved_static_variable is None
                ):
                    resolved_static_variable = mapped_static_variable
                    resolved_static_reference = mapped_static_reference
                else:
                    pass
            if resolved_static_variable is None and descriptor.static_reference is not None:
                semantic_static_variable: Var | None = owner.api_obj_mapping.get(
                    descriptor.static_reference,
                    None,
                )
                if isinstance(semantic_static_variable, Var):
                    resolved_static_variable = semantic_static_variable
                    resolved_static_reference = descriptor.static_reference
                else:
                    pass
            else:
                pass
        else:
            resolved_static_reference = get_parameter_static_reference(
                block=owner,
                variable=resolved_static_variable,
            )
        if resolved_static_variable is not None:
            return ComparisonParameterBinding(
                owner=owner,
                variable=resolved_static_variable,
                expression=owner.parameters.get(resolved_static_variable, None),
                static_reference=resolved_static_reference,
            )
        else:
            pass
    return None


class ComparisonValueCell:
    """Expose one device source or stage one editable local parameter."""

    __slots__ = (
        "owner",
        "variable",
        "expression",
        "is_event_parameter",
        "static_reference",
        "_pending_value",
        "_changed",
    )

    def __init__(
            self,
            owner: Block,
            variable: Var,
            expression: Expr | None,
            is_event_parameter: bool,
            static_reference: ParamPowerFlowReferenceType | None,
    ) -> None:
        """Initialize one table cell from a saved parameter expression.

        :param owner: Complete-tree block owning the parameter mapping.
        :param variable: Parameter key.
        :param expression: Current local parameter expression, when declared.
        :param is_event_parameter: Whether the owner is ``event_dict``.
        :param static_reference: Static device-property key, when applicable.
        :return: None.
        """
        self.owner: Block = owner
        self.variable: Var = variable
        self.expression: Expr | None = expression
        self.is_event_parameter: bool = is_event_parameter
        self.static_reference: ParamPowerFlowReferenceType | None = static_reference
        self._pending_value: NUMBER | None = expression.value if isinstance(expression, Const) else None
        self._changed: bool = False

    def is_editable(self) -> bool:
        """Return whether this cell contains an editable local constant.

        :return: ``True`` only for an unmapped constant-backed parameter.
        """
        editable: bool = self.static_reference is None and isinstance(self.expression, Const)
        return editable

    def get_value(self) -> NUMBER | None | str:
        """Return the staged scalar or read-only symbolic expression.

        :return: Display/edit value.
        """
        if self.static_reference is not None:
            return self.static_reference.value
        elif isinstance(self.expression, Const):
            return self._pending_value
        elif isinstance(self.expression, Expr):
            return str(self.expression)
        else:
            return None

    def set_pending_value(self, value: NUMBER | None) -> None:
        """Stage a parsed scalar replacement.

        :param value: Numeric or undefined scalar value.
        :return: None.
        """
        if self.is_editable():
            self._pending_value = value
            original_value: NUMBER | None = (
                self.expression.value if isinstance(self.expression, Const) else None
            )
            self._changed = value != original_value
        else:
            pass

    def has_changes(self) -> bool:
        """Return whether this cell differs from the saved constant.

        :return: Cell dirty state.
        """
        return self._changed

    def apply(self) -> None:
        """Replace the saved local parameter expression with its staged constant.

        :return: None.
        """
        if self._changed and isinstance(self.expression, Const):
            new_expression: Const = Const(self._pending_value)
            if self.is_event_parameter:
                self.owner.event_dict[self.variable] = new_expression
            else:
                self.owner.parameters[self.variable] = new_expression
            self.expression = new_expression
            self._changed = False
        else:
            pass


def parse_numeric_value(value: object) -> tuple[bool, NUMBER | None]:
    """Parse one spreadsheet edit into a supported scalar constant.

    :param value: Qt editor or clipboard value.
    :return: Acceptance flag and parsed scalar.
    """
    if value is None:
        return True, None
    elif isinstance(value, bool):
        return False, None
    elif isinstance(value, (int, float, complex)):
        return True, value
    elif isinstance(value, str):
        normalized_value: str = value.strip()
        if normalized_value == "" or normalized_value.casefold() == "none":
            return True, None
        else:
            try:
                parsed_value: object = ast.literal_eval(normalized_value)
            except (SyntaxError, ValueError):
                return False, None
            if isinstance(parsed_value, bool):
                return False, None
            elif isinstance(parsed_value, (int, float, complex)):
                return True, parsed_value
            else:
                return False, None
    else:
        return False, None


class DynamicModelComparisonTableModel(QtCore.QAbstractTableModel):
    """Expose devices as rows and recursively collected parameters as columns."""

    dirtyStateChanged = QtCore.Signal(bool)

    __slots__ = ("group", "descriptors", "cells", "_dirty")

    def __init__(
            self,
            group: DynamicModelComparisonGroup | None,
            parent: QtCore.QObject | None = None,
    ) -> None:
        """Build a table snapshot for one selected model family.

        :param group: Selected group or ``None`` for an empty table.
        :param parent: Owning Qt object.
        :return: None.
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.group: DynamicModelComparisonGroup | None = group
        self.descriptors: List[ComparisonParameterDescriptor] = list()
        self.cells: List[List[ComparisonValueCell | None]] = list()
        self._dirty: bool = False
        self._build_snapshot()

    def _build_snapshot(self) -> None:
        """Resolve every representative parameter against every saved model.

        :return: None.
        """
        if self.group is None or len(self.group.records) == 0:
            return
        else:
            self.descriptors = collect_parameter_descriptors(self.group.records[0].block)

        member_index: int
        record: ComparisonDeviceRecord
        for member_index, record in enumerate(self.group.records):
            row_cells: List[ComparisonValueCell | None] = list()
            descriptor: ComparisonParameterDescriptor
            for descriptor in self.descriptors:
                mapped_uid: int | None = self.group.mapped_variable_uid(
                    reference_uid=descriptor.variable.uid,
                    member_index=member_index,
                )
                resolved: ComparisonParameterBinding | None
                if mapped_uid is None:
                    resolved = None
                else:
                    resolved = find_parameter_owner_by_uid(
                        root=record.block,
                        variable_uid=mapped_uid,
                        descriptor=descriptor,
                    )
                if resolved is None:
                    resolved = find_parameter_owner_by_descriptor(
                        root=record.block,
                        descriptor=descriptor,
                    )
                else:
                    pass
                if resolved is None:
                    row_cells.append(None)
                else:
                    row_cells.append(
                        ComparisonValueCell(
                            owner=resolved.owner,
                            variable=resolved.variable,
                            expression=resolved.expression,
                            is_event_parameter=descriptor.is_event_parameter,
                            static_reference=resolved.static_reference,
                        )
                    )
            self.cells.append(row_cells)

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the number of devices in the selected family.

        :param parent: Parent index, unused for a flat table.
        :return: Device row count.
        """
        if parent.isValid() or self.group is None:
            return 0
        else:
            return len(self.group.records)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the device-name column plus every parameter column.

        :param parent: Parent index, unused for a flat table.
        :return: Table column count.
        """
        if parent.isValid():
            return 0
        else:
            return 1 + len(self.descriptors)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> object:
        """Return device labels, staged values and edit-state decoration.

        :param index: Requested table cell.
        :param role: Qt item-data role.
        :return: Role value or ``None``.
        """
        if not index.isValid() or self.group is None:
            return None
        elif index.column() == 0:
            record: ComparisonDeviceRecord = self.group.records[index.row()]
            if role == QtCore.Qt.ItemDataRole.DisplayRole or role == QtCore.Qt.ItemDataRole.EditRole:
                return record.device.name
            elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
                return f"{record.device.device_type.value}: {record.device.name}"
            else:
                return None
        else:
            cell: ComparisonValueCell | None = self.cells[index.row()][index.column() - 1]
            if cell is None:
                if role == QtCore.Qt.ItemDataRole.ToolTipRole:
                    descriptor: ComparisonParameterDescriptor = self.descriptors[index.column() - 1]
                    if not descriptor.is_event_parameter:
                        if descriptor.static_reference is not None:
                            return (
                                f"Static reference ParamPowerFlowReferenceType."
                                f"{descriptor.static_reference.name} is not mapped in this saved model"
                            )
                        else:
                            return "This static parameter could not be aligned in the saved model"
                    else:
                        return "This event parameter could not be aligned in the saved model"
                else:
                    return None
            elif role == QtCore.Qt.ItemDataRole.DisplayRole or role == QtCore.Qt.ItemDataRole.EditRole:
                value: NUMBER | None | str = cell.get_value()
                return "" if value is None else value
            elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
                if cell.static_reference is not None:
                    return (
                        f"Static device-property reference: "
                        f"ParamPowerFlowReferenceType.{cell.static_reference.name}"
                    )
                elif not cell.is_event_parameter:
                    return (
                        f"Fixed local parameter: {cell.variable.name}. "
                        "It has no grid-device initialization mapping."
                    )
                elif cell.is_editable():
                    return f"Event parameter: {cell.variable.name}"
                else:
                    return "Symbolic parameter expressions are read-only in the comparator"
            elif role == QtCore.Qt.ItemDataRole.BackgroundRole and cell.has_changes():
                return QtGui.QBrush(QtGui.QColor(73, 117, 99, 90))
            else:
                return None

    def headerData(
            self,
            section: int,
            orientation: QtCore.Qt.Orientation,
            role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> object:
        """Return table headers and parameter-source tooltips.

        :param section: Row or column section.
        :param orientation: Header orientation.
        :param role: Qt item-data role.
        :return: Header value or ``None``.
        """
        if role != QtCore.Qt.ItemDataRole.DisplayRole and role != QtCore.Qt.ItemDataRole.ToolTipRole:
            return None
        elif orientation == QtCore.Qt.Orientation.Vertical:
            return section + 1
        elif section == 0:
            return "Device"
        else:
            descriptor: ComparisonParameterDescriptor = self.descriptors[section - 1]
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return descriptor.header
            else:
                parameter_kind: str = "event_dict" if descriptor.is_event_parameter else "parameters"
                return f"{descriptor.owner_name}: {descriptor.variable.name} ({parameter_kind})"

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """Make only scalar parameter cells editable.

        :param index: Candidate table cell.
        :return: Qt item flags.
        """
        result: QtCore.Qt.ItemFlag = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if index.isValid() and index.column() > 0:
            cell: ComparisonValueCell | None = self.cells[index.row()][index.column() - 1]
            if cell is not None and cell.is_editable():
                result |= QtCore.Qt.ItemFlag.ItemIsEditable
            else:
                pass
        else:
            pass
        return result

    def setData(
            self,
            index: QtCore.QModelIndex,
            value: object,
            role: int = QtCore.Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Stage one scalar edit without mutating the persistent block.

        :param index: Edited table cell.
        :param value: Editor or clipboard value.
        :param role: Qt item-data role.
        :return: Whether the value was accepted.
        """
        if not index.isValid() or index.column() == 0 or role != QtCore.Qt.ItemDataRole.EditRole:
            return False
        else:
            cell: ComparisonValueCell | None = self.cells[index.row()][index.column() - 1]
        if cell is None or not cell.is_editable():
            return False
        else:
            accepted: bool
            parsed_value: NUMBER | None
            accepted, parsed_value = parse_numeric_value(value=value)
        if not accepted:
            return False
        else:
            cell.set_pending_value(value=parsed_value)
            self.dataChanged.emit(
                index,
                index,
                list((
                    QtCore.Qt.ItemDataRole.DisplayRole,
                    QtCore.Qt.ItemDataRole.EditRole,
                    QtCore.Qt.ItemDataRole.BackgroundRole,
                )),
            )
            self._refresh_dirty_state()
            return True

    def get_column_type(self, column_index: int) -> type:
        """Return the typed spreadsheet signature for one column.

        :param column_index: Table column index.
        :return: String for device names and complex-capable numeric type otherwise.
        """
        if column_index == 0:
            column_type: type = str
        else:
            # Mapped cells are read-only labels, so every editable parameter
            # cell in these columns is a local numeric value regardless of
            # whether another compared model uses a device mapping.
            column_type = complex
        return column_type

    def fill_column_from_row(self, column_index: int, source_row: int) -> int:
        """Stage one source value for every editable cell in its parameter column.

        :param column_index: Parameter column to fill.
        :param source_row: Row providing the value.
        :return: Number of accepted target edits.
        """
        if column_index <= 0 or source_row < 0 or source_row >= self.rowCount():
            return 0
        else:
            source_index: QtCore.QModelIndex = self.index(source_row, column_index)
            source_value: object = self.data(source_index, QtCore.Qt.ItemDataRole.EditRole)
        accepted_count: int = 0
        row_index: int
        for row_index in range(self.rowCount()):
            target_index: QtCore.QModelIndex = self.index(row_index, column_index)
            if self.flags(target_index) & QtCore.Qt.ItemFlag.ItemIsEditable:
                if self.setData(target_index, source_value, QtCore.Qt.ItemDataRole.EditRole):
                    accepted_count += 1
                else:
                    pass
            else:
                pass
        return accepted_count

    def _refresh_dirty_state(self) -> None:
        """Recompute and emit the aggregate staged-cell state.

        :return: None.
        """
        dirty: bool = False
        row: List[ComparisonValueCell | None]
        cell: ComparisonValueCell | None
        for row in self.cells:
            for cell in row:
                if cell is not None and cell.has_changes():
                    dirty = True
                else:
                    pass
        if dirty != self._dirty:
            self._dirty = dirty
            self.dirtyStateChanged.emit(dirty)
        else:
            pass

    def has_changes(self) -> bool:
        """Return whether the table contains staged scalar edits.

        :return: Aggregate table dirty state.
        """
        return self._dirty

    def apply_changes(self) -> None:
        """Commit every staged cell to its original complete saved model.

        :return: None.
        """
        row: List[ComparisonValueCell | None]
        cell: ComparisonValueCell | None
        for row in self.cells:
            for cell in row:
                if cell is not None:
                    cell.apply()
                else:
                    pass
        self._dirty = False
        self.dirtyStateChanged.emit(False)
