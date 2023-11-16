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
import darkdetect
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QPushButton, QGraphicsLineItem, QGraphicsItem, QVBoxLayout, QGraphicsPolygonItem,
                               QDialog, QGraphicsRectItem, QGraphicsEllipseItem)

try:
    is_dark = darkdetect.theme() == "Dark"
except ImportError:
    is_dark = False

# Declare colors
ACTIVE = {'style': Qt.SolidLine,
          'color': Qt.white if is_dark else Qt.black,
          'text': Qt.white if is_dark else Qt.black}

DEACTIVATED = {'style': Qt.DashLine, 'color': Qt.gray}
EMERGENCY = {'style': Qt.SolidLine, 'color': Qt.yellow}
OTHER = ACTIVE
FONT_SCALE = 1.9


def set_dark_mode():
    """
    Set the dark mode
    """
    is_dark = True
    ACTIVE['color'] = Qt.white
    ACTIVE['text'] = Qt.white


def set_light_mode():
    """
    Set the light mode
    """
    is_dark = False
    ACTIVE['color'] = Qt.black
    ACTIVE['text'] = Qt.black


class LineUpdateMixin:

    def __init__(self, parent):
        super(LineUpdateMixin, self).__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.parentItem().update_line(value)
        return super(LineUpdateMixin, self).itemChange(change, value)


class Polygon(LineUpdateMixin, QGraphicsPolygonItem):
    pass


class Square(LineUpdateMixin, QGraphicsRectItem):
    pass


class Circle(LineUpdateMixin, QGraphicsEllipseItem):
    pass


class Line(LineUpdateMixin, QGraphicsLineItem):
    pass


class ParameterDialog(QDialog):
    """
    ParameterDialog
    """

    def __init__(self, parent=None):
        super(ParameterDialog, self).__init__(parent)
        self.button = QPushButton('Ok', self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.button)
        self.button.clicked.connect(self.OK)

    def OK(self):
        self.close()
