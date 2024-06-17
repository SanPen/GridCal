# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QDialog, QLabel, QComboBox

from GridCal.Gui.GuiFunctions import create_spinbox, create_int_spinbox, get_list_model
from GridCalEngine.Devices.Branches.tap_changer import TapChanger, TapChangerTypes


class TransformerTapsEditor(QDialog):
    """
    TransformerTapsEditor
    """

    def __init__(self, api_object: TapChanger):
        QDialog.__init__(self)

        self.api_object: TapChanger = api_object

        self.layout = QVBoxLayout(self)

        self.asymmetry_angle_spinner = create_spinbox(value=self.api_object.asymmetry_angle,
                                                      minimum=0, maximum=999999, decimals=6)

        self.total_positions_spinner = create_int_spinbox(value=self.api_object.total_positions,
                                                          minimum=0, maximum=999999)

        self.dV_spinner = create_spinbox(value=self.api_object.dV,
                                         minimum=0, maximum=999999, decimals=6)

        self.neutral_position_spinner = create_int_spinbox(value=self.api_object.neutral_position,
                                                           minimum=0, maximum=999999)

        self.tap_position_spinner = create_int_spinbox(value=self.api_object.tap_position,
                                                       minimum=0, maximum=999999)

        self.tap_changer_types = QComboBox()
        self.tap_changer_types_dict = {
            TapChangerTypes.NoRegulation.value: TapChangerTypes.NoRegulation,
            TapChangerTypes.Symmetrical.value: TapChangerTypes.Symmetrical,
            TapChangerTypes.Asymmetrical.value: TapChangerTypes.Asymmetrical,
            TapChangerTypes.VoltageRegulation.value: TapChangerTypes.VoltageRegulation,
        }
        lst = list(self.tap_changer_types_dict.keys())
        self.tap_changer_types.setModel(get_list_model(lst))
        self.tap_changer_types.setCurrentIndex(lst.index(self.api_object.tc_type.value))

        self.layout.addWidget(QLabel("Tap changer type"))
        self.layout.addWidget(self.tap_changer_types)

        self.layout.addWidget(QLabel("Asymetry angle (deg)"))
        self.layout.addWidget(self.asymmetry_angle_spinner)

        self.layout.addWidget(QLabel("Total positions"))
        self.layout.addWidget(self.total_positions_spinner)

        self.layout.addWidget(QLabel("Neutral position"))
        self.layout.addWidget(self.neutral_position_spinner)

        self.layout.addWidget(QLabel("Tap position"))
        self.layout.addWidget(self.tap_position_spinner)

        self.layout.addWidget(QLabel("Voltage increment per position"))
        self.layout.addWidget(self.dV_spinner)

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)
        self.layout.addWidget(self.accept_btn)

    def accept_click(self):
        """
        Accept
        """

        self.api_object.asymmetry_angle = self.asymmetry_angle_spinner.value()
        self.api_object.total_positions = self.total_positions_spinner.value()
        self.api_object.tap_position = self.tap_position_spinner.value()
        self.api_object.dV = self.dV_spinner.value()
        self.api_object.neutral_position = self.neutral_position_spinner.value()

        self.api_object.tc_type = self.tap_changer_types_dict[self.tap_changer_types.currentText()]

        self.api_object.recalc()

        self.close()
