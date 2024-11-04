# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Script to update correctly the main GUI (.py) file from the Qt design (.ui) file
"""
import os
from GridCal.Gui.update_gui_common import convert_resource_file, convert_ui_file

if __name__ == '__main__':
    # pyrcc5 icons.qrc -o icons_rc.py
    # pyuic5 -x MainWindow.ui -o MainWindow.py

    rcc_cmd = 'pyside6-rcc'
    uic_cmd = 'pyside6-uic'

    if os.name == 'nt':
        rcc_cmd += '.exe'
        uic_cmd += '.exe'

    convert_resource_file(source='icons.qrc', rcc_cmd=rcc_cmd)
    for f in ['MainWindow.ui', 'ConsoleLog.ui']:
        convert_ui_file(source=f, uic_cmd=uic_cmd)
