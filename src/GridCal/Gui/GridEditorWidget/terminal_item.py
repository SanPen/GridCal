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

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QCursor
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsEllipseItem

from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE


class TerminalItem(QGraphicsRectItem):
    """
    Represents a connection point to a subsystem
    """

    def __init__(self, name, editor=None, parent=None, h=10.0, w=10.0):
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
        self.parent = parent

        self.hosting_connections = list()

        self.editor = editor

        # Name:
        self.name = name
        self.posCallbacks = list()
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    @property
    def w(self):
        return self.rect().width()

    @property
    def h(self):
        return self.rect().height()

    @property
    def x(self):
        return self.pos().x()

    @property
    def y(self):
        return self.pos().y()

    @property
    def xc(self):
        return self.pos().x() - self.w / 2

    @property
    def yc(self):
        return self.pos().y() - self.h / 2

    def update(self):

        self.process_callbacks(self.parent.pos() + self.pos())

    def process_callbacks(self, value):
        """

        :param value:
        :return:
        """
        w = self.rect().width()
        h2 = self.rect().height() / 2.0
        n = len(self.posCallbacks)
        dx = w / (n + 1)
        for i, call_back in enumerate(self.posCallbacks):
            call_back(value + QPointF((i + 1) * dx, h2))

    def itemChange(self, change, value):
        """

        @param change:
        @param value: This is a QPointF object with the coordinates of the upper left corner of the TerminalItem
        @return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.process_callbacks(value)
            return value
        else:
            return super(TerminalItem, self).itemChange(change, value)

    def mousePressEvent(self, event):
        """
        Start a connection
        Args:
            event:

        Returns:

        """
        self.editor.start_connection(self)
        if self.editor.started_branch is not None:
            self.hosting_connections.append(self.editor.started_branch)

    def remove_all_connections(self):
        """
        Removes all the terminal connections
        Returns:

        """
        n = len(self.hosting_connections)
        for i in range(n - 1, -1, -1):
            self.hosting_connections[i].remove_widget()
            self.hosting_connections[i].remove(ask=False)
            self.hosting_connections.pop(i)


class HandleItem(QGraphicsEllipseItem):
    """
    A handle that can be moved by the mouse: Element to resize the boxes
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """
        QGraphicsEllipseItem.__init__(self, QRectF(-4, -4, 8, 8), parent)

        self.posChangeCallbacks = list()
        self.setBrush(Qt.red)
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(self.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setCursor(QCursor(Qt.SizeFDiagCursor))

    def itemChange(self, change, value):
        """

        @param change:
        @param value:
        @return:
        """
        if change == self.GraphicsItemChange.ItemPositionChange:
            x, y = value.x(), value.y()

            # This cannot be a signal because this is not a QObject
            for cb in self.posChangeCallbacks:
                res = cb(x, y)
                if res:
                    x, y = res
                    value = QPointF(x, y)
            return value

        # Call superclass method:
        return super(HandleItem, self).itemChange(change, value)

