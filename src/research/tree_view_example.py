from PySide2.QtWidgets import QTreeView, QFileSystemModel, QApplication
from PySide2 import QtCore, QtWidgets, QtGui
import os


class Main(QTreeView):

    def __init__(self):
        QTreeView.__init__(self)
        # model = QFileSystemModel()
        # model.setRootPath('C:\\')

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(['col1', 'col2', 'col3'])

        self.setModel(model)
        self.doubleClicked.connect(self.double_click)

        # populate data
        for i in range(3):
            parent1 = QtGui.QStandardItem('Family {}. Some long status text for sp'.format(i))
            for j in range(3):
                child1 = QtGui.QStandardItem('Child {}'.format(i * 3 + j))
                child2 = QtGui.QStandardItem('row: {}, col: {}'.format(i, j + 1))
                child3 = QtGui.QStandardItem('row: {}, col: {}'.format(i, j + 2))
                parent1.appendRow([child1, child2, child3])
            model.appendRow(parent1)
            # span container columns
            self.setFirstColumnSpanned(i, self.rootIndex(), True)
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # expand third container
        # index = model.indexFromItem(parent1)
        # self.expand(index)
        # # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # # select last row
        # selmod = self.selectionModel()
        # index2 = model.indexFromItem(child3)
        # selmod.select(index2, QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)

    def double_click(self, signal):
        # file_path = self.model().filePath(signal)
        # print(file_path)
        print('Clicked!')


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    w = Main()
    w.show()
    sys.exit(app.exec_())
