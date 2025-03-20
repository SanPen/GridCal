# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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

TRANSPARENT = QColor(0, 0, 0, 0)
WHITE = QColor(255, 255, 255, 255)
BLACK = QColor(0, 0, 0, 255)
GRAY = QColor(115, 115, 115, 255)
YELLOW = QColor(255, 247, 0, 255)

# Declare colors
ACTIVE = {'style': Qt.PenStyle.SolidLine,
          'color': WHITE if IS_DARK else BLACK,
          'text': WHITE if IS_DARK else BLACK,
          'background': BLACK if IS_DARK else WHITE,
          'fluid': QColor(0, 170, 212, 255)}

DEACTIVATED = {'style': Qt.PenStyle.DashLine, 'color': GRAY}
EMERGENCY = {'style': Qt.PenStyle.SolidLine, 'color': YELLOW}
OTHER = ACTIVE
FONT_SCALE = 1.9


def set_dark_mode() -> None:
    """
    Set the dark mode
    """
    ACTIVE['color'] = WHITE
    ACTIVE['text'] = WHITE


def set_light_mode() -> None:
    """
    Set the light mode
    """
    ACTIVE['color'] = BLACK
    ACTIVE['text'] = BLACK


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
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
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
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
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
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
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
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
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
