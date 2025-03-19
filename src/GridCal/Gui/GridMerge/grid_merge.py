# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from typing import List, Dict, Any
from GridCal.Gui.GridMerge.grid_merge_gui import Ui_Dialog
from GridCal.Gui.messages import yes_no_question
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import DeviceType, SubstationTypes, ActionType
from GridCalEngine.Devices.types import ALL_DEV_TYPES


def handle_item_changed(item, column):
    """

    :param item:
    :param column:
    :return:
    """
    if item.parent() is None:  # Root item
        state = item.checkState(0)
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, state)


class GridMergeDialogue(QtWidgets.QDialog):
    """
    GridMergeDialogue
    """

    def __init__(self, grid: MultiCircuit):
        """

        :param grid:
        """
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid merger')

        self.ui.treeWidget.setHeaderLabels(
            ["Grid", "Object type", "action", "idtag", "name", "property", "value", "new value"]
        )

        self._base_grid: MultiCircuit = grid

        self._all_elms_base_dict, _ = self._base_grid.get_all_elements_dict()

        self._diff: MultiCircuit | None = None

        self._objects_dict: Dict[str, ALL_DEV_TYPES] = dict()

        # tree item changes
        self.ui.treeWidget.itemChanged.connect(handle_item_changed)

        self.ui.acceptButton.clicked.connect(self.apply_changes)

    def open_grid(self):
        pass

    def set_diff(self, diff: MultiCircuit):
        """

        :param diff:
        :return:
        """
        self._diff = diff

    def build_tree(self):
        """

        :return:
        """
        self.ui.treeWidget.clear()

        self._objects_dict, ok2 = self._diff.get_all_elements_dict()
        diff_name = self._diff.name
        logger = Logger()
        nt = self._base_grid.get_time_number()
        detailed_profile_comparison = False

        custom_red = QColor(255, 102, 102)
        custom_green = QColor(102, 255, 102)
        custom_blue = QColor(102, 178, 255)

        # ["Grid", "Object type", "action", "idtag", "name", "property", "value", "new value"]

        for elm in self._diff.items():

            if elm.action == ActionType.Add:
                parent_item = QtWidgets.QTreeWidgetItem(
                    self.ui.treeWidget,
                    [f"{diff_name}", f"{elm.device_type.value}", "Add", f"{elm.idtag}", f"{elm.name}", "", "", ""]
                )
                parent_item.setCheckState(0, Qt.CheckState.Unchecked)
                parent_item.setBackground(2, custom_green)

            elif elm.action == ActionType.Delete:
                parent_item = QtWidgets.QTreeWidgetItem(
                    self.ui.treeWidget,
                    [f"{diff_name}", f"{elm.device_type.value}", "Del", f"{elm.idtag}", f"{elm.name}", "", "", ""]
                )
                parent_item.setCheckState(0, Qt.CheckState.Unchecked)
                parent_item.setBackground(2, custom_red)

            elif elm.action == ActionType.Modify:
                parent_item = QtWidgets.QTreeWidgetItem(
                    self.ui.treeWidget,
                    [f"{diff_name}", f"{elm.device_type.value}", "Mod", f"{elm.idtag}", f"{elm.name}", "", "", ""]
                )
                parent_item.setCheckState(0, Qt.CheckState.Unchecked)
                parent_item.setBackground(2, custom_blue)

                elm_from_base = self._all_elms_base_dict.get(elm.idtag, None)

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

    def apply_changes(self):
        """
        Apply the changes
        :return:
        """

        for i in range(self.ui.treeWidget.topLevelItemCount()):

            tree_item = self.ui.treeWidget.topLevelItem(i)

            # ["Grid", "Object type", "action", "idtag", "name", "property", "value", "new value"]
            idtag = tree_item.text(3)
            elm: ALL_DEV_TYPES = self._objects_dict.get(idtag, None)
            selected = tree_item.checkState(0) == Qt.CheckState.Checked

            if elm is not None and selected:

                if elm.action == ActionType.Add:
                    self._base_grid.add_element(obj=elm)

                elif elm.action == ActionType.Delete:

                    elm_from_base = self._all_elms_base_dict.get(idtag, None)
                    if elm_from_base is not None:
                        self._base_grid.delete_element(obj=elm_from_base)

                elif elm.action == ActionType.Modify:

                    elm_from_base = self._all_elms_base_dict.get(idtag, None)

                    if elm_from_base is not None:

                        for j in range(tree_item.childCount()):

                            child_item = tree_item.child(j)
                            if child_item.checkState(0) == Qt.CheckState.Checked:
                                prop_name = child_item.text(0)
                                prop = elm.get_property_by_name(prop_name)

                                value = elm.get_property_value(prop=prop, t_idx=None)

                                elm_from_base.set_property_value(prop=prop, value=value, t_idx=None)

        # Done
        self.close()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    window = GridMergeDialogue(None)
    # window.resize(int(1.61 * 700.0), int(600.0))  # golden ratio
    window.show()
    sys.exit(app.exec())
