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
from typing import Union, Any, TYPE_CHECKING, Callable, Dict
from PySide6.QtCore import Qt, QPointF, QRectF, QRect
from PySide6.QtGui import QPen, QCursor
from PySide6.QtWidgets import (QGraphicsRectItem, QGraphicsItem, QGraphicsEllipseItem, QGraphicsSceneMouseEvent)

from GridCal.Gui.Diagrams.generic_graphics import ACTIVE

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
    from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
    from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer3w_graphics import Transformer3WGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Substation.busbar_graphics import BusBarGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Substation.cn_graphics import CnGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem


class BarTerminalItem(QGraphicsRectItem):
    """
    Represents a connection point to a subsystem
    """

    def __init__(self,
                 name: str,
                 editor: SchematicWidget,
                 parent: Union[None, BusGraphicItem, BusBarGraphicItem, Transformer3WGraphicItem, FluidNodeGraphicItem] = None,
                 h=10.0,
                 w=10.0):
        """

        @param name:
        @param editor:
        @param parent:
        """

        QGraphicsRectItem.__init__(self, QRectF(-6.0, -6.0, h, w), parent)
        self.setCursor(QCursor(Qt.CrossCursor))

        # Properties:
        self.color = ACTIVE['color']
        self.pen_width = 2
        self.style = ACTIVE['style']
        self.setBrush(Qt.darkGray)
        self.setPen(QPen(self.color, self.pen_width, self.style))

        # terminal parent object
        self.parent: Union[None, BusGraphicItem, Transformer3WGraphicItem, FluidNodeGraphicItem] = parent

        # object -> callback
        self._hosting_connections: Dict[LineGraphicTemplateItem, Callable[[QPointF], None]] = dict()

        self.editor = editor

        # Name:
        self.name = name
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def get_parent(self) -> Union[None, BusGraphicItem, Transformer3WGraphicItem]:
        """
        Returns the parent object
        :return: Union[None, BusGraphicItem, Transformer3WGraphicItem]
        """
        return self.parent

    @property
    def w(self) -> float:
        """
        Width
        """
        return self.rect().width()

    @property
    def h(self) -> float:
        """
        Height
        """
        return self.rect().height()

    @property
    def x(self) -> float:
        """
        x position
        """
        return self.pos().x()

    @property
    def y(self) -> float:
        """
        y position
        """
        return self.pos().y()

    @property
    def xc(self) -> float:
        """
        x-center
        :return:
        """
        return self.pos().x() - self.w / 2

    @property
    def yc(self) -> float:
        """
        Y-center
        :return:
        """
        return self.pos().y() - self.h / 2

    def add_hosting_connection(self,
                               graphic_obj: LineGraphicTemplateItem,
                               callback: Callable[[QPointF], None]):
        """
        Add object graphically connected to the graphical bus
        :param graphic_obj: LineGraphicTemplateItem (or child of this)
        :param callback: callback function
        """
        self._hosting_connections[graphic_obj] = callback

    def delete_hosting_connection(self, graphic_obj: LineGraphicTemplateItem):
        """
        Delete object graphically connected to the graphical bus
        :param graphic_obj: LineGraphicTemplateItem (or child of this)
        """
        if graphic_obj in self._hosting_connections.keys():
            del self._hosting_connections[graphic_obj]
        else:
            print(f'No such hosting connection {self.name} -> {graphic_obj}')

    def update(self, rect: Union[QRectF, QRect] = ...):
        """

        :param rect:
        :return:
        """
        self.process_callbacks(self.parent.pos() + self.pos())

    def process_callbacks(self, value: QPointF, scale: float = 1.0):
        """

        :param value:
        :param scale:
        :return:
        """
        w = self.rect().width()
        h2 = self.y + self.h / 2
        n = len(self._hosting_connections)
        dx = w / (n + 1)

        for i, (connection, call_back) in enumerate(self._hosting_connections.items()):
            call_back(value + QPointF((i + 1) * dx, h2))

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """

        @param change:
        @param value: This is a QPointF object with the coordinates of the upper left corner of the TerminalItem
        @return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.process_callbacks(value)
            return value
        else:
            return super(BarTerminalItem, self).itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Start a connection
        :param event: QGraphicsSceneMouseEvent
        """
        self.editor.start_connection(self)

    def remove_all_connections(self) -> None:
        """
        Removes all the terminal connections
        """
        for graphic_item, _ in self._hosting_connections.items():
            self.editor.remove_element(graphic_object=graphic_item, device=graphic_item.api_object)

        self._hosting_connections.clear()

    def __str__(self):

        if self.parent is None:
            return f"Terminal [{hex(id(self))}]"
        else:
            return f"Terminal {self.parent} [{hex(id(self))}]"

    def __repr__(self):
        return str(self)


