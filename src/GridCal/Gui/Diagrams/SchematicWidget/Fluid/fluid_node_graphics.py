# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import Union, TYPE_CHECKING, List, Dict
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QPen, QCursor, QBrush, QColor
from PySide6.QtWidgets import QMenu, QGraphicsSceneMouseEvent

from GridCalEngine.Devices.Fluid import FluidNode, FluidTurbine, FluidPump, FluidP2x
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import DeviceType, FaultType
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Devices.types import FLUID_TYPES

from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, FONT_SCALE, GenericDiagramWidget
from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, HandleItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_turbine_graphics import FluidTurbineGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_pump_graphics import FluidPumpGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_p2x_graphics import FluidP2xGraphicItem
from GridCal.Gui.messages import yes_no_question, error_msg
from GridCal.Gui.gui_functions import add_menu_entry

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class FluidNodeGraphicItem(GenericDiagramWidget, QtWidgets.QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self, editor: SchematicWidget, fluid_node: FluidNode,
                 parent=None, index=0, h: int = 20, w: int = 80, x: float = 0, y: float = 0,
                 draw_labels: bool = True):

        GenericDiagramWidget.__init__(self, parent=parent, api_object=fluid_node, editor=editor,
                                      draw_labels=draw_labels)
        QtWidgets.QGraphicsRectItem.__init__(self, parent)

        self.min_w = 180.0
        self.min_h = 40.0
        self.offset = 20
        self.h = h if h >= self.min_h else self.min_h
        self.w = w if w >= self.min_w else self.min_w

        self.api_object: FluidNode = fluid_node  # reassign for type to be clear

        # loads, shunts, generators, etc...
        self.shunt_children = list()

        # Enabled for short circuit
        self.sc_enabled = [False, False, False, False]
        self.sc_type = FaultType.ph3
        self.pen_width = 4

        # index
        self.index = index

        self.color = QColor(fluid_node.color) if fluid_node is not None else ACTIVE['fluid']
        self.style = ACTIVE['style']

        # Label:
        self.label = QtWidgets.QGraphicsTextItem(self.api_object.name if self.api_object is not None else "", self)
        self.label.setDefaultTextColor(ACTIVE['text'])
        self.label.setScale(FONT_SCALE)

        # square
        self.tile = QtWidgets.QGraphicsRectItem(0, 0, 20, 20, self)
        self.tile.setOpacity(0.7)

        # connection terminals the block
        self._terminal = BarTerminalItem('s', parent=self, editor=self.editor)  # , h=self.h))
        self._terminal.setPen(QPen(Qt.GlobalColor.transparent, self.pen_width, self.style,
                                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        # Create corner for resize:
        self.sizer = HandleItem(self._terminal, callback=self.change_size)
        self.sizer.setPos(self.w, self.h)
        self.sizer.setFlag(self.GraphicsItemFlag.ItemIsMovable)

        self.big_marker = None

        self.set_tile_color(self.color)

        self.setPen(QPen(Qt.GlobalColor.transparent, self.pen_width, self.style))
        self.setBrush(Qt.GlobalColor.transparent)
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Update size:
        self.change_size(self.w, self.h)

        self.set_position(x, y)

    def set_api_object_color(self):
        """
        Gether the color from the api object and apply
        :return:
        """
        self.color = QColor(self.api_object.color) if self.api_object is not None else ACTIVE['fluid']
        self.set_tile_color(self.color)

    def set_label(self, val: str):
        """
        Set the label content
        :param val:
        :return:
        """
        self.label.setPlainText(val)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        mouse press: display the editor
        :param event:
        :return:
        """
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """
        On mouse move of this object...
        Args:
            event: QGraphicsSceneMouseEvent inherited
        """
        super().mouseMoveEvent(event)

        self.editor.update_diagram_element(device=self.api_object,
                                           x=self.pos().x(),
                                           y=self.pos().y(),
                                           w=self.w,
                                           h=self.h,
                                           r=self.rotation(),
                                           draw_labels=self.draw_labels,
                                           graphic_object=self)

    def set_position(self, x, y):
        """
        Set the bus x, y position
        :param x: x in pixels
        :param y: y in pixels
        """
        if np.isnan(x):
            x = 0
        if np.isnan(y):
            y = 0
        self.setPos(QPoint(int(x), int(y)))

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
        # self.color = ACTIVE['color']
        # self.style = ACTIVE['style']
        self.label.setDefaultTextColor(ACTIVE['text'])
        # self.set_tile_color(self.color)

        for e in self.shunt_children:
            if e is not None:
                e.recolour_mode()

    def get_nexus_point(self) -> QPointF:
        """
        Get the connection point for the chldren nexus line
        :return: QPointF
        """
        return QPointF(self.x() + self.rect().width() / 2.0,
                       self.y() + self.rect().height() + self._terminal.h / 2.0)

    def set_tile_color(self, brush):
        """
        Set the color of the title
        Args:
            brush:  Qt Color
        """
        self.tile.setBrush(brush)
        self._terminal.setBrush(brush)

    def redraw(self):
        """
        Update the object
        :return:
        """
        self.change_size(self.w, self.h)

    def set_height(self, h):
        """
        Set the object height
        :param h: height in pixels
        """
        self.setRect(0.0, 0.0, self.w, h)
        self.h = h

    def change_size(self, w: int, h: Union[None, int] = None):
        """
        Resize block function
        @param w:
        @param h:
        @return:
        """
        # Limit the block size to the minimum size:
        self.w = w if w > self.min_w else self.min_w
        self.setRect(0.0, 0.0, self.w, self.min_h)
        y0 = self.offset
        x0 = 0

        # center label:
        self.label.setPos(self.w + 5, -20)

        # lower
        self._terminal.setPos(x0, y0)
        self._terminal.setRect(0, 20, self.w, 10)

        # rearrange children
        self.arrange_children()

        # update editor diagram position
        self.editor.update_diagram_element(device=self.api_object,
                                           x=self.pos().x(),
                                           y=self.pos().y(),
                                           w=self.w,
                                           h=int(self.min_h),
                                           r=self.rotation(),
                                           draw_labels=self.draw_labels,
                                           graphic_object=self)

        return self.w, self.min_h

    def arrange_children(self):
        """
        This function sorts the load and generators icons
        Returns:
            Nothing
        """
        y0 = self.h + 40
        n = len(self.shunt_children)
        inc_x = self.w / (n + 1)
        x = inc_x
        for elm in self.shunt_children:
            elm.setPos(x - elm.w / 2, y0)
            x += inc_x

        # Arrange line positions
        self._terminal.process_callbacks(self.pos() + self._terminal.pos())

    def create_children_widgets(self, injections_by_tpe: Dict[DeviceType, List[FLUID_TYPES]]):
        """
        Create the icons of the elements that are attached to the API bus object
        Returns:
            Nothing
        """
        for tpe, dev_list in injections_by_tpe.items():

            if tpe == DeviceType.FluidPumpDevice:
                for elm in dev_list:
                    self.add_pump(elm)

            elif tpe == DeviceType.FluidTurbineDevice:
                for elm in dev_list:
                    self.add_turbine(elm)

            elif tpe == DeviceType.FluidP2XDevice:
                for elm in dev_list:
                    self.add_p2x(elm)

            else:
                raise Exception("Unknown device type:" + str(tpe))

        self.arrange_children()

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Fluid node")

        add_menu_entry(menu=menu,
                       text="Plot electrical profiles",
                       icon_path=":/Icons/icons/plot.svg",
                       function_ptr=self.plot_electrical_profiles)

        add_menu_entry(menu=menu,
                       text="Plot fluid profiles",
                       icon_path=":/Icons/icons/plot.svg",
                       function_ptr=self.plot_fluid_profiles)

        add_menu_entry(menu=menu,
                       text="Arrange",
                       icon_path=":/Icons/icons/automatic_layout.svg",
                       function_ptr=self.arrange_children)

        add_menu_entry(menu=menu,
                       text="Delete all the connections",
                       icon_path=":/Icons/icons/delete_conn.svg",
                       function_ptr=lambda: self.delete_all_connections(ask=True, delete_from_db=True))

        add_menu_entry(menu=menu,
                       text="Delete",
                       icon_path=":/Icons/icons/delete3.svg",
                       function_ptr=self.remove)

        menu.addSection("Add")

        add_menu_entry(menu=menu,
                       text="Turbine",
                       icon_path=":/Icons/icons/add_gen.svg",
                       function_ptr=self.add_turbine)

        add_menu_entry(menu=menu,
                       text="Pump",
                       icon_path=":/Icons/icons/add_gen.svg",
                       function_ptr=self.add_pump)

        add_menu_entry(menu=menu,
                       text="P2X",
                       icon_path=":/Icons/icons/add_gen.svg",
                       function_ptr=self.add_p2x)

        menu.exec_(event.screenPos())

    def get_terminal(self) -> BarTerminalItem:
        """
        Get the hosting terminal of this bus object
        :return: TerminalItem
        """
        return self._terminal

    def add_object(self, api_obj: Union[None, EditableDevice] = None):
        """
        Add any recognized object
        :param api_obj: EditableDevice
        """

        if api_obj.device_type == DeviceType.FluidTurbineDevice:
            self.add_turbine(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.FluidPumpDevice:
            self.add_pump(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.FluidP2XDevice:
            self.add_p2x(api_obj=api_obj)

        else:
            raise Exception("Cannot add device of type {}".format(api_obj.device_type.value))

    def create_bus_if_necessary(self) -> Bus:
        """
        Create the internal electrical bus of the fluid node
        :return api_object.bus
        """

        if self.api_object.bus is None:
            # create the bus and assign it
            self.api_object.bus = self.editor.circuit.add_bus()

            # set the same name
            self.api_object.bus.name = "Bus of " + self.api_object.name

        return self.api_object.bus

    def add_turbine(self, api_obj: Union[None, FluidTurbine] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_fluid_turbine(node=self.api_object, api_obj=None)
            api_obj.generator = self.editor.circuit.add_generator(bus=self.create_bus_if_necessary())
            api_obj.generator.name = f"Turbine @{self.api_object.name}"

        _grph = FluidTurbineGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_pump(self, api_obj: Union[None, FluidPump] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_fluid_pump(node=self.api_object, api_obj=None)
            api_obj.generator = self.editor.circuit.add_generator(bus=self.create_bus_if_necessary())
            api_obj.generator.name = f"Pump @{self.api_object.name}"

        _grph = FluidPumpGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_p2x(self, api_obj: Union[None, FluidP2x] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_fluid_p2x(node=self.api_object, api_obj=None)
            api_obj.generator = self.editor.circuit.add_generator(bus=self.create_bus_if_necessary())
            api_obj.generator.name = f"P2X @{self.api_object.name}"

        _grph = FluidP2xGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def delete_all_connections(self, ask: bool, delete_from_db: bool) -> None:
        """
        Delete all bus connections
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this fluid node',
                                 'Remove fluid node from schematic and DB' if delete_from_db else "Remove bus from schematic")
        else:
            ok = True

        if ok:
            self._terminal.remove_all_connections(delete_from_db=delete_from_db)

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this fluid node',
                                 'Remove fluid node')
        else:
            ok = True

        if ok:
            self.editor.remove_element(device=self.api_object, graphic_object=self)

    def update_color(self):
        """
        Update the colour
        """
        self.set_tile_color(QBrush(ACTIVE['color']))

    def plot_electrical_profiles(self):
        """

        @return:
        """
        # get the index of this object
        if self.api_object is not None:
            if self.api_object.bus is not None:
                i = self.editor.circuit.fluid_nodes.index(self.api_object)
                self.editor.plot_bus(i, self.api_object.bus)
            else:
                error_msg("No electrical bus attached :/")
        else:
            error_msg("No DB object attached :/")

    def plot_fluid_profiles(self):
        """

        @return:
        """
        # get the index of this object
        if self.api_object is not None:
            i = self.editor.circuit.fluid_nodes.index(self.api_object)
            self.editor.plot_fluid_node(i, self.api_object)
        else:
            error_msg("No DB object attached :/")

    def set_values(self, i: int, Vm: float, Va: float, P: float, Q: float,
                   tpe: str, format_str="{:10.2f}"):
        """

        :param i:
        :param Vm:
        :param Va:
        :param P:
        :param Q:
        :param tpe:
        :param format_str:
        :return:
        """
        if self.draw_labels:
            vm = format_str.format(Vm)

            if self.api_object is not None:
                if self.api_object.bus is not None:
                    vm_kv = format_str.format(Vm * self.api_object.bus.Vnom)
                else:
                    vm_kv = "No electrical bus"
            else:
                vm_kv = ""
            va = format_str.format(Va)
            msg = f"Bus {i}"
            if tpe is not None:
                msg += f" [{tpe}]"
            msg += "<br>"
            msg += f"v={vm}&lt;{va}º pu<br>"
            msg += f"V={vm_kv} KV<br>"
            if P is not None:
                p = format_str.format(P)
                q = format_str.format(Q)
                msg += f"P={p} MW<br>Q={q} MVAr"
        else:
            msg = ""

        title = self.api_object.name if self.api_object is not None else ""
        self.label.setHtml(f'<html><head/><body><p><span style=" font-size:10pt;">{title}<br/></span>'
                           f'<span style=" font-size:6pt;">{msg}</span></p></body></html>')

        self.setToolTip(msg)

    def set_fluid_values(self, i: int, Vm: float, Va: float, P: float, Q: float,
                         tpe: str,
                         fluid_node_p2x_flow: float,
                         fluid_node_current_level: float,
                         fluid_node_spillage: float,
                         fluid_node_flow_in: float,
                         fluid_node_flow_out: float,
                         format_str="{:10.2f}"):
        """

        :param i:
        :param Vm:
        :param Va:
        :param P:
        :param Q:
        :param tpe:
        :param fluid_node_p2x_flow:
        :param fluid_node_current_level:
        :param fluid_node_spillage:
        :param fluid_node_flow_in:
        :param fluid_node_flow_out:
        :param format_str:
        :return:
        """
        if self.draw_labels:
            vm = format_str.format(Vm)

            if self.api_object is not None:
                if self.api_object.bus is not None:
                    vm_kv = format_str.format(Vm * self.api_object.bus.Vnom)
                else:
                    vm_kv = "No electrical bus"
            else:
                vm_kv = ""
            va = format_str.format(Va)
            msg = f"Bus {i}"
            if tpe is not None:
                msg += f" [{tpe}]"
            msg += "<br>"
            msg += f"v={vm}&lt;{va}º pu<br>"
            msg += f"V={vm_kv} KV<br>"
            if P is not None:
                p = format_str.format(P)
                q = format_str.format(Q)
                msg += f"P={p} MW<br>Q={q} MVAr<br>"

            if fluid_node_flow_in is not None:
                f_in = format_str.format(fluid_node_flow_in)
                msg += f"In={f_in} m3/s<br>"

            if fluid_node_flow_out is not None:
                f_out = format_str.format(fluid_node_flow_out)
                msg += f"Out={f_out} m3/s<br>"

            if fluid_node_spillage is not None:
                f_spill = format_str.format(fluid_node_spillage)
                msg += f"Spill={f_spill} m3/s<br>"

            if fluid_node_current_level is not None:
                f_lvl = format_str.format(fluid_node_current_level)
                msg += f"Lvl={f_lvl} m3<br>"

            if fluid_node_p2x_flow is not None:
                f_p2x = format_str.format(fluid_node_p2x_flow)
                msg += f"P2X={f_p2x} m3/s<br>"

        else:
            msg = ""

        title = self.api_object.name if self.api_object is not None else ""
        self.label.setHtml(f'<html><head/><body><p><span style=" font-size:10pt;">{title}<br/></span>'
                           f'<span style=" font-size:6pt;">{msg}</span></p></body></html>')

        self.setToolTip(msg)
