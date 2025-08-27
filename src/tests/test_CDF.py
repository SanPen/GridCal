import numpy as np
from numpy import random
import VeraGridEngine as gce

def test_CDF_expectation():

    x = random.normal(4, 1, size=20)

    assert np.allclose(x.mean(), gce.CDF(x).expectation(), atol=1e-5)

    x = random.rand(200)

    assert np.allclose(x.mean(), gce.CDF(x).expectation(), atol=1e-5)
