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
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPen, QCursor, QIcon, QPixmap, QBrush, QColor
from PySide6.QtWidgets import QMenu
from GridCalEngine.Core.Devices.Substation import Bus
from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, FONT_SCALE, EMERGENCY
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCalEngine.Simulations.Topology.topology_driver import reduce_buses
from GridCal.Gui.GridEditorWidget.terminal_item import TerminalItem, HandleItem
from GridCal.Gui.GridEditorWidget.Injections.load_graphics import LoadGraphicItem
from GridCal.Gui.GridEditorWidget.Injections.generator_graphics import GeneratorGraphicItem
from GridCal.Gui.GridEditorWidget.Injections.static_generator_graphics import StaticGeneratorGraphicItem
from GridCal.Gui.GridEditorWidget.Injections.battery_graphics import BatteryGraphicItem
from GridCal.Gui.GridEditorWidget.Injections.shunt_graphics import ShuntGraphicItem
from GridCal.Gui.GridEditorWidget.Injections.external_grid_graphics import ExternalGridGraphicItem
from GridCal.Gui.messages import yes_no_question
from GridCalEngine.enumerations import DeviceType, FaultType
from GridCalEngine.Core.Devices.editable_device import EditableDevice


class BusGraphicItem(QtWidgets.QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self, scene, parent=None, index=0, editor=None, bus: Bus = None,
                 h: int = 20, w: int = 80, x: int = 0, y: int = 0):
        """

        @param scene:
        @param parent:
        @param index:
        @param editor:
        """
        super(BusGraphicItem, self).__init__(parent)

        self.min_w = 180.0
        self.min_h = 20.0
        self.offset = 10
        self.h = h if h >= self.min_h else self.min_h
        self.w = w if w >= self.min_w else self.min_w

        self.api_object = bus

        self.scene = scene  # this is the parent that hosts the pointer to the circuit

        self.editor = editor

        # loads, shunts, generators, etc...
        self.shunt_children = list()

        # Enabled for short circuit
        self.sc_enabled = [False, False, False, False]
        self.sc_type = FaultType.ph3
        self.pen_width = 4

        # index
        self.index = index

        # color
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

        # Label:
        self.label = QtWidgets.QGraphicsTextItem(bus.name, self)
        self.label.setDefaultTextColor(ACTIVE['text'])
        self.label.setScale(FONT_SCALE)

        # square
        self.tile = QtWidgets.QGraphicsRectItem(0, 0, self.min_h, self.min_h, self)
        self.tile.setOpacity(0.7)

        # connection terminals the block
        self.terminal = TerminalItem('s', parent=self, editor=self.editor)  # , h=self.h))
        self.terminal.setPen(QPen(Qt.transparent, self.pen_width, self.style, Qt.RoundCap, Qt.RoundJoin))

        # Create corner for resize:
        self.sizer = HandleItem(self.terminal)
        self.sizer.setPos(self.w, self.h)
        self.sizer.posChangeCallbacks.append(self.change_size)  # Connect the callback
        self.sizer.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.adapt()

        self.big_marker = None

        self.set_tile_color(self.color)

        self.setPen(QPen(Qt.transparent, self.pen_width, self.style))
        self.setBrush(Qt.transparent)
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Update size:
        self.change_size(self.w, self.h)

        self.set_position(x, y)

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

        self.label.setDefaultTextColor(ACTIVE['text'])
        self.set_tile_color(self.color)

        for e in self.shunt_children:
            if e is not None:
                e.recolour_mode()

    def set_label(self, val: str):
        """
        Set the label content
        :param val:
        :return:
        """
        self.label.setPlainText(val)

    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """
        On mouse move of this object...
        Args:
            event: QGraphicsSceneMouseEvent inherited
        """
        super().mouseMoveEvent(event)

        self.scene.parent_.update_diagram_element(device=self.api_object,
                                                  x=self.pos().x(),
                                                  y=self.pos().y(),
                                                  w=self.w,
                                                  h=self.h,
                                                  r=self.rotation(),
                                                  graphic_object=self)

    def add_big_marker(self, color=Qt.red, tool_tip_text=""):
        """
        Add a big marker to the bus
        :param color: Qt Color ot the marker
        :param tool_tip_text: tool tip text to display
        :return:
        """
        if self.big_marker is None:
            self.big_marker = QtWidgets.QGraphicsEllipseItem(0, 0, 180, 180, parent=self)
            self.big_marker.setBrush(color)
            self.big_marker.setOpacity(0.5)
            self.big_marker.setToolTip(tool_tip_text)

    def delete_big_marker(self):
        """
        Delete the big marker
        """
        if self.big_marker is not None:
            self.scene.removeItem(self.big_marker)
            self.big_marker = None

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

    def set_tile_color(self, brush):
        """
        Set the color of the title
        Args:
            brush:  Qt Color
        """
        self.tile.setBrush(brush)
        self.terminal.setBrush(brush)

    def merge(self, other_bus_graphic):

        self.shunt_children += other_bus_graphic.shunt_children

    def update(self):
        """
        Update the object
        :return:
        """
        self.change_size(self.w, self.h)

    def set_height(self, h):

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
        if h is None:
            h = self.min_h

        if w < self.min_w:
            w = self.min_w

        self.setRect(0.0, 0.0, w, h)
        self.h = h
        self.w = w

        # center label:
        rect = self.label.boundingRect()
        lw, lh = rect.width(), rect.height()
        lx = (w - lw) / 2
        ly = (h - lh) / 2 - lh * (FONT_SCALE - 1)
        self.label.setPos(lx, ly)

        # lower
        y0 = h + self.offset
        x0 = 0
        self.terminal.setPos(x0, y0)
        self.terminal.setRect(0, 0, w, 10)

        # Set text
        if self.api_object is not None:
            self.label.setPlainText(self.api_object.name)

        # rearrange children
        self.arrange_children()

        self.scene.parent_.update_diagram_element(device=self.api_object,
                                                  x=self.pos().x(),
                                                  y=self.pos().y(),
                                                  w=w,
                                                  h=h,
                                                  r=self.rotation(),
                                                  graphic_object=self)

        return w, h

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
        self.terminal.process_callbacks(self.pos() + self.terminal.pos())

    def create_children_widgets(self):
        """
        Create the icons of the elements that are attached to the API bus object
        Returns:
            Nothing
        """
        for elm in self.api_object.loads:
            self.add_load(elm)

        for elm in self.api_object.static_generators:
            self.add_static_generator(elm)

        for elm in self.api_object.generators:
            self.add_generator(elm)

        for elm in self.api_object.shunts:
            self.add_shunt(elm)

        for elm in self.api_object.batteries:
            self.add_battery(elm)

        self.arrange_children()

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Bus")

        pe = menu.addAction('Active')
        pe.setCheckable(True)
        pe.setChecked(self.api_object.active)
        pe.triggered.connect(self.enable_disable_toggle)

        sc = menu.addMenu('Short circuit')
        sc_icon = QIcon()
        sc_icon.addPixmap(QPixmap(":/Icons/icons/short_circuit.svg"))
        sc.setIcon(sc_icon)
        # sc.setCheckable(True)
        # sc.setChecked(self.sc_enabled)
        # sc.triggered.connect(self.enable_disable_sc)

        sc_3p = sc.addAction('3-phase')
        sc_3p_icon = QIcon()
        sc_3p_icon.addPixmap(QPixmap(":/Icons/icons/short_circuit.svg"))
        sc_3p.setIcon(sc_3p_icon)
        sc_3p.setCheckable(True)
        sc_3p.setChecked(self.sc_enabled[0])
        sc_3p.triggered.connect(self.enable_disable_sc_3p)

        sc_lg = sc.addAction('Line-Ground')
        sc_lg_icon = QIcon()
        sc_lg_icon.addPixmap(QPixmap(":/Icons/icons/short_circuit.svg"))
        sc_lg.setIcon(sc_lg_icon)
        sc_lg.setCheckable(True)
        sc_lg.setChecked(self.sc_enabled[1])
        sc_lg.triggered.connect(self.enable_disable_sc_lg)

        sc_ll = sc.addAction('Line-Line')
        sc_ll_icon = QIcon()
        sc_ll_icon.addPixmap(QPixmap(":/Icons/icons/short_circuit.svg"))
        sc_ll.setIcon(sc_ll_icon)
        sc_ll.setCheckable(True)
        sc_ll.setChecked(self.sc_enabled[2])
        sc_ll.triggered.connect(self.enable_disable_sc_ll)

        sc_llg = sc.addAction('Line-Line-Ground')
        sc_llg_icon = QIcon()
        sc_llg_icon.addPixmap(QPixmap(":/Icons/icons/short_circuit.svg"))
        sc_llg.setIcon(sc_llg_icon)
        sc_llg.setCheckable(True)
        sc_llg.setChecked(self.sc_enabled[3])
        sc_llg.triggered.connect(self.enable_disable_sc_llg)

        sc_no = sc.addAction('Disable')
        # sc_no_icon = QIcon()
        # sc_no_icon.addPixmap(QPixmap(":/Icons/icons/short_circuit.svg"))
        # sc_no.setIcon(sc_no_icon)
        # sc_no.setCheckable(True)
        # sc_no.setChecked(self.api_object.is_dc)
        sc_no.triggered.connect(self.disable_sc)

        # types
        # ph3 = '3x'
        # LG = 'LG'
        # LL = 'LL'
        # LLG = 'LLG'

        dc = menu.addAction('Is a DC bus')
        dc_icon = QIcon()
        dc_icon.addPixmap(QPixmap(":/Icons/icons/dc.svg"))
        dc.setIcon(dc_icon)
        dc.setCheckable(True)
        dc.setChecked(self.api_object.is_dc)
        dc.triggered.connect(self.enable_disable_dc)

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

        ra5 = menu.addAction('Assign active state to profile')
        ra5_icon = QIcon()
        ra5_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
        ra5.setIcon(ra5_icon)
        ra5.triggered.connect(self.assign_status_to_profile)

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

        re = menu.addAction('Reduce')
        re_icon = QIcon()
        re_icon.addPixmap(QPixmap(":/Icons/icons/grid_reduction.svg"))
        re.setIcon(re_icon)
        re.triggered.connect(self.reduce)

        menu.addSection("Add")

        al = menu.addAction('Load')
        al_icon = QIcon()
        al_icon.addPixmap(QPixmap(":/Icons/icons/add_load.svg"))
        al.setIcon(al_icon)
        al.triggered.connect(self.add_load)

        ash = menu.addAction('Shunt')
        ash_icon = QIcon()
        ash_icon.addPixmap(QPixmap(":/Icons/icons/add_shunt.svg"))
        ash.setIcon(ash_icon)
        ash.triggered.connect(self.add_shunt)

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

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self.scene.set_active_status_to_profile(self.api_object)

    def delete_all_connections(self):
        """
        Delete all bus connections
        """
        self.terminal.remove_all_connections()

    def reduce(self):
        """
        Reduce this bus
        :return:
        """
        ok = yes_no_question('Are you sure that you want to reduce this bus', 'Reduce bus')
        if ok:
            reduce_buses(self.scene.circuit, [self.api_object])
            self.remove()

    def remove(self, ask=True):
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
                self.scene.removeItem(g.nexus)

            self.scene.removeItem(self)
            self.scene.circuit.delete_bus(self.api_object, ask)

    def update_color(self):
        if self.api_object.active:
            self.set_tile_color(QBrush(ACTIVE['color']))
        else:
            self.set_tile_color(QBrush(DEACTIVATED['color']))

    def enable_disable_toggle(self):
        """
        Toggle bus element state
        @return:
        """
        if self.api_object is not None:

            # change the bus state (snapshot)
            self.api_object.active = not self.api_object.active

            # change the Branches state (snapshot)
            for host in self.terminal.hosting_connections:
                if host.api_object is not None:
                    host.set_enable(val=self.api_object.active)

            self.update_color()

            if self.scene.circuit.has_time_series:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.scene.set_active_status_to_profile(self.api_object, override_question=True)

                    # change the Branches state (time series)
                    for host in self.terminal.hosting_connections:
                        if host.api_object is not None:
                            self.scene.set_active_status_to_profile(host.api_object, override_question=True)

    def any_short_circuit(self):
        for t in self.sc_enabled:
            if t:
                return True
        return False

    def enable_sc(self):
        """

        Returns:

        """
        self.tile.setPen(QPen(QColor(EMERGENCY['color']), self.pen_width))

    def disable_sc(self):
        """

        Returns:

        """
        # self.tile.setPen(QPen(QColor(ACTIVE['color']), self.pen_width))
        self.tile.setPen(QPen(Qt.transparent, self.pen_width))
        self.sc_enabled = [False, False, False, False]

    def enable_disable_sc_3p(self):
        self.sc_enabled = [True, False, False, False]
        self.sc_type = FaultType.ph3
        self.enable_sc()

    def enable_disable_sc_lg(self):
        self.sc_enabled = [False, True, False, False]
        self.sc_type = FaultType.LG
        self.enable_sc()

    def enable_disable_sc_ll(self):
        self.sc_enabled = [False, False, True, False]
        self.sc_type = FaultType.LL
        self.enable_sc()

    def enable_disable_sc_llg(self):
        self.sc_enabled = [False, False, False, True]
        self.sc_type = FaultType.LLG
        self.enable_sc()

    def enable_disable_dc(self):
        """
        Activates or deactivates the bus as a DC bus
        """
        if self.api_object.is_dc:
            self.api_object.is_dc = False
        else:
            self.api_object.is_dc = True

    def plot_profiles(self):
        """

        @return:
        """
        # get the index of this object
        i = self.editor.circuit.buses.index(self.api_object)
        self.editor.diagramScene.plot_bus(i, self.api_object)

    def mousePressEvent(self, event):
        """
        mouse press: display the editor
        :param event: QGraphicsSceneMouseEvent
        """
        dictionary_of_lists = dict()

        if self.api_object.device_type == DeviceType.BusDevice:
            dictionary_of_lists = {DeviceType.AreaDevice.value: self.scene.circuit.areas,
                                   DeviceType.ZoneDevice.value: self.scene.circuit.zones,
                                   DeviceType.SubstationDevice.value: self.scene.circuit.substations,
                                   DeviceType.CountryDevice.value: self.scene.circuit.countries}

        mdl = ObjectsModel([self.api_object],
                           self.api_object.editable_headers,
                           parent=self.scene.parent().object_editor_table,
                           editable=True,
                           transposed=True,
                           dictionary_of_lists=dictionary_of_lists)

        self.scene.parent().object_editor_table.setModel(mdl)

    def mouseDoubleClickEvent(self, event):
        """
        Mouse double click
        :param event: event object
        """
        self.adapt()

    def adapt(self):
        """
        Set the bus width according to the label text
        """
        # Todo: fix the resizing on double click
        h = self.terminal.boundingRect().height()
        w = len(self.api_object.name) * 8 + 10
        self.change_size(w=w, h=h)
        self.sizer.setPos(w, self.h)

    def add_hosting_connection(self, graphic_obj):
        """
        Add object graphically connected to the graphical bus
        :param graphic_obj:
        :return:
        """
        self.terminal.hosting_connections.append(graphic_obj)

    def delete_hosting_connection(self, graphic_obj):
        """
        Delete object graphically connected to the graphical bus
        :param graphic_obj:
        :return:
        """
        self.terminal.hosting_connections.remove(graphic_obj)

    def add_object(self, api_obj: Union[None, EditableDevice] = None):
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

        else:
            raise Exception("Cannot add device of type {}".format(api_obj.device_type.value))

    def add_load(self, api_obj=None):
        """
        Add load object to bus
        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.scene.circuit.add_load(bus=self.api_object)

        _grph = LoadGraphicItem(parent=self, api_obj=api_obj, diagramScene=self.scene)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_shunt(self, api_obj=None):
        """
        Add shunt device
        :param api_obj: If None, a new shunt is created
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.scene.circuit.add_shunt(bus=self.api_object)

        _grph = ShuntGraphicItem(parent=self, api_obj=api_obj, diagramScene=self.scene)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_generator(self, api_obj=None):
        """
        Add generator
        :param api_obj: if None, a new generator is created
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.scene.circuit.add_generator(bus=self.api_object)

        _grph = GeneratorGraphicItem(parent=self, api_obj=api_obj, diagramScene=self.scene)
        self.shunt_children.append(_grph)
        self.arrange_children()
        return _grph

    def add_static_generator(self, api_obj=None):
        """
        Add static generator
        :param api_obj: If none, a new static generator is created
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.scene.circuit.add_static_generator(bus=self.api_object)

        _grph = StaticGeneratorGraphicItem(parent=self, api_obj=api_obj, diagramScene=self.scene)
        self.shunt_children.append(_grph)
        self.arrange_children()

        return _grph

    def add_battery(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.scene.circuit.add_battery(bus=self.api_object)

        _grph = BatteryGraphicItem(parent=self, api_obj=api_obj, diagramScene=self.scene)
        self.shunt_children.append(_grph)
        self.arrange_children()

        return _grph

    def add_external_grid(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.scene.circuit.add_external_grid(bus=self.api_object)

        _grph = ExternalGridGraphicItem(parent=self, api_obj=api_obj, diagramScene=self.scene)
        self.shunt_children.append(_grph)
        self.arrange_children()

        return _grph
