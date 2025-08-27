# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDialogButtonBox)
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.substation import Substation


class NewMapLineDialogue(QDialog):
    """
    NewMapLineDialogue
    """
    def __init__(self, grid: MultiCircuit, se_from: Substation, se_to: Substation, parent=None):
        """
        Constructor
        :param grid: MultiCircuit
        :param se_from: Substation
        :param se_to: Substation
        :param parent: ?
        """
        QDialog.__init__(self, parent)
        self.setWindowTitle("New line")

        # Create layout
        main_layout = QVBoxLayout()

        # Create horizontal layout for labels and combo-boxes
        combo_layout = QHBoxLayout()

        self.buses_from = grid.get_substation_buses(substation=se_from)
        self.buses_to = grid.get_substation_buses(substation=se_to)
        self._is_valid = len(self.buses_from) > 0 and len(self.buses_to) > 0

        # Create labels and combo-boxes
        label1 = QLabel(se_from.name)
        self.combo_box_from = QComboBox()
        self.combo_box_from.addItems([bus.name for bus in self.buses_from])
        if len(self.buses_from) > 0:
            self.combo_box_from.setCurrentIndex(0)

        label2 = QLabel(se_to.name)
        self.combo_box_to = QComboBox()
        self.combo_box_to.addItems([bus.name for bus in self.buses_to])
        if len(self.buses_to) > 0:
            self.combo_box_to.setCurrentIndex(0)

        # Create vertical layout for first label and combobox
        vbox1 = QVBoxLayout()
        vbox1.addWidget(label1)
        vbox1.addWidget(self.combo_box_from)

        # Create vertical layout for second label and combobox
        vbox2 = QVBoxLayout()
        vbox2.addWidget(label2)
        vbox2.addWidget(self.combo_box_to)

        # Add vertical layouts to horizontal layout
        combo_layout.addLayout(vbox1)
        combo_layout.addLayout(vbox2)

        # Add horizontal layout to main layout
        main_layout.addLayout(combo_layout)

        # Create and add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # Align the button box to the bottom-right
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(button_box)

        # Add button layout to main layout
        main_layout.addLayout(button_layout)

        # Set main layout
        self.setLayout(main_layout)

    def is_valid(self):
        """

        :return: 
        """
        return self._is_valid

    def bus_from(self):
        """

        :return:
        """
        idx = self.combo_box_from.currentIndex()
        if idx > -1:
            return self.buses_from[idx]
        else:
            return None

    def bus_to(self):
        """

        :return:
        """
        idx = self.combo_box_to.currentIndex()
        if idx > -1:
            return self.buses_to[idx]
        else:
            return None

    def accept(self):
        """
        accept
        """
        super().accept()

    def reject(self):
        """
        reject
        """
        self._is_valid = False
        super().reject()
