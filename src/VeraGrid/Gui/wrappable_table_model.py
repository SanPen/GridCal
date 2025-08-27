# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from PySide6 import QtCore, QtWidgets


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

    def hide_headers(self) -> None:
        """

        :return:
        """
        self._hide_headers_mode = True

    def unhide_headers(self) -> None:
        """

        :return:
        """
        self._hide_headers_mode = False
