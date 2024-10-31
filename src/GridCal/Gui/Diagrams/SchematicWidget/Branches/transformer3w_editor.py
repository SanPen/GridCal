# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QDialog, QLabel, QFrame
from GridCal.Gui.gui_functions import create_spinbox
from GridCal.ThirdParty.qdarktheme.qtpy.QtWidgets import QApplication
from GridCalEngine.Devices.Branches.transformer3w import Transformer3W
from GridCalEngine.Devices.Substation.bus import Bus


class WindingWidget(QFrame):
    """
    Widget to package the winding editor logic
    """

    def __init__(self, i: int, V: float, Sn: float, Pcu: float, Vsc: float, bus_to: Bus, Sbase: float):
        """

        :param i:
        :param V:
        :param Sn:
        :param Pcu:
        :param Vsc:
        :param bus_to:
        :param Sbase:
        """
        QFrame.__init__(self)

        self.i = i

        self.Sbase = Sbase

        self.layout = QVBoxLayout(self)

        # Vn
        self.vn_spinner = create_spinbox(value=V, minimum=0, maximum=999999, decimals=6)

        # Sn
        self.sn_spinner = create_spinbox(value=Sn, minimum=0, maximum=999999, decimals=6)

        # Pcu
        self.pcu_spinner = create_spinbox(value=Pcu, minimum=0, maximum=999999, decimals=6)

        # Vsc
        self.vsc_spinner = create_spinbox(value=Vsc, minimum=0, maximum=999999, decimals=6)

        # add all to the GUI
        self.layout.addWidget(QLabel(f"Winding {self.i}"))

        v_str = f"{bus_to.Vnom} KV" if bus_to is not None else 'Not connected'
        self.layout.addWidget(QLabel(f"Bus voltage: {v_str}"))

        if i == 1:
            wstr = "1-2"
        elif i == 2:
            wstr = "2-3"
        elif i == 3:
            wstr = "3-1"
        else:
            wstr = ""

        # spacer
        self.layout.addWidget(QLabel(""))

        self.layout.addWidget(QLabel(f"V{i}: Nominal voltage [KV]"))
        self.layout.addWidget(self.vn_spinner)

        self.layout.addWidget(QLabel(f"Sn{i}: Nominal power [MVA]"))
        self.layout.addWidget(self.sn_spinner)

        self.layout.addWidget(QLabel(f"Pcu {wstr}: Copper losses [kW]"))
        self.layout.addWidget(self.pcu_spinner)

        self.layout.addWidget(QLabel(f"Vsc {wstr}: Short circuit voltage [%]"))
        self.layout.addWidget(self.vsc_spinner)


class Transformer3WEditor(QDialog):
    """
    TransformerEditor
    """

    def __init__(self, tr3: Transformer3W, Sbase: float = 100.0, modify_on_accept=True):
        """
        Transformer
        :param tr3:
        :param Sbase:
        """
        super(Transformer3WEditor, self).__init__()

        # keep pointer to the line object
        self.transformer_obj = tr3

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
        self.w1 = WindingWidget(1, V=tr3.V1, Sn=tr3.rate1, Pcu=tr3.Pcu12, Vsc=tr3.Vsc12,
                                bus_to=tr3.bus1, Sbase=self.Sbase)

        self.w2 = WindingWidget(2, V=tr3.V2, Sn=tr3.rate2, Pcu=tr3.Pcu23, Vsc=tr3.Vsc23,
                                bus_to=tr3.bus2, Sbase=self.Sbase)

        self.w3 = WindingWidget(3, V=tr3.V3, Sn=tr3.rate3, Pcu=tr3.Pcu31, Vsc=tr3.Vsc31,
                                bus_to=tr3.bus3, Sbase=self.Sbase)

        self.h_layout.addWidget(self.w1)
        self.h_layout.addWidget(self.w2)
        self.h_layout.addWidget(self.w3)

        # Pfe
        self.pfe_spinner = create_spinbox(value=0.0, minimum=0, maximum=999999, decimals=6)

        # I0
        self.I0_spinner = create_spinbox(value=0.0, minimum=0, maximum=999999, decimals=6)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        self.layout.addWidget(QLabel(f"Name: {tr3.name}"))
        self.layout.addWidget(QLabel(f""))

        self.layout.addWidget(QLabel("Pfe: Iron losses [kW]"))
        self.layout.addWidget(self.pfe_spinner)

        self.layout.addWidget(QLabel("I0: No load current [%]"))
        self.layout.addWidget(self.I0_spinner)

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
            self.transformer_obj.fill_from_design_values(V1=self.w1.vn_spinner.value(),
                                                         V2=self.w2.vn_spinner.value(),
                                                         V3=self.w3.vn_spinner.value(),
                                                         Sn1=self.w1.sn_spinner.value(),
                                                         Sn2=self.w2.sn_spinner.value(),
                                                         Sn3=self.w3.sn_spinner.value(),
                                                         Pcu12=self.w1.pcu_spinner.value(),
                                                         Pcu23=self.w2.pcu_spinner.value(),
                                                         Pcu31=self.w3.pcu_spinner.value(),
                                                         Vsc12=self.w1.vsc_spinner.value(),
                                                         Vsc23=self.w2.vsc_spinner.value(),
                                                         Vsc31=self.w3.vsc_spinner.value(),
                                                         Pfe=self.pfe_spinner.value(),
                                                         I0=self.I0_spinner.value(),
                                                         Sbase=self.Sbase)

        self.accept()


if __name__ == '__main__':
    import sys
    from GridCalEngine.Devices.Substation.bus import Bus

    app = QApplication(sys.argv)

    b1 = Bus()
    b2 = Bus()
    b3 = Bus()
    tr3 = Transformer3W(bus1=b1, bus2=b2, bus3=b3)
    editor = Transformer3WEditor(tr3, 100.0)
    editor.exec()
