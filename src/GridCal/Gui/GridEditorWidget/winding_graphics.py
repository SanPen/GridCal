

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
from typing import Union
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMenu
from GridCal.Gui.GridEditorWidget.bus_graphics import TerminalItem
from GridCal.Gui.messages import yes_no_question
from GridCalEngine.Core.Devices.Branches.winding import Winding
from GridCal.Gui.GridEditorWidget.line_graphics_template import LineGraphicTemplateItem


class WindingGraphicItem(LineGraphicTemplateItem):

    def __init__(self, fromPort: TerminalItem,
                 toPort: Union[TerminalItem, None],
                 diagramScene,
                 width=5,
                 api_object: Winding = None):
        """

        :param fromPort:
        :param toPort:
        :param diagramScene:
        :param width:
        :param api_object:
        """
        LineGraphicTemplateItem.__init__(self=self,
                                         fromPort=fromPort,
                                         toPort=toPort,
                                         diagramScene=diagramScene,
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

            # menu.addSeparator()

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

    def remove(self, ask=True):
        """
        Remove this object in the diagram and the API
        @return:
        """
        if ask:
            ok = yes_no_question('Do you want to remove this winding?', 'Remove winding')
        else:
            ok = True

        if ok:
            self.diagramScene.circuit.delete_winding(self.api_object)
            self.diagramScene.removeItem(self)

