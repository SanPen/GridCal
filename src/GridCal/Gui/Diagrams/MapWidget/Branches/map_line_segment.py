# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import webbrowser
from typing import List, TYPE_CHECKING
from PySide6.QtCore import Qt, QPointF, QLineF
from PySide6.QtGui import QPen, QColor, QCursor
from PySide6.QtWidgets import QMenu, QGraphicsSceneContextMenuEvent
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsSceneMouseEvent

from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import ArrowHead
from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER
from GridCal.Gui.Diagrams.Editors.line_editor import LineEditor

from GridCalEngine.Devices.types import BRANCH_TYPES, ALL_DEV_TYPES
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.Branches.line_location_graphic_item import LineLocationGraphicItem
    from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


def open_street_view(lat: float, lon: float):
    """
    Call open street maps
    :return:
    """
    # https://maps.google.com/?q=<lat>,<lng>
    url = f"https://www.google.com/maps/?q={lat},{lon}"
    webbrowser.open(url)


class MapLineSegment(QGraphicsLineItem):
    """
    Segment joining two NodeGraphicItem
    """

    def __init__(self,
                 first: LineLocationGraphicItem,
                 second: LineLocationGraphicItem,
                 container: MapLineContainer,
                 width: float):
        """
        Segment constructor
        :param first: LineLocationGraphicItem
        :param second: LineLocationGraphicItem
        :param container: MapLineContainer
        """
        QGraphicsLineItem.__init__(self)
        self.first: LineLocationGraphicItem = first
        self.second: LineLocationGraphicItem = second
        self.container: MapLineContainer = container
        self.draw_labels = True

        self.style = Qt.PenStyle.SolidLine
        # self.color = QColor(115, 115, 115, 200)  # translucent gray

        self.color = QColor(self.api_object.color)
        self.color.setAlpha(128)
        self.hoover_color = QColor(self.api_object.color)
        self.hoover_color.setAlpha(180)

        self.width = width

        self.pos1: QPointF = self.first.get_center_pos()
        self.pos2: QPointF = self.second.get_center_pos()

        # arrows
        self.view_arrows = True
        self._arrow_size = self.width * 1.5
        self.arrow_p_from = ArrowHead(parent=self, arrow_size=self._arrow_size, position=0.2, under=False,
                                      text_scale=0.01, show_text=False)
        self.arrow_q_from = ArrowHead(parent=self, arrow_size=self._arrow_size, position=0.2, under=True,
                                      text_scale=0.01, show_text=False)
        self.arrow_p_to = ArrowHead(parent=self, arrow_size=self._arrow_size, position=0.8, under=False,
                                    text_scale=0.01, show_text=False)
        self.arrow_q_to = ArrowHead(parent=self, arrow_size=self._arrow_size, position=0.8, under=True,
                                    text_scale=0.01, show_text=False)

        # set callbacks
        self.first.add_position_change_callback(self, self.set_from_side_coordinates)
        self.second.add_position_change_callback(self, self.set_to_side_coordinates)

        self._pen = self.set_colour(self.color, self.style)
        # self._pen.setCosmetic(True)
        self.update_endings()
        self.needsUpdate = True
        self.setZValue(0)

        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def get_width(self) -> float:
        return self.width

    def get_arrow_size(self) -> float:
        return self._arrow_size

    @property
    def api_object(self) -> BRANCH_TYPES:
        """

        :return:
        """
        return self.container.api_object

    @property
    def editor(self) -> GridMapWidget:
        """

        :return:
        """
        return self.container.editor

    def delete_from_associations(self):
        """
        Delete the connections
        """
        self.first.delete_hosting_connection(self)
        self.second.delete_hosting_connection(self)

    def get_associated_widgets(self) -> List[MapLineContainer]:
        """
        This forwards to the map line container for the appropriate deletion of everything
        :return:
        """
        return [self.container]

    def get_associated_devices(self) -> List[ALL_DEV_TYPES]:
        """
        This forwards to the map line container for the appropriate deletion of everything
        :return:
        """
        return [self.container.api_object]

    def set_width(self, width: float):
        """

        :param width:
        :return:
        """

        # self.setScale(width / self.width)  # Faster since it avoids repainting each QPen

        if self.width != width:  # Only update if width changes
            self._pen.setWidthF(width)
            self.setPen(self._pen)
            self.width = width

    def set_arrow_sizes(self, width: float):
        """

        :param width:
        :return:
        """
        self.arrow_p_from.set_size(width)
        self.arrow_q_from.set_size(width)
        self.arrow_p_to.set_size(width)
        self.arrow_q_to.set_size(width)

    def set_colour(self, color: QColor, style: Qt.PenStyle):
        """
        Set color and style
        :param color: QColor instance
        :param style: PenStyle instance
        :return:
        """

        pen = QPen(color, self.width, style, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        self.setPen(pen)
        self.arrow_p_from.set_colour(color)
        self.arrow_q_from.set_colour(color)
        self.arrow_p_to.set_colour(color)
        self.arrow_q_to.set_colour(color)

        return pen

    def set_from_side_coordinates(self, x: float, y: float):
        """

        :param x:
        :param y:
        :return:
        """
        self.pos1 = QPointF(x, y)
        self.update_endings()

    def set_to_side_coordinates(self, x: float, y: float):
        """

        :param x:
        :param y:
        :return:
        """
        self.pos2 = QPointF(x, y)
        self.update_endings()

    def update_endings(self, force=False) -> None:
        """
        Update the endings of this segment
        """
        self.setLine(QLineF(self.pos1, self.pos2))

        if self.api_object is not None:

            # arrows
            if self.view_arrows:
                self.arrow_p_from.redraw()
                self.arrow_q_from.redraw()
                self.arrow_p_to.redraw()
                self.arrow_q_to.redraw()

    def end_update(self) -> None:
        """

        :return:
        """
        self.first.needsUpdate = False
        self.second.needsUpdate = False

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param event:
        :return:
        """
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """

        :param event:
        :return:
        """

        menu = QMenu()

        menu.addSection("Line")

        add_menu_entry(menu=menu,
                       text="Active",
                       function_ptr=self.enable_disable_toggle,
                       checkeable=True,
                       checked_value=self.container.api_object.active)

        add_menu_entry(menu=menu,
                       text="Draw labels",
                       function_ptr=self.enable_disable_label_drawing,
                       checkeable=True,
                       checked_value=self.draw_labels)

        add_menu_entry(menu=menu,
                       text="Editor",
                       function_ptr=self.call_editor,
                       icon_path=":/Icons/icons/edit.svg")

        # We could create a new icon for this I guess
        add_menu_entry(menu=menu,
                       text="Calculate total length",
                       function_ptr=self.calculate_total_length,
                       icon_path=":/Icons/icons/ruler.svg")

        add_menu_entry(menu=menu,
                       text="Consolidate selected objects coordinates",
                       function_ptr=self.editor.consolidate_object_coordinates,
                       icon_path=":/Icons/icons/assign_to_profile.svg")

        menu.addSeparator()

        # Check if a substation is selected
        has_substation = False
        substation_counter = 0
        line_counter = 0

        for graphic_obj in self.editor._get_selected():
            if hasattr(graphic_obj, 'api_object'):
                if hasattr(graphic_obj.api_object, 'device_type'):
                    if graphic_obj.api_object.device_type == DeviceType.SubstationDevice:
                        has_substation = True
                        substation_counter += 1
                    elif graphic_obj.api_object.device_type == DeviceType.LineDevice:
                        line_counter += 1

        if line_counter > 1:

            add_menu_entry(menu=menu,
                           text="Merge selected lines",
                           function_ptr=self.editor.merge_selected_lines,
                           icon_path=":/Icons/icons/fusion.svg")

        menu.addSeparator()

        # Add the split line to substation option if a substation is selected
        if has_substation:
            if substation_counter == 1:
                add_menu_entry(menu=menu,
                               text="Split line to selected substation (In-Out)",
                               function_ptr=self.editor.split_line_to_substation,
                               icon_path=":/Icons/icons/divide.svg")

            elif substation_counter == 2:

                add_menu_entry(menu=menu,
                               text="Change substation connection of the line",
                               function_ptr=self.editor.change_line_connection,
                               icon_path=":/Icons/icons/move_bus.svg")
            else:
                pass

        add_menu_entry(menu=menu,
                       text="Plot profiles",
                       function_ptr=self.plot_profiles,
                       icon_path=":/Icons/icons/plot.svg")

        scene_pos = event.scenePos()  # Position in scene coordinates
        x, y = scene_pos.x(), scene_pos.y()
        lat, lon = self.editor.to_lat_lon(x=x, y=y)
        add_menu_entry(menu=menu,
                       text="Open in Street view",
                       function_ptr=lambda: open_street_view(lat, lon),
                       icon_path=":/Icons/icons/map.svg")

        add_menu_entry(menu=menu,
                       text="Assign rate to profile",
                       function_ptr=self.assign_rate_to_profile,
                       icon_path=":/Icons/icons/assign_to_profile.svg")

        add_menu_entry(menu=menu,
                       text="Assign active state to profile",
                       function_ptr=self.assign_status_to_profile,
                       icon_path=":/Icons/icons/assign_to_profile.svg")

        add_menu_entry(menu=menu,
                       text="Add point",
                       function_ptr=self.add_node,
                       icon_path=":/Icons/icons/cn_icon.svg")

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Delete",
                       function_ptr=self.delete,
                       icon_path=":/Icons/icons/delete_schematic.svg")

        menu.exec_(event.screenPos())

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

        # Set pen for everyone
        self.set_colour(self.color, self.style)

    def enable_disable_label_drawing(self):
        """

        :return:
        """
        self.draw_labels = not self.draw_labels

    def call_editor(self):
        """
        Call the line editor
        :return:
        """

        Vnom = self.api_object.get_max_bus_nominal_voltage()
        templates = list()

        for lst in [self.editor.circuit.sequence_line_types,
                    self.editor.circuit.underground_cable_types,
                    self.editor.circuit.overhead_line_types]:
            for temp in lst:
                if Vnom == temp.Vnom:
                    templates.append(temp)

        dlg = LineEditor(
            line=self.api_object,
            Sbase=self.editor.circuit.Sbase,
            frequency=self.editor.circuit.fBase,
            templates=templates,
            current_template=self.api_object.template
        )
        dlg.exec()

    def plot_profiles(self) -> None:
        """
        Plot the time series profiles
        @return:
        """
        # get the index of this object
        i = self.editor.circuit.get_branches().index(self.api_object)
        self.editor.plot_branch(i, self.api_object)

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

    def add_node(self):
        """
        Add a path to the container by adding a new graphical segment
        """

        if len(self.container.nodes_list) == 0:
            self.container.insert_new_node_at_position(0)

        elif len(self.container.nodes_list) == 1:
            if self.second == self.container.substation_to() or self.first == self.container.substation_to():
                self.container.insert_new_node_at_position(1)
            else:
                self.container.insert_new_node_at_position(0)
        else:
            if self.second == self.container.substation_to() or self.first == self.container.substation_to():
                self.container.insert_new_node_at_position(len(self.container.nodes_list))

            elif self.second == self.container.substation_from() or self.first == self.container.substation_from():
                self.container.insert_new_node_at_position(0)

            else:
                if self.first.index > self.second.index:
                    self.container.insert_new_node_at_position(self.second.index)

                elif self.first.index < self.second.index:
                    self.container.insert_new_node_at_position(self.second.index)

    def set_arrows_with_power(self, Sf: complex | None, St: complex | None) -> None:
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
            self.arrow_p_from.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
            self.arrow_q_from.set_value(Qf, True, Qf < 0, name="Qf", units="MVAr", draw_label=self.draw_labels)
            self.arrow_p_to.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)
            self.arrow_q_to.set_value(Qt_, True, Qt_ > 0, name="Qt", units="MVAr", draw_label=self.draw_labels)

    def set_arrows_with_hvdc_power(self, Pf: float, Pt: float) -> None:
        """
        Set the arrow directions
        :param Pf: Complex power from
        :param Pt: Complex power to
        """
        self.arrow_p_from.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
        self.arrow_q_from.set_value(Pf, True, Pf < 0, name="Pf", units="MW", draw_label=self.draw_labels)
        self.arrow_p_to.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)
        self.arrow_q_to.set_value(Pt, True, Pt > 0, name="Pt", units="MW", draw_label=self.draw_labels)

    def calculate_total_length(self):
        """
        Calculate the total length of the line by summing the distances between all waypoints
        using the haversine formula, and update the line's length property.
        """
        # Use the container's method to calculate the total length
        total_length = self.container.calculate_total_length()

        # Show a message with the calculated length
        self.editor.gui.show_info_toast(
            message=f"Line length calculated: {total_length:.2f} km. The length property of line "
                    f"{self.api_object.name} has been updated.")

    def delete(self):
        """
        Delete this and all the MapLineContainer segments
        """
        self.container.delete()
