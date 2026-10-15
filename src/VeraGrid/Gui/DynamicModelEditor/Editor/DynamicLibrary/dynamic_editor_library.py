# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import math
import uuid

from typing import Dict, List, Optional, Sequence

from PySide6 import QtCore, QtGui

from VeraGrid.Gui.Icons.icon_associations import device_type_icons
from VeraGridEngine.enumerations import DeviceType, DynamicSimulationMode
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog import (
    BasicBlockTemplateDescriptor,
    ExactMathematicalBlockDescriptor,
    build_exact_mathematical_block_descriptors,
    get_editor_ready_basic_block_catalog_descriptors,
)
from VeraGridEngine.Templates.ProceduralLogicCatalog import (
    ProceduralBlockParameterSpec,
    ProceduralBlockTemplateDescriptor,
)
from VeraGridEngine.Templates.InternationalStandardsCatalog import (
    InternationalStandardTemplateDescriptor,
    load_international_standard_template,
)
from VeraGridEngine.enumerations import (
    BlockType,
    DynamicDeviceTemplateType,
    ExactMathematicalBlockOperation,
    InternationalStandardModel,
    ProceduralLogicType,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_utilities import (
    create_block_of_type,
    create_default_template_builder,
)
from VeraGridEngine.Templates.template_definition import TemplateDefinition
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Templates as tem


def _new_uid() -> int:
    """
    Generate a fresh integer identifier.

    :return: Fresh uid.
    """
    return uuid.uuid4().int


class LibraryLeafSpec:
    """Describe one draggable leaf entry in the library tree."""

    __slots__ = ("label", "payload", "search_text")

    def __init__(self, label: str, payload: object, search_text: str = "") -> None:
        """Create an immutable-by-convention library leaf description.

        :param label: Text displayed in the library tree.
        :param payload: Typed object materialized when the leaf is dropped.
        :param search_text: Optional text used by the recursive filter.
        :return: None.
        """
        self.label: str = label
        self.payload: object = payload
        self.search_text: str = search_text


class LibraryDeviceTemplateSpec:
    """Describe one complete reusable device model owned by the Library."""

    __slots__ = (
        "label",
        "source",
        "mode",
        "device_type",
        "category_path",
        "unique_key",
        "description",
        "search_text",
        "compatible_device_types",
    )

    def __init__(
            self,
            label: str,
            source: DynamicDeviceTemplateType | BlockType | InternationalStandardTemplateDescriptor,
            mode: DynamicSimulationMode,
            device_type: DeviceType,
            category_path: tuple[str, ...],
            unique_key: str,
            description: str,
            search_text: str = "",
            compatible_device_types: tuple[DeviceType, ...] | None = None,
    ) -> None:
        """Store one canonical device-template registration.

        :param label: Human-facing Library and catalogue label.
        :param source: Typed materialization identifier.
        :param mode: Dynamic simulation domain.
        :param device_type: Physical device type accepting the template.
        :param category_path: Path below the ``Devices`` branch.
        :param unique_key: Stable key persisted by catalogue imports.
        :param description: Human-facing explanation of the model behavior.
        :param search_text: Optional additional filter terms.
        :param compatible_device_types: Physical device types that may use the
            same registered drawing without duplicating the Library entry.
        :return: None.
        """
        self.label: str = label
        self.source: DynamicDeviceTemplateType | BlockType | InternationalStandardTemplateDescriptor = source
        self.mode: DynamicSimulationMode = mode
        self.device_type: DeviceType = device_type
        self.category_path: tuple[str, ...] = category_path
        self.unique_key: str = unique_key
        self.description: str = description
        self.search_text: str = search_text
        if compatible_device_types is None:
            self.compatible_device_types: tuple[DeviceType, ...] = (device_type,)
        else:
            self.compatible_device_types = compatible_device_types

    def is_compatible_with(self, device_type: DeviceType) -> bool:
        """Check whether this drawing can model one physical device type.

        :param device_type: Physical editor host under consideration.
        :return: ``True`` when the registered drawing is compatible.
        """
        return device_type in self.compatible_device_types


class DynamicsLibraryTreeModel(QtGui.QStandardItemModel):
    __slots__ = ("_block_role", "_mime_type", "_drag_token_role", "_drag_payloads")

    def __init__(self, block_role: int, mime_type: str) -> None:
        """Create a source model that owns drag payloads explicitly.

        :param block_role: Qt item-data role containing the typed payload.
        :param mime_type: MIME type used for internal drag operations.
        :return: None.
        """
        super().__init__()
        self._block_role: int = block_role
        self._mime_type: str = mime_type
        self._drag_token_role: int = block_role + 1
        self._drag_payloads: Dict[str, object] = dict()

        self.setHorizontalHeaderLabels(list(("Name", "Description")))

    def register_drag_payload(self, item: QtGui.QStandardItem, payload: object) -> None:
        """Register one payload and expose its opaque drag token on an item.

        :param item: Tree item that starts the drag.
        :param payload: Typed editor object represented by the item.
        :return: None.
        """
        token: str = str(_new_uid())
        self._drag_payloads[token] = payload
        item.setData(payload, self._block_role)
        item.setData(token, self._drag_token_role)

    def get_drag_payload(self, token: str) -> object | None:
        """Return the payload associated with one drag token.

        :param token: Opaque token serialized in the MIME data.
        :return: Registered payload or ``None`` when the token is unknown.
        """
        return self._drag_payloads.get(token, None)

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """Return drag-enabled flags only for supported leaf payloads.

        :param index: Source-model index being queried by Qt.
        :return: Flags appropriate for a category or draggable leaf.
        """
        if index.isValid():
            if index.column() != 0:
                return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
            else:
                pass
            item: QtGui.QStandardItem | None = self.itemFromIndex(index)
            if item is not None:
                item_data: object = item.data(self._block_role)
                if is_supported_library_payload(item_data):
                    return (QtCore.Qt.ItemFlag.ItemIsEnabled
                            | QtCore.Qt.ItemFlag.ItemIsSelectable
                            | QtCore.Qt.ItemFlag.ItemIsDragEnabled)
                else:
                    return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
            else:
                return QtCore.Qt.ItemFlag.ItemIsEnabled
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def mimeTypes(self) -> List[str]:
        """Return the MIME types produced by this model.

        :return: Single internal dynamic-editor MIME type.
        """
        return list((self._mime_type,))

    def supportedDragActions(self) -> QtCore.Qt.DropAction:
        """Return the copy action used for library drags.

        :return: Qt copy action.
        """
        return QtCore.Qt.DropAction.CopyAction

    def mimeData(self, indexes: List[QtCore.QModelIndex]) -> QtCore.QMimeData:
        """Serialize the first supported selected leaf as an opaque token.

        :param indexes: Selected source-model indexes supplied by Qt.
        :return: MIME data containing a registered payload token when possible.
        """
        mime_data: QtCore.QMimeData = QtCore.QMimeData()

        index: QtCore.QModelIndex
        for index in indexes:
            if index.isValid():
                source_index: QtCore.QModelIndex = index.siblingAtColumn(0)
                item: QtGui.QStandardItem | None = self.itemFromIndex(source_index)
                if item is not None:
                    item_token: object = item.data(self._drag_token_role)
                    item_data: object = item.data(self._block_role)
                    if isinstance(item_token, str) and is_supported_library_payload(item_data):
                        mime_data.setData(self._mime_type, QtCore.QByteArray(item_token.encode("utf-8")))
                        return mime_data
                    else:
                        pass
                else:
                    pass
            else:
                pass

        return mime_data


class LibraryTreeFilterProxyModel(QtCore.QSortFilterProxyModel):
    __slots__ = ("_search_role",)

    def __init__(self, search_role: int, parent: QtCore.QObject | None = None) -> None:
        """Create a recursive proxy filtering one dedicated search role.

        :param search_role: Source-model role containing normalized search text.
        :param parent: Optional Qt owner.
        :return: None.
        """
        super().__init__(parent)
        self._search_role: int = search_role
        self.setRecursiveFilteringEnabled(True)
        self.setAutoAcceptChildRows(True)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterRole(search_role)
        self.setFilterKeyColumn(0)

    def mimeData(self, indexes: List[QtCore.QModelIndex]) -> QtCore.QMimeData:
        """Map proxy indexes to the source model before serializing a drag.

        :param indexes: Selected proxy-model indexes.
        :return: MIME data produced by the typed source model.
        """
        source_model: QtCore.QAbstractItemModel | None = self.sourceModel()
        if isinstance(source_model, DynamicsLibraryTreeModel):
            source_indexes: List[QtCore.QModelIndex] = [self.mapToSource(index) for index in indexes if index.isValid()]
            return source_model.mimeData(source_indexes)
        else:
            return super().mimeData(indexes)

    def supportedDragActions(self) -> QtCore.Qt.DropAction:
        """Delegate supported drag actions to the source model.

        :return: Drag actions supported by the active source model.
        """
        source_model: QtCore.QAbstractItemModel | None = self.sourceModel()
        if isinstance(source_model, DynamicsLibraryTreeModel):
            return source_model.supportedDragActions()
        else:
            return super().supportedDragActions()


class DynamicEditorLibrary:
    """Build the mode- and device-specific dynamic block library."""

    __slots__ = (
        "api_object",
        "mode",
        "templates_list",
        "block_role",
        "mime_type",
        "LIBRARY_SEARCH_TEXT_ROLE",
        "tree_structure",
        "library_model",
    )

    def __init__(self,
                 api_object: ALL_DEV_TYPES,
                 mode: DynamicSimulationMode = DynamicSimulationMode.RMS,
                 templates_list: Optional[List[RmsModelTemplate | EmtModelTemplate | FmuTemplate]] = None) -> None:
        """Create a library definition for one device and simulation mode.

        :param api_object: Static device associated with the editor.
        :param mode: RMS or EMT editor mode.
        :param templates_list: Optional catalogue templates exposed as leaves.
        :return: None.
        """

        self.api_object: ALL_DEV_TYPES = api_object
        self.mode: DynamicSimulationMode = mode
        self.templates_list: Optional[List[RmsModelTemplate | EmtModelTemplate | FmuTemplate]] = templates_list
        self.block_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 300
        self.mime_type: str = "application/x-veragrid-dynamics-block"
        self.LIBRARY_SEARCH_TEXT_ROLE: int = int(QtCore.Qt.ItemDataRole.UserRole) + 502

        # Build one projection of the canonical mode library for the active
        # physical device. The catalogue uses the same builders without this
        # device filter, so availability cannot drift between the two views.
        active_device_type: DeviceType = (
            self.api_object.device_type if self.api_object is not None else DeviceType.NoDevice
        )
        self.tree_structure: Dict[str, object] = build_dynamic_library_structure(
            mode=mode,
            device_type=active_device_type,
        )

        self.tree_structure["Tools"] = list((
            LibraryLeafSpec("Signal pair", BlockType.FROM_GOTO),
            LibraryLeafSpec("Measurements", BlockType.INPUT_CONN),
            LibraryLeafSpec("Generic device", BlockType.GENERIC),
        ))

        if self.templates_list:
            self.tree_structure["Templates"] = dict((("Available", [LibraryLeafSpec(template.name, template, template.name) for template in
                              self.templates_list]),))
        else:
            pass

        # build and add library model
        self.library_model: DynamicsLibraryTreeModel = self.build_library_tree_model()

    def build_library_tree_model(self) -> DynamicsLibraryTreeModel:
        """
        Build the source tree-view model for dynamic library.

        :return: Populated source model owned by the editor library.
        """

        model: DynamicsLibraryTreeModel = DynamicsLibraryTreeModel(self.block_role, self.mime_type)
        root_item: QtGui.QStandardItem = model.invisibleRootItem()

        category: str
        branch_data: object
        for category, branch_data in self.tree_structure.items():
            self._append_library_branch(model, root_item, category, branch_data)

        return model

    def _append_library_branch(self,
                               model: DynamicsLibraryTreeModel,
                               parent_item: QtGui.QStandardItem,
                               branch_label: str,
                               branch_data: object,
                               path_tokens: tuple[str, ...] = tuple()) -> None:
        """
        Append one recursive library branch into the tree model.

        :param model: Source model receiving the branch.
        :param parent_item: Parent item under which the branch is inserted.
        :param branch_label: Visible branch label.
        :param branch_data: Validated nested branch dictionary or leaf list.
        :param path_tokens: Ancestor labels used to build searchable text.
        :return: None.
        """

        branch_item: QtGui.QStandardItem = QtGui.QStandardItem(branch_label)
        description_item: QtGui.QStandardItem = QtGui.QStandardItem("")
        branch_item.setEditable(False)
        description_item.setEditable(False)
        branch_item.setData(" ".join((*path_tokens, branch_label)).strip(), self.LIBRARY_SEARCH_TEXT_ROLE)
        set_library_branch_icon(item=branch_item, branch_label=branch_label)
        parent_item.appendRow(list((branch_item, description_item)))

        if isinstance(branch_data, dict):
            child_label: str
            child_data: object
            for child_label, child_data in branch_data.items():
                self._append_library_branch(model, branch_item, child_label, child_data, (*path_tokens, branch_label))
        else:
            if isinstance(branch_data, list):
                leaf: LibraryLeafSpec
                for leaf in sorted(branch_data, key=_library_leaf_label_sort_key):
                    item: QtGui.QStandardItem = QtGui.QStandardItem(leaf.label)
                    leaf_description: str = build_library_item_description(payload=leaf.payload)
                    leaf_description_item: QtGui.QStandardItem = QtGui.QStandardItem(leaf_description)
                    item.setEditable(False)
                    leaf_description_item.setEditable(False)
                    if len(leaf.search_text) > 0:
                        search_text: str = f"{leaf.search_text} {leaf_description}".strip()
                    else:
                        search_text = f"{leaf.label} {leaf_description}".strip()
                    item.setData(search_text, self.LIBRARY_SEARCH_TEXT_ROLE)
                    item.setToolTip(leaf_description)
                    leaf_description_item.setToolTip(leaf_description)
                    if isinstance(leaf.payload, ProceduralBlockTemplateDescriptor):
                        procedural_tooltip: str = (
                            f"{leaf.payload.display_label} — {leaf.payload.logic_tpe.value}. "
                            "Drag onto the canvas or double-click to insert."
                        )
                        if leaf.payload.requires_configuration:
                            procedural_tooltip += " Complete the external target identifiers in Python code."
                        else:
                            pass
                        item.setToolTip(procedural_tooltip)
                    elif isinstance(leaf.payload, InternationalStandardTemplateDescriptor):
                        item.setToolTip(
                            f"{leaf.payload.display_label} — {leaf_description}. "
                            "Drag onto the canvas or double-click to insert."
                        )
                    else:
                        pass
                    set_library_item_icon(item, leaf.payload)
                    model.register_drag_payload(item, leaf.payload)
                    branch_item.appendRow(list((item, leaf_description_item)))
            else:
                raise TypeError(f"Unsupported library branch data type {type(branch_data)!r}")


def build_native_device_description(
        source: DynamicDeviceTemplateType | BlockType,
        label: str,
) -> str:
    """Return the functional description of one native device template.

    Descriptions live beside the native-device registry rather than in the
    tree rendering code. This keeps the same text available to the Library,
    catalogue dialogue, tooltips, and search without materializing a model.

    :param source: Typed native materialization source.
    :param label: Human-facing template label used by related source variants.
    :return: Functional description of the complete device template.
    """
    if source == DynamicDeviceTemplateType.RMS_COMPLETE_GENERATOR:
        description: str = (
            "Complete synchronous-generator RMS model with GENQEC machine, exciter, governor, and stabilizer"
        )
    elif source == DynamicDeviceTemplateType.RMS_GENCLS:
        description = "Classical two-state synchronous-generator GENCLS RMS model"
    elif source == BlockType.GENQEC:
        description = "Synchronous-generator GENQEC RMS model with quadratic magnetic saturation"
    elif source == BlockType.GENRAW:
        description = "Round-rotor synchronous-generator GENROU/GENROW RMS machine model"
    elif source == BlockType.VOLTAGE_SOURCE_RMS:
        description = "Ideal voltage-source RMS model for a generator or external-grid equivalent"
    elif source == DynamicDeviceTemplateType.RMS_PVD1:
        description = "PVD1 photovoltaic generator RMS model with inverter electrical controls"
    elif source == DynamicDeviceTemplateType.RMS_PVD1_COMPLETE:
        description = "Complete PVD1 photovoltaic RMS model with inverter, plant, and DC-side controls"
    elif source == DynamicDeviceTemplateType.RMS_PVD1_DC_MPPT:
        description = "PVD1 photovoltaic RMS model with a DC source and maximum-power-point tracking"
    elif source == DynamicDeviceTemplateType.RMS_PVD1_DC_LINK_MPPT:
        description = "PVD1 photovoltaic RMS model with DC-link dynamics and maximum-power-point tracking"
    elif source == DynamicDeviceTemplateType.RMS_PVD1_DC_LINK_BESS:
        description = "PVD1 battery-storage RMS model with inverter and DC-link dynamics"
    elif source == DynamicDeviceTemplateType.RMS_ESD1:
        description = "ESD1 battery energy-storage RMS model with active and reactive power controls"
    elif source == BlockType.LINE_RMS:
        description = "AC transmission-line RMS model using a pi-equivalent network"
    elif source == BlockType.DC_LINE_RMS:
        description = "DC transmission-line RMS model using a series resistance-inductance branch"
    elif source == BlockType.TRANSFORMER_2W_RMS:
        description = "Ideal two-winding transformer RMS model"
    elif source == BlockType.LOAD_RMS:
        description = "Static constant-power load RMS model initialized from the solved operating point"
    elif source == DynamicDeviceTemplateType.RMS_SHUNT:
        description = "Constant-admittance shunt RMS model"
    elif source == BlockType.GFL_CONVERTER_RMS:
        description = "Grid-following voltage-source converter RMS model with PLL and current control"
    elif source == BlockType.GFL_VSC_HVDC_RMS:
        description = "Complete grid-following VSC-HVDC terminal RMS model with AC and DC controls"
    elif source == DynamicDeviceTemplateType.EMT_COMPLETE_GENERATOR:
        description = "Complete three-phase synchronous-generator EMT model with machine and controls"
    elif source == BlockType.EMT_THEVENIN:
        description = "Three-phase Thevenin generator EMT model behind a series resistance-inductance impedance"
    elif source == DynamicDeviceTemplateType.EMT_IDEAL_CONVERTER:
        description = "Averaged ideal voltage-source converter EMT model without semiconductor switching"
    elif source == BlockType.COMPLETE_PSEUDO_VSC_EMT:
        description = "Complete averaged voltage-source converter EMT model with pseudo-switching behavior"
    elif source == DynamicDeviceTemplateType.EMT_SWITCHED_CONVERTER:
        description = "Explicitly switched three-phase voltage-source converter EMT model"
    elif source == DynamicDeviceTemplateType.EMT_GFM:
        description = "Grid-forming voltage-source converter EMT model with voltage and frequency control"
    elif source == BlockType.BESS_EMT:
        description = "Battery energy-storage EMT model with averaged grid-following converter controls"
    elif source == BlockType.PV_EMT:
        description = "Photovoltaic plant EMT model with averaged grid-following converter controls"
    elif source == BlockType.DC_LOAD_EMT:
        description = "Dynamic DC load EMT model connected to a DC network"
    elif source == BlockType.EXP_LOAD_EMT:
        description = "Three-phase exponential load EMT model with voltage-dependent active and reactive power"
    elif source == BlockType.ZIP_LOAD_EMT:
        description = "Three-phase ZIP load EMT model combining constant impedance, current, and power"
    elif source == DynamicDeviceTemplateType.EMT_SINGLE_CAGE_INDUCTION_MOTOR:
        description = "Three-phase single-cage induction-motor EMT model"
    elif source == DynamicDeviceTemplateType.EMT_DOUBLE_CAGE_INDUCTION_MOTOR:
        description = "Three-phase double-cage induction-motor EMT model"
    elif source == BlockType.R_LOAD_EMT:
        description = "Three-phase resistive shunt EMT model with independently selectable phases"
    elif source == BlockType.L_LOAD_EMT:
        description = "Three-phase inductive shunt EMT model with independently selectable phases"
    elif source == BlockType.C_LOAD_EMT:
        description = "Three-phase capacitive shunt EMT model with independently selectable phases"
    elif source == BlockType.EMT_PI_LINE:
        description = "Three-phase lumped-parameter pi-section transmission-line EMT model"
    elif source == BlockType.EMT_BERGERON_LINE:
        description = "Three-phase distributed-parameter Bergeron travelling-wave line EMT model"
    elif source == BlockType.EMT_DC_LINE:
        description = "DC transmission-line EMT model with electrical dynamics and power input"
    elif source == BlockType.TRAFO_EMT:
        description = "Three-phase two-winding transformer EMT model with winding electrical dynamics"
    elif source == BlockType.XFMR_TRANSFORMER:
        description = "XFMR three-phase transformer EMT model with configurable winding connections"
    elif source == BlockType.EMT_GENERATOR:
        description = "Simple three-phase synchronous-generator EMT model"
    elif source == BlockType.VOLTAGE_SOURCE_EMT:
        description = "Single-phase sinusoidal voltage-source EMT model"
    elif source == BlockType.CURRENT_SOURCE_EMT:
        description = "Single-phase sinusoidal current-source EMT model"
    elif source == BlockType.CONTROLLED_VOLTAGE_SOURCE_EMT:
        description = "Single-phase EMT voltage source driven by an external control signal"
    elif source == BlockType.CONTROLLED_CURRENT_SOURCE_EMT:
        description = "Single-phase EMT current source driven by an external control signal"
    elif source == BlockType.BALANCED_3PH_VOLTAGE_SOURCE_EMT:
        description = "Balanced three-phase sinusoidal voltage-source EMT model"
    elif source == BlockType.BALANCED_3PH_CURRENT_SOURCE_EMT:
        description = "Balanced three-phase sinusoidal current-source EMT model"
    elif source == BlockType.CONTROLLED_BALANCED_3PH_VOLTAGE_SOURCE_EMT:
        description = "Balanced three-phase EMT voltage source driven by external control signals"
    elif source == BlockType.CONTROLLED_BALANCED_3PH_CURRENT_SOURCE_EMT:
        description = "Balanced three-phase EMT current source driven by external control signals"
    elif source == BlockType.ARBITRARY_WAVEFORM_VOLTAGE_SOURCE_EMT:
        description = "EMT voltage source defined by an arbitrary time-domain waveform"
    elif source == BlockType.ARBITRARY_WAVEFORM_CURRENT_SOURCE_EMT:
        description = "EMT current source defined by an arbitrary time-domain waveform"
    elif source == BlockType.STEP_VOLTAGE_SOURCE_EMT:
        description = "EMT voltage source that applies a configurable step waveform"
    elif source == BlockType.STEP_CURRENT_SOURCE_EMT:
        description = "EMT current source that applies a configurable step waveform"
    elif source == BlockType.RAMP_VOLTAGE_SOURCE_EMT:
        description = "EMT voltage source that applies a configurable ramp waveform"
    elif source == BlockType.RAMP_CURRENT_SOURCE_EMT:
        description = "EMT current source that applies a configurable ramp waveform"
    elif source == BlockType.DOUBLE_EXPONENTIAL_CURRENT_SOURCE_EMT:
        description = "EMT impulse-current source using a double-exponential waveform"
    elif source == BlockType.HEIDLER_CURRENT_SOURCE_EMT:
        description = "EMT lightning-current source using the Heidler impulse function"
    elif source == BlockType.CIGRE_SURGE_CURRENT_SOURCE_EMT:
        description = "EMT lightning-current source using the CIGRE surge waveform"
    elif source == BlockType.PV_POWER_PLANT_EMT:
        description = "Three-phase photovoltaic power-plant EMT model with converter interface"
    elif source == BlockType.BATTERY_EMT:
        description = "Battery EMT model with state-of-charge and DC electrical dynamics"
    elif source == BlockType.EMT_JMARTI_LINE:
        description = "Frequency-dependent JMarti travelling-wave transmission-line EMT model"
    elif source == BlockType.SWITCH_EMT:
        description = "Controlled ideal electrical switch EMT model"
    elif source == BlockType.GROUND_EMT:
        description = "Electrical ground reference for an EMT network"
    elif source == BlockType.GROUNDING_LINK_EMT:
        description = "Configurable grounding connection between an EMT node and ground"
    elif source == BlockType.NONLINEAR_RESISTOR_EMT:
        description = "Nonlinear resistor EMT model defined by its voltage-current characteristic"
    elif source == BlockType.RLC_COMBO_EMT:
        description = "Configurable resistor-inductor-capacitor branch for an EMT network"
    elif source == BlockType.DC_VOLTAGE_SOURCE_EMT:
        description = "Ideal constant DC voltage-source EMT model"
    elif source == BlockType.DC_CURRENT_SOURCE_EMT:
        description = "Ideal constant DC current-source EMT model"
    elif source == BlockType.CONTROLLED_DC_VOLTAGE_SOURCE_EMT:
        description = "DC voltage-source EMT model driven by an external control signal"
    elif source == BlockType.CONTROLLED_DC_CURRENT_SOURCE_EMT:
        description = "DC current-source EMT model driven by an external control signal"
    else:
        description = f"{label} complete dynamic-device template"

    return description


def _build_native_device_spec(
        label: str,
        source: DynamicDeviceTemplateType | BlockType,
        mode: DynamicSimulationMode,
        device_type: DeviceType,
        category_name: str,
        unique_key: str,
        compatible_device_types: tuple[DeviceType, ...] | None = None,
) -> LibraryDeviceTemplateSpec:
    """Build one native device registration with a canonical Library path.

    :param label: Visible device-template label.
    :param source: Typed native materialization source.
    :param mode: Dynamic simulation domain.
    :param device_type: Compatible physical device type.
    :param category_name: Category below ``Devices/Native``.
    :param unique_key: Stable catalogue identity.
    :param compatible_device_types: Physical device types sharing this entry.
    :return: Complete device-template specification.
    """
    return LibraryDeviceTemplateSpec(
        label=label,
        source=source,
        mode=mode,
        device_type=device_type,
        category_path=("Native", category_name),
        unique_key=unique_key,
        description=build_native_device_description(source=source, label=label),
        compatible_device_types=compatible_device_types,
    )


def build_rms_native_device_specs() -> List[LibraryDeviceTemplateSpec]:
    """Build every native RMS device entry in canonical Library order.

    :return: Complete native RMS device specifications.
    """
    return list((
        _build_native_device_spec("Complete generator", DynamicDeviceTemplateType.RMS_COMPLETE_GENERATOR,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_COMPLETE_GENERATOR.value),
        _build_native_device_spec("Generator GENCLS", DynamicDeviceTemplateType.RMS_GENCLS,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_GENCLS.value),
        _build_native_device_spec("Generator QEC", BlockType.GENQEC,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_GENQEC.value),
        _build_native_device_spec("Generator basic", BlockType.GENRAW,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_GENROW.value),
        _build_native_device_spec("Voltage source", BlockType.VOLTAGE_SOURCE_RMS,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_VOLTAGE_SOURCE.value),
        _build_native_device_spec("PVD1", DynamicDeviceTemplateType.RMS_PVD1,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_PVD1.value),
        _build_native_device_spec("PVD1 complete", DynamicDeviceTemplateType.RMS_PVD1_COMPLETE,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_PVD1_COMPLETE.value),
        _build_native_device_spec("PVD1 DC MPPT", DynamicDeviceTemplateType.RMS_PVD1_DC_MPPT,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_PVD1_DC_MPPT.value),
        _build_native_device_spec("PVD1 DC-link MPPT", DynamicDeviceTemplateType.RMS_PVD1_DC_LINK_MPPT,
                                  DynamicSimulationMode.RMS, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.RMS_PVD1_DC_LINK_MPPT.value),
        _build_native_device_spec("PVD1 DC-link BESS", DynamicDeviceTemplateType.RMS_PVD1_DC_LINK_BESS,
                                  DynamicSimulationMode.RMS, DeviceType.BatteryDevice,
                                  "Batteries", DynamicDeviceTemplateType.RMS_PVD1_DC_LINK_BESS.value),
        _build_native_device_spec("ESD1", DynamicDeviceTemplateType.RMS_ESD1,
                                  DynamicSimulationMode.RMS, DeviceType.BatteryDevice,
                                  "Batteries", DynamicDeviceTemplateType.RMS_ESD1.value),
        _build_native_device_spec("Line", BlockType.LINE_RMS,
                                  DynamicSimulationMode.RMS, DeviceType.LineDevice,
                                  "Lines", DynamicDeviceTemplateType.RMS_LINE.value),
        _build_native_device_spec("DC line", BlockType.DC_LINE_RMS,
                                  DynamicSimulationMode.RMS, DeviceType.DCLineDevice,
                                  "DC lines", DynamicDeviceTemplateType.RMS_DC_LINE.value),
        _build_native_device_spec("Transformer 2W", BlockType.TRANSFORMER_2W_RMS,
                                  DynamicSimulationMode.RMS, DeviceType.Transformer2WDevice,
                                  "Transformers", DynamicDeviceTemplateType.RMS_TRANSFORMER_2W.value),
        _build_native_device_spec("Load", BlockType.LOAD_RMS,
                                  DynamicSimulationMode.RMS, DeviceType.LoadDevice,
                                  "Loads and motors", DynamicDeviceTemplateType.RMS_LOAD.value),
        _build_native_device_spec("Shunt", DynamicDeviceTemplateType.RMS_SHUNT,
                                  DynamicSimulationMode.RMS, DeviceType.ShuntDevice,
                                  "Loads and shunts", DynamicDeviceTemplateType.RMS_SHUNT.value),
        _build_native_device_spec("GFL converter", BlockType.GFL_CONVERTER_RMS,
                                  DynamicSimulationMode.RMS, DeviceType.VscDevice,
                                  "Converters and VSC", DynamicDeviceTemplateType.RMS_GFL_CONVERTER.value),
        _build_native_device_spec("Complete GFL VSC HVDC", BlockType.GFL_VSC_HVDC_RMS,
                                  DynamicSimulationMode.RMS, DeviceType.VscDevice,
                                  "Converters and VSC", DynamicDeviceTemplateType.RMS_HVDC_VSC_GFL.value),
    ))


def build_emt_native_device_specs() -> List[LibraryDeviceTemplateSpec]:
    """Build every native EMT device entry in canonical Library order.

    :return: Complete native EMT device specifications.
    """
    specs: List[LibraryDeviceTemplateSpec] = list((
        _build_native_device_spec("Complete generator", DynamicDeviceTemplateType.EMT_COMPLETE_GENERATOR,
                                  DynamicSimulationMode.EMT, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.EMT_COMPLETE_GENERATOR.value),
        _build_native_device_spec("Thevenin generator", BlockType.EMT_THEVENIN,
                                  DynamicSimulationMode.EMT, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.EMT_THEVENIN_GENERATOR.value),
        _build_native_device_spec("Ideal converter", DynamicDeviceTemplateType.EMT_IDEAL_CONVERTER,
                                  DynamicSimulationMode.EMT, DeviceType.VscDevice,
                                  "Converters and VSC", DynamicDeviceTemplateType.EMT_IDEAL_CONVERTER.value),
        _build_native_device_spec("Full pseudo converter", BlockType.COMPLETE_PSEUDO_VSC_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.VscDevice,
                                  "Converters and VSC", DynamicDeviceTemplateType.EMT_FULL_PSEUDO_CONVERTER.value),
        _build_native_device_spec("Switched converter", DynamicDeviceTemplateType.EMT_SWITCHED_CONVERTER,
                                  DynamicSimulationMode.EMT, DeviceType.VscDevice,
                                  "Converters and VSC", DynamicDeviceTemplateType.EMT_SWITCHED_CONVERTER.value),
        _build_native_device_spec("VSC Grid-Forming (GFM)", DynamicDeviceTemplateType.EMT_GFM,
                                  DynamicSimulationMode.EMT, DeviceType.VscDevice,
                                  "Converters and VSC", DynamicDeviceTemplateType.EMT_GFM.value),
        _build_native_device_spec("BESS", BlockType.BESS_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.BatteryDevice,
                                  "Batteries", DynamicDeviceTemplateType.EMT_BESS.value),
        _build_native_device_spec("PV plant grid following", BlockType.PV_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.GeneratorDevice,
                                  "Generators and sources", DynamicDeviceTemplateType.EMT_PV_GRID_FOLLOWING.value),
        _build_native_device_spec("DC load", BlockType.DC_LOAD_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.LoadDevice,
                                  "Loads and motors", DynamicDeviceTemplateType.EMT_DC_LOAD.value),
        _build_native_device_spec("Exponential load (ABC)", BlockType.EXP_LOAD_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.LoadDevice,
                                  "Loads and motors", DynamicDeviceTemplateType.EMT_EXPONENTIAL_LOAD_ABC.value),
        _build_native_device_spec("ZIP load (ABC)", BlockType.ZIP_LOAD_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.LoadDevice,
                                  "Loads and motors", DynamicDeviceTemplateType.EMT_ZIP_LOAD_ABC.value),
        _build_native_device_spec("Single cage induction motor",
                                  DynamicDeviceTemplateType.EMT_SINGLE_CAGE_INDUCTION_MOTOR,
                                  DynamicSimulationMode.EMT, DeviceType.LoadDevice,
                                  "Loads and motors",
                                  DynamicDeviceTemplateType.EMT_SINGLE_CAGE_INDUCTION_MOTOR.value),
        _build_native_device_spec("Double cage induction motor",
                                  DynamicDeviceTemplateType.EMT_DOUBLE_CAGE_INDUCTION_MOTOR,
                                  DynamicSimulationMode.EMT, DeviceType.LoadDevice,
                                  "Loads and motors",
                                  DynamicDeviceTemplateType.EMT_DOUBLE_CAGE_INDUCTION_MOTOR.value),
        _build_native_device_spec("Shunt R (ABC)", BlockType.R_LOAD_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.LoadDevice,
                                  "Loads and shunts", DynamicDeviceTemplateType.EMT_SHUNT_R_ABC.value),
        _build_native_device_spec("Shunt L (ABC)", BlockType.L_LOAD_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.LoadDevice,
                                  "Loads and shunts", DynamicDeviceTemplateType.EMT_SHUNT_L_ABC.value),
        _build_native_device_spec("Shunt C (ABC)", BlockType.C_LOAD_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.LoadDevice,
                                  "Loads and shunts", DynamicDeviceTemplateType.EMT_SHUNT_C_ABC.value),
        _build_native_device_spec("PI line (ABC)", BlockType.EMT_PI_LINE,
                                  DynamicSimulationMode.EMT, DeviceType.LineDevice,
                                  "Lines", DynamicDeviceTemplateType.EMT_PI_LINE_ABC.value),
        _build_native_device_spec("Bergeron line (ABC)", BlockType.EMT_BERGERON_LINE,
                                  DynamicSimulationMode.EMT, DeviceType.LineDevice,
                                  "Lines", DynamicDeviceTemplateType.EMT_BERGERON_LINE_ABC.value),
        _build_native_device_spec("DC line", BlockType.EMT_DC_LINE,
                                  DynamicSimulationMode.EMT, DeviceType.DCLineDevice,
                                  "DC lines", DynamicDeviceTemplateType.EMT_DC_LINE.value),
        _build_native_device_spec("Transformer", BlockType.TRAFO_EMT,
                                  DynamicSimulationMode.EMT, DeviceType.Transformer2WDevice,
                                  "Transformers", DynamicDeviceTemplateType.EMT_TRANSFORMER.value,
                                  (DeviceType.Transformer2WDevice, DeviceType.Transformer3WDevice,
                                   DeviceType.TransformerTypeDevice)),
        _build_native_device_spec("XFMR", BlockType.XFMR_TRANSFORMER,
                                  DynamicSimulationMode.EMT, DeviceType.Transformer2WDevice,
                                  "Transformers", DynamicDeviceTemplateType.EMT_XFMR.value,
                                  (DeviceType.Transformer2WDevice, DeviceType.Transformer3WDevice,
                                   DeviceType.TransformerTypeDevice)),
    ))

    block_entries: tuple[tuple[str, BlockType, DeviceType, str], ...] = (
        ("Simple generator", BlockType.EMT_GENERATOR, DeviceType.GeneratorDevice, "Generators and sources"),
        ("Voltage source EMT", BlockType.VOLTAGE_SOURCE_EMT, DeviceType.GeneratorDevice, "Generators and sources"),
        ("Current source EMT", BlockType.CURRENT_SOURCE_EMT, DeviceType.GeneratorDevice, "Generators and sources"),
        ("Controlled voltage source EMT", BlockType.CONTROLLED_VOLTAGE_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Controlled current source EMT", BlockType.CONTROLLED_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Balanced 3-phase voltage source EMT", BlockType.BALANCED_3PH_VOLTAGE_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Balanced 3-phase current source EMT", BlockType.BALANCED_3PH_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Controlled balanced 3-phase voltage source EMT", BlockType.CONTROLLED_BALANCED_3PH_VOLTAGE_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Controlled balanced 3-phase current source EMT", BlockType.CONTROLLED_BALANCED_3PH_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Arbitrary waveform voltage source EMT", BlockType.ARBITRARY_WAVEFORM_VOLTAGE_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Arbitrary waveform current source EMT", BlockType.ARBITRARY_WAVEFORM_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Step voltage source EMT", BlockType.STEP_VOLTAGE_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Step current source EMT", BlockType.STEP_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Ramp voltage source EMT", BlockType.RAMP_VOLTAGE_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Ramp current source EMT", BlockType.RAMP_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Double exponential current source EMT", BlockType.DOUBLE_EXPONENTIAL_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Heidler current source EMT", BlockType.HEIDLER_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("CIGRE surge current source EMT", BlockType.CIGRE_SURGE_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("PV power plant", BlockType.PV_POWER_PLANT_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Battery", BlockType.BATTERY_EMT, DeviceType.BatteryDevice, "Batteries"),
        ("JMarti line", BlockType.EMT_JMARTI_LINE, DeviceType.LineDevice, "Lines"),
        ("Switch EMT", BlockType.SWITCH_EMT, DeviceType.SwitchDevice, "Switches"),
        ("Ground EMT", BlockType.GROUND_EMT, DeviceType.LoadDevice, "Loads and shunts"),
        ("Grounding link EMT", BlockType.GROUNDING_LINK_EMT, DeviceType.LoadDevice, "Loads and shunts"),
        ("Nonlinear resistor EMT", BlockType.NONLINEAR_RESISTOR_EMT, DeviceType.LoadDevice, "Loads and shunts"),
        ("RLC combo", BlockType.RLC_COMBO_EMT, DeviceType.LoadDevice, "Loads and shunts"),
        ("DC voltage source EMT", BlockType.DC_VOLTAGE_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("DC current source EMT", BlockType.DC_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Controlled DC voltage source EMT", BlockType.CONTROLLED_DC_VOLTAGE_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
        ("Controlled DC current source EMT", BlockType.CONTROLLED_DC_CURRENT_SOURCE_EMT,
         DeviceType.GeneratorDevice, "Generators and sources"),
    )
    entry: tuple[str, BlockType, DeviceType, str]
    for entry in block_entries:
        label: str = entry[0]
        block_type: BlockType = entry[1]
        device_type: DeviceType = entry[2]
        category_name: str = entry[3]
        specs.append(_build_native_device_spec(
            label=label,
            source=block_type,
            mode=DynamicSimulationMode.EMT,
            device_type=device_type,
            category_name=category_name,
            unique_key=f"emt:native:{block_type.name}",
        ))
    return specs


def _international_standard_label(model: InternationalStandardModel) -> str:
    """Return the established visible label for one standard model.

    :param model: International-standard model identifier.
    :return: Human-facing Library label.
    """
    if model == InternationalStandardModel.PSS1AOMEGA:
        label: str = "PSS1A (omega input)"
    elif model == InternationalStandardModel.PSS1APGEN:
        label = "PSS1A (Pgen input)"
    elif model == InternationalStandardModel.IEEEVC_1981:
        label = "IEEEVC 1981"
    elif model == InternationalStandardModel.PSSKUNDUR:
        label = "PSS Kundur"
    elif model == InternationalStandardModel.REGCBCS:
        label = "REGCbCS"
    elif model == InternationalStandardModel.WT4ACURRENTSOURCE:
        label = "WT4A current source"
    elif model == InternationalStandardModel.WT4ACURRENTSOURCE2020:
        label = "WT4A current source 2020"
    elif model == InternationalStandardModel.WT4BCURRENTSOURCE:
        label = "WT4B current source"
    elif model == InternationalStandardModel.WT4BCURRENTSOURCE2020:
        label = "WT4B current source 2020"
    elif model == InternationalStandardModel.WT4INJECTOR:
        label = "WT4 injector"
    elif model == InternationalStandardModel.WTG4ACURRENTSOURCE:
        label = "WTG4A current source"
    elif model == InternationalStandardModel.WTG4BCURRENTSOURCE:
        label = "WTG4B current source"
    elif model == InternationalStandardModel.WPP4BCURRENTSOURCE2020:
        label = "WPP4B current source 2020"
    elif model == InternationalStandardModel.PVCURRENTSOURCEBNOPLANTCONTROL:
        label = "PV current source B (no plant control)"
    elif model == InternationalStandardModel.PVVOLTAGESOURCEANOPLANTCONTROL:
        label = "PV voltage source A (no plant control)"
    elif model == InternationalStandardModel.PVVOLTAGESOURCEBNOPLANTCONTROL:
        label = "PV voltage source B (no plant control)"
    elif model == InternationalStandardModel.BESSCBCURRENTSOURCENOPLANTCONTROL:
        label = "BESSCB current source (no plant control)"
    else:
        label = model.name
    return label


def build_international_standard_description(model: InternationalStandardModel) -> str:
    """Return the functional description of an international-standard model.

    The descriptor registry is intentionally lightweight and does not build
    every symbolic template merely to read its comment. This function mirrors
    the model-level meaning needed by the Library while keeping tree creation
    fast and deterministic.

    :param model: International-standard model identifier.
    :return: Functional description shown in the Library and its tooltips.
    """
    label: str = _international_standard_label(model=model)
    if model == InternationalStandardModel.GENSAL:
        description: str = "GENSAL salient-pole synchronous-machine RMS model"
    elif model == InternationalStandardModel.GENROU:
        description = "GENROU round-rotor synchronous-machine RMS model"
    elif model == InternationalStandardModel.CIMTR1:
        description = "CIMTR1 induction-generator RMS model"
    elif model == InternationalStandardModel.CIMW:
        description = "CIMW induction-motor RMS model for a dynamic load"
    elif model == InternationalStandardModel.GGOV1:
        description = "GGOV1 general-purpose turbine-governor model for synchronous generation"
    elif model in tuple((InternationalStandardModel.GOVHYDRO4, InternationalStandardModel.HYGOV)):
        description = f"{label} hydro-turbine governor model for synchronous generation"
    elif model in tuple((InternationalStandardModel.GOVSTEAM1, InternationalStandardModel.GOVSTEAMEU)):
        description = f"{label} steam-turbine governor model for synchronous generation"
    elif model in tuple((InternationalStandardModel.IEEEG1, InternationalStandardModel.IEEEG2)):
        description = f"{label} IEEE turbine-governor model for synchronous generation"
    elif model in tuple((InternationalStandardModel.TGOV1, InternationalStandardModel.TGOV3)):
        description = f"{label} turbine-governor model for synchronous generation"
    elif model == InternationalStandardModel.IEEEVC_1981:
        description = "IEEEVC 1981 terminal-voltage compensation model for a synchronous generator"
    elif model == InternationalStandardModel.VRKUNDUR:
        description = "Kundur automatic voltage regulator model for a synchronous generator"
    elif model in tuple((
            InternationalStandardModel.AC1A,
            InternationalStandardModel.AC1C,
            InternationalStandardModel.AC6A,
            InternationalStandardModel.AC6C,
            InternationalStandardModel.AC7B,
            InternationalStandardModel.AC7C,
            InternationalStandardModel.AC8B,
            InternationalStandardModel.AC8C,
            InternationalStandardModel.BBSEX1,
            InternationalStandardModel.DC1A,
            InternationalStandardModel.DC1C,
            InternationalStandardModel.ESDC2A,
            InternationalStandardModel.EXAC1,
            InternationalStandardModel.IEEET1,
            InternationalStandardModel.IEEEX2,
            InternationalStandardModel.IEEX2A,
            InternationalStandardModel.SCRX,
            InternationalStandardModel.SEXS,
            InternationalStandardModel.ST1A,
            InternationalStandardModel.ST1C,
            InternationalStandardModel.ST4B,
            InternationalStandardModel.ST4C,
            InternationalStandardModel.ST5B,
            InternationalStandardModel.ST5C,
            InternationalStandardModel.ST6B,
            InternationalStandardModel.ST6C,
            InternationalStandardModel.ST7B,
            InternationalStandardModel.ST7C,
            InternationalStandardModel.ST9C,
    )):
        description = f"{label} automatic voltage regulator and excitation-system model for a synchronous generator"
    elif model == InternationalStandardModel.IEEL:
        description = "IEEL excitation limiter model for a synchronous generator"
    elif model == InternationalStandardModel.MAXEX2:
        description = "MAXEX2 maximum-excitation limiter model for a synchronous generator"
    elif model in tuple((InternationalStandardModel.OEL2C, InternationalStandardModel.OEL3C,
                         InternationalStandardModel.OEL4C, InternationalStandardModel.OEL5C)):
        description = f"{label} over-excitation limiter model protecting a synchronous generator field winding"
    elif model in tuple((InternationalStandardModel.SCL1C, InternationalStandardModel.SCL2C)):
        description = f"{label} stator-current limiter model for a synchronous generator"
    elif model in tuple((InternationalStandardModel.UEL1, InternationalStandardModel.UEL2C)):
        description = f"{label} under-excitation limiter model for a synchronous generator"
    elif model == InternationalStandardModel.PSS1AOMEGA:
        description = "PSS1A power-system stabilizer using rotor-speed deviation as its input"
    elif model == InternationalStandardModel.PSS1APGEN:
        description = "PSS1A power-system stabilizer using generator active power as its input"
    elif model in tuple((InternationalStandardModel.PSS2A, InternationalStandardModel.PSS2B,
                         InternationalStandardModel.PSS2C)):
        description = f"{label} dual-input power-system stabilizer for damping electromechanical oscillations"
    elif model in tuple((InternationalStandardModel.PSS3B, InternationalStandardModel.PSS3C,
                         InternationalStandardModel.PSS6C)):
        description = f"{label} power-system stabilizer for damping generator electromechanical oscillations"
    elif model == InternationalStandardModel.PSSKUNDUR:
        description = "Kundur power-system stabilizer for damping generator electromechanical oscillations"
    elif model == InternationalStandardModel.REECB:
        description = "WECC REECB renewable-energy electrical control model"
    elif model == InternationalStandardModel.REECC:
        description = "WECC REECC renewable-energy electrical control model"
    elif model == InternationalStandardModel.REGCBCS:
        description = "WECC REGCbCS current-source converter control model for renewable generation"
    elif model == InternationalStandardModel.REPCA:
        description = "WECC REPCA plant-level active- and reactive-power controller for renewable generation"
    elif model == InternationalStandardModel.WT4ACURRENTSOURCE:
        description = "WECC type-4A wind-turbine generator RMS current-source model"
    elif model == InternationalStandardModel.WT4ACURRENTSOURCE2020:
        description = "2020 WECC type-4A wind-turbine generator RMS current-source model"
    elif model == InternationalStandardModel.WT4BCURRENTSOURCE:
        description = "WECC type-4B wind-turbine generator RMS current-source model"
    elif model == InternationalStandardModel.WT4BCURRENTSOURCE2020:
        description = "2020 WECC type-4B wind-turbine generator RMS current-source model"
    elif model == InternationalStandardModel.WT4INJECTOR:
        description = "WECC type-4 wind-turbine RMS current-injection model"
    elif model == InternationalStandardModel.WTG4ACURRENTSOURCE:
        description = "WECC WTG4A type-4 wind-turbine generator RMS current-source model"
    elif model == InternationalStandardModel.WTG4BCURRENTSOURCE:
        description = "WECC WTG4B type-4 wind-turbine generator RMS current-source model"
    elif model == InternationalStandardModel.WPP4BCURRENTSOURCE2020:
        description = "2020 WECC type-4B wind-power-plant RMS current-source model"
    elif model == InternationalStandardModel.PVCURRENTSOURCEBNOPLANTCONTROL:
        description = "Photovoltaic generator RMS current-source B model without plant-level control"
    elif model == InternationalStandardModel.PVVOLTAGESOURCEANOPLANTCONTROL:
        description = "Photovoltaic generator RMS voltage-source A model without plant-level control"
    elif model == InternationalStandardModel.PVVOLTAGESOURCEBNOPLANTCONTROL:
        description = "Photovoltaic generator RMS voltage-source B model without plant-level control"
    elif model == InternationalStandardModel.BESSCBCURRENTSOURCENOPLANTCONTROL:
        description = "WECC BESSCB battery energy-storage RMS current-source model without plant-level control"
    elif model == InternationalStandardModel.FRQTPA:
        description = "FRQTPA frequency trip relay model for generator protection"
    elif model == InternationalStandardModel.VTGTPA:
        description = "VTGTPA voltage trip relay model for generator protection"
    else:
        description = f"{label} international-standard RMS dynamic model"

    return description


def _append_international_standard_group(
        descriptors: List[InternationalStandardTemplateDescriptor],
        models: tuple[InternationalStandardModel, ...],
        category_name: str,
        module_folder: str,
        device_type: DeviceType | None,
) -> None:
    """Append one ordered international-standard family to the local registry.

    :param descriptors: Destination descriptor list.
    :param models: Ordered model identifiers in the family.
    :param category_name: Canonical standard family name.
    :param module_folder: Engine implementation subpackage.
    :param device_type: Complete device type, or ``None`` for controls.
    :return: None.
    """
    model: InternationalStandardModel
    for model in models:
        descriptors.append(InternationalStandardTemplateDescriptor(
            model=model,
            display_label=_international_standard_label(model=model),
            category_path=(category_name,),
            module_folder=module_folder,
            device_type=device_type,
        ))


def get_dynamic_library_international_standard_descriptors() -> Sequence[InternationalStandardTemplateDescriptor]:
    """Return the international-standard inventory owned by the GUI Library.

    :return: Immutable descriptors in canonical family order.
    """
    descriptors: List[InternationalStandardTemplateDescriptor] = list()
    _append_international_standard_group(
        descriptors, (InternationalStandardModel.GENSAL, InternationalStandardModel.GENROU),
        "Synchronous machines", "synchronous_machines", DeviceType.GeneratorDevice)

    # Induction models have different physical hosts and are registered
    # explicitly so the editor projection can filter them correctly.
    descriptors.append(InternationalStandardTemplateDescriptor(
        InternationalStandardModel.CIMTR1, "CIMTR1", ("Induction machines",),
        "induction_machines", DeviceType.GeneratorDevice))
    descriptors.append(InternationalStandardTemplateDescriptor(
        InternationalStandardModel.CIMW, "CIMW", ("Induction machines",),
        "induction_machines", DeviceType.LoadDevice))

    _append_international_standard_group(
        descriptors,
        (InternationalStandardModel.GGOV1, InternationalStandardModel.GOVHYDRO4,
         InternationalStandardModel.GOVSTEAM1, InternationalStandardModel.GOVSTEAMEU,
         InternationalStandardModel.HYGOV, InternationalStandardModel.IEEEG1,
         InternationalStandardModel.IEEEG2, InternationalStandardModel.TGOV1,
         InternationalStandardModel.TGOV3),
        "Governors", "governors", None)
    _append_international_standard_group(
        descriptors,
        (InternationalStandardModel.AC1A, InternationalStandardModel.AC1C,
         InternationalStandardModel.AC6A, InternationalStandardModel.AC6C,
         InternationalStandardModel.AC7B, InternationalStandardModel.AC7C,
         InternationalStandardModel.AC8B, InternationalStandardModel.AC8C,
         InternationalStandardModel.BBSEX1, InternationalStandardModel.DC1A,
         InternationalStandardModel.DC1C, InternationalStandardModel.ESDC2A,
         InternationalStandardModel.EXAC1, InternationalStandardModel.IEEET1,
         InternationalStandardModel.IEEEX2, InternationalStandardModel.IEEX2A,
         InternationalStandardModel.SCRX, InternationalStandardModel.SEXS,
         InternationalStandardModel.ST1A, InternationalStandardModel.ST1C,
         InternationalStandardModel.ST4B, InternationalStandardModel.ST4C,
         InternationalStandardModel.ST5B, InternationalStandardModel.ST5C,
         InternationalStandardModel.ST6B, InternationalStandardModel.ST6C,
         InternationalStandardModel.ST7B, InternationalStandardModel.ST7C,
         InternationalStandardModel.ST9C, InternationalStandardModel.VRKUNDUR,
         InternationalStandardModel.IEEEVC_1981),
        "Excitation systems", "excitation_systems", None)
    _append_international_standard_group(
        descriptors,
        (InternationalStandardModel.IEEL, InternationalStandardModel.MAXEX2,
         InternationalStandardModel.OEL2C, InternationalStandardModel.OEL3C,
         InternationalStandardModel.OEL4C, InternationalStandardModel.OEL5C,
         InternationalStandardModel.SCL1C, InternationalStandardModel.SCL2C,
         InternationalStandardModel.UEL1, InternationalStandardModel.UEL2C),
        "Excitation limiters", "excitation_limiters", None)
    _append_international_standard_group(
        descriptors,
        (InternationalStandardModel.PSS1AOMEGA, InternationalStandardModel.PSS1APGEN,
         InternationalStandardModel.PSS2A, InternationalStandardModel.PSS2B,
         InternationalStandardModel.PSS2C, InternationalStandardModel.PSS3B,
         InternationalStandardModel.PSS3C, InternationalStandardModel.PSS6C,
         InternationalStandardModel.PSSKUNDUR),
        "Power system stabilizers", "power_system_stabilizers", None)
    _append_international_standard_group(
        descriptors,
        (InternationalStandardModel.REECB, InternationalStandardModel.REECC,
         InternationalStandardModel.REGCBCS, InternationalStandardModel.REPCA),
        "Renewable controls", "renewable_controls", None)
    _append_international_standard_group(
        descriptors,
        (InternationalStandardModel.WT4ACURRENTSOURCE, InternationalStandardModel.WT4ACURRENTSOURCE2020,
         InternationalStandardModel.WT4BCURRENTSOURCE, InternationalStandardModel.WT4BCURRENTSOURCE2020,
         InternationalStandardModel.WT4INJECTOR, InternationalStandardModel.WTG4ACURRENTSOURCE,
         InternationalStandardModel.WTG4BCURRENTSOURCE, InternationalStandardModel.WPP4BCURRENTSOURCE2020),
        "Wind generation", "wind_generation", DeviceType.GeneratorDevice)
    _append_international_standard_group(
        descriptors,
        (InternationalStandardModel.PVCURRENTSOURCEBNOPLANTCONTROL,
         InternationalStandardModel.PVVOLTAGESOURCEANOPLANTCONTROL,
         InternationalStandardModel.PVVOLTAGESOURCEBNOPLANTCONTROL),
        "Solar PV generation", "solar_pv_generation", DeviceType.GeneratorDevice)
    _append_international_standard_group(
        descriptors, (InternationalStandardModel.BESSCBCURRENTSOURCENOPLANTCONTROL,),
        "Battery energy storage", "battery_energy_storage", DeviceType.BatteryDevice)
    _append_international_standard_group(
        descriptors, (InternationalStandardModel.FRQTPA, InternationalStandardModel.VTGTPA),
        "Protection relays", "protection_relays", None)
    return tuple(descriptors)


def get_dynamic_library_procedural_descriptors() -> Sequence[ProceduralBlockTemplateDescriptor]:
    """Return the procedural inventory and ordering owned by the GUI Library.

    :return: Immutable procedural descriptors in canonical category order.
    """
    return tuple((
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.FixedSample, "Fixed sample",
                                          ("Sampling and history",), ("condition",), ("y",), tuple()),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.SampledValue, "Sampled value",
                                          ("Sampling and history",), ("u",), ("y",), tuple()),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.TimeDelay, "Time delay",
                                          ("Sampling and history",), ("u",), ("y",),
                                          (ProceduralBlockParameterSpec("delay", 0.0),)),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.MovingAverage, "Moving average",
                                          ("Sampling and history",), ("u",), ("y",),
                                          (ProceduralBlockParameterSpec("delay", 0.0),
                                           ProceduralBlockParameterSpec("window", 0.01))),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.HardSaturation, "Hard saturation",
                                          ("Limits and latches",), ("u",), ("y",),
                                          (ProceduralBlockParameterSpec("minimum", -1.0),
                                           ProceduralBlockParameterSpec("maximum", 1.0))),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.GradientLimiter, "Gradient limiter",
                                          ("Limits and latches",), ("u",), ("y",),
                                          (ProceduralBlockParameterSpec("lower_rate", -1.0),
                                           ProceduralBlockParameterSpec("upper_rate", 1.0))),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.FlipFlop, "Flip-flop",
                                          ("Limits and latches",), ("set", "reset"), ("y",), tuple()),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.AnalogFlipFlop, "Analog flip-flop",
                                          ("Limits and latches",), ("u", "set", "reset"), ("y",), tuple()),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.PickupDropoff, "Pickup/dropoff",
                                          ("Limits and latches",), ("condition",), ("y",),
                                          (ProceduralBlockParameterSpec("pickup_delay", 0.0),
                                           ProceduralBlockParameterSpec("dropoff_delay", 0.0))),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.DelayedThresholdLatch,
                                          "Delayed threshold latch", ("Limits and latches",),
                                          ("monitored",), ("y",), tuple()),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.ConditionalDiagnostic,
                                          "Conditional diagnostic", ("Events and diagnostics",),
                                          ("condition",), tuple(), tuple()),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.DelayedSwitchEvent,
                                          "Delayed switch event", ("Events and diagnostics",),
                                          ("guard", "trigger"), ("closed",),
                                          (ProceduralBlockParameterSpec("delay", 0.0),), True),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.ResetOnRisingEdge,
                                          "Reset on rising edge", ("Events and diagnostics",),
                                          ("condition", "value"), ("y",), tuple()),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.StartupHandover,
                                          "Startup handover", ("Events and diagnostics",),
                                          tuple(), ("enabled",),
                                          (ProceduralBlockParameterSpec("enable_time", 0.0),)),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.ValveState, "Valve state",
                                          ("Switching and modulation",),
                                          ("valve_voltage", "valve_current"), ("state",),
                                          (ProceduralBlockParameterSpec("valve_type", 0.0),
                                           ProceduralBlockParameterSpec("gate", 0.0),
                                           ProceduralBlockParameterSpec("antiparallel", 1.0),
                                           ProceduralBlockParameterSpec("voltage_epsilon", 1.0e-9),
                                           ProceduralBlockParameterSpec("current_epsilon", 1.0e-9))),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.ThreePhaseCarrierPwm,
                                          "Three-phase carrier PWM", ("Switching and modulation",),
                                          ("modulation_a", "modulation_b", "modulation_c"),
                                          ("gate_a", "gate_b", "gate_c"),
                                          (ProceduralBlockParameterSpec("switching_frequency", 2.0 * math.pi * 1000.0),
                                           ProceduralBlockParameterSpec("carrier_phase", 0.0))),
        ProceduralBlockTemplateDescriptor(ProceduralLogicType.ThreePhaseCarrierSampledModulation,
                                          "Three-phase sampled modulation", ("Switching and modulation",),
                                          ("modulation_a", "modulation_b", "modulation_c"),
                                          ("sample_a", "sample_b", "sample_c"),
                                          (ProceduralBlockParameterSpec("switching_frequency", 2.0 * math.pi * 1000.0),
                                           ProceduralBlockParameterSpec("carrier_phase", 0.0))),
    ))


