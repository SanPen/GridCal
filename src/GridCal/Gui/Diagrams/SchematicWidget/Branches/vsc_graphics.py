# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING, Union
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMenu
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from GridCalEngine.Devices.Branches.vsc import VSC
from GridCalEngine.enumerations import TapModuleControl
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class VscGraphicItem(LineGraphicTemplateItem):
    """
    Graphics item for the VSC converter
    """

    def __init__(self,
                 from_port: Union[BarTerminalItem, RoundTerminalItem],
                 to_port: Union[BarTerminalItem, RoundTerminalItem],
                 editor: SchematicWidget,
                 width=5,
                 api_object: VSC = None,
                 draw_labels: bool = True):
        """

        :param from_port:
        :param to_port:
        :param editor:
        :param width:
        :param api_object:
        """
        LineGraphicTemplateItem.__init__(self=self,
                                         from_port=from_port,
                                         to_port=to_port,
                                         editor=editor,
                                         width=width,
                                         api_object=api_object,
                                         draw_labels=draw_labels)

    @property
    def api_object(self) -> VSC:
        return self._api_object

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()

            pe = menu.addAction('Enable/Disable')
            pe_icon = QIcon()
            if self.api_object.active:
                pe_icon.addPixmap(QPixmap(":/Icons/icons/uncheck_all.svg"))
            else:
                pe_icon.addPixmap(QPixmap(":/Icons/icons/check_all.svg"))
            pe.setIcon(pe_icon)
            pe.triggered.connect(self.enable_disable_toggle)

            add_menu_entry(menu=menu,
                           text="Draw labels",
                           function_ptr=self.enable_disable_label_drawing,
                           checkeable=True,
                           checked_value=self.draw_labels)

            # rabf = menu.addAction('Change bus')
            # move_bus_icon = QIcon()
            # move_bus_icon.addPixmap(QPixmap(":/Icons/icons/move_bus.svg"))
            # rabf.setIcon(move_bus_icon)
            # rabf.triggered.connect(self.change_bus)

            add_menu_entry(menu=menu,
                           text="Change bus",
                           function_ptr=self.change_bus,
                           icon_path=":/Icons/icons/move_bus.svg")

            add_menu_entry(menu=menu,
                           text="Set Control dev 1",
                           function_ptr=self.set_control_dev_1,
                           icon_path=":/Icons/icons/move_bus.svg")

            add_menu_entry(menu=menu,
                           text="Set Control dev 2",
                           function_ptr=self.set_control_dev_2,
                           icon_path=":/Icons/icons/move_bus.svg")

            menu.addSeparator()

            # ra2 = menu.addAction('Delete')
            # del_icon = QIcon()
            # del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            # ra2.setIcon(del_icon)
            # ra2.triggered.connect(self.delete)

            add_menu_entry(menu=menu,
                           text="Delete",
                           function_ptr=self.delete,
                           icon_path=":/Icons/icons/delete3.svg")

            menu.addSeparator()

            add_menu_entry(menu=menu,
                           text="Control V from",
                           function_ptr=self.control_v_from,
                           icon_path=":/Icons/icons/edit.svg")

            add_menu_entry(menu=menu,
                           text="Control V to",
                           function_ptr=self.control_v_to,
                           icon_path=":/Icons/icons/edit.svg")

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

            menu.exec_(event.screenPos())
        else:
            pass

    def mouseDoubleClickEvent(self, event):
        """
        On double click, edit
        :param event:
        :return:
        """

        pass

    def control_v_from(self):
        """

        :return:
        """
        self.api_object.regulation_bus = self.api_object.bus_from
        self.api_object.tap_module_control_mode = TapModuleControl.Vm

    def control_v_to(self):
        """

        :return:
        """
        self.api_object.regulation_bus = self.api_object.bus_to
        self.api_object.tap_module_control_mode = TapModuleControl.Vm

    def set_control_dev_1(self):
        """

        :return:
        """
        self.editor.set_vsc_control_dev(graphic=self, control_idx=1)

    def set_control_dev_2(self):
        """

        :return:
        """
        self.editor.set_vsc_control_dev(graphic=self, control_idx=2)