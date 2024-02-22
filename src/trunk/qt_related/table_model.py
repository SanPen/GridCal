import sys
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSize
from PySide6.QtWidgets import QApplication, QMainWindow, QTableView, QVBoxLayout, QWidget, QPushButton

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
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super(MyTableModel, self).headerData(section, orientation, role)

    def addRow(self, rowData):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._data.append(rowData)
        self.endInsertRows()

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.data = [
            ["John", 30, "Engineer"],
            ["Alice", 25, "Designer"],
            ["Bob", 35, "Manager"],
        ]
        self.headers = ["Name", "Age", "Occupation"]

        self.table_model = MyTableModel(self.data, self.headers)

        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)

        add_row_button = QPushButton("Add Row")
        add_row_button.clicked.connect(self.addRow)

        central_widget = QWidget()
        central_layout = QVBoxLayout()
        central_layout.addWidget(self.table_view)
        central_layout.addWidget(add_row_button)
        central_widget.setLayout(central_layout)

        self.setCentralWidget(central_widget)

    def addRow(self):
        new_row_data = ["New Person", 0, "Unemployed"]
        self.table_model.addRow(new_row_data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