def build_rms_control_library_branch() -> Dict[str, object]:
    """Build the categorized RMS control branch, including standards.

    :return: Nested RMS control branch.
    """
    branch: Dict[str, object] = dict()
    native_controls: tuple[tuple[tuple[str, ...], LibraryLeafSpec], ...] = (
        (("PLL", "Native"), LibraryLeafSpec("PLL transformer", BlockType.PLL_TRANSFORM_RMS)),
        (("PLL", "Native"), LibraryLeafSpec("PLL explicit PI", BlockType.VSC_PLL_RMS)),
        (("Governors", "Native"), LibraryLeafSpec("Governor", BlockType.GOV_RMS)),
        (("Exciters", "Native"), LibraryLeafSpec("Exciter", BlockType.EXCITER_RMS)),
        (("Stabilizers", "Native"), LibraryLeafSpec("Stabilizer", BlockType.STAB_RMS)),
        (("Active power and Vdc", "Native"), LibraryLeafSpec("PI power controller", BlockType.PI_POWER_CONTROLLER)),
        (("Active power and Vdc", "Native"), LibraryLeafSpec("Vdc / P control", BlockType.VSC_ACTIVE_CONTROL_RMS)),
        (("Reactive power and voltage", "Native"), LibraryLeafSpec("Qac / Vac control", BlockType.VSC_REACTIVE_CONTROL_RMS)),
        (("Current control", "Native"), LibraryLeafSpec("PI current controller", BlockType.PI_CURRENT_CONTROLLER)),
        (("Current control", "Native"), LibraryLeafSpec("d-axis current PI controller", BlockType.VSC_VD_HAT_RMS,
                                                         "d-axis current PI controller vd hat vd_hat y_vd_hat")),
        (("Current control", "Native"), LibraryLeafSpec("q-axis current PI controller", BlockType.VSC_VQ_HAT_RMS,
                                                         "q-axis current PI controller vq hat vq_hat y_vq_hat")),
        (("Current control", "Native"), LibraryLeafSpec("Converter electrical equations", BlockType.VSC_ELECTRICAL_RMS)),
        (("Current control", "Native"), LibraryLeafSpec("DC-link capacitor", BlockType.VSC_DC_LINK_RMS)),
        (("Limiters", "Native"), LibraryLeafSpec("Current limiter", BlockType.VSC_CURRENT_LIMITER_RMS)),
    )
    native_entry: tuple[tuple[str, ...], LibraryLeafSpec]
    for native_entry in native_controls:
        insert_library_leaf(branch, native_entry[0], native_entry[1])

    standard_category_map: tuple[tuple[str, str], ...] = (
        ("Governors", "Governors"),
        ("Excitation systems", "Exciters"),
        ("Excitation limiters", "Limiters"),
        ("Power system stabilizers", "Stabilizers"),
        ("Renewable controls", "Renewable controls"),
        ("Protection relays", "Protection"),
    )
    descriptor: InternationalStandardTemplateDescriptor
    for descriptor in get_dynamic_library_international_standard_descriptors():
        if descriptor.device_type is None:
            destination_name: str | None = None
            mapping_entry: tuple[str, str]
            for mapping_entry in standard_category_map:
                if descriptor.category_path[0] == mapping_entry[0]:
                    destination_name = mapping_entry[1]
                else:
                    pass
            if destination_name is not None:
                insert_library_leaf(
                    branch, (destination_name, "International standards"),
                    LibraryLeafSpec(descriptor.display_label, descriptor, descriptor.search_text))
            else:
                pass
        else:
            pass
    return branch


