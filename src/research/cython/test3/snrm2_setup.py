#!/usr/bin/env python

import os
# from skimage._build \
import cython

base_path = os.path.abspath(os.path.dirname(__file__))

def configuration(parent_package='', top_path=None):
    from numpy.distutils.misc_util import Configuration, get_numpy_include_dirs

    config = Configuration()

    cython(['snrm2_.pyx'], working_path=base_path)
    config.add_extension('snrm2_', sources=['snrm2_.c'],
                         include_dirs=[get_numpy_include_dirs()],
                         libraries=['blas'],
                        )

    return config

if __name__ == '__main__':
    from numpy.distutils.core import setup
    setup(**(configuration(top_path='').todict()))