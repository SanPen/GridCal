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
from typing import Union, TYPE_CHECKING
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QIcon, QPixmap, QColor
from PySide6.QtWidgets import QMenu
from GridCal.Gui.Diagrams.DiagramEditorWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.generic_graphics import GenericDBWidget, ACTIVE
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from GridCalEngine.Devices.Fluid.fluid_path import FluidPath
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.DiagramEditorWidget.diagram_editor_widget import DiagramEditorWidget


class FluidPathGraphicItem(LineGraphicTemplateItem):
    """
    LineGraphicItem
    """

    def __init__(self,
                 from_port: Union[BarTerminalItem, RoundTerminalItem],
                 to_port: Union[BarTerminalItem, RoundTerminalItem, None],
                 editor: DiagramEditorWidget,
                 width=10,
                 api_object: FluidPath = None,
                 arrow_size=15):
        """
        
        :param from_port:
        :param to_port:
        :param editor:
        :param width:
        :param api_object:
        :param arrow_size:
        """
        GenericDBWidget.__init__(self, parent=None, api_object=api_object, editor=editor, draw_labels=True)
        LineGraphicTemplateItem.__init__(self,
                                         from_port=from_port,
                                         to_port=to_port,
                                         editor=editor,
                                         width=width,
                                         api_object=api_object,
                                         arrow_size=arrow_size)

        # self.style = Qt.CustomDashLine
        self.style = ACTIVE['style']
        self.color = ACTIVE['fluid']
        self.set_colour(color=self.color,
                        w=self.width,
                        style=self.style)

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """

        pen = QPen(color, w, style, Qt.RoundCap, Qt.RoundJoin)
        # pen.setDashPattern([5, 3, 2, 3])

        self.setPen(pen)
        self.arrow_from_1.set_colour(color, w, style)
        self.arrow_from_2.set_colour(color, w, style)
        self.arrow_to_1.set_colour(color, w, style)
        self.arrow_to_2.set_colour(color, w, style)

        if self.symbol is not None:
            self.symbol.set_colour(color, w, style)

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
        # super().recolour_mode()
        self.set_colour(self.color, self.width, self.style)

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

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("FluidPath")

            menu.addSeparator()

            ra6 = menu.addAction('Plot profiles')
            plot_icon = QIcon()
            plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
            ra6.setIcon(plot_icon)
            ra6.triggered.connect(self.plot_profiles)

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

            menu.addSection('Convert to')

            ra4 = menu.addAction('Line')
            ra4_icon = QIcon()
            ra4_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra4.setIcon(ra4_icon)
            ra4.triggered.connect(self.to_line)

            menu.exec_(event.screenPos())
        else:
            pass

    def plot_profiles(self):
        """
        Plot the time series profiles
        @return:
        """
        # get the index of this object
        i = self.editor.circuit.get_fluid_paths().index(self.api_object)
        # self.editor.diagramScene.plot_branch(i, self.api_object)

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        pass

    def to_line(self):
        """
        Convert this object to transformer
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this fluid path into a line?',
                             'Convert fluid path')
        if ok:
            self.editor.convert_fluid_path_to_line(element=self.api_object, item_graphic=self)