def build_emt_control_library_branch() -> Dict[str, object]:
    """Build the categorized EMT control branch.

    :return: Nested EMT control branch.
    """
    return dict((
        ("Governors", dict((("Native", list((LibraryLeafSpec("Governor", BlockType.GOV_EMT),))),))),
        ("Exciters", dict((("Native", list((LibraryLeafSpec("Exciter", BlockType.EXCITER_EMT),))),))),
        ("Stabilizers", dict((("Native", list((LibraryLeafSpec("Stabilizer", BlockType.STAB_EMT),))),))),
    ))


def build_device_library_branch(
        mode: DynamicSimulationMode,
        device_type: DeviceType | None,
) -> Dict[str, object]:
    """Build the complete or device-filtered canonical ``Devices`` branch.

    :param mode: Dynamic simulation domain.
    :param device_type: Physical device filter, or ``None`` for all devices.
    :return: Nested device branch used by both editor and catalogue.
    """
    branch: Dict[str, object] = dict()
    if mode == DynamicSimulationMode.RMS:
        native_specs: List[LibraryDeviceTemplateSpec] = build_rms_native_device_specs()
    elif mode == DynamicSimulationMode.EMT:
        native_specs = build_emt_native_device_specs()
    else:
        native_specs = list()

    spec: LibraryDeviceTemplateSpec
    for spec in native_specs:
        if device_type is None or spec.is_compatible_with(device_type=device_type):
            insert_library_leaf(
                branch, spec.category_path,
                LibraryLeafSpec(spec.label, spec, spec.search_text))
        else:
            pass

    if mode == DynamicSimulationMode.RMS:
        descriptor: InternationalStandardTemplateDescriptor
        for descriptor in get_dynamic_library_international_standard_descriptors():
            if descriptor.device_type is not None:
                if device_type is None or descriptor.device_type == device_type:
                    standard_spec: LibraryDeviceTemplateSpec = LibraryDeviceTemplateSpec(
                        label=descriptor.display_label,
                        source=descriptor,
                        mode=DynamicSimulationMode.RMS,
                        device_type=descriptor.device_type,
                        category_path=("International standards", str(descriptor.category_path[0])),
                        unique_key=f"rms:international:{descriptor.template_key}",
                        description=build_international_standard_description(model=descriptor.model),
                        search_text=descriptor.search_text,
                    )
                    insert_library_leaf(
                        branch, standard_spec.category_path,
                        LibraryLeafSpec(standard_spec.label, standard_spec, standard_spec.search_text))
                else:
                    pass
            else:
                pass
    else:
        pass
    return branch


