# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import webbrowser
from typing import List, TYPE_CHECKING, Tuple
from PySide6 import QtWidgets
from PySide6.QtWidgets import QMenu, QGraphicsSceneContextMenuEvent, QGraphicsSceneMouseEvent, QGraphicsRectItem
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor
from GridCal.Gui.Diagrams.MapWidget.Substation.node_template import NodeTemplate
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.general_dialogues import InputNumberDialogue, CheckListDialogue

from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices import VoltageLevel
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget
    from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem


class SubstationGraphicItem(NodeTemplate, QGraphicsRectItem):
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
                 size: float = 0.8,
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        :param lat:
        :param lon:
        :param size:
        """
        # Correct way to call multiple inheritance
        super().__init__()

        # Explicitly call QGraphicsRectItem initialization
        QGraphicsRectItem.__init__(self)

        # Explicitly call NodeTemplate initialization
        NodeTemplate.__init__(self, api_object=api_object,
                              editor=editor,
                              draw_labels=draw_labels,
                              lat=lat,
                              lon=lon)

        self.size = size
        self.line_container = None
        self.editor: GridMapWidget = editor  # reassign for the types to be clear
        self.api_object: Substation = api_object  # reassign for the types to be clear

        r2 = size / 2
        x, y = editor.to_x_y(lat=lat, lon=lon)  # upper left corner
        self.setRect(
            x - r2,
            y - r2,
            self.size,
            self.size
        )

        # Enable hover events for the item
        self.setAcceptHoverEvents(True)

        # Allow selecting the node
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Create a pen with reduced line width
        self.change_pen_width(0.05 * size)

        # Create a pen with reduced line width
        self.color = QColor(self.api_object.color)
        self.color.setAlpha(128)
        self.hoover_color = QColor(self.api_object.color)
        self.hoover_color.setAlpha(180)
        self.border_color = QColor(self.api_object.color)  # No Alpha

        self.set_default_color()

        # list of voltage levels graphics
        self.voltage_level_graphics: List[VoltageLevelGraphicItem] = list()

    def merge(self, se: "SubstationGraphicItem"):
        """
        Merge a substation into this one
        :param se: other SubstationGraphicItem
        """
        self._callbacks += se._callbacks
        self.voltage_level_graphics += se.voltage_level_graphics

    def set_size(self, r: float):
        """

        :param r: radius in pixels
        :return:
        """
        if r != self.size:
            rect = self.rect()
            rect.setWidth(r)
            rect.setHeight(r)

            # change the width and height while keeping the same center
            r2 = (self.size - r) / 2
            new_x = rect.x() + r2
            new_y = rect.y() + r2

            self.size = r

            # Set the new rectangle with the updated dimensions
            self.setRect(new_x, new_y, r, r)

            # update the callbacks position for the lines to move accordingly
            r3 = r / 2
            xc = new_x + r3
            yc = new_y + r3
            self.set_callbacks(xc, yc)

            for vl_graphics in self.voltage_level_graphics:
                vl_graphics.center_on_substation()

            self.change_pen_width(0.05 * self.size)

            self.update_position_at_the_diagram()

            self.resize_voltage_levels()

    def resize_voltage_levels(self) -> None:
        """

        :return:
        """
        max_vl = 1.0  # 1 KV
        for vl_graphics in self.voltage_level_graphics:
            max_vl = max(max_vl, vl_graphics.api_object.Vnom)

        for vl_graphics in self.voltage_level_graphics:
            # radius here is the width, therefore we need to send W/2
            scale = vl_graphics.api_object.Vnom / max_vl * 0.5
            vl_graphics.set_size(r=self.size * scale)
            vl_graphics.center_on_substation()

    def set_api_object_color(self) -> None:
        """
        Gather the API object color and update this objects
        """
        self.color = QColor(self.api_object.color)
        self.color.setAlpha(128)

        self.hoover_color = QColor(self.api_object.color)
        self.hoover_color.setAlpha(180)

        self.border_color = QColor(self.api_object.color)  # No Alpha

        self.set_default_color()

    def move_to(self, lat: float, lon: float) -> Tuple[float, float]:
        """

        :param lat:
        :param lon:
        :return: x, y
        """
        x, y = self.editor.to_x_y(lat=lat, lon=lon)  # upper left corner

        self.setRect(
            x - self.rect().width() / 2,
            y - self.rect().height() / 2,
            self.rect().width(),
            self.rect().height()
        )

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
        max_vl = 1.0  # 1 KV
        for vl_graphics in self.voltage_level_graphics:
            max_vl = max(max_vl, vl_graphics.api_object.Vnom)

        for vl_graphics in self.voltage_level_graphics:
            scale = vl_graphics.api_object.Vnom / max_vl * 0.8
            vl_graphics.set_size(r=self.size * scale)
            vl_graphics.center_on_substation()

        sorted_objects = sorted(self.voltage_level_graphics, key=lambda x: -x.api_object.Vnom)
        for i, vl_graphics in enumerate(sorted_objects):
            vl_graphics.setZValue(i)

    def update_position_at_the_diagram(self) -> None:
        """
        Updates the element position in the diagram (to save)
        :return: 
        """
        lat, long = self.editor.to_lat_lon(self.rect().x(), self.rect().y())

        self.lat = lat
        self.lon = long

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=lat,
                                           longitude=long,
                                           graphic_object=self)

    def get_center_pos(self) -> QPointF:
        """
        Get the center position
        :return: QPointF
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
            self.set_callbacks(pos.x(), pos.y())

            for vl_graphics in self.voltage_level_graphics:
                vl_graphics.center_on_substation()

            self.update_position_at_the_diagram()  # always update

        # QGraphicsRectItem.mouseMoveEvent(self, event)
        # pos = self.mapToParent(event.pos())
        # x = pos.x() + self.rect().width() / 2
        # y = pos.y() + self.rect().height() / 2
        # self.set_callbacks(x, y)
        # self.update_position_at_the_diagram()  # always update

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)
        # selected_items = self.editor.map.view.selected_items()
        # if len(selected_items) < 2:
        self.setSelected(True)

        event.setAccepted(True)
        self.editor.map.view.disable_move = True

        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse release events.
        """
        # super().mouseReleaseEvent(event)
        self.editor.disableMove = True
        self.update_position_at_the_diagram()  # always update

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse enters the item.
        """
        # self.editor.map.view.in_item = True
        self.set_color(self.hoover_color, self.color)
        self.hovered = True

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse leaves the item.
        """
        # self.editor.map.view.in_item = False
        self.hovered = False
        self.set_default_color()
        # QApplication.instance().restoreOverrideCursor()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """

        :param event:
        """
        menu = QMenu()

        add_menu_entry(menu=menu,
                       text="Add voltage level",
                       icon_path=":/Icons/icons/plus.svg",
                       function_ptr=self.add_voltage_level)

        add_menu_entry(menu=menu,
                       text="Create line from here",
                       icon_path=":/Icons/icons/plus.svg",
                       function_ptr=self.create_new_line)

        add_menu_entry(menu=menu,
                       text="Merge selected substations here",
                       icon_path=":/Icons/icons/fusion.svg",
                       function_ptr=self.merge_selected_substations)

        add_menu_entry(menu=menu,
                       text="Set coordinates to DB",
                       icon_path=":/Icons/icons/down.svg",
                       function_ptr=self.move_to_api_coordinates)

        add_menu_entry(menu=menu,
                       text="Remove from schematic only",
                       icon_path=":/Icons/icons/delete_schematic.svg",
                       function_ptr=self.remove_function_from_schematic)

        add_menu_entry(menu=menu,
                       text="Remove from schematic and database",
                       icon_path=":/Icons/icons/delete_db.svg",
                       function_ptr=self.remove_function_from_schematic_and_db)

        add_menu_entry(menu=menu,
                       text="Show diagram",
                       icon_path=":/Icons/icons/grid_icon.svg",
                       function_ptr=self.new_substation_diagram)

        add_menu_entry(menu=menu,
                       text="Plot",
                       icon_path=":/Icons/icons/plot.svg",
                       function_ptr=self.plot)

        add_menu_entry(menu=menu,
                       text="Open in street view",
                       icon_path=":/Icons/icons/map.svg",
                       function_ptr=self.open_street_view)

        menu.exec_(event.screenPos())

    def create_new_line(self):
        """
        Create a new line in the map wizard
        """
        self.editor.create_new_line_wizard()

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
                    elm=graphic_object.api_object.get_substation_from()
                )
                substation_to_graphics = self.editor.graphics_manager.query(
                    elm=graphic_object.api_object.get_substation_to()
                )
                lines_info.append((idtag, graphic_object, substation_from_graphics, substation_to_graphics))

            # Now, iterate over the collected information
            for idtag, graphic_object, substation_from_graphics, substation_to_graphics in lines_info:
                if substation_from_graphics == self:
                    graphic_object.insert_new_node_at_position(0)

                if substation_to_graphics == self:
                    graphic_object.insert_new_node_at_position(len(graphic_object.nodes_list))

        pass

    def remove_function_from_schematic(self) -> None:
        """
        Removes the substation from the schematic only. The substation will remain in the database.
        """
        ok = yes_no_question(f"Remove substation {self.api_object.name} from the schematic only? It will remain in the database.",
                             "Remove substation from schematic")

        if ok:
            self.editor.remove_substation(substation=self, delete_from_db=False)

    def remove_function_from_schematic_and_db(self) -> None:
        """
        Removes the substation from both the schematic and the database. This action cannot be undone.
        """

        ok = yes_no_question(f"Remove substation {self.api_object.name} from both the schematic and the database? This action cannot be undone.",
                             "Remove substation from schematic and database")

        if ok:
            self.editor.remove_substation(substation=self, delete_from_db=True)

    def move_to_api_coordinates(self):
        """
        Function to move the graphics to the Database location
        :return:
        """
        ok = yes_no_question(f"Move substation {self.api_object.name} graphics to it's database coordinates?",
                             "Move substation graphics")

        if ok:
            x, y = self.move_to(lat=self.api_object.latitude, lon=self.api_object.longitude)  # this moves the vl too
            self.set_callbacks(x, y)

    def merge_selected_substations(self):
        """
        Merge selected substations into this one
        """
        selected = self.editor.get_selected_substations()

        dlg = CheckListDialogue(
            objects_list=[f"{graphic_obj.api_object.device_type.value}: {graphic_obj.api_object.name}"
                          for graphic_obj in selected],
            title=f"Merge into {self.api_object.name}"
        )

        dlg.setModal(True)
        dlg.exec()

        if dlg.is_accepted:

            deleted_api_objs: List[Substation] = list()
            
            # Collect all codes to merge
            merged_codes = ""
            
            for i in dlg.selected_indices:

                se_graphics = selected[i]
                if merged_codes == "":
                    merged_codes = se_graphics.api_object.code
                else:
                    merged_codes = merged_codes + ',' + se_graphics.api_object.code
                
                deleted_api_objs.append(se_graphics.api_object)

                if se_graphics != self:
                    self.merge(se=se_graphics)
                    self.editor.remove_substation(substation=se_graphics,
                                                  delete_from_db=True,
                                                  delete_connections=False)
            
            # Update the code of the base substation
            self.api_object.code = merged_codes  # Needed?
            
            # Find the base substation in the circuit's collection and update it
            for i, substation in enumerate(self.editor.circuit._substations):
                if substation == self.api_object:
                    self.editor.circuit._substations[i].code = merged_codes
                    break

            # re-index the stuff pointing at deleted api elements to this api object
            for vl in self.editor.circuit.voltage_levels:
                if vl.substation in deleted_api_objs:
                    vl.substation = self.api_object

            for bus in self.editor.circuit.buses:
                if bus.substation in deleted_api_objs:
                    bus.substation = self.api_object

            # remove connections that are from and to the same substation
            for tpe in [DeviceType.LineDevice, DeviceType.DCLineDevice, DeviceType.HVDCLineDevice]:
                for elm in self.editor.graphics_manager.get_device_type_list(tpe):
                    if elm.api_object.get_substation_from() == elm.api_object.get_substation_to():
                        self.editor.remove_branch_graphic(elm, delete_from_db=True)

        self.update_position_at_the_diagram()  # always update

    def new_substation_diagram(self):
        """
        Function to create a new substation
        :return:
        """
        self.editor.new_substation_diagram(substation=self.api_object)

    def plot(self):
        """
        Plot the substations data
        """
        i = self.editor.circuit.get_substations().index(self.api_object)
        self.editor.plot_substation(i, self.api_object)

    def add_voltage_level(self) -> None:
        """
        Add Voltage Level
        """

        inpt = InputNumberDialogue(
            min_value=0.1,
            max_value=100000.0,
            default_value=self.editor.diagram.default_bus_voltage,
            title="Add voltage level",
            text="Voltage (KV)",
        )

        inpt.exec()

        if inpt.is_accepted:
            kv = inpt.value
            vl = VoltageLevel(name=f'{self.api_object.name} @{kv} kV VL',
                              Vnom=kv,
                              substation=self.api_object)

            bus = Bus(name=f"{self.api_object.name} @{kv} kV bus",
                      Vnom=kv,
                      substation=self.api_object,
                      voltage_level=vl)

            self.editor.circuit.add_voltage_level(vl)
            self.editor.circuit.add_bus(obj=bus)
            self.editor.add_api_voltage_level(substation_graphics=self, api_object=vl)
            self.sort_voltage_levels()

    def get_pos(self) -> QPointF:
        """

        :return:
        """
        # Get the bounding rectangle of the ellipse item
        bounding_rect = self.boundingRect()

        # Calculate the center point of the bounding rectangle
        center_point = bounding_rect.center()

        return center_point

    def change_pen_width(self, width: float) -> None:
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidthF(width)
        self.setPen(pen)

    def set_color(self, inner_color: QColor = None, border_color: QColor = None) -> None:
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

    def set_default_color(self) -> None:
        """

        :return:
        """
        # Example: color assignment
        self.set_color(self.color, self.border_color)

    def open_street_view(self):
        """
        Call open street maps
        :return:
        """
        # https://maps.google.com/?q=<lat>,<lng>
        url = f"https://www.google.com/maps/?q={self.lat},{self.lon}"
        webbrowser.open(url)


