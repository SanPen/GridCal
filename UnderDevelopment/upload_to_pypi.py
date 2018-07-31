

"""

#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-2.30.tar.gz

"""

from subprocess import call
from GridCal.__version__ import __GridCal_VERSION__

import os

if os.name == 'nt':
    call(['python', 'setup.py', 'sdist'])
else:
    call(['python3', 'setup.py', 'sdist'])

call(['twine', 'upload', 'dist/GridCal-' + str(__GridCal_VERSION__) + '.tar.gz'])