def build_dynamic_library_structure(
        mode: DynamicSimulationMode,
        device_type: DeviceType,
) -> Dict[str, object]:
    """Build one editor projection from the canonical Library registrations.

    :param mode: Dynamic simulation domain.
    :param device_type: Physical device whose internal model is edited.
    :return: Ordered top-level Library tree structure.
    """
    structure: Dict[str, object] = dict()
    structure["Basic"] = build_basic_library_branch()
    if mode == DynamicSimulationMode.EMT:
        # Fault insertion is a mode-wide composition tool rather than a full
        # network-device drawing. Keep it near the top of the visible Library
        # so the large device and control trees cannot obscure its presence.
        structure["Faults"] = list((LibraryLeafSpec(
            label="Fault EMT",
            payload=BlockType.FAULT_EMT,
            search_text="EMT fault short circuit LG LL LLG LLL LLLG ground",
        ),))
    else:
        pass
    structure["Devices"] = build_device_library_branch(mode=mode, device_type=device_type)
    if mode == DynamicSimulationMode.RMS:
        structure["Controls"] = build_rms_control_library_branch()
    elif mode == DynamicSimulationMode.EMT:
        structure["Controls"] = build_emt_control_library_branch()
    else:
        pass
    structure["Procedural logic"] = build_procedural_library_branch()
    return structure


