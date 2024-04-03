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
from GridCal.Gui.GeneralDialogues import InputNumberDialogue
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Substation.bus_graphics import TerminalItem
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Branches.line_editor import LineEditor
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.generic_graphics import ACTIVE
from GridCalEngine.Devices.Fluid.fluid_path import FluidPath
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.node_breaker_editor_widget import NodeBreakerEditorWidget


class FluidPathGraphicItem(LineGraphicTemplateItem):
    """
    LineGraphicItem
    """

    def __init__(self,
                 fromPort: TerminalItem,
                 toPort: Union[TerminalItem, None],
                 editor: NodeBreakerEditorWidget,
                 width=10,
                 api_object: FluidPath = None,
                 arrow_size=15):
        """
        
        :param fromPort:
        :param toPort:
        :param editor:
        :param width:
        :param api_object:
        :param arrow_size:
        """
        LineGraphicTemplateItem.__init__(self,
                                         fromPort=fromPort,
                                         toPort=toPort,
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

            # pe = menu.addAction('Active')
            # pe.setCheckable(True)
            # pe.setChecked(self.api_object.active)
            # pe.triggered.connect(self.enable_disable_toggle)

            # ra3 = menu.addAction('Editor')
            # edit_icon = QIcon()
            # edit_icon.addPixmap(QPixmap(":/Icons/icons/edit.svg"))
            # ra3.setIcon(edit_icon)
            # ra3.triggered.connect(self.edit)

            # rabf = menu.addAction('Change bus')
            # move_bus_icon = QIcon()
            # move_bus_icon.addPixmap(QPixmap(":/Icons/icons/move_bus.svg"))
            # rabf.setIcon(move_bus_icon)
            # rabf.triggered.connect(self.change_bus)

            menu.addSeparator()

            ra6 = menu.addAction('Plot profiles')
            plot_icon = QIcon()
            plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
            ra6.setIcon(plot_icon)
            ra6.triggered.connect(self.plot_profiles)


            #
            # ra5 = menu.addAction('Assign active state to profile')
            # ra5_icon = QIcon()
            # ra5_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            # ra5.setIcon(ra5_icon)
            # ra5.triggered.connect(self.assign_status_to_profile)

            # spl = menu.addAction('Split line')
            # spl_icon = QIcon()
            # spl_icon.addPixmap(QPixmap(":/Icons/icons/divide.svg"))
            # spl.setIcon(spl_icon)
            # spl.triggered.connect(self.split_line)

            # menu.addSeparator()

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

            # menu.addSeparator()

            menu.addSection('Convert to')

            ra4 = menu.addAction('Line')
            ra4_icon = QIcon()
            ra4_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra4.setIcon(ra4_icon)
            ra4.triggered.connect(self.to_line)

            menu.exec_(event.screenPos())
        else:
            pass

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.editor.circuit.has_time_series:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.editor.set_active_status_to_profile(self.api_object, override_question=True)

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

    def show_line_editor(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase

        dlg = LineEditor(self.api_object, Sbase)
        if dlg.exec_():
            pass

    def split_line(self):
        """
        Split line
        :return:
        """
        dlg = InputNumberDialogue(min_value=1.0,
                                  max_value=99.0,
                                  is_int=False,
                                  title="Split fluid path",
                                  text="Enter the distance from the beginning of the \n"
                                       "fluid path as a percentage of the total length",
                                  suffix=' %',
                                  decimals=2,
                                  default_value=50.0)
        if dlg.exec_():

            if dlg.is_accepted:
                br1, br2, middle_bus = self.api_object.split_line(position=dlg.value / 100.0)

                # add the graphical objects
                # TODO: Figure this out
                # middle_bus.graphic_obj = self.diagramScene.parent_.add_api_bus(middle_bus)
                # br1.graphic_obj = self.diagramScene.parent_.add_api_line(br1)
                # br2.graphic_obj = self.diagramScene.parent_.add_api_line(br2)
                # # middle_bus.graphic_obj.redraw()
                # br1.bus_from.graphic_obj.arrange_children()
                # br2.bus_to.graphic_obj.arrange_children()

                # add to gridcal
                self.editor.circuit.add_bus(middle_bus)
                self.editor.circuit.add_line(br1)
                self.editor.circuit.add_line(br2)

                # remove this line
                self.remove(ask=False)

    def to_line(self):
        """
        Convert this object to transformer
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this fluid path into a line?',
                             'Convert fluid path')
        if ok:
            self.editor.convert_fluid_path_to_line(element=self.api_object, item_graphic=self)
