# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from PySide6 import QtCore, QtWidgets, QtGui
from GridCal.Gui.wrappable_table_model import WrappableTableModel
from GridCal.Gui.results_model import ResultsModel


class HeaderViewWithWordWrap(QtWidgets.QHeaderView):
    """
    HeaderViewWithWordWrap
    """

    def __init__(self, parent) -> None:
        """
        THe parent must be passed on
        :param parent:
        """
        super().__init__(QtCore.Qt.Orientation.Horizontal, parent)

        # Get the table view (assumes the header's parent is a QTableView)
        self.tableView: QtWidgets.QTableView = self.parentWidget()

        if isinstance(self.tableView, QtWidgets.QTableView):

            self.setSectionsClickable(True)  # Enable section clickability
            self.setHighlightSections(True)  # Ensure visual feedback when sections are clicked

            # Connect the sectionClicked signal to the select_column method
            self.sectionClicked.connect(self.select_column)
            self.sectionDoubleClicked.connect(self.sort_column)
        else:
            raise Exception("The parent is not a QTableView :(" + str(type(self.tableView)) + ")")

    def sectionSizeFromContents(self, logicalIndex: int) -> QtCore.QSize:
        """

        :param logicalIndex:
        :return:
        """
        mdl: WrappableTableModel = self.model()
        if mdl:
            headerText = mdl.headerData(section=logicalIndex,
                                        orientation=self.orientation(),
                                        role=QtCore.Qt.ItemDataRole.DisplayRole)
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

    def select_column(self, logicalIndex: int):
        """
        Select the column corresponding to the clicked header.
        :param logicalIndex: Index of the clicked header section (column)
        """
        # Select the column
        self.tableView.selectColumn(logicalIndex)

    def sort_column(self, i: int):
        """

        :param i:
        :return:
        """
        mdl = self.model()  # assign with typing

        if isinstance(mdl, ResultsModel):
            mdl.sort_column(c=i)
            mdl.update()