def _collect_device_specs_from_branch(
        branch_data: object,
        specs: List[LibraryDeviceTemplateSpec],
) -> None:
    """Collect canonical device specifications from one recursive branch.

    :param branch_data: Nested branch or leaf list.
    :param specs: Destination device specification list.
    :return: None.
    """
    if isinstance(branch_data, dict):
        child_data: object
        for child_data in branch_data.values():
            _collect_device_specs_from_branch(child_data, specs)
    elif isinstance(branch_data, list):
        leaf: LibraryLeafSpec
        for leaf in sorted(branch_data, key=_library_leaf_label_sort_key):
            if isinstance(leaf.payload, LibraryDeviceTemplateSpec):
                specs.append(leaf.payload)
            else:
                pass
    else:
        raise TypeError(f"Unsupported device branch data type {type(branch_data)!r}")


def get_dynamic_library_device_specs(mode: DynamicSimulationMode) -> List[LibraryDeviceTemplateSpec]:
    """Return every descendant of the canonical mode ``Devices`` branch.

    :param mode: Dynamic simulation domain.
    :return: Device-template specifications in Library branch order.
    """
    device_branch: Dict[str, object] = build_device_library_branch(mode=mode, device_type=None)
    specs: List[LibraryDeviceTemplateSpec] = list()
    _collect_device_specs_from_branch(device_branch, specs)
    return specs


