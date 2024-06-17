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
import sys
import numpy as np
from typing import Union, TYPE_CHECKING
from PySide6.QtCore import Qt, QLineF, QPointF, QRectF
from PySide6.QtGui import QPen, QCursor, QPixmap, QBrush, QColor, QTransform, QPolygonF
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsRectItem, QGraphicsPolygonItem,
                               QGraphicsEllipseItem, QGraphicsSceneMouseEvent, QGraphicsTextItem)
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER, GenericDiagramWidget
from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from GridCal.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Substation.cn_graphics import CnGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Substation.busbar_graphics import BusBarGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
from GridCal.Gui.messages import yes_no_question

from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.Devices.Substation.busbar import BusBar
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Branches.winding import Winding
from GridCalEngine.Devices.Branches.vsc import VSC
from GridCalEngine.Devices.Branches.upfc import UPFC
from GridCalEngine.Devices.Branches.switch import Switch
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.series_reactance import SeriesReactance
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.Devices.Fluid.fluid_path import FluidPath
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
    from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer3w_graphics import Transformer3WGraphicItem


class ArrowHead(QGraphicsPolygonItem):
    """
    This is the arrow object
    """

    def __init__(self,
                 parent: QGraphicsLineItem,
                 arrow_size: int,
                 position: float = 0.9,
                 under: bool = False,
                 backwards: bool = False,
                 separation: int = 5,
                 show_text: bool = True):
        """
        Constructor
        :param parent: Parent line
        :param arrow_size: Size of the arrow
        :param position: proportion of the line where to locate the arrow
        :param under: Is it under?
        :param backwards: Is it backwards?
        :param separation: Separation
        :param show_text: Show the label?
        """
        QGraphicsPolygonItem.__init__(self, parent=parent)

        self.parent: QGraphicsLineItem = parent
        self.arrow_size: int = arrow_size
        self.position: float = position
        self.under: bool = under
        self.backwards: float = backwards
        self.sep = separation

        self.label = QGraphicsTextItem(self)
        self.label.setPlainText("")
        self.show_text = show_text

        self.w = arrow_size
        self.h = arrow_size

        self.setPen(Qt.NoPen)

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        # self.setPen(QPen(color, w, style))
        # self.setPen(Qt.NoPen)
        self.setBrush(color)
        self.label.setDefaultTextColor(color)

    def set_value(self, value: float, redraw=True, backwards=False, name="", units="", format_str="{:10.2f}",
                  draw_label: bool = True):
        """
        Set the sign with a value
        :param value: any real value
        :param redraw: redraw after the sign update
        :param backwards: draw backwards
        :param name: name of the displayed magnitude (i.e. Pf)
        :param units: the units of the displayed magnitude (i.e MW)
        :param format_str: the formatting string of the displayed magnitude
        :param draw_label: Draw label
        """
        # self.backwards = value < 0
        self.backwards = backwards

        self.label.setVisible(draw_label)
        if draw_label:
            x = format_str.format(value)
            msg = f'{name}:{x} {units}'
            self.label.setPlainText(msg)
            self.setToolTip(msg)

        if redraw:
            self.redraw()

    def redraw(self) -> None:
        """
        Redraw the arrow
        """
        line = self.parent.line()

        # the angle is added 180º if the sign is negative
        angle = - line.angle()
        base_pt = line.p1() + (line.p2() - line.p1()) * self.position

        p1 = -self.arrow_size if self.backwards else self.arrow_size
        p2 = -self.arrow_size if self.under else self.arrow_size
        arrow_p1 = base_pt - QTransform().rotate(angle).map(QPointF(p1, 0))
        arrow_p2 = base_pt - QTransform().rotate(angle).map(QPointF(p1, p2))
        arrow_polygon = QPolygonF([base_pt, arrow_p1, arrow_p2])

        self.setPolygon(arrow_polygon)

        if self.show_text:
            a = angle + 180 if 90 < line.angle() <= 270 else angle  # this keep the labels upside
            label_p = base_pt - QTransform().rotate(a).map(QPointF(0, -10 if self.under else 35))
            self.label.setPos(label_p)
            self.label.setRotation(a)


