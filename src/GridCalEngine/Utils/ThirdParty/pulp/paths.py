# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
