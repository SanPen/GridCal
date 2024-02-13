import sys
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QTableView, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtWidgets import QStyledItemDelegate


class MyTableModel(QAbstractTableModel):
    def __init__(self, data, headers):
        super(MyTableModel, self).__init__()
        self.data = data
        self.headers = headers

    def rowCount(self, parent=QModelIndex()):
        return len(self.data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.data[index.row()][index.column()]
        elif role == Qt.DecorationRole and index.column() == 0:
            # Assuming the first column is for icons
            return QIcon(self.data[index.row()][index.column()])
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None


class MyWindow(QWidget):
    def __init__(self):
        super(MyWindow, self).__init__()

        self.initUI()

    def initUI(self):
        data = [
            [QIcon.fromTheme("document-open"), "File 1", "Text 1"],
            [QIcon.fromTheme("document-save"), "File 2", "Text 2"],
            [QIcon.fromTheme("edit-cut"), "File 3", "Text 3"],
        ]
        headers = ["Icon", "Name", "Text"]

        model = MyTableModel(data, headers)
        table_view = QTableView(self)
        table_view.setModel(model)

        # Add a button to each row for updating
        update_button_delegate = UpdateButtonDelegate(self)
        table_view.setItemDelegateForColumn(3, update_button_delegate)

        layout = QVBoxLayout(self)
        layout.addWidget(table_view)
        self.setLayout(layout)

        self.setGeometry(100, 100, 600, 400)
        self.setWindowTitle("PySide6 TableView Example")
        self.show()


class UpdateButtonDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        button = QPushButton("Update", parent)
        button.clicked.connect(self.handleButtonClick)
        return button

    def setEditorData(self, editor, index):
        pass

    def setModelData(self, editor, model, index):
        pass

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def handleButtonClick(self):
        print("Update button clicked")


def main():
    app = QApplication(sys.argv)
    window = MyWindow()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
