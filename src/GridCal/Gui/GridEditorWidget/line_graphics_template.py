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
import numpy as np

from typing import Union
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QPoint, QLineF, QPointF, QRectF
from PySide6.QtGui import QPen, QCursor, QIcon, QPixmap, QBrush, QColor, QTransform, QPolygonF
from PySide6.QtWidgets import QMenu, QGraphicsLineItem, QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsEllipseItem
from GridCal.Gui.GeneralDialogues import InputNumberDialogue
from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, FONT_SCALE, EMERGENCY, OTHER
from GridCal.Gui.GridEditorWidget.bus_graphics import TerminalItem
from GridCal.Gui.GridEditorWidget.line_editor import LineEditor
from GridCal.Gui.GridEditorWidget.messages import yes_no_question, warning_msg
from GridCal.Gui.GuiFunctions import BranchObjectModel
from GridCal.Engine.Core.Devices.Branches.line import Line, SequenceLineType
from GridCal.Engine.Core.Devices.Branches.transformer import Transformer2W
from GridCal.Engine.Simulations.Topology.topology_driver import reduce_grid_brute


class ArrowHead(QGraphicsPolygonItem):
    """
    This is the arrow object
    """

    def __init__(self,
                 parent: QGraphicsLineItem,
                 arrow_size: int,
                 position: float = 0.9,
                 draw_below: bool = False,
                 sign: float = 1):

        QGraphicsPolygonItem.__init__(self, parent=parent)

        self.parent: QGraphicsLineItem = parent
        self.arrow_size: int = arrow_size
        self.position: float = position
        self.draw_below: bool = draw_below
        self.sign: float = sign

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        # self.setPen(QPen(color, w, style))
        self.setPen(Qt.NoPen)
        self.setBrush(color)

    def set_value(self, value: float, redraw=True):
        """
        Set the sign with a value
        :param value: any real value
        :param redraw: redraw after the sign update
        """
        self.sign = 1.0 if value >= 0 else -1.0

        if redraw:
            self.redraw()

    def redraw(self) -> None:
        """
        Redraw the arrow
        """
        line = self.parent.line()

        # the angle is added 180º if the sign is negative
        angle = line.angle() if self.sign >= 0 else line.angle() + 180.0

        p2 = -self.arrow_size if self.draw_below else self.arrow_size

        arrow_position = line.p1() + (line.p2() - line.p1()) * self.position
        arrow_p1 = arrow_position - QTransform().rotate(-angle).map(QPointF(self.arrow_size, 0))
        arrow_p2 = arrow_position - QTransform().rotate(-angle).map(QPointF(self.arrow_size, p2))
        arrow_polygon = QPolygonF([arrow_position, arrow_p1, arrow_p2])

        self.setPolygon(arrow_polygon)


