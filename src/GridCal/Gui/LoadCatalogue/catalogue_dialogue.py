import sys
import numpy as np
from numpy.random import default_rng
import networkx as nx
import os
from typing import Union, List, Callable
import pandas as pd
from PySide6 import QtWidgets

from GridCal.Gui.LoadCatalogue.SelectComponents import Ui_MainWindow
import GridCalEngine.Devices as dev
import GridCal.Session.file_handler as filedrv
# from GridCalEngine.Devices.multi_circuit import MultiCircuit
# from GridCalEngine.Utils.ThirdParty.SyntheticNetworks.rpgm_algo import RpgAlgorithm


class CatalogueGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, ):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Custom Catalogue')

        self.ui.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.ui.buttonBox.accepted.connect(self.on_accept)
        self.ui.buttonBox.rejected.connect(self.on_reject)

    def on_accept(self):
        self.open_file_threaded()
        self.accept()

    def on_reject(self):
        self.reject()

    def open_file_threaded(self, post_function=None, title: str = 'Open file'):
        files_types = "CSV (*.csv)"

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(None,
                                                            caption=title,
                                                            filter=f"Formats ({files_types})")

        if filename:
            self.open_file_now([filename], post_function)

    def open_file_now(self, filenames: Union[str, List[str]],
                      post_function: Union[None, Callable[[], None]] = None) -> None:
        """
        Open a file without questions
        :param filenames: list of file names (maybe more than one because of CIM TP and EQ files)
        :param post_function: function callback
        :return: Nothing
        """
        if len(filenames) > 0:
            self.file_name = filenames[0]

            # store the working directory
            self.project_directory = os.path.dirname(self.file_name)

            # lock the ui
            # self.LOCK()

            # create thread
            self.open_file_thread_object = filedrv.FileOpenThread(
                file_name=filenames if len(filenames) > 1 else filenames[0]
            )

            # make connections
            # self.open_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
            # self.open_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
            # self.open_file_thread_object.done_signal.connect(self.UNLOCK)
            if post_function is None:
                self.open_file_thread_object.done_signal.connect(self.post_open_file)
            else:
                self.open_file_thread_object.done_signal.connect(post_function)

            # thread start
            self.open_file_thread_object.start()

            # register as the latest file driver
            self.last_file_driver = self.open_file_thread_object
            print('File opened')

            # register thread
            # self.stuff_running_now.append('file_open')

    def post_open_file(self) -> None:
        """
        Actions to perform after a file has been loaded
        """
        pass


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = CatalogueGUI()
    window.resize(int(1.61 * 400), 400)  # golden ratio
    window.show()
    sys.exit(app.exec())
