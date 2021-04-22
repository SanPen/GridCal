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

from PySide2.QtWidgets import *
import sys


class SampleObject:
    def __init__(self, name='o'):
        self.name = name

    def __str__(self):
        return self.name


class ObjectSelectWindow(QDialog):
    def __init__(self, title, object_list):
        QDialog.__init__(self)

        self.setWindowTitle(title)

        layout = QGridLayout()
        self.setLayout(layout)
        self.object_list = object_list
        self.list_widget = QListWidget()

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
    app = QApplication(sys.argv)
    lst = [SampleObject(name='Object {}'.format(i)) for i in range(5)]
    screen = ObjectSelectWindow('Cosas', lst)
    screen.show()
    sys.exit(app.exec_())
