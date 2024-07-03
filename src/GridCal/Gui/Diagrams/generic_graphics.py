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
from typing import Union, TYPE_CHECKING
import darkdetect
from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsItem, QGraphicsPolygonItem,
                               QGraphicsRectItem, QGraphicsEllipseItem)
from PySide6.QtGui import QColor
from GridCalEngine.Devices.types import ALL_DEV_TYPES

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget

try:
    IS_DARK = darkdetect.theme() == "Dark"
except ImportError:
    IS_DARK = False

# Declare colors
ACTIVE = {'style': Qt.SolidLine,
          'color': Qt.white if IS_DARK else Qt.black,
          'text': Qt.white if IS_DARK else Qt.black,
          'backgound': Qt.black if IS_DARK else Qt.white,
          'fluid': QColor(0, 170, 212, 255)}

DEACTIVATED = {'style': Qt.DashLine, 'color': Qt.gray}
EMERGENCY = {'style': Qt.SolidLine, 'color': Qt.yellow}
OTHER = ACTIVE
FONT_SCALE = 1.9


def set_dark_mode() -> None:
    """
    Set the dark mode
    """
    IS_DARK = True
    ACTIVE['color'] = Qt.white
    ACTIVE['text'] = Qt.white


def set_light_mode() -> None:
    """
    Set the light mode
    """
    IS_DARK = False
    ACTIVE['color'] = Qt.black
    ACTIVE['text'] = Qt.black


def is_dark_mode() -> bool:
    """

    :return:
    """
    return IS_DARK


if IS_DARK:
    set_dark_mode()
else:
    set_light_mode()


class Polygon(QGraphicsPolygonItem):
    """
    PolygonItem
    """

    def __init__(self, parent):
        """
        Constructor
        :param parent:
        """
        QGraphicsPolygonItem.__init__(self, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.parentItem().update_nexus(value)
        return super(QGraphicsPolygonItem, self).itemChange(change, value)


class Square(QGraphicsRectItem):
    """
    Square
    """

    def __init__(self, parent):
        """
        Constructor
        :param parent:
        """
        QGraphicsRectItem.__init__(self, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.parentItem().update_nexus(value)
        return super(QGraphicsRectItem, self).itemChange(change, value)


class Circle(QGraphicsEllipseItem):
    """
    Circle
    """

    def __init__(self, parent):
        """
        Constructor
        :param parent:
        """
        QGraphicsEllipseItem.__init__(self, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.parentItem().update_nexus(value)
        return super(QGraphicsEllipseItem, self).itemChange(change, value)


class Line(QGraphicsLineItem):
    """
    Line
    """

    def __init__(self, parent):
        """
        Constructor
        :param parent:
        """
        QGraphicsLineItem.__init__(self, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.parentItem().update_nexus(value)
        return super(QGraphicsLineItem, self).itemChange(change, value)


class GenericDiagramWidget:
    """
    Generic DataBase Widget
    """

    def __init__(self,
                 parent,
                 api_object: ALL_DEV_TYPES,
                 editor: Union[SchematicWidget, GridMapWidget],
                 draw_labels: bool):
        """
        Constructor
        :param parent:
        :param api_object: Any database object
        :param editor: DiagramEditorWidget
        :param draw_labels:
        """

        self.parent = parent

        self.api_object: ALL_DEV_TYPES = api_object

        self.editor: Union[SchematicWidget, GridMapWidget] = editor

        self._draw_labels: bool = draw_labels

        # color
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']

    @property
    def draw_labels(self) -> bool:
        """
        draw labels getter
        :return: Bool
        """
        return self._draw_labels

    @draw_labels.setter
    def draw_labels(self, value: bool):
        """
        Draw labels setter, it updates the diagram
        :param value: boolean
        """
        self._draw_labels = value

        # update editor diagram position
        self.editor.update_label_drwaing_status(device=self.api_object, draw_labels=self._draw_labels)

    def recolour_mode(self) -> None:
        """
        Change the colour according to the system theme
        """
        if self.api_object is not None:
            if hasattr(self.api_object, 'active'):
                if self.api_object.active:
                    self.color = ACTIVE['color']
                    self.style = ACTIVE['style']
                else:
                    self.color = DEACTIVATED['color']
                    self.style = DEACTIVATED['style']
            else:
                self.color = ACTIVE['color']
                self.style = ACTIVE['style']
        else:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']

    def enable_label_drawing(self):
        """

        :return:
        """
        self.draw_labels = True

    def disable_label_drawing(self):
        """

        :return:
        """
        self.draw_labels = False

    def enable_disable_label_drawing(self):
        """

        :return:
        """
        self.draw_labels = not self.draw_labels
