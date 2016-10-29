# The following tells SIP (the system that binds Qt's C++ to Python)
# to return Python native types rather than QString and QVariant
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

    def flags(self, index):
        if index.column() == 0:
            return Qt.ItemIsEditable | Qt.ItemIsEnabled
        else:
            return Qt.ItemIsEnabled

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if not role == Qt.DisplayRole:
            return None
        return "{0:02d}".format(index.row())

    def setData(self, index, value, role=Qt.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """
        setattr(self.objects[index.row()], self.attributes[index.column()], value)


class ComboDelegate(QItemDelegate):
    commitData = pyqtSignal(object)
    """
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied
    """
    def __init__(self, parent):

        QItemDelegate.__init__(self, parent)
        self.combo = None

    @pyqtSlot()
    def currentIndexChanged(self):
        self.commitData.emit(self.sender())
        print()

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        li = list()
        li.append('True')
        li.append('False')
        combo.addItems(li)
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setCurrentIndex(int(index.model().data(index)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentIndex())


class TableView(QTableView):
    """
    A simple table to demonstrate the QComboBox delegate.
    """
    def __init__(self, *args, **kwargs):
        QTableView.__init__(self, *args, **kwargs)

        # Set the delegate for column 0 of our table
        # self.setItemDelegateForColumn(0, ButtonDelegate(self))
        self.setItemDelegateForColumn(0, ComboDelegate(self))

    @pyqtSlot()
    def currentIndexChanged(self, ind):
        print("Combo Index changed {0} {1} : {2}".format(ind, self.sender().currentIndex(), self.sender().currentText()))

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
            self._tv.setModel(self._tm)
            l.addWidget(self._tv)

    a = QApplication(argv)
    w = Widget()
    w.show()
    w.raise_()
    exit(a.exec_())
