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
import numpy as np
from typing import Union, TYPE_CHECKING, List, Dict
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPen, QCursor, QIcon, QPixmap, QBrush, QPainterPath, QFont
from PySide6.QtWidgets import QMenu, QGraphicsRectItem, QGraphicsSceneMouseEvent, QGraphicsTextItem

from GridCalEngine.Devices.Fluid import FluidNode, FluidTurbine, FluidPump, FluidP2x
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import DeviceType, FaultType
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Devices.types import FLUID_TYPES

from GridCal.Gui.Diagrams.SchematicWidget.generic_graphics import ACTIVE, FONT_SCALE, GenericDBWidget
from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, HandleItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_turbine_graphics import FluidTurbineGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_pump_graphics import FluidPumpGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_p2x_graphics import FluidP2xGraphicItem
from GridCal.Gui.messages import yes_no_question

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class RoundedRect(QtWidgets.QGraphicsRectItem):
    """
    Rounded rectangle
    """
    def __init__(self, x, y, width, height, radius, parent):
        super().__init__(x, y, width, height, parent=parent)
        self.radius = radius

    def paint(self, painter, option, widget):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), self.radius, self.radius)
        painter.setClipPath(path)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRoundedRect(self.rect(), self.radius, self.radius)


class VerticalWaterIndicator(QGraphicsRectItem):
    def __init__(self, x, y, width, height, outer_radius, inner_radius, parent=None):
        super().__init__(x, y, width, height, parent=parent)
        self.outer_radius = outer_radius
        self.inner_radius = inner_radius
        self.setBrush(Qt.lightGray)  # Set the outer rectangle color

        self.inner_rect = QGraphicsRectItem(self.rect(), self)
        self.inner_rect.setBrush(Qt.blue)  # Set the inner rectangle color

        self.label = QGraphicsTextItem('', self)
        self.label.setDefaultTextColor(Qt.black)
        self.label.setFont(QFont('Arial', 10))

    def set_percentage(self, percentage):
        # Update the inner rectangle size based on the percentage
        inner_height = self.rect().height() * percentage / 100
        self.inner_rect.setRect(self.rect().x(), self.rect().y() + self.rect().height() - inner_height,
                                self.rect().width(), inner_height)
        self.inner_rect.setPos(self.rect().x(), self.rect().y())

        # Update the label text
        self.label.setPlainText(f'{percentage}%')