class TransformerSymbol(QGraphicsRectItem):
    """
    TransformerSymbol
    """

    def __init__(self, parent, pen_width, h=80, w=80):
        QGraphicsRectItem.__init__(self, parent=parent)

        d = w / 2

        self.parent = parent

        self.width = pen_width
        self.pen_width = pen_width
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']

        self.setPen(QPen(Qt.transparent))
        self.setRect(QRectF(0, 0, w, h))

        self.c0 = QGraphicsEllipseItem(0, 0, d, d, parent=self)
        self.c1 = QGraphicsEllipseItem(0, 0, d, d, parent=self)
        self.c2 = QGraphicsEllipseItem(0, 0, d, d, parent=self)

        self.c0.setPen(QPen(Qt.transparent, self.width, self.style))
        self.c2.setPen(QPen(self.color, self.width, self.style))
        self.c1.setPen(QPen(self.color, self.width, self.style))

        self.c0.setBrush(QBrush(Qt.white))
        self.c2.setBrush(QBrush(Qt.white))

        self.c0.setPos(w * 0.35 - d / 2, h * 0.5 - d / 2)
        self.c1.setPos(w * 0.35 - d / 2, h * 0.5 - d / 2)
        self.c2.setPos(w * 0.65 - d / 2, h * 0.5 - d / 2)

        self.c0.setZValue(0)
        self.c1.setZValue(2)
        self.c2.setZValue(1)

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        self.c2.setPen(QPen(color, w, style))
        self.c1.setPen(QPen(color, w, style))

    def set_pen(self, pen: QPen):
        """

        :param pen:
        :return:
        """
        self.setPen(pen)
        self.c1.setPen(pen)
        self.c2.setPen(pen)

    def setToolTipText(self, toolTip: str):
        """
        Set branch tool tip text
        Args:
            toolTip: text
        """
        self.setToolTip(toolTip)
        self.c0.setToolTip(toolTip)
        self.c1.setToolTip(toolTip)
        self.c2.setToolTip(toolTip)

    def redraw(self):
        h = self.parent.pos2.y() - self.parent.pos1.y()
        b = self.parent.pos2.x() - self.parent.pos1.x()
        ang = np.arctan2(h, b)
        h2 = self.rect().height() / 2.0
        w2 = self.rect().width() / 2.0
        a = h2 * np.cos(ang) - w2 * np.sin(ang)
        b = w2 * np.sin(ang) + h2 * np.cos(ang)

        center = (self.parent.pos1 + self.parent.pos2) * 0.5 - QPointF(a, b)

        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(np.rad2deg(ang))
        self.setTransform(transform)


