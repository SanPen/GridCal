# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
import pytest
# from pytestqt.qtbot import QtBot
from PySide6.QtTest import QTest
from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI, QApplication


# @pytest.fixture
# def app(qtbot: QtBot):
#     app = QApplication.instance() if QApplication.instance() else QApplication(sys.argv)
#     main_window = MainGUI()
#     qtbot.addWidget(main_window)
#     return main_window


# def test_gui1(qtbot: QtBot, app: MainGUI):
#     """
#
#     :param qtbot:
#     :param app:
#     :return:
#     """
#     app.open_file_now(filenames=os.path.join("data", "grids", "IEEE57.gridcal"))
#     app.run_power_flow()
#
#     qtbot.waitCallback()
#     QTest.currentAppName()
