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
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMenu
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Substation.bus_graphics import TerminalItem
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Branches.line_graphics_template import LineGraphicTemplateItem

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.node_breaker_editor_widget import NodeBreakerEditorWidget


class HvdcGraphicItem(LineGraphicTemplateItem):

    def __init__(self, fromPort: TerminalItem, toPort: TerminalItem,
                 editor: NodeBreakerEditorWidget, width=5,
                 api_object: HvdcLine = None):
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
            menu.addSection("HVDC line")

            pe = menu.addAction('Active')
            pe.setCheckable(True)
            pe.setChecked(self.api_object.active)
            pe.triggered.connect(self.enable_disable_toggle)

            # pe2 = menu.addAction('Convert to Multi-terminal')
            # pe2.triggered.connect(self.convert_to_multi_terminal)

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

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

            menu.exec_(event.screenPos())
        else:
            pass

    def convert_to_multi_terminal(self):
        """

        """
        pass

    def plot_profiles(self):
        """
        Plot the time series profiles
        @return:
        """
        # get the index of this object
        i = self.editor.circuit.get_hvdc().index(self.api_object)
        self.editor.plot_hvdc_branch(i, self.api_object)
