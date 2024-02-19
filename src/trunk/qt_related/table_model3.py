import sys
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import QApplication, QMainWindow, QTableView, QVBoxLayout, QWidget, QPushButton, QInputDialog

class MyTableModel(QAbstractTableModel):
    def __init__(self, data, headers, parent=None):
        super(MyTableModel, self).__init__(parent)
        self._data = data
        self._headers = headers

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return self._data[index.row()][index.column()]

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole:
            try:
                # Attempt to convert the input to a float value
                value = float(value)
            except ValueError:
                return False  # Input is not a valid float

            # Update the data in the model
            self._data[index.row()][index.column()] = value

            # Emit the dataChanged signal to notify views
            self.dataChanged.emit(index, index)

            return True

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super(MyTableModel, self).headerData(section, orientation, role)

    def addRow(self, rowData):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._data.append(rowData)
        self.endInsertRows()

    def removeRow(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._data[row]
        self.endRemoveRows()

    def sort(self, column, order=Qt.AscendingOrder):
        self.layoutAboutToBeChanged.emit()

        self._data = sorted(self._data, key=lambda x: x[column], reverse=(order == Qt.DescendingOrder))

        self.layoutChanged.emit()
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.data = [
            [3.0, 2.0, 1.0],
            [6.0, 5.0, 4.0],
            [9.0, 8.0, 7.0],
        ]
        self.headers = ["P", "Qmin", "Qmax"]

        self.table_model = MyTableModel(self.data, self.headers)

        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)

        # Enable row selection
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)

        sort_button = QPushButton("Sort by Column 0")
        sort_button.clicked.connect(self.sortByColumn0)

        add_row_button = QPushButton("Add Row")
        add_row_button.clicked.connect(self.addRow)

        remove_row_button = QPushButton("Remove Selected Row")
        remove_row_button.clicked.connect(self.removeSelectedRow)

        update_value_button = QPushButton("Update Value")
        update_value_button.clicked.connect(self.updateValue)

        # Create a vertical layout for buttons
        button_layout = QVBoxLayout()
        button_layout.addWidget(sort_button)
        button_layout.addWidget(add_row_button)
        button_layout.addWidget(remove_row_button)
        button_layout.addWidget(update_value_button)

        # Create a horizontal layout for the table view and buttons
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.table_view)
        main_layout.addLayout(button_layout)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)

        self.setCentralWidget(central_widget)

    def sortByColumn0(self):
        self.table_model.sort(0)

    def addRow(self):
        new_row_data = [0.0, 0.0, 0.0]
        self.table_model.addRow(new_row_data)

    def removeSelectedRow(self):
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if selected_indexes:
            # Assuming the selection model is set to single selection mode
            row = selected_indexes[0].row()
            self.table_model.removeRow(row)

    def updateValue(self):
        row = 1  # Row to update
        column = 0  # Column to update
        new_value, ok = QInputDialog.getDouble(self, "Update Value", "New Value:", 0.0, -1000.0, 1000.0, 1)
        if ok:
            index = self.table_model.index(row, column)
            self.table_model.setData(index, new_value, role=Qt.EditRole)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())