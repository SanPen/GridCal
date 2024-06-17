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
from typing import TYPE_CHECKING
import numpy as np
from PySide6.QtGui import QPen, QFont
from PySide6.QtWidgets import (QMenu, QGraphicsTextItem)
from GridCalEngine.Devices.Injections.generator import Generator
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Circle
from GridCal.Gui.messages import yes_no_question, info_msg
from GridCal.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Injections.generator_editor import GeneratorQCurveEditor
from GridCal.Gui.SolarPowerWizard.solar_power_wizzard import SolarPvWizard
from GridCal.Gui.WindPowerWizard.wind_power_wizzard import WindFarmWizard
from GridCal.Gui.GuiFunctions import add_menu_entry

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class GeneratorGraphicItem(InjectionTemplateGraphicItem):
    """
    GeneratorGraphicItem
    """

    def __init__(self, parent, api_obj: Generator, editor: SchematicWidget):
        """

        :param parent:
        :param api_obj:
        :param editor:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='generator',
                                              w=40,
                                              h=40)

        pen = QPen(self.color, self.width, self.style)

        self.glyph = Circle(self)
        self.glyph.setRect(0, 0, self.h, self.w)
        self.glyph.setPen(pen)
        self.addToGroup(self.glyph)

        self.label = QGraphicsTextItem('G', parent=self.glyph)
        self.label.setDefaultTextColor(self.color)
        self.label.setPos(self.h / 4, self.w / 5)

        self.setPos(self.parent.x(), self.parent.y() + 100)
        self.update_nexus(self.pos())

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

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Generator")

        add_menu_entry(menu=menu,
                       text="Active",
                       icon_path="",
                       function_ptr=self.enable_disable_toggle,
                       checkeable=True,
                       checked_value=self.api_object.active)

        add_menu_entry(menu=menu,
                       text="Voltage control",
                       icon_path="",
                       function_ptr=self.enable_disable_control_toggle,
                       checkeable=True,
                       checked_value=self.api_object.is_controlled)

        add_menu_entry(menu=menu,
                       text="Set regulation bus",
                       icon_path="",
                       function_ptr=self.set_regulation_bus)

        add_menu_entry(menu=menu,
                       text="Set regulation cn",
                       icon_path="",
                       function_ptr=self.set_regulation_cn)

        add_menu_entry(menu=menu,
                       text="Qcurve edit",
                       function_ptr=self.edit_q_curve,
                       icon_path=":/Icons/icons/edit.svg")

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Plot profiles",
                       icon_path=":/Icons/icons/plot.svg",
                       function_ptr=self.plot)

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Solar photovoltaic wizard",
                       icon_path=":/Icons/icons/solar_power.svg",
                       function_ptr=self.solar_pv_wizard)

        add_menu_entry(menu=menu,
                       text="Wind farm wizard",
                       icon_path=":/Icons/icons/wind_power.svg",
                       function_ptr=self.wind_farm_wizard)

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Delete",
                       icon_path=":/Icons/icons/delete3.svg",
                       function_ptr=self.remove)

        add_menu_entry(menu=menu,
                       text="Convert to battery",
                       icon_path=":/Icons/icons/add_batt.svg",
                       function_ptr=self.to_battery)

        add_menu_entry(menu=menu,
                       text="Change bus",
                       icon_path=":/Icons/icons/move_bus.svg",
                       function_ptr=self.change_bus)

        menu.exec_(event.screenPos())

    def to_battery(self):
        """
        Convert this generator to a battery
        """
        ok = yes_no_question('Are you sure that you want to convert this generator into a battery?',
                             'Convert generator')
        if ok:
            self.editor.convert_generator_to_battery(gen=self.api_object, graphic_object=self)

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

    def enable_disable_control_toggle(self):
        """
        Enable / Disable device voltage control
        """
        if self.api_object is not None:
            self.api_object.is_controlled = not self.api_object.is_controlled

    def set_regulation_bus(self):
        """
        Set regulation bus
        :return:
        """
        self.editor.set_generator_control_bus(generator_graphics=self)

    def set_regulation_cn(self):
        """
        Set regulation bus
        :return:
        """
        self.editor.set_generator_control_cn(generator_graphics=self)

    def clear_regulation_bus(self):
        """

        :return:
        """
        self.api_object.control_bus = None

    def clear_regulation_cn(self):
        """

        :return:
        """
        self.api_object.control_cn = None

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
        ts = self.editor.circuit.time_profile

        # plot the profiles
        self.api_object.plot_profiles(time=ts)

    def edit_q_curve(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        dlg = GeneratorQCurveEditor(q_curve=self.api_object.q_curve,
                                    Qmin=self.api_object.Qmin,
                                    Qmax=self.api_object.Qmax,
                                    Pmin=self.api_object.Pmin,
                                    Pmax=self.api_object.Pmax,
                                    Snom=self.api_object.Snom)
        if dlg.exec():
            pass

        self.api_object.Snom = np.round(dlg.Snom, 1) if dlg.Snom > 1 else dlg.Snom
        self.api_object.Qmin = dlg.Qmin
        self.api_object.Qmax = dlg.Qmax
        self.api_object.Pmin = dlg.Pmin
        self.api_object.Pmax = dlg.Pmax

    def solar_pv_wizard(self):
        """
        Open the appropriate editor dialogue
        :return:
        """

        if self.editor.circuit.has_time_series:

            time_array = self.editor.circuit.time_profile

            dlg = SolarPvWizard(time_array=time_array,
                                peak_power=self.api_object.Pmax,
                                latitude=self.api_object.bus.latitude,
                                longitude=self.api_object.bus.longitude,
                                gen_name=self.api_object.name,
                                bus_name=self.api_object.bus.name)
            if dlg.exec_():
                if dlg.is_accepted:
                    if len(dlg.P) == self.api_object.P_prof.size():
                        self.api_object.P_prof.set(dlg.P)

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

        if self.editor.circuit.has_time_series:

            time_array = self.editor.circuit.time_profile

            dlg = WindFarmWizard(time_array=time_array,
                                 peak_power=self.api_object.Pmax,
                                 latitude=self.api_object.bus.latitude,
                                 longitude=self.api_object.bus.longitude,
                                 gen_name=self.api_object.name,
                                 bus_name=self.api_object.bus.name)
            if dlg.exec_():
                if dlg.is_accepted:
                    if len(dlg.P) == self.api_object.P_prof.size():
                        self.api_object.P_prof.set(dlg.P)
                        self.plot()
                    else:
                        raise Exception("Wrong length from the solar photovoltaic wizard")
        else:
            info_msg("You need to have time profiles for this function")

    def rescale(self, scale: float = 1.0):
        """

        :param scale:
        :return:
        """
        super().rescale(scale)
        pen = QPen(self.color, self.width / scale, self.style)

        self.glyph.setRect(0, 0, self.h / scale, self.w / scale)
        self.glyph.setPen(pen)

        font = QFont()
        scaleFt = 12 / scale
        if scaleFt < 1:
            scaleFt = 1
        font.setPointSize(scaleFt)  # Set the desired font size here

        # Set the font for the QGraphicsTextItem

        self.label.setFont(font)
        self.label.setPos((self.h / scale) / 4, (self.w / scale) / 5)
        # self.setRect(self.h / scale, self.w / scale)
        self.setPos(0, (100 / scale))
