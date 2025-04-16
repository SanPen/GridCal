# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Union, List, TYPE_CHECKING, Callable
import darkdetect
from PySide6.QtCore import Qt, QPointF, QLineF
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsItem, QGraphicsPolygonItem, QGraphicsItemGroup,
                               QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem)
from PySide6.QtGui import QColor, QPen, QPolygon
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

        self._parent = parent

        self._api_object: ALL_DEV_TYPES = api_object

        self._editor: Union[SchematicWidget, GridMapWidget] = editor

        self._draw_labels: bool = draw_labels

        # color
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']

    @property
    def api_object(self) -> ALL_DEV_TYPES:
        return self._api_object

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
        self._editor.update_label_drwaing_status(device=self.api_object, draw_labels=self._draw_labels)

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

    def delete_from_associations(self):
        """
        Delete this object from other associations, i.e. for a line, delete from the terminal connections
        :return:
        """
        pass

    def get_associated_widgets(self) -> List["GenericDiagramWidget"]:
        """
        Get a list of all graphical elements associated with this widget.
        In the case of a BusGraphicsItem, it will be all the shunt connections
        plus the LineGraphicItems connecting to it, etc.
        This function is meant to be overloaded.
        :return:
        """
        return list()

    def get_extra_graphics(self) -> List[QGraphicsItem]:
        """
        Get a list of all QGraphicsItem elements associated with this widget.
        In the case of a GeneratorGraphicsItem, it will be all the nexus
        This function is meant to be overloaded.
        :return:
        """
        return list()


class Polygon(QGraphicsPolygonItem):
    """
    PolygonItem
    """

    def __init__(self, parent, polygon: QPolygon, update_nexus_fcn: Callable[[QPointF], None]):
        """
        Constructor
        :param parent:
        """
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.setPolygon(polygon)
        self.update_nexus_fcn = update_nexus_fcn

    def setPen(self, pen: QPen):
        super().setPen(pen)
        pass

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.update_nexus_fcn(value)
        return super(QGraphicsPolygonItem, self).itemChange(change, value)


class Square(QGraphicsRectItem):
    """
    Square
    """

    def __init__(self, parent, h: int, w: int, label_letter: str, update_nexus_fcn: Callable[[QPointF], None]):
        """
        Constructor
        :param parent:
        """
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.setRect(0, 0, h, w)

        self.label = QGraphicsTextItem(label_letter, parent=self)
        self.label.setPos(h / 4, w / 5)
        self.update_nexus_fcn = update_nexus_fcn

    def setPen(self, pen: QPen):
        super().setPen(pen)
        self.label.setDefaultTextColor(pen.color())

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.update_nexus_fcn(value)
        return super(QGraphicsRectItem, self).itemChange(change, value)


class Circle(QGraphicsEllipseItem):
    """
    Circle
    """

    def __init__(self, parent, h: int, w: int, label_letter: str, update_nexus_fcn: Callable[[QPointF], None]):
        """
        Constructor
        :param parent:
        """
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.setRect(0, 0, h, w)

        self.label = QGraphicsTextItem(label_letter, parent=self)
        self.label.setPos(h / 4, w / 5)
        self.update_nexus_fcn = update_nexus_fcn

    def setPen(self, pen: QPen):
        super().setPen(pen)
        self.label.setDefaultTextColor(pen.color())

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.update_nexus_fcn(value)
        return super(QGraphicsEllipseItem, self).itemChange(change, value)


class Condenser(QGraphicsItemGroup):
    """
    Square
    """

    def __init__(self, parent, h: int, w: int, update_nexus_fcn: Callable[[QPointF], None]):
        """
        Constructor
        :param parent:
        """
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        lines_data = list()
        lines_data.append(QLineF(QPointF(w / 2, 0), QPointF(w / 2, h * 0.4)))
        lines_data.append(QLineF(QPointF(0, h * 0.4), QPointF(w, h * 0.4)))
        lines_data.append(QLineF(QPointF(0, h * 0.6), QPointF(w, h * 0.6)))
        lines_data.append(QLineF(QPointF(w / 2, h * 0.6), QPointF(w / 2, h)))
        lines_data.append(QLineF(QPointF(0, h * 1), QPointF(w, h * 1)))
        lines_data.append(QLineF(QPointF(w * 0.15, h * 1.1), QPointF(w * 0.85, h * 1.1)))
        lines_data.append(QLineF(QPointF(w * 0.3, h * 1.2), QPointF(w * 0.7, h * 1.2)))

        self.lines = list()
        for l in lines_data:
            l1 = QGraphicsLineItem(parent)
            l1.setLine(l)
            self.lines.append(l1)
            self.addToGroup(l1)

        self.update_nexus_fcn = update_nexus_fcn

    def setPen(self, pen: QPen):
        for l in self.lines:
            l.setPen(pen)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.update_nexus_fcn(value)
        return super(QGraphicsItemGroup, self).itemChange(change, value)


class Line(QGraphicsLineItem):
    """
    Line
    """

    def __init__(self, parent, update_nexus_fcn: Callable[[QPointF], None]):
        """
        Constructor
        :param parent:
        """
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.update_nexus_fcn = update_nexus_fcn

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Union[int, QPointF]) -> Union[int, QPointF]:
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self.update_nexus_fcn(value)
        return super(QGraphicsLineItem, self).itemChange(change, value)