class TransformerSymbol(QGraphicsRectItem):
    """
    TransformerSymbol
    """

    def __init__(self, parent, pen_width: int, h=80, w=80):
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
        """

        :return:
        """
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


class VscSymbol(QGraphicsRectItem):
    """
    VscSymbol
    """

    def __init__(self, parent, pen_width, h=48, w=48, icon_route=":/Icons/icons/vsc.svg"):
        QGraphicsRectItem.__init__(self, parent=parent)

        self.parent = parent

        self.width = pen_width
        self.pen_width = pen_width
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']

        self.setPen(QPen(Qt.transparent))
        self.setRect(QRectF(0, 0, w, h))

        graphic = QGraphicsRectItem(QRectF(0, 0, w, h), parent=self)
        graphic.setBrush(QBrush(QPixmap(icon_route)))
        graphic.setPen(QPen(Qt.transparent, self.width, self.style))

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        self.setBrush(color)
        self.setPen(QPen(color, w, style))

    def set_pen(self, pen: QPen):
        """

        :param pen:
        :return:
        """
        self.setPen(pen)

    def setToolTipText(self, toolTip: str):
        """
        Set branch tool tip text
        Args:
            toolTip: text
        """
        self.setToolTip(toolTip)

    def redraw(self):
        """

        :return:
        """
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


class UpfcSymbol(VscSymbol):
    """
    UpfcSymbol
    """

    def __init__(self, parent, pen_width, h=48, w=48):
        VscSymbol.__init__(self, parent=parent, pen_width=pen_width, h=h, w=w, icon_route=":/Icons/icons/upfc.svg")


class SeriesReactanceSymbol(VscSymbol):
    """
    UpfcSymbol
    """

    def __init__(self, parent, pen_width, h=30, w=30):
        VscSymbol.__init__(self, parent=parent, pen_width=pen_width, h=h, w=w,
                           icon_route=":/Icons/icons/reactance.svg")


class SwitchSymbol(VscSymbol):
    """
    UpfcSymbol
    """

    def __init__(self, parent, pen_width, h=30, w=30):
        VscSymbol.__init__(self, parent=parent, pen_width=pen_width, h=h, w=w,
                           icon_route=":/Icons/icons/switch.svg")


