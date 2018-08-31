from PyQt5.QtWidgets import QTreeView, QFileSystemModel, QApplication
from PyQt5 import QtCore, QtWidgets, QtGui, Qt
import os


class GroupNode(object):
    """A group node in the tree of databases model."""

    def __init__(self, parent, name):
        """Create a group node for the tree of databases model."""

        self.children = []
        self.parent = parent
        self.name = name


    def __len__(self):
        return len(self.children)


    def insertChild(self, child, position=0):
        """Insert a child in a group node."""
        self.children.insert(position, child)


    def childAtRow(self, row):
        """The row-th child of this node."""

        assert 0 <= row <= len(self.children)
        return self.children[row]


    def row(self):
        """The position of this node in the parent's list of children."""

        if self.parent:
            return self.parent.children.index(self)

        return 0


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