class FluidNodeGraphicItem(GenericDBWidget, QtWidgets.QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self, editor: SchematicWidget, fluid_node: FluidNode,
                 parent=None, index=0, h: int = 20, w: int = 80, x: int = 0, y: int = 0,
                 draw_labels: bool = True):

        GenericDBWidget.__init__(self, parent=parent, api_object=fluid_node, editor=editor, draw_labels=draw_labels)
        QtWidgets.QGraphicsRectItem.__init__(self, parent)

        self.min_w = 180.0
        self.min_h = 40.0
        self.offset = 20
        self.h = h if h >= self.min_h else self.min_h
        self.w = w if w >= self.min_w else self.min_w

        # loads, shunts, generators, etc...
        self.shunt_children = list()

        # Enabled for short circuit
        self.sc_enabled = [False, False, False, False]
        self.sc_type = FaultType.ph3
        self.pen_width = 4

        # index
        self.index = index

        self.color = ACTIVE['fluid']
        self.style = ACTIVE['style']

        # Label:
        self.label = QtWidgets.QGraphicsTextItem(self.api_object.name if self.api_object is not None else "", self)
        self.label.setDefaultTextColor(ACTIVE['text'])
        self.label.setScale(FONT_SCALE)

        # square
        self.tile = QtWidgets.QGraphicsRectItem(0, 0, 20, 20, self)
        self.tile.setOpacity(0.7)

        # connection terminals the block
        self._terminal = BarTerminalItem('s', parent=self, editor=self.editor)  # , h=self.h))
        self._terminal.setPen(QPen(Qt.transparent, self.pen_width, self.style, Qt.RoundCap, Qt.RoundJoin))

        # Create corner for resize:
        self.sizer = HandleItem(self._terminal, callback=self.change_size)
        self.sizer.setPos(self.w, self.h)
        self.sizer.setFlag(self.GraphicsItemFlag.ItemIsMovable)

        self.big_marker = None

        self.set_tile_color(self.color)

        self.setPen(QPen(Qt.transparent, self.pen_width, self.style))
        self.setBrush(Qt.transparent)
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Update size:
        self.change_size(self.w, self.h)

        self.set_position(x, y)

    def set_label(self, val: str):
        """
        Set the label content
        :param val:
        :return:
        """
        self.label.setPlainText(val)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        mouse press: display the editor
        :param event:
        :return:
        """
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
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
                                           draw_labels=self.draw_labels,
                                           graphic_object=self)

    def set_position(self, x, y):
        """
        Set the bus x, y position
        :param x: x in pixels
        :param y: y in pixels
        """
        if np.isnan(x):
            x = 0
        if np.isnan(y):
            y = 0
        self.setPos(QPoint(int(x), int(y)))

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
        # self.color = ACTIVE['color']
        # self.style = ACTIVE['style']
        self.label.setDefaultTextColor(ACTIVE['text'])
        # self.set_tile_color(self.color)

        for e in self.shunt_children:
            if e is not None:
                e.recolour_mode()

    def set_tile_color(self, brush):
        """
        Set the color of the title
        Args:
            brush:  Qt Color
        """
        self.tile.setBrush(brush)
        self._terminal.setBrush(brush)

    def redraw(self):
        """
        Update the object
        :return:
        """
        self.change_size(self.w, self.h)

    def set_height(self, h):
        """
        Set the object height
        :param h: height in pixels
        """
        self.setRect(0.0, 0.0, self.w, h)
        self.h = h

    def change_size(self, w: int, h: Union[None, int] = None):
        """
        Resize block function
        @param w:
        @param h:
        @return:
        """
        # Limit the block size to the minimum size:
        self.w = w if w > self.min_w else self.min_w
        self.setRect(0.0, 0.0, self.w, self.min_h)
        y0 = self.offset
        x0 = 0

        # center label:
        self.label.setPos(self.w + 5, -20)

        # lower
        self._terminal.setPos(x0, y0)
        self._terminal.setRect(0, 20, self.w, 10)

        # rearrange children
        self.arrange_children()

        # update editor diagram position
        self.editor.update_diagram_element(device=self.api_object,
                                           x=self.pos().x(),
                                           y=self.pos().y(),
                                           w=self.w,
                                           h=int(self.min_h),
                                           r=self.rotation(),
                                           draw_labels=self.draw_labels,
                                           graphic_object=self)

        return self.w, self.min_h

    def arrange_children(self):
        """
        This function sorts the load and generators icons
        Returns:
            Nothing
        """
        y0 = self.h + 40
        n = len(self.shunt_children)
        inc_x = self.w / (n + 1)
        x = inc_x
        for elm in self.shunt_children:
            elm.setPos(x - elm.w / 2, y0)
            x += inc_x

        # Arrange line positions
        self._terminal.process_callbacks(self.pos() + self._terminal.pos())

    def create_children_widgets(self, injections_by_tpe: Dict[DeviceType, List[FLUID_TYPES]]):
        """
        Create the icons of the elements that are attached to the API bus object
        Returns:
            Nothing
        """
        for tpe, dev_list in injections_by_tpe.items():

            if tpe == DeviceType.FluidPumpDevice:
                for elm in dev_list:
                    self.add_pump(elm)

            elif tpe == DeviceType.FluidTurbineDevice:
                for elm in dev_list:
                    self.add_turbine(elm)

            elif tpe == DeviceType.FluidP2XDevice:
                for elm in dev_list:
                    self.add_p2x(elm)

            else:
                raise Exception("Unknown device type:" + str(tpe))

        self.arrange_children()

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Fluid node")

        pl = menu.addAction('Plot profiles')
        plot_icon = QIcon()
        plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
        pl.setIcon(plot_icon)
        pl.triggered.connect(self.plot_profiles)

        arr = menu.addAction('Arrange')
        arr_icon = QIcon()
        arr_icon.addPixmap(QPixmap(":/Icons/icons/automatic_layout.svg"))
        arr.setIcon(arr_icon)
        arr.triggered.connect(self.arrange_children)

        ra3 = menu.addAction('Delete all the connections')
        del2_icon = QIcon()
        del2_icon.addPixmap(QPixmap(":/Icons/icons/delete_conn.svg"))
        ra3.setIcon(del2_icon)
        ra3.triggered.connect(self.delete_all_connections)

        da = menu.addAction('Delete')
        del_icon = QIcon()
        del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
        da.setIcon(del_icon)
        da.triggered.connect(self.remove)

        menu.addSection("Add")

        al = menu.addAction('Turbine')
        al_icon = QIcon()
        al_icon.addPixmap(QPixmap(":/Icons/icons/add_gen.svg"))
        al.setIcon(al_icon)
        al.triggered.connect(self.add_turbine)

        ash = menu.addAction('Pump')
        ash_icon = QIcon()
        ash_icon.addPixmap(QPixmap(":/Icons/icons/add_gen.svg"))
        ash.setIcon(ash_icon)
        ash.triggered.connect(self.add_pump)

        acg = menu.addAction('P2X')
        acg_icon = QIcon()
        acg_icon.addPixmap(QPixmap(":/Icons/icons/add_gen.svg"))
        acg.setIcon(acg_icon)
        acg.triggered.connect(self.add_p2x)

        menu.exec_(event.screenPos())

    def get_terminal(self) -> BarTerminalItem:
        """
        Get the hosting terminal of this bus object
        :return: TerminalItem
        """
        return self._terminal

    def add_object(self, api_obj: Union[None, EditableDevice] = None):
        """
        Add any recognized object
        :param api_obj: EditableDevice
        """

        if api_obj.device_type == DeviceType.FluidTurbineDevice:
            self.add_turbine(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.FluidPumpDevice:
            self.add_pump(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.FluidP2XDevice:
            self.add_p2x(api_obj=api_obj)

        else:
            raise Exception("Cannot add device of type {}".format(api_obj.device_type.value))

    def create_bus_if_necessary(self) -> Bus:
        """
        Create the internal electrical bus of the fluid node
        :return api_object.bus
        """

        if self.api_object.bus is None:
            # create the bus and assign it
            self.api_object.bus = self.editor.circuit.add_bus()

            # set the same name
            self.api_object.bus.name = "Bus of " + self.api_object.name

        return self.api_object.bus

    def add_turbine(self, api_obj: Union[None, FluidTurbine] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_fluid_turbine(node=self.api_object, api_obj=None)
            api_obj.generator = self.editor.circuit.add_generator(bus=self.create_bus_if_necessary())
            api_obj.generator.name = f"Turbine @{self.api_object.name}"

        _grph = FluidTurbineGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_pump(self, api_obj: Union[None, FluidPump] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_fluid_pump(node=self.api_object, api_obj=None)
            api_obj.generator = self.editor.circuit.add_generator(bus=self.create_bus_if_necessary())
            api_obj.generator.name = f"Pump @{self.api_object.name}"

        _grph = FluidPumpGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_p2x(self, api_obj: Union[None, FluidP2x] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_fluid_p2x(node=self.api_object, api_obj=None)
            api_obj.generator = self.editor.circuit.add_generator(bus=self.create_bus_if_necessary())
            api_obj.generator.name = f"P2X @{self.api_object.name}"

        _grph = FluidP2xGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def delete_all_connections(self):
        """
        Delete all bus connections
        """
        self._terminal.remove_all_connections()

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this fluid node',
                                 'Remove fluid node')
        else:
            ok = True

        if ok:
            self.delete_all_connections()

            for g in self.shunt_children:
                self.editor.remove_from_scene(g.nexus)

            self.editor.remove_element(device=self.api_object, graphic_object=self)

    def update_color(self):
        """
        Update the colour
        """
        self.set_tile_color(QBrush(ACTIVE['color']))

    def plot_profiles(self):
        """

        @return:
        """
        # get the index of this object
        i = self.editor.circuit.fluid_nodes.index(self.api_object)
        # self.editor.diagramScene.plot_bus(i, self.api_object)
