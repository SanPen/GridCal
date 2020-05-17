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

from PySide2 import QtWidgets


def info_msg(text, title="Information"):
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Information)
    msg.setText(text)
    msg.setWindowTitle(title)
    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
    return msg.exec_()


def warning_msg(text, title="Warning"):
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Warning)
    msg.setText(text)
    msg.setWindowTitle(title)
    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
    return msg.exec_()


def error_msg(text, title="Error"):
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Critical)
    msg.setText(text)
    msg.setWindowTitle(title)
    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
    return msg.exec_()


def yes_no_question(text, title='Question'):
    """
    Question message
    :param text:
    :param title:
    :return: True / False
    """
    buttonReply = QtWidgets.QMessageBox.question(None,
                                                 title,
                                                 text,
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                                 QtWidgets.QMessageBox.No)
    return buttonReply == QtWidgets.QMessageBox.Yes
