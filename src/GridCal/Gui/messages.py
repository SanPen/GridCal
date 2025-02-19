# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from PySide6 import QtWidgets


def info_msg(text, title="Information"):
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
    msg.setText(text)
    msg.setWindowTitle(title)
    msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    return msg.exec()


def warning_msg(text, title="Warning"):
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    msg.setText(text)
    msg.setWindowTitle(title)
    msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    return msg.exec()


def error_msg(text, title="Error"):
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    msg.setText(text)
    msg.setWindowTitle(title)
    msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    return msg.exec()


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
                                                 QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                                 QtWidgets.QMessageBox.StandardButton.No)
    return buttonReply == QtWidgets.QMessageBox.StandardButton.Yes.value
