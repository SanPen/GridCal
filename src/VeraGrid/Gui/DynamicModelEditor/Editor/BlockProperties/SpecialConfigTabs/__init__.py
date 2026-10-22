# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Reusable infrastructure for block-specific configuration tabs."""

from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.lookup_1d_config_tab import (
    Lookup1DConfigTab,
    Lookup1DTableModel,
    get_lookup_1d_builder_points,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.special_config_tab import (
    SpecialConfigTabWidget,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.special_config_tab_factory import (
    create_special_config_tab,
    get_special_config_tab_title,
    has_special_config_tab_editor,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.SpecialConfigTabs.table_configuration_data import (
    CurveTableDraft,
    LookupMatrixDraft,
    build_sorted_axis_indexes,
    generate_curve_points_from_expression,
    normalize_curve_points,
    normalize_lookup_matrix,
    validate_strictly_increasing_axis,
)

__all__: tuple[str, ...] = (
    "CurveTableDraft",
    "Lookup1DConfigTab",
    "Lookup1DTableModel",
    "LookupMatrixDraft",
    "SpecialConfigTabWidget",
    "build_sorted_axis_indexes",
    "create_special_config_tab",
    "generate_curve_points_from_expression",
    "get_special_config_tab_title",
    "has_special_config_tab_editor",
    "get_lookup_1d_builder_points",
    "normalize_curve_points",
    "normalize_lookup_matrix",
    "validate_strictly_increasing_axis",
)
