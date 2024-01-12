# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import numpy as np
from typing import List, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QDialog, QLabel, QDoubleSpinBox, QComboBox
from GridCal.Gui.GuiFunctions import get_list_model
from GridCalEngine.Core.Devices.Branches.transformer import Transformer2W, TransformerType


def reverse_transformer_short_circuit_study(transformer_obj: Transformer2W,
                                            Sbase: float) -> Tuple[float, float, float, float, float]:
    """
    Get the short circuit study values from the impedance values
    :param transformer_obj: Transformer2W
    :param Sbase: base power in MVA (100 MVA)
    :return: Pfe, Pcu, Vsc, I0, Sn
    """

    # Change the impedances to the system base
    base_change = Sbase / (transformer_obj.rate + 1e-9)

    R = transformer_obj.R / base_change
    X = transformer_obj.X / base_change
    G = transformer_obj.G / base_change
    B = transformer_obj.B / base_change
    Sn = transformer_obj.rate

    zsc = np.sqrt(R * R + X * X)
    Vsc = 100.0 * zsc
    Pcu = R * Sn * 1000.0

    if abs(G) > 0.0 and abs(B) > 0.0:
        zl = 1.0 / complex(G, B)
        rfe = zl.real
        xm = zl.imag

        Pfe = 1000.0 * Sn / rfe

        k = 1 / (rfe * rfe) + 1 / (xm * xm)
        I0 = 100.0 * np.sqrt(k)
    else:
        Pfe = 0
        I0 = 0

    return Pfe, Pcu, Vsc, I0, Sn


