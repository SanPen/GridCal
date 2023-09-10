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
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QCursor, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QGraphicsLineItem, QGraphicsItemGroup, QVBoxLayout, QGraphicsTextItem, QDialog
from GridCalEngine.Core.Devices.Injections.generator import Generator, DeviceType
from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Circle
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCal.Gui.messages import yes_no_question, info_msg
from GridCal.Gui.GridEditorWidget.matplotlibwidget import MatplotlibWidget
from GridCal.Gui.SolarPowerWizard.solar_power_wizzard import SolarPvWizard
from GridCal.Gui.WindPowerWizard.wind_power_wizzard import WindFarmWizard


class GeneratorEditor(QDialog):
    """
    GeneratorEditor
    """

    def __init__(self, generator: Generator):
        """
        Line Editor constructor
        :param generator: Generator object to update
        """
        super(GeneratorEditor, self).__init__()

        # keep pointer to the line object
        self.generator = generator

        self.selected_template = None

        self.setObjectName("self")

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.layout = QVBoxLayout(self)

        # create matplotlib object
        self.plotter = MatplotlibWidget(parent=self)
        self.layout.addWidget(self.plotter)

        self.setLayout(self.layout)

        self.plot_q_points()

    def plot_q_points(self):
        p = self.generator.q_points[:, 0]
        qmin = self.generator.q_points[:, 1]
        qmax = self.generator.q_points[:, 2]
        self.plotter.plot(qmax, p, 'x-')
        self.plotter.plot(qmin, p, 'x-')
        self.plotter.redraw()


