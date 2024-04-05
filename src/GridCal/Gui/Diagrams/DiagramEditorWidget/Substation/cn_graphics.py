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
import numpy as np
from typing import Union, TYPE_CHECKING, List, Dict
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPoint, QRectF, QRect
from PySide6.QtGui import QPen, QCursor, QIcon, QPixmap, QBrush, QColor
from PySide6.QtWidgets import QMenu, QGraphicsSceneMouseEvent

from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.Diagrams.DiagramEditorWidget.generic_graphics import (GenericDBWidget, ACTIVE, DEACTIVATED,
                                                                       FONT_SCALE, EMERGENCY)
from GridCal.Gui.Diagrams.DiagramEditorWidget.terminal_item import RoundTerminalItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.load_graphics import LoadGraphicItem, Load
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.generator_graphics import GeneratorGraphicItem, Generator
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.static_generator_graphics import (StaticGeneratorGraphicItem,
                                                                                           StaticGenerator)
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.battery_graphics import (BatteryGraphicItem, Battery)
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.shunt_graphics import (ShuntGraphicItem, Shunt)
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.external_grid_graphics import (ExternalGridGraphicItem,
                                                                                        ExternalGrid)
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.current_injection_graphics import (
    CurrentInjectionGraphicItem,
    CurrentInjection)
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.controllable_shunt_graphics import (
    ControllableShuntGraphicItem,
    ControllableShunt)

from GridCalEngine.enumerations import DeviceType, FaultType
from GridCalEngine.Devices.types import INJECTION_DEVICE_TYPES
from GridCalEngine.Simulations.Topology.topology_reduction_driver import reduce_buses
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.DiagramEditorWidget.diagram_editor_widget import DiagramEditorWidget


