# -*- coding: utf-8 -*-
"""
Created on Fri Jun 24 17:55:37 2016

@author: santi
"""

try:
    import cython_example
except:
    # if the extension is not compiled, then compile it
    import os
    path = os.path.dirname(os.path.realpath(__file__))
    import pyximport

    pyximport.install(build_dir=path)

    import cython_example

import numpy as np
import cython_example


import time


np.random.seed(0)
data = np.random.randn(2000, 2000)

a = time.time()
res = cython_example.busca_min_(data)

print((time.time() - a) * 1000, ' ms')
print('Minimum:',res)