# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Set
from PySide6 import QtWidgets
import numpy as np
from VeraGrid.Gui.GridReduce.grid_reduce_gui import Ui_ReduceDialog
from VeraGrid.Gui.general_dialogues import LogsDialogue
from VeraGrid.Gui.messages import yes_no_question, warning_msg
from VeraGrid.Gui.gui_functions import get_list_model
from VeraGrid.Session.session import SimulationSession
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Topology.GridReduction.di_shi_grid_reduction import di_shi_reduction
from VeraGridEngine.Topology.GridReduction.ptdf_grid_reduction import ptdf_reduction
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import GridReductionMethod


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

        lmdl = get_list_model(list(selected_buses_set))
        self.ui.listView.setModel(lmdl)

        methods = [GridReductionMethod.DiShi, GridReductionMethod.PTDF]
        self.methods_dict = {m.value: m for m in methods}
        cmdl = get_list_model([m.value for m in methods])
        self.ui.methodComboBox.setModel(cmdl)

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

            method: GridReductionMethod = self.methods_dict[self.ui.methodComboBox.currentText()]

            ok = yes_no_question(
                text="This will delete the selected buses and reintroduce their influence"
                     "using the Ward equivalent. This cannot be undone and it is dangerous if you don't know"
                     "what you are doing \nAre you sure?",
                title="Grid reduction?")

            if ok:
                reduction_bus_indices = np.array([self._grid.buses.index(b) for b in self._selected_buses_set],
                                                 dtype=int)

                if method == GridReductionMethod.DiShi:

                    # get the previous power flow
                    _, pf_res = self._session.power_flow

                    if pf_res is None:
                        warning_msg("Run a power flow first! or select another method", "Grid reduction")
                        return

                    grid_reduced, logger = di_shi_reduction(
                        grid=self._grid,
                        reduction_bus_indices=reduction_bus_indices,
                        pf_res=pf_res,
                        add_power_loads=True,
                        use_linear=False
                    )

                elif method == GridReductionMethod.PTDF:
                    # get the previous power flow
                    _, lin_res = self._session.linear_power_flow

                    if lin_res is None:
                        warning_msg("Run a linear analysis first! or select another method", "Grid reduction")
                        return

                    logger = ptdf_reduction(
                        grid=self._grid,
                        reduction_bus_indices=reduction_bus_indices,
                        PTDF=lin_res.PTDF
                    )
                else:
                    raise NotImplementedError("Reduction method not supported")

                if logger.has_logs():
                    self.logs_dialogue = LogsDialogue(name="Import profiles", logger=logger)
                    self.logs_dialogue.exec()
            else:
                pass  # not ok
        else:
            warning_msg("No reduction happened", "Grid reduction")

        # exit
        self.close()
