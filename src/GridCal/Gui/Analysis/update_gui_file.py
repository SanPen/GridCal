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

    convert_resource_file(source='icons.qrc', rcc_cmd=rcc_cmd)

    for f in ['gui.ui']:
        convert_ui_file(source=f, uic_cmd=uic_cmd)