class HvdcSymbol(QGraphicsRectItem):
    """
    HvdcSymbol
    """

    def __init__(self, parent, pen_width, h=30, w=30):
        QGraphicsRectItem.__init__(self, parent=parent)

        w2 = int(w / 2)
        self.parent = parent

        self.width = pen_width
        self.pen_width = pen_width
        self.color = ACTIVE['color']
        self.style = ACTIVE['style']

        self.setPen(QPen(Qt.transparent))
        self.setRect(QRectF(0, 0, w, h))

        offset = 3
        t_points = QPolygonF()
        t_points.append(QPointF(0, offset))
        t_points.append(QPointF(w - offset, w2))
        t_points.append(QPointF(0, w - offset))

        triangle = QGraphicsPolygonItem(self)
        triangle.setPolygon(t_points)
        triangle.setPen(QPen(Qt.white))
        triangle.setBrush(QBrush(Qt.white))

        line = QGraphicsRectItem(QRectF(h - offset, offset, offset, w - 2 * offset), parent=self)
        line.setPen(QPen(Qt.white))
        line.setBrush(QBrush(Qt.white))

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """
        self.setBrush(color)
        self.setPen(QPen(color, w, style))

    def set_pen(self, pen: QPen):
        """

        :param pen:
        :return:
        """
        self.setPen(pen)

    def setToolTipText(self, toolTip: str):
        """
        Set branch tool tip text
        Args:
            toolTip: text
        """
        self.setToolTip(toolTip)

    def redraw(self):
        """
        Redraw the HVDC symbol
        """
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


class LineGraphicTemplateItem(GenericDiagramWidget, QGraphicsLineItem):
    """
    LineGraphicItem
    """

    def __init__(self,
                 from_port: Union[BarTerminalItem, RoundTerminalItem],
                 to_port: Union[BarTerminalItem, RoundTerminalItem, None],
                 editor: SchematicWidget,
                 width=5,
                 api_object: Union[Line, Transformer2W, VSC, UPFC, HvdcLine, DcLine, FluidPath, None] = None,
                 arrow_size=10,
                 draw_labels: bool = True):
        """

        :param from_port:
        :param to_port:
        :param editor:
        :param width:
        :param api_object:
        :param arrow_size:
        :param draw_labels:
        """
        GenericDiagramWidget.__init__(self, parent=None, api_object=api_object, editor=editor, draw_labels=draw_labels)
        QGraphicsLineItem.__init__(self)

        if isinstance(api_object, Transformer2W):
            if isinstance(api_object, Winding):  # Winding is a sublass of Transformer
                self.symbol = None
            else:
                self.symbol = TransformerSymbol(parent=self, pen_width=width, h=80, w=80)
        elif isinstance(api_object, VSC):
            self.symbol = VscSymbol(parent=self, pen_width=width, h=48, w=48)
        elif isinstance(api_object, UPFC):
            self.symbol = UpfcSymbol(parent=self, pen_width=width, h=48, w=48)
        elif isinstance(api_object, HvdcLine):
            self.symbol = HvdcSymbol(parent=self, pen_width=width, h=30, w=30)
        elif isinstance(api_object, SeriesReactance):
            self.symbol = SeriesReactanceSymbol(parent=self, pen_width=width, h=30, w=30)
        elif isinstance(api_object, Switch):
            self.symbol = SwitchSymbol(parent=self, pen_width=width, h=30, w=30)
        else:
            self.symbol = None

        self.scale = 1.0
        self.pen_style = Qt.SolidLine
        self.pen_color = Qt.black
        self.pen_width = width
        self.width = width

        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.pos1: QPointF = QPointF(0.0, 0.0)
        self.pos2: QPointF = QPointF(0.0, 0.0)

        self._from_port: Union[BarTerminalItem, RoundTerminalItem, None] = None
        self._to_port: Union[BarTerminalItem, RoundTerminalItem, None] = None

        # arrows
        self.view_arrows = True
        self.arrow_from_1 = ArrowHead(parent=self, arrow_size=arrow_size, position=0.2, under=False)
        self.arrow_from_2 = ArrowHead(parent=self, arrow_size=arrow_size, position=0.2, under=True)
        self.arrow_to_1 = ArrowHead(parent=self, arrow_size=arrow_size, position=0.8, under=False)
        self.arrow_to_2 = ArrowHead(parent=self, arrow_size=arrow_size, position=0.8, under=True)

        if from_port and to_port:
            self.redraw()

        if from_port:
            self.set_from_port(from_port)

        if to_port:
            self.set_to_port(to_port)

        self.set_colour(self.color, self.width, self.style)

    def get_terminal_from(self) -> Union[None, BarTerminalItem, RoundTerminalItem]:
        """
        Get the terminal from
        :return: TerminalItem 
        """
        return self._from_port

    def get_terminal_to(self) -> Union[None, BarTerminalItem, RoundTerminalItem]:
        """
        Get the terminal to
        :return: TerminalItem
        """
        return self._to_port

    def get_terminal_from_parent(self) -> Union[None, BusGraphicItem, Transformer3WGraphicItem, FluidNodeGraphicItem]:
        """
        Get the terminal from parent object
        :return: TerminalItem 
        """
        return self._from_port.get_parent()

    def get_terminal_to_parent(self) -> Union[None, BusGraphicItem, Transformer3WGraphicItem, FluidNodeGraphicItem]:
        """
        Get the terminal to parent object
        :return: TerminalItem
        """
        return self._to_port.get_parent()

    def update_ports(self):
        """

        :return:
        """
        self._from_port.update()
        self._to_port.update()

    def recolour_mode(self) -> None:
        """
        Change the colour according to the system theme
        """
        super().recolour_mode()

        self.set_colour(self.color, self.width, self.style)

    def set_colour(self, color: QColor, w, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param w: width
        :param style: PenStyle instance
        :return:
        """

        pen = QPen(color, w, style, Qt.RoundCap, Qt.RoundJoin)

        self.setPen(pen)
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

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param event:
        :return:
        """
        if self.api_object is not None:           
            
            self.editor.set_editor_model(api_object=self.api_object,
                                         dictionary_of_lists={
                                             DeviceType.BusDevice: self.editor.circuit.get_buses(),
                                             DeviceType.ConnectivityNodeDevice: self.editor.circuit.get_connectivity_nodes(),
                                         })

    def remove_widget(self):
        """
        Remove this object in the diagram
        @return:
        """
        self.editor.remove_from_scene(self)

    def remove(self, ask=True):
        """
        Remove this object in the diagram and the API
        @return:
        """
        if ask:
            dtype = self.api_object.device_type.value
            ok = yes_no_question(f'Do you want to remove the {dtype} {self.api_object.name}?',
                                 f'Remove {dtype}')
        else:
            ok = True

        if ok:
            self.editor.circuit.delete_branch(obj=self.api_object)
            self.editor.delete_diagram_element(device=self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.editor.circuit.get_time_number() > 0:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.editor.set_active_status_to_profile(self.api_object, override_question=True)

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
        i = self.editor.circuit.get_branches().index(self.api_object)
        self.editor.plot_branch(i, self.api_object)

    def set_from_port(self, from_port: BarTerminalItem):
        """
        Set the From terminal in a connection
        @param from_port: TerminalItem
        """

        if self._from_port:
            # there was a port before, unregister it
            self._from_port.delete_hosting_connection(graphic_obj=self)

        # register the new port
        self._from_port = from_port
        self._from_port.add_hosting_connection(graphic_obj=self, callback=self.setBeginPos)
        self._from_port.update()
        self._from_port.get_parent().setZValue(0)

    def set_to_port(self, to_port: BarTerminalItem):
        """
        Set the To terminal in a connection
        @param to_port: TerminalItem
        """
        if self._to_port:
            # there was a port before, unregister it
            self._to_port.delete_hosting_connection(graphic_obj=self)

        # register the new port
        self._to_port = to_port
        self._to_port.add_hosting_connection(graphic_obj=self, callback=self.setEndPos)
        self._to_port.update()
        self._to_port.get_parent().setZValue(0)

    def unregister_port_from(self) -> None:
        """

        :return:
        """
        if self._from_port:
            self._from_port.delete_hosting_connection(graphic_obj=self)

    def unregister_port_to(self) -> None:
        """

        :return:
        """
        if self._to_port:
            self._to_port.delete_hosting_connection(graphic_obj=self)

    def setEndPos(self, endpos: QPointF):
        """
        Set the starting position
        @param endpos:
        @return:
        """
        self.pos2 = endpos
        self.redraw()

    def setBeginPos(self, pos1: QPointF):
        """
        Set the starting position
        @param pos1:
        @return:
        """
        self.pos1 = pos1
        self.redraw()

    def redraw(self) -> None:
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

    def set_pen(self, pen, scale: float = 1.0):
        """
        Set pen to all objects
        :param pen:
        :param scale:
        :return:
        """

        self.pen_style = pen.style()
        self.pen_color = pen.color()
        self.pen_width = pen.width()
        self.scale = scale

        pen.setWidth(self.pen_width / scale)

        self.setPen(pen)

        if self.symbol:
            self.symbol.set_pen(pen)

    def assign_rate_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.editor.set_rate_to_profile(self.api_object)

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.editor.set_active_status_to_profile(self.api_object)

    def set_arrows_with_power(self, Sf: complex, St: complex) -> None:
        """
        Set the arrow directions
        :param Sf: Complex power from
        :param St: Complex power to
        """

        if Sf is not None:
            if St is None:
                St = -Sf

            Pf = Sf.real
            Qf = Sf.imag
            Pt = St.real
            Qt_ = St.imag
            self.arrow_from_1.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
            self.arrow_from_2.set_value(Qf, True, Qf < 0, name="Qf", units="MVAr", draw_label=self.draw_labels)
            self.arrow_to_1.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)
            self.arrow_to_2.set_value(Qt_, True, Qt_ > 0, name="Qt", units="MVAr", draw_label=self.draw_labels)

    def set_arrows_with_hvdc_power(self, Pf: float, Pt: float) -> None:
        """
        Set the arrow directions
        :param Pf: Complex power from
        :param Pt: Complex power to
        """
        self.arrow_from_1.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
        self.arrow_from_2.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
        self.arrow_to_1.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)
        self.arrow_to_2.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)

    def change_bus(self):
        """
        change the from or to bus of the nbranch with another selected bus
        """
        self.editor.change_bus(line_graphics=self)

    def get_from_graphic_object(self):
        """

        :return:
        """
        if self._from_port:
            return self.get_terminal_from_parent()
        else:
            return None

    def get_to_graphic_object(self):
        """

        :return:
        """
        if self._to_port:
            return self.get_terminal_to_parent()
        else:
            return None

    def is_from_port_a_bus(self) -> bool:
        """

        :return:
        """
        if self._from_port:
            return isinstance(self.get_terminal_from_parent(), BusGraphicItem)
        else:
            return False

    def is_to_port_a_bus(self) -> bool:
        """

        :return:
        """
        if self._to_port:
            return isinstance(self.get_terminal_to_parent(), BusGraphicItem)
        else:
            return False

    def is_from_port_a_cn(self) -> bool:
        """

        :return:
        """
        if self._from_port:
            return isinstance(self.get_terminal_from_parent(), CnGraphicItem)
        else:
            return False

    def is_to_port_a_cn(self) -> bool:
        """

        :return:
        """
        if self._to_port:
            return isinstance(self.get_terminal_to_parent(), CnGraphicItem)
        else:
            return False

    def is_from_port_a_busbar(self) -> bool:
        """

        :return:
        """
        if self._from_port:
            return isinstance(self.get_terminal_from_parent(), BusBarGraphicItem)
        else:
            return False

    def is_to_port_a_busbar(self) -> bool:
        """

        :return:
        """
        if self._to_port:
            return isinstance(self.get_terminal_to_parent(), BusBarGraphicItem)
        else:
            return False

    def is_from_port_a_tr3(self) -> bool:
        """

        :return:
        """
        if self._from_port:
            if 'Transformer3WGraphicItem' not in sys.modules:
                from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer3w_graphics import \
                    Transformer3WGraphicItem
            return isinstance(self.get_terminal_from_parent(), Transformer3WGraphicItem)
        else:
            return False

    def is_to_port_a_tr3(self) -> bool:
        """

        :return:
        """
        if self._to_port:
            if 'Transformer3WGraphicItem' not in sys.modules:
                from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer3w_graphics import \
                    Transformer3WGraphicItem
            return isinstance(self.get_terminal_to_parent(), Transformer3WGraphicItem)
        else:
            return False

    def is_from_port_a_fluid_node(self) -> bool:
        """

        :return:
        """
        if self._from_port:
            return isinstance(self.get_terminal_from_parent(), FluidNodeGraphicItem)
        else:
            return False

    def is_to_port_a_fluid_node(self) -> bool:
        """

        :return:
        """
        if self._to_port:
            return isinstance(self.get_terminal_to_parent(), FluidNodeGraphicItem)
        else:
            return False

    def get_bus_from(self) -> Bus:
        """

        :return:
        """
        return self.get_from_graphic_object().api_object

    def get_bus_to(self) -> Bus:
        """

        :return:
        """
        return self.get_to_graphic_object().api_object

    def get_cn_from(self) -> ConnectivityNode:
        """

        :return:
        """
        return self.get_from_graphic_object().api_object

    def get_cn_to(self) -> ConnectivityNode:
        """

        :return:
        """
        return self.get_to_graphic_object().api_object

    def get_busbar_from(self) -> BusBar:
        """

        :return:
        """
        return self.get_from_graphic_object().api_object

    def get_busbar_to(self) -> BusBar:
        """

        :return:
        """
        return self.get_to_graphic_object().api_object

    def get_fluid_node_from(self) -> FluidNode:
        """

        :return:
        """
        return self.get_from_graphic_object().api_object

    def get_fluid_node_to(self) -> FluidNode:
        """

        :return:
        """
        return self.get_to_graphic_object().api_object

    def get_fluid_node_graphics_from(self) -> FluidNodeGraphicItem:
        """

        :return:
        """
        return self.get_from_graphic_object()

    def get_fluid_node_graphics_to(self) -> FluidNodeGraphicItem:
        """

        :return:
        """
        return self.get_to_graphic_object()

    def connected_between_buses(self):
        """

        :return:
        """
        return self.is_from_port_a_bus() and self.is_to_port_a_bus()

    def connected_between_bus_and_tr3(self):
        """

        :return:
        """
        return self.is_from_port_a_bus() and self.is_to_port_a_tr3()

    def conneted_between_tr3_and_bus(self):
        """

        :return:
        """
        return self.is_from_port_a_tr3() and self.is_to_port_a_bus()

    def connected_between_fluid_nodes(self):
        """

        :return:
        """
        return self.is_from_port_a_fluid_node() and self.is_to_port_a_fluid_node()

    def connected_between_fluid_node_and_bus(self):
        """

        :return:
        """
        return self.is_from_port_a_fluid_node() and self.is_to_port_a_bus()

    def connected_between_bus_and_fluid_node(self):
        """

        :return:
        """
        return self.is_from_port_a_bus() and self.is_to_port_a_fluid_node()

    def connected_between_cn_and_bus(self):
        """

        :return:
        """
        return self.is_from_port_a_cn() and self.is_to_port_a_bus()

    def connected_between_bus_and_cn(self):
        """

        :return:
        """
        return self.is_from_port_a_bus() and self.is_to_port_a_cn()

    def connected_between_cn(self):
        """

        :return:
        """
        return self.is_from_port_a_cn() and self.is_to_port_a_cn()

    def connected_between_busbar_and_bus(self):
        """

        :return:
        """
        return self.is_from_port_a_busbar() and self.is_to_port_a_bus()

    def connected_between_bus_and_busbar(self):
        """

        :return:
        """
        return self.is_from_port_a_bus() and self.is_to_port_a_busbar()

    def connected_between_busbar(self):
        """

        :return:
        """
        return self.is_from_port_a_busbar() and self.is_to_port_a_busbar()

    def connected_between_busbar_and_cn(self):
        """

        :return:
        """
        return self.is_from_port_a_busbar() and self.is_to_port_a_cn()

    def connected_between_cn_and_busbar(self):
        """

        :return:
        """
        return self.is_from_port_a_cn() and self.is_to_port_a_busbar()

    def should_be_a_converter(self) -> bool:
        """

        :return:
        """
        return self.get_bus_from().is_dc != self.get_bus_to().is_dc

    def should_be_a_dc_line(self) -> bool:
        """

        :return:
        """
        return self.get_bus_from().is_dc and self.get_bus_to().is_dc

    def should_be_a_transformer(self, branch_connection_voltage_tolerance: float = 0.1) -> bool:
        """

        :param branch_connection_voltage_tolerance:
        :return:
        """
        bus_from = self.get_bus_from()
        bus_to = self.get_bus_to()

        V1 = min(bus_to.Vnom, bus_from.Vnom)
        V2 = max(bus_to.Vnom, bus_from.Vnom)
        if V2 > 0:
            per = V1 / V2
            return per < (1.0 - branch_connection_voltage_tolerance)
        else:
            return V1 != V2
