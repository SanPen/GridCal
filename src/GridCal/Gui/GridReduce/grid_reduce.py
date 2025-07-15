# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Set
from PySide6 import QtWidgets
import numpy as np
from GridCal.Gui.GridReduce.grid_reduce_gui import Ui_ReduceDialog
from GridCal.Gui.general_dialogues import LogsDialogue
from GridCal.Gui.messages import yes_no_question, warning_msg
from GridCal.Gui.gui_functions import get_list_model
from GridCal.Session.session import SimulationSession
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Topology.grid_reduction import ward_reduction
from GridCalEngine.basic_structures import Logger


class GridReduceDialogue(QtWidgets.QDialog):
    """
    GridMergeDialogue
    """

    def __init__(self, grid: MultiCircuit, session: SimulationSession, selected_buses_set: Set[Bus]):
        """

        :param grid:
        :param session:
        """
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_ReduceDialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid reduction')

        self.logger = Logger()
        self.logs_dialogue: LogsDialogue | None = None

        mdl = get_list_model(list(selected_buses_set))
        self.ui.listView.setModel(mdl)

        self._grid: MultiCircuit = grid
        self._session: SimulationSession = session
        self._selected_buses_set: Set[Bus] = selected_buses_set

        self.ui.reduceButton.clicked.connect(self.reduce_grid)

    def reduce_grid(self):
        """
        The elements of the grid will be added with new idtags.
        This is useful in the case you want to compose a new grid from grids that are the same.
        :return:
        """
        if len(self._selected_buses_set):

            # get the previous power flow
            _, pf_res = self._session.power_flow

            if pf_res is None and not self.ui.use_linear_checkBox.isChecked():
                warning_msg("Run a power flow first!", "Grid reduction")
                return

            ok = yes_no_question(
                text="This will delete the selected buses and reintroduce their influence"
                     "using the Ward equivalent. This cannot be undone and it is dangerous if you don't know"
                     "what you are doing \nAre you sure?",
                title="Grid reduction?")

            if ok:
                reduction_bus_indices = np.array([self._grid.buses.index(b) for b in self._selected_buses_set], dtype=int)

                logger = ward_reduction(
                    grid=self._grid,
                    reduction_bus_indices=reduction_bus_indices,
                    pf_res=pf_res,
                    add_power_loads=True,
                    use_linear=self.ui.use_linear_checkBox.isChecked()
                )

                if logger.has_logs():
                    self.logs_dialogue = LogsDialogue(name="Import profiles", logger=logger)
                    self.logs_dialogue.exec()

                # exit
                self.close()
