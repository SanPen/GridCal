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
                               QGraphicsEllipseItem, QGraphicsSceneMouseEvent)
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, OTHER
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Substation.bus_graphics import TerminalItem
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Substation.bus_graphics import BusGraphicItem
from GridCal.Gui.Diagrams.NodeBreakerEditorWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem

from GridCal.Gui.messages import yes_no_question, warning_msg, error_msg
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Branches.vsc import VSC
from GridCalEngine.Devices.Branches.upfc import UPFC
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.Devices.Fluid.fluid_path import FluidPath
from GridCalEngine.Simulations.Topology.topology_reduction_driver import reduce_grid_brute

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.NodeBreakerEditorWidget.node_breaker_editor_widget import NodeBreakerEditorWidget


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
                 separation: int = 5):
        QGraphicsPolygonItem.__init__(self, parent=parent)

        self.parent: QGraphicsLineItem = parent
        self.arrow_size: int = arrow_size
        self.position: float = position
        self.under: bool = under
        self.backwards: float = backwards
        self.sep = separation

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

    def set_value(self, value: float, redraw=True):
        """
        Set the sign with a value
        :param value: any real value
        :param redraw: redraw after the sign update
        """
        self.backwards = value < 0

        if redraw:
            self.redraw()

    def redraw(self) -> None:
        """
        Redraw the arrow
        """
        line = self.parent.line()

        # the angle is added 180º if the sign is negative
        angle = line.angle()
        base_pt = line.p1() + (line.p2() - line.p1()) * self.position

        p1 = -self.arrow_size if self.backwards else self.arrow_size
        p2 = -self.arrow_size if self.under else self.arrow_size
        arrow_p1 = base_pt - QTransform().rotate(-angle).map(QPointF(p1, 0))
        arrow_p2 = base_pt - QTransform().rotate(-angle).map(QPointF(p1, p2))
        arrow_polygon = QPolygonF([base_pt, arrow_p1, arrow_p2])

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
                 editor: NodeBreakerEditorWidget,
                 width=5,
                 api_object: Union[Line, Transformer2W, VSC, UPFC, HvdcLine, DcLine, FluidPath, None] = None,
                 arrow_size=10):
        """

        :param fromPort:
        :param toPort:
        :param editor:
        :param width:
        :param api_object:
        :param arrow_size:
        """
        QGraphicsLineItem.__init__(self)

        self.api_object = api_object

        if isinstance(api_object, Transformer2W):
            self.symbol = TransformerSymbol(parent=self, pen_width=width, h=80, w=80)
        elif isinstance(api_object, VSC):
            self.symbol = VscSymbol(parent=self, pen_width=width, h=48, w=48)
        elif isinstance(api_object, UPFC):
            self.symbol = UpfcSymbol(parent=self, pen_width=width, h=48, w=48)
        elif isinstance(api_object, HvdcLine):
            self.symbol = HvdcSymbol(parent=self, pen_width=width, h=30, w=30)
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
        self.editor: NodeBreakerEditorWidget = editor

        if fromPort:
            self.setFromPort(fromPort)

        if toPort:
            self.setToPort(toPort)

        # arrows
        self.view_arrows = True
        self.arrow_from_1 = ArrowHead(parent=self, arrow_size=arrow_size, position=0.15, under=False)
        self.arrow_from_2 = ArrowHead(parent=self, arrow_size=arrow_size, position=0.15, under=True)
        self.arrow_to_1 = ArrowHead(parent=self, arrow_size=arrow_size, position=0.85, under=False)
        self.arrow_to_2 = ArrowHead(parent=self, arrow_size=arrow_size, position=0.85, under=True)

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
            self.editor.set_editor_model(api_object=self.api_object)

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
                                 'Remove branch')
        else:
            ok = True

        if ok:
            self.editor.circuit.delete_branch(self.api_object)
            self.editor.delete_diagram_element(self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.editor.circuit.has_time_series:
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

        # TODO: Review the signs and conditions

        if Sf is not None:
            if St is None:
                St = -Sf

            Pf = Sf.real
            Qf = Sf.imag
            Pt = St.real
            Qt = St.imag
            self.arrow_from_1.set_value(Pf, True)
            self.arrow_from_2.set_value(Qf if Qf != 0.0 else Pf, True)
            self.arrow_to_1.set_value(-Pt, True)
            self.arrow_to_2.set_value(-Qt if Qt != 0.0 else -Pt, True)

            self.arrow_from_1.setToolTip("Pf: {} MW".format(Pf))
            self.arrow_from_2.setToolTip("Qf: {} MVAr".format(Qf))
            self.arrow_to_1.setToolTip("Pt: {} MW".format(Pt))
            self.arrow_to_2.setToolTip("Qt: {} MVAr".format(Qt))

    def set_arrows_with_hvdc_power(self, Pf: float, Pt: float) -> None:
        """
        Set the arrow directions
        :param Pf: Complex power from
        :param Pt: Complex power to
        """
        self.arrow_from_1.set_value(Pf, True)
        self.arrow_from_2.set_value(Pf, True)
        self.arrow_to_1.set_value(-Pt, True)
        self.arrow_to_2.set_value(-Pt, True)

        self.arrow_from_1.setToolTip("Pf: {} MW".format(Pf))
        self.arrow_from_2.setToolTip("Pf: {} MW".format(Pf))
        self.arrow_to_1.setToolTip("Pt: {} MW".format(Pt))
        self.arrow_to_2.setToolTip("Pt: {} MW".format(Pt))

    def reduce(self):
        """
        Reduce this branch
        """
        # TODO: Fix this

        ok = yes_no_question('Do you want to reduce this branch {}?'.format(self.api_object.name),
                             'Remove branch')

        if ok:
            # get the index of the branch
            br_idx = self.editor.circuit.get_branches().index(self.api_object)

            # call the reduction routine
            (removed_branch, removed_bus,
             updated_bus, updated_branches) = reduce_grid_brute(self.editor.circuit, br_idx)

            # remove the reduced branch
            removed_branch.graphic_obj.remove_symbol()
            self.editor.delete_diagram_element(device=removed_branch.graphic_obj)

            # update the buses (the deleted one and the updated one)
            if removed_bus is not None:
                # merge the removed bus with the remaining one
                updated_bus.graphic_obj.merge(removed_bus.graphic_obj)

                # remove the updated bus children
                for g in updated_bus.graphic_obj.shunt_children:
                    self.editor.remove_from_scene(g.nexus)
                    self.editor.remove_from_scene(g)
                # re-draw the children
                updated_bus.graphic_obj.create_children_widgets()

                # remove bus
                for g in removed_bus.graphic_obj.shunt_children:
                    self.editor.remove_from_scene(g.nexus)  # remove the links between the bus and the children
                self.editor.delete_diagram_element(device=removed_bus.graphic_obj)  # remove the bus and all the children contained

            for br in updated_branches:
                # remove the branch from the schematic
                self.editor.delete_diagram_element(br.graphic_obj)
                # add the branch to the schematic with the rerouting and all
                self.editor.add_api_line(br)
                # update both buses
                br.bus_from.graphic_obj.update()
                br.bus_to.graphic_obj.update()

    def change_bus(self):
        """
        change the from or to bus of the nbranch with another selected bus
        """

        idx_bus_list = self.editor.get_selected_buses()

        if len(idx_bus_list) == 2:

            # detect the bus and its combinations
            if idx_bus_list[0][1] == self.api_object.bus_from:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]
                idx, new_bus, new_bus_graphic_item = idx_bus_list[1]
                side = 'f'
            elif idx_bus_list[1][1] == self.api_object.bus_from:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]
                side = 'f'
            elif idx_bus_list[0][1] == self.api_object.bus_to:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]
                idx, new_bus, new_bus_graphic_item = idx_bus_list[1]
                side = 't'
            elif idx_bus_list[1][1] == self.api_object.bus_to:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]
                side = 't'
            else:
                error_msg("The 'from' or 'to' bus to change has not been selected!",
                          'Change bus')
                return

            ok = yes_no_question(
                text="Are you sure that you want to relocate the bus from {0} to {1}?".format(old_bus.name,
                                                                                              new_bus.name),
                title='Change bus')

            if ok:
                if side == 'f':
                    self.api_object.bus_from = new_bus
                    self.setFromPort(new_bus_graphic_item.terminal)
                elif side == 't':
                    self.api_object.bus_to = new_bus
                    self.setToPort(new_bus_graphic_item.terminal)
                else:
                    raise Exception('Unsupported side value {}'.format(side))

                new_bus_graphic_item.add_hosting_connection(graphic_obj=self)
                old_bus_graphic_item.delete_hosting_connection(graphic_obj=self)
                new_bus_graphic_item.terminal.update()
        else:
            warning_msg("you have to select the origin and destination buses!",
                        title='Change bus')

    def get_from_graphic_object(self):
        """

        :return:
        """
        if self.fromPort:
            return self.fromPort.parent
        else:
            return None

    def get_to_graphic_object(self):
        """

        :return:
        """
        if self.toPort:
            return self.toPort.parent
        else:
            return None

    def is_from_port_a_bus(self) -> bool:

        if self.fromPort:
            return isinstance(self.fromPort.parent, BusGraphicItem)
        else:
            return False

    def is_to_port_a_bus(self) -> bool:

        if self.toPort:
            return isinstance(self.toPort.parent, BusGraphicItem)
        else:
            return False

    def is_from_port_a_tr3(self) -> bool:

        if self.fromPort:
            if 'Transformer3WGraphicItem' not in sys.modules:
                from GridCal.Gui.NodeBreakerEditorWidget.Branches.Rectangle_Connector import RectangleConnectorGraphicItem
            return isinstance(self.fromPort.parent, RectangleConnectorGraphicItem)
        else:
            return False

    def is_to_port_a_tr3(self) -> bool:

        if self.toPort:
            if 'Transformer3WGraphicItem' not in sys.modules:
                from GridCal.Gui.NodeBreakerEditorWidget.Branches.Rectangle_Connector import RectangleConnectorGraphicItem
            return isinstance(self.toPort.parent, RectangleConnectorGraphicItem)
        else:
            return False

    def is_from_port_a_fluid_node(self) -> bool:

        if self.fromPort:
            return isinstance(self.fromPort.parent, FluidNodeGraphicItem)
        else:
            return False

    def is_to_port_a_fluid_node(self) -> bool:

        if self.toPort:
            return isinstance(self.toPort.parent, FluidNodeGraphicItem)
        else:
            return False

    def get_bus_from(self) -> Bus:
        return self.get_from_graphic_object().api_object

    def get_bus_to(self) -> Bus:
        return self.get_to_graphic_object().api_object

    def get_fluid_node_from(self) -> FluidNode:
        return self.get_from_graphic_object().api_object

    def get_fluid_node_to(self) -> FluidNode:
        return self.get_to_graphic_object().api_object

    def get_fluid_node_graphics_from(self) -> FluidNodeGraphicItem:
        return self.get_from_graphic_object()

    def get_fluid_node_graphics_to(self) -> FluidNodeGraphicItem:
        return self.get_to_graphic_object()

    def connected_between_buses(self):

        return self.is_from_port_a_bus() and self.is_to_port_a_bus()
    def connected_between_bus_and_tr3(self):

        return self.is_from_port_a_bus() and self.is_to_port_a_tr3()

    def conneted_between_tr3_and_bus(self):

        return self.is_from_port_a_tr3() and self.is_to_port_a_bus()

    def connected_between_fluid_nodes(self):

        return self.is_from_port_a_fluid_node() and self.is_to_port_a_fluid_node()

    def connected_between_fluid_node_and_bus(self):

        return self.is_from_port_a_fluid_node() and self.is_to_port_a_bus()

    def connected_between_bus_and_fluid_node(self):

        return self.is_from_port_a_bus() and self.is_to_port_a_fluid_node()

    def should_be_a_converter(self):

        return self.fromPort.parent.api_object.is_dc != self.toPort.parent.api_object.is_dc

    def should_be_a_dc_line(self):

        return self.fromPort.parent.api_object.is_dc and self.toPort.parent.api_object.is_dc

    def should_be_a_transformer(self, branch_connection_voltage_tolerance=0.1):

        bus_from = self.fromPort.parent.api_object
        bus_to = self.toPort.parent.api_object

        V1 = min(bus_to.Vnom, bus_from.Vnom)
        V2 = max(bus_to.Vnom, bus_from.Vnom)
        if V2 > 0:
            per = V1 / V2
            return per < (1.0 - branch_connection_voltage_tolerance)
        else:
            return V1 != V2
