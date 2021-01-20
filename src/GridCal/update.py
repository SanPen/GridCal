import subprocess
import sys
import pkg_resources
from GridCal.__version__ import __GridCal_VERSION__


def find_latest_version():
    name = 'GridCal'
    latest_version = str(subprocess.run([sys.executable, '-m', 'pip', 'install', '{}==random'.format(name)],
                                        capture_output=True, text=True))
    latest_version = latest_version[latest_version.find('(from versions:') + 15:]
    latest_version = latest_version[:latest_version.find(')')]
    latest_version = latest_version.replace(' ', '').split(',')[-1]
    return latest_version


def check_version():
    """
    Check package version
    :return: version status code, pipy version string

    version status code:
    -2: failure
    -1: this is a newer version
     0: we are ok
    +1: we are behind pipy, we can update
    """

    latest_version = find_latest_version()

    pipy_version = pkg_resources.parse_version(latest_version)
    gc_version = pkg_resources.parse_version(__GridCal_VERSION__)

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
    Get GridCal update command
    :return:
    """
    if latest_version is None:
        latest_version = find_latest_version()
    cmd = [sys.executable, '-m', 'pip', 'install',
           'GridCal=={}'.format(latest_version),
           '--upgrade',
           '--upgrade-strategy only-if-needed']

    return cmd


if __name__ == '__main__':
    is_latest, curr_ver = check_version('GridCal')
    print('is the latest', is_latest, curr_ver)