class LineGraphicTemplateItem(QGraphicsLineItem):
    """
    LineGraphicItem
    """

    def __init__(self,
                 fromPort: TerminalItem,
                 toPort: Union[TerminalItem, None],
                 diagramScene,
                 width=5,
                 api_object: Union[Line, Transformer2W, None] = None):
        """

        :param fromPort:
        :param toPort:
        :param diagramScene:
        :param width:
        :param api_object: 
        """
        QGraphicsLineItem.__init__(self)

        self.api_object = api_object

        if isinstance(api_object, Transformer2W):
            self.symbol = TransformerSymbol(parent=self, pen_width=width, h=80, w=80)
        else:
            self.symbol = None

        self.width = width
        self.pen_width = width
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']

        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.pos1 = None
        self.pos2 = None
        self.fromPort: Union[TerminalItem, None] = None
        self.toPort: Union[TerminalItem, None] = None
        self.diagramScene = diagramScene

        if fromPort:
            self.setFromPort(fromPort)

        if toPort:
            self.setToPort(toPort)

        # arrows
        self.view_arrows = True
        self.arrow_from_1 = ArrowHead(parent=self, arrow_size=10, position=0.15, draw_below=False)
        self.arrow_from_2 = ArrowHead(parent=self, arrow_size=10, position=0.15, draw_below=True)
        self.arrow_to_1 = ArrowHead(parent=self, arrow_size=10, position=0.85, draw_below=False)
        self.arrow_to_2 = ArrowHead(parent=self, arrow_size=10, position=0.85, draw_below=True)

        # add the line and it possible children to the scene
        self.diagramScene.addItem(self)

        if fromPort and toPort:
            self.redraw()

        # set coulours
        self.recolour_mode()

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

        self.set_colour(self.color, self.width, self.style)

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        self.setPen(QPen(color, w, style))
        self.arrow_from_1.set_colour(color, w, style)
        self.arrow_from_2.set_colour(color, w, style)
        self.arrow_to_1.set_colour(color, w, style)
        self.arrow_to_2.set_colour(color, w, style)

        if self.symbol is not None:
            self.symbol.set_colour(color, w, style)

    def setToolTipText(self, toolTip: str):
        """
        Set branch tool tip text
        Args:
            toolTip: text
        """
        self.setToolTip(toolTip)

        if self.symbol is not None:
            self.symbol.setToolTipText(toolTip=toolTip)

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        if self.api_object is not None:
            mdl = BranchObjectModel([self.api_object], self.api_object.editable_headers,
                                    parent=self.diagramScene.parent().object_editor_table,
                                    editable=True, transposed=True,
                                    non_editable_attributes=self.api_object.non_editable_attributes)

            self.diagramScene.parent().object_editor_table.setModel(mdl)

    def remove_widget(self):
        """
        Remove this object in the diagram
        @return:
        """
        self.diagramScene.removeItem(self)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.diagramScene.circuit.has_time_series:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.diagramScene.set_active_status_to_profile(self.api_object, override_question=True)

    def set_enable(self, val=True):
        """
        Set the enable value, graphically and in the API
        @param val:
        @return:
        """
        self.api_object.active = val
        if self.api_object is not None:
            if self.api_object.active:
                self.style = ACTIVE['style']
                self.color = ACTIVE['color']
            else:
                self.style = DEACTIVATED['style']
                self.color = DEACTIVATED['color']
        else:
            self.style = OTHER['style']
            self.color = OTHER['color']

        if self.symbol:
            self.symbol.setBrush(self.color)
            if self.api_object.active:
                self.symbol.setPen(QPen(ACTIVE['color']))
            else:
                self.symbol.setPen(QPen(DEACTIVATED['color']))

        # Set pen for everyone
        self.set_pen(QPen(self.color, self.width, self.style))

    def plot_profiles(self):
        """
        Plot the time series profiles
        @return:
        """
        # get the index of this object
        i = self.diagramScene.circuit.get_branches().index(self.api_object)
        self.diagramScene.plot_branch(i, self.api_object)

    def setFromPort(self, fromPort):
        """
        Set the From terminal in a connection
        @param fromPort:
        @return:
        """
        self.fromPort = fromPort
        if self.fromPort:
            self.pos1 = fromPort.scenePos()
            self.fromPort.posCallbacks.append(self.setBeginPos)
            self.fromPort.parent.setZValue(0)

    def setToPort(self, toPort):
        """
        Set the To terminal in a connection
        @param toPort:
        @return:
        """
        self.toPort = toPort
        if self.toPort:
            self.pos2 = toPort.scenePos()
            self.toPort.posCallbacks.append(self.setEndPos)
            self.toPort.parent.setZValue(0)

    def setEndPos(self, endpos):
        """
        Set the starting position
        @param endpos:
        @return:
        """
        self.pos2 = endpos
        self.redraw()

    def setBeginPos(self, pos1):
        """
        Set the starting position
        @param pos1:
        @return:
        """
        self.pos1 = pos1
        self.redraw()

    def redraw(self):
        """
        Redraw the line with the given positions
        @return:
        """
        if self.pos1 is not None and self.pos2 is not None:

            # Set position
            self.setLine(QLineF(self.pos1, self.pos2))

            # set Z-Order (to the back)
            self.setZValue(-1)

            if self.api_object is not None:

                # arrows
                if self.view_arrows:
                    self.arrow_from_1.redraw()
                    self.arrow_from_2.redraw()
                    self.arrow_to_1.redraw()
                    self.arrow_to_2.redraw()

                if self.symbol is not None:
                    self.symbol.redraw()

    def set_pen(self, pen):
        """
        Set pen to all objects
        Args:
            pen:
        """
        self.setPen(pen)

        if self.symbol:
            self.symbol.set_pen(pen)

    def assign_rate_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.diagramScene.set_rate_to_profile(self.api_object)

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.diagramScene.set_active_status_to_profile(self.api_object)

    def set_arrows_with_power(self, Sf: complex, St: complex) -> None:
        """
        Set the arrow directions
        :param Sf: Complex power from
        :param St: Complex power to
        """

        if Sf is not None:
            if St is None:
                St = -Sf

            self.arrow_from_1.set_value(Sf.real, True)
            self.arrow_from_2.set_value(Sf.imag, True)
            self.arrow_to_1.set_value(-St.real, True)
            self.arrow_to_2.set_value(-St.imag, True)
