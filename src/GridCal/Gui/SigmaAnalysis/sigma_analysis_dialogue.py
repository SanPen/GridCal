import os
import string
import sys
from random import randint
from enum import Enum
import numpy as np
import pandas as pd
from PySide2.QtWidgets import *

from GridCal.Gui.SigmaAnalysis.gui import *
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.SigmaAnalysis.sigma_analysis_driver import SigmaAnalysisResults


class PandasModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """
    def __init__(self, data, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._data = np.array(data.values)
        self._cols = data.columns
        self._index = data.index.values
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


def get_list_model(iterable):
    """
    get Qt list model from a simple iterable
    :param iterable: 
    :return: List model
    """
    list_model = QtGui.QStandardItemModel()
    if iterable is not None:
        for val in iterable:
            # for the list model
            item = QtGui.QStandardItem(val)
            item.setEditable(False)
            list_model.appendRow(item)
    return list_model


class SigmaAnalysisGUI(QtWidgets.QMainWindow):

    def __init__(self, parent=None, results: SigmaAnalysisResults = None, bus_names=None, use_native_dialogues=True):
        """

        :param parent:
        :param results:
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('HELM-Sigma analysis dialogue')

        self.use_native_dialogues = use_native_dialogues

        self.results = results

        if results is not None:
            ax = self.ui.plotwidget.get_axis()
            fig = self.ui.plotwidget.get_figure()
            self.results.plot(fig, ax)
            fig.tight_layout()

            n = len(bus_names)

            self.mdl = self.results.mdl(result_type=ResultTypes.SigmaPlusDistances,
                                        indices=np.arange(n),
                                        names=bus_names)
            self.ui.tableView.setModel(self.mdl)
        else:
            self.mdl = None

        self.ui.actionCopy_to_clipboard.triggered.connect(self.copy_to_clipboard)
        self.ui.actionSave.triggered.connect(self.save)

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

    def copy_to_clipboard(self):
        """
        Copy data to clipboard
        """
        if self.mdl is not None:
            self.mdl.copy_to_clipboard()

    def save(self):
        """

        :return:
        """
        if self.mdl is not None:
            options = QFileDialog.Options()
            if self.use_native_dialogues:
                options |= QFileDialog.DontUseNativeDialog

            file, filter = QFileDialog.getSaveFileName(self, "Export results", '',
                                                       filter="CSV (*.csv);;Excel files (*.xlsx)",
                                                       options=options)

            if file != '':
                if 'xlsx' in filter:
                    f = file
                    if not f.endswith('.xlsx'):
                        f += '.xlsx'
                    self.mdl.save_to_excel(f, mode='real')
                    print('Saved!')
                if 'csv' in filter:
                    f = file
                    if not f.endswith('.csv'):
                        f += '.csv'
                    self.mdl.save_to_csv(f, mode='real')
                    print('Saved!')



if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = SigmaAnalysisGUI()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

