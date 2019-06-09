import PySide2
from GridCal.Engine import *

import os


def test_all_grids():

    curr_path = os.path.dirname(__file__)  # get the directory of this file
    grids_path = os.path.join(curr_path, '..', '..', 'Grids_and_profiles', 'grids')  # navigate to the grids folder

    files = os.listdir(grids_path)
    failed = list()
    for file_name in files:

        path = os.path.join(grids_path, file_name)

        print('-' * 160)
        print('Loading', file_name, '...', end='')
        try:
            file_handler = FileOpen(path)
            circuit = file_handler.open()
            circuit.compile()
            print('ok')
        except:
            print('Failed')
            failed.append(file_name)

    print('Failed:')
    for f in failed:
        print('\t', f)

    for f in failed:
        print('Attempting', f)
        path = os.path.join(grids_path, f)
        file_handler = FileOpen(path)
        circuit = file_handler.open()
        circuit.compile()

    assert len(failed) == 0
