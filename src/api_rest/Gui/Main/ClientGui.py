# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from api_rest.Gui.Main.MainWindow import *
import json
import requests
import os.path
import pandas as pd
import sys
from matplotlib import pyplot as plt
import os
os.environ['no_proxy'] = '127.0.0.1,localhost'

__author__ = 'Santiago Peñate Vera'


# shit to be done for this to work in windows
proxyDict = {'no': 'pass',}


"""
This class is the handler of the main gui of GridCal.
"""

########################################################################################################################
# Main Window
########################################################################################################################


def get_list_model(lst, checks=False):
    """
    Pass a list to a list model
    """
    list_model = QStandardItemModel()
    if lst is not None:
        if not checks:
            for val in lst:
                # for the list model
                item = QStandardItem(str(val))
                item.setEditable(False)
                list_model.appendRow(item)
        else:
            for val in lst:
                # for the list model
                item = QStandardItem(str(val))
                item.setEditable(False)
                item.setCheckable(True)
                item.setCheckState(QtCore.Qt.Checked)
                list_model.appendRow(item)

    return list_model


class MainGUI(QMainWindow):

    def __init__(self, parent=None, url='http://0.0.0.0:5000'):
        """

        @param parent:
        """

        # create main window
        QWidget.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)

        self.url = url

        #  Buttons
        self.ui.refresh_items_pushButton.clicked.connect(self.update_list)
        self.ui.send_pushButton.clicked.connect(self.send)

        # call action
        self.ui.url_lineEdit.setText(self.url)

        try:
            self.get_grid_name()
            self.update()
            self.update_voltages()
        except:
            self.msg('Could not connect to ' + self.url, 'Connection')

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

    def get_grid_name(self):
        """
        Get the grid name
        Returns:

        """
        response = requests.get(self.url + '/grid_name', proxies=proxyDict)
        if response.status_code == 200:
            jData = json.loads(response.content.decode('UTF-8'))
            print(jData)
            self.ui.status_label.setText(str(jData))
        else:
            print('error', response)

    def update_list(self):
        """
        Update the values
        Returns:

        """

        # pick URL from GUI
        self.url = self.ui.url_lineEdit.text().strip()

        response = requests.get(self.url + '/loads_list', proxies=proxyDict)
        if response.status_code == 200:
            jData = json.loads(response.content.decode('UTF-8'))

            lst = jData['loads']

            mdl = get_list_model(lst)
            self.ui.items_listView.setModel(mdl)

            print(jData)
        else:
            print('error', response)

    def send(self):
        """
        Send data
        Returns:

        """

        if len(self.ui.items_listView.selectedIndexes()) > 0:
            idx = self.ui.items_listView.selectedIndexes()[0].row()

            mx = self.ui.max_val_doubleSpinBox.value()
            val = self.ui.value_horizontalSlider.value() / 100.0
            P = mx * val
            Q = 0.8 * P

            data = {'idx': idx, 'P': P, 'Q': Q}
            response = requests.post(self.url + '/set_load', json=data, proxies=proxyDict)
            if response.status_code == 200:
                jData = json.loads(response.content.decode('UTF-8'))

                self.ui.status_label.setText(str(jData))

                print(jData)

                self.update_voltages()
            else:
                print('error', response)

            self.ui.status_label.setText('Response: ' + str(response))

    def update_voltages(self):
        """

        Returns:

        """
        response = requests.get(self.url + '/voltages', proxies=proxyDict)
        if response.status_code == 200:
            jData = json.loads(response.content.decode('UTF-8'))

            voltages = jData['val']

            print(voltages)

            self.ui.status_label.setText(str(response.status_code))

            # clear the plot display
            self.ui.resultsPlot.clear()

            # get the plot axis
            ax = self.ui.resultsPlot.get_axis()

            df = pd.DataFrame(data=voltages)
            df.fillna(0, inplace=True)
            df.plot(ax=ax, kind='bar')
            ax.axhline(0.9, c='r', alpha=0.7)
            ax.axhline(1.1, c='r', alpha=0.7)

            self.ui.resultsPlot.redraw()

        else:
            print('error', response)


def run():
    """
    Main function to run the GUI
    :return: 
    """
    print('loading...')
    app = QApplication(sys.argv)
    # url = 'http://192.168.1.103:5000'
    # url = 'http://192.168.197.22:5000'
    url = 'http://127.0.0.1:5000'
    window = MainGUI(url=url)
    window.resize(1.61 * 700.0, 700.0)  # golden ratio :)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run()
