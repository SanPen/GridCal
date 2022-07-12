"""
Script to update correctly the main GUI (.py) file from the Qt design (.ui) file
"""
from GridCal.Gui.update_gui_common import convert_resource_file, convert_ui_file

if __name__ == '__main__':
    # pyrcc5 icons.qrc -o icons_rc.py
    # pyuic5 -x MainWindow.ui -o MainWindow.py

    convert_resource_file(source='icons.qrc')
    for f in ['MainWindow.ui', 'ConsoleLog.ui', 'banner.ui']:
        convert_ui_file(source=f)