def build_dynamic_library_device_template(
        spec: LibraryDeviceTemplateSpec,
        var_factory: VarFactory,
) -> RmsModelTemplate | EmtModelTemplate | None:
    """Materialize one complete device template from its Library registration.

    :param spec: Canonical device-template specification.
    :param var_factory: Factory allocating the symbolic variables.
    :return: Fresh RMS or EMT template, or ``None`` when unsupported.
    """
    source: DynamicDeviceTemplateType | BlockType | InternationalStandardTemplateDescriptor = spec.source
    if isinstance(source, InternationalStandardTemplateDescriptor):
        template: RmsModelTemplate | EmtModelTemplate | None = load_international_standard_template(
            descriptor=source,
            var_factory=var_factory,
        )
    elif isinstance(source, BlockType):
        builder: TemplateDefinition | None = create_default_template_builder(
            var_factory=var_factory,
            block_type=source,
            item_name=spec.label,
            api_object=None,
        )
        built_object: object | None
        if builder is not None:
            built_object = builder.eval()
        else:
            built_object = create_block_of_type(
                var_factory=var_factory,
                block_type=source,
                item_name=spec.label,
                api_object=None,
            )
        if isinstance(built_object, (RmsModelTemplate, EmtModelTemplate)):
            template = built_object
        elif isinstance(built_object, Block):
            if spec.mode == DynamicSimulationMode.RMS:
                rms_template: RmsModelTemplate = RmsModelTemplate()
                rms_template.name = spec.label
                rms_template.tpe = spec.device_type
                rms_template.block = built_object
                template = rms_template
            elif spec.mode == DynamicSimulationMode.EMT:
                emt_template: EmtModelTemplate = EmtModelTemplate()
                emt_template.name = spec.label
                emt_template.tpe = spec.device_type
                emt_template.block = built_object
                template = emt_template
            else:
                template = None
        else:
            template = None
    elif source == DynamicDeviceTemplateType.RMS_COMPLETE_GENERATOR:
        template = tem.get_complete_generator_template_rms(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_GENCLS:
        template = tem.get_gencls_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_GENQEC:
        template = tem.get_genqec_rms(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_GENROW:
        template = tem.get_genrow_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_LINE:
        template = tem.get_line_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_DC_LINE:
        template = tem.build_dc_line_rms_v2(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_LOAD:
        template = tem.get_load_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_TRANSFORMER_2W:
        template = tem.get_transformer2w_rms(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_SHUNT:
        template = tem.get_shunt_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_PVD1:
        template = tem.get_pvd1_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_PVD1_COMPLETE:
        template = tem.get_pvd1_complete_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_PVD1_DC_MPPT:
        template = tem.get_pvd1_dc_mppt_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_PVD1_DC_LINK_MPPT:
        template = tem.get_pvd1_dc_link_mppt_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_PVD1_DC_LINK_BESS:
        template = tem.get_pvd1_dc_link_bess_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_ESD1:
        template = tem.get_esd1_rms_template(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_VOLTAGE_SOURCE:
        template = tem.VoltageSourceBuild(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_GFL_CONVERTER:
        template = tem.get_gfl_converter_rms(var_factory)
    elif source == DynamicDeviceTemplateType.RMS_HVDC_VSC_GFL:
        template = tem.build_hvdc_vsc_gfl_rms(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_COMPLETE_GENERATOR:
        template = tem.get_complete_generator_template_emt(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_THEVENIN_GENERATOR:
        template = tem.get_generator_thevenin_rl_emt_template_with_ref(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_IDEAL_CONVERTER:
        template = tem.get_emt_ideal_converter(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_FULL_PSEUDO_CONVERTER:
        template = tem.get_full_pseudo_emt_converter(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_SWITCHED_CONVERTER:
        template = tem.get_switched_emt_converter(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_DC_LOAD:
        template = tem.get_dc_load_emt_template(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_DC_LINE:
        template = tem.get_dc_line_with_power_input_emt_template(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_TRANSFORMER:
        template = tem.get_transformer_emt_template(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_XFMR:
        template = tem.get_xfmr_emt_template(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_SHUNT_C_ABC:
        template = tem.get_shunt_c_emt_template(var_factory, True, True, True)
    elif source == DynamicDeviceTemplateType.EMT_SHUNT_L_ABC:
        template = tem.get_shunt_l_emt_template(var_factory, True, True, True)
    elif source == DynamicDeviceTemplateType.EMT_SHUNT_R_ABC:
        template = tem.get_shunt_r_emt_template(var_factory, True, True, True)
    elif source == DynamicDeviceTemplateType.EMT_EXPONENTIAL_LOAD_ABC:
        template = tem.get_exponential_load_emt(var_factory, True, True, True)
    elif source == DynamicDeviceTemplateType.EMT_ZIP_LOAD_ABC:
        template = tem.get_load_ZIP_emt_template(var_factory, True, True, True)
    elif source == DynamicDeviceTemplateType.EMT_PI_LINE_ABC:
        template = tem.get_pi_line_emt_template(var_factory, False, True, True, True)
    elif source == DynamicDeviceTemplateType.EMT_BERGERON_LINE_ABC:
        template = tem.get_bergeron_line_emt_template(var_factory, False, True, True, True)
    elif source == DynamicDeviceTemplateType.EMT_SINGLE_CAGE_INDUCTION_MOTOR:
        template = tem.get_induction_motor_single_cage_emt_template(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_DOUBLE_CAGE_INDUCTION_MOTOR:
        template = tem.get_induction_motor_double_cage_emt_template(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_BESS:
        template = tem.get_bess_avm_grid_following_emt_template(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_PV_GRID_FOLLOWING:
        template = tem.get_pv_avm_grid_following_emt_template(var_factory)
    elif source == DynamicDeviceTemplateType.EMT_GFM:
        template = tem.get_gfm_emt_template(var_factory)
    else:
        template = None

    if template is not None:
        # A device registration is authoritative for host compatibility even
        # when the underlying block builder is also usable as a control block.
        # The same registration also owns the user-facing catalogue label. A
        # builder's internal symbolic name must not leak into device selectors.
        template.name = spec.label
        template.tpe = spec.device_type
        template.code = spec.unique_key
    else:
        pass
    return template


def build_basic_branch_skeleton() -> Dict[str, object]:
    """Build the canonical empty hierarchy below ``Basic``.

    The hierarchy lives beside the ``Devices`` and ``Controls`` registrations
    so the complete dynamic-editor library can be inspected and maintained in
    one module. Empty leaf collections reserve the requested semantic location
    while the tree is populated; they are removed before it becomes visible.

    :return: Ordered category tree whose leaf nodes are empty lists.
    """
    # Mathematical operations are separated by behavior rather than by the
    # implementation family from which a block happened to originate.
    mathematical_functions: Dict[str, object] = dict((
        ("Sum", list()),
        ("Product", list()),
        ("Gain", list()),
        ("Affine", list()),
        ("Polynomials", list()),
        ("Minimum/Maximum", list()),
        ("Absolute value", list()),
        ("Sign", list()),
        ("Square root", list()),
        ("Power", list()),
        ("Exponential and logarithms", list()),
        ("Rounding and modulo", list()),
        ("Trigonometric functions", list()),
        ("Constants", list()),
    ))

    # State-bearing continuous blocks are kept apart from discrete memory so
    # their numerical meaning is evident from the library path.
    continuous_dynamics: Dict[str, object] = dict((
        ("Integrators", list()),
        ("Derivatives", list()),
        ("Transfer functions", list()),
        ("Filters", list()),
        ("Delay approximations", list()),
    ))
    memory_and_discrete_time: Dict[str, object] = dict((
        ("Sample and hold", list()),
        ("Previous value", list()),
        ("Exact time delay", list()),
        ("Moving average", list()),
    ))

    # Event-generating comparators are distinguished from ordinary algebraic
    # comparisons and from the switches that consume their results.
    logic_and_events: Dict[str, object] = dict((
        ("Logic gate", list()),
        ("Comparator", list()),
        ("Timed comparator", list()),
        ("Selector / Switch", list()),
        ("Edge detector", list()),
        ("Latches and flip-flops", list()),
        ("Timers", list()),
    ))
    limits_and_nonlinearities: Dict[str, object] = dict((
        ("Saturation", list()),
        ("Deadband", list()),
        ("Rate limiter", list()),
        ("Hysteresis", list()),
    ))

    # Sources are classified by the waveform users look for. Scalar constants
    # belong with the other mathematical constants, while clocks have their
    # own category instead of being presented incorrectly as steps.
    sources: Dict[str, object] = dict((
        ("Initial conditions", list()),
        ("Simulation time", list()),
        ("Periodic clocks", list()),
        ("Pulse", list()),
        ("Sine", list()),
        ("Square", list()),
        ("Triangle", list()),
        ("Sawtooth", list()),
    ))
    lookup_tables: Dict[str, object] = dict((
        ("1D lookup table", list()),
        ("Inverse 1D lookup table", list()),
        ("2D lookup table", list()),
    ))
    transforms: Dict[str, object] = dict((
        ("Clarke", list()),
        ("Park / dq0", list()),
        ("Sequence components", list()),
        ("RMS conversions", list()),
    ))
    complex_numbers: Dict[str, object] = dict((
        ("Cartesian / polar conversion", list()),
        ("Magnitude and angle", list()),
        ("Conjugate", list()),
        ("Arithmetic", list()),
    ))
    measurements: Dict[str, object] = dict((
        ("Electrical measurements", list()),
        ("Per-unit conversions", list()),
        ("Unit conversions", list()),
    ))
    mechanical: Dict[str, object] = dict((("Drive train", list()),))

    return dict((
        ("Mathematical functions", mathematical_functions),
        ("Continuous dynamics", continuous_dynamics),
        ("Memory and discrete-time", memory_and_discrete_time),
        ("Logic and events", logic_and_events),
        ("Limits and nonlinearities", limits_and_nonlinearities),
        ("Sources", sources),
        ("Lookup tables", lookup_tables),
        ("Transforms", transforms),
        ("Complex numbers", complex_numbers),
        ("Measurements and conversions", measurements),
        ("Mechanical", mechanical),
    ))


def get_basic_lookup_table_category_path(descriptor: BasicBlockTemplateDescriptor) -> tuple[str, ...]:
    """Return the dimensional lookup-table category for one descriptor.

    :param descriptor: Basic-block descriptor being classified.
    :return: Path below ``Basic`` for the lookup implementation.
    """
    template_key: str = descriptor.template_key
    inverse_keys: tuple[str, ...] = (
        "inverse_lookup_array_object_linear",
        "invlapprox",
    )
    matrix_keys: tuple[str, ...] = (
        "lookup_matrix_linear",
        "lookup_matrix_spline",
        "lookup_matrix_object_linear",
        "lookup_matrix_object_spline",
        "lapprox2",
        "sapprox2",
    )
    array_keys: tuple[str, ...] = (
        "lookup_array_linear_noclipping",
        "lookup_array_1x3_linear_fixed",
        "lookup_array_1x3_linear_variable",
        "lookup_array_1x4_linear_fixed",
        "lookup_array_1x4_linear_variable",
        "lookup_array_object_linear",
        "lookup_array_object_linear_noclipping",
        "lookup_array_object_spline",
        "lapprox",
        "lapproxext",
        "sapprox",
    )

    # Every shipped lookup implementation is named explicitly. This prevents a
    # future matrix or inverse implementation from silently landing in 1D.
    if template_key in inverse_keys:
        category_path: tuple[str, ...] = ("Lookup tables", "Inverse 1D lookup table")
    elif template_key in matrix_keys:
        category_path = ("Lookup tables", "2D lookup table")
    elif template_key in array_keys:
        category_path = ("Lookup tables", "1D lookup table")
    else:
        raise ValueError(f"Unclassified lookup-table template '{template_key}'")
    return category_path


def get_basic_mathematical_category_path(descriptor: BasicBlockTemplateDescriptor,
                                         source_category: str) -> tuple[str, ...]:
    """Classify a descriptor from the legacy mathematical families.

    :param descriptor: Basic-block descriptor being classified.
    :param source_category: Legacy second-level mathematical category.
    :return: Path below ``Basic`` for the mathematical behavior.
    """
    template_key: str = descriptor.template_key
    scaling_gain_keys: tuple[str, ...] = (
        "multiply_1_form_a", "multiply_k_form_a", "multiply_1_k_form_a",
        "multiply_1_k1_k2", "multiply_1_form_b",
        "multiply_1_k_form_b",
        "multiply_k_form_b", "multiply_k1_k2_k3_form_a",
        "multiply_k1_k2_k3_form_b", "multiply_k1_k2_form_a",
        "multiply_k1_k2_form_b", "multiply_sqrt2", "multiply_sqrt3",
    )
    saturated_gain_keys: tuple[str, ...] = (
        "multiply_1_k_p", "multiply_1_k1k2_p", "multiply_k_p",
    )
    trigonometric_keys: tuple[str, ...] = (
        "acos", "asin", "atan", "atan2", "atan2d", "atand",
        "cos", "cosd", "cosh", "coshd", "sin", "sind",
        "sinh", "sinhd", "tan", "tand", "tanh", "tanhd",
    )
    polynomial_keys: tuple[str, ...] = (
        "a_x_c1_x_c2", "ax_2_bx_c",
    )
    power_keys: tuple[str, ...] = (
        "reciprocal", "reciprocal_fb", "x_2", "x_p",
    )

    if source_category == "Constants and Scaling":
        category_path: tuple[str, ...] = ("Mathematical functions", "Constants")
    elif source_category == "Scaling and Products":
        if template_key == "bias":
            category_path = ("Sources", "Initial conditions")
        elif template_key == "mx_n":
            category_path = ("Mathematical functions", "Affine")
        elif template_key in polynomial_keys:
            category_path = ("Mathematical functions", "Polynomials")
        elif template_key in power_keys:
            category_path = ("Mathematical functions", "Power")
        elif template_key in saturated_gain_keys:
            category_path = ("Limits and nonlinearities", "Saturation")
        elif template_key in scaling_gain_keys:
            category_path = ("Mathematical functions", "Gain")
        else:
            raise ValueError(f"Unclassified scaling template '{template_key}'")
    elif template_key == "equal":
        category_path = ("Logic and events", "Comparator")
    elif template_key == "abs":
        category_path = ("Mathematical functions", "Absolute value")
    elif template_key == "sign":
        category_path = ("Mathematical functions", "Sign")
    elif template_key == "sqrt":
        category_path = ("Mathematical functions", "Square root")
    elif template_key in ("exp", "ln", "log"):
        category_path = ("Mathematical functions", "Exponential and logarithms")
    elif template_key in ("ceil", "floor", "frac", "modulo", "round"):
        category_path = ("Mathematical functions", "Rounding and modulo")
    elif template_key in trigonometric_keys:
        category_path = ("Mathematical functions", "Trigonometric functions")
    elif template_key in power_keys:
        category_path = ("Mathematical functions", "Power")
    else:
        raise ValueError(f"Unclassified elementary-function template '{template_key}'")
    return category_path


def get_basic_waveform_category_path(descriptor: BasicBlockTemplateDescriptor,
                                     source_category: str) -> tuple[str, ...]:
    """Classify waveform, clock, and event-pulse descriptors.

    :param descriptor: Basic-block descriptor being classified.
    :param source_category: Legacy waveform category.
    :return: Path below ``Basic`` for the source or event behavior.
    """
    template_key: str = descriptor.template_key
    timed_comparator_keys: tuple[str, ...] = (
        "abs_in_greater_than_c_ip", "abs_in_less_than_c_ip",
        "yi_equals_c_ip", "yi_greater_than_c_ip",
        "yi_greater_than_or_equal_c_ip", "yi_less_than_c_ip",
        "yi_less_than_or_equal_c_ip", "yi1_equals_yi2_ip",
        "yi1_greater_than_or_equal_yi2_ip", "yi1_greater_than_yi2_ip",
        "yi1_less_than_or_equal_yi2_ip", "yi1_less_than_yi2_ip",
    )
    pulse_logic_keys: tuple[str, ...] = (
        "2_out_of_3_ip", "and2_ip", "and3_ip", "invert_logic_ip",
        "not_ip", "or2_ip", "or3_ip",
    )
    clock_keys: tuple[str, ...] = (
        "clock_t_0_par", "clock_t_0_sig", "clock_t_t0_par",
        "clock_t_t0_sig", "clock_par", "clock_sig",
    )

    if template_key in ("sawtooth_wave_generator_ip", "sawtooth_wave_generator"):
        category_path: tuple[str, ...] = ("Sources", "Sawtooth")
    elif template_key in ("triangle_wave_generator", "triangle_wave_generator_ip"):
        category_path = ("Sources", "Triangle")
    elif template_key in ("square_wave_generator", "square_wave_generator_ip"):
        category_path = ("Sources", "Square")
    elif template_key in ("sine_wave_generator_t_t0", "sine_wave_generator"):
        category_path = ("Sources", "Sine")
    elif template_key == "pulse":
        category_path = ("Sources", "Pulse")
    elif template_key in ("time_form_a", "time_form_b"):
        category_path = ("Sources", "Simulation time")
    elif template_key in clock_keys:
        category_path = ("Sources", "Periodic clocks")
    elif template_key in ("timer_reset", "timer_reset_hold_reset_t0_reset_incfw"):
        category_path = ("Logic and events", "Timers")
    elif template_key in timed_comparator_keys:
        category_path = ("Logic and events", "Timed comparator")
    elif template_key in pulse_logic_keys:
        category_path = ("Logic and events", "Logic gate")
    else:
        raise ValueError(
            f"Unclassified waveform template '{template_key}' from '{source_category}'"
        )
    return category_path


def get_basic_continuous_category_path(descriptor: BasicBlockTemplateDescriptor,
                                       source_category: str) -> tuple[str, ...]:
    """Classify legacy continuous-time descriptors by numerical behavior.

    :param descriptor: Basic-block descriptor being classified.
    :param source_category: Legacy continuous-time category.
    :return: Path below ``Basic`` for the continuous behavior.
    """
    template_key: str = descriptor.template_key
    previous_value_keys: tuple[str, ...] = (
        "lastvalue_form_a", "lastvalue_incbackward",
        "lastvalue_incforward", "lastvalue_form_b",
    )
    delay_approximation_keys: tuple[str, ...] = (
        "ke_st_bypass_incforward", "ke_st_incforward",
        "pade_approximant_r12_incbackward", "pade_approximant_r12_incforward",
        "e_s0_01_incforward", "e_st_bypass", "e_st_bypass_incbackward",
        "e_st_bypass_incforward", "e_st_incbackward", "e_st_incforward",
    )
    derivative_keys: tuple[str, ...] = (
        "s_1_st", "s_w0_2_s_2", "st_1_st_bypass_form_a", "st_1_st",
        "st_1_st_bypass_form_b", "skt_1_st", "sktd_1_st",
        "stb_1_sta_fb", "stld_1_stlg_fb", "sk_1_0_01s",
        "sk_1_st_fb", "sk_1_st", "s_2k_1_st_2",
    )
    filter_keys: tuple[str, ...] = (
        "h0w0_q_s_w0_2_sw0_q_s_2", "butterworth_2nd_order",
        "butterworth_3rd_order", "butterworth_2nd_order_rst_hold",
        "butterworth_3rd_order_rst_hold",
    )
    integrator_keys_from_controllers: tuple[str, ...] = (
        "k_s_p", "k_s_s", "k_s",
    )
    mathematical_gain_keys: tuple[str, ...] = (
        "multiply_1_sqrt2", "multiply_1_sqrt3", "multiply_pi",
        "multiply_sqrt_2_3", "multiply_sqrt_3_2", "multiply_sqrt_k1_k2",
    )
    minimum_maximum_keys: tuple[str, ...] = (
        "max2", "max3", "max4", "min2", "min3", "min4",
    )

    if source_category == "Delays and Memory":
        if template_key == "movingavg":
            category_path: tuple[str, ...] = ("Memory and discrete-time", "Moving average")
        elif template_key in previous_value_keys:
            category_path = ("Memory and discrete-time", "Previous value")
        elif template_key in delay_approximation_keys:
            category_path = ("Continuous dynamics", "Delay approximations")
        elif template_key == "delay":
            category_path = ("Memory and discrete-time", "Exact time delay")
        else:
            raise ValueError(f"Unclassified delay or memory template '{template_key}'")
    elif source_category == "Integrators and Derivatives":
        if template_key in derivative_keys:
            category_path = ("Continuous dynamics", "Derivatives")
        else:
            # The remaining audited source records implement 1/s or 1/(sT)
            # variants with reset, hold, freeze, and limit options.
            category_path = ("Continuous dynamics", "Integrators")
    elif template_key in minimum_maximum_keys:
        category_path = ("Mathematical functions", "Minimum/Maximum")
    elif template_key in ("picdro", "picdro_const"):
        category_path = ("Logic and events", "Timed comparator")
    elif template_key in mathematical_gain_keys:
        category_path = ("Mathematical functions", "Gain")
    elif template_key in filter_keys:
        category_path = ("Continuous dynamics", "Filters")
    elif template_key in derivative_keys:
        category_path = ("Continuous dynamics", "Derivatives")
    elif template_key in integrator_keys_from_controllers or template_key == "1_2hs":
        category_path = ("Continuous dynamics", "Integrators")
    elif source_category in ("Transfer Functions and Filters", "Controllers"):
        # All non-exception records in these two audited legacy families are
        # rational transfer functions or complete continuous controllers.
        category_path = ("Continuous dynamics", "Transfer functions")
    else:
        raise ValueError(
            f"Unclassified continuous template '{template_key}' from '{source_category}'"
        )
    return category_path


def get_basic_logic_category_path(descriptor: BasicBlockTemplateDescriptor,
                                  source_category: str) -> tuple[str, ...]:
    """Classify legacy logical and event descriptors.

    :param descriptor: Basic-block descriptor being classified.
    :param source_category: Legacy logical category.
    :return: Path below ``Basic`` for the logical behavior.
    """
    template_key: str = descriptor.template_key
    latch_keys: tuple[str, ...] = ("aflipflop", "flipflop", "bistable")
    gate_keys: tuple[str, ...] = (
        "and2", "and3", "and4", "eor", "nor", "not", "or2", "or3", "or4",
    )
    gate_memory_switch_keys: tuple[str, ...] = (
        "switch_sig_2_1_not_eq_k_by_s_p", "switch_sw_not_equal_c_2s_1s",
    )
    enabled_integrator_keys: tuple[str, ...] = (
        "1_s_enable", "1_s_enable_reset", "1_s_enable_reset_sig",
    )
    enabled_derivative_keys: tuple[str, ...] = ("st_1_st_enable",)
    enabled_transfer_function_keys: tuple[str, ...] = ("1_1_st_enable",)
    signal_enable_keys: tuple[str, ...] = (
        "enable_1_sig_hold", "enable_1_sig",
        "enable_2_sig_hold", "enable_2_sig",
        "enable_3_sig_hold", "enable_3_sig",
        "enable_4_sig_hold", "enable_4_sig",
        "enable_5_sig_hold", "enable_5_sig",
        "enable_6_sig_hold", "enable_7_sig_hold", "enable_8_sig_hold",
        "enable_signal_fixed", "enable_signal",
    )
    if source_category == "Comparators":
        category_path: tuple[str, ...] = ("Logic and events", "Comparator")
    elif source_category == "Switching and Selection" or template_key in gate_memory_switch_keys:
        category_path = ("Logic and events", "Selector / Switch")
    elif template_key in enabled_integrator_keys:
        category_path = ("Continuous dynamics", "Integrators")
    elif template_key in enabled_derivative_keys:
        category_path = ("Continuous dynamics", "Derivatives")
    elif template_key in enabled_transfer_function_keys:
        category_path = ("Continuous dynamics", "Transfer functions")
    elif template_key in signal_enable_keys:
        category_path = ("Logic and events", "Selector / Switch")
    elif template_key == "edge_detector":
        category_path = ("Logic and events", "Edge detector")
    elif template_key == "monostable":
        category_path = ("Logic and events", "Timers")
    elif template_key in latch_keys:
        category_path = ("Logic and events", "Latches and flip-flops")
    elif template_key in gate_keys:
        category_path = ("Logic and events", "Logic gate")
    else:
        raise ValueError(
            f"Unclassified logic template '{template_key}' from '{source_category}'"
        )
    return category_path


def get_basic_measurement_category_path(descriptor: BasicBlockTemplateDescriptor) -> tuple[str, ...]:
    """Classify measurements separately from unit and per-unit conversions.

    :param descriptor: Basic-block descriptor being classified.
    :return: Path below ``Basic`` for the measurement or conversion behavior.
    """
    template_key: str = descriptor.template_key
    electrical_measurement_keys: tuple[str, ...] = (
        "el_power", "pq_calculator", "accelerating_power_simple", "accelerating_power_ipb",
    )
    per_unit_conversion_keys: tuple[str, ...] = (
        "power_base", "hz_p_u", "nm_p_u", "abs_p_u_par", "abs_p_u_sig",
        "p_u_hz", "p_u_abs_par", "p_u_abs_sig", "p_u_rpm", "rpm_p_u",
    )
    unit_conversion_keys: tuple[str, ...] = (
        "deg_rad", "rad_deg", "rad_s_rpm", "rpm_rad_s",
    )

    if template_key in electrical_measurement_keys:
        category_path: tuple[str, ...] = ("Measurements and conversions", "Electrical measurements")
    elif template_key in per_unit_conversion_keys:
        category_path = ("Measurements and conversions", "Per-unit conversions")
    elif template_key in unit_conversion_keys:
        category_path = ("Measurements and conversions", "Unit conversions")
    else:
        raise ValueError(f"Unclassified measurement or conversion template '{template_key}'")
    return category_path


def get_basic_limit_category_path(descriptor: BasicBlockTemplateDescriptor,
                                  source_category: str) -> tuple[str, ...]:
    """Classify limiter and nonlinearity descriptors.

    :param descriptor: Basic-block descriptor being classified.
    :param source_category: Legacy limit category.
    :return: Path below ``Basic`` for the nonlinear behavior.
    """
    template_key: str = descriptor.template_key
    deadband_keys: tuple[str, ...] = (
        "deadband_p", "deadband_bypass", "deadband_discontinuous",
        "deadband_offset_p", "deadband_offset_bypass", "deadband_stepped_p",
        "deadband_stepped_bypass", "deadband",
    )
    rate_limiter_keys: tuple[str, ...] = (
        "gradlim_const", "rate_limiter", "rate_limiter_base",
        "rate_limiter_base_p_form_a", "rate_limiter_base_p_form_b",
        "rate_limiter_base_p_form_c", "rate_limiter_p_form_a",
        "rate_limiter_p_form_b", "rate_limiter_p_form_c", "rate_limiter_s",
    )
    if template_key in deadband_keys:
        category_path: tuple[str, ...] = ("Limits and nonlinearities", "Deadband")
    elif template_key == "backlash":
        category_path = ("Limits and nonlinearities", "Hysteresis")
    elif template_key in rate_limiter_keys:
        category_path = ("Limits and nonlinearities", "Rate limiter")
    elif source_category == "Limiters":
        category_path = ("Limits and nonlinearities", "Saturation")
    else:
        raise ValueError(
            f"Unclassified limit template '{template_key}' from '{source_category}'"
        )
    return category_path


def get_basic_transform_category_path(descriptor: BasicBlockTemplateDescriptor) -> tuple[str, ...]:
    """Classify coordinate, sequence, and RMS transform descriptors.

    :param descriptor: Basic-block descriptor being classified.
    :return: Path below ``Basic`` for the transform behavior.
    """
    template_key: str = descriptor.template_key
    clarke_keys: tuple[str, ...] = (
        "clarke_transform_power_invariant", "clarke_transform",
        "inverse_clarke_transform_pow_invariant", "inverse_clarke_transform",
    )
    park_keys: tuple[str, ...] = (
        "inverse_park_transform_dq", "inverse_park_transform_dq0",
        "park_transform_dq", "park_transform_dq0",
        "abc_dq0_power_invariant_align_a_d", "abc_dq0_power_invariant_align_a_q",
        "abc_dq0_power_variant_align_a_d", "abc_dq0_power_variant_align_a_q",
        "dq0_abc_power_invariant_align_a_d", "dq0_abc_power_invariant_align_a_q",
        "dq0_abc_power_variant_align_a_d", "dq0_abc_power_variant_align_a_q",
    )
    rms_keys: tuple[str, ...] = ("rms", "rms_value_p_u", "rms_value")
    sequence_keys: tuple[str, ...] = ("balanced", "u_seq_ab0_u_abc")
    if template_key in clarke_keys:
        category_path: tuple[str, ...] = ("Transforms", "Clarke")
    elif template_key in park_keys:
        category_path = ("Transforms", "Park / dq0")
    elif template_key in rms_keys:
        category_path = ("Transforms", "RMS conversions")
    elif template_key in sequence_keys:
        category_path = ("Transforms", "Sequence components")
    else:
        raise ValueError(f"Unclassified transform template '{template_key}'")
    return category_path


def get_basic_complex_category_path(descriptor: BasicBlockTemplateDescriptor) -> tuple[str, ...]:
    """Classify complex-number descriptors by their visible operation.

    :param descriptor: Basic-block descriptor being classified.
    :return: Path below ``Basic`` for the complex operation.
    """
    template_key: str = descriptor.template_key
    if template_key in ("to_polar_complex", "to_rectangular_complex"):
        category_path: tuple[str, ...] = ("Complex numbers", "Cartesian / polar conversion")
    elif template_key == "mag_complex":
        category_path = ("Complex numbers", "Magnitude and angle")
    elif template_key == "conj_complex":
        category_path = ("Complex numbers", "Conjugate")
    elif template_key in ("add_complex", "div_complex", "mul_complex", "sub_complex"):
        category_path = ("Complex numbers", "Arithmetic")
    elif template_key in ("limit_p_complex", "limit_ppp_complex_with_prio"):
        category_path = ("Limits and nonlinearities", "Saturation")
    else:
        raise ValueError(f"Unclassified complex template '{template_key}'")
    return category_path


def get_basic_library_category_path(descriptor: BasicBlockTemplateDescriptor) -> tuple[str, ...]:
    """Translate catalog metadata into the canonical ``Basic`` tree.

    The catalog retains its stable import metadata while this GUI-owned mapping
    controls only where a draggable leaf is presented. This keeps persistence
    and template materialization independent from library organization.

    :param descriptor: Editor-ready catalog descriptor to place in the tree.
    :return: Canonical path below ``Basic``.
    """
    source_path: tuple[str, ...] = tuple(descriptor.category_path)
    if len(source_path) > 0 and source_path[0] == "Native":
        source_path = source_path[1:]
    else:
        pass

    if len(source_path) > 0:
        primary_category: str = source_path[0]
    else:
        primary_category = ""
    if len(source_path) > 1:
        secondary_category: str = source_path[1]
    else:
        secondary_category = ""

    if primary_category in ("Arrays and Matrices", "Lookup and Tables"):
        category_path: tuple[str, ...] = get_basic_lookup_table_category_path(descriptor=descriptor)
    elif primary_category == "Math and Functions":
        category_path = get_basic_mathematical_category_path(
            descriptor=descriptor,
            source_category=secondary_category,
        )
    elif primary_category == "Waveforms and Time":
        category_path = get_basic_waveform_category_path(
            descriptor=descriptor,
            source_category=secondary_category,
        )
    elif primary_category == "Continuous":
        category_path = get_basic_continuous_category_path(
            descriptor=descriptor,
            source_category=secondary_category,
        )
    elif primary_category == "Logic and Events":
        category_path = get_basic_logic_category_path(
            descriptor=descriptor,
            source_category=secondary_category,
        )
    elif primary_category == "Limits and Nonlinearities":
        category_path = get_basic_limit_category_path(
            descriptor=descriptor,
            source_category=secondary_category,
        )
    elif primary_category == "Transforms":
        category_path = get_basic_transform_category_path(descriptor=descriptor)
    elif primary_category == "Complex":
        category_path = get_basic_complex_category_path(descriptor=descriptor)
    elif primary_category == "Mechanical":
        category_path = ("Mechanical", "Drive train")
    elif primary_category == "Control and Measurement" and secondary_category == "Controllers":
        category_path = get_basic_continuous_category_path(
            descriptor=descriptor,
            source_category=secondary_category,
        )
    elif primary_category == "Control and Measurement" and secondary_category == "Measurements and Units":
        category_path = get_basic_measurement_category_path(descriptor=descriptor)
    else:
        raise ValueError(
            f"Unclassified basic-catalog path {source_path!r} for '{descriptor.template_key}'"
        )
    return category_path


def get_basic_procedural_category_path(
        descriptor: ProceduralBlockTemplateDescriptor,
) -> tuple[str, ...] | None:
    """Return the Basic path for a reusable procedural primitive.

    Common sampling, memory, limit, latch, edge, and timer behaviors belong in
    the semantic Basic taxonomy. Device-oriented switching and diagnostic
    behaviors remain under the dedicated ``Procedural logic`` branch.

    :param descriptor: Procedural descriptor being projected into the Library.
    :return: Basic category path, or ``None`` for an advanced procedural block.
    """
    logic_tpe: ProceduralLogicType = descriptor.logic_tpe
    if logic_tpe == ProceduralLogicType.FixedSample:
        category_path: tuple[str, ...] | None = ("Memory and discrete-time", "Sample and hold")
    elif logic_tpe == ProceduralLogicType.SampledValue:
        category_path = ("Memory and discrete-time", "Previous value")
    elif logic_tpe == ProceduralLogicType.TimeDelay:
        category_path = ("Memory and discrete-time", "Exact time delay")
    elif logic_tpe == ProceduralLogicType.MovingAverage:
        category_path = ("Memory and discrete-time", "Moving average")
    elif logic_tpe == ProceduralLogicType.HardSaturation:
        category_path = ("Limits and nonlinearities", "Saturation")
    elif logic_tpe == ProceduralLogicType.GradientLimiter:
        category_path = ("Limits and nonlinearities", "Rate limiter")
    elif logic_tpe in (ProceduralLogicType.FlipFlop, ProceduralLogicType.AnalogFlipFlop):
        category_path = ("Logic and events", "Latches and flip-flops")
    elif logic_tpe in (ProceduralLogicType.PickupDropoff, ProceduralLogicType.DelayedThresholdLatch):
        category_path = ("Logic and events", "Timed comparator")
    elif logic_tpe == ProceduralLogicType.ResetOnRisingEdge:
        category_path = ("Logic and events", "Edge detector")
    elif logic_tpe == ProceduralLogicType.StartupHandover:
        category_path = ("Logic and events", "Timers")
    elif logic_tpe in (
            ProceduralLogicType.ConditionalDiagnostic,
            ProceduralLogicType.DelayedSwitchEvent,
            ProceduralLogicType.ValveState,
            ProceduralLogicType.ThreePhaseCarrierPwm,
            ProceduralLogicType.ThreePhaseCarrierSampledModulation,
    ):
        category_path = None
    else:
        raise ValueError(f"Unclassified procedural Library type '{logic_tpe.name}'")
    return category_path


def is_replaced_legacy_basic_descriptor(descriptor: BasicBlockTemplateDescriptor) -> bool:
    """Return whether the Basic library omits one redundant legacy leaf.

    The generated templates remain importable for saved-model compatibility.
    Their draggable entries are suppressed when a canonical structural,
    mathematical, or procedural block provides the same behavior, or when the
    template is a no-op identity block.

    :param descriptor: Basic catalog descriptor being considered for display.
    :return: ``True`` when the legacy descriptor must stay out of the library.
    """
    replaced_template_keys: tuple[str, ...] = (
        "1_sqrt2",
        "2pi_form_a",
        "2pi_form_b",
        "2pi_form_c",
        "2pi_form_d",
        "2pi_form_e",
        "abs",
        "aflipflop",
        "c_form_b",
        "c_form_c",
        "c_form_d",
        "c_form_e",
        "c_form_f",
        "delay",
        "e",
        "flipflop",
        "gradlim_const",
        "inverse_lookup_array_object_linear",
        "lastvalue_form_a",
        "lastvalue_form_b",
        "lookup_array_1x3_linear_fixed",
        "lookup_array_1x3_linear_variable",
        "lookup_array_1x4_linear_fixed",
        "lookup_array_1x4_linear_variable",
        "lookup_array_linear_noclipping",
        "lookup_array_object_linear",
        "lookup_array_object_linear_noclipping",
        "lookup_array_object_spline",
        "lookup_matrix_linear",
        "lookup_matrix_object_linear",
        "lookup_matrix_object_spline",
        "lookup_matrix_spline",
        "movingavg",
        "max2",
        "max3",
        "max4",
        "min2",
        "min3",
        "min4",
        "multiply_1_form_b",
        "multiply_1_sqrt2",
        "multiply_1_sqrt3",
        "multiply_k_form_a",
        "multiply_k_form_b",
        "multiply_pi",
        "multiply_sqrt2",
        "multiply_sqrt3",
        "multiply_sqrt_2_3",
        "multiply_sqrt_3_2",
        "pi",
        "pi_2",
        "picdro_const",
        "sqrt2",
        "sqrt3",
        "sqrt_2_3",
        "sqrt_3_2",
        "time_form_a",
    )
    return descriptor.template_key in replaced_template_keys


def build_non_empty_library_branch(branch: Dict[str, object]) -> Dict[str, object]:
    """Copy a Library branch while removing empty categories recursively.

    :param branch: Fully populated branch built from the canonical skeleton.
    :return: Branch containing only categories with at least one visible leaf.
    """
    result: Dict[str, object] = dict()
    label: str
    child_data: object
    for label, child_data in branch.items():
        if isinstance(child_data, dict):
            filtered_child: Dict[str, object] = build_non_empty_library_branch(branch=child_data)
            if len(filtered_child) > 0:
                result[label] = filtered_child
            else:
                pass
        elif isinstance(child_data, list):
            if len(child_data) > 0:
                result[label] = child_data
            else:
                pass
        else:
            raise TypeError(f"Unsupported Library branch data type {type(child_data)!r}")
    return result


def build_basic_library_branch() -> Dict[str, object]:
    """Build the complete categorized ``Basic`` library branch.

    Structural blocks, canonical procedural primitives, and non-duplicate
    catalog descriptors are inserted into one semantic hierarchy. Legacy
    wrapper templates remain loadable even when their duplicate leaf is hidden.

    :return: Nested branch data consumed by :class:`DynamicEditorLibrary`.
    """
    basic_branch: Dict[str, object] = build_basic_branch_skeleton()
    structural_blocks: tuple[tuple[tuple[str, ...], LibraryLeafSpec], ...] = (
        (("Mathematical functions", "Constants"), LibraryLeafSpec("Configurable constant", BlockType.CONST)),
        (("Mathematical functions", "Gain"), LibraryLeafSpec("Gain", BlockType.GAIN)),
        (("Mathematical functions", "Sum"), LibraryLeafSpec("Sum", BlockType.SUM)),
        (("Mathematical functions", "Product"), LibraryLeafSpec("Product", BlockType.PRODUCT)),
        (("Mathematical functions", "Minimum/Maximum"), LibraryLeafSpec("MIN", BlockType.MIN)),
        (("Mathematical functions", "Minimum/Maximum"), LibraryLeafSpec("MAX", BlockType.MAX)),
        (("Mathematical functions", "Absolute value"), LibraryLeafSpec("Absolute value", BlockType.ABS)),
        (("Lookup tables", "Inverse 1D lookup table"),
         LibraryLeafSpec("Inverse linear lookup table", BlockType.INVERSE_LOOKUP_ARRAY)),
        (("Lookup tables", "1D lookup table"),
         LibraryLeafSpec("Linear lookup table", BlockType.LOOKUP_ARRAY_LINEAR)),
        (("Lookup tables", "1D lookup table"),
         LibraryLeafSpec("Spline lookup table", BlockType.LOOKUP_ARRAY_SPLINE)),
        (("Lookup tables", "1D lookup table"),
         LibraryLeafSpec("Dynamic linear lookup table", BlockType.LOOKUP_ARRAY_LINEAR_VARIABLE)),
        (("Lookup tables", "2D lookup table"),
         LibraryLeafSpec("Bilinear lookup table", BlockType.LOOKUP_MATRIX_LINEAR)),
        (("Lookup tables", "2D lookup table"),
         LibraryLeafSpec("2D spline lookup table", BlockType.LOOKUP_MATRIX_SPLINE)),
    )
    structural_entry: tuple[tuple[str, ...], LibraryLeafSpec]
    for structural_entry in structural_blocks:
        insert_library_leaf(
            branch=basic_branch,
            category_path=structural_entry[0],
            leaf=structural_entry[1],
        )

    # Exact named values are registered as two parallel normal block families:
    # sources under Constants and multipliers under Gain. Imported equivalents
    # remain available for legacy files but their duplicate leaves are hidden.
    exact_descriptor: ExactMathematicalBlockDescriptor
    for exact_descriptor in build_exact_mathematical_block_descriptors():
        if exact_descriptor.operation == ExactMathematicalBlockOperation.CONSTANT:
            exact_category_path: tuple[str, ...] = ("Mathematical functions", "Constants")
        else:
            exact_category_path = ("Mathematical functions", "Gain")
        insert_library_leaf(
            branch=basic_branch,
            category_path=exact_category_path,
            leaf=LibraryLeafSpec(
                label=exact_descriptor.display_label,
                payload=exact_descriptor,
                search_text=exact_descriptor.search_text,
            ),
        )

    # Reusable procedural primitives are shown in their semantic Basic category
    # instead of being duplicated under the top-level procedural branch.
    procedural_descriptor: ProceduralBlockTemplateDescriptor
    for procedural_descriptor in get_dynamic_library_procedural_descriptors():
        procedural_category_path: tuple[str, ...] | None = get_basic_procedural_category_path(
            descriptor=procedural_descriptor,
        )
        if procedural_category_path is not None:
            insert_library_leaf(
                branch=basic_branch,
                category_path=procedural_category_path,
                leaf=LibraryLeafSpec(
                    label=procedural_descriptor.display_label,
                    payload=procedural_descriptor,
                    search_text=procedural_descriptor.search_text,
                ),
            )
        else:
            pass

    # Catalog descriptors carry stable import identities. Only their visible
    # paths are translated here, beside the rest of the Library registrations.
    # Redundant wrappers stay loadable for legacy models but are not exposed as
    # duplicate draggable entries.
    descriptor: BasicBlockTemplateDescriptor
    for descriptor in get_editor_ready_basic_block_catalog_descriptors():
        if is_replaced_legacy_basic_descriptor(descriptor=descriptor):
            pass
        else:
            insert_library_leaf(
                branch=basic_branch,
                category_path=get_basic_library_category_path(descriptor=descriptor),
                leaf=LibraryLeafSpec(
                    label=descriptor.display_label,
                    payload=descriptor,
                    search_text=descriptor.search_text,
                ),
            )

    # Planned categories without an implementation are intentionally omitted
    # until a real block is available, avoiding dead ends in the visible tree.
    return build_non_empty_library_branch(branch=basic_branch)


def build_procedural_library_branch() -> Dict[str, object]:
    """Build the advanced procedural-logic branch.

    The descriptor inventory and its ordering are owned locally by this
    Library module. Engine code remains responsible only for materializing the
    selected typed behavior.

    :return: Nested branch data shared by RMS and EMT editors.
    """
    branch: Dict[str, object] = dict()
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        if get_basic_procedural_category_path(descriptor=descriptor) is None:
            insert_library_leaf(
                branch=branch,
                category_path=tuple(descriptor.category_path),
                leaf=LibraryLeafSpec(
                    label=descriptor.display_label,
                    payload=descriptor,
                    search_text=descriptor.search_text,
                ),
            )
        else:
            pass
    return branch


def _library_leaf_label_sort_key(leaf: "LibraryLeafSpec") -> str:
    """
    Return the case-insensitive sort key for one library leaf.

    :param leaf: Library leaf specification.
    :return: Lower-case label.
    """
    return leaf.label.lower()


def is_supported_library_payload(item_data: object) -> bool:
    """
    Check whether a tree item payload can be dragged into the editor scene.

    :param item_data: Candidate payload object.
    :return: ``True`` when the payload can be materialized in the editor.
    """
    if isinstance(item_data, BlockType):
        return True
    elif isinstance(item_data, ExactMathematicalBlockDescriptor):
        return True
    elif isinstance(item_data, BasicBlockTemplateDescriptor):
        return True
    elif isinstance(item_data, ProceduralBlockTemplateDescriptor):
        return True
    elif isinstance(item_data, InternationalStandardTemplateDescriptor):
        return True
    elif isinstance(item_data, LibraryDeviceTemplateSpec):
        return True
    elif isinstance(item_data, (RmsModelTemplate, EmtModelTemplate, FmuTemplate)):
        return True
    else:
        return False


def insert_library_leaf(branch: Dict[str, object], category_path: tuple[str, ...], leaf: LibraryLeafSpec) -> None:
    """
    Insert one library leaf into a nested dictionary branch.

    :param branch: Mutable catalogue branch being populated.
    :param category_path: Remaining category path for the leaf.
    :param leaf: Typed leaf to insert.
    :return: None.
    """

    head: str = category_path[0]
    if len(category_path) == 1:
        leaves: object = branch.setdefault(head, list())
        if isinstance(leaves, list):
            leaves.append(leaf)
        else:
            raise TypeError(f"Category '{head}' is already used as a branch node")
    else:
        child_branch: object = branch.setdefault(head, dict())
        if isinstance(child_branch, dict):
            insert_library_leaf(child_branch, category_path[1:], leaf)
        else:
            raise TypeError(f"Category '{head}' is already used as a leaf collection")


def build_library_item_description(payload: object) -> str:
    """Return the description shown in the library tree second column.

    :param payload: Typed payload represented by one library leaf.
    :return: Human-readable description derived from existing block metadata.
    """
    if isinstance(payload, BasicBlockTemplateDescriptor):
        if len(payload.description) > 0:
            description: str = payload.description
        else:
            description = build_library_interface_description(
                inputs=payload.inputs,
                outputs=payload.outputs,
                states=payload.states,
                params=payload.params,
            )
    elif isinstance(payload, ExactMathematicalBlockDescriptor):
        description = payload.description
    elif isinstance(payload, ProceduralBlockTemplateDescriptor):
        if len(payload.description) > 0:
            description = payload.description
        else:
            description = build_library_interface_description(
                inputs=payload.input_names,
                outputs=payload.output_names,
                states=tuple(),
                params=tuple(parameter_spec.name for parameter_spec in payload.parameter_specs),
            )
        if payload.requires_configuration:
            description = f"{description.rstrip('.')}. Requires external configuration"
        else:
            pass
    elif isinstance(payload, InternationalStandardTemplateDescriptor):
        description = build_international_standard_description(model=payload.model)
    elif isinstance(payload, LibraryDeviceTemplateSpec):
        description = payload.description
    elif isinstance(payload, RmsModelTemplate):
        if len(payload.comment) > 0:
            description = payload.comment
        else:
            description = "RMS model template"
    elif isinstance(payload, EmtModelTemplate):
        if len(payload.comment) > 0:
            description = payload.comment
        else:
            description = "EMT model template"
    elif isinstance(payload, FmuTemplate):
        if len(payload.comment) > 0:
            description = payload.comment
        else:
            description = "FMU model template"
    elif isinstance(payload, BlockType):
        description = build_block_type_description(block_type=payload)
    else:
        description = ""

    return description


def build_library_interface_description(
        inputs: Sequence[str],
        outputs: Sequence[str],
        states: Sequence[str],
        params: Sequence[str],
) -> str:
    """Build a compact interface summary from descriptor metadata.

    :param inputs: Input port names.
    :param outputs: Output port names.
    :param states: State variable names.
    :param params: Runtime parameter names.
    :return: Compact description text.
    """
    parts: list[str] = list()
    input_part: str = build_library_name_list(label="Inputs", names=inputs)
    output_part: str = build_library_name_list(label="Outputs", names=outputs)
    state_part: str = build_library_name_list(label="States", names=states)
    param_part: str = build_library_name_list(label="Parameters", names=params)

    if len(input_part) > 0:
        parts.append(input_part)
    else:
        pass
    if len(output_part) > 0:
        parts.append(output_part)
    else:
        pass
    if len(state_part) > 0:
        parts.append(state_part)
    else:
        pass
    if len(param_part) > 0:
        parts.append(param_part)
    else:
        pass

    if len(parts) > 0:
        description: str = "; ".join(parts)
    else:
        description = "No exposed ports"

    return description


def build_library_name_list(label: str, names: Sequence[str]) -> str:
    """Build one bounded comma-separated description segment.

    :param label: Segment label.
    :param names: Names to display.
    :return: Description segment, or an empty string when no names exist.
    """
    if len(names) == 0:
        text: str = ""
    else:
        visible_names: list[str] = list()
        name_index: int
        for name_index in range(min(6, len(names))):
            visible_names.append(str(names[name_index]))
        if len(names) > len(visible_names):
            visible_names.append(f"+{len(names) - len(visible_names)} more")
        else:
            pass
        text = f"{label}: {', '.join(visible_names)}"

    return text


def build_block_type_description(block_type: BlockType) -> str:
    """Return the functional description of a native enum-backed block.

    :param block_type: Native block type.
    :return: Human-readable explanation of the block behavior.
    """
    if block_type == BlockType.FROM_GOTO:
        description: str = "Routes a signal between paired From and Goto connectors without a visible wire"
    elif block_type == BlockType.INPUT_CONN:
        description = "Connects bus measurements or external device variables to the dynamic model"
    elif block_type == BlockType.OUTPUT_CONN:
        description = "Maps a dynamic-model signal to an external device variable"
    elif block_type == BlockType.GENERIC:
        description = "Empty dynamic-model template for building a custom device or control"
    elif block_type == BlockType.PLL_TRANSFORM_RMS:
        description = "Phase-locked loop and reference-frame transform that derives d-q voltage and frequency"
    elif block_type == BlockType.VSC_PLL_RMS:
        description = "Explicit-state PI phase-locked loop that tracks AC-grid angle and frequency"
    elif block_type == BlockType.GOV_RMS:
        description = "Generator turbine-governor RMS control that regulates mechanical power from speed error"
    elif block_type == BlockType.EXCITER_RMS:
        description = "Generator excitation-system RMS control that regulates terminal voltage"
    elif block_type == BlockType.STAB_RMS:
        description = "Generator power-system stabilizer RMS control for damping electromechanical oscillations"
    elif block_type == BlockType.PI_POWER_CONTROLLER:
        description = "VSC outer-loop PI controller that converts active and reactive power errors to current references"
    elif block_type == BlockType.VSC_ACTIVE_CONTROL_RMS:
        description = "VSC outer-loop PI control of DC voltage or active power, producing a q-axis current reference"
    elif block_type == BlockType.VSC_REACTIVE_CONTROL_RMS:
        description = "VSC outer-loop PI control of AC voltage or reactive power, producing a d-axis current reference"
    elif block_type == BlockType.PI_CURRENT_CONTROLLER:
        description = "VSC inner-loop PI controller that converts current error to a converter voltage command"
    elif block_type == BlockType.VSC_VD_HAT_RMS:
        description = "VSC d-axis inner current PI controller producing the d-axis voltage correction"
    elif block_type == BlockType.VSC_VQ_HAT_RMS:
        description = "VSC q-axis inner current PI controller producing the q-axis voltage correction"
    elif block_type == BlockType.VSC_ELECTRICAL_RMS:
        description = "VSC electrical RMS equations for d-q current dynamics and AC-terminal power"
    elif block_type == BlockType.VSC_DC_LINK_RMS:
        description = "VSC DC-link capacitor dynamics with DC voltage and terminal-power constraints"
    elif block_type == BlockType.VSC_CURRENT_LIMITER_RMS:
        description = "VSC current-reference magnitude limiter with q-axis priority"
    elif block_type == BlockType.GOV_EMT:
        description = "Generator turbine-governor EMT control that regulates mechanical power from speed error"
    elif block_type == BlockType.EXCITER_EMT:
        description = "Generator excitation-system EMT control that regulates field voltage"
    elif block_type == BlockType.STAB_EMT:
        description = "Generator stabilizer EMT control for damping electromechanical oscillations"
    elif block_type == BlockType.RLC_COMBO_EMT:
        description = "Configurable three-phase resistor-inductor-capacitor branch for an EMT network"
    elif block_type == BlockType.FAULT_EMT:
        description = "Configurable EMT short-circuit fault with selectable phases and ground connection"
    elif block_type == BlockType.SWITCH_EMT:
        description = "Controlled ideal electrical switch for opening or closing an EMT branch"
    elif block_type.name.startswith("MEASUREMENTS_"):
        description = f"Exposes the {block_type.value} network measurement as a dynamic-model signal"
    elif block_type == BlockType.CONST:
        description = "Produces a configurable constant signal"
    elif block_type == BlockType.GAIN:
        description = "Multiplies an input signal by a configurable gain"
    elif block_type == BlockType.MIN:
        description = "Outputs the smallest input signal; the number of inputs is configurable"
    elif block_type == BlockType.MAX:
        description = "Outputs the largest input signal; the number of inputs is configurable"
    elif block_type == BlockType.SUM:
        description = "Adds or subtracts a configurable set of input signals"
    elif block_type == BlockType.DIVIDE:
        description = "Divides one input signal by another"
    elif block_type == BlockType.PRODUCT:
        description = "Multiplies a configurable set of input signals"
    elif block_type == BlockType.ABS:
        description = "Returns the absolute value or magnitude of the input signal"
    elif block_type == BlockType.INTEGRATOR:
        description = "Integrates the input signal over simulation time"
    elif block_type == BlockType.POWER:
        description = "Raises the input signal to a configurable power"
    elif block_type in tuple((BlockType.SIN, BlockType.COS, BlockType.TAN)):
        description = f"Applies the {block_type.value} trigonometric function to the input signal"
    elif block_type == BlockType.EXP:
        description = "Applies the natural exponential function to the input signal"
    elif block_type == BlockType.LOG:
        description = "Applies the natural logarithm to the input signal"
    elif block_type == BlockType.LOG10:
        description = "Applies the base-10 logarithm to the input signal"
    elif block_type == BlockType.SQRT:
        description = "Returns the square root of the input signal"
    elif block_type in tuple((BlockType.ASIN, BlockType.ACOS, BlockType.ATAN)):
        description = f"Applies the inverse {block_type.value} trigonometric function to the input signal"
    elif block_type in tuple((BlockType.SINH, BlockType.COSH, BlockType.TANH)):
        description = f"Applies the {block_type.value} hyperbolic function to the input signal"
    elif block_type == BlockType.REAL:
        description = "Extracts the real component of a complex input signal"
    elif block_type == BlockType.IMAG:
        description = "Extracts the imaginary component of a complex input signal"
    elif block_type == BlockType.CONJ:
        description = "Returns the complex conjugate of the input signal"
    elif block_type == BlockType.ANGLE:
        description = "Returns the phase angle of a complex input signal"
    elif block_type == BlockType.INVERSE_LOOKUP_ARRAY:
        description = "Computes the input corresponding to a tabulated output using linear interpolation"
    elif block_type == BlockType.LOOKUP_ARRAY_LINEAR:
        description = "Interpolates a configurable one-dimensional table linearly, with clipping or extrapolation"
    elif block_type == BlockType.LOOKUP_ARRAY_LINEAR_VARIABLE:
        description = (
            "Linearly interpolates a table whose ordered x/y points are signal inputs; "
            "the point count and clipping rule are configurable"
        )
    elif block_type == BlockType.LOOKUP_ARRAY_SPLINE:
        description = "Interpolates a configurable one-dimensional table with a clipped natural cubic spline"
    elif block_type == BlockType.LOOKUP_MATRIX_LINEAR:
        description = "Interpolates a configurable two-dimensional table bilinearly"
    elif block_type == BlockType.LOOKUP_MATRIX_SPLINE:
        description = "Interpolates a configurable two-dimensional table with a clipped natural cubic spline"
    elif block_type.name.endswith("_RMS"):
        description = f"RMS dynamic-model component implementing {block_type.value} behavior"
    elif block_type.name.endswith("_EMT"):
        description = f"EMT dynamic-model component implementing {block_type.value} behavior"
    else:
        description = f"Dynamic-model component implementing {block_type.value} behavior"

    return description


def set_library_branch_icon(item: QtGui.QStandardItem, branch_label: str) -> None:
    """Apply the best matching icon for one library branch row.

    :param item: Branch item whose icon is updated.
    :param branch_label: Branch text shown in the library tree.
    :return: None.
    """
    icon_path: str | None = device_type_icons.get(branch_label, None)
    if icon_path is None:
        if branch_label == "Basic":
            icon_path = ":/Icons/icons/Catalogue.png"
        elif branch_label == "Tools":
            icon_path = ":/Icons/icons/gear.png"
        elif branch_label == "Procedural logic":
            icon_path = ":/Icons/icons/dyn_edit.png"
        elif branch_label == "International standards":
            icon_path = ":/Icons/icons/dyn.png"
        elif branch_label == "Native":
            icon_path = ":/Icons/icons/dyn_gray.png"
        elif branch_label == "Faults":
            icon_path = ":/Icons/icons/short_circuit_plus.png"
        elif branch_label == "Devices":
            icon_path = ":/Icons/icons/dyn_gray.png"
        elif branch_label == "Controls":
            icon_path = ":/Icons/icons/control_pc.png"
        else:
            icon_path = ":/Icons/icons/tree.png"
    else:
        pass
    item.setIcon(QtGui.QIcon(icon_path))


def set_library_item_icon(item: QtGui.QStandardItem, payload: object) -> None:
    """
    Apply the best matching icon for one draggable library leaf.

    :param item: Tree item whose icon is updated.
    :param payload: Typed payload represented by the item.
    :return: None.
    """

    if isinstance(payload, FmuTemplate):
        item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.FmuTemplateDevice.value]))
    elif isinstance(payload, RmsModelTemplate):
        item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.RmsModelTemplateDevice.value]))
    elif isinstance(payload, InternationalStandardTemplateDescriptor):
        item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.RmsModelTemplateDevice.value]))
    elif isinstance(payload, LibraryDeviceTemplateSpec):
        icon_path: str | None = device_type_icons.get(payload.device_type.value, None)
        if icon_path is not None:
            item.setIcon(QtGui.QIcon(icon_path))
        elif payload.mode == DynamicSimulationMode.RMS:
            item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.RmsModelTemplateDevice.value]))
        else:
            item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.EmtModelTemplateDevice.value]))
    elif isinstance(
            payload,
            (
                EmtModelTemplate,
                BasicBlockTemplateDescriptor,
                ExactMathematicalBlockDescriptor,
                ProceduralBlockTemplateDescriptor,
            ),
    ):
        item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.EmtModelTemplateDevice.value]))
    elif isinstance(payload, BlockType):
        if payload == BlockType.FROM_GOTO:
            item.setIcon(QtGui.QIcon(":/Icons/icons/tree.png"))
        elif payload == BlockType.INPUT_CONN or payload.name.startswith("MEASUREMENTS_"):
            item.setIcon(QtGui.QIcon(":/Icons/icons/measurement.png"))
        elif payload == BlockType.SUM:
            item.setIcon(QtGui.QIcon(":/Icons/icons/plus.png"))
        elif payload == BlockType.PRODUCT:
            item.setIcon(QtGui.QIcon(":/Icons/icons/multiply.png"))
        elif payload == BlockType.DIVIDE:
            item.setIcon(QtGui.QIcon(":/Icons/icons/divide.png"))
        elif payload.name.endswith("_EMT"):
            item.setIcon(QtGui.QIcon(":/Icons/icons/dyn_emt.png"))
        elif payload.name.endswith("_RMS"):
            item.setIcon(QtGui.QIcon(":/Icons/icons/dyn.png"))
        else:
            item.setIcon(QtGui.QIcon(":/Icons/icons/dyn_gray.png"))
    else:
        pass
