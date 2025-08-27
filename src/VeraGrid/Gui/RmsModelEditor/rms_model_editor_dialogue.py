# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys
from PySide6 import QtWidgets

from VeraGrid.Gui.gui_functions import get_icon_list_model
from VeraGrid.Gui.RmsModelEditor.rms_model_editor import Ui_MainWindow
from VeraGrid.Gui.RmsModelEditor.block_editor import BlockEditor
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Devices as dev


class RmsModelEditorGUI(QtWidgets.QMainWindow):

    def __init__(self, model: Block, parent=None, ):
        """

        :param parent:
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('RMS Model editor')

        self.model = model

        self._list_mdl = get_icon_list_model(
            lst=[
                ("Index dynamic parameters", ":/Icons/icons/dyn.svg"),
                ("Numeric dynamic parameters", ":/Icons/icons/dyn.svg"),
                ("External dynamic parameters", ":/Icons/icons/dyn.svg"),
                ("State variables", ":/Icons/icons/dyn.svg"),
                ("Algebraic variables", ":/Icons/icons/dyn.svg"),
                ("External state variables", ":/Icons/icons/dyn.svg"),
                ("External algebraic variables", ":/Icons/icons/dyn.svg")
            ]
        )
        self.ui.listView.setModel(self._list_mdl)

        self.editor = BlockEditor()
        self.ui.editorLayout.addWidget(self.editor)

        self.ui.actionCheckModel.triggered.connect(self.extract_dae)

    def extract_dae(self):
        eqs = self.editor.run()

        for eq in eqs:
            print(str(eq))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    md = dev.DynamicModel()
    window = RmsModelEditorGUI(md)
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
