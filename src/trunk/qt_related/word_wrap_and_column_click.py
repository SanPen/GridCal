from PySide6 import QtCore, QtWidgets, QtGui


class WrappableTableModel(QtCore.QAbstractTableModel):
    """
    Simple table model with wrappable headers for demonstration purposes.
    """

    def __init__(self, data, headers):
        super().__init__()
        self._data = data
        self._headers = headers

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])

    def data(self, index, role):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return self._data[index.row()][index.column()]

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Orientation.Horizontal and role == QtCore.Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def hide_headers(self):
        pass

    def unhide_headers(self):
        pass


class HeaderViewWithWordWrap(QtWidgets.QHeaderView):
    """
    HeaderViewWithWordWrap - Header view that wraps text and selects columns on click.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(QtCore.Qt.Orientation.Horizontal, parent)

        # Get the table view (assumes the header's parent is a QTableView)
        self.tableView = self.parentWidget()

        if isinstance(self.tableView, QtWidgets.QTableView):

            self.setSectionsClickable(True)  # Enable section clickability
            self.setHighlightSections(True)  # Ensure visual feedback when sections are clicked

            # Connect the sectionClicked signal to the select_column method
            self.sectionClicked.connect(self.select_column)
        else:
            raise Exception("The parent is not a QTableView :(")

    def sectionSizeFromContents(self, logicalIndex: int) -> QtCore.QSize:
        """
        Override section size to wrap text if needed.
        """
        mdl: WrappableTableModel = self.model()
        if mdl:
            headerText = mdl.headerData(logicalIndex, self.orientation(), QtCore.Qt.ItemDataRole.DisplayRole)
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
        Custom painting to handle text wrapping in header.
        """
        mdl: WrappableTableModel = self.model()
        if mdl:
            painter.save()
            super().paintSection(painter, rect, logicalIndex)
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

        # Debugging prints
        # print(f"Column {logicalIndex} selected")



class MyWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Create table data and headers
        data = [
            ["Alice", 23, "Engineer"],
            ["Bob", 30, "Doctor"],
            ["Charlie", 22, "Artist"],
            ["David", 40, "Lawyer"]
        ]
        headers = ["Name", "Age", "Occupation with very long description"]

        # Set up the model
        self.model = WrappableTableModel(data, headers)

        # Set up the table view
        self.tableView = QtWidgets.QTableView(self)
        self.tableView.setModel(self.model)

        # Set up the custom header and explicitly pass the table view as the parent
        self.headerView = HeaderViewWithWordWrap(self.tableView)
        self.tableView.setHorizontalHeader(self.headerView)

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tableView)


# Main application loop
if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.setWindowTitle("QTableView with Wrappable Headers and Column Selection")
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec())