class HandleItem(QGraphicsEllipseItem):
    """
    A handle that can be moved by the mouse: Element to resize the boxes
    """

    def __init__(self, parent: BarTerminalItem = None, callback: Callable = None) -> None:
        """

        @param parent:
        """
        QGraphicsEllipseItem.__init__(self, QRectF(-4, -4, 8, 8), parent)

        self.callback = callback

        self.setBrush(Qt.red)
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(self.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setCursor(QCursor(Qt.SizeFDiagCursor))

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any):
        """

        @param change:
        @param value:
        @return:
        """
        if change == self.GraphicsItemChange.ItemPositionChange:
            x, y = value.x(), value.y()

            # This cannot be a signal because this is not a QObject
            if self.callback is not None:
                res = self.callback(x, y)
                if res:
                    x, y = res
                    value = QPointF(x, y)
            return value

        # Call superclass method:
        return super(HandleItem, self).itemChange(change, value)


class RoundTerminalItem(QGraphicsEllipseItem):
    """
    Represents a connection point to a subsystem
    """

    def __init__(self,
                 name: str,
                 editor: SchematicWidget,
                 parent: Union[None, CnGraphicItem] = None,
                 h=10.0,
                 w=10.0):
        """

        @param name:
        @param editor:
        @param parent:
        """

        QGraphicsEllipseItem.__init__(self, QRectF(-6.0, -6.0, h, w), parent)
        self.setCursor(QCursor(Qt.CrossCursor))

        # Properties:
        self.color = ACTIVE['color']
        self.pen_width = 2
        self.style = ACTIVE['style']
        self.setBrush(Qt.darkGray)
        self.setPen(QPen(self.color, self.pen_width, self.style))

        # terminal parent object
        self.parent: Union[None, BusGraphicItem, Transformer3WGraphicItem, FluidNodeGraphicItem] = parent

        # object -> callback
        self._hosting_connections: Dict[LineGraphicTemplateItem, Callable[[float], None]] = dict()

        self.editor = editor

        # Name:
        self.name = name
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def get_parent(self) -> Union[None, BusGraphicItem, Transformer3WGraphicItem]:
        """
        Returns the parent object
        :return: Union[None, BusGraphicItem, Transformer3WGraphicItem]
        """
        return self.parent

    @property
    def w(self) -> float:
        """
        Width
        """
        return self.rect().width()

    @property
    def h(self) -> float:
        """
        Height
        """
        return self.rect().height()

    @property
    def x(self) -> int:
        """
        x position
        """
        return self.pos().x()

    @property
    def y(self) -> int:
        """
        y position
        """
        return self.pos().y()

    @property
    def xc(self) -> int:
        """
        x-center
        :return:
        """
        return self.pos().x() - self.w / 2

    @property
    def yc(self) -> int:
        """
        Y-center
        :return:
        """
        return self.pos().y() - self.h / 2

    def add_hosting_connection(self,
                               graphic_obj: LineGraphicTemplateItem,
                               callback: Callable[[float], None]):
        """
        Add object graphically connected to the graphical bus
        :param graphic_obj: LineGraphicTemplateItem (or child of this)
        :param callback: callback function
        """
        self._hosting_connections[graphic_obj] = callback

    def delete_hosting_connection(self, graphic_obj: LineGraphicTemplateItem):
        """
        Delete object graphically connected to the graphical bus
        :param graphic_obj: LineGraphicTemplateItem (or child of this)
        """
        if graphic_obj in self._hosting_connections.keys():
            del self._hosting_connections[graphic_obj]
        else:
            print(f'No such hosting connection {self.name} -> {graphic_obj}')

    def update(self, rect: Union[QRectF, QRect] = ...):
        """

        :param rect:
        :return:
        """
        self.process_callbacks(parent_pos=self.parent.pos())

    def process_callbacks(self, parent_pos: QPointF, mul: float = 1.0):
        """
        Send the callbacks, ussually setEndPos or setStartPos functions from the line template
        :param parent_pos: Parent position
        :param mul: Multiplier
        """
        scene_pos = parent_pos + self.pos() * mul  # + QPointF(self.w / 2, self.h / 2)

        for i, (connection, call_back) in enumerate(self._hosting_connections.items()):
            call_back(scene_pos)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: QPointF) -> QPointF:
        """

        @param change:
        @param value: This is a QPointF object with the coordinates of the upper left corner of the TerminalItem
        @return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.process_callbacks(parent_pos=value, mul=0.5)
            return value
        else:
            return super(RoundTerminalItem, self).itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Start a connection
        :param event: QGraphicsSceneMouseEvent
        """
        self.editor.start_connection(self)

    def remove_all_connections(self) -> None:
        """
        Removes all the terminal connections
        """
        for graphic_item, _ in self._hosting_connections.items():
            self.editor.remove_element(graphic_object=graphic_item, device=graphic_item.api_object)

        self._hosting_connections.clear()

    def __str__(self):

        if self.parent is None:
            return f"Round Terminal [{hex(id(self))}]"
        else:
            return f"Round Terminal {self.parent} [{hex(id(self))}]"

    def __repr__(self):
        return str(self)
