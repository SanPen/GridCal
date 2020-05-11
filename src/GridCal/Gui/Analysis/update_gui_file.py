"""
Script to update correctly the main GUI (.py) file from the Qt design (.ui) file
"""
import os
import sys
from subprocess import call

if __name__ == '__main__':
    # pyrcc5 icons.qrc -o icons_rc.py
    # pyuic5 -x MainWindow.ui -o MainWindow.py

    py = sys.executable
    folder = os.path.dirname(py)
    f1 = folder.split(os.sep)[-1]

    if f1 == 'bin':
        fbase = folder
        script_name = 'pyside2-uic'
    else:
        fbase = os.path.join(folder, 'Scripts')
        script_name = 'pyside2-uic-script.py'

    # update icon/images resources
    # call([py, os.path.join(fbase, 'pyside2-rcc'), 'icons.qrc', '-o', 'icons_rc.py'])

    #  update files
    file_names_ui = ['gui.ui']
    file_names = ['gui.py']

    for filename, filename_ui in zip(file_names, file_names_ui):

        # update ui handler file
        call([py, os.path.join(fbase, script_name), '-x', filename_ui, '-o', filename])

        # replace annoying text import
        # Read in the file
        with open(filename, 'r') as file:
            file_data = file.read()

        # Replace the target string
        file_data = file_data.replace('import icons_rc', 'from .icons_rc import *')

        # Write the file out again
        with open(filename, 'w') as file:
            file.write(file_data)
