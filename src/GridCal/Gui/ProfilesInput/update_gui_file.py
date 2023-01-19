"""
Script to update correctly the main GUI (.py) file from the Qt design (.ui) file
"""
from GridCal.Gui.update_gui_common import convert_resource_file, convert_ui_file

if __name__ == '__main__':
    convert_resource_file(source='icons.qrc')
    for f in ['profiles_from_data_gui.ui', 'profiles_from_models_gui.ui']:
        convert_ui_file(source=f)
