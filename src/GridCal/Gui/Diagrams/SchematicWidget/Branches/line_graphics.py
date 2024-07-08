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
from typing import TYPE_CHECKING, Union
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QBrush
from PySide6.QtWidgets import QMenu, QGraphicsRectItem, QGraphicsSceneContextMenuEvent
from GridCal.Gui.GuiFunctions import add_menu_entry
from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_editor import LineEditor
from GridCal.Gui.messages import yes_no_question, warning_msg
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from GridCalEngine.Devices.Branches.line import Line, SequenceLineType
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class LineGraphicItem(LineGraphicTemplateItem):
    """
    LineGraphicItem
    """

    def __init__(self,
                 from_port: Union[BarTerminalItem, RoundTerminalItem],
                 to_port: Union[BarTerminalItem, RoundTerminalItem, None],
                 editor: SchematicWidget,
                 width=5,
                 api_object: Line = None,
                 draw_labels: bool = True):
        """

        :param from_port:
        :param to_port:
        :param editor:
        :param width:
        :param api_object:
        :param draw_labels:
        """
        LineGraphicTemplateItem.__init__(self,
                                         from_port=from_port,
                                         to_port=to_port,
                                         editor=editor,
                                         width=width,
                                         api_object=api_object,
                                         draw_labels=draw_labels)

    def remove_symbol(self) -> None:
        """
        Remove all symbols
        """
        for elm in [self.symbol]:
            if elm is not None:
                try:
                    self.editor.remove_from_scene(elm)
                    # sip.delete(elm)
                    elm = None
                except:
                    pass

    def make_switch_symbol(self):
        """
        Mathe the switch symbol
        :return:
        """
        h = 40.0
        w = h
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        self.symbol.setPen(QPen(self.color, self.width, self.style))
        if self.api_object.active:
            self.symbol.setBrush(self.color)
        else:
            self.symbol.setBrush(QBrush(Qt.white))

    def make_reactance_symbol(self):
        """
        Make the reactance symbol
        :return:
        """
        h = 40.0
        w = 2 * h
        self.symbol = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        self.symbol.setPen(QPen(self.color, self.width, self.style))
        self.symbol.setBrush(self.color)

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

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("Line")

            add_menu_entry(menu=menu,
                           text="Active",
                           function_ptr=self.enable_disable_toggle,
                           checkeable=True,
                           checked_value=self.api_object.active)

            add_menu_entry(menu=menu,
                           text="Draw labels",
                           function_ptr=self.enable_disable_label_drawing,
                           checkeable=True,
                           checked_value=self.draw_labels)

            add_menu_entry(menu=menu,
                           text="Editor",
                           function_ptr=self.edit,
                           icon_path=":/Icons/icons/edit.svg")

            add_menu_entry(menu=menu,
                           text="Change bus",
                           function_ptr=self.change_bus,
                           icon_path=":/Icons/icons/move_bus.svg")

            menu.addSeparator()

            add_menu_entry(menu=menu,
                           text="Plot profiles",
                           function_ptr=self.plot_profiles,
                           icon_path=":/Icons/icons/plot.svg")

            add_menu_entry(menu=menu,
                           text="Assign rate to profile",
                           function_ptr=self.assign_rate_to_profile,
                           icon_path=":/Icons/icons/assign_to_profile.svg")

            add_menu_entry(menu=menu,
                           text="Assign active state to profile",
                           function_ptr=self.assign_status_to_profile,
                           icon_path=":/Icons/icons/assign_to_profile.svg")

            add_menu_entry(menu=menu,
                           text="Add to catalogue",
                           function_ptr=self.add_to_catalogue,
                           icon_path=":/Icons/icons/Catalogue.svg")

            add_menu_entry(menu=menu,
                           text="Split line",
                           function_ptr=self.split_line,
                           icon_path=":/Icons/icons/divide.svg")

            add_menu_entry(menu=menu,
                           text="Split line with in/out",
                           function_ptr=self.split_line_in_out,
                           icon_path=":/Icons/icons/divide.svg")

            menu.addSeparator()

            add_menu_entry(menu=menu,
                           text="Delete",
                           function_ptr=self.remove,
                           icon_path=":/Icons/icons/delete3.svg")

            menu.addSection('Convert to')

            add_menu_entry(menu=menu,
                           text="Transformer",
                           function_ptr=self.to_transformer,
                           icon_path=":/Icons/icons/to_transformer.svg")

            add_menu_entry(menu=menu,
                           text="HVDC",
                           function_ptr=self.to_hvdc,
                           icon_path=":/Icons/icons/to_hvdc.svg")

            add_menu_entry(menu=menu,
                           text="VSC",
                           function_ptr=self.to_vsc,
                           icon_path=":/Icons/icons/to_vsc.svg")

            add_menu_entry(menu=menu,
                           text="UPFC",
                           function_ptr=self.to_upfc,
                           icon_path=":/Icons/icons/to_upfc.svg")

            add_menu_entry(menu=menu,
                           text="Series reactance",
                           function_ptr=self.to_series_reactance,
                           icon_path=":/Icons/icons/to_series_reactance.svg")

            add_menu_entry(menu=menu,
                           text="Switch",
                           function_ptr=self.to_switch,
                           icon_path=":/Icons/icons/switch.svg")

            menu.exec(event.screenPos())
        else:
            pass

    def plot_profiles(self) -> None:
        """
        Plot the time series profiles
        @return:
        """
        # get the index of this object
        i = self.editor.circuit.get_branches().index(self.api_object)
        self.editor.plot_branch(i, self.api_object)

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase
        Vnom = self.api_object.get_max_bus_nominal_voltage()
        templates = list()

        for lst in [self.editor.circuit.sequence_line_types,
                    self.editor.circuit.underground_cable_types,
                    self.editor.circuit.overhead_line_types]:
            for temp in lst:
                if Vnom == temp.Vnom:
                    templates.append(temp)

        current_template = self.api_object.template
        dlg = LineEditor(self.api_object, Sbase, templates, current_template)
        if dlg.exec_():
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

    def add_to_catalogue(self):
        """
        Add this to the catalogue
        """
        ok = yes_no_question(text="A template will be generated using this line values per unit of length",
                             title="Add sequence line type")

        if ok:
            # rate = I
            rated_current = self.api_object.rate / (self.api_object.Vf * 1.73205080757)  # MVA = kA * kV * sqrt(3)

            tpe = SequenceLineType(name='SequenceLine from ' + self.api_object.name,
                                   idtag=None,
                                   Imax=rated_current,
                                   Vnom=self.api_object.Vf,
                                   R=self.api_object.R / self.api_object.length,
                                   X=self.api_object.X / self.api_object.length,
                                   B=self.api_object.B / self.api_object.length,
                                   R0=self.api_object.R0 / self.api_object.length,
                                   X0=self.api_object.X0 / self.api_object.length,
                                   B0=self.api_object.B0 / self.api_object.length)

            self.editor.circuit.add_sequence_line(tpe)

    def split_line(self):
        """
        Split the line
        :return:
        """
        self.editor.split_line(line_graphics=self)

    def split_line_in_out(self):
        """
        Split the line
        :return:
        """
        self.editor.split_line_in_out(line_graphics=self)

    def to_transformer(self):
        """
        Convert this object to transformer
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this line into a transformer?', 'Convert line')
        if ok:
            self.editor.convert_line_to_transformer(line=self.api_object, line_graphic=self)

    def to_hvdc(self):
        """
        Convert this object to HVDC
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this line into a HVDC line?', 'Convert line')
        if ok:
            self.editor.convert_line_to_hvdc(line=self.api_object, line_graphic=self)

    def to_vsc(self):
        """
        Convert this object to VSC
        :return:
        """
        if self.api_object.convertible_to_vsc():
            ok = yes_no_question('Are you sure that you want to convert this line into a VSC device?',
                                 'Convert line')
            if ok:
                self.editor.convert_line_to_vsc(line=self.api_object, line_graphic=self)
        else:
            warning_msg('Unable to convert to VSC. One of the buses must be DC and the other AC.')

    def to_upfc(self):
        """
        Convert this object to UPFC
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this line into a UPFC device?',
                             'Convert line')
        if ok:
            self.editor.convert_line_to_upfc(line=self.api_object, line_graphic=self)

    def to_series_reactance(self):
        """
        Convert this object to series reactance
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this line into a series reactance device?',
                             'Convert line')
        if ok:
            self.editor.convert_line_to_series_reactance(line=self.api_object, line_graphic=self)

    def to_switch(self):
        """
        Convert this object to switch
        :return:
        """
        ok = yes_no_question('Are you sure that you want to convert this line into a switch device?',
                             'Convert line')
        if ok:
            self.editor.convert_line_to_switch(line=self.api_object, line_graphic=self)

    def __str__(self):

        if self.api_object is None:
            return f"Line graphics {hex(id(self))}"
        else:
            return f"Graphics of {self.api_object.name} [{hex(id(self))}]"

    def __repr__(self):
        return str(self)
