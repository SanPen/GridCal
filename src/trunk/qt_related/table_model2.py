import sys
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import QApplication, QMainWindow, QTableView, QVBoxLayout, QWidget, QPushButton, QInputDialog, QSplitter, QFrame


class GeneratorQCurveEditorTableModel(QAbstractTableModel):
    def __init__(self, data, headers, parent=None):
        super(GeneratorQCurveEditorTableModel, self).__init__(parent)
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
            self.dataChanged.emit(index, index)
            return True

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super(GeneratorQCurveEditorTableModel, self).headerData(section, orientation, role)

    def addRow(self, rowData):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._data.append(rowData)
        self.endInsertRows()


class GeneratorQCurveEditor(QMainWindow):
    def __init__(self):
        super(GeneratorQCurveEditor, self).__init__()

        self.data = [
            [1.0, 0.5, 1.5],
            [2.0, 1.0, 2.0],
            [3.0, 1.5, 3.5],
        ]
        self.headers = ["P", "Qmin", "Qmax"]

        self.table_model = GeneratorQCurveEditorTableModel(self.data, self.headers)

        self.l_frame = QFrame()
        self.r_frame = QFrame()
        self.l_layout = QVBoxLayout(self.l_frame)

        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        # self.table_view.doubleClicked.connect(self.cellDoubleClicked)

        self.add_row_button = QPushButton("Add Row")
        self.add_row_button.clicked.connect(self.addRow)

        self.l_layout.addWidget(self.table_view)
        self.l_layout.addWidget(self.add_row_button)

        # Create a splitter to create a vertical split view
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.l_frame)
        splitter.addWidget(self.r_frame)

        central_widget = QWidget()
        central_layout = QVBoxLayout()
        central_layout.addWidget(splitter)
        central_widget.setLayout(central_layout)

        self.setCentralWidget(central_widget)

    def addRow(self):
        new_row_data = [0.0, 0.0, 0.0]
        self.table_model.addRow(new_row_data)

    # def cellDoubleClicked(self, index):
    #     # Double-clicked on the phantom row
    #     column_name = self.headers[index.column()]
    #     value, ok = QInputDialog.getDouble(self, f"Enter {column_name}", f"{column_name}:", 0.0, -1000.0, 1000.0, 1)
    #     if ok:
    #         self.table_model.setData(index, value, role=Qt.EditRole)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorQCurveEditor()
    window.show()
    sys.exit(app.exec())
