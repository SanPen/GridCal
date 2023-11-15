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

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QGraphicsScene
from GridCal.Gui.GridEditorWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from GridCal.Gui.GridEditorWidget.substation.bus_graphics import TerminalItem
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.GridEditorWidget.Branches.transformer_editor import TransformerEditor, reverse_transformer_short_circuit_study
from GridCalEngine.Core.Devices.Branches.transformer import Transformer2W, TransformerType
from GridCalEngine.enumerations import DeviceType


class TransformerGraphicItem(LineGraphicTemplateItem):
    """
    TransformerGraphicItem
    """

    def __init__(self, fromPort: TerminalItem, toPort: TerminalItem, editor, width=5,
                 api_object: Transformer2W = None):
        """

        :param fromPort:
        :param toPort:
        :param editor:
        :param width:
        :param api_object:
        """
        LineGraphicTemplateItem.__init__(self=self,
                                         fromPort=fromPort,
                                         toPort=toPort,
                                         editor=editor,
                                         width=width,
                                         api_object=api_object)

    def contextMenuEvent(self, event):
        """
        Show context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("Transformer")

            pe = menu.addAction('Active')
            pe.setCheckable(True)
            pe.setChecked(self.api_object.active)
            pe.triggered.connect(self.enable_disable_toggle)

            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.remove)

            re = menu.addAction('Reduce')
            re_icon = QIcon()
            re_icon.addPixmap(QPixmap(":/Icons/icons/grid_reduction.svg"))
            re.setIcon(re_icon)
            re.triggered.connect(self.reduce)

            ra3 = menu.addAction('Editor')
            edit_icon = QIcon()
            edit_icon.addPixmap(QPixmap(":/Icons/icons/edit.svg"))
            ra3.setIcon(edit_icon)
            ra3.triggered.connect(self.edit)

            rabf = menu.addAction('Change bus')
            move_bus_icon = QIcon()
            move_bus_icon.addPixmap(QPixmap(":/Icons/icons/move_bus.svg"))
            rabf.setIcon(move_bus_icon)
            rabf.triggered.connect(self.change_bus)

            menu.addSeparator()

            ra6 = menu.addAction('Plot profiles')
            plot_icon = QIcon()
            plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
            ra6.setIcon(plot_icon)
            ra6.triggered.connect(self.plot_profiles)

            ra3 = menu.addAction('Add to catalogue')
            ra3_icon = QIcon()
            ra3_icon.addPixmap(QPixmap(":/Icons/icons/Catalogue.svg"))
            ra3.setIcon(ra3_icon)
            ra3.triggered.connect(self.add_to_catalogue)

            ra4 = menu.addAction('Assign rate to profile')
            ra4_icon = QIcon()
            ra4_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra4.setIcon(ra4_icon)
            ra4.triggered.connect(self.assign_rate_to_profile)

            ra5 = menu.addAction('Assign active state to profile')
            ra5_icon = QIcon()
            ra5_icon.addPixmap(QPixmap(":/Icons/icons/assign_to_profile.svg"))
            ra5.setIcon(ra5_icon)
            ra5.triggered.connect(self.assign_status_to_profile)

            ra7 = menu.addAction('Flip')
            ra7_icon = QIcon()
            ra7_icon.addPixmap(QPixmap(":/Icons/icons/redo.svg"))
            ra7.setIcon(ra7_icon)
            ra7.triggered.connect(self.flip_connections)

            menu.addSection('Tap changer')

            ra4 = menu.addAction('Tap up')
            ra4_icon = QIcon()
            ra4_icon.addPixmap(QPixmap(":/Icons/icons/up.svg"))
            ra4.setIcon(ra4_icon)
            ra4.triggered.connect(self.tap_up)

            ra5 = menu.addAction('Tap down')
            ra5_icon = QIcon()
            ra5_icon.addPixmap(QPixmap(":/Icons/icons/down.svg"))
            ra5.setIcon(ra5_icon)
            ra5.triggered.connect(self.tap_down)

            menu.exec_(event.screenPos())

        else:
            pass

    def mouseDoubleClickEvent(self, event):
        """
        On double click, edit
        :param event:
        :return:
        """

        if self.api_object is not None:
            if self.api_object.device_type in [DeviceType.Transformer2WDevice, DeviceType.LineDevice]:
                # trigger the editor
                self.edit()
            elif self.api_object.device_type is DeviceType.SwitchDevice:
                # change state
                self.enable_disable_toggle()

    def edit(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase
        templates = self.editor.circuit.transformer_types
        current_template = self.api_object.template
        dlg = TransformerEditor(self.api_object, Sbase,
                                modify_on_accept=True,
                                templates=templates,
                                current_template=current_template)
        if dlg.exec_():
            pass

    def show_transformer_editor(self):
        """
        Open the appropriate editor dialogue
        :return:
        """
        Sbase = self.editor.circuit.Sbase

        if self.api_object.template is not None:
            # automatically pick the template
            if isinstance(self.api_object.template, TransformerType):
                self.editor.circuit.add_transformer_type(self.api_object.template)
            else:
                # raise dialogue to set the template
                dlg = TransformerEditor(self.api_object, Sbase, modify_on_accept=False)
                if dlg.exec_():
                    tpe = dlg.get_template()
                    self.editor.circuit.add_transformer_type(tpe)
        else:
            # raise dialogue to set the template
            dlg = TransformerEditor(self.api_object, Sbase, modify_on_accept=False)
            if dlg.exec_():
                tpe = dlg.get_template()
                self.editor.circuit.add_transformer_type(tpe)

    def add_to_catalogue(self):
        """
        Add this object to the catalogue
        :return:
        """

        ok = yes_no_question(text="A template will be generated using this transformer values",
                             title="Add transformer type")

        if ok:
            Pfe, Pcu, Vsc, I0, Sn = reverse_transformer_short_circuit_study(transformer_obj=self.api_object,
                                                                            Sbase=self.editor.circuit.Sbase)

            tpe = TransformerType(hv_nominal_voltage=self.api_object.HV,
                                  lv_nominal_voltage=self.api_object.LV,
                                  nominal_power=Sn,
                                  copper_losses=Pcu,
                                  iron_losses=Pfe,
                                  no_load_current=I0,
                                  short_circuit_voltage=Vsc,
                                  gr_hv1=0.5,
                                  gx_hv1=0.5,
                                  name='type from ' + self.api_object.name)

            self.editor.circuit.add_transformer_type(tpe)

    def flip_connections(self):
        """
        Flip connections
        :return:
        """
        self.api_object.flip()

    def tap_up(self):
        """
        Set one tap up
        """
        self.api_object.tap_up()

    def tap_down(self):
        """
        Set one tap down
        """
        self.api_object.tap_down()
