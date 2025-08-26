# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Union
from PySide6 import QtCore, QtGui
from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class DiagramsModel(QtCore.QAbstractListModel):
    """
    Model for the diagrams
    # from GridCal.Gui.Diagrams.BusViewer.bus_viewer_dialogue import BusViewerGUI
    # from GridCal.Gui.DiagramEditorWidget import DiagramEditorWidget
    # from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget
    """

    def __init__(self, list_of_diagrams: List[Union[SchematicWidget, GridMapWidget]]):
        """
        Enumeration model
        :param list_of_diagrams: list of enumeration values to show
        """
        QtCore.QAbstractListModel.__init__(self)
        self.items = list_of_diagrams

        self.bus_branch_editor_icon = QtGui.QIcon()
        self.bus_branch_editor_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/schematic.svg"))

        self.bus_branch_vicinity_icon = QtGui.QIcon()
        self.bus_branch_vicinity_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/grid_icon.svg"))

        self.map_editor_icon = QtGui.QIcon()
        self.map_editor_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/map.svg"))

    def flags(self, index: QtCore.QModelIndex):
        """
        Get the display mode
        :param index:
        :return:
        """
        return (QtCore.Qt.ItemFlag.ItemIsEditable |
                QtCore.Qt.ItemFlag.ItemIsEnabled |
                QtCore.Qt.ItemFlag.ItemIsSelectable)

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """

        :param parent:
        :return:
        """
        return len(self.items)

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():

            if index.row() < len(self.items):
                diagram = self.items[index.row()]

                if (role == QtCore.Qt.ItemDataRole.DisplayRole or
                        role == QtCore.Qt.ItemDataRole.EditRole):
                    return diagram.name

                elif role == QtCore.Qt.ItemDataRole.DecorationRole:
                    if isinstance(diagram, SchematicWidget):
                        return self.bus_branch_editor_icon
                    elif isinstance(diagram, GridMapWidget):
                        return self.map_editor_icon

        return None

    def setData(self, index, value, role=None):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """

        self.items[index.row()].name = value
        self.dataChanged.emit(index, index, [role])  # keep view in sync
        return True
