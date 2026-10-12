# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from itertools import chain
from typing import Iterable

from VeraGridEngine.Devices.Parents.dynamic_bus_parent import DynamicBusDevice
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType, DynamicSimulationMode, FmuTemplateDomain


def get_available_dynamic_modes(api_object: ALL_DEV_TYPES) -> tuple[DynamicSimulationMode, ...]:
    """
    Return the modes that can be opened for one API object.

    :param api_object: Device or template candidate.
    :return: Tuple of supported dynamic simulation modes.
    """
    modes: list[DynamicSimulationMode] = list()

    device_type = api_object.device_type

    if device_type == DeviceType.RmsModelTemplateDevice:
        return (DynamicSimulationMode.RMS,)
    if device_type == DeviceType.EmtModelTemplateDevice:
        return (DynamicSimulationMode.EMT,)

    if isinstance(api_object, (DynamicDevice, DynamicBusDevice)):
        if api_object.rms_model is not None:
            modes.append(DynamicSimulationMode.RMS)
        else:
            pass
        if api_object.emt_model is not None:
            modes.append(DynamicSimulationMode.EMT)
        else:
            pass
    else:
        pass

    return tuple(modes)


def entry_supports_dynamic_events(entry: "DynamicEditorEntry") -> bool:
    """Return whether an entry represents a concrete event-target device.

    Dynamic model templates are valid model-editor entries, but events target
    network devices. Keeping this distinction in the entry layer prevents the
    device tree and direct routing paths from advertising invalid event tabs.

    :param entry: Dynamic editor entry to inspect.
    :return: ``True`` for concrete devices and ``False`` for model templates.
    """
    device_type: DeviceType = entry.api_object.device_type
    is_model_template: bool = (
        device_type == DeviceType.RmsModelTemplateDevice
        or device_type == DeviceType.EmtModelTemplateDevice
    )
    return isinstance(entry.api_object, EditableDevice) and not is_model_template


def build_dynamic_editor_entry(
        api_object: ALL_DEV_TYPES,
        circuit: MultiCircuit,
) -> DynamicEditorEntry | None:
    """
    Build one dynamic editor entry or return ``None`` when unsupported.

    :param api_object: Device or template candidate.
    :param circuit: Circuit that owns the candidate object.
    :return: Resolved editor entry or ``None``.
    """
    available_modes: tuple[DynamicSimulationMode, ...] = get_available_dynamic_modes(api_object)
    if len(available_modes) == 0:
        return None
    else:
        pass

    if isinstance(api_object, EditableDevice):
        key_base: str = f"{api_object.device_type.value}:{api_object.idtag}"
        type_label: str = str(api_object.device_type.value)
        display_name: str = api_object.name
    else:
        key_base = f"dynamic-object:{id(api_object)}"
        api_object_class_name: str = api_object.__class__.__name__
        type_label = api_object_class_name
        display_name = api_object.name

    return DynamicEditorEntry(
        api_object=api_object,
        circuit=circuit,
        available_modes=available_modes,
        display_name=display_name,
        type_label=type_label,
        key_base=key_base,
    )


def iter_dynamic_editor_entries(circuit: MultiCircuit) -> Iterable[DynamicEditorEntry]:
    """
    Yield every circuit object that can be opened in the dynamic editor.

    :param circuit: Circuit whose devices will be scanned.
    :return: Iterable of unique editor entries.
    """
    seen_keys: set[str] = set()
    branch_objects: list[ALL_DEV_TYPES] = list(circuit.get_branches(add_vsc=True, add_hvdc=True, add_switch=True))
    injection_objects: list[ALL_DEV_TYPES] = list(circuit.get_injection_devices())
    scanned_objects: Iterable[ALL_DEV_TYPES] = chain(injection_objects, branch_objects)
    api_object: ALL_DEV_TYPES
    entry: DynamicEditorEntry | None

    # The tree must list every branch-like device that can own one dynamic
    # editor model. The default branch collector excludes VSC and HVDC objects,
    # so request the full branch family explicitly before deduplicating entries.
    # The algorithm scans injections and branch-like devices in one pass, then
    # filters unsupported objects and duplicate mode keys before yielding them
    # to the workspace tree builder.
    for api_object in scanned_objects:
        entry = build_dynamic_editor_entry(api_object, circuit)
        if entry is None:
            pass
        else:
            if entry.key_base in seen_keys:
                pass
            else:
                seen_keys.add(entry.key_base)
                yield entry


