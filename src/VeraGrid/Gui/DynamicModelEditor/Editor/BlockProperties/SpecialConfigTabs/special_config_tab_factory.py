# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Select the special Block Properties tab for one native block type."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.lookup_1d_config_tab import (
    Lookup1DConfigTab,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.special_config_tab import (
    SpecialConfigTabWidget,
)
from VeraGridEngine.enumerations import BlockType
from VeraGridEngine.Templates.template_definition import TemplateDefinition


def get_special_config_tab_title(block_type: BlockType) -> str:
    """Return the semantic tab title associated with one block family.

    :param block_type: Native block type being edited.
    :return: Translatable user-facing tab title.
    """
    if block_type in (
            BlockType.INVERSE_LOOKUP_ARRAY,
            BlockType.LOOKUP_ARRAY_LINEAR,
            BlockType.LOOKUP_ARRAY_SPLINE,
            BlockType.LOOKUP_MATRIX_LINEAR,
            BlockType.LOOKUP_MATRIX_SPLINE,
    ):
        title: str = QtCore.QCoreApplication.translate(
            "SpecialConfigTabs",
            "Table configuration",
        )
    elif block_type == BlockType.NONLINEAR_RESISTOR_EMT:
        title = QtCore.QCoreApplication.translate(
            "SpecialConfigTabs",
            "V-I curve",
        )
    elif block_type in (
            BlockType.ARBITRARY_WAVEFORM_VOLTAGE_SOURCE_EMT,
            BlockType.ARBITRARY_WAVEFORM_CURRENT_SOURCE_EMT,
    ):
        title = QtCore.QCoreApplication.translate(
            "SpecialConfigTabs",
            "Waveform configuration",
        )
    elif block_type == BlockType.XFMR_TRANSFORMER:
        title = QtCore.QCoreApplication.translate(
            "SpecialConfigTabs",
            "Core saturation",
        )
    elif block_type == BlockType.EMT_JMARTI_LINE:
        title = QtCore.QCoreApplication.translate(
            "SpecialConfigTabs",
            "JMarti line configuration",
        )
    else:
        title = QtCore.QCoreApplication.translate(
            "SpecialConfigTabs",
            "Special configuration",
        )
    return title


def has_special_config_tab_editor(block_type: BlockType | None,
                                  builder: TemplateDefinition | None) -> bool:
    """Return whether a concrete special editor is implemented and usable.

    This capability check does not instantiate Qt widgets. Block Properties can
    therefore decide which generated parameters belong to a dedicated editor
    without changing the established widget construction order.

    :param block_type: Native block type considered for special configuration.
    :param builder: Detached template builder required by structural editors.
    :return: Whether the factory can create the corresponding concrete tab.
    """
    if (
            block_type in (
                BlockType.INVERSE_LOOKUP_ARRAY,
                BlockType.LOOKUP_ARRAY_LINEAR,
                BlockType.LOOKUP_ARRAY_SPLINE,
            )
            and builder is not None
    ):
        result: bool = True
    else:
        result = False
    return result


def create_special_config_tab(
        block_type: BlockType | None,
        builder: TemplateDefinition | None,
        parent: QtWidgets.QWidget,
        dark_theme: bool,
) -> SpecialConfigTabWidget | None:
    """Create the editor selected for the current structural block family.

    Dedicated editor branches are added here as their implementation points are
    completed. Keeping selection in this factory prevents Block Properties from
    accumulating block-specific branches or restoring a generic fallback tab.

    :param block_type: Native block type controlling editor selection.
    :param builder: Detached template builder receiving validated values.
    :param parent: Owning Block Properties dialog.
    :param dark_theme: Whether charts and custom controls use a dark palette.
    :return: Selected tab widget, or ``None`` when its concrete editor is absent.
    """
    if (
            has_special_config_tab_editor(block_type=block_type, builder=builder)
            and builder is not None
            and block_type is not None
    ):
        # Static one-dimensional lookups own stored point coordinates. The
        # signal-driven lookup variant remains in General options because its
        # points are diagram inputs rather than editable table data.
        result: SpecialConfigTabWidget | None = Lookup1DConfigTab(
            builder=builder,
            block_type=block_type,
            parent=parent,
            dark_theme=dark_theme,
        )
    else:
        # Each following implementation point adds another explicit branch.
        # No generic fallback is allowed for unimplemented block families.
        result = None
    return result
