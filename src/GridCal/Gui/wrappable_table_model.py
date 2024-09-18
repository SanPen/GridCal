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
from typing import Dict, List, Union
from PySide6 import QtCore, QtWidgets, QtGui
from enum import EnumMeta
from GridCal.Gui.GuiFunctions import (IntDelegate, ComboDelegate, TextDelegate, FloatDelegate, ColorPickerDelegate,
                                      ComplexDelegate, LineLocationsDelegate)
from GridCalEngine.Devices import Bus, ContingencyGroup
from GridCalEngine.Devices.Parents.editable_device import GCProp, GCPROP_TYPES
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.Branches.line_locations import LineLocations
from GridCalEngine.Devices.types import ALL_DEV_TYPES


class WrappableTableModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with the properties of objects
    """

    def __init__(self, parent: QtWidgets.QTableView = None):
        """

        :param parent: Parent object: the QTableView object
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        # flag for the headers text wraper: HeaderViewWithWordWrap
        self._hide_headers_mode = False

    def hideHeaders(self) -> None:  # Do not rename, this is used by HeaderViewWithWordWrap
        """

        :return:
        """
        self._hide_headers_mode = True

    def unhideHeaders(self) -> None:  # Do not rename, this is used by HeaderViewWithWordWrap
        """

        :return:
        """
        self._hide_headers_mode = False
