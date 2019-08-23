import pandas as pd
from numpy import angle, c_
from numpy.core._multiarray_umath import array


def res_2_df(complex_bus_voltages, complex_bus_powers, bus_types):
    """
    Create data frame to display the results nicely

    :param complex_bus_voltages: List of complex voltages
    :param complex_bus_powers: List of complex powers
    :param bus_types: List of bus types

    :return: Pandas DataFrame
    """
    vm = abs(complex_bus_voltages)
    va = angle(complex_bus_voltages)

    d = {1: 'PQ', 2: 'PV', 3: 'VD'}

    tpe_str = array([d[i] for i in bus_types], dtype=object)
    data = c_[tpe_str, complex_bus_powers.real, complex_bus_powers.imag, vm, va]
    cols = ['Type', 'P', 'Q', '|V|', 'angle']
    data_frame = pd.DataFrame(data=data, columns=cols)

    return data_frame
