import os
import json

from GridCalEngine.IO.file_system import get_create_gridcal_folder


def solvers_config_file_path() -> str:
    """
    get the config file path
    :return: config file path
    """
    return os.path.join(get_create_gridcal_folder(), 'solvers_config.json')


def solvers_config_file_exists() -> bool:
    """
    Check if the config file exists
    :return: True / False
    """
    return os.path.exists(solvers_config_file_path())


def get_solvers_config_data():
    """
    Get server data from the GUI
    :return:
    """
    return {"cplex_bin": "cplex", }


def save_solvers_config():
    """
    Save the GUI configuration
    :return:
    """
    data = get_solvers_config_data()
    with open(solvers_config_file_path(), "w") as f:
        f.write(json.dumps(data, indent=4))


def get_solvers_config():
    """

    :return:
    """
    if solvers_config_file_exists():
        return json.load(open(solvers_config_file_path()))
    else:
        data = get_solvers_config_data()
        save_solvers_config()
        return data
