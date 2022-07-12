"""
Script to update correctly the main GUI (.py) file from the Qt design (.ui) file
"""
import os
from GridCal.Gui.update_gui_common import convert_resource_file, convert_ui_file

if __name__ == '__main__':

    rcc_cmd = 'pyside2-rcc'
    uic_cmd = 'pyside2-uic'

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
