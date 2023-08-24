import os
from pathlib import Path


def get_create_roseta_folder():
    """
    Get the home folder of Roseta, and if it does not exist, create it
    :return: folder path string
    """
    home = str(Path.home())

    r_folder = os.path.join(home, '.roseta_grid_converter')

    if not os.path.exists(r_folder):
        os.makedirs(r_folder)

    return r_folder


def get_create_roseta_db_folder():
    """
    Get the home folder of Roseta, and if it does not exist, create it
    :return: folder path string
    """
    home = get_create_roseta_folder()

    r_folder = os.path.join(home, 'lookup_db')

    if not os.path.exists(r_folder):
        os.makedirs(r_folder)

    return r_folder
