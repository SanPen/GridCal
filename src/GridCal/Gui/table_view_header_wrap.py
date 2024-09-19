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
from PySide6 import QtCore, QtWidgets, QtGui
from GridCal.Gui.wrappable_table_model import WrappableTableModel


class HeaderViewWithWordWrap(QtWidgets.QHeaderView):
    """
    HeaderViewWithWordWrap
    """

    def __init__(self) -> None:
        QtWidgets.QHeaderView.__init__(self, QtCore.Qt.Orientation.Horizontal)

    def sectionSizeFromContents(self, logicalIndex: int) -> QtCore.QSize:
        """

        :param logicalIndex:
        :return:
        """
        mdl: WrappableTableModel = self.model()
        if mdl:
            headerText = mdl.headerData(logicalIndex, self.orientation(), QtCore.Qt.ItemDataRole.DisplayRole)
            option = QtWidgets.QStyleOptionHeader()
            self.initStyleOption(option)
            option.section = logicalIndex
            metrics = QtGui.QFontMetrics(self.font())

            maxWidth = self.sectionSize(logicalIndex)

            rect = metrics.boundingRect(QtCore.QRect(0, 0, maxWidth, 5000),
                                        QtCore.Qt.AlignmentFlag.AlignLeft |
                                        QtCore.Qt.TextFlag.TextWordWrap |
                                        QtCore.Qt.TextFlag.TextExpandTabs,
                                        headerText, 4)
            return rect.size()
        else:
            return QtWidgets.QHeaderView.sectionSizeFromContents(self, logicalIndex)

    def paintSection(self, painter, rect, logicalIndex: int):
        """

        :param painter:
        :param rect:
        :param logicalIndex:
        :return:
        """
        mdl: WrappableTableModel = self.model()  # assign with typing
        if mdl:
            painter.save()
            mdl.hide_headers()
            super().paintSection(painter, rect, logicalIndex)
            mdl.unhide_headers()
            painter.restore()
            headerText = mdl.headerData(logicalIndex, self.orientation(), QtCore.Qt.ItemDataRole.DisplayRole)

            if headerText is not None:

                headerText = headerText.replace("_", " ")

                # Define text indentation
                indentation = 4  # pixels
                textRect = QtCore.QRectF(rect.adjusted(indentation, 0, 0, 0))  # Indent left and right

                painter.drawText(textRect,
                                 QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.TextFlag.TextWordWrap,
                                 headerText)
        else:
            QtWidgets.QHeaderView.paintSection(self, painter, rect, logicalIndex)
