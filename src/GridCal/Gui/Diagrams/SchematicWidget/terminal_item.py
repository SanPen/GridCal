# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Union, Any, TYPE_CHECKING, Callable, Dict
from PySide6.QtCore import Qt, QPointF, QRectF, QRect
from PySide6.QtGui import QPen, QCursor
from PySide6.QtWidgets import (QGraphicsRectItem, QGraphicsItem, QGraphicsEllipseItem, QGraphicsSceneMouseEvent)
from GridCalEngine.enumerations import TerminalType

from GridCal.Gui.Diagrams.generic_graphics import ACTIVE

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
    from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
    from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer3w_graphics import Transformer3WGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Branches.vsc_graphics_3term import VscGraphicItem3Term
    from GridCal.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
    from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem


class BarTerminalItem(QGraphicsRectItem):
    """
    Represents a connection point to a subsystem
    """

    def __init__(self,
                 name: str,
                 editor: SchematicWidget,
                 parent: Union[
                     None, BusGraphicItem, Transformer3WGraphicItem, FluidNodeGraphicItem] = None,
                 h=10.0,
                 w=10.0):
        """

        :param name:
        :param editor:
        :param parent:
        :param h:
        :param w:
        """

        QGraphicsRectItem.__init__(self, QRectF(-6.0, -6.0, h, w), parent)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        # Properties:
        self.color = ACTIVE['color']
        self.pen_width = 2
        self.style = ACTIVE['style']
        self.setBrush(Qt.GlobalColor.darkGray)
        self.setPen(QPen(self.color, self.pen_width, self.style))

        # terminal parent object
        self.parent: Union[BusGraphicItem, Transformer3WGraphicItem, FluidNodeGraphicItem] = parent

        # object -> callback
        self._hosting_connections: Dict[LineGraphicTemplateItem, Callable[[QPointF], None]] = dict()

        self.editor = editor

        # Name:
        self.name = name
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def get_parent(self) -> Union[None, BusGraphicItem, Transformer3WGraphicItem, VscGraphicItem3Term]:
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

    @property
    def hosting_connections(self):
        """
        Getter for hosting connections
        :return:
        """
        return self._hosting_connections

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

    def get_hosted_graphics(self) -> List[LineGraphicTemplateItem]:
        """
        Get hosted graphics
        :return:
        """
        return [graphic_obj for graphic_obj in self._hosting_connections.keys()]

    def update(self, rect: Union[QRectF, QRect] = ...):
        """

        :param rect:
        :return:
        """
        # TODO: Take into account that the parent may be rotated, try to use Qt's translation formulas
        self.process_callbacks(self.scenePos())

    def get_center_pos(self, value: QPointF):
        h2 = self.h / 2.0
        w2 = self.w / 2.0
        center = QPointF(w2, h2)
        return value + center

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

    def remove_all_connections(self, delete_from_db: bool) -> None:
        """
        Removes all the terminal connections
        """
        for graphic_item, _ in self._hosting_connections.items():
            self.editor.remove_element(graphic_object=graphic_item,
                                       device=graphic_item.api_object,
                                       delete_from_db=delete_from_db)

        self.clear()

    def clear(self):
        self._hosting_connections.clear()

    def __str__(self):

        if self.parent is None:
            return f"Terminal [{hex(id(self))}]"
        else:
            return f"Terminal {self.parent} [{hex(id(self))}]"

    def __repr__(self):
        return str(self)


class RoundTerminalItem(QGraphicsEllipseItem):
    """
    Represents a connection point to a subsystem
    """

    def __init__(self,
                 name: str,
                 editor: SchematicWidget,
                 parent: Union[Transformer3WGraphicItem, VscGraphicItem3Term],
                 terminal_type: TerminalType = TerminalType.OTHER,
                 h=10.0,
                 w=10.0):
        """

        :param name:
        :param editor:
        :param parent:
        :param terminal_type:
        :param h:
        :param w:
        """

        QGraphicsEllipseItem.__init__(self, QRectF(0, 0, h, w), parent)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        # Properties:
        self.color = ACTIVE['color']
        self.pen_width = 2
        self.style = ACTIVE['style']
        self.setBrush(Qt.GlobalColor.darkGray)
        self.setPen(QPen(self.color, self.pen_width, self.style))

        self.terminal_type = terminal_type

        h2 = self.h / 2.0
        w2 = self.w / 2.0
        self.center = QPointF(w2, h2)

        # terminal parent object
        self.parent: Union[BusGraphicItem, Transformer3WGraphicItem, FluidNodeGraphicItem] = parent

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
        return self.pos().x() - self.w / 2.0

    @property
    def yc(self) -> float:
        """
        Y-center
        :return:
        """
        return self.pos().y() - self.h / 2.0

    @property
    def hosting_connections(self):
        """
        Getter for hosting connections
        :return:
        """
        return self._hosting_connections

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

    def get_hosted_graphics(self) -> List[LineGraphicTemplateItem]:
        """
        Get hosted graphics
        :return:
        """
        return [graphic_obj for graphic_obj in self._hosting_connections.keys()]

    def update(self, rect: Union[QRectF, QRect] = ...):
        """

        :param rect:
        :return:
        """
        # TODO: Take into account that the parent may be rotated, try to use Qt's translation formulas
        self.process_callbacks(self.scenePos())

    def get_center_pos(self, value: QPointF):
        return value + self.center

    def process_callbacks(self, value: QPointF):
        """
        Send the callbacks, usually setEndPos or setStartPos functions from the line template
        :param value: Parent position
        """

        for i, (connection, call_back) in enumerate(self._hosting_connections.items()):
            call_back(value + self.center)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: QPointF) -> QPointF:
        """

        @param change:
        @param value: This is a QPointF object with the coordinates of the upper left corner of the TerminalItem
        @return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.process_callbacks(value)
            return value
        else:
            return super(RoundTerminalItem, self).itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Start a connection
        :param event: QGraphicsSceneMouseEvent
        """
        self.editor.start_connection(self)

    def remove_all_connections(self, delete_from_db: bool = True) -> None:
        """
        Removes all the terminal connections
        """
        for graphic_item, _ in self._hosting_connections.items():
            self.editor.remove_element(graphic_object=graphic_item,
                                       device=graphic_item.api_object,
                                       delete_from_db=delete_from_db)

        self.clear()

    def clear(self):
        self._hosting_connections.clear()

    def __str__(self):

        if self.parent is None:
            return f"Round Terminal [{hex(id(self))}]"
        else:
            return f"Round Terminal {self.parent} [{hex(id(self))}]"

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

        self.setBrush(Qt.GlobalColor.red)
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(self.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))

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
