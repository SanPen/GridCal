import sys
from typing import Union, List, Callable
import pandas as pd
from PySide6 import QtWidgets

from GridCal.Gui.LoadCatalogue.SelectComponents import Ui_MainWindow
import GridCalEngine.Devices as dev
import GridCal.Session.file_handler as filedrv
from GridCalEngine.Devices import TransformerType, UndergroundLineType, SequenceLineType
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCal.Session.synchronization_driver as syncdrv
from GridCalEngine.Devices.assets import Assets


class CatalogueGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, ):
        """
        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Custom Catalogue')
        self.circuit: MultiCircuit = MultiCircuit()

        self.ui.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.ui.buttonBox.accepted.connect(self.on_accept)
        self.ui.buttonBox.rejected.connect(self.on_reject)

        self.file_sync_thread = syncdrv.FileSyncThread(self.circuit, None, None)

    def on_accept(self):
        self.open_file_threaded()
        self.accept()

    def on_reject(self):
        self.reject()

    def read_csv_file(self, filename):
        return pd.read_csv(filename)

    def get_transformer_catalogue(self, df):
        lst = list()
        for _, item in df.iterrows():
            transformer = TransformerType(
                hv_nominal_voltage=item['HV (kV)'],
                lv_nominal_voltage=item['LV (kV)'],
                nominal_power=item['Rate (MVA)'],
                copper_losses=item['Copper losses (kW)'],
                iron_losses=item['No load losses (kW)'],
                no_load_current=item['No load current (%)'],
                short_circuit_voltage=item['V short circuit (%)'],
                gr_hv1=0.5,
                gx_hv1=0.5,
                name=item['Name']
            )
            lst.append(transformer)
        return lst

    def get_cables_catalogue(self, df):
        # df = pd.read_csv(filename)
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
        # df = pd.read_csv(filename)
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

    def open_file_and_add_data(self, filename):
        df = self.read_csv_file(filename)
        print(df.head())
        checkbox_checked = False

        if self.ui.checkBox.isChecked() or self.ui.checkBox_5.isChecked():
            print(df.head())
            transformers = self.get_transformer_catalogue(df)
            print(f'Adding {len(transformers)} transformer types')
            self.circuit.transformer_types += transformers
            print(self.circuit.transformer_types)

        elif self.ui.checkBox_2.isChecked():  # and self.open_file_thread_object.circuit == 'UndergroundLineType'
            self.circuit.underground_cable_types += self.get_cables_catalogue(df)

        elif self.ui.checkBox_3.isChecked() or self.ui.checkBox_6.isChecked():  # and self.open_file_thread_object.circuit == 'SequenceLineType'
            self.circuit.sequence_line_types += self.get_sequence_lines_catalogue(df)

        else:
            if not checkbox_checked:
                # quit_msg = "No checkbox was selected for adding the component to the catalogue."
                print("No checkbox was selected for adding the component to the catalogue.")
                # QtWidgets.QMessageBox.warning(self, "Can't upload file", quit_msg)

    def open_file_threaded(self, post_function=None, title: str = 'Open file'):
        files_types = "CSV (*.csv)"
        dialogue = QtWidgets.QFileDialog(None, caption=title, filter=f"Formats ({files_types})")
        if dialogue.exec():
            filename = dialogue.selectedFiles()[0]
            self.open_file_and_add_data(filename)
            if post_function:
                post_function()

    def print_circuit_content(self):
        print("Circuit Content:")
        print("Transformer Types:")
        for transformer in self.circuit.transformer_types:
            print(transformer)
        print("Underground Cable Types:")
        for cable in self.circuit.underground_cable_types:
            print(cable)
        print("Sequence Line Types:")
        for line in self.circuit.sequence_line_types:
            print(line)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = CatalogueGUI()
    window.resize(int(1.61 * 400), 400)  # golden ratio
    window.show()
    sys.exit(app.exec())

    # def open_file_threaded(self, post_function=None, title: str = 'Open file'):
    #     files_types = "CSV (*.csv)"
    #
    #     filename, _ = QtWidgets.QFileDialog.getOpenFileName(None,
    #                                                         caption=title,
    #                                                         filter=f"Formats ({files_types})")
    #
    #     if filename:
    #         self.open_file_now([filename], post_function)
    #
    # def open_file_now(self, filenames: Union[str, List[str]],
    #                   post_function: Union[None, Callable[[], None]] = None) -> None:
    #     """
    #     Open a file without questions
    #     :param filenames: list of file names (maybe more than one because of CIM TP and EQ files)
    #     :param post_function: function callback
    #     :return: Nothing
    #     """
    #     if len(filenames) > 0:
    #         self.file_name = filenames[0]
    #
    #         # store the working directory
    #         self.project_directory = os.path.dirname(self.file_name)
    #
    #         # lock the ui
    #         # self.LOCK()
    #
    #         # create thread
    #         self.open_file_thread_object = filedrv.FileOpenThread(
    #             file_name=filenames if len(filenames) > 1 else filenames[0]
    #         )
    #
    #         # make connections
    #         # self.open_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
    #         # self.open_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
    #         # self.open_file_thread_object.done_signal.connect(self.UNLOCK)
    #         if post_function is None:
    #             self.open_file_thread_object.done_signal.connect(self.post_open_file)
    #         else:
    #             self.open_file_thread_object.done_signal.connect(post_function)
    #
    #         # thread start
    #         self.open_file_thread_object.start()
    #
    #         # register as the latest file driver
    #         self.last_file_driver = self.open_file_thread_object
    #         print('File opened')
    #
    #         # register thread
    #         # self.stuff_running_now.append('file_open')
    #
    # def post_open_file(self) -> None:
    #     """
    #     Actions to perform after a file has been loaded
    #     """
    #     print('Post open file')
    #     if self.open_file_thread_object is not None:
    #         print('Valid')
    #         checkbox_checked = False
    #         if self.open_file_thread_object.valid:
    #             print('Valid2')
    #             # Check the state of checkboxes and add items to the catalogue accordingly
    #             if self.ui.checkBox.isChecked() or self.ui.checkBox_5.isChecked():  # and self.open_file_thread_object.circuit == 'TransformerType'
    #                 self.circuit.transformer_types += self.get_transformer_catalogue(self.open_file_thread_object.file_name)
    #                 # transformers = self.get_transformer_catalogue(self.open_file_thread_object.file_name)
    #                 # self.circuit.transformer_types += transformers
    #                 # print(f'Added {len(transformers)} transformer types')
    #             elif self.ui.checkBox_2.isChecked():  # and self.open_file_thread_object.circuit == 'UndergroundLineType'
    #                 self.circuit.underground_cable_types += self.get_cables_catalogue(self.open_file_thread_object.file_name)
    #             elif self.ui.checkBox_3.isChecked() or self.ui.checkBox_6.isChecked():  # and self.open_file_thread_object.circuit == 'SequenceLineType'
    #                 self.circuit.sequence_line_types += self.get_sequence_lines_catalogue(self.open_file_thread_object.file_name)
    #             # elif self.ui.checkBox_X.isChecked() : # and self.open_file_thread_object.circuit == 'Wire'
    #             #     self.circuit.wire_types += get_wires_catalogue(self.open_file_thread_object.file_name)
    #             else:
    #                 if not checkbox_checked:
    #                     quit_msg = "No checkbox was selected for adding the component to the catalogue."
    #                     QtWidgets.QMessageBox.warning(self, "Can't upload file", quit_msg)
    #
    # def get_transformer_catalogue(self, filename):
    #     print('Getting transformer catalogue')
    #     df = pd.read_csv(filename)
    #     print(df.head())
    #     lst = []
    #     for _, item in df.iterrows():
    #         tpe = TransformerType(
    #             hv_nominal_voltage=item['HV (kV)'],
    #             lv_nominal_voltage=item['LV (kV)'],
    #             nominal_power=item['Rate (MVA)'],
    #             copper_losses=item['Copper losses (kW)'],
    #             iron_losses=item['No load losses (kW)'],
    #             no_load_current=item['No load current (%)'],
    #             short_circuit_voltage=item['V short circuit (%)'],
    #             gr_hv1=0.5,
    #             gx_hv1=0.5,
    #             name=item['Name']
    #         )
    #         lst.append(tpe)
    #     print(f'Returning {len(lst)} transformer types')
    #     return lst
