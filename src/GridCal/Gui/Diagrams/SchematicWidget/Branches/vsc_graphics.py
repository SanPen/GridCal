# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING, List, Union, cast
from PySide6.QtCore import Qt, QPoint, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QBrush, QColor, QCursor
from PySide6.QtWidgets import QMenu, QGraphicsItem, QGraphicsRectItem, QGraphicsSceneMouseEvent

from GridCal.Gui.gui_functions import add_menu_entry
from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import RoundTerminalItem
from GridCal.Gui.Diagrams.generic_graphics import GenericDiagramWidget, ACTIVE, DEACTIVATED
from GridCalEngine.Devices.Branches.vsc import VSC
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import DeviceType, ConverterControlType # Assuming VSC controls might be relevant later

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
    from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem # For type hints if needed later


class VscGraphicItem(GenericDiagramWidget, QGraphicsRectItem):
    """
    Graphics item for the 3-Terminal VSC converter
    """

    def __init__(self,
                 editor: SchematicWidget,
                 api_object: VSC,
                 pos: QPoint = None,
                 parent=None,
                 draw_labels: bool = True):
        """
        Constructor for the 3-Terminal VSC Graphic Item.

        :param editor: SchematicWidget instance
        :param api_object: VSC API object
        :param pos: Initial position
        :param parent: Parent item
        :param draw_labels: Whether to draw labels
        """
        GenericDiagramWidget.__init__(self, parent=parent, api_object=api_object, editor=editor, draw_labels=draw_labels)
        QGraphicsRectItem.__init__(self, parent=parent)

        # Make it a square
        self.w = 60  # Width of the VSC symbol
        self.h = self.w  # Height of the VSC symbol
        self.setRect(0.0, 0.0, self.w, self.h)

        self.draw_labels = draw_labels

        # Color and style based on active state
        self.pen_width = 2
        if self.api_object.active:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']
        else:
            self.color = DEACTIVATED['color']

        # Setup pen, brush, flags and cursor
        self.setPen(QPen(self.color, self.pen_width, self.style))
        self.setBrush(Qt.BrushStyle.NoBrush) # Set transparent background
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        if pos is not None:
            self.setPos(pos)

        # --- Create Terminals ---
        # Terminal positions (relative to the item's top-left corner 0,0)
        # AC terminal on the right middle
        t_ac_pos = QPoint(self.w, self.h / 2)
        # DC+ terminal on the left top
        t_dc_p_pos = QPoint(0, self.h * 0.2)
        # DC- terminal on the left bottom
        t_dc_n_pos = QPoint(0, self.h * 0.8)

        self.terminals: List[RoundTerminalItem] = list()
        self.connection_lines: List[LineGraphicTemplateItem | None] = [None, None, None] # Index 0: AC, 1: DC+, 2: DC-

        # AC Terminal (Index 0)
        terminal_ac = RoundTerminalItem("ac", parent=self, editor=self.editor)
        terminal_ac.setPos(t_ac_pos)
        terminal_ac.setRotation(0) # Points right
        terminal_ac.setPen(QPen(self.color, self.pen_width, self.style))
        self.terminals.append(terminal_ac)

        # DC+ Terminal (Index 1)
        terminal_dc_p = RoundTerminalItem("dc_p", parent=self, editor=self.editor)
        terminal_dc_p.setPos(t_dc_p_pos)
        terminal_dc_p.setRotation(180) # Points left
        terminal_dc_p.setPen(QPen(self.color, self.pen_width, self.style))
        self.terminals.append(terminal_dc_p)

        # DC- Terminal (Index 2)
        terminal_dc_n = RoundTerminalItem("dc_n", parent=self, editor=self.editor)
        terminal_dc_n.setPos(t_dc_n_pos)
        terminal_dc_n.setRotation(180) # Points left
        terminal_dc_n.setPen(QPen(self.color, self.pen_width, self.style))
        self.terminals.append(terminal_dc_n)

        self.set_terminal_tooltips()

    @property
    def api_object(self) -> VSC:
        return self._api_object

    @property
    def editor(self) -> SchematicWidget:
        return self._editor

    def paint(self, painter: QPainter, option, widget=None) -> None:
        """Paint the VSC symbol."""
        # Draw the main rectangle (square)
        painter.setPen(QPen(self.color, self.pen_width, self.style))
        painter.setBrush(Qt.BrushStyle.NoBrush) # Ensure transparent background
        painter.drawRect(self.rect())

        # Draw a diagonal line from top-right to bottom-left
        pen = QPen(self.color, self.pen_width)
        painter.setPen(pen)
        painter.drawLine(QPoint(self.w, 0), QPoint(0, self.h))

        # Draw AC/DC symbols near terminals (optional)
        text_rect_size = 15
        painter.drawText(QRectF(self.w + 2, self.h / 2 - text_rect_size / 2, text_rect_size, text_rect_size), Qt.AlignmentFlag.AlignCenter, "~") # AC ~ symbol to the right
        painter.drawText(QRectF(-text_rect_size - 2, self.h * 0.2 - text_rect_size / 2, text_rect_size, text_rect_size), Qt.AlignmentFlag.AlignCenter, "+") # DC+ symbol to the left
        painter.drawText(QRectF(-text_rect_size - 2, self.h * 0.8 - text_rect_size / 2, text_rect_size, text_rect_size), Qt.AlignmentFlag.AlignCenter, "-") # DC- symbol to the left

        # Draw selection rectangle if selected
        if self.isSelected():
            select_pen = QPen(Qt.GlobalColor.yellow, 1, Qt.PenStyle.DashLine)
            painter.setPen(select_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(-2, -2, 2, 2))


    def set_terminal_tooltips(self):
        """Set tooltips for the terminals."""
        if self.api_object:
            self.terminals[0].setToolTip(f"AC Terminal ({self.api_object.bus_ac.name if self.api_object.bus_ac else 'Unconnected'})")
            self.terminals[1].setToolTip(f"DC+ Terminal ({self.api_object.bus_dc_p.name if self.api_object.bus_dc_p else 'Unconnected'})")
            self.terminals[2].setToolTip(f"DC- Terminal ({self.api_object.bus_dc_n.name if self.api_object.bus_dc_n else 'Unconnected'})")

    def update_conn(self):
        """Update the connection lines attached to this item."""
        for line in self.connection_lines:
            if line is not None:
                line.update_position()

    def get_associated_widgets(self) -> List[LineGraphicTemplateItem]:
        """Return the graphical line items connected to this VSC."""
        return [line for line in self.connection_lines if line is not None]

    def get_extra_graphics(self):
         """Return terminals associated with this widget."""
         return self.terminals

    def recolour_mode(self):
        """Change the colour according to the system theme and active state."""
        if self.api_object is None:
            return

        if self.api_object.active:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']

        pen = QPen(self.color, self.pen_width, self.style)
        self.setPen(pen)

        for terminal in self.terminals:
            terminal.setPen(pen)

        for line in self.connection_lines:
            if line is not None:
                line.recolour_mode()
        self.update() # Request repaint

    def set_enable(self, val=True):
        """Set the enable value, graphically and in the API."""
        self.api_object.active = val
        self.recolour_mode()

    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """Handle mouse move event."""
        super().mouseMoveEvent(event)
        self.editor.update_diagram_element(device=self.api_object,
                                           x=self.pos().x(),
                                           y=self.pos().y(),
                                           w=self.w,
                                           h=self.h,
                                           r=self.rotation(),
                                           graphic_object=self)
        self.update_conn()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press: select item and show in editor."""
        super().mousePressEvent(event) # Handle selection
        if self.api_object is not None:
            self.editor.set_editor_model(api_object=self.api_object)

    def mouseDoubleClickEvent(self, event):
         """ On double-click, potentially open an editor (optional)."""
         # Currently no specific editor for VSC, but could be added.
         # self.edit()
         pass

    def delete(self):
        """Delete the VSC and its connections."""
        # Remove connections first
        for i in range(len(self.connection_lines)):
             self.remove_connection(i)

        # Remove the item itself
        self.editor.scene().removeItem(self)
        self.editor.remove_diagram_element(self.api_object)
        self.editor.circuit.remove_vsc(self.api_object)
        self.editor.viewport().update()

    def set_connection(self, terminal_index: int, bus: Bus, conn_line: LineGraphicTemplateItem, set_voltage: bool = True):
        """Set a connection to a specific terminal."""
        if not (0 <= terminal_index < 3):
             print(f"Error: Invalid terminal index {terminal_index} for VSC {self.api_object.name}")
             return

        # Remove existing connection if any
        self.remove_connection(terminal_index)

        # Update API object
        if terminal_index == 0: # AC Terminal
            if bus.is_dc:
                 print(f"Warning: Connecting AC terminal of VSC {self.api_object.name} to DC bus {bus.name}")
            self.api_object.bus_ac = bus
            self.api_object.cn_ac = None # Explicitly connected to Bus
        elif terminal_index == 1: # DC+ Terminal
            if not bus.is_dc:
                 print(f"Warning: Connecting DC+ terminal of VSC {self.api_object.name} to AC bus {bus.name}")
            self.api_object.bus_dc_p = bus
            self.api_object.cn_dc_p = None # Explicitly connected to Bus
        elif terminal_index == 2: # DC- Terminal
            if not bus.is_dc:
                 print(f"Warning: Connecting DC- terminal of VSC {self.api_object.name} to AC bus {bus.name}")
            self.api_object.bus_dc_n = bus
            self.api_object.cn_dc_n = None # Explicitly connected to Bus

        # Store connection line
        self.connection_lines[terminal_index] = conn_line
        self.set_terminal_tooltips()

    def set_connection_cn(self, terminal_index: int, cn: ConnectivityNode, conn_line: LineGraphicTemplateItem, set_voltage: bool = True):
         """ Set a connection to a specific terminal using a connectivity node. """
         if not (0 <= terminal_index < 3):
             print(f"Error: Invalid terminal index {terminal_index} for VSC {self.api_object.name}")
             return

         # Remove existing connection if any
         self.remove_connection(terminal_index)

         # Update API object
         bus = cn.bus # Get the bus from the CN
         if terminal_index == 0: # AC Terminal
             if bus.is_dc:
                 print(f"Warning: Connecting AC terminal of VSC {self.api_object.name} to DC bus {bus.name}")
             self.api_object.bus_ac = cn.bus # Store parent bus
             self.api_object.cn_ac = cn
         elif terminal_index == 1: # DC+ Terminal
             if not bus.is_dc:
                 print(f"Warning: Connecting DC+ terminal of VSC {self.api_object.name} to AC bus {bus.name}")
             self.api_object.bus_dc_p = cn.bus # Store parent bus
             self.api_object.cn_dc_p = cn
         elif terminal_index == 2: # DC- Terminal
             if not bus.is_dc:
                 print(f"Warning: Connecting DC- terminal of VSC {self.api_object.name} to AC bus {bus.name}")
             self.api_object.bus_dc_n = cn.bus # Store parent bus
             self.api_object.cn_dc_n = cn

         # Store connection line
         self.connection_lines[terminal_index] = conn_line
         self.set_terminal_tooltips()
         self.editor.viewport().update()


    def remove_connection(self, terminal_index: int):
        """Remove a connection from a specific terminal."""
        if not (0 <= terminal_index < 3):
             return
        if self.connection_lines[terminal_index] is not None:
             line = self.connection_lines[terminal_index]
             # Remove the line from the scene
             if line.scene():
                 line.scene().removeItem(line)
             # Clear the reference
             self.connection_lines[terminal_index] = None
             # Optionally clear the bus/cn reference in the api_object
             if terminal_index == 0:
                 self.api_object.bus_ac = None
                 self.api_object.cn_ac = None
             elif terminal_index == 1:
                 self.api_object.bus_dc_p = None
                 self.api_object.cn_dc_p = None
             elif terminal_index == 2:
                 self.api_object.bus_dc_n = None
                 self.api_object.cn_dc_n = None
             self.set_terminal_tooltips()
             self.editor.viewport().update()


    def contextMenuEvent(self, event):
        """Show context menu."""
        if self.api_object is not None:
            menu = QMenu()

            # Enable/Disable
            pe = menu.addAction('Enable/Disable')
            pe_icon = QIcon()
            if self.api_object.active:
                pe_icon.addPixmap(QPixmap(":/Icons/icons/uncheck_all.svg"))
            else:
                pe_icon.addPixmap(QPixmap(":/Icons/icons/check_all.svg"))
            pe.setIcon(pe_icon)
            pe.triggered.connect(lambda: self.set_enable(not self.api_object.active))

            # Draw Labels (if applicable)
            # add_menu_entry(menu=menu,
            #                text="Draw labels",
            #                function_ptr=self.enable_disable_label_drawing, # Needs implementation if label drawing is kept
            #                checkeable=True,
            #                checked_value=self.draw_labels)

            # Delete
            menu.addSeparator()
            ra2 = menu.addAction('Delete')
            del_icon = QIcon()
            del_icon.addPixmap(QPixmap(":/Icons/icons/delete3.svg"))
            ra2.setIcon(del_icon)
            ra2.triggered.connect(self.delete)

            # --- Add back original control/profile actions ---
            menu.addSeparator()

            add_menu_entry(menu=menu,
                           text="Control V AC from DC+",
                           function_ptr=self.control_v_from,
                           icon_path=":/Icons/icons/edit.svg")

            add_menu_entry(menu=menu,
                           text="Control V AC from AC",
                           function_ptr=self.control_v_to,
                           icon_path=":/Icons/icons/edit.svg")

            menu.addSeparator()

            ra6 = menu.addAction('Plot profiles')
            plot_icon = QIcon()
            plot_icon.addPixmap(QPixmap(":/Icons/icons/plot.svg"))
            ra6.setIcon(plot_icon)
            ra6.triggered.connect(self.plot_profiles)

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

            menu.exec_(event.screenPos())
        else:
            pass


    def control_v_from(self):
        """
        Set control mode to regulate DC voltage based on DC+ side (Interpretation).
        Sets control1 to Vm_dcp.
        """
        if self.api_object.bus_ac and self.api_object.bus_dc_p:
            self.api_object.control1 = ConverterControlType.Vm_ac
            self.api_object.control1_dev = self.api_object.bus_ac
            self.api_object.control1_val = 1.0 # Default to 1.0 pu

            self.api_object.control2 = ConverterControlType.Vm_dc
            self.api_object.control2_dev = self.api_object.bus_dc_p
            self.api_object.control2_val = 1.0 # Default to 1.0 pu

            print(f"VSC {self.api_object.name} control set: Control1=Vm_dcp (Bus: {self.api_object.bus_dc_p.name})")
            self.editor.set_editor_model(api_object=self.api_object) # Refresh editor view
        else:
            print("Error: Cannot set control_v_from, DC+ bus not connected.")

    def control_v_to(self):
        """
        Set control mode to regulate AC voltage based on AC side itself.
        Sets control1 to Vm_ac (controlling AC bus).
        Leaves control2 as is, or sets it to something default like Pac if necessary.
        """
        if self.api_object.bus_ac:
            self.api_object.control1 = ConverterControlType.Vm_ac
            self.api_object.control1_dev = self.api_object.bus_ac
            self.api_object.control1_val = 1.0 # Default to 1.0 pu

            print(f"VSC {self.api_object.name} control set: Control1=Vm_ac (Bus: {self.api_object.bus_ac.name})")
            self.editor.set_editor_model(api_object=self.api_object) # Refresh editor view
        else:
            print("Error: Cannot set control_v_to, AC bus not connected.")


    def assign_rate_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self._editor.set_rate_to_profile(self.api_object)

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self._editor.set_active_status_to_profile(self.api_object)