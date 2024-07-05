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
from typing import List, TYPE_CHECKING, Tuple
from PySide6 import QtWidgets
from PySide6.QtWidgets import (QApplication, QMenu, QGraphicsSceneContextMenuEvent, QGraphicsSceneMouseEvent,
                               QGraphicsRectItem, QGraphicsEllipseItem)
from PySide6.QtCore import Qt, QPointF, QPoint
from PySide6.QtGui import QBrush, QColor, QCursor
from GridCal.Gui.Diagrams.MapWidget.Substation.node_template import NodeTemplate
from GridCal.Gui.GuiFunctions import add_menu_entry
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.GeneralDialogues import InputNumberDialogue
from GridCalEngine.Devices import VoltageLevel
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget
    from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem


class SubstationGraphicItem(QGraphicsRectItem, NodeTemplate):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self,
                 editor: GridMapWidget,
                 api_object: Substation,
                 lat: float,
                 lon: float,
                 r: float = 0.8,
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        :param lat:
        :param lon:
        :param r:
        """
        QGraphicsRectItem.__init__(self)
        NodeTemplate.__init__(self,
                              api_object=api_object,
                              editor=editor,
                              draw_labels=draw_labels,
                              lat=lat,
                              lon=lon)

        self.line_container = None
        self.editor: GridMapWidget = editor  # re assign for the types to be clear
        self.api_object: Substation = api_object

        self.lat = lat
        self.lon = lon
        self.radius = r
        x, y = self.editor.to_x_y(lat=lat, lon=lon)
        self.setRect(x, y, r, r)

        # ellipse_item = QGraphicsEllipseItem(0, 0, r, r)
        # ellipse_item.setBrush(QBrush(QColor(0, 0, 255, 127)))
        # ellipse_item.setParentItem(self)
        # ellipse_item.setPos(QPointF(-84.287109, -1007.726563))

        # self.resize(r)
        self.setAcceptHoverEvents(True)  # Enable hover events for the item
        # self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)  # Allow moving the node
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)  # Allow selecting the node
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Create a pen with reduced line width
        self.change_pen_width(0.5)
        self.colorInner = QColor(255, 100, 100, 100)
        self.colorBorder = QColor(255, 100, 100, 100)

        # Assign color to the node
        self.setDefaultColor()
        self.hovered = False
        self.needsUpdate = False
        # self.setZValue(1)
        self.voltage_level_graphics: List[VoltageLevelGraphicItem] = list()

    def move_to(self, lat: float, lon: float) -> Tuple[float, float]:
        """

        :param lat:
        :param lon:
        :return: x, y
        """
        x, y = self.editor.to_x_y(lat=lat, lon=lon)
        self.setRect(x, y, self.rect().width(), self.rect().height())

        for vl in self.voltage_level_graphics:
            vl.center_on_substation()

        return x, y

    def register_voltage_level(self, vl: VoltageLevelGraphicItem):
        """

        :param vl:
        :return:
        """
        self.voltage_level_graphics.append(vl)
        vl.center_on_substation()

    def sort_voltage_levels(self) -> None:
        """
        Set the Zorder based on the voltage level voltage
        """
        # TODO: Check this
        sorted_objects = sorted(self.voltage_level_graphics, key=lambda x: x.api_object.Vnom)
        for i, vl_graphics in enumerate(sorted_objects):
            vl_graphics.setZValue(i)

    def updatePosition(self) -> None:
        """

        :return: 
        """
        real_position = self.pos()
        center_point = self.getPos()
        # self.x = center_point.x() + real_position.x()
        # self.y = center_point.y() + real_position.y()
        self.needsUpdate = True

    def updateDiagram(self):
        """
        
        :return: 
        """
        lat, long = self.editor.to_lat_lon(self.rect().x(), self.rect().y())

        # print(f'Updating SE position id:{self.api_object.idtag}, lat:{lat}, lon:{long}')

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=lat,
                                           longitude=long,
                                           graphic_object=self)

    def get_center_pos(self) -> QPointF:
        """

        :return:
        """
        x = self.rect().x() + self.rect().width() / 2
        y = self.rect().y() + self.rect().height() / 2
        return QPointF(x, y)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse move events.
        """

        if self.hovered:
            # super().mouseMoveEvent(event)
            pos = self.mapToParent(event.pos())
            x = pos.x() - self.rect().width() / 2
            y = pos.y() - self.rect().height() / 2
            self.setRect(x, y, self.rect().width(), self.rect().height())
            self.set_callabacks(pos.x(), pos.y())

            for vl_graphics in self.voltage_level_graphics:
                vl_graphics.center_on_substation()

            self.updateDiagram()  # always update

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)
        event.setAccepted(True)
        self.editor.map.view.disableMove = True

        print("SE mouse press")
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object,
                                         dictionary_of_lists={
                                             DeviceType.CountryDevice: self.editor.circuit.get_countries(),
                                             DeviceType.CommunityDevice: self.editor.circuit.get_communities(),
                                             DeviceType.RegionDevice: self.editor.circuit.get_regions(),
                                             DeviceType.MunicipalityDevice: self.editor.circuit.get_municipalities(),
                                             DeviceType.AreaDevice: self.editor.circuit.get_areas(),
                                             DeviceType.ZoneDevice: self.editor.circuit.get_zones(),
                                         })

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse release events.
        """
        # super().mouseReleaseEvent(event)
        self.editor.disableMove = True
        self.updateDiagram()  # always update
        print("SE mouse release")

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse enters the item.
        """
        self.setNodeColor(QColor(Qt.red), QColor(Qt.red))
        self.hovered = True
        QApplication.instance().setOverrideCursor(Qt.PointingHandCursor)

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse leaves the item.
        """
        self.hovered = False
        self.setDefaultColor()
        QApplication.instance().restoreOverrideCursor()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """

        :param event:
        """
        menu = QMenu()

        add_menu_entry(menu=menu,
                       text="Add voltage level",
                       icon_path="",
                       function_ptr=self.add_voltage_level)

        add_menu_entry(menu=menu,
                       text="Move to API coordinates",
                       icon_path="",
                       function_ptr=self.move_to_api_coordinates)

        add_menu_entry(menu=menu,
                       text="Remove",
                       icon_path="",
                       function_ptr=self.remove_function)

        add_menu_entry(menu=menu,
                       text="ADD node",
                       icon_path=":/Icons/icons/divide.svg",
                       function_ptr=self.add_function)

        add_menu_entry(menu=menu,
                       text="Show diagram",
                       icon_path="",
                       function_ptr=self.new_substation_diagram)

        menu.exec_(event.screenPos())

    def add_function(self):
        """

        :return:
        """

        for dev_tpe in [DeviceType.LineDevice,
                        DeviceType.DCLineDevice,
                        DeviceType.HVDCLineDevice,
                        DeviceType.FluidPathDevice]:

            dev_dict = self.editor.graphics_manager.get_device_type_dict(device_type=dev_tpe)
            lines_info = []

            for idtag, graphic_object in dev_dict.items():
                substation_from_graphics = self.editor.graphics_manager.query(
                    elm=graphic_object.api_object.get_substation_from())
                substation_to_graphics = self.editor.graphics_manager.query(
                    elm=graphic_object.api_object.get_substation_to())
                lines_info.append((idtag, graphic_object, substation_from_graphics, substation_to_graphics))

            # Now, iterate over the collected information
            for idtag, graphic_object, substation_from_graphics, substation_to_graphics in lines_info:
                if substation_from_graphics == self:
                    graphic_object.insert_new_node_at_position(0)

                if substation_to_graphics == self:
                    graphic_object.insert_new_node_at_position(len(graphic_object.nodes_list))

        pass

    def remove_function(self):
        """
        Function to be called when Action 1 is selected.
        """
        ok = yes_no_question(f"Remove substation {self.api_object.name}?",
                             "Remove substation graphics")

        if ok:
            self.editor.removeSubstation(self)

    def move_to_api_coordinates(self):
        """
        Function to move the graphics to the Database location
        :return:
        """
        ok = yes_no_question(f"Move substation {self.api_object.name} graphics to it's database coordinates?",
                             "Move substation graphics")

        if ok:
            x, y = self.move_to(lat=self.api_object.latitude, lon=self.api_object.longitude)  # this moves the vl too
            self.set_callabacks(x, y)

    def new_substation_diagram(self):
        """
        Function to create a new substation
        :return:
        """
        self.editor.new_substation_diagram(substation=self.api_object)

    def add_voltage_level(self) -> None:
        """
        Add Voltage Level
        """

        inpt = InputNumberDialogue(
            min_value=1.0,
            max_value=100000.0,
            default_value=1.0,
            title="Add voltage level",
            text="Voltage (kV)",
        )

        inpt.exec()

        if inpt.is_accepted:
            kv = inpt.value
            vl = VoltageLevel(name=f'{kv}kV @ {self.api_object.name}',
                              Vnom=kv,
                              substation=self.api_object)

            self.editor.circuit.add_voltage_level(vl)
            self.editor.add_api_voltage_level(substation_graphics=self,
                                              api_object=vl)

    def setNodeColor(self, inner_color: QColor = None, border_color: QColor = None) -> None:
        """

        :param inner_color:
        :param border_color:
        :return:
        """
        # Example: color assignment
        brush = QBrush(inner_color)
        self.setBrush(brush)

        if border_color is not None:
            pen = self.pen()
            pen.setColor(border_color)
            self.setPen(pen)

    def setDefaultColor(self) -> None:
        """

        :return:
        """
        # Example: color assignment
        self.setNodeColor(self.colorInner, self.colorBorder)

    def getPos(self) -> QPointF:
        """

        :return:
        """
        # Get the bounding rectangle of the ellipse item
        bounding_rect = self.boundingRect()

        # Calculate the center point of the bounding rectangle
        center_point = bounding_rect.center()

        return center_point

    # def resize(self, new_radius: float) -> None:
    #     """
    #     Resize the node.
    #     :param new_radius: New radius for the node.
    #     """
    #     self.radius = new_radius
    #     self.setRect(self.x - new_radius, self.y - new_radius, new_radius * 2, new_radius * 2)

    def change_pen_width(self, width: float) -> None:
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidth(width)
        self.setPen(pen)
