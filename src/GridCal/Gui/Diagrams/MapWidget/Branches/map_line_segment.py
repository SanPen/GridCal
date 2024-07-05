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
from PySide6.QtCore import Qt, QPointF, QLineF
from PySide6.QtGui import QPen, QColor, QCursor
from PySide6.QtWidgets import QMenu, QGraphicsSceneContextMenuEvent
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsSceneMouseEvent

from GridCal.Gui.GuiFunctions import add_menu_entry
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_editor import LineEditor

from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.Substation.node_graphic_item import NodeGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapLineSegment(QGraphicsLineItem):
    """
    Segment joining two NodeGraphicItem
    """

    def __init__(self, first: NodeGraphicItem, second: NodeGraphicItem, container: MapLineContainer):
        """
        Segment constructor
        :param first: NodeGraphicItem
        :param second: NodeGraphicItem
        """
        QGraphicsLineItem.__init__(self)
        self.first: NodeGraphicItem = first
        self.second: NodeGraphicItem = second
        self.container: MapLineContainer = container
        self.draw_labels = True

        self.style = Qt.SolidLine
        self.color = Qt.blue
        self.width = 0.1

        self.pos1: QPointF = self.first.get_center_pos()
        self.pos2: QPointF = self.second.get_center_pos()

        self.first.add_position_change_callback(self.set_from_side_coordinates)
        self.second.add_position_change_callback(self.set_to_side_coordinates)

        self.set_colour(self.color, self.width, self.style)
        self.update_endings()
        self.needsUpdate = True
        self.setZValue(0)

        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    @property
    def api_object(self) -> BRANCH_TYPES:
        """

        :return:
        """
        return self.container.api_object

    @property
    def editor(self) -> GridMapWidget:
        """

        :return:
        """
        return self.container.editor

    def set_colour(self, color: QColor, w: float, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """

        pen = QPen(color, w, style, Qt.RoundCap, Qt.RoundJoin)
        pen.setWidthF(w)

        self.setPen(pen)
        # self.arrow_from_1.set_colour(color, w, style)
        # self.arrow_from_2.set_colour(color, w, style)
        # self.arrow_to_1.set_colour(color, w, style)
        # self.arrow_to_2.set_colour(color, w, style)

    def set_from_side_coordinates(self, x: float, y: float):
        """

        :param x:
        :param y:
        :return:
        """
        self.pos1 = QPointF(x, y)
        self.update_endings()

    def set_to_side_coordinates(self, x: float, y: float):
        """

        :param x:
        :param y:
        :return:
        """
        self.pos2 = QPointF(x, y)
        self.update_endings()

    def update_endings(self, force=False) -> None:
        """
        Update the endings of this segment
        """
        self.setLine(QLineF(self.pos1, self.pos2))
        # Get the positions of the first and second objects
        # if self.first.needsUpdate or self.second.needsUpdate or force:
        #     # Set the line's starting and ending points
        #     self.setLine(self.first.rect().x(),
        #                  self.first.rect().y(),
        #                  self.second.rect().x(),
        #                  self.second.rect().y())

    def end_update(self) -> None:
        """

        :return:
        """
        self.first.needsUpdate = False
        self.second.needsUpdate = False

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param event:
        :return:
        """
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object,
                                         dictionary_of_lists={
                                             DeviceType.BusDevice: self.editor.circuit.get_buses(),
                                             DeviceType.ConnectivityNodeDevice: self.editor.circuit.get_connectivity_nodes(),
                                             DeviceType.BranchGroupDevice: self.editor.circuit.get_branch_groups()
                                         })

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """

        :param event:
        :return:
        """
        menu = QMenu()

        # add_menu_entry(menu=menu,
        #                text="Remove",
        #                icon_path="",
        #                function_ptr=self.RemoveFunction)

        menu.addSection("Line")

        add_menu_entry(menu=menu,
                       text="Active",
                       function_ptr=self.enable_disable_toggle,
                       checkeable=True,
                       checked_value=self.container.api_object.active)

        add_menu_entry(menu=menu,
                       text="Draw labels",
                       function_ptr=self.enable_disable_label_drawing,
                       checkeable=True,
                       checked_value=self.draw_labels)

        add_menu_entry(menu=menu,
                       text="Editor",
                       function_ptr=self.call_editor,
                       icon_path=":/Icons/icons/edit.svg")

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

        menu.exec_(event.screenPos())

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.editor.circuit.get_time_number() > 0:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.editor.set_active_status_to_profile(self.api_object, override_question=True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']

        # Set pen for everyone
        self.set_colour(self.color, self.width, self.style)

    def enable_disable_label_drawing(self):
        """

        :return:
        """
        self.draw_labels = not self.draw_labels

    def call_editor(self):
        """
        Call the line editor
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

    def plot_profiles(self) -> None:
        """
        Plot the time series profiles
        @return:
        """
        # get the index of this object
        i = self.editor.circuit.get_branches().index(self.api_object)
        self.editor.plot_branch(i, self.api_object)

    def assign_rate_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.editor.set_rate_to_profile(self.api_object)

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.editor.set_active_status_to_profile(self.api_object)

    def split_line(self):
        """

        :return:
        """

        if len(self.container.nodes_list) == 0:
            self.container.insert_new_node_at_position(0)
        elif len(self.container.nodes_list) == 1:
            if self.second == self.container.substation_to() or self.first == self.container.substation_to():
                self.container.insert_new_node_at_position(1)
            else:
                self.container.insert_new_node_at_position(0)
        else:
            if self.second == self.container.substation_to() or self.first == self.container.substation_to():
                self.container.insert_new_node_at_position(len(self.container.nodes_list))
            elif self.second == self.container.substation_from() or self.first == self.container.substation_from():
                self.container.insert_new_node_at_position(0)
            else:
                self.container.insert_new_node_at_position(self.first.index)

        # TODO implement
        # self.editor.split_line(line_graphics=self)
        pass

    def split_line_in_out(self):
        """
        Split the line
        :return:
        """
        # TODO implement
        # self.editor.split_line_in_out(line_graphics=self)
        pass

    def remove(self, ask=True):
        """
        Remove this object in the diagram and the API
        @return:
        """
        if ask:
            dtype = self.api_object.device_type.value
            ok = yes_no_question(f'Do you want to remove the {dtype} {self.api_object.name}?',
                                 f'Remove {dtype}')
        else:
            ok = True

        if ok:
            self.editor.circuit.delete_branch(obj=self.api_object)
            self.editor.delete_diagram_element(device=self.api_object)
