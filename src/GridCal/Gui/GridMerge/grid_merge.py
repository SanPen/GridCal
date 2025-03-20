# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from GridCal.Gui.GridMerge.build_diff_tree import populate_tree
from GridCal.Gui.GridMerge.grid_merge_gui import Ui_Dialog
from GridCal.Gui.general_dialogues import LogsDialogue
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import ActionType
from GridCalEngine.Devices.types import ALL_DEV_TYPES


def handle_item_changed(item: QtWidgets.QTreeWidgetItem, column: int):
    """

    :param item:
    :param column: THis must be here because this is an event handler
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

    def __init__(self, grid: MultiCircuit, diff: MultiCircuit):
        """

        :param grid:
        """
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid merges & acquisitions')

        self.ui.treeWidget.setHeaderLabels(
            ["Grid", "Object type", "action", "idtag", "name", "property", "value", "new value"]
        )

        self.logger = Logger()

        self._base_grid: MultiCircuit = grid

        self._diff: MultiCircuit = diff

        self.all_elms_base_dict, ok = self._base_grid.get_all_elements_dict(logger=self.logger)

        if not ok:
            dlg = LogsDialogue('The base circuit has duplicated idtags and cannot be merged :(', self.logger)
            dlg.exec()
            return

        self.build_tree()

        self.added_grid: bool = False
        self.merged_grid: bool = False

        # tree item changes
        self.ui.treeWidget.itemChanged.connect(handle_item_changed)

        self.ui.acceptButton.clicked.connect(self.merge_grid)

        self.ui.addButton.clicked.connect(self.add_grid)

    def set_diff(self, diff: MultiCircuit):
        """

        :param diff:
        :return:
        """
        self._diff = diff

    def build_tree(self):
        """
        Build the display tree
        """

        all_no_action = populate_tree(tree_widget=self.ui.treeWidget,
                                      base=self._base_grid,
                                      diff=self._diff,
                                      all_elms_base_dict=self.all_elms_base_dict)

        # if all_no_action: we cannot merge
        self.ui.acceptButton.setVisible(not all_no_action)

    def merge_grid(self):
        """
        Apply the changes
        :return:
        """

        # logger = Logger()
        #
        # # add profiles if required
        # if self.time_profile is not None:
        #     new_grid.time_profile = self.time_profile
        #     new_grid.ensure_profiles_exist()
        #
        # for new_elm in new_grid.items():
        #     self.add_or_replace_object(api_obj=new_elm, logger=logger)
        #
        # return logger



        objects_dict, ok2 = self._diff.get_all_elements_dict(logger=self.logger)
        if not ok2:
            dlg = LogsDialogue('The diff circuit has duplicated idtags and cannot be merged :(', self.logger)
            dlg.exec()
            return

        for i in range(self.ui.treeWidget.topLevelItemCount()):

            tree_item = self.ui.treeWidget.topLevelItem(i)

            # ["Grid", "Object type", "action", "idtag", "name", "property", "value", "new value"]
            idtag = tree_item.text(3)
            elm: ALL_DEV_TYPES = objects_dict.get(idtag, None)
            selected = tree_item.checkState(0) == Qt.CheckState.Checked

            if elm is not None and selected:

                if elm.action == ActionType.Add:
                    self._base_grid.add_element(obj=elm)

                elif elm.action == ActionType.Delete:

                    elm_from_base = self.all_elms_base_dict.get(idtag, None)
                    if elm_from_base is not None:
                        self._base_grid.delete_element(obj=elm_from_base)

                elif elm.action == ActionType.Modify:

                    elm_from_base = self.all_elms_base_dict.get(idtag, None)

                    if elm_from_base is not None:

                        for j in range(tree_item.childCount()):

                            child_item = tree_item.child(j)
                            if child_item.checkState(0) == Qt.CheckState.Checked:
                                prop_name = child_item.text(0)
                                prop = elm.get_property_by_name(prop_name)

                                value = elm.get_property_value(prop=prop, t_idx=None)

                                elm_from_base.set_property_value(prop=prop, value=value, t_idx=None)

        # Done
        self.added_grid: bool = False
        self.merged_grid: bool = True
        self.close()

    def add_grid(self):
        """
        The elements of the grid will be added with new idtags.
        This is useful in the case you want to compose a new grid from grids that are the same.
        :return:
        """
        self._base_grid.add_circuit(self._base_grid)
        self.added_grid: bool = True
        self.merged_grid: bool = False
        self.close()