class CnGraphicItem(GenericDBWidget, QtWidgets.QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self,
                 parent=None,
                 index=0,
                 editor: DiagramEditorWidget = None,
                 node: ConnectivityNode = None,
                 h: int = 40,
                 w: int = 40,
                 x: int = 0,
                 y: int = 0):
        """

        :param parent:
        :param index:
        :param editor:
        :param bus:
        :param h:
        :param w:
        :param x:
        :param y:
        """
        GenericDBWidget.__init__(self, parent=parent, api_object=node, editor=editor, draw_labels=True)
        QtWidgets.QGraphicsRectItem.__init__(self, parent)

        self.min_w = 5.0
        self.min_h = 5.0
        self.offset = 20
        self.h = h if h >= self.min_h else self.min_h
        self.w = w if w >= self.min_w else self.min_w

        # loads, shunts, generators, etc...
        self.shunt_children = list()

        # Enabled for short circuit
        self.sc_enabled = [False, False, False, False]
        self.sc_type = FaultType.ph3
        self.pen_width = 4

        # index
        self.index = index

        # Label:
        self.label = QtWidgets.QGraphicsTextItem(self.api_object.name if self.api_object is not None else "", self)
        self.label.setDefaultTextColor(ACTIVE['text'])
        self.label.setScale(FONT_SCALE)
        self.label.setPos(QPoint(self.w, 0))

        # connection terminals the block
        self._terminal = RoundTerminalItem('s', parent=self, editor=self.editor, h=20, w=20)  # , h=self.h))
        self._terminal.setPen(QPen(Qt.transparent, self.pen_width, self.style, Qt.RoundCap, Qt.RoundJoin))
        self._terminal.setPos(QPoint(15, 15))

        self.setPen(QPen(Qt.transparent, self.pen_width, self.style))
        self.setBrush(Qt.transparent)
        # self.setBrush(QBrush(QColor(255, 0, 0)))
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.set_position(x, y)
        self.setRect(0.0, 0.0, self.w, self.h)

    def recolour_mode(self) -> None:
        """
        Change the colour according to the system theme
        """
        super().recolour_mode()

        self.label.setDefaultTextColor(ACTIVE['text'])

        for e in self.shunt_children:
            if e is not None:
                e.recolour_mode()

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
                                           graphic_object=self)

    def set_position(self, x: int, y: int) -> None:
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

    def merge(self, other_bus_graphic: "CnGraphicItem") -> None:
        """
        Merge another BusGraphicItem into this
        :param other_bus_graphic: BusGraphicItem
        """
        self.shunt_children += other_bus_graphic.shunt_children

    def set_height(self, h: int):
        """
        Set the height of the
        :param h:
        :return:
        """
        self.setRect(0.0, 0.0, self.w, h)
        self.h = h

    def arrange_children(self) -> None:
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
        self._terminal.process_callbacks(parent_pos=self.pos())

    def create_children_widgets(self, injections_by_tpe: Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]):
        """
        Create the icons of the elements that are attached to the API bus object
        Returns:
            Nothing
        """

        for tpe, dev_list in injections_by_tpe.items():

            if tpe == DeviceType.LoadDevice:
                for elm in dev_list:
                    self.add_load(elm)

            elif tpe == DeviceType.StaticGeneratorDevice:
                for elm in dev_list:
                    self.add_static_generator(elm)

            elif tpe == DeviceType.GeneratorDevice:
                for elm in dev_list:
                    self.add_generator(elm)

            elif tpe == DeviceType.ShuntDevice:
                for elm in dev_list:
                    self.add_shunt(elm)

            elif tpe == DeviceType.BatteryDevice:
                for elm in dev_list:
                    self.add_battery(elm)

            elif tpe == DeviceType.ExternalGridDevice:
                for elm in dev_list:
                    self.add_external_grid(elm)

            elif tpe == DeviceType.CurrentInjectionDevice:
                for elm in dev_list:
                    self.add_current_injection(elm)

            elif tpe == DeviceType.ControllableShuntDevice:
                for elm in dev_list:
                    self.add_controllable_shunt(elm)

            else:
                raise Exception("Unknown device type:" + str(tpe))

        self.arrange_children()

    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Connectivity node")

        # dc = menu.addAction('Is a DC cn')
        # dc_icon = QIcon()
        # dc_icon.addPixmap(QPixmap(":/Icons/icons/dc.svg"))
        # dc.setIcon(dc_icon)
        # dc.setCheckable(True)
        # dc.setChecked(self.api_object.is_dc)
        # dc.triggered.connect(self.enable_disable_dc)

        pl = menu.addAction('Plot profiles')
        plot_icon = QIcon()
        plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
        pl.setIcon(plot_icon)
        pl.triggered.connect(self.plot_profiles)

        arr = menu.addAction('Arrange')
        arr_icon = QIcon()
        arr_icon.addPixmap(QPixmap(":/Icons/icons/automatic_layout.svg"))
        arr.setIcon(arr_icon)
        arr.triggered.connect(self.arrange_children)

        ra3 = menu.addAction('Delete all the connections')
        del2_icon = QIcon()
        del2_icon.addPixmap(QPixmap(":/Icons/icons/delete_conn.svg"))
        ra3.setIcon(del2_icon)
        ra3.triggered.connect(self.delete_all_connections)

        da = menu.addAction('Delete')
        del_icon = QIcon()
        del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
        da.setIcon(del_icon)
        da.triggered.connect(self.remove)

        menu.addSection("Add")

        al = menu.addAction('Load')
        al_icon = QIcon()
        al_icon.addPixmap(QPixmap(":/Icons/icons/add_load.svg"))
        al.setIcon(al_icon)
        al.triggered.connect(self.add_load)

        ac_i = menu.addAction('Current injection')
        ac_i_icon = QIcon()
        ac_i_icon.addPixmap(QPixmap(":/Icons/icons/add_load.svg"))
        ac_i.setIcon(ac_i_icon)
        ac_i.triggered.connect(self.add_current_injection)

        ash = menu.addAction('Shunt')
        ash_icon = QIcon()
        ash_icon.addPixmap(QPixmap(":/Icons/icons/add_shunt.svg"))
        ash.setIcon(ash_icon)
        ash.triggered.connect(self.add_shunt)

        acsh = menu.addAction('Controllable shunt')
        acsh_icon = QIcon()
        acsh_icon.addPixmap(QPixmap(":/Icons/icons/add_shunt.svg"))
        acsh.setIcon(acsh_icon)
        acsh.triggered.connect(self.add_controllable_shunt)

        acg = menu.addAction('Generator')
        acg_icon = QIcon()
        acg_icon.addPixmap(QPixmap(":/Icons/icons/add_gen.svg"))
        acg.setIcon(acg_icon)
        acg.triggered.connect(self.add_generator)

        asg = menu.addAction('Static generator')
        asg_icon = QIcon()
        asg_icon.addPixmap(QPixmap(":/Icons/icons/add_stagen.svg"))
        asg.setIcon(asg_icon)
        asg.triggered.connect(self.add_static_generator)

        ab = menu.addAction('Battery')
        ab_icon = QIcon()
        ab_icon.addPixmap(QPixmap(":/Icons/icons/add_batt.svg"))
        ab.setIcon(ab_icon)
        ab.triggered.connect(self.add_battery)

        aeg = menu.addAction('External grid')
        aeg_icon = QIcon()
        aeg_icon.addPixmap(QPixmap(":/Icons/icons/add_external_grid.svg"))
        aeg.setIcon(aeg_icon)
        aeg.triggered.connect(self.add_external_grid)

        menu.exec_(event.screenPos())

    def delete_all_connections(self) -> None:
        """
        Delete all bus connections
        """
        self._terminal.remove_all_connections()

    def remove(self, ask: bool = True) -> None:
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this bus', 'Remove bus')
        else:
            ok = True

        if ok:
            self.delete_all_connections()

            for g in self.shunt_children:
                self.editor.remove_from_scene(g.nexus)

            self.editor.remove_element(device=self.api_object, graphic_object=self)

    def enable_disable_dc(self):
        """
        Activates or deactivates the bus as a DC bus
        """
        if self.api_object.is_dc:
            self.api_object.is_dc = False
        else:
            self.api_object.is_dc = True

    def plot_profiles(self) -> None:
        """
        Plot profiles
        """
        # get the index of this object
        i = self.editor.circuit.get_buses().index(self.api_object)
        self.editor.plot_bus(i, self.api_object)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param event: QGraphicsSceneMouseEvent
        """

        if self.api_object.device_type == DeviceType.BusDevice:
            dictionary_of_lists = {DeviceType.AreaDevice.value: self.editor.circuit.get_areas(),
                                   DeviceType.ZoneDevice.value: self.editor.circuit.get_zones(),
                                   DeviceType.SubstationDevice.value: self.editor.circuit.get_substations(),
                                   DeviceType.VoltageLevelDevice.value: self.editor.circuit.get_voltage_levels(),
                                   DeviceType.CountryDevice.value: self.editor.circuit.get_countries()}

            self.editor.set_editor_model(api_object=self.api_object,
                                         dictionary_of_lists=dictionary_of_lists)

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        """
        Mouse double click
        :param event: event object
        """
        title = self.api_object.name if self.api_object is not None else ""
        msg = ""
        self.label.setHtml(f'<html><head/><body><p><span style=" font-size:10pt;">{title}<br/></span>'
                           f'<span style=" font-size:6pt;">{msg}</span></p></body></html>')

        self.setToolTip(msg)

    def get_terminal(self) -> RoundTerminalItem:
        """
        Get the hosting terminal of this bus object
        :return: TerminalItem
        """
        return self._terminal

    def add_object(self, api_obj: Union[None, INJECTION_DEVICE_TYPES] = None):
        """
        Add any recognized object
        :param api_obj: EditableDevice
        """

        if api_obj.device_type == DeviceType.GeneratorDevice:
            self.add_generator(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.LoadDevice:
            self.add_load(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.StaticGeneratorDevice:
            self.add_static_generator(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.ShuntDevice:
            self.add_shunt(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.BatteryDevice:
            self.add_battery(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.ExternalGridDevice:
            self.add_external_grid(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.CurrentInjectionDevice:
            self.add_current_injection(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.ControllableShuntDevice:
            self.add_controllable_shunt(api_obj=api_obj)

        else:
            raise Exception("Cannot add device of type {}".format(api_obj.device_type.value))

    def add_load(self, api_obj: Union[Load, None] = None):
        """
        Add load object to bus
        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_load(bus=self.api_object)

        _grph = LoadGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_shunt(self, api_obj: Union[Shunt, None] = None):
        """
        Add shunt device
        :param api_obj: If None, a new shunt is created
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_shunt(bus=self.api_object)

        _grph = ShuntGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_generator(self, api_obj: Union[Generator, None] = None):
        """
        Add generator
        :param api_obj: if None, a new generator is created
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_generator(bus=self.api_object)

        _grph = GeneratorGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_static_generator(self, api_obj: Union[StaticGenerator, None] = None):
        """
        Add static generator
        :param api_obj: If none, a new static generator is created
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_static_generator(bus=self.api_object)

        _grph = StaticGeneratorGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()

        return _grph

    def add_battery(self, api_obj: Union[Battery, None] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_battery(bus=self.api_object)

        _grph = BatteryGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()

        return _grph

    def add_external_grid(self, api_obj: Union[ExternalGrid, None] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_external_grid(bus=self.api_object)

        _grph = ExternalGridGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()

        return _grph

    def add_current_injection(self, api_obj: Union[CurrentInjection, None] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_current_injection(bus=self.api_object)

        _grph = CurrentInjectionGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()

        return _grph

    def add_controllable_shunt(self, api_obj: Union[ControllableShunt, None] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.editor.circuit.add_controllable_shunt(bus=self.api_object)

        _grph = ControllableShuntGraphicItem(parent=self, api_obj=api_obj, editor=self.editor)
        self.shunt_children.append(_grph)
        self.arrange_children()

        return _grph

    def set_values(self, i: int, Vm: float, Va: float, P: float, Q: float, tpe: str, format_str="{:10.2f}"):
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
        vm = format_str.format(Vm)
        vm_kv = format_str.format(Vm * self.api_object.Vnom)
        va = format_str.format(Va)
        msg = f"Bus {i}"
        if tpe is not None:
            msg += f" [{tpe}]"
        msg += "<br>"
        msg += f"v={vm}&lt;{va}º pu<br>"
        msg += f"V={vm_kv} kV<br>"
        if P is not None:
            p = format_str.format(P)
            q = format_str.format(Q)
            msg += f"P={p} MW<br>Q={q} MVAr"

        title = self.api_object.name if self.api_object is not None else ""
        self.label.setHtml(f'<html><head/><body><p><span style=" font-size:10pt;">{title}<br/></span>'
                           f'<span style=" font-size:6pt;">{msg}</span></p></body></html>')

        self.setToolTip(msg)

    def __str__(self):

        if self.api_object is None:
            return f"CN graphics {hex(id(self))}"
        else:
            return f"Graphics of {self.api_object.name} [{hex(id(self))}]"

    def __repr__(self):
        return str(self)