class GeneratorGraphicItem(QGraphicsItemGroup):
    """
    GeneratorGraphicItem
    """

    def __init__(self, parent, api_obj, scene):
        """

        :param parent:
        :param api_obj:
        """
        super(GeneratorGraphicItem, self).__init__(parent)

        self.parent = parent

        self.api_object = api_obj

        self.scene = scene

        self.w = 40
        self.h = 40

        # Properties of the container:
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.width = 4
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

        # line to tie this object with the original bus (the parent)
        self.nexus = QGraphicsLineItem()
        self.nexus.setPen(QPen(self.color, self.width, self.style))
        self.scene.addItem(self.nexus)

        pen = QPen(self.color, self.width, self.style)

        self.glyph = Circle(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('G', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h / 4, self.w / 5)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_line(self.pos())

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

        pen = QPen(self.color, self.width, self.style)
        self.glyph.setPen(pen)
        self.nexus.setPen(pen)
        self.label.setDefaultTextColor(self.color)

    def update_line(self, pos):
        """
        Update the line that joins the parent and this object
        :param pos: position of this object
        """
        parent = self.parentItem()
        rect = parent.rect()
        self.nexus.setLine(
            pos.x() + self.w / 2,
            pos.y() + 0,
            parent.x() + rect.width() / 2,
            parent.y() + parent.terminal.y + 5,
        )
        self.setZValue(-1)
        self.nexus.setZValue(-1)

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Generator")

        pe = menu.addAction('Active')
        pe.setCheckable(True)
        pe.setChecked(self.api_object.active)
        pe.triggered.connect(self.enable_disable_toggle)

        pc = menu.addAction('Voltage control')
        pc.setCheckable(True)
        pc.setChecked(self.api_object.is_controlled)
        pc.triggered.connect(self.enable_disable_control_toggle)

        pa = menu.addAction('Plot profiles')
        plot_icon = QIcon()
        plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
        pa.setIcon(plot_icon)
        pa.triggered.connect(self.plot)

        pv = menu.addAction('Solar photovoltaic wizard')
        pv_icon = QIcon()
        pv_icon.addPixmap(QPixmap(":/Icons/icons/solar_power.svg"))
        pv.setIcon(pv_icon)
        pv.triggered.connect(self.solar_pv_wizard)

        wp = menu.addAction('Wind farm wizard')
        wp_icon = QIcon()
        wp_icon.addPixmap(QPixmap(":/Icons/icons/wind_power.svg"))
        wp.setIcon(wp_icon)
        wp.triggered.connect(self.wind_farm_wizard)

        menu.addSeparator()

        da = menu.addAction('Delete')
        del_icon = QIcon()
        del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
        da.setIcon(del_icon)
        da.triggered.connect(self.remove)

        cb = menu.addAction('Convert to battery')
        batt_icon = QIcon()
        batt_icon.addPixmap(QPixmap(":/Icons/icons/add_batt.svg"))
        cb.setIcon(batt_icon)
        cb.triggered.connect(self.to_battery)

        menu.exec_(event.screenPos())

    def to_battery(self):
        """
        Convert this generator to a battery
        """
        ok = yes_no_question('Are you sure that you want to convert this generator into a battery?',
                             'Convert generator')
        if ok:
            editor = self.scene.parent()
            editor.convert_generator_to_battery(gen=self.api_object)

    def remove(self, ask=True):
        """
        Remove this element
        @return:
        """
        if ask:
            ok = yes_no_question('Are you sure that you want to remove this generator', 'Remove generator')
        else:
            ok = True

        if ok:
            self.scene.removeItem(self.nexus)
            self.scene.removeItem(self)
            if self.api_object in self.api_object.bus.generators:
                self.api_object.bus.generators.remove(self.api_object)

    def enable_disable_toggle(self):
        """

        @return:
        """
        if self.api_object is not None:
            if self.api_object.active:
                self.set_enable(False)
            else:
                self.set_enable(True)

            if self.scene.circuit.has_time_series:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self.scene.set_active_status_to_profile(self.api_object, override_question=True)

    def enable_disable_control_toggle(self):
        """
        Enable / Disable device voltage control
        """
        if self.api_object is not None:
            self.api_object.is_controlled = not self.api_object.is_controlled

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
        self.glyph.setPen(QPen(self.color, self.width, self.style))
        self.label.setDefaultTextColor(self.color)

    def plot(self):
        """
        Plot API objects profiles
        """
        # time series object from the last simulation
        ts = self.scene.circuit.time_profile

        # plot the profiles
        self.api_object.plot_profiles(time=ts)

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        dlg = GeneratorEditor(self.api_object)
        if dlg.exec_():
            pass

    def solar_pv_wizard(self):
        """
        Open the appropriate editor dialogue
        :return:
        """

        if self.scene.circuit.has_time_series:

            time_array = self.scene.circuit.time_profile

            dlg = SolarPvWizard(time_array=time_array,
                                peak_power=self.api_object.Pmax,
                                latitude=self.api_object.bus.latitude,
                                longitude=self.api_object.bus.longitude,
                                gen_name=self.api_object.name,
                                bus_name=self.api_object.bus.name)
            if dlg.exec_():
                if dlg.is_accepted:
                    if len(dlg.P) == len(self.api_object.P_prof):
                        self.api_object.P_prof = dlg.P

                        self.plot()
                    else:
                        raise Exception("Wrong length from the solar photovoltaic wizard")
        else:
            info_msg("You need to have time profiles for this function")

    def wind_farm_wizard(self):
        """
        Open the appropriate editor dialogue
        :return:
        """

        if self.scene.circuit.has_time_series:

            time_array = self.scene.circuit.time_profile

            dlg = WindFarmWizard(time_array=time_array,
                                 peak_power=self.api_object.Pmax,
                                 latitude=self.api_object.bus.latitude,
                                 longitude=self.api_object.bus.longitude,
                                 gen_name=self.api_object.name,
                                 bus_name=self.api_object.bus.name)
            if dlg.exec_():
                if dlg.is_accepted:
                    if len(dlg.P) == len(self.api_object.P_prof):
                        self.api_object.P_prof = dlg.P

                        self.plot()
                    else:
                        raise Exception("Wrong length from the solar photovoltaic wizard")
        else:
            info_msg("You need to have time profiles for this function")

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        mdl = ObjectsModel([self.api_object],
                           self.api_object.editable_headers,
                           parent=self.scene.parent().object_editor_table,
                           editable=True,
                           transposed=True,
                           dictionary_of_lists={DeviceType.Technology.value: self.scene.circuit.technologies,
                                                DeviceType.FuelDevice.value: self.scene.circuit.fuels,
                                                DeviceType.EmissionGasDevice.value: self.scene.circuit.emission_gases,
                                                })
        self.scene.parent().object_editor_table.setModel(mdl)

    def mouseDoubleClickEvent(self, event):
        self.edit()
