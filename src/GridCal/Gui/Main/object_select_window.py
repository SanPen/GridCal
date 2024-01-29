# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

from PySide6 import QtWidgets
import sys


class SampleObject:
    def __init__(self, name='o'):
        self.name = name

    def __str__(self):
        return self.name


class ObjectSelectWindow(QtWidgets.QDialog):
    def __init__(self, title, object_list, parent=None):
        QtWidgets.QDialog.__init__(self, parent)

        self.setWindowTitle(title)

        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        self.object_list = object_list
        self.list_widget = QtWidgets.QListWidget()

        self.selected_object = None

        for i, obj in enumerate(object_list):
            self.list_widget.insertItem(i, obj.name)

        # self.list_widget.clicked.connect(self.clicked)
        self.list_widget.itemDoubleClicked.connect(self.dbl_clicked)
        layout.addWidget(self.list_widget)

    def dbl_clicked(self, qmodelindex):
        """
        Double clicked selection
        :param qmodelindex:
        :return:
        """
        idx = self.list_widget.currentIndex().row()
        if idx > -1:
            print(self.object_list[idx])
            self.selected_object = self.object_list[idx]
            self.close()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    lst = [SampleObject(name='Object {}'.format(i)) for i in range(5)]
    screen = ObjectSelectWindow('Cosas', lst)
    screen.show()
    sys.exit(app.exec_())
