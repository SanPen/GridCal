# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import webbrowser
from typing import List, TYPE_CHECKING, Tuple
from PySide6 import QtWidgets
from PySide6.QtWidgets import QMenu, QGraphicsSceneContextMenuEvent, QGraphicsSceneMouseEvent, QGraphicsRectItem
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor

from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from GridCal.Gui.Diagrams.MapWidget.Substation.node_template import NodeTemplate
from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.messages import yes_no_question, info_msg
from GridCal.Gui.general_dialogues import InputNumberDialogue, CheckListDialogue
from GridCal.Gui.object_model import ObjectsModel
from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget import schematic_widget

from GridCalEngine.Devices.types import ALL_DEV_TYPES, INJECTION_DEVICE_TYPES, BRANCH_TYPES
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices import VoltageLevel
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class SubstationGraphicItem(NodeTemplate, QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self,
                 editor: GridMapWidget,
                 api_object: Substation,
                 lat: float,
                 lon: float,
                 size: float = 0.8,
                 draw_labels: bool = True):
        """

        :param editor:
        :param api_object:
        :param lat:
        :param lon:
        :param size:
        """
        # Correct way to call multiple inheritance
        super().__init__()

        # Explicitly call QGraphicsRectItem initialization
        QGraphicsRectItem.__init__(self)

        # Explicitly call NodeTemplate initialization
        NodeTemplate.__init__(self, api_object=api_object,
                              editor=editor,
                              draw_labels=draw_labels,
                              lat=lat,
                              lon=lon)

        self.size = size
        self.line_container = None
        self.editor: GridMapWidget = editor  # reassign for the types to be clear

        r2 = size / 2.0
        x, y = editor.to_x_y(lat=lat, lon=lon)  # upper left corner
        self.setRect(x - r2, y - r2, self.size, self.size)

        # Enable hover events for the item
        self.setAcceptHoverEvents(True)

        # Allow selecting the node
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Create a pen with reduced line width
        self.change_pen_width(0.05 * size)

        # Create a pen with reduced line width
        self._color = QColor(self.api_object.color)
        self._color.setAlpha(128)
        self._hoover_color = QColor(self.api_object.color)
        self._hoover_color.setAlpha(180)
        self._border_color = QColor(self.api_object.color)  # No Alpha

        self.set_default_color()

        # list of voltage levels graphics
        self.voltage_level_graphics: List[VoltageLevelGraphicItem] = list()

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, val: QColor):
        self._color = val

    @property
    def hover_color(self) -> QColor:
        return self._hoover_color

    @hover_color.setter
    def hover_color(self, val: QColor):
        self._hoover_color = val

    @property
    def border_color(self) -> QColor:
        return self._border_color

    @border_color.setter
    def border_color(self, val: QColor):
        self._border_color = val

    @property
    def api_object(self) -> Substation:
        return self._api_object

    def merge(self, se: "SubstationGraphicItem"):
        """
        Merge a substation into this one
        :param se: other SubstationGraphicItem
        """

        # merge the hosting connections
        for key, val in se._hosting_connections.items():
            self._hosting_connections[key] = val

        for vl_graphic in se.voltage_level_graphics:
            self.register_voltage_level(vl=vl_graphic.get_copy(new_parent=self))

        self.sort_voltage_levels()

    def set_size(self, r: float):
        """

        :param r: radius in pixels
        :return:
        """
        if r != self.size:
            rect = self.rect()
            rect.setWidth(r)
            rect.setHeight(r)

            # change the width and height while keeping the same center
            r2 = (self.size - r) / 2
            new_x = rect.x() + r2
            new_y = rect.y() + r2

            self.size = r

            # Set the new rectangle with the updated dimensions
            self.setRect(new_x, new_y, r, r)

            # update the callbacks position for the lines to move accordingly
            r3 = r / 2
            xc = new_x + r3
            yc = new_y + r3
            self.set_callbacks(xc, yc)

            for vl_graphics in self.voltage_level_graphics:
                vl_graphics.center_on_substation()

            self.change_pen_width(0.05 * self.size)

            self.update_position_at_the_diagram()

            self.resize_voltage_levels()

    def resize_voltage_levels(self) -> None:
        """

        :return:
        """
        max_vl = 1.0  # 1 KV
        for vl_graphics in self.voltage_level_graphics:
            max_vl = max(max_vl, vl_graphics.api_object.Vnom)

        for vl_graphics in self.voltage_level_graphics:
            # radius here is the width, therefore we need to send W/2
            scale = vl_graphics.api_object.Vnom / max_vl * 0.5
            vl_graphics.set_size(r=self.size * scale)
            vl_graphics.center_on_substation()

    def set_api_object_color(self) -> None:
        """
        Gather the API object color and update this objects
        """
        self.color = QColor(self.api_object.color)
        self.color.setAlpha(128)

        self.hover_color = QColor(self.api_object.color)
        self.hover_color.setAlpha(180)

        self.border_color = QColor(self.api_object.color)  # No Alpha

        self.set_default_color()

    def move_to(self, lat: float, lon: float) -> Tuple[float, float]:
        """

        :param lat:
        :param lon:
        :return: x, y
        """
        x, y = self.editor.to_x_y(lat=lat, lon=lon)  # upper left corner

        self.setRect(
            x - self.rect().width() / 2,
            y - self.rect().height() / 2,
            self.rect().width(),
            self.rect().height()
        )

        for vl in self.voltage_level_graphics:
            vl.center_on_substation()

        return x, y

    def register_voltage_level(self, vl: VoltageLevelGraphicItem):
        """

        :param vl:
        :return:
        """
        self.voltage_level_graphics.append(vl)
        vl.center_on_substation()

    def sort_voltage_levels(self) -> None:
        """
        Set the Z-order based on the voltage level voltage
        """
        max_vl = 1.0  # 1 KV
        for vl_graphics in self.voltage_level_graphics:
            max_vl = max(max_vl, vl_graphics.api_object.Vnom)

        for vl_graphics in self.voltage_level_graphics:
            scale = vl_graphics.api_object.Vnom / max_vl * 0.8
            vl_graphics.set_size(r=self.size * scale)
            vl_graphics.center_on_substation()

        sorted_objects = sorted(self.voltage_level_graphics, key=lambda x: -x.api_object.Vnom)
        for i, vl_graphics in enumerate(sorted_objects):
            vl_graphics.setZValue(i)

    def update_position_at_the_diagram(self) -> None:
        """
        Updates the element position in the diagram (to save)
        :return: 
        """
        lat, long = self.editor.to_lat_lon(self.rect().x(), self.rect().y())

        self.lat = lat
        self.lon = long

        self.editor.update_diagram_element(device=self.api_object,
                                           latitude=lat,
                                           longitude=long,
                                           graphic_object=self)

    def refresh(self, pos: QPointF):
        """
        This function refreshes the x, y coordinates of the graphic item
        Returns:

        """

        x = pos.x() - self.rect().width() / 2
        y = pos.y() - self.rect().height() / 2
        self.setRect(x, y, self.rect().width(), self.rect().height())
        self.set_callbacks(pos.x(), pos.y())

        for vl_graphics in self.voltage_level_graphics:
            vl_graphics.center_on_substation()

        self.update_position_at_the_diagram()  # always update

    def get_center_pos(self) -> QPointF:
        """
        Get the center position
        :return: QPointF
        """
        x = self.rect().x() + self.rect().width() / 2
        y = self.rect().y() + self.rect().height() / 2
        return QPointF(x, y)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Event handler for mouse move events.
        """

        if self.hovered:
            # super().mouseMoveEvent(event)
            pos = self.mapToParent(event.pos())
            self.refresh(pos=pos)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse press events.
        """
        super().mousePressEvent(event)
        # selected_items = self.editor.map.view.selected_items()
        # if len(selected_items) < 2:
        self.setSelected(True)

        event.setAccepted(True)
        self.editor.map.view.disable_move = True

        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """
        Event handler for mouse release events.
        """
        # super().mouseReleaseEvent(event)
        self.editor.disableMove = True
        self.update_position_at_the_diagram()  # always update

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse enters the item.
        """
        # self.editor.map.view.in_item = True
        self.color_widget(self.color, self.hover_color)
        self.hovered = True

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Event handler for when the mouse leaves the item.
        """
        self.hovered = False
        self.color_widget(self.color, self.border_color)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """

        :param event:
        """
        menu = QMenu()

        add_menu_entry(menu=menu,
                       text="Add voltage level",
                       icon_path=":/Icons/icons/plus.svg",
                       function_ptr=self.add_voltage_level)

        add_menu_entry(menu=menu,
                       text="Create line from here",
                       icon_path=":/Icons/icons/plus.svg",
                       function_ptr=self.create_new_line)

        add_menu_entry(menu=menu,
                       text="Merge selected substations here",
                       icon_path=":/Icons/icons/fusion.svg",
                       function_ptr=self.merge_selected_substations)

        add_menu_entry(menu=menu,
                       text="Set coordinates to DB",
                       icon_path=":/Icons/icons/down.svg",
                       function_ptr=self.move_to_api_coordinates)

        add_menu_entry(menu=menu,
                       text="Remove substation",
                       icon_path=":/Icons/icons/delete_schematic.svg",
                       function_ptr=self.delete)

        add_menu_entry(menu=menu,
                       text="Substation diagram",
                       icon_path=":/Icons/icons/grid_icon.svg",
                       function_ptr=self.new_substation_diagram)

        add_menu_entry(menu=menu,
                       text="Plot",
                       icon_path=":/Icons/icons/plot.svg",
                       function_ptr=self.plot)

        add_menu_entry(menu=menu,
                       text="Open in street view",
                       icon_path=":/Icons/icons/map.svg",
                       function_ptr=self.open_street_view)

        add_menu_entry(menu=menu,
                       text="Consolidate selected objects coordinates",
                       function_ptr=self.editor.consolidate_object_coordinates,
                       icon_path=":/Icons/icons/assign_to_profile.svg")

        menu.exec_(event.screenPos())

    def create_new_line(self):
        """
        Create a new line in the map wizard
        """
        self.editor.create_new_line_wizard()

    def add_function(self):
        """

        :return:
        """

        for dev_tpe in [DeviceType.LineDevice,
                        DeviceType.DCLineDevice,
                        DeviceType.HVDCLineDevice,
                        DeviceType.FluidPathDevice]:

            dev_dict = self.editor.graphics_manager.get_device_type_dict(device_type=dev_tpe)
            lines_info = []

            for idtag, graphic_object in dev_dict.items():
                substation_from_graphics = self.editor.graphics_manager.query(
                    elm=graphic_object.api_object.get_substation_from()
                )
                substation_to_graphics = self.editor.graphics_manager.query(
                    elm=graphic_object.api_object.get_substation_to()
                )
                lines_info.append((idtag, graphic_object, substation_from_graphics, substation_to_graphics))

            # Now, iterate over the collected information
            for idtag, graphic_object, substation_from_graphics, substation_to_graphics in lines_info:
                if substation_from_graphics == self:
                    graphic_object.insert_new_node_at_position(0)

                if substation_to_graphics == self:
                    graphic_object.insert_new_node_at_position(len(graphic_object.nodes_list))

        pass

    def remove_function_from_schematic(self) -> None:
        """
        Removes the substation from the schematic only. The substation will remain in the database.
        """
        ok = yes_no_question(
            f"Remove substation {self.api_object.name} from the schematic only? It will remain in the database.",
            "Remove substation from schematic")

        if ok:
            self.editor.remove_substation(api_object=self.api_object, delete_from_db=False, substation_buses=[],
                                          voltage_levels=[])

    def remove_function_from_schematic_and_db(self) -> None:
        """
        Removes the substation from both the schematic and the database. This action cannot be undone.
        """

        # Store the API object before deleting the graphic
        api_object = self.api_object

        # Get all buses connected to this substation
        substation_buses = [bus for bus in self.editor.circuit.buses if bus.substation == api_object]

        # Get all voltage levels associated with this substation
        voltage_levels = [vl for vl in self.editor.circuit.voltage_levels if vl.substation == api_object]

        # voltage_levels = api_object.voltage_levels

        delete_connections = True  # TODO: This option was defaulted, no input was given from the GUI

        devs = list()
        # find associated Branches in reverse order
        for obj in substation_buses:
            for branch_list in self.editor.circuit.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
                for i in range(len(branch_list) - 1, -1, -1):
                    if branch_list[i].bus_from == obj:
                        devs.append(branch_list[i])
                    elif branch_list[i].bus_to == obj:
                        devs.append(branch_list[i])

            # find the associated injection devices
            for inj_list in self.editor.circuit.get_injection_devices_lists():
                for i in range(len(inj_list) - 1, -1, -1):
                    if inj_list[i].bus == obj:
                        devs.append(inj_list[i])

        # Show all devices that will be disconnected
        title = f"Devices to be {'deleted' if delete_connections else 'disconnected'} from {api_object.name}"

        self.show_devices_to_disconnect_dialog(devices=devs, buses=substation_buses,
                                               voltage_levels=voltage_levels, dialog_title=title)

        ok = yes_no_question(
            f"Remove substation {self.api_object.name} from both the schematic and the database? This action cannot be undone.",
            "Remove substation from schematic and database")

        if ok:
            self.editor.remove_substation(api_object=api_object, substation_buses=substation_buses,
                                          voltage_levels=voltage_levels, delete_from_db=True)

    def show_devices_to_disconnect_dialog(self,
                                          devices: List[ALL_DEV_TYPES],
                                          buses: List[Bus],
                                          voltage_levels: List[VoltageLevel],
                                          dialog_title: str):
        """
        Show a dialog with the list of all devices that will be disconnected

        :param devices: List of devices to be disconnected
        :param buses: List of buses associated with the substation
        :param voltage_levels: List of voltage levels associated with the substation
        :param dialog_title: Title for the dialog
        """
        from GridCal.Gui.general_dialogues import ElementsDialogue
        from GridCalEngine.Devices.Parents.editable_device import GCProp

        # Combine all devices
        all_devices = devices + buses + voltage_levels

        if not all_devices:
            info_msg('No devices to disconnect', dialog_title)
            return

        # Create custom properties for name, type, and ID tag
        name_prop = GCProp(prop_name='name', tpe=str, units='', definition='Device name',
                           display=True, editable=False)

        type_prop = GCProp(prop_name='device_type', tpe=DeviceType, units='', definition='Device type',
                           display=True, editable=False)

        idtag_prop = GCProp(prop_name='idtag', tpe=str, units='', definition='ID tag',
                            display=True, editable=False)

        custom_props = [name_prop, type_prop, idtag_prop]

        # Create and show the dialog
        dialog = ElementsDialogue(name=dialog_title, elements=all_devices)

        # Replace the model with our custom one that only shows name, type, and idtag
        model = ObjectsModel(objects=all_devices,
                             time_index=None,
                             property_list=custom_props,
                             parent=dialog.objects_table,
                             editable=False)

        dialog.objects_table.setModel(model)

        # Make the dialog modal so the user must acknowledge it before continuing
        dialog.setModal(True)
        dialog.exec()

    def move_to_api_coordinates(self, question: bool = True):
        """
        Function to move the graphics to the Database location
        :return:
        """
        if question:
            ok = yes_no_question(f"Move substation {self.api_object.name} graphics to it's database coordinates?",
                                 "Move substation graphics")

            if ok:
                x, y = self.move_to(lat=self.api_object.latitude,
                                    lon=self.api_object.longitude)  # this moves the vl too
                self.set_callbacks(x, y)
        else:
            x, y = self.move_to(lat=self.api_object.latitude, lon=self.api_object.longitude)  # this moves the vl too
            self.set_callbacks(x, y)

    def merge_selected_substations(self):
        """
        Merge selected substations into this one
        """
        selected = self.editor.get_selected_substations()

        dlg = CheckListDialogue(
            objects_list=[f"{graphic_obj.api_object.device_type.value}: {graphic_obj.api_object.name}"
                          for graphic_obj in selected],
            title=f"Merge into {self.api_object.name}"
        )

        dlg.setModal(True)
        dlg.exec()

        if dlg.is_accepted:
            selected_buses = []
            deleted_api_objs: List[Substation] = list()

            # Collect all codes to merge
            merged_codes = ""

            for i in dlg.selected_indices:

                se_graphics = selected[i]
                if merged_codes == "":
                    merged_codes = se_graphics.api_object.code
                else:
                    if se_graphics.api_object.code != "":
                        merged_codes = merged_codes + ',' + se_graphics.api_object.code

                deleted_api_objs.append(se_graphics.api_object)

                if se_graphics != self:
                    self.merge(se=se_graphics)
                    sub = self.editor.graphics_manager.delete_device(se_graphics.api_object)
                    self.editor.diagram_scene.removeItem(sub)

            # Update the code of the base substation
            self.api_object.code = merged_codes  # Needed?

            # Find the base substation in the circuit's collection and update it
            for i, substation in enumerate(self.editor.circuit.substations):
                if substation == self.api_object:
                    self.editor.circuit.substations[i].code = merged_codes
                    break

            # re-index the stuff pointing at deleted api elements to this api object
            for vl in self.editor.circuit.voltage_levels:
                if vl.substation in deleted_api_objs:
                    print(f'{vl.substation.name} changed to {self.api_object.name} for {vl.name}')
                    vl.substation = self.api_object

            for bus in self.editor.circuit.buses:
                if bus.substation in deleted_api_objs:
                    print(f'{bus.substation.name} changed to {self.api_object.name} for {bus.name}')
                    bus.substation = self.api_object
                    selected_buses.append(bus)

            # delete connections that are from and to the same substation
            for tpe in [DeviceType.LineDevice, DeviceType.DCLineDevice, DeviceType.HVDCLineDevice]:
                for elm in self.editor.graphics_manager.get_device_type_list(tpe):
                    if elm.api_object.get_substation_from() == elm.api_object.get_substation_to():
                        self.editor.remove_branch_graphic(elm, delete_from_db=True)

            for substation in deleted_api_objs:
                if substation == self.api_object:
                    pass
                else:
                    self.editor.circuit.delete_substation(obj=substation)

            self.refresh(pos=self.get_pos())  # always update

            if len(selected_buses):

                dlg = CheckListDialogue(
                    objects_list=[f'Create schematic diagram for the recipient substation {self.api_object.name}',
                                  f'Unify buses and voltage levels with the same nominal voltage in recipient '
                                  f'substation {self.api_object.name}. This will reattach the following items to the '
                                  f'recipient substation: Lines, generators, loads, shunts, controllable shunts'],
                    title=f"Finishing merging proces in substation{self.api_object.name}"
                )
                dlg.setModal(True)
                dlg.exec()

                if dlg.accepted:

                    if 1 in dlg.selected_indices:
                        recipient_buses = {}
                        removed_buses = []
                        for bus in self.editor.circuit.get_substation_buses(substation=self.api_object):
                            if bus.Vnom not in recipient_buses.keys():
                                recipient_buses[bus.Vnom] = bus
                            else:
                                removed_buses.append(bus)
                                selected_buses.remove(bus)
                                self.editor.graphics_manager.delete_device(device=bus.voltage_level)

                        for line in self.editor.circuit.lines:
                            if line.bus_from in removed_buses:
                                line.bus_from = recipient_buses[line.bus_from.Vnom]
                                line_graphic = self.editor.graphics_manager.query(elm=line)
                                line_graphic.calculate_total_length()

                            if line.bus_to in removed_buses:
                                line.bus_to = recipient_buses[line.bus_to.Vnom]
                                line_graphic = self.editor.graphics_manager.query(elm=line)
                                line_graphic.calculate_total_length()

                        for inj in self.editor.circuit.get_injection_devices_iter():
                            if inj.bus in removed_buses:
                                inj.bus = recipient_buses[inj.bus.Vnom]

                        for bus in removed_buses:
                            self.editor.circuit.delete_bus(obj=bus, delete_associated=False)
                            self.editor.circuit.delete_voltage_level(obj=bus.voltage_level)

                    if 0 in dlg.selected_indices:
                        diagram = schematic_widget.make_diagram_from_buses(circuit=self.editor.circuit,
                                                                           buses=selected_buses,
                                                                           name=self.api_object.name + " diagram")

                        diagram_widget = schematic_widget.SchematicWidget(gui=self.editor.gui,
                                                                          circuit=self.editor.circuit,
                                                                          diagram=diagram,
                                                                          default_bus_voltage=self.editor.gui.ui.defaultBusVoltageSpinBox.value(),
                                                                          time_index=self.editor.gui.get_diagram_slider_index())

                        self.editor.gui.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                                       diagram=diagram)
                        self.editor.gui.set_diagrams_list_view()
                        self.editor.gui.set_diagram_widget(widget=diagram_widget)

                else:
                    self.editor.gui.show_info_toast(
                        message='Merge ended. There was no diagram produced. The buses and voltages were not unified.')

            else:
                self.editor.gui.show_info_toast(
                    message='The substation merged have no associated buses. No schematic can be produced.')

    def new_substation_diagram(self):
        """
        Function to create a new substation
        :return:
        """
        self.editor.new_substation_diagram(substation=self.api_object)

    def plot(self):
        """
        Plot the substations data
        """
        i = self.editor.circuit.get_substations().index(self.api_object)
        self.editor.plot_substation(i, self.api_object)

    def add_voltage_level(self) -> None:
        """
        Add Voltage Level
        """

        inpt = InputNumberDialogue(
            min_value=0.1,
            max_value=100000.0,
            default_value=self.editor.diagram.default_bus_voltage,
            title="Add voltage level",
            text="Voltage (KV)",
        )

        inpt.exec()

        if inpt.is_accepted:
            kv = inpt.value
            vl = VoltageLevel(name=f'{self.api_object.name} @{kv} kV VL',
                              Vnom=kv,
                              substation=self.api_object)

            bus = Bus(name=f"{self.api_object.name} @{kv} kV bus",
                      Vnom=kv,
                      substation=self.api_object,
                      voltage_level=vl)

            self.editor.circuit.add_voltage_level(vl)
            self.editor.circuit.add_bus(obj=bus)
            self.editor.add_api_voltage_level(substation_graphics=self, api_object=vl)
            self.sort_voltage_levels()

    def get_pos(self) -> QPointF:
        """

        :return:
        """
        # Get the bounding rectangle of the ellipse item
        bounding_rect = self.boundingRect()

        # Calculate the center point of the bounding rectangle
        center_point = bounding_rect.center()

        return center_point

    def change_pen_width(self, width: float) -> None:
        """
        Change the pen width for the node.
        :param width: New pen width.
        """
        pen = self.pen()
        pen.setWidthF(width)
        self.setPen(pen)

    def color_widget(self, inner_color: QColor = None, border_color: QColor = None) -> None:
        """

        :param inner_color:
        :param border_color:
        :return:
        """
        # Example: color assignment
        brush = QBrush(inner_color)
        self.setBrush(brush)

        if border_color is not None:
            pen = self.pen()
            pen.setColor(border_color)
            self.setPen(pen)

    def set_default_color(self) -> None:
        """

        :return:
        """
        # Example: color assignment
        self.color_widget(self.color, self.border_color)

    def open_street_view(self):
        """
        Call open street maps
        :return:
        """
        # https://maps.google.com/?q=<lat>,<lng>
        url = f"https://www.google.com/maps/?q={self.lat},{self.lon}"
        webbrowser.open(url)

    def get_associated_widgets(self) -> List[GenericDiagramWidget]:
        """

        :return:
        """
        associated_buses = self.editor.circuit.get_substation_buses(substation=self.api_object)
        associated_lines_graphics: List[MapLineContainer] = list()
        for line in self.editor.circuit.lines:
            if line.bus_to in associated_buses or line.bus_from in associated_buses:
                associated_lines_graphics.append(self.editor.graphics_manager.query(elm=line))

        # TODO: Connectivity nodes / busbars? Probably this is only when dealing with the schematic

        # for bus in associated_buses:
        #     associated_buses_graphics.append(self.editor.graphics_manager.query(elm=bus))

        # for segment in self.get_hosting_line_segments():
        #     associated_lines_graphics.append(segment.container)

        return self.voltage_level_graphics + associated_lines_graphics

    def get_associated_devices(self) -> List[ALL_DEV_TYPES]:
        """
        This function returns all the api_object devices associated with the selected graphic object.
        :return: List of the associated devices.
        """
        associated_vl = [vl.api_object for vl in self.voltage_level_graphics]
        associated_buses = self.editor.circuit.get_substation_buses(substation=self.api_object)
        associated_branches: List[BRANCH_TYPES] = list()
        associated_shunts: List[INJECTION_DEVICE_TYPES] = list()

        for branch in self.editor.circuit.get_branches():
            if branch.bus_to in associated_buses or branch.bus_from in associated_buses:
                associated_branches.append(branch)

        for inj in self.editor.circuit.get_injection_devices_iter():
            if inj.bus in associated_buses:
                associated_shunts.append(inj)

        # TODO: Connectivity nodes / busbars? Probably this is only when dealing with the schematic

        # for bus in associated_buses:
        #     associated_buses_graphics.append(self.editor.graphics_manager.query(elm=bus))

        # for segment in self.get_hosting_line_segments():
        #     associated_lines_graphics.append(segment.container)

        return associated_vl + associated_branches + associated_shunts + associated_buses

    def delete(self):
        """

        :return:
        """

        self.editor.delete_with_dialogue(selected=[self], delete_from_db=False)
