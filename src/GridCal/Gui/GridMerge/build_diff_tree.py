# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from typing import List, Dict, Any

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import DeviceType, SubstationTypes, ActionType
from GridCalEngine.Devices.types import ALL_DEV_TYPES


def populate_tree(tree_widget, base: MultiCircuit, diff: MultiCircuit,
                  all_elms_base_dict: Dict[str, ALL_DEV_TYPES]):
    """
    Build the display tree
    :param tree_widget:
    :param base:
    :param diff:
    :param all_elms_base_dict:
    :return:
    """
    tree_widget.clear()
    logger = Logger()

    diff_name = diff.name

    nt = base.get_time_number()
    detailed_profile_comparison = False

    custom_red = QColor(173, 0, 43)
    custom_green = QColor(0, 173, 61)
    custom_blue = QColor(0, 93, 173)

    # all no_action
    all_no_action = True
    # ["Grid", "Object type", "action", "idtag", "name", "property", "value", "new value"]

    for elm in diff.items():

        if elm.action == ActionType.Add:
            parent_item = QtWidgets.QTreeWidgetItem(
                tree_widget,
                [f"{diff_name}", f"{elm.device_type.value}", "Add", f"{elm.idtag}", f"{elm.name}", "", "", ""]
            )
            parent_item.setCheckState(0, Qt.CheckState.Checked)
            parent_item.setBackground(2, custom_green)
            all_no_action = False

        elif elm.action == ActionType.Delete:
            parent_item = QtWidgets.QTreeWidgetItem(
                tree_widget,
                [f"{diff_name}", f"{elm.device_type.value}", "Del", f"{elm.idtag}", f"{elm.name}", "", "", ""]
            )
            parent_item.setCheckState(0, Qt.CheckState.Checked)
            parent_item.setBackground(2, custom_red)
            all_no_action = False

        elif elm.action == ActionType.NoAction:
            parent_item = QtWidgets.QTreeWidgetItem(
                tree_widget,
                [f"{diff_name}", f"{elm.device_type.value}", "-", f"{elm.idtag}", f"{elm.name}", "", "", ""]
            )
            # parent_item.setCheckState(0, Qt.CheckState.Checked)
            # parent_item.setBackground(2, custom_green)

        elif elm.action == ActionType.Modify:
            parent_item = QtWidgets.QTreeWidgetItem(
                tree_widget,
                [f"{diff_name}", f"{elm.device_type.value}", "Mod", f"{elm.idtag}", f"{elm.name}", "", "", ""]
            )
            parent_item.setCheckState(0, Qt.CheckState.Checked)
            parent_item.setBackground(2, custom_blue)
            all_no_action = False

            elm_from_base = all_elms_base_dict.get(elm.idtag, None)

            if elm_from_base is not None:

                action, changed_props = elm.compare(
                    other=elm_from_base,
                    logger=logger,
                    detailed_profile_comparison=detailed_profile_comparison,
                    nt=nt
                )

                for prop in changed_props:
                    base_val = elm_from_base.get_property_value(prop=prop, t_idx=None)
                    new_val = elm.get_property_value(prop=prop, t_idx=None)

                    child_item = QtWidgets.QTreeWidgetItem(
                        parent_item,
                        [f"{elm.device_type.value}", "Mod", f"{elm.idtag}", f"{elm.name}",
                         prop.name, str(base_val), str(new_val)]
                    )
                    child_item.setCheckState(0, Qt.CheckState.Unchecked)

    return all_no_action
