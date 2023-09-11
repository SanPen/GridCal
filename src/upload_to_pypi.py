

"""

#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-2.30.tar.gz

"""
import os
import sys
from subprocess import call
from GridCalEngine.__version__ import __GridCalEngine_VERSION__
from GridCal.__version__ import __GridCal_VERSION__


def publish(pkg_name: str, setup_path: str, version: str):
    """
    Publish package to Pypi using twine
    :param pkg_name: name of the package (i.e GridCal)
    :param setup_path: path to the package setup.py (i.e. GridCal/setup.py)
    :param version: verison of the package (i.e. 5.1.0)
    """

    # build the tar.gz file
    call([sys.executable, setup_path, 'sdist'])

    # build the .whl file
    # call([sys.executable, setup_path, 'bdist_wheel'])

    name = pkg_name + '-' + str(version) + '.tar.gz'
    fpath = os.path.join('dist', name)

    # check the tar.gz file
    call([sys.executable, '-m', 'twine', 'check', fpath])

    # upload the tar.gz file
    call([sys.executable, '-m', 'twine', 'upload', '--repository', 'pypi', fpath])


if __GridCalEngine_VERSION__ == __GridCal_VERSION__:  # both packages' versions must be exactly the same

    publish(pkg_name='GridCalEngine',
            setup_path=os.path.join('GridCalEngine', 'setup.py'),
            version=__GridCalEngine_VERSION__)

    publish(pkg_name='GridCal',
            setup_path=os.path.join('GridCal', 'setup.py'),
            version=__GridCal_VERSION__)

else:

    print(__GridCalEngine_VERSION__, 'and', __GridCal_VERSION__, "are different :(")
