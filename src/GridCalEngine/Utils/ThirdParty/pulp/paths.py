# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import json
from typing import Dict

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


def get_solvers_config_data() -> Dict[str, str]:
    """
    Get server data from the GUI
    :return:
    """
    return {"cplex_bin": "cplex", 
            "xpress_bin": "optimizer",
            "gurobi_bin": "gurobi_cl"}


def save_solvers_config() -> None:
    """
    Save the GUI configuration
    :return:
    """
    data = get_solvers_config_data()
    with open(solvers_config_file_path(), "w") as f:
        f.write(json.dumps(data, indent=4))


def get_solvers_config() -> Dict[str, str]:
    """

    :return:
    """
    if solvers_config_file_exists():
        return json.load(open(solvers_config_file_path()))
    else:
        data = get_solvers_config_data()
        save_solvers_config()
        return data
