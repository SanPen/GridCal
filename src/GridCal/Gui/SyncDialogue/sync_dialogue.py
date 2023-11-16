
import sys
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt
from GridCal.Gui.SyncDialogue.gui import Ui_Dialog
from GridCal.Gui.Session.synchronization_driver import get_issues_tree_view_model, FileSyncThread


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

        self.model = get_issues_tree_view_model(self.file_sync_thread.issues)
        self.ui.treeView.setModel(self.model)
        self.ui.treeView.expandAll()

        self.ui.accept_selected_pushButton.clicked.connect(self.accept_changes)
        self.ui.reject_selected_pushButton.clicked.connect(self.reject_changes)
        self.ui.doit_pushButton.clicked.connect(self.doit)

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

    def closeEvent(self, event):
        self.file_sync_thread.resume()

    def get_item_level(self, item):

        l = 0
        idx = item
        while idx.parent().data() is not None:
            idx = idx.parent()
            l += 1
        return l

    def set_selection_value(self, value=True):
        """
        Change the selected tree items
        :param value: True / False
        :return: Nothing
        """
        idx = self.ui.treeView.selectedIndexes()

        # filter by indices of level 2
        for i in idx:

            c = i.column()
            r = i.row()

            if c == 0 or c == 5:
                if self.get_item_level(i) == 2:

                    if c == 0:  # if it is the first column process the issue index
                        issue_idx = int(i.data())
                        self.file_sync_thread.issues[issue_idx].__accept__ = value

                    elif c == 5:   # if it is the status column, process the status

                        item = self.ui.treeView.model().itemFromIndex(i)
                        if value:
                            item.setCheckState(Qt.Checked)
                        else:
                            item.setCheckState(Qt.Unchecked)

    def accept_changes(self):
        """
        Accept selected issues
        """
        self.set_selection_value(True)

    def reject_changes(self):
        """
        Reject selected issues
        """
        self.set_selection_value(False)

    def doit(self):
        """
        process issues and close
        """

        self.file_sync_thread.process_issues()
        self.close()


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = SyncDialogueWindow()
    window.resize(1.61 * 500.0, 500.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

