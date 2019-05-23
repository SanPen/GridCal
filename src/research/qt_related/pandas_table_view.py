# from PyQt5.QtWidgets import *
# from PyQt5 import QtCore
from PySide2.QtWidgets import *
from PySide2 import QtCore
import pandas as pd
import numpy as np


class PandasModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """
    def __init__(self, data: pd.DataFrame, parent=None, editable=False, editable_min_idx=-1, decimals=6):
        """

        :param data:
        :param parent:
        :param editable:
        :param editable_min_idx:
        :param decimals:
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.data_c = data.values
        self.cols_c = data.columns
        self.index_c = data.index.values
        self.editable = editable
        self.editable_min_idx = editable_min_idx
        self.r, self.c = self.data_c.shape
        self.isDate = False
        if self.r > 0 and self.c > 0:
            if isinstance(self.index_c[0], np.datetime64):
                self.index_c = pd.to_datetime(self.index_c)
                self.isDate = True

        self.format_string = '.' + str(decimals) + 'f'

        self.formatter = lambda x: "%.2f" % x

    def flags(self, index):
        if self.editable and index.column() > self.editable_min_idx:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

    def rowCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return self.r

    def columnCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return self.c

    def data(self, index, role=None):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                val = self.data_c[index.row(), index.column()]
                if isinstance(val, str):
                    return val
                elif isinstance(val, complex):
                    if val.real != 0 or val.imag != 0:
                        return val.__format__(self.format_string)
                    else:
                        return '0'
                else:
                    if val != 0:
                        return val.__format__(self.format_string)
                    else:
                        return '0'
        return None

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        self.data_c[index.row(), index.column()] = value
        return None

    def headerData(self, p_int, orientation, role):
        """

        :param p_int:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.cols_c[p_int]
            elif orientation == QtCore.Qt.Vertical:
                if self.index_c is None:
                    return p_int
                else:
                    if self.isDate:
                        return self.index_c[p_int].strftime('%Y/%m/%d  %H:%M.%S')
                    else:
                        return str(self.index_c[p_int])
        return None

    def copy_to_column(self, row, col):
        """
        Copies one value to all the column
        @param row: Row of the value
        @param col: Column of the value
        @return: Nothing
        """
        self.data_c[:, col] = self.data_c[row, col]


if __name__ == '__main__':
    import sys

    arr = np.random.rand(3, 3) + 1j * np.random.rand(3, 3)
    df =pd.DataFrame(arr)

    model = PandasModel(data=df)

    app = QApplication(sys.argv)
    elm = QTableView()
    elm.setModel(model)
    elm.show()
    sys.exit(app.exec_())
