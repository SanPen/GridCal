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

    rcc_cmd = 'pyside6-rcc'
    uic_cmd = 'pyside6-uic'

    if os.name == 'nt':
        rcc_cmd += '.exe'
        uic_cmd += '.exe'

    dir_path = os.path.dirname(os.path.realpath(__file__))

    for subFolderRoot, foldersWithinSubFolder, files in os.walk(dir_path):

        for fileName in files:
            fname = os.path.join(subFolderRoot, fileName)

            if fileName.endswith('.qrc'):
                print(fname)
                convert_resource_file(source=fname, rcc_cmd=rcc_cmd)
            elif fileName.endswith('.ui'):
                print(fname)
                convert_ui_file(source=fname, uic_cmd=uic_cmd)