def get_templates_for_entry(
        entry: DynamicEditorEntry,
        mode: DynamicSimulationMode,
) -> list[ALL_DEV_TYPES]:
    """
    Return the template list exposed in the editor library for one entry.

    :param entry: Entry being edited.
    :param mode: Dynamic simulation mode being opened.
    :return: Template list for the editor library.
    """
    api_object: ALL_DEV_TYPES = entry.api_object
    device_type: DeviceType = api_object.device_type
    templates: list[ALL_DEV_TYPES]

    if device_type == DeviceType.RmsModelTemplateDevice:
        templates = list(
            entry.circuit.get_dynamic_templates_by_domain(FmuTemplateDomain.RMS)
        )
    else:
        if device_type == DeviceType.EmtModelTemplateDevice:
            templates = list(
                entry.circuit.get_dynamic_templates_by_domain(FmuTemplateDomain.EMT)
            )
        else:
            if mode == DynamicSimulationMode.RMS:
                domain: FmuTemplateDomain = FmuTemplateDomain.RMS
            else:
                domain = FmuTemplateDomain.EMT

            # Assets owns the native-plus-FMU compatibility rule. Both initial
            # page construction and later session refresh therefore consume the
            # same ordered catalogue without duplicating filters in the GUI.
            templates = list(
                entry.circuit.get_dynamic_templates_by_device_type_and_domain(
                    tpe=device_type,
                    domain=domain,
                )
            )

    return templates


def get_block_for_entry(entry: DynamicEditorEntry, mode: DynamicSimulationMode) -> Block:
    """
    Return the block edited by one entry and mode.

    :param entry: Entry being edited.
    :param mode: Dynamic simulation mode being opened.
    :return: Backing block object for the editor page.
    """
    api_object = entry.api_object
    device_type = api_object.device_type

    if (
        device_type == DeviceType.RmsModelTemplateDevice
        or device_type == DeviceType.EmtModelTemplateDevice
    ):
        return api_object.block
    if mode == DynamicSimulationMode.RMS:
        return api_object.rms_model
    return api_object.emt_model


class DynamicEditorEntry:
    """
    One selectable and openable dynamic editor entry.
    """

    __slots__ = (
        "api_object",
        "circuit",
        "available_modes",
        "display_name",
        "type_label",
        "key_base",
    )

    def __init__(
        self,
        api_object: ALL_DEV_TYPES,
        circuit: MultiCircuit,
        available_modes: tuple[DynamicSimulationMode, ...],
        display_name: str,
        type_label: str,
        key_base: str,
    ) -> None:
        """
        Initialize one dynamic editor entry.

        :param api_object: Device or template being referenced.
        :param circuit: Circuit that owns the object.
        :param available_modes: Supported dynamic simulation modes.
        :param display_name: User-facing device name.
        :param type_label: User-facing device type label.
        :param key_base: Stable key shared by both modes of the same object.
        :return: None.
        """
        self.api_object: ALL_DEV_TYPES = api_object
        self.circuit: MultiCircuit = circuit
        self.available_modes: tuple[DynamicSimulationMode, ...] = available_modes
        self.display_name: str = display_name
        self.type_label: str = type_label
        self.key_base: str = key_base

    def session_key(self, mode: DynamicSimulationMode) -> str:
        """
        Build the unique session key for one entry-mode pair.

        :param mode: Dynamic simulation mode to encode.
        :return: Unique session key.
        """
        return f"{self.key_base}:{mode.name}"
