# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import List, TYPE_CHECKING
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QPen, QCursor, QColor
from PySide6.QtWidgets import QGraphicsItem, QGraphicsEllipseItem, QGraphicsRectItem, QMenu, QGraphicsSceneMouseEvent

from VeraGrid.Gui.Diagrams.Editors.transformer3w_editor import Transformer3WEditor
from VeraGrid.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, GenericDiagramWidget
from VeraGrid.Gui.Diagrams.SchematicWidget.terminal_item import RoundTerminalItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.winding_graphics import WindingGraphicItem
from VeraGridEngine.Devices.Branches.transformer3w import Transformer3W
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGrid.Gui.messages import yes_no_question
from VeraGridEngine.enumerations import DeviceType
from VeraGrid.Gui.gui_functions import add_menu_entry

if TYPE_CHECKING:
    # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class Transformer3WGraphicItem(GenericDiagramWidget, QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self, editor: SchematicWidget,
                 elm: Transformer3W,
                 pos: QPoint = None,
                 parent=None,
                 index=0,
                 draw_labels: bool = True):
        """

        :param editor: GridEditor object
        :param elm: Transformer3W object
        :param pos: position
        :param parent:
        :param index:
        :param draw_labels:
        """
        self.h = 100
        self.w = 100
        GenericDiagramWidget.__init__(self, parent=parent, api_object=elm, editor=editor, draw_labels=True)
        QGraphicsRectItem.__init__(self, 0.0, 0.0, self.w, self.h, parent=parent)
        self.n_windings = 3

        self.draw_labels = draw_labels

        # color
        self.pen_width = 4
        if self.api_object is not None:
            if self.api_object.active:
                self.color = ACTIVE['color']
                self.style = ACTIVE['style']
            else:
                self.color = DEACTIVATED['color']
                self.style = DEACTIVATED['style']
        else:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']

        self.setPen(QPen(Qt.GlobalColor.transparent, self.pen_width, self.style))
        self.setBrush(Qt.GlobalColor.transparent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # index
        self.index = index

        if pos is not None:
            self.setPos(pos)

        # windings
        winding_diameter = 40
        radius_large = winding_diameter * 0.5
        radius_small = 5
        angle_0 = -90.0
        d_angle = 360.0 / self.n_windings
        center = QPointF(self.w / 2.0, self.h / 2.0)

        self.winding_circles: List[QGraphicsEllipseItem] = list()
        self.terminals: List[RoundTerminalItem] = list()
        self.connection_lines: List[WindingGraphicItem | None] = list()

        pen = QPen(self.color, self.pen_width, self.style)

        for i in range(self.n_windings):
            angles_deg = angle_0 + d_angle * i
            angle_rad = np.deg2rad(angles_deg)

            # Direction vector
            dx = np.cos(angle_rad)
            dy = np.sin(angle_rad)

            winding_center_x = center.x() + dx * radius_large - radius_large
            winding_center_y = center.y() + dy * radius_large - radius_large

            # create objects
            winding_circle = QGraphicsEllipseItem(parent=self)
            winding_circle.setRect(winding_center_x, winding_center_y, winding_diameter, winding_diameter)

            # Compute offset to make small circle tangent and centered on the same line
            tangent_center_distance = winding_diameter + radius_small
            terminal_center_x = center.x() + dx * tangent_center_distance - radius_small
            terminal_center_y = center.y() + dy * tangent_center_distance - radius_small

            terminal = RoundTerminalItem(name=f"t{i + 1}", parent=self, editor=self.editor, h=10, w=10)
            terminal.setPos(terminal_center_x, terminal_center_y)

            # set objects style
            winding_circle.setPen(pen)
            terminal.setPen(pen)

            self.winding_circles.append(winding_circle)
            self.terminals.append(terminal)
            self.connection_lines.append(None)

        self.big_marker = None

        # other actions
        self.set_winding_tool_tips()

    @property
    def api_object(self) -> Transformer3W:
        return self._api_object

    @property
    def editor(self) -> SchematicWidget:
        return self._editor

    def get_associated_widgets(self) -> List[WindingGraphicItem]:
        """

        :return:
        """
        return self.connection_lines

    def get_extra_graphics(self):
        """
        Get a list of all QGraphicsItem that are not GenericDiagramWidget elements associated with this widget.
        :return:
        """
        return self.winding_circles + self.terminals

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.color = ACTIVE['color']
                self.style = ACTIVE['style']
            else:
                self.color = DEACTIVATED['color']
                self.style = DEACTIVATED['style']
        else:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']

        pen = QPen(self.color, self.pen_width, self.style)
        for i in range(self.n_windings):
            self.winding_circles[i].setPen(pen)
            self.terminals[i].setPen(pen)

            if self.connection_lines[i] is not None:
                self.connection_lines[i].recolour_mode()

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        self.api_object.winding1.active = val
        self.api_object.winding2.active = val
        self.api_object.winding3.active = val

        self.recolour_mode()

    def set_winding_tool_tips(self) -> None:
        """
        Set
        :return:
        """
        if self.api_object is not None:
            self.winding_circles[0].setToolTip("Winding 1: {0} KV".format(self.api_object.V1))
            self.winding_circles[1].setToolTip("Winding 2: {0} KV".format(self.api_object.V2))
            self.winding_circles[2].setToolTip("Winding 3: {0} KV".format(self.api_object.V3))

    def set_label(self, val: str):
        """
        Set the label content
        :param val:
        :return:
        """
        # this function is just for compatibility
        pass

    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """
        On mouse move of this object...
        Args:
            event: QGraphicsSceneMouseEvent inherited
        """
        super().mouseMoveEvent(event)

        self.editor.update_diagram_element(device=self.api_object,
                                           x=self.pos().x(),
                                           y=self.pos().y(),
                                           w=self.w,
                                           h=self.h,
                                           r=self.rotation(),
                                           graphic_object=self)

        # self.update_conn()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param event:
        :return:
        """
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def mouseDoubleClickEvent(self, event):
        """
        On double-click, edit
        :param event:
        :return:
        """

        if self.api_object is not None:
            if self.api_object.device_type in [DeviceType.Transformer3WDevice]:
                # trigger the editor
                self.edit()

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("3w-Transformer")

            add_menu_entry(menu=menu,
                           text="Active",
                           function_ptr=self.enable_disable_toggle,
                           checkeable=True,
                           checked_value=self.api_object.active)

            menu.addSeparator()

            add_menu_entry(menu=menu,
                           text="Edit",
                           function_ptr=self.edit,
                           icon_path=":/Icons/icons/edit.svg")

            add_menu_entry(menu=menu,
                           text="Delete",
                           function_ptr=self.delete,
                           icon_path=":/Icons/icons/delete_schematic.svg")

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

            if self._editor.circuit.get_time_number() > 0:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self._editor.set_active_status_to_profile(self.api_object, override_question=True)
                    self._editor.set_active_status_to_profile(self.api_object.winding1, override_question=True)
                    self._editor.set_active_status_to_profile(self.api_object.winding2, override_question=True)
                    self._editor.set_active_status_to_profile(self.api_object.winding3, override_question=True)

    def add_big_marker(self, color=Qt.GlobalColor.red, tool_tip_text=""):
        """
        Add a big marker to the bus
        :param color: Qt Color ot the marker
        :param tool_tip_text: tool tip text to display
        :return:
        """
        if self.big_marker is None:
            self.big_marker = QGraphicsEllipseItem(0, 0, 180, 180, parent=self)
            self.big_marker.setBrush(color)
            self.big_marker.setOpacity(0.5)
            self.big_marker.setToolTip(tool_tip_text)

    def delete_big_marker(self):
        """
        Delete the big marker
        """
        if self.big_marker is not None:
            self.editor._remove_from_scene(self.big_marker)
            self.big_marker = None

    def change_size(self, w, h):
        """

        :param w:
        :param h:
        """
        # Keep for compatibility

        self.editor.update_diagram_element(device=self.api_object,
                                           x=self.pos().x(),
                                           y=self.pos().y(),
                                           w=w,
                                           h=h,
                                           r=self.rotation(),
                                           graphic_object=self)

    def set_position(self, x: float, y: float) -> None:
        """
        Set the bus x, y position
        :param x: x in pixels
        :param y: y in pixels
        """
        x = 0 if np.isnan(x) else int(x)
        y = 0 if np.isnan(y) else int(y)
        self.setPos(QPoint(int(x), int(y)))

    def get_connection_winding(self, from_port: RoundTerminalItem, to_port: RoundTerminalItem):
        """
        Find the winding between the terminals
        :param from_port: "from" terminal [TerminalItem]
        :param to_port: "to" terminal [TerminalItem]
        """
        for i, t in enumerate(self.terminals):
            if t in [from_port, to_port]:
                return i

        raise Exception("Unknown winding")

    def set_connection(self, i: int, bus: Bus, conn: WindingGraphicItem, set_voltage: bool = True):
        """
        Create the connection with a bus
        :param i: winding index 0-2
        :param bus: Bus object to connect to
        :param conn: Connection graphical object [LineGraphicItem]
        :param set_voltage: Set voltage in the object (Transformer3W and Windings)
        """
        if i == 0:
            self.api_object.bus1 = bus
            if set_voltage:
                self.api_object.V1 = bus.Vnom
            self.connection_lines[0] = conn
            self.terminals[0].setZValue(-1)
            conn.api_object = self.api_object.winding1
            conn.winding_number = 0

        elif i == 1:
            self.api_object.bus2 = bus
            if set_voltage:
                self.api_object.V2 = bus.Vnom
            self.connection_lines[1] = conn
            self.terminals[1].setZValue(-1)
            conn.api_object = self.api_object.winding2
            conn.winding_number = 1

        elif i == 2:
            self.api_object.bus3 = bus
            if set_voltage:
                self.api_object.V3 = bus.Vnom
            self.connection_lines[2] = conn
            self.terminals[2].setZValue(-1)
            conn.api_object = self.api_object.winding3
            conn.winding_number = 2
        else:
            raise Exception('Unsupported winding index {}'.format(i))

        # set the reverse lookup
        conn.parent_tr3_graphics_item = self

        # update the connection placement
        # self.update_conn()
        self.mousePressEvent(None)

    def remove_winding(self, i: int):
        """
        Remove winding by index
        :param i: winding index [0, 1, 2]
        """
        if i == 0:
            self.api_object.bus1 = None
            self.api_object.V1 = 0
            self.connection_lines[0] = None
            self.api_object.winding1.bus_to = None
            self.terminals[0].setZValue(-1)

        elif i == 1:
            self.api_object.bus2 = None
            self.api_object.V2 = 0
            self.connection_lines[1] = None
            self.api_object.winding2.bus_to = None
            self.terminals[1].setZValue(-1)

        elif i == 2:
            self.api_object.bus3 = None
            self.api_object.V3 = 0
            self.connection_lines[2] = None
            self.api_object.winding3.bus_to = None
            self.terminals[2].setZValue(-1)
        else:
            raise Exception('Unsupported winding index {}'.format(i))

    def arrange_children(self) -> None:
        """
        this function is necessary because this graphic item behaves like a bus,
        but the function itself does nothing
        """
        pass

    def set_tile_color(self, brush: QColor):
        """
        Set the voltage colour
        :param brush: QColor object
        """
        for w in self.winding_circles:
            w.setPen(QPen(brush, self.pen_width, self.style))

    def set_winding_color(self, i, color: QColor):
        """
        Set a winding (loading) colour
        :param i: winding index 0-2
        :param color: QColor
        """
        self.winding_circles[i].setPen(QPen(color, self.pen_width, self.style))
        self.terminals[i].setPen(QPen(color, self.pen_width, self.style))

    def delete(self):
        """
        Remove this element
        @return:
        """
        self.editor.delete_with_dialogue(selected=[self], delete_from_db=False)

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase
        dlg = Transformer3WEditor(self.api_object, Sbase, modify_on_accept=True)
        if dlg.exec():
            pass
