

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


def publish(pkg_name='GridCal', setup_path='setup.py', version='0.0.1'):
    """
    Publish package to Pypi using twine
    :param pkg_name:
    :param setup_path:
    :param version:
    """
    call([sys.executable, setup_path, 'sdist'])
    call([sys.executable, setup_path, 'bdist_wheel'])

    name = pkg_name + '-' + str(version) + '.tar.gz'
    fpath = os.path.join('dist', name)

    call([sys.executable, '-m', 'twine', 'check', fpath])

    call([sys.executable, '-m', 'twine', 'upload', '--repository', 'pypi', fpath])


if __GridCalEngine_VERSION__ == __GridCal_VERSION__:

    # both packages' versions must be exactly the same

    publish(pkg_name='GridCalEngine',
            setup_path=os.path.join('GridCalEngine', 'setup.py'),
            version=__GridCalEngine_VERSION__)

    publish(pkg_name='GridCal',
            setup_path=os.path.join('GridCal', 'setup.py'),
            version=__GridCal_VERSION__)

else:

    print(__GridCalEngine_VERSION__, 'and', __GridCal_VERSION__, "are different :(")
