from PySide2.QtWidgets import *
from PySide2 import QtCore
from enum import Enum


class SomeEnum(Enum):
    A = 'A'
    B = 'B'
    C = 'C'


class EnumModel(QtCore.QAbstractListModel):

    def __init__(self, list_of_enums):
        """
        Enumeration model
        :param list_of_enums: list of enumeration values to show
        """
        QtCore.QAbstractListModel.__init__(self)
        self.items = list_of_enums

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.items)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid() is True:
            if role == QtCore.Qt.DisplayRole:
                return self.items[index.row()].value[0]
        return None


if __name__ == '__main__':
    import sys

    model = EnumModel([SomeEnum.A, SomeEnum.A, SomeEnum.B, SomeEnum.C])

    app = QApplication(sys.argv)
    lst = QListView()
    lst.setModel(model)
    lst.show()
    sys.exit(app.exec_())
