import sys
import xlrd

from PySide2 import QtCore, QtGui, QtWidgets

from GridCal.Engine.Devices.meta_devices import DeviceType
from GridCal.Gui.Main.SmartSearch import *
from GridCal.Gui.GuiFunctions import *


class SmartSearchDialogue(QtWidgets.QDialog):

    def __init__(self, objects, attributes, parent=None):
        """

        :param objects:
        :param attributes:
        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_SmartSearch()
        self.ui.setupUi(self)

        self.objects = objects
        self.ui.property_comboBox.addItems(attributes)

        # click
        self.ui.filter_pushButton.clicked.connect(self.filter)
        self.ui.delete_pushButton.clicked.connect(self.delete)
        self.ui.reduce_pushButton.clicked.connect(self.reduce)

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

    def display(self, elements):
        """

        :param elements:
        :return:
        """
        if len(elements) > 0:

            elm = elements[0]

            if elm.device_type in [DeviceType.BranchDevice, DeviceType.SequenceLineDevice,
                                   DeviceType.UnderGroundLineDevice]:

                mdl = BranchObjectModel(elements, elm.editable_headers,
                                        parent=self.ui.tableView, editable=False,
                                        non_editable_attributes=elm.non_editable_attributes)
            else:

                mdl = ObjectsModel(elements, elm.editable_headers,
                                   parent=self.ui.tableView, editable=False,
                                   non_editable_attributes=elm.non_editable_attributes)

            self.ui.tableView.setModel(mdl)

        else:

            self.ui.tableView.setModel(None)

    def filter(self):
        """
        Filter
        """

        if len(self.objects) > 0:
            command = self.ui.lineEdit.text().lower()
            attr = self.ui.property_comboBox.currentText()

            elm = self.objects[0]
            tpe = elm.editable_headers[attr].tpe

            filtered_objects = list()

            if command.startswith('>'):
                # greater than selection
                args = command.replace('>', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.objects if getattr(x, attr) > args]

            elif command.startswith('<'):
                # "less than" selection
                args = command.replace('<', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.objects if getattr(x, attr) < args]

            elif command.startswith('>='):
                # greater or equal than selection
                args = command.replace('>=', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.objects if getattr(x, attr) >= args]

            elif command.startswith('<='):
                # "less or equal than" selection
                args = command.replace('<=', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.objects if getattr(x, attr) <= args]

            elif command.startswith('*'):
                # "like" selection

                if tpe == str:
                    args = command.replace('*', '').strip()

                    try:
                        args = tpe(args)
                    except:
                        self.msg('Could not parse the argument for the data type')
                        return

                    filtered_objects = [x for x in self.objects if args in getattr(x, attr).lower()]
                else:
                    self.msg('This filter type is only valid for strings')

            elif command.startswith('=='):
                # Exact match
                args = command.replace('==', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                if tpe == str:
                    filtered_objects = [x for x in self.objects if getattr(x, attr).lower() == args]
                else:
                    filtered_objects = [x for x in self.objects if getattr(x, attr) == args]

            elif command.startswith('!='):
                # Exact match
                args = command.replace('==', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                if tpe == str:
                    filtered_objects = [x for x in self.objects if getattr(x, attr).lower() != args]
                else:
                    filtered_objects = [x for x in self.objects if getattr(x, attr) != args]

            else:
                filtered_objects = self.objects

            self.display(filtered_objects)

        else:
            # nothing to search
            pass

    def delete(self):
        pass

    def reduce(self):
        pass


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SmartSearchDialogue()
    window.show()
    sys.exit(app.exec_())
