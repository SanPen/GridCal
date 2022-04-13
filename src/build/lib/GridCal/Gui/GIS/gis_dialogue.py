import sys
import os
from PySide2.QtWidgets import *
import folium
from shutil import copyfile
import webbrowser

try:
    from PySide2.QtWebEngineWidgets import QWebEngineView as QWebView, QWebEnginePage as QWebPage
    qt_web_engine_available = True
except ModuleNotFoundError:
    qt_web_engine_available = False
    print('QtWebEngineWidgets not found :(')

from GridCal.Gui.GIS.gui import *
from GridCal.Engine.IO.file_system import get_create_gridcal_folder


class GISWindow(QMainWindow):

    def __init__(self, external_file_path=''):
        """
        Constructor
        :param external_file_path: path to the file to open
        """
        QMainWindow.__init__(self)
        self.ui = Ui_GisWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('GridCal - GIS')

        if os.path.exists(external_file_path):
            self.file_path = external_file_path
        else:
            self.file_path = self.generate_blank_map_html(lon_avg=40.430, lat_avg=3.56)

        # create web browser for the map
        if qt_web_engine_available:
            self.web_layout = QtWidgets.QVBoxLayout(self.ui.webFrame)
            self.webView = QWebView()
            self.web_layout.addWidget(self.webView)
            self.ui.webFrame.setContentsMargins(0, 0, 0, 0)
            self.web_layout.setContentsMargins(0, 0, 0, 0)
            self.webView.setUrl(QtCore.QUrl.fromLocalFile(self.file_path))
        else:
            webbrowser.open('file://' + self.file_path)

        # # action linking
        self.ui.actionSave_map.triggered.connect(self.save)

    def closeEvent(self, event):
        """
        Remove the file on close
        :param event:
        """
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def save(self):
        """
        Save a copy of the displayed map
        :return:
        """
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog

        file, filter = QFileDialog.getSaveFileName(self, "Save map", '',
                                                   filter="html (*.html)",
                                                   options=options)

        if file != '':
            if not file.endswith('.html'):
                file += '.html'

            copyfile(self.file_path, file)

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

    @staticmethod
    def generate_blank_map_html(lon_avg, lat_avg):
        """
        Generate a blank HTML map file
        :param lon_avg: center longitude
        :param lat_avg: center latitude
        :return: file name
        """
        my_map = folium.Map(location=[lon_avg, lat_avg], zoom_start=5)

        gc_path = get_create_gridcal_folder()

        path = os.path.join(gc_path, 'map.html')

        my_map.save(path)

        return path


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = GISWindow()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

