# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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
