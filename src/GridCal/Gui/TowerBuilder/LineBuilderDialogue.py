# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import sys

from PySide2.QtWidgets import *

from GridCal.Gui.TowerBuilder.gui import *
from GridCal.Engine.Devices import *
from GridCal.Gui.TowerBuilder.tower_model import *
from GridCal.Gui.GuiFunctions import PandasModel
from GridCal.Gui.GeneralDialogues import LogsDialogue


class TowerBuilderGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, tower=None, wires_catalogue=list()):
        """
        Constructor
        Args:
            parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Line builder')

        # 10:1
        self.ui.main_splitter.setStretchFactor(0, 8)
        self.ui.main_splitter.setStretchFactor(1, 2)

        # create wire collection from the catalogue
        self.wires_table = WiresTable(self)
        for wire in wires_catalogue:
            self.wires_table.add(wire)

        # was there a tower passed? else create one
        if tower is None:
            self.tower_driver = TowerModel(self, edit_callback=self.plot)
        else:
            self.tower_driver = TowerModel(self, edit_callback=self.plot, tower=tower)

        self.ui.name_lineEdit.setText(self.tower_driver.tower.name)
        self.ui.rho_doubleSpinBox.setValue(self.tower_driver.tower.earth_resistivity)

        # set models
        self.ui.wires_tableView.setModel(self.wires_table)
        self.ui.tower_tableView.setModel(self.tower_driver)

        # button clicks
        # self.ui.add_wire_pushButton.clicked.connect(self.add_wire_to_collection)
        # self.ui.delete_wire_pushButton.clicked.connect(self.delete_wire_from_collection)
        self.ui.add_to_tower_pushButton.clicked.connect(self.add_wire_to_tower)
        self.ui.delete_from_tower_pushButton.clicked.connect(self.delete_wire_from_tower)
        self.ui.compute_pushButton.clicked.connect(self.compute)

        self.ui.name_lineEdit.textChanged.connect(self.name_changed)

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

    def name_changed(self):
        """
        Change name
        :return:
        """
        self.tower_driver.tower.tower_name = self.ui.name_lineEdit.text()

    def add_wire_to_collection(self):
        """
        Add new wire to collection
        :return:
        """
        name = 'Wire_' + str(len(self.wires_table.wires) + 1)
        wire = Wire(name=name, gmr=0.01, r=0.01, x=0)
        self.wires_table.add(wire)

    def delete_wire_from_collection(self):
        """
        Delete wire from the collection
        :return:
        """
        idx = self.ui.wires_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:

            # delete all the wires from the tower too
            self.tower_driver.delete_by_name(self.wires_table.wires[sel_idx])

            # delete from the catalogue
            self.wires_table.delete(sel_idx)

            self.plot()
        else:
            self.msg('Select a wire in the wires catalogue')

    def add_wire_to_tower(self):
        """
        Add wire to tower
        :return:
        """
        idx = self.ui.wires_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:
            selected_wire = self.wires_table.wires[sel_idx].copy()
            self.tower_driver.add(WireInTower(selected_wire))
        else:
            self.msg('Select a wire in the wires catalogue')

    def delete_wire_from_tower(self):
        """
        Delete wire from the tower
        :return:
        """
        idx = self.ui.tower_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:
            self.tower_driver.delete(sel_idx)

            self.plot()
        else:
            self.msg('Select a wire from the tower')

    def compute(self):
        """

        :return:
        """

        self.tower_driver.tower.frequency = self.ui.frequency_doubleSpinBox.value()
        self.tower_driver.tower.earth_resistivity = self.ui.rho_doubleSpinBox.value()

        # heck the wires configuration
        logs = Logger()
        all_ok = self.tower_driver.tower.check(logs)

        if not all_ok:
            logger_diag = LogsDialogue(name='Tower computation', logs=logs)
            logger_diag.exec_()
        else:
            try:
                # compute the matrices
                self.tower_driver.tower.compute()

                # Impedances in Ohm/km
                cols = ['Phase' + str(i) for i in self.tower_driver.tower.z_phases_abcn]
                z_df = pd.DataFrame(data=self.tower_driver.tower.z_abcn, columns=cols, index=cols)
                self.ui.z_tableView_abcn.setModel(PandasModel(z_df))

                cols = ['Phase' + str(i) for i in self.tower_driver.tower.z_phases_abc]
                z_df = pd.DataFrame(data=self.tower_driver.tower.z_abc, columns=cols, index=cols)
                self.ui.z_tableView_abc.setModel(PandasModel(z_df))

                cols = ['Sequence ' + str(i) for i in range(3)]
                z_df = pd.DataFrame(data=self.tower_driver.tower.z_seq, columns=cols, index=cols)
                self.ui.z_tableView_seq.setModel(PandasModel(z_df))

                # Admittances in uS/km
                cols = ['Phase' + str(i) for i in self.tower_driver.tower.y_phases_abcn]
                z_df = pd.DataFrame(data=self.tower_driver.tower.y_abcn * 1e6, columns=cols, index=cols)
                self.ui.y_tableView_abcn.setModel(PandasModel(z_df))

                cols = ['Phase' + str(i) for i in self.tower_driver.tower.y_phases_abc]
                z_df = pd.DataFrame(data=self.tower_driver.tower.y_abc * 1e6, columns=cols, index=cols)
                self.ui.y_tableView_abc.setModel(PandasModel(z_df))

                cols = ['Sequence ' + str(i) for i in range(3)]
                z_df = pd.DataFrame(data=self.tower_driver.tower.y_seq * 1e6, columns=cols, index=cols)
                self.ui.y_tableView_seq.setModel(PandasModel(z_df))

                # plot
                self.plot()

            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.msg(str(exc_traceback) + '\n' + str(exc_value), 'Tower calculation')

    def plot(self):
        """
        PLot the tower distribution
        """
        self.ui.plotwidget.clear()

        fig = self.ui.plotwidget.get_figure()
        fig.set_facecolor('white')
        ax = self.ui.plotwidget.get_axis()

        self.tower_driver.tower.plot(ax=ax)
        self.ui.plotwidget.redraw()

    def example_1(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        wire = Wire(name=name, gmr=gmr, r=r, x=x)

        self.tower_driver.add(WireInTower(wire=wire, xpos=0, ypos=8.8392, phase=0))
        self.tower_driver.add(WireInTower(wire=wire, xpos=0.762, ypos=8.8392, phase=1))
        self.tower_driver.add(WireInTower(wire=wire, xpos=2.1336, ypos=8.8392, phase=2))
        self.tower_driver.add(WireInTower(wire=wire, xpos=1.2192, ypos=7.62, phase=3))

        self.wires_table.add(wire)

    def example_2(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        incx = 0.1
        incy = 0.1

        wire = Wire(name=name, gmr=gmr, r=r, x=x)

        self.tower_driver.add(WireInTower(wire, xpos=0, ypos=8.8392, phase=1))
        self.tower_driver.add(WireInTower(wire, xpos=0.762, ypos=8.8392, phase=2))
        self.tower_driver.add(WireInTower(wire,  xpos=2.1336, ypos=8.8392, phase=3))
        self.tower_driver.add(WireInTower(wire,  xpos=1.2192, ypos=7.62, phase=0))

        self.tower_driver.add(WireInTower(wire,  xpos=incx + 0, ypos=8.8392, phase=1))
        self.tower_driver.add(WireInTower(wire,  xpos=incx + 0.762, ypos=8.8392, phase=2))
        self.tower_driver.add(WireInTower(wire,  xpos=incx + 2.1336, ypos=8.8392, phase=3))
        # self.tower.add(Wire(name, xpos=incx+1.2192, ypos=7.62, gmr=gmr, r=r, x=x, phase=0))

        self.tower_driver.add(WireInTower(wire,  xpos=incx / 2 + 0, ypos=incy + 8.8392, phase=1))
        self.tower_driver.add(WireInTower(wire,  xpos=incx / 2 + 0.762, ypos=incy + 8.8392, phase=2))
        self.tower_driver.add(WireInTower(wire,  xpos=incx / 2 + 2.1336, ypos=incy + 8.8392, phase=3))
        # self.tower.add(Wire(name, xpos=incx/2 + 1.2192, ypos=incy+7.62, gmr=gmr, r=r, x=x, phase=0))

        self.wires_table.add(wire)


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = TowerBuilderGUI()

    window.example_2()
    window.compute()

    window.resize(1.81 * 700.0, 700.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

