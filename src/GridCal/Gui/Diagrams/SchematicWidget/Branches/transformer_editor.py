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
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QDialog, QLabel, QComboBox
from GridCal.Gui.GuiFunctions import get_list_model, create_spinbox
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Branches.transformer_type import TransformerType, reverse_transformer_short_circuit_study


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

        Pfe, Pcu, Vsc, I0, Sn = reverse_transformer_short_circuit_study(R=self.transformer_obj.R,
                                                                        X=self.transformer_obj.X,
                                                                        G=self.transformer_obj.G,
                                                                        B=self.transformer_obj.B,
                                                                        rate=self.transformer_obj.rate,
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
        self.sn_spinner = create_spinbox(value=Sn, minimum=0, maximum=999999, decimals=6)

        # Pcu
        self.pcu_spinner = create_spinbox(value=Pcu, minimum=0, maximum=999999, decimals=6)

        # Pfe
        self.pfe_spinner = create_spinbox(value=Pfe, minimum=0, maximum=999999, decimals=6)

        # I0
        self.I0_spinner = create_spinbox(value=I0, minimum=0, maximum=999999, decimals=6)

        # Vsc
        self.vsc_spinner = create_spinbox(value=Vsc, minimum=0, maximum=999999, decimals=6)

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

    def filter_valid_templates(self, templates: List[TransformerType], pu_range=0.1) -> List[TransformerType]:
        """
        Filter templates
        :param templates: Complete list of templates
        :param pu_range: range in per unit voltage for matching templates
        :return: List[TransformerType]
        """
        if templates is None:
            return list()

        lst = list()

        Vf = self.transformer_obj.bus_from.Vnom
        Vt = self.transformer_obj.bus_to.Vnom
        upper = 1.0 + pu_range
        lower = 1.0 - pu_range

        for tpe in templates:

            HV2 = tpe.HV * upper
            HV1 = tpe.HV * lower

            LV2 = tpe.LV * upper
            LV1 = tpe.LV * lower

            # check that the voltages are within a 1% tolerance
            if (HV1 < Vf < HV2) or (LV1 < Vf < LV2):
                if (HV1 < Vt < HV2) or (LV1 < Vt < LV2):
                    lst.append(tpe)

        return lst

    def get_template(self) -> TransformerType:
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

            self.transformer_obj.apply_template(obj=tpe, Sbase=self.Sbase)

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
