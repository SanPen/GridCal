
import sys
from PySide2.QtWidgets import *

from GridCal.Gui.SyncDialogue.gui import *
from GridCal.Engine.IO.synchronization_driver import get_issues_tree_view_model, FileSyncThread


class SyncDialogueWindow(QtWidgets.QDialog):

    def __init__(self, file_sync_thread: FileSyncThread, parent=None):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Sync conflicts')

        self.file_sync_thread = file_sync_thread

        self.file_sync_thread.pause()

        self.model = get_issues_tree_view_model(file_sync_thread.issues)
        self.ui.treeView.setModel(self.model)

        self.ui.accept_pushButton.clicked.connect(self.accept_changes)
        self.ui.dismiss_pushButton.clicked.connect(self.dismiss_changes)

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

    def closeEvent(self, event):
        self.file_sync_thread.resume()

    def accept_changes(self):
        print('Accepted')

    def dismiss_changes(self):
        print('dismiss')


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = SyncDialogueWindow()
    window.resize(1.61 * 500.0, 500.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

