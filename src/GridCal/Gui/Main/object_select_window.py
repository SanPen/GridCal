# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


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
    sys.exit(app.exec())
