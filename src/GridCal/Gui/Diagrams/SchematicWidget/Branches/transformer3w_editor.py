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

from typing import List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QDialog, QLabel, QComboBox, QFrame
from GridCal.Gui.gui_functions import get_list_model, create_spinbox
from GridCal.ThirdParty.qdarktheme.qtpy.QtWidgets import QApplication
from GridCalEngine.Devices.Branches.transformer3w import Transformer3W
from GridCalEngine.Devices.Branches.winding import Winding
from GridCalEngine.Devices.Branches.transformer_type import TransformerType, reverse_transformer_short_circuit_study


def get_winding_design_values(winding: Winding, Sbase: float):
    """

    :param winding:
    :param Sbase:
    :return:
    """
    Pfe, Pcu, Vsc, I0, Sn = reverse_transformer_short_circuit_study(R=winding.R,
                                                                    X=winding.X,
                                                                    G=winding.G,
                                                                    B=winding.B,
                                                                    rate=winding.rate,
                                                                    Sbase=Sbase)

    return Pfe, Pcu, Vsc, I0, Sn


class WindingWidget(QFrame):
    """
    Widget to package the winding editor logic
    """

    def __init__(self, i: int, winding: Winding, Sbase: float):
        """

        :param i: winding index
        :param winding:
        :param Sbase:
        """
        QFrame.__init__(self)

        self.i = i

        self.winding = winding

        self.Sbase = Sbase

        Pfe, Pcu, Vsc, I0, Sn = get_winding_design_values(winding=winding, Sbase=Sbase)

        self.layout = QVBoxLayout(self)

        # Sn
        self.sn_spinner = create_spinbox(value=Sn, minimum=0, maximum=999999, decimals=6)

        # Pcu
        self.pcu_spinner = create_spinbox(value=Pcu, minimum=0, maximum=999999, decimals=6)

        # Pfe
        self.pfe_spinner = create_spinbox(value=Pfe, minimum=0, maximum=999999, decimals=6)

        # I0
        self.I0_spinner = create_spinbox(value=I0, minimum=0, maximum=999999, decimals=6)

        # Vsc
        self.vsc_spinner = create_spinbox(value=Vsc, minimum=0, maximum=999999, decimals=6)

        # add all to the GUI
        self.layout.addWidget(QLabel(f"Winding {self.i}"))

        v_str = f"{self.winding.bus_to.Vnom} KV" if self.winding.bus_to is not None else 'Not connected'
        self.layout.addWidget(QLabel(f"Bus voltage: {v_str}"))

        # spacer
        self.layout.addWidget(QLabel(""))

        self.layout.addWidget(QLabel("Sn: Nominal power [MVA]"))
        self.layout.addWidget(self.sn_spinner)

        self.layout.addWidget(QLabel("Pcu: Copper losses [kW]"))
        self.layout.addWidget(self.pcu_spinner)

        self.layout.addWidget(QLabel("Pfe: Iron losses [kW]"))
        self.layout.addWidget(self.pfe_spinner)

        self.layout.addWidget(QLabel("I0: No load current [%]"))
        self.layout.addWidget(self.I0_spinner)

        self.layout.addWidget(QLabel("Vsc: Short circuit voltage [%]"))
        self.layout.addWidget(self.vsc_spinner)

    def apply(self):
        """
        Apply this editor to the widget
        :return:
        """
        eps = 1e-20

        # Nominal power
        Sn = self.sn_spinner.value() + eps  # MVA
        Pcu = self.pcu_spinner.value() + eps  # kW
        Pfe = self.pfe_spinner.value() + eps  # kW
        I0 = self.I0_spinner.value() + eps  # %
        Vsc = self.vsc_spinner.value()  # %

        # fill the impedance values from the design values
        self.winding.fill_design_properties(
            Pcu=Pcu,  # kW
            Pfe=Pfe,  # kW
            I0=I0,  # %
            Vsc=Vsc,  # %
            Sbase=self.Sbase
        )

        # set the values for later
        self.winding.Sn = Sn
        self.winding.Pcu = Pcu
        self.winding.Pfe = Pfe
        self.winding.I0 = I0
        self.winding.Vsc = Vsc


class Transformer3WEditor(QDialog):
    """
    TransformerEditor
    """

    def __init__(self, branch: Transformer3W, Sbase: float = 100.0, modify_on_accept=True):
        """
        Transformer
        :param branch:
        :param Sbase:
        """
        super(Transformer3WEditor, self).__init__()

        # keep pointer to the line object
        self.transformer_obj = branch

        self.Sbase = Sbase

        self.modify_on_accept = modify_on_accept

        self.selected_template = None

        self.setObjectName("self")

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        # main vertical layout
        self.layout = QVBoxLayout(self)

        # windings horizontal layout
        self.h_layout = QHBoxLayout(self)
        self.w_frame = QFrame(self)
        self.w_frame.setLayout(self.h_layout)

        # create the windings frames
        self.w1 = WindingWidget(1, self.transformer_obj.winding1, self.Sbase)
        self.w2 = WindingWidget(2, self.transformer_obj.winding2, self.Sbase)
        self.w3 = WindingWidget(3, self.transformer_obj.winding3, self.Sbase)

        self.h_layout.addWidget(self.w1)
        self.h_layout.addWidget(self.w2)
        self.h_layout.addWidget(self.w3)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # compose main layout
        self.layout.addWidget(self.w_frame)
        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('Transformer editor')

    def accept_click(self):
        """
        Create transformer type and get the impedances
        :return:
        """

        if self.modify_on_accept:
            self.w1.apply()
            self.w2.apply()
            self.w3.apply()

        self.accept()


# if __name__ == '__main__':
#     import sys
#     from GridCalEngine.Devices.Substation.bus import Bus
#
#     app = QApplication(sys.argv)
#
#     b1 = Bus()
#     b2 = Bus()
#     b3 = Bus()
#     tr3 = Transformer3W(bus1=b1, bus2=b2, bus3=b3)
#     editor = Transformer3WEditor(tr3, 100.0)
#     editor.exec()
