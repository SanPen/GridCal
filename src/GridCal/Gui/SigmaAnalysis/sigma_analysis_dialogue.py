import sys
import numpy as np
from PySide6 import QtWidgets

from GridCal.Gui.SigmaAnalysis.gui import Ui_MainWindow
from GridCal.Gui.Session.results_model import ResultsModel
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.Simulations.SigmaAnalysis.sigma_analysis_driver import SigmaAnalysisResults


class SigmaAnalysisGUI(QtWidgets.QMainWindow):

    def __init__(self, parent=None, results: SigmaAnalysisResults = None, bus_names=None,
                 good_coefficients=True):
        """

        :param parent:
        :param results:
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('HELM-Sigma analysis dialogue')

        self.results = results

        if results is not None:
            ax = self.ui.plotwidget.get_axis()
            fig = self.ui.plotwidget.get_figure()
            self.results.plot(fig, ax)
            fig.tight_layout()

            n = len(bus_names)

            self.mdl = ResultsModel(self.results.mdl(result_type=ResultTypes.SigmaPlusDistances,
                                                     indices=np.arange(n),
                                                     names=bus_names))
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
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
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
            file, filter = QtWidgets.QFileDialog.getSaveFileName(self, "Export results", '',
                                                                 filter="CSV (*.csv);;Excel files (*.xlsx)")

            if file != '':
                if 'xlsx' in filter:
                    f = file
                    if not f.endswith('.xlsx'):
                        f += '.xlsx'
                    self.mdl.save_to_excel(f)
                    print('Saved!')
                if 'csv' in filter:
                    f = file
                    if not f.endswith('.csv'):
                        f += '.csv'
                    self.mdl.save_to_csv(f)
                    print('Saved!')


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SigmaAnalysisGUI()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())
