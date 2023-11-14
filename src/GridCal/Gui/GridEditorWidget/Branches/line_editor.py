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

from typing import Union, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QDialog, QLabel, QDoubleSpinBox, QComboBox
from GridCal.Gui.GuiFunctions import get_list_model
from GridCalEngine.Core.Devices.Branches.line import Line, SequenceLineType, OverheadLineType, UndergroundLineType


class LineEditor(QDialog):
    """
    LineEditor
    """

    def __init__(self, line: Line,
                 Sbase=100,
                 templates: Union[List[Union[SequenceLineType, OverheadLineType, UndergroundLineType]], None] = None,
                 current_template=None):
        """
        Line Editor constructor
        :param line: Branch object to update
        :param templates: List of templates
        :param Sbase: Base power in MVA
        """
        super(LineEditor, self).__init__()

        # keep pointer to the line object
        self.line = line

        self.Sbase = Sbase

        self.templates = templates

        self.current_template = current_template

        self.selected_template = None

        self.setObjectName("self")

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.layout = QVBoxLayout(self)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------

        Vf = self.line.bus_from.Vnom
        Vt = self.line.bus_to.Vnom

        Zbase = (Vf * Vf) / self.Sbase
        Ybase = 1 / Zbase
        length = self.line.length

        if length == 0:
            length = 1.0

        R = self.line.R * Zbase / length
        X = self.line.X * Zbase / length
        B = self.line.B * Ybase / length
        I = np.round(self.line.rate / (Vf * 1.73205080757), 6)  # current in kA

        # ------------------------------------------------------------------------------------------

        # catalogue
        self.catalogue_combo = QComboBox()
        if self.templates is not None:
            if len(self.templates) > 0:
                self.catalogue_combo.setModel(get_list_model(self.templates))

                if self.current_template is not None:
                    try:
                        idx = self.templates.index(self.current_template)
                        self.catalogue_combo.setCurrentIndex(idx)

                        if isinstance(self.current_template, SequenceLineType):
                            I = self.current_template.Imax
                            R = self.current_template.R
                            X = self.current_template.X
                            B = self.current_template.B

                        if isinstance(self.current_template, UndergroundLineType):
                            I = self.current_template.Imax
                            R = self.current_template.R
                            X = self.current_template.X
                            B = self.current_template.B

                        elif isinstance(self.current_template, OverheadLineType):
                            I = self.current_template.Imax
                            R = self.current_template.R1
                            X = self.current_template.X1
                            B = self.current_template.Bsh1

                    except:
                        pass

        # load template
        self.load_template_btn = QPushButton()
        self.load_template_btn.setText('Load template values')
        self.load_template_btn.clicked.connect(self.load_template_btn_click)

        # line length
        self.l_spinner = QDoubleSpinBox()
        self.l_spinner.setMinimum(0)
        self.l_spinner.setMaximum(9999999)
        self.l_spinner.setDecimals(6)
        self.l_spinner.setValue(length)

        # Max current
        self.i_spinner = QDoubleSpinBox()
        self.i_spinner.setMinimum(0)
        self.i_spinner.setMaximum(9999999)
        self.i_spinner.setDecimals(2)
        self.i_spinner.setValue(I)

        # R
        self.r_spinner = QDoubleSpinBox()
        self.r_spinner.setMinimum(0)
        self.r_spinner.setMaximum(9999999)
        self.r_spinner.setDecimals(6)
        self.r_spinner.setValue(R)

        # X
        self.x_spinner = QDoubleSpinBox()
        self.x_spinner.setMinimum(0)
        self.x_spinner.setMaximum(9999999)
        self.x_spinner.setDecimals(6)
        self.x_spinner.setValue(X)

        # B
        self.b_spinner = QDoubleSpinBox()
        self.b_spinner.setMinimum(0)
        self.b_spinner.setMaximum(9999999)
        self.b_spinner.setDecimals(6)
        self.b_spinner.setValue(B)

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        if templates is not None:
            self.layout.addWidget(QLabel("Available templates"))
            self.layout.addWidget(self.catalogue_combo)
            self.layout.addWidget(self.load_template_btn)
            self.layout.addWidget(QLabel(""))

        self.layout.addWidget(QLabel("L: Line length [Km]"))
        self.layout.addWidget(self.l_spinner)

        self.layout.addWidget(QLabel("Imax: Max. current [KA] @" + str(int(Vf)) + " [KV]"))
        self.layout.addWidget(self.i_spinner)

        self.layout.addWidget(QLabel("R: Resistance [Ohm/Km]"))
        self.layout.addWidget(self.r_spinner)

        self.layout.addWidget(QLabel("X: Inductance [Ohm/Km]"))
        self.layout.addWidget(self.x_spinner)

        self.layout.addWidget(QLabel("B: Susceptance [uS/Km]"))
        self.layout.addWidget(self.b_spinner)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('Line editor')

    def accept_click(self):
        """
        Set the values
        :return:
        """

        if self.selected_template is not None:
            self.line.apply_template(self.selected_template, Sbase=self.Sbase)
        else:
            length = self.l_spinner.value()
            I = self.i_spinner.value()
            R = self.r_spinner.value() * length
            X = self.x_spinner.value() * length
            B = self.b_spinner.value() * length

            Vf = self.line.get_max_bus_nominal_voltage()

            Zbase = (Vf * Vf) / self.Sbase
            Ybase = 1.0 / Zbase

            self.line.R = np.round(R / Zbase, 6)
            self.line.X = np.round(X / Zbase, 6)
            self.line.B = np.round(B / Ybase, 6)
            self.line.rate = np.round(I * Vf * 1.73205080757, 6)  # nominal power in MVA = kA * kV * sqrt(3)
            self.line.length = length

        self.accept()

    def load_template(self, template):
        """

        :param template:
        :return:
        """
        if isinstance(template, SequenceLineType):
            self.i_spinner.setValue(template.Imax)
            self.r_spinner.setValue(template.R)
            self.x_spinner.setValue(template.X)
            self.b_spinner.setValue(template.B)

            self.selected_template = template

        elif isinstance(template, UndergroundLineType):
            self.i_spinner.setValue(template.Imax)
            self.r_spinner.setValue(template.R)
            self.x_spinner.setValue(template.X)
            self.b_spinner.setValue(template.B)

            self.selected_template = template

        elif isinstance(template, OverheadLineType):
            self.i_spinner.setValue(template.Imax)
            self.r_spinner.setValue(template.R1)
            self.x_spinner.setValue(template.X1)
            self.b_spinner.setValue(template.Bsh1)

            self.selected_template = template

    def load_template_btn_click(self):
        """
        Accept template values
        """

        if self.templates is not None:
            idx = self.catalogue_combo.currentIndex()

            if idx > -1:
                self.load_template(template=self.templates[idx])
