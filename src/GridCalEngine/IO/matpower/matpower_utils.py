# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, Tuple, List, Union
import numpy as np
import pandas as pd
from GridCalEngine.basic_structures import Logger


def find_between(s: str, first: str, last: str) -> str:
    """
    Find sting between two sub-strings
    Args:
        s: Main string
        first: first sub-string
        last: second sub-string
    Example find_between('[Hello]', '[', ']')  -> returns 'Hello'
    Returns:
        String between the first and second sub-strings, if any was found otherwise returns an empty string
    """
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""


def txt2mat(txt: str, line_splitter=';', to_float=True):
    """

    :param txt:
    :param line_splitter:
    :param to_float:
    :return:
    """
    lines = txt.strip().split('\n')
    # del lines[-1]

    # preprocess lines (remove the comments)
    lines2 = list()
    for i, line in enumerate(lines):
        if line.lstrip()[0] != '%':
            lines2.append(line)
        else:
            # print('skipping', line)
            pass

    # convert the lines to data
    nrows = len(lines2)
    arr = None
    for i, line in enumerate(lines2):

        if ';' in line:
            line2 = line.split(line_splitter)[0]
        else:
            line2 = line

        vec = line2.strip().split()

        # declare the container array based on the first line
        if arr is None:
            ncols = len(vec)
            if to_float:
                arr = np.zeros((nrows, ncols))
            else:
                arr = np.zeros((nrows, ncols), dtype=object)

        # fill-in the data
        for j, val in enumerate(vec):
            if to_float:
                arr[i, j] = float(val)
            else:
                arr[i, j] = val.strip().replace("'", "")

    return np.array(arr)
