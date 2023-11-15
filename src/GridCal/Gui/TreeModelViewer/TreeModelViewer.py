
import sys
# GUI imports
from GridCal.Gui.GuiFunctions import *
from GridCal.Gui.TreeModelViewer.MainWindow import *


########################################################################################################################
# Main Window
########################################################################################################################

class TreeModelViewerGUI(QMainWindow):

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        QMainWindow.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Roseta Explorer')
        self.setAcceptDrops(True)

        self.open_file_thread_object = None

        self.accepted_extensions = ['.zip', '.xml']
        self.project_directory = ''
        self.lock_ui = True

        # search proxy model
        self.current_model = None
        self.proxyModel = QtCore.QSortFilterProxyModel(self.ui.mainTreeView)
        self.proxyModel.setRecursiveFilteringEnabled(True)
        self.proxyModel.setFilterKeyColumn(0)
        self.ui.mainTreeView.setSortingEnabled(True)

        self.ui.filterComboBox.setModel(get_list_model(['Class', 'Property', 'Value']))
        self.ui.filterComboBox.setCurrentIndex(0)

        # Connections --------------------------------------------------------------------------------------------------
        # self.ui.actionOpen.triggered.connect(self.open_file)

        self.ui.filterButton.clicked.connect(self.filter_main_tree)

        self.ui.mainTreeView.clicked.connect(self.update_main_tree_on_click)

        self.ui.filterComboBox.currentTextChanged.connect(self.on_filter_combobox_changed)

        self.UNLOCK()

    def LOCK(self, val=True):
        """
        Lock the interface to prevent new simulation launches
        :param val:
        :return:
        """
        self.lock_ui = val
        QtGui.QGuiApplication.processEvents()

    def UNLOCK(self):
        """
        Unlock the interface
        """
        if not self.any_thread_running():
            self.LOCK(False)

    def filter_main_tree(self):
        self.proxyModel.setFilterRegExp(self.ui.filterLineEdit.text())

    def update_main_tree_on_click(self, index):
        # ix = self.proxyModel.mapToSource(index)
        # parent = self.current_model.itemFromIndex(ix)
        # for text in ['Object class', 'Property', 'Value']:
        #     children = QtGui.QStandardItem("{}_{}".format(parent.text(), text))
        #     parent.appendRow(children)
        # self.ui.mainTreeView.expand(index)
        pass

    def on_filter_combobox_changed(self):

        idx = self.ui.filterComboBox.currentIndex()

        if idx > -1:
            self.proxyModel.setFilterKeyColumn(idx)

    def get_process_threads(self):
        """
        Get all threads that has to do with processing
        :return: list of process threads
        """
        all_threads = [self.open_file_thread_object]
        return all_threads

    def get_all_threads(self):
        """
        Get all threads
        :return: list of all threads
        """
        all_threads = self.get_process_threads()
        return all_threads

    def any_thread_running(self):
        """
        Checks if any thread is running
        :return: True/False
        """
        val = False

        # this list cannot be created only once, because the None will be copied
        # instead of being a pointer to the future value like it would in a typed language
        all_threads = self.get_all_threads()

        for thr in all_threads:
            if thr is not None:
                if thr.isRunning():
                    return True
        return val

    # def dragEnterEvent(self, event):
    #     """
    #
    #     :param event:
    #     :return:
    #     """
    #     if event.mimeData().hasUrls:
    #         event.accept()
    #     else:
    #         event.ignore()
    #
    # def dragMoveEvent(self, event):
    #     """
    #
    #     :param event:
    #     :return:
    #     """
    #     if event.mimeData().hasUrls:
    #         event.accept()
    #     else:
    #         event.ignore()
    #
    # def dropEvent(self, event):
    #     """
    #     Drop file on the GUI, the default behaviour is to load the file
    #     :param event: event containing all the information
    #     """
    #     if event.mimeData().hasUrls:
    #         events = event.mimeData().urls()
    #         if len(events) > 0:
    #
    #             file_names = list()
    #
    #             for event in events:
    #                 file_name = event.toLocalFile()
    #                 name, file_extension = os.path.splitext(file_name)
    #                 if file_extension.lower() in self.accepted_extensions:
    #                     file_names.append(file_name)
    #                 else:
    #                     error_msg('The file type ' + file_extension.lower() + ' is not accepted :(')
    #
    #             self.open_file_now(filenames=file_names)
    #
    # def open_file(self):
    #     """
    #     Open file from a Qt thread to remain responsive
    #     """
    #
    #     files_types = "Formats (*.raw *.RAW *.rawx *.json *.ejson2 *.ejson3 *.xml *.zip )"
    #     # files_types = ''
    #     # call dialog to select the file
    #
    #     options = QFileDialog.Options()
    #
    #     filenames, type_selected = QtWidgets.QFileDialog.getOpenFileNames(parent=self,
    #                                                                       caption='Open file',
    #                                                                       dir=self.project_directory,
    #                                                                       filter=files_types,
    #                                                                       options=options)
    #
    #     if len(filenames) > 0:
    #         self.open_file_now(filenames, None)
    #
    # def open_file_now(self, filenames: List[str], callback=None):
    #     """
    #
    #     """
    #     if len(filenames) > 0:
    #
    #         # store the working directory
    #         self.project_directory = os.path.dirname(filenames[0])
    #
    #         # lock the ui
    #         self.LOCK()
    #
    #         # create thread
    #         self.open_file_thread_object = filedrv.FileOpenThread(
    #             file_name=filenames if len(filenames) > 1 else filenames[0])
    #
    #         # make connections
    #         self.open_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
    #         self.open_file_thread_object.progress_text.connect(self.ui.progressLabel.setText)
    #         self.open_file_thread_object.done_signal.connect(self.UNLOCK)
    #         if callback is None:
    #             self.open_file_thread_object.done_signal.connect(self.post_open_file)
    #         else:
    #             self.open_file_thread_object.done_signal.connect(callback)
    #
    #         # thread start
    #         self.open_file_thread_object.start()
    #
    # def post_open_file(self):
    #
    #     nlog = len(self.open_file_thread_object.logger)
    #
    #     if nlog > 0:
    #         logger_model = get_logger_tree_model(self.open_file_thread_object.logger)
    #         self.ui.loggerTreeView.setModel(logger_model)
    #
    #         # warning_msg("There were " + str(nlog) + ' errors or warnings')  # TODO: uncomment
    #
    #     self.current_model = get_cim_tree_model(self.open_file_thread_object.model)
    #
    #     self.proxyModel.setSourceModel(self.current_model)
    #     self.ui.mainTreeView.setModel(self.proxyModel)
    #
    #     if nlog > 0:
    #         warning_msg("There were " + str(nlog) + ' errors or warnings')  # TODO: uncomment
    #
    #     self.UNLOCK()
    #     gc.collect()

    def set_circuit(self, mdl):

        if mdl is not None:
            self.current_model = get_cim_tree_model(mdl)

            self.proxyModel.setSourceModel(self.current_model)
            self.ui.mainTreeView.setModel(self.proxyModel)

    def clear_now(self):
        print()


def runTreeModelViewerGUI(use_native_dialogues=False):
    """
    Main function to run the GUI
    :return:
    """
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # ['Breeze', 'Oxygen', 'QtCurve', 'Windows', 'Fusion']

    # dark = QDarkPalette(None)
    # dark.set_app(app)

    window = TreeModelViewerGUI()
    h = 740
    window.resize(int(1.61 * h), h)  # golden ratio :)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    runTreeModelViewerGUI()
