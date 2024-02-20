from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import QApplication, QMainWindow, QTableView, QVBoxLayout, QLineEdit, QWidget
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


class YourTableModel(QAbstractTableModel):
    def __init__(self, data, header_data, parent=None):
        super().__init__(parent)
        self._data = data
        self._header_data = header_data

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        if self._data:
            return len(self._data[0])
        return 0

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._header_data[section])
            else:
                return str(section + 1)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return ""

        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            return str(self._data[row][col])

        return ""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Table Filtering Example")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Create the table view and set up the model
        self.table_view = QTableView(self)
        # Inside MainWindow class __init__ method
        self.model = YourTableModel(data=[[1, 'Alice'],
                                          [2, 'Bob'],
                                          [3, 'Charlie']],
                                    header_data=['ID', 'Name'])
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.table_view.setModel(self.proxy_model)

        # Create the line edit for filtering
        self.filter_line_edit = QLineEdit(self)
        self.filter_line_edit.setPlaceholderText("Filter...")

        # Connect the line edit to the filter function
        self.filter_line_edit.textChanged.connect(self.filter_table)

        # Add widgets to the layout
        layout.addWidget(self.filter_line_edit)
        layout.addWidget(self.table_view)

    def filter_table(self, text):
        filter_text = text.lower()
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterFixedString(filter_text)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()