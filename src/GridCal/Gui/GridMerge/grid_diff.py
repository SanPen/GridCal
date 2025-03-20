# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from GridCal.Gui.GridMerge.build_diff_tree import populate_tree
from GridCal.Gui.GridMerge.grid_diff_gui import Ui_Dialog
from GridCal.Gui.general_dialogues import LogsDialogue
from GridCal.Gui.messages import error_msg
import GridCal.Session.file_handler as filedrv

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.types import ALL_DEV_TYPES


def handle_item_changed(item: QtWidgets.QTreeWidgetItem, column: int):
    """

    :param item:
    :param column: THis must be here because this is an event handler
    :return:
    """
    if item.parent() is None:  # Root item
        item.setCheckState(0, Qt.CheckState.Checked)  # always checked...
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, Qt.CheckState.Checked)


class GridDiffDialogue(QtWidgets.QDialog):
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
        self.setWindowTitle('Grid differential')

        self.ui.treeWidget.setHeaderLabels(
            ["Grid", "Object type", "action", "idtag", "name", "property", "value", "new value"]
        )

        self.logger = Logger()

        self._new_grid: MultiCircuit = grid

        self.all_elms_base_dict, ok = self._new_grid.get_all_elements_dict(logger=self.logger)

        if not ok:
            dlg = LogsDialogue('The circuit has duplicated idtags and cannot be differentiated :(', self.logger)
            dlg.exec()
            return

        self._diff: MultiCircuit | None = None

        self.added_grid: bool = False
        self.merged_grid: bool = False
        self.ui.addButton.setText("Open base")
        self.ui.acceptButton.setText("Save diff")

        self.open_file_thread_object = None
        self.save_file_thread_object = None

        # tree item changes
        self.ui.treeWidget.itemChanged.connect(handle_item_changed)
        self.ui.acceptButton.clicked.connect(self.save_diff)
        self.ui.addButton.clicked.connect(self.open_base_grid)

    def open_base_grid(self):
        """
        Open base grid
        :return:
        """
        files_types = "GridCal (*.gridcal)"

        filename, type_selected = QtWidgets.QFileDialog.getOpenFileName(parent=self,
                                                                        caption="Open base grid",
                                                                        filter=files_types)

        if len(filename) > 0:
            if os.path.exists(filename):
                # create thread
                self.open_file_thread_object = filedrv.FileOpenThread(
                    file_name=filename,
                    previous_circuit=None,
                    options=filedrv.FileOpenOptions()
                )

                # make connections
                # self.open_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
                # self.open_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
                self.open_file_thread_object.done_signal.connect(self.post_open_base_grid)

                # thread start
                self.open_file_thread_object.start()
            else:
                error_msg(title="File not found", text=f"{filename} not found :(")

        else:
            self.open_file_thread_object = None

    def post_open_base_grid(self):
        """
        After open, make the diff
        :return:
        """
        if self.open_file_thread_object is not None:

            if self.open_file_thread_object.valid:

                # assign the loaded circuit
                if self.open_file_thread_object.circuit is not None:
                    base_grid: MultiCircuit = self.open_file_thread_object.circuit

                    ok, logger, self._diff = self._new_grid.differentiate_circuits(base_grid=base_grid,
                                                                                   detailed_profile_comparison=True)

                    if ok:
                        self.build_tree()
                    else:
                        dlg = LogsDialogue('Errors while computing the differential :(', logger)
                        dlg.exec()

    def build_tree(self):
        """
        Build the display tree
        """
        all_no_action = populate_tree(tree_widget=self.ui.treeWidget,
                                      base=self._new_grid,
                                      diff=self._diff,
                                      all_elms_base_dict=self.all_elms_base_dict)

    def save_diff(self):
        """
        Apply the changes
        :return:
        """
        if self._diff is None:
            error_msg(text="No differential created :(\nDid you load a base grid to compare?",
                      title="No diff")
        else:
            # select the file to save
            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file',
                                                                            self._diff.name,
                                                                            "GridCal diff (*.dgridcal)")

            if filename != '':

                # if the user did not enter the extension, add it automatically
                name, file_extension = os.path.splitext(filename)

                if file_extension == '':
                    filename = name + ".dgridcal"

                self.save_file_thread_object = filedrv.FileSaveThread(circuit=self._diff,
                                                                      file_name=filename,
                                                                      options=filedrv.FileSavingOptions())

                # make connections
                # self.save_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
                # self.save_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
                # self.save_file_thread_object.done_signal.connect(self.UNLOCK)
                self.save_file_thread_object.done_signal.connect(self.post_save_diff)

                # thread start
                self.save_file_thread_object.start()

    def post_save_diff(self):
        """

        :return:
        """
        self.close()