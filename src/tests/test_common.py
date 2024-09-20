import numpy as np
from GridCalEngine.Utils.NumericalMethods.common import find_closest_number


def test_find_closest_number():

    arr = np.arange(1, 10, 0.1)
    # print(arr)

    """
    0	1
    1	1,1
    2	1,2
    3	1,3
    4	1,4
    5	1,5
    6	1,6
    7	1,7
    8	1,8
    9	1,9
    10	2
    11	2,1
    12	2,2
    13	2,3
    14	2,4
    15	2,5
    16	2,6
    17	2,7
    18	2,8
    19	2,9
    20	3
    21	3,1
    22	3,2
    23	3,3
    24	3,4
    25	3,5
    26	3,6
    27	3,7
    28	3,8
    29	3,9
    30	4
    31	4,1
    32	4,2
    33	4,3
    34	4,4
    35	4,5
    36	4,6
    37	4,7
    38	4,8
    39	4,9
    40	5
    41	5,1
    42	5,2
    43	5,3
    44	5,4
    45	5,5
    46	5,6
    47	5,7
    48	5,8
    49	5,9
    50	6
    51	6,1
    52	6,2
    53	6,3
    54	6,4
    55	6,5
    56	6,6
    57	6,7
    58	6,8
    59	6,9
    60	7
    61	7,1
    62	7,2
    63	7,3
    64	7,4
    65	7,5
    66	7,6
    67	7,7
    68	7,8
    69	7,9
    70	8
    71	8,1
    72	8,2
    73	8,3
    74	8,4
    75	8,5
    76	8,6
    77	8,7
    78	8,8
    79	8,9
    80	9
    81	9,1
    82	9,2
    83	9,3
    84	9,4
    85	9,5
    86	9,6
    87	9,7
    88	9,8
    89	9,9
    90	10
    """

    # test upper outside bounds
    target = 11
    idx, val = find_closest_number(arr, target)

    assert idx == len(arr) -1
    assert val == arr[len(arr)-1]

    # test lower outside bounds
    target = 0.3
    idx, val = find_closest_number(arr, target)

    assert idx == 0
    assert val == arr[0]

    # test some middle points
    target = 3.95
    idx, val = find_closest_number(arr, target)

    assert idx == 30
    assert val == arr[30]

    target = 3.91
    idx, val = find_closest_number(arr, target)

    assert idx == 29
    assert val == arr[29]