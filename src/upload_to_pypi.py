

"""

#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-2.30.tar.gz

"""

from subprocess import call
from GridCal.__version__ import __GridCal_VERSION__

import os
import sys

call([sys.executable, 'setup_gridcal.py', 'sdist'])

call([sys.executable, 'setup_gridcal.py', 'bdist_wheel'])

name = 'GridCal-' + str(__GridCal_VERSION__) + '.tar.gz'
fpath = os.path.join('dist', name)

call([sys.executable, '-m', 'twine', 'check', fpath])

call([sys.executable, '-m', 'twine', 'upload', '--repository', 'pypi', fpath])

