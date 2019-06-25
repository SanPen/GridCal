import os
import string
import sys
from random import randint
from enum import Enum

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
# from PySide2.QtCore import *
# from PySide2.QtGui import *
from PySide2.QtWidgets import *

from GridCal.Gui.LoadDesigner.gui import *


class LoadPointsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """
    def __init__(self, n_rows, cols, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._data = np.zeros((n_rows, len(cols)))
        self._cols = cols
        self._index = range(n_rows)
        self.r, self.c = np.shape(self._data)
        self.isDate = False

        if len(self._index) > 0:
            if isinstance(self._index[0], np.datetime64):
                self._index = pd.to_datetime(self._index)
                self.isDate = True

        self.formatter = lambda x: "%.2f" % x

    def rowCount(self, parent=None):
        return self.r

    def columnCount(self, parent=None):
        return self.c

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self._data[index.row(), index.column()])
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._cols[p_int]
            elif orientation == QtCore.Qt.Vertical:
                if self._index is None:
                    return p_int
                else:
                    if self.isDate:
                        return self._index[p_int].strftime('%Y/%m/%d  %H:%M.%S')
                    else:
                        return str(self._index[p_int])
        return None

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        self._data[index.row(), index.column()] = value
        return None


class LoadDesigner(QtWidgets.QDialog):

    def __init__(self, parent=None):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Load designer')

        model = LoadPointsModel(24, ['Value (MW)'])
        self.ui.tableView.setModel(model)

        self.ui.draw_by_peak_pushButton.clicked.connect(self.process_by_peak)

    def msg(self, text, title="Warning"):
        """
        Message box
        :param text: Text to display
        :param title: Name of the window
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()

    def process_by_peak(self):

        x = [self.ui.evening_peak_timeEdit.dateTime().toPython() - timedelta(days=1),
             self.ui.night_valley_timeEdit.dateTime().toPython(),
             self.ui.morning_peak_timeEdit.dateTime().toPython(),
             self.ui.afternoon_valley_timeEdit.dateTime().toPython(),
             self.ui.evening_peak_timeEdit.dateTime().toPython(),
             self.ui.night_valley_timeEdit.dateTime().toPython() + timedelta(days=1)]

        y = [self.ui.evening_peak_doubleSpinBox.value(),
             self.ui.night_valley_doubleSpinBox.value(),
             self.ui.morning_peak_doubleSpinBox.value(),
             self.ui.afternoon_valley_doubleSpinBox.value(),
             self.ui.evening_peak_doubleSpinBox.value(),
             self.ui.night_valley_doubleSpinBox.value()]
        data = pd.DataFrame(data=y, index=x)

        t1 = self.ui.evening_peak_timeEdit.dateTime().toPython() - timedelta(days=1)
        t2 = self.ui.night_valley_timeEdit.dateTime().toPython() + timedelta(days=1)
        dh = int((t2-t1).seconds / 3600 + (t2-t1).days * 24)
        t = [t1 + timedelta(hours=i) for i in range(dh)]
        data2 = data.reindex(t)

        interpolated = data2.interpolate()
        # interpolated = data2.interpolate(method='spline', order=1)

        self.ui.plotwidget.clear()
        ax = self.ui.plotwidget.get_axis()
        interpolated.plot(ax=ax)
        self.ui.plotwidget.redraw()


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = LoadDesigner()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

