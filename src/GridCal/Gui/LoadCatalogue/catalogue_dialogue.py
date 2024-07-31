import sys
import pandas as pd
from PySide6 import QtWidgets

from GridCal.Gui.LoadCatalogue.SelectComponents import Ui_MainWindow
from GridCalEngine.Devices import TransformerType, UndergroundLineType, SequenceLineType
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCal.Session.synchronization_driver as syncdrv


class CatalogueGUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        """
        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.selected_file = None
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Custom Catalogue')
        self.circuit: MultiCircuit = MultiCircuit()

        self.ui.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.ui.buttonBox.accepted.connect(self.on_accept)
        self.ui.buttonBox.rejected.connect(self.on_reject)

        self.file_sync_thread = syncdrv.FileSyncThread(self.circuit, None, None)

    def on_accept(self):
        if self.ui.checkBox.isChecked() or self.ui.checkBox_2.isChecked() or self.ui.checkBox_3.isChecked():
            self.open_file_threaded()
            self.accept()
        else:
            quit_msg = "No checkbox was selected for adding the component to the catalogue."
            QtWidgets.QMessageBox.warning(self, "Can't upload file", quit_msg)
            print("No checkbox was selected for adding the component to the catalogue.")

    def on_reject(self):
        self.reject()

    def read_csv_file(self, filename):
        return pd.read_csv(filename)

    def open_file_threaded(self, post_function=None, title: str = 'Open file'):
        files_types = "CSV (*.csv)"
        dialogue = QtWidgets.QFileDialog(None, caption=title, filter=f"Formats ({files_types})")
        if dialogue.exec():
            self.selected_file = dialogue.selectedFiles()[0]
            if post_function:
                post_function()

    def get_transformer_catalogue(self, df):
        lst = list()
        for _, item in df.iterrows():
            transformer = TransformerType(hv_nominal_voltage=item['HV (kV)'],
                                          lv_nominal_voltage=item['LV (kV)'],
                                          nominal_power=item['Rate (MVA)'],
                                          copper_losses=item['Copper losses (kW)'],
                                          iron_losses=item['No load losses (kW)'],
                                          no_load_current=item['No load current (%)'],
                                          short_circuit_voltage=item['V short circuit (%)'],
                                          gr_hv1=0.5,
                                          gx_hv1=0.5,
                                          name=item['Name'])
            lst.append(transformer)
        return lst

    def get_cables_catalogue(self, df):
        lst = list()
        for _, item in df.iterrows():
            tpe = UndergroundLineType(name=item['Name'],
                                      Imax=item['Rated current [kA]'],
                                      Vnom=item['Rated voltage [kV]'],
                                      R=item['R [Ohm/km AC@20°C]'],
                                      X=item['X [Ohm/km]'],
                                      B=0.0,
                                      R0=item['R0 (AC) [Ohm/km]'],
                                      X0=item['X0  [Ohm/km]'],
                                      B0=0.0)
            lst.append(tpe)

        return lst

    def get_sequence_lines_catalogue(self, df):
        lst = list()
        for i, item in df.iterrows():
            tpe = SequenceLineType(name=item['Name'],
                                   Vnom=item['Vnom (kV)'],
                                   Imax=item['Imax (kA)'],
                                   R=item['r (ohm/km)'],
                                   X=item['x (ohm/km)'],
                                   B=item['b (uS/km)'],
                                   R0=item['r0 (ohm/km)'],
                                   X0=item['x0 (ohm/km)'],
                                   B0=item['b0 (uS/km)'])

            lst.append(tpe)
        return lst

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = CatalogueGUI()
    window.resize(int(1.61 * 400), 400)  # golden ratio
    window.show()
    sys.exit(app.exec())