class TransformerEditor(QDialog):
    """
    TransformerEditor
    """

    def __init__(self, branch: Transformer2W, Sbase=100, modify_on_accept=True, templates=None, current_template=None):
        """
        Transformer
        :param branch:
        :param Sbase:
        """
        super(TransformerEditor, self).__init__()

        # keep pointer to the line object
        self.transformer_obj = branch

        self.Sbase = Sbase

        self.modify_on_accept = modify_on_accept

        self.templates = self.filter_valid_templates(templates)

        self.current_template = current_template

        self.selected_template = None

        self.setObjectName("self")

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.layout = QVBoxLayout(self)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------
        self.Vf = self.transformer_obj.bus_from.Vnom
        self.Vt = self.transformer_obj.bus_to.Vnom

        Pfe, Pcu, Vsc, I0, Sn = reverse_transformer_short_circuit_study(transformer_obj=self.transformer_obj,
                                                                        Sbase=Sbase)

        # ------------------------------------------------------------------------------------------

        # catalogue
        self.catalogue_combo = QComboBox()
        if templates is not None:
            if len(self.templates) > 0:

                self.catalogue_combo.setModel(get_list_model(self.templates))

                if self.current_template is not None:
                    idx = self.templates.index(self.current_template)
                    if idx > -1:
                        self.catalogue_combo.setCurrentIndex(idx)

                        # set the template parameters
                        Sn = self.current_template.Sn  # MVA
                        Pcu = self.current_template.Pcu  # kW
                        Pfe = self.current_template.Pfe  # kW
                        I0 = self.current_template.I0  # %
                        Vsc = self.current_template.Vsc  # %

        # load template
        self.load_template_btn = QPushButton()
        self.load_template_btn.setText('Load template values')
        self.load_template_btn.clicked.connect(self.load_template_btn_click)

        # Sn
        self.sn_spinner = QDoubleSpinBox()
        self.sn_spinner.setMinimum(0)
        self.sn_spinner.setMaximum(9999999)
        self.sn_spinner.setDecimals(6)
        self.sn_spinner.setValue(Sn)

        # Pcu
        self.pcu_spinner = QDoubleSpinBox()
        self.pcu_spinner.setMinimum(0)
        self.pcu_spinner.setMaximum(9999999)
        self.pcu_spinner.setDecimals(6)
        self.pcu_spinner.setValue(Pcu)

        # Pfe
        self.pfe_spinner = QDoubleSpinBox()
        self.pfe_spinner.setMinimum(0)
        self.pfe_spinner.setMaximum(9999999)
        self.pfe_spinner.setDecimals(6)
        self.pfe_spinner.setValue(Pfe)

        # I0
        self.I0_spinner = QDoubleSpinBox()
        self.I0_spinner.setMinimum(0)
        self.I0_spinner.setMaximum(9999999)
        self.I0_spinner.setDecimals(6)
        self.I0_spinner.setValue(I0)

        # Vsc
        self.vsc_spinner = QDoubleSpinBox()
        self.vsc_spinner.setMinimum(0)
        self.vsc_spinner.setMaximum(9999999)
        self.vsc_spinner.setDecimals(6)
        self.vsc_spinner.setValue(Vsc)

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # labels

        # add all to the GUI

        # add all to the GUI
        if templates is not None:
            self.layout.addWidget(QLabel("Suitable templates"))
            self.layout.addWidget(self.catalogue_combo)
            self.layout.addWidget(self.load_template_btn)
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

        # self.layout.addWidget(self.system_base_chk)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('Transformer editor')

    def filter_valid_templates(self, templates: List[TransformerType]):
        """
        Filter templates
        :param templates:
        :return:
        """
        if templates is None:
            return None

        lst = list()

        Vf = self.transformer_obj.bus_from.Vnom
        Vt = self.transformer_obj.bus_to.Vnom

        for tpe in templates:

            HV2 = tpe.HV * 1.01
            HV1 = tpe.HV * 0.99

            LV2 = tpe.LV * 1.01
            LV1 = tpe.LV * 0.99

            # check that the voltages are within a 1% tolerance
            if (HV1 < Vf < HV2) or (LV1 < Vf < LV2):
                if (HV1 < Vt < HV2) or (LV1 < Vt < LV2):
                    lst.append(tpe)

        return lst

    def get_template(self):
        """
        Fabricate template values from the branch values
        :return: TransformerType instance
        """
        eps = 1e-20
        Vf = self.transformer_obj.bus_from.Vnom  # kV
        Vt = self.transformer_obj.bus_to.Vnom  # kV
        Sn = self.sn_spinner.value() + eps  # MVA
        Pcu = self.pcu_spinner.value() + eps  # kW
        Pfe = self.pfe_spinner.value() + eps  # kW
        I0 = self.I0_spinner.value() + eps  # %
        Vsc = self.vsc_spinner.value()  # %

        Pfe = eps if Pfe == 0.0 else Pfe
        I0 = eps if I0 == 0.0 else I0

        tpe = TransformerType(hv_nominal_voltage=Vf,
                              lv_nominal_voltage=Vt,
                              nominal_power=Sn,
                              copper_losses=Pcu,
                              iron_losses=Pfe,
                              no_load_current=I0,
                              short_circuit_voltage=Vsc,
                              gr_hv1=0.5,
                              gx_hv1=0.5)

        return tpe

    def accept_click(self):
        """
        Create transformer type and get the impedances
        :return:
        """

        if self.modify_on_accept:

            if self.selected_template is None:
                # no selected template, but a new one was generated
                tpe = self.get_template()
            else:
                # pick the last selected template
                tpe = self.selected_template

            self.transformer_obj.apply_template(tpe, Sbase=self.Sbase)

        self.accept()

    def load_template(self, template: TransformerType):
        """

        :param template:
        :return:
        """
        self.sn_spinner.setValue(template.Sn)  # MVA
        self.pcu_spinner.setValue(template.Pcu)  # kW
        self.pfe_spinner.setValue(template.Pfe)  # kW
        self.I0_spinner.setValue(template.I0)  # %
        self.vsc_spinner.setValue(template.Vsc)  # %

        self.selected_template = template

    def load_template_btn_click(self):
        """
        Accept template values
        """

        if self.templates is not None:

            idx = self.catalogue_combo.currentIndex()
            template = self.templates[idx]

            if isinstance(template, TransformerType):
                self.load_template(template)
