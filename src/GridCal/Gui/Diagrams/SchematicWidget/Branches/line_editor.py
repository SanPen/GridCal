# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np

from typing import Union, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QDialog, QLabel, QDoubleSpinBox, QComboBox, QCheckBox
from GridCal.Gui.gui_functions import get_list_model
from GridCal.Gui.messages import error_msg
from GridCalEngine.Devices.Branches.line import Line, SequenceLineType, OverheadLineType, UndergroundLineType


class LineEditor(QDialog):
    """
    LineEditor
    """

    def __init__(self,
                 line: Line,
                 Sbase=100,
                 frequency=50,
                 templates: Union[List[SequenceLineType | OverheadLineType | UndergroundLineType], None] = None,
                 current_template: SequenceLineType | OverheadLineType | UndergroundLineType | None = None):
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

        self.frequency = frequency

        self.templates = templates

        self.current_template = current_template

        self.selected_template = None

        self.setObjectName("self")

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.layout = QVBoxLayout(self)

        # ------------------------------------------------------------------------------------------
        # Set the object values
        # ------------------------------------------------------------------------------------------

        Vf = self.line.bus_from.Vnom
        # Vt = self.line.bus_to.Vnom

        if Vf <= 0.0:
            error_msg(f"Vnom in bus {self.line.bus_from} is {Vf}\n"
                      f"That causes an infinite base admittance.\n"
                      f"The process has been aborted.\n"
                      f"Please correct the data and try again.",
                      title="Line editor initialization")
            return

        Zbase = (Vf * Vf) / self.Sbase
        Ybase = 1 / Zbase
        length = self.line.length

        if length == 0:
            length = 1.0

        r_ohm = self.line.R * Zbase / length
        x_ohm = self.line.X * Zbase / length
        b_us = self.line.B * Ybase / length * 1e6
        I_KA = np.round(self.line.rate / (Vf * 1.73205080757), 6)  # current in KA

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
                            I_KA = self.current_template.Imax
                            r_ohm = self.current_template.R
                            x_ohm = self.current_template.X
                            b_us = self.current_template.B

                        if isinstance(self.current_template, UndergroundLineType):
                            I_KA = self.current_template.Imax
                            r_ohm = self.current_template.R
                            x_ohm = self.current_template.X
                            b_us = self.current_template.B

                        elif isinstance(self.current_template, OverheadLineType):
                            R1, X1, Bsh1 = self.current_template.get_sequence_values(circuit_idx=self.line.circuit_idx,
                                                                                     seq=1)
                            I_KA = self.current_template.Imax
                            r_ohm = R1
                            x_ohm = X1
                            b_us = Bsh1

                    except ValueError:
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
        self.l_spinner.setSuffix(' Km')

        # Max current
        self.i_spinner = QDoubleSpinBox()
        self.i_spinner.setMinimum(0)
        self.i_spinner.setMaximum(9999999)
        self.i_spinner.setDecimals(2)
        self.i_spinner.setValue(I_KA)
        self.i_spinner.setSuffix(' KA')

        # R
        self.r_spinner = QDoubleSpinBox()
        self.r_spinner.setMinimum(0)
        self.r_spinner.setMaximum(9999999)
        self.r_spinner.setDecimals(6)
        self.r_spinner.setValue(r_ohm)
        self.r_spinner.setSuffix(' Ω/Km')

        # X
        self.x_spinner = QDoubleSpinBox()
        self.x_spinner.setMinimum(0)
        self.x_spinner.setMaximum(9999999)
        self.x_spinner.setDecimals(6)
        self.x_spinner.setValue(x_ohm)
        self.x_spinner.setSuffix(' Ω/Km')

        # B
        self.b_spinner = QDoubleSpinBox()
        self.b_spinner.setMinimum(0)
        self.b_spinner.setMaximum(9999999)
        self.b_spinner.setDecimals(6)
        self.b_spinner.setValue(b_us)
        self.b_spinner.setSuffix(" uS/Km")

        # apply to profile
        self.apply_to_profile = QCheckBox()
        self.apply_to_profile.setToolTip("Apply the newly computed values like the rating to the profile")
        self.apply_to_profile.setChecked(True)
        self.apply_to_profile.setText("Apply to profiles")

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

        self.layout.addWidget(QLabel("L: Line length"))
        self.layout.addWidget(self.l_spinner)

        self.layout.addWidget(QLabel("Imax: Max. current @" + str(int(Vf)) + " [KV]"))
        self.layout.addWidget(self.i_spinner)

        self.layout.addWidget(QLabel("R: Resistance"))
        self.layout.addWidget(self.r_spinner)

        self.layout.addWidget(QLabel("X: Inductance"))
        self.layout.addWidget(self.x_spinner)

        self.layout.addWidget(QLabel("S: Susceptance"))
        self.layout.addWidget(self.b_spinner)

        self.layout.addWidget(self.apply_to_profile)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('Line editor')

    def accept_click(self) -> None:
        """
        Set the values
        :return:
        """

        length = self.l_spinner.value()

        if length != 0.0:

            if self.selected_template is not None:
                self.line.disable_auto_updates()
                self.line.set_length(val=length)
                self.line.apply_template(obj=self.selected_template, Sbase=self.Sbase, freq=self.frequency)
                self.line.enable_auto_updates()
            else:
                wf = 2 * np.pi * self.frequency
                self.line.fill_design_properties(
                    r_ohm=self.r_spinner.value(),  # ohm / km
                    x_ohm=self.x_spinner.value(),  # ohm / km
                    c_nf=self.b_spinner.value() * 1e3 / wf,  # nF / km
                    length=length,  # km
                    Imax=self.i_spinner.value(),  # KA
                    freq=self.frequency,  # Hz
                    Sbase=self.Sbase,  # MVA
                    apply_to_profile=self.apply_to_profile.isChecked()
                )

            self.accept()
        else:
            error_msg(text="The length cannot be 0!", title="Accept line design values")

    def load_template(self, template: Union[SequenceLineType, OverheadLineType, UndergroundLineType]):
        """
        Load a template in the editor
        :param template: line compatible template
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
            R1, X1, Bsh1 = template.get_sequence_values(circuit_idx=self.line.circuit_idx, seq=1)
            self.i_spinner.setValue(template.Imax)
            self.r_spinner.setValue(R1)
            self.x_spinner.setValue(X1)
            self.b_spinner.setValue(Bsh1)

            self.selected_template = template

    def load_template_btn_click(self):
        """
        Accept template values
        """

        if self.templates is not None:
            idx = self.catalogue_combo.currentIndex()

            if idx > -1:
                self.load_template(template=self.templates[idx])
