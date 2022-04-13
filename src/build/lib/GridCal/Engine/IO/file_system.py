import os
from pathlib import Path


def get_create_gridcal_folder():
    """
    Get the home folder of gridCAl, and if it does not exist, create it
    :return: folder path string
    """
    home = str(Path.home())

    gc_folder = os.path.join(home, '.GridCal')

    if not os.path.exists(gc_folder):
        os.makedirs(gc_folder)

    return gc_folder



