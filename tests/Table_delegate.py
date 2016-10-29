# https://gist.github.com/Riateche/5984815
import sip

sip.setapi('QString', 2)
sip.setapi('QVariant', 2)

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


class TableModel(QAbstractTableModel):
    """
    A simple 5x4 table model to demonstrate the delegates
    """

    def rowCount(self, parent=QModelIndex()):
        return 5

    def columnCount(self, parent=QModelIndex()):
        return 4

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        if not role == Qt.DisplayRole: return None
        return "{0:02d}".format(index.row())

    def setData(self, index, value, role=Qt.DisplayRole):
        print
        "setData", index.row(), index.column(), value

    def flags(self, index):
        if (index.column() == 0):
            return Qt.ItemIsEditable | Qt.ItemIsEnabled
        else:
            return Qt.ItemIsEnabled


class ButtonDelegate(QItemDelegate):
    commitData = pyqtSignal(object)

    def __init__(self, parent):
        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        combo = QPushButton(str(index.data()), parent)

        # self.connect(combo, QtCore.SIGNAL("currentIndexChanged(int)"), self, QtCore.SLOT("currentIndexChanged()"))
        combo.clicked.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        # editor.setCurrentIndex(int(index.model().data(index)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text())

    @pyqtSlot()
    def currentIndexChanged(self):
        self.commitData.emit(self.sender())


class ComboDelegate(QItemDelegate):
    commitData = pyqtSignal(object)
    """
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied
    """

    def __init__(self, parent):
        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        li = list()
        li.append("Zero")
        li.append("One")
        li.append("Two")
        li.append("Three")
        li.append("Four")
        li.append("Five")
        combo.addItems(li)
        # self.connect(combo, QtCore.SIGNAL("currentIndexChanged(int)"), self, QtCore.SLOT("currentIndexChanged()"))
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setCurrentIndex(int(index.model().data(index)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentIndex())

    @pyqtSlot()
    def currentIndexChanged(self):
        self.commitData.emit(self.sender())


class TableView(QTableView):
    """
    A simple table to demonstrate the QComboBox delegate.
    """

    def __init__(self, *args, **kwargs):
        QTableView.__init__(self, *args, **kwargs)

        # Set the delegate for column 0 of our table
        # self.setItemDelegateForColumn(0, ButtonDelegate(self))
        self.setItemDelegateForColumn(0, ComboDelegate(self))
        self.setItemDelegateForColumn(1, ButtonDelegate(self))


if __name__ == "__main__":
    from sys import argv, exit


    class Widget(QWidget):
        """
        A simple test widget to contain and own the model and table.
        """

        def __init__(self, parent=None):
            QWidget.__init__(self, parent)

            l = QVBoxLayout(self)
            self._tm = TableModel(self)
            self._tv = TableView(self)
            # self._tv.setGridStyle(QtCore.Qt.NoPen)
            self._tv.setShowGrid(False)
            self._tv.setAlternatingRowColors(True)
            self._tv.setModel(self._tm)
            for row in range(0, self._tm.rowCount()):
                self._tv.openPersistentEditor(self._tm.index(row, 0))
                self._tv.openPersistentEditor(self._tm.index(row, 1))

            l.addWidget(self._tv)


    a = QApplication(argv)
    w = Widget()
    w.move(0, 0)
    w.resize(800, 600)
    w.show()
    w.raise_()
    exit(a.exec_())