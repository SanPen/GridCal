# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
from PySide6.QtGui import QPen, QFont
from PySide6.QtWidgets import (QMenu, QGraphicsTextItem)
from GridCalEngine.Devices.Injections.generator import Generator
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Circle
from GridCal.Gui.messages import yes_no_question, info_msg
from GridCal.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from GridCal.Gui.Diagrams.Editors.generator_editor import GeneratorQCurveEditor
from GridCal.Gui.SolarPowerWizard.solar_power_wizzard import SolarPvWizard
from GridCal.Gui.WindPowerWizard.wind_power_wizzard import WindFarmWizard
from GridCal.Gui.gui_functions import add_menu_entry

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
        self.set_glyph(glyph=Circle(self, 40, 40, "G", self.update_nexus))

    @property
    def api_object(self) -> Generator:
        return self._api_object

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

        add_menu_entry(menu, text='Remove',
                       icon_path=":/Icons/icons/delete_schematic.svg",
                       function_ptr=self.delete)

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
            self._editor.convert_generator_to_battery(gen=self.api_object, graphic_object=self)

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
        self._editor.set_generator_control_bus(generator_graphics=self)

    def set_regulation_cn(self):
        """
        Set regulation bus
        :return:
        """
        self._editor.set_generator_control_cn(generator_graphics=self)

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

        if self._editor.circuit.has_time_series:

            dlg = SolarPvWizard(time_array=self._editor.circuit.time_profile.strftime("%Y-%m-%d %H:%M").tolist(),
                                peak_power=self.api_object.Pmax,
                                latitude=self.api_object.bus.latitude,
                                longitude=self.api_object.bus.longitude,
                                gen_name=self.api_object.name,
                                bus_name=self.api_object.bus.name)
            if dlg.exec():
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

        if self._editor.circuit.has_time_series:

            dlg = WindFarmWizard(time_array=self._editor.circuit.time_profile.strftime("%Y-%m-%d %H:%M").tolist(),
                                 peak_power=self.api_object.Pmax,
                                 latitude=self.api_object.bus.latitude,
                                 longitude=self.api_object.bus.longitude,
                                 gen_name=self.api_object.name,
                                 bus_name=self.api_object.bus.name)
            if dlg.exec():
                if dlg.is_accepted:
                    if len(dlg.P) == self.api_object.P_prof.size():
                        self.api_object.P_prof.set(dlg.P)
                        self.plot()
                    else:
                        raise Exception("Wrong length from the solar photovoltaic wizard")
        else:
            info_msg("You need to have time profiles for this function")
