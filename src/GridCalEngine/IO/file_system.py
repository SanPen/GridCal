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
from pathlib import Path


def get_create_gridcal_folder() -> str:
    """
    Get the home folder of gridCAl, and if it does not exist, create it
    :return: folder path string
    """
    home = str(Path.home())

    gc_folder = os.path.join(home, '.GridCal')

    if not os.path.exists(gc_folder):
        os.makedirs(gc_folder)

    return gc_folder


def opf_file_path() -> str:
    """
    get the OPF files folder path
    :return: str
    """
    d = os.path.join(get_create_gridcal_folder(), 'mip_files')

    if not os.path.exists(d):
        os.makedirs(d)
    return d


def plugins_path() -> str:
    """
    get the plugins file path
    :return: plugins file path
    """
    pth = os.path.join(get_create_gridcal_folder(), 'plugins')

    if not os.path.exists(pth):
        os.makedirs(pth)

    return pth


def tiles_path() -> str:
    """
    get the tiles file path
    :return: tiles file path
    """
    pth = os.path.join(get_create_gridcal_folder(), 'tiles')

    if not os.path.exists(pth):
        os.makedirs(pth)

    return pth


def scripts_path() -> str:
    """
    get the scripts file path
    :return: scripts file path
    """
    pth = os.path.join(get_create_gridcal_folder(), 'scripts')

    if not os.path.exists(pth):
        os.makedirs(pth)

    return pth


def api_keys_path() -> str:
    """
    get the api keys file path
    :return: api keys file path
    """
    pth = os.path.join(get_create_gridcal_folder(), 'api_keys')

    if not os.path.exists(pth):
        os.makedirs(pth)

    return pth
