# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
import ctypes
import threading
PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))
from VeraGrid.__version__ import about_msg

# NOTE: For some reason I cannot begin to comprehend, the activation fails on windows if called before the GUI...
import VeraGridEngine.Utils.ThirdParty.gslv.gslv_activation

from VeraGrid.Gui.Main.VeraGridMain import runVeraGrid

import platform

if platform.system() == 'Windows':
    # this makes the icon display properly under windows
    myappid = 'mycompany.myproduct.subproduct.version'  # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

if __name__ == "__main__":
    print('Loading VeraGrid...')
    print(about_msg)

    # Set the application style to the clear theme
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    # os.environ["QT_QPA_PLATFORMTHEME"] = "qt5ct"  # this forces QT-only menus and look and feel
    threading.stack_size(134217728)
    runVeraGrid()