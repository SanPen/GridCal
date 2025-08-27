# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Tuple
import requests
import sys
import packaging.version as pkg
from VeraGrid.__version__ import __VeraGrid_VERSION__


def find_latest_version(package_name: str = 'VeraGrid'):
    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data["info"]["version"]
    except Exception:
        return None


def check_version(name: str = 'VeraGrid') -> Tuple[int, str]:
    """
    Check package version
    :param name: package name, VeraGrid by default
    :return: version status code, pipy version string

    version status code:
    -2: failure
    -1: this is a newer version
     0: we are ok
    +1: we are behind pipy, we can update
    """

    latest_version = find_latest_version(package_name=name)

    # pipy_version = pkg_resources.parse_version(latest_version)
    # gc_version = pkg_resources.parse_version(__VeraGrid_VERSION__)
    print(f"{name} latest version: {latest_version}")
    pipy_version = pkg.parse(latest_version) if latest_version is not None else None
    gc_version = pkg.parse(__VeraGrid_VERSION__)

    if pipy_version is None:
        # could not connect
        return -2, '0.0.0'
    else:
        if hasattr(pipy_version, 'release'):
            if pipy_version.release is None:
                # could not connect
                return -2, '0.0.0'

    if pipy_version == gc_version:
        # same version, we're up to date
        return 0, latest_version

    elif pipy_version > gc_version:
        # we have an older version, we may update
        return 1, latest_version

    elif pipy_version < gc_version:
        # this version is newer than PiPy's
        return -1, latest_version

    else:
        return 0, latest_version


def get_upgrade_command(latest_version=None):
    """
    Get VeraGrid update command
    :return:
    """
    if latest_version is None:
        latest_version = find_latest_version()
    cmd = [sys.executable, '-m', 'pip', 'install',
           'VeraGrid=={}'.format(latest_version),
           '--upgrade',
           '--no-dependencies']

    return cmd


if __name__ == '__main__':
    is_latest, curr_ver = check_version()
    print('is the latest', is_latest, curr_ver)
