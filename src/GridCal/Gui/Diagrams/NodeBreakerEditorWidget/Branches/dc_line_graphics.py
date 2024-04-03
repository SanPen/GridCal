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
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QLabel, QDoubleSpinBox, QPushButton, QVBoxLayout, QComboBox, QDialog, QGraphicsScene
from GridCal.Gui.GuiFunctions import get_list_model
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Substation.bus_graphics import TerminalItem
from GridCalEngine.Devices.Branches.line import SequenceLineType, OverheadLineType, UndergroundLineType
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.enumerations import DeviceType
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Branches.line_graphics_template import LineGraphicTemplateItem

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.node_breaker_editor_widget import NodeBreakerEditorWidget


class DcLineEditor(QDialog):
    """
    DcLineEditor
    """
    def __init__(self, branch: DcLine, Sbase=100, templates=None, current_template=None):
        """
        Line Editor constructor
        :param branch: Branch object to update
        :param Sbase: Base power in MVA
        """
        super(DcLineEditor, self).__init__()

        # keep pointer to the line object
        self.branch = branch

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
        Vf = self.branch.bus_from.Vnom
        Vt = self.branch.bus_to.Vnom

        Zbase = self.Sbase / (Vf * Vf)
        Ybase = 1 / Zbase

        R = self.branch.R * Zbase
        # X = self.branch.X * Zbase
        # B = self.branch.B * Ybase

        I = self.branch.rate / Vf  # current in kA

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

                        if isinstance(self.current_template, UndergroundLineType):
                            I = self.current_template.Imax
                            R = self.current_template.R

                        elif isinstance(self.current_template, OverheadLineType):
                            I = self.current_template.Imax
                            R = self.current_template.R1

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
        self.l_spinner.setValue(1)

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

        # self.layout.addWidget(QLabel("X: Inductance [Ohm/Km]"))
        # self.layout.addWidget(self.x_spinner)

        # self.layout.addWidget(QLabel("G: Conductance [S/Km]"))
        # self.layout.addWidget(self.g_spinner)

        # self.layout.addWidget(QLabel("B: Susceptance [S/Km]"))
        # self.layout.addWidget(self.b_spinner)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('Line editor')

    def accept_click(self):
        """
        Set the values
        :return:
        """
        l = self.l_spinner.value()
        I = self.i_spinner.value()
        R = self.r_spinner.value() * l

        Vf = self.branch.bus_from.Vnom
        Vt = self.branch.bus_to.Vnom

        Sn = np.round(I * Vf, 2)  # nominal power in MVA = kA * kV

        Zbase = self.Sbase / (Vf * Vf)
        Ybase = 1.0 / Zbase

        self.branch.R = np.round(R / Zbase, 6)
        self.branch.rate = Sn

        if self.selected_template is not None:
            self.branch.template = self.selected_template

        self.accept()

    def load_template(self, template):
        """

        :param template:
        :return:
        """
        if isinstance(template, SequenceLineType):
            self.i_spinner.setValue(template.Imax)
            self.r_spinner.setValue(template.R)

            self.selected_template = template

        elif isinstance(template, UndergroundLineType):
            self.i_spinner.setValue(template.Imax)
            self.r_spinner.setValue(template.R)

            self.selected_template = template

        elif isinstance(template, OverheadLineType):
            self.i_spinner.setValue(template.Imax)
            self.r_spinner.setValue(template.R1)

            self.selected_template = template

    def load_template_btn_click(self):
        """
        Accept template values
        """

        if self.templates is not None:

            idx = self.catalogue_combo.currentIndex()
            template = self.templates[idx]

            self.load_template(template)


class DcLineGraphicItem(LineGraphicTemplateItem):

    def __init__(self, fromPort: TerminalItem, toPort: TerminalItem,
                 editor: NodeBreakerEditorWidget,
                 width=5, api_object: DcLine = None):
        """

        :param fromPort:
        :param toPort:
        :param editor:
        :param width:
        :param api_object:
        """
        LineGraphicTemplateItem.__init__(self=self,
                                         fromPort=fromPort,
                                         toPort=toPort,
                                         editor=editor,
                                         width=width,
                                         api_object=api_object)

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("Line")

            pe = menu.addAction('Active')
            pe.setCheckable(True)
            pe.setChecked(self.api_object.active)
            pe.triggered.connect(self.enable_disable_toggle)

            ra3 = menu.addAction('Editor')
            edit_icon = QIcon()
            edit_icon.addPixmap(QPixmap(":/Icons/icons/edit.svg"))
            ra3.setIcon(edit_icon)
            ra3.triggered.connect(self.edit)

            rabf = menu.addAction('Change bus')
            move_bus_icon = QIcon()
            move_bus_icon.addPixmap(QPixmap(":/Icons/icons/move_bus.svg"))
            rabf.setIcon(move_bus_icon)
            rabf.triggered.connect(self.change_bus)

            menu.addSeparator()

            ra6 = menu.addAction('Plot profiles')
            plot_icon = QIcon()
            plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
            ra6.setIcon(plot_icon)
            ra6.triggered.connect(self.plot_profiles)

            ra4 = menu.addAction('Assign rate to profile')
            ra4_icon = QIcon()
            ra4_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra4.setIcon(ra4_icon)
            ra4.triggered.connect(self.assign_rate_to_profile)

            ra5 = menu.addAction('Assign active state to profile')
            ra5_icon = QIcon()
            ra5_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra5.setIcon(ra5_icon)
            ra5.triggered.connect(self.assign_status_to_profile)

            # menu.addSeparator()

            re = menu.addAction('Reduce')
            re_icon = QIcon()
            re_icon.addPixmap(QPixmap(":/Icons/icons/grid_reduction.svg"))
            re.setIcon(re_icon)
            re.triggered.connect(self.reduce)

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

            menu.exec_(event.screenPos())
        else:
            pass

    def mouseDoubleClickEvent(self, event):
        """
        On double click, edit
        :param event:
        :return:
        """
        if self.api_object is not None:
            if self.api_object.device_type in [DeviceType.Transformer2WDevice, DeviceType.LineDevice]:
                # trigger the editor
                self.edit()
            elif self.api_object.device_type is DeviceType.SwitchDevice:
                # change state
                self.enable_disable_toggle()

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase
        templates = self.editor.circuit.underground_cable_types + self.editor.circuit.overhead_line_types
        current_template = self.api_object.template
        dlg = DcLineEditor(self.api_object, Sbase, templates, current_template)
        if dlg.exec_():
            pass

    def add_to_templates(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase

        dlg = DcLineEditor(self.api_object, Sbase)
        if dlg.exec_():
            pass


